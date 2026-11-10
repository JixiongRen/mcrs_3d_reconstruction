# 演示入口

先从项目根目录执行 `uv pip install --python .venv/Scripts/python.exe -e ".[camera]"`。演示入口只解析并调用应用流程，不放算法副本。

| 入口 | 功能 | 需要相机 |
| --- | --- | --- |
| `camera.py` | 枚举、RGB/深度预览、有限帧连通性检查 | 是 |
| `live.py` | 约 1 Hz 蓝色导管实时局部重建 | 是 |
| `offline.py` | 保存图像的中心线与三角测量 | 否 |
| `evaluate.py` | 保留样本与人工估计的事后对照 | 否 |
| `black_wire.py` | 黑色导丝暗线候选诊断 | 否 |

完整命令见 `docs/usage.md`，各入口支持 `--help`。
