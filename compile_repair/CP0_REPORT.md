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
