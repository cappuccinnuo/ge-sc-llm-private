"""Fill the CP5.2 handover, change record and report from the completed acceptance tables."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
MODULE=HERE.parents[1]
load=lambda path:json.loads(path.read_bytes())
data=load(HERE/"acceptance.json")
audit=load(HERE/"code_audit.json")
movement=data["movement"]["outcomes"]
external=data["real"]
ir=data["partial_ir"]["cohorts"]
bench=data["benchmark"]["regression"]
m=movement["all"]
rel=external["missing_relative"]
untouched=external["unaffected"]
all_units=external["all"]
oldmove=bench["missing_relative_file_moved"]
flags="、".join("{} {}/{}".format(label,ir[name]["both_or_either_units"],ir[name]["units"]) for name,label in
               (("real_dev","真实开发集"),("benchmark","基准成功样本"),("mando","MANDO"),("cp3","CP3 基础抽样")))


def append(name, text, marker):
    p=MODULE/name
    if marker in p.read_text(encoding="utf8"):raise ValueError("记录已存在 "+name)
    with p.open("ab") as f:f.write(("\n"+text.strip()+"\n").encode("utf8"))


lines=["### 移动 v2 的配对实验","",
       "| 划分 | 抽样 | 预期错误触发 | 精确逆向还原 | 修复通过 D3 | 原邻域 exact | 新邻域 exact |",
       "|---|---:|---:|---:|---:|---:|---:|"]
for key,label in (("dev","开发"),("test","测试"),("all","合计")):
    s=movement[key]
    lines.append("| {} | {} | {} | {} | {} | {} | {} |".format(label,s["sampled"],s["triggers"]["included"],
                 s["inverse_full"],s["repaired"],s["old_neighbourhood_exact"],s["exact"]))
lines += ["","抽样沿用 20261122、原有项目划分和原移动算子的排序命名空间，每语料上限 200。DAppSCAN 有 6,139 项适用，Trace 有 920 项适用；最终 400 项全部与旧版移动样本配对。363 个修复成功中有 4 个未达到 exact。1 项节点无法完全对应，1 项计数器定义的映射未能验证，2 项 Yul switch 的来源编号未能验证。这四项均保留实测分。对应单元、图哈希和指标见 `continuation/v2_scoring_details.json`。","",
          "| 400 个触发样本的全图评分 | kept | CFG 边 | 调用 |",
          "|---|---:|---:|---:|"]
for k,label in (("all_triggered_metrics","全部 400 个"),("successful_only_metrics","其中通过 D3 的 363 个")):
    for s,label2 in (("main","主指标"),("surviving","存活部分")):
        v=m[k][s]
        lines.append("| {}，{} | {:.6f} | {:.6f} | {:.6f} |".format(label,label2,*(v[x]["pooled_ratio"] for x in ("kept","cfg_edges","calls"))))
lines += ["","kept 按匹配节点数和真值分母汇总。CFG 边与调用按多重集交集除以并集计算；分子、分母、丢失与新增节点总数见 `acceptance.json`。","","### 同一管线重跑 CP5.1 基准和真实单元","",
    "| 基准算子 | 单元 | CP5.1 D3 | CP5.2 D3 | D3 与图 SHA256 均相同 |","|---|---:|---:|---:|---:|"]
for op,s in sorted(bench.items()):
    lines.append("| `{}` | {} | {} | {} | {} |".format(op,s["units"],s["prior_d3"],s["current_d3"],s["unchanged_d3_and_graph_sha"]))
lines += ["","旧移动算子新增 90 个通过 D3 的样本。90 项均经两轮改写，并改动了被移动文件自身的出向导入。该位置超出本步新增的入向导入字面量范围。89 项的 kept、CFG 边、调用三个指标均为 1，另 1 项的 Yul switch 来源编号未能验证；这 90 项均保留 exact=false。见 `continuation/old_move_recoveries.json`。","","| 外部语料范围 | 单元 | CP5.1 D3 | CP5.2 D3 | 新增通过 | 原通过后失败 | D3 与图 SHA256 均相同 |",
          "|---|---:|---:|---:|---:|---:|---:|"]
for name,label in (("all","全量"),("missing_relative","含缺相对文件"),("io_error","含 I/O 错误"),("missing_or_io","两者并集"),("unaffected","其余单元")):
    s=external[name];lines.append("| {} | {} | {} | {} | {} | {} | {} |".format(label,s["units"],s["old_d3"],s["new_d3"],
       s["improved"],s["lost"],s["d3_and_graph_equal"]))
lines += ["","子集由冻结的初始主要原因决定，缺相对文件和 I/O 错误两行有交集。历史评分对照只改变评分；这两张重跑表使用实际重新运行的工具结果。逐项核对见 `continuation/benchmark_rerun.jsonl` 与四份 `continuation/real_??.jsonl`。","","### 生产 Slither 的部分 IR","",
          "| 范围 | 单元 | 有任一标记的单元 | 被标记的合约实例 | 顶层函数错误条数 | 与原图一致的单元 |","|---|---:|---:|---:|---:|---:|"]
for name,label in (("real_dev","真实开发集 CP5.1 成功项"),("benchmark","CP5.1 基准成功项"),("mando","MANDO 成功项"),("cp3","按语料、编译器小版本分层的 CP3 成功基础单元")):
    v=ir[name];lines.append("| {} | {} | {} | {} | {} | {} |".format(label,v["units"],v["both_or_either_units"],v["contracts"],v["top_level_messages"],v.get("raw_graph_facts_equal",843)))
lines += ["","合约实例按每次构图计数，各范围单独统计。MANDO 核对完整图字节，其余三组对照加溯源标记前的原生图事实及哈希。`cp3_19463` 的 `BalancerLBPSwapper` 与 `OracleRef` 均有标记，顶层函数日志为 0，该次回放的图事实与原记录相同。D25 待用户决定；本步记录观测，D3 沿用既有定义。711 个历史项目使用原编译器、原目录及原设置，另行实测了绝对项目根参数；每项的预登记、成功的 solc 收据和原参数都已核对。其余 2,660 份开发、基准和 CP3 回放使用原成功编译收据。","","### 回归、资源与封存","",
          "MANDO 846 项中，843 份成功图逐字节等于 v5，另 3 项保留原有失败状态。对 18 个生产文件在每套测试运行前后核对了 SHA256。production 模块 1,155 项通过、6 项跳过；mando 模块 671 项通过、490 项跳过；DFG v2 2,653 项通过，9 条警告。354 个 DFG 代码引用与冻结基线相同。",
          "四个生产文件的变动合计增加 278 行、删除 38 行。逐文件函数名与行数见 `code_audit.json`，阶段用时见各 `*_exit.json`。本地 CPU 运行，下载 0，训练与外部 LLM 调用均为 0，费用 0 美元。首轮封存测试的并发编辑失败、收据定位修正、原始导入路径与允许路径差异以及用户原话见 `docs/DECISIONS.md` 的 CP5.2 节。"]
lines += ["", "| 生产文件 | 新增行 | 删除行 | 变动函数 |", "|---|---:|---:|---|"]
for path, info in sorted(audit["changed"].items()):
    names = "、".join("`"+name+"`" for name in info["functions"])
    lines.append("| `{}` | {} | {} | {} |".format(path.replace("compile_repair/","",1),
                 info["added"],info["removed"],names))
append("CP5_REPORT.md","\n".join(lines),"### 移动 v2 的配对实验")

common=("旧移动样本的 D3 通过数为 CP5.1 的 {prior_d3}/400 与 CP5.2 的 {current_d3}/400；".format(**oldmove)+
        "真实缺相对文件的 D3 通过数为 CP5.1 的 {old_d3}/{units} 与 CP5.2 的 {new_d3}/{units}。".format(**rel)+
        "其余 {units} 个外部单元的 D3 和图 SHA256 逐项相同。".format(**untouched))
endlog=f"""400 个 v2 样本全部触发并精确逆向还原，363 项实际修复通过 D3，359 项达到新邻域 exact。{common} 全量 D3 为 {all_units['new_d3']}/9,138。部分 IR 检出的单元为{flags}。各自的合约实例数、顶层函数计数和全图分数见 CP5_REPORT 的 CP5.2 节与 acceptance.json。

### 59.4 用户批准、原文差异与待确认设计

用户批准对包装单文件做有限身份转换并保留原分。WSL 恢复、按原收据定位、封存源码后的回归续跑和 711 次历史参数补编均有独立授权。WSL 单独重启后实测两侧代理及直连阻断；后来个别新启动器再次超时，既有计算保持运行，原生启动方式和共享目录读取完成了复核。17 份移动收据指向最终接受轮次，核对其哈希与顶层记录相同后按登记位置读取。首轮生产用例在复制 benchmark.py 后发现工作树已更新，18 个副本均匹配封存值。另一次 IR 清单预检把导入来源路径当作工作副本路径，首个 Slither 调用前停止。独立核验全部 3,371 份清单后，按用户批准的范围在新目录续作，保留首轮数据。D25 仍待用户结合实测比例决定。

### 59.5 验收、资源、未执行事项与停止

production 回归通过 1,155 项、跳过 6 项；mando 通过 671 项、跳过 490 项；DFG v2 通过 2,653 项。843 份 MANDO 成功图等于 v5，354 个 DFG 引用与冻结值相同，生产文件保持 18 个。四个生产文件改动 278 行新增、38 行删除；见 code_audit.json。CPU 运行、无下载、无 HGT 训练、无外部 LLM 调用，费用 0 美元。文档按各自追加边界执行 doc_check，命令、逐文件结果及最终 SHA256 见本批 final_doc_check.json。"""
append("docs/CHANGE_LOG.md",endlog,"### 59.4 用户批准")
append("PROGRESS.md",f"""## CP5.2 相对导入链、文件级 exact 与部分 IR（2026-11-24，修改 AI 为 Codex）

修改 pipeline.py、rules/dependencies.py、evaluation/benchmark.py、toolchain/slither.py，新增 tests/test_cp52.py。313 份漏修逐项归因。v2 的 400 项均触发并精确逆向还原，363 项通过 D3，359 项达到 exact。重算 950 个历史包装样本得到 950 个 exact。{common}

两套环境分别通过 1,155 和 671 项模块测试，DFG v2 通过 2,653 项。测试命令为各环境的 `python -B -m pytest -x -q -p no:cacheprovider`，测试目录、临时目录与源码哈希见 `artifacts/cp5_2_v1/frozen_suites/`。生产文件 18 个，冻结 DFG 引用 354 个。843 个 MANDO 图均等于 v5。研究方案差异、用户授权及首轮停点见 `docs/CHANGE_LOG.md` §59；完整指标见 `CP5_REPORT.md`。D25 待用户决定。""","## CP5.2 相对导入链")

h=MODULE/"docs/HANDOVER.md"
initial=load(HERE/"baseline.json")["documents"]["docs/HANDOVER.md"]["sha256"]
assert hashlib.sha256(h.read_bytes()).hexdigest()==initial
text=h.read_text(encoding="utf8")
start=text.index("> 本轮交接先读");end=text.index("\n",start)
text=text[:start]+"> 本轮先读第 0–5 节、CP5_REPORT.md 的 CP5.2 节、CHANGE_LOG §59 及 artifacts/cp5_2_v1/README.md。"+text[end:]
start=text.index("\n\n",text.index("## 0."))+2;end=text.index("\n\n",start)
text=text[:start]+f"CP5.2 完成验收，v2 移动样本 363/400 通过 D3、359/400 达到 exact，950 个包装样本全部达到 exact。全量外部语料 {all_units['new_d3']}/9,138 通过 D3。下一步为 CP5.2 审查，部分 IR 是否纳入 D3 由用户决定。"+text[end:]
text=text.replace("| 下一步 | CP5.2 → 审查 → CP6 |","| CP5.2 | 313 项漏修归因、有限链、文件评分及部分 IR 测量完成，843 个 MANDO 图等于 v5 |\n| 下一步 | 审查 CP5.2，用户评估 D25，然后按计划开展 CP6 |",1)
for heading,paragraph in [("## 3. 环境","CP5.2 基线为 fba94f1d，使用独立 compile-repair 工作树，证据及续作均位于 artifacts/cp5_2_v1。"),
    ("## 4. 必读与下一步","CP5.2 的 18 个生产文件在三套回归前后逐项核验。WSL 恢复和实测代理保护的依据在本批 network_recovery.json 与 launcher_continuity.json。"),
    ("## 5. 关键路径","复核 CP5.2 时先看 acceptance.json、diagnosis_details.json、v2_scoring_details.json 和 IR 的四个分母，再核对 D25 的决策范围。v2_scoring_details.json 位于本批 continuation 下。"),
    ("## 6. 交接记录","CP5.2 的索引为 artifacts/cp5_2_v1/README.md。完整运行工作副本位于同级 compile-repair-local/cp5_2_v1/，每项压缩记录的哈希见 record_archives.json。")]:
    text=text.replace(heading,paragraph+"\n\n"+heading,1)
text+="\n### 2026-11-24 CompileRepair CP5.2 完成（修改 AI 为 Codex）\n\n"
text+=f"专用工作树以 fba94f1d 为起点，执行 PROMPTS r2.24 §4.6i。生产改动集中于四个既有模块，细节及函数清单见 code_audit.json。本次更新交接第 0–5 节的状态、环境、阅读顺序及证据路径。\n\n"
text+=f"400 个 v2 移动样本均通过触发和逆向对照。363 项通过实际修复，359 项达到 exact。{common} 原 950 份包装结果均经验证达到 exact。\n\n"
text+=f"部分 IR 检出的单元为{flags}。17 份移动收据使用已接受轮次的位置，按原指针核对双份哈希后完成诊断。用户批准保留包装原分，并在验证唯一源身份后转换图表示。首份 IR 清单保留导入来源绝对路径，逐项核对逻辑目标后恢复原清单；711 个旧参数项目按原目录另行编译。D25 仍待用户决定。\n\n"
text+="全部 843 份 MANDO 成功图与 v5 相同，另 3 项保留原失败。首轮回归因测试复制源码时评分函数仍在编辑而停止；冻结 18 个生产文件后在新目录通过全部三套回归，354 个 DFG 引用核验完成。WSL 单独重启后验证了代理和直连阻断；后续启动器间歇超时时保留运行中的作业，通过原生启动方式和共享目录核验收据。CPU 评估费用 0 美元，未执行下载或训练。\n"
h.write_bytes(text.encode("utf8"))
append("docs/DECISIONS.md",f"""### CP5.2 的 D25 测量结果（2026-11-24，记录者 Codex）

各范围检出的单元为{flags}。cp3_19463 的两个合约被标记；完整结果及合约计数见 CP5_REPORT 的 CP5.2 部分。D25 继续保留待定状态。""","### CP5.2 的 D25 测量结果")
append("artifacts/cp5_2_v1/README.md","""## 最终结果入口

`acceptance.json` 汇集四个测量范围、真实语料分母、逐算子回归和 v2 全图指标。`record_archives.json` 登记原始逐项表及其 gzip 文件的 SHA256 和行数，Git 中的可移植副本在 `packed/`。在新的检出中，可按清单将 gzip 副本解压到原相对路径并核验原始 SHA256。完整手写夹具、编译器输出、图及工具日志保存在本机。文档核验见 `final_doc_check.json`。""","## 最终结果入口")
