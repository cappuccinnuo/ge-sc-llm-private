# CP0.1 B 本机生产环境与验证（修改 AI：Codex，2026-11-13）

依据 PROMPTS r2.4 与用户明确授权，起始提交 897fbd03116040ddbc8d106db1b844624f512091。B 全部原定门槛通过，A 不重做、不改历史；C 的独立停止状态见相邻 cp0_1_compilers_v1。详解见 CP0_1_REPORT B 与 CHANGE_LOG §11。

| 证据 | 内容 |
|---|---|
| authorization.json、environment_installation_request.json | 本轮明确授权与替代 0.9.6 的请求；原请求保留 |
| baseline.json、frozen_audit.json | 开始前身份、文档偏移及冻结文件/旧产物/环境/旧编译器审计 |
| conda_*、pip_*、environment.json | 精确包、官方来源、哈希、安装过程与测试日志；pip_freeze.txt 完整版本 |
| isolation_adjustment.json | 仅新环境禁用 user-site，先解析现场保留 |
| intervals_*、interval_equivalence.json | 冻结 tree-sitter 区间 846/846 相同 |
| production_comparison.json、production_invocations.jsonl | 846 次固定版本直接 solc 与 Slither；843 D3，3 个指定断言 |
| production_node_facts_v2.jsonl.gz、structure_differences.json | 完整节点、435 份 key5 差异；类型与数量吻合 |
| ir_differences.json | 有序 IR 统计及前 20 例，不作为失败 |
| feature_probes_B.json | 原始 19 个 probe 的 SHA/下界与 23 次适用组合的完整结果 |
| rewrite_manifest.json、rewrite/、rewrite_*.json | 三工作副本及两套环境前后节点差异，无生产规则 |
| pytest_*.json/log、development_corrections.json | B 测试；初次正则收集错误及修正后的通过 |
| B_acceptance.json | 进入 C 的全部门槛及绑定 SHA，通过时间 2026-11-13 07:55:58 EST |
| *_command.txt | 本次一次性命令源码，用于复核执行方式，不是新增模块入口 |
| file_inventory.json、final_audit.json、doc_check_v*.jsonl、seal.json | 本轮文件清单、最终检查与封存 |

新环境为 /home/zhao/miniconda3/envs/compile-repair-production，Python 3.10.21、Slither 0.11.6、crytic-compile 0.4.2、solc-select 1.0.4、tree-sitter 0.20.4。始终显式调用 solc 路径，禁用 user-site，仅代理联网，不调用 solc-select install/use。mando 保留，回归 profile 为 0.8.0/0.2.4。

本次实际 B 主命令可表示为下列形式。目录已经存在且写入采用排他模式；只有另获准复验、将命令源码中的 out 改为新批次并校验输入后才能再次运行，不能直接覆盖。B 的生产测试是在 C 安装之前运行，不能据此把安装后的全部新增组合记为已通过。

~~~bash
cd /home/zhao/SmartContract/ge-sc-llm-compile
env PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64 /home/zhao/miniconda3/envs/compile-repair-production/bin/python -B - < compile_repair/artifacts/cp0_1_env_v1/production_batch_command.txt
~~~

结果只证明指定版本下的编译、D3 与归档差异，未证明全部图边或 transient 语义。没有训练、图存储、LLM 或范围外安装，费用 0 美元。pytest 临时树和 runtime_downloads 不提交，已提交的抽取结果与正式日志足以查证本轮数字。

最终封存说明：seal.json 保留为首次封存快照；最后新增暂存检查记录后的权威文件清单及校验和使用 seal_v2.json。原始 Slither stderr 中的三处空白格式提示未裁剪，检查范围与原始诊断见 cp0_1_env_v1/final_staging_audit.json；全部提交文件以 file_inventory_v2.json 为准。
