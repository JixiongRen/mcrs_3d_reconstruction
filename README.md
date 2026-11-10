# mcrs_3d_reconstruction

磁控导丝／导管三维重建原型。

使用 Orbbec Gemini 2 的 RGB 与 IR 图像提取中心线、进行极线匹配和三角测量。原生深度只用于基础设备演示，不参与导管三维重建。

目前**蓝色导管支持约 1 Hz 的实时局部重建**；**黑色导丝仍是离线候选诊断**，不能视为稳定全长重建。人工对照不是真值，重投影误差不代表测量精度。

## 工程结构

```text
src/guidewire/       核心算法、相机适配、数据配对、结果存储和显示
  workflows/        相机预览、离线重建、实时运行、人工对照、黑色导丝诊断
demos/             五个可直接运行的薄入口
tests/             单元测试和真实样本回归测试
data/fixtures/     精简、固定的测试图像、标定与参考结果
docs/              架构、运行方法、实验记录与设备规格书
third_party/       原厂 C/C++ 示例及其运行文件
outputs/           新采集、图表、重建结果、运行日志（不提交）
pyproject.toml     包定义、依赖版本、命令行入口
```

核心算法与界面／相机解耦，演示脚本不再互相导入。目录职责见 [架构说明](docs/architecture.md)。

## 安装

当前验证环境：**Windows x64 / CPython 3.11**。已有 `.venv` 可继续使用。首次安装从项目根目录执行：

```powershell
uv venv --python 3.11 .venv
uv pip install --python .venv\Scripts\python.exe -e ".[camera]"
```

只运行离线分析时可以安装 `-e .`，无需相机 SDK。`requirements.txt` 是完整环境的兼容安装入口，依赖版本统一定义于 `pyproject.toml`。

## 常用命令

以下命令均在项目根目录运行：

```powershell
# 查看设备；不会启动图像流
.\.venv\Scripts\python.exe demos\camera.py --list-devices

# 实时蓝色导管重建，Q / Esc 退出，S 保存当前结果
.\.venv\Scripts\python.exe demos\live.py --hz 1

# 使用固定测试样本，无需相机
.\.venv\Scripts\python.exe demos\offline.py data\fixtures\catheter_static --frames 50 10 80 140 20 100 120

# 黑色导丝：输出多个待核验候选，不自动认定阴影与导丝
.\.venv\Scripts\python.exe demos\black_wire.py data\fixtures\black_wire_horizontal

# 单元测试和样本回归，无需相机
.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
```

新输出默认写入 `outputs/`，不会覆盖 `data/fixtures/`。参数、人工对照、有限时间采集与输出格式见 [运行说明](docs/usage.md)。

## 开发与实验

- [架构与模块职责](docs/architecture.md)
- [测试样本说明与新增规则](data/README.md)
- [实验结论与已知限制](docs/experiments.md)
- [本次迁移、清理和备份](docs/cleanup.md)
- [设备规格书阅读记录](docs/manual_notes.md)
- [测试说明](tests/README.md)

实时程序会临时调整 IR 曝光，退出时尝试恢复并回读核验。设备断连或 SDK 限幅可能导致恢复失败，程序会明确记录并返回非零退出码。保持 LDP 保护、激光投射器与增益设置不变。RGB/IR 时间配对仍不等同于曝光同步。
