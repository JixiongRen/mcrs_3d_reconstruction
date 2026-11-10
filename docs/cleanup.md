# 2026-11-10 工作区整理

## 已完成

- 核心代码从根目录演示脚本拆入 `src/guidewire/`，几何、分割、中心线、配对、硬件、存储和显示各自有明确职责。
- 五个演示入口放到 `demos/`；单元测试和真实样本回归放到 `tests/`。
- 依赖版本集中在 `pyproject.toml`，采用可编辑安装。`requirements.txt` 仅作兼容入口，旧 `requirements-offline.txt` 已归档。
- 原厂示例完整迁到 `third_party/orbbec_examples/`；保留原代码和二进制，运行日志单独归档。
- 采集数据原约 **864.1 MiB**，工作区只保留 **14.59 MiB** 固定测试样本。全部新输出写入 `outputs/`。
- 旧 Python 脚本、重复采集、旧输出、根目录缓存和 SDK 日志均移出工作区。保留现有 `.venv`，避免破坏可用环境。

## 备份与归档

整理前完整快照（不含 `.venv` 和 Python 缓存）：

`C:/Data/orbbec_gemini2_demo-backup-20261110_101758.zip`

共 4259 个文件，ZIP 内部 CRC 检查通过；SHA-256 保存在 `cleanup_manifest.json` 中。此备份包含原代码、文档、原始采集及厂商示例。

被移出的旧文件在可直接查看的归档目录：

`C:/Data/orbbec_gemini2_demo-retired-20261110/`

批量永久删除被自动审批检查拒绝，仅返回 `blocked by policy`，没有更具体原因。因此采用可恢复的工作区外归档，**没有永久删除原始采集，也没有宣称释放对应磁盘空间**。ZIP 是完整整理前快照，归档目录是本次退出活动工程的旧内容。

`Example/bin/Log/OrbbecSDK.log.txt` 最初被旧 HelloOrbbec 进程占用，用户关闭进程后已归档到 `remaining_sdk_log/`，工作区中不再保留 `Example/`。

## 迁移对应

| 旧入口 | 新入口 |
| --- | --- |
| `gemini2_demo.py` | `demos/camera.py` |
| `offline_reconstruct.py` | `demos/offline.py` |
| `live_reconstruct.py` | `demos/live.py` |
| `evaluate_offline_reconstruction.py` | `demos/evaluate.py` |
| `probe_black_wire.py` | `demos/black_wire.py` |
| 根目录 `test_*.py` | `tests/unit/` 与 `tests/integration/` |
| `captures/` | 精选输入在 `data/fixtures/`，新运行输出在 `outputs/` |
| `Example/` | `third_party/orbbec_examples/` |

本轮不改变算法阈值、三角测量约定或匹配拒绝规则。旧临时采集脚本、人工标点绘图脚本及重复诊断版本不进入核心包；需要复查时可从完整 ZIP 或归档目录取得。人工点与数值参考保留在测试数据中，继续支持事后评估。

## 验证

- 15 项测试通过，保留输入的 SHA-256 检查通过。
- 七组导管匹配点数及 XYZ 与重构前一致。
- 黑色导丝候选保留为 16 点和 22 点两组假设，未把错误阴影匹配包装为成功结果。
- 五个演示帮助入口、三条离线工作流、设备枚举和依赖一致性检查通过。
- 所有保留文件的来源、目的路径与哈希见 `cleanup_manifest.json`。

## 项目更名

2026-11-10 项目及本地仓库迁移到 `C:/Data/mcrs_3d_reconstruction/`，Python 项目名称同步为 `mcrs_3d_reconstruction`。新目录重建了 `.venv` 和可编辑安装，避免旧绝对路径残留。内部 `guidewire` 模块名和 `gemini-*` 相机演示命令保持原有接口。

此前备份、归档路径与样本来源记录保留原名，指向真实存在的历史文件，并不是需要改写的新运行路径。

旧虚拟环境已移到外部归档目录的 `environment_before_rename/`。旧工作区目录因当前会话占用保留空壳（含空 `.git` 目录），实际 Git 元数据、源码、数据和运行环境均位于新目录。新旧环境共有依赖版本一致，15 项测试与五个演示帮助入口均通过。请在 Codex／编辑器中重新打开新目录。
