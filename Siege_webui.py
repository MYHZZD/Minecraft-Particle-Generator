import gradio as gr
import pretty_midi
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import json
import os
import time
import zipfile
import tempfile
import io
import siegedata
import siegefunc
import extrafunction

MAX_TRACKS = siegedata.MAX_TRACKS
GM_PROGRAM_NAMES = siegedata.GM_PROGRAM_NAMES
MC_PROGRAM_NAMES = siegedata.MC_PROGRAM_NAMES

# 16 种高对比度颜色
channel_colors = ["#e41a1c", "#377eb8", "#4daf4a", "#984ea3", "#ff7f00", "#ffff33", "#a65628", "#f781bf", "#999999", "#66c2a5", "#fc8d62", "#8da0cb", "#e78ac3", "#a6d854", "#ffd92f", "#e5c494"]


def midi_to_note_name(midi_note, use_flats=False):
    """
    use_flats若为True使用降号表示,否则使用升号表示
    """
    if not 0 <= midi_note <= 127:
        raise ValueError(f"MIDI 编号必须在 0-127 之间，实际为 {midi_note}")

    # 12 个半音的音名列表(升号版和降号版)
    note_names_sharp = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    note_names_flat = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]

    pitch_class = midi_note % 12
    note_name = note_names_flat[pitch_class] if use_flats else note_names_sharp[pitch_class]
    octave = midi_note // 12 - 1  # MIDI 60 = C4
    return f"{note_name}{octave}"


def recommend_range(low, high):
    def binary_search_insert_pos(num, arr):  # 二分法查找
        left, right = 0, len(arr)
        while left < right:
            mid = (left + right) // 2
            if arr[mid] < num:  # 插在相同值左边
                left = mid + 1
            else:
                right = mid
        return left

    pitch_all = [6, 18, 30, 42, 54, 66, 78, 90, 102, 114, 126]  # pitch_all[0]对应F#-1，因此角标要-1输出
    minleft = binary_search_insert_pos(low, pitch_all)
    maxright = binary_search_insert_pos(high, pitch_all)
    return f"F#{minleft-2}-F#{maxright-1}"


def parse_midi(file_path):
    try:
        midi_data = extrafunction.process_midi_file(file_path)
        tracks = midi_data["tracks"]

        rows = []
        track_serial = 0  # 只统计有音符的轨道

        for _, track in enumerate(tracks):
            notes = track["notes"]
            if not notes:
                continue
            track_serial += 1

            # 按通道统计
            channel_notes = {}  # channel -> list of pitches
            for note_event in notes:
                ch = note_event["channel"]
                pitch = note_event["note"]
                channel_notes.setdefault(ch, []).append(pitch)

            total_notes = len(notes)

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
                    "通道组成": "; ".join(ch_parts),
                    "音符数量": total_notes,
                    "最小音高": "; ".join(min_parts),
                    "最大音高": "; ".join(max_parts),
                    "推荐音域": "; ".join(range_parts),
                }
            )

        df = pd.DataFrame(rows)
        return df

    except Exception as e:
        raise gr.Error(f"解析失败：{str(e)}")


def on_file_upload(file):
    """上传文件后：更新信息表格、轨道数量，并显示对应数量的参数组"""
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


def generate(file, num_tracks, *args):
    results = []
    for i in range(num_tracks):
        ida = i * 13
        results.append(
            {
                "轨道索引": int(i),
                "X": int(args[ida]),
                "Y": int(args[ida + 1]),
                "结构模式": int(args[ida + 2]),
                "旋律Y": int(args[ida + 3]),
                "音色1": str(args[ida + 4]),
                "音色2": str(args[ida + 5]),
                "音色3": str(args[ida + 6]),
                "音色4": str(args[ida + 7]),
                "特效模式": int(args[ida + 8]),
                "旋律X": int(args[ida + 9]),
                "ADSR": list(args[ida + 10][2]),
                "包络模式": str(args[ida + 11]),
                "粒子特效": str(args[ida + 12]),
            }
        )
    midievent, max_tick = extrafunction.mcmappings(extrafunction.process_midi_file(file), 8)
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


def generate_envelope(attack_len, decay_len, sustain_level, release_len, decay_curve=0.0, release_curve=0.0):  # 核心包络计算
    attack_len, decay_len, release_len, sustain_len = adjust_lengths(attack_len, decay_len, release_len)

    attack_end = attack_len
    decay_end = attack_len + decay_len
    sustain_end = decay_end + sustain_len

    decay_alpha = 5.0**decay_curve
    release_alpha = 5.0**release_curve

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
                y = interpolate_curve(peak_y, sustain_level, t, decay_alpha)
        elif x <= sustain_end:
            y = sustain_level
        else:
            if release_len == 0:
                y = 0
            else:
                t = (x - sustain_end) / release_len
                y = interpolate_curve(sustain_level, 0, t, release_alpha)

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


# 构建界面
with gr.Blocks(title="MIDI 轨道参数", theme=gr.themes.Soft(), fill_width=True) as demo:
    gr.Markdown("# 🎵 MIDI 轨道配置")

    with gr.Row():
        upload = gr.File(label="上传 MIDI 文件", file_types=[".mid", ".midi"], type="filepath")

    info_df = gr.DataFrame(label="轨道基础信息", interactive=False, datatype=["number", "html", "number", "html", "html", "html"])
    state_num_tracks = gr.Number(value=0, visible=False)

    # 动态创建轨道参数组
    track_groups = []
    track_titles = []
    all_components = []  # 存储所有参数，用于生成回调

    for i in range(MAX_TRACKS):
        with gr.Group(visible=False) as group:
            title_md = gr.Markdown(f"### 轨道 {i} 参数")
            with gr.Row(scale=0):
                mode_d = gr.Dropdown(label="结构模式", choices=[0, 1, 2, 3, 99], value=0, scale=0)
                tmode_d = gr.Dropdown(label="特效模式", choices=[0, 1], value=0, scale=0)
                x_s = gr.Slider(label="DELAY X", minimum=4, maximum=48, step=1, value=22)  # delay轨右侧距离 左侧依靠对称
                y_s = gr.Slider(label="DELAY Y", minimum=-48, maximum=48, step=1, value=0)  # delay轨上下位置
                mainx_s = gr.Slider(label="旋律 X", minimum=-2, maximum=2, step=1, value=0)  # 旋律轨左右距离
                mainy_s = gr.Slider(label="旋律 Y", minimum=-50, maximum=50, step=1, value=0)  # 旋律轨上下位置 ±48外不生成
                timbre1_d = gr.Dropdown(choices=MC_PROGRAM_NAMES, label="音色1", value=MC_PROGRAM_NAMES[10])
            with gr.Accordion("高级选项", open=False):
                with gr.Row(scale=0, equal_height="true"):
                    envelope_r = gr.Radio(choices=["NONE", "ADSR", "CC"], label="包络模式", value="NONE")
                    timbre2_d = gr.Dropdown(choices=MC_PROGRAM_NAMES, label="音色2", value=MC_PROGRAM_NAMES[0])
                    timbre3_d = gr.Dropdown(choices=MC_PROGRAM_NAMES, label="音色3", value=MC_PROGRAM_NAMES[0])
                    timbre4_d = gr.Dropdown(choices=MC_PROGRAM_NAMES, label="音色4", value=MC_PROGRAM_NAMES[0])
                    particle_f = gr.UploadButton(label="上传特效配置", file_types=[".json", ".mcfunction"], type="filepath")
                with gr.Accordion("ADSR设置", open=False):
                    with gr.Row():
                        with gr.Column(scale=1):
                            attack_slider = gr.Slider(0, peak_x + 1, value=0, step=1, label="Attack 长度")
                            decay_slider = gr.Slider(0, peak_x + 1, value=32, step=1, label="Decay 长度")
                            sustain_slider = gr.Slider(0, peak_y + 1, value=24, step=1, label="Sustain 电平")
                            release_slider = gr.Slider(0, peak_x + 1, value=24, step=1, label="Release 长度")
                            decay_curve_slider = gr.Slider(-1, 1, value=0, step=0.01, label="Decay 弯曲度")
                            release_curve_slider = gr.Slider(-1, 1, value=0, step=0.01, label="Release 弯曲度")

                        with gr.Column(scale=2):
                            plot_output = gr.Plot(label="包络示意图")

                    # 创建隐形容器暂存adsr列表
                    state_adsr = gr.State()

                    # 所有滑块绑定 release 事件，即时更新图表
                    all_adsr_inputs = [attack_slider, decay_slider, sustain_slider, release_slider, decay_curve_slider, release_curve_slider]

                    for slider in all_adsr_inputs:  # 先传参到state缓存，再输入图表
                        slider.release(fn=generate_envelope, inputs=all_adsr_inputs, outputs=state_adsr).then(fn=plot_envelope, inputs=[sustain_slider, state_adsr], outputs=plot_output)

                    # 页面加载时绘制默认曲线
                    demo.load(fn=generate_envelope, inputs=all_adsr_inputs, outputs=state_adsr).then(fn=plot_envelope, inputs=[sustain_slider, state_adsr], outputs=plot_output)

        track_groups.append(group)
        track_titles.append(title_md)
        all_components.extend([x_s, y_s, mode_d, mainy_s, timbre1_d, timbre2_d, timbre3_d, timbre4_d, tmode_d, mainx_s, state_adsr, envelope_r, particle_f])

    generate_btn = gr.Button("生成", variant="primary")
    download_zip = gr.File(label="📦 下载 ZIP 文件", interactive=False)

    # 上传文件后更新
    upload.change(fn=on_file_upload, inputs=upload, outputs=[info_df] + track_groups + track_titles).then(fn=lambda df: len(df), inputs=info_df, outputs=state_num_tracks)

    # 生成按钮
    generate_btn.click(fn=generate, inputs=[upload] + [state_num_tracks] + all_components, outputs=download_zip)


if __name__ == "__main__":
    demo.launch(inbrowser=True)
