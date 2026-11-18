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
