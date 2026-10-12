import pytest
from scripts.DFG.experiments.summarize_paper import rows_for
from scripts.DFG.experiments.paper_protocol import NAME, VERSION, SCORE_ROLE


def fixture():
    return {"protocol": NAME, "protocol_version": VERSION, "score_role": SCORE_ROLE,
            "mode": "smoke", "cohort": "fixture", "task": "node", "folds": [
                {"fold": 0, "status": "complete", "variants": {"E0": {
                    "score_role": SCORE_ROLE, "best_epoch": 0, "last_epoch": 2,
                    "cv_validation": {"best": {"buggy_f1": 12}, "last": {"buggy_f1": 10}}}}}]}


def test_output_names_and_role_are_cv_validation():
    rows = rows_for(fixture())
    assert len(rows) == 2
    assert all(r["score_role"] == "cv_validation" for r in rows)


@pytest.mark.parametrize("change", ["nested", "outer", "incomplete", "inner_outer"])
def test_report_rejects_protocol_mixing_and_omitted_folds(change):
    data = fixture()
    if change == "nested":
        data["protocol_version"] = "ddg-nested-paired-v1"
    elif change == "outer":
        data["score_role"] = "independent_outer_test"
    elif change == "incomplete":
        data["folds"][0]["status"] = "blocked"
    else:
        data["folds"][0]["variants"]["E0"]["outer_test"] = {}
    with pytest.raises(ValueError):
        rows_for(data)
