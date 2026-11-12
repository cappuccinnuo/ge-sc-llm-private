# cp0_review_v1：CP0 审查证据（Claude，2026-11-12）

审查对象：`compile-repair@ac2b3465`（Codex 的 CP0 两次提交 8fb81ed9、ac2b3465 与合并）。本目录是独立复核与 D16 补充测量的证据，全部可复现；不是生产代码，任何 Prompt 都不导入这里的脚本。

## 环境（与用户 `mando` 环境不同）

| 环境 | Python | Slither | crytic-compile |
|---|---|---|---|
| venv38 | 3.8.20 | 0.8.0 | 0.2.4 |
| venv38_s083 | 3.8.20 | 0.8.3 | 0.2.4（固定，以便只比较 Slither 的差别） |
| venv312_s096 | 3.12.13 | 0.9.6 | 0.3.11 |
| venv312_s0104 | 3.12.13 | 0.10.4 | 0.3.11 |
| venv312_s0116 | 3.12.13 | 0.11.6 | 0.4.2 |

见 `environments.txt`。Python 3.7 在本环境不可得（uv 没有 3.7 发行包），所以 0.8.3 没有在 3.7 上实测；PyPI 元数据声明 0.8.3 要求 Python ≥ 3.6，0.9.0 起 ≥ 3.8，0.11.5 起 ≥ 3.10。

solc：GitHub `ethereum/solidity` 发布页的 `solc-static-linux`。与 `cp0_v2/recon.json` 中 37 个可信编译器的 SHA256 比较：本环境有其中 30 个，29 个逐字节相同，0.4.26 不同（来源不同的构建）；cp0_v2 升序选定的 24 个版本全部在相同的 29 个之内，0.4.26 没有被选中。0.8.4、0.8.38 的 SHA256 见 `solc_08_SHA256SUMS`。

## 文件

| 文件 | 内容 |
|---|---|
| `verify_cp0.py` / `verify_cp0.json` | 从 `cp0_v2` 的逐文件记录与原始调用日志独立重算全部汇总数字，并逐条检查选定版本 |
| `node_dump.py` | 按 Slither 自身节点顺序导出每个声明函数/修饰器的节点（类型、起始偏移、有序 SlithIR）与顶层函数；同时按 CP0 的口径计算节点指纹，用于与 `invocations.jsonl` 的 `node_facts_sha256` 对照 |
| `d16_analyze.py` / `ordinal_and_s083_analysis.json` | 0.8.0 指纹对照；0.8.3 对照；序号身份在两个编译器版本之间的稳定性 |
| `slither_versions_corpus.json` | 0.8.3、0.9.6、0.10.4、0.11.6 与 0.8.0 在 743 个不同源文件（846 个文件去掉 103 个跨类别逐字节重复）上的结构、有序 IR、失败对照（节点类型按各版本 `NodeType` 枚举名归一） |
| `nodetype_*.json` | 各版本 `NodeType` 枚举名到字符串的映射（归一依据） |
| `d16_probe.py`、`features/*.sol`、`feature_probes.jsonl` | 6 个 0.7.1–0.8.28 语法特征探针在 solc 0.8.38 上、5 个 Slither 版本的构造与映射结果；顶层函数存放位置检查 |

## 结论（数字均来自上述文件）

1. **CP0 数字全部可复现**：846 输入、SHA256 与 git 语料一致 0 差异；规则 A 821/22/3；升降序不同 617；相对规则 A 移动 44；重复 key4 文件 55；双端比较 678，key4 678、IR 678、长度 650 相同。逐条检查 1,692 个选定版本（升序与降序）：每个都有 rc0 的 solc 记录与 D3 通过的 Slither 记录，都在文件合取区间内、与下界同一小版本系列、≥ 0.4.12，违例 0。
2. **与旧证据对账**：旧 ok→本机 passed 806、旧 ok→unavailable 1、旧 fail→failed 10、旧 unavailable→passed 15 / failed 12 / unavailable 2，与 RECON §9 的解释一致。旧证据中规则 B 找到的可编译版本在本机矩阵中没有一个失败。6c 的 17 个异常文件与旧证据集合完全相同，现在都在升序选定版本上通过 D3。
3. **168 个没有第二端点的文件**全部是精确 pragma（区间只含一个版本），不是遗漏。
4. **metadata 来源**：冻结 `versioning.recorded_version` 读取 CSV 的 `compiled version` 列；SolidiFI 的 `BugLog_*.csv` 是标签位置文件。Codex 关于 SmartBugs `versions.csv` 的更正成立。
5. **本环境的 Slither 0.8.0 与 Codex 的结果逐字节一致**：743 个不同源文件的节点指纹（key4、有序 IR、长度）与 `invocations.jsonl` 全部相同。
6. **key4 不唯一的原因**：例如 `access_control/0x000c1000…sol` 的 `min` 函数 `return a < b ? a : b;`，Slither 把三元表达式拆成 IF 与两个 RETURN 节点，两个 RETURN 节点共享语句起始偏移。这是合法的重复，不是工具错误。
7. **序号身份稳定**：在 Slither 节点顺序中给相同 (类型, 起始偏移) 的节点编 1、2、…；678 对双端比较中，每个函数的 (类型, 起始偏移, 序号) 有序序列 678/678 相同，加上有序 IR 仍 678/678 相同；其中包含重复节点的 31 对全部相同。
8. **顶层函数不在 `functions_and_modifiers_declared` 中**：0.7.1 起允许的自由函数在 0.8.0、0.8.3、0.11.6 中都放在 `compilation_unit.functions_top_level`。当前 D3 与节点指纹都没有覆盖它们（MANDO 语料只有 0.4/0.5，不受影响）。
9. **Slither 版本对照**（743 个不同源文件；`slither_versions_corpus.json`）：

| Slither | 结构与 0.8.0 相同 | 与 0.8.0 的结构差异 | 有序 IR 相同 | 失败 | 0.8.4–0.8.28 特征探针（6 个） |
|---|---:|---|---:|---:|---|
| 0.8.3 | 743 | 无 | 482 | 0 | 4/6；顶层 `using … for` 与全局用户定义运算符失败 |
| 0.9.6 | 721 | 47 个节点缺失，全部是 Slither 合成的 `slitherConstructorConstantVariables()` 的入口节点 | 62 | 0 | 6/6 |
| 0.10.4 | 369 | 多 1,999、少 47 | 51 | 3 | 6/6 |
| 0.11.6 | 369 | 多 1,999、少 50 | 51 | 3 | 6/6 |

   0.8.0 本身在 6 个特征中失败 4 个（自定义错误、UDVT、顶层 using、全局运算符）。0.10.4 与 0.11.6 在 `reentrancy_bonus.sol`、`reentrancy_cross_function.sol`、`reentrancy_insecure.sol`（solc 0.4.24）上抛 `AssertionError`（`expression_to_slithir.py` 中 `assert isinstance(right, TupleVariable)`，源码为 `(bool success, ) = msg.sender.call.value(x)("")`）。0.8.3 的 IR 差异主要是 `.balance` 从 `BALANCE` 操作改为 `SOLIDITY_CALL balance(address)`；0.9.6 的差异多为 IR 文本格式（例如 Emit 参数分隔符、类型标注）。`transient` 探针在所有版本都“构造成功”，包括早于该语法的 0.8.0，因此它只说明不崩溃，不说明正确建模。
10. **冻结的 6c 抽取代码依赖 dict 形式的 source_mapping**：`validate_slither._mapping` 在 source_mapping 不是 dict 时返回 `{}`；Slither 0.9 起 source_mapping 是对象。新版 Slither 下冻结抽取会静默丢失映射，CP0 的 `node_facts` 会在 `.get` 处报错。
11. **Slither 的使用者**：`node-sem` 与 `edge-sem` 分支中导入 slither 的生产代码只有 `scripts/DFG/dfg_v2/` 的验证与对照脚本（`node_sem/artifacts/.../runtime_archive` 下是归档副本）。NodeSem、EdgeSem 模型不读取 Slither 图。

## 复现

```bash
python3 -I verify_cp0.py <repo>
# 每个 Slither 环境各运行一次（jobs 由 cp0_v2/recon.json 生成：每个文件的升序选定版本；678 个文件的最低与最高 D3 版本）
python -I node_dump.py jobs.jsonl <solc 目录> out_<tag>_<w>.jsonl <w> <n>
python3 -I d16_analyze.py <out 目录> <repo>/compile_repair/artifacts/cp0_v2/recon.json
python -I d16_probe.py features/<文件>.sol <solc-0.8.38 路径>
```
