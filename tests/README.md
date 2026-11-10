# 测试

从项目根目录运行：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
```

- `unit/`：合成几何、近水平退化、亮线与暗影区分、小骨架环、空目标、过曝拒绝、时间戳配对与旧帧拒绝。
- `integration/`：真实固定样本，检查保留文件校验和、七组导管的点数及逐点 XYZ、黑色导丝多个候选、实时预处理，以及计算模块不加载相机 SDK／绘图。
- `helpers.py`：共享合成双目标定。

这些测试不打开相机，不证明测量准确度。需要显式启动 `demos/camera.py` 或 `demos/live.py` 做硬件验证。新增算法行为时应同时更新实验说明，避免静默改写基准来掩盖回归。
