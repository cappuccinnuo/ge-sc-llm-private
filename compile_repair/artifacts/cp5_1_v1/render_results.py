"""Render final Markdown tables directly from the checked machine-readable results."""
from collections import Counter
import json
from pathlib import Path

from population import ART, OUT, load, sha256


def table(headers, rows):
    cells = [headers, ["---"]*len(headers)] + list(rows)
    return "\n".join("| " + " | ".join(map(str,row)) + " |" for row in cells)


def ratio(m):
    return str(m["numerator"])+"/"+str(m["denominator"])


def summary(m):
    return "、".join(str(k)+" "+str(v) for k,v in sorted(m.items()) if v) or "0"


def main():
    policy = load(OUT/"policy.json")
    selected = policy["policy"]
    real = load(OUT/"external_summary.json")
    bench = load(OUT/"benchmark_summary.json")
    assert bench["policies"] == [selected] and bench["limit"] == policy["limit"]
    data = bench["scores"][selected]
    lines = ["### 开发选版与每单元组合上限", "",
             "固定规则为 `"+selected+"`，每个单元最多实际编译 "+str(policy["limit"])+" 个依赖版本组合。"
             "以三个规则在真实开发集上的 D3 成功数为首要指标，缺包开发样本的编译、主 kept 和库文件字节用于次级比较。"
             "K 取所选规则下全部成功开发单元实际编译的最大组合数，覆盖其检查过的每个位置。", ""]
    rows = []
    assembly = {key: [] for key in policy["comparison"]}
    development = OUT/"real_dev.jsonl"
    assert sha256(development) == policy["dev_measurement_sha256"]
    with development.open(encoding="utf8") as observations:
        for row in map(json.loads, observations):
            if row["compiled_combinations"] == 0 and row["step3_seconds"] > 0:
                assembly[row["rule"]].append(row["step3_seconds"])
    for p,d in policy["comparison"].items():
        b = d["package_dev"]
        h = policy["uncapped_measurements"][p]
        totals = sum(int(k)*v for k,v in h["histogram"].items())
        rows.append([p,str(d["real_d3"])+"/"+str(d["real_units"]),totals,b["compiled"],ratio(b["main"]["kept"]),
                     str(b["original_package_files"]["equal"])+"/"+str(b["original_package_files"]["total"])])
    lines += [table(["规则","真实开发集 D3","实际编译组合总数","基准成功 / 8","主 kept","相同库文件"],rows),"",
              "各单元的首个成功位置、实际尝试清单、耗时及分布见 `real_dev.jsonl` 与 `policy.json`。", "",
              "下表统计第 3 步记录了耗时、实际编译组合数为 0 的开发运行。时间包含依赖筛选、组装及收据写入。K 只限制实际编译次数。","",
              table(["规则","运行数","第 3 步累计秒数","最长单次秒数"],
                    [[p,len(times),round(sum(times),2),round(max(times,default=0),2)] for p,times in assembly.items()]),"",
              "### 冻结规则后的损坏基准", "",
              "下表采用汇总分子和分母。CFG 边和调用的分母是保留事实的并集。逐单元均值、改动等级、逐样本分数见 `benchmark_summary.json` 与 `benchmark.jsonl`。", ""]
    rows, wrapped, names = [], [], []
    for split, groups in sorted(data.items()):
        for op, item in sorted(groups.items()):
            n=item["units"]
            exact_rate = f"{item['exact']}/{n} ({item['exact']/n:.1%})"
            names.append([split,op,summary(item["names"]),summary(item["change_levels"])])
            if op=="standard_json_input":
                wrapped.append([split,n,item["compiled"],item["recovered_nodes"],item["lost"],item["added"],exact_rate])
                continue
            a,b=item["main"],item["surviving"]
            rows.append([split,op,n,item["compiled"],ratio(a["kept"]),ratio(b["kept"]),
                         ratio(a["cfg_edges"]),ratio(b["cfg_edges"]),ratio(a["calls"]),ratio(b["calls"]),
                         item["removed_by_repair"],exact_rate])
    lines += [table(["划分","算子","单元","编译及 D3","主 kept","存活 kept","主 CFG","存活 CFG","主调用","存活调用","修复删除","exact"],rows),"",
              "standard JSON 包装的统计如下。","",
              table(["划分","单元","编译及 D3","恢复节点","lost","added","exact"],wrapped),"",
              table(["划分","算子","名称状态","改动等级"],names),""]
    br=[]
    for split,group in sorted(data.items()):
        item=group["unresolved_package_import"]["original_package_files"]
        br.append([split,item["equal"],item["total"],round(item["ratio"],4)])
    controls = []
    for item in sorted(bench["negative_control_successes"], key=lambda x:(x["operator"], x["split"], x["unit_id"])):
        paths = [path for step in item["accepted"] if step["step"] == 4 for path in step.get("path_search", [])
                 if path.get("selected") and Path(path["selected"]).name.casefold() == Path(path["path"]).name.casefold()]
        controls.append([item["operator"], item["split"], item["unit_id"],
                         ", ".join(str(step["step"]) for step in item["accepted"]), len(paths)])
    control_list = (table(["算子","划分","单元","接受步骤","已选中的项目内同名路径数"], controls) if controls
                    else "本轮三个对照算子中，因项目内已有同名文件而成功的样本为 0 个。")
    lines += [table(["缺包划分","字节相同文件","原库文件","比例"],br),"",
              "第 2–4 步利用项目内文件、离线发布版和可验证的导入路径。这三个步骤通常保留删除源文件、无效 I/O 路径和修改 pragma 所致的失败。三个对照算子共有 "+str(len(bench["negative_control_successes"]))+
              " 个成功样本。原改动和逐条路径依据见 `benchmark_summary.json` 的 `negative_control_successes`。","",control_list,
              "","### 真实语料与锁版本参照","",
              "9,138 个原主因目标中有 "+str(real["d3"])+" 个通过生产 D3，"+str(real["truncated"])+
              " 个触发实际编译组合上限。下表按最后接纳步骤和本次使用的最低身份等级统计。",""]
    groups={}
    for r in real["groups"]:
        key=r["corpus"],r["step"],r["tier"]
        c=groups.setdefault(key,Counter())
        c["units"]+=r["units"]
        if r["d3"]: c["d3"]+=r["units"]
        if r["truncated"]: c["truncated"]+=r["units"]
    lines += [table(["语料","最后步骤","身份","单元","D3","截断"],
                    [list(k)+[v["units"],v["d3"],v["truncated"]] for k,v in sorted(groups.items())]),"",
              "73 个 T1 单元来自同一测试项目。三种规则都在隐藏版本和清单范围后运行，参照分母包括未修复的单元。","",
              table(["规则","参照数","D3","同锁版本","同版本或闭包文件字节相同","截断"],[
                    [k,v["units"],v["d3"],v["versions"],v["version_or_bytes"],v["truncated"]]
                    for k,v in sorted(real["masked_t1_by_policy"].items())]),""]
    lines += ["另按成功单元实际接受的步骤计数。一次修复可先后采用多个步骤，所以下表各行不能相加作为成功总数。","",
              table(["语料","接受的步骤","最终通过 D3 的单元"],[
                    [r["corpus"],r["step"],r["units"]] for r in real["successful_units_by_accepted_step"]]),""]
    old_table=load(ART/"cp4_1_v1/cp3_failure_summary.json")
    new_table=real["failure_table"]
    before, after = old_table["primary"], new_table["primary"]
    for t in (old_table, new_table):
        assert sum(t["primary"]["total"].values())+sum(t["non_solidity_by_corpus"].values())+sum(t["unmeasured_by_corpus"].values())==31307
    old_categories = {r["category"]:r["units"] for r in before["category_unit_counts"]}
    new_categories = {r["category"]:r["units"] for r in after["category_unit_counts"]}
    lines+=["按 CP3.1 对同一批 31,307 个输入重新统计，可计量分母由 "+str(sum(before["total"].values()))+
            " 至 "+str(sum(after["total"].values()))+"。修复前有 "+str(sum(before["remaining_failures"].values()))+" 个失败单元，修复后有 "+
            str(sum(after["remaining_failures"].values()))+" 个。一个单元可有多个主因。语言排除项和未测单元分开留存在 `external_summary.json`。","",
            table(["剩余主因","修复前","修复后"],[[k,old_categories.get(k,0),new_categories.get(k,0)]
                for k in sorted(set(old_categories)|set(new_categories))]),""]
    with (OUT/"final_tables.md").open("x",encoding="utf8") as fp:
        fp.write("\n".join(lines))


if __name__=="__main__":
    main()
