# CP5 项目组装与离线依赖修复

修改 AI 为 Codex。2026-11-23 在 `compile-repair` 的 `26f44492` 上执行 PROMPTS r2.22 §4.6g。本报告记录中途检查点。D22 和 D23 已获批准，完整离线索引、开发集规则选择和全量修复率仍待验收。以下产物路径均相对于 `compile_repair/artifacts/cp5_v1/`。

## 实现

| 文件 | 本次行为 | 新增行 | 删除行 |
|---|---|---:|---:|
| `toolchain/project.py` | 校验 standard JSON 的源单元名、内容、可选 Keccak 与 remapping。全部源共同参与同一次 CLI 和 Slither 编译。为有证据的项目内唯一目录提出 remapping | 248 | 21 |
| `rules/dependencies.py` | 从指定归档构建只含 Solidity 文件的带 seal 索引。查锁文件与清单、核验发布版文件和传递导入、查找项目内相对文件 | 585 | 0 |
| `pipeline.py` | 先运行既有环境策略，失败后处理第 2–4 步。保存各轮工作副本、全部调用、错误数、接受条件和字节溯源。发布版选择保留实际 D3 结果 | 252 | 20 |
| `cli.py` | 增加离线索引构建命令 `dependency-index`，沿用既有 `repair` 入口 | 7 | 1 |
| `evaluation/benchmark.py` | 保留原基准的环境阶段观测，新增损坏工作副本的 CP5 修复与评分接入 | 84 | 1 |
| `evaluation/report.py` | 汇总编译、主与存活 kept、CFG 边、调用、移除数、exact、名称状态和包字节符合率 | 37 | 0 |

统计依据为 `checkpoint_audit.json` 的逐文件行差、函数名与 SHA256。生产模块由 17 个增至 18 个。评分函数与既有 DFG v2 的 354 个代码引用均通过比对。本次保留单文件原有处理方式。只有调用方提供的项目根、或包装自身列出的源文件，才界定项目内搜索范围。项目外发布版通过完整性校验后才写入工作副本。

## 真实验收

| r2.22 要求 | 本轮实测 | 状态 |
|---|---|---|
| 全部基础图自比 | 16,136/16,136 exact，名称状态全部 identical，name_mismatch 和 disputed 均为 0。耗时 156.845 秒 | 通过，见 `self_summary.json` 和逐项流 |
| CP4.5 历史名称状态 | 最终批次 14,196 项精确还原、200 项移动、114 项迁移中的 rejected 均为 0。初轮与续批分列 | 通过，见 `historical_status.json` |
| 全量只读测量 | 9,144 个不同单元。其中主因命中 9,138 个，另有 6 个仅候选原因命中 | 通过，见 `measurement.json`、`measurement_units.jsonl.gz`、`measurement_verification.json` |
| 单个 JSON 的全部源进入图 | 手写包装编译探针使用相互导入的命名空间与一个独立合约。solc 0.8.38 返回 0，生产 Slither D3 与项目图可用性均通过，三个源文件都有节点 | 已验证，见 `multi_input_probe.json`。`optimizer` 另有文件范围冲突 |
| 第 2、3、4 步 | 手写的项目内唯一目录、测试发布版补包和导入路径改写，均经正常修复入口完成真实编译与 D3。另测多候选、哈希错误、缺符号、版本不合和路径越界。两个发布版对照验证最新、最旧、接近选定编译器系列及已知版本优先 | 实现探针通过，见 `step_probes.log`、`implementation_checks/` |
| 真实发布版索引 | 172 个获批版本中已下载 149 个，逐包重新读取归档、核对 npm SHA512 和本地 SHA256。一共 80,004,759 字节。其余 23 个待续传 | 停在传输层，见 `d23/transport_stop.json`、`checkpoint_audit.json` |
| MANDO 真值回归 | 846 个输入走原 CLI。843 个成功单元全部通过 D3，图与 `cr_store_mando_v5` 逐字节相同，第 2–4 步触发 0 次。3 个历史 Slither 失败状态相同 | 通过，见 `mando_regression.jsonl`、`mando_regression.json` |
| 损坏基准 | 2,264 项纳入清单核对完成。开发集四项接入检查中，包装 `cp3_00775` 达到 exact，缺相对文件、I/O 错误和 pragma 冲突三个样本保留未修复。四项 removed_by_repair 均为 0 | 仅开发探针。完整评分、包原件符合率和全量机械检查待测 |
| 外部语料 | 已确定主因命中的 9,138 个不同单元。完整离线索引和开发规则尚待冻结 | 全量重跑及剩余主因表未运行 |

测量覆盖 454 个物理项目和 449 个独立输入。按语料分为 DAppSCAN 7,694、Trace 仓库 1,001、Trace 链上 410、SOChecker 39。五个主因计数为缺包 8,454、缺相对文件 412、standard JSON 410、I/O 错误 28、闭包版本冲突 4。一个单元可有多个主因。详见 `measurement.json`。

8,469 个单元需要补全包前缀。所有待补包均有 T1 证据的为 73 个，只靠 T2 即可全部覆盖的为 0 个，至少有一个 T3 的为 8,396 个。按项目中证据最弱的单元计，393 个项目含 T3，61 个没有待补包。唯一同时出现 package.json、package-lock.json 和 Hardhat 配置的项目含 73 个 T1 单元。别名限定于所属清单。项目内现有目录能唯一覆盖全部缺包路径的有 747 个，有歧义 91 个，部分覆盖 103 个，找不到目录 7,528 个。按观测前缀频次取前 5、10、20、40 个，可覆盖全部待补前缀的分别为 5,546、6,592、7,397、8,058 个。上述计数只衡量路径与版本证据。数据见 `measurement.json` 的 identity、copy_coverage、coverage。

410 个 JSON 包装含 5,829 个源码单元，每个包装有 1–89 个源码单元。没有观测到 urls 或 keccak256 字段。280 个带 optimizer，其中 254 个启用、26 个关闭。232 个带 remappings，214 个带 evmVersion，104 个带 viaIR，190 个带 libraries。详细设置和 pragma 见 `measurement.json`、`optimizer_request.json`。

| 损坏算子 | dev | test | 合计 |
|---|---:|---:|---:|
| 缺包 | 8 | 106 | 114 |
| 缺相对文件 | 90 | 310 | 400 |
| standard JSON | 189 | 761 | 950 |
| I/O 错误 | 91 | 309 | 400 |
| 闭包版本冲突 | 78 | 322 | 400 |

8 个开发缺包样本将用于比较三条版本选择规则。106 个测试样本留给规则冻结后的报告。分母从 CP4.1 已封存的纳入收据计算，见 `benchmark_inventory.json`。四项接入检查的真值、图和调用路径见 `dev_probes.jsonl`。

## 测试与开发记录

| 环境与测试 | 结果 | 依据 |
|---|---|---|
| production 模块测试 | 1,126 通过，6 跳过 | `implementation_checks/production_tests.json` |
| mando 模块测试 | 651 通过，481 跳过 | `implementation_checks/mando_tests.json` |
| mando 的 DFG v2 | 2,653 通过，9 条警告 | `dfg_tests.json` |

增加了 CP5 测试，并把旧迁移测试的生产文件数从 17 更新为 18，保留其 SHA 与迁移执行检查。首批 22 项手写与分层检查已留档。增加双发布版选择的四个对照后再次运行两个环境的模块测试，日志分目录保存。评分接入没有修改 CP4 的评分规则。可用以下命令复核代码，两套环境分别使用自己已有的 Python。

```bash
python -B -m pytest -q -p no:cacheprovider compile_repair/tests
python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests
```

## 归档与资源

全量单元清点、元数据和三次批准的原文、D23 精确版本与大小限额、测试命令均在 `artifacts/cp5_v1/`。外部包只存放在工作树外的 `corpora/compile-repair-npm-cp5-v1/archives/`。完整探针、回归图及调用在工作树外的 `compile-repair-local/cp5_v1/`。MANDO 新运行的 seal SHA256 为 `fd3a59d4cb32c6ee64906432dccc5e3cd485c1ec96e28874d145425ebda72b7a`。编译器绝对路径、哈希、版本、Slither profile 和执行参数见该 seal、相应调用收据与 `multi_input_probe.json`。

官方注册表元数据请求 141 次，响应传输 3,132,219 字节。172 次 HEAD 均未给出压缩长度，158 版有已公布解压大小，合计 828,750,659 字节。用户批准 20 个包的具体 172 版，明确每版与累计的硬上限。按前缀计这份清单可覆盖 5,855/8,469 个单元的全部待补包。149 份成功下载收据的时长合计 155.055 秒。LLM 调用 0，费用 0 美元。分项证据见 `registry_get_summary.json`、`registry_head_summary.json`、`d23_download_request.json`、`d23/authorization.json` 和 `checkpoint_audit.json`。

## 停止位置与后续边界

1. 请求 `openzeppelin-solidity@2.3.0` 时，远端在返回 HTTP 状态前关闭连接。没有未登记的归档或部分文件。原始日志保留。待确认的续传仅涉及剩余 23 个既定 URL，每个版本新建代理连接，沿用原来的累计限额。另一次 WSL 启动超时发生在发出网络请求前，已通过现有会话恢复，经过记在 `wsl_startup.json`。
2. §4.6g 要求映射包装的 optimizer，但 §3.3 第 3a 条和当前共享参数验证器只允许 evm-version 与 via-ir。§4.6g 的生产文件表也没列出验证器所在文件。拟仅在 `toolchain/solc.py::validate_settings` 中加入经过校验的 optimize 和 uint32 runs，保留诊断分类。请求及 280 个包装的证据在 `optimizer_request.json`。当前实现将无法表示的设置记录为未接纳，等待用户决定。
3. 两项决定落实后，完成正式离线索引、缺包 dev 策略选择、2,264 个损坏样本的评分与 9,138 个外部单元的重跑，再报告修复率和剩余主因。本次为本地检查点。

### 本次提交代码的回归复核

补齐三条发布版候选规则的对照测试后，以拟提交的 18 个生产文件再次执行完整 MANDO CLI 回归。运行 seal 中逐文件实现 SHA256 与工作树全部相同。843 个成功图与 v5 逐字节相同，新步骤触发 0 次，另 3 个单元保留原失败。最终 seal SHA256 为 `ee79944b01697357a9c899432bb9e064f7fa363a7b07d241518bebde431064af`。见 `final_mando/summary.json` 和 `final_mando/rows.jsonl`。待完整索引生成后使用的 `run_benchmark.py`、`run_external.py` 已保存，本检查点只核对了这两个脚本的语法。

两份 MANDO 控制台日志在 Git 中以无损 gzip 形式交付。原始日志行内含编译器引用的旧源码缩进。可按 `log_archives.json` 对照压缩包及解压字节的 SHA256，再按 `checkpoint_seal.json` 核对原始收据。

## CP5.1

本节从 `5fe7671f` 的 CP5 检查点继续。依据为 PROMPTS r2.23 §4.6g、§4.6h。新结果在 `artifacts/cp5_1_v1/`，逐次编译与源码副本在仓库外 `compile-repair-local/cp5_1_v1/`。本节中的 D3 成功要求 solc 返回 0、生产 Slither 通过 D3 且图可用。

### 依赖索引与传输

D23 清单中的 20 个包、172 个指定发布版全部通过官方 SHA512 和本地 SHA256 校验，压缩总量 88,886,992 字节。本步新增 23 个发布版及 8,882,233 字节。归档内普通文件总计 834,378,333 字节。离线索引只提取了 13,073 个 Solidity 文件，共 59,535,987 字节。逐文件核验内容摘要及磁盘文件集。索引 SHA256 为 `a02cc091f958aa78fd61f33f2f166912b870b98c77ae6e0cd810bdd704689511`。见 `download_summary.json`、`index_verification.json`。

前 18 个新增发布版成功后，TLS 对端在下一次握手时断开。之后一次新 WSL 进程启动超时，自动审批因可能重复请求而拒绝切换会话。用户同意在现有会话内加独占登记。第一次受保护执行时漏传代理变量，在创建连接前退出。1.6.0 有一条预登记，GET 数为 0。保留原现场，以禁用套接字和 DNS 的方式核对代理与五个目标，用户批准另启动一次。新批次固定代理，五个 URL 各取得一个 HTTP 200，沿用原始大小上限。历次授权见 `docs/DECISIONS.md` 及 `configured_five/authorization.json`。下载与本地实测费用均为 0 美元。

### 代码、分母与独立验收

- D24 支持包装自带的 `--optimize` 与 `--optimize-runs`，runs 限定为十进制 uint32，重复参数拒绝。真实包装在 solc 及 Slither 使用相同参数。针对设置和诊断的 109 项通过。另有 8 项 CP5.1 生产环境探针覆盖参数传递、锁版本遮蔽、依赖编译次数、导入文件移动和包装汇总。
- 依赖组合在实际进入编译时记一次序号。同一次组合内尝试多个 solc 或重试编译设置仍占一个位置。各轮共享同一计数，记录首个 D3 成功位置、逐项版本和截断状态。手写回归覆盖了新依赖使调用方自身报错、换到第二个版本后成功的情况。
- 在 CP4 的 16,136 个基础单元上复核了分组规则。外部主因汇集去重后为 9,138 个单元，开发集 2,316 个，测试集 6,822 个。全部 73 个有精确锁版本的单元位于测试集且来自同一个项目，只作为规则冻结后的参照。见 `population.json`。
- 文件移动算子在项目内把一个非入口、受相对导入的真实文件移到 `.cp5_moved/`，完整保留字节。7,059 个适用单元中按种子 20261122 抽取 DAppSCAN 和 Trace_repo 各 200 个，开发集 94 个、测试集 306 个。400/400 在环境阶段触发缺失相对导入。逐文件把它移回并重新运行生产工具链后，400/400 的精确评分、kept、CFG 边及调用比例均为满分。此项单独衡量逆操作。见 `moved_summary.json`。
- 412 个缺相对文件单元中，158 个有不区分大小写的同名候选，137 个有唯一同名候选，150 个有候选声明所需符号，131 个有唯一符号候选。28 个 I/O 单元的对应数量为 8、8、4、4，其中 0 个属于可改写的相对导入。计数以每个单元至少有一条相应导入为准。见 `path_census.json`。
- 包装基准按 `affected_by_damage − lost` 报告恢复节点，同时报告 lost、added 和 exact。其他算子使用 CP4.5 的评分。8 个开发缺包样本上，三条规则都得到 7/8 个 D3 成功，主 kept 共 213/232。23 个原库文件中，最新及最近系列各有 1 个字节相同，最旧有 2 个。版本池是代表版本抽样，文件字节相同与可编译分别统计。见 `package_dev_summary.json`。

当前已验证的 18 个生产文件对应的 MANDO 回归为 843 张成功图逐字节相同、3 项历史失败、第 2–4 步在成功单元触发 0 次。production 模块测试 1,147 通过、6 跳过。mando 模块测试 667 通过、486 跳过。DFG v2 为 2,653 通过、9 条警告。354 项 DFG 源码引用与冻结证据一致。函数及行数和检查命令见 `checkpoint_audit.json`。

D23 的抽样上限适用于每包的代表版本。锁文件要求的精确版本另行并入获批清单，`@chainlink/contracts` 实际有 13 版，其他 19 个包各有 1–12 版。这个范围限制了恢复原库文件字节的机会。清单及抽样实现见 `artifacts/cp5_v1/d23_download_request.json` 与 `release_plan.py`。

实测还发现组合上限没有涵盖的耗时。在 `cp3_09664` 的最新优先开发运行中，第 3 步用 148.84 秒生成了 1,280 个仍有未解析导入的组装候选，solc 调用次数为 0。一次候选减少了诊断错误数，随后第 2 步接受新的组装并通过 D3。此类候选会占用 CPU 和磁盘，直接跳过也可能丢失后续成功。本步按 §4.6h 只限制实际编译组合，保留全部尝试。证据见 `assembly_only_example.json`。

### D3 通过的图中观察到的 SlithIR 缺失

DAppSCAN 开发单元 cp3_19463 的三条选版规则都用 solc 0.8.4 编译成功，生产 Slither 均通过 D3(a)/(b)。在对应的开发日志窗口，Slither 分别三次报告 OracleRef.readOracle 和继承该函数的 BalancerLBPSwapper.readOracle 生成 IR 时发生 AttributeError。三份图中该函数各有 19 个节点，存下的 RETURN 节点没有 IR。该窗口内只有这个单元的图含对应源文件中的函数。Slither 0.11.6 会捕获这种异常、标记合约并继续构图。根据用户确认，本文的通过数均按原 D3 统计。单个空 IR 节点本身不足以证明生成中断，现有计数也无法给出全部图的 IR 完整率。逐项日志、图哈希与决定见 partial_ir_review.json 和 partial_ir_decision.json。

### 开发测量中断与计时

原开发进程在 6,940/6,948 份完整收据后结束。下一项 cp3_30233 / oldest 留有 31 份 solc 调用记录，另 7 项没有工作目录。原生输出与内核日志未给出进程退出原因。其后两个 WSL 启动检查确实返回 0x8007274c，现有证据无法把先前的进程退出归因于这个错误。用户已批准这 8 项在独立目录限定执行一次。完整开发观测的耗时按逐项收据加总，先前中断项的调用时间单列。旧收据、清单及授权见 development_interrupt.json 与 development_continuation/。

### 使用测试集前的选版记录

真实开发集 D3 成功数为 closest 1130/2316，latest 1130/2316，oldest 1131/2316。按照开发集的主次指标固定 `oldest`，每个单元最多实际编译 21 个依赖版本组合。该上限覆盖所选规则在所有成功开发单元中实际尝试的组合。规则固定时的开发证据、并列情况及原始测量摘要保存在 `policy.json`，SHA256 为 `570ef7759a983e8b7d0a9e64f04a090e0cda0a4c971ce6d3308df1058039da34`。测试集和遮蔽锁版本的参照均在此记录之后运行。

失去原交互进程后，逐项核对了 6,940 份结果与 6,940 份修复步骤的 SHA256，共 474,552,564 字节。经授权单独重启 Ubuntu，实测 Windows 与 Ubuntu 均能经既有代理取得预期出口，直连均被阻断。用于启动的用户会话缺少 D-Bus，总线调用在实验开始前退出。后续工作改在独立的普通用户 tmux 中执行，原调用顺序、设置和 D3 判据沿用。收据见 development_continuation/recovery_summary.json。

冻结策略后的首轮回归中，独立进程遗漏了 TREE_SITTER_LIB_DIR。production 有 551 项通过，mando 有 519 项通过、32 项跳过，两者均停在冻结的 846 源码等价性测试。CP0 记录的 450,136 字节既有语法库已核对 SHA256。用户批准显式传入该目录并在新目录各运行一次完整套件。失败日志与环境续作分别见 frozen_suites/ 和 test_environment_resume_v2/。

逐单元配对后，2,316 个真实开发单元中有 1,130 个在三条规则下均通过 D3，1,185 个均未通过。唯一结论不同的是 cp3_20546，仅最旧优先通过。此项解释了规则间相差的 1 个成功单元，具体候选次数、发布版和三份收据的 SHA256 见 dev_rule_overlap.json。

### 移动文件的目标路径与 exact

400 个移动样本中，开发集 40/94、测试集 149/306 完成修复并通过 D3。这 189 项中，每一项实际接受的导入都指向其真值中记录的移动目标。188 项的保留节点、CFG 边、调用均完全匹配，且没有丢失或新增节点。其中 187 项在导入方改写了路径，新增字节落在原损坏区间邻近范围之外，按冻结评分仍为 exact=false。开发集 exact 为 0/94，测试集为 1/306。把文件原样移回的独立自检为 400/400 exact。逐单元对照见 moved_path_outcomes.json。

全量运行时新 WSL 命令再次返回 0x8007274c，独立的 /bin/true 在 30.14 秒后报告同一错误，内核仍记录 Relay 等待 vsock。原 tmux 中两个分片继续写入。通过共享目录恢复只读核验，并核对 Windows Git 所见分支、基线提交、仓库身份设置和生产文件哈希。该通道可在保留现有会话的条件下完成本地交付。详见 test_environment_resume_v2/launcher_recurrence.json。

真实外部语料按冻结的项目组划分后，开发集通过 D3 的单元为 1,131/2,316，测试集为 4,749/6,822。14 个达到组合上限的单元都在测试集。逐项匹配入口 SHA256 后，开发集 2,316 项的 D3 成败均与最旧优先的无上限测量一致。两张原始表的哈希与分组计数见 external_split_summary.json。

### 开发选版与每单元组合上限

固定规则为 `oldest`，每个单元最多实际编译 21 个依赖版本组合。以三个规则在真实开发集上的 D3 成功数为首要指标，缺包开发样本的编译、主 kept 和库文件字节用于次级比较。K 取所选规则下全部成功开发单元实际编译的最大组合数，覆盖其检查过的每个位置。

| 规则 | 真实开发集 D3 | 实际编译组合总数 | 基准成功 / 8 | 主 kept | 相同库文件 |
| --- | --- | --- | --- | --- | --- |
| closest | 1130/2316 | 1617 | 7 | 213/232 | 1/23 |
| latest | 1130/2316 | 1460 | 7 | 213/232 | 1/23 |
| oldest | 1131/2316 | 1323 | 7 | 213/232 | 2/23 |

各单元的首个成功位置、实际尝试清单、耗时及分布见 `real_dev.jsonl` 与 `policy.json`。

下表统计第 3 步记录了耗时、实际编译组合数为 0 的开发运行。时间包含依赖筛选、组装及收据写入。K 只限制实际编译次数。

| 规则 | 运行数 | 第 3 步累计秒数 | 最长单次秒数 |
| --- | --- | --- | --- |
| closest | 1105 | 356.51 | 150.83 |
| latest | 1105 | 355.1 | 149.51 |
| oldest | 1105 | 360.78 | 153.93 |

### 冻结规则后的损坏基准

下表采用汇总分子和分母。CFG 边和调用的分母是保留事实的并集。逐单元均值、改动等级、逐样本分数见 `benchmark_summary.json` 与 `benchmark.jsonl`。

| 划分 | 算子 | 单元 | 编译及 D3 | 主 kept | 存活 kept | 主 CFG | 存活 CFG | 主调用 | 存活调用 | 修复删除 | exact |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| dev | closure_version_conflict | 78 | 0 | 0/23951 | 0/23951 | 0/19752 | 0/19752 | 0/10379 | 0/10379 | 0 | 0/78 (0.0%) |
| dev | io_error | 91 | 0 | 0/29392 | 0/29392 | 0/24166 | 0/24166 | 0/12911 | 0/12911 | 0 | 0/91 (0.0%) |
| dev | missing_relative_file | 90 | 0 | 0/19177 | 0/19177 | 0/15946 | 0/15946 | 0/8429 | 0/7754 | 0 | 0/90 (0.0%) |
| dev | missing_relative_file_moved | 94 | 40 | 12042/24476 | 12042/24476 | 9568/19856 | 9568/19856 | 5194/10676 | 5194/10676 | 0 | 0/94 (0.0%) |
| dev | unresolved_package_import | 8 | 7 | 213/232 | 213/232 | 161/174 | 161/174 | 123/137 | 84/92 | 0 | 0/8 (0.0%) |
| test | closure_version_conflict | 322 | 0 | 0/69743 | 0/69743 | 0/60339 | 0/60339 | 0/28567 | 0/28567 | 0 | 0/322 (0.0%) |
| test | io_error | 309 | 0 | 0/66886 | 0/66886 | 0/57532 | 0/57532 | 0/27298 | 0/27298 | 0 | 0/309 (0.0%) |
| test | missing_relative_file | 310 | 0 | 0/60885 | 0/60885 | 0/51255 | 0/51255 | 0/26503 | 0/25149 | 0 | 0/310 (0.0%) |
| test | missing_relative_file_moved | 306 | 149 | 24137/77682 | 24137/77682 | 20800/67253 | 20800/67253 | 9276/33347 | 9276/33347 | 0 | 1/306 (0.3%) |
| test | unresolved_package_import | 106 | 94 | 3929/5836 | 3929/5836 | 4451/4853 | 4451/4853 | 1832/3650 | 1394/3097 | 0 | 2/106 (1.9%) |

standard JSON 包装的统计如下。

| 划分 | 单元 | 编译及 D3 | 恢复节点 | lost | added | exact |
| --- | --- | --- | --- | --- | --- | --- |
| dev | 189 | 189 | 18272 | 0 | 0 | 77/189 (40.7%) |
| test | 761 | 761 | 71202 | 0 | 0 | 323/761 (42.4%) |

| 划分 | 算子 | 名称状态 | 改动等级 |
| --- | --- | --- | --- |
| dev | closure_version_conflict | rejected 78 | none 78 |
| dev | io_error | rejected 91 | none 91 |
| dev | missing_relative_file | rejected 90 | none 90 |
| dev | missing_relative_file_moved | identical 27、rejected 54、verified 13 | none 48、rewrite 46 |
| dev | standard_json_input | identical 189 | none 189 |
| dev | unresolved_package_import | identical 2、rejected 1、verified 5 | additive 8 |
| test | closure_version_conflict | rejected 322 | none 322 |
| test | io_error | rejected 309 | none 309 |
| test | missing_relative_file | rejected 310 | none 310 |
| test | missing_relative_file_moved | identical 107、rejected 158、verified 41 | none 146、rewrite 160 |
| test | standard_json_input | identical 761 | none 761 |
| test | unresolved_package_import | identical 34、rejected 28、verified 44 | additive 95、none 11 |

| 缺包划分 | 字节相同文件 | 原库文件 | 比例 |
| --- | --- | --- | --- |
| dev | 2 | 23 | 0.087 |
| test | 66 | 398 | 0.1658 |

第 2–4 步利用项目内文件、离线发布版和可验证的导入路径。这三个步骤通常保留删除源文件、无效 I/O 路径和修改 pragma 所致的失败。三个对照算子共有 0 个成功样本。原改动和逐条路径依据见 `benchmark_summary.json` 的 `negative_control_successes`。

本轮三个对照算子中，因项目内已有同名文件而成功的样本为 0 个。

### 真实语料与锁版本参照

9,138 个原主因目标中有 5880 个通过生产 D3，14 个触发实际编译组合上限。下表按最后接纳步骤和本次使用的最低身份等级统计。

| 语料 | 最后步骤 | 身份 | 单元 | D3 | 截断 |
| --- | --- | --- | --- | --- | --- |
| DAppSCAN | 1 | no_release | 2109 | 0 | 8 |
| DAppSCAN | 2 | T3 | 20 | 10 | 0 |
| DAppSCAN | 2 | no_release | 612 | 569 | 0 |
| DAppSCAN | 3 | T1 | 73 | 73 | 0 |
| DAppSCAN | 3 | T3 | 4791 | 4161 | 6 |
| DAppSCAN | 4 | T3 | 12 | 4 | 0 |
| DAppSCAN | 4 | no_release | 77 | 23 | 0 |
| SOChecker | 1 | no_release | 14 | 0 | 0 |
| SOChecker | 3 | T3 | 19 | 17 | 0 |
| Trace_on_chain | 1 | no_release | 40 | 0 | 0 |
| Trace_on_chain | 2 | no_release | 369 | 369 | 0 |
| Trace_on_chain | 4 | no_release | 1 | 1 | 0 |
| Trace_repo | 1 | no_release | 293 | 0 | 0 |
| Trace_repo | 2 | no_release | 7 | 5 | 0 |
| Trace_repo | 3 | T3 | 701 | 648 | 0 |

73 个 T1 单元来自同一测试项目。三种规则都在隐藏版本和清单范围后运行，参照分母包括未修复的单元。

| 规则 | 参照数 | D3 | 同锁版本 | 同版本或闭包文件字节相同 | 截断 |
| --- | --- | --- | --- | --- | --- |
| closest | 73 | 73 | 8 | 10 | 0 |
| latest | 73 | 73 | 8 | 10 | 0 |
| oldest | 73 | 73 | 70 | 73 | 0 |

另按成功单元实际接受的步骤计数。一次修复可先后采用多个步骤，所以下表各行不能相加作为成功总数。

| 语料 | 接受的步骤 | 最终通过 D3 的单元 |
| --- | --- | --- |
| DAppSCAN | 2 | 652 |
| DAppSCAN | 3 | 4248 |
| DAppSCAN | 4 | 30 |
| SOChecker | 3 | 17 |
| Trace_on_chain | 2 | 369 |
| Trace_on_chain | 4 | 1 |
| Trace_repo | 2 | 7 |
| Trace_repo | 3 | 648 |

按 CP3.1 对同一批 31,307 个输入重新统计，可计量分母由 31048 至 31048。修复前有 9825 个失败单元，修复后有 3945 个。一个单元可有多个主因。语言排除项和未测单元分开留存在 `external_summary.json`。

| 剩余主因 | 修复前 | 修复后 |
| --- | --- | --- |
| abi_coder_required | 0 | 0 |
| closure_version_conflict | 4 | 4 |
| codegen_only | 39 | 62 |
| compiler_exception | 0 | 0 |
| declaration_error | 2 | 2 |
| docstring_error | 0 | 0 |
| duplicate_definition | 19 | 24 |
| encoding | 0 | 0 |
| fatal_error | 0 | 0 |
| file_level_member | 9 | 9 |
| internal_compiler_error | 0 | 0 |
| io_error | 28 | 28 |
| json_error | 0 | 0 |
| missing_base_contract | 2 | 2 |
| missing_relative_file | 412 | 357 |
| multiple_license_or_pragma | 8 | 8 |
| non_solidity_input | 0 | 0 |
| other | 0 | 1 |
| parser_error_other | 267 | 268 |
| pragma_missing_semicolon_candidate | 0 | 0 |
| slither_incomplete | 24 | 24 |
| slither_no_timeout | 0 | 0 |
| standard_json_input | 410 | 40 |
| syntax_error | 1 | 1 |
| type_error_other | 11 | 49 |
| unbalanced_structure | 64 | 64 |
| undeclared_identifier | 25 | 40 |
| unimplemented_feature | 0 | 0 |
| unresolved_package_import | 8454 | 2804 |
| unsupported_disjunction | 1 | 1 |
| unsupported_expression | 4 | 4 |
| unterminated_pragma | 1 | 1 |
| version_dependent | 219 | 219 |
| version_mismatch | 0 | 0 |
| warning | 0 | 0 |


### CP5.1 最终验收与资源

真实语料 5880/9,138 通过 D3，其中 14 个触发编译组合上限。基准开发集 236/550、测试集 1004/2114 通过编译和 D3。 外部全量与基准合计核验 24766 个候选轮，包含被拒绝的轮次。其中新增文件编辑 267614 次，导入字符串改写 1029 次。未改变的输入按原始文件 SHA 复核。各阶段和逐项调用收据索引见 `*_provenance.json`、`invocation_seals.json`。

D3 检查编译、节点映射和合约覆盖。开发单元 cp3_19463 的 readOracle 出现 SlithIR 生成中断。冻结规则下该单元的整图 SHA256 与开发阶段确认的部分 IR 图一致。可核对的单元收据与各阶段原生日志的独立事件数见 partial_ir_summary.json。同一单元或未接受的候选均可多次产生日志，无法据此估计全部成功图的 IR 缺失率。

最终 MANDO CLI 加载完整离线索引。843 张图与 v5 逐字节相同，3 项历史失败保留，成功图触发第 2–4 步 0 次。实施文件仍为 18 个。354 项 DFG 引用与基线一致。最终测试为 dfg 为 2653 passed, 9 warnings in 273.57s (0:04:33)。mando 为 667 passed, 486 skipped in 50.98s。production 为 1147 passed, 6 skipped in 150.28s (0:02:30)。

| 生产文件 | 增加行 | 移除行 | 改动函数 |
|---|---|---|---|
| evaluation/benchmark.py | 54 | 6 | `_sample_edits`, `assess_mutation`, `build_mutation`, `classify_trigger`, `dependency_repair_observation`, `mutation_sites`, `relative_move_site` |
| evaluation/report.py | 6 | 0 | `dependency_benchmark_summary` |
| pipeline.py | 42 | 9 | `_environment`, `repair`, `repair_unit` |
| rules/dependencies.py | 6 | 3 | `dependency_choices`, `manifest_identities` |
| toolchain/solc.py | 11 | 4 | `validate_settings` |

| 阶段 | 秒 |
|---|---|
| 新增 400 个移动样本的触发与逆操作 | 498.54 |
| 真实开发集三规则，有效单元耗时之和 | 8899.42 |
| 8 个缺包开发样本的三规则 | 24.4 |
| 冻结策略的完整基准 | 1071.24 |
| 锁版本遮蔽参照 | 387.62 |
| 9,138 个外部单元，两分片工作进程耗时之和 | 20183.77 |
| 最终 MANDO 回归 | 346.37 |

开发耗时为 6,948 份完整观测各自的墙钟时间之和。中断前另有 31 次 solc 调用，其耗时之和为 0.13 秒，单独留存。两个外部语料分片分别记录并作加总。正式阶段边界与逐条命令见 `test_environment_resume_v2/stage_runs.jsonl`，首轮停点留在原 `stage_runs.jsonl`。CPU 本地执行，LLM 调用 0，费用 0 美元。


## CP5.2

### 问题、基线与判据

从 `fba94f1d` 执行 PROMPTS r2.24 §4.6i。依赖发布版继续按 oldest 选择，每个单元至多实际编译 21 个候选组合。D3 继续衡量 solc 成功、Slither 构造、节点来源映射和合约覆盖；项目另有既有的绑定与重名检查。完整分母按本节各表定义。修改 AI 为 Codex。

### 313 个漏修单元

| CP5.1 来源 | 单元 | 新进入的文件有失效相对导入 | 候选筛选失败或不唯一 | 已接受路径修正、仍有其他编译错误 | 其他 |
|---|---:|---:|---:|---:|---:|
| 旧移动算子 | 211 | 180 | 31 | 0 | 0 |
| 真实语料中至少有一个唯一符号候选的失败单元 | 102 | 12 | 59 | 4 | 27 |

180 个移动样本中有 141 个符合链式改写的严格条件，另 39 个至少有一个新路径越过项目根，工具记为 `io_error/import_outside_project`。真实语料有 12 个单元、17 个被拒轮次符合严格条件。单次改写后最多新增 9 个物理文件，错误数可由至多 14 个增至至多 24 个；限长 4 是 §4.6i 建议的计算上限，本次没有据此估计最优链长。典型单元为移动样本 `cp3_14630` 和真实项目 `cp3_05855`。

在 31 个候选筛选失败的移动样本中，30 个缺少符号依据，1 个没有共同支持的 pragma。真实语料的 59 项中，11 项的文件名忽略大小写仍没有匹配，41 项遇到符号筛选，14 项遇到 pragma 筛选，26 项出现并列最优路径；各类可重叠。4 项已接受路径修正后的剩余主因为 `type_error_other`。其余 27 项中，18 项只余包导入或在新闭包中暴露包导入，4 项同时暴露包导入和相对导入，3 项暴露解析错误，1 项暴露未声明标识符，1 项遇到 Slither 不完整。每项保留独立归因。数据见 `artifacts/cp5_2_v1/diagnosis_details.json`、`diagnosis_details.jsonl` 和 `filter_breakdown.json`。

### 链式修复与文件级评分

第 4 步逐个验证被改写的导入确实解析到了所选文件，并按物理文件识别新进入的闭包成员。只有新出现的问题全部来自这些文件的缺失相对导入时，才临时继续。最多尝试 4 轮，最终必须成功或比链开始时少了阻塞错误；否则全部回滚。各轮的路径搜索、改动范围、前后错误数和最终决定保存在单元收据。v2 移动算子使用与旧算子相同的配对抽样顺序，仅重写被移动文件自身的相对路径字面量，并保留逆向编辑及偏移映射。

| 在同一份 CP5.1 修复输出上重算 | 单元 | 原 exact | 新 exact |
|---|---:|---:|---:|
| 旧移动算子 | 400 | 1 | 181 |
| 缺包 | 114 | 2 | 2 |
| 标准 JSON 包装 | 950 | 400 | 950 |

新增的文件级评分范围限于真值中实际指向受损文件的导入字面量。导入方另一个位置发生的字节插入须在故意错误测试中得到 `exact=false`。550 个包装样本的图级差异均为 `schema` 从 `compile-repair-graph-v1` 变成 `compile-repair-project-graph-v1`。仅略去该字段，550 项仍因显式和隐式文件标识不同而无法逐节点对应。按用户批准的规则先验证唯一物理源文件和相同源码 SHA，再对齐外层文件身份，复查全部节点、声明、CFG 边和调用。549 对原始图事实一致；`cp3_23979` 另有 11,199 字节创建码中的 32 字节处于可验证的终端 solc 元数据内，沿用 CP4 已有规则后相同。原始图与原分均可追溯。数据见 `benchmark_scores.json`、`wrapper_graph_summary.json` 和 `wrapper_representation_review.json`。

### 移动 v2 的配对实验

| 划分 | 抽样 | 预期错误触发 | 精确逆向还原 | 修复通过 D3 | 原邻域 exact | 新邻域 exact |
|---|---:|---:|---:|---:|---:|---:|
| 开发 | 94 | 94 | 94 | 83 | 0 | 83 |
| 测试 | 306 | 306 | 306 | 280 | 3 | 276 |
| 合计 | 400 | 400 | 400 | 363 | 3 | 359 |

抽样沿用 20261122、原有项目划分和原移动算子的排序命名空间，每语料上限 200。DAppSCAN 有 6,139 项适用，Trace 有 920 项适用；最终 400 项全部与旧版移动样本配对。363 个修复成功中有 4 个未达到 exact。1 项节点无法完全对应，1 项计数器定义的映射未能验证，2 项 Yul switch 的来源编号未能验证。这四项均保留实测分。对应单元、图哈希和指标见 `continuation/v2_scoring_details.json`。

| 400 个触发样本的全图评分 | kept | CFG 边 | 调用 |
|---|---:|---:|---:|
| 全部 400 个，主指标 | 0.806036 | 0.814313 | 0.754838 |
| 全部 400 个，存活部分 | 0.806036 | 0.814313 | 0.754838 |
| 其中通过 D3 的 363 个，主指标 | 0.988678 | 0.999972 | 0.952242 |
| 其中通过 D3 的 363 个，存活部分 | 0.988678 | 0.999972 | 0.952242 |

kept 按匹配节点数和真值分母汇总。CFG 边与调用按多重集交集除以并集计算；分子、分母、丢失与新增节点总数见 `acceptance.json`。

### 同一管线重跑 CP5.1 基准和真实单元

| 基准算子 | 单元 | CP5.1 D3 | CP5.2 D3 | D3 与图 SHA256 均相同 |
|---|---:|---:|---:|---:|
| `closure_version_conflict` | 400 | 0 | 0 | 400 |
| `io_error` | 400 | 0 | 0 | 400 |
| `missing_relative_file` | 400 | 0 | 0 | 400 |
| `missing_relative_file_moved` | 400 | 189 | 279 | 310 |
| `standard_json_input` | 950 | 950 | 950 | 950 |
| `unresolved_package_import` | 114 | 101 | 101 | 114 |

旧移动算子新增 90 个通过 D3 的样本。90 项均经两轮改写，并改动了被移动文件自身的出向导入。该位置超出本步新增的入向导入字面量范围。89 项的 kept、CFG 边、调用三个指标均为 1，另 1 项的 Yul switch 来源编号未能验证；这 90 项均保留 exact=false。见 `continuation/old_move_recoveries.json`。

| 外部语料范围 | 单元 | CP5.1 D3 | CP5.2 D3 | 新增通过 | 原通过后失败 | D3 与图 SHA256 均相同 |
|---|---:|---:|---:|---:|---:|---:|
| 全量 | 9138 | 5880 | 5882 | 2 | 0 | 9136 |
| 含缺相对文件 | 412 | 42 | 44 | 2 | 0 | 410 |
| 含 I/O 错误 | 28 | 0 | 0 | 0 | 0 | 28 |
| 两者并集 | 424 | 42 | 44 | 2 | 0 | 422 |
| 其余单元 | 8714 | 5838 | 5838 | 0 | 0 | 8714 |

子集由冻结的初始主要原因决定，缺相对文件和 I/O 错误两行有交集。历史评分对照只改变评分；这两张重跑表使用实际重新运行的工具结果。逐项核对见 `continuation/benchmark_rerun.jsonl` 与四份 `continuation/real_??.jsonl`。

### 生产 Slither 的部分 IR

| 范围 | 单元 | 有任一标记的单元 | 被标记的合约实例 | 顶层函数错误条数 | 与原图一致的单元 |
|---|---:|---:|---:|---:|---:|
| 真实开发集 CP5.1 成功项 | 1131 | 4 | 6 | 0 | 1131 |
| CP5.1 基准成功项 | 1240 | 0 | 0 | 0 | 1240 |
| MANDO 成功项 | 843 | 0 | 0 | 0 | 843 |
| 按语料、编译器小版本分层的 CP3 成功基础单元 | 1000 | 0 | 0 | 0 | 1000 |

合约实例按每次构图计数，各范围单独统计。MANDO 核对完整图字节，其余三组对照加溯源标记前的原生图事实及哈希。`cp3_19463` 的 `BalancerLBPSwapper` 与 `OracleRef` 均有标记，顶层函数日志为 0，该次回放的图事实与原记录相同。D25 待用户决定；本步记录观测，D3 沿用既有定义。711 个历史项目使用原编译器、原目录及原设置，另行实测了绝对项目根参数；每项的预登记、成功的 solc 收据和原参数都已核对。其余 2,660 份开发、基准和 CP3 回放使用原成功编译收据。

### 回归、资源与封存

MANDO 846 项中，843 份成功图逐字节等于 v5，另 3 项保留原有失败状态。对 18 个生产文件在每套测试运行前后核对了 SHA256。production 模块 1,155 项通过、6 项跳过；mando 模块 671 项通过、490 项跳过；DFG v2 2,653 项通过，9 条警告。354 个 DFG 代码引用与冻结基线相同。
四个生产文件的变动合计增加 278 行、删除 38 行。逐文件函数名与行数见 `code_audit.json`，阶段用时见各 `*_exit.json`。本地 CPU 运行，下载 0，训练与外部 LLM 调用均为 0，费用 0 美元。首轮封存测试的并发编辑失败、收据定位修正、原始导入路径与允许路径差异以及用户原话见 `docs/DECISIONS.md` 的 CP5.2 节。

| 生产文件 | 新增行 | 删除行 | 变动函数 |
|---|---:|---:|---|
| `evaluation/benchmark.py` | 176 | 23 | `_correspondence`、`_sample_edits`、`_single_file_wrapper_graph`、`assess_mutation`、`build_mutation`、`classify_trigger`、`dependency_repair_observation`、`file_damage_import_spans`、`mutation_sites`、`relative_move_v2_site`、`score_dependency_repair`、`score_graphs`、`score_request` |
| `pipeline.py` | 33 | 12 | `repair_unit` |
| `rules/dependencies.py` | 42 | 2 | `chain_relative_issues`、`relative_repairs` |
| `toolchain/slither.py` | 27 | 1 | `_TopLevelIRLog.__init__`、`_TopLevelIRLog.emit`、`run_slither` |
