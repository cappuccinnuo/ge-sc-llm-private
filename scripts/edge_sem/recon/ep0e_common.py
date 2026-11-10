"""EP0e append-only baseline; EP0 through EP0d evidence stays immutable."""
import subprocess
from .common import ROOT, PLAN, ref, read, write
from .ep0b_common import contexts, file_views, anchor
OUT = ROOT / "scripts/edge_sem/artifacts/ep0e_v1"
EP0D = ROOT / "scripts/edge_sem/artifacts/ep0d_v1"
EP0B = ROOT / "scripts/edge_sem/artifacts/ep0b_v1"
TASKS = ("reentrancy_node", "access_control_node")
AUTHORIZED_EDITS = ("scripts/edge_sem/call_resolve.py", "scripts/edge_sem/tests/test_call_resolve.py")


def prepare():
    from scripts.DFG.dfg_v2.benchmark_v2.execution import load
    from scripts.DFG.dfg_v2.experiment.run import _code_refs
    OUT.mkdir(parents=True, exist_ok=False)
    load(PLAN)
    paths = subprocess.check_output(["git", "ls-files", "-z"], cwd=str(ROOT), text=True).split("\0")
    frozen = [ref(ROOT/p) for p in paths if p and (ROOT/p).is_file()
              and (p.startswith(("scripts/DFG/", "scripts/node_sem/", "sco_models/",
                                  "process_graphs/", "experiments/"))
                   or p in ("node_classifier.py", "graph_classifier.py", "infer_smart_contract.py"))
              and "/artifacts/" not in p and p.endswith(".py")]
    prior = [ref(p) for folder in ("ep0_v1", "ep0b_v1", "ep0c_v1", "ep0d_v1")
             for p in sorted((OUT.parent/folder).rglob("*")) if p.is_file()]
    edge_sources = [ref(ROOT/p) for p in paths if p.startswith("scripts/edge_sem/")
                    and (p.endswith(".py") or p == "scripts/edge_sem/recon.json")
                    and p not in AUTHORIZED_EDITS]
    documents = {p:ref(ROOT/p) for p in ("HANDOVER.md", "docs/training_changes_2026-10-07.md",
                                      "scripts/edge_sem/PROGRESS.md", "scripts/edge_sem/RECON.md")}
    archive = OUT/"baseline"
    archive.mkdir()
    edits=[]
    for name in AUTHORIZED_EDITS:
        old=ROOT/name
        copy=archive/(old.stem+"_ep0d.py.txt")
        with copy.open("xb") as dest:
            dest.write(old.read_bytes())
        edits.append(dict(original=ref(old),snapshot=ref(copy)))
    write(OUT/"before.json",dict(
        head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=str(ROOT),text=True).strip(),
        prompt=ref(ROOT/"scripts/edge_sem/PROMPTS.md"),plan=ref(PLAN),
        seal=ref(PLAN.with_name("plan.seal.json")),frozen_code=frozen,
        dfg_code_refs=_code_refs(),prior_artifacts=prior,prior_edge_sources=edge_sources,
        authorized_source_changes=edits,documents=documents,
        historical_verification=ref(EP0D/"verification.json")))
    print("EP0e baseline recorded; EP0d artifacts preserved",flush=True)


if __name__=="__main__":
    prepare()
