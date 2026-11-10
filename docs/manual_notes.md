# Gemini 2 规格书阅读记录

来源：[Orbbec Gemini 2 系列产品规格书 V1.7，2024-03-16](./orbbec_gemini2_manual/Orbbec%20Gemini%202系列产品规格书%28对外版本%29V1.7%2820240316%29.pdf)。共 58 页；下表页码为印刷页码，PDF 阅读器页码需加 1。

该文件是产品规格书，并非 Python SDK 操作手册。已阅读全文并核对关键规格表；Python 安装和 API 由下方官方 SDK 资料补充。

## 与基础测试有关的要求

| 项目 | Gemini 2 要求或说明 | 印刷页码 |
| --- | --- | --- |
| 深度原理 | 主动双目结构光，设备端计算深度，应用直接获取深度帧 | 11–12 |
| 设备识别 | VID `0x2BC5`，PID `0x0670`；Gemini 2L 的 PID 为 `0x0673` | 23 |
| 连接与供电 | Type-C 同时传输数据和供电，支持 USB3/USB2；Gemini 2 建议 DC 5V、至少 1.5A，2L 至少 2A | 8、21、44 |
| 深度范围 | 标称 0.15–10m，理想范围 0.2–5m；最远距离受反射率和场景影响 | 7、9 |
| 深度模式 | Dense/Sparse/Obstacle Avoidance 建议 0.20–5m，Binned 建议 0.15–2.5m | 37 |
| USB3 深度流 | 1280×800 最高 30fps；640×400、320×200 的 60fps 需 Binned Sparse Default | 27 |
| USB2 深度流 | 1280×800 仅 5/10fps；640×400、320×200 最高 30fps；多流组合受带宽限制 | 27–28 |
| RGB | Gemini 2 最大 1920×1080、卷帘快门；2L 为 1280×800、全局快门，两者配置不能混用 | 7–8、20–21 |
| 深度格式 | 设备传输 Y14/RLE，SDK 输出 Y16；毫米值应使用 SDK 的 depth scale 换算 | 26 |
| 彩色格式 | MJPEG/YUYV，SDK 可提供 RGB888；显示前按实际格式解码 | 26 |
| 深度对齐 | D2C 后深度尺寸可能改变，应从实际帧读取宽高；基础预览不自动做对齐 | 32 |
| LDP | 1–400mm 单点接近测距，不代表整幅深度量程；0 表示 400mm 内无障碍物 | 29 |
| 系统支持 | 规格书列出 Windows/Android/Linux/macOS，Python 版本要求需查 SDK | 49 |

优先使用稳定供电的 USB3 端口及数据线，并以 SDK 实际报告的连接类型和可用 profiles 为准。不能因为设备支持 USB3 就假定当前连接是 USB3。先用低分辨率、低帧率验证 RGB 与深度同时取流，再提高配置。

测距验证应使用已知距离的平面目标。规格书精度指标有反射率、ROI 和距离等条件，不能当成所有场景的保证。深度值 0 应视为无效，不应显示为近距离物体。

## 操作注意与文档边界

- 工作温度 0–40℃，湿度 <95%RH、非凝结；IP5X 不代表防水（p8、47）。
- 不拆机、不触摸镜头、保持散热；即使为 Class1，也不建议长时间直视发射器（p50、53）。
- 固件更新需先停深度流并保持 USB 稳定；本次环境搭建没有升级固件（p48）。
- p6 的内存简表与 p23 的详细推荐不一致，Windows 宜参考后者的至少 8GB。
- p57 的线材泛化描述不取代 p27–28 的 USB2/USB3 流规格。
- 文档不含 Python 安装命令、当前 wheel 兼容表或 Python API 示例。

## Python SDK 选择

本项目固定 CPython 3.11 / Windows x64、`pyorbbecsdk==2.0.15`、`numpy==1.26.4`、`opencv-python==4.11.0.86`。

- [官方 v2.0.15 发布说明](https://github.com/orbbec/pyorbbecsdk/releases/tag/v2.0.15)：底层为 Orbbec SDK 2.5.5。
- [该版本支持与固件表](https://github.com/orbbec/pyorbbecsdk/blob/v2.0.15/README.md)：支持 Gemini 2，最低固件 1.4.92，推荐 1.4.98。
- [官方深度示例](https://github.com/orbbec/pyorbbecsdk/blob/v2.0.15/examples/depth.py)与 [API 声明](https://github.com/orbbec/pyorbbecsdk/blob/v2.0.15/stubs/pyorbbecsdk.pyi)：使用 `get_depth_scale()` 将原始深度换算为毫米。

这不是最新 SDK。调研时最新版 `pyorbbecsdk2==2.1.3` 的依赖包含 Open3D、PyAV、pygame 等；本次基础预览使用官方 v2.0.15 wheel，正常安装且不跳过依赖检查。不要同时安装 `pyorbbecsdk` 和 `pyorbbecsdk2`，它们提供同名 Python 导入模块。

本机初次枚举：一台 Gemini 2，固件 1.4.92，连接 USB2.0。此信息是本次现场状态，后续以实际枚举结果为准。
