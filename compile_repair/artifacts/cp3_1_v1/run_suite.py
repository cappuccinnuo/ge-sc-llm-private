"""Run each requested CPU suite in a fresh external directory."""
from batch import *
name=sys.argv[1]
suite='scripts/DFG/dfg_v2/tests' if name=='dfg' else 'compile_repair/tests'
env='compile-repair-production' if name=='production' else 'mando'
python='/home/zhao/miniconda3/envs/'+env+'/bin/python'
command=[python,'-B','-m','pytest','-x','-q','-p','no:cacheprovider',suite,'--basetemp='+str(LOCAL/('tests_'+name))]
assert not (LOCAL/('tests_'+name)).exists()
t=time.monotonic()
with (B/(name+'_tests.log')).open('x') as out:
    cp=subprocess.run(command,stdout=out,stderr=subprocess.STDOUT)
save(name+'_tests.json',dict(command=command,cwd=str(ROOT),elapsed_seconds=time.monotonic()-t,returncode=cp.returncode,summary=(B/(name+'_tests.log')).read_text().splitlines()[-1]))
sys.exit(cp.returncode)
