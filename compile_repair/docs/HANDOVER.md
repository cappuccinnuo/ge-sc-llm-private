# CompileRepair 交接文档

> 新接手（包括新的 Codex 或 Claude 会话）请先读本文第 0–5 节，再读 `../PROMPTS.md`（方案与 Prompt）、`DECISIONS.md`（决策状态）和 `CHANGE_LOG.md` 的最新一节。记录规则与模板见 `README.md`。
> 第 0–5 节描述当前状态，状态变化时更新；第 6 节“交接记录”只追加。

---

## 0. 一句话

CompileRepair 是 MANDO-LLM 私有仓库中的编译修复模块：对任意 Solidity 合约（单文件或项目中的编译单元），先用确定性方法、仍失败时用 LLM 代理，使 solc 可编译、Slither 0.8.0 能生成完整的 CFG/CG/SlithIR，并记录每一处改动、在图中标记来自改动的节点。当前（2026-11-12）只有方案与证据，没有任何模块代码。

## 1. 当前状态

| 项 | 状态 | 依据 |
|---|---|---|
| 方案 | `PROMPTS.md` r2（2026-11-11） | 提交 bfd23e83 |
| 模块代码 | 0 个文件（3.10 节计划 29 个非测试 `.py`，上限 30） | `git ls-tree` |
| 已完成的 Prompt | 无 | `PROGRESS.md` |
| 下一步 | CP0（MANDO 语料侦察与核对，只读） | `PROMPTS.md` 4.2 节 |
| 待确认决策 | D5、D6 阈值、D9、D10；待定 D12、D13 | `DECISIONS.md` |
| CP0 是否被待确认决策阻塞 | 否 | CP0 不涉及版本策略细节、规则阈值与 LLM |

## 2. 分支与工作树

- 分支 `compile-repair`，从 `node-sem@306c135b` 切出，与 `edge-sem` 起点相同，不含 EdgeSem 代码。本分支只新增 `compile_repair/`，与其他分支没有文件交集。
- 用户的 EdgeSem 工作树：`/home/zhao/SmartContract/ge-sc-llm-ddg-v11`（来源：`edge-sem` 分支 `scripts/edge_sem/PROMPTS.md` 共享上下文）。不得在其中切换分支。
- 本模块的工作树（建议）：`/home/zhao/SmartContract/ge-sc-llm-compile`。在 EdgeSem 工作树中执行一次：

```bash
cd /home/zhao/SmartContract/ge-sc-llm-ddg-v11
git fetch origin compile-repair
git worktree add /home/zhao/SmartContract/ge-sc-llm-compile -b compile-repair origin/compile-repair
git worktree list
```

## 3. 环境

```bash
conda activate mando          # Python 3.7.12（与 EdgeSem/NodeSem 相同环境）
cd /home/zhao/SmartContract/ge-sc-llm-compile
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
```

- solc：用 solc-select 安装在 `~/.solc-select/artifacts`，两个工作树共用；6c 已安装并核验 26 个版本（SHA256 与 Keccak256）。不得切换全局版本，一律传可执行文件路径。
- Slither 0.8.0、crytic-compile 0.2.4（6c 记录的版本）。
- 不得安装、升级、下载任何东西，除非用户在 `compile_repair/artifacts/<批次>/authorization.json` 中授权。
- CP0–CP7 只用 CPU；CP0 运行 846 个文件 × 多个编译器版本的 solc 与 Slither，会与 EdgeSem 训练争用 CPU，时间敏感时在两次训练之间运行。

## 4. 必读事项（已知的坑）

1. **6c 的本地结果只在 EdgeSem 工作树中。** `scripts/DFG/experiments/artifacts/dfg_v2/prompt6c_v1/` 下的 `slither_full/report.json`、`slither_full/report.seal.json`、`trusted_compilers_complete.json` 被 `.gitignore` 的 `*.json` 规则忽略，新工作树中不存在。CP0/CP2 必须用绝对路径 `/home/zhao/SmartContract/ge-sc-llm-ddg-v11/scripts/DFG/experiments/artifacts/dfg_v2/prompt6c_v1/...` 只读读取，并先核对 `PROMPTS.md` 1.2 节记录的 SHA256；不得复制、移动或修改。
2. **`.gitignore` 忽略 `*.json` 与 `*.txt`。** 需要提交的 JSON/TXT 产物要用 `git add -f`（EdgeSem 与本模块证据目录都是这样提交的）。
3. **solc ≤ 0.4.11 时 Slither 0.8.0 的节点没有文件名。** 编译成功不等于可用；成功判据是 D3（`PROMPTS.md` 第 2 节）。这是 6c 中 6 个“映射不可比”文件的原因（`artifacts/cr_pre_v1` 证据 5）。
4. **0.4.10 及更早版本在 GitHub 发布页没有静态 Linux 二进制**（0.4.10 返回 404）。用户本机的 solc-select 来源不同，CP0 需在本机核实可得性。
5. **仓库默认规则 `auto_version_solc.py` 只取 pragma 中第一个版本号、只试一次。** 在 MANDO 846 个文件上它导致 39 个文件不通过；在区间内换版本后 39/39 可编译（`artifacts/cr_pre_v1` 证据 2、3）。
6. **证据环境与用户环境不同**（GitHub 静态 solc、Python 3.8、直接调用 solc）。`artifacts/cr_pre_v1`、`cr_pre_v2` 的数字都须由 CP0/CP3 在用户环境复核。
7. **外部语料仓库（DAppSCAN、SOChecker、Trace）都没有 LICENSE 文件。** 使用范围由用户决定；语料放在仓库之外，不提交。
8. **记录只写在 `compile_repair/docs/`。** 不修改仓库根目录 `HANDOVER.md` 与 `docs/training_changes_2026-10-07.md`（避免与 EdgeSem 合并冲突，见 `README.md`）。

## 5. 关键路径

| 内容 | 路径 |
|---|---|
| 方案与 Prompt | `compile_repair/PROMPTS.md` |
| 证据（MANDO 编译与 Slither） | `compile_repair/artifacts/cr_pre_v1/README.md` |
| 证据（外部语料结构） | `compile_repair/artifacts/cr_pre_v2/README.md` |
| 报告模板 | `compile_repair/REPORT_TEMPLATE.md` |
| 可复用的冻结模块 | `scripts/DFG/state/stage_f/versioning.py`、`scripts/DFG/dfg_v2/validate_slither.py`、`scripts/DFG/dfg_v2/inputs.py` |
| 文档检查工具 | `python -B -m scripts.node_sem.doc_check` |

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
