
# NS-P6 N-B 准备与执行说明

本批使用原名视图，正式计划包含 120 次新 fit：四个任务的 5/10 折分别运行 S3×G3R、S4g×G3R、S4m×G3R、S4-noG×G0（layers=0）。N-A 的 240 份正式结果只读引用，不重新训练。

## 当前授权边界

PROMPTS.md §5.9 要求先准备和封存，停下等用户授权，再执行。准备阶段不生成授权为 true 的记录，不启动训练或 GPU 评估。需要阅读最终 NS_P6_REPORT.md 和 batch_NB_v1/verification.json；未通过时不得执行下一步。

S4m 只替换 CTX 为 ctx_masked，CODE 保留原名、STATIC 不变。S4-noG 删除 HGT 消息传递，但 CTX/STATIC 仍含 DFG 分析信息，不能称完全不使用依赖信息。

## 环境和命令

在 WSL 项目目录中使用原 mando 环境：

```bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
CUDA_VISIBLE_DEVICES='' python -B -m scripts.node_sem.p6_prepare verify --out scripts/node_sem/artifacts/batch_NB_v1
```

准备入口使用排他目录。已有 batch_NB_v1 时不要重跑 prepare 或覆盖目录。完整准备命令记录在 NS_P6_REPORT.md。

将来获得独立 N-B 授权后，先记录新电源检查及 execution_decisions.json，再由下列入口生成执行修订/授权并串行调度。当前不能直接执行：

```bash
python -B -m scripts.node_sem.batch_nb_controller seal --root scripts/node_sem/artifacts/batch_NB_v1
python -B -m scripts.node_sem.batch_nb_controller run --root scripts/node_sem/artifacts/batch_NB_v1
python -B -m scripts.node_sem.batch_nb_controller verify --root scripts/node_sem/artifacts/batch_NB_v1
```

调度适配直接复用 N-A 的 construct、run_core、收据核验和外部中断判定；原 N-A 源码与产物不变。每项独立进程、共享 GPU 锁；优先重入节点40项。没有明确同意外部中断重跑的授权时，不自动重跑。OOM、数值、输入及 checkpoint 错误均停止。

本轮只完成准备门槛。N-B 训练后的专用汇总、门控与注意力诊断仍需在执行阶段接入并单独绑定；控制器到120个收据齐备时只标记 complete_training_pending_NB_report，不冒称报告完成。全部比较只作描述，不进行 Holm/显著性选型，不推进 NS-P7。

## 归档与运行位置

PT/NPZ、特征和初值保存在 WSL；Git 保存代码、计划、摘要及可审查记录。下载的预训练资产保持原样，本阶段无需再编码或下载。

用户已说明最终实验会在显存充足的服务器开展。当前RTX3050 4GiB只是本机开发限制；本批与N-A绑定同一设备、PyTorch/CUDA和TF32设置。服务器另建批次，不混合、择优或用服务器单个结果替换本机困难折。服务器尚未实测。
