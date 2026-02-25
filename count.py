import os

def count_lines_in_mcfunction_files(folder='.'):
    total_lines = 0
    # 遍历当前文件夹中的所有文件
    for filename in os.listdir(folder):
        if filename.endswith('.mcfunction'):
            filepath = os.path.join(folder, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    # 统计文件行数
                    lines = f.readlines()
                    total_lines += len(lines)
            except Exception as e:
                print(f"读取文件 {filename} 时出错: {e}")
    return total_lines

if __name__ == '__main__':
    total = count_lines_in_mcfunction_files()
    print(f"当前文件夹内所有 .mcfunction 文件的总行数为: {total}")