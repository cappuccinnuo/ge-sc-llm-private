"""Inventory relative package-layout clues without reading labels or changing source."""
from collections import Counter,defaultdict
from batch import *
occurrences=Counter();examples=defaultdict(list);units=Counter()
for base in rows(OLD/"bases.jsonl.gz"):
    if base["kind"]!="project":continue
    path=Path(base["result"]["result_path"]).with_name("project.json")
    project=json.loads(path.read_bytes());root=Path(project["root"]);names=set()
    for d in project["imports"]:
        if not d["resolved"] or not d["path"].startswith(("./","../")):continue
        parts=Path(d["target_path"]).relative_to(root).parts
        for i,part in enumerate(parts[:-1]):
            if part=="node_modules" or part in ("openzeppelin","openzeppelin-solidity","zeppelin-solidity") or part.startswith("@"):
                k="/".join(parts[i:i+2]);occurrences[k]+=1;names.add(k)
                if len(examples[k])<3:
                    examples[k].append(dict(unit=base["unit_id"],corpus=base["corpus"],tail="/".join(parts[i:]),manifest=str(path)))
    units.update(names)
saved("package_layout_inventory.json",dict(occurrences=occurrences,candidate_units=units,examples=examples))
print("root patterns",len(occurrences),units.most_common(24))
