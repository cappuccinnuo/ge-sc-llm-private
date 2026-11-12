"""EP6 immutable input inventory and approved prerequisite changes."""
import subprocess
from .common import ROOT, PLAN, ref, read, write, checked
OUT = ROOT/"scripts/edge_sem/artifacts/ep6_v1"
TASKS = ("reentrancy_node", "access_control_node")
EDITS = ("build_f4.py", "attrs.py", "attr_batch.py", "model.py",
         "tests/test_attrs.py", "tests/test_build_f4_calls.py")
DOCS = ("HANDOVER.md", "docs/training_changes_2026-10-07.md", "scripts/edge_sem/PROGRESS.md")


def prepare():
    from scripts.DFG.dfg_v2.benchmark_v2.execution import load
    from scripts.DFG.dfg_v2.experiment.run import _code_refs
    OUT.mkdir(parents=True, exist_ok=False)
    load(PLAN)
    tracked = subprocess.check_output(["git","ls-files","-z"],cwd=str(ROOT),text=True).split("\0")
    frozen = [ref(ROOT/p) for p in tracked if p and (ROOT/p).is_file()
        and p.endswith(".py") and "/artifacts/" not in p
        and (p.startswith(("scripts/DFG/","scripts/node_sem/","sco_models/","process_graphs/","experiments/"))
             or p in ("node_classifier.py","graph_classifier.py","infer_smart_contract.py"))]
    prior = [ref(p) for p in sorted(OUT.parent.rglob("*")) if p.is_file() and OUT not in p.parents]
    snaps=[]
    for name in EDITS:
        old=ROOT/"scripts/edge_sem"/name
        dest=OUT/"baseline"/(name.replace("/","__")+".txt")
        dest.parent.mkdir(parents=True,exist_ok=True)
        with dest.open("xb") as f: f.write(old.read_bytes())
        snaps.append(dict(original=ref(old),snapshot=ref(dest)))
    write(OUT/"before.json",dict(head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=str(ROOT),text=True).strip(),
        prompt=ref(ROOT/"scripts/edge_sem/PROMPTS.md"),plan=ref(PLAN),
        frozen_code=frozen,dfg_code_refs=_code_refs(),prior_artifacts=prior,
        authorized_source_changes=snaps,documents={p:ref(ROOT/p) for p in DOCS},
        edge_sources=[ref(ROOT/p) for p in tracked if p.startswith("scripts/edge_sem/") and p.endswith(".py")
                      and p[len("scripts/edge_sem/"):] not in EDITS]))
    write(OUT/"decisions.json",dict(prompt_revision="r14",approval="call_1c4fc0064fb94266be56b656e6399928",
        user_answer="同意按冻结 sink 补齐并严格核验（推荐）",
        sink_rule="Frozen sem.sink(target_statement, exact sealed symbol); union evidence; exact recorded-sink gate",
        allowed_deltas="Only missing recorded DATA_DEF_USE sink rows; bits 22-29/37-40; 0 to 1",
        compute="CPU only; no training or GPU",final_experiments="Server with sufficient VRAM; local RTX3050 is a temporary limitation"))
    print("EP6 baseline sealed",len(frozen),len(prior),flush=True)


def historical_refs(records):
    baseline=read(OUT/"before.json")
    snapshots={x["original"]["path"]:x["snapshot"] for x in baseline["authorized_source_changes"]}
    for record in records:
        substitute=snapshots.get(record["path"],record)
        if substitute["sha256"]!=record["sha256"]:raise ValueError("Historical source mismatch: "+record["path"])
        checked(substitute)


if __name__=="__main__": prepare()
