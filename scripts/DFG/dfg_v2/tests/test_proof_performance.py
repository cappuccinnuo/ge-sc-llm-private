"""Proof scope and comparison tests; no GPU or extra real-data fits."""
import pytest
from scripts.DFG.dfg_v2.experiment import proof_performance as proof


def test_proof_refuses_formal_batch_output_before_any_write(tmp_path):
    plan = tmp_path / "batch" / "plan.json"
    output = plan.parent / "runs" / "proof"
    with pytest.raises(ValueError, match="frozen batch"):
        proof.worker(plan, output, proof.JOBS[0])
    assert not output.exists()


def test_proof_refuses_other_job_before_any_write(tmp_path):
    output = tmp_path / "proof"
    with pytest.raises(ValueError, match="exactly the two"):
        proof.worker(tmp_path / "batch/plan.json", output, "reentrancy_node/0/1/G0")
    assert not output.exists()
