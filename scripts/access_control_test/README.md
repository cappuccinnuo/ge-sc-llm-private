# Dataset A 权限访问控制测试

本目录由 **Codex** 于 2026-10-08 新建。只处理 Dataset A 的 `access_control`，复用当前重入流程的构图配置和源码范围标注规则。脚本、图、日志和审计均保存在本目录；原来的训练器、构图器、标注模块和其他漏洞数据未修改。

## 已生成的数据

位置：`scripts/access_control_test/artifacts/dataset_a_source_range_v1/`。

| 项目 | 合约级图 | 行级图 |
|---|---:|---:|
| 合约文件数 | 114 | 57 |
| 节点数 | 13,432 | 7,710 |
| 边数 | 15,538 | 8,840 |
| 漏洞节点数 | 3,236 | 3,236 |
| 节点类型 | 16 | 16 |
| 边类型 | 7 | 7 |

合约级标签为 57 个权限控制漏洞合约、57 个仓库选定的良性候选合约。
行级图保留全部漏洞合约的节点和内部边，包括正常节点；不是仅提取正类节点。
特征使用 `Salesforce/codet5p-770m` 的本地 tokenizer，`ids` 方案、float32、补齐/截断至 512。没有加载 LLM 模型权重。实际 tokenizer 类为 `RobertaTokenizerFast`，词表大小 32,100。

| 文件 | 用途 |
|---|---|
| `tokenizer_ids_codet5p-770m_hcg_compressed_graphs.gpickle` | 合约级训练输入，包含节点标签和 token 特征 |
| `linelevel_tokenizer_ids.gpickle` | 行级训练输入，57 个漏洞合约的诱导子图 |
| `hcg_labeled.gpickle` | 未添加 token 特征的全量图 |
| `graph_labels.json` | 合约级 0/1 标签，文件名排序，供 EthIdsDataset 读取 |
| `per_contract/*.gpickle` | 114 份分别生成的合约图，未添加 token 特征 |
| `annotations.json` | 本次使用的权限控制标注 |
| `source_provenance.json` | 标注源码对应关系及核验信息 |
| `generation.json` / `generator.log` | 每个合约的生成统计、解析检查及底层输出 |
| `manifest.json` | 参数、输入/输出哈希、tokenizer 资产和脚本哈希 |
| `audit.json` / `audit_report.md` | 完整审计数据和人可读报告 |
| `original_code_hashes.json` | 原有代码与文档的生成前哈希 |

## 生成流程与复用

1. 使用仓库 `experiments/ge-sc-data/source_code/access_control/source_files/` 的 114 份源码，未重新随机选择良性合约。
2. 调用 `labeling_v2/label_rules.py::verified_annotations`，加载 SmartBugs JSON 中的 `access_control` 标注，以及 SolidiFI `tx.origin` 的 CSV 区间。
3. 核验漏洞源码：17 份 SmartBugs、40 份 SolidiFI。56 份字节一致；FibonacciBalance.sol 仅第 8 行 pragma 不同，行号不移动且不涉及标注行。
4. 调用现有 `CFGDriver` 和 `generator._annotate_cfg_graph`。现有生成器在 CFG 中加入函数关系；保留本地 HCG 的节点、边类型及 narrow end_if 行号配置。
5. 调用 `line_mapping.py` 将预处理行号映射到原始源码行。节点原始源码行与权限控制标注有交集时，保存相应漏洞记录，否则为 None。
6. 生成完整合约标签；确认 57 个有标注文件与仓库既有 buggy CFG 文件集合一致。每份标注合约必须至少命中一个节点，失败文件不静默跳过。
7. 调用 `encode_tokenizer_features.py::encode_ids` 生成固定长度特征。
8. 从全量图取全部 57 个漏洞合约形成行级图，保留完整节点属性、边和特征。
9. 使用原有训练标签读取器、DGL 关系转换及 get_node_token 验证输入，不进行训练。

本次不调用旧 `build_labeled_graph.py` 的无类别过滤入口，也不调用写死 reentrancy 的 `labeling_v2/build.py` 主程序；只导入已有的通用函数。

## 在 WSL 中重新生成

当前 v1 已经生成，脚本拒绝覆盖现有输出。重跑时选择一个新的输出目录：

```bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm

bash scripts/access_control_test/run.sh \
  --output scripts/access_control_test/artifacts/dataset_a_source_range_v2
```

仅使用本地 tokenizer 缓存，终端实时输出每份合约的节点/边数量与 token 处理进度；日志写入 `scripts/access_control_test/build_runs.log`。
如 v2 已存在，应更换输出版本。目录里若存在某次失败的中间产物，也不直接覆盖它。

## 独立复核已有结果

```bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm

python -u scripts/access_control_test/audit_dataset.py \
  --input scripts/access_control_test/artifacts/dataset_a_source_range_v1

python scripts/access_control_test/test_dataset.py -v
```

独立复核生成 `audit_recheck.json` 和 `audit_recheck.md`，不会重建图或启动训练。
4 项回归测试覆盖多行范围匹配、空行/注释映射、越界坐标拒绝、同名文件跨类别过滤及源码内容变化拒绝。

## 审计结论与限制

数据一致性检查通过：114 份全部生成、解析器错误为 0；原始坐标、类别过滤、标签、子图、特征、实际训练读取均已核验。
哈希审计覆盖 127 个原有代码/文档文件和 269 个输入数据文件；核验通过。
CSV 范围有 52 个标注行没有图行号覆盖，全部为空行；非空标注行无遗漏，所有标注记录都至少命中一个节点。
117 个节点的 token 序列超过 512，已按原 ids 方案截断；长度统计见 manifest.json。

| 论文 Table 1 项目 | 论文 | 本地 |
|---|---:|---:|
| 合约总数 / 漏洞合约数 | 114 / 57 | 114 / 57 |
| 节点 | 13,432 | 13,432 |
| 边 | 15,538 | 15,538 |
| 漏洞节点 | 2,977 | 3,236 |

漏洞节点多 259，当前没有作者权限控制参考图或其原始转换标注文件，尚未逐节点确定原因。
本地标注属于公开 JSON/CSV 的源码范围重建，不能因节点/边总数一致就声称完全复现作者数据。

保留的已知限制：

- 良性标签沿用仓库选定语料，没有重新执行论文使用的 11 工具筛查，也不能独立证明不存在其他漏洞。
- 本地 7 种边类型保留原状；没有借助作者结果改写边类型或标注。
- `recursive_method_call` 的 3,723 条边都从合约/库/接口声明节点发出，不能将其名称理解为真实递归调用；原生成器的调用目标识别问题未在本实验中修复。
- 行级图约 68.26% 的节点代码在多个合约重复；这是语料重复统计，不是实际交叉验证折间泄漏率。
- 本次完成的是数据生成与审计，没有训练分类器或产生 F1 结果。

构图与节点标签验证通过，不等于真实漏洞语义、每条调用关系或论文数值均已完全验证。详细问题和数据见 audit_report.md、audit.json。

同一份公开标注和原始坐标下，改为只检查端点的诊断计数是 3,114，减少 122（114 个合约声明、8 个函数定义），仍比论文多 137。
因此范围与端点的差别不足以独自解释当前统计差异；这不是作者兼容版本，也未改变本次训练图。
