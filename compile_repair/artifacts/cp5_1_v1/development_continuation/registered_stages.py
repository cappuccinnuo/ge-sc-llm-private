"""Run the originally registered downstream stages once after the eight approved observations."""
import os
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from complete_measurements import MANDO, PRODUCTION, freeze_defaults, program, record, run_group
from population import ART, LOCAL, OUT, load, save, sha256


def main():
    assert Path(sys.executable).resolve()==Path(PRODUCTION).resolve()
    assert load(HERE/"resume_summary.json")["result_rows"]==6948
    assert sha256(OUT/"real_dev.jsonl")==load(OUT/"real_dev_summary.json")["rows_sha256"]
    assert not (OUT/"policy.json").exists() and not (OUT/"evaluation_stop.json").exists()
    assert (OUT/"stage_runs.jsonl").stat().st_size==0
    save(HERE/"downstream_claim.json",dict(pid=os.getpid(),original_registered_stages_sha256='1d5ced4531fc94631bec9e75372487a79fc71b679b08bb3ea1ccb6c57f79f805',
         development_summary_sha256=sha256(OUT/"real_dev_summary.json")))
    with (OUT/"stage_runs.jsonl").open("a",encoding="utf8") as log:
        run_group([program("policy_freeze","evaluate_benchmark.py","freeze")],log)
        freeze_defaults()
        record(log,dict(stage="apply_frozen_policy",status="complete",proof=sha256(OUT/"policy_application.json")))
        suites=OUT/"frozen_suites"
        suites.mkdir(exist_ok=False)
        env=dict(CP4_OUTPUT=str(suites),CP4_SCRATCH=str(LOCAL/"frozen_suites"))
        suite_script=str(ART/"cp4_v1/run_suite.py")
        run_group([(n+"_frozen_tests", [interp,"-B",suite_script,n], suites/(n+"_driver.log"),env)
                   for n,interp in (("production",PRODUCTION),("mando",MANDO),("dfg",MANDO))],log)
        run_group([("frozen_mando",[PRODUCTION,"-B","-u",str(OUT/"frozen_mando.py")],LOCAL/"frozen_mando.log",{}),
                   program("benchmark","evaluate_benchmark.py","full"),
                   program("real_full_part0","evaluate_units.py","full0"),
                   program("real_masked","evaluate_units.py","masked"),
                   program("real_full_part1","evaluate_units.py","full1")],log)
        run_group([program("merge_full","merge_partitions.py")],log)
        run_group([program("final_aggregation","evaluate_benchmark.py","summarize")],log)
        run_group([program(n+"_provenance","check_provenance.py",n) for n in ("real_dev","benchmark","real_full","real_masked")],log)
        run_group([program("render_results","render_results.py")],log)
        save(OUT/"measurement_completion.json",dict(status="complete",policy_sha256=sha256(OUT/"policy.json"),
             external_summary_sha256=sha256(OUT/"external_summary.json"),benchmark_summary_sha256=sha256(OUT/"benchmark_summary.json"),
             tables_sha256=sha256(OUT/"final_tables.md"),stages_sha256=sha256(OUT/"stage_runs.jsonl")))


if __name__=="__main__":
    main()
