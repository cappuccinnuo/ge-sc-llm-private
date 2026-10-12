# 独立节点标注工具 labeling_v2

修改 AI：**Codex**。日期：2026-10-08（EDT）。该目录包含本轮新增代码、验证、图文件及回退记录。原构图/训练代码不需要改动。

## 两种方式

| 方式 | 原始漏洞行来源 | 节点如何成为正例 |
| --- | --- | --- |
| author_compat | 作者下载的完整 CFG+CG 图内嵌记录 | 使用对应作者节点保存的端点/单行值，与恢复出的漏洞行相交，逐节点验证与作者原标签一致 |
| source_range | SmartBugs JSON、SolidiFI CSV | 只保留 reentrancy；CSV 使用 [loc, loc+length-1]；按本地 narrow 节点对应的原始源码行求交 |

source_range 保留 narrow 的既有节点跨度，不把所有节点改成单行。end_if 仍只对应闭合行。CSV 区间代表注入片段，不等于逐行人工验证的可利用漏洞。

author_compat 仅对齐训练标签。它保留作者的异常标注（buggy_18 有 41 个越界预处理行）以及 1 个仅属于 unchecked_low_level_calls 的正例，并在 manifest 中报告。它不是“修正后的真实标注”。

## 实际生成结果

输入是本地 tokenizer_ids_narrow.gpickle；节点、边、原代码、token 和行号属性原样保留。两种版本仍是本地的 7 类关系，未修复/切换边类型，也未重新编码 tokenizer。

| 输出方式 | 全量图 节点/边 | 行级图 节点/边 | 正例节点 | 相比本地 narrow 的 0/1 标签变化 |
| --- | --- | --- | --- | --- |
| author_compat | 18312 / 19267 | 12036 / 11710 | 6570 | 410 |
| source_range | 18312 / 19267 | 12036 / 11710 | 6976 | 2 |

每种方式位于 artifacts/labels_v1/<方式>/，有 contractlevel.gpickle、linelevel.gpickle、graph_labels.json、annotations.json、label_changes.json、manifest.json。总表为 artifacts/labels_v1/summary.json。

全量图中标签元数据变化，所以也另存一份；但合约级监督只用原 graph_labels.json，节点、边、token 与合约标签均未变化，**合约级模型有效训练输入没有变化**。无需仅因本次节点标签调整重跑合约级。行级目标变化，需要重新训练比较。

author_compat 的 node_info_vulnerabilities.lines 使用作者预处理坐标，而 node_source_code_lines_original 仍保留本地 narrow 坐标。不要把两者直接混合做推理行号评估；本工具只提供明确记录坐标系的训练标签对照。

## 环境与运行

在 WSL Ubuntu 中：

~~~bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm
mkdir -p outputs
set -o pipefail
~~~

图已经生成，不必重复构建。先跑作者标签兼容版：

~~~bash
bash scripts/train_linelevel.sh \
  scripts/labeling_v2/artifacts/labels_v1/author_compat/linelevel.gpickle \
  inside_token labels_author_compat_v1 \
  --split_by contract --verbose_epochs \
  2>&1 | tee outputs/linelevel_labels_author_compat_v1.log
~~~

再跑源码范围版：

~~~bash
bash scripts/train_linelevel.sh \
  scripts/labeling_v2/artifacts/labels_v1/source_range/linelevel.gpickle \
  inside_token labels_source_range_v1 \
  --split_by contract --verbose_epochs \
  2>&1 | tee outputs/linelevel_labels_source_range_v1.log
~~~

顺序运行，不要同时占用显存。使用同一 tag 再运行会覆盖该 tag 的训练输出；上述新 tag 在本轮记录时尚不存在。当前训练的随机折划分未修改，因此单次分数差不能严格归因于标签。比较时查看每折 selection.json。

如果仍要用新全量图验证合约训练接口（不预期有标签带来的效果变化）：

~~~bash
bash scripts/train_contractlevel.sh \
  scripts/labeling_v2/artifacts/labels_v1/author_compat/contractlevel.gpickle \
  inside_token labels_author_compat_contract_v1 \
  --label scripts/labeling_v2/artifacts/labels_v1/author_compat/graph_labels.json \
  --verbose_epochs \
  2>&1 | tee outputs/contractlevel_labels_author_compat_contract_v1.log
~~~

重新生成时指定新目录，默认禁止覆盖：

~~~bash
python -B scripts/labeling_v2/build.py --mode both \
  --output scripts/labeling_v2/artifacts/labels_v2
~~~

--mode 可选 both、author_compat、source_range。--graph 指定带现成 token 的本地全量图；--author-graph 指定作者完整混合图；--contract-labels 指定既有合约标签；其余 --source-dir、--smartbugs、--solidifi-dir 用于核验源码和原始标注。所有输出必须在本目录中。默认针对当前 reentrancy 语料，非任意漏洞的通用标注器。

## 验证和限制

~~~bash
python -B -m unittest discover -s scripts/labeling_v2 -p test_labeling.py -v
~~~

12 项检查通过，覆盖范围/端点、单行格式、多类别过滤、源码行号、pragma 差异、重复节点拒绝、节点顺序变化、作者标签不自洽、非标签属性不变量、图文件往返及拒绝未允许 pickle 类型。

构建时额外完成全量节点一一映射、作者标签逐节点重放、图保存重载、真实 get_node_label 读取、合约名单/标签顺序/输入哈希核验。节点身份匹配含源文件、类型、规范化代码和 AST/合流节点锚点；不凭同名或总数转移标签。

源码校验发现 4 份 SmartBugs 文件仅有原位置 pragma 版本变化；记录两边哈希和变更行，只有这些行不属于标注行时才允许。其他代码或行号变化会报错。40 份 SolidiFI 文件必须字节一致。注释器复用只读 scripts/line_mapping.py，其哈希写入 manifest。

## 回退

训练时改回 experiments/ge-sc-data/source_code/reentrancy/linelevel_narrow.gpickle 即可；原图未覆盖。不要还原整个仓库。本目录 history/ 保存文档修改前快照和已有代码哈希。详细变更见 ../../docs/training_changes_2026-10-07.md 第 11 节。
