# cp1_1_v1：CP1.1 本机验收证据（修改 AI：Codex，2026-11-14）

依据 PROMPTS r2.7 §4.3b，起始 compile-repair@d4f4b48a2484591dc185b90475f775f6c9f5498d。只修复 command 路径边界、regression_6c 危险目录防护、输入级 solc 超时与无 Git 封存。旧 CP0–CP1 正式产物和结论未重跑或改写；本目录拒绝覆盖。

## 结果与环境

production：Python 3.10.21、Slither 0.11.6、crytic-compile 0.4.2；mando：Python 3.7.12、Slither 0.8.0、crytic-compile 0.2.4。OMP/MKL=2，production 关闭用户 site-packages；原 96 个可信 solc（支持范围 92 个）保持。CPU 验证，没有训练、GPU 锁、LLM、安装或下载，费用 0。

| 验收 | 结果 |
|---|---|
| 两环境模块测试 | production 562 passed/6 skipped；mando 128 passed/440 skipped |
| 冻结 DFG v2 | mando 2653 passed，9 个原有弃用警告 |
| 旧 argv 等价 | 两环境各 846 个 MANDO + 501 个 C 续计划项，全相同；只生成命令，不重编译语料 |
| 五类路径 | 两环境真实 solc 各 5/5，0.5.17 |
| 超时 | 两环境三场景各 3/3；生产批次继续，信任错误仍停止 |
| 无 Git | 两种真实子进程 complete、code_commit=null、14 个实现 SHA 正常 |
| CLI | 3 fixture × 3 cwd = 9/9；同一 fixture 的状态/版本/设置/key5+IR+标记完全相同 |

CLI 12 次前置 solc、9 次 Slither；各 10 节点，合计 90 个 original。compat_05 选 0.5.0，精确 Cancun 选 0.8.24 + --evm-version cancun，精确 0.4.10 覆盖后选 0.4.12。输入副本和原 fixture 哈希保持，九个 case 的 seal 逐文件回验通过。不能据本批次推出所有合约图语义均正确。

## 文件与身份

| 文件 | 内容 |
|---|---|
| baseline.json | 起始 HEAD、28,331 个跟踪文件 SHA、文档追加字节边界、354 code_refs、96 solc 与包元数据 |
| run_checks.py、pytest_*.json、pytest_*.log.gz | 一次运行的完整测试命令/环境/耗时/退出码/日志哈希；压缩日志无损 |
| test_evidence_production.json.gz / test_evidence_mando.json.gz | 新增测试的原始 JSON/JSONL 文本字典，键为 pytest 临时目录内相对路径，分别 43/9 项 |
| module_acceptance.json | argv、路径、超时、批次边界和无 Git 测试的可读汇总 |
| run_cli_acceptance.py、cli_plan.json | 三个源副本的出处、SHA、预期与九组运行计划；首项非预期即停 |
| cli_invocations.jsonl | 每次 CLI 的完整 argv、cwd、退出码、stdout/stderr、耗时 |
| cli_acceptance.json | 九组逐项验收、节点投影哈希与 case seal 身份 |
| inputs/*.sol | 只在本批次构造的三份测试副本；精确 pragma 改动不作用在原 fixture |
| cwd/out2/* | 九个独立生产输出，含输入副本、完整 manifest、工具调用、节点和原 seal |
| audit_frozen.py、frozen_audit.json | 冻结文件/环境/历史/实现身份/文件数和允许范围核验 |
| check_docs.py、doc_check_v* | 强制六份 UTF-8/CJK 文档检查及命令收据 |
| seal.json、file_inventory.json | 产物 SHA256 和精确提交清单；不包括自身形成循环 |

原始 pytest 日志仍留本地；提交压缩日志与收据，不提交重复明文或 /tmp 临时树。没有删除旧临时目录或修改旧 case seal。本目录的校验脚本只属于证据，不被生产模块导入；全部模块改动清单见 CP1_REPORT 的 CP1.1 和 CHANGE_LOG §17。

## 复现

测试的精确命令在 pytest_*.json；也可直接使用 CP1_REPORT 的三个完整 pytest 命令。当前证据不可覆盖，CLI 重放需在同层创建新的证据目录；以下目录名必须未存在：

```bash
cd /home/zhao/SmartContract/ge-sc-llm-compile
mkdir compile_repair/artifacts/cp1_1_replay_v1
cp compile_repair/artifacts/cp1_1_v1/run_cli_acceptance.py compile_repair/artifacts/cp1_1_v1/baseline.json compile_repair/artifacts/cp1_1_replay_v1/
env PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64 /home/zhao/miniconda3/envs/compile-repair-production/bin/python -B compile_repair/artifacts/cp1_1_replay_v1/run_cli_acceptance.py
```

脚本会生成新目录下的 out/out2，确保前缀兄弟关系真实成立，并分别用仓库根、/、out 作为 cwd。代码提交号与逐文件 SHA 由每个新 case 的 seal 记录；不使用旧报告数字代替新运行。此命令仅为复现说明，本轮未额外执行重放。

## 停止边界

CP1.1 验收完成后按记录规则本地提交，等待独立审查；CP2 未执行，不自动 push。|| pragma 和 Slither 进程内无超时仍留 CP3，D19 未改。提交前冻结/doc_check/暂存检查的最终收据与结论见 CHANGE_LOG §17.5。


无损交付归档补记（修改 AI：Codex）：首次暂存清单 123 文件，内容 SHA 检查通过，但 git diff --cached --check 返回 2：三个精确 0.4.10 case 的 pragma_overridden.sol 第 3 行是按方案要求生成的等长空格，触发行尾空白检查。该空格不能删除，否则会改变字节偏移与既有 case seal。沿用 CP1 的交付方式，把九组 CLI 输出的 84 个文件无损打包为 cli_cases.tar.gz，逐成员 SHA256/长度回读 84/84 一致；原文件和九个 case seal 在本地保留不改。未放宽 Git 检查，未重新运行 CLI，未修改生产存储格式。

CLI 归档 SHA256 为 bec8f18cdc4510bf066d4bf79abe4489ab8d70c8c8e61a263b60ee63f1cf844b，大小 95,681 字节，archive_audit.json 保存成员清单。前文 cwd/out2/* 路径现在表示归档内成员，替代此前“按原目录提交”的交付说明。首次 seal.json、file_inventory.json、final_validation.json 均保留原字节，作为归档前阶段快照；当时的六份文档保存于 prepackaging_documents.tar.gz，与初版文档哈希完全一致。最终交付以 delivery_seal.json、delivery_inventory.json 为准，它们绑定最终文档及两个压缩包；不得将初版快照误当最终提交清单。失败现场为 staging_failure.json，当前原始目录只留本地，不删除、不提交重复副本。

归档说明纳入 CP1_REPORT、PROGRESS、CHANGE_LOG §17.5、HANDOVER 和本批次 README；追加记录遵守历史字节边界。doc_check_v1/v2 均已 6/6 通过，归档补记后按相同六目标再检查并保存新收据，完成后重新核对精确暂存范围和格式，再本地提交；编译、测试与 CLI 的已通过结果保持。
