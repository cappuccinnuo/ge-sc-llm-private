"""8G full-population gate; neither a flag nor a partial view authorizes work."""
import pytest
from scripts.DFG.dfg_v2.benchmark_v2.prepare import write, ref
from scripts.DFG.dfg_v2.benchmark_v2.spelling_names import VERSION
from scripts.DFG.dfg_v2.benchmark_v2.prepare_spelling import (
    load_names, verify_semantics, require_semantic_pass, blocked_decision)


def prepared(tmp_path):
    naming = tmp_path/"names"; naming.mkdir()
    sem = tmp_path/"semantic"; sem.mkdir()
    src = tmp_path/"a.sol"; src.write_text("contract C {}")
    detail = tmp_path/"a.json"; write(detail, dict(status="renamed"))
    sources = {"toy/a.sol": dict(source=ref(src), result=ref(detail))}
    write(naming/"sources.json", sources)
    write(naming/"task_files.json", {"toy_node":["toy/a.sol"]})
    old = tmp_path/"old.json"
    write(old, dict(fit_count=170, tasks={}, bound_artifacts={"timing":ref(src)}))
    manifest = dict(version=VERSION, source_identities=1, task_file_references=1,
                    fallback_files=0, old_plan=ref(old),
                    artifacts={k:ref(naming/(k+".json")) for k in ("sources","task_files")})
    write(naming/"manifest.json",manifest)
    write(naming/"manifest.seal.json",dict(manifest=ref(naming/"manifest.json")))
    row = dict(task="toy_node",file="a.sol",identity="toy/a.sol",source=ref(src),
               status="semantic_failed",passed=False,whole_file_fallback=True,
               committed_feature_edits=0)
    write(sem/"rows.json",[row])
    write(sem/"synthetic.json",dict(nodes=[],expected=36,resolved=0,passed=False))
    summary=dict(naming=ref(naming/"manifest.json"),passed=False,
                 counts={"semantic_failed":1},
                 artifacts={"toy_node":ref(sem/"rows.json")},
                 synthetic_resolution=ref(sem/"synthetic.json"))
    write(sem/"summary.json",summary)
    write(sem/"summary.seal.json",dict(summary=ref(sem/"summary.json")))
    return naming,sem,summary,row


def save_summary(sem, summary):
    # Intentional re-sealing in negative tests tests semantic checks, not just SHA.
    import json
    (sem/"summary.json").write_text(json.dumps(summary))
    (sem/"summary.seal.json").write_text(json.dumps(dict(summary=ref(sem/"summary.json"))))


def test_actual_file_failure_blocks_all_downstream(tmp_path):
    naming,sem,summary,row=prepared(tmp_path)
    with pytest.raises(ValueError,match="blocks probes"):
        require_semantic_pass(naming,sem)
    result=blocked_decision(naming,sem,tmp_path/"decision")
    assert result["failed_source_identities"]==1 and not result["execution_authorized"]
    assert not result["new_features_created"] and not result["new_executable_plan_created"]


def test_forged_pass_does_not_override_failed_file(tmp_path):
    naming,sem,summary,row=prepared(tmp_path)
    summary["passed"]=True;save_summary(sem,summary)
    with pytest.raises(ValueError,match="completeness"):
        verify_semantics(naming,sem)


@pytest.mark.parametrize("path",["a.sol","a.json","names/sources.json","semantic/rows.json"])
def test_bound_source_result_or_summary_mutation_rejected(tmp_path,path):
    naming,sem,summary,row=prepared(tmp_path)
    with (tmp_path/path).open("a") as f:f.write("changed")
    with pytest.raises((ValueError,KeyError)):
        verify_semantics(naming,sem)


def test_missing_identity_is_rejected_even_with_new_summary_hash(tmp_path):
    naming,sem,summary,row=prepared(tmp_path)
    summary["artifacts"]={}
    save_summary(sem,summary)
    with pytest.raises(ValueError,match="Missing/duplicate"):
        verify_semantics(naming,sem)


def test_duplicate_identity_not_used_to_fill_population(tmp_path):
    naming,sem,summary,row=prepared(tmp_path)
    write(sem/"duplicate.json",[row,row])
    summary["artifacts"]={"toy_node":ref(sem/"duplicate.json")}
    save_summary(sem,summary)
    with pytest.raises(ValueError,match="Missing/duplicate"):
        verify_semantics(naming,sem)


def test_failed_file_cannot_retain_partial_feature_edits(tmp_path):
    naming,sem,summary,row=prepared(tmp_path)
    row["committed_feature_edits"]=1
    write(sem/"partial.json",[row])
    summary["artifacts"]={"toy_node":ref(sem/"partial.json")}
    save_summary(sem,summary)
    with pytest.raises(ValueError,match="whole-file fallback"):
        verify_semantics(naming,sem)
