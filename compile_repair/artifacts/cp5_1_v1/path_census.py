"""Count local basename and import-symbol evidence in the frozen CP3 primary populations."""
from collections import Counter, defaultdict
from functools import lru_cache
import json
from pathlib import Path
import posixpath

from population import OUT, entry, population, save
from compile_repair.core.store import emit, sha256
from compile_repair.rules.dependencies import import_symbols, source_declarations, package_spec
from compile_repair.toolchain.solc import lexical_tokens


@lru_cache(maxsize=4096)
def exports(data):
    return set(source_declarations(data)[0])


@lru_cache(maxsize=30)
def names(index):
    result = defaultdict(list)
    for p in index.entries:
        result[p.name.casefold()].append(p)
    return result


def main():
    targets, _ = population()
    groups = defaultdict(Counter)
    with (OUT / "path_census.jsonl").open("x",encoding="utf8") as fp:
        for t in targets.values():
            labels = sorted(set(t["primary"]) & {"missing_relative_file","io_error"})
            if not labels:
                continue
            unit, project, index = entry(t)
            files = {f.path:f.content for f in unit.sources}
            facts = []
            issues = project.issues if project else ()
            known = set().union(*(exports(v) for v in files.values())) if project else set()
            for row in issues:
                if row.get("category") not in labels or "source_path" not in row:
                    continue
                spelling = row["path"]
                # A URI spelling is only a lookup key in this census. Production
                # never rewrites a URL to a local basename.
                leaf = posixpath.basename(spelling.partition(":")[2] if spelling.startswith("file:") else spelling)
                matches = [p for p in names(index).get(leaf.casefold(), ()) if str(p)!=row["source_path"]]
                raw = files[row["source_path"]]
                required = import_symbols(raw,row)
                used = {v.decode("ascii") for _,_,k,v in lexical_tokens(raw) if k=="word" and v.isascii()}
                supported = []
                for p in matches:
                    declared = exports(p.read_bytes())
                    needed = required or (used & declared - known)
                    if needed and needed <= declared:
                        supported.append(dict(file=p.relative_to(index.root).as_posix(), symbols=sorted(needed)))
                facts.append(dict(category=row["category"], importer=row["importer"], path=spelling,
                    applicable_relative=spelling.startswith(("./","../")) and not package_spec(spelling) and row["supported_literal"],
                    matching_basename=[p.relative_to(index.root).as_posix() for p in matches],
                    same_case=sum(p.name==leaf for p in matches), symbols=supported))
            for label in labels:
                rows = [r for r in facts if r["category"]==label]
                c = groups[label]
                c["units"] += 1
                c["located_import"] += bool(rows)
                c["has_same_basename"] += any(r["matching_basename"] for r in rows)
                c["has_exact_case_basename"] += any(r["same_case"] for r in rows)
                c["has_unique_basename"] += any(len(r["matching_basename"])==1 for r in rows)
                c["has_candidate_with_required_symbols"] += any(r["symbols"] for r in rows)
                c["has_unique_symbol_candidate"] += any(len(r["symbols"])==1 for r in rows)
                c["eligible_relative_with_symbols"] += any(r["applicable_relative"] and r["symbols"] for r in rows)
            emit(fp,dict(unit_id=t["unit_id"], corpus=t["corpus"], categories=labels, has_project=bool(project),
                         source_sha256=t["entry_sha256"], imports=facts))
    assert groups["missing_relative_file"]["units"]==412 and groups["io_error"]["units"]==28
    save(OUT/"path_census.json",dict(by_primary_category=groups,rows_sha256=sha256(OUT/"path_census.jsonl"),
         basis="Count distinct units with at least one target import at the indicated stage; basename uses casefold and exact case is also reported. Required symbols precede pragma and compiler validation."))
    print(dict(groups),flush=True)


if __name__=="__main__":
    main()
