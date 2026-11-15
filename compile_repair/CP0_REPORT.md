# CP0：前置核验与工具封装检查点（尚未完成全量验收）

修改 AI：Codex。2026-11-12（America/New_York）。状态：`blocked_missing_compilers`。唯一必需缺口为 solc 0.4.17，按 PROMPTS r2.1 §4.2.3 停止；本报告不表示 CP0 通过审查。

## 实现

- `compile_repair/__init__.py`
- `compile_repair/cli.py`
- `compile_repair/core/__init__.py`
- `compile_repair/core/model.py`
- `compile_repair/evaluation/__init__.py`
- `compile_repair/evaluation/survey.py`
- `compile_repair/toolchain/__init__.py`
- `compile_repair/toolchain/slither.py`
- `compile_repair/toolchain/solc.py`
- `compile_repair/tests/test_layering.py`
- `compile_repair/tests/test_survey.py`
- `compile_repair/tests/test_toolchain.py`
- `compile_repair/tests/fixtures/counter.sol`

9 个生产模块均在 §3.10 允许的目录表内。core 只保存数据；solc 校验可信二进制、构造 crytic 同口径命令并保留真实退出码；slither 复用冻结 `_compile`，检查全部声明函数/修饰器节点、保存有序 IR 与 key4 多重集合；survey 完成身份、metadata、历史差异和安装清单核验。CLI 只解析和派发。源码、旧证据、scripts/**、EdgeSem、根目录交接/训练改变文档均未修改。

本次未实现编译矩阵和升降序 D3 选版的调查编排。缺口出现后按原 Prompt 停在前置阶段，工具封装通过小合约测试；不得把现有 survey 当作完整 CP0 或 CP1 repair 命令。

文档新增 `RECON.md`、本报告；追加 `PROGRESS.md`、`docs/CHANGE_LOG.md`；更新 `docs/HANDOVER.md` 当前状态并追加 §6；更新 `docs/DECISIONS.md` 的 D15、登记待确认 D16。全部数字、17 个异常文件、版本缺口清单及关键差异详见 `RECON.md` 与 `artifacts/cp0_v1/recon.json`。

复用函数而未复制冻结实现：`frontend.parse`、`versioning.interval/recorded_version`、`validate_slither.inspect_environment/compiler_for_selection/_compile`、`auto_version_solc.get_solc_version`。`inputs._check_metadata` 先阅读，实际来源校验使用等价职责的 `recorded_version`；registry 只读 AST 字面量，不载入 labels/graph loaders。冻结源文件哈希：

| 文件 | SHA256 |
|---|---|
| `auto_version_solc.py` | `5b701860825c58e2e5d7b1e46c4780ec4119f965b9dbf3f228eb5227685ac121` |
| `scripts/DFG/dfg_v2/experiment/run.py` | `3670d4e6b7e953ec705e9863e5011b518a111bf74007be2a3a4e5833a3e5da2c` |
| `scripts/DFG/dfg_v2/inputs.py` | `7a1d1b2a488b6083095811519c46f1a1207b87e1b535a7c9e4e58eaaced6d109` |
| `scripts/DFG/dfg_v2/tasks.py` | `139b8835680e52e3c8b1be12546142ea2ec8ff87017d78aaf17c79ed3cf48fc2` |
| `scripts/DFG/dfg_v2/validate_slither.py` | `4f3dde9c48063a48f9dd3b0011bda8dab410186682d4bce82b48414f56caa3a8` |
| `scripts/DFG/frontend.py` | `cfe6ee2a975abeb374e2ce17f0f7c47c400e823cfa8ca05c96d3e4657d161207` |
| `scripts/DFG/state/stage_f/versioning.py` | `130251d6a9e46ec176ba183a0a66fa5a30210b43c1ab8faa2bfcf5a676d2ed18` |

## 真实验收

| 验收项 | 预期 | 实际 / 结果 |
|---|---|---|
| 输入集合 | 846 | 846，集合一致；旧 JSON 不含源码哈希，已说明证明边界 |
| 6c 身份匹配 | 256 | 256，按 SHA256 匹配；seal 与报告固定哈希均通过 |
| metadata | 43 | 43 来源校验通过，4 个 ≤0.4.11 |
| 6c 异常核对 | 11+6 | 与旧 A 异常 17 个文件完全一致 |
| 安装清单 | 与可信清单一致 | 26/26 SHA256 一致 |
| 全部文件有可用候选 | 846 | 845 有候选、1 无候选；**已停止** |
| 真实 D3 探针 | 拒绝缺映射 | 0.4.11：rc0/5 个缺 filename/D3失败；0.4.13：rc0/0 个缺失/D3通过 |
| 编译矩阵、全量 D3、升降序及跨版本比较 | 全量统计 | 未实现全量编排、未运行，待补齐环境 |
| CP2 时间估计 | 实测推算 | 未运行，不能以小探针推算全量 |
| 分层/文件上限 | ≤30 | test_layering 通过，9 个生产文件 |
| 冻结引用 | 不变 | `_code_refs()` 354 项不变 |

与原文差异：① 43 metadata 实为 SmartBugs versions.csv，已追加更正，未改 PROMPTS 原文；② 读取两个额外 source manifests 已获用户明确批准并记录 D15；③ 本地缺少必需 0.4.17，旧云环境的 846/846 不能直接套用；④ 6c occurrence 报告不能重建完整 CFG key4/原始 IR，CP2 比较范围建议待审；⑤ 精确 pragma 的覆盖与不越界要求冲突留给 CP1 确认。没有自行采用替代设计。

## 测试与开发记录

- `python -B -m pytest -q -p no:cacheprovider compile_repair/tests`：第二轮 21 passed（0.42 秒），无跳过。实际命令额外指定新的 `--basetemp` 以保留探针 JSON。第一轮 20 passed / 1 failed：测试目录属于 artifacts，因此不该期待被拒绝；修正测试为仓库外目标后通过。两轮日志和真实调用记录全部保留。
- `python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests`：2653 passed，9 warnings（既有 dgl distutils/networkx gpickle 弃用），182.50 秒。只运行一次。
- `git pull --ff-only origin compile-repair` 因 WSL 无法解析 github.com 失败；通过已连接 GitHub 工具只读核对远端分支和本地 HEAD 同为 `068433d0cfa3367fe09cd1f94f78319eeff3c6d0`，未修改网络配置，不声称 pull 成功。
- PowerShell 默认路径/UNC 访问不适合本工作树，改用显式 `wsl.exe --cd`；WSL 无 rg，使用 git/Python 枚举；探索 6c schema 时一次 IndexError 改为 tasks[*].files；首次基线脚本的中文分隔符受 PowerShell 管道默认编码影响，设置 OutputEncoding=UTF8 后解决。开发失败与解决方式记录在 `development_context.json`、`development_issues.json` 和 `development_test_fix_v1.json`。

## 归档与复现

正式产物 `artifacts/cp0_v1/recon.json` SHA256 `e4dfe405a16ca90c962b54996f117e76eb1a17656197062be17196200906bca1`；seal SHA256 `eed04a53213e62a9b1b0fc41cdbd827a6073d4451f093b4de44134b7d5c8b1d0`。原始输入和旧产物只读。开发产物中保留任务前基线、授权范围、测试结果、真实编译/Slither 调用、源码来源和待批准安装请求。

```bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-compile
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
python -B -m compile_repair.cli survey   --output compile_repair/artifacts/cp0_v2   --metadata-authorization compile_repair/artifacts/cp0_development_v1/metadata_read_authorization.json
```

该命令只供批准后的下一轮使用，不在本轮重跑。当前实现遇到缺失版本返回 2 并封存现场；若无版本缺口，非 `--inventory-only` 模式仍返回 `stopped_after_preflight`，因为全量矩阵编排尚未实施，不能把前置通过当作 CP0 完成。`cp0_v1` 已存在，禁止使用它重跑。补齐编译器后还需实现独立追加信任清单的接入、编译矩阵及 D3 选版调查，再使用新批次。


## 停止位置与后续边界

已停止在必需版本缺口，CP0 未完成，CP1 前提不满足。待用户批准单独的 solc 0.4.17 环境补齐；申请文件为 `artifacts/cp0_development_v1/compiler_installation_request.json`，不是安装授权。收到批准后先写授权记录，获取并双校验官方二进制，新增独立可信清单，再补完 CP0 矩阵编排，在全新产物目录验证。可选缺失版本未申请安装。

本轮没有下载、安装、包变更、全局 solc 切换、语料修复、图存储写入、HGT 训练、GPU 锁操作或 LLM 调用，费用 0 美元。文档检查、最终冻结审计及本地提交结果追加在 CHANGE_LOG §4.5；不 push。


## 2026-11-12 续作：按 PROMPTS r2.2 完成基线调查并提交审查（修改 AI：Codex）

以下为续作记录，前文保留第一次缺少 0.4.17 时的检查点。本轮起始本地 HEAD 为 `8fb81ed91a189405df8e8ee7a06a2c3eb3249e47`。`git pull --ff-only` 取得上游 r2.2 提交 `54ecc927c6b277ffcca962c13838cbadcdfa1192`，但因本地检查点与上游分叉而不能快进。合并保留双方历史及原文，四份记录文档的冲突按追加解决；上游 CHANGE_LOG §4 在本地改编号为 §5，原本地安装请求 D16 改编号为 D17，r2.2 的 Slither 兼容性继续使用 D16。PROMPTS 与上游逐字节一致，没有自行改写方案。

### 续作实现

- 修改 `toolchain/solc.py`：读取独立追加信任清单，绑定授权与官方发布快照，复核双哈希和可执行文件路径；按系列输出发布、已安装及未安装版本。原 6c 清单不变。
- 修改 `evaluation/survey.py`：完整候选编译矩阵、规则 A 对照、实验性升降序选版、最低/最高 D3 端点与逐条差异、37 个安装版本的特征探针、CP2 编译和分析耗时估计；逐调用 JSONL 日志与结果 seal。保留失败、超时停止、拒绝覆盖目录。
- 修改 `cli.py`：增加可重复 `--trusted-addition` 参数，只做参数解析与派发。
- 修改 `tests/test_survey.py`、`tests/test_toolchain.py`；新增 `tests/fixtures/compat_04.sol`、`compat_05.sol`、`compat_06.sol`、`compat_07.sol`、`compat_08.sol`、`compat_08_errors.sol`。覆盖授权链篡改、原可信版本禁止替换、官方索引边界、metadata 优先级、JSON 区间往返和 D3 端点失败后的继续选择。
- 文档：合并 r2.2 的 PROMPTS/PROGRESS/DECISIONS/CHANGE_LOG/HANDOVER；本轮另向 RECON、CP0_REPORT、PROGRESS、CHANGE_LOG 追加记录，更新 HANDOVER 当前状态与 DECISIONS，新增 `artifacts/cp0_continue_v1/README.md`。产物分为安装证据、续作开发证据、两个独立小样本现场及正式 `cp0_v2`。

调查沿用冻结 `interval`、`recorded_version`、`inspect_environment`、`compiler_for_selection`、`_compile` 和 crytic-compile `_build_options`，没有复制或 monkeypatch 冻结函数。版本选择在 evaluation 中只服务 CP0 对照，不把待确认 D5 写成已定的通用修复策略。节点比较保留重复次数及 IR 顺序，source length 单列；日志保留 solc 实际退出码和 Slither API 结果，不伪称观察到 Slither 内部子进程的退出码。


### 续作真实验收

正式结果为 `artifacts/cp0_v2/recon.json`，状态 `awaiting_d16`，CLI 退出码 2 是兼容性调查后的受控停止。原始身份核验仍为 846 输入、43 metadata、256 个 6c SHA 对应，元数据来源更正继续有效。完整逐文件列表、版本分布及所有差异在 recon 与两个 JSONL 文件中；详细解释见 RECON §8–11。

| 项目 | 实测 | 判定 |
|---|---|---|
| 官方快照范围 | 0.4.12–0.8.38 共 92 版；范围内安装 33 版，缺 59 版 | 清单完整；不宣称所有补丁已验证 |
| 可信安装 | 原 26 + 新授权 11 = 37 | 所有身份校验通过；全局版本不变 |
| 846 份候选矩阵 | solc 5,391 次，rc0 5,254、rc1 137 | 每次调用有记录，零输入缺候选或 D3 成功版本 |
| 规则 A | 821 通过、22 失败、3 未安装 | 如实保留不可用对照；3 份均有合法替代 |
| 升序选定 D3 | 846/846；缺 filename 节点 0；空 CFG 文件 0 | 通过 |
| 版本变化 | 升降序不同 617；相对 A 移动 44；crossed_minor 0；A 区间外 2 | 已记录 |
| 双版本比较 | 678/678 key4 和有序 SlithIR 一致；650/678 length 一致 | 28 份 length 差异全量保留；另 168 份无第二 D3 端点 |
| 6c 历史异常 | 17/17 现在 D3 通过 | 基线回归成立，未声称重建了 6c 完整图 |
| key4 重复 | 55 份文件 | 多重集合保留；唯一图主键方案待 CP2 审查 |
| 系列兼容性 | 37 版、39 组探针，全部 solc rc0；D3 33 通过、6 失败 | 4 组为 ≤0.4.11 缺映射负对照，2 组为范围内真实缺口 |
| 现代语法缺口 | 0.8.4/0.8.38 自定义错误均报 `Unknown contract item: ErrorDefinition` | **D16 已停止**；同版本基线、try/catch、unchecked 均通过 |
| CP2 时间依据 | 所选 solc 80.853 秒 + Slither 228.587 秒，约 5.16 分钟 | 仅编译/分析，不含 CP2 存储与比较 |

MANDO Slither 共 1,546 次全部 D3 通过；兼容性另有 39 次。正式内部耗时 928.330 秒，包含启动的 CLI 总耗时 932.935 秒；费用 0 美元，CPU 环境 OMP/MKL=2，没有 HGT 训练或 GPU 锁操作。

### 续作测试与开发记录

- `python -B -m pytest -q -p no:cacheprovider compile_repair/tests`：最终 32 passed、0 failed、0 skipped（0.83 秒），日志 `cp0_continue_v1/tests_cp0_v2.log`。首轮 31 passed；随后开发小样本暴露 JSON 列表/元组区间比较错误，修复并新增一条回归测试。首个小样本失败保留于 `cp0_matrix_smoke_v1`，新 `cp0_matrix_smoke_v2` 的六份边界输入全部通过，耗时 6.970 秒；没有覆盖失败现场。
- `python -B -m pytest -q -p no:cacheprovider scripts/DFG/dfg_v2/tests`：2653 passed，9 条既有依赖弃用 warnings，174.88 秒；日志 `cp0_continue_v1/tests_dfg_v2_v1.log`。生产代码修正只涉及本模块区间规范化，冻结测试不重复运行。
- 每次 pytest 实际命令加独立 `--basetemp`，完整命令、退出码和耗时在同名 JSON；只显式提交必要探针 JSON，不提交全部 pytest 临时语料。代码与新 fixture 在正式运行前测试完成，正式运行后未改实现。
- 安装首次 HTTP 403、文档合并、Python 3.7 写入接口、JSON 区间类型及处理均记录在 CHANGE_LOG §6.2 和 `development_issues.json`。没有自动重跑正式 `cp0_v2`；源码诊断初记行号的更正独立保留在 `final_findings.json`。

### 续作归档与停止

- `cp0_v2/recon.json` SHA256：`bddbeaa256192b567525370f8b27335a3d2bdcf3ccb48e22086150718414ffb6`。
- `cp0_v2/seal.json` SHA256：`16dfb47bb17cbcb9da0a1a11b3c02a9cc7e4cfae39717e1d38ed8a3294284a9b`。
- `invocations.jsonl` SHA256：`f0fc471835d9d613b8d61cfd1fcd87e20e9331413ce6ca98341aab8a15f72fb9`；`cross_version.jsonl` SHA256：`8201ce3dba362b99d8a4584568e36f5b80e491f3ed9b52876814f6fb31a4fde3`。
- 精确复现命令见 RECON §11，包含两份追加信任清单，必须使用新的输出目录。原 `cp0_v1` 的 report/seal 未修改；本轮 `_code_refs()` 354 项、846 份输入及全局版本选择不变量通过，来源见 `cp0_continue_v1/freeze_audit_v1.json` 与最终审计。

可继续讨论、但未实施的实质事项只有：① D16，若要面向带自定义错误的现代输入，需要选择兼容工具链，建议独立环境评估并保留 6c 环境；② key4 不是唯一节点主键，且 6c 报告不含 node.type/原始 SlithIR，CP2 的比较与存储标识需审查；③ 精确 pragma 覆盖与不越区间的既有冲突，留 D5/CP1 决定。没有据此擅自更换设计。

CP0 获准调查已完成，尚未通过用户审查，CP1 前提未满足。依 PROMPTS CP0 §5b 在 D16 停止，没有升级 Slither、crytic-compile 或 Python，没有下载其余 59 个补丁、外部语料或文档包，没有编写通用 repair、修改源码、写图存储或调用 LLM。文档检查与最终提交说明见 CHANGE_LOG §6.5；本轮只作本地提交，不 push。
