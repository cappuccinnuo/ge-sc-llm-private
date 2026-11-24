"""Derive the continuation runners from the preserved first-run sources and bind their input identities."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
BATCH=HERE.parent
ROOT=BATCH.parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def derived(name, changes, source=None):
    original=BATCH/(source or name)
    text=original.read_text(encoding="utf8")
    for old,new in changes:
        if text.count(old)!=1:
            raise ValueError((name,old[:70],text.count(old)))
        text=text.replace(old,new)
    out=HERE/name
    with out.open("x",encoding="utf8") as fp:fp.write(text)
    return dict(original_sha256=sha(original),continuation_sha256=sha(out))


auth=json.loads((HERE/"authorization.json").read_bytes())
assert sha(BATCH/"ir_argument_differences.jsonl")==auth["units_sha256"]
assert sha(BATCH/"frozen_suites/source_freeze.json")==auth["production_modules_sha256"]
main=derived("measure.py", [
    ('ART = HERE.parent','BATCH = HERE.parent\nART = BATCH.parent'),
    (' / "compile-repair-local" / HERE.name',' / "compile-repair-local" / BATCH.name / HERE.name'),
    ('from population import entry','sys.path.append(str(BATCH))\nfrom population import entry'),
    ('from compile_repair.toolchain.project import resolve_project, ProjectIndex',
     'from compile_repair.toolchain.project import compile_project, project_command, resolve_project, ProjectIndex'),
    ('    name = "ir_" + cohort','''    from ir_manifest_check import checked_project
    author=load(HERE/"authorization.json")
    table=BATCH/"ir_argument_differences.jsonl"
    assert sha256(table)==author["units_sha256"]
    permitted={r["unit_id"]:r for r in map(json.loads,table.read_bytes().splitlines())}
    assert len(permitted)==author["max_solc_calls"]==711
    name = "ir_" + cohort'''),
    ('''                info = old["project"]
                members = tuple(Path(f["path"]) for f in info["files"])
                project = resolve_project(info["root"], info["entry"], info["remappings"],
                    ProjectIndex(info["root"], members), info.get("additional_entries", ()))
                assert json.loads(json.dumps(project.manifest())) == info''',
     '''                project,_ = checked_project(old["project"])
                argv=project_command(project,build.compiler,build.settings)
                if cohort=="cp3" and uid in permitted:
                    ref=permitted[uid]
                    assert ref["historical_result_sha256"]==digest and build.command==ref["old_solc"] and argv==ref["new_solc"]
                    local=LOCAL/"ir_solc"/uid
                    local.mkdir(parents=True,exist_ok=False)
                    save(local/"claim.json",dict(unit_id=uid,version=build.compiler.version,
                         old_receipt_sha256=digest,command=argv,authorization_sha256=sha256(HERE/"authorization.json")))
                    build=compile_project(project,build.compiler,settings=tuple(build.settings))
                    save(local/"compilation.json",asdict(build))
                    if build.timed_out or build.returncode!=0 or build.command!=argv:
                        raise ValueError("Fresh historical-root compilation failed: "+uid)
                else:
                    assert build.command==argv'''),
    ('            assert actual["d3"] and actual.get("graph_usable", True)','''            evidence={k:v for k,v in actual.items() if k not in ("graph","nodes","project","contract_coverage","project_binding")}
            if not actual["d3"] or not actual.get("graph_usable",True):
                save(HERE/(name+"_"+uid+"_native_stop.json"),dict(unit_id=uid,observed=evidence,original=digest))
                raise ValueError("Production D3 or graph availability changed: "+uid)'''),
    ('            row = dict(unit_id=uid, corpus=corpus, operator=op, result_path=path, result_sha256=digest,','''            def graph_hash(graph):
                return hashlib.sha256((json.dumps(graph,sort_keys=True,indent=2,ensure_ascii=False)+"\\n").encode("utf8")).hexdigest()
            row = dict(unit_id=uid, corpus=corpus, operator=op, result_path=path, result_sha256=digest,
                       historical_solc=attempt["solc"]["command"],fresh_solc=(cohort=="cp3" and uid in permitted),
                       original_native_graph_sha256=graph_hash(native),measured_native_graph_sha256=graph_hash(actual["graph"]),''')
])
files={"measure.py":main}
for name in ("benchmarks.py","moved_v2.py"):
    files[name]=derived(name,[])
files["stage.py"]=derived("stage.py",[("ROOT = OUT.parents[2]","ROOT = OUT.parents[3]"),
    ('OUT/"frozen_suites/source_freeze.json"','OUT.parent/"frozen_suites/source_freeze.json"')])
files["schedule.py"]=derived("schedule.py",[
    ('    ("diagnostic_details","diagnosis_details"),\n',''),
    ('    ("mando_v5","mando"),\n',''),
    ('OUT/"frozen_suites/source_freeze.json"','OUT.parent/"frozen_suites/source_freeze.json"')])
with (HERE/"runner_hashes.json").open("x",encoding="utf8") as fp:
    json.dump(files,fp,sort_keys=True,indent=2);fp.write("\n")
