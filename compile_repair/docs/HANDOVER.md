# CompileRepair 交接文档

> 新接手先读本文第 0–5 节、PROMPTS r2.5（尤其 1.8、3.3 第 3a 条、4.2c）、DECISIONS、CP0_1_REPORT 的 C 续和 CHANGE_LOG §13。第 6 节历史只追加；记录规则见 README.md。

## 0. 一句话

CP0.1 C 续本机验收完成：两次生产 843/843 指纹一致，20/20 mando 回归一致，501/501 兼容性组合符合预期；等待审查，通过后才开始 CP1。

## 1. 当前状态

| 项 | 状态 | 依据 |
|---|---|---|
| 方案与决定 | PROMPTS r2.5；D5 升序、D16 0.11.6/0.4.2、D18 的 59 版安装决定沿用 | DECISIONS |
| 模块 | 9 个生产 Python、6 个测试文件、28 个 Solidity fixture | implementation_audit.json、文件清单 |
| CP0、CP0.1 A/B | 已审查通过，旧结论/产物不变 | 原 review 目录 |
| 原 C 安装 | 59/59 校验通过，支持快照已安装 92/92；本轮无安装 | cp0_1_compilers_v1、v2/coverage.json |
| C 续工具链 | settings 白名单及透传、what 消息和 IR 规范化已实现；regression 拒绝设置 | core/model.py、toolchain/solc.py、slither.py |
| 生产确定性 | 两次各 D3 843/846；同 3 份已知 AssertionError；843 指纹全相同；各 4 行 IR 规范化 | cp0_1_env_v2/production_run*.json |
| 回归样本 | Random(0) 的 20/20 与 A 指纹相同 | regression_sample*.json |
| C 续兼容性 | 501/501 符合预期；491 默认正例 + 5 设置正例 + 5 默认负对照；旧 224 指纹全部相同 | cp0_1_compilers_v2/compatibility.json |
| 测试 | production 506 passed/6 skipped；mando 83/429；DFG v2 2653 passed/9 warnings | cp0_1_env_v2/test_summary.json |
| 下一步 | 审查本次代码/证据/记录；通过后按 §4.3 开始 CP1 | 本轮未开始 CP1 |
| 其他决定 | D9/D10 待确认；D12/D13 待定 | DECISIONS |

## 2. 分支与工作树

- 工作树 /home/zhao/SmartContract/ge-sc-llm-compile，分支 compile-repair；不在 EdgeSem 工作树执行 git。
- 本轮起始 HEAD 为 3742fb75e535b5517ded58659e78737a01b51000，按要求 pull --ff-only 后 Already up to date。前一轮 B/C 提交 33c23a3b 已按用户要求推送；本轮只本地提交，以 git log 的 CP0.1 C continuation 条目定位，不自动 push。
- 生产改动仅 core/model.py、toolchain/solc.py、toolchain/slither.py；新产物仅两个 v2 目录，A/B/原 C 产物和 fixture 不改。

## 3. 环境

```bash
cd /home/zhao/SmartContract/ge-sc-llm-compile
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
/home/zhao/miniconda3/envs/mando/bin/python -B --version
env PYTHONNOUSERSITE=1 /home/zhao/miniconda3/envs/compile-repair-production/bin/python -B --version
```

mando 保持 Python 3.7.12 / Slither 0.8.0 / crytic-compile 0.2.4，只作回归。production 保持 Python 3.10.21 / Slither 0.11.6 / crytic-compile 0.4.2 / solc-select 1.0.4 / tree-sitter 0.20.4 / pycryptodome 3.20.0 / pytest 7.4.4；包及来源沿用 cp0_1_env_v1/environment.json。生产调用必须隔离用户 site-packages，mando 不作安装或设置变更。

可信编译器一律绝对路径，不运行 solc-select install/use；总 96 个二进制，其中 92 个在 0.4.12–0.8.38 支持快照，4 个历史负对照低于下限。新安装/下载必须先获限定授权，本轮没有任何新安装或下载。Windows 仓库操作使用显式 wsl.exe --cd；UTF-8 Python 管道写文档。网络沿用既有代理，无直连回退，本轮只有用户明确要求的 git pull。

## 4. 必读事项（已知的坑）

1. 模块面向未来任意合约输入，MANDO 846 只作回归；不凭语料频率缩减规则范围。CP1 尚未实现。
2. EdgeSem 只允许已授权的 6c 文件只读核验；本轮没有新增读取范围，不在其工作树执行 git。
3. *.json/*.txt 被忽略；按 file_inventory.json 显式 add -f。不要整体暂存 pytest 临时树或二进制。新原始 stderr 以 gzip 无损提交，映射见 log_compression.json。
4. D3 同时要求节点映射与 solc AST 合约覆盖；顶层函数也必须遍历。0.4.11 以下是历史负对照，编译成功不等于 D3。
5. key5 是同函数相同类型/起点的出现序号，不能去重；length 只记录。CP0 投影保留原函数，已独立检查不变。
6. source_mapping 在 0.8.x 为 dict、0.9 起为对象，两个 profile 必须显式选定；不自动接受其他版本。
7. settings 为有序元组，默认空。白名单只有 --evm-version <名称> 与 --via-ir；production 经 solc_args 透传，regression_6c 对非空设置抛错。
8. 0.8.24 的 4 个 Cancun 探针默认失败，加 --evm-version cancun 后通过；0.8.26 require 自定义错误默认 rc2，加 --via-ir 后通过。崩溃原因在 std::exception::what 行，不能只看 Unimplemented feature banner。
9. §3.3 第 3a 条的错误匹配/设置重试顺序在 CP1 实现；本轮只验证显式参数。不能把这 5 个手工设置对照写成自动修复已完成。
10. IR 规范化只去掉限定对象 repr 的内存地址；残留 object at 0x 使 D3(a) 失败，counts/ir_diagnostics 记录位置。两个生产归档各规范化 4 行，其他节点字段不变。
11. 0.11.6 的三个 0.4.24 AssertionError 仍存在；第 10 行源码改写在 CP6，不能把 B 工作副本试验当成生产规则。
12. 501 组矩阵只覆盖新增 59 版；92/92 是可信安装口径，不是所有语法/图语义的穷举保证。0.8.28–0.8.37 本轮已按计划通过。
13. 冻结 versioning 的 tree-sitter 库仍为 /home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64，SHA256 f424e0d52ebcdda4932a973af5357874fedd0348c78d87b1575bf15ee539d967。原 846 区间等价结果保留，不重跑 B。
14. pragma 覆盖仅在区间内无可信可用编译器时考虑；不因分析失败就越过区间。43 份 metadata 来源仍为 SmartBugs versions.csv。
15. production 仍通过公开 CryticCompile/Slither 组合记录实际 solc 平台；不 monkeypatch 冻结代码。
16. 所有旧 artifact 与报告前缀只读；新批次 x/xb 创建，遇首个非预期即停、不自动重试。A/B/原 C 失败证据不可覆盖。
17. 交接/运行与训练改变记录只写 compile_repair/docs，沿用 NodeSem 的五段变更和四段交接格式；完成 doc_check 才提交，不改根目录两份记录。
18. WSL 未安装 rg 时使用现有 Python/sed，不为查找工具安装包。审查 ir_object_repr.json 是两个连续 JSON 对象，按实际格式读取，不改原文件。

## 5. 关键路径

| 内容 | 路径（compile_repair 下） |
|---|---|
| 本轮完整报告与详细记录 | CP0_1_REPORT.md 的 C 续；docs/CHANGE_LOG.md §13 |
| 两次生产与归档 | artifacts/cp0_1_env_v2/production_run1/2.json、对应 invocations 与 node_facts_v2.jsonl.gz |
| 抽样方法与回归 | 同目录 regression_sample_plan.json、regression_sample.json 与归档 |
| 独立归档审计 | 同目录 archive_audit.json、implementation_audit.json |
| 新兼容性计划、结果与覆盖 | artifacts/cp0_1_compilers_v2/compatibility_plan.json、compatibility.json、coverage.json |
| 完整测试 | artifacts/cp0_1_env_v2/test_summary.json、pytest_*.json/log |
| 冻结审计与记录检查 | 同目录 baseline.json、frozen_audit.json、doc_check_*.jsonl |
| 提交清单与封存 | 同目录 file_inventory.json、seal_hashes.json；两批 seal.json |
| 原 B/C 审查与失败现场 | artifacts/cp0_1bc_review_v1/；cp0_1_env_v1/；cp0_1_compilers_v1/ |
| A、CP0 与请求 | artifacts/cp0_1_v1/、cp0_v2/、cp0_1_development_v1/（只读） |

---

## 6. 交接记录

### 2026-11-11 CompileRepair 方案 r1 完成（修改 AI：Claude）

在 `node-sem@306c135b` 上新建 `compile-repair` 分支，新增 `scripts/compile_repair/`（PROMPTS r1、PROGRESS、REPORT_TEMPLATE 与 `artifacts/cr_pre_v1/` 证据），提交 39b78108（2026-11-11 06:29:57 EST）并 push；没有修改任何已有文件，其他分支头不变。

证据在云端临时环境中取得：MANDO 七类 `source_files` 共 846 个文件 0 个 import；按 `auto_version_solc.py` 规则 807 通过、10 失败、29 个所选版本 ≤ 0.4.10 不可得；在各自合取 pragma 区间内同一小版本系列换版本后 39/39 可编译，不改源码；Slither 0.8.0 在 39 个文件 × 2 个版本上全部成功，节点键与 SlithIR 39/39 相同，source length 36/39 相同；solc 0.4.11 时节点缺文件名；三个 solc 行为探针（等长 pragma 替换保持偏移、基类须先定义、无函数体声明可编译）通过。

r1 据此把方案收缩为确定性版本策略，LLM 层列为有触发条件的扩展。该收缩在当天被用户否定（需要覆盖更多编译问题、面向检测与 DAppSCAN 等真实语料），由 r2 替代；r1 的证据仍然有效。

本轮没有模块代码、没有在用户环境运行、没有下载语料到仓库；solc 二进制与 Python 3.8 环境只存在于 Claude 的临时环境中。详见 `CHANGE_LOG.md` §1。

### 2026-11-11 CompileRepair 方案 r2 完成（修改 AI：Claude）

按用户要求把模块目录从 `scripts/compile_repair/` 移到仓库根目录 `compile_repair/`（`git mv`，21 个文件内容不变），并把 `PROMPTS.md` 改为 r2；新增 `artifacts/cr_pre_v2/`（外部语料结构统计）。提交 bfd23e83（2026-11-11 09:00:39 EST）并 push，`edge-sem` 等分支头不变。

r2 的设计：一条流水线处理所有输入；九步确定性方法先于代理；第一阶段单代理（一个修复模板、RAG、带原文校验的补丁、多候选、按编译结果择优）；第二阶段多代理（失败分析、上下文扩展、2–3 个异构模型独立提议、工具裁决、至多一轮基于编译结果的交流）；改动记录与节点标记；代码结构规范（分层目录，非测试 `.py` 上限 30）；Prompt 重排为 CP0–CP10，CP0–CP3 写全，CP4–CP10 给出范围与验收。

外部语料只读统计：DAppSCAN 608 个项目、21,457 个 `.sol`，405 个项目有仓库内无法解析的 import，1,094 条相对导入目标缺失，606/608 个项目没有构建配置，版本跨 0.4–0.8；SOChecker 897 条片段中 656 条含 `contract `/`function `；Trace on-chain 5,000、repo-level 83 个项目 3,092 个文件、CVEs 15。这些数字说明依赖补全与项目组装是外部语料的主要工作量。

待用户确认 D5、D6 阈值、D9、D10，待定 D12、D13；CP0 不受影响。本轮没有模块代码。详见 `CHANGE_LOG.md` §2。

### 2026-11-12 CompileRepair 文档目录建立（修改 AI：Claude）

按用户要求参照 NodeSem 的记录方式，在 `compile_repair/docs/` 新建 `README.md`（文件用途、每个编码任务必须完成的记录、交接与详细记录模板）、`HANDOVER.md`（本文件）、`CHANGE_LOG.md`（编号五段式详细记录，补记 r1、r2 与本轮）、`DECISIONS.md`（决策当前表与历史表）。

同时修订 `PROMPTS.md` r2 的共享上下文与 CP0：记录改写到 `compile_repair/docs/`，并禁止修改仓库根目录 `HANDOVER.md` 与 `docs/training_changes_2026-10-07.md`（与 EdgeSem 并行追加会在合并时冲突）；写明 6c 被 git 忽略的本地结果只在 EdgeSem 工作树中，CP0 以绝对路径只读读取。修订记为 r2.1，设计内容不变。

本轮没有模块代码、没有运行编译或 LLM。全部新文档通过 `doc_check`。详见 `CHANGE_LOG.md` §3。


### 2026-11-12 CompileRepair CP0 前置核验检查点（修改 AI：Codex）

在独立 compile-repair 工作树、起始 HEAD 068433d0 上，先读 PROMPTS r2.1 §4.1 与 docs 当前交接/最新变更，再实现 CP0 前置调查和 solc/Slither 封装。新增 9 个生产模块、3 个测试和 1 个 fixture，完整清单见 CP0_REPORT。根目录记录、冻结 scripts、源码语料、旧证据和 EdgeSem 文件未修改。本次更新本文第 0–5 节的当前状态、工作树、环境、已知问题与关键路径；第 6 节此前记录逐字保留。

cp0_v1 正式调查一次：846 输入集合核对、256 份 6c SHA256 对应、43 metadata 来源校验、26 安装编译器 SHA256 核验通过，耗时 5.684 秒。6c 的 17 个异常文件与旧规则 A 异常集合完全相同。发现唯一精确要求 0.4.17 的输入没有本地候选，调查以退出码 2 停止；其他 845 份仅证明有候选，未证明能编译。真实 fixture 测试中 0.4.11 和 0.4.13 都 rc0，但前者 5 个缺 filename 节点被 D3 拒绝，后者通过。

用户已批准读取两份冻结 sources.json 及 metadata 引用的原始源码/CSV，D15 更新为明确授权，未读取标签/图/模型。43 份来源都是 SmartBugs versions.csv，更正了 PROMPTS 的 SolidiFI 描述。待批准 D16 只请求补齐必需 0.4.17，不包括可选端点；CP2 完整图比较的证据不足和精确 pragma 覆盖边界只登记建议，未改设计。停止位置是 CP0 前置门槛，矩阵编排尚未完成，不能进入 CP1。

CP0 测试第二轮 21 passed，首轮 1 failed/20 passed 是测试路径假设错误，已修正并保留日志；冻结 DFG v2 一轮 2653 passed、9 warnings。354 份 code refs 不变，9 个生产文件满足上限和分层；文档/最终审计结果见 CHANGE_LOG §4.5。本轮准备保存本地 CP0 检查点，不 push；实际提交号可由 git log 查询。没有下载、安装、全局 solc 切换、语料修复、图存储、HGT 训练、GPU 锁操作或 LLM 调用。


> 上游交接导入说明：下文来自 54ecc927；其中 CHANGE_LOG §4 指上游 r2.2 记录，在本地合并文档中编号为 §5。上文 CP0 的本地安装决策 D16 已映射为 D17；r2.2 D16 指 Slither 兼容性。

### 2026-11-12 CompileRepair 方案 r2.2：面向检测时任意输入，去除对训练数据集的依赖（修改 AI：Claude）

用户说明本方案不只修复当前训练数据集中的问题，还要修复将来模型检测时输入的任意损坏合约，不应只针对当前数据集设计。据此把 `PROMPTS.md` 从 r2.1 改为 r2.2，只修改该文件；同时按记录规则更新本文件、`CHANGE_LOG.md`、`DECISIONS.md` 与 `PROGRESS.md`。

主要修改：0 节新增“适用范围”（检测时的任意输入，0.4.12–0.8.x）；D6 取消“占剩余失败 ≥ 1% 或 ≥ 20 个编译单元”的频率门槛，改为按与语料无关的失败分类表逐类判定（有可确定性实施并能机械验证的修复就实现，否则交给代理，频率只排顺序）；分类表来源限定为 solc 文档的 13 种错误类型（已核对 v0.7.6 文档“Error types”一节）与 0.5–0.8 各版本 breaking changes 等有文档依据的内容；版本策略中“metadata”改为调用方可选提供的已知版本，无 pragma 时按文档有出处的版本特征推断区间，MANDO 的 0.4.25 默认值只作回归配置；入口统一为 `cli repair <路径>`；CP0 增加全版本范围编译器清单与 Slither 可用性探针，CP2 改为 MANDO 回归运行，CP3 先建分类表，CP4 破坏算子覆盖分类表中每个可构造类别。

新增 D16：Slither 0.8.0（6c 使用的版本）能否处理较新 0.8.x 编译器的输出未验证，由 CP0 测出后用户决定。顺带更正：本文件第 1 节状态表在 r2.1 提交中仍写着 r2，本轮改为 r2.2；第 0、1、4 节（一句话、状态表、必读事项第 8–10 条）均已更新。

本轮没有模块代码、没有编译或 LLM 运行，所有文档通过 `doc_check`。下一步仍为 CP0。详见 `CHANGE_LOG.md` §4。


### 2026-11-12 CompileRepair CP0 续作调查完成，停在 D16（修改 AI：Codex）

本轮位于独立 compile-repair 工作树，起始 HEAD 8fb81ed9，先阅读 PROMPTS 共享上下文及 CP0，并同步上游 r2.2。因本地检查点与 54ecc927 分叉，保留双方历史合并，原安装 D16 改编号为 D17，Slither 兼容性沿用上游 D16。扩展 solc、survey 和 CLI，补测试及六个版本特征 fixture，仍是 9 个生产文件。本文第 0–5 节已更新当前阻塞、版本覆盖、测试、分支、路径与下一步，旧交接记录全部保留。

cp0_v2 在 846/846 输入上找到 D3 合格版本，旧 6c 的 17 个异常全部通过。678 份双版本的 key4 和有序 SlithIR 一致，28 份 source length 不同；55 份有重复 key4，保留重数而不去重。官方快照目标范围 92 版，33 版已装，另有四个历史负对照，总 37 版；39 组探针全部编译成功，但六组 D3 失败。四组早期负对照缺映射，另两组为 0.8.4/0.8.38 自定义错误解析失败，正式状态 awaiting_d16、CLI rc2，依据见 RECON §9–10 与封存结果。

用户“可以下载”批准 0.4.17，随后“批准这 10 个探针版本（推荐）”追加批准十个明确版本，授权、官方索引和二进制双哈希全部落盘。未把该授权扩展为安装全部补丁或升级 Python/Slither；原 26 份信任记录、全局版本选择保持原样。当前停在 PROMPTS CP0 §5b 要求的 D16，建议独立评估新版工具链但尚未实施。D4/CP2 的重复节点及报告可观察范围、D5 的精确 pragma 边界均列为审查项，没有自行更换设计。

CP0 最终 32 passed，冻结 DFG v2 为 2653 passed、9 warnings；开发首轮区间反序列化错误已在新小样本和新增测试中验证修复，失败现场保留。354 个冻结引用与 846 份输入不变，正式运行后不改实现，文档检查与最终审计结果见 CHANGE_LOG §6.5。全部验收后本地提交，以 CP0 开头，提交号由 git log -1 与最终答复给出，不 push。没有通用 repair、源码修复、图存储、外部语料获取、HGT 训练、GPU 锁或 LLM 调用。


### 2026-11-12 CompileRepair CP0 审查与方案 r2.3（修改 AI：Claude）

用户要求审查 Codex 完成的 CP0（提交 8fb81ed9、ac2b3465）：核对方案、代码、产物与四份记录中的问题，判断 Codex 的处理是否正确，对错误或未解决的问题给 Codex 写计划；全部核实后才能进入 CP1。起点 `compile-repair@ac2b3465`。新增证据目录 `artifacts/cp0_review_v1/`（独立复核脚本、5 个 Slither 版本的语料与特征对照），修改 `PROMPTS.md`（r2.2 → r2.3）。本文第 0、1、4、5 节已重写：一句话与状态表换成审查结论；第 4 节恢复 r2.2 中被合并丢失的条目（证据环境不同、外部语料无许可证、检测时任意输入、0.4.10 无静态二进制），并加入 key5、source_mapping 两种形式、tree_sitter 依赖、pragma 覆盖边界与编号笔误；第 5 节加入审查证据路径。

结论：CP0 的数字全部可复现，SHA256、规则 A、升降序、1,692 个选定版本的区间与 D3 记录、678 对跨版本比较都与 Codex 一致；本环境 Slither 0.8.0 的节点指纹与 Codex 743/743 相同。Codex 的处理中，metadata 来源的更正、按多重集合保留重复 key4、停在 D16 都正确。问题在方案本身：D3 漏了顶层函数且没有合约覆盖检查；key4 不唯一（序号身份 678/678 稳定，改为 key5）；pragma 覆盖两处规定互相矛盾；CP0 的 toolchain 只能读 dict 形式 source_mapping，新版 Slither 下会报错。

D16 补测：0.8.3 结构与 0.8.0 完全相同但不支持顶层 using 与全局运算符；0.9.6 六个特征全部通过、MANDO 无失败、只缺合成的常量构造函数节点；0.10.4/0.11.6 在 3 个 0.4.24 重入合约上崩溃且结构大幅变化。推荐 0.9.6 独立环境做生产，0.8.0 只做 6c 精确重放。新增 D18（补齐其余 59 个官方编译器）。

下一步：用户决定 D5、D16、D18；Codex 执行 CP0.1（A 部分不需要授权，可先做）；Claude 审查后再进入 CP1。本轮没有模块代码改动、安装或 LLM 调用。详见 CHANGE_LOG §7。

### 2026-11-12 CompileRepair CP0.1 A 完成，B/C 待授权（修改 AI：Codex）

在 compile-repair 从已同步的 61a3cb6a944140108763442999bbfd4199f53ca3 开始，先读 PROMPTS r2.3 §4.1、全文及当前交接/最新记录，再执行 A。修改 Slither 封装、survey、CLI、旧测试，新增映射/key5/覆盖/profile 测试与两个 fixture，生产文件仍为 9 个。冻结代码、输入、旧产物、CP0 报告和根文档未改。本次更新交接第 0、1、2、4、5 节状态、下一步与路径，第 6 节历史逐字保留。

846 文件全部通过新 D3，(a)/(b) 失败均 0，CP0 投影 846/846 一致，语料顶层函数 0。678 组跨版本 key5 与有序 IR 全同，其中重复 key4 的 31 组也全同；55 个选定版本文件的重数保留。solc 与 Slither 各 1,546 次成功，201,044 条节点中无重复 key5 组，完整证据在 cp0_1_v1。length 的 28 组差异仅诊断，生产环境和完整图边语义未验证。

按 §4.2b，B 需 D16 决定与环境授权，C 需 D18 决定与编译器授权，因此完成 A 后停止。两份具体清单已在 cp0_1_development_v1 列出，均 pending、费用上限 0 美元；此前 11 个 solc 批准不扩张使用。另登记 transient 0.8.24 文案与审查 >=0.8.28 高级变量 fixture 的边界待核对，如需改方案先咨询，没有自行实施替代。CP1 仍需完整 CP0.1 审查及 D5/D16/D18 决定。

模块 CPU 测试 55 passed，冻结 DFG v2 测试 2653 passed、9 个既有警告，无失败/跳过；文档和最终审计见 CHANGE_LOG §8.5。编辑工具的 WSL 路径与模板问题已解决并保留说明，无正式运行重试。本轮检查通过后只作本地提交，标题以 CP0.1 complete A 开头、不 push；旧 CP0 ac2b3465 在此前已按用户要求推送，当前区据此更正。没有新增下载/安装、LLM、HGT 训练、GPU 锁操作、输入改写或图存储。
终审首轮因 PowerShell 中文字面量编码导致标题定位失败，已保留现场并改用 ASCII 前缀；最终确认 354 个冻结代码引用、846 个输入、37 个编译器与四份历史记录均未改变，文档 6/6 通过后提交。


### 2026-11-13 CompileRepair CP0.1 A 审查与方案 r2.4（修改 AI：Claude）

用户要求审查 Codex 完成的 CP0.1（提交 18940a8a）：核对方案、代码、产物与记录中的问题，判断处理是否正确，对错误或未解决的问题给 Codex 写计划；全部核实后才能进入 CP1。新增证据目录 `artifacts/cp0_1_review_v1/`，修改 `PROMPTS.md`（r2.3 → r2.4）。本文第 0、1 节换成审查结论，第 4 节第 15 条改写（transient 待核对项已核实），第 5 节加入审查证据路径。

结论：CP0.1 A 正确。验收数字全部可复现；1,546 组（源文件, 版本）节点的 key5 与有序 IR 和 Claude 用独立脚本按 Slither 节点顺序导出的结果逐组相同；所用版本与 cp0_v2 的选定和端点集合完全一致；CP0 投影 1,546/1,546。Codex 的代码在 Slither 0.9.6、0.11.6 下也能正确处理对象形式的 source_mapping 与 AST。Codex 登记的 transient 问题成立：0.8.24 只有 Yul tload/tstore，transient 状态变量从 0.8.28 起才能编译，r2.3 写错了。D18 的 59 个编译器请求与官方 solc-bin 索引逐项一致。

新发现：r2.3 推荐 Slither 0.9.6 只依据 6 个探针。扩展到 19 个后，0.9.6 有 6 种 0.8.7 起的合法写法无法分析，0.11.6 全部通过；846 个文件上 0.9.6 全部通过，0.11.6 有 3 个 0.4.24 文件崩溃，可用语义等价改写处理。推荐改为 0.11.6，备选 0.9.6；若选 0.11.6，Codex 已提交的 0.9.6 环境请求需要改写。

下一步：用户决定 D5、D16、D18 并授权；Codex 执行 CP0.1 B、C（4.2b 节 r2.4 版）；Claude 审查后再进入 CP1。本轮没有模块代码改动、安装或 LLM 调用。详见 CHANGE_LOG §9。


### 2026-11-13 用户决定 D5、D16、D18（修改 AI：Claude）

用户采纳 r2.4 的推荐：D5 区间内升序；D16 生产工具链用 Slither 0.11.6 + crytic-compile 0.4.2（Python 3.10 独立环境，0.8.0 只做 6c 重放）；D18 安装其余 59 个官方编译器。已更新本文第 0、1 节与 DECISIONS。Codex 的 0.9.6 环境请求作废，B 开始时按 4.2b 节重写为 0.11.6 版本并落盘授权。没有代码改动或运行。详见 CHANGE_LOG §10。


### 2026-11-13 CompileRepair CP0.1 B 完成、C 安装完成后遇兼容性失配停止（修改 AI：Codex）

本轮在 compile-repair@897fbd03116040ddbc8d106db1b844624f512091 开始，pull --ff-only 已同步，阅读完整 r2.4 及必读记录后按用户新授权执行 B/C。生产代码只在 toolchain/slither.py 增加 production、metadata 回退与实际平台记录，新增对应测试和原字节的 19 个 probe。A 未重跑，CP0/A 归档、旧 0.9.6 请求、原输入、mando 和旧 solc 文件未修改。当前第 0–5 节已更新为 B 实测完成、C 安装完成但兼容性停止的状态，并替换旧待授权环境信息与下一步边界。

B 的 846 份区间与 mando 全同，固定版本 D3 为 843/846，指定的三个 0.4.24 AssertionError 和 435 份结构差异全部吻合审查。23 组当前特征组合全部通过，三个工作副本在两套环境中均通过，节点数 11→10、11→10、6→5，具体见 CP0_1_REPORT B 与 cp0_1_env_v1。B 门槛通过后才安装 59 个 solc，全部双哈希和 --version 通过，支持范围达到快照 92/92。C 的 496 组只执行了 225：224 过、1 失败、271 未运行，见 compatibility.json。

用户本轮明确批准 D5 升序、D16 0.11.6/0.4.2 独立环境与 D18 的 59 版下载，费用上限 0 美元，授权在两个批次中先行写入。C 首个失配为 0.8.24 编译 h0824_blob.sol 时 blobhash 未声明，rc1 且未运行 Slither，已按原文停止并保留现场。没有放宽判据、变更编译参数、修改 probe 或自动重试；后续应先审查最低语法版本及 EVM 设置，任何方案调整须先咨询用户。C 与 CP0.1 整体尚未通过，CP1 不开始，第 10 行改写规则仍留给 CP6。

生产模块测试 77 passed/6 skipped，mando 模块 58 passed/25 skipped，冻结 DFG 2653 passed/9 warnings；两套 metadata 路径和平台组合等价均验证。初始 user-site 依赖混入在安装前用新环境专属隔离解决，开发正则收集错误已修正并保留失败日志，均未改变验收判据。frozen_audit 核对模块外 27845 文件、旧产物 204、旧编译器 37、mando 元数据 205 以及 code_refs 354 项不变，doc_check 与最终审计见 CHANGE_LOG §11.5。本轮在全部强制记录之后本地提交，不 push；无 LLM、训练、GPU 锁、图存储或范围外安装。


### 2026-11-13 CompileRepair CP0.1 B、C 审查与方案 r2.5（修改 AI：Claude）

用户要求审查 Codex 完成的 CP0.1 B、C（提交 33c23a3b）。新增证据目录 `artifacts/cp0_1bc_review_v1/`，修改 `PROMPTS.md`（r2.4 → r2.5）。本文第 0、1 节换成审查结论，第 5 节加入证据路径；第 4 节 Codex 写的 18 条保留（第 16、17 条的待处理事项由 4.2c 节处理）。

结论：B 正确。生产运行的 846 次调用、843 个 D3 通过、3 个 0.4.24 失败、435 个结构差异文件都与审查预期相同；与 Claude 独立的 0.11.6 运行比较，839/843 个文件的 key5 与有序 IR 完全相同。59 个编译器的哈希与官方索引 0 差异。C 停在 0.8.24 + h0824_blob 是方案错误：r2.4 写的探针下界是语法引入版本，审查时只在 0.8.38 上运行过；实测默认设置下 4 个 Cancun 探针从 0.8.25 起可编译（0.8.24 需要 `--evm-version cancun`），h0826 从 0.8.27 起可编译（0.8.26 需要 `--via-ir`），加设置后 Slither 0.11.6 D3 通过。Codex 不改参数、停下报告是正确的。

新发现：其余 4 个文件的差异来自 Slither 0.11.6 在 IR 文本中输出 Python 对象内存地址，指纹不能复现，CP2 前必须规范化。设计缺口：精确 pragma 0.8.24 或 0.8.26 的真实合约只能靠编译设置编译，r2.5 在 3.3 节加入第 3a 条（设置表、同一版本重试、Slither 使用相同设置），在 CP1 实现。

下一步：Codex 执行 4.2c 节（不需要新的安装或授权）；Claude 审查后进入 CP1。本轮没有模块代码改动或安装。详见 CHANGE_LOG §12。


### 2026-11-13 CompileRepair CP0.1 C 续完成本机验收（修改 AI：Codex）

本轮在 compile-repair@3742fb75e535b5517ded58659e78737a01b51000 上执行 PROMPTS r2.5 §4.2c，pull --ff-only 返回 Already up to date。完整阅读共享上下文、最新交接、DECISIONS、CHANGE_LOG §11/§12 和审查 README 后，修改三个工具链/数据文件、一个测试文件并新增一个测试文件。新产物只写 cp0_1_env_v2 与 cp0_1_compilers_v2，旧报告只追加 C 续，A/B/原 C 证据不变。本次更新本文第 0、1 节状态，第 2 节起点/提交边界，第 3 节环境限制，第 4 节设置/IR/覆盖事项和第 5 节新证据路径。

两次生产各 843/846 D3，失败仍为相同 3 个 0.4.24 AssertionError；843/843 指纹跨运行相同。与 B 比较，839 个成功文件完全相同，另外 4 个文件各只规范化 1 行 IR；四份新节点归档无对象地址残留（archive_audit.json）。按 SHA256 排序后 Random(0) 抽样的 20/20 在 mando 与 A 指纹一致。兼容性 501/501 符合预期，含 491 默认正例、5 设置正例、5 默认负对照；原 224 成功组逐组一致，59 个新增版本均完成计划。

本轮严格使用 r2.5 新批准的参数与预期，没有方案外替代或放宽判据。读取审查 JSON 时发现其为连续两个对象，按实际格式读取并记录，原证据不改；原始 stderr 无损压缩保留。92/92 是可信安装口径，本次 501 组是新增 59 版的矩阵，不宣称穷举全部语法。设置的自动触发/升序策略留给 CP1，源码改写留给 CP6；下一步必须审查本轮之后才能开始 CP1。

两环境新增逻辑与分层各 27 passed；完整模块 production 506 passed/6 skipped、mando 83 passed/429 skipped，冻结 DFG v2 为 2653 passed/9 个既有弃用警告。全部命令与 rc 见 test_summary.json 和同名日志，UTF-8/doc_check 与冻结审计见 CHANGE_LOG §13.5 最终补记。完成记录和检查后按要求本地提交，本任务不 push。没有训练、GPU 锁操作、安装、下载或 LLM API 调用，费用 0 美元。
