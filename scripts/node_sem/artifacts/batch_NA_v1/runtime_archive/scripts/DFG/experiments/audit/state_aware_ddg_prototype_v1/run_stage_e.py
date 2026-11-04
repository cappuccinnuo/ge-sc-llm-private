"""Stage E finite-sample audit. No training and no category-specific analysis rules."""
import argparse,csv,hashlib,json,os,pickle
from pathlib import Path
from collections import Counter
from dataclasses import asdict
import networkx as nx

from scripts.DFG.frontend import SourceView,span,solidity_version_interval
from scripts.DFG.projection import Projector
from scripts.DFG.graph_audit import fingerprint
from scripts.DFG.pipeline import augment
from scripts.DFG.state.analyzer import analyze_view
from scripts.DFG.state.projection import augment_state,result_record,assert_state_augmented
from scripts.DFG.state.audit import side_relations,information_increment
from scripts.DFG.state import VERSION
from process_graphs.tree_sitter_codeviews.generator import generate_cfg_from_source

ROOT=Path(__file__).resolve().parents[5]
PREVIOUS=ROOT/"scripts/DFG/experiments/audit/ddg_v11_correctness"
ORIGINAL=Path("/home/zhao/SmartContract/ge-sc-llm")

def sha(path):
    h=hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda:f.read(4*1024*1024),b""):h.update(b)
    return h.hexdigest()

def dump(path,data):
    with Path(path).open("x",encoding="utf8") as f:json.dump(data,f,ensure_ascii=False,indent=2)

def write_csv(path,rows):
    keys=list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open("x",newline="",encoding="utf8") as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
        for row in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict,tuple)) else v for k,v in row.items()})

def extra_oracles():
    fixtures=[
        ("O15","Arithmetic/local propagation","uint s;","s=1;uint a=s;uint b=a+1;return b;","",1),
        ("O16","Loop state and fixpoint","uint s;","s=3;while(s>0){s--;}return s;","",6),
        ("O17","External return scalar flow","uint s;",'(bool ok,)=to.call("");require(ok);return 0;',"address payable to",0),
        ("O18","Environment condition","uint s;","s=1;if(block.timestamp>0){s=2;}return s;","",2),
        ("O19","Independent storage roots","uint s;uint t;","s=1;t=2;require(s>0);return t;","",2),
        ("O20","Branch kills old definition","uint s;","s=1;if(c){s=2;}else{s=3;}return s;","bool c",2)]
    return [{"id":ident,"title":title,"origin":"synthetic_specification",
             "source":"pragma solidity 0.5.17;contract T{"+decl+"function f("+params+") public returns(uint){"+body+"}}",
             "expected_exact_fact_count":count,
             "expected_and_forbidden_facts":"Independent hand-written fixture assertions; no relation from environment as a storage declaration."}
            for ident,title,decl,body,params,count in fixtures]

def validate_expectation(ident,r,view,oracle):
    """Acceptance of specified subset behavior, not independent semantic certification."""
    fallback={"O1","O3","O5","O6","O8","O9","O11"}
    if ident in fallback:
        assert r.status=="function_fallback",(ident,r.status)
        assert not r.facts and r.ir is None
        return
    assert r.status=="supported_subset",(ident,r.diagnostics)
    events=[e for b,es in r.ir.events.items() if b in r.reachable for e in es]
    roots=[e.location.root.name for e in events if e.location is not None]
    if ident=="O2":
        assert roots==["balances_re_ent10"]*3 and not r.facts
        assert sum(e.kind=="WRITE" for e in events)==1
    elif ident=="O4":
        assert roots==["owner"] and len(r.unknown_reads)==1 and not r.facts
    elif ident=="O7":
        assert not roots and not r.facts
    elif ident=="O10":
        assert len(r.facts)==1 and r.facts[0].certainty=="EXACT" and len(r.unknown_reads)==1
    elif ident=="O12":
        assert len(r.facts)==2 and all(f.certainty=="EXACT" for f in r.facts)
        assert {view.raw[f.definition.anchor.start:f.definition.anchor.end].decode() for f in r.facts}=={"s=1;","s=2;"}
    elif ident=="O13":
        assert r.facts and all(f.certainty=="MAY" for f in r.facts) and r.unknown_reads
    elif ident=="O14":
        assert not r.facts and any(u["origin"].startswith("HAVOC:") for u in r.unknown_reads)
    else:
        assert sum(f.certainty=="EXACT" for f in r.facts)==oracle["expected_exact_fact_count"],(ident,len(r.facts))

def main(output):
    out=Path(output)
    if out.exists():raise FileExistsError("Use a new output directory, preserve prior attempts")
    out.mkdir(parents=True)
    old_prov=json.loads((PREVIOUS/"D1_PROVENANCE.json").read_text())
    candidates=json.loads((PREVIOUS/"context_design/D3_ORACLE_CANDIDATES.json").read_text())["oracles"]
    inputs={str(PREVIOUS/"D1_PROVENANCE.json"):sha(PREVIOUS/"D1_PROVENANCE.json"),
            str(PREVIOUS/"context_design/D3_ORACLE_CANDIDATES.json"):sha(PREVIOUS/"context_design/D3_ORACLE_CANDIDATES.json")}
    graphs={}
    for task,spec in old_prov["graphs"].items():
        assert sha(spec["path"])==spec["sha256"],"E2 artifact changed"
        inputs[spec["path"]]=spec["sha256"]
        with open(spec["path"],"rb") as f:graphs[task]=pickle.load(f)
    specs=[];oracle_results=[];source_by_cohort={}
    for o in candidates+extra_oracles():
        ident=o["id"];real=isinstance(o["source"],dict)
        original=o["source"] if real else None
        if real:
            path=Path(original["source_path"]);raw=path.read_bytes()
            assert hashlib.sha256(raw).hexdigest()==original["source_sha256"]
            inputs[str(path)]=original["source_sha256"]
            source=raw.decode("utf8");file=path.name
            cohort=path.parent.parent.name+"_author"
            source_by_cohort.setdefault(cohort,{})[file]=source
            view=SourceView(source,file)
            oldfn=original["function"]
            fn=view.raw_nodes[(oldfn["start_byte"],oldfn["end_byte"],oldfn["ast_type"])]
            assert raw[fn.start_byte:fn.end_byte].decode()==oldfn["text"]
            contract=original["contract"]
            assert (contract["start_byte"],contract["end_byte"],contract["ast_type"]) in view.raw_nodes
            for decl in original["state_declarations"]:
                assert raw[decl["start_byte"]:decl["end_byte"]].decode()==decl["text"]
            g=graphs[cohort+"_contract"];proj=Projector(g,view)
            anchors=[]
            for n in original["function_hcg_nodes"]:
                key=(n["start_byte"],n["end_byte"],n["ast_type"])
                assert raw[key[0]:key[1]].decode()==n["text"]
                a=span(file,view.raw_nodes[key]);ck=view.compat_key(a)
                assert proj.by_ast.get(view.compat_ids[ck])==n["node_id"]
                anchors.append({"span":asdict(a),"node_id":n["node_id"]})
            selected=[oldfn["identity"]];existing_projection=anchors
        else:
            source=o["source"];file=ident+".sol";view=SourceView(source,file)
            g=generate_cfg_from_source(source,file)
            g,_=augment(g,{file:source})
            selected=None
            existing_projection=[{"node_id":n,"node_type":d["node_type"],"code":d["code"]} for n,d in g.nodes(data=True)]
        results=analyze_view(view,selected)
        assert len(results)==1,(ident,len(results))
        r=results[0]
        validate_expectation(ident,r,view,o)
        enhanced,audit=augment_state(g,{file:source},selected_functions={file:[r.function]})
        assert_state_augmented(g,enhanced)
        if not real:
            with (out/(ident+"_E3a_fixture.gpickle")).open("xb") as f:pickle.dump(enhanced,f,protocol=4)
        specs.append({"oracle_id":ident,"title":o["title"],"origin":o["origin"],
                      "solidity_version":{"pragma_interval":solidity_version_interval(view.source,view.tree.root_node),"chosen_compiler":None},
                      "source_sha256":view.sha256,"source_path":str(path) if real else None,
                      "source":source if not real else None,"contract_identity":original["contract"] if real else "AST in source",
                      "function_identity":r.function,"AST_anchors":existing_projection,
                      "state_locations":list(r.ir.locations) if r.ir else [],
                      "expected_reads":o.get("expected_accesses",o.get("expected_and_forbidden_facts")),
                      "expected_writes":o.get("expected_accesses",o.get("expected_and_forbidden_facts")),
                      "expected_def_use":o["expected_and_forbidden_facts"],
                      "expected_unknown":o.get("uncertainty","ENTRY_UNKNOWN/HAVOC or explicit unsupported outcome as specified"),
                      "forbidden_dependencies":["later write to earlier non-loop read","unproved MUST alias","environment as storage","control guard as Def-Use"],
                      "alias_assumptions":o.get("uncertainty","declaration/key policy; parameter reassignment UNKNOWN"),
                      "expected_projection":o.get("projection","exact AST projection, no invented nodes"),
                      "support_status":r.status,"reviewer_status":"Codex_static_candidate;independent_review_pending",
                      "compiler_validation":"not_executed_no_new_compiler_authorization",
                      "automated_subset_checks":"passed_not_independent_certification",
                      "evidence":{"input_manifest":"INPUT_MANIFEST.json","semantic_result":ident}})
        oracle_results.append({"oracle_id":ident,"analysis":result_record(r),"side_relations":side_relations(r),
                               "projection":audit["files"].get(file,{}),"edges":audit["invariants"]["state_edges"]})
    dump(out/"ORACLE_EXPECTATIONS.json",specs)
    dump(out/"STATE_REACHING_DEF_RESULTS.json",{"scope":"oracles","results":oracle_results})
    summaries=[];access_rows=[];projection_rows=[];corpus_results={}
    for cohort,sources in source_by_cohort.items():
        selected={}
        for file,source in sources.items():
            view=SourceView(source,file)
            selected[file]=["{}:{}".format(file,n.start_byte) for n in view.functions]
        base=graphs[cohort+"_contract"]
        enhanced,audit=augment_state(base,sources,selected_functions=selected)
        all_results=[]
        for file,source in sources.items():
            view=SourceView(source,file);rs=analyze_view(view,selected[file])
            # An independent replay must reproduce the projection analyzer's facts.
            assert [result_record(r) for r in rs]==audit["files"][file]["functions"]
            for r in rs:
                rec=result_record(r);rec["side_relations"]=side_relations(r);all_results.append(rec)
                if not rec["events"]:
                    access_rows.append({"cohort":cohort,"file":file,"function":r.function,"status":r.status,"kind":"NO_COMMITTED_EVENTS","reason":r.diagnostics})
                for e in rec["events"]:
                    access_rows.append({"cohort":cohort,"file":file,"function":r.function,"status":r.status,
                        "event_id":e["id"],"kind":e["kind"],"block":e["block"],"anchor":e["anchor"],
                        "location":e["location"]["id"] if e["location"] else None,"detail":e["detail"]})
            rec=audit["files"][file]
            projection_rows.append({"cohort":cohort,"file":file,"functions":len(rs),
                "supported_functions":sum(r.status=="supported_subset" for r in rs),
                "fallback_functions":sum(r.status!="supported_subset" for r in rs),
                "exact_facts":sum(f.certainty=="EXACT" for r in rs for f in r.facts),
                "may_facts":sum(f.certainty=="MAY" for r in rs for f in r.facts),
                "unknown_reads":sum(len(r.unknown_reads) for r in rs),"projected":rec["facts_projected"],
                "missing_anchors":len(rec["projection_missing"]),"self_facts":rec["self_facts"],
                "edges_added":rec["edges_added"],"file_fallback":rec.get("fallback")})
        corpus_results[cohort]=all_results
        for task in ["contract","node"]:
            taskbase=graphs[cohort+"_"+task]
            candidate=enhanced if task=="contract" else enhanced.subgraph(list(taskbase.nodes())).copy()
            assert_state_augmented(taskbase,candidate)
            off,_=augment_state(taskbase,{},enabled=False)
            assert fingerprint(off)==fingerprint(taskbase)
            path=out/(cohort+"_E3a_selected_"+task+".gpickle")
            with path.open("xb") as f:pickle.dump(candidate,f,protocol=4)
            with path.open("rb") as f:assert fingerprint(pickle.load(f))==fingerprint(candidate)
            info=information_increment(taskbase,candidate)
            summaries.append(dict(info,task=cohort+"_"+task,selected_files=list(sources),
                                  partial_dataset_enhancement=True,path=str(path),sha256=sha(path),
                                  E2_fingerprint=fingerprint(taskbase),E3a_fingerprint=fingerprint(candidate)))
        dump(out/(cohort+"_projection.json"),audit)
    dump(out/"CORPUS_STATE_RESULTS.json",corpus_results)
    write_csv(out/"STATE_ACCESS_AUDIT.csv",access_rows)
    write_csv(out/"STATE_PROJECTION_AUDIT.csv",projection_rows)
    write_csv(out/"E2_E3_INFORMATION_INCREMENT.csv",summaries)
    dump(out/"GRAPH_MANIFEST.json",summaries)
    for path,digest in inputs.items():assert sha(path)==digest,"Input changed during run"
    dump(out/"INPUT_MANIFEST.json",{"inputs":inputs,"all_unchanged":True,"version":VERSION,
        "code":{str(p.relative_to(ROOT)):sha(p) for p in (ROOT/"scripts/DFG/state").glob("*.py")},
        "scope":"two cohorts; all functions in seven preselected difficult files; no seven-category run"})
    summary={"status":"automated_subset_checks_passed","oracles":len(specs),
             "independently_approved_oracles":0,"compiled_oracles":0,
             "oracle_supported":sum(o["support_status"]=="supported_subset" for o in specs),
             "oracle_fallback":sum(o["support_status"]!="supported_subset" for o in specs),
             "projection_files":projection_rows,"graphs":summaries,"new_training":False,
             "formal_training_ready":False,"reason":"partial candidate graphs; independent oracles pending; existing formal loader not migrated"}
    dump(out/"SUMMARY.json",summary)
    print(json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--output",required=True)
    main(p.parse_args().output)
