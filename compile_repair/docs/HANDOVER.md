# CompileRepair 交接文档

> 新接手请先读本文第 0–5 节、PROMPTS.md r2.1、DECISIONS.md 和 CHANGE_LOG 最新节。第 6 节只追加；记录规则见 README.md。

## 0. 一句话

CompileRepair 在 MANDO-LLM 上实现可审计的 Solidity 编译修复；当前已完成 CP0 前置调查与工具封装，因缺少必需 solc 0.4.17 停止，尚未完成全量 CP0，不可进入 CP1。

## 1. 当前状态

| 项 | 状态 | 依据 |
|---|---|---|
| 方案 | PROMPTS r2.1（2026-11-12） | 起始 HEAD 068433d0 |
| 模块代码 | 9 个生产 Python 文件，3 个测试文件、1 个 fixture | CP0_REPORT.md |
| 已完成的 Prompt | 无；CP0 完成前置核验，完整验收未完成 | cp0_v1/recon.json |
| 当前阻塞 | 精确 pragma 0.4.17 的 1 份合约无已安装可信候选 | RECON.md §4 |
| 下一步 | 用户批准后补齐 0.4.17，并新增独立信任清单；继续 CP0 矩阵编排与全量验收 | compiler_installation_request.json |
| 测试 | CP0 21 passed；DFG v2 2653 passed、9 warnings | 开发产物测试日志 |
| 待确认决策 | D5、D6 阈值、D9、D10、D16；待定 D12、D13 | DECISIONS.md |

## 2. 分支与工作树

- 独立工作树已存在：`/home/zhao/SmartContract/ge-sc-llm-compile`，分支 `compile-repair`。不要重复创建或在 EdgeSem 中执行 git 操作。
- 起始 HEAD 为 `068433d0cfa3367fe09cd1f94f78319eeff3c6d0`。本轮 pull 因 WSL DNS 失败，已通过连接的 GitHub 工具核对远端 HEAD 相同；未修改网络配置。
- 本分支改动只在 compile_repair/；根目录交接/训练改变文档、scripts/**、输入语料、旧产物保持原样。本地检查点提交后不 push。

## 3. 环境

```bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm-compile
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
export TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64
```

Python 3.7.12、Slither 0.8.0、crytic-compile 0.2.4、solc-select 1.0.4。26 个现有编译器已核验；新工作树没有 tree-sitter 动态库，使用上面的既有库路径，不复制或编译库。Windows 侧以明确的 `wsl.exe -d Ubuntu-22.04 --cd ... --exec ...` 执行；Python 脚本含中文时设置 PowerShell `$OutputEncoding = [System.Text.UTF8Encoding]::new()`。安装、下载或升级需独立授权；本轮读取授权不包含安装。

## 4. 必读事项

1. 6c 的报告、seal 和可信编译器清单只在 EdgeSem 工作树，按固定 SHA256 先验证再只读。用户已额外批准两份 contract sources.json 及 metadata 引用的来源源码/CSV；精确范围见 `artifacts/cp0_development_v1/metadata_read_authorization.json`，不含标签/图/模型。
2. 43 metadata 实际全部来自 SmartBugs versions.csv，PROMPTS §1.2 的 SolidiFI 描述有误；更正在 RECON，未改原文。
3. solc 编译成功不足以满足 D3。真实测试中 0.4.11 的 5 个节点全部缺 filename，0.4.13 正常。
4. `denial_of_service/source_files/0xea68d87ae3a55ba91c1a8e6488627a175be81588.sol` 精确要求 0.4.17；这是唯一无候选输入。不能用其他版本或改 pragma 绕过；安装请求尚待批准。
5. 当前 survey 仅完成前置编排与停止归档，工具封装已测；缺口消除后仍要实现全量矩阵/选版/跨版本统计。已有 cp0_v1 不得覆盖或重跑，后续用新批次。
6. 6c occurrence 没有 node.type/原始 SlithIR，不能直接作为完整 CFG/CG 基线；CP2 的回归键建议见 RECON §6，待审查。
7. `.gitignore` 忽略 JSON/TXT。只显式暂存要提交的证据；开发 pytest 临时目录含大量回归样本，不要整体 git add。首轮失败日志保留，不覆盖历史。
8. 记录只写本模块 docs/，中文文档用 Python UTF-8 写入并通过 doc_check。没有 HGT 训练、GPU 锁、下载或 LLM 调用。

## 5. 关键路径

| 内容 | 路径 |
|---|---|
| 完整要求 | compile_repair/PROMPTS.md |
| CP0 当前报告 | compile_repair/CP0_REPORT.md、RECON.md |
| 正式停止现场 | compile_repair/artifacts/cp0_v1/recon.json、seal.json |
| 开发基线、测试、授权范围 | compile_repair/artifacts/cp0_development_v1/ |
| 待批准安装请求 | compile_repair/artifacts/cp0_development_v1/compiler_installation_request.json |
| 旧证据 | compile_repair/artifacts/cr_pre_v1/、cr_pre_v2/ |
| 记录规范 | compile_repair/docs/README.md |

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
