# EP7 执行说明

当前状态：实现与 CPU 验收完成，GPU/正式训练尚未授权。详细结果见 [EP7_REPORT.md](EP7_REPORT.md)。已有输出目录禁止覆盖；以下已完成命令仅作复现记录，不能直接对同目录重复运行。

## 环境

在 WSL Ubuntu-22.04 工作树中执行：

```bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
```

本机为 RTX 3050 4 GiB。最终实验将运行于显存充足的服务器，当前资源限制只属于本机阶段。

## 已完成命令

```bash
CUDA_VISIBLE_DEVICES= python -B -m scripts.edge_sem.recon.ep7_checks nodesem
CUDA_VISIBLE_DEVICES= python -B -m scripts.edge_sem.recon.ep7_checks dfg
CUDA_VISIBLE_DEVICES= python -B -m scripts.edge_sem.recon.ep7_checks edgesem
CUDA_VISIBLE_DEVICES= python -B -m scripts.edge_sem.recon.ep7_prepare prepare
CUDA_VISIBLE_DEVICES= python -B -m scripts.edge_sem.recon.ep7_prepare seal
CUDA_VISIBLE_DEVICES= python -B -m scripts.edge_sem.recon.ep7_verify accept
```

真实安慰剂闸门由 test_model_relations.py 写入 placebo_probes。封存后两剖面重载记录见 sealed_plan_cpu.json。定向回归：

```bash
CUDA_VISIBLE_DEVICES= python -B -m pytest -q scripts/edge_sem/tests/test_execution_core.py scripts/edge_sem/tests/test_execution_policy.py
```

可重复执行的只读历史验收：

```bash
CUDA_VISIBLE_DEVICES= python -B -m scripts.edge_sem.recon.ep7_verify frozen
```

## 授权后才可执行

1. 先将 protocol_p2/registration.json 按原字节本地提交。
2. 用户确认 D1–D3 和本轮 8 个 GPU 探针、1 个范数试点、20 个正式 G3R fit。
3. 将实际用户回复另存为批准记录，含 user_request 和明确的 D1_D2_D3_confirmed、gpu_probes_authorized、norm_pilot_authorized、formal_20_fits_authorized；不能由脚本自行推断授权。
4. 以下入口新建 decisions 与独立执行授权；原 plan/seal/authorization 不改：

```bash
python -B -m scripts.edge_sem.recon.ep7_authorize \
  --approval-file <实际用户批准记录.json> \
  --registration-commit <含登记文件的真实提交SHA>
```

串行执行（确保没有继承 CPU 检查用的空 CUDA_VISIBLE_DEVICES）：

```bash
python -B -m scripts.edge_sem.recon.ep7_run \
  --root scripts/edge_sem/artifacts/ep7_v1
```

顺序固定：8 次单轮探针 → 50 轮仅训练范数试点 → 20 次正式 G3R → 完整结果汇总。每次 GPU 工作使用独立子进程和原训练锁。任一门槛失败保留现场并停止；不自动重试、降维或更换设备。

权重保存在本地 WSL；计划、初始化摘要、收据、日志和源码快照用于审查。禁止将后续正式结果写回已有 CPU 收据或历史报告。
