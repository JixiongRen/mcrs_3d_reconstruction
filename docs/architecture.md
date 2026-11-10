# 架构说明

## 依赖与职责

```text
演示入口 demos/ 或安装后的命令
                 ↓
           workflows/ 调度
          ↙       ↓       ↘
     camera    processing   visualization / results
       ↓          ↓
    pairing   segmentation → centerline → matching → stereo
```

核心算法接收 NumPy 数组、标定参数与像素曲线，不打开相机、不写文件、不创建窗口。`camera.py` 仅在需要硬件时加载 `pyorbbecsdk`；离线测试无需安装或连接相机。

| 模块 | 职责 |
| --- | --- |
| `camera.py` | Gemini 2 取流、帧解码、profile 选择、标定读取、曝光恢复核验 |
| `pairing.py` | 有界 RGB/IR 缓冲、设备时间戳近邻配对、旧帧拒绝 |
| `segmentation.py` | 蓝色导管分割、IR 亮线响应、黑色导丝暗线候选 |
| `centerline.py` | 骨架图、小环处理、短枝清理、端点路径和弧长采样 |
| `stereo.py` | 内外参核对、去畸变、三角测量、回投 |
| `matching.py` | 极线交点、沿曲线顺序、交叉角度、歧义与短片段拒绝 |
| `processing.py` | 并行提取一对图像的中心线并匹配，返回结果字典 |
| `results.py` | 可序列化结果及原图／中心线快照 |
| `visualization.py` | 离线图表和实时 RGB/IR/三维画面渲染 |
| `workflows/` | 五个应用流程的参数解析和调度；黑色导丝流程保留诊断图表 |

## 数据约定

- RGB 输入是原始分辨率的 **BGR uint8**，IR 是单通道 **uint8**；不使用缩放预览图求几何。
- 二维坐标顺序为 `(u, v)`，曲线形状为 `(N, 2)`；弧长单位为像素。
- 三维坐标为 IR 相机系 `(X, Y, Z)`，X 向右、Y 向下、Z 向前，单位 mm。
- RGB 畸变保留完整八参数模型；目前仅接受已核对的零畸变 IR profile。
- `metadata.json` 保留 `calibration`；实时样本另带 `checked_profile`，离线序列的校验数据位于 `triangulation/profile_calibration_check.json`。
- `partial_reconstruction` 仅表示部分点通过当前匹配规则，不能等同于精度合格。

## 实时调度

相机三路以 5 fps 采集。采集线程只解码并写入有界缓冲；工作线程约每秒取最新可配对图像，在两个线程上提取 RGB/IR；主线程负责窗口。处理来不及时不排队积压历史帧。

配对等待 RGB 时间戳两侧的 IR，选择较近帧；最大时间差 120 ms，拒绝接收后超过 1.5 秒的旧输入。画面超过 3 秒未更新时清空三维显示。深度像素不参与三角测量。

## 修改规则

1. 分割／骨架修改先跑单元测试，再跑保存样本回归。
2. 改变参数或行为时明确更新实验记录；不要为使测试通过而无说明地重写数值基准。
3. 新采集写入 `outputs/captures/`。只有有测试目的的少量原始样本进入 `data/fixtures/`，同时保存标定、来源和必要时间戳。
4. 修改厂商代码前先确认确有必要；项目 Python 流程不依赖 `third_party/` 中的二进制文件。
