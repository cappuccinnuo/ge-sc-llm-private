"""EP7 sequential fresh-process coordinator; never grants its own authorization."""
import argparse
from pathlib import Path
import subprocess
import sys
import traceback
from ..io import ROOT,ref,read,write
from ..execution import _Lock
from ..analysis_ep7 import summarize

def run(root):
    root=Path(root).resolve()
    with _Lock(root/".pipeline.lock"):
        if (root/"pipeline_complete.json").exists():raise FileExistsError("EP7 already complete; verify existing results")
        if (root/"pipeline_failure.json").exists():raise RuntimeError("Retained pipeline failure; explicit recovery required")
        try:
            for scope,module in (("gpu_probes","scripts.edge_sem.pilot"),("norm_pilot","scripts.edge_sem.pilot"),
                                 ("formal","scripts.edge_sem.execution")):
                plan=root/scope/"plan.json"
                subprocess.run([sys.executable,"-B","-m",module,"all","--plan",str(plan)],
                    check=True,cwd=str(ROOT))
            result=summarize(root/"formal/plan.json",root/"results")
            write(root/"pipeline_complete.json",dict(passed=True,summary=ref(root/"results/summary.json"),
                formal_fits=result["fits"],gpu_probe_jobs=8,norm_pilot_fits=1))
        except Exception as error:
            write(root/"pipeline_failure.json",dict(error=repr(error),traceback=traceback.format_exc(),
                automatic_retry=False))
            raise

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--root",required=True)
    run(p.parse_args().root)
