# 测试数据

`fixtures/` 是固定回归样本，不是运行输出目录。全部来自本机 Gemini 2 实际采集；无独立三维真值。精简时保留了原始图像分辨率、标定、时间戳和必要实验结果，图像没有重采样或重新压缩。

| 样本 | 用途 | 原始采集 |
| --- | --- | --- |
| `catheter_static` | 七组离线 RGB/IR 数值回归与人工对照 | `20261109_200401_retry` |
| `catheter_live` | 实时预处理和匹配成功场景 | `live_validation_20261109_final` |
| `catheter_tip_loop` | 小骨架环造成端点丢失的回归场景 | `live_validation_20261109_endpoints` |
| `ir_overexposed` | IR 饱和时必须拒绝重建 | `live_validation_20261109_replug` |
| `black_wire_horizontal` | 黑色导丝、阴影和近水平退化的诊断场景 | `wire_test_20261110_baseline` |

`catheter_static` 保留 RGB 索引 50、10、80、140、20、100、120 及各自最近 IR 的 51、11、81、141、21、101、121，共 14 个采集时刻的 RGB/IR/原生深度/D2C 图像。`metadata.json` 的帧表已裁剪为这 14 个时刻，内外参保持原样；`fixture_subset` 明确标注裁剪信息。深度图仅保留作原生深度失败现象的证据，不进入重建算法。

其他样本各保留一对 RGB/IR 与源结果、标定和有限运行日志。`first_result/result.json` 是历史采集时的结果，可能来自当时尚未修复的版本，特别是端点小环样本；不能把它直接当成今天算法的预期输出。

`expected.json` 和 `catheter_static/expected_xyz.npz` 是本次模块化前用当前算法计算的数值基准，只用于检测重构改变了输出，并非精度标准。保留文件来源与 SHA-256 在 `docs/cleanup_manifest.json` 中。

新采集先写入 `outputs/captures/`；选入固定测试集时说明它覆盖哪类成功／失败场景、记录相机设置并添加有意义的检查，避免整段视频直接堆入测试目录。
