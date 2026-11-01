# NS-P1 验收报告

实施：Codex，2026-11-01。分支 node-sem；输入 HEAD：27ea6617fd9fc81d9d60cf068122b8d8c996d930。

**NS-P1 已完成并通过验收。S0 接入等价；本轮没有检验 S1 的正式检测收益。**

## 实际完成

- FeatureSpec、S0/S1 配置、SHA 绑定的特征载体、行身份/源码/AST 锚点校验。
- S0 保留原 Linear(512,128)；S1 用模型级单份 EmbeddingBag(V,64)，各类型 Linear(64,128)。
- 确定性零步初值、独立 plan/seal/authorization、监督与 checkpoint 绑定、历史复用和失败保留。
- 原 DFG、HGT、tokenizer、图、标签、折、8H 数值训练循环及历史结果不变。
- 代码位于本目录；详细文件和选择记录见[训练变更 §72](../../docs/training_changes_2026-10-07.md)、[PROGRESS](PROGRESS.md)和[HANDOVER](../../HANDOVER.md)。

## 验收数字

| 检查 | 结果 |
|---|---|
| 60份历史零步初值独立 tensor_digest | 60/60通过 |
| 历史S0收据、checkpoint及预测指标完整只读核验 | 60/60通过 |
| 四任务×G0/G3R×S0/S1真实载体检查 | 16/16通过 |
| 重入节点fold0/G3R：旧、新入口各2轮CPU | 数值与预测一致 |
| 访问控制合约fold0/G0：旧、新入口各2轮CPU | 数值与预测一致 |
| NodeSem / DFG v2 / 原项目回归 | 184 / 2653 / 223通过 |
| 唯一测试合计 | 3060通过，0失败、0跳过 |

CPU检查比较初值、各类型输入、canonical relation字典、原节点ID、非特征binding、逐轮loss/学习率、最终及best/last权重、Adam、scheduler数值状态和inner/outer预测，数值零容差。仅把maximum_training_epochs改为2，schedule_epochs仍50；实际设备CPU，保留历史config的其他字段。4次短检查共8轮，不计正式结果。没有重训已完成的重入检查。

| CPU任务 | 原/新构造秒 | 原/新fit秒 |
|---|---:|---:|
| 重入节点G3R | 15.969 / 30.813 | 35.177 / 35.032 |
| 访问控制合约G0 | 15.040 / 31.461 | 31.393 / 31.885 |

新增身份与载体核验增加构造开销；单次计时不是稳定性能结论。

S1真实重入节点G3R：V=32100、17节点类型、513维载体，唯一嵌入表2054400参数，总参数6190564，比S0增加1079552。CPU前向有限，无S1正式训练或GPU显存结果。

## 批准的调整与失败记录

1. 用户明确批准限定来源、紧邻SHA校验的torch.load。PyTorch1.8仍使用pickle；没有扩大授权范围。新loader先核对同一打开文件的SHA，再核验张量摘要。
2. 冻结assemble的整图指纹会拒绝标签属性扰动。按批准，生产校验保持；测试先证明旧manifest拒绝改图，再仅重绑临时manifest图指纹，验证载体不变。NPZ/行/source不变，损坏AST锚点仍拒绝。
3. PyTorch1.8的scheduler含实例绑定的anneal_func。首组训练完成后对象身份比较失败；用户批准改为核验同一OneCycleLR类、同一函数实现，其余字段保持严格比较。新测试拒绝换函数/类或微小数值变化。

旧计划、seal、failure.json、38个重入产物及修改前验收源码均保留。独立acceptance_revision1只修改验收逻辑，不修改训练器或旧运行保护；重新构造零步输入复验重入，直接读取原权重，之后只执行尚未运行的访问控制检查。初始内存快照原未落盘，此次重入的初始输入验证是重新构造，报告不将其冒称旧快照。

准备时漏建specs父目录，在零计划/零fit时失败；审查另发现fit父目录也需显式创建。两项均已修复并补测试，未删除历史结果。

## 证据与命令

- [初值摘要](artifacts/ns_p1_initial_digests/digests.json)
- [批准与r4决定](artifacts/ns_p1_acceptance/decisions.json)
- [真实载体检查](artifacts/ns_p1_acceptance/carrier_probe.json)
- [60份历史完整验收](artifacts/ns_p1_acceptance/historical_reuses.json)
- [最终CPU等价结果](artifacts/ns_p1_equivalence/equivalence.json)
- [当前验收计划](artifacts/ns_p1_equivalence/acceptance_revision1/batch/plan.json)
- [最终测试记录](artifacts/ns_p1_acceptance/tests_revision1.json)

最初的batch/plan.json是归档来源；最终报告绑定acceptance_revision1，不改旧seal。60份历史结果复用了已完成的完整审计，并在修订末尾复查收据身份。

实际执行（mando，CPU，原TREE_SITTER_LIB_DIR，OMP/MKL=2，禁写pyc）：

```bash
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
python -B -m pytest -q -p no:cacheprovider scripts/node_sem/tests scripts/DFG/tests tests/test_graph_utils.py
# 批准验收修订后，重跑受影响的NodeSem全套
python -B -m pytest -q -p no:cacheprovider scripts/node_sem/tests

python -B -m scripts.node_sem.equivalence prepare
python -B -m scripts.node_sem.equivalence run
# 首组比较停止后，经明确批准建立独立修订
python -B -m scripts.node_sem.equivalence_resume prepare
python -B -m scripts.node_sem.equivalence_resume run
```

上述准备/验收命令已运行，已有目录拒绝覆盖；不要把它们当作自动重训命令。当前计划只读复验可用：

```bash
python -B -m scripts.node_sem.execution verify --plan scripts/node_sem/artifacts/ns_p1_equivalence/acceptance_revision1/batch/plan.json
```

## 剩余范围

M1/M2、教师/学生、完整融合、GPU预检和正式K折留给后续Prompt。未来F3上下文用于G0时需明确profile行视图，目前不默默裁剪辅助节点。S1配置中的单模态concat入口不代表已实现多模态融合。

最终实验按用户安排在显存充足服务器执行；RTX3050 4GiB只是当前本机开发限制，服务器尚未部署实测。产物保存在WSL；二进制载体和短检查checkpoint保留本地，文本证据与代码随本地提交。停止于NS-P1，不自动推进NS-P2或推送GitHub。
