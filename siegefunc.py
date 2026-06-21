import math
import numpy as np
import mido
import copy
from mido import MidiFile
import siegedata

player_speed = 0.5  # 玩家每tick前进距离

start_delay = 40  # 从开始到第一个音符播放的距离
inplace_distance = 3  # 音符入轨距离与激活距离之差
note_point = [80, 10, 0]  # 音符生成点，x值要大于start_delay
structure_point = [20, 0, 0]  # 结构生成点
pig_point = [0, 0, 0]  # 基准点

# 玩家移动，结构生成，音符生成，三者同时开始
# 音符动画用时
summon_time = int((start_delay - inplace_distance) / player_speed)
# 音符x方向移动距离
summon_x = note_point[0] - start_delay
# 轨道动画用时，音符盒入轨时正好动画结束
structure_time = int((structure_point[0] - inplace_distance) / player_speed)

# 注意方向替换，面朝太阳时，x轴是前后，z轴是左右。向前向右为正方向
# 一切tick计算均包含起点和终点
# 一切从距离到用时的折算都要考虑player speed


def pos2time(pos):
    return int(pos / player_speed)


def time2pos(time):
    return float(time * player_speed)


def spiral(x, y, start, direction, total, tick):  # x y 起始相位 方向正负 总旋转角度 总时间
    # 将度数转换为弧度
    start_rad = math.radians(start)
    total_rad = math.radians(total)
    target_angle = math.atan2(y, x)

    # 沿着指定方向转到目标角度所需的角度 取模[0, 2π)
    if direction == 1:  # 逆时针
        delta = (target_angle - start_rad) % (2 * math.pi)
    else:  # 顺时针
        delta = (start_rad - target_angle) % (2 * math.pi)

    R = math.hypot(x, y)  # 终点到原点的距离
    steps = tick - 1
    points = []

    for i in range(tick):
        t = i / steps
        r = R * t  # 当前半径
        angle_rad = start_rad + direction * (delta + total_rad) * t
        px = r * math.cos(angle_rad)
        py = r * math.sin(angle_rad)
        points.append([px, py])

    return points


def linepath(a, n):
    v = 1.0 / (n - 1)
    T_acc = 0.75 * (n - 1)
    a1 = 2 * v / T_acc
    a2 = 3 * a1
    result = []

    for t in range(n):
        if t <= T_acc:
            s = 0.5 * a1 * t * t
        else:
            dt = t - T_acc
            s = 0.5 * a1 * T_acc * T_acc + 2 * v * dt - 0.5 * a2 * dt * dt
        result.append(a * s)
    return result


# 标记包括音符标记track/note 位置标记right/left 生成时间标记summontick 统一标记
def summon_note_block(dx, dy, dz, instrument, note_pitch, tags, summon_tick):
    all_tags = tags + ["note", f"summontick{summon_tick}", "siege"]
    tags_json = "[" + ",".join(f'"{t}"' for t in all_tags) + "]"

    return (
        f"execute at @e[type=minecraft:block_display,tag=pig] run summon block_display "
        f'~{dx} ~{dy} ~{dz} {{block_state:{{Name:"minecraft:note_block",'
        f'Properties:{{powered:"false",instrument:"{instrument}",note:"{note_pitch}"}}}},'
        f"brightness:{{block:0,sky:15}},Tags:{tags_json}}}"
    )


def move_note_entity(tag, pig_offset_x, pig_offset_y, pig_offset_z, target_x, target_y, target_z):
    return (
        f"execute as @e[tag={tag[0]},tag={tag[1]}] at @e[type=minecraft:block_display,tag=pig] "
        f"positioned ~{pig_offset_x:.4f} ~{pig_offset_y:.4f} ~{pig_offset_z:.4f} "
        f"run tp @s ~{target_x:.4f} ~{target_y:.4f} ~{target_z:.4f}"
    )


# 激活音符盒 考虑player speed
def power_note_entity(mcfunction, time, tag, loctag, pitch, timbre):
    if loctag in ("mainright", "mainleft"):
        power_delay = 0
    elif loctag == "left":
        power_delay = 1
    elif loctag == "right":
        power_delay = 2
    # 在time时刻放下的音符盒，在距离(start_delay)/速度=时间后激活。power delay是定值
    mcfunction[time + pos2time(start_delay) + power_delay].append(
        f'execute as @e[type=minecraft:block_display,tag=summontick{time},tag={tag},tag={loctag}] run data merge entity @s {{block_state:{{Properties:{{powered:"true"}}}}}}'
    )

    # 声音比power快1tick，不知道为啥，先+1对齐
    pitch_volume = math.pow(2, -(pitch - 12) / 12)
    mcfunction[time + pos2time(start_delay) + power_delay + 1].append(
        f"execute at @e[type=minecraft:block_display,tag=summontick{time},tag={tag},tag={loctag}] run playsound minecraft:block.note_block.{timbre} master @p ~ ~ ~ 3 {pitch_volume:.8f}"
    )

    # 粒子
    mcfunction[time + pos2time(start_delay) + power_delay].append(
        f"execute at @e[type=minecraft:block_display,tag=summontick{time},tag={tag},tag={loctag}] run particle minecraft:note ~0.5 ~1.25 ~0.5 {pitch/24.0:.8f} 0 0 1 0 force @p"
    )


# 标记包括类型标记track/structure 位置标记right/left 生成时间标记summontick 动态标记state0 统一标记
def summon_structure(dx, dy, dz, block_name, track_id, struc_tick, tag_suffix):  # 生成轨道
    if dz == 0:
        start_z = 0.495
    else:
        start_z = 0.000 if dz > 0 else 0.990
    return (
        f"execute at @e[type=minecraft:block_display,tag=pig] run summon block_display "
        f'~{dx} ~{dy} ~{dz} {{block_state:{{Name:"minecraft:{block_name}"}},'
        f'brightness:{{block:0,sky:15}},Tags:["track{track_id}","structure","{tag_suffix}","state0",'
        f'"summontick{struc_tick}","siege"],'
        f"transformation:[0.01f,0.00f,0.00f,0.495f,0.00f,0.01f,0.00f,0.495f,0.00f,0.00f,0.01f,{start_z}f,0.00f,0.00f,0.00f,1.00f]}}"
    )


# 标记包括类型标记track/repeater 位置标记right/left 生成时间标记summontick 动态标记state0 统一标记
def summon_repeater(dx, dy, dz, delay, facing, track_id, struc_tick, tag_suffix):  # 生成中继器 facing是屁股方向
    if dz == 0:
        start_z = 0.495
    else:
        start_z = 0.000 if dz > 0 else 0.990
    if facing == "ahead":
        face = "west"
    elif facing == "side":
        if dz > 0:
            face = "north"
        else:
            face = "south"
    return (
        f"execute at @e[type=minecraft:block_display,tag=pig] run summon block_display "
        f'~{dx} ~{dy} ~{dz} {{block_state:{{Name:"minecraft:repeater",'
        f'Properties:{{powered:"false",delay:"{delay}",facing:{face}}}}},'
        f'brightness:{{block:0,sky:15}},Tags:["track{track_id}","structure","repeater","{tag_suffix}","state0",'
        f'"summontick{struc_tick}","siege"],'
        f"transformation:[0.01f,0.00f,0.00f,0.495f,0.00f,0.01f,0.00f,0.495f,0.00f,0.00f,0.01f,{start_z}f,0.00f,0.00f,0.00f,1.00f]}}"
    )


# 包络分支结构 不包括首尾 起点z轴不能为0
def adsr_branch(dx, dy, dz, block_name, track_id, struc_tick, tag_suffix, length, mcfunction):
    start_z = 0.000 if dz > 0 else 0.990
    for le in range(0, int(dz / abs(dz) * abs(length)), int(dz / abs(dz))):  # range(0,-5,-1)=[0,-1,-2,-3,-4]
        le = int(le * length / abs(length))
        if le != 0:
            if block_name != "redstone_wire":
                mcfunction[struc_tick].append(
                    f"execute at @e[type=minecraft:block_display,tag=pig] run summon block_display "
                    f'~{dx} ~{dy} ~{dz+le} {{block_state:{{Name:"minecraft:{block_name}"}},'
                    f'brightness:{{block:0,sky:15}},Tags:["track{track_id}","structure","{tag_suffix}","state0",'
                    f'"summontick{struc_tick}","siege"],'
                    f"transformation:[0.01f,0.00f,0.00f,0.495f,0.00f,0.01f,0.00f,0.495f,0.00f,0.00f,0.01f,{start_z}f,0.00f,0.00f,0.00f,1.00f]}}"
                )
            else:
                if abs(length) != 1:
                    mcfunction[struc_tick].append(
                        f"execute at @e[type=minecraft:block_display,tag=pig] run summon block_display "
                        f'~{dx} ~{dy} ~{dz+le} {{block_state:{{Name:"minecraft:redstone_wire",'
                        f'Properties:{{power:"0",north:"side",south:"side"}}}},'
                        f'brightness:{{block:0,sky:15}},Tags:["track{track_id}","structure","redstonewire","{tag_suffix}","state0",'
                        f'"summontick{struc_tick}","siege"],'
                        f"transformation:[0.01f,0.00f,0.00f,0.495f,0.00f,0.01f,0.00f,0.495f,0.00f,0.00f,0.01f,{start_z}f,0.00f,0.00f,0.00f,1.00f]}}"
                    )
                else:
                    mcfunction[struc_tick].append(
                        f"execute at @e[type=minecraft:block_display,tag=pig] run summon block_display "
                        f'~{dx} ~{dy} ~{dz+le} {{block_state:{{Name:"minecraft:redstone_wire",'
                        f'Properties:{{power:"0",north:"side",south:"side",east:"side",west:"side"}}}},'
                        f'brightness:{{block:0,sky:15}},Tags:["track{track_id}","structure","redstonewire","{tag_suffix}","state0",'
                        f'"summontick{struc_tick}","siege"],'
                        f"transformation:[0.01f,0.00f,0.00f,0.495f,0.00f,0.01f,0.00f,0.495f,0.00f,0.00f,0.01f,{start_z}f,0.00f,0.00f,0.00f,1.00f]}}"
                    )


def create_cross_note():  # speed 0.5时主旋律的判断
    flag = True

    def cross_note(z, x, change):
        nonlocal flag  # 声明要修改外部变量
        if x != 0:
            return z
        else:
            result = z if flag else -z
            if change:
                flag = not flag  # 修改了外部函数的变量
            return result

    return cross_note  # 返回内部函数本身


def gen(midievent, result, max_tick):
    mcfunction = [[] for _ in range(max_tick + 3 + pos2time(start_delay))]  # 时间

    # 骑猪tp，猪为原点
    mcfunction[0].append("execute as @p at @s run tp @s ~ ~ ~ -90 -10")
    mcfunction[0].append('execute as @p at @s align xyz run summon block_display ~ ~ ~ {Tags:["pig","siege"]}')
    # 解决不骑乘在中间的问题
    mcfunction[0].append('execute as @e[type=minecraft:block_display,tag=pig] at @s run summon block_display ~-10 ~2 ~0.5 {Tags:["rider","siege"]}')
    mcfunction[0].append("execute as @e[type=minecraft:block_display] run data merge entity @s {start_interpolation:0,teleport_duration:1}")
    mcfunction[0].append("ride @p mount @n[type=minecraft:block_display,tag=rider]")

    note_track_id = 0
    for i, track in enumerate(midievent["tracks"]):  # i为轨道序号
        total_ticks = int(track["total_ticks"])
        if track["notes"] != []:
            track_x = result[note_track_id]["X"]
            track_y = result[note_track_id]["Y"]
            track_mode = result[note_track_id]["结构模式"]
            mainx = result[note_track_id]["旋律X"]
            mainy = result[note_track_id]["旋律Y"]
            timbre1 = result[note_track_id]["音色1"]
            timbre2 = result[note_track_id]["音色2"]
            timbre3 = result[note_track_id]["音色3"]
            timbre4 = result[note_track_id]["音色4"]
            effect_mode = result[note_track_id]["特效模式"]
            adsr = result[note_track_id]["ADSR"]
            envelope_mode = result[note_track_id]["包络模式"]

            note_track_id += 1  # 非空轨道，解决mido提取到空轨的问题

            pitch_all = [18, 30, 42, 54, 66, 78, 90, 102, 114, 126, 6]  # 所有的F#，因为最低八度是C-1所以正好放在最后一个，用[-1]调用

            timbre_list = [timbre1, timbre2, timbre3, timbre4]  # 用channel序号调用

            if track_mode in (0, 1, 2, 3):  # 基础对称轨 纯旋律轨 左右分轨
                # delay音符盒生成轨迹，涉及从结构点到生成点的坐标变换 -note_point[1]
                pos_x = linepath(-summon_x, summon_time)
                if effect_mode == 0:  # 螺旋线
                    pos_note = spiral(track_x, track_y - note_point[1], 0, 1, 360, summon_time)  # YOZ平面轨迹
                    pos_note_3d = [[pos_x[pos_count], py, px] for pos_count, (px, py) in enumerate(pos_note)]
                elif effect_mode == 1:  # 直线
                    pos_y = linepath(track_y - note_point[1], summon_time)
                    pos_z = linepath(track_x, summon_time)
                    pos_note_3d = [[pos_x[pos_count], pos_y[pos_count], pos_z[pos_count]] for pos_count, _ in enumerate(pos_x)]
                # 旋律生成轨迹
                mainpos_y = linepath(mainy - note_point[1], summon_time)
                mainpos_z = linepath(mainx, summon_time)
                # speed=0.5的额外偏移
                if player_speed == 0.5:
                    speed_z = linepath(2, summon_time)
                    speed_x = linepath(1, summon_time)
                # 额外包络 adsr是包络列表，env_z是运动轨迹二维列表
                if envelope_mode in ("NONE", "CC"):
                    adsr_n = [0 for _ in range(len(adsr))]
                if envelope_mode == "ADSR":
                    adsr_n = adsr
                env_z = [linepath(adsr_value, summon_time) for _, adsr_value in enumerate(adsr_n)]
                # 专门处理cc
                if envelope_mode == "CC":
                    # 创建对应全部时刻的CC列表，后续对每个音符映射到单独的adsr再计算env_z
                    cc_list = [0] * (max_tick + 2 * len(adsr_n) + 1)  # 额外多2个adsr_n的长度防止最后一刻越界。映射是2对1
                    last_value = 64
                    last_tick = 0
                    for cc_event in track["cc_events"]:
                        if cc_event["control"] == 1:
                            # 填充从 last_tick 到当前 tick-1 的区间（使用上一个值）
                            if cc_event["tick"] > last_tick:
                                cc_list[last_tick : cc_event["tick"]] = [last_value] * (cc_event["tick"] - last_tick)
                            # 当前 tick 设置新值
                            cc_list[cc_event["tick"]] = cc_event["value"]
                            last_value = cc_event["value"]
                            last_tick = cc_event["tick"]
                    # 填充末尾
                    cc_list[last_tick : max_tick + 2 * len(adsr_n) + 1] = [last_value] * (max_tick + 2 * len(adsr_n) + 1 - last_tick)

                have_note = {}  # 记录是否有音符盒，否则草方块占位。delay轨要考虑包络，储存 {位置:[垫块,包络]}
                have_note_main = {}  # 旋律轨占位
                cross_note = create_cross_note()  # 交替左右生成

                # 音符处理
                for j, note_event in enumerate(track["notes"]):  # j为音符序号
                    k = note_event["start_tick"]  # k为起始时间
                    note_duration = note_event["duration"]
                    # 通道控制音色，从音色中提取底层F#编号，获取对应F# id，相减
                    # 例如"5-7 gold_block bell" split()[0]是八度，[1]是垫块，[2]是乐器
                    note_pitch = note_event["note"] - pitch_all[int(timbre_list[note_event["channel"]].split()[0].split("-")[0])]
                    note_instrument = timbre_list[note_event["channel"]].split()[2]
                    # 用CC LIST迭代env_z偏移量
                    if envelope_mode == "CC":
                        # 从 k 开始，每隔 2 个取一个，长度截取到 env_z 所需大小
                        adsr_n[:] = cc_list[k : k + 2 * len(env_z) : 2]
                        # 将CC值映射为距离
                        for idx, cc2env in enumerate(adsr_n):
                            if cc2env % 4 < 2:  # 余数0和1往下，余数2和3往上
                                adsr_n[idx] = -(int(math.floor(cc2env / 4)) - 16)  # 正值代表远离，127为正值，因此额外取负号
                            else:
                                adsr_n[idx] = -(int(math.floor(cc2env / 4)) + 1 - 16)
                        env_z = [linepath(cc_value, summon_time) for _, cc_value in enumerate(adsr_n)]

                    # 单独标记开始时间为奇数tick的音符
                    if k % 2 != 0:
                        k = k - 1
                        ifodd = True
                    else:
                        ifodd = False

                    for dur in range(note_duration):
                        if dur % 2 == 0:  # 2tick一个音符盒
                            # 音符生成部分
                            # 无论speed为何，都是固定生成。dur不是从距离折算的时间，无需折算
                            # delay
                            if track_mode in (0, 2, 3):  # 基础对称轨 左右分轨
                                if track_mode in (0, 3):  # 基础对称轨 右分轨
                                    mcfunction[k + dur].append(summon_note_block(note_point[0], note_point[1], note_point[2], note_instrument, note_pitch, [f"track{i}note{j}dur{dur}", "right"], k + dur))
                                    power_note_entity(mcfunction, k + dur, f"track{i}note{j}dur{dur}", "right", note_pitch, note_instrument)  # 这个要折算
                                if track_mode in (0, 2):  # 基础对称轨 左分轨
                                    mcfunction[k + dur].append(summon_note_block(note_point[0], note_point[1], note_point[2], note_instrument, note_pitch, [f"track{i}note{j}dur{dur}", "left"], k + dur))
                                    power_note_entity(mcfunction, k + dur, f"track{i}note{j}dur{dur}", "left", note_pitch, note_instrument)
                            # 标记该位置为已生成 x方向：[垫块,包络]。这里的start delay是距离量，不需要折算
                            have_note[time2pos(k) + time2pos(dur) + start_delay] = [timbre_list[note_event["channel"]].split()[1], adsr_n[int(dur / 2)]]  # +start_delay的意义是在k+dur时刻生成的音符会落在前方start_delay处
                            # 旋律
                            if dur == 0:  # 只在音头创建
                                if track_mode in (1, 2, 3) or track_mode == 0 and abs(mainy) <= 48:  # 符合要求的基础对称轨 纯旋律轨 左右分轨
                                    # 默认创建右侧或者居中旋律轨
                                    mcfunction[k + dur].append(summon_note_block(note_point[0], note_point[1], note_point[2], note_instrument, note_pitch, [f"track{i}note{j}dur{dur}", "mainright"], k + dur))
                                    power_note_entity(mcfunction, k + dur, f"track{i}note{j}dur{dur}", "mainright", note_pitch, note_instrument)
                                if mainx != 0 and (track_mode == 1 or track_mode == 0 and abs(mainy) <= 48):  # 如果是两条轨，且不是左右分轨
                                    mcfunction[k + dur].append(summon_note_block(note_point[0], note_point[1], note_point[2], note_instrument, note_pitch, [f"track{i}note{j}dur{dur}", "mainleft"], k + dur))
                                    power_note_entity(mcfunction, k + dur, f"track{i}note{j}dur{dur}", "mainleft", note_pitch, note_instrument)
                                # 标记该位置为已生成
                                have_note_main[time2pos(k) + time2pos(dur) + start_delay] = timbre_list[note_event["channel"]].split()[1]

                            # 音符移动部分
                            for move_dur in range(summon_time - 1):  # -1是因为初始tick0就是生成时刻
                                # 相对起点。考虑参考系一直在以speed向前运动
                                ox = note_point[0] - (move_dur + 1) * player_speed
                                oy = note_point[1]
                                oz = note_point[2]
                                # 目标点。相对于相对起点
                                tx, ty, _ = pos_note_3d[move_dur + 1]
                                tz = pos_note_3d[move_dur + 1][2] + env_z[int(dur / 2)][move_dur + 1]  # 叠加adsr偏移
                                txm = pos_note_3d[move_dur + 1][0]
                                tym = mainpos_y[move_dur + 1]
                                tzm = mainpos_z[move_dur + 1]

                                offset_x = 0
                                offset_y_delay = 0
                                offset_z_delay = 0
                                offset_z_main = 0

                                if player_speed == 0.5 and (k + dur) % 4 != 0:  # 非主干音符应用偏移
                                    # delay轨 固定偏移
                                    offset_x = speed_x[move_dur + 1]
                                    offset_z_delay = speed_z[move_dur + 1]

                                    # 旋律轨偏移
                                    if dur == 0:
                                        offset_z_main = cross_note(speed_z[move_dur + 1], mainx, False)

                                if player_speed == 0.5 and envelope_mode != "NONE":  # delay轨双层包络
                                    offset_z_delay = 0
                                    if (k + dur) % 4 == 0:  # 主干 底层
                                        offset_y_delay = -speed_x[move_dur + 1]  # -1
                                    if (k + dur) % 4 == 2:  # 分支 上层
                                        offset_y_delay = speed_z[move_dur + 1]  # -2

                                # delay
                                if track_mode in (0, 3):  # 基础对称轨 右分轨
                                    mcfunction[k + 1 + dur + move_dur].append(move_note_entity([f"track{i}note{j}dur{dur}", "right"], ox, oy, oz, tx - offset_x, ty + offset_y_delay, tz + offset_z_delay))
                                if track_mode in (0, 2):  # 基础对称轨 左分轨
                                    mcfunction[k + 1 + dur + move_dur].append(move_note_entity([f"track{i}note{j}dur{dur}", "left"], ox, oy, oz, tx - offset_x, ty + offset_y_delay, -tz - offset_z_delay))

                                # 旋律
                                if dur == 0:
                                    if track_mode in (1, 2, 3) or (track_mode == 0 and abs(mainy) <= 48):  # 符合要求的基础对称轨 纯旋律轨 左右分轨
                                        mcfunction[k + 1 + dur + move_dur].append(move_note_entity([f"track{i}note{j}dur{dur}", "mainright"], ox, oy, oz, txm - offset_x, tym, tzm + offset_z_main))
                                    if mainx != 0 and (track_mode == 1 or (track_mode == 0 and abs(mainy) <= 48)):  # 符合要求的基础对称轨 纯旋律轨 第二条轨
                                        mcfunction[k + 1 + dur + move_dur].append(move_note_entity([f"track{i}note{j}dur{dur}", "mainleft"], ox, oy, oz, txm - offset_x, tym, -tzm - offset_z_main))
                    if k % 4 != 0:  # 如果非主干，更新旋律轨左右
                        cross_note(0, mainx, True)

                cross_note = create_cross_note()  # 重置

                # 轨道生成
                for struc_tick, _ in enumerate(mcfunction):
                    if struc_tick <= max_tick + pos2time(start_delay - structure_point[0]):  # 最后一个方块生成
                        # 根据距离匹配
                        bottom_block = have_note.get(time2pos(struc_tick) + structure_point[0], ["grass_block", 0] if struc_tick % 2 != 0 else ["dirt", 0])  # 如果有音获取[垫块,包络],没有音根据是否2的倍数选垫块
                        bottom_block_main = have_note_main.get(time2pos(struc_tick) + structure_point[0], "grass_block" if struc_tick % 2 != 0 else "dirt")  # 垫块
                        spawn_top = (struc_tick % 2 == 0) and (time2pos(struc_tick) + structure_point[0] not in have_note) or (struc_tick % 2 == 0) and bottom_block[1] != 0  # 不存在音或者包络不为零
                        spawn_top_main = (struc_tick % 2 == 0) and (time2pos(struc_tick) + structure_point[0] not in have_note_main)

                        offset_x_delay = offset_y_delay = offset_z_delay = offset_x_main = offset_z_main = 0

                        if player_speed == 0.5:
                            # 根据有无包络计算delay xyz偏移。旋律x取无包络模式，z取交叉模式
                            # 非包络偏移 (余数 -> (x, z))
                            offsets = {0: (0, 0), 1: (0.5, 1), 2: (1, 2), 3: (0.5, 0)}  # x: 0 0.5 1 1.5 -> 0 0 0 1
                            offset_x_delay, offset_z_delay = offsets[struc_tick % 4]
                            offset_x_main = offset_x_delay  # 旋律轨一直是无包络模式，先赋值
                            # 包络偏移
                            if envelope_mode != "NONE":
                                env_offsets = {0: (0, -1, 0), 1: (1.5, 2, 0), 2: (1, 2, 0), 3: (0.5, -1, 0)}  # x: 0 0.5 1 1.5 -> 0 -1 0 1
                                offset_x_delay, offset_y_delay, offset_z_delay = env_offsets[struc_tick % 4]
                            # 主旋律 Z 交叉
                            if struc_tick % 4 == 1:
                                pos = time2pos(struc_tick + 1) + structure_point[0]
                                if pos in have_note_main:
                                    offset_z_main = cross_note(1, mainx, False)
                                else:
                                    offset_z_main = 100
                            elif struc_tick % 4 == 2:
                                pos = time2pos(struc_tick) + structure_point[0]
                                if pos in have_note_main:
                                    offset_z_main = cross_note(2, mainx, True)
                                else:
                                    offset_z_main = 100

                        ox = structure_point[0] - offset_x_delay
                        oxm = structure_point[0] - offset_x_main
                        oy = track_y + offset_y_delay
                        oz = track_x + offset_z_delay
                        ozm = mainx + offset_z_main

                        if track_mode in (0, 3):  # 基础对称轨 右分轨
                            if bottom_block[1] == 0:  # 没有音或者包络为0
                                mcfunction[struc_tick].append(summon_structure(ox, oy - 1, oz, bottom_block[0], i, struc_tick, "right"))
                            else:  # 包络不为0,一定有音
                                mcfunction[struc_tick].append(summon_structure(ox, oy - 1, oz, "dirt", i, struc_tick, "right"))  # 轨道上生成土块
                                mcfunction[struc_tick].append(summon_structure(ox, oy - 1, oz + bottom_block[1], bottom_block[0], i, struc_tick, "right"))  # 偏移生成垫块
                                adsr_branch(ox, oy - 1, oz, "grass_block", i, struc_tick, "right", bottom_block[1], mcfunction)  # 生成包络分支
                                adsr_branch(ox, oy, oz, "redstone_wire", i, struc_tick, "right", bottom_block[1], mcfunction)  # 生成包络红石线
                            if spawn_top:  # 上层，避让音符盒
                                mcfunction[struc_tick].append(summon_structure(ox, oy, oz, "grass_block", i, struc_tick, "right"))
                        if track_mode in (0, 2):  # 基础对称轨 左分轨
                            if bottom_block[1] == 0:
                                mcfunction[struc_tick].append(summon_structure(ox, oy - 1, -oz, bottom_block[0], i, struc_tick, "left"))
                            else:
                                mcfunction[struc_tick].append(summon_structure(ox, oy - 1, -oz, "dirt", i, struc_tick, "left"))
                                mcfunction[struc_tick].append(summon_structure(ox, oy - 1, -oz - bottom_block[1], bottom_block[0], i, struc_tick, "left"))
                                adsr_branch(ox, oy - 1, -oz, "grass_block", i, struc_tick, "left", bottom_block[1], mcfunction)
                                adsr_branch(ox, oy, -oz, "redstone_wire", i, struc_tick, "left", bottom_block[1], mcfunction)
                            if spawn_top:
                                mcfunction[struc_tick].append(summon_structure(ox, oy, -oz, "grass_block", i, struc_tick, "left"))
                        if track_mode in (1, 2, 3) or track_mode == 0 and abs(mainy) <= 48:  # 符合要求的基础对称轨 纯旋律轨 左右分轨
                            mcfunction[struc_tick].append(summon_structure(oxm, mainy - 1, ozm, bottom_block_main, i, struc_tick, "mainright"))
                            if spawn_top_main:
                                mcfunction[struc_tick].append(summon_structure(oxm, mainy, ozm, "grass_block", i, struc_tick, "mainright"))
                        if mainx != 0 and (track_mode == 1 or track_mode == 0 and abs(mainy) <= 48):  # 符合要求的基础对称轨 纯旋律轨 第二条轨
                            mcfunction[struc_tick].append(summon_structure(oxm, mainy - 1, -ozm, bottom_block_main, i, struc_tick, "mainleft"))
                            if spawn_top_main:
                                mcfunction[struc_tick].append(summon_structure(oxm, mainy, -ozm, "grass_block", i, struc_tick, "mainleft"))

                cross_note = create_cross_note()  # 重置

                # 中继器生成
                for struc_tick, _ in enumerate(mcfunction):
                    if struc_tick <= max_tick + pos2time(start_delay - structure_point[0]):
                        delay, facing, ox, oy, oz, oxm, ozm, facingm = (1, "ahead", 0, 0, 0, 0, 0, "ahead")
                        if player_speed == 0.5:
                            # 与轨道一样的流程，先计算无包络模式，给旋律轨x赋值。再计算有包络模式，根据情况给delay xyz赋值。最后根据交叉计算旋律z
                            delay = 2
                            env_offsets = {0: (0, 0, 0, "side"), 1: (0.5, 0, 1, "side"), 2: (0, 0, 0, "side"), 3: (0.5, 0, 0, "ahead")}  # x: 0 0.5 1 1.5 -> 0 0 0 1
                            oxm, _, _, facingm = env_offsets[struc_tick % 4]  # 先赋值旋律轨X和中继器方向
                            if envelope_mode != "NONE":
                                env_offsets = {0: (0, 0, 0, "side"), 1: (1.5, 2, 0, "ahead"), 2: (0, 0, 0, "side"), 3: (0.5, -1, 0, "ahead")}  # x: 0 0.5 1 1.5 -> 0 -1 0 1
                            ox, oy, oz, facing = env_offsets[struc_tick % 4]
                            if struc_tick % 4 == 1:  # 下一个是分叉
                                pos = time2pos(struc_tick + 1) + structure_point[0]
                                if pos in have_note_main:
                                    ozm = cross_note(1, mainx, True)
                                else:
                                    ozm = 100

                        if struc_tick % 2 != 0:  # 与音符错开
                            if track_mode in (0, 3):  # 基础对称轨 右分轨
                                mcfunction[struc_tick].append(summon_repeater(structure_point[0] - ox, track_y + oy, track_x + oz, delay, facing, i, struc_tick, "right"))
                            if track_mode in (0, 2):  # 基础对称轨 左分轨
                                mcfunction[struc_tick].append(summon_repeater(structure_point[0] - ox, track_y + oy, -track_x - oz, delay, facing, i, struc_tick, "left"))
                            if track_mode in (1, 2, 3) or track_mode == 0 and abs(mainy) <= 48:  # 符合要求的基础对称轨 纯旋律轨 左右分轨
                                mcfunction[struc_tick].append(summon_repeater(structure_point[0] - oxm, mainy, mainx + ozm, delay, facingm, i, struc_tick, "main"))
                            if mainx != 0 and (track_mode == 1 or track_mode == 0 and abs(mainy) <= 48):  # 符合要求的基础对称轨 纯旋律轨 第二条轨
                                mcfunction[struc_tick].append(summon_repeater(structure_point[0] - oxm, mainy, -mainx - ozm, delay, facingm, i, struc_tick, "main"))

    # 激活中继器和红石线，音符盒有自己的音高和音色，难以统一
    for power_tick, _ in enumerate(mcfunction):
        if power_tick <= max_tick + pos2time(start_delay - structure_point[0]):
            if power_tick % 2 != 0:  # 中继器 和音符交叉
                mcfunction[power_tick + pos2time(structure_point[0])].append(
                    f'execute as @e[type=minecraft:block_display,tag=summontick{power_tick},tag=repeater,tag=main] run data merge entity @s {{block_state:{{Properties:{{powered:"true"}}}}}}'
                )
                mcfunction[power_tick + pos2time(structure_point[0]) + 2].append(
                    f'execute as @e[type=minecraft:block_display,tag=summontick{power_tick},tag=repeater,tag=right] run data merge entity @s {{block_state:{{Properties:{{powered:"true"}}}}}}'
                )
                mcfunction[power_tick + pos2time(structure_point[0]) + 1].append(
                    f'execute as @e[type=minecraft:block_display,tag=summontick{power_tick},tag=repeater,tag=left] run data merge entity @s {{block_state:{{Properties:{{powered:"true"}}}}}}'
                )
            if power_tick % 2 == 0:  # 红石线 和音符同步
                mcfunction[power_tick + pos2time(structure_point[0]) + 2].append(
                    f'execute as @e[type=minecraft:block_display,tag=summontick{power_tick},tag=redstonewire,tag=right] run data merge entity @s {{block_state:{{Properties:{{power:"15"}}}}}}'
                )
                mcfunction[power_tick + pos2time(structure_point[0]) + 1].append(
                    f'execute as @e[type=minecraft:block_display,tag=summontick{power_tick},tag=redstonewire,tag=left] run data merge entity @s {{block_state:{{Properties:{{power:"15"}}}}}}'
                )

    for allfuncid, allfunc in enumerate(mcfunction):
        allfunc.append(f"execute as @e[type=minecraft:block_display,tag=pig] at @s run tp @s ~{player_speed} ~ ~")  # tp
        allfunc.append(f"execute as @e[type=minecraft:block_display,tag=rider] at @s run tp @s ~{player_speed} ~ ~")
        allfunc.append(f"execute as @e[tag=summontick{allfuncid}] run data merge entity @s {{start_interpolation:0,teleport_duration:1,interpolation_duration:1}}")  # 每个tick生成的实体配置过渡属性
        allfunc.append(f"kill @e[tag=summontick{int(allfuncid-(start_delay/player_speed)-20)},tag=note]")
        allfunc.append(f"kill @e[tag=summontick{int(allfuncid-(structure_point[0]/player_speed)-20)},tag=structure]")

    mcfunction[-1].append("ride @p dismount")
    mcfunction[-1].append("kill @e[tag=siege]")

    return mcfunction
