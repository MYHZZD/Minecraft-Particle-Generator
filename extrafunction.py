import math
import numpy as np
import mido
from mido import MidiFile


def process_midi_file(midi_file_path):
    # 读取MIDI文件基本信息
    midi = MidiFile(midi_file_path)
    ticks_per_beat = midi.ticks_per_beat

    # 创建基于绝对时间轴的速度事件表
    tempo_events = []
    found_tempo = False

    # 遍历所有轨道寻找速度事件
    for track_index, track in enumerate(midi.tracks):
        if not track:  # 跳过空轨道
            continue

        absolute_tick = 0
        for msg in track:
            absolute_tick += msg.time
            if msg.type == "set_tempo":
                tempo_events.append(
                    {"tick": absolute_tick, "bpm": mido.tempo2bpm(msg.tempo)}
                )
                found_tempo = True

    # 如果没有任何速度事件，添加默认的150 BPM
    if not found_tempo:
        tempo_events.append({"tick": 0, "bpm": 150})

    # 字典去重并按时间排序速度事件
    temp_dict = {}
    for event in tempo_events:
        temp_dict[event["tick"]] = event["bpm"]
    tempo_events = [
        {"tick": tick, "bpm": bpm} for tick, bpm in sorted(temp_dict.items())
    ]

    # 处理所有轨道音符
    tracks = []

    for track_index, track in enumerate(midi.tracks):
        if not track:
            continue

        absolute_tick = 0
        active_notes = {}  # 跟踪活动的音符: (channel, note) -> start_tick
        track_notes = []  # 存储音符事件
        track_cc = []  # 存储CC事件

        for msg in track:
            absolute_tick += msg.time

            # 处理音符事件
            if msg.type == "note_on" and msg.velocity > 0:
                key = (msg.channel, msg.note)
                active_notes[key] = {
                    "start_tick": absolute_tick,
                    "velocity": msg.velocity,
                }

            elif msg.type == "note_off" or (
                msg.type == "note_on" and msg.velocity == 0
            ):
                key = (msg.channel, msg.note)
                if key in active_notes:
                    note_start = active_notes.pop(key)
                    duration = absolute_tick - note_start["start_tick"]

                    track_notes.append(
                        {
                            "start_tick": note_start["start_tick"],
                            "duration": duration,
                            "end_tick": absolute_tick,
                            "note": msg.note,
                            "channel": msg.channel,
                            "velocity": note_start["velocity"],
                        }
                    )

            # 处理CC事件
            elif msg.type == "control_change":
                track_cc.append(
                    {
                        "tick": absolute_tick,
                        "channel": msg.channel,
                        "control": msg.control,
                        "value": msg.value,
                    }
                )

        # 处理未结束的音符
        for (channel, note), note_start in active_notes.items():
            duration = absolute_tick - note_start["start_tick"]
            track_notes.append(
                {
                    "start_tick": note_start["start_tick"],
                    "duration": duration,
                    "end_tick": absolute_tick,
                    "note": note,
                    "channel": channel,
                    "velocity": note_start["velocity"],
                }
            )

        # 按开始时间排序
        track_notes.sort(key=lambda x: x["start_tick"])
        track_cc.sort(key=lambda x: x["tick"])

        # 对CC去重
        cc_dic = {}
        for event in track_cc:
            cc_dic[
                str(event["tick"])
                + "/"
                + str(event["channel"])
                + "/"
                + str(event["control"])
                + "/"
                + str(event["value"])
            ] = event
        track_cc = list(cc_dic.values())

        # 添加到轨道列表
        tracks.append(
            {
                "index": track_index,
                "notes": track_notes,
                "cc_events": track_cc,
                "total_ticks": absolute_tick,
            }
        )

    return {
        "ticks_per_beat": ticks_per_beat,
        "tempo_events": tempo_events,
        "tracks": tracks,
    }


def simulate_explosion(
    n_particles,
    duration_ticks,
    max_distance,
    seed,
    min_speed=0.1,
):
    def solve_v(a, n, S, eps=1e-4):  # a初速度 n时间 S最大路程
        def f(v):
            x = (v / a) ** (1 / (n - 1))
            return a * (x**n - 1) / (x - 1) - S  # 二分法逼近S

        lo, hi = a, S  # v 至少是 a，最大不可能超过 S
        while hi - lo > eps:
            mid = (lo + hi) / 2
            if f(mid) > 0:
                hi = mid
            else:
                lo = mid
        return (lo + hi) / 2

    rng = np.random.RandomState(seed)

    # 生成随机方向向量（球面均匀分布）
    theta = rng.uniform(0, 2 * np.pi, n_particles)
    phi = np.arccos(2 * rng.uniform(0, 1, n_particles) - 1)

    direction_vectors = np.zeros((n_particles, 3))
    direction_vectors[:, 0] = np.sin(phi) * np.cos(theta)
    direction_vectors[:, 1] = np.sin(phi) * np.sin(theta)
    direction_vectors[:, 2] = np.cos(phi)

    # 计算最大速度
    initial_speed = solve_v(min_speed, duration_ticks, max_distance)

    # 生成随机初始速度
    initial_speeds = rng.uniform(initial_speed / 2, initial_speed, n_particles)

    # 计算每个粒子需要的衰减率，使它们统一在duration_ticks帧后速度降为min_speed
    # v0 * (decay_rate)^(duration_ticks-1) = min_speed
    # 所以: decay_rate = (min_speed / v0) ** (1/(duration_ticks-1))
    decay_rates = (min_speed / initial_speeds) ** (1 / (duration_ticks - 1))

    # 初始化位置数组，所有粒子从原点(0,0,0)开始
    positions = np.zeros((duration_ticks, n_particles, 3))
    positions[0, :, :] = 0  # 所有粒子初始位置为原点

    # 计算速度衰减
    tick_indices = np.arange(duration_ticks)
    # 为每个粒子应用其自身的衰减率
    speed_at_ticks = initial_speeds * (decay_rates ** (tick_indices[:, np.newaxis] - 1))
    speed_at_ticks[0, :] = 0  # 第0帧速度为0
    speed_at_ticks[speed_at_ticks < min_speed] = 0  # 低于最小速度则停止

    # 计算位移并更新位置
    displacement_increments = np.zeros((duration_ticks, n_particles, 3))
    for dim in range(3):
        displacement_increments[:, :, dim] = direction_vectors[:, dim] * speed_at_ticks

    cumulative_displacements = np.cumsum(displacement_increments, axis=0)

    for dim in range(3):
        positions[:, :, dim] = cumulative_displacements[:, :, dim]

    return positions, displacement_increments


class QuinticPolynomial:
    """单段五次多项式 p(t) = a0 + a1*t + ... + a5*t^5"""

    def __init__(self, t0, t1, p0, p1, v0, v1, a0, a1):
        self.t0 = t0
        self.t1 = t1
        T = t1 - t0
        # 构建方程组求解五次多项式系数
        M = np.array(
            [
                [1, 0, 0, 0, 0, 0],
                [0, 1, 0, 0, 0, 0],
                [0, 0, 2, 0, 0, 0],
                [1, T, T**2, T**3, T**4, T**5],
                [0, 1, 2 * T, 3 * T**2, 4 * T**3, 5 * T**4],
                [0, 0, 2, 6 * T, 12 * T**2, 20 * T**3],
            ]
        )
        b = np.array([p0, v0, a0, p1, v1, a1])
        self.coef = np.linalg.solve(M, b)

    def eval(self, t):
        dt = t - self.t0
        return sum(c * dt**i for i, c in enumerate(self.coef))

    def derivative(self, t):
        dt = t - self.t0
        return sum(i * c * dt ** (i - 1) for i, c in enumerate(self.coef) if i > 0)


def random_trajectory(
    start_pos,
    start_vel,
    end_pos,
    end_vel,
    T,
    n_samples,
):
    pos0 = np.array(start_pos)
    pos1 = np.array(end_pos)
    vel0 = np.array(start_vel)
    vel1 = np.array(end_vel)

    # 三维五次多项式，每个维度加速度默认0
    polys = [
        QuinticPolynomial(0, T, pos0[dim], pos1[dim], vel0[dim], vel1[dim], 0.0, 0.0)
        for dim in range(3)
    ]

    total_samples = int(T * n_samples) + 1
    t_eval = np.linspace(0, T, total_samples)

    pos_list = []
    vel_list = []
    for t in t_eval:
        pos = [polys[dim].eval(t) for dim in range(3)]
        vel = [polys[dim].derivative(t) for dim in range(3)]
        pos_list.append(tuple(pos))
        vel_list.append(tuple(vel))

    return pos_list, vel_list


def add_note_to_spectrum(
    spectrum, freq_bands, t, d, n, v, fade_frames, Q, rand_range, seed
):
    np.random.seed(seed)
    total_frames = len(spectrum)
    num_bands = len(freq_bands)

    # 计算音符基频
    f0 = 440.0 * 2 ** ((n - 69) / 12.0)
    amplitude = v / 127.0

    # 确定泛音频率与幅度，默认幅度
    amps = [1.0]
    k = 1
    while True:
        a = 0.5 * np.exp(1 - k)
        if a <= 0.05:
            break
        amps.append(a)
        k += 1
    harmonic_amps = amps

    # 确定受影响的帧范围
    start_frame = max(0, t)
    sustain_end_frame = min(total_frames, t + d)
    fade_end_frame = min(total_frames, t + d + fade_frames)

    # 指数衰减常数（控制先快后慢的程度，值越大衰减越快）
    decay_constant = 5.0

    # 遍历每一帧
    for frame_idx in range(start_frame, fade_end_frame):
        # 计算当前帧的幅度系数
        if frame_idx < sustain_end_frame:
            coeff = max(1 - 0.02 * (frame_idx - start_frame), 0.5)
        else:
            # 淡出阶段：指数衰减
            fade_progress = (frame_idx - sustain_end_frame + 1) / fade_frames
            coeff = max(1 - 0.02 * d, 0.5) * np.exp(-decay_constant * fade_progress)

        # 对每个泛音分别处理
        for harm_idx, amp_h in enumerate(harmonic_amps):
            k = harm_idx + 1  # 谐波次数（基频为1）
            f_h = f0 * k
            # 如果泛音频率超出频段范围，可跳过（高斯响应几乎为零）
            if f_h < freq_bands[0] or f_h > freq_bands[-1]:
                continue

            # 计算该泛音的高斯频率响应
            sigma_h = f_h / Q
            gauss_h = np.exp(-((freq_bands - f_h) ** 2) / (2 * sigma_h**2))
            gauss_h *= amplitude * amp_h  # 乘以力度和泛音幅度

            # 叠加到该帧的每个频段（每个频段独立随机因子）
            for band_idx in range(num_bands):
                rand_factor = np.random.uniform(rand_range[0], rand_range[1])
                spectrum[frame_idx][band_idx] += gauss_h[band_idx] * coeff * rand_factor

    return spectrum
