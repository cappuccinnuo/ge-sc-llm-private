"""Frozen CP3 population, CP4 split identities, and per-entry input provenance."""
from collections import Counter
from functools import lru_cache
import gzip
import hashlib
import json
from pathlib import Path
import sys

OUT = Path(__file__).resolve().parent
ART = OUT.parent
CP5 = ART / "cp5_v1"
ROOT = ART.parents[1]
LOCAL = ROOT.parent / "compile-repair-local" / OUT.name
sys.path.insert(0, str(ROOT))
from compile_repair.core.model import CompilationUnit, SourceFile
from compile_repair.core.store import read_checked_json, sha256
from compile_repair.evaluation.benchmark import group_and_split
from compile_repair.toolchain.project import ProjectIndex, resolve_project


def load(path):
    return json.loads(Path(path).read_bytes())


def save(path, data):
    with Path(path).open("x", encoding="utf8") as fp:
        json.dump(data, fp, ensure_ascii=False, sort_keys=True, indent=2)
        fp.write("\n")


def checked_rows(path, expected):
    raw = Path(path).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == expected, str(path)
    if str(path).endswith(".gz"):
        raw = gzip.decompress(raw)
    return list(map(json.loads, raw.splitlines()))


def split_identity(unit):
    corpus = unit["corpus"]
    if unit["project_root"]:
        root = Path(unit["project_root"])
        checkout = next(p for p in root.parents if p.name.endswith("@"+unit["repository_commit"]))
        name = root.relative_to(checkout).as_posix()
    elif corpus == "Trace_on_chain":
        name = Path(unit["path"]).stem.lower()
    elif corpus == "Trace_CVEs":
        name = Path(unit["path"]).stem.upper()
    else:
        name = unit["entry_sha256"]
    return group_and_split(corpus, name)


@lru_cache(maxsize=1)
def population():
    meta = load(CP5 / "measurement.json")
    evidence = load(CP5 / "checkpoint_seal.json")["files"]
    assert sha256(CP5 / "measurement.json") == evidence["measurement.json"]
    rows = checked_rows(CP5 / "measurement_units.jsonl.gz", meta["units_sha256"])
    inv = checked_rows(ART / "cp3_continue_v1/unit_inventory.jsonl", meta["inputs"]["inventory_sha256"])
    old = checked_rows(ART / "cp4_1_v1/cp3_attributions.jsonl.gz", meta["inputs"]["attributions_sha256"])
    by_id = {u["unit_id"]:u for u in inv}
    primary = {u["unit_id"]:u for u in old}
    assert len(by_id) == len(primary) == 31307
    targets = {}
    for row in rows:
        if not row["primary"]:
            continue
        uid = row["unit_id"]
        item, baseline = by_id[uid], primary[uid]
        assert row["entry_sha256"] == item["entry_sha256"] == baseline["entry_sha256"]
        assert row["result_sha256"] == baseline["selected_result"]["result_sha256"]
        group, split = split_identity(item)
        targets[uid] = dict(row, group=group, split=split, source=item, ref=baseline["selected_result"])
    assert len(targets) == meta["primary_union"] == 9138
    return targets, primary


@lru_cache(maxsize=16)
def project_index(path):
    return ProjectIndex(path)


def entry(target):
    ref, source = target["ref"], target["source"]
    path = Path(source["path"])
    baseline = read_checked_json(ref["result_path"], ref["result_sha256"])
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    assert digest == target["entry_sha256"]
    index = project_index(source["project_root"]) if source["project_root"] else None
    info = Path(ref["result_path"]).with_name("project.json")
    remaps = load(info)["remappings"] if index and info.is_file() else ()
    project = resolve_project(index.root, path, remaps, index) if index else None
    files = project.files if project else (SourceFile(str(path),digest,raw,source["kind"]),)
    assert [(f.path,f.sha256) for f in files] == [(f["path"],f["sha256"]) for f in baseline["inputs"]]
    return CompilationUnit(target["unit_id"], files), project, index


def audit():
    targets, _ = population()
    basepath = ART / "cp4_v1/bases.jsonl.gz"
    old = load(CP5/"self_summary.json")
    assert sha256(basepath) == old["base_catalog_sha256"]
    invfile = ART / "cp3_continue_v1/unit_inventory.jsonl"
    inv = {r["unit_id"]:r for r in map(json.loads, invfile.read_bytes().splitlines())}
    verified = 0
    with gzip.open(basepath, "rt") as fp:
        for base in map(json.loads, fp):
            if base["unit_id"] in inv:
                assert tuple(split_identity(inv[base["unit_id"]])) == (base["group"],base["split"])
                verified += 1
    subsets = {s:[r for r in targets.values() if r["split"]==s] for s in ("dev","test")}
    assert not {r["group"] for r in subsets["dev"]} & {r["group"] for r in subsets["test"]}
    info = dict(units=len(targets), split_reference_bases=verified, units_per_split={k:len(v) for k,v in subsets.items()},
                t1_per_split={s:sum(r["tier"]=="T1" for r in group) for s,group in subsets.items()},
                primary_per_split={s:dict(Counter(c for r in group for c in r["primary"])) for s,group in subsets.items()})
    with gzip.GzipFile(filename=str(OUT/"population.jsonl.gz"),mode="xb",mtime=0) as fp:
        for u in targets.values():
            fp.write((json.dumps({k:u[k] for k in ("unit_id","entry_sha256","corpus","group","split","tier","primary","result_sha256")},sort_keys=True)+"\n").encode())
    info["membership_sha256"] = sha256(OUT/"population.jsonl.gz")
    save(OUT/"population.json",info)
    print(info,flush=True)


if __name__ == "__main__":
    audit()
