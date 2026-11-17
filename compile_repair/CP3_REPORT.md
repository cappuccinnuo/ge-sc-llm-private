# CP3：前置核查与资料获取请求（未完成）

2026-11-17（EST），修改 AI：Codex。依据 PROMPTS r2.13 §4.1、§4.5。起始分支 compile-repair，HEAD=0d39c3546dbb8d456ef7c2fd5534143dcef92c94；git pull --ff-only origin compile-repair 返回 Already up to date。当前状态：pending_user_authorization，停在 §4.5 第 0、1 节的资料获取授权门槛；本报告不表示 CP3 已实现或通过。

## 实现

本轮只完成资料可用性核查和具体获取请求，未改生产代码或测试。新增批次为 artifacts/cp3_preflight_v1，核心文件为 authorization_request.json、remote_metadata.json、local_availability.json、baseline.json、runtime.json、development_issues.json、run_checks.py、runner_provenance.json、verify_preflight.py、README.md 及测试/审计收据。新报告为本文件，修改的既有文档仅 docs/CHANGE_LOG.md、docs/HANDOVER.md、PROGRESS.md；完整交付路径与 SHA256 见 delivery_inventory.json。

既有 CP0–CP2.4 产物、CP2_REPORT、PROMPTS、DECISIONS、生产文件、测试文件、scripts、原作者代码、原语料和根目录记录均受保护。run_checks.py 复制自 cp2_4_v1/run_checks.py，只替换批次标题和临时目录前缀，原文件 SHA256 见 runner_provenance.json；未复制或修改冻结生产函数。非测试生产文件数保持 14，分层实现未变。

读取顺序先共享上下文，再最新方案、当前交接/决策/变更与 CP2.4 审查。旧 r2.12 全文与当前 r2.13 的完整差异、当前 CP3 全节共同覆盖更新内容。目标仍是未来检测时任意合约，未把 MANDO 或外部语料的频率变成分类收录门槛。

## 真实验收

| CP3 项目 | 预期 | 本轮实际 | 状态 |
|---|---|---|---|
| §0 官方依据 | 逐条阅读 Error types、四次 breaking changes、导入与布局文档 | 本地约定位置未找到；已列 10 份固定标签/提交/路径 | 等用户授权，正文未下载 |
| §0 分类表、分类器和逐类测试 | taxonomy.json、toolchain/solc.py 与夹具覆盖 | 未创建、未实现、未运行 | 未验收 |
| §1 语料获取 | 三个固定提交、逐文件 SHA256、复核旧统计 | 精确获取请求已保存；只有元数据计数 | 等用户授权 |
| §2 三文件四版本前提探针及编译单元 | combined-json 与生产 Slither 参数一致、D3 完整 | 未运行；project.py 尚未创建 | 未验收 |
| §3 失败/包导入/相对缺失统计 | 只跑步骤 1、6 后按分类表统计 | 未运行 | 未验收 |
| §4 重复定义/许可/pragma、codegen 前提 | 已安装编译器与手写夹具实测 | 未运行 | 未验收 |
| §5 规则/代理判断和 CP4 算子 | 以文档和机械验证为依据 | 未编制 | 未验收 |

获取请求合计三套语料 235,835,756 字节（约 224.91 MiB），官方文档 10 份/188,817 字节；来源是远端 Git tree 的未压缩 blob 大小，不代表实测网络流量。语料保存到仓库外 /home/zhao/SmartContract/corpora/<名称>@<完整提交>；文档保存到同根下 solidity-docs@<固定标签>/docs。完整来源、固定提交、各文件路径和文档 blob SHA1 见 authorization_request.json。

元数据验证 DAppSCAN contracts 子树有 608 个项目目录、21,457 个 .sol，Trace 有 on-chain 5,000、repo-level 83 个项目/3,092 个 .sol、CVEs 15；与 cr_pre_v2 的结构计数一致。SOChecker 的 evaluation/RQ1 下有四个 JSON，input 数量 897 与 Solidity 判定数 656 仍仅是历史待核对值，未验证。尚未读取语料内容，未验证逐文件 SHA256、import 统计或 pragma 分布。

## 测试与开发记录

共享上下文要求中途停止也运行既有测试，三轮各运行一次且 rc=0，无失败后重试。依据 test_acceptance.json、pytest_*.json、pytest_*.log.gz：

| 环境与目标 | 实际结果 | 驱动计时 |
|---|---|---:|
| production，compile_repair/tests | 622 passed、6 skipped | 71.10 秒 |
| mando，compile_repair/tests | 181 passed、447 skipped | 20.86 秒 |
| mando，scripts/DFG/dfg_v2/tests | 2653 passed、9 个既有 warnings | 154.89 秒 |

跳过是既有环境边界：production 下 6 个要求 Python 3.7 或 regression_6c 的检查；mando 下 446 个要求 production、1 个要求标准库 metadata 的检查。测试结果不替代 CP3 新功能验收，也未触发全量生产或 6c 重放。

开发问题与处理见 development_issues.json：DAppSCAN 整仓目录响应截断后，改查固定 contracts 子树并确认完整；官方仓库旧 URL 返回迁移提示后，通过 repository id=40892817 确认 argotorg/solidity 为同一仓库。一次调试输出过长，仅影响显示，之后改用聚合字段与正确的符号链接模式判断；未用截断或错误聚合结果写入正式请求。没有代码缺陷修复或方案替换。

## 归档与复现

新批次仅 cp3_preflight_v1，拒绝覆盖历史批次。baseline.json 保存起始跟踪文件 SHA256、354 个 _code_refs、14 个生产文件、96 个本地编译器文件、两套环境元数据和旧 seal 索引身份；本次未执行新的 CP3 编译探针，因此不存在 CP3 新探针的版本选择或 D3 结论。

runtime.json 现场核对 production 为 Python 3.10.21 / Slither 0.11.6 / crytic-compile 0.4.2；mando 为 Python 3.7.12 / Slither 0.8.0 / crytic-compile 0.2.4。两环境均使用已有 solc-select 1.0.4、tree-sitter 0.20.4、pytest 7.4.4、pycryptodome 3.20.0，未安装或升级。

以下为已运行命令的结构，完整可复用 argv（含每轮不同的 basetemp）在 pytest_*.json：

~~~bash
cd /home/zhao/SmartContract/ge-sc-llm-compile
export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
/home/zhao/miniconda3/envs/compile-repair-production/bin/python -B -m pytest -q -ra -x -p no:cacheprovider compile_repair/tests
/home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -ra -x -p no:cacheprovider compile_repair/tests
/home/zhao/miniconda3/envs/mando/bin/python -B -m pytest -q -ra -x -p no:cacheprovider scripts/DFG/dfg_v2/tests
~~~

重跑须使用新批次与新的 /tmp basetemp，不能覆盖本轮收据。evidence_seal.json 封存新批次文件，seal 本身的 SHA256 记录在 delivery_inventory.json；文档检查与冻结审计在提交前执行，结果另行补记。

## 停止位置与后续边界

已停止在 PROMPTS §4.5 第 0、1 节明确规定的下载授权处。当前没有 authorization.json，authorization_request.json 的 status=pending_user_authorization 不能解释为批准。旧 solc/环境下载授权未扩展到文档或语料；DECISIONS 的已定/待定状态没有变化，本轮不修改该文件。

请求用户批准所列 10 份官方文档与三套固定提交指定目录，费用上限 0 美元，语料仅用于本地研究与只读编译分类。三仓根目录元数据未列出 LICENSE，按方案把使用范围交给用户确认。批准后先保存用户原话、日期、范围和请求 SHA256，再获取、逐文件验证、核对历史内容统计，然后继续 CP3 原定顺序；如身份/计数不符或需要新增资料则停下报告。

尚未提出新的方案替换。已知 || pragma 与 Slither 进程内无超时保留后续统计/建议边界；批量运行尚无用户指定时长上限，必要时先给出估时依据，不自行抽样或伪造授权。没有安装、文档正文/语料下载、LLM API、HGT 训练、GPU 锁操作、全局 solc 切换或 push。CP3 未完成，CP4 前提未满足。


前置终审补记（Codex）：doc_check v1 的五份文档全部通过，冻结审计通过；28,750 个保护跟踪文件与 25,828 个旧封存文件均无变化，354 个 DFG 引用、96 个编译器文件、两套环境元数据和 14 个生产文件全同。三份历史文档前缀保留。补记后的 doc_check v2 收据记录最终文档 SHA256，通过后才本地提交；本次通过的是前置检查点，CP3 实现/验收状态仍为未完成。
