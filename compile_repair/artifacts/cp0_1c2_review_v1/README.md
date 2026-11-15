# cp0_1c2_review_v1：CP0.1 C 续审查证据（Claude，2026-11-14）

审查对象：`compile-repair@08337158`（Codex 的 CP0.1 C 续：`core/model.py`、`toolchain/solc.py`、`toolchain/slither.py`、`tests/test_settings.py`、`tests/test_production.py`，产物 `artifacts/cp0_1_env_v2/` 与 `cp0_1_compilers_v2/`）。本目录是独立复核证据，不是生产代码。

## 环境

沿用前几轮的 Slither 0.8.0（Python 3.8.20、crytic-compile 0.2.4）与 0.11.6（Python 3.12.13、crytic-compile 0.4.2）环境；solc 0.4.11–0.8.38 为 GitHub 发布页 `solc-static-linux`，0.8.24–0.8.27 的 SHA256 与官方 solc-bin 索引一致（`cp0_1bc_review_v1/solc_0824_0827_SHA256SUMS`）。输出中的本机路径已替换为 `<repo>`、`<scratch>`。

## 文件

| 文件 | 内容 |
|---|---|
| `verify_c2.py` / `verify_c2.json` | 从两次生产运行、B 归档、A 归档、回归样本与兼容性产物独立重算验收数字；生产归档与 Claude 在 `cp0_1_review_v1` 中独立的 0.11.6 运行（按同一规则规范化对象地址后）逐组比较。seal 的核对另在审查时完成（41 + 8 个产物、9 个实现文件、7 份文档的 SHA256 全部一致） |
| `settings_e2e.py` / `settings_e2e.jsonl` | 在 Claude 的 0.11.6 环境中直接调用 Codex 的 `compile_file(settings=…)` 与 `run_slither(profile="production")`，覆盖默认失败、加设置通过、默认下界版本通过与非白名单选项被拒绝 |
| `c0411.sol`、`github_0411_cwd.jsonl`、`old_mapping.py` | solc 0.4.11（GitHub 静态构建）在 4 种工作目录下、Slither 0.8.0 与 0.11.6 中的文件名映射 |

## 结论

1. **C 续的数字全部可复现**（`verify_c2.json`）：
   - 两次生产运行各 743 个不同源文件记录（846 个文件按 SHA256 去重），节点内容与指纹 743/743 相同，自身指纹 1,486/1,486 一致，归档中对象地址残留 0，成功节点 99,716 个（按 846 个文件计为 110,996）。
   - 与 B 归档比较：739 个逐组相同；4 个只在把 B 中的对象地址按同一规则规范化后相同，正是 `cp0_1bc_review_v1/ir_object_repr.json` 列出的 4 个文件；其他差异 0。
   - 与 Claude 独立的 0.11.6 运行（规范化后）比较：740/740 个成功文件 key5 + 有序 IR 完全相同。
   - mando 回归样本 20/20 与 A 归档相同。
   - 兼容性计划 501 组 = 原 496 组（逐组保留）+ 5 组设置正对照；solc 501 次，非零退出正好是 5 个负对照，错误文本与 r2.5 1.8 节相同（0.8.26 的诊断行含 `std::exception::what:` 消息）；Slither 496 次 D3 全部通过，其中 5 次带设置。旧 224 组相同。
2. **设置通路端到端正确**（`settings_e2e.jsonl`）：Codex 的代码在 Claude 环境中，0.8.24 默认失败（`Function "tload" not found.`），加 `--evm-version cancun` 后 rc 0、D3 通过、Slither 记录相同设置、平台为 solc；0.8.26 同理（`--via-ir`）；0.8.25、0.8.27 默认通过；`--optimize` 被拒绝。crytic-compile 0.4.2 在传入 `solc_args` 时仍会补上 `--allow-paths`（源码第 582–598 行），单文件之外的导入解析不受影响。
3. **代码审查**：设置白名单、顺序保留、regression_6c 拒绝设置、崩溃诊断合并 what 行、对象地址规范化与残留即 D3(a) 失败，都与 r2.5 4.2c 节一致；CP0 投影未改。
4. **新发现：0.4.12 下限的依据与工作目录有关，且只在 Slither 0.8.0 中出现**（`github_0411_cwd.jsonl`）。同一 0.4.11 合约：Slither 0.8.0 在工作目录为仓库根或文件所在目录时 5/5 节点缺文件名，在 `/` 或无关目录时 0 缺失；Slither 0.11.6 在 4 种工作目录下都是 0 缺失、D3 通过。用户环境的 CP0 记录（0.8.0）中 0.4.11 负对照缺文件名，与第一种情形一致。生产工具链（0.11.6）是否仍需要 0.4.12 下限，现有证据不能回答，需要在用户环境、官方 solc-bin 构建上实测；在此之前下限不变。
5. **CP1 方案需要的修正**：r2.5 的 CP1 小样本验收写“选定版本与 CP0 第 4 节预测相同”“D3 失败数为 0”，这是在 Slither 0.8.0、37 个编译器下得出的预期；CP1 使用生产 0.11.6 与 92 个编译器，选定版本可能因新装的更低版本而变化，3 个重入合约（pragma `^0.4.0`）在 0.4.24 上生产 Slither 失败，其他 0.4 候选上是否同样失败尚未实测（0.4 的 `.call` 都只返回 bool，预计相同，须由 CP1 记录）。验收必须改为可归因的比较。

## 复现

```bash
python3 -I verify_c2.py <repo> <cp0_1_review 的 0.11.6 批量输出 jsonl>
python -I settings_e2e.py <repo> <含 solc-0.8.24..0.8.27 的目录>      # Slither 0.11.6 环境
(cd <工作目录> && python -I ../cp0_1_review_v1/port_probe.py <repo> c0411.sol <solc-0.4.11>)
```
