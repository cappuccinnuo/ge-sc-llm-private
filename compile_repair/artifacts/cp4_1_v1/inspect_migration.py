"""Inspect the stopped graph without invoking either compiler or rescoring the benchmark."""
from collections import Counter
import re
from batch import *
from replay import restore_sample
from compile_repair.evaluation.benchmark import (_at_original, _comparison_graph, _correspondence,
    _edges_and_calls, _nodes, base_contents)

token = re.compile(r"(?<![\w$])(?:TMP|REF)_[0-9]+(?![\w$])")
def compare(x,y,forward,back):
    xs,ys=token.findall(x),token.findall(y)
    if token.split(x)!=token.split(y) or len(xs)!=len(ys):return False
    for a,b in zip(xs,ys):
        if a.split("_")[0]!=b.split("_")[0]:return False
        if forward.setdefault(a,b)!=b or back.setdefault(b,a)!=a:return False
    return True

def inspect(stage):
    failure=load(stage+"_restoration_stop.json")
    uid=failure["unit_id"]
    base=next(r for r in rows(OLD/"bases.jsonl.gz") if r["unit_id"]==uid)
    obs=next(r for r in rows(OUT/(stage+"_observations.jsonl.gz")) if r["unit_id"]==uid and r["operator"]==failure["operator"])
    source=base_contents(base)
    manifests, damaged, relocated, first,second=restore_sample(base,source,obs,migration=True)
    inverse={v:k for k,v in failure["file_renames"].items()}
    repaired={inverse.get(k,k):v for k,v in relocated.items()}
    maps,_,_=_correspondence(source,damaged,repaired,first,second)
    truth,_=_comparison_graph(json.loads(checked(base["graph_path"],base["graph_sha256"])),{},True)
    ref=failure["migration_graph"];actual,_=_comparison_graph(json.loads(checked(ref["graph_path"],ref["graph_sha256"])),inverse,True)
    truth_nodes,actual_nodes=_nodes(truth),_nodes(actual)
    assert len(truth_nodes)==len(actual_nodes)
    renames={};back={};keys={};literal_diffs=0;unexplained=[];example=None
    for identity,n in truth_nodes.items():
        name,key=identity;offset=key[3]
        if name in maps and offset<len(source[name]):
            section=_at_original(maps[name][2],offset)
            assert section,identity
            offset=section.new_start+offset-section.original_start
        elif name in maps:offset=len(repaired[name])
        mapped=(name,key[:3]+(offset,)+key[4:])
        keys[identity]=mapped;v=actual_nodes[mapped]
        if n["ir"]!=v["ir"]:
            literal_diffs+=1
            if example is None:example=[n["ir"][:1],v["ir"][:1]]
        if n["node_type"]!=v["node_type"] or len(n["ir"])!=len(v["ir"]) or not all(compare(a,b,renames,back) for a,b in zip(n["ir"],v["ir"])):
            unexplained.append([name,list(key)])
    oldedges,oldcalls=_edges_and_calls(truth,keys)
    newedges,newcalls=_edges_and_calls(actual,{id:id for id in actual_nodes})
    textual_calls=0
    for call in actual["calls"]:
        target=call["callee"]
        if "text" in target:
            old=target["text"]
            target["text"]=token.sub(lambda m:back.get(m[0],m[0]),old)
            textual_calls+=int(old!=target["text"])
    _,renamed_calls=_edges_and_calls(actual,{id:id for id in actual_nodes})
    common=Path("/home/zhao/miniconda3/envs/compile-repair-production/lib/python3.10/site-packages/slither/slithir/variables")
    docs={f:sha((common/f).read_bytes()) for f in ("temporary.py","reference.py")}
    return dict(stage=stage,unit_id=uid,compiler=base["version"],source_graph=base["graph_sha256"],migration_graph=ref["graph_sha256"],
        raw_score=failure["migration"],total_nodes=len(truth_nodes),raw_ir_mismatch_nodes=literal_diffs,ir_example=example,
        generated_tokens=len(renames),changed_tokens=sum(a!=b for a,b in renames.items()),bijection=len(renames)==len(back),
        other_node_differences=unexplained,all_edges_equal=oldedges==newedges,all_call_count=sum(oldcalls.values()),
        all_calls_equal_before=oldcalls==newcalls,all_calls_equal_after_diagnostic_substitution=oldcalls==renamed_calls,
        calls_with_renumbered_text=textual_calls,sources_with_verbatim_counter_identifiers=sum(bool(token.search(v.decode("utf8","replace"))) for v in source.values()),
        tool_classes_sha256=docs,acceptance_status="stopped; comparison of saved graphs only")
if __name__=="__main__":
    stage=sys.argv[1]
    result=inspect(stage)
    saved(stage+"_migration_difference.json",result)
    print(json.dumps({k:v for k,v in result.items() if k not in ("raw_score","ir_example","other_node_differences")},ensure_ascii=False))
