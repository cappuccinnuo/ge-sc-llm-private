# cr_pre_v2：外部语料结构证据（Claude，2026-11-11）

方案 r2 选择外部语料与设计确定性层之前的只读统计。只看文件结构与源码文本，没有编译。所有仓库都没有 LICENSE 文件，仅作研究用途；使用前由用户确认。

## 来源与版本

| 语料 | 仓库 | 提交 |
|---|---|---|
| DAppSCAN | github.com/InPlusLab/DAppSCAN（`DAppSCAN-source/contracts`） | 66a56619c44770e05c2db600fa6468115ff0dcd5 |
| SOChecker 评估片段 | github.com/BugmakerCC/SOChecker（`evaluation/RQ1/*.json` 的 input 字段） | 5e56d7542ac1f4d81004d05b9375c7042a506b0c |
| Trace 数据集 | github.com/BugmakerCC/Trace（`datasets/`） | 4260215b5330293db7739d9fadeecf014ef97816 |

## DAppSCAN（`dappscan_stats.py` → `dappscan_stats.json`）

- 608 个项目目录，21,457 个 `.sol` 文件（跳过 node_modules；实际没有任何项目带 node_modules）。
- 473 个项目含 `import`；405 个项目至少有一条无法在仓库内静态解析的 import（包导入，或相对路径指向不存在的文件）。
- 相对导入：38,122 条可找到，1,094 条目标文件缺失。
- 包导入前列：`@openzeppelin/contracts` 4,783，`@openzeppelin/contracts-ethereum-package` 1,181，其他裸路径 1,111，`@openzeppelin/contracts-upgradeable` 668，`openzeppelin-solidity` 597，`@0x/contracts-utils` 523，`@0x/contracts-exchange-libs` 341，`@pancakeswap-libs/pancake-swap-core` 328，`@aragon/os` 198，`@0x/contracts-erc20` 165，`zeppelin-solidity` 154，`@uniswap/v2-core` 130，`@uniswap/v3-core` 108 等（完整列表见 JSON）。
- 构建配置：606/608 个项目没有 hardhat/truffle/foundry 配置、package.json、remappings.txt 或 brownie 配置；只有 1 个 hardhat、1 个 truffle、2 个 package.json。
- pragma 首个版本号的小版本系列（按文件）：0.5 6,552；0.6 5,464；0.8 4,222；0.4 3,503；0.7 1,542；无 pragma 135；无法解析 35；另有 0.9 与 6.0 各 2 个（疑似书写错误，待 CP3 核对）。

## SOChecker 评估片段

- `evaluation/RQ1/ours.json` 等含 897 条 Stack Overflow 片段（input）。其中 656 条文本含 `contract ` 或 `function `；其余包含非 Solidity 内容（例如第一条是 Hardhat 的 JavaScript 配置）。

## Trace 数据集

- `on-chain/`：5,000 个单文件（以地址命名）。
- `repo-level/`：83 个项目，3,092 个 `.sol` 文件；深度 3 以内没有 truffle/hardhat 配置或 package.json。
- `CVEs/`：15 个单文件。

## 对方案的含义

- 依赖补全是外部语料的主要工作量；只覆盖 OpenZeppelin（DAI 的范围）不够，需要按导入包频次建立离线库索引。
- 几乎没有构建配置，项目编译需要模块自己组装输入（导入图、remapping、库源码），不能依赖 crytic-compile 的框架模式。
- 版本跨 0.4–0.8，版本策略的“0.4/0.5 系列”假设只对 MANDO 语料成立，r2 中改为一般规则。
- 缺失的相对导入（1,094 条）需要单列：一部分可能在项目内其他位置（缺失文件搜索），其余只能由桩或代理处理。
