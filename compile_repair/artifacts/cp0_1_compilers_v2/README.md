# cp0_1_compilers_v2：CP0.1 C 续 501 组兼容性验证（修改 AI：Codex）

2026-11-13，起点 3742fb75e535b5517ded58659e78737a01b51000。按 PROMPTS r2.5 §4.2c，从旧 compatibility_plan.json 的 496 组建立新计划；没有安装、下载或修改编译器、fixture、原计划与失败现场。

## 计划与结果

- 491 默认正例、5 默认负对照、5 设置正对照，共 501，唯一性/版本升序/数目检查通过（compatibility_plan.json）。
- 501/501 均符合预期；正例 496 次 solc rc0、D3，负对照 5 次预期失败且不运行 Slither；原 224 个成功组逐组结果/指纹一致（compatibility.json）。
- 默认负对照为 4 个 0.8.24 Cancun 探针 rc1、一个 0.8.26 require 自定义错误探针 rc2；错误正文见 invocations。对应设置正对照分别是 --evm-version cancun（4）和 --via-ir（1），完全相同设置传给 Slither。
- 运行 wall 28.131 秒，solc 累计 3.007 秒、Slither 7.225 秒；没有自动重试或非预期失败（compatibility.json）。
- 当前 501 组覆盖新增 59 版，逐版计划全部完成。0.4.12–0.8.38 官方快照可信已安装 92/92；其余 33 版保留原证据，不改称本次全部版本/语法穷举验证（coverage.json）。

## 文件与复现

compatibility_plan.json 保存执行前计划及来源哈希；compatibility_command.txt 保存实际脚本；compatibility_invocations.jsonl 保存所有实际命令、输入/二进制 SHA、设置、返回码、诊断、耗时；compatibility_node_facts_v2.jsonl.gz 保存 496 组节点与指纹；compatibility.json 保存逐组与逐版结果；coverage.json 给出覆盖口径。compatibility.stderr.log.gz 是无损原始诊断，SHA/回读校验见 ../cp0_1_env_v2/log_compression.json；原始日志本地保留。

完整命令及顺序见 ../cp0_1_env_v2/README.md 与 CP0_1_REPORT 的 C 续.4。先保证两个生产运行和 20 文件回归都通过，再从第一组运行全 501 组；输出 x/xb 创建，已有批次拒绝覆盖。可信编译器来自旧 cp0_v2 与 cp0_1_compilers_v1 追加清单，重新校验原授权/官方索引/双哈希链，没有新信任文件。

## 验收与边界

节点归档地址残留与重算哈希差异均为 0（../cp0_1_env_v2/archive_audit.json）。两个环境模块测试与 mando DFG 测试全部完成，记录见 ../cp0_1_env_v2/test_summary.json。报告和强制记录已同步追加，doc_check 与冻结审计通过后本地提交，等待审查，不进入 CP1。设置自动触发策略与源码修复规则均未实现，费用为 0 美元。
