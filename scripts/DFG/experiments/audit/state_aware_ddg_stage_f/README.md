# Stage F：状态 DDG 覆盖与状态访问顺序验证

日期：2026-10-14；执行者：Codex。版本：`state-aware-ddg-stage-f-v1`。

本轮完成 F0–F3，F4 仅完成合成兼容性和接口准备。没有训练、没有新 F1。
代码位于独立工作树 `/home/zhao/SmartContract/ge-sc-llm-ddg-v11`。
原工作树 `ge-sc-llm` 只追加训练变化和交接文档。

先读 [实施报告](IMPLEMENTATION_REPORT.md)，再按需查：
- [全语料盘点](F0_SUMMARY.md)
- [绑定与版本变更](F1_BINDING_CHANGELOG.md)
- [Oracle 源码复核](ORACLE_SOURCE_REVIEW.md)
- [关系定义](F2_RELATION_SPEC.md) 与 [限制](F2_LIMITATIONS.md)
- [候选图验收](F3_E3_READINESS.md)
- [HGT 接口与后续计划](F4_MODEL_INTEGRATION.md)
- [测试结果](REGRESSION_RESULTS.json)、[资产保护](protected_after.json)

接受的结果为 F0_attempt_001、F1_attempt_002、F3_attempt_002。
旧 attempt_001 和修复前失败日志保留；不是挑选训练成绩。
图清单在 F3_attempt_002/GRAPH_MANIFEST.json，8 个 gpickle 是独立候选资产；
不能用旧 formal 命令直接开始训练。

验证命令（已有 mando 环境，不安装依赖）：

```bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export PYTHONDONTWRITEBYTECODE=1
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export OMP_NUM_THREADS=2
export MKL_NUM_THREADS=2
python -B -m pytest -q -p no:cacheprovider scripts/DFG/state/stage_f/tests
python -B scripts/DFG/experiments/audit/state_aware_ddg_stage_f/verify_delivery.py --validate-only
```

全量回归命令见 IMPLEMENTATION_REPORT。F0/F1/F3生成脚本要求全新输出目录，
并且当前旁路明确绑定本批已接受的上游 attempt，不是任意实验版本的通用控制器。
