"""Final read-only identity, archival runtime and immutable-file verification.

The only writes are new verification receipts in the accepted output directory.
Graphs/checkpoints are never deserialized here. Historical tracked artifacts are
byte-hashed without interpreting target/score content. No training is performed.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from scripts.DFG.dfg_v2.benchmark_v2.prepare import checked, read, ref, write
from .facts_schema import validate, VERSION

ROOT = Path(__file__).resolve().parents[2]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf8")).hexdigest()


def byte_sha(path):
    result=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda:stream.read(1024*1024),b""):
            result.update(block)
    return result.hexdigest()


def sealed_manifest(path):
    path=Path(path)
    seal_path=path.with_name("manifest.seal.json")
    if read(seal_path).get("manifest") != ref(path):
        raise ValueError("Manifest seal mismatch: "+str(path))
    return read(path)


def discover_original_text(directory):
    """Discover only original text manifests, then follow their input_text refs."""
    result={}
    for path in sorted(Path(directory).rglob("manifest.json")):
        value=sealed_manifest(path)
        if value.get("version")!="nodesem-text-v1" or value.get("view")!="original":
            raise ValueError("Unexpected original text manifest identity")
        task=value["task_id"]
        if task in result:raise ValueError("Duplicate original text task")
        result[task]=(path,value)
    if not result:raise ValueError("No sealed original text manifests")
    return result


def read_jsonl(path):
    with Path(path).open(encoding="utf8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def validate_row_identity(fact_rows,text_rows,sources):
    if len(fact_rows)!=len(text_rows):raise ValueError("Fact/text population mismatch")
    seen=set()
    identities=[]
    for actual,expected in zip(fact_rows,text_rows):
        identity=actual.get("row_key")
        if type(identity) not in (str,int):raise ValueError("Invalid row identity type")
        typed=(type(identity).__name__,identity)
        if typed in seen:raise ValueError("Duplicate fact row identity")
        seen.add(typed)
        if type(identity) is not type(expected["row_key"]) or identity!=expected["row_key"]:
            raise ValueError("Fact/text row identity or order mismatch")
        fact=actual["facts"]
        validate(fact)
        filename=expected["file"]
        source=sources.get(filename)
        if source is None or source["sha256"]!=expected["source_sha256"]:
            raise ValueError("Text file/source identity mismatch")
        if fact["provenance"]["source_sha256"]!=expected["source_sha256"] or fact["provenance"]["view"]!="original":
            raise ValueError("Fact source/view identity mismatch")
        if hashlib.sha256(expected["text"].encode("utf8")).hexdigest()!=expected["text_sha256"]:
            raise ValueError("Original text row checksum mismatch")
        if expected["node_type"]=="env_source" and fact["node_kind"]!="env":
            raise ValueError("Auxiliary node identity changed")
        if expected["node_type"] in ("end_if","end_loop") and fact["node_kind"]!="end":
            raise ValueError("Placeholder node identity changed")
        identities.append([identity,filename,expected["source_sha256"],expected["node_type"],expected["code_sha256"]])
    return dict(rows=len(identities),identity_order_sha256=digest(identities),
                source_files=len({row[1] for row in identities}),
                file_order_sha256=digest([row[1] for row in identities]))


def verify_frozen_snapshot(snapshot_path,root=ROOT):
    snapshot=read(snapshot_path)
    allowed_exact={"HANDOVER.md","docs/training_changes_2026-10-07.md"}
    changes,checked_count={},0
    for relative,expected in snapshot["tracked_sha256"].items():
        path=Path(root)/relative
        if not path.is_file():raise ValueError("Previously tracked file missing: "+relative)
        actual=byte_sha(path)
        allowed=relative.startswith("scripts/node_sem/") or relative in allowed_exact
        if actual!=expected:
            if not allowed:raise ValueError("Frozen tracked file changed: "+relative)
            changes[relative]={"before":expected,"after":actual}
        if not allowed:checked_count+=1
    return dict(snapshot=ref(snapshot_path),tracked_files=len(snapshot["tracked_sha256"]),
                frozen_files_checked=checked_count,allowed_changes=changes,
                method="streaming byte hashes; no target or score parsing")


def verify_task(path,text_entry,plan,store):
    from .facts import statistics
    manifest=sealed_manifest(path)
    task=manifest["task_id"]
    if manifest.get("version")!=VERSION or manifest.get("view")!="original":
        raise ValueError("Unsupported accepted fact version/view")
    text_path,text_manifest=text_entry
    if text_manifest["task_id"]!=task:raise ValueError("Task identity mismatch")
    if manifest["profiles"]!=text_manifest["profiles"]:raise ValueError("Original graph profile fingerprints differ")
    if manifest["sources"]!=plan["tasks"][task]["record"]["sources"] or manifest["sources"]!=text_manifest["sources"]:
        raise ValueError("Fact/text/plan sources differ")
    for source in manifest["sources"].values():checked(source)
    provenance=manifest["provenance"]
    from .facts_io import PLAN,STORE
    if provenance["plan"]!=ref(PLAN) or provenance["store"]!=ref(STORE):
        raise ValueError("Accepted provenance differs from fixed historical input refs")
    for field in ("plan","store","audit"):
        checked(provenance[field])
    expected_graphs={name:store["tasks"][task]["graphs"][name]["graph"] for name in ("F0","F3")}
    if provenance["graphs"]!=expected_graphs:raise ValueError("Accepted graph refs differ from frozen store")
    for name,profile in (("F0","G0"),("F3","G3R")):
        if expected_graphs[name]["sha256"]!=plan["tasks"][task]["profiles"][profile]["graph"]["sha256"]:
            raise ValueError("Graph plan/store SHA mismatch")
        checked(expected_graphs[name])
    if provenance["audit"]!=store["tasks"][task]["graphs"]["F3"]["audit"]:
        raise ValueError("Accepted evidence reference differs")
    for source in manifest["implementation"].values():checked(source)
    checked(manifest["audit"])
    facts_path=checked(manifest["facts"])
    if facts_path.resolve().parent!=Path(path).resolve().parent:
        raise ValueError("Facts file must belong to accepted task directory")
    fact_rows=read_jsonl(facts_path)
    text_rows=read_jsonl(checked(text_manifest["input_text"]))
    if text_rows!=text_manifest["rows"]:raise ValueError("Text JSONL differs from sealed rows")
    identity=validate_row_identity(fact_rows,text_rows,manifest["sources"])
    if len(fact_rows)!=manifest["rows"]:raise ValueError("Manifest row count mismatch")
    current=statistics({row["row_key"]:row["facts"] for row in fact_rows})
    if current!=manifest["stats"]:raise ValueError("Accepted manifest statistics differ from actual facts")
    return dict(manifest=ref(path),seal=ref(Path(path).with_name("manifest.seal.json")),
                facts=manifest["facts"],text_manifest=ref(text_path),text_rows=text_manifest["input_text"],
                identity=identity,statistics=current,source_refs_checked=len(manifest["sources"]),
                graph_refs=expected_graphs,implementation_refs=manifest["implementation"])


def verify(output,snapshot_path=None,text_directory=None):
    from .facts_io import PLAN,STORE
    from scripts.DFG.dfg_v2.benchmark_v2.execution import load
    from scripts.DFG.dfg_v2.experiment.run import _code_refs
    output=Path(output).resolve()
    if not output.is_dir():raise ValueError("Accepted output directory does not exist")
    for name in ("runtime_closure.json","final_validation.json","verification.seal.json"):
        if (output/name).exists():raise FileExistsError(str(output/name))
    snapshot_path=Path(snapshot_path) if snapshot_path else ROOT/"scripts/node_sem/artifacts/facts_v1/started.json"
    text_directory=Path(text_directory) if text_directory else ROOT/"scripts/node_sem/artifacts/text_v1/original"
    plan=load(PLAN)
    resume=PLAN.with_name("runtime_resume_v2.json")
    amendment=read(resume)
    if amendment["plan"]!=ref(PLAN) or amendment["plan_seal"]!=ref(PLAN.with_name("plan.seal.json")):
        raise ValueError("Effective runtime belongs to another historical plan")
    frozen_runtime=_code_refs()
    if frozen_runtime!=amendment["runtime"]:raise ValueError("Historical effective runtime changed")
    store=read(STORE)
    if ref(STORE)["sha256"]!=read(STORE.with_name("store.seal.json"))["store_sha256"]:
        raise ValueError("Frozen graph store seal differs")
    text_index=discover_original_text(text_directory)
    manifests={}
    for path in sorted((output/"original").rglob("manifest.json")):
        task=read(path)["task_id"]
        if task in manifests:raise ValueError("Duplicate accepted fact task")
        manifests[task]=path
    if set(manifests)!=set(plan["tasks"]):raise ValueError("Accepted fact task population incomplete")
    if not set(manifests).issubset(text_index):raise ValueError("Missing original text task identity")
    tasks={task:verify_task(path,text_index[task],plan,store) for task,path in sorted(manifests.items())}
    stats_path=output/"stats.json"
    stats=read(stats_path)
    if stats.get("view")!="original" or stats.get("tasks")!={task:row["statistics"] for task,row in tasks.items()}:
        raise ValueError("Batch statistics differ from verified task statistics")
    immutable=verify_frozen_snapshot(snapshot_path)
    producers={str(p.relative_to(ROOT)):ref(p) for p in sorted(Path(__file__).parent.glob("facts*.py"))}
    closure=dict(version="nodesem-facts-runtime-closure-v1",view="original",
        legacy_plan=ref(PLAN),effective_runtime=ref(resume),legacy_load_passed=True,
        frozen_runtime=frozen_runtime,producer_runtime=producers,
        accepted_manifests={task:row["manifest"] for task,row in tasks.items()},
        accepted_stats=ref(stats_path),implementation_refs_verified=True)
    validation=dict(passed=True,view="original",tasks=tasks,immutable_snapshot=immutable,
        legacy_runtime_equal=True,training_executed=False,gpu_used=False,
        checkpoint_deserialization=False,target_or_score_parsing=False,
        anonymous_inputs_loaded=False,graphs_deserialized=False)
    write(output/"runtime_closure.json",closure)
    validation["runtime_closure"]=ref(output/"runtime_closure.json")
    write(output/"final_validation.json",validation)
    write(output/"verification.seal.json",dict(runtime_closure=ref(output/"runtime_closure.json"),
        final_validation=ref(output/"final_validation.json")))
    return validation


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out",required=True)
    args=parser.parse_args()
    result=verify(args.out)
    print(json.dumps(dict(passed=result["passed"],tasks={task:row["identity"] for task,row in result["tasks"].items()},
                         frozen_files_checked=result["immutable_snapshot"]["frozen_files_checked"]),indent=2))


if __name__=="__main__":main()
