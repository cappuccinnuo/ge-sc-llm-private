# CP5.1 编译修复验收

输入提交为 `5fe7671f`，使用 PROMPTS r2.23。原始语料、发布版和运行工作副本只保存在仓库外。生产工具为 Python 3.10、Slither 0.11.6、crytic-compile 0.4.2 和冻结的 92 个受支持 solc 版本。本批只做 CPU 编译与图评估。

| 核验内容 | 文件 |
|---|---|
| D24 与 23 版续传的范围 | `authorization.json`，`d24_tests.log` |
| TLS 断开及 167 份离线复核 | `download_remaining.jsonl`，`transport_stop.json`，`last_five_authorization.json` |
| WSL 启动与一次受保护执行的停点 | `launcher_stop.json`，`launcher_health.json`，`launcher_authorization.json`，`guard_stop.json` |
| 5 版显式代理与最终 172 版核验 | `configured_five/authorization.json`，`configured_five/receipts.jsonl`，`download_summary.json`，`index_verification.json` |
| 9,138 个真实单元与数据划分 | `population.py`，`population.json`，`population.jsonl.gz` |
| 两类真实导入的项目内候选 | `path_census.json`，`path_census.jsonl` |
| 新移动算子的抽样、触发和逆操作 | `moved_sampling.json`，`moved_plan.json`，`moved_triggers.jsonl`，`moved_inverse.jsonl`，`moved_summary.json` |
| 缺包开发基准的三规则对照 | `package_dev_summary.json`，`package_dev.jsonl` |
| 版本选择、截断与已接纳字节的核验程序 | `evaluate_units.py`，`evaluate_benchmark.py`，`evidence.py`，`driver_fixture_checks.json` |
| 三个回归套件、原图及生产代码范围 | `suites/`，`final_suites/`，`mando_regression/summary.json`，`checkpoint_audit.json` |

`configured_five/receipts.jsonl` 的每一行对应一个原清单 URL。原执行的预登记与空收据完整保留。正式索引位于工作树旁的 `corpora/compile-repair-npm-cp5-v1/index/`。可用 `index_verification.json` 核对 172 个发布版、13,073 个 Solidity 文件和索引摘要。发布版归档与提取源码保留在本地。

图真值、逆操作的编译结果及库文件候选的完整工作副本位于 `compile-repair-local/cp5_1_v1/`。逐项收据提供路径、SHA256 和真实状态。各算子的失败样本计入分母。版本选择只使用开发集，锁版本遮蔽对照在规则固定后取数。

开发集的原生 SlithIR 报错及其与三个已接受图的对应关系见 partial_ir_review.json。用户决定和该文件的 SHA256 见 partial_ir_decision.json。各表的 D3 沿用既定定义。

开发前缀的顺序、停点与原始 SHA256 见 development_interrupt.json。development_continuation/ 保存限定授权、前缀核验与后续八项的清单。正式开发表由两个有序部分组成。

WSL 启动故障、限定重启授权、活动网络验证与专属工作进程分别见 development_continuation/wsl_health_review.json、wsl_restart_authorization.json、recovery_summary.json 和 service_claim.json。Windows 完整出站例外列表需要管理员权限，本轮另存了默认阻断策略与实际连通性验证。

冻结策略的首轮测试停点在 evaluation_stop.json 和 frozen_suites/。后续测试使用已核验的原语法库，独立停止标志和运行记录放在 test_environment_resume_v2/。

verify_moved_targets.py 可用已有收据核对移动算子的导入目的地。moved_path_outcomes.json 保存 400 个单元的真值路径、实际选择、图指标和结果摘要。

### 正式验收

正式默认规则为 `oldest`，K=21。 真实语料 5880/9,138 通过 D3，其中 14 个触发编译组合上限。基准开发集 236/550、测试集 1004/2114 通过编译和 D3。

| 内容 | 文件 |
|---|---|
| 选版、K 与逐单元未截断观测 | `policy.json`、`policy_application.json`、`real_dev.jsonl` |
| 完整基准、负对照成功样本 | `benchmark_summary.json`、`benchmark.jsonl`、`final_tables.md` |
| 真实单元、分类及 73 项锁版本参照 | `real_full.jsonl`、`real_masked.jsonl`、`external_summary.json` |
| 原始字节、导入字符串与逐轮收据 | `*_provenance.json`、`invocation_seals.jsonl.gz` |
| 最终代码、测试和 MANDO 图回归 | `final_audit.json`、`test_environment_resume_v2/suites/`、`frozen_mando/summary.json` |
| D3 与 SlithIR 缺失的独立记录 | `partial_ir_review.json`、`partial_ir_decision.json`、`partial_ir_summary.json` |
| 正式阶段用时及批次封存 | `test_environment_resume_v2/stage_runs.jsonl`、`measurement_completion.json`、`seal.json` |

Git 以无损 gzip 保存 5 份较大的 JSONL 表。解码前后 SHA256 和字节数在 `record_archives.json`。新检出需要原始表时，可从仓库根目录运行 `python -B compile_repair/artifacts/cp5_1_v1/record_archives.py restore`。该入口只还原清单中的本地表，已有文件先核验字节。原生编译与分析日志可能带有第三方源码表达式，仅供本地研究。各本地日志的路径、长度和 SHA256 见 `partial_ir_summary.json`。
