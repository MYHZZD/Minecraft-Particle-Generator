import gradio as gr
import pretty_midi
import pandas as pd
import json
import os
import siegedata
import siegefunc
import extrafunction

MAX_TRACKS = siegedata.MAX_TRACKS
GM_PROGRAM_NAMES = siegedata.GM_PROGRAM_NAMES
MC_PROGRAM_NAMES = siegedata.MC_PROGRAM_NAMES


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
    """解析MIDI文件，返回基础信息DataFrame和乐器列表"""
    try:
        midi = pretty_midi.PrettyMIDI(file_path)
        instruments = midi.instruments
        data = []
        for idx, inst in enumerate(instruments):
            program = inst.program
            is_drum = inst.is_drum
            num_notes = len(inst.notes)
            if num_notes > 0:
                pitches = [note.pitch for note in inst.notes]
                min_pitch = min(pitches)
                max_pitch = max(pitches)
            else:
                min_pitch = max_pitch = None
            data.append(
                {
                    "轨道索引": idx,
                    "音色名称": "Drum Kit" if is_drum else f"{program} : {GM_PROGRAM_NAMES[program]}",
                    "音符数量": num_notes,
                    "最小音高": "None" if min_pitch is None else f"{min_pitch} : {midi_to_note_name(min_pitch)}",
                    "最大音高": "None" if max_pitch is None else f"{max_pitch} : {midi_to_note_name(max_pitch)}",
                    "推荐音域": "None" if max_pitch is None else recommend_range(min_pitch, max_pitch),
                }
            )
        df = pd.DataFrame(data)
        return df, instruments
    except Exception as e:
        raise gr.Error(f"解析失败：{str(e)}")


def on_file_upload(file):
    """上传文件后：更新信息表格、轨道数量，并显示对应数量的参数组"""
    df, instruments = parse_midi(file)
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
    return [df, instruments] + group_updates + title_updates


def generate(file, num_tracks, *args):
    """收集参数"""
    results = []
    for i in range(num_tracks):
        ida = i * 10
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
            }
        )
    midievent, max_tick = extrafunction.mcmappings(extrafunction.process_midi_file(file), 8)
    mcfunction = siegefunc.gen(midievent, results, max_tick)
    # 写入文件
    for i in range(len(mcfunction)):
        with open(f"output/tick{i}.mcfunction", "w", encoding="utf-8") as f:
            if i != len(mcfunction) - 2:
                mcfunction[i].append(f"schedule function tick{i+1} 1")
            else:
                mcfunction[i].append(f"schedule function tick{i+1} 20")
            f.write("\n".join(mcfunction[i]))
    return json.dumps(results, indent=2, ensure_ascii=False)


# 构建界面
with gr.Blocks(title="MIDI 轨道参数", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🎵 MIDI 轨道配置")

    with gr.Row():
        upload = gr.File(label="上传 MIDI 文件", file_types=[".mid", ".midi"], type="filepath")

    info_df = gr.DataFrame(label="轨道基础信息", interactive=False)
    state_instruments = gr.State()
    state_num_tracks = gr.Number(value=0, visible=False)

    # 动态创建轨道参数组
    track_groups = []
    track_titles = []
    all_components = []  # 存储所有参数，用于生成回调

    for i in range(MAX_TRACKS):
        with gr.Group(visible=False) as group:
            title_md = gr.Markdown(f"### 轨道 {i} 参数")
            with gr.Row():
                mode_d = gr.Dropdown(label="结构模式", choices=[0, 1, 2, 3, 99], value=0, scale=0)
                x_s = gr.Slider(label="X", info="delay轨右侧距离 左侧依靠对称", minimum=4, maximum=48, step=1, value=22)
                y_s = gr.Slider(label="Y", info="delay轨上下位置", minimum=-48, maximum=48, step=1, value=0)
                mainx_s = gr.Slider(label="旋律轨X", info="旋律轨左右距离", minimum=-2, maximum=2, step=1, value=0)
                mainy_s = gr.Slider(label="旋律轨Y", info="旋律轨上下位置 ±48外不生成", minimum=-50, maximum=50, step=1, value=0)
            with gr.Row():
                tmode_d = gr.Dropdown(label="特效模式", choices=[0, 1], value=0, scale=0)
                timbre1_d = gr.Dropdown(choices=MC_PROGRAM_NAMES, label="音色1", value=MC_PROGRAM_NAMES[0])
                timbre2_d = gr.Dropdown(choices=MC_PROGRAM_NAMES, label="音色2", value=MC_PROGRAM_NAMES[0])
                timbre3_d = gr.Dropdown(choices=MC_PROGRAM_NAMES, label="音色3", value=MC_PROGRAM_NAMES[0])
                timbre4_d = gr.Dropdown(choices=MC_PROGRAM_NAMES, label="音色4", value=MC_PROGRAM_NAMES[0])

        track_groups.append(group)
        track_titles.append(title_md)
        all_components.extend([x_s, y_s, mode_d, mainy_s, timbre1_d, timbre2_d, timbre3_d, timbre4_d, tmode_d, mainx_s])

    generate_btn = gr.Button("生成", variant="primary")
    output_text = gr.Textbox(label="输出结果", lines=10, interactive=False)

    # 上传文件后更新
    upload.change(fn=on_file_upload, inputs=upload, outputs=[info_df, state_instruments] + track_groups + track_titles).then(fn=lambda df: len(df), inputs=info_df, outputs=state_num_tracks)

    # 生成按钮
    generate_btn.click(fn=generate, inputs=[upload] + [state_num_tracks] + all_components, outputs=output_text)


if __name__ == "__main__":
    demo.launch(inbrowser=True)
