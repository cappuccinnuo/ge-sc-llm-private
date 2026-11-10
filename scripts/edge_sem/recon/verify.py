"""Final EP0 read-only verification; write one independent acceptance record."""
import hashlib
import re
import subprocess
from pathlib import Path

from .common import ROOT, OUT, PLAN, read, ref, checked, write


def all_refs(value):
    if isinstance(value, dict):
        if isinstance(value.get("path"), str) and isinstance(value.get("sha256"), str):
            yield value
        for child in value.values():
            for row in all_refs(child):
                yield row
    elif isinstance(value, list):
        for child in value:
            for row in all_refs(child):
                yield row


def verify():
    from scripts.DFG.dfg_v2.benchmark_v2.execution import load
    from scripts.DFG.dfg_v2.experiment.run import _code_refs
    from scripts.node_sem.doc_check import check
    import torch

    before = read(OUT / "before.json")
    inputs = read(OUT / "inputs.json")
    recon = read(ROOT / "scripts/edge_sem/recon.json")
    for row in before["frozen_code"]:
        checked(row)
    assert _code_refs() == before["dfg_code_refs"]
    load(PLAN)

    refs = {}
    for row in all_refs(inputs):
        identity = (row["path"], row["sha256"])
        if identity not in refs:
            refs[identity] = ref(checked(row))
    for row in all_refs(recon["artifact_refs"]):
        checked(row)

    prefixes = []
    for name, original in before["documents"].items():
        raw = (ROOT / name).read_bytes()
        assert hashlib.sha256(raw[:original["bytes"]]).hexdigest() == original["sha256"]
        prefixes.append(dict(original=original,
                             current=ref(ROOT / name), unchanged_prefix=True))

    tasks = {}
    file_count = 0
    for task in inputs["tasks"]:
        evidence = read(OUT / (task + ".json"))
        assert evidence["graph_unchanged"]
        assert not evidence["graphs_written"] and not evidence["new_production_edges"]
        assert not evidence["cf_back_enable_threshold50"]
        for file_row in evidence["files"]:
            assert file_row["anonymous_projection"]["code_view_same_ast_to_hcg"]
            file_count += 1
        tasks[task] = dict(evidence=ref(OUT / (task + ".json")),
                          files=len(evidence["files"]),
                          original_graph_unchanged=True)
    assert file_count == 384

    probes = {}
    for name in ("A", "B", "C"):
        p = OUT / ("cpu_" + name + ".json")
        d = read(p)
        assert d["optimizer_steps"] == 0
        assert d["device"] == "cpu" and not d["cuda_initialized"]
        assert not d["trained_checkpoint_loaded"] and d["input_graph_unchanged"]
        probes[name] = ref(p)
    a, b, c = [read(OUT / ("cpu_" + name + ".json")) for name in ("A", "B", "C")]
    assert a["state_equal"] and a["forward_bitwise_equal"] and a["max_abs"] == 0
    assert b["copied_relation_rows_equal"] and b["forward_backward_finite"]
    assert b["deep_registration_under_G3R"]["rejected"]
    assert b["deep_registration_under_new_profile"]["rejected"]
    assert c["forward_finite"] and c["scale_only"] and not c["semantic_edges_built"]

    tests = {}
    for name, expected in (("regression_edge_sem2", 11), ("regression_node_sem", 1353),
                           ("regression_dfg_v2", 2653)):
        p = OUT / "execution" / (name + ".json")
        receipt = read(p)
        assert receipt["exit_code"] == 0
        log = checked(receipt["log"]).read_text(encoding="utf8")
        matches = re.findall(r"(?m)^(\d+) passed", log)
        assert matches == [str(expected)], (name, matches)
        tests[name] = dict(receipt=ref(p), passed=expected, log=receipt["log"])

    doc_receipt = OUT / "execution/doc_check2.json"
    assert read(doc_receipt)["exit_code"] == 0
    checked(read(doc_receipt)["log"])
    docs = []
    for name in ("scripts/edge_sem/RECON.md", "scripts/edge_sem/PROGRESS.md",
                 "HANDOVER.md", "docs/training_changes_2026-10-07.md"):
        old = before["documents"].get(name)
        docs.append(check(ROOT / name, old["bytes"] if old else None, expect_cjk=True))

    prompt = ROOT / "scripts/edge_sem/PROMPTS.md"
    git_prompt = subprocess.check_output(["git", "show", "HEAD:scripts/edge_sem/PROMPTS.md"], cwd=str(ROOT))
    current = prompt.read_bytes()
    assert current.replace(b"\r\n", b"\n") == git_prompt.replace(b"\r\n", b"\n")
    changed = subprocess.check_output(["git", "diff", "--name-only", "HEAD"], cwd=str(ROOT), text=True).splitlines()
    allowed_docs = set(before["documents"])
    assert all(p in allowed_docs or p.startswith("scripts/edge_sem/") for p in changed), changed
    subprocess.run(["git", "-c", "core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol",
                    "diff", "--check"], cwd=str(ROOT), check=True)
    assert not torch.cuda.is_initialized()

    implementations = sorted((ROOT / "scripts/edge_sem/recon").glob("*.py"))
    implementations += sorted((ROOT / "scripts/edge_sem/tests").glob("*.py"))
    implementations += [ROOT / "scripts/edge_sem/__init__.py"]
    result = dict(
        passed=True, scope="EP0 reconnaissance acceptance, not EP1 or training",
        input_manifest=ref(OUT / "inputs.json"), frozen_source_files=len(before["frozen_code"]),
        frozen_source_sha_unchanged=True, dfg_code_refs_count=len(before["dfg_code_refs"]),
        dfg_code_refs_unchanged=True, archived_8h_load_passed=True,
        checked_input_files=len(refs), input_refs=list(refs.values()),
        document_prefixes=prefixes, documents=docs, doc_check_receipt=ref(doc_receipt),
        prompt_line_endings=dict(current=ref(prompt), head_blob_sha256=hashlib.sha256(git_prompt).hexdigest(),
                                text_equal_after_crlf_normalization=True,
                                current_crlf=current.count(b"\r\n"), head_crlf=git_prompt.count(b"\r\n"),
                                action="Preserve existing working-tree bytes; do not stage newline-only PROMPTS change."),
        tasks=tasks, anonymous_projection_task_file_refs=file_count,
        cpu_probes=probes, tests=tests, test_total=sum(t["passed"] for t in tests.values()),
        implementations=[ref(p) for p in implementations],
        report=ref(ROOT / "scripts/edge_sem/RECON.md"), summary=ref(ROOT / "scripts/edge_sem/recon.json"),
        allowed_tracked_changes=changed, cuda_initialized=False, optimizer_steps=0)
    write(OUT / "verification.json", result)
    print("EP0 verified: {} tests; {} frozen source files; {} input refs".format(
        result["test_total"], result["frozen_source_files"], result["checked_input_files"]), flush=True)


if __name__ == "__main__":
    verify()
