# cr_pre_v1：方案 r1 的证据（Claude，2026-11-11）

本目录是写 `PROMPTS.md` r1 之前收集的证据（r1 时目录为 `scripts/compile_repair/`，r2 起为仓库根目录 `compile_repair/`），全部可复现。不是生产代码，任何 Prompt 都不导入这里的脚本。

## 环境（与用户 `mando` 环境不同，结论须由 CP0 在用户环境复核）

- 语料：本仓库 `experiments/ge-sc-data/source_code/<类别>/source_files/*.sol` 的拷贝，七类共 846 个文件，只读。
- 编译器：GitHub 发布页 `ethereum/solidity` 的 `solc-static-linux`，0.4.11–0.4.26、0.5.0–0.5.17 共 34 个版本，SHA256 见 `solc_github_static_SHA256SUMS`。0.4.10 及更早版本在 GitHub 发布页没有静态二进制（0.4.10 返回 404），所以这里无法运行 0.4.0–0.4.10。用户 6c 使用的是 solc-select 安装的 binaries.soliditylang.org 版本，来源不同。
- Slither：slither-analyzer 0.8.0、crytic-compile 0.2.4（与 6c 记录的版本相同），但运行在 Python 3.8.20 上（用户环境为 Python 3.7.12）；另装 setuptools<70 以提供 pkg_resources。
- 编译方式：`compile_repro.py` 直接调用 `solc <文件>`，按退出码判定；不经 crytic-compile。`slither_probe.py`、`cross_version.py` 经 Slither（内部用 crytic-compile）。

## 文件

| 文件 | 内容 |
|---|---|
| `corpus_stats.py` / `corpus_stats.json` | 各类 `source_files`、`cleaned_buggy_curated` 等目录的文件数、pragma 形式、首个版本号的小版本系列、文件名类型、标签型注释、import 计数 |
| `compile_repro.py` / `compile_repro.json` | A：按 `auto_version_solc.py` 规则（pragma 中第一个 x.y.z，无 pragma 用 0.4.25）每文件编译一次；B：A 不通过时，尝试合取 pragma 区间内所有可用版本 |
| `slither_probe.py` / `slither_probe.json` | 对 A 不通过的 39 个文件，用 B 中最低与最高可编译版本各跑一次 Slither |
| `cross_version.py` / `cross_version.json` | 同两次运行的节点比较：key4 =（合约、函数 full_name、节点类型、起始偏移），key5 = key4 + SlithIR，以及 source length |
| `probes/*.sol`、`probes/RESULTS.txt` | 三个 solc 行为探针（0.4.25、0.5.11） |

## 结论（数字均来自上述 JSON/日志）

1. 846 个文件中 0 个含 `import`；首个版本号只有 0.4.x 与 0.5.x；22 个没有 pragma；15 个文件有两条不同的 pragma。
2. A：807 通过，10 失败，29 个所选版本 ≤ 0.4.10（这里不可用：0.4.0×21、0.4.2×4、0.4.9×2、0.4.10×1、0.4.6×1）。10 个失败是 pragma 下界早于代码实际使用的语法（`^0.4.11` 下的 `view`/`pure`，`^0.4.13`–`^0.4.20` 下在 `(` 处的解析错误），或两条 pragma 时规则取了第一条（2 个文件的规则版本落在文件自身合取区间之外）。
3. B：39/39 在合取区间内、且与规则版本同一小版本系列中找到可编译版本。按退出码，846/846 可编译，不改源码。
4. 重入 + 访问控制两类：A 不通过 17 个（6 失败 + 11 不可用），与 6c 报告的 17 个（11 个 solc 失败 + 6 个映射不可比）总数相同；逐文件对应尚未核对（6c 完整报告只在用户本地）。
5. Slither 0.8.0：39 个文件、78 次运行全部成功。solc 0.4.11 时节点的 `filename_absolute`/`filename_used` 为 None，0.4.12 起正常；6c 的 6 个不可比文件（0.4.0/0.4.2/0.4.9，缺 CFG filename）与此症状一致。
6. 同一文件两个版本之间：key4 39/39 相同，key5（含 SlithIR）39/39 相同，source length 36/39 相同（3 个文件只有长度不同）。
7. 规则版本可编译但 ≤ 0.4.11 的文件有 4 个，会在 Slither 中静默丢失文件名。
8. 探针：等长空格替换 pragma 行后 0.4.25、0.5.11 均编译通过（只有警告），文件字节数不变；基类定义在派生类之后时 0.4.25、0.5.11 都报 “Definition of base has to precede definition of derived contract”；无函数体的内部函数声明在基类先出现时 0.4.25、0.5.11 都可编译。另：`^0.4.24` 原文件在 0.5.11 下报版本错误，空格替换后在 0.5.11 下可编译，说明 pragma 替换会越过作者声明的区间。

## 复现

```bash
python3 -I corpus_stats.py <repo>/experiments/ge-sc-data/source_code
python3 -I compile_repro.py <source_code 目录> <solc 目录> compile_repro.json
python -I slither_probe.py compile_repro.json <source_code 目录> <solc 目录> slither_probe.json      # Slither 0.8.0 环境
python -I cross_version.py slither_probe.json <source_code 目录> <solc 目录> cross_version.json
```
`<solc 目录>` 内文件名为 `solc-<版本>`。
