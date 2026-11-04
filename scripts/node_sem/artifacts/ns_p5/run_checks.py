import os,sys,subprocess,time,json
from pathlib import Path
out=Path(__file__).resolve().parent
env=dict(os.environ,CUDA_VISIBLE_DEVICES='',PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',TREE_SITTER_LIB_DIR='/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64')
python='/home/zhao/miniconda3/envs/mando/bin/python'
commands=[('nodesem',[python,'-B','-m','pytest','-q','-p','no:cacheprovider','scripts/node_sem/tests']),
('dfg_v2',[python,'-B','-m','pytest','-q','-p','no:cacheprovider','scripts/DFG/dfg_v2/tests']),
('legacy',[python,'-B','-m','pytest','-q','-p','no:cacheprovider','scripts/DFG/tests','tests/test_graph_utils.py'])]
for name,cmd in commands:
    t=time.monotonic()
    with (out/(name+'.log')).open('xb') as stream:
        p=subprocess.run(cmd,env=env,stdout=stream,stderr=subprocess.STDOUT)
    row=dict(command=cmd,exit_code=p.returncode,seconds=time.monotonic()-t)
    (out/(name+'.json')).write_text(json.dumps(row,indent=2)+'\n')
    print(name+' '+(out/(name+'.log')).read_text()[-600:],flush=True)
    if p.returncode:sys.exit(p.returncode)
