# Prompt 8G 操作说明

这是 N-anon-s 特征与170项实验计划的**准备入口**。不包含授权训练入口，不修改冻结图/标签/折，不接受部分文件通过后继续。

实际执行环境：

```bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export CUDA_VISIBLE_DEVICES=''
ART=scripts/DFG/experiments/artifacts/dfg_v2
BATCH="$ART/prompt8g_v1"
```

以下是本次实际运行次序。该批目录已存在，**不要直接覆盖重跑**；复现实验应先指定全新 BATCH 并同步所有新引用。入口排他创建输出目录。

```bash
python -B -m scripts.DFG.dfg_v2.benchmark_v2.prepare_spelling names \
  --prior "$ART/prompt8f_v1/naming" --output "$BATCH/naming"

python -B -m scripts.DFG.dfg_v2.benchmark_v2.prepare_spelling semantic \
  --naming "$BATCH/naming" --store "$ART/graphs_v2_r1/store.json" \
  --historical-cases "$ART/prompt8f_v1/projection_blockers.json" \
  --output "$BATCH/semantic"

python -B -m scripts.DFG.dfg_v2.benchmark_v2.spelling_probes \
  --naming "$BATCH/naming" --semantic "$BATCH/semantic" \
  --old8e-naming "$ART/prompt8e_v1/naming" --output "$BATCH/probes"

python -B -m scripts.DFG.dfg_v2.benchmark_v2.spelling_features build \
  --naming "$BATCH/naming" --semantic "$BATCH/semantic" \
  --probes "$BATCH/probes" --output "$BATCH/features"

python -B -m scripts.DFG.dfg_v2.benchmark_v2.spelling_features verify \
  --features "$BATCH/features" --output "$BATCH/model_proof_attempt2"

python -B -m scripts.DFG.dfg_v2.benchmark_v2.spelling_plan \
  --naming "$BATCH/naming" --semantic "$BATCH/semantic" \
  --probes "$BATCH/probes" --features "$BATCH/features" \
  --model-proof "$BATCH/model_proof_attempt2" --output "$BATCH/plan"
```

原 model_proof/ 尝试因会话中断不完整，原样保留。model_proof_attempt2/ 是完成验收的独立目录；不是从训练中断点续训。verify只用CPU eval、已有零步初值；正式训练须另建新初值。

语义检查失败可用 prepare_spelling decision 保存阻断决定；通过语义并不授权训练。探针失败时停止，不修改规则/门槛重试。本批384项语义与P2/P3全部通过；无需调用阻断入口。

只读检查已封存的计划：

```bash
python -B -c "from scripts.DFG.dfg_v2.benchmark_v2.spelling_plan import verify_plan; print(verify_plan('scripts/DFG/experiments/artifacts/dfg_v2/prompt8g_v1/plan/plan.json'))"
```

测试（需创建专用临时父目录；本次临时树已在测试结束后清理）：

```bash
mkdir -p "$BATCH/_test_tmp_recheck"
python -B -m pytest -q -p no:cacheprovider \
  scripts/DFG/dfg_v2/tests/test_prompt8g_spelling.py \
  scripts/DFG/dfg_v2/tests/test_prompt8g_parity.py \
  scripts/DFG/dfg_v2/tests/test_prompt8g_gate.py \
  scripts/DFG/dfg_v2/tests/test_prompt8g_probes.py \
  scripts/DFG/dfg_v2/tests/test_prompt8g_features.py \
  scripts/DFG/dfg_v2/tests/test_prompt8g_plan.py \
  --basetemp "$BATCH/_test_tmp_recheck/targeted"
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests \
  --basetemp "$BATCH/_test_tmp_recheck/v2"
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py \
  --basetemp "$BATCH/_test_tmp_recheck/legacy"
```

输出：naming/逐文件双射与保留计数；semantic/384项事实与投影证据及36节点恢复；probes/冻结OOF预测与角色AUC；features/四任务新旧NPZ；model_proof_attempt2/20项装配检查；plan/计划、seal、false授权模板；*.command.json/实际命令与退出记录。

原源码与图 code 字节不改。特征装配仅在内存模型副本中替换原节点 token，env_source及其他属性保留。512维数组是冻结 tokenizer IDs，不加载CodeT5模型权重。需保留原清单所引用的本地图、tokenizer资产和零步初值；仅克隆源码不能自动获得全部大文件。

本轮正式HGT训练0次；P3有5次CPU逻辑回归诊断。170项准备计划不得直接传给旧CLI。后续先确认L-orig/L-audit、seed数量、执行位置，再完成运行绑定验证。报告见 ../PROMPT8G_REPORT.md，详细记录见 training_changes §69。
