import gradio as gr
import plotly.graph_objects as go
from particle_trajectory import calculate_positions

# 全局变量，用于存储缓存的参数组
cached_parameters = []


# 创建 Gradio 界面
def create_gradio_interface():
    with gr.Blocks(fill_width=True) as demo:
        with gr.Row():
            with gr.Column(scale=4):
                with gr.Row():
                    # 起点终点坐标输入
                    start_input = gr.Textbox(label="起点坐标", value="0 0 0")
                    end_input = gr.Textbox(label="终点坐标", value="10 10 10")

                    # 时间密度输入
                    time_input = gr.Number(label="时间(Tick)", value=20, minimum=1, step=1)
                    amount_input = gr.Number(label="密度(每tick坐标数)", value=5, minimum=1, step=1)

                # 特效类型选择
                with gr.Group():
                    with gr.Row():
                        trajectory_type_input = gr.Dropdown(
                            label="轨迹类型",
                            choices=["直线", "二次函数线", "正弦波"],
                            value="直线",
                        )

                    # 二次函数形状控制参数 a 输入框（初始隐藏）
                    with gr.Row():
                        quadratic_h_input = gr.Number(
                            label="二次函数参数 控制函数顶点与端点的高度差,正值与较高端点比较,负值与较低端点比较",
                            value=5.0,
                            step=0.001,
                            visible=False,
                        )

                # 波动类型选择
                with gr.Group():
                    with gr.Row():
                        fluctuation_type_input = gr.Dropdown(
                            label="波动类型",
                            choices=["无", "正弦波"],
                            value="无",
                        )

                    # 正弦波控制参数 Amplitude、Frequency 输入框（初始隐藏）
                    with gr.Row():
                        sin_amplitude_input = gr.Number(
                            label="正弦波振幅 控制波峰与轨迹距离",
                            value=1.0,
                            step=0.001,
                            visible=False,
                        )
                        sin_frequency_input = gr.Slider(
                            label="正弦波频率 控制全程有几个周期",
                            value=5.0,
                            minimum=0.5,
                            maximum=20,
                            step=0.5,
                            visible=False,
                        )

                # 轨迹旋转
                with gr.Group():
                    with gr.Row():
                        trajectory_rotation_start_input = gr.Slider(
                            label="轨迹初始相位",
                            value=0,
                            minimum=0,
                            maximum=360,
                            step=15,
                        )
                        trajectory_rotation_end_input = gr.Slider(
                            label="旋转角度",
                            value=180,
                            step=15,
                            minimum=0,
                            maximum=7200,
                            visible=False,
                        )
                        trajectory_rotation_input = gr.Radio(
                            label="是否旋转",
                            choices=["是", "否"],
                            value="否",
                            scale=0,
                        )
                    with gr.Row():
                        trajectory_rotation_direction_input = gr.Radio(
                            label="旋转方向 大拇指指向旋转轴正方向,四指指向旋转方向",
                            choices=["右手螺旋", "左手螺旋"],
                            value="右手螺旋",
                        )
                        trajectory_rotation_influence_input = gr.Radio(
                            label="是否影响波动法平面",
                            choices=["是", "否"],
                            value="是",
                            scale=0,
                            visible=False,
                        )

                # 波动旋转
                with gr.Group():
                    with gr.Row():
                        fluctuation_rotation_start_input = gr.Slider(
                            label="波动初始相位",
                            value=0,
                            minimum=0,
                            maximum=360,
                            step=15,
                        )
                        fluctuation_rotation_end_input = gr.Slider(
                            label="旋转角度",
                            value=1800,
                            step=15,
                            minimum=0,
                            maximum=7200,
                            visible=False,
                        )
                        fluctuation_rotation_input = gr.Radio(
                            label="是否旋转",
                            choices=["是", "否"],
                            value="否",
                            scale=0,
                        )
                    with gr.Row():
                        fluctuation_rotation_direction_input = gr.Radio(
                            label="旋转方向 大拇指指向旋转轴正方向,四指指向旋转方向",
                            choices=["右手螺旋", "左手螺旋"],
                            value="右手螺旋",
                        )

            with gr.Column(scale=5):
                with gr.Row():
                    calculate_button = gr.Button("预览")
                    calculate_all_button = gr.Button("全部预览")

                output = gr.Plot(label="三维轨迹展示")

            with gr.Column(scale=0):
                cache_button = gr.Button("缓存当前")
                clear_cache_button = gr.Button("清空缓存")
                delete_cache_button = gr.Button("删除选中的参数")
                delete_cache_input = gr.Number(label="待删除ID", value=-1, step=1)

                cached_params_display = gr.Dataframe(
                    headers=["ID", "参数"],
                    value=[],
                    label="已缓存的参数",
                )

        # 轨迹类型输入框 显示与隐藏
        def show_hide_quadratic_h_input(current_type):
            return gr.update(visible=current_type == "二次函数线")

        trajectory_type_input.change(
            show_hide_quadratic_h_input,
            inputs=trajectory_type_input,
            outputs=quadratic_h_input,
        )

        # 波动类型输入框 显示与隐藏
        def show_hide_sin_input(current_type):
            return [
                gr.update(visible=current_type == "正弦波"),
                gr.update(visible=current_type == "正弦波"),
            ]

        fluctuation_type_input.change(
            show_hide_sin_input,
            inputs=fluctuation_type_input,
            outputs=[sin_amplitude_input, sin_frequency_input],
        )

        # 轨迹旋转 显示与隐藏
        def show_hide_trajectory_rotation_input(current_type):
            return [
                gr.update(visible=current_type == "是"),
                gr.update(visible=current_type == "是"),
            ]

        trajectory_rotation_input.change(
            show_hide_trajectory_rotation_input,
            inputs=trajectory_rotation_input,
            outputs=[trajectory_rotation_end_input, trajectory_rotation_influence_input],
        )

        # 波动旋转 显示与隐藏
        def show_hide_fluctuation_rotation_input(current_type):
            return gr.update(visible=current_type == "是")

        fluctuation_rotation_input.change(
            show_hide_fluctuation_rotation_input,
            inputs=fluctuation_rotation_input,
            outputs=fluctuation_rotation_end_input,
        )

        # 缓存当前参数
        def cache_parameters(
            start,
            end,
            time,
            amount,
            trajectory_type,
            quadratic_h,
            trajectory_rotation_start,
            trajectory_rotation_end,
            trajectory_rotation_direction,
            trajectory_rotation,
            trajectory_rotation_influence,
            fluctuation_type,
            sin_amplitude,
            sin_frequency,
            fluctuation_rotation_start,
            fluctuation_rotation_end,
            fluctuation_rotation_direction,
            fluctuation_rotation,
        ):
            inputs_dict = {
                "start": start,
                "end": end,
                "time": time,
                "amount": amount,
                "trajectory_type": trajectory_type,
                "quadratic_h": quadratic_h,
                "fluctuation_type": fluctuation_type,
                "sin_fluctuation": (sin_amplitude, sin_frequency),
                "trajectory_rotation": (
                    trajectory_rotation_start,
                    trajectory_rotation_end,
                    trajectory_rotation_direction,
                    trajectory_rotation,
                    trajectory_rotation_influence,
                ),
                "fluctuation_rotation": (
                    fluctuation_rotation_start,
                    fluctuation_rotation_end,
                    fluctuation_rotation_direction,
                    fluctuation_rotation,
                ),
            }
            global cached_parameters
            cached_parameters.append(inputs_dict)
            return update_cached_params_display()

        # 清空缓存
        def clear_cache():
            global cached_parameters
            cached_parameters = []
            return update_cached_params_display()

        # 更新缓存的参数显示
        def update_cached_params_display():
            global cached_parameters
            data = []
            for idx, params in enumerate(cached_parameters):
                data.append(
                    [
                        idx,
                        params["trajectory_type"]
                        + " "
                        + params["fluctuation_type"]
                        + " "
                        + str(params["trajectory_rotation"][0]),
                    ]
                )
            return data

        # 删除选中的缓存参数
        def delete_selected_cache(ID):
            global cached_parameters
            if ID != -1:
                # 删除选中的参数
                cached_parameters = [params for idx, params in enumerate(cached_parameters) if idx != ID]
            return update_cached_params_display()

        # 创建 3D 图形
        def create_3d_plot(positions_list):
            fig = go.Figure()

            # 突出显示原点 (0, 0, 0)
            origin_marker = go.Scatter3d(
                x=[0],
                y=[0],
                z=[0],
                mode="markers",
                marker=dict(size=7, color="red", symbol="square"),
                name="原点",
            )
            fig.add_trace(origin_marker)

            # 遍历所有轨迹，绘制到同一个图形中
            for i, positions in enumerate(positions_list):
                x_vals, y_vals, z_vals = zip(*positions)
                color_vals = list(range(len(positions)))

                # 绘制轨迹
                trace = go.Scatter3d(
                    x=x_vals,
                    y=y_vals,
                    z=z_vals,
                    mode="lines+markers",
                    marker=dict(
                        size=5,
                        color=color_vals,
                        colorscale="Viridis",
                    ),
                    name=f"轨迹 {i + 1}",
                )
                fig.add_trace(trace)

            # 设置布局
            fig.update_layout(
                title="粒子轨迹",
                scene=dict(
                    xaxis_title="X",
                    yaxis_title="Y",
                    zaxis_title="Z",
                    camera=dict(eye=dict(x=1, y=1, z=3), up=dict(x=0, y=1, z=0)),
                ),
                margin=dict(l=0, r=0, b=0, t=0),
                height=800,
            )

            return fig

        # 计算函数
        def on_calculate_button_click(
            start,
            end,
            time,
            amount,
            trajectory_type,
            quadratic_h,
            trajectory_rotation_start,
            trajectory_rotation_end,
            trajectory_rotation_direction,
            trajectory_rotation,
            trajectory_rotation_influence,
            fluctuation_type,
            sin_amplitude,
            sin_frequency,
            fluctuation_rotation_start,
            fluctuation_rotation_end,
            fluctuation_rotation_direction,
            fluctuation_rotation,
        ):
            inputs_dict = {
                "start": start,
                "end": end,
                "time": time,
                "amount": amount,
                "trajectory_type": trajectory_type,
                "quadratic_h": quadratic_h,
                "fluctuation_type": fluctuation_type,
                "sin_fluctuation": (sin_amplitude, sin_frequency),
                "trajectory_rotation": (
                    trajectory_rotation_start,
                    trajectory_rotation_end,
                    trajectory_rotation_direction,
                    trajectory_rotation,
                    trajectory_rotation_influence,
                ),
                "fluctuation_rotation": (
                    fluctuation_rotation_start,
                    fluctuation_rotation_end,
                    fluctuation_rotation_direction,
                    fluctuation_rotation,
                ),
            }
            # 调用计算函数获取三维坐标
            positions = calculate_positions(inputs_dict)
            # 创建 3D 图形并返回
            return create_3d_plot([positions])

        # 全部预览函数
        def on_calculate_all_button_click():
            global cached_parameters
            positions_list = []
            for params in cached_parameters:
                positions = calculate_positions(params)
                positions_list.append(positions)
            # 创建 3D 图形并返回
            return create_3d_plot(positions_list)

        # 预览按钮触发器
        calculate_button.click(
            fn=on_calculate_button_click,
            inputs=[
                start_input,
                end_input,
                time_input,
                amount_input,
                trajectory_type_input,
                quadratic_h_input,
                trajectory_rotation_start_input,
                trajectory_rotation_end_input,
                trajectory_rotation_direction_input,
                trajectory_rotation_input,
                trajectory_rotation_influence_input,
                fluctuation_type_input,
                sin_amplitude_input,
                sin_frequency_input,
                fluctuation_rotation_start_input,
                fluctuation_rotation_end_input,
                fluctuation_rotation_direction_input,
                fluctuation_rotation_input,
            ],
            outputs=output,
        )

        # 缓存按钮触发器
        cache_button.click(
            fn=cache_parameters,
            inputs=[
                start_input,
                end_input,
                time_input,
                amount_input,
                trajectory_type_input,
                quadratic_h_input,
                trajectory_rotation_start_input,
                trajectory_rotation_end_input,
                trajectory_rotation_direction_input,
                trajectory_rotation_input,
                trajectory_rotation_influence_input,
                fluctuation_type_input,
                sin_amplitude_input,
                sin_frequency_input,
                fluctuation_rotation_start_input,
                fluctuation_rotation_end_input,
                fluctuation_rotation_direction_input,
                fluctuation_rotation_input,
            ],
            outputs=cached_params_display,
        )

        # 清空缓存按钮触发器
        clear_cache_button.click(
            fn=clear_cache,
            outputs=cached_params_display,
        )

        # 删除缓存按钮触发器
        delete_cache_button.click(
            fn=delete_selected_cache,
            inputs=delete_cache_input,
            outputs=cached_params_display,
        )

        # 全部预览按钮触发器
        calculate_all_button.click(
            fn=on_calculate_all_button_click,
            outputs=output,
        )

    return demo


# 启动 Gradio 界面并自动唤起浏览器
demo = create_gradio_interface()
demo.launch(inbrowser=True)  # 自动唤起浏览器并显示界面
