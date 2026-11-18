"""CP3 category denominators, multi-label counts and zero-count retention."""
from compile_repair.evaluation.report import aggregate_failures

def test_unit_counts_not_attempt_counts_and_zero_categories():
    rows=[{"corpus":"A","unit_id":"x","entry_sha256":"a"*64,"status":"unrepaired",
           "failures":[{"category":"other","template":"x"},{"category":"other","template":"x"},
                       {"category":"type_error_other","template":"y"}]},
          {"corpus":"A","unit_id":"y","entry_sha256":"b"*64,"status":"success","failures":[]},
          {"corpus":"B","unit_id":"z","entry_sha256":"c"*64,"status":"unrepaired",
           "failures":[{"category":"missing_relative_file","source_path":"a.sol","start":4,
                        "path":"./absent.sol","candidate_kind":"unique"}]}]
    result=aggregate_failures(rows,["other","type_error_other","missing_relative_file","json_error"])
    table={r["category"]:r for r in result["category_unit_counts"]}
    assert result["remaining_failures"]=={"A":1,"B":1}
    assert table["other"]["units"]==1 and table["other"]["fraction_remaining_failures"]==0.5
    assert table["json_error"]["units"]==0 and table["json_error"]["example_sha256"]==[]
    assert result["relative_basename_candidates"]=={"unique":1}
    assert result["other_templates"]=={"x":2}
    assert sum(r["fraction_remaining_failures"] for r in table.values())==1.5
