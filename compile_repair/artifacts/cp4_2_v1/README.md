# CP4.2 普通修复的图评分

修改 AI 为 Codex。输入提交为 `30df6664`，规范为 PROMPTS r2.18 §4.6c。在仓库根目录使用本地 CPU、生产 Slither 0.11.6 与冻结的 solc，所有物理源码和编译器输出位于仓库外的 `/home/zhao/SmartContract/compile-repair-local/cp4_2_v1/`。

## 如何读一个分数

`raw` 保存按原始指令文本得到的分数。普通修复只在有偏移对应的保留节点中核对 TMP、REF 和 TUPLE 的定义和使用。成功必须同时满足节点的其他事实一致、指令类型与操作数相同、同族双向唯一，并排除原始与修复后所有源码中同名标识符和解码字面量。遇到一处不匹配就保留整项原分，原因写在 `counter_correspondence`。真正被移动的节点按原位置丢失及新位置新增计数。

用户批准原文件迁移沿用 CP4.1 全图结论，同时记录仅用保留节点推导的对应关系。原有 61 项的原分和全图分在 lost 上有差异。例如 `cp3_15136` 两个数分别为 17 和 0。[迁移决定](authorization.json) · [全部差异](migration_review.json)

## 已封存数据的重算

- `rescore.py exact` 逐项读取加密哈希已核对的图、编辑、原始与工作副本以及成功编译记录。14,196/14,196 个样本的旧评分字段逐项相等，保留节点对应均为 identical。[逐项结果](exact.jsonl.gz) · [汇总](exact_summary.json)
- 114 个迁移的原分、全图分和原适用范围内的核验证明均相等。仅看保留节点时 58 项 identical、56 项 verified。初版汇总在第 5 行发现原始证明计数 111、现有计数 112。核对第一批 21 项后，发现其中 7 项还含当时尚未加入计数范围的未改名 TUPLE。第二次核对取已生成的 5 行并补余下 109 行，对初批重新推导当时的计数，同时保留当前计数。所有评分指标都参与了对照。[逐项结果](migrations_final.jsonl.gz) · [计数依据](migration_summary.json)
- `negative.py` 使用 CP4 已封存源码算子、编辑和真实图，对 22 个错误修复以及 1 个缺节点对照重新评分，全部检出。新增测试覆盖错误的 TMP 操作数、只交换结果名称，以及文件改名同时存在缺失节点时对保留节点的评分。[错误修复](negative.json) · [审查夹具](review_fixture.json)
- 三套最终测试使用两个环境各自的 Python，以仓库根目录为工作目录，关闭缓存并写入独立临时目录。production 为 1,073 通过、6 跳过，mando 为 608 通过、471 跳过，DFG v2 为 2,653 通过、9 条告警。既有 CP4.1 的 253 项均在生产测试中。逐函数增删及 354 个冻结 DFG 引用验证在范围文件中。[回归记录](final_tests/) · [代码范围](final_scope.json)

## 函数移动实验

固定种子 20261122，按语料轮流抽取 dev 单元，用带种子的单元哈希定序。合约主体开头已有的函数、构造函数和没有实际 IR 的定义不入选。选定单元、文件位置、函数、原始字节哈希、编译器及设置在编译前封存。只向修复映射写入删除和插入两次编辑。[原始抽样](move_plan.json)

首轮第 60 项 `cp3_27168` 在 solc 0.4.25 下因函数的 NatSpec 参数注释留在原处而失败。全部 200 项中有 45 项涉及这类注释。用户批准沿用 46 项有效收据，在独立目录对 154 项使用完整声明，其中包含首轮通过但须带上注释的 13 项。源码选择与编译设置沿用。[首轮停点](move_stop.json) · [授权](natspec_authorization.json)

第 76 项的创建字节码确有变化。用户同意将这类样本保留在分母，采用产生图时的实测分数，两份 Keccak-256 见单独收据。第 79 项的三个 Yul switch 的变量名包含源码字节起点，移动留下两个换行，使另一个函数内的三个未改动源码段均后移两字节。核实了图、源码和实际安装的 Slither 构造名称的实现。在诊断副本对齐后才得到满分，正式记录保留 616/622。78 项在 `moves_accepted.jsonl`，第 79 项单独保存在 `unexplained_move_stop.json`。逐项核验包含两种工具的收据和图哈希。[创建码授权](literal_authorization.json) · [创建码诊断](literal_rest_of_graph.json) · [Yul 诊断](observed_yul_positions.json)

## 本地复核

从仓库根目录运行下列命令可核对这 79 份收据。命令只读已有记录。完整生产、mando 和 DFG 测试使用的实际命令、独立临时路径与退出状态见 `final_tests/*_tests.json`。重做测试时指定新的临时路径。历史清单保留了顺序和抽样种子。旧结果使用了当时的绝对源码路径，复核时需要能访问同一批外部文件。

```bash
export PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1
q=compile_repair/artifacts/cp4_2_v1
pp=/home/zhao/miniconda3/envs/compile-repair-production/bin/python
mp=/home/zhao/miniconda3/envs/mando/bin/python
"$pp" -B "$q/checkpoint_79.py"
# 两套模块回归及冻结的 DFG v2 回归
"$pp" -B -m pytest -x -q -p no:cacheprovider compile_repair/tests
"$mp" -B -m pytest -x -q -p no:cacheprovider compile_repair/tests
"$mp" -B -m pytest -x -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
```

## 200 项最终结果

200 项固定 dev 函数移动全部编译并通过 D3，其中 198 项保留节点、CFG 边和调用全部相等。逐字 kept 低于 1 的有 81 项。核验后仍低于 1 的包括 1 项嵌入创建字节码变化、1 项 Yul 源码起点变化。所有低分均按实际数值计入 200 项分母。

项目单元共 87 个。按语料计数为 DAppSCAN 44、MANDO 44、SOChecker 21、Trace_CVEs 5、Trace_on_chain 43、Trace_repo 43。生成名称核验状态为 identical 119 项、verified 79 项、rejected 2 项。

| 单元 | 已验证差异 | 保留节点 | CFG 边 | 调用 |
|---|---|---:|---:|---:|
| `cp3_00291` | 创建字节码摘要 | 261/264 | 247/247 | 132/133 |
| `cp3_21529` | Yul 名称中的源码起点 | 616/622 | 592/592 | 244/244 |

执行顺序为首轮、NatSpec 限定续跑、创建字节码差异确认后的续跑，以及从第 80 项开始的最后 121 项。完整 200 行收据和各项实际分数在 `moves_completed.jsonl`，逐项核对入口为 `final_audit.py`。该脚本会独占创建验收文件。仓库外源码及两侧图保留在各条收据指向的路径。历史前 79 项仍可用前文只读命令复核。下列命令从仓库根只读核对最终封存文件中登记的全部产物和交付文件。

```bash
python3 -B - <<'PY'
from pathlib import Path
import hashlib, json
module = Path('compile_repair')
batch = module / 'artifacts/cp4_2_v1'
seal = json.loads((batch / 'seal.json').read_bytes())
for root, records in ((batch, seal['batch_files_excluding_seal']), (module, seal['deliverables_sha256'])):
    for name, expected in records.items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == expected, name
print('CP4.2 hashes verified')
PY
```

[200 项收据](moves_completed.jsonl) · [例外的逐字节或源码段证据](measured_differences.json) · [汇总](acceptance.json)
