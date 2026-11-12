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
