"""Read-only localization of an EP5 synthetic projection stop."""
import json
from scripts.edge_sem.recon.common import ref,write,ROOT
from scripts.edge_sem.recon.ep5_common import OUT
from scripts.node_sem.facts_io import load_context
from scripts.DFG.projection import ANCHOR,decoded,code_equal
from scripts.DFG.dfg_v2.projection_view import ProjectionView
from scripts.DFG.dfg_v2.benchmark_v2.anon_binding import anonymize

def main():
    task="reentrancy_node";file="buggy_15.sol"
    ctx=load_context(task);source=ctx["source_text"][file]
    result=anonymize(source,ctx["sources"][file].get("metadata"))
    before=ProjectionView(source,file);after=ProjectionView(result["rewritten"],file)
    old_ids={v:k for k,v in before.compat_ids.items()}
    new_ids={v:k for k,v in after.compat_ids.items()}
    g=ctx["graphs"]["F3"]
    rows=[]
    for n,a in g.nodes(data=True):
        if a["source_file"]!=file or a["node_type"] not in ("end_if","end_loop"):continue
        if ANCHOR.search(decoded(a.get("label",""))):continue
        kinds={"if_statement"} if a["node_type"]=="end_if" else {"for_statement","while_statement","do_while_statement","if_statement"}
        ids=[i for i,k in old_ids.items() if k[2] in kinds and code_equal(a["code"],before.compat[k[0]:k[1]].decode())]
        texts={after.compat[new_ids[i][0]:new_ids[i][1]].decode() for i in ids}
        if len(texts)==1:continue
        row=dict(node=n,attrs={k:v for k,v in a.items() if k in ("node_type","code","label","node_info_lines")},exact_match_ids=ids,rewritten_candidates=sorted(texts),
            incoming=[dict(src=s,attrs={k:v for k,v in g.nodes[s].items() if k in ("node_type","code","label","node_info_lines")},edge=d) for s,_,d in g.in_edges(n,data=True)],
            outgoing=[dict(dst=t,attrs={k:v for k,v in g.nodes[t].items() if k in ("node_type","code","label","node_info_lines")},edge=d) for _,t,d in g.out_edges(n,data=True)])
        rows.append(row)
    payload=dict(task_id=task,file=file,source=ctx["sources"][file],status=result["status"],issues=rows,
                 failed_attempt=ref(OUT/"anonymous_gate_attempt2/failure.json"))
    write(OUT/"projection_diagnostic_details.json",payload)
    print(json.dumps(payload,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
