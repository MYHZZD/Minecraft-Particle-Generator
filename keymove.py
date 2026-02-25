import math
import copy
import numpy as np
from extrafunction import (
    simulate_explosion,
    random_trajectory,
    add_note_to_spectrum,
    process_midi_file,
)


midi_path = "./tests.mid"
ticks_per_beats = 16.00  # FL PPQ默认96
start_delay = 72
fade_time = 5
move_mode = "stable"  # stable固定键盘位置。legacy移动键盘位置


def tick_mappings(tick, mapping_times):
    remainder = int(tick % mapping_times)
    # 如果余数小于映射倍数的一半则向下取整,对于mapping times=6，余数012向下取整，345向上取整
    if remainder < int(mapping_times / 2):
        tick = int(math.floor(tick / mapping_times))
    else:
        tick = int(math.floor(tick / mapping_times)) + 1
    return tick


if __name__ == "__main__":
    result = process_midi_file(midi_path)
    mcresult = copy.deepcopy(result)
    max_tick = 0
    mapping_times = result["ticks_per_beat"] / ticks_per_beats
    # 检查映射倍数是否为整数且为偶数
    if not mapping_times.is_integer() or mapping_times % 2 != 0:
        print(f"不合法的ticks per beats与PPQ。映射倍数为{mapping_times}")

    # 曲速处理
    mapped_tempos = []
    for tempo in result["tempo_events"]:
        mapped_tempo_event = tempo.copy()
        mapped_tempo_event["tick"] = tick_mappings(tempo["tick"], mapping_times)
        mapped_tempos.append(mapped_tempo_event)
        if mapped_tempo_event["tick"] > max_tick:
            max_tick = mapped_tempo_event["tick"]
    mcresult["tempo_events"] = mapped_tempos

    # 轨道处理
    mapped_tracks = []
    for track in result["tracks"]:
        mapped_track = track.copy()

        mapped_track["total_ticks"] = tick_mappings(track["total_ticks"], mapping_times)

        if track["notes"]:
            mapped_notes = []
            for note in track["notes"]:
                mapped_note_event = note.copy()
                mapped_note_event["start_tick"] = tick_mappings(
                    note["start_tick"], mapping_times
                )
                mapped_note_event["duration"] = tick_mappings(
                    note["duration"], mapping_times
                )
                mapped_note_event["end_tick"] = tick_mappings(
                    note["end_tick"], mapping_times
                )
                mapped_notes.append(mapped_note_event)
                if mapped_note_event["end_tick"] > max_tick:
                    max_tick = mapped_note_event["end_tick"]
            mapped_track["notes"] = mapped_notes

        if track["cc_events"]:
            mapped_ccs = []
            for cc in track["cc_events"]:
                mapped_cc_event = cc.copy()
                mapped_cc_event["tick"] = tick_mappings(cc["tick"], mapping_times)
                mapped_ccs.append(mapped_cc_event)
                if mapped_cc_event["tick"] > max_tick:
                    max_tick = mapped_cc_event["tick"]
            mapped_track["cc_events"] = mapped_ccs
        mapped_tracks.append(mapped_track)
    mcresult["tracks"] = mapped_tracks
    # print(result)
    # print(mcresult)
    print("midi读取成功\n")

    # 输出部分
    mcfunction = [
        [] for _ in range(max_tick + 1 + start_delay + 2 + fade_time)
    ]  # 瀑布流延迟start_delay，瀑布流清除2tick,频谱图fade_time
    # 琴键操作
    for i, track in enumerate(mcresult["tracks"]):
        total_ticks = int(track["total_ticks"])
        if track["notes"] != []:
            for j in range(total_ticks + 1):
                repeat_note = []
                for note_event in reversed(
                    track["notes"]
                ):  # 反转序列，先添加后侧音符到按键列表，判断重复
                    if note_event["start_tick"] == j:
                        if int(note_event["note"] % 12) in [0, 2, 4, 5, 7, 9, 11]:
                            mcfunction[j + start_delay].append(
                                f'execute as @e[tag=keys,tag={note_event["note"]}] run data merge entity @s {{brightness:{{block:{int(12+note_event["velocity"]/32)},sky:15}},transformation:[15.9392f,-0.1744f,0.00f,0.3f,1.3952f,1.9924f,0.00f,-1.5f,0.00f,0.00f,2.00f,0.00f,0.00f,0.00f,0.00f,1.00f]}}'
                            )
                        else:
                            mcfunction[j + start_delay].append(
                                f'execute as @e[tag=keys,tag={note_event["note"]}] run data merge entity @s {{brightness:{{block:{int(12+note_event["velocity"]/32)},sky:15}},transformation:[9.96200f,-0.2616f,0.00f,0.3f,0.8720f,2.9886f,0.00f,-1.1f,0.00f,0.00f,1.00f,0.00f,0.00f,0.00f,0.00f,1.00f]}}'
                            )
                        repeat_note.append(note_event["note"])  # 某刻会按下去的键

                    elif note_event["end_tick"] == j:
                        if (
                            note_event["note"] in repeat_note
                        ):  # 如果同一刻有前个音符end和后个音符on，off事件提前1tick.注意：如果前一个音符只有1t，会吞掉前一个音符
                            k = j - 1
                        else:
                            k = j
                        if int(note_event["note"] % 12) in [0, 2, 4, 5, 7, 9, 11]:
                            mcfunction[k + start_delay].append(
                                f'execute as @e[tag=keys,tag={note_event["note"]}] run data merge entity @s {{brightness:{{block:0,sky:15}},transformation:[16.00f,0.00f,0.00f,0.00f,0.00f,2.00f,0.00f,0.00f,0.00f,0.00f,2.00f,0.00f,0.00f,0.00f,0.00f,1.00f]}}'
                            )
                        else:
                            mcfunction[k + start_delay].append(
                                f'execute as @e[tag=keys,tag={note_event["note"]}] run data merge entity @s {{brightness:{{block:0,sky:15}},transformation:[10.00f,0.00f,0.00f,0.00f,0.00f,3.00f,0.00f,0.00f,0.00f,0.00f,1.00f,0.00f,0.00f,0.00f,0.00f,1.00f]}}'
                            )
    print("按键成功\n")

    # 瀑布流
    waterfall_tick = 12  # 瀑布步数
    waterfall_interval = 2  # 每步间隔
    for i, track in enumerate(mcresult["tracks"]):
        total_ticks = int(track["total_ticks"])
        if track["notes"] != []:
            for j in range(total_ticks + 1):
                for k, note_event in enumerate(track["notes"]):
                    if note_event["start_tick"] == j:
                        if int(note_event["note"] % 12) < 5:
                            location = 0.5
                        else:
                            location = 1.5
                        location += (
                            math.floor(note_event["note"] / 12) * 14
                            + int(note_event["note"] % 12)
                            - 24
                        )
                        for l in range(note_event["duration"]):
                            if note_event["duration"] > start_delay and l > start_delay:
                                mcfunction[j + l].append(
                                    f'execute at @e[type=minecraft:armor_stand,tag=piano] run summon block_display ~{start_delay+20} ~{0.5*waterfall_tick**2+4.495:.4f} ~{location} {{block_state:{{Name:"minecraft:note_block",Properties:{{powered:"true",instrument:"harp",note:"{i}"}}}},brightness:{{block:15,sky:15}},Tags:["waterfall","track{i}note{k}","tick{l}"]}}'
                                )
                            else:
                                mcfunction[j + l].append(
                                    f'execute at @e[type=minecraft:armor_stand,tag=piano] run summon block_display ~{start_delay+20} ~{0.5*waterfall_tick**2+4.495:.4f} ~{location} {{block_state:{{Name:"minecraft:note_block",Properties:{{powered:"false",instrument:"harp",note:"{i}"}}}},brightness:{{block:12,sky:15}},Tags:["waterfall","track{i}note{k}","tick{l}"]}}'
                                )
                            mcfunction[j + l].append(
                                f"execute as @e[tag=track{i}note{k},tag=tick{l}] run data merge entity @s {{start_interpolation:0,teleport_duration:1}}"
                            )
                            for m in range(waterfall_tick * waterfall_interval):
                                mcfunction[j + l + m].append(
                                    f"execute as @e[tag=track{i}note{k},tag=tick{l}] at @s run tp @s ~ ~{0.5*(waterfall_tick-(1/waterfall_interval)-0.5*m)**2-0.5*(waterfall_tick-0.5*m)**2:.4f} ~"
                                )
                            mcfunction[j + l + start_delay + 2].append(
                                f"kill @e[tag=track{i}note{k},tag=tick{l}]"
                            )
                        mcfunction[j + start_delay].append(
                            f'execute as @e[tag=track{i}note{k}] run data merge entity @s {{block_state:{{Name:"minecraft:note_block",Properties:{{powered:"true",instrument:"harp",note:"{i}"}}}},brightness:{{block:15,sky:15}}}}'
                        )
                        # 创建激活粒子
                        for ii in range(120):
                            mcfunction[j + start_delay].append(
                                f"execute as @e[type=minecraft:armor_stand,tag=piano] at @s run particle minecraft:end_rod ~18 ~6 ~{location} {math.cos((math.pi/60)*ii)-5:.4f} 0.5 {math.sin((math.pi/60)*ii):.4f} 0.1802 0 force"
                            )
    print("瀑布流成功\n")

    spectrum = []
    for i in range(144):
        spectrum.append(
            f'execute at @e[type=minecraft:armor_stand,tag=piano] run summon block_display ~{start_delay+20} ~{0.5*waterfall_tick**2-(0.5*waterfall_tick**2-0.5*(waterfall_tick-(1/waterfall_interval))**2)+5.5:.4f} ~{-20+i+0.5+0.1} {{block_state:{{Name:"minecraft:sea_lantern"}},brightness:{{block:15,sky:15}},transformation:[1.00f,0.00f,0.00f,0.00f,0.00f,0.10f,0.00f,0.00f,0.00f,0.00f,0.80f,0.00f,0.00f,0.00f,0.00f,1.00f],Tags:["spectrum","spectrum{i}"]}}'
        )
    spectrum.append(
        f"execute as @e[tag=spectrum] run data merge entity @s {{start_interpolation:0,teleport_duration:1,interpolation_duration:1}}"
    )
    with open("spectrum.mcfunction", "w") as f:
        for cmd in spectrum:
            f.write(cmd + "\n")
    print("频谱图初始化成功\n")

    # 特效
    tcount_default = 192
    ttime_default = int(5 * ticks_per_beats)  # ticks_per_beats必须是4的整数倍

    ttime = ttime_default
    ttime_next = ttime_default  # 预测下一段时长
    tcount = tcount_default

    tdistance = 64
    exp_center = [52, 32, 52]
    cc_exp = []
    for track in mcresult["tracks"]:
        if track["cc_events"] != []:
            for cc_event in track["cc_events"]:
                if cc_event["control"] == 90:
                    if cc_event["tick"] not in cc_exp:
                        cc_exp.append(cc_event["tick"])
    cc_exp.sort()
    cc_exp.append(max_tick)
    cc_exp.append(max_tick)

    for i in range(max_tick + 1):
        if (
            cc_exp == [max_tick, max_tick]
            and i % ttime == 0
            and max_tick + 3 + fade_time - i
            > ttime  # 传统模式，适用于标准对齐的midi，tcount点处于小节线上。fade time也作为冗余
        ) or (
            cc_exp != [max_tick, max_tick]
            and i in cc_exp
            and i != max_tick  # cc控制模式，需要手动创建cc事件作为标记
        ):
            if cc_exp != [max_tick, max_tick]:
                ttime_cc = cc_exp[cc_exp.index(i) + 1] - cc_exp[cc_exp.index(i)]
                ttime_cc_next = (
                    cc_exp[cc_exp.index(i) + 2] - cc_exp[cc_exp.index(i) + 1]
                )
                ttime = ((ttime_cc // 4) + 1) * 4
                ttime_next = ((ttime_cc_next // 4) + 1) * 4
                tcount = tcount_default * ttime // ttime_default

            # 爆炸特效
            positions, _ = simulate_explosion(tcount, ttime, tdistance, i)
            for count in range(tcount):
                mcfunction[i + start_delay].append(
                    f'execute at @e[type=minecraft:armor_stand,tag=piano] run summon block_display ~{exp_center[0]} ~{exp_center[1]} ~{exp_center[2]} {{block_state:{{Name:"minecraft:cherry_leaves"}},brightness:{{block:15,sky:15}},Tags:["expblock","tick{i}exp","block{count}"]}}'
                )
            mcfunction[i + start_delay].append(
                f"execute as @e[tag=tick{i}exp] run data merge entity @s {{start_interpolation:0,teleport_duration:1,interpolation_duration:1}}"
            )
            for timeadd in range(ttime - 1):
                for count in range(tcount):
                    addpos = positions[timeadd + 1][count]
                    mcfunction[i + start_delay + timeadd + 1].append(
                        f"execute as @e[type=minecraft:armor_stand,tag=piano] at @s run tp @e[tag=tick{i}exp,tag=block{count}] ~{exp_center[0]+addpos[0]:.4f} ~{exp_center[1]+addpos[1]*0.75:.4f} ~{exp_center[2]+addpos[2]:.4f}"
                    )
            if max_tick - i > ttime * 2 + exp_center[0]:
                mcfunction[i + start_delay + ttime + exp_center[0]].append(
                    f"kill @e[tag=tick{i}exp]"
                )
            print(f"爆炸特效{i}tick成功")

            # 粒子特效
            note_pos = []  # 终点位置
            note_vel = []  # 终点速度矢量
            note_time = []  # 整体时间
            density = 10  # 每tick多少粒子
            for track in mcresult["tracks"]:
                if track["notes"] != []:
                    for note_event in track["notes"]:
                        if (
                            note_event["start_tick"] >= i + ttime / 2
                            and note_event["start_tick"] < i + ttime_next / 2 + ttime
                        ):

                            if int(note_event["note"] % 12) < 5:
                                location = (
                                    0.5 + 0.5
                                )  # 粒子与方块不同，没有体积，额外加半格才是对应方块中心位置
                            else:
                                location = 1.5 + 0.5
                            location += (
                                math.floor(note_event["note"] / 12) * 14
                                + int(note_event["note"] % 12)
                                - 24
                            )
                            if move_mode == "legacy":
                                note_pos.append(
                                    [note_event["start_tick"] - i, 6, location]
                                )  # 基于参考点
                            else:
                                note_pos.append([0, 6, location])
                            note_time.append(note_event["start_tick"] - i)
                            note_vel.append([-note_event["velocity"] / 16, 0, 0])
            ttcount = len(note_pos)  # 数量不少于十六分之一
            if ttcount == 0:
                continue
            while ttcount <= tcount / 16:
                ttcount = ttcount * 2
                note_pos = note_pos + note_pos
                note_vel = note_vel + note_vel
                note_time = note_time + note_time
            print(f"本轮粒子数{ttcount}")
            n_positions, n_displacement_increments = simulate_explosion(
                ttcount, int((ttime / 4) * density * 2), tdistance * density, i + 1
            )  # 四分之一的时间爆炸，输入二分之一时间，后期取数组一半位置。每秒钟density个点，但输入时间单位是tick，所以时间变成density倍，距离也要变成density倍，后期除density

            delta_positisons = (
                np.array(n_positions) * np.array([1, 1, 3]) / density
                + np.array(exp_center) * np.array([1.5, 1, 1])
            ).tolist()  # 原点从爆炸中心点移动到参考点，x轴远1.5倍，z轴缩放3倍
            delta_increments = (
                np.array(n_displacement_increments) * np.array([1, 1, 3])
            ).tolist()
            for j in range(ttcount):
                pos_list, vel_list = random_trajectory(
                    delta_positisons[int((ttime / 4) * density - 1)][j],
                    delta_increments[int((ttime / 4) * density - 1)][j],
                    (np.array(note_pos[j]) + np.array([18, 0, 0])).tolist(),
                    note_vel[j],
                    int(note_time[j] - (ttime / 4)),
                    density,
                )  # 时间为整体时间-爆炸时长。终点位置考虑键盘尺寸20格,但是稍微插入一些效果会更好，18格
                for k in range(int(ttime / 4)):  # 爆炸时间
                    delta_k = 0
                    if move_mode == "legacy":
                        delta_k = k
                    for m in range(density):
                        mcfunction[i + start_delay + k].append(
                            f"execute as @e[type=minecraft:armor_stand,tag=piano] at @s run particle minecraft:end_rod ~{delta_positisons[density*k+m][j][0]-delta_k:.4f} ~{delta_positisons[density*k+m][j][1]:.4f} ~{delta_positisons[density*k+m][j][2]:.4f} 0 0 0 0 0 force"
                        )
                for k in range(int(note_time[j] - (ttime / 4))):
                    delta_k = -(ttime / 4)
                    if move_mode == "legacy":
                        delta_k = k
                    for m in range(density):
                        mcfunction[i + start_delay + int((ttime / 4)) + k].append(
                            f"execute as @e[type=minecraft:armor_stand,tag=piano] at @s run particle minecraft:end_rod ~{pos_list[density*k+m][0]-(ttime / 4)-delta_k:.4f} ~{pos_list[density*k+m][1]:.4f} ~{pos_list[density*k+m][2]:.4f} 0 0 0 0 0 force"
                        )
            print(f"粒子特效{i}tick成功")

    # 频谱图
    # 使用 np.geomspace 生成频段
    freq_bands = np.geomspace(20, 24000, 144)  # 从20Hz到24000Hz，共144个频段
    num_bands = len(freq_bands)
    # 初始化频谱：二维列表 [时间帧][频段]
    spectrum = [[0.0] * num_bands for _ in range(max_tick + 10)]
    for track in mcresult["tracks"]:
        if track["notes"] != []:
            pedal_intervals = []  # 构建踏板区间
            pedal_on = False
            on_tick = 0
            for cc_event in track["cc_events"]:  # 钢琴特化CC64
                if cc_event["control"] == 64:
                    if cc_event["value"] > 16:  # 踏板按下
                        if not pedal_on:
                            pedal_on = True
                            on_tick = cc_event["tick"]
                    else:  # 踏板松开
                        if pedal_on:
                            pedal_intervals.append((on_tick, cc_event["tick"]))
                            pedal_on = False
            # 如果文件结束时踏板还按着
            if pedal_on:
                pedal_intervals.append((on_tick, max_tick))

            interval_index = 0  # 双指针扫描
            n_intervals = len(pedal_intervals)
            for i, note_event in enumerate(track["notes"]):
                duration = note_event["duration"]
                if n_intervals != 0:
                    while (
                        interval_index < n_intervals
                        and pedal_intervals[interval_index][1] <= note_event["end_tick"]
                    ):
                        interval_index += 1
                    if interval_index < n_intervals:
                        on_tick, off_tick = pedal_intervals[interval_index]
                        # 如果音符结束时处于踏板区间内
                        if on_tick <= note_event["end_tick"] < off_tick:
                            duration = off_tick - note_event["start_tick"]
                add_note_to_spectrum(
                    spectrum,
                    freq_bands,
                    note_event["start_tick"],
                    duration,
                    note_event["note"],
                    note_event["velocity"],
                    fade_time,
                    16,
                    (0.9, 1.1),
                    i,
                )
                print(f"添加音符{note_event["note"]}成功")
    # 防爆
    threshold = 2
    global_max = max([v for frame in spectrum for v in frame])
    for frame in spectrum:
        for i in range(len(frame)):
            x = frame[i]
            frame[i] = threshold * np.log1p(k * x) / np.log1p(k * global_max)
    # 变换实体
    for j in range(max_tick + fade_time):
        for k in range(num_bands):
            if j > 0 and str(f"{spectrum[j][k]:.4f}") == str(f"{spectrum[j-1][k]:.4f}"):
                continue
            mcfunction[j + start_delay].append(
                f"execute as @e[tag=spectrum{k}] run data modify entity @s transformation set value [1.00f,0.00f,0.00f,0.00f,0.00f,{0.1+8*spectrum[j][k]:.4f}f,0.00f,0.00f,0.00f,0.00f,0.80f,0.00f,0.00f,0.00f,0.00f,1.00f]"
            )
    print("频谱成功\n")

    # tp
    if move_mode == "legacy":
        for i in range(max_tick + 1 + start_delay + 2):
            mcfunction[i].append(
                f"execute as @e[type=minecraft:armor_stand,tag=piano] at @s run tp ~1 ~ ~"
            )
            mcfunction[i].append(f"execute as @e[tag=keys] at @s run tp ~1 ~ ~")
            mcfunction[i].append(f"execute as @e[tag=spectrum] at @s run tp ~1 ~ ~")
            if i == 0:
                mcfunction[i].append(
                    f"execute as @e[type=minecraft:armor_stand,tag=piano] at @s run tp @p ~-32 ~23 ~52 -90 1"
                )
            else:
                mcfunction[i].append(f"execute as @p at @p run tp ~1 ~ ~")
    else:
        for i in range(max_tick + 1 + start_delay + 2):
            mcfunction[i].append(f"execute as @e[tag=waterfall] at @s run tp ~-1 ~ ~")
            mcfunction[i].append(f"execute as @e[tag=expblock] at @s run tp ~-1 ~ ~")
            if i == 0:
                mcfunction[i].append(
                    f"execute as @e[type=minecraft:armor_stand,tag=piano] at @s run tp @p ~-32 ~23 ~52 -90 1"
                )
                mcfunction[i].append(
                    f"execute as @e[tag=spectrum] at @s run tp ~-1 ~ ~"
                )

    # 写入文件
    for i in range(
        max_tick + 1 + start_delay + fade_time
    ):  # 2tick瀑布流消失，包含在频谱淡出里
        with open(f"tick{i}.mcfunction", "w", encoding="utf-8") as f:
            mcfunction[i].append(f"schedule function tick{i+1} 1")
            f.write("\n".join(mcfunction[i]))
