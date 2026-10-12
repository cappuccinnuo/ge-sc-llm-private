# labeling_v3：通用图节点标签标注器（测试代码）

2026-10-10 新建。全部在 `Test_code/` 下，没有修改任何正式代码或已有数据。

## 规则（四步，7 类漏洞通用）

1. **取标注行（原始源码行号）**：SolidiFI 取 BugLog 每行的 `range(loc, loc+length)`；SmartBugs 取 `vulnerabilities.json` 中该文件的 `lines`。
2. **换算到预处理坐标**：tree-sitter 构图前先去空行、去注释，节点行号是预处理后的行号。
3. **取节点端点**：普通节点取标签尾部的 `[首行, 末行]`；`end_if` / `end_loop` 取标签开头的 0 基起始行（单个值）。
4. **求交**：端点落在标注行里即为漏洞节点，并把整条记录挂到节点上。

## 两种模式

| 模式 | 行为 | 用途 |
|---|---|---|
| `clean` | 只用上面四步；SmartBugs 记录按漏洞类别过滤 | 源码层面正确的标签，做后续研究 |
| `author` | 另外复现作者数据的两个通用行为，并对 `author_overrides.json` 里的文件直接使用作者自己的行号列表 | 与论文 / 作者图逐节点对齐 |

`author` 模式的两个通用行为：SmartBugs 记录不按类别过滤；同一行既有代码又有 `/* */` 注释时，该行不参与换算。

## author_overrides.json 是什么

7 类共 423 个漏洞合约里，有 17 个文件的作者标注无法由规则推出，原因有两种：

- **SolidiFI（13 个，文件名是 `buggy_12/18/26.sol`）**：BugLog 中有重叠的行（同一行被登记两次），作者的行号换算从重叠处附近开始失效，后面的标注行全部丢失，换成了超出文件长度的无效行号。
- **SmartBugs（4 个）**：作者使用的行号与公开标注不同。

这 17 个文件的作者记录原样存放在 `author_overrides.json`，由 `fit_author_overrides.py` 从作者图中提取。其余 406 个文件完全由规则从公开数据生成。

## 验证结果

`validate_against_author.py`，在作者的 7 张融合图上逐节点比较：

| 漏洞类型 | 作者 / 论文 | clean | author（仅规则） | author |
|---|---|---|---|---|
| access_control | 2,977 | 3,114（差 137） | 差 137 | 差 0 |
| arithmetic | 5,395 | 5,722（差 327） | 差 327 | 差 0 |
| denial_of_service | 4,106 | 4,106（差 0） | 差 0 | 差 0 |
| front_running | 10,400 | 10,889（差 491） | 差 491 | 差 0 |
| reentrancy | 6,570 | 6,784（差 216） | 差 217 | 差 0 |
| time_manipulation | 5,800 | 6,020（差 220） | 差 219 | 差 0 |
| unchecked_low_level_calls | 2,352 | 2,435（差 91） | 差 90 | 差 0 |

`label_local_graph.py` 把同一套规则用在本地自建的重入、访问控制融合图上，`author` 模式与作者图对齐后差异为 0。

## 文件

| 文件 | 作用 |
|---|---|
| `author_rule.py` | 规则本身，不读取任何作者图 |
| `fit_author_overrides.py` | 找出规则推不出的文件，生成 `author_overrides.json` |
| `validate_against_author.py` | 在 7 张作者图上验证三种标签 |
| `label_local_graph.py` | 给本地构建的图打标签，可选与作者图对比 |
| `run_local.sh` | 对重入、访问控制两张本地图跑两种模式 |
| `artifacts/v1/` | 生成的带标签图（含 token 特征，可直接训练） |

## 运行

```bash
conda activate mando
cd /home/zhao/SmartContract/ge-sc-llm
python -B Test_code/labeling_v3/fit_author_overrides.py
python -B Test_code/labeling_v3/validate_against_author.py
bash Test_code/labeling_v3/run_local.sh v2     # 输出目录已存在时换一个版本号
```

## 限制

- 13 个 SolidiFI 文件的失效机制只定位到"与重叠的 BugLog 行有关"，没有还原出能预测失效位置的规则，所以用例外表而不是规则来复现。
- `author` 模式的目标是对齐作者数据，不代表这些标签更正确；`buggy_18.sol` 等文件里大量真实注入的漏洞行在作者数据中是负例。
- 本地图目前只有重入和访问控制两类，其余 5 类只在作者图的节点上验证了标注规则，尚未验证本地构图。
