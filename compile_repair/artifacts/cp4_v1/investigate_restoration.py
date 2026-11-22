"""Locate the strict restoration discrepancy using only the two already observed graphs."""
from collections import Counter
from pathlib import Path
import re
from batch import OUT, checked, json, load, receipt_rows, save, sha
from audit_samples import json_lines, key

stop=load("inverse_acceptance.json")
assert not stop["passed"]
failed=stop["first_failure"]
bases={r["unit_id"]:r for r in receipt_rows("bases.jsonl.gz")}
uid=failed["unit_id"]
base=bases[uid]
graphs={r["unit_id"]:r for r in json_lines(OUT/"inverse_graphs.jsonl")}
old=base["result"];new=graphs[uid]
observations=[]
for ref in (old,new):
    path=Path(ref["result_path"])
    record=json.loads(checked(path,ref["result_sha256"]))
    attempt=record["attempts"][-1]
    sl=attempt["slither"];target=Path(sl["command"]["target"])
    checked(target,attempt["solc"]["source_sha256"])
    graph=json.loads(checked(path.with_name("graph.json"),sl["graph_sha256"]))
    observations.append((record,attempt,graph,target))
r1,a1,g1,t1=observations[0];r2,a2,g2,t2=observations[1]
assert t1!=t2 and t1.read_bytes()==t2.read_bytes()
assert a1["version"]==a2["version"] and a1["settings"]==a2["settings"]
assert a1["slither"]["compiler_sha256"]==a2["slither"]["compiler_sha256"]
assert all(g1[k]==g2[k] for k in g1 if k!="nodes")
assert len(g1["nodes"])==len(g2["nodes"])
pairs=[(a,b) for a,b in zip(g1["nodes"],g2["nodes"]) if a!=b]
assert len(pairs)==1
a,b=pairs[0]
assert all(a[k]==b[k] for k in a if k!="ir")
different=[i for i,(x,y) in enumerate(zip(a["ir"],b["ir"])) if x!=y]
assert len(a["ir"])==len(b["ir"]) and len(different)==1
index=different[0];parts=[]
for node in [a,b]:
    ir=node["ir"][index]
    m=re.search(r"(?<![0-9A-Fa-f])([0-9a-f]{200,})(?![0-9A-Fa-f])",ir)
    raw=bytes.fromhex(m.group(1));length=int.from_bytes(raw[-2:],"big")
    meta=raw[-length-2:]
    # CBOR map(2), "ipfs", bytes(34), multihash sha2-256/32, then "solc" and the three version bytes.
    prefix=bytes.fromhex("a2646970667358221220")
    assert meta.startswith(prefix) and meta[len(prefix)+32:]==bytes.fromhex("64736f6c634300060c0033")
    parts.append((ir[:m.start()]+ir[m.end():],raw[:-length-2],meta[len(prefix):len(prefix)+32],len(raw),len(meta)))
assert parts[0][:2]==parts[1][:2] and parts[0][2]!=parts[1][2]
scores=list(json_lines(OUT/"inverse_scores.jsonl"))
passing={key(r) for r in scores if r["score"]["exact"]}
failure_rows=[r for r in scores if not r["score"]["exact"]]
assert len(failure_rows)==1
all_included={key(r) for r in json_lines(OUT/"sample_receipts.jsonl") if r["outcome"]=="included"}
remaining=all_included-passing
remaining_ids={u for _,u in remaining}
categories=Counter(bases[u]["kind"] for u in remaining_ids)
save("restoration_identity_request.json",dict(
    date="2026-11-22",basis="PROMPTS r2.16 §4.1 and §4.6a.5: stopped on first failed exact inverse",
    unit_id=uid,operator=failed["operator"],split=base["split"],score=failed["score"],
    previous_result=old,first_inverse_result=new,original_source_target=str(t1),relocated_source_target=str(t2),
    both_working_inputs_sha256=sha(t1.read_bytes()),selected_version=base["version"],settings=base["settings"],
    compiler_sha256=a1["slither"]["compiler_sha256"],node_key5=a["key5"],changed_ir_index=index,
    differing_nodes=1,differing_ir_operations=1,bytecode_bytes=parts[0][3],metadata_trailer_bytes=parts[0][4],
    executable_prefix_bytes=len(parts[0][1]),executable_prefix_sha256=sha(parts[0][1]),
    metadata_field="ipfs multihash digest only",historical_digest=parts[0][2].hex(),relocated_digest=parts[1][2].hex(),
    no_other_graph_field_difference=True,causality="Only the embedded metadata hash differs. Source-unit target path changed; same-path replay has not been run.",
    first_batch=dict(scored=len(scores),passed=len(passing),failed=len(failure_rows),pending=len(all_included)-len(scores),
        graphs=len(graphs),graphs_byte_equal=sum(r["graph_sha256"]==r["truth_graph_sha256"] for r in graphs.values())),
    remaining=dict(samples=len(remaining),distinct_units=len(remaining_ids),unit_kinds=categories),
    proposed="First replay this failed unit once in production with the historical canonical tool target. Compare its bytes against the inverse working bytes before every compile; record all new results in a fresh external store. Only if all raw graph bytes and the strict score match, process remaining score pairs once; reuse the already passed 4315 scores. Use the same read-only canonical target for pending single-file compiles, the existing project method for projects. Verify original artifacts before and after. Stop on any discrepancy; no metadata removal, no change to scoring, compiler options or production code.",
    cost_ceiling_usd=0,new_network_downloads=0,training=False,llm_calls=0))
print(len(passing),len(remaining),len(remaining_ids),categories,parts[0][3:])