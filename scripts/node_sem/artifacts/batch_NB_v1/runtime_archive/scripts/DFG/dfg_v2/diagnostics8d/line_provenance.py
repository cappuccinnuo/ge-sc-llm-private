"""Prompt 8D D: provenance candidates for attached author line sets, read only."""
import argparse
import hashlib
import io
from pathlib import Path
import re
import subprocess
from scripts.DFG.dfg_v2.diagnostics8c import labels, scoring as s
from scripts.DFG.dfg_v2.diagnostics8c.common import checked_plan
from scripts.labeling_v2.safe_graph import read_graph
from .stratification import checked

VERSION = "prompt8d-line-provenance-v1"
FOCUS = (("reentrancy_node", "buggy_18.sol"),
         ("access_control_node", "buggy_18.sol"),
         ("access_control_node", "buggy_26.sol"))
CATEGORIES = {"reentrancy": "Re-entrancy", "access_control": "tx.origin"}

def numeric_file(file):
    match = re.fullmatch(r"buggy_(\d+)\.sol", file)
    if not match:
        raise ValueError("Unexpected SolidiFI filename")
    return int(match.group(1))

def line_set(value):
    if isinstance(value, str):
        value = labels._json_value(value)
    if isinstance(value, int):
        if value < 0:
            raise ValueError("Negative graph line")
        return {value}
    if isinstance(value, (list, tuple)):
        return set().union(*(line_set(x) for x in value)) if value else set()
    raise ValueError("Unsupported line representation")

def jaccard(left, right):
    left, right = set(left), set(right)
    union = left | right
    return float(len(left & right))/len(union) if union else 1.0

def ranking(query, candidates):
    rows = [dict(file=name, jaccard=jaccard(query, lines),
                 intersection=len(set(query)&set(lines)), union=len(set(query)|set(lines)),
                 candidate_line_count=len(lines), max_line=max(lines) if lines else None)
            for name, lines in candidates.items()]
    rows.sort(key=lambda row: (-row["jaccard"], numeric_file(row["file"])))
    top = rows[0]["jaccard"] if rows else None
    return dict(best=[row for row in rows if row["jaccard"] == top],
                all=rows, buggy_24=next((row for row in rows if row["file"]=="buggy_24.sol"),None))

def graph_line_sets(graph):
    attached, positive = {}, {}
    for node, attrs in graph.nodes(data=True):
        name = labels._json_value(attrs["source_file"])
        if not re.fullmatch(r"buggy_\d+\.sol", name):
            continue
        attached.setdefault(name, set())
        positive.setdefault(name, set())
        annotation = labels._json_value(attrs.get("node_info_vulnerabilities"))
        if annotation is None or annotation == []:
            continue
        if not isinstance(annotation, (tuple,list)):
            raise ValueError("Attached vulnerability record is not a sequence")
        for record in annotation:
            if not isinstance(record,dict) or "lines" not in record:
                raise ValueError("Invalid author annotation record")
            attached[name].update(line_set(record["lines"]))
        positive[name].update(line_set(attrs["node_source_code_lines"]))
    return attached, positive

def select_controls(audit, count=5):
    eligible=[]
    for task, record in audit["tasks"].items():
        for item in record["files"]:
            if item["solidifi"] and not item["truncation"]["truncated"]:
                eligible.append((task,item["file"]))
    # Round-robin categories, ascending numeric file ID: controls span both tasks.
    queues={task:sorted([x for x in eligible if x[0]==task],key=lambda x:numeric_file(x[1]))
            for task in sorted({x[0] for x in eligible})}
    result=[]
    while len(result)<count:
        added=False
        for task in sorted(queues):
            if queues[task] and len(result)<count:
                result.append(queues[task].pop(0));added=True
        if not added:
            raise ValueError("Not enough nontruncated controls")
    return result

def git_bytes(repo, path):
    return subprocess.check_output(["git","-C",str(repo),"show",labels.PIN+":"+path])

def run_line_provenance(plan_path, frozen_root, output, solidifi_repo=None):
    from process_graphs.tree_sitter_codeviews.utils import preprocessor
    plan=checked_plan(plan_path)
    frozen_root,output=Path(frozen_root),Path(output)
    if output.exists(): raise FileExistsError(str(output))
    audit=s.read(frozen_root/"A/audit.json")
    if audit["provenance"]["plan"] != s.ref(plan_path):
        raise ValueError("8C audit plan identity differs")
    repo=Path(solidifi_repo) if solidifi_repo else Path("/home/zhao/SmartContract/ge-sc-llm/data/SolidiFI-benchmark")
    actual=subprocess.check_output(["git","-C",str(repo),"rev-parse","HEAD"]).decode().strip()
    if actual != labels.PIN: raise ValueError("Pinned SolidiFI checkout differs")
    controls=select_controls(audit)
    graph_sets, inputs, mapped, mapping_records={},[],{},[]
    for task, task_record in plan["tasks"].items():
        ref=task_record["record"]["original_graph"]
        graph=read_graph(checked(ref))
        attached,positive=graph_line_sets(graph)
        graph_sets[task]=dict(attached=attached,positive=positive)
        inputs.append(dict(task=task,graph=ref))
    for category,csv_category in CATEGORIES.items():
        prefix="buggy_contracts/"+csv_category+"/"
        files=subprocess.check_output(["git","-C",str(repo),"ls-tree","-r","--name-only",
                                       labels.PIN,"--",prefix]).decode().splitlines()
        mapped[category]={}
        for relative in sorted(files):
            if not re.fullmatch(r"buggy_\d+\.sol",Path(relative).name): continue
            file=Path(relative).name
            source_bytes=git_bytes(repo,relative)
            csv_path=prefix+"BugLog_"+str(numeric_file(file))+".csv"
            csv_bytes=git_bytes(repo,csv_path)
            source=source_bytes.decode("utf8")
            cleaned=preprocessor.remove_comments("solidity",preprocessor.remove_empty_lines(source))
            mapping=labels.map_lines(source,cleaned)
            import csv
            records=list(csv.DictReader(io.StringIO(csv_bytes.decode("utf-8-sig"))))
            # Same explicit interval used by frozen 8C, source-coordinate mapping unchanged.
            raw=set()
            for record in records:
                normalized={key.strip().lower():value for key,value in record.items()}
                loc=int(normalized["loc"]);length=int(normalized["length"])
                if loc<1 or length<1: raise ValueError("Invalid pinned CSV interval")
                raw.update(range(loc,loc+length))
            lines={mapping["raw_to_clean"][line] for line in raw if line in mapping["raw_to_clean"]}
            mapped[category][file]=lines
            mapping_records.append(dict(category=category,file=file,source_git_path=relative,
                source_sha256=hashlib.sha256(source_bytes).hexdigest(),csv_git_path=csv_path,
                csv_sha256=hashlib.sha256(csv_bytes).hexdigest(),
                mapped_lines=sorted(lines),unmapped_raw_lines=sorted(raw-set(mapping["raw_to_clean"])),
                unmapped_cleaned_lines=mapping["unmapped_cleaned_lines"]))
    results=[]
    for task,file in list(FOCUS)+controls:
        category=plan["tasks"][task]["record"]["category"]
        query=graph_sets[task]["attached"][file]
        comparisons={"mapped_bug_lines_all_pinned_files":ranking(query,mapped[category])}
        for candidate_task,record in plan["tasks"].items():
            if record["record"]["category"]==category:
                comparisons[candidate_task+"_frozen_positive_stored_lines"]=ranking(
                    query,graph_sets[candidate_task]["positive"])
        results.append(dict(task=task,file=file,role="focus" if (task,file) in FOCUS else "control",
                            source=plan["tasks"][task]["record"]["sources"][file],
                            attached_lines=sorted(query),line_count=len(query),
                            max_line=max(query) if query else None,comparisons=comparisons))
    # Existing 8C same-file mapping must agree exactly for its included 80 files.
    checks=[]
    for task,record in audit["tasks"].items():
        category=record["category"]
        for item in record["files"]:
            if not item["solidifi"]: continue
            actual=sorted(mapped[category][item["file"]])
            if actual!=item["mapped_bug_lines_cleaned"]:
                raise ValueError("Pinned mapped line set differs from 8C: "+task+"/"+item["file"])
            checks.append([task,item["file"]])
    result=dict(version=VERSION,training_count=0,model_forward_count=0,
        bindings=dict(plan=s.ref(plan_path),audit=s.ref(frozen_root/"A/audit.json"),
                      solidifi_git_commit=labels.PIN,graphs=inputs),
        control_selection="five total, round-robin sorted task IDs; ascending numeric buggy IDs; nontruncated by frozen8C",
        controls=controls,queries=results,mapping_records=mapping_records,
        mapped_8c_exact_checks=checks,
        notes=["Attached union is from positive nodes only.",
               "Frozen positive-node lines use saved endpoints/synthetic singleton lines, never expanded into spans.",
               "Node and contract graph candidate sets are reported separately; no graph population mixing.",
               "Similarity is descriptive numeric-coordinate evidence, not proof of annotation provenance or a license to relabel."])
    output.mkdir(parents=False)
    s.write(output/"line_provenance.json",result)
    return result

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--plan",required=True);parser.add_argument("--frozen-root",required=True)
    parser.add_argument("--output",required=True);parser.add_argument("--solidifi-repo")
    args=parser.parse_args()
    result=run_line_provenance(args.plan,args.frozen_root,args.output,args.solidifi_repo)
    print("Compared",len(result["queries"]),"queries")
