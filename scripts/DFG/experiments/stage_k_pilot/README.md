# Stage K：整体DDG修复后的固定单折对照

2026-10-19，Codex。工作树`/home/zhao/SmartContract/ge-sc-llm-ddg-v11`。

只运行两个节点任务：reentrancy_author_node、access_control_author_node，均为原固定fold0。

- B0：旧E3b冻结图（已有标量DDG和旧状态/顺序关系）。
- B1：冻结E2标量图＋Stage J覆盖恢复＋Stage K版本域修复后的完整状态关系。
- 共4次新的正式拟合；不为继承、modifier、每个版本检查分别做训练消融。
- B0是上一版DDG基线，不是完全无DDG的原MANDO。历史E0/E1及H1/H2成绩不作为本轮同初始化的配对数值。
- 四任务均生成B1候选图；合约级本轮只构图，不训练。

复用原HGT分类器、Stage F正向adapter和语义成对初始化。B0/B1均从CPU新模型开始，共同参数按节点类型/canonical关系对齐；没有读取训练后权重。构造seed=10000，配对关系seed=10077，fit_seed=1010000，均来源于原任务seed策略。原已有E3b checkpoint不被冒充为当前配对基线。

复用原paper_kfold训练函数体和资源记录，仅换独立checkpoint绑定：
512维inside_token、hidden128、2层、8头；节点Adam lr0.0002/max_lr0.005、OneCycle50步、weight_decay0；最多50epoch、patience7、delta0.001，严格最低验证loss保存best，last独立。完整图前向、train mask监督，同val选模评分；称CV validation、按HCG节点计分。

## 运行与实时日志

```bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
export PYTHONPATH="$PWD"
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2

python -B -m scripts.DFG.experiments.stage_k_pilot.control prepare
python -B -m scripts.DFG.experiments.stage_k_pilot.control run
python -B -m scripts.DFG.experiments.stage_k_pilot.control verify
python -B -m scripts.DFG.experiments.stage_k_pilot.control summarize
```

默认批次`scripts/DFG/experiments/artifacts/paper_kfold/stage_k_v1/`。prepare已存在时拒绝覆盖；成功fit有收据后run会校验复用。失败保留，只有诊断后显式`--retry task_id/B0`或B1才允许整fit重试，不是epoch续训，不自动降配或切CPU。

本次后台实际运行日志：
```bash
tail -F scripts/DFG/experiments/artifacts/paper_kfold/stage_k_v1/run.log
tail -F scripts/DFG/experiments/artifacts/paper_kfold/stage_k_v1/runs/reentrancy_author_node/B1/attempt_001.log
```

一个worker只加载一个GPU模型。新批次plan/seal绑定源码、图、标签、token来源、划分、初值和环境。原Stage G/H/J封存产物不覆盖。不得训练期间更改封存的.py文件。

## 交付

prepared/<task>/B1.gpickle与graph_audit.json；两个节点任务另有task.json、B0/B1_initial.pt及成对初始化记录。
runs/<task>/<variant>/attempt_001包含best/last、逐轮history、梯度/关系支持、有效配置、验证预测、资源和receipt。
results.csv、paired_results.json、prediction_changes.csv由冻结标签和原nodeID独立复算。

本批是单seed固定单折的整体对照，不能宣称完整K折稳定收益或独立泛化。几个既有困难文件不在这两个fold0验证集中，不换折挑成绩，不用训练集结果证明它们被修复。
