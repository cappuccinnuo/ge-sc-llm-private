"""Score verified original and relocated creation code, then change only a child comment."""
from batch import *
from compile_repair.core.model import Patch
from compile_repair.core.provenance import apply_patches
from compile_repair.core.store import ArtifactStore
from compile_repair.evaluation.benchmark import score_graphs
from compile_repair.toolchain.project import compile_project, resolve_project
from compile_repair.toolchain.slither import run_slither
from compile_repair.toolchain.solc import compile_file, load_trusted_compilers

compilers,_,_ = load_trusted_compilers()
compiler = compilers["0.6.12"]
store = ArtifactStore(LOCAL/"creation_code_validation")
def observe(path,project,tag):
    compilation = compile_project(project,compiler) if project else compile_file(path,compiler)
    store.write_json(tag+"/solc.json",compilation)
    if compilation.returncode != 0 or compilation.timed_out:
        raise ValueError("Creation-code source failed to compile: "+tag)
    analyzed = run_slither(compilation,profile="production",project=project)
    graph = analyzed.pop("graph",None)
    store.write_json(tag+"/slither.json",analyzed)
    if not analyzed["d3"] or not analyzed.get("graph_usable",True) or graph is None:
        raise ValueError("D3 or project binding failed: "+tag)
    target=store.write_json(tag+"/graph.json",graph)
    return graph,dict(graph_path=str(target),graph_sha256=sha(target.read_bytes()),compiler=compiler.version,
                      compiler_sha256=compiler.sha256,solc_returncode=compilation.returncode,d3=analyzed["d3"])

def compare(truth,actual,source,repaired,maps):
    return [score_graphs(truth,actual,source,source,repaired,{},maps,0,True,normalize_creation_code=mode) for mode in (False,True)]

ref=json.loads(frozen(OLD/"restoration_identity_request.json"))
a=ref["previous_result"];z=ref["first_inverse_result"]
original=json.loads(checked(a["result_path"],a["result_sha256"]))
past=json.loads(checked(z["result_path"],z["result_sha256"]))
assert all(r["status"]=="success" and r["selected_version"]=="0.6.12" and r["attempts"][-1]["slither"]["d3"] for r in (original,past))
truth=json.loads(checked(Path(a["result_path"]).with_name("graph.json"),z["truth_graph_sha256"]))
other=json.loads(checked(Path(z["result_path"]).with_name("graph.json"),z["graph_sha256"]))
raw=checked(ref["original_source_target"],ref["both_working_inputs_sha256"])
assert checked(ref["relocated_source_target"],ref["both_working_inputs_sha256"])==raw
archived=compare(truth,other,{"":raw},{"":raw},{})
def validate_pinned(result):
    return result[0]["kept"]["units"]==299 and result[0]["kept"]["equal"]==298 and result[1]["kept"]["equal"]==299 and result[1]["exact"] and result[1]["metadata_normalized"]
if not validate_pinned(archived):
    saved("creation_archive_stop.json",archived);raise ValueError("Archived 298/299 comparison differs")
new_path=store.write_bytes("relocated/input.sol",raw)
actual,fresh=observe(new_path,None,"pinned")
current=compare(truth,actual,{"":raw},{"":raw},{})
if not validate_pinned(current):
    saved("creation_fresh_stop.json",current);raise ValueError("Fresh 298/299 comparison differs")
saved("creation_archived_and_fresh.json",dict(archived=archived,fresh=current,new_observation=fresh,
    archived_results=[a,z],source_sha256=sha(raw),reference_sha256=sha((OLD/"restoration_identity_request.json").read_bytes())))
fx=ROOT/"compile_repair/tests/fixtures/cp4_1/creation"
sources={name:(fx/name).read_bytes() for name in ("Factory.sol","Child.sol")}
for name,raw in sources.items():store.write_bytes("manual/"+name,raw)
manual_root=store.path/"manual";entry=manual_root/"Factory.sol"
before,before_obs=observe(entry,resolve_project(manual_root,entry),"before")
child=sources["Child.sol"];offset=child.index(b"note A")+5
changed,provenance=apply_patches(child,[Patch(offset,offset+1,b"A",b"B","change child comment")])
(manual_root/"Child.sol").write_bytes(changed)
after,after_obs=observe(entry,resolve_project(manual_root,entry),"after")
repaired=dict(sources,**{"Child.sol":changed})
scores=compare(before,after,sources,repaired,{"Child.sol":provenance})
passed=(scores[0]["kept"]["equal"]<scores[0]["kept"]["units"] and scores[1]["exact"] and scores[1]["metadata_normalized"])
saved("creation_manual.json",dict(before=before_obs,after=after_obs,scores=scores,changed_file="Child.sol",
    changed_offset=offset,original_sha256={n:sha(x) for n,x in sources.items()},repaired_sha256={n:sha(x) for n,x in repaired.items()},passed=passed))
print("pinned",[(r["kept"]["equal"],r["kept"]["units"]) for r in current],"manual",[(r["kept"]["equal"],r["kept"]["units"]) for r in scores],flush=True)
if not passed:raise SystemExit(2)
