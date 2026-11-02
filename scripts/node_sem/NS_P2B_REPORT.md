# NS-P2b 完成报告

日期：2026-11-02。修改 AI：Codex。基线：node-sem@e5aab8d2，PROMPTS r7。新增代码只有非训练模块 doc_check.py 及其测试；诊断与文档生成脚本位于本批产物目录。未改生产者、特征或模型，未使用 GPU，未启动训练。

## 1. 中文损坏与保护

已确认 f049d18e 中报告为 2,058 个字面 U+003F 问号、0 个中文字符；三份历史记录的 NS-P2 节也损坏。写入通道为 Windows PowerShell 字符串脚本经 stdin 到 WSL Python，调用形态是 `$s=@'…Python script…'@; $s | wsl.exe -d Ubuntu-22.04 -- python3 -`。项目未保存当时完整脚本文本，因此不能逐字复原原始命令。当前 $OutputEncoding=us-ascii；把 U+4E2D/U+6587 组成字符串经同一路径传给 od，得到 3f3f0d0a，复现了替换机制。此前核验只检查本地/Git 字节一致，没有检查中文可读性，这是 Codex 的验收遗漏。

本轮只用 ASCII 的 JSON Unicode 转义或 Base64 载荷通过该通道，在 Python 里解码并以 UTF-8 写文件。所有修订中文必须再经 doc_check --expect-cjk，不能以可解码或哈希一致代替内容检查。

doc_check.check(path, since_bytes=None, expect_cjk=False) 严格解码全文件 UTF-8；指定追加前字节长度时，只对新增段落检查连续问号、U+FFFD 和中文要求，偏移不得切断 UTF-8 字符。--expect-cjk 由调用方明确声明中文意图，避免把合法英文标题误判为损坏。doc_check 不进入 RUNTIME_MODULES。

用户已批准两项最小调整并予以记录：(1) 实际损坏节后已有上一轮可读更正，归档后只替换损坏节，前缀与后缀均逐字保留；(2) “标题原本应有中文”不能由纯英文内容推断，用 --expect-cjk 显式声明，本轮四份中文文档强制启用。没有改变匿名化、模型或特征设计。

原始损坏内容来自 f049d18e，四份分别保存原始字节；替换记录同时记录 prefix/suffix SHA 与长度。本轮文档已经在上一轮追加更正，因此后缀确实存在。已批准保留前后全部字节，而非按模板假设删除后缀。旧独立报告的上一轮可读版本保存在 preexisting_document_edits.patch。

## 2. 编号影响（只读 CPU）

按节点类型＋原名文本分组，要求出现在两个以上文件中；排除 env_source 与 END 占位文本。分裂组内对每个唯一匿名文本选一份已封存向量，计算全部无序两两 cosine；不同匿名文本的频次不会重复加权。总体统计按 pair 加权，另保存等权组均值。原名对照检查同原文向量逐位相同，cosine 数值误差 <1e-12。

随机对照在同节点类型中选原文不同的两个文本组，再各取匿名变体；每任务固定 RandomState(1)、有放回抽样、每类型对数与组内完全一致。这只是诊断种子，没有新增训练 seed；“原文不同”不等于语义无关，不将其解释为严格负例。

| task | split/shared | pairs | within mean | median | p05 | control mean | median | p05 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| reentrancy_node | 735/841 | 75457 | 0.903835 | 0.912406 | 0.804697 | 0.601283 | 0.594306 | 0.381917 |
| access_control_node | 561/669 | 36939 | 0.922279 | 0.927494 | 0.848926 | 0.624942 | 0.635369 | 0.388834 |
| reentrancy_contract | 1155/1269 | 99042 | 0.902175 | 0.912087 | 0.799734 | 0.615706 | 0.612720 | 0.386796 |
| access_control_contract | 893/1005 | 60230 | 0.912641 | 0.921694 | 0.813855 | 0.637461 | 0.643771 | 0.405901 |

不同文件的 vN 编号使向量不再相同，但同原句变体的平均相似度仍高于同类型不同原文对照。结果量化了编号敏感性，没有证明检测 F1 会提升或下降，也不构成改变 r7 冻结编号决定的依据。原名上限全部通过：同一原文的向量逐位相同，cosine 为 1（容许浮点舍入）。不把大量语句对当作独立实验做显著性宣称。

## 3. 未改名名称的事实核对

对冻结完整匿名源码 AST 按原切片身份统计，四任务均为 0 个非 vN 且不在保留表中的代码名称，re_ent/txorigin 原文标记匹配均为 0。字符串字面量中的普通词单列，它们不是变量名，不隐去也不误计为匿名化失败。

文档列举的 data、number、min、max、sig、interfaceId、encodePacked 在实际 grammar 中确实出现为 identifier，且 reserved(name)=true；它们未改名的原因是保留表，而非“不是 identifier”。例如 data 在 parameter、call_argument、member_expression 等上下文保留，说明保留规则是拼写级而非只保留内建绑定。此为冻结 8G 的范围限制，本轮只记录，不修改；不同任务具体次数与 grammar_type/parent_type 见 residual_names.json。

| task | checked statements | nonreserved code occurrences | marker matches | reserved identifier type groups |
| --- | --- | --- | --- | --- |
| reentrancy_node | 10977 | 0 | 0 | 78 |
| access_control_node | 7495 | 0 | 0 | 80 |
| reentrancy_contract | 17080 | 0 | 0 | 91 |
| access_control_contract | 13069 | 0 | 0 | 92 |

## 4. 测试、完整性与停止位置

| suite | passed | failed | skipped | warnings | seconds |
| --- | --- | --- | --- | --- | --- |
| node_sem | 237 | 0 | 0 | 4 | 6.313 |
| dfg_v2 | 2653 | 0 | 0 | 9 | 152.547 |
| legacy | 223 | 0 | 0 | 29 | 3.650 |

8 份 CODE manifest 均经 carrier.load_modality 重新通过源文件、实现、资产和逐行向量校验；8H 计划 load 与生效 runtime_resume_v2 相等。未重新编码，不使用 GPU、不读取评分或预测文件。最终完整性检查与 doc_check 日志见 artifacts/ns_p2b/final_validation.json、doc_check.log；原文归档与替换字节边界见 corrupted_docs/index.json、document_rewrite.json。

实际命令（仓库根目录，mando，CUDA_VISIBLE_DEVICES=''、PYTHONDONTWRITEBYTECODE=1、OMP/MKL=2、既有 TREE_SITTER_LIB_DIR）：

```bash
python -B -m pytest -q -p no:cacheprovider scripts/node_sem/tests/test_doc_check.py
python -B -m scripts.node_sem.artifacts.ns_p2b.run_diagnostics numbering
python -B -m scripts.node_sem.artifacts.ns_p2b.run_diagnostics residual
python -B -m scripts.node_sem.artifacts.ns_p2b.run_diagnostics legacy
python -B -m pytest -q -p no:cacheprovider scripts/node_sem/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/tests tests/test_graph_utils.py
python -B -m scripts.node_sem.doc_check --expect-cjk scripts/node_sem/NS_P2_REPORT.md scripts/node_sem/NS_P2B_REPORT.md scripts/node_sem/PROGRESS.md HANDOVER.md docs/training_changes_2026-10-07.md
```

诊断输出使用排他创建；复验需新建输出批次或只读检查现有 JSON，不能直接覆盖本批结果。

仅完成 NS-P2b，本地提交但不自动推送或推进 NS-P3。最终实验按用户计划运行于显存充足服务器；本机 RTX3050 4 GiB 只是当前开发资源限制，服务器尚未部署实测。


提交前补充：通用 `git diff --cached --check` 对原始 `preexisting_document_edits.patch` 的空白上下文行报尾空格。这是原始 diff 语法的一部分；为保留归档字节，仅该历史归档免于尾空格格式检查，其 SHA 与暂存字节仍严格核验。其余新增代码、可读文档和 JSON 的暂存格式检查通过。原失败与限定复核记录保存于 artifacts/ns_p2b/commit_validation.json；未改算法或实验产物。
