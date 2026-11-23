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
