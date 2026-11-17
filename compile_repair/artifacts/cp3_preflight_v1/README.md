# CP3 前置核查与获取请求（修改 AI：Codex）

日期：2026-11-17（America/New_York，EST）。依据：PROMPTS r2.13 §4.1、§4.5；起始 HEAD 为 0d39c3546dbb8d456ef7c2fd5534143dcef92c94，pull --ff-only 返回 Already up to date。

本批次是 CP3 的资料获取前置检查点，**不是 CP3 实现或验收完成**。状态为 pending_user_authorization。authorization_request.json 是请求，不能用作已批准的 authorization.json。

## 待批准的获取范围

| 语料 | 固定提交 | 仅获取的路径 | 未压缩字节估计 |
|---|---|---|---:|
| DAppSCAN | 66a56619c44770e05c2db600fa6468115ff0dcd5 | DAppSCAN-source/contracts/ | 109,776,516 |
| SOChecker | 5e56d7542ac1f4d81004d05b9375c7042a506b0c | evaluation/RQ1/ 下四个 JSON | 3,762,624 |
| Trace | 4260215b5330293db7739d9fadeecf014ef97816 | datasets/ | 122,296,616 |

合计 235,835,756 字节（约 224.91 MiB）。这些数字来自固定提交的 GitHub Git tree 元数据，见 remote_metadata.json；不是实测网络流量，不含 Git 元数据、文件系统块及传输开销。三套语料均保存到仓库外 /home/zhao/SmartContract/corpora/<名称>@<完整提交>。获取使用现有 Git 的限定目录部分获取或固定提交的逐文件读取，不自动退化为整仓下载，不获取缺失依赖或子模块。

SOChecker 的四个文件为 gpt-3.5-turbo.json、gpt-4.json、ours+GPT.json、ours.json。仅 input 字段用于后续分类，以既有 cr_pre_v2 的 ours.json 897 条为核对目标；其余三份核对 input 集合一致性，发现不同先报告，不自行合并或去重。

三个固定提交的根目录元数据均未列出 LICENSE，cr_pre_v2 也记录无仓库 LICENSE。该事实不代表所有嵌入源码均无单独许可。本请求建议的使用范围仅为本地研究、只读编译分类，不提交或再分发原语料，由用户批准使用范围。

| 官方文档标签 | 文件路径 |
|---|---|
| v0.4.12 | docs/using-the-compiler.rst；docs/layout-of-source-files.rst |
| v0.5.0 | docs/050-breaking-changes.rst |
| v0.6.0 | docs/060-breaking-changes.rst |
| v0.7.0 | docs/070-breaking-changes.rst |
| v0.7.6 | docs/using-the-compiler.rst |
| v0.8.0 | docs/080-breaking-changes.rst |
| v0.8.38 | docs/using-the-compiler.rst；docs/path-resolution.rst；docs/layout-of-source-files.rst |

共 10 份、188,817 字节（约 184.39 KiB），用于错误类型、四次 breaking changes、导入/remapping、源码布局与版本边界的文档依据。每个标签解析到的完整 commit、文件 blob SHA1、下载 URL 和仓库外保存路径均在 authorization_request.json；文件 SHA256 在批准获取后计算。旧 ethereum/solidity API 返回迁移提示，已核对 repository id=40892817 对应 argotorg/solidity，仍为同一官方仓库，见 remote_metadata.json。

费用上限为 0 美元。本请求只涉及所列资料获取；不授权安装或升级软件、编译器或依赖库，也不授权 LLM 调用。获准后先将用户原话、日期、范围和本请求 SHA256 写入新执行批次的 authorization.json，再获取与逐文件校验；当前尚未创建该授权。

## 已做与未做

已同步分支、读取更新方案和交接/审查证据，核对仓库与约定本地位置，读取远端仓库身份、树和 tag/ref 元数据以形成可审核清单。未读取外部源码或官方文档正文。DAppSCAN 整仓递归树被截断，已改查完整的 contracts 子树，不使用截断结果计算最终数量。

元数据层面核得 DAppSCAN 608 个项目目录、21,457 个 .sol；Trace on-chain 5,000、repo-level 83 个项目/3,092 个 .sol、CVEs 15，均与 cr_pre_v2 的目录计数一致。源码 SHA256、SOChecker input 数量、import 和 pragma 分布尚未核验。未创建 taxonomy.json、分类器、项目闭包实现或 CP3 探针，未执行语料分类或修复。

## 证据与复现

- authorization_request.json：待批准的精确范围、来源、版本、大小、路径、用途与费用。
- remote_metadata.json、local_availability.json：远端元数据摘要、限定范围本地可用性核查；不声称全盘扫描。
- baseline.json、runtime.json：起始跟踪文件、354 个 DFG 引用、14 个生产文件、96 个编译器文件与两套环境的身份。
- run_checks.py、runner_provenance.json：从 cp2_4_v1 复制的证据驱动，只改标题和临时目录前缀；不导入审查脚本。
- pytest_*.json、pytest_*.log.gz、test_evidence_*.json.gz、test_acceptance.json：本轮既有测试收据；不能替代 CP3 新功能验收。
- verify_preflight.py、frozen_audit.json、doc_check*：完整性和五份文档的检查。
- evidence_seal.json、delivery_inventory.json：新批次内容封存与精确交付清单。

从仓库根使用已存在的对应环境运行 python -B -m pytest -q -ra -x -p no:cacheprovider，目标为 compile_repair/tests 或 scripts/DFG/dfg_v2/tests；完整 argv、独立 /tmp basetemp、环境变量和退出码在 pytest_*.json。复查已有批次应只读收据；如需重新执行证据驱动，先使用新的输出批次，不能覆盖本批次。

## 停止依据

PROMPTS §4.5 第 0 节原文：“文档需要下载时，列出版本标签与路径写入 authorization 请求后停下。”第 1 节要求列出语料、仓库、提交、预计大小与存放路径后同样停下等用户授权。因此当前停止下载依赖工作；继续实施须先取得本清单授权。历史 solc/环境授权未扩大使用。CP3 批量运行的时长上限尚未由用户给出，本请求不虚构该上限；必要时在资料核验与规定探针之后提出有估时依据的运行请求。
