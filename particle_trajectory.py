import numpy as np
import math
import re
from scipy.spatial.transform import Rotation as R


def parse_coordinates(input_str):  # 处理输入坐标
    input_str = re.sub(r"[^\d.,\s-]", "", input_str)  # 清洗输入，删除无关字符
    numbers = re.findall(r"-?\d+\.?\d*", input_str)  # 提取有效数字
    if len(numbers) == 3:
        return np.array([float(num) for num in numbers])  # 转换为 np.array 并返回
    else:
        return "请输入恰好三个有效数字"


def normalize_vector(vec):  # 归一化处理
    norm = np.linalg.norm(vec)
    if norm == 0:
        raise ValueError("零向量不能归一化")
    return vec / norm


def rotate_point_scipy(point, axis, theta):  # 绕轴旋转 左手系
    # 创建一个旋转对象
    r = R.from_rotvec(axis * theta)  # 旋转向量 = 旋转轴 * 旋转角度

    # 使用旋转对象来旋转点
    rotated_point = r.apply(point)

    return rotated_point


def rotate_axis_scipy(point, tangent):  # 将参考系旋转至法向量方向
    # 原始y轴
    y_axis = np.array([0, 1, 0])  # 原始y轴

    theta = np.arctan2(tangent[2], tangent[0])
    rotated_point = rotate_point_scipy(point, y_axis, -theta)  # 绕y轴旋转
    # 新z轴
    new_z_axis = normalize_vector(rotate_point_scipy([0, 0, 1], y_axis, -theta))

    theta2 = np.arctan2(tangent[1], np.sqrt(np.square(tangent[0]) + np.square(tangent[2])))
    rotated_point = rotate_point_scipy(rotated_point, new_z_axis, theta2)  # 绕新z轴旋转

    return rotated_point


def trajectory_fluctuation_theta(rotation, total_particles): # 生成角度列表
    theta = []
    for i in range(total_particles):  # 角度列表
        theta.append(((rotation[1] * (i / (total_particles - 1))) / 180.0) * np.pi)
    if rotation[2] == "右手螺旋":  # 旋转方向
        theta = [-x + (rotation[0]/180.0) * np.pi for x in theta]
    else:
        theta = [x + (rotation[0]/180.0) * np.pi for x in theta]

    return theta


def calculate_linear_trajectory(delta, total_particles):  # 直线
    coordinates = [delta * (i / (total_particles - 1)) for i in range(total_particles)]
    tangent = [normalize_vector(delta)] * total_particles

    return coordinates, tangent


def calculate_quadratic_trajectory(delta, total_particles, a):  # 二次函数
    length = math.sqrt(np.square(delta[0]) + np.square(delta[2]))
    if a > 0:
        if a <= delta[1]:  # 保证参数是相对较高点的
            a += delta[1]
        alpha = (delta[1] - 2 * a - 2 * math.sqrt(a * (a - delta[1]))) / np.square(length)
        beta = (2 * a + 2 * math.sqrt(a * (a - delta[1]))) / length
    else:
        if a >= delta[1]:  # 保证参数是相对较低点的
            a += delta[1]
        alpha = (delta[1] - 2 * a + 2 * math.sqrt(a * (a - delta[1]))) / np.square(length)
        beta = (2 * a - 2 * math.sqrt(a * (a - delta[1]))) / length

    coordinates = []
    tangent = []
    for i in range(total_particles):
        t_factor = i / (total_particles - 1)
        coordinates.append(
            [
                delta[0] * t_factor,
                alpha * np.square((length * t_factor)) + beta * length * t_factor,
                delta[2] * t_factor,
            ]
        )
        tang_t = np.sqrt(np.square(coordinates[i][0]) + np.square(coordinates[i][2]))
        tangent.append(
            [
                coordinates[i][0] / tang_t,
                2 * alpha * tang_t + beta,
                coordinates[i][2] / tang_t,
            ]
        )

    return coordinates, tangent


def calculate_sin_trajectory(delta, total_particles, sin_fluctuation):
    return


def calculate_sin_fluctuation(tangent, total_particles, sin_fluctuation, fluctuation_rotation):  # 正弦波 波动
    # 生成正弦波
    length = 1
    lamda = length / sin_fluctuation[1]
    t = np.linspace(0, length, total_particles)
    x = np.zeros_like(t)
    y = sin_fluctuation[0] * np.sin(2 * np.pi * t / lamda)
    z = np.zeros_like(t)
    points = np.vstack((x, y, z)).T
    
    if fluctuation_rotation[3] != "否":  # 轨迹旋转，使用基础法向量
        theta = trajectory_fluctuation_theta(fluctuation_rotation, total_particles)
        for i in range(total_particles):
            points[i] = rotate_point_scipy(points[i], np.array([1,0,0]), theta[i])
    else:
        if fluctuation_rotation[0] != 0:
            for i in range(total_particles):
                points[i] = rotate_point_scipy(points[i], np.array([1,0,0]), (fluctuation_rotation[0]/180.0) * np.pi)

    rotated_points = []
    for i in range(total_particles):
        rotated_points.append(rotate_axis_scipy(points[i], tangent[i]))

    return rotated_points


def calculate_positions(inputs_dict):
    # 读取数据
    start = inputs_dict["start"]
    end = inputs_dict["end"]

    time = inputs_dict["time"]
    amount = inputs_dict["amount"]

    trajectory_type = inputs_dict["trajectory_type"]
    quadratic_h = inputs_dict["quadratic_h"]

    fluctuation_type = inputs_dict["fluctuation_type"]
    sin_fluctuation = inputs_dict["sin_fluctuation"]

    trajectory_rotation = inputs_dict["trajectory_rotation"]
    fluctuation_rotation = inputs_dict["fluctuation_rotation"]

    # 处理数据
    start_point = parse_coordinates(start)
    end_point = parse_coordinates(end)
    delta = end_point - start_point  # 相对位置
    total_particles = time * amount  # 总粒子数

    if trajectory_type == "直线":
        coordinates, tangent = calculate_linear_trajectory(delta, total_particles)
    elif trajectory_type == "二次函数线":
        coordinates, tangent = calculate_quadratic_trajectory(delta, total_particles, quadratic_h)
    else:
        raise ValueError("未知轨迹类型")

    coordinates_step0 = coordinates

    if fluctuation_type == "无":
        coordinates = coordinates
    elif fluctuation_type == "正弦波":
        coordinates_add = calculate_sin_fluctuation(tangent, total_particles, sin_fluctuation, fluctuation_rotation)
        for i in range(total_particles):
            coordinates[i] += coordinates_add[i]
    else:
        raise ValueError("未知轨迹类型")

    coordinates_step1 = coordinates

    tangent_base = normalize_vector(delta)  # 基础直线法向量
    
    if trajectory_rotation[3] != "否":  # 轨迹旋转，使用基础法向量
        theta = trajectory_fluctuation_theta(trajectory_rotation, total_particles)
        for i in range(total_particles):
            coordinates[i] = rotate_point_scipy(coordinates[i], tangent_base, theta[i])
    else:
        if trajectory_rotation[0] != 0:
            for i in range(total_particles):
                coordinates[i] = rotate_point_scipy(coordinates[i], tangent_base, (trajectory_rotation[0]/180.0) * np.pi)
            

    return coordinates
