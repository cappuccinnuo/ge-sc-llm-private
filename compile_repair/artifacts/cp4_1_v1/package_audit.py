"""Distinguish external package consumers, entries inside their own package and unknown vendor names."""
from collections import Counter,defaultdict
from batch import *
from compile_repair.evaluation.benchmark import _package_layout
app={r["unit_id"]:r.get("package") for r in rows(OUT/"new_eligibility.jsonl.gz")}
counts=Counter();examples=defaultdict(list);closed_subsets=[]
for base in rows(OLD/"bases.jsonl.gz"):
    if base["kind"]!="project":continue
    root=Path(base["project_root"]).resolve()
    entry=Path(base["entry"]).relative_to(root).as_posix()
    project=json.loads(Path(base["result"]["result_path"]).with_name("project.json").read_bytes())
    edges=[]
    for edge in project["imports"]:
        if not edge["resolved"]:continue
        src=Path(edge["source_path"]).relative_to(root).as_posix()
        dst=Path(edge["target_path"]).relative_to(root).as_posix()
        edges.append((src,dst,edge["path"].startswith(("./","../"))))
    roots={_package_layout(root,d) for s,d,relative in edges if relative}- {None}
    if app[base["unit_id"]]:reason="sample-eligible external dependency"
    elif roots:
        entries_inside=[(prefix,pkg) for prefix,pkg,_ in roots if entry.startswith(prefix+"/")]
        if entries_inside:
            reason="entry belongs to identified package"
            for prefix,pkg in entries_inside:
                moved={d for _,d,_ in edges if d!=entry and d.startswith(prefix+"/")}
                if (moved and any(s not in moved and d in moved and rel for s,d,rel in edges)
                        and all(not rel or s not in moved or d in moved for s,d,rel in edges)
                        and all(rel or s in moved or d not in moved for s,d,rel in edges)):
                    closed_subsets.append(dict(unit=base["unit_id"],corpus=base["corpus"],package=pkg,
                                                entry=entry,members=len(moved)))
                    break
        else:reason="no safely relocatable external package closure"
    elif any(any(x in ("openzeppelin","openzeppelin-solidity","zeppelin-solidity","@openzeppelin","node_modules") or x.startswith("@") for x in d.split("/")[:-1]) for s,d,rel in edges if rel):
        reason="vendor path lacks verified package layout"
    else:reason="no package-directory clue"
    key=(base["corpus"],reason);counts[key]+=1
    if len(examples[key])<2:examples[key].append(base["unit_id"])
saved("package_applicability_audit.json",dict(rows=[dict(corpus=c,reason=r,units=n,examples=examples[c,r])
    for (c,r),n in sorted(counts.items())],own_package_entries_with_a_closed_imported_subset=closed_subsets))
print("project reasons",dict(counts),"entry in package with a separate closed subset",len(closed_subsets),flush=True)
