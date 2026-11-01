"""NS-P0 read-only orchestration; emits JSON to stdout, never starts a fit."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]

def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def run(repo_root=None):
    root = Path(repo_root or ROOT).resolve()
    if Path.cwd().resolve() != root:
        raise ValueError("Run from the repository root to preserve frozen relative references")
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "":
        raise ValueError("NS-P0 requires CUDA_VISIBLE_DEVICES=''")
    from scripts.DFG.dfg_v2.experiment.run import _code_refs
    from scripts.DFG.dfg_v2.benchmark_v2.execution import load
    from scripts.node_sem.recon import inputs, text_ast, cfg, carrier_probe
    plan_path = root / inputs.BASE / "plan.json"
    before = _code_refs()
    plan = load(plan_path)
    amendment_path = root / inputs.BASE / "runtime_resume_v2.json"
    effective = json.loads(amendment_path.read_text(encoding="utf8"))
    assert before == effective["runtime"], "Effective approved 8H runtime differs"
    started = time.monotonic()
    sections = {}
    for name, module in (("inputs", inputs), ("carrier", carrier_probe),
                         ("text_ast", text_ast), ("cfg", cfg)):
        print("NS-P0 section: " + name, file=sys.stderr, flush=True)
        sections[name] = module.run(root)
    assert _code_refs() == before, "Frozen production runtime changed during recon"
    load(plan_path)
    import torch
    assert not torch.cuda.is_initialized(), "NS-P0 initialized CUDA"
    scripts = {str(p.relative_to(root)): _sha(p)
               for p in sorted((root / "scripts/node_sem/recon").glob("*.py"))}
    return dict(version="nodesem-nsp0-recon-v1", scope="CPU reconnaissance only",
        timestamp_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        branch=subprocess.check_output(["git","branch","--show-current"], universal_newlines=True).strip(),
        input_head=subprocess.check_output(["git","rev-parse","HEAD"], universal_newlines=True).strip(),
        prompt=dict(path="scripts/node_sem/PROMPTS.md", sha256=_sha(root/"scripts/node_sem/PROMPTS.md")),
        sections=sections, scripts=scripts,
        frozen_runtime=dict(before=before, after_identical=True, execution_load_passed=True,
            original_plan_literal_match=before == plan["runtime"],
            effective_amendment=dict(path=str(amendment_path), sha256=_sha(amendment_path)),
            effective_amendment_match=True,
            interpretation="Original plan is preserved. Existing approved cache/resume amendments define the effective runtime; no new waiver or seal rewrite."),
        approved_scope_adjustment=dict(
            question="NS-P0 permits reconnaissance scripts only but Shared Context asks for nonexistent NodeSem tests.",
            answer="User approved reconnaissance assertions plus both existing regression suites; dedicated NodeSem tests begin NS-P1.",
            implementation="No scripts/node_sem/tests or production feature algorithms created."),
        boundaries=dict(gpu_used=False, training_fits=0, optimizer_steps=0,
                        frozen_files_written=False, downloaded_or_installed=False,
                        new_initials_or_checkpoints=False),
        command="CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 TREE_SITTER_LIB_DIR=/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64 python -B -m scripts.node_sem.recon.run",
        seconds=time.monotonic()-started)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=str(ROOT))
    args = parser.parse_args()
    print(json.dumps(run(args.repo), ensure_ascii=False, indent=2, allow_nan=False))
