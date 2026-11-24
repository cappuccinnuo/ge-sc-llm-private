"""Verify which graph differences survive the currently approved creation-code normalization."""
import json
from collections import Counter
from pathlib import Path
from wrapper_graphs import OUT, OLD, ROOT, sha, checked, facts
import gzip
from compile_repair.evaluation.benchmark import _comparison_graph, _verified_migration, _nodes, _IR_BYTECODE, _solc_metadata

def main():
    pairs=[json.loads(v) for v in (OUT/'wrapper_graph_pairs.jsonl').read_bytes().splitlines()]
    summary=json.loads((OUT/'wrapper_graph_summary.json').read_bytes())
    assert sha((OUT/'wrapper_graph_pairs.jsonl').read_bytes())==summary['rows_sha256']
    catalog={b["unit_id"]:b for b in map(json.loads,gzip.decompress((OUT.parent/'cp4_v1/bases.jsonl.gz').read_bytes()).splitlines())}
    tallies=Counter();example={};scope=Counter()
    for d in pairs:
        uid=d['unit_id'];folder=ROOT.parent/'compile-repair-local/cp5_1_v1/benchmark/oldest/standard_json_input'/uid/'units'/uid
        a=checked(catalog[uid]['graph_path'],d['truth_sha256'])
        b=checked(folder/'graph.json',d['observed_sha256'])
        assert a["schema"]=="compile-repair-graph-v1" and b["schema"]=="compile-repair-project-graph-v1"
        names={d['filename']:''}
        a1,_=_comparison_graph(a,{},True);b1,_=_comparison_graph(b,names,True)
        pos={n:n for n in _nodes(a1)}
        assert set(pos)==set(_nodes(b1))
        try:
            _verified_migration(a1,dict(b1,schema=a1['schema']),pos,{}, {})
        except ValueError as err:scope[str(err)]+=1
        else:scope['passed']+=1
        nn,dd,ee,cc=facts(b1,'')
        converted=dict(b1,schema=a1["schema"],nodes=list(nn.values()),declarations=dd,cfg_edges=ee,calls=cc)
        try:
            _,proof=_verified_migration(a1,converted,pos,{}, {})
            tallies[proof["status"]]+=1
        except ValueError as err:tallies[str(err)]+=1
        if d['unequal_facts']:
            left,_,_,_=facts(a,'');right,_,_,_=facts(b,d['filename'])
            for k,n in left.items():
                for op1,op2 in zip(n["ir"],right[k]["ir"]):
                    if op1==op2:continue
                    x=_IR_BYTECODE.search(op1);y=_IR_BYTECODE.search(op2)
                    if not (x and y):continue
                    u,v=bytes.fromhex(x["hex"]),bytes.fromhex(y["hex"])
                    size=int.from_bytes(u[-2:],"big");base=len(u)-size-2
                    diffs=[i for i,(j,z) in enumerate(zip(u,v)) if j!=z]
                    example[uid]=dict(length_bytes=[len(u),len(v)],different_bytes=len(diffs),
                         byte_range=[min(diffs),max(diffs)+1],metadata_range=[base,len(u)-2],
                         valid_terminal_metadata=all(_solc_metadata(z[base:-2]) for z in (u,v)),
                         equal_outside_metadata=u[:base]==v[:base] and u[-2:]==v[-2:],
                         source_sha256=d["source_sha256"],raw_literal_sha256=[sha(u),sha(v)],
                         equal_after_existing_normalization=_nodes(a1)[('',k)]["ir"]==_nodes(b1)[('',k)]["ir"])
    result=dict(units=len(pairs),changing_only_schema=dict(scope),explicit_single_file_identity_and_existing_normalization=dict(tallies),
        raw_node_differences=example,prior_comparison=summary['rows_sha256'],historical_graphs_modified=0,production_files_changed=0)
    with (OUT/'wrapper_representation_review.json').open('x',encoding='utf8') as f:
        json.dump(result,f,sort_keys=True,indent=2);f.write('\n')
    print(json.dumps(result),flush=True)

if __name__=='__main__':main()
