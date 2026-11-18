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


## CP3 续：授权获取、初始分类表与结构核验停止（未完成）

2026-11-17（EST），修改 AI：Codex。本节追加于前置检查点之后，不改前文历史。起点 compile-repair@88b499e714883066b3bc1379f42a5a89ce8ba1d6；这是同一 CP3 任务在收到下载许可后的继续，前置 pull 已完成。用户原话“批准全部资料，仅本地研究使用（推荐）”先写入 artifacts/cp3_v1/authorization.json（SHA256 f42f045ba9c235674cc3fea3a4b42a7d28945daaf56b1b43ba9ae8aef869a87a），再开始获取。当前状态 stopped_on_structure_mismatch，不能把本节作为 CP3 完成结论。

### 实现与范围

新增 artifacts/cp3_v1 的授权、获取驱动、逐文件哈希清单、分类表初稿、结构核对、三文件前提探针、停止审查请求及校验收据。新增 tests/fixtures/cp3_project/Main.sol、sub/Base.sol、vendor/Numbers.sol；未创建 project.py，未改 toolchain/solc.py、pipeline 或 Slither，生产文件保持 14。DECISIONS 记录下载授权，HANDOVER 更新 §0–5 并追加历史；CHANGE_LOG §30 和 PROGRESS 记录本轮工作。完整文件和 SHA256 见 delivery_inventory.json。

10 份官方文档全部按固定标签解析出的提交、路径、Git blob SHA1 和大小核验，合计 188,817 字节。三套语料合计 29,611 文件、235,835,756 字节，逐文件 SHA256 与 Git blob 校验通过，均存仓库外；这些字节数是源文件大小，不是网络传输量。DAppSCAN 21,495 文件/109,776,516 字节，SOChecker 4/3,762,624，Trace 8,112/122,296,616。来源及全提交见 authorization.json、acquisition/*/receipt.json；未分发外部源码。

分类表先于语料内容统计建立；taxonomy_initial_receipt.json 记录 taxonomy.json 的 SHA256 7096c70be45debbbd671919674ee2afd63dc59e3bf08c969ed977353299832bb。包含 29 类，覆盖文档中的 13 种诊断类型和 PROMPTS 初始集合，并记录 125 个 breaking-change 条目（0.5:59、0.6:23、0.7:22、0.8:21）。每条有来源行、类型/模板、原因、修复候选、D3/D7 检查和可构造的 CP4 候选算子；这不是已实现规则。尚未实测的模板 verified_versions 为空，errorCode 不凭空填写。

### 初始分类表（文档依据，尚未完成逐类实测）

下表是 taxonomy.json 的类别层；125 条版本变化的逐条文档行号及映射保存在同一文件的 breaking_changes 和 breaking_change_coverage。官方 error_types 指 v0.7.6 using-the-compiler 的 Error types；imports 指 v0.8.38 path-resolution；layout 指 v0.8.38 layout-of-source-files；old_imports 指 v0.4.12 layout-of-source-files；cp3 指 PROMPTS §4.5 与已定决定。所有候选均须通过 D3，并执行 D7 的原字节前提、逐文件等级、错误行限制及节点来源标记，不能仅凭编译通过宣称语义等价。

| 类别 | 类型与消息模板 | 原因 | 候选修复与等级 | 来源 |
|---|---|---|---|---|
| unresolved_package_import | IOError, ParserError; Source <path> not found | Package is absent or no supplied mapping resolves its source-unit name. | deterministic: authorized offline package and version match; otherwise agent after dependency evidence; additive | error_types, cp3, imports, old_imports |
| missing_relative_file | IOError, ParserError; Source <path> not found | Relative import target is absent from the approved project. | deterministic only with an unambiguous identity-checked existing dependency; otherwise agent; additive | error_types, cp3, imports, old_imports |
| undeclared_identifier | DeclarationError; Undeclared identifier / Identifier not found | A referenced declaration or scope is missing. | deterministic declaration-only stub when its complete type is constrained; otherwise agent; additive | error_types, cp3 |
| missing_base_contract | DeclarationError; Identifier not found or not unique / Definition of base has to precede | A base declaration is absent, ambiguous, or ordered incorrectly. | deterministic proven declaration recovery; otherwise agent; additive | error_types, cp3 |
| duplicate_definition | DeclarationError; Identifier already declared / defined twice / same name and parameter types | Flattening or project assembly introduced competing declarations. | deterministic only for byte/token-identical declarations with preserved binding; otherwise agent; rewrite | error_types, cp3 |
| multiple_license_or_pragma | ParserError, SyntaxError; Multiple SPDX license identifiers / ABI coder has already been selected / experimental features | Repeated flattened directives may conflict; repeated Solidity constraints alone are not inherently invalid. | deterministic redundant identical directive removal only; conflicting licenses require human scope decision and conflicting versions require evidence; rewrite | error_types, cp3, layout |
| encoding | ParserError; Invalid character / Invalid escape / Invalid UTF-8 / unicode | Bytes or escapes are not legal at their lexical position; arbitrary comment bytes need not fail. | deterministic BOM or proven escape representation correction; otherwise agent; rewrite | error_types, cp3 |
| unbalanced_structure | ParserError; Expected token Semicolon got 'RBrace' / Expected ';' but got '}' / end of source | A required delimiter, statement terminator, or source tail is missing. | deterministic unique missing delimiter with no invented executable body; otherwise agent; additive | error_types, cp3 |
| parser_error_other | ParserError; Expected <token> but got <token> / Expected token | Grammar does not accept the token sequence. | deterministic documented local syntax migration where equivalent; otherwise agent; rewrite | error_types, cp3 |
| type_error_other | TypeError; not implicitly convertible / Invalid type / Wrong argument count / Member <name> not found | Declarations and expressions have incompatible types or arity. | deterministic mechanically equivalent type spelling or cast only; otherwise agent; rewrite | error_types, cp3 |
| codegen_only | CompilerError, UnimplementedFeatureError; Stack too deep / stack too deep / Unimplemented feature | Parsing/type checking succeeded but requested code generation cannot finish. | deterministic compiler settings only after matched solc and Slither D3 validation; otherwise tool limitation; none | error_types, cp3 |
| closure_version_conflict | SyntaxError; F: empty pragma interval | File constraints or their transitive intersection have no common compiler. | deterministic compatible original dependency retrieval only; otherwise agent with version evidence; additive | error_types, cp3, layout |
| slither_incomplete | ; solc rc0; Slither exception or D3(a/b) incomplete | Analysis cannot represent the compiler-accepted unit. | deterministic only for separately proven equivalent tuple-call case; otherwise tool limitation, no agent rewrite of legal source; rewrite_or_none | error_types, cp3 |
| other | ; unmatched compiler diagnostic | Observed diagnostic has no verified template yet. | unclassified: enumerate every normalized template, establish cause before routing; undetermined | error_types, cp3 |
| json_error | JSONError; Invalid JSON input / Unknown key / Invalid component | Malformed standard-JSON input; diagnostic probes only, not main compilation path. | deterministic repair of caller input, not Solidity source; none | error_types, cp3 |
| io_error | IOError; File not found / Permission denied / File outside of allowed directories | The compiler cannot read a requested source. | deterministic path/permission configuration within approved scope; no dependency download; none | error_types, cp3, imports, old_imports |
| docstring_error | DocstringParsingError; Documentation tag / Documented parameter / @return | NatSpec tags refer to absent or inconsistent declarations. | deterministic exact tag-name correction if binding is unique; otherwise agent; rewrite | error_types, cp3 |
| syntax_error | SyntaxError; outside of a for / not inside a loop / No visibility specified | Parsed construct violates a syntactic context restriction. | deterministic documented context correction only if behavior is preserved; otherwise agent; rewrite | error_types, cp3 |
| unimplemented_feature | UnimplementedFeatureError; Unimplemented feature / not yet supported / not implemented | Compiler feature is not implemented for this version or code-generation mode. | deterministic existing candidate/settings selection; otherwise tool limitation; none | error_types, cp3 |
| internal_compiler_error | InternalCompilerError; Internal compiler error / InternalCompilerError | Compiler implementation failed internally; source location may be absent. | tool limitation: retain compiler/version/diagnostic and try only existing permitted candidates; none | error_types, cp3 |
| compiler_exception | Exception; Exception / std::exception::what | Compiler exception with no stable more-specific diagnosis. | tool limitation; never infer a source repair from exception text alone; none | error_types, cp3 |
| fatal_error | FatalError; Fatal error / FatalError | Unhandled fatal compiler condition. | tool limitation; preserve crash evidence, no arbitrary source rewrite; none | error_types, cp3 |
| warning | Warning; Warning: <message> | Non-fatal diagnostic; not a failed compilation. | no repair required; none | error_types, cp3 |
| unsupported_disjunction | ; F: unsupported pragma expression; expression contains  /  /  | Frozen interval semantics do not represent a union. | later deterministic union of intervals with ordered attempts; CP3 classification only; none | error_types, cp3, layout |
| unsupported_expression | ; F: unsupported pragma expression | Malformed or unsupported version expression without a proven missing terminator. | agent when source malformed; tool limitation when legal expression unsupported; rewrite_or_none | error_types, cp3, layout |
| unterminated_pragma | ; F: unterminated pragma directive | A top-level Solidity pragma has no terminator before braces or EOF. | deterministic insertion only if unique; otherwise agent; additive | error_types, cp3, layout |
| pragma_missing_semicolon_candidate | ; F: unsupported pragma expression; expression includes directive keyword | The expression consumes a following import/pragma/contract/interface/library/abstract token. | deterministic unique semicolon insertion only after compiler validation; keep original expression evidence; additive | error_types, cp3, layout |
| slither_no_timeout | ; no completed API call | In-process Slither has no enforced timeout; absence of timeout records is not evidence of no hangs. | later subprocess isolation and explicit deadline; no implementation in CP3; none | error_types, cp3 |
| declaration_error | DeclarationError; Identifier <name> invalid or unavailable | A declaration violates a documented naming or binding rule. | deterministic declaration-only stub when its complete type is constrained; otherwise agent; additive | error_types, cp3 |

### 真实验收与停止位置

| 项目 | 实测 | 判定 |
|---|---|---|
| 官方文档身份与字节核验 | 10/10 | 通过 |
| 指定语料文件身份与字节核验 | 29,611/29,611 | 通过 |
| 三文件四版本前提 | 0.4.12、0.4.24、0.5.17、0.8.38 的 solc rc0、Slither 构造、D3(a/b) 与三文件映射覆盖均通过 | 4/4，通过 |
| DAppSCAN 历史结构 | summary、首个版本文本系列、import 前25项、608 项目明细逐项全同 | 通过 |
| Trace 历史结构 | on-chain 5,000；repo-level 83 项目/3,092 .sol；CVEs 15 | 通过 |
| SOChecker 四份 input 一致性 | 三份 897 条完全同序；ours+GPT.json 846 条，是其中严格子集，缺 51 条 | 不符合，停止 |
| 分类器与项目闭包生产实现、语料步骤1/6、各类统计及 §4 前提探针 | 未运行 | 未验收 |

SOChecker 无额外或重复 input；897 条的历史 contract/function 子串计数为 656，846 条对应为 621。这里只复核 cr_pre_v2 的文本口径，未把它当作新的 Solidity 判定规则，也没有用旧整文件 parse 产生 CP3 版本区间统计。51 条差异只保存 input SHA256，证据为 structure_acceptance.json 和 structure_review_request.json。

三文件探针以夹具目录为 cwd、Main.sol 为相对入口、@vendor/=vendor/ 为 remapping、--allow-paths . 为允许路径，采用既有 combined-json 输出项。CryticCompile 同时接收 solc_working_dir、solc_remaps、solc_args，参数一致；Slither 使用 production，记录可执行文件 SHA256、完整命令、rc、错误、耗时和费用。源码哈希未变，没有改全局编译器选择；该探针只证明前提，不替代项目闭包的通用实现验收。

### 问题处理、候选建议与剩余工作

初稿覆盖校验发现 0.6 文档中 fallback/receive 下的两个嵌套条目未列入，补齐后 125 条覆盖成立；尚未读取语料统计时完成，未改标准。读取不存在的 core/types.py 后按实际目录定位到 core/model.py；默认 WSL 调用受沙箱限制后采用既有授权 WSL 执行方式，未改网络配置。一次过长的统计文件显示被截断，正式核验采用 JSON 字段比较并保存完整结果，不依赖截断显示。详见 development_issues.json。

值得保留的边界：Warning 不导致编译失败，部分版本变化只影响运行语义或输出接口；初表将这些条目保留且明确区分。编译器内部错误不等于可修复的源码错误，Slither 工具限制不直接交给代理改写合法源码。所有修复候选仍需后续探针和 D3/D7 验证，未把语料频率用作覆盖门槛。

获批请求 after_approval 明确要求内容计数不符时保留并停止，PROMPTS §4.5.1 要求不一致时报告。建议继续采用原定 ours.json 的 897 条唯一输入，把 ours+GPT.json 登记为仅供来源核对的 846 条附属子集，不合并、不去重、不补数据。该核验假设的调整尚未批准；structure_review_request.json 给出具体范围，下载许可本身没有撤销，无须重下资料。

生产分类器、项目闭包、片段判定、语料编译与失败频率、冻结 parse 与新读取差异、0.6/0.7 格式切换、旧/新错误模板测试、tuple-call 复核、重复声明/许可/pragma、AST-only/codegen、CP4 最终算子全部仍未完成。|| 并集支持和 Slither 超时仍只登记缺口；本轮未增加新修复。没有 LLM、软件安装/升级、额外下载、6c 重放、HGT 训练、GPU 锁或 push，费用 0 美元。

### 测试、封存与复现

停止检查点按共享上下文运行两个环境的模块测试和 mando DFG v2；实际命令、rc、耗时、日志哈希见 pytest_*.json，结果在下方终审补记。命令为相应环境 python -B -m pytest -q -ra -x -p no:cacheprovider，目标 compile_repair/tests 或 scripts/DFG/dfg_v2/tests，独立 /tmp basetemp。所有新文档及追加段运行 doc_check，保护核验同时检查旧跟踪/封存文件、生产实现、354 个 code refs、96 个编译器文件与环境元数据。

本批次证据只追加，evidence_seal.json 和 delivery_inventory.json 封存后不可覆盖；后续执行使用新批次并只读复用初表/已获取资料。旧 CP3 前置报告状态仅表示当时历史，本节为最新状态。完成强制记录和校验后仅本地提交；CP3 仍未完成。


终审补记（2026-11-17，修改 AI：Codex）：本轮 production 622 passed/6 skipped（驱动79.93秒）、mando 181 passed/447 skipped（20.26秒）、DFG v2 2653 passed/9既有warnings（152.65秒），各执行一次且rc=0，见test_acceptance与pytest_*。首次汇总收据的数字正则转义错误只影响日志解析，改为读取已有末行的词项后正确汇总，未重跑测试、未改验收判据，详见development_issues。

六份doc_check v1全部通过。frozen_audit通过：28,779个保护跟踪文件、25,828个旧封存文件无变化；354个code refs、96个编译器文件、production/mando的145/118份环境元数据、14个生产文件均保持；29,611语料文件与10份文档复核无变化。五份既有文档的历史字节段保持。补记后的doc_check v2记录最终文档SHA256，通过后按delivery_inventory精确本地提交；结构核验差异仍未解决，CP3仍未完成，不将该项改记为通过。


交付补记（2026-11-17，修改 AI：Codex）：暂存后的 git diff --cached --check 报告三份 Git init 原始 stderr 的提示行尾空格，以及 solc 0.8.38 原始 stderr 的末尾空行。为保持取证原字节，未修改四份日志或已封存 cp3_v1；仅将这四个精确日志路径排除后，其余全部文件的同一空白检查通过。该处理不排除代码、文档或任何CP3验收项；SOChecker的结构差异仍为未通过。

另建 artifacts/cp3_delivery_v1 保存原始报错、四日志SHA、检查命令和上次doc_check对应的文档快照。最终文档检查与提交清单改以该交付批次的 doc_check_final_invocation.json、delivery_inventory.json 为准；cp3_v1/evidence_seal.json 原样保留。没有重跑编译或测试，也没有改变生产实现、授权范围或待确认建议；本地检查点提交后仍等待对846/897子集差异的处理确认。


交付终检补记（修改 AI：Codex）：七份 doc_check_delivery_v1 全部通过；本条补记后再次检查的最终文档哈希见 cp3_delivery_v1/doc_check_final_invocation.json。四份原始工具日志按精确路径保留并豁免空白检查，其余文件检查通过；编译验收和 SOChecker 待确认状态均未改变。

## CP3 续做：诊断与项目管线、同名类型绑定缺口（2026-11-17，修改 AI：Codex）

### 任务、授权和当前结论

本轮承接 compile-repair@dc6c5fb44041e1023daef1bfd7d9760f534c7f0a，执行 PROMPTS r2.13 §4.1、§4.5。原文已在同一任务前段完整阅读，旧 CP3 前置、获取与交付批次只读。用户先批准继续使用 ours.json 的 897 条 input，后批准项目图增加文件名 + key5；两个决定分别写入 cp3_continue_v1/authorization.json、project_identity_authorization.json，均绑定请求 SHA、原话、日期及范围。

CP3 尚未完成。诊断、项目闭包、统一管线、手写探针和部分语料运行已完成；追加的调用图测试证明原生 Slither 存在现有 D3 检不出的同名合约类型错绑，全量已暂停。新增接受条件尚待用户批准，不改装 Slither、不改写合法源码，不把失败测试转成通过。

### 实施方式

分类规则在 toolchain/solc.py：以实际 combined-json stderr 为主，保留无位置诊断，区分旧式位置与箭头位置、Error 与可观测类型。类型模板取文档和匹配的 standard JSON 辅助探针，未把 Error 猜成具体类型；源码字节和错误位置只用于分类。对 ||、无法解析表达式、未结束 pragma、文件/闭包空交集、缺分号吞入后续指令分别记录。未改变 pragma_interval 或任何选版规则。

toolchain/project.py 只读解析传递导入；不同源码单元名与物理文件分别记录，缺失包、相对文件、外部路径、符号链接或不支持的转义均显式记录，不补依赖。每个项目复用文件清单，所有副本保持相对路径。solc 与 Slither 共用入口、cwd、remaps、--allow-paths .，D3 检查闭包所有文件。已封存的三文件四版本前提探针只读复用，新增集成测试验证代码实现而非重做旧证据。

pipeline.py 的同一个 repair_unit 负责文件、片段和项目，共用 CP1 的候选顺序、设置重试与 pragma 工作副本规则。每个文件独立 provenance；项目图节点、边和调用用相对文件名区分原 key5，单文件默认输出保持。cli.py 接受项目目录和显式 --remapping。survey.py 按注释/字符串外的 pragma、contract/interface/library 或 function 片段判定 Solidity 候选；evaluation/report.py 统计单位是单元，多个诊断/版本不会重复增加同类单元数，多类别占比可以合计超过 100%。

生产模块 16 个，新增仅为目录表中的 project.py 与 evaluation/report.py；旧实现只改 solc.py、slither.py、pipeline.py、cli.py、survey.py。测试新增 test_diagnostics.py、test_project.py、test_cp3_report.py，以及 cp3_diagnostics、cp3_alias、cp3_alias_calls 手写夹具；旧测试只调整目录输入预期、搬迁模块清单和五个新增负向 pragma 夹具的显式清单。未修改 rules/environment.py、core、原作者代码或 scripts。

### 与语料无关的探针和分类表

初表保留 29 类、125 条 breaking changes；新 taxonomy_verified.json 增加 30 个观察模板和精确已测版本集合，未删除零观察类别。完整调用与原始输出见 diagnostic_invocations.jsonl、diagnostics/、codegen_invocations.jsonl、codegen/。每个模板的 standard JSON type/errorCode 仅在消息相符时关联，旧 standard JSON 的内部错误不冒充 CLI 错误类型。

| 实测项目 | 结果 | 证据 |
|---|---|---|
| stderr 格式 | 92 版均测；0.6.0 首次使用现代位置格式 | diagnostic_probe_acceptance、taxonomy_verified |
| 缺分号措辞 | 0.4.12–0.4.23 为 Expected token Semicolon；0.4.24 起为 Expected ';' | 同上 |
| 相同 contract 重复 | 92/92 拒绝 | duplicate_contract 行 |
| 相同 Solidity pragma 重复 | 92/92 接受 | duplicate_pragma 行 |
| 两个相同 SPDX MIT 标识 | 0.4.12–0.8.7 接受；0.8.8–0.8.38 拒绝 | duplicate_license 行 |
| 继承中的相同 event | 所测 0.4/0.5/0.6 接受，0.7/0.8 拒绝；不是全补丁边界证明 | duplicate_event 行 |
| tuple call | 0.4.12 原文 solc 失败；0.4.24/.26 原文 solc rc0、Slither AssertionError；等价手写形式三版均 D3 通过 | 6 组 tuple 前提 |
| Stack too deep | 0.8.38 的 via-ir + optimizer D3 通过；仅 optimizer 或仅 via-ir 未通过该夹具 | codegen_probe_summary |
| AST-only | 所测旧系列仅请求 AST 仍报 codegen 错误；0.8.38 AST 生成成功，当前原生构造调用未得到 Slither D3 | codegen_probe_summary |

诊断矩阵包含 548 次 combined-json、84 次仅诊断用途 standard JSON；tuple 另有 6 次 solc 和 5 次 Slither。codegen 探针另为 12 次 compiler、2 次 Slither。内部错误、Exception、Fatal 等不能可靠由源码变异制造的类型，以明确标识的合成接口诊断测试覆盖，不声称已触发真实编译器崩溃。|| 与 Slither 无超时仍为后续候选，未实施；codegen 设置与 tuple 改写也没有加入自动修复。

### 全部输入与部分运行

unit_inventory_summary.json 核对 29,611 个取得文件的 SHA。原始单元 31,307 个：DAppSCAN 21,457；Trace repo-level 3,092；on-chain 5,000；CVEs 15；SOChecker 897；MANDO 846。DAppSCAN 608 个项目根、Trace 83 个；更深一层 DAppSCAN 目录数 682 不属于冻结项目口径。

SOChecker 的 661 条有词法 Solidity 声明证据，236 条无此证据单列，故完整运行序列为 31,071 条。判定保留不完整函数和声明，不以编译成功作为语言筛选；与其他语言共享的 function 语法仍可能有歧义。未合并、去重或补入附属 846 条 input。

首段 120 条用 47.744 秒完成并正常封存；按六语料分别加权估计全量约 2.415 小时，不是保证或时限。用户未设时限，因此按完整序列继续，没有自行抽样。第二段完成 752 条后因独立测试失败受控 SIGINT，rc=-2、304.657 秒；另有 SOChecker cp3_30208 留下 9 条已记录调用，不能计为完成。现场 200,545,035 字节由 interrupted_segment_preservation.json 保留哈希；未伪造正常 pipeline seal。

已完成 872 条的 provisional 分类有 599 个旧 D3 成功、273 个剩余失败，11900 次完整单元 solc 调用、599 次 Slither 调用；包括中断单元时已记录 solc 为 11909。冻结 parse 失败而新 interval 读取成功的完整单元为 92。逐类数量、占比、语料分布、最多三个 SHA 示例、7 个 other 模板、包名/导入路径、相对路径候选 none=11、unique=5、multiple=2，见 partial_failure_summary.json。导入次数按单元内 importer/位置/路径去重，闭包重叠的不同单元仍分别计数。

上述数字仅为暂停前证据，不能解释为抽样终验、全量成功率或已验证调用图语义。599 次完成 Slither 调用未观察到挂起，但进程内没有自动期限，不能据此声称解决了超时缺口。外部源码、工作副本、图和原始批量 stderr 留在仓库外 compile-repair-local/cp3_continue_v1，Git 仅保存身份、哈希和统计。

### 已批准差异与新的实质问题

原 D4 在合法的两个文件 C.f() 上产生相同 key5。project_identity_probe.json 记录 solc rc0、D3(a/b) 通过而 graph_facts 抛 Duplicate graph key5；用户批准相对文件名作为外层身份后，两个声明的节点和 CFG 均保留，不去重。这个扩展已实施，并保留原单文件格式。

随后跨文件调用测试发现更深一层问题。alias_call_probe.json 独立调用原生 CryticCompile/Slither，确认 solc AST 中 a 引用 A.sol 的 ContractDefinition id 37，b 引用 B.sol 的 id 48，而 Slither 把二者类型及调用目标都绑定 A.sol。原生对象已错绑，序列化没有自行改写目标；旧 D3(a/b) 仍为 true。已安装 Slither 的 type_parsing.py 中按合约名取首个匹配对象的实现是相关代码证据，文件 SHA 保存在请求中，未修改安装目录。

待确认方案见 alias_binding_review_request.json：仅项目增加 AST 与 Slither 直接合约类型声明绑定的一致性接受检查，保留 D3 原始测量；不一致或不能验证时拒绝该次可用图输出，归为工具限制，不交给代理改写合法源码。此方案增加现有 D3 之外的条件，超出文件名 + key5 授权；已询问，尚未实施。原测试 1 failed 保留，不改为通过或跳过，全量不自动重试。

D6 与 CP4 的文档候选仍保留在 taxonomy_verified 中：有明确语法/身份和可机械验证边界者是确定性候选，其余为代理或工具限制；所有 constructible 类别保留破坏算子，即使当前频率为零。不能把重复许可证、未知类型桩、补括号和编译器崩溃笼统视为安全可改写。绑定问题解决后的最终分类、全量统计和完整 CP3 结论仍未完成。

### 问题修正、验收与交付边界

定向测试先发现测试中误把 Missing 基类写为 Absent，修正引用；类型错误含 expected type 时被过宽 parser 模板匹配，改为行首 Expected/Unexpected；UTF-8 导入名使用明确解码，不支持的转义保留原因。旧搬迁测试有两处 14 文件假设，更新为 16 文件并比较封存中的实际清单；旧 CP2.4 等价测试新增五个明确负向夹具，846 个 MANDO 及所有可读夹具仍逐字段比较。所有失败收据保持，不覆盖、不虚报为通过。

tests_targeted_v2 为 110 passed；完整 production v4 为 714 passed/6 skipped（69.246 秒），mando v1 为 268 passed/452 skipped（22.342 秒），冻结 DFG v2 为 2653 passed/9 既有 warnings（164.070 秒）。随后项目补充验收为 24 passed/1 failed，失败正是当前待处理的类型绑定问题，因此先前完整测试通过不代表当前全部验收通过。

本轮无下载、安装、升级、LLM、HGT、GPU 锁或 push，0 美元。模块、交接、运行/训练改变和决策记录已补充；最终 doc_check 与范围核验的实际结果在后续补记与收据中登记。PROMPTS §4.1 要求影响方案时停止并要求全部通过后提交；目前保留未提交的具体代码、测试和证据，不满足提交条件，CP3 未标记完成。


交付检查补记（2026-11-17，修改 AI：Codex）：六份 doc_check_v1 全部通过；frozen_audit 检查28,908份保护跟踪文件、25,828份旧封存文件、354项code refs、96份编译器文件、production/mando的145/118份环境元数据、29,611份语料和10份文档，均未变化。生产文件16个，历史文档字节段保留。tracked git diff --check通过，新增代码/文档无空白问题；仅322份逐一列明且SHA固定的原始工具输出保留其原空白，见whitespace_review，不豁免代码或验收项。本条追加后的最终doc_check收据为doc_check_final_invocation.json。上述记录和范围检查不代表新增绑定测试通过；24passed/1failed与待确认状态保持，本批次未提交、未push。


测量边界补记（修改 AI：Codex）：另有三次交互式诊断检查和一次初始项目 smoke check 未保留完整逐调用耗时/输出哈希；exploratory_observations.json 明确以 null 标示缺项，不混入正式548/84诊断矩阵及前提验收计数。development_issues.json登记了全部实质问题与解决或停止方法。新增绑定检查仍待确认，失败测试状态未变。


## CP3 绑定检查批准与恢复进展（2026-11-17，修改 AI：Codex）

用户已批准“批准项目图绑定检查（推荐）”，之前待确认问题现已解决，原pending记录保持历史原文。授权请求SHA、代码前快照与旧762成员核验在cp3_binding_v1。生产只增加项目直接合约类型绑定检查及pipeline/report配套；D3事实不变，graph_usable额外控制图输出/成功状态。AST引用ID与原生文件/字节位置不一致或无法核验时记工具限制；不改Slither包或合法源码。

原失败测试按批准的门槛改为精确拒绝：D3(a/b)仍true，b预期B.sol而原生A.sol，不写graph.json。四版本正常项目七条类型变量声明与两文件调用通过。定向32passed；production723passed/6skipped；mando271passed/458skipped；DFG2653passed/9既有warnings。receipt及binding_rejection_acceptance保存具体依据。

原两段4,716文件校验后，529条单文件复用，343条项目新批次复验230成功/113未修复，状态/版本/设置/flags与原一致。现已继续原完整序列剩余30,199条，当前时间点计数见progress_checkpoint_v1（动态进展，不是最终统计）。旧中断9次编译与原现场保持，不假称原段完成。最终完整统计、D6/CP4清单及所有检查后才提交；本轮未提交、未push。

统计复核发现单文件CLI缺包诊断没有project-assembly的package/path字段；最终报告只读补计已经保存的定位诊断和源码，不改变原分类或重跑编译。12个现有单元核验通过，见import_statistics_validation。具体实施、问题处理与已批准偏离见CHANGE_LOG §32、DECISIONS、development_issues。当前仍有||区间和Slither无超时等后续缺口；CP3没有实现CP4–CP6规则。

## CP3 绑定检查获批后的完整分类（修改 AI：Codex）

### 范围、批准与方法

2026-11-17用户批准“批准项目图绑定检查（推荐）”；authorization.json绑定原request SHA。先验证旧检查点762成员及seal；所有新证据写cp3_binding_v1。此前source差异与文件名+key5批准仍有效。原D3(a/b)、单文件和6c路径保持；项目graph_usable必须额外通过直接合约类型绑定检查。检查使用编译单元内AST引用ID与原生对象文件/偏移，不按同名猜测目标；无法核验即拒绝该次图。没有修改安装包、合法源文件或版本策略。

### 全量结果

完整清单31,307条，其中SOChecker236条无Solidity声明证据单列；进入固定完整序列31,071条，成功21150、剩余失败9921。529个单文件观察复用，343个旧项目以新批次结果替换，再完成30,199条续跑；每单元只计一次，无抽样。

| 语料 | 单元 | 成功 | 剩余失败 |
|---|---:|---:|---:|
| DAppSCAN | 21457 | 13566 | 7891 |
| MANDO | 846 | 843 | 3 |
| SOChecker | 661 | 96 | 565 |
| Trace_CVEs | 15 | 14 | 1 |
| Trace_on_chain | 5000 | 4565 | 435 |
| Trace_repo | 3092 | 2066 | 1026 |

有效结果对应solc调用115771次、Slither调用21298次；原中断9次编译与被替换的旧项目335次编译/230次Slither不计入有效结果调用数，原始记录保留。旧整文件parse失败而新pragma读取成功1012个单元；unsupported_disjunction为1个。项目Slither调用15771次，直接合约类型绑定核对34973条；D3为true但绑定检查拒绝的调用0次。

原始语料、工作副本、stderr、AST相关事实和图保存在仓库外。本批次result_provenance逐单元绑定原/新result SHA与批次seal，final_aggregate先逐成员验证再汇总。单位是每个.sol入口及其闭包，闭包可以重叠；成功指满足当前全部接受条件，不表示合约安全，也不是所有Slither语义正确性的证明。

### 剩余失败分类

分母为全部剩余失败单元；同一单元可有多个类别，比例之和可能超过100%。每类分语料计数与最多三个完整SHA示例在failure_summary.category_unit_counts，少于三个时仅列已有例，不编造。unit_examples另给最多三个完整单元的unit_id、入口SHA和结果SHA；同字节入口可能属于不同项目闭包，结果SHA绑定各自完整记录。零观察类别保留：compiler_exception, declaration_error, docstring_error, encoding, fatal_error, json_error, pragma_missing_semicolon_candidate, slither_no_timeout, unimplemented_feature, warning.

| 类别 | 单元数 | 占剩余失败 |
|---|---:|---:|
| closure_version_conflict | 4 | 0.040% |
| codegen_only | 43 | 0.433% |
| compiler_exception | 0 | 0.000% |
| declaration_error | 0 | 0.000% |
| docstring_error | 0 | 0.000% |
| duplicate_definition | 26 | 0.262% |
| encoding | 0 | 0.000% |
| fatal_error | 0 | 0.000% |
| internal_compiler_error | 5 | 0.050% |
| io_error | 28 | 0.282% |
| json_error | 0 | 0.000% |
| missing_base_contract | 13 | 0.131% |
| missing_relative_file | 428 | 4.314% |
| multiple_license_or_pragma | 8 | 0.081% |
| other | 210 | 2.117% |
| parser_error_other | 892 | 8.991% |
| pragma_missing_semicolon_candidate | 0 | 0.000% |
| slither_incomplete | 24 | 0.242% |
| slither_no_timeout | 0 | 0.000% |
| syntax_error | 17 | 0.171% |
| type_error_other | 25 | 0.252% |
| unbalanced_structure | 84 | 0.847% |
| undeclared_identifier | 156 | 1.572% |
| unimplemented_feature | 0 | 0.000% |
| unresolved_package_import | 8450 | 85.173% |
| unsupported_disjunction | 1 | 0.010% |
| unsupported_expression | 92 | 0.927% |
| unterminated_pragma | 1 | 0.010% |
| warning | 0 | 0.000% |


最终D6清单由语料独立草案与完整频率表关联，保留原草案及SHA；频率只决定实现顺序。保护审计另核对已定位的Slither类型解析器源文件SHA，确认原生安装包没有变化。

所有other模板逐条列在failure_summary.other_templates及other_template_unit_counts，包含对应单元数和SHA示例。包名/路径与相对文件候选见unresolved_packages、unresolved_import_paths、relative_basename_candidates；前者按单元内导入位置计数。distinct_source_import_statistics另给跨重叠闭包按原始位置计数的结果，便于库索引规划。

发现原聚合器的包/路径字段来自项目组装，单文件CLI诊断缺少这些字段。最终只读统计据保存的工作源码SHA与诊断字节位置补计，12个当时已观察到的单元验证通过；原分类/结果与生产实现不变。无法唯一恢复的导入明确计入missing_import_identity_records，不按basename猜测。相对文件候选搜索只在声明的项目内进行，单文件不扩展目录搜索。

### D6与CP4清单

| 类别 | D6 路由 | 改动等级 | 修复方式 |
|---|---|---|---|
| unresolved_package_import | conditional_rule | additive | 恢复调用方或离线索引中可确定版本/身份的缺失包文件；不联网猜版本 |
| missing_relative_file | conditional_rule | rewrite | 依据项目内候选及声明/版本约束修正缺失的相对导入路径；唯一basename仅为候选证据 |
| undeclared_identifier | conditional_rule | additive_or_local_rewrite | 使用处唯一约束签名时增加声明型接口/事件/结构/合约桩，或明确文档中的旧内建名称迁移 |
| missing_base_contract | conditional_rule | additive | 恢复可确认的基类/声明，或类型约束充分时增加声明型基类桩 |
| duplicate_definition | conditional_rule | rewrite | 删除被编译器拒绝且逐字节相同的重复定义 |
| multiple_license_or_pragma | conditional_rule | rewrite | 仅处理被当前版本拒绝的逐字节重复许可证/指令；相同Solidity pragma通常无需改 |
| encoding | conditional_rule | rewrite | 只做可验证的字节编码/转义等价规范化 |
| unbalanced_structure | conditional_rule | additive | 仅补唯一可确定的末尾括号；不补推测执行逻辑 |
| parser_error_other | conditional_rule | rewrite | 逐项文档证明的局部等价语法/拼写迁移，其他解析错误交代理 |
| type_error_other | conditional_rule | rewrite | 只有类型约束唯一且等价可机械检查时使用明确类型拼写/转换 |
| codegen_only | conditional_rule | none | 编译设置候选须同时满足solc与Slither；手写探针支持的via-ir+optimizer留后续实现 |
| closure_version_conflict | conditional_rule | additive_or_import_rewrite | 可确认依赖身份时恢复兼容原版本；不跨小版本任意覆盖pragma |
| slither_incomplete | conditional_rule | rewrite_or_none | 仅已逐类证明等价的0.4.x tuple-call形式列为CP6改写候选；其余工具限制 |
| other | diagnosis_required | undetermined | 逐项检查归一化模板后再决定类别与路由；不猜修复 |
| json_error | caller_input_rule | none | 修正调用方序列化/配置输入；当前CLI路径无standard JSON主编译 |
| io_error | conditional_rule | none_or_import_rewrite | 在批准路径范围内处理导入/路径配置；缺依赖转对应依赖类 |
| docstring_error | conditional_rule | rewrite | 可唯一绑定时修正错误NatSpec参数/tag |
| syntax_error | conditional_rule | additive_or_rewrite | 有版本文档与唯一含义时补/改修饰词（例如明确旧默认visibility）；不擅改控制流 |
| unimplemented_feature | existing_environment_rule | none | 只尝试既有允许编译器/设置；没有合法选择则工具限制 |
| internal_compiler_error | tool_limitation | none | 保留崩溃证据，只继续既有允许候选；不据崩溃猜源码修复 |
| compiler_exception | tool_limitation | none | 保留异常并继续既有允许候选 |
| fatal_error | tool_limitation | none | 保留致命错误，不做任意源码改写 |
| warning | no_repair | none | Warning本身不作为编译失败或修复触发 |
| unsupported_disjunction | deferred_environment_rule | none | 后续实现区间并集求值和合并后的确定性升序尝试，CP3仅计数 |
| unsupported_expression | diagnosis_required | rewrite_or_none | 区分非法pragma与模块不支持的合法表达式；前者代理、后者工具缺口 |
| unterminated_pragma | conditional_rule | additive | 仅唯一位置可确定时补pragma分号 |
| pragma_missing_semicolon_candidate | conditional_rule | additive | 检查吞入下一条指令的表达式，在唯一边界补分号 |
| slither_no_timeout | deferred_runtime_rule | none | 后续采用子进程隔离与明确截止时间；CP3只报告暴露次数/观察到的挂起 |
| declaration_error | conditional_rule | additive_or_rewrite | 名字/作用域可唯一恢复时处理声明；否则代理分析，不一律补桩 |


各类完整机械检查、兜底路由、CP4破坏算子和没有源码算子的原因在d6_cp4_final；29类和125条breaking-change记录全部保留。源码算子从可编译/D3成立的基础单元删除或修改，实际触发目标诊断后才纳入类别。纯Warning、运行语义、调用方JSON和无法一般构造的工具崩溃不伪造源码算子。频率只排实现先后，不删除低频/零频规则候选。

规则前提包括D3、D7原字节/偏移/节点标记、改写限错误行，以及批准的项目绑定门槛；等价性、签名或依赖身份不能唯一确定时交代理分析。合法源码的Slither原生错绑归工具限制；不会让代理“修”合法源码。0.4.x tuple-call只列已验证候选，实际改写仍留CP6。本轮不实现CP4基准或其他依赖/结构/类型修复规则。

### 已知缺口与前提实测

|| pragma频率见上；后续并集求值与版本升序尝试仍未实现。Slither仍为进程内调用，无强制超时；全部选定调用已完成不证明未来不会挂起，最大已完成Slither耗时见failure_summary。后续建议子进程隔离/明确截止时间。D19下限涉及的原区间（允许0.4.11但不允许0.4.12）逐单元列于d19_intervals_allowing_0411_but_not_0412，当前0.4.12下限未调整。

沿用前批次已封存前提：92版诊断格式切换0.6.0；重复SPDX同形探针从0.8.8拒绝，相同Solidity pragma不因此失败；tuple-call等价形态探针通过；AST-only不足以使原生Slither避开所测codegen失败，0.8.38的via-ir+optimizer组合在手写探针通过。没有重跑或修改这些旧证据。

### 测试、交付与限制

定向32passed；production723passed/6skipped，mando271passed/458skipped，DFG2653passed/9既有warnings；命令、环境、退出码与耗时见pytest_*收据。精确alias拒绝证据由既有测试产物导出，原D3(a/b)true、b预期B.sol而原生A.sol、没有graph.json。四版本正常项目核对七条直接类型声明及A/B调用位置。

生产仍16个模块，本次批准后只改slither.py、pipeline.py、evaluation/report.py及项目测试；之前CP3改动一并交付，精确清单见最终inventory。无安装/下载/LLM/训练/GPU锁/全局solc更改，0美元。最终doc_check、保护审计、空白检查与本地提交在后续补记；未自动push。


完整分类文档记录时间：2026-11-18T00:18:10-05:00（America/New_York，EST；依据本次脚本系统时间）。授权日期仍为2026-11-17。


最终复核暂停（2026-11-18，修改 AI：Codex）：完整观测统计已生成，但CP3最终验收尚未通过。11个DAppSCAN项目入口以连字符开头，project_command与slither_arguments原样传入入口；315次solc调用将路径当选项拒绝。该问题属于参数组装，不属于源码损坏，原9,921个剩余失败包含这11项，当前统计仅为修正前观察。具体清单、命令与SHA、限定./前缀方案及新批次11单元重验请求见leading_dash_review_request.json；已向用户询问，尚未修改参数或重跑。当前批次、所有旧产物及其统计保持，修正后应另建批次、仅替换这11条观察，不把现有数字写成最终接受结果。

三套最终无缓存回归均通过，但它们未覆盖本次发现的连字符入口问题，不能据此放行CP3。读取完成收据的自动审批一度超时，按工具允许仅重试一次只读检查后成功；随后WSL新命令暂报Wsl/Service/0x8007274c，使用只读UNC检查并在最小连接探测恢复后继续，没有重启WSL或修改网络。诊断提取首次漏读reason字段，随后只遍历续跑批次得10项；补入项目复验批次后确认共11项。这些是只读提取修正，没有重试编译。


### 收尾检查与待确认事项


本批次收尾检查（修改 AI：Codex；时间：2026-11-18T00:21:18-05:00，America/New_York/EST）：完整31,071单元观察与两个新运行seal全部核验，复验批次2,385文件、续跑批次193,136文件，运行实现SHA与当前16模块一致。三套最终无缓存回归均通过：production723passed/6skipped（88.344秒）、mando271passed/458skipped（21.392秒）、DFG2653passed/9既有warnings（164.618秒），数据见pytest_*_final_v1.json。定向32passed沿用本轮既有收据，没有再次重跑。

doc_check_v1检查7份正文，全部UTF-8/CJK通过；本次补记完成后以doc_check_v2.json复查最终字节。frozen_audit通过：28,908份受保护跟踪文件、25,828份旧封存文件、753份上一检查点受保护成员、29,611份外部语料文件和10份资料无变化；96个solc相关文件、两环境145/118份元数据、354条DFG引用及原生Slither类型解析器SHA保持。文档历史前缀全部保留。这些是分别定义的检查范围，可能重叠，不能相加作为独立文件总数。

全量中34,973条直接合约类型声明被核对；D3为true但新增绑定检查拒绝的调用为0。139次未获绑定认证的项目调用全部属于Slither未构造成功，不能表述为139次错绑；手写alias用例独立证明已知错绑会拒绝图。原D3事实、源码和安装包均保持。

CP3最终验收仍暂停：11个连字符入口被误当solc选项（315次调用），修正请求见leading_dash_review_request.json，尚未批准、未修改project.py、未重验。当前统计为修正前完整观察，不能宣称CP3已完成。按PROMPTS的中途停止记录要求整理本地检查点；提交身份以包含本条记录的CP3提交为准，未push。无安装、下载、LLM、训练、GPU锁、全局solc或网络修改。所有原始数据与本轮新运行证据保留，后续修正须使用新批次。


2026-11-18收尾检查补记（修改 AI：Codex）：doc_check_v2七份正文全部通过；whitespace_review_v2通过，仅沿用旧批次322份精确SHA绑定的原始工具输出空白，没有新增代码或正文豁免。检查器v1误把git diff --no-index的正常差异退出码1当作空白错误，诊断输出实际为空；已保留v1，v2只修正退出码解释，所有实际空白诊断和异常仍拒绝，没有用v1暂存。该调整不改生产代码、不重跑测试或编译。本文补记后的最终字节由doc_check_v3核验；CP3仍等待11入口参数修正授权。


## CP3 连字符入口修正续节（2026-11-18，修改 AI：Codex）

### 范围、授权与实现

起点为 compile-repair 的 e3fb634f。用户原话“批准限定修正与 11 个单元重验（推荐）”，授权先写 cp3_entry_v1/authorization.json；原请求和完整观察仍保存在封存的 cp3_binding_v1。仅 toolchain/project.py 新增共享入口参数规范化，对以 - 开头的相对入口加 ./，同时供 solc 与 Slither 使用。新增两文件手写夹具和四版本测试核对相对导入、直接合约类型与调用文件身份；普通路径、源字节、版本/设置策略、D3及绑定检查不变。

### 首次验证与停止

run_entry_probes.py 计划运行四个新探针及四个既有普通入口检查，生产环境、已安装版本0.4.12/0.4.24/0.5.17/0.8.38，使用-x防止失败后继续。脚本漏建临时目录父目录，首项测试在初始化时FileNotFoundError；entry_probes.json记录退出码1、0passed，stdout记录1setup error/27 deselected，耗时4.196043秒，实际solc/Slither调用均0。四版本行为没有得到本次运行证实，不能宣称入口修正已验收。

具体修正脚本 run_entry_probes_v2.py 已准备，仅补父目录创建并使用新证据与临时路径；probe_setup_retry_request.json 说明一次续跑范围。依§4.1保留失败并等回复，没有自动重试、没有重验11个单元。旧31,071项观察及21,150/9,921计数保持修正前含义，旧315次错误调用不回写。新汇总、完整回归与最终验收未运行；CP3尚未完成。

### 记录与交付

本次改动、原因和脚本错误修正记于CHANGE_LOG §33、HANDOVER第6节、PROGRESS、DECISIONS和新批次README。生产仍16个模块；0美元，无安装、下载、LLM、HGT、GPU锁或全局solc操作。按中途停止要求完成文档及范围检查后本地提交；最终收据另补，不自动push。


2026-11-18 停止检查点验收补记（修改 AI：Codex）：doc_check_v1对六份正文及五份原文快照共11份全部通过；本补记后的最终字节由doc_check_v2再次核验。frozen_audit通过：28,908份保护跟踪文件、25,828份旧封存文件、841份上一检查点保护成员、29,611份语料和10份资料均未变化；96份solc相关文件、两环境145/118份元数据、354条DFG代码引用和原生Slither解析器SHA保持。这些检查集合可能重叠，不相加计数。Python3.7语法解析与tracked diff --check通过，记录static_review；这些都是范围/静态检查，不能代替未完成的四版本运行验收。

本轮仍停在探针初始化错误后的续跑确认，没有再次运行pytest、solc、Slither或11单元语料。将按中途停止记录要求提交本地检查点，实际提交号以包含本补记的CP3提交及仓库外提交收据为准，未push。现有失败脚本和输出封存；若用户随后允许续跑，须把已准备且SHA固定的run_entry_probes_v2.py原字节复制到新证据批次执行，维持旧批次只读，不覆盖任何旧文件。该脚本按自身目录写入新证据，并使用新的v2临时目录；测试、版本、条件和原11项批准范围保持。


## CP3 获准探针续跑与允许目录问题（2026-11-18，修改 AI：Codex）

### 授权与执行边界

起点compile-repair/8900abe8，用户原话“允许修正脚本并续跑一次（推荐）”，授权保存在新批次cp3_entry_resume_v1。旧cp3_entry_v1及更早批次全部只读，合并879成员基线先核验。本轮未修改生产代码、测试或夹具；原入口./修正保持。

准备执行时发现pytest current符号链接会被原收据glob重复计数，因此保存原字节脚本并仅在执行副本跳过别名。八项测试、四个版本、物化源码和通过条件没有改变；具体SHA在pre_execution_review。这是执行前的证据收集纠错，不是额外实验重试，也未把失败记录删除。

### 探针结果及只读影响核对

| 项目 | 观察 | 证据 |
|---|---|---|
| 普通入口0.4.12/0.4.24/0.5.17/0.8.38 | 4项通过 | entry_probes_v2.stdout |
| 连字符入口0.4.12 | solc rc1，./目标被识别为文件；兄弟目录导入被允许目录限制拒绝 | probes_v2下compiled.json |
| 其余三个连字符版本 | -x停止后未运行 | 同一pytest输出 |
| 汇总 | 4passed/1failed/27deselected；包装器4.440440秒 | entry_probes_v2.json |
| 语料重验 | 0项 | 本次只执行探针脚本 |

测试控制流对应5次显式compile_project、4次run_slither；不声称是原生库内部所有子进程的计数。错误消息为Source "./lib/Dependency.sol" not found: File outside of allowed directories。入口与依赖两文件均实际存在、SHA与夹具一致，且解析后位于同一物化项目根中；没有修改失败夹具以逃避验收。

只读扫描原31,071份结果并核对SHA，92个单元在521次旧调用中出现同一目录拒绝，全部位于0.4.12–0.4.17。79个后来选择其他候选成功，13个仍unrepaired。521次调用包含1,473条相关诊断，路径全部存在且在各自工作根内。它们与11个连字符入口互不重叠，联合范围103项；计数不是新编译或新成功率。完整证据在allowed_paths_existing_evidence和allowed_paths_source_verification。

### 建议与待确认验收

仅建议project.py把solc argv与Slither solc_args的--allow-paths改为解析后的项目根绝对路径，原./入口、物理目录范围、候选升序、设置、源码、D3和绑定门槛保持。补丁proposed_project_allowed_paths.diff尚未应用。已经授权下载的0.4.12官方文档第32行给出允许目录的绝对路径例子；该文档和0.8.38路径说明已核对原manifest SHA，只作为建议依据，不能证明四版本成功。

保留现有八项探针，新增普通嵌套入口/兄弟导入的四版本检查；12项全通过后才新批次重验103项。包含79个旧成功项目是因为目录限制可能让更早候选被错误跳过。其余观察不重跑，新汇总逐项记录替换出处。请求SHA256为141e6bc425aee16c4c2198d2881f3d5b1187cff1667b00d74bf32fc72a08d43d，原授权只涵盖入口前缀与11项，需先确认本次参数和范围扩展。

### 记录、资源与停止

按PROMPTS §4.5第2节和§4.1停止，不继续编译、不自行更改参数。CP3未完成；本轮完整回归、语料重验与最终统计未运行，旧21,150/9,921仍为修正前观察。CHANGE_LOG §34、HANDOVER、DECISIONS和PROGRESS记录全部问题与处理，检查收据后补后本地提交。无新安装、下载、LLM、HGT、GPU锁或全局solc操作，0美元，未push。


2026-11-18 停止检查点核验补记（修改 AI：Codex）：doc_check_v1对六份正文与五份文档快照共11份全部通过，最终补记字节另由doc_check_v2核验。frozen_audit通过：28,908份保护跟踪文件、25,828份旧封存文件、874份上一检查点保护成员、29,611份语料和10份资料未变；96份solc相关文件、两环境145/118份元数据、354条DFG引用及原生Slither解析器SHA不变。这些范围可能重叠，不相加作总文件数。生产仍16模块，本轮生产/测试/夹具均未修改。

Python3.7语法与未应用补丁的git apply --check通过，静态检查不替代四版本运行。tracked diff空白检查通过；唯一保留的是建议补丁.diff的四条空源行上下文，其单个前导空格属于统一diff格式，文件SHA与行号精确绑定于whitespace_review，不豁免生产代码、测试或正文的空白问题。补丁仍未应用。

一次探针续跑已经使用，后续三个连字符版本与任何语料均未继续。当前等待allowed_paths_review_request对应参数及103项范围批准；完整回归、新汇总和最终验收未运行，CP3未完成。按中途停止要求提交本地证据检查点，提交号以包含本条记录的CP3提交及仓库外收据为准，未push。后续批准后须在新批次继续，不向本批次或任何旧批次覆盖写入。


## CP3 最终续节：允许路径修正与完整分类结果（2026-11-18，修改 AI：Codex）

### 任务、批准与实现

本次从compile-repair/967d0890继续同一PROMPTS r2.13 CP3。用户原话“批准参数修正、探针与103项重验（推荐）”，authorization绑定请求SHA256 141e6bc425aee16c4c2198d2881f3d5b1187cff1667b00d74bf32fc72a08d43d、日期、0美元及精确清单；912成员基线先核验。旧cp3_entry_resume_v1、cp3_entry_v1、cp3_binding_v1及更早产物不改写。

仅project.py把solc argv和Slither solc_args两处--allow-paths从相对点号改为解析后的项目根绝对路径。物理允许根仍相同，保留连字符入口./前缀、其他目标字符串、原始源字节、候选顺序和设置政策、D3及已批准项目绑定门槛。test_project.py只追加普通嵌套入口四版本检查，原八项测试和失败夹具均未改。生产模块仍16个；没有新增修复规则、补依赖或更换安装包。

12项探针在0.4.12、0.4.24、0.5.17、0.8.38全部通过，覆盖普通根入口、连字符嵌套入口、普通嵌套入口，核对同参数编译、D3、直接类型绑定与调用文件身份。首个103项运行中cp3_05901已成功，却因脚本tuple/list比较误报而停止；新旧保存JSON计划和输入逐字段相同。保留原停止收据，恢复已完成结果分类后只继续102个未执行ID，manifest核验103项各一次；没有实验重试。首项精确单元结束时间缺失，分类elapsed_seconds为null并注明；原首段summary中0是分类列表计数，实际1编译/1Slither单列更正而不覆盖原文。

只读汇总首次错误寻找历史中断段的正常seal，后按原已登记的interrupted_segment_preservation清单验证，该清单自身SHA与基线一致。正常完成段仍核对seal，所有结果与输入SHA校验保持。两次汇总收据都保留，修正不涉及编译或放宽接受标准。完整问题处理见CHANGE_LOG §35及driver_comparison_recovery、aggregate_inventory_correction。

### 103项重验与有效统计口径

原103项为79成功/24未修复，重验为89成功/14未修复，新增10成功；79个旧成功没有回退，全部从0.4.18恢复到更早允许候选：0.4.12为35项、0.4.13为2项、0.4.15为9项、0.4.16为33项。14项剩余为12个Slither构造工具限制（旧AST导入别名不受当前Slither支持）、1个类型错误、1个未声明标识符；不将这些问题交由本CP改写源码或强行跨版本区间。

新观察453次显式编译/265次Slither，替换旧观察1032/187次；旧数据保持，另有此前335/230次被替换项目调用与9次中断编译单列，不重复计入有效结果。首段包装器18.600598秒、102项续段73.017230秒；它们是运行包装器壁钟，不作为未记录的首项精确耗时。103项输入闭包和JSON计划完全一致，只有已批准的调用路径参数变化。

最终31,071个有效单元中21,160成功、9,911剩余，236条非Solidity单列，无抽样。仅103条使用本次重验结果，其他30,968条provenance与原记录逐字段相同；本报告不宣称全部原观察都用最终实现重新执行。每个结果均保留其实际运行批次、实现和版本来源，新旧替换路径/SHA在result_provenance与replacement_summary。

| 语料 | 有效单元 | 成功 | 剩余失败 |
|---|---:|---:|---:|
| DAppSCAN | 21457 | 13576 | 7881 |
| Trace_CVEs | 15 | 14 | 1 |
| Trace_on_chain | 5000 | 4565 | 435 |
| Trace_repo | 3092 | 2066 | 1026 |
| SOChecker | 661 | 96 | 565 |
| MANDO | 846 | 843 | 3 |


有效编译115,192次、Slither21,376次，旧整文件parse失败但新pragma读取成功1012项，unsupported_disjunction为1项。项目Slither调用15,849次，直接合约类型声明核对34,980条；207次未获绑定认证全部为Slither未构造，不能称为207次错绑，D3为true而绑定检查拒绝仍为0。手写alias拒绝证据继续证明已知错绑被拒绝，但该有限检查不能证明全部IR语义。最大已完成Slither耗时68.116624秒，无强制超时；观察均完成不保证未来不会挂起。

### 完整分类与每类证据

以下比例分母为9,911个剩余失败单元，类别不互斥，比例不可相加解释为总失败率。每类最多3个以输入SHA标识的例证及对应结果SHA、路径均在本批次failure_summary.category_unit_counts.unit_examples；不足3个保留实际数量，零频类别不捏造例子。原分类表来自13种官方错误类型、四代breaking changes和路径/项目结构依据，当前频率不决定覆盖范围。

| 类别 | 单元数 | 占剩余失败 | 语料分布 |
|---|---:|---:|---|
| closure_version_conflict | 4 | 0.0404% | DAppSCAN:3、SOChecker:1 |
| codegen_only | 43 | 0.4339% | DAppSCAN:27、Trace_on_chain:1、Trace_repo:15 |
| compiler_exception | 0 | 0.0000% | 未观察到 |
| declaration_error | 0 | 0.0000% | 未观察到 |
| docstring_error | 0 | 0.0000% | 未观察到 |
| duplicate_definition | 26 | 0.2623% | DAppSCAN:12、SOChecker:14 |
| encoding | 0 | 0.0000% | 未观察到 |
| fatal_error | 0 | 0.0000% | 未观察到 |
| internal_compiler_error | 5 | 0.0504% | DAppSCAN:5 |
| io_error | 28 | 0.2825% | DAppSCAN:25、Trace_repo:3 |
| json_error | 0 | 0.0000% | 未观察到 |
| missing_base_contract | 13 | 0.1312% | DAppSCAN:2、SOChecker:11 |
| missing_relative_file | 415 | 4.1873% | DAppSCAN:373、SOChecker:11、Trace_repo:31 |
| multiple_license_or_pragma | 8 | 0.0807% | DAppSCAN:8 |
| other | 199 | 2.0079% | DAppSCAN:15、SOChecker:180、Trace_CVEs:1、Trace_repo:3 |
| parser_error_other | 892 | 9.0001% | DAppSCAN:78、MANDO:3、SOChecker:379、Trace_on_chain:432 |
| pragma_missing_semicolon_candidate | 0 | 0.0000% | 未观察到 |
| slither_incomplete | 24 | 0.2422% | DAppSCAN:14、MANDO:3、Trace_repo:7 |
| slither_no_timeout | 0 | 0.0000% | 未观察到 |
| syntax_error | 17 | 0.1715% | DAppSCAN:5、SOChecker:12 |
| type_error_other | 25 | 0.2522% | DAppSCAN:9、SOChecker:14、Trace_CVEs:1、Trace_repo:1 |
| unbalanced_structure | 84 | 0.8475% | DAppSCAN:5、SOChecker:78、Trace_on_chain:1 |
| undeclared_identifier | 157 | 1.5841% | DAppSCAN:12、MANDO:3、SOChecker:142 |
| unimplemented_feature | 0 | 0.0000% | 未观察到 |
| unresolved_package_import | 8450 | 85.2588% | DAppSCAN:7450、SOChecker:20、Trace_repo:980 |
| unsupported_disjunction | 1 | 0.0101% | DAppSCAN:1 |
| unsupported_expression | 92 | 0.9283% | DAppSCAN:18、SOChecker:73、Trace_on_chain:1 |
| unterminated_pragma | 1 | 0.0101% | SOChecker:1 |
| warning | 0 | 0.0000% | 未观察到 |


other的23种归一化模板及SHA例证在other_template_unit_counts逐项列出。包名和完整导入路径统计保留于unresolved_packages/unresolved_import_paths；每单元导入位置去重后，主要包包括@openzeppelin/contracts 14906次、@0x/contracts-utils 3092次、openzeppelin-solidity 2972次。相对导入同名候选为找不到934、唯一393、多个230次；这些是导入位置出现次数而非失败单元数。跨重叠入口闭包去重的物理源位置视图另在distinct_source_import_statistics，两个口径不混合。单文件定位诊断的包/路径身份仅从已保存且SHA核验的源码恢复，没有新增编译或修改旧结果，缺失身份记录为0。

### D6路由、CP4算子与保留限制

最终d6_cp4_final仍保留全部29类、125条breaking changes和10个零频类别，规则/代理路由、改动级别、D3/D7机械验证及CP4破坏算子沿用已建立且经过官方资料/手写前提验证的清单。本次只将频率更新并排序实现优先次序；不因语料中未出现而删除候选。能从可编译、D3成立基础上删除/修改构造的类别均列算子；纯Warning、运行语义、调用输入或不能一般构造的工具崩溃则说明不能伪造源码算子的原因。该清单是CP4的输入，CP4基准尚未运行。

既有手写前提证据保持：92版诊断格式在0.6.0切换；重复合约定义92/92被拒绝，相同pragma不因此失败；重复SPDX从0.8.8拒绝；0.4.x tuple-call等价形态只列CP6候选；AST-only不足以让原生Slither绕开所测codegen失败，0.8.38的via-ir+optimizer组合在手写探针通过。这些旧证据未重复运行或回写。

仍需后续处理的实质限制是：并集pragma、Slither子进程超时，以及绑定检查无法覆盖全部表达式/嵌套类型/IR语义。D19下限维持0.4.12，原区间允许0.4.11而不允许0.4.12的6项已单列，不自动扩展支持范围。模块目标仍是未来任意合约，语料只用于评估；本CP没有实现依赖恢复、结构补全、tuple改写或LLM代理。

### 测试、资源和交付

| 验证 | 结果 | 包装器秒数 |
|---|---|---:|
| 四版本路径探针 | 12passed，27deselected | 5.097138 |
| production完整CompileRepair | 731passed，6skipped | 72.332530 |
| mando完整CompileRepair | 271passed，466skipped | 20.864750 |
| mando DFGv2完整回归 | 2653passed，9既有warnings | 156.669927 |
| 只读最终汇总 | rc0，无编译调用 | 31.164432 |

所有测试均使用-B -m pytest -q -p no:cacheprovider及新basetemp，完整命令/环境/退出码见收据；定向探针另带-x。103唯一执行、79旧成功不退化、候选与输入相同、30,968条原来源保持由runtime_acceptance验证。CP3实验与回归验收通过，最终保护审计、doc_check和提交身份在后续补记，不能用这里的已通过实验替代尚未完成的文档核验。

本轮生产只改project.py，原Slither安装、全局solc、DFG和旧产物保持；0美元，无下载、安装、LLM、HGT或GPU锁操作。原语料只读，仓库只保存路径/哈希及诊断证据，运行原始资料在仓库外。完成全部交付检查后本地提交，不自动push，后续由独立审查接手。

本批次最终统计SHA256：afd39e142a5b7418e1cd52dacf53eb94df9f5f5fdf6867249cbdeda99e8e70ae；D6/CP4清单SHA256：da3377a309b418eb7926617b5fec454b28ae2eefdbbf5e7b4ae5d0710dcbf220。


2026-11-18 最终交付核验补记（修改 AI：Codex）：frozen_audit通过，28,908份保护跟踪文件、25,828份旧封存文件、905份上一检查点保护成员、29,611份外部语料及10份官方资料均未变；96份solc相关文件、两环境145/118份元数据、354条DFG引用及原生Slither解析器SHA保持。这些检查集合可能重叠，不相加作总文件数。历史文档均保留，生产仍16模块。Python3.7语法检查、tracked diff空白检查及本批次新文件空白检查通过，没有新增豁免。

doc_check_v1对六份正文与五份原文快照共11份通过；本补记及当前状态更新后的最终字节由doc_check_v2再次核验，提交以该收据通过并绑定各文档SHA为前置条件。新证据由evidence_seal与delivery_inventory封存，acceptance_status汇总最终门槛。完整回归与保护检查已通过，此后只补交付记录，没有再跑实验或修改生产代码。

CP3本地实施与验收完成，后续交独立审查。仅本地提交compile-repair，实际提交号以包含本记录的CP3提交及仓库外delivery_commit_receipt为准；本轮未push，未实施CP4或新增修复规则。参数修正及103项批准全部落实，无新增待批准执行事项；已知工具与版本边界继续按本报告保留。
