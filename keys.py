# 定义键类型序列：True表示白键，False表示黑键
key_types = []

# 添加起始的A0、A#0、B0
key_types.append(True)  # A0 白键
key_types.append(False)  # A#0 黑键
key_types.append(True)  # B0 白键

# 添加第1到第7八度的键（每个八度12个键）
for octave in range(1, 8):  # 1到7八度
    # 每个八度内的音：C, C#, D, D#, E, F, F#, G, G#, A, A#, B
    notes = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    for note in notes:
        if "#" in note:  # 带#的是黑键
            key_types.append(False)
        else:  # 不带#的是白键
            key_types.append(True)

# 添加最后的C8白键
key_types.append(True)  # C8 白键

# 白键数量：52，黑键数量：36
print(f"总键数：{len(key_types)}")

# 生成指令
current_z_white = 0  # 当前白键的z坐标
instructions = []  # 存储所有指令

for i, is_white in enumerate(key_types):
    if is_white:  # 白键
        z = current_z_white
        # 白键指令模板
        cmd = f'execute at @e[type=minecraft:armor_stand,tag=piano] run summon block_display ~ ~1.5 ~{z} {{block_state:{{Name:"minecraft:iron_block"}},transformation:[16.00f,0.00f,0.00f,0.00f,0.00f,2.00f,0.00f,0.00f,0.00f,0.00f,2.00f,0.00f,0.00f,0.00f,0.00f,1.00f],Tags:["keys","{i+21}"]}}'

        current_z_white += 2  # 下一个白键z坐标增加2
    else:  # 黑键
        z = current_z_white - 0.5  # 黑键z坐标是下一个白键z坐标减0.5
        # 黑键指令模板
        cmd = f'execute at @e[type=minecraft:armor_stand,tag=piano] run summon block_display ~6 ~2 ~{z} {{block_state:{{Name:"minecraft:netherite_block"}},transformation:[10.00f,0.00f,0.00f,0.00f,0.00f,3.00f,0.00f,0.00f,0.00f,0.00f,1.00f,0.00f,0.00f,0.00f,0.00f,1.00f],Tags:["keys","{i+21}"]}}'


    instructions.append(cmd)

# 侧面琴板
instructions.append(
    f'execute at @e[type=minecraft:armor_stand,tag=piano] run summon block_display ~ ~3.5 ~-2 {{block_state:{{Name:"minecraft:black_terracotta"}},brightness:{{block:4,sky:8}},transformation:[16.9354f,-0.1744f,0.00f,0.00f,1.4824f,1.9924f,0.00f,-1.6f,0.00f,0.00f,2.00f,0.00f,0.00f,0.00f,0.00f,1.00f],Tags:["keys","upleftboard"]}}'
)
instructions.append(
    f'execute at @e[type=minecraft:armor_stand,tag=piano] run summon block_display ~-1 ~1.5 ~-2 {{block_state:{{Name:"minecraft:black_terracotta"}},brightness:{{block:4,sky:8}},transformation:[18.00f,0.00f,0.00f,0.00f,0.00f,2.50f,0.00f,0.00f,0.00f,0.00f,2.00f,0.00f,0.00f,0.00f,0.00f,1.00f],Tags:["keys","downleftboard"]}}'
)

instructions.append(
    f'execute at @e[type=minecraft:armor_stand,tag=piano] run summon block_display ~ ~3.5 ~104 {{block_state:{{Name:"minecraft:black_terracotta"}},brightness:{{block:4,sky:8}},transformation:[16.9354f,-0.1744f,0.00f,0.00f,1.4824f,1.9924f,0.00f,-1.6f,0.00f,0.00f,2.00f,0.00f,0.00f,0.00f,0.00f,1.00f],Tags:["keys","uprightboard"]}}'
)
instructions.append(
    f'execute at @e[type=minecraft:armor_stand,tag=piano] run summon block_display ~-1 ~1.5 ~104 {{block_state:{{Name:"minecraft:black_terracotta"}},brightness:{{block:4,sky:8}},transformation:[18.00f,0.00f,0.00f,0.00f,0.00f,2.50f,0.00f,0.00f,0.00f,0.00f,2.00f,0.00f,0.00f,0.00f,0.00f,1.00f],Tags:["keys","downrightboard"]}}'
)
# 底部琴板
for i in range(54):
    instructions.append(
        f'execute at @e[type=minecraft:armor_stand,tag=piano] run summon block_display ~-1 ~0.5 ~{-2+2*i} {{block_state:{{Name:"minecraft:black_terracotta"}},brightness:{{block:4,sky:8}},transformation:[21.00f,0.00f,0.00f,0.00f,0.00f,1.00f,0.00f,0.00f,0.00f,0.00f,2.00f,0.00f,0.00f,0.00f,0.00f,1.00f],Tags:["keys","downboard"]}}'
    )
# 后琴板
for i in range(54):
    instructions.append(
        f'execute at @e[type=minecraft:armor_stand,tag=piano] run summon block_display ~16 ~1.5 ~{-2+2*i} {{block_state:{{Name:"minecraft:black_terracotta"}},brightness:{{block:4,sky:8}},transformation:[4.00f,0.00f,0.00f,0.00f,0.00f,4.00f,0.00f,0.00f,0.00f,0.00f,2.00f,0.00f,0.00f,0.00f,0.00f,1.00f],Tags:["keys","backboard"]}}'
    )

# data
'''
instructions.append(
    f"execute as @e[tag=keys] run data modify entity @s start_interpolation set value 0"
)
instructions.append(
    f"execute as @e[tag=keys] run data modify entity @s teleport_duration set value 1"
)
instructions.append(
    f"execute as @e[tag=keys] run data modify entity @s interpolation_duration set value 1"
)
'''
instructions.append(
    f"execute as @e[tag=keys] run data merge entity @s {{start_interpolation:0,teleport_duration:1,interpolation_duration:1}}"
)


# 将指令保存到文件
with open("pianokeys.mcfunction", "w") as f:
    for cmd in instructions:
        f.write(cmd + "\n")

print(f"\n指令已保存到 pianokeys.mcfunction 文件")
