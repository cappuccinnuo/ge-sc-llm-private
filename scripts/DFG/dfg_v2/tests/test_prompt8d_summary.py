"""Prompt8D read-only summary accounting and binding regression tests."""
import copy
from pathlib import Path
import pytest
from scripts.DFG.dfg_v2.diagnostics8d import inference_summary as m
from scripts.DFG.dfg_v2.diagnostics8d import inference_batch as batch

def row(file="buggy_2.sol",node=1,target=1,original=1,renamed=0):
    return dict(file=file,original_graph_node_id=node,source_sha256="s"+file,target=target,
                original_best=original,renamed_best=renamed,
                original_probability=.9 if original else .1,
                renamed_probability=.8 if renamed else .2)

def view_index():
    return {("buggy_2.sol",1):dict(orig=1,C1=1,solidifi=True,fold=0),
            ("real.sol",2):dict(orig=0,C1=0,solidifi=False,fold=1)}

def report(rows,mode="B_full"):
    files={r["file"] for r in rows}
    changed=[dict(file=r["file"],original_graph_node_id=r["original_graph_node_id"],
                  source_sha256=r["source_sha256"],replacements=1,feature_changed=True,
                  position_proof=dict(edited_token_positions=2)) for r in rows
             if r["file"].startswith("buggy")]
    return dict(intervention=mode,predictions=rows,changed_nodes=changed,
                mappings={file:{"x":"alpha"} if file.startswith("buggy") else {} for file in files})

def test_class_flip_rates_respect_targets_and_no_zero_division():
    views=view_index();rows=[row(),row("real.sol",2,0,0,1)]
    result=m.flip_rates(rows,views,"orig")
    assert result["positive_flip_rate_percent"]==100
    assert result["negative_flip_rate_percent"]==100
    assert m.flip_rates([],views,"orig")["negative_flip_rate_percent"] is None

def test_cohort_tables_keep_pooled_fold_mean_and_exposure_distinct():
    views=view_index()
    reports={0:report([row()]),1:report([row("real.sol",2,0,0,0)])}
    result=m.cohort_tables("task","G0","B_full",reports,views)
    assert len(result["cohort_fold_metrics"])==24
    assert not any(r["cohort"]=="nonSolidiFI" for r in result["cohort_fold_means"])
    solid=next(r for r in result["cohort_fold_means"]
               if r["cohort"]=="SolidiFI" and r["view"]=="orig" and r["prediction_state"]=="renamed")
    assert solid["empty_folds"]==[1]
    assert solid["buggy_f1"]["n_folds"]==1
    file=next(r for r in result["file_exposure_changes"] if r["file"]=="buggy_2.sol")
    assert file["changed_code_nodes"]==1 and file["lexical_occurrences_in_scored_node_code"]==1
    assert file["edited_token_positions_in_scored_node_code"]==2

def test_paired_contrast_aligns_identity_not_order_and_sign_is_right_minus_left():
    views=view_index()
    left=[row(),row("real.sol",2,0,0,0)]
    right=[row("real.sol",2,0,0,0),row(renamed=1)]
    result=m.paired_change(left,right,views,"orig")
    assert result["metric_delta_pp"]["buggy_f1"]==100
    assert result["corrected_errors"]==1 and result["introduced_errors"]==0
    assert result["positive_flips"]==1

@pytest.mark.parametrize("failure",["missing","duplicate","source","target","frozen_original"])
def test_paired_contrast_rejects_identity_or_original_drift(failure):
    left=[row()];right=[row(renamed=1)]
    if failure=="missing":right=[]
    elif failure=="duplicate":right.append(dict(right[0]))
    elif failure=="source":right[0]["source_sha256"]="different"
    elif failure=="target":right[0]["target"]=0
    else:right[0]["original_probability"]=.4
    with pytest.raises(ValueError):m.paired_change(left,right,view_index(),"orig")

def test_matrix_refuses_missing_duplicate_and_wrong_intervention():
    job=dict(task_id="t",fold=0,seed=1,profile="G0")
    planned=[dict(mode=mode,job=job) for mode in m.MODES]
    reports=[(Path(mode),dict(intervention=mode,job=job)) for mode in m.MODES]
    assert len(m.matrix_index(planned,reports))==3
    with pytest.raises(ValueError,match="Incomplete"):m.matrix_index(planned,reports[:-1])
    with pytest.raises(ValueError,match="duplicate"):m.matrix_index(planned,reports+[reports[0]])
    wrong=copy.deepcopy(reports);wrong[0][1]["intervention"]="C_full"
    with pytest.raises(ValueError):m.matrix_index(planned,wrong)

def prepared_report():
    r=row()
    changed=dict(file=r["file"],original_graph_node_id=1,
                 original_vector_sha256="a",renamed_vector_sha256="b",
                 before_token_length=7,after_token_length=7,
                 position_proof={"unedited_token_ids_equal":True})
    prepared=dict(rows=[changed],tokenizer={"scheme":"frozen"},
                  mappings={"buggy_2.sol":{"x":"alpha"}},
                  source_refs={"buggy_2.sol":{"path":"bound","sha256":"s"}})
    worker=dict(predictions=[r],prepared={"manifest":"M"},tokenizer=prepared["tokenizer"],
                mappings=prepared["mappings"],source_refs=prepared["source_refs"],
                changed_nodes=[dict(changed,feature_changed=True)])
    return worker,prepared,{"manifest":"M"}

def test_prepared_proof_exact_match():
    assert m.validate_prepared_report(*prepared_report())==1

@pytest.mark.parametrize("failure",["missing","extra","proof","mapping","source","tokenizer","feature_flag"])
def test_prepared_report_rejects_unbound_rows_or_false_proof(failure):
    worker,prepared,binding=prepared_report()
    worker=copy.deepcopy(worker)
    if failure=="missing":worker["changed_nodes"]=[]
    elif failure=="extra":worker["changed_nodes"].append(dict(worker["changed_nodes"][0],original_graph_node_id=2))
    elif failure=="proof":worker["changed_nodes"][0]["before_token_length"]=8
    elif failure=="mapping":worker["mappings"]["buggy_2.sol"]["x"]="beta"
    elif failure=="source":worker["source_refs"]["buggy_2.sol"]["sha256"]="wrong"
    elif failure=="tokenizer":worker["tokenizer"]["scheme"]="other"
    else:worker["changed_nodes"][0]["feature_changed"]=False
    with pytest.raises(ValueError):m.validate_prepared_report(worker,prepared,binding)

def fake_plan():
    jobs=[dict(task_id=t,fold=f,seed=1,profile=p,layer_impl="shared_projection")
          for t in ("r_node","a_node") for f in range(10)
          for p in ("G0","G1R","G2R","G3R","G3")]
    jobs += [dict(task_id="r_contract",fold=0,seed=1,profile="G0")]
    return dict(tasks={task:{"record":{"task":"node"}} for task in ("r_node","a_node")},
                jobs=jobs)

def test_batch_expected_complete_300_and_contract_excluded():
    plan=fake_plan();plan["tasks"]["r_contract"]={"record":{"task":"graph"}}
    jobs=batch.expected_jobs(plan)
    assert len(jobs)==300
    assert {mode:sum(item["mode"]==mode for item in jobs) for mode in m.MODES}==dict.fromkeys(m.MODES,100)
    assert all(item["job"]["task_id"]!="r_contract" for item in jobs)
    plan["jobs"].append(plan["jobs"][0])
    with pytest.raises(ValueError):batch.expected_jobs(plan)

@pytest.mark.parametrize("failure",[None,"mode","plan","prepared","gate","weights","optimizer"])
def test_batch_success_binding_must_hold(failure):
    job=dict(task_id="r_node",fold=0,seed=1,profile="G0")
    bound=dict(source_plan={"sha256":"p"},code={"inference.py":"i"},gate={"sha256":"g"},
               prepared={"path":"prep","sha256":"v"})
    report=dict(job=job,intervention="B_full",plan_sha256="p",implementation_sha256="i",
                gate_sha256="g",prepared={"manifest":bound["prepared"]},optimizer_steps=0,
                weights_unchanged=True,graph_edges_unchanged=True,
                unchanged_features_verified=True,frozen_nx_attributes_untouched=True)
    if failure=="mode":report["intervention"]="C_matched"
    elif failure=="plan":report["plan_sha256"]="other"
    elif failure=="prepared":report["prepared"]={}
    elif failure=="gate":report["gate_sha256"]="other"
    elif failure=="weights":report["weights_unchanged"]=False
    elif failure=="optimizer":report["optimizer_steps"]=1
    if failure:
        with pytest.raises(ValueError):batch.validate_completed(report,job,"B_full",bound)
    else:batch.validate_completed(report,job,"B_full",bound)

def test_contrast_tables_separate_density_and_never_average_nonsolidifi():
    views=view_index()
    left={0:report([row()],"B_matched"),1:report([row("real.sol",2,0,0,0)],"B_matched")}
    right={0:report([row(renamed=1)],"C_matched"),
           1:report([row("real.sol",2,0,0,0)],"C_matched")}
    # Equal unique rename counts do not imply equal occurrence exposure.
    right[0]["changed_nodes"][0]["replacements"]=5
    tables=m.contrast_tables("t","G0","B_matched","C_matched",left,right,views)
    assert all(row["cohort"]!="nonSolidiFI" for row in tables["contrast_fold_means"])
    file=next(row for row in tables["contrast_file_changes"] if row["file"]=="buggy_2.sol")
    assert file["left_renamed_identifiers"]==file["right_renamed_identifiers"]==1
    assert file["left_occurrences"]==1 and file["right_occurrences"]==5
    overall=next(row for row in tables["contrast_pooled_metrics"]
                 if row["cohort"]=="all" and row["view"]=="orig")
    assert overall["metric_delta_pp"]["buggy_f1"]==100
    assert overall["corrected_errors"]==1

def current_gate_fixture(tmp_path):
    import json
    job = dict(task_id="r_node", fold=0, seed=1, profile="G0", layer_impl="shared_projection")
    graph = dict(path="frozen.gpickle", sha256="graph", nodes=12, edges=11)
    feature = dict(scheme="ids", feature_size=512, ordered_feature_sha256="features")
    info = tmp_path / "prepared.json"
    info.write_text(json.dumps(dict(profiles={"G0":dict(graph=graph,layer_impl="shared_projection")})))
    plan = dict(jobs=[job], tasks={"r_node":dict(record=dict(task="node", feature=feature),
                                               prepared={"0/1":m.s.ref(info)})})
    gate = dict(job=job, plan_sha256="plan", graph=graph, feature_recipe=feature,
                optimizer_steps=0, gate_only=True, gate_sha256=None,
                implementation_sha256="worker", checkpoint_sha256="a"*64,
                checkpoint_state_sha256="b"*64,
                archive_parity=dict(passed=True, argmax_bitwise=True,
                                   probability_float32_bitwise=True, maximum_probability_difference=0.0))
    path=tmp_path/"current_gate.json"
    path.write_text(json.dumps(gate))
    binding = dict(current_environment_gate=m.s.ref(path), source_plan={"sha256":"plan"},
                   old_worker={"sha256":"worker"})
    return gate, binding, plan, path


def test_current_environment_gate_requires_actual_checked_binding(tmp_path):
    gate, bound, plan, path=current_gate_fixture(tmp_path)
    assert m.validate_current_environment_gate(bound,plan)==gate
    path.write_text(path.read_text()+" ")
    with pytest.raises(ValueError,match="SHA"):
        m.validate_current_environment_gate(bound,plan)
    del bound["current_environment_gate"]
    with pytest.raises(ValueError,match="binding missing"):
        m.validate_current_environment_gate(bound,plan)


@pytest.mark.parametrize("failure", [
    "gate_only", "optimizer", "bool_optimizer", "prior_gate", "passed",
    "argmax", "probability", "maxdiff", "plan", "worker", "job",
    "layer", "graph", "feature", "missing_checkpoint"
])
def test_current_environment_gate_rejects_semantic_identity_drift(tmp_path, failure):
    import json
    gate,bound,plan,path=current_gate_fixture(tmp_path)
    gate=copy.deepcopy(gate)
    if failure=="gate_only":gate["gate_only"]=False
    elif failure=="optimizer":gate["optimizer_steps"]=1
    elif failure=="bool_optimizer":gate["optimizer_steps"]=False
    elif failure=="prior_gate":gate["gate_sha256"]="old-gate"
    elif failure=="passed":gate["archive_parity"]["passed"]=False
    elif failure=="argmax":gate["archive_parity"]["argmax_bitwise"]=False
    elif failure=="probability":gate["archive_parity"]["probability_float32_bitwise"]=False
    elif failure=="maxdiff":gate["archive_parity"]["maximum_probability_difference"]=1e-12
    elif failure=="plan":gate["plan_sha256"]="other-plan"
    elif failure=="worker":gate["implementation_sha256"]="other-worker"
    elif failure=="job":gate["job"]["fold"]=9
    elif failure=="layer":gate["job"]["layer_impl"]="different"
    elif failure=="graph":gate["graph"]["nodes"]=13
    elif failure=="feature":gate["feature_recipe"]["feature_size"]=256
    else:del gate["checkpoint_state_sha256"]
    path.write_text(json.dumps(gate))
    bound["current_environment_gate"]=m.s.ref(path)
    with pytest.raises(ValueError):
        m.validate_current_environment_gate(bound,plan)


def test_current_gate_checkpoint_is_bound_to_verified_inference(tmp_path):
    gate,bound,plan,path=current_gate_fixture(tmp_path)
    checked=m.validate_current_environment_gate(bound,plan)
    actual=dict(job=gate["job"],checkpoint_sha256=gate["checkpoint_sha256"],
                checkpoint_state_sha256=gate["checkpoint_state_sha256"])
    m.validate_gate_checkpoint(checked,actual)
    for field in ("checkpoint_sha256","checkpoint_state_sha256"):
        changed=dict(actual,**{field:"c"*64})
        with pytest.raises(ValueError,match="checkpoint identity differs"):
            m.validate_gate_checkpoint(checked,changed)
    with pytest.raises(ValueError,match="job differs"):
        m.validate_gate_checkpoint(checked,dict(actual,job=dict(gate["job"],fold=1)))
