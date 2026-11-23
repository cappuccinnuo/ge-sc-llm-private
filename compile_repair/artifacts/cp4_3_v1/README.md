# CP4.3 修复删除与 Yul 起点的评分核验

基线为 `compile-repair@09a8355e`，依据为 PROMPTS r2.19 §4.6d。CP4.2 的图、源码、编辑与工具收据作为输入。本批次记录了每个样本的新分数，以及重算时核对的输入身份。

## 复核入口

`acceptance.json` 汇总三个重算任务、测试套件与历史输入的哈希。`moves.jsonl.gz`、`exact.jsonl.gz`、`migration.jsonl.gz` 逐行记录单元、图哈希、分数、名称核验及原样分数。`replay_scores.py` 将历史分数与移除新增字段后的完整新记录逐项比较，用每个编辑的原始字节重建映射。移动实验使用原 200 项的终版编辑起点和所有项目文件，核对实际工作副本与编辑重放结果。`scope.json` 记录逐函数增删、生产文件 SHA256 及冻结的 DFG 代码引用。`fixtures.json` 指向手写夹具的真实 solc 与 Slither 收据，包含四种场景的评分与工具身份。`negative.json` 保存 22 个错误修复与一个缺节点对照的结果。[验收](acceptance.json) · [工具收据](fixtures.json) · [代码范围](scope.json)

在原工作树从仓库根目录执行以下命令，可只读核对本批文件及交付代码、文档的 SHA256。外部历史源码与图位于封存清单登记的路径，完整重算时需要能够读取这些路径。

```bash
q=compile_repair/artifacts/cp4_3_v1
pp=/home/zhao/miniconda3/envs/compile-repair-production/bin/python
"$pp" -B "$q/delivery.py" verify
```

## 如何解释两个分母

主 kept 以破坏前真值为基准，所有未落入破坏区的原始节点都进入分母。假如修复又删掉一个完好函数，其节点进入 `missing_kept` 和 `removed_by_repair`，对应的边与调用继续计入主指标。诊断块 `surviving` 仅选取原字节仍有对应位置的 kept 节点。如果源码字节仍存在而 Slither 漏了节点，诊断分母仍包含它。CFG 要求两端存活。解析到函数的调用按文件、合约与函数签名识别目标，排除原节点字节已全部消失的函数目标。对于仅记录文本的调用，直接比较存活调用点的 IR。`lost` 单独统计破坏区中未恢复的节点。

Yul 源码范围必须落在组合映射的同一个 original 或 restored 片段，长度、范围内字节、变量名其余部分以及 IR 的定义和使用均须吻合。变更源文件编号仍须两份 solc AST 见证。任一名称核验失败时保留整项原分与原因。`cp3_00291` 的嵌入创建字节码保留实测差异。[创建字节码的既有证据](../cp4_2_v1/observed_creation_hashes.json)

## 重算与测试命令

以下示例使用新的同级目录。每项只运行一次，每个分数文件都采用独占创建。手写夹具使用本机已有 solc 0.8.38、Slither 0.11.6 和 crytic-compile 0.4.2，历史图重算直接读取已有产物。负例驱动沿用 CP4.2 的同字节版本，按 CP4 原始收据中的编译结果重新评分。

```bash
cd /home/zhao/SmartContract/ge-sc-llm-compile
export PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 CUDA_VISIBLE_DEVICES=""
q=compile_repair/artifacts/cp4_3_v1
dest=$(mktemp -d compile_repair/artifacts/cp4_3_replay_XXXXXX)
cp "$q/replay_scores.py" "$q/negative.py" "$dest/"
pp=/home/zhao/miniconda3/envs/compile-repair-production/bin/python
mp=/home/zhao/miniconda3/envs/mando/bin/python
"$pp" -B "$dest/replay_scores.py" moves
"$pp" -B "$dest/replay_scores.py" exact
"$pp" -B "$dest/replay_scores.py" migration
"$pp" -B "$dest/negative.py"
export CP4_SCRATCH=$(mktemp -d) CP4_OUTPUT="$dest"
"$pp" -B compile_repair/artifacts/cp4_v1/run_suite.py production
"$mp" -B compile_repair/artifacts/cp4_v1/run_suite.py mando
"$mp" -B compile_repair/artifacts/cp4_v1/run_suite.py dfg
```

实际套件的命令、独立临时目录与退出状态见 `suites/*_tests.json`。`evidence_seal.json` 对运行证据和代码计算哈希，供报告引用。`seal.json` 另包含文档与文档检查收据，最终版本按 Git 提交定位。
