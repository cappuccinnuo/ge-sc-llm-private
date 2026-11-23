"""Read-only diagnosis of the first distinct variable family in the stopped, sealed graph pair."""
from collections import Counter
import json
from pathlib import Path
import re
import sys

DEST = Path(__file__).resolve().parent
sys.path.insert(0,str(DEST.parent))
from batch import HERE, OLD, checked, rows, sha
from replay import restore_sample
from compile_repair.evaluation.benchmark import (_at_original, _comparison_graph, _correspondence,
    _literal_bytes, _nodes, _verified_migration, base_contents)
from compile_repair.toolchain.solc import lexical_tokens

tuple_token = re.compile(r"(?<![\w$])TUPLE_[0-9]+(?![\w$])")


def inspect_source(data):
    names, pending, prefix = set(), bytearray(), None
    for _, _, kind, spelling in lexical_tokens(data):
        if kind == "word":
            names.update(tuple_token.findall(spelling.decode("ascii")))
        if kind == "word" and spelling in (b"unicode",b"hex"):
            prefix=spelling
            continue
        if kind == "string":
            raw=_literal_bytes(spelling,prefix)
            names.update(tuple_token.findall(raw.decode("latin1")))
            pending.extend(raw)
        else:
            names.update(tuple_token.findall(pending.decode("latin1")))
            pending.clear()
        prefix=None
    names.update(tuple_token.findall(pending.decode("latin1")))
    return names


def diagnostic_view(graph, token):
    counts = Counter()
    def project(text):
        return tuple_token.sub(lambda m:"DIAGNOSTIC_TUPLE_RESULT" if m.group()==token else m.group(),text)
    nodes=[]
    for row in graph["nodes"]:
        counts.update(n for op in row["ir"] for n in tuple_token.findall(op))
        nodes.append(dict(row,ir=[project(op) for op in row["ir"]]))
    calls=[]
    for row in graph["calls"]:
        callee=row["callee"]
        if "text" in callee:
            callee=dict(callee,text=project(callee["text"]))
        calls.append(dict(row,callee=callee))
    return dict(graph,nodes=nodes,calls=calls),counts


def main():
    stop_path=DEST/"results/stop.json"
    stop=json.loads(stop_path.read_bytes())
    assert stop["unit_id"]=="cp3_03927"
    uid=stop["unit_id"]
    obs=next(r for r in rows(HERE/(stop["cohort"]+"_observations.jsonl.gz"))
             if r["operator"]==stop["operator"] and r["unit_id"]==uid)
    base=next(r for r in rows(OLD/"bases.jsonl.gz") if r["unit_id"]==uid)
    source=base_contents(base)
    _,damaged,moved,first,second=restore_sample(base,source,obs,migration=True)
    reverse={b:a for a,b in stop["file_renames"].items()}
    repaired={reverse.get(n,n):v for n,v in moved.items()}
    maps,_,_=_correspondence(source,damaged,repaired,first,second)
    original,_=_comparison_graph(json.loads(checked(base["graph_path"],base["graph_sha256"])),{},True)
    ref=stop["migration_graph"]
    actual,_=_comparison_graph(json.loads(checked(ref["graph_path"],ref["graph_sha256"])),reverse,True)
    positions={}
    for (name,key),node in _nodes(original).items():
        offset=key[3]
        if name in maps and offset<len(source[name]):
            segment=_at_original(maps[name][2],offset)
            offset=segment.new_start+offset-segment.original_start
        elif name in maps:
            offset=len(repaired[name])
        positions[name,key]=(name,key[:3]+(offset,)+key[4:])
    a, before=diagnostic_view(original,"TUPLE_0")
    b, after=diagnostic_view(actual,"TUPLE_1")
    guard=set().union(*(inspect_source(v) for v in set(source.values())|set(repaired.values())))
    assert before["TUPLE_0"]==after["TUPLE_1"]==3 and "TUPLE_1" not in before and "TUPLE_0" not in after
    assert not (guard & {"TUPLE_0","TUPLE_1"})
    _, verified=_verified_migration(a,b,positions,source,repaired)
    tool=Path(sys.executable).resolve().parents[1]/"lib/python3.10/site-packages/slither/slithir/variables/tuple.py"
    program=tool.read_bytes()
    assert b"counter_slithir_tuple += 1" in program and b'TUPLE_{self.index}' in program
    body=dict(unit_id=uid,scope="Read-only comparison; original strict migration remains rejected.",
        stop_sha256=sha(stop_path.read_bytes()),truth_sha256=base["graph_sha256"],migration_sha256=ref["graph_sha256"],
        tuple_names_before=dict(before),tuple_names_after=dict(after),changed={"TUPLE_0":"TUPLE_1"},
        affected_ir_operations=3,uses="one tuple result definition and two UNPACK uses with unchanged indexes 0 and 1",
        verified_node_count=verified["nodes"],verified_cfg_edges=verified["cfg_edges"],verified_calls=verified["calls"],
        changed_tmp_ref_names=len(verified["renamed"]),source_collision=False,raw=stop["migration"]["raw_migration_score"],
        tool_source=str(tool),tool_source_sha256=sha(program),selected_solc=base["version"],
        proposal="Extend the verified families from TMP/REF to Slither's generated TUPLE counter only. Require the same full bijection, same-family witnessed definitions, source identifier/literal collision exclusion, matched types/arity, ordered UNPACK uses and indexes, CFG and calls. Keep both scores. Reuse physical receipts and complete only missing restorations.")
    with (DEST/"tuple_review.json").open("x",encoding="utf8") as fp:
        json.dump(body,fp,indent=2,ensure_ascii=False);fp.write("\n")
    print(uid,verified["nodes"],"nodes",verified["cfg_edges"],"edges",verified["calls"],"calls")
if __name__=="__main__":main()
