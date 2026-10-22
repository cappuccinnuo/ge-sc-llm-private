# buggy_18：MANDO-HGT 与 MANDO-LLM 发布图标注对比

日期：2026-10-20。审查与记录：Codex。仅检查重入、访问控制各自的 buggy_18.sol；同名文件分属不同类别，内容不同。

## 结论

两类均不一致。换算到同一预处理坐标后仍存在差异，不能用“一个是原始行号、一个是预处理行号”解释。对比的是 MANDO-HGT 已提交的原始 vulnerabilities.json 与 MANDO-LLM 下载的 CFG+CG 图中实际保存的 node_info_vulnerabilities；没有取得或声称取得 MANDO-LLM 发布图生成时的完整原始 JSON。

## 来源核验

MANDO-HGT HEAD：f791a855cd58b52420c7690200a90a415a449e1c。每类 buggy_18.sol、BugLog_18.csv、vulnerabilities.json 共六个文件均与 git show HEAD 对应文件逐字节一致。标注 JSON 不是本轮本地重建文件。

每类 HGT 源码、MANDO-LLM 本地 source_files 源码、SolidiFI-benchmark 对应源码三者逐字节相同。重入 source SHA 为 b9e23563d26a4976a295154577358f01d63bf533c67775b065a877b934bef9ec；访问控制为 d8505eecd2d5acd06a30006b1e163a08e5bc3a7918c69c86f809c4e9bdeb8ad4。此检查不单独证明作者历史生成环境使用了同一版本源码。

HGT 原始 JSON 的去重行集合与 CSV 区间 [loc, loc+length-1] 的并集完全一致。重入 JSON 有328个条目、324个不同行号；访问控制150个条目、148个不同行号。CSV重叠带来的重复不影响集合求交，不能据此解释越界行号。

## 同坐标比较

| 类别 | HGT原始不重复标注行 | 换算为预处理坐标 | LLM图内不重复标注行 | 交集 | LLM图内越界行 |
| --- | ---: | ---: | ---: | ---: | ---: |
| reentrancy | 324 | 300 | 82 | 41 | 41 |
| access_control | 148 | 148 | 46 | 23 | 23 |

重入源码按换行切分738个行槽，预处理后525行；图内最大标注840。访问控制分别560、371，图内最大标注687。这两个最大值甚至超过当前原始源码长度，不能仅用去注释、去空行解释。

行号转换调用已存在 scripts/line_mapping.py 的字符来源映射，未使用常量偏移。图读取前核验既有冻结 SHA，再使用 scripts/labeling_v2/safe_graph.py 的受限全局白名单读取器。没有运行普通 pickle.load，没有修改任何原图。

## 同一份 LLM 图上的节点标签复放

| 类别 | 文件节点数 | 作者发布标签正例节点 | HGT标注+同一HCG端点规则 | 标签不同节点数 |
| --- | ---: | ---: | ---: | ---: |
| reentrancy | 424 | 35 | 249 | 214 |
| access_control | 284 | 17 | 110 | 93 |

两类发布图内嵌标注用端点求交都能零差异复现发布图标签。换用 HGT 标注产生上述差异，说明这一对比中差异来自标注集合，而非更换图结构或改用整个节点范围。

注意249/110不是MANDO-HGT自身Slither图的实际正例节点数，而是将其原始标注换算后投影到同一MANDO-LLM图的受控结果。本轮未运行HGT构图，也未检查HGT发布的二进制训练图。

## HGT源码中的规则

ge-sc-transformer/process_graphs/control_flow_graph_generator.py 第46–47行取 Slither node.source_mapping['lines']；第60–81行计算其与漏洞行集合的交集，非空时挂载整条漏洞记录。因此HGT原生处理使用Slither提供的源码行集合，不应等同于Tree-sitter首末端点表示。此次坐标转换仅服务于跨版本同图比较。

## 可以确定与尚不能确定

- 可以确定：已核验的两个版本资产中，buggy_18标注不一致；不是本轮DDG或本地近期标签加工才产生的差异。
- 可以确定：HGT仓库原始标注与其CSV一致；LLM发布图记录对当前源码存在越界和缺失。
- 尚不能确定：作者历史流程是使用了不同源码/标注版本、发生坐标转换错误，还是其他发布处理问题；需要生成脚本、当时的标注输入或作者说明。
- 不能推导：CSV整个注入区间就是人工核验后的最小漏洞语句，或换成HGT标注得到的更高F1就更正确。

## 产物与执行

audit.py 为定点只读审计脚本；comparison.json 保存完整行集合、逐节点分歧、输入SHA和来源证明。两类断言均通过，输入前后SHA一致。新增报告与两树训练变化/交接记录；未修改算法、训练代码、标签、特征、图或checkpoint，无新训练。

已执行命令：

~~~bash
conda activate mando
python -B /home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/buggy18_hgt_llm_comparison_v1/audit.py
~~~

脚本使用独占创建 comparison.json，避免重跑覆盖本轮记录。复核时应使用新审计目录。本轮未运行全部DDG单元测试（无运行代码变动），未下载新资产或执行编译。一次辅助源码检索因WSL未安装rg而未完成，改用只读Python检索完成，不涉及数据/训练失败。
