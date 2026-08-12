import sys
import mido


def get_abs_time_track(track):
    abs_time = 0
    result = []
    for msg in track:
        abs_time += msg.time
        result.append((abs_time, msg))
    return result


def build_note_events_and_others(abs_events):
    """
    从绝对时间事件中提取：
      - notes: 音符字典列表（包含 start, end, channel, note, velocity, off_velocity）
      - other_events: 所有非音符事件（包括 CC、弯音、程序变更、元事件等）
    """
    notes = []
    other_events = []
    active_notes = []

    for abs_time, msg in abs_events:
        is_note_on = msg.type == "note_on" and msg.velocity > 0
        is_note_off = msg.type == "note_off" or (msg.type == "note_on" and msg.velocity == 0)

        if is_note_on:
            active_notes.append({"channel": msg.channel, "note": msg.note, "start": abs_time, "velocity": msg.velocity, "off_velocity": 0, "ended": False})
        elif is_note_off:
            # 匹配未关闭的同通道同音高音符
            for i in range(len(active_notes) - 1, -1, -1):
                n = active_notes[i]
                if not n["ended"] and n["channel"] == msg.channel and n["note"] == msg.note:
                    n["end"] = abs_time
                    n["off_velocity"] = msg.velocity if msg.type == "note_off" else 0
                    n["ended"] = True
                    notes.append(n)
                    del active_notes[i]
                    break
        else:
            # 所有非音符事件（CC, pitchwheel, program_change, meta, sysex, etc.）
            if msg.type != "track_name":  # 过滤掉 track_name
                other_events.append((abs_time, msg))

    # 处理未关闭的音符（文件结尾）
    if active_notes:
        last_time = abs_events[-1][0] if abs_events else 0
        for n in active_notes:
            if not n["ended"]:
                n["end"] = last_time
                n["off_velocity"] = 0
                notes.append(n)

    return notes, other_events


def compute_max_polyphony(notes):
    if not notes:
        return 0
    events = []
    for n in notes:
        events.append((n["start"], 1))
        events.append((n["end"], -1))
    events.sort(key=lambda x: (x[0], x[1]))  # 同一时刻先结束再开始，避免虚高
    current = 0
    max_poly = 0
    for _, delta in events:
        current += delta
        if current > max_poly:
            max_poly = current
    return max_poly


def assign_notes_to_tracks(notes, num_tracks):
    sorted_notes = sorted(notes, key=lambda x: (x["start"], -x["note"]))
    last_end = [0] * num_tracks
    track_notes = [[] for _ in range(num_tracks)]

    for n in sorted_notes:
        start = n["start"]
        chosen = None
        for i in range(num_tracks):
            if last_end[i] <= start:
                chosen = i
                break
        if chosen is None:
            chosen = min(range(num_tracks), key=lambda i: last_end[i])
        track_notes[chosen].append(n)
        last_end[chosen] = n["end"]

    return track_notes


def build_track_events(other_events, track_notes):
    """
    合并其他事件和本轨道的音符，返回按绝对时间排序的事件列表。
    """
    events = list(other_events)  # 复制所有非音符事件
    for n in track_notes:
        events.append((n["start"], mido.Message("note_on", channel=n["channel"], note=n["note"], velocity=n["velocity"])))
        off_vel = n.get("off_velocity", 0)
        events.append((n["end"], mido.Message("note_off", channel=n["channel"], note=n["note"], velocity=off_vel)))
    events.sort(key=lambda x: x[0])  # 按绝对时间排序
    return events


def process_track(abs_events):
    # 提取原始轨道名称
    original_name = None
    for _, msg in abs_events:
        if msg.type == "track_name":
            original_name = msg.name
            break

    notes, other_events = build_note_events_and_others(abs_events)
    if not notes:
        # 无音符，原样保留所有事件
        return [abs_events]

    max_poly = compute_max_polyphony(notes)
    if max_poly <= 1:
        return [abs_events]

    num_tracks = max_poly
    track_notes_list = assign_notes_to_tracks(notes, num_tracks)

    result_tracks = []
    for i, tn in enumerate(track_notes_list):
        events = build_track_events(other_events, tn)
        # 添加轨道名称
        if original_name:
            new_name = f"{original_name}{i+1}"
        else:
            new_name = f"Track {i+1}"
        events.insert(0, (0, mido.MetaMessage("track_name", name=new_name)))
        result_tracks.append(events)

    return result_tracks


def events_to_track(events, ticks_per_beat):
    track = mido.MidiTrack()
    prev_time = 0
    for abs_time, msg in events:
        delta = abs_time - prev_time
        if delta < 0:
            delta = 0
        msg = msg.copy(time=delta)
        track.append(msg)
        prev_time = abs_time
    return track


def main():
    INPUT_FILE = "input.mid"
    OUTPUT_FILE = "output.mid"

    try:
        mid = mido.MidiFile(INPUT_FILE)
    except FileNotFoundError:
        print(f"错误：找不到文件 '{INPUT_FILE}'")
        sys.exit(1)

    new_mid = mido.MidiFile(ticks_per_beat=mid.ticks_per_beat)

    for track in mid.tracks:
        abs_events = get_abs_time_track(track)
        processed = process_track(abs_events)
        for events in processed:
            new_track = events_to_track(events, mid.ticks_per_beat)
            new_mid.tracks.append(new_track)

    new_mid.save(OUTPUT_FILE)
    print(f"处理完成，输出文件: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
