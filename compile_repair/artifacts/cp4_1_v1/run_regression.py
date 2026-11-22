"""Run the two module suites and the DFG suite from the repository root, stopping on failure."""
from batch import *
frozen(OLD/"run_suite.py")
env=dict(os.environ, CP4_OUTPUT=str(OUT), CP4_SCRATCH=str(LOCAL), PYTHONDONTWRITEBYTECODE="1",
         PYTHONNOUSERSITE="1", OMP_NUM_THREADS="2", MKL_NUM_THREADS="2", CUDA_VISIBLE_DEVICES="")
for name,profile in (("production","compile-repair-production"),("mando","mando"),("dfg","mando")):
    python=Path("/home/zhao/miniconda3/envs")/profile/"bin/python"
    command=[str(python),"-B",str(OLD/"run_suite.py"),name]
    result=subprocess.run(command,cwd=str(ROOT),env=env)
    if result.returncode:
        sys.exit(result.returncode)
    print(name,load(name+"_tests.json")["summary"],flush=True)
