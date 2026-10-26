"""Synthetic-only unit tests for the approved supplemental probe."""
import pytest
from scripts.DFG.dfg_v2 import slither_shape_supplement as probe


def fake(function, source, local_reads=(), local_writes=(), phi=False):
    return dict(function=function+"(uint256)", source=source, node_type_name="IFLOOP",
                context_kind="function", span=dict(start=0,end=len(source)),
                ir=[], ir_ssa=([dict(class_name="Phi",text="storage phi")] if phi else []),
                local_variables_read=[dict(name=x) for x in local_reads],
                local_variables_written=[dict(name=x) for x in local_writes],
                state_variables_read=[],state_variables_written=[])


def test_fixed_supplement_source_has_only_expected_shapes():
    p=probe.case_path()
    s=p.read_text()
    assert "S[9] storage records = stateRecords" in s
    assert "records[i] = S(v)" in s
    assert "bytes memory out = new bytes(n)" in s
    assert "out[i] = bytes1(uint8(1))" in s
    assert "msg.sender.call.value(amount);" in s
    assert "msg.sender.call.value(amount)();" not in s


def test_conditions_match_their_actual_function_not_shared_text():
    cases=[dict(compiler_version="0.4.24",status="compiled",nodes=[
        fake("storageArrayLoop","i < n",local_writes=("records",),phi=True),
        fake("memoryBytes","i < n",local_writes=("out",),phi=True)])]
    d=probe.observations(cases)["0.4.24"]
    assert d["storage_array_loop"]["target_local_write"]
    assert d["bytes_loop"]["target_local_write"]
    assert d["storage_array_loop"]["local_variables_written"]==["records"]
    assert d["bytes_loop"]["local_variables_written"]==["out"]


def test_negative_bare_read_is_preserved_not_defaulted_true():
    cases=[dict(compiler_version="0.5.11",status="compiled",nodes=[fake("bare","x")])]
    d=probe.observations(cases)["0.5.11"]["bare_identifier"]
    assert d["status"]=="observed"
    assert d["target_local_read"] is False


def test_missing_and_duplicate_observation_never_confirms():
    n=fake("bare","x")
    case=dict(compiler_version="0.4.24",status="compiled",nodes=[n,n])
    d=probe.observations([case])["0.4.24"]
    assert d["bare_identifier"]["status"]=="missing_or_ambiguous"
    assert d["bare_identifier"]["matched_nodes"]==2
    assert d["bytes_loop"]["status"]=="missing_or_ambiguous"


def test_existing_output_fails_before_environment_access(tmp_path,monkeypatch):
    def fail():
        raise AssertionError("No environment or compiler access allowed")
    monkeypatch.setattr(probe,"inspect_environment",fail)
    with pytest.raises(ValueError,match="overwrite"):
        probe.run(tmp_path,tmp_path/"manifest")


def test_unapproved_version_rejected():
    with pytest.raises(ValueError,match="compiler"):
        probe.observations([dict(compiler_version="0.8.0",status="compiled",nodes=[])])


def test_corrected_cast_has_no_other_source_change():
    directory=probe.case_path().parent
    original=(directory/"ShapeSupplement.sol").read_bytes()
    corrected=(directory/"ShapeSupplementRetry.sol").read_bytes()
    assert corrected==original.replace(b"byte(1)",b"bytes1(uint8(1))")


def test_corrected_cast_preserves_actual_observed_source():
    n=fake("memoryBytes","out[i] = bytes1(uint8(1))",local_writes=("out",))
    row=probe.observations([dict(compiler_version="0.5.11",status="compiled",nodes=[n])])
    obs=row["0.5.11"]["bytes_write"]
    assert obs["status"]=="observed"
    assert obs["source"]=="out[i] = bytes1(uint8(1))"
    assert obs["target_local_write"]


def test_cast_retry_rejects_existing_output_before_reading_history(tmp_path):
    from scripts.DFG.dfg_v2 import slither_shape_retry
    with pytest.raises(ValueError,match="overwrite"):
        slither_shape_retry.run(tmp_path,tmp_path/"trusted",tmp_path/"failed")
