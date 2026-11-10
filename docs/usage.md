# 运行说明

先按根目录 README 完成可编辑安装。以下命令在项目根目录运行，也可以使用 `.venv/Scripts/` 下安装的 `gemini-*` 命令。

## 设备预览

```powershell
.\.venv\Scripts\python.exe demos\camera.py --list-devices
.\.venv\Scripts\python.exe demos\camera.py --frames 30
.\.venv\Scripts\python.exe demos\camera.py
```

基础预览按连接类型选择实际支持的 RGB／深度 profile。深度值使用 SDK 的比例因子转成 mm；颜色显示范围是 0.2–5 m，无效深度显示黑色。此演示不做 D2C，也不验证测距精度。

## 实时蓝色导管

```powershell
.\.venv\Scripts\python.exe demos\live.py --hz 1
.\.venv\Scripts\python.exe demos\live.py --hz 1 --duration 25 --output outputs\captures\trial
```

RGB 1920×1080 MJPG、IR 1280×800 Y8、深度 1280×800 Y16，各 5 fps。`--duration 0` 表示一直运行；Q / Esc 或关闭窗口停止，S 保存当前图像与结果。

`--ir-exposure` 默认 300，单位沿用 SDK；运行时暂时关闭自动曝光，退出后恢复启动时的曝光和自动曝光状态并核验。SDK 曾将旧值 3000 回写为 2500，断连时也无法保证恢复；非零退出码及 `session_summary.json` 会保留原因。不要在相机被其他软件占用时并行启动采集。

绿色表示中心线，红色表示通过匹配的点，橙色表示未匹配位置。右侧显示 IR 坐标系三维点及正视图。时间差、实际更新率与接收后的图像年龄位于顶部；1 Hz 更新率不等同于小于 1 秒的端到端延迟。

输出目录包含 `metadata.json`、`updates.jsonl`、`latest_result.json`、`latest_preview.jpg`、`first_result/`、`first_valid/`、按 S 生成的 `snapshot_*/` 和结束后的 `session_summary.json`。不默认录制全部原始帧。过曝、旧图像、无可靠匹配时拒绝或清空三维结果。

## 离线重建与人工对照

```powershell
.\.venv\Scripts\python.exe demos\offline.py data\fixtures\catheter_static --frames 50 10 80 140 20 100 120
.\.venv\Scripts\python.exe demos\evaluate.py data\fixtures\catheter_static outputs\offline\catheter_static
```

默认输出到 `outputs/offline/<输入目录名>/`，可用 `--output` 指定其他输出目录。图像使用 `NNNN_rgb.jpg` 与 `NNNN_ir.png`，时间戳由 `metadata.json` 读取，自动选择最近的 IR 帧。

每对图像输出中心线、掩膜、匹配与拒绝原因、三维 CSV 和图表。人工对照单独运行，只在评估阶段读取 `triangulation/result.json`；评估目前针对保留的第 50 帧人工参考，不能将它当成通用标注集评估器。人工估计也不是精度真值。

## 黑色导丝候选诊断

```powershell
.\.venv\Scripts\python.exe demos\black_wire.py data\fixtures\black_wire_horizontal
```

默认从输入目录的 `first_result/rgb.jpg` 和 `first_result/ir.png` 读取，可用 `--pair` 指定其他子目录。默认输出 `outputs/black_wire/<输入目录名>/`。

诊断会保留 IR 的多个暗线候选，包括可能的阴影。`hypothesis_*.png` 是尚未认证的三维假设，不能自动选择看起来最平滑的一条作为真实导丝。该入口没有接入实时导管模式。
