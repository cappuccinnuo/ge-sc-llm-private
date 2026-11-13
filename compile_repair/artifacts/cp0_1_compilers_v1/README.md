# CP0.1 C：59 版安装通过，兼容性首次失配停止（修改 AI：Codex，2026-11-13）

B_acceptance.json 全通过后才开始本目录的安装。59 个官方 solc 全部通过 SHA256、Keccak256、--version，支持快照 0.4.12–0.8.38 已安装 92/92；总安装 96 含 4 个原有低版本负对照。没有修改原可信清单、原 ~/.solc-select 文件或全局选择，没有运行 solc-select install/use。

| 证据 | 内容 |
|---|---|
| authorization.json | 用户批准的 59 版、官方 URL/双哈希、0 美元与 B 门槛 |
| installation_invocations.jsonl、installation_summary.json | 59/59 校验；722168656 字节、335.193 秒 |
| trusted_compilers_addition.json | 独立追加信任，绑定授权、B 门槛及原官方索引 |
| coverage.json | 安装时的官方快照覆盖；其中 pending 是当时状态，最终以下两项为准 |
| compatibility_plan.json | 496 个适用组合及固定顺序、默认选项、首次意外即停止 |
| compatibility_invocations.jsonl、compatibility_node_facts_v2.jsonl.gz | 已执行的直接 solc、Slither 和节点证据 |
| compatibility.json、final_status.json | 224 过、1 失败、271 未运行；完整剩余清单及分版本状态 |
| installation_command.txt、compatibility_command.txt | 精确一次性执行源码；既有目录禁止重用覆盖 |
| seal.json | 本批证据 SHA256 |

首个失败是 0.8.24 + tests/fixtures/features/h0824_blob.sol，solc rc1，错误指向 blobhash(0) 未声明；未进入 Slither。45 个新版本的适用矩阵全部通过，0.8.24 执行 12/18（11 过、1 失败），0.8.25–0.8.37 的 13 个新版本未测试。详见 CP0_1_REPORT C 与 CHANGE_LOG §11，C 未通过，CP1 不能开始。

按照用户与 PROMPTS 的停止规则，没有改变 probe、版本下界、EVM 参数或判据，也没有自动重试。下一步只建议先审查语法引入版本和 EVM 设置；任何变更须先咨询用户，确认后使用新批次继续，不能修改本目录现场。安装成功不等于全部特征或图语义验证成功。

本次兼容性执行等效命令如下，列出供审阅；未授权直接重新执行已经存在的批次。

~~~bash
cd /home/zhao/SmartContract/ge-sc-llm-compile
env PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64 /home/zhao/miniconda3/envs/compile-repair-production/bin/python -B - < compile_repair/artifacts/cp0_1_compilers_v1/compatibility_command.txt
~~~

费用 0 美元，无 LLM、训练或范围外下载安装；旧输入与既有编译器不变的证据在 cp0_1_env_v1/frozen_audit.json。

最终封存说明：seal.json 保留为首次封存快照；最后新增暂存检查记录后的权威文件清单及校验和使用 seal_v2.json。原始 Slither stderr 中的三处空白格式提示未裁剪，检查范围与原始诊断见 cp0_1_env_v1/final_staging_audit.json；全部提交文件以 file_inventory_v2.json 为准。
