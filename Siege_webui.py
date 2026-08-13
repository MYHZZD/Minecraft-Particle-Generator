import gradio as gr
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import json
import os
import time
import zipfile
import tempfile
import io
import math
import colorsys
import siegedata
import siegefunc
import extrafunction
from matplotlib.patches import Rectangle
from matplotlib.collections import PatchCollection
from matplotlib.lines import Line2D
from functools import lru_cache

MAX_TRACKS = siegedata.MAX_TRACKS
GM_PROGRAM_NAMES = siegedata.GM_PROGRAM_NAMES
MC_PROGRAM_NAMES = siegedata.MC_PROGRAM_NAMES + siegedata.MC_EXTRA_PROGRAM_NAMES


def rgb_to_hex(r, g, b):
    return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"


def generate_optimal_colors(n, saturation=0.85, lightness=0.55):  # 创建颜色
    colors = []
    total_points = 2 * n  # 精细网格总数
    step_angle = 360 / total_points  # 基础步长 (180/n)
    jump = n - 1  # 跳跃步数

    for i in range(n):
        # 计算在精细网格上的索引，并取模
        idx = (i * jump) % total_points
        hue_deg = idx * step_angle

        # HSL 转 RGB（这里使用 hls_to_rgb，注意参数顺序是 H, L, S）
        r, g, b = colorsys.hls_to_rgb(hue_deg / 360.0, lightness, saturation)
        colors.append(rgb_to_hex(r, g, b))

    return colors


# 16 种高对比度颜色
# channel_colors = ["#e41a1c", "#377eb8", "#4daf4a", "#984ea3", "#ff7f00", "#ffff33", "#a65628", "#f781bf", "#999999", "#66c2a5", "#fc8d62", "#8da0cb", "#e78ac3", "#a6d854", "#ffd92f", "#e5c494"]
channel_colors = generate_optimal_colors(MAX_TRACKS)


def midi_to_note_name(midi_note, use_flats=False):  # midi音高转化为音名
    """
    use_flats若为True使用降号表示,否则使用升号表示
    """
    if not 0 <= midi_note <= 127:
        raise ValueError(f"MIDI 编号必须在 0-127 之间,实际为 {midi_note}")

    # 12 个半音的音名列表(升号版和降号版)
    note_names_sharp = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    note_names_flat = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]

    pitch_class = midi_note % 12
    note_name = note_names_flat[pitch_class] if use_flats else note_names_sharp[pitch_class]
    octave = midi_note // 12 - 1  # MIDI 60 = C4
    return f"{note_name}{octave}"


def recommend_range(low, high):  # 判断所属F#区间
    def binary_search_insert_pos(num, arr):  # 二分法查找
        left, right = 0, len(arr)
        while left < right:
            mid = (left + right) // 2
            if arr[mid] < num:  # 插在相同值左边
                left = mid + 1
            else:
                right = mid
        return left

    pitch_all = [6, 18, 30, 42, 54, 66, 78, 90, 102, 114, 126]  # pitch_all[0]对应F#-1,因此角标要-1输出
    minleft = binary_search_insert_pos(low, pitch_all)
    maxright = binary_search_insert_pos(high, pitch_all)
    if maxright - minleft <= 1:
        check = "√"
    else:
        check = "X"
    return f"F#{minleft-2}-F#{maxright-1} {check}"


def parse_midi(file_path):  # 分析midi信息
    try:
        midi_data = extrafunction.process_midi_file(file_path)
        track_names = extrafunction.get_track_name(file_path)
        tracks = midi_data["tracks"]

        def has_overlap(notes):
            """检测同一轨道内是否有音符时间重叠"""
            sorted_notes = sorted(notes, key=lambda x: x["start_tick"])
            for i in range(len(sorted_notes) - 1):
                if sorted_notes[i]["end_tick"] > sorted_notes[i + 1]["start_tick"]:
                    return True
            return False

        rows = []
        track_serial = 0  # 只统计有音符的轨道

        for _, track in enumerate(tracks):
            notes = track["notes"]
            if not notes:
                continue
            track_serial += 1

            # 获取原始轨道索引，并取出对应的名称
            orig_idx = track["index"]
            track_name = track_names[orig_idx] if orig_idx < len(track_names) else "未命名"
            if not track_name.strip():
                track_name = "Default"

            # 按通道统计
            channel_notes = {}  # channel -> list of pitches
            for note_event in notes:
                ch = note_event["channel"]
                pitch = note_event["note"]
                channel_notes.setdefault(ch, []).append(pitch)

            total_notes = len(notes)
            polyphony = has_overlap(notes)

            # 准备各列的多通道拼接字符串
            ch_parts = []  # 通道组成
            min_parts = []  # 最小音高
            max_parts = []  # 最大音高
            range_parts = []  # 推荐音域

            for ch, pitches in sorted(channel_notes.items()):
                cnt = len(pitches)
                min_p = min(pitches)
                max_p = max(pitches)
                range_str = recommend_range(min_p, max_p)
                color = channel_colors[ch % len(channel_colors)]

                # 通道组成：通道号 + 音符数
                ch_parts.append(f'<span style="color:{color}; font-weight:bold;">通道{ch+1}:{cnt}音符</span>')
                # 最小音高：通道号 + 音高值
                min_parts.append(f'<span style="color:{color}; font-weight:bold;">{min_p}:{midi_to_note_name(min_p)}</span>')
                # 最大音高
                max_parts.append(f'<span style="color:{color}; font-weight:bold;">{max_p}:{midi_to_note_name(max_p)}</span>')
                # 推荐音域
                range_parts.append(f'<span style="color:{color}; font-weight:bold;">{range_str}</span>')

            rows.append(
                {
                    "轨道索引": track_serial - 1,
                    "轨道名称": track_name,
                    "通道组成": "; ".join(ch_parts),
                    "音符数量": total_notes,
                    "最小音高": "; ".join(min_parts),
                    "最大音高": "; ".join(max_parts),
                    "推荐音域": "; ".join(range_parts),
                    "是否有复音": polyphony,
                }
            )

        df = pd.DataFrame(rows)
        return df

    except Exception as e:
        raise gr.Error(f"解析失败：{str(e)}")


def on_file_upload(file):
    """上传文件后：更新信息表格、轨道数量,并显示对应数量的参数组"""
    df = parse_midi(file)
    num_tracks = len(df)
    group_updates = []
    title_updates = []
    for i in range(MAX_TRACKS):
        visible = i < num_tracks
        group_updates.append(gr.update(visible=visible))
        if visible:
            title_updates.append(gr.update(value=f"### 轨道 {i} 参数"))
        else:
            title_updates.append(gr.update(value=""))
    return [df] + group_updates + title_updates


def build_results(num_tracks, *args):  # 创建config
    """从UI参数构建配置数据，返回轨道列表 + 全局字典"""
    tracks = []
    for i in range(num_tracks):
        base = i * 18
        attack = int(args[base + 10])
        decay = int(args[base + 11])
        sustain = int(args[base + 12])
        release = int(args[base + 13])
        decay_curve = float(args[base + 14])
        release_curve = float(args[base + 15])

        # 实时计算包络数组
        _, _, adsr_curve = generate_envelope(attack, decay, sustain, release, decay_curve, release_curve)

        tracks.append(
            {
                "轨道索引": i,
                "X": int(args[base]),
                "Y": int(args[base + 1]),
                "结构模式": int(args[base + 2]),
                "特效模式": int(args[base + 3]),
                "旋律X": int(args[base + 4]),
                "旋律Y": int(args[base + 5]),
                "音色1": str(args[base + 6]),
                "音色2": str(args[base + 7]),
                "音色3": str(args[base + 8]),
                "音色4": str(args[base + 9]),
                "ADSR": list(adsr_curve),
                "包络模式": str(args[base + 16]),
                "粒子特效": str(args[base + 17]) if args[base + 17] else "",
                "ADSR_params": {
                    "attack": attack,
                    "decay": decay,
                    "sustain": sustain,
                    "release": release,
                    "decay_curve": decay_curve,
                    "release_curve": release_curve,
                },
            }
        )
    global_data = {
        "纯音符模式": bool(args[-6]),
        "运动速度": float(args[-5]),
        "音符生成点": str(args[-4]),
        "结构生成点": str(args[-3]),
        "激活距离": int(args[-2]),
        "激活延迟": int(args[-1]),
    }
    return tracks, global_data


def generate(file, num_tracks, *args):
    tracks, global_data = build_results(num_tracks, *args)
    results = tracks + [global_data]

    midievent, max_tick = extrafunction.mcmappings(extrafunction.process_midi_file(file), 8)  # 8为一拍的tick数，4rt8gt
    mcfunction = siegefunc.gen(midievent, results, max_tick)

    mcmeta = json.dumps({"pack": {"pack_format": 1, "description": "hello\nby MYHZZD"}}, indent=2, ensure_ascii=False)

    # 内存中创建 ZIP 文件
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
        # 写入文件
        config_json = json.dumps(results, indent=2, ensure_ascii=False)
        zipf.writestr("config.json", config_json)
        zipf.writestr("pack.mcmeta", mcmeta)
        # 写入每个 tick 的 mcfunction 文件
        for i, commands in enumerate(mcfunction):
            if i != len(mcfunction) - 2:
                commands.append(f"schedule function tick{i+1} 1")
            else:
                commands.append(f"schedule function tick{i+1} 60")
            content = "\n".join(commands)
            zipf.writestr(f"data\\minecraft\\function\\tick{i}.mcfunction", content)
    zip_buffer.seek(0)
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, f"siege_{int(time.time())}.zip")
    with open(temp_path, "wb") as f:
        f.write(zip_buffer.getvalue())

    return temp_path


def download_config(num_tracks, *args):
    if num_tracks == 0:
        raise gr.Error("没有轨道，无法生成配置")
    tracks, global_data = build_results(num_tracks, *args)
    results = tracks + [global_data]
    config_json = json.dumps(results, indent=2, ensure_ascii=False)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write(config_json)
        return f.name


# ADSR相关
peak_x = 64
peak_y = 48


def adjust_lengths(attack, decay, release):  # 调整各阶段长度
    total = attack + decay + release
    if total > peak_x:
        scale = peak_x / total
        attack = round(attack * scale)
        decay = round(decay * scale)
        release = round(release * scale)
        total_new = attack + decay + release
        diff = peak_x - total_new
        if diff != 0:
            release = max(0, release + diff)
        sustain = 0
    else:
        sustain = peak_x - attack - decay - release
    return attack, decay, release, sustain


def interpolate_curve(start, end, t, alpha):  # 定义插值函数
    if alpha == 1 or start == end:
        return start + (end - start) * t
    else:
        return start + (end - start) * (t**alpha)


def generate_envelope(attack_len, decay_len, sustain_level, release_len, decay_curve, release_curve):  # 核心包络计算
    attack_len, decay_len, release_len, sustain_len = adjust_lengths(attack_len, decay_len, release_len)

    attack_end = attack_len
    decay_end = attack_len + decay_len
    sustain_end = decay_end + sustain_len

    xs = list(range(peak_x + 1))  # 横坐标列表 0~peak_x 共peak_x+1个点
    ys = []
    yf = []  # 折算为轨道偏移值

    for x in xs:
        if x <= attack_end:
            if attack_len == 0:
                y = peak_y
            else:
                y = 0 + (peak_y - 0) * (x / attack_len)
        elif x <= decay_end:
            if decay_len == 0:
                y = sustain_level
            else:
                t = (x - attack_end) / decay_len
                y = interpolate_curve(peak_y, sustain_level, t, 5**decay_curve)
        elif x <= sustain_end:
            y = sustain_level
        else:
            if release_len == 0:
                y = 0
            else:
                t = (x - sustain_end) / release_len
                y = interpolate_curve(sustain_level, 0, t, 5**release_curve)

        y = int(round(y))
        y = max(0, min(peak_y, y))
        ys.append(y)
        yf.append(peak_y - y)

    return [xs, ys, yf]


def plot_envelope(sustain, xy):  # 绘图函数
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.plot(xy[0], xy[1], marker="o", markersize=3, linestyle="-", linewidth=2, color="#1f77b4")
    ax.set_xlim(0, peak_x)
    ax.set_ylim(0, peak_y)
    ax.set_xlabel("Tick", fontsize=10)
    ax.set_ylabel("Amplitude", fontsize=10)
    ax.set_title("ADSR Envelope", fontsize=12)

    # 每个整数位置的网格线
    ax.set_xticks(np.arange(0, peak_x + 1, 1), minor=True)
    ax.set_xticks(np.arange(0, peak_x + 1, 5))
    ax.set_yticks(np.arange(0, peak_y + 1, 1), minor=True)
    ax.set_yticks(np.arange(0, peak_y + 1, 5))

    ax.grid(True, which="minor", linestyle="-", linewidth=0.5, alpha=0.4, color="gray")
    ax.grid(True, which="major", linestyle="--", linewidth=0.8, alpha=0.6, color="black")

    ax.axhline(y=sustain, color="r", linestyle=":", alpha=0.7, label=f"Sustain = {sustain}")
    ax.legend()
    plt.tight_layout()
    return fig


def load_config(file):  # 加载配置
    if not file:
        raise gr.Error("请上传有效的 config.json 文件")
    with open(file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 分离轨道和全局（最后一项如果是全局字典，则取出）
    if len(data) > 0 and isinstance(data[-1], dict) and "纯音符模式" in data[-1]:
        tracks = data[:-1]
        global_data = data[-1]
    else:
        tracks = data
        global_data = {}  # 无全局参数时用默认
    num_tracks = len(tracks)

    updates = []
    for i in range(MAX_TRACKS):
        if i < num_tracks:
            cfg = data[i]
            track_updates = [
                gr.update(value=cfg.get("X", 22)),
                gr.update(value=cfg.get("Y", 0)),
                gr.update(value=cfg.get("结构模式", 0)),
                gr.update(value=cfg.get("特效模式", 0)),
                gr.update(value=cfg.get("旋律X", 0)),
                gr.update(value=cfg.get("旋律Y", 0)),
                gr.update(value=cfg.get("音色1", MC_PROGRAM_NAMES[10])),
                gr.update(value=cfg.get("音色2", MC_PROGRAM_NAMES[0])),
                gr.update(value=cfg.get("音色3", MC_PROGRAM_NAMES[0])),
                gr.update(value=cfg.get("音色4", MC_PROGRAM_NAMES[0])),
                gr.update(value=cfg.get("ADSR_params", {}).get("attack", 0)),
                gr.update(value=cfg.get("ADSR_params", {}).get("decay", 32)),
                gr.update(value=cfg.get("ADSR_params", {}).get("sustain", 32)),
                gr.update(value=cfg.get("ADSR_params", {}).get("release", 24)),
                gr.update(value=cfg.get("ADSR_params", {}).get("decay_curve", -0.5)),
                gr.update(value=cfg.get("ADSR_params", {}).get("release_curve", 0)),
                gr.update(value=cfg.get("包络模式", "NONE")),
                gr.update(),  # 粒子特效不更新
            ]
        else:
            # config中不存在的轨道,保持当前状态
            track_updates = [gr.update() for _ in range(18)]  # 每个轨道18个控件
        updates.extend(track_updates)
    # 更新全局控件（6 个）
    global_updates = [
        gr.update(value=global_data.get("纯音符模式", False)),
        gr.update(value=global_data.get("运动速度", 1.0)),
        gr.update(value=global_data.get("音符生成点", "80,10,0")),
        gr.update(value=global_data.get("结构生成点", "20,0,0")),
        gr.update(value=global_data.get("激活距离", 40)),
        gr.update(value=global_data.get("激活延迟", 3)),
    ]
    updates.extend(global_updates)

    return updates


def map_coordinate(moded, envelope, x, y, mx, my):  # 位置图计算 返回位置列表
    coords = []
    if abs(my) <= 48:  # 有旋律轨
        if mx == 0:
            coords.append((mx, my))
            coords.append((mx, my + 1))
        else:
            coords.append((mx, my))
            coords.append((mx, my + 1))
            coords.append((-mx, my))
            coords.append((-mx, my + 1))
    if moded != 1:  # 不是纯旋律轨
        if moded in (0, 2):  # left
            coords.append((-x, y))
            coords.append((-x, y + 1))
        if moded in (0, 3):  # right
            coords.append((x, y))
            coords.append((x, y + 1))

    return coords


def draw_position_grid(moded, envelope_r, xs, ys, mxs, mys):  # 位置图绘制
    fig, ax = plt.subplots(figsize=(12, 12))
    ax.set_xlim(-48, 48)
    ax.set_ylim(-48, 48)
    ax.set_aspect("equal")  # 强制等比例，保证网格正方形
    # 主要刻度
    ax.set_xticks(np.arange(-40, 50, 10))
    ax.set_yticks(np.arange(-40, 50, 10))
    # 次要刻度（每1个单位）仅网格线，不显示标签
    ax.set_xticks(np.arange(-48, 49, 1), minor=True)
    ax.set_yticks(np.arange(-48, 49, 1), minor=True)
    # 网格线
    ax.grid(True, which="minor", linestyle="-", linewidth=0.4, alpha=0.4, color="gray")
    ax.grid(True, which="major", linestyle="--", linewidth=0.6, alpha=0.6, color="black")
    # 中心十字线
    ax.axhline(0, color="black", linewidth=0.8)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel("X")
    ax.set_ylabel("Y")

    legend_elements = []  # 收集图例
    # 方块位置
    rectangles = []  # 收集点图
    for i, (m, e, x, y, mx, my) in enumerate(zip(moded, envelope_r, xs, ys, mxs, mys)):
        coords = map_coordinate(m, e, x, y, mx, my)
        color = channel_colors[i % len(channel_colors)]
        for x, y in coords:
            rect = Rectangle(xy=(x - 0.5, y - 0.5), width=1.0, height=1.0, facecolor=color, edgecolor=color)
            rectangles.append(rect)
        legend_elements.append(Line2D([0], [0], marker="s", color="#FFFFFF", label=f"TRACK{i}", markerfacecolor=color, markersize=10))
    # 音量圆
    for v, a in enumerate([47, 45, 43, 41, 38, 34, 29, 23, 15]):
        points = get_minecraft_circle(a)
        points.append(points[0])
        vol = (v + 1) * 10
        color = channel_colors[v % len(channel_colors)]
        for x, y in points:
            rect = Rectangle(xy=(x - 0.3, y - 0.3), width=0.6, height=0.6, facecolor=color, edgecolor=color, alpha=0.6)
            rectangles.append(rect)
        legend_elements.append(Line2D([0], [0], marker="s", color="#FFFFFF", label=f"VOLUME{vol}%", markerfacecolor=color, markersize=7))
    if rectangles:  # 添加进图表
        pc = PatchCollection(rectangles, match_original=True)
        ax.add_collection(pc)
    ax.legend(handles=legend_elements, loc="upper left", fontsize=8, bbox_to_anchor=(1, 1))  # 添加图例
    plt.tight_layout()
    return fig


@lru_cache(maxsize=None)  # 启用缓存
def get_minecraft_circle(a):  # 生成 Bresenham 连续像素圆
    a = int(abs(a))
    if a == 0:
        return [(0, 0)]

    points = []
    x = 0
    y = a
    d = 1 - a  # 决策参数（或使用 3 - 2*a，效果相同）

    # 利用八分对称性，每次添加 8 个对称点
    def add_symmetric_points(cx, cy):
        # 添加以 (0,0) 为中心的 8 个对称点
        pts = [(cx, cy), (cy, cx), (cy, -cx), (cx, -cy), (-cx, -cy), (-cy, -cx), (-cy, cx), (-cx, cy)]
        # 去重（处理 cx=cy 或 cx=0 的情况）
        for p in pts:
            if p not in points:  # 小半径时去重避免重复
                points.append(p)

    while x <= y:
        add_symmetric_points(x, y)
        if d < 0:
            d += 2 * x + 3
        else:
            d += 2 * (x - y) + 5
            y -= 1
        x += 1

    # 按角度顺时针排序，方便绘图连线（避免乱序交叉）
    points.sort(key=lambda p: (math.atan2(p[1], p[0]) + math.pi))  # 从 -π 到 π 排序
    return points


def update_position(*args):  # 更新位置图
    """
    参数：各轨道[mode_d, envelope_r, x_s, y_s, mainx_s, mainy_s] 最后一个state_num_tracks
    """
    num_tracks = int(args[-1])
    slider_vals = args[:-1]
    if num_tracks == 0:
        return gr.update(visible=False)  # 隐藏位置图

    moded, envelope_r, xs, ys, mxs, mys = [], [], [], [], [], []
    for i in range(num_tracks):
        base = i * 6
        moded.append(slider_vals[base])
        envelope_r.append(slider_vals[base + 1])
        xs.append(slider_vals[base + 2])
        ys.append(slider_vals[base + 3])
        mxs.append(slider_vals[base + 4])
        mys.append(slider_vals[base + 5])
    fig = draw_position_grid(moded, envelope_r, xs, ys, mxs, mys)
    return gr.update(value=fig, visible=True)


def update_adsr_plot(attack, decay, sustain, release, decay_curve, release_curve, envelope_mode):  # ADSR绘图条件判定
    """仅在包络模式为 ADSR 时绘图，否则不更新"""
    if envelope_mode != "ADSR":
        return gr.update()  # 保持原有图表不变
    # 计算包络数组
    xs, ys, yf = generate_envelope(attack, decay, sustain, release, decay_curve, release_curve)
    # 绘制曲线
    fig = plot_envelope(sustain, (xs, ys))
    return fig


# 构建界面
with gr.Blocks(title="MIDI 轨道参数", theme=gr.themes.Soft(), fill_width=True, fill_height=True) as demo:
    # gr.Markdown("# 🎵 MIDI 轨道配置")

    upload = gr.UploadButton(label="🎵 上传 MIDI 文件", file_types=[".mid", ".midi"], type="filepath")
    info_df = gr.DataFrame(label="轨道基础信息", interactive=False, datatype=["number", "str", "html", "number", "html", "html", "html", "bool"], max_height="20vh")

    state_num_tracks = gr.Number(value=0, visible=False)

    # 动态创建轨道参数组
    track_groups = []
    track_titles = []
    all_components = []  # 存储所有参数,用于生成回调
    slider_inputs = []  # 位置图输入

    with gr.Tabs():
        with gr.TabItem("基础设置"):
            for i in range(MAX_TRACKS):
                dynamic_y = ((i + 1) // 2) * 3 * ((-1) ** (i + 1))  # 0 3 -3 6 -6 ......
                with gr.Group(visible=False) as group:
                    title_md = gr.Markdown(f"### 轨道 {i} 参数")
                    with gr.Row(scale=0):
                        mode_d = gr.Dropdown(label="结构模式", choices=[0, 1, 2, 3], value=0, scale=0)
                        tmode_d = gr.Dropdown(label="特效模式", choices=[0, 1, 99], value=0, scale=0)
                        x_s = gr.Slider(label="DELAY X", minimum=6, maximum=48, step=1, value=22)  # delay轨右侧距离 左侧依靠对称
                        y_s = gr.Slider(label="DELAY Y", minimum=-48, maximum=48, step=1, value=dynamic_y)  # delay轨上下位置
                        mainx_s = gr.Slider(label="旋律 X", minimum=-2, maximum=2, step=1, value=0)  # 旋律轨左右距离
                        mainy_s = gr.Slider(label="旋律 Y", minimum=-50, maximum=50, step=1, value=dynamic_y)  # 旋律轨上下位置 ±48外不生成
                        timbre1_d = gr.Dropdown(choices=MC_PROGRAM_NAMES, label="音色1", value=MC_PROGRAM_NAMES[10], allow_custom_value=True)
                    with gr.Accordion("高级选项", open=False):
                        with gr.Row(scale=0, equal_height="true"):
                            envelope_r = gr.Radio(choices=["NONE", "ADSR", "CC"], label="包络模式", value="NONE")
                            timbre2_d = gr.Dropdown(choices=MC_PROGRAM_NAMES, label="音色2", value=MC_PROGRAM_NAMES[0], allow_custom_value=True)
                            timbre3_d = gr.Dropdown(choices=MC_PROGRAM_NAMES, label="音色3", value=MC_PROGRAM_NAMES[0], allow_custom_value=True)
                            timbre4_d = gr.Dropdown(choices=MC_PROGRAM_NAMES, label="音色4", value=MC_PROGRAM_NAMES[0], allow_custom_value=True)
                            particle_f = gr.UploadButton(label="上传特效配置", file_types=[".json", ".mcfunction"], type="filepath")
                        with gr.Accordion("ADSR设置", open=False):
                            with gr.Row():
                                with gr.Column(scale=1):
                                    attack_slider = gr.Slider(0, peak_x, value=0, step=1, label="Attack 长度")
                                    decay_slider = gr.Slider(0, peak_x, value=32, step=1, label="Decay 长度")
                                    sustain_slider = gr.Slider(0, peak_y, value=32, step=1, label="Sustain 电平")
                                    release_slider = gr.Slider(0, peak_x, value=24, step=1, label="Release 长度")
                                    decay_curve_slider = gr.Slider(-1, 1, value=-0.5, step=0.01, label="Decay 弯曲度")
                                    release_curve_slider = gr.Slider(-1, 1, value=0, step=0.01, label="Release 弯曲度")
                                with gr.Column(scale=2):
                                    plot_output = gr.Plot(label="包络示意图")

                            # 收集当前轨道的 ADSR 滑块
                            adsr_sliders = [attack_slider, decay_slider, sustain_slider, release_slider, decay_curve_slider, release_curve_slider]
                            # 输入：6个滑块 + envelope_r
                            inputs_for_adsr = adsr_sliders + [envelope_r]

                            # 为每个滑块绑定 release 事件
                            for slider in adsr_sliders:
                                slider.release(fn=update_adsr_plot, inputs=inputs_for_adsr, outputs=plot_output)

                            # 为包络模式单选钮绑定 change 事件（切换时立即刷新）
                            envelope_r.change(fn=update_adsr_plot, inputs=inputs_for_adsr, outputs=plot_output)

                track_groups.append(group)
                track_titles.append(title_md)
                all_components.extend([x_s, y_s, mode_d, tmode_d, mainx_s, mainy_s])  # 位置&结构&模式
                all_components.extend([timbre1_d, timbre2_d, timbre3_d, timbre4_d])  # 音色
                all_components.extend([attack_slider, decay_slider, sustain_slider, release_slider, decay_curve_slider, release_curve_slider])  # ADSR
                all_components.extend([envelope_r, particle_f])  # 包络模式 & 粒子特效文件
                slider_inputs.extend([mode_d, envelope_r, x_s, y_s, mainx_s, mainy_s])
        with gr.TabItem("轨道位置图"):
            position_plot = gr.Plot(visible=False)

    with gr.Row():
        note_b = gr.Radio(choices=[True, False], label="纯音符模式", value=False)
        speed_r = gr.Radio(choices=[1, 0.5], label="运动速度", value=1)
        note_t = gr.Textbox(label="音符生成点", value="80,10,0")
        structure_t = gr.Textbox(label="结构生成点", value="20,0,0")
        start_n = gr.Number(label="激活距离", value=40)
        inplace_n = gr.Number(label="激活延迟", value=3)
    all_components.extend([note_b, speed_r, note_t, structure_t, start_n, inplace_n])

    with gr.Row():
        config_upload = gr.UploadButton(label="上传 config.json", file_types=[".json"], type="filepath")
        generate_btn = gr.Button("生成", variant="primary")
        config_download_btn = gr.Button("下载 config.json")
    download_zip = gr.File(label="📦 下载 ZIP 文件", interactive=False)

    # 上传文件后更新
    upload.change(fn=on_file_upload, inputs=upload, outputs=[info_df] + track_groups + track_titles).then(fn=lambda df: len(df), inputs=info_df, outputs=state_num_tracks)

    # 生成按钮
    config_download_btn.click(fn=download_config, inputs=[state_num_tracks] + all_components, outputs=download_zip)
    generate_btn.click(fn=generate, inputs=[upload] + [state_num_tracks] + all_components, outputs=download_zip)

    # 加载配置 更新位置图
    config_upload.upload(fn=load_config, inputs=config_upload, outputs=all_components).then(fn=update_position, inputs=slider_inputs + [state_num_tracks], outputs=position_plot)

    # 位置图
    # 输入变化时更新
    for ids, slider in enumerate(slider_inputs):
        if ids % 6 in (0, 1):
            slider.change(fn=update_position, inputs=slider_inputs + [state_num_tracks], outputs=position_plot)
        else:
            slider.release(fn=update_position, inputs=slider_inputs + [state_num_tracks], outputs=position_plot)
    # 上传MIDI时更新
    state_num_tracks.change(fn=update_position, inputs=slider_inputs + [state_num_tracks], outputs=position_plot)
    # 页面加载时初始化
    demo.load(fn=update_position, inputs=slider_inputs + [state_num_tracks], outputs=position_plot)


if __name__ == "__main__":
    demo.launch(inbrowser=True)
