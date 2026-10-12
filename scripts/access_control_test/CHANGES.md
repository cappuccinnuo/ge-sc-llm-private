# 权限访问控制测试目录修改记录

- 修改 AI：**Codex**。
- 日期：2026-10-08；实际生成和审计 UTC 时间记录在 manifest.json / audit.json。
- 授权范围：在 scripts 下新建权限访问控制测试目录，处理 Dataset A，生成图并审计，尽量只调用现有代码。
- 原有目录修改：无。原有训练改变文档、HANDOVER.md 和 DFG 设计说明均未修改。

## 新增代码

| 文件 | 实现内容 |
|---|---|
| build_dataset.py | 核验权限控制语料和标注；调用现有构图、映射、编码；生成合约级/行级图、标签和 manifest；实时进度 |
| audit_dataset.py | 受限图读取；输入/输出与旧代码哈希、坐标、类别、标签、覆盖率、子图、特征、DGL/训练读取审计 |
| run.sh | WSL 运行入口，python -u、tee 日志、离线 tokenizer、禁止生成原目录 pycache |
| test_dataset.py | 标注匹配与来源校验的 4 项回归测试 |
| README.md | 数据文件用途、流程、参数与环境命令、审计和限制 |

## 原有代码的调用位置

- process_graphs/tree_sitter_codeviews/codeviews/CFG/CFG_driver.py：CFGDriver。
- process_graphs/tree_sitter_codeviews/generator.py：_annotate_cfg_graph。
- scripts/line_mapping.py：build_line_map、preprocessed_to_original。
- scripts/labeling_v2/label_rules.py：verified_annotations、hit_records、parse_records。
- scripts/labeling_v2/safe_graph.py：受限 read_graph、protocol 4 write_graph、sha256。
- scripts/encode_tokenizer_features.py：encode_ids。
- sco_models/graph_utils.py：节点标签、HGT 输入关系、类型编号和 token 特征读取。
- sco_models/dataloader.py：EthIdsDataset。

这些文件只读取/导入，没有修改。禁止写入原模块 pycache；现有 Linux tree-sitter 库存在时直接复用，若缺失则在本测试目录编译。

## 新的权限控制标注入口

1. 类别固定为 access_control，本测试不假称已经实现七类通用入口。
2. SmartBugs 同名文件多条记录累计，只保留当前类别，严格核验对应源码。
3. SolidiFI 对应 tx.origin 数据，使用 CSV 的 [loc, loc+length-1] 完整注入范围。
4. 节点预处理行映射到原始源码行后，求交集生成节点标签；不是端点匹配。
5. 合约标签首先来自目标类别的已核验标注，再核验正类节点是否命中，避免将标注丢失的合约静默当作正常。
6. 全量包含仓库原 114 份源码；行级包含全部 57 份漏洞合约，保留其中正常节点。

## 本次运行与复核

- 实际生成 114/114，失败 0，解析器错误 0。
- 合约级：13,432 节点 / 15,538 边 / 114 文件。
- 行级：7,710 节点 / 8,840 边 / 57 文件。
- 正类节点 3,236；论文 Table 1 为 2,977，差 +259，未调整标签拟合统计。
- 原有 127 份代码/文档和 269 份输入文件哈希未变。
- 52 个未覆盖标注行逐行查明均为空行；无非空标注行遗漏。
- 4 项回归测试通过，真实训练标签读取和 HGT 输入形状检查通过。
- tokenizer 资产补充记录 vocab.json、merges.txt 的哈希及词表大小 32,100。
- 最终审计增加脚本版本哈希和非空标注行覆盖核验。已有图、token、标签未因审计补充而修改。
- 未运行模型训练；没有本次 F1 成绩。

## 兼容性与回退

产物使用 protocol 4，兼容 mando 的 Python 3.7。脚本拒绝覆盖已有输出，重跑应使用新的输出版本。
所有实现和产物均在 scripts/access_control_test 下，不需要切换原构图器、训练器或重入数据即可停止使用本实验。

- 新增同公开标注、原始坐标的端点诊断计数：3,114，少 122、仍比论文多 137。只记录诊断，不生成另一种训练图。
