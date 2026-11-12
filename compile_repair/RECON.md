# CP0 侦察记录：前置核验完成，停在必需编译器缺口

修改 AI：Codex。日期：2026-11-12（America/New_York）。依据：`PROMPTS.md` r2.1 §4.1、§4.2。**CP0 尚未全量验收，不能进入 CP1。** 正式调查只运行一次，CLI 退出码 2，状态 `blocked_missing_compilers`。本次调查耗时 5.684 秒；未运行语料编译矩阵或全量 Slither。

## 1. 输入身份

- `artifacts/cp0_v1/recon.json` 的 `inputs` 记录全部 846 个相对路径、字节数、SHA256、pragma 合取区间、旧规则 A 版本；与 `cr_pre_v1/compile_repro.json` 的类别和文件名集合完全相同。旧证据没有源码 SHA256 字段，因此只能证明文件集合相同，不能由它独立证明旧云端源码与今天逐字节相同。
- 6c 的 256 个文件全部以源码 SHA256 匹配本次清单；跨类别同字节副本保留全部 `all_sha_matches`，再用任务与文件标识选定报告行。类别只作统计与证据对齐，不参与版本候选决策。
- 6c 报告 SHA256：`db56b7066430813540e468c900283414bf49c5e7c1f519cded8a874a760fd2a6`；seal SHA256：`91e054c9cdd2331b7f21bc48e195a394d6034ffe85f878daa8fb013c9431e49c`；seal 内的 report SHA 再次匹配。可信编译器清单 SHA256：`c836e07304aa94f6036fda7c9aae43ee8095066b94cf68a72b116302ba0a4c7e`，来自已验证报告的绑定引用。
- 846 份源码全部能通过冻结 `frontend.parse`；22 份无 pragma；旧规则 A 取值落在自身合取区间之外的有 2 份，明细在 `inputs[*].rule_version_outside_interval`。这不是当前环境编译成功率。

## 2. metadata 来源与校验

用户于 2026-11-12 回复“允许这些必要的只读校验（推荐）”。授权范围是冻结注册表中两个 contract `sources.json` 及其中 metadata 引用的原始源码与 CSV；不读取标签、图存储或模型产物。精确路径与清单 SHA256 见 `artifacts/cp0_development_v1/metadata_read_authorization.json`。43 份记录各自的清单路径、`sources[文件名].metadata` 字段、原始源码与 CSV 路径/哈希、CSV 行键和版本均保存在 `recon.json.metadata`。

**更正 PROMPTS §1.2：43/43 来自 SmartBugs 的 `/home/zhao/SmartContract/ge-sc-llm/data/smartbug-dataset/versions.csv`，不是 SolidiFI BugLog。** CSV SHA256 为 `6bb1d0542e443533c730aefeb2ac7139e31b1c4955287a9df99e2d4d928b4570`。冻结 `recorded_version` 已逐项验证输入字节、来源源码、CSV 哈希、唯一行、版本值和相对路径绑定；全部通过。≤0.4.11 共 4 份，不能因 metadata 优先而绕过 D3。

| recorded version | 文件数 |
|---|---:|
| 0.4.0 | 2 |
| 0.4.2 | 1 |
| 0.4.9 | 1 |
| 0.4.15 | 3 |
| 0.4.18 | 1 |
| 0.4.19 | 16 |
| 0.4.22 | 1 |
| 0.4.23 | 2 |
| 0.4.24 | 10 |
| 0.4.25 | 6 |

## 3. 与 6c 的逐文件核对

6c：239 compared、11 compile_failed、6 not_comparable；版本来源为 43 metadata、207 pragma_derived、6 fallback_default。对应旧云端规则 A：239 ok、6 fail、11 unavailable_here。两边的 17 个异常文件集合完全一致；全部 256 份所选版本也相同，因此本批没有 metadata 造成的选版差异。旧环境未提供的 11 个早期编译器文件，在 6c 中分为 5 个编译失败和 6 个缺映射。已在旧环境执行的 6 个失败，6c 同样失败。这里依据历史记录归因，不冒充本机重新编译的结论。

| 文件（类别/文件名） | 6c 版本 / origin | 6c 状态 | 旧 A | 错误首行或原因 |
|---|---|---|---|---|
| access_control/0x0bec4767cd170242895d244d7ff73feaff6c2598.sol | 0.4.2 / pragma_derived | not_comparable | unavailable_here | slither_source_mapping_not_comparable |
| access_control/0x0ef23ae0a27130999bf9d886e9598ff355ecf323.sol | 0.4.20 / pragma_derived | compile_failed | fail | Error: Expected identifier, got 'LParen' |
| access_control/0x0f35d82007119dc339af57b29dc8ae794b92926c.sol | 0.4.13 / pragma_derived | compile_failed | fail | Error: Expected identifier, got 'LParen' |
| access_control/FibonacciBalance.sol | 0.4.0 / pragma_derived | compile_failed | unavailable_here | Error: Expected identifier, got 'LParen' |
| access_control/parity_wallet_bug_2.sol | 0.4.9 / metadata | not_comparable | unavailable_here | slither_source_mapping_not_comparable |
| access_control/simple_suicide.sol | 0.4.0 / metadata | not_comparable | unavailable_here | slither_source_mapping_not_comparable |
| reentrancy/0x1839864616602fee4d5cc7a6448dd257636c9a9a.sol | 0.4.11 / pragma_derived | compile_failed | fail | Error: Expected token LBrace got reserved keyword 'Pure' |
| reentrancy/0x416768387836bd8715d127ef9065975325cfad14.sol | 0.4.18 / pragma_derived | compile_failed | fail | Error: Expected identifier, got 'LParen' |
| reentrancy/0x6817178368e30a0cd92662442a966b428e8f2d49.sol | 0.4.0 / pragma_derived | not_comparable | unavailable_here | slither_source_mapping_not_comparable |
| reentrancy/0x966889549fe7b3b950063151f6e2ad7651becdb9.sol | 0.4.16 / pragma_derived | compile_failed | fail | Error: Source file requires different compiler version (current compiler is 0.4.16+commit.d7661dd9.Linux.g++ - note that nightly builds are considered to be strictly less than the released version |
| reentrancy/0xa7fac98b27435c90b916950bbeed91c7dbfe3e44.sol | 0.4.18 / pragma_derived | compile_failed | fail | Error: Expected token Semicolon got 'LParen' |
| reentrancy/etherbank.sol | 0.4.0 / metadata | not_comparable | unavailable_here | slither_source_mapping_not_comparable |
| reentrancy/etherstore.sol | 0.4.0 / pragma_derived | compile_failed | unavailable_here | Error: Undeclared identifier. |
| reentrancy/reentrancy_bonus.sol | 0.4.0 / pragma_derived | compile_failed | unavailable_here | Error: Undeclared identifier. |
| reentrancy/reentrancy_cross_function.sol | 0.4.0 / pragma_derived | compile_failed | unavailable_here | Error: Undeclared identifier. |
| reentrancy/reentrancy_insecure.sol | 0.4.0 / pragma_derived | compile_failed | unavailable_here | Error: Undeclared identifier. |
| reentrancy/simple_dao.sol | 0.4.2 / metadata | not_comparable | unavailable_here | slither_source_mapping_not_comparable |

6 个 not_comparable 的 `missing_filename` 节点数分别保存在 `historical_comparison.exceptions[*].six_c_blockers`。历史错误全文首行与两种调用方式的证据均保留在 JSON。旧 A 是直接 `solc 文件`；6c 是 Slither → crytic-compile 的 combined-json。当前封装复用 crytic-compile 0.2.4 的 `_build_options`，并匹配单文件 allow-paths 参数；直接 subprocess 保留真实退出码，Slither 则复用冻结 `_compile`。Slither API 不暴露其内部子进程退出码，所以记录 API 结果与前一次实测 solc 退出码，不伪造内部退出码。

## 4. 编译器清单与停止条件

26/26 已安装 solc 的 SHA256 与 6c 可信清单一致，没有额外未被清单绑定的安装版本。详细路径、哈希和包版本见 `recon.json.compilers`、`environment`。Slither 0.8.0、crytic-compile 0.2.4、solc-select 1.0.4；Python 3.7.12。

缺失候选的统计范围是 `cr_pre_v1/solc_github_static_SHA256SUMS` 和 6c 清单的有限已知版本集合；不是在线完整发行目录。下表统计版本落入文件初始小版本系列区间的文件数，**不等于每个版本都必须安装**。

| 未安装版本 | 初始候选区间包含它的文件数 |
|---|---:|
| 0.4.12 | 57 |
| 0.4.14 | 62 |
| 0.4.17 | 78 |
| 0.4.26 | 256 |
| 0.5.5 | 226 |
| 0.5.12 | 422 |
| 0.5.13 | 422 |
| 0.5.14 | 422 |
| 0.5.15 | 422 |
| 0.5.16 | 422 |
| 0.5.17 | 422 |

必须补齐的是 **0.4.17**：`denial_of_service/source_files/0xea68d87ae3a55ba91c1a8e6488627a175be81588.sol` 精确声明 `pragma solidity 0.4.17;`，区间 `[0.4.17,0.4.18)`，输入 SHA256 `330e9c9b8dbb865a7de4b842b988a6c45f7a3b615806ce0a7db45281c4c8a256`。它是唯一没有任何已安装可信候选的文件；其他 845 份有候选，但尚未证明编译成功。缺失 0.4.17 涉及 78 份区间，其中只有这一份无替代。

待批准请求：`artifacts/cp0_development_v1/compiler_installation_request.json`。建议仅安装官方 Linux amd64 solc 0.4.17，使用现有 solc-select 1.0.4；先核验官方 SHA256/Keccak256，与旧证据 SHA256 `13414bf86f80319e6f5863b4ca4af786956d188f5f9b99dda6439362c6d91115` 交叉核对；新增独立信任清单，不改 6c 清单，不切换全局 solc，费用上限 0 美元。**请求尚未批准，未下载、未安装。**

## 5. 本地探针与未运行项目

`tests/test_toolchain.py` 的同一合约包含 2 个声明、5 个 CFG 节点。保存的真实调用记录位于 `artifacts/cp0_development_v1/pytest_cp0_tmp_v2/test_real_compiler_success_is_0/`。

| 编译器 | solc 退出码 | Slither 构造 | 缺文件名节点 | D3 |
|---|---:|---|---:|---|
| 0.4.11 | 0 | 成功 | 5 | 失败 |
| 0.4.13 | 0 | 成功 | 0 | 通过 |

CP0 测试 21 passed；冻结 DFG 测试 2653 passed、9 条既有依赖弃用警告。前者第二轮耗时 0.42 秒，后者 pytest 耗时 182.50 秒；完整命令与日志在开发产物。第一轮 CP0 测试为 20 passed / 1 failed：测试将位于归档目录内的 tmp_path 误判为外部路径；仅修正测试路径，首轮日志与现场保留。

未运行且未计为通过：846 文件的编译矩阵、当前规则 A 成功率、升/降序 D3 选版差异、moved/crossed_minor 计数、全量 Slither、跨版本 key4/SlithIR/length 比较和 CP2 时间估计。调查编排目前止于前置核验，补齐环境后继续实现和验收。

## 6. CP2 比较键建议与证据边界

6c 的 Slither 报告保存的是带声明来源的读写 occurrence 与函数上下文。`node`、`function`、`declaration` span 只有 start/end/filename，occurrence 没有 CFG node.type 或原始有序 SlithIR。因此不能直接从该报告重建完整 key4、CFG/CG 或原始 IR 基线。

建议评审的可观察回归键：外层用 source_sha256；内层使用 `(layer, function_name, function.start, modifier, context_contract, context_declarer, inherited_context, node.start, declaration.start, canonical_name, fact, tags)` 的多重集合。保留继承上下文和重复次数，排除 source length。该键能比较报告实际保存的事件/声明/上下文，但尚未逐条验证碰撞，不能声称唯一标识所有 CFG 节点。当前两版本新运行仍可按 D4 比较 key4、SlithIR 和长度诊断。此处只提出比较接口，未改 CP2 验收方案，实施前须确认。

另一个留给 CP1 的实质问题：§3.3.6 对“精确 pragma 版本不可得”提出覆盖，同时 §3.2 禁止越过声明区间；精确版本没有第二个区间内版本。此次建议补齐 0.4.17，不借助 pragma 覆盖。未来对此类输入的覆盖边界仍须用户决定。

## 7. 归档

- `artifacts/cp0_v1/recon.json` SHA256：`e4dfe405a16ca90c962b54996f117e76eb1a17656197062be17196200906bca1`。
- `artifacts/cp0_v1/seal.json` SHA256：`eed04a53213e62a9b1b0fc41cdbd827a6073d4451f093b4de44134b7d5c8b1d0`；seal 绑定 recon。
- 源码来源、tree-sitter 动态库与 crytic-compile 文件哈希见 `artifacts/cp0_development_v1/source_provenance.json`。354 个 `_code_refs()` 与任务前基线一致；9 个生产 Python 文件符合限定目录。

```bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-compile
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
python -B -m compile_repair.cli survey   --output compile_repair/artifacts/cp0_v2   --metadata-authorization compile_repair/artifacts/cp0_development_v1/metadata_read_authorization.json
```

该命令只供批准后的下一轮使用，不在本轮重跑。当前实现遇到缺失版本返回 2 并封存现场；若无版本缺口，非 `--inventory-only` 模式仍返回 `stopped_after_preflight`，因为全量矩阵编排尚未实施，不能把前置通过当作 CP0 完成。`cp0_v1` 已存在，禁止使用它重跑。补齐编译器后还需实现独立追加信任清单的接入、编译矩阵及 D3 选版调查，再使用新批次。


## 8. 2026-11-12 续作：安装授权与 r2.2 版本范围（修改 AI：Codex）

以下追加内容是本轮状态，前七节保留先前检查点，不回写历史。用户先以“可以下载，当前的编译模块是涵盖所有的版本的solc吗”批准原单个 0.4.17 请求；同步 r2.2 后，再以“批准这 10 个探针版本（推荐）”批准 0.4.12、0.4.26、0.5.17、0.6.0、0.6.12、0.7.0、0.7.6、0.8.0、0.8.4、0.8.38。两份授权分别保存在 `artifacts/cp0_compiler_install_v1/authorization.json` 与 `artifacts/cp0_compatibility_install_v1/authorization.json`，均限定官方 Linux amd64、费用上限 0 美元、不改包与全局 solc 选择。没有从该批准推导下载所有版本的授权。

11 个新增二进制均以官方 SHA256 和 Keccak256 校验，旧 26 项可信清单保持不变；两个 `trusted_compilers_addition.json` 记录授权引用、发布索引哈希、二进制路径、双哈希与真实 `--version` 输出。工具入口显式加载追加清单，核验链路后再加入清单，拒绝替换原有可信版本。`solc-select 1.0.4 install 0.4.17` 首次因上游索引请求 HTTP 403 退出且未创建目标文件；同一官方索引通过已有显式代理的 requests 客户端可读，因此使用该客户端获取已授权二进制，校验后写入既有 solc-select 目录。失败日志保留，没有升级客户端或切换全局版本。

官方发布索引来自 `https://binaries.soliditylang.org/linux-amd64/list.json`，缓存 SHA256 `b44c1d0e598ed0bcbf4ee49c86c5ae85b63718c1591689b02d12d7a11d45a2ac`；快照 latestRelease 为 0.8.38。下表来源为 `cp0_matrix_smoke_v2/report.json.coverage`，正式调查再次核验同一快照；范围内共 92 个正式版本，安装 33 个，未安装 59 个。另有 0.4.0、0.4.2、0.4.9、0.4.11 四个历史对照版本，所以总安装数为 37。

| 系列 | 快照发布数 | 已安装数 | 未安装版本 |
|---|---:|---:|---|
| 0.4（从 0.4.12） | 15 | 14 | 0.4.14 |
| 0.5 | 18 | 12 | 0.5.5、0.5.12–0.5.16 |
| 0.6 | 13 | 2 | 0.6.1–0.6.11 |
| 0.7 | 7 | 2 | 0.7.1–0.7.5 |
| 0.8 | 39 | 3 | 0.8.1–0.8.3、0.8.5–0.8.37 |

因此，“目标范围为 0.4.12–0.8.x”“某版本已经安装”“本次特征探针通过”“任意输入均受支持”是不同结论。本轮只测已安装版本的小型特征探针和 MANDO 回归，不证明所有补丁版本或所有 Solidity 语法可用。CP0 仍是基线调查，通用 repair 入口和后续修复方法未在此步实现。

本轮代码在 9 个既有生产模块内扩展，无新增生产模块。`survey` 为每份合约编译初始候选集全部已安装可信版本；只有本系列全部 D3 失败才激活后续系列。规则 A 单独作为对照，不因落在区间外而成为有效修复候选。实验性升序/降序都保留已验证 metadata 的优先级；无 pragma 的 MANDO 回归先试 0.4.25。每份输入另找真正通过 D3 的最低与最高候选，因此既记录“选定版本对最高版本”，也记录“最低版本对最高版本”的多重集合差异。内层没有重新尝试已观察过的失败，同一文件/版本结果复用；通用无 pragma 语法推断仍属 CP1。

六个新手写 fixture 覆盖各系列的状态读写、内部调用、修饰器、事件、外部调用和继承；0.6 起使用 try/catch，0.8 起使用 unchecked。自定义错误另放在 `compat_08_errors.sol`，只交给 0.8.4 及以上探针，避免把未引入语法误判为工具失败。语法依据为 [0.6.0 breaking changes](https://docs.soliditylang.org/en/v0.6.0/060-breaking-changes.html)、[0.8.0 breaking changes](https://docs.soliditylang.org/en/v0.8.0/080-breaking-changes.html) 和 [0.8.4 release announcement](https://www.soliditylang.org/blog/2021/04/21/solidity-0.8.4-release-announcement/)；本轮只核对网页，未下载文档语料。


## 9. 正式 MANDO 回归结果与差异边界

来源：`artifacts/cp0_v2/recon.json`（SHA256 `bddbeaa256192b567525370f8b27335a3d2bdcf3ccb48e22086150718414ffb6`）、`invocations.jsonl`、`cross_version.jsonl`；补充汇总在 `cp0_continue_v1/final_findings.json`。正式运行只执行一次；内部调查耗时 928.330 秒，CLI 包含启动共 932.935 秒，退出码 2，受控停止状态为 `awaiting_d16`。

| 验收项 | 结果 |
|---|---:|
| 输入 / metadata / 6c 匹配 | 846 / 43 / 256，全部重新核验 |
| 无已安装可信候选 | 0 |
| 至少一个候选通过编译与 D3 | 846/846 |
| 选定节点缺 filename / 空 CFG 文件 | 0 / 0 |
| 规则 A：通过 / 失败 / 未安装 | 821 / 22 / 3 |
| 规则 A 在 pragma 合取区间外 | 2 |
| 升序与降序选定版本不同 | 617 |
| 相对规则 A 移动版本 / 跨小版本系列 | 44 / 0 |
| 至少两种版本通过 D3，可做端点比较 | 678 |
| 最低/最高 key4 相同 / 有序 SlithIR 相同 | 678 / 678 |
| 最低/最高 source length 相同 / 不同 | 650 / 28 |
| 升序选定/最高版本的三项比较 | 同为 678 / 678 / 650 |
| 选定版本存在重复 key4 的文件 | 55 |
| 原 6c 的 17 个异常文件现在通过 D3 | 17/17 |

MANDO 直接 solc 调用 5,391 次（rc0 5,254、rc1 137），Slither 调用 1,546 次（D3 全通过）。候选中的预期编译失败是矩阵数据，未把它们静默丢弃或当作基础设施重试。每次调用均有可执行文件 SHA、命令、结果与时间。原始源码 SHA 在编译前后及全量结束时校验，没有源码修复或 pragma 覆盖。

规则 A 不可用的三份明细：`unchecked_low_level_calls/0x0cbe050f75bc8f8c2d6c0d249fea125fd6e1acc9.sol` 选 0.4.10；`unchecked_low_level_calls/0x366cf49c6bc3986b20ecf4fd7c05f0c617332e8c.sol` 选 0.5.5；`unchecked_low_level_calls/0x388b2f93e822d39d45ce748f2b827aa1df657c39.sol` 选 0.4.6。这三份都已用合法区间内其他版本通过 D3，不需要为旧对照规则额外安装它们。对照旧云端记录：旧 ok 中 806 份本机 passed、1 份因缺 0.5.5 unavailable；旧 fail 的 10 份仍 failed；旧 unavailable 的 29 份中 15 passed、12 failed、2 仍 unavailable。由此解释原 807/10/29 与本机 821/22/3 的差异，不把环境不同当成源码改变。

尚缺的初始候选版本为 0.4.14（62 份区间包含它）、0.5.5（226）、0.5.12–0.5.16（每个 422）。这是候选区间覆盖计数，不是必需安装清单：本轮没有零候选或零 D3 成功输入。全支持范围的 59 个未安装补丁仍按 §8 清单登记，未申请或擅自安装。

**D4 的边界**：key4 在 55 份输入中有重复，不能直接作为唯一图节点主键。例如 `access_control/0x000c100050e98c91f9114fa5dd75ce6869bf4f53.sol` 的 `(C10Token, min(uint256,uint256), RETURN, 33685)` 出现两次。本步比较使用多重集合，保留每次出现及有序 IR，没有去重；完整重复键在 `invocations.jsonl`。678 份的相等结论只覆盖本次节点字段和 IR，不等于证明控制流边、调用图边或行为语义相等。其余 168 份没有两个 D3 端点，不进入跨版本分母。CP2 的存储节点标识及 6c occurrence 比较范围仍需审查，未自行更换方案。

CP2 时间依据：846 个升序选定版本的直接 solc 时间合计 80.853 秒，Slither API 合计 228.587 秒，共约 309.440 秒（5.16 分钟）。这是同一 CPU 环境下编译与分析部分的实测合计，未包含未来图序列化、存储、比较与额外候选重试，不是完整 CP2 总耗时承诺。

## 10. Slither 兼容性：在 D16 停止

共 37 个安装版本、39 组适用探针；solc 均 rc0，Slither D3 33 组通过、6 组失败。四个低于下限的历史版本各缺 10 个 CFG 节点文件名；范围内另有两组自定义错误失败。基线特征探针在目标范围内全部 33 个安装版本通过；31 个版本的全部适用探针通过，0.8.4 和 0.8.38 的自定义错误探针未通过。

| 实测版本 | 特征与 D3 结果 |
|---|---|
| 0.4.0、0.4.2、0.4.9、0.4.11 | 编译和 Slither 构造成功；每个缺 10 个 filename，D3 失败，支持下限负对照 |
| 0.4.12–0.4.26 中已安装的 14 个版本 | 基线特征全部通过；0.4.14 未测试 |
| 0.5 系列已安装的 12 个版本 | 基线特征全部通过；缺失补丁见 §8 |
| 0.6.0、0.6.12 | 基线特征与 try/catch 通过 |
| 0.7.0、0.7.6 | 基线特征与 try/catch 通过 |
| 0.8.0 | 基线特征、try/catch、unchecked 通过；自定义错误尚未在此版本引入，不运行该项 |
| 0.8.4、0.8.38 | 基线特征、try/catch、unchecked 通过；自定义错误编译成功但 Slither 构造失败 |

失败输入为 `tests/fixtures/compat_08_errors.sol`，SHA256 `62f0b3f19b8dedb126661f34439296387569fd1e2a63b7ae1294ed6b40315e54`。两版均抛 `ParsingError: Unknown contract item: ErrorDefinition`。安装中的 `slither/solc_parsing/declarations/contract.py:250` 拒绝此 AST 项，文件 SHA256 `4c80abf3a0fae5d33c674de5f28ab798d8d5f9b2921b619deeb19b4bbc73f88d`。诊断来源见 `cp0_continue_v1/slither_failure_diagnosis.json`；其中初记行号 252 已在 `final_findings.json.diagnosis_corrections` 更正为 250，原记录保留。

证据说明这是 Slither 对自定义错误 AST 的解析缺口，不是 solc 0.8.38 的所有合约都不可用。机制同样值得关注产生 ErrorDefinition 的其他版本，但未安装的 0.8.5–0.8.37 没有逐版实测，不标成“全部测试失败”。同理，三个 0.8 探针版本不能外推成完整 0.8.x 支持。

依据 PROMPTS CP0 §5b“若较新版本失败……作为 D16 的输入后停下”，正式状态 `awaiting_d16`。需要用户在保留当前工具链并限定可声明支持范围、或评估新版 Slither 的方案之间作出决定；如选择升级，建议先在独立环境验证并保留 6c 环境作历史回归，这只是待确认建议，尚未实施。没有擅自安装或升级 Slither/crytic-compile/Python，也没有进入 CP1。

## 11. 正式归档与复现

`cp0_v2/seal.json` SHA256 为 `16dfb47bb17cbcb9da0a1a11b3c02a9cc7e4cfae39717e1d38ed8a3294284a9b`，绑定 recon、调用日志和全部跨版本差异。源码及 9 个实现模块的 SHA、fixture SHA、工具包版本都在 recon。命令已经运行一次，不能再次使用同一输出目录；下面只供未来经审查后在**另一个尚不存在的目录**复现，不在本轮重跑。

```bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-compile
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
python -B -m compile_repair.cli survey \
  --output compile_repair/artifacts/cp0_review_reproduction_v1 \
  --metadata-authorization compile_repair/artifacts/cp0_development_v1/metadata_read_authorization.json \
  --trusted-addition compile_repair/artifacts/cp0_compiler_install_v1/trusted_compilers_addition.json \
  --trusted-addition compile_repair/artifacts/cp0_compatibility_install_v1/trusted_compilers_addition.json
```

旧 §7 的无追加清单示例属于首轮停止现场，续作需要上面两个参数。测试与文档验收、冻结审计及提交说明见 CP0_REPORT 的续作小节、CHANGE_LOG §6.5；当前允许的 CP0 调查已完成，审查与 D16 决定尚未完成。
