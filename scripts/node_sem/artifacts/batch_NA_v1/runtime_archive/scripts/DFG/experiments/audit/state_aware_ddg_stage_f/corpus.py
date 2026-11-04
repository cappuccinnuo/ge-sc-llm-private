"""F0 syntax demand versus confirmed Stage E semantics; no label-based rules."""
import argparse,json
from collections import Counter
from pathlib import Path
from common import *
from scripts.DFG.frontend import SourceView,parse,walk,text,FUNCTION_TYPES
from scripts.DFG.models import Unsupported
from scripts.DFG.state.analyzer import analyze_view
from scripts.DFG.state.projection import result_record
from scripts.DFG.state.audit import side_relations
def syntax_inventory(source,file):
 tree=parse(source);nodes=list(walk(tree.root_node));decls={}
 for n in nodes:
  if n.type=="state_variable_declaration":
   name=n.child_by_field_name("name");typ=n.child_by_field_name("type")
   if name and typ:decls.setdefault(text(source,name),set()).add(text(source,typ))
 functions=[]
 for fn in nodes:
  if fn.type not in FUNCTION_TYPES or not fn.child_by_field_name("body"):continue
  ns=list(walk(fn));names={text(source,n) for n in ns if n.type=="identifier"}&set(decls)
  writes=[];reads=[]
  for n in ns:
   if n.type=="identifier" and text(source,n) in names:
    parent=n.parent
    # Bare assignment LHS only; indexed/member targets remain conservative syntax candidates.
    left=parent.child_by_field_name("left") if parent else None
    is_write=parent is not None and parent.type=="assignment_expression" and left is not None and left.start_byte==n.start_byte
    (writes if is_write else reads).append(n.start_byte)
   if n.type in ("assignment_expression","augmented_assignment_expression","update_expression"):
    target=n.child_by_field_name("left") or n.child_by_field_name("argument")
    if target and any(c.type=="identifier" and text(source,c) in names for c in walk(target)):writes.append(n.start_byte)
  kinds={k for name in names for k in decls[name]}
  functions.append({"function":file+":"+str(fn.start_byte),"start":fn.start_byte,"end":fn.end_byte,"line":fn.start_point[0]+1,
    "syntactic_state_names":sorted(names),"scalar_spelling_candidate":bool(kinds and any("mapping" not in k and "[" not in k for k in kinds)),
    "mapping_spelling_candidate":any("mapping" in k for k in kinds),"array_spelling_candidate":any("[" in k for k in kinds),
    "write_read_cooccurrence":bool(writes and reads),"textual_write_before_read_candidate":any(w<u for w in writes for u in reads),
    "possible_external_member_call":any(n.type=="call_expression" and n.child_by_field_name("function") is not None and n.child_by_field_name("function").type=="member_expression" for n in ns),
    "potential_limits":sorted({n.type for n in ns if n.type in ("modifier_invocation","assembly_statement","try_statement","new_expression","array_access")}),
    "candidate_policy":"name/AST syntax only; may include shadowed or unreachable uses, not binding or dataflow proof"})
 return {"pragmas":[text(source,n) for n in tree.root_node.named_children if n.type=="pragma_directive"],
 "imports":sum(n.type=="import_directive" for n in nodes),"inheritance_specifiers":sum(n.type=="inheritance_specifier" for n in nodes),
 "modifier_invocations":sum(n.type=="modifier_invocation" for n in nodes),"functions":functions}
def main(output):
 out=Path(output);out.mkdir(exist_ok=False,parents=True)
 cohorts,inputs=catalogue();inventory=[];funcs=[];patterns=[];rows=[];global_paths=set();hashes=set();summaries=[]
 for cohort,c in cohorts.items():
  records={};cache={}
  for idx,file in enumerate(c["files"]["contract"]):
   spec=c["manifest"]["sources"][file];source=Path(spec["path"]).read_text();global_paths.add(spec["path"]);hashes.add(spec["sha256"])
   row={"cohort":cohort,"file":file,"source_sha256":spec["sha256"],"source_path":spec["path"],
        "in_contract":True,"in_node":file in c["files"]["node"],"compiler_evidence":"pragma only; no chosen compiler / no compile verification"}
   try:synt=syntax_inventory(source,file);row.update({k:v for k,v in synt.items() if k!="functions"});row["parser_status"]="parsed"
   except Unsupported as e:row.update(parser_status="fallback",reason=str(e));synt={"functions":[]}
   try:view=SourceView(source,file);rs=analyze_view(view);rec=[dict(result_record(r),side_relations=side_relations(r)) for r in rs];row["analysis_frontend"]="ready"
   except Unsupported as e:rec=[];row.update(analysis_frontend="fallback",reason=str(e))
   byid={r["function"]:r for r in rec};records[file]=rec
   for fn in synt["functions"]:
    v=byid.get(fn["function"]);status=v["status"] if v else "file_fallback";reason=(v["diagnostics"][0]["reason"] if v and v["diagnostics"] else row.get("reason",""))
    events=v["events"] if v else [];facts=v["facts"] if v else []
    f=dict(fn,cohort=cohort,file=file,in_node=row["in_node"],status=status,first_fallback_reason=reason,
      exact_facts=sum(x["certainty"]=="EXACT" for x in facts),may_facts=sum(x["certainty"]=="MAY" for x in facts),
      bound_locations=len(v["locations"]) if v else 0,reads=sum(e["kind"]=="READ" for e in events),writes=sum(e["kind"]=="WRITE" for e in events),
      rmw_reads=sum(e["kind"]=="READ" and e["detail"]=="READ_MODIFY_WRITE" for e in events),
      havoc=sum(e["kind"]=="HAVOC" for e in events),external_calls=sum(e["kind"]=="HAVOC" and e["detail"].startswith("EXTERNAL_CALL:") for e in events),
      unknown_origins=len(v["unknown_reads"]) if v else 0,state_access_order=sum(e["relation"]=="STATE_ACCESS_ORDER" for e in v["side_relations"]) if v else 0)
    funcs.append(f)
    if fn["write_read_cooccurrence"]:patterns.append(dict(fn,cohort=cohort,file=file))
   row["functions"]=len(synt["functions"]);inventory.append(row)
   if idx%20==0:print(cohort,idx+1,"/",len(c["files"]["contract"]),flush=True)
  dump(out/(cohort+"_stage_e_results.json"),records)
  for task,names in c["files"].items():
   fs=[f for f in funcs if f["cohort"]==cohort and f["file"] in names]
   s={"cohort":cohort,"task":task,"files":len(names),"functions":len(fs),"supported":sum(f["status"]=="supported_subset" for f in fs),
      "syntax_write_read_candidates":sum(f["write_read_cooccurrence"] for f in fs),"syntax_textual_write_before_read":sum(f["textual_write_before_read_candidate"] for f in fs)}
   for k in ("reads","writes","rmw_reads","havoc","external_calls","unknown_origins","exact_facts","may_facts","bound_locations","state_access_order"):s[k]=sum(f[k] for f in fs)
   summaries.append(s)
  rc=Counter(f["first_fallback_reason"] for f in funcs if f["cohort"]==cohort and f["status"]!="supported_subset")
  rows.extend({"cohort":cohort,"reason":k,"functions":v} for k,v in rc.items())
 check_inputs(inputs);dump(out/"INPUT_MANIFEST.json",{"inputs":inputs})
 csv_out(out/"F0_CORPUS_INVENTORY.csv",inventory);csv_out(out/"F0_FUNCTION_SUPPORT.csv",funcs);csv_out(out/"F0_FALLBACK_REASONS.csv",rows)
 dump(out/"F0_STATE_PATTERN_CANDIDATES.json",patterns)
 dump(out/"F0_SUMMARY.json",{"tasks":summaries,"unique_source_paths":len(global_paths),"unique_source_sha256":len(hashes),"cohort_file_entries":len(inventory),"syntax_is_not_semantic_proof":True})
 print(json.dumps(summaries),flush=True)
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("--output",required=True);main(p.parse_args().output)
