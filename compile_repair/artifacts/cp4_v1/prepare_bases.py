"""Validate the CP3.2 population and every successful unit's historical D3 and graph."""
from pathlib import Path
import time
from batch import ART, OUT, ROOT, SEED, Counter, checked, frozen, gzip, json, receipt_stream, save, sha
from compile_repair.evaluation.benchmark import group_and_split, stratified_sample

start=time.monotonic()
source_inventory=ART/"cp3_continue_v1/unit_inventory.jsonl"
source_population=ART/"cp3_2_v1/unit_attributions.jsonl.gz"
original={r["unit_id"]:r for r in (json.loads(l) for l in frozen(source_inventory).splitlines())}
raw_population=frozen(source_population)
cp32=json.loads(frozen(ART/"cp3_2_v1/seal.json"))
assert sha(raw_population)==cp32["artifacts"][source_population.name]["sha256"]
v5=ART/"cr_store_mando_v5"
vseal=json.loads(checked(v5/"seal.json","db925ee1642b5f8eae79d20defbbec673ffbaa7b4a0bb37cc270027bb1a8372b"))
old={r["inputs"][0]["path"]:r for r in (json.loads(l) for l in checked(v5/"manifest.jsonl",vseal["files"]["manifest.jsonl"]).splitlines())}
raw_groups, input_hash, counts, reasons, gates = {}, {}, Counter(), Counter(), Counter()
bases, group_splits, seen=set(),{},set()
pool=[]
def group_value(unit):
    corpus=unit["corpus"]
    if unit["project_root"]:
        root=Path(unit["project_root"])
        checkout=next(p for p in root.parents if p.name.endswith("@"+unit["repository_commit"]))
        return root.relative_to(checkout).as_posix()
    if corpus in ("Trace_on_chain","Trace_CVEs"):
        return Path(unit["path"]).stem.lower() if corpus=="Trace_on_chain" else Path(unit["path"]).stem.upper()
    return unit["entry_sha256"]
with receipt_stream("bases.jsonl.gz") as accept, receipt_stream("base_exclusions.jsonl.gz") as exclude:
    for line in gzip.decompress(raw_population).splitlines():
        r=json.loads(line); uid=r["unit_id"]; u=original[uid]; corpus=u["corpus"]
        assert uid not in seen and (u["entry_sha256"],corpus)==(r["entry_sha256"],r["corpus"]);seen.add(uid)
        status=r["status"];counts[corpus]+=1
        if corpus=="MANDO":
            match=old[u["path"]]
            assert r["entry_sha256"]==match["inputs"][0]["sha256"] and status==match["status"]
            gates["mando_inputs"]+=1
        if status!="success":
            reason="non_solidity_input" if r["language"]["status"]=="non_solidity" else status
            reasons[reason]+=1;exclude(dict(unit_id=uid,corpus=corpus,reasons=[reason]));continue
        ref=r["selected_result"]; path=Path(ref["result_path"]); m=json.loads(checked(path,ref["result_sha256"]))
        assert m["status"]=="success" and m["unit_id"]==uid and m["inputs"][0]["sha256"]==u["entry_sha256"]
        att=m["attempts"][-1]; sl=att["slither"]
        assert att["version"]==m["selected_version"] and att["solc"]["returncode"]==0
        for src in m["inputs"]:
            key=src["path"]
            if key not in input_hash:
                input_hash[key]=sha(Path(key).read_bytes())
            assert input_hash[key]==src["sha256"],(uid,key)
        graphpath=path.with_name("graph.json");raw=checked(graphpath,sl["graph_sha256"])
        if sl["graph_sha256"] not in raw_groups:
            raw_groups[sl["graph_sha256"]]=len(json.loads(raw)["nodes"])
        nodes=raw_groups[sl["graph_sha256"]]
        assert nodes==sl["counts"]["nodes"]
        if corpus=="MANDO":
            rel="units/"+match["unit_id"]+"/graph.json"
            assert raw==checked(v5/rel,vseal["files"][rel]) and m["selected_version"]==match["selected_version"] and m["settings"]==match["settings"],uid
            gates["mando_graphs_equal_v5"]+=1
        gates["prior_successes"]+=1
        fail=[]
        if r["language"]["status"]!="solidity":fail.append("language_"+r["language"]["status"])
        if not nodes:fail.append("zero_nodes")
        if not sl["d3"] or not sl["d3_a"] or not sl["d3_b"]:fail.append("d3")
        remappings=[]
        if u["project_root"]:
            if not (sl.get("graph_usable") and (sl.get("project_binding") or {}).get("complete")):fail.append("project_binding")
            cov=sl["contract_coverage"]
            if not cov["complete"] or any(n>1 for n in cov["expected"].values()):fail.append("d21")
            remappings=json.loads(path.with_name("project.json").read_bytes())["remappings"]
        if fail:
            for why in fail:reasons[why]+=1
            exclude(dict(unit_id=uid,corpus=corpus,reasons=fail,nodes=nodes,graph_sha256=sl["graph_sha256"]));continue
        group,split=group_and_split(corpus,group_value(u))
        assert group_splits.setdefault(group,split)==split and uid not in bases
        bases.add(uid);version=m["selected_version"]
        row=dict(unit_id=uid,corpus=corpus,group=group,split=split,series=".".join(version.split(".")[:2]),
                 entry=u["path"],entry_sha256=u["entry_sha256"],kind=u["kind"],project_root=u["project_root"],
                 remappings=remappings,result=ref,graph_path=str(graphpath),graph_sha256=sl["graph_sha256"],
                 nodes=nodes,version=version,settings=m["settings"],input_count=len(m["inputs"]))
        accept(row);pool.append(row)
assert len(seen)==len(original)==31307 and gates["prior_successes"]==21223 and gates["mando_graphs_equal_v5"]==843
controls=stratified_sample(pool,200,SEED,"unmodified-controls")
assert len({r["unit_id"] for r in controls})==200
save("control_plan.json",dict(seed=SEED,rank="SHA256(seed:name:unit_id); round-robin strata (corpus,minor)",units=controls))
save("base_summary.json",dict(original=len(original),prior_successes=21223,eligible=len(bases),gates=gates,
     original_by_corpus=counts,eligible_by_corpus=Counter(r["corpus"] for r in pool),exclusion_flags=reasons,
     verified_input_paths=len(input_hash),distinct_checked_success_graphs=len(raw_groups),groups=Counter(group_splits.values()),
     units_by_split=Counter(r["split"] for r in pool),controls=Counter(r["corpus"] for r in controls),
     split="first eight hexadecimal digits of SHA256(cp4-split-v1: + group), modulo 5 == 0 gives dev",
     base_inventory_sha256=sha((OUT/"bases.jsonl.gz").read_bytes()),source_inventory_sha256=sha(source_inventory.read_bytes()),
     source_population_sha256=sha(raw_population),elapsed_seconds=round(time.monotonic()-start,3)))
print("eligible",len(bases),"exclusion flags",reasons,"controls",len(controls),"v5",gates["mando_graphs_equal_v5"],flush=True)
