"""CP1 reproducible checks; evidence runner only, never imported by production."""
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent


def write(name, value):
    with (OUT/name).open('x', encoding='utf8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write('\n')


def run_tests(name, environment, target):
    python = '/home/zhao/miniconda3/envs/'+environment+'/bin/python'
    command = [python,'-B','-m','pytest','-q','-ra','-x','-p','no:cacheprovider',target,
               '--basetemp='+str(OUT/('tmp_'+name))]
    env = dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',
               TREE_SITTER_LIB_DIR='/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64')
    if environment == 'compile-repair-production':env['PYTHONNOUSERSITE']='1'
    started=time.monotonic()
    with (OUT/(name+'.log')).open('xb') as stream:
        result=subprocess.run(command,cwd=str(ROOT),env=env,stdout=stream,stderr=subprocess.STDOUT)
    raw=(OUT/(name+'.log')).read_bytes()
    with (OUT/(name+'.log.gz')).open('xb') as stream:
        with gzip.GzipFile(filename='',mode='wb',fileobj=stream,mtime=0) as compressed:compressed.write(raw)
    receipt={'command':command,'returncode':result.returncode,'elapsed_seconds':time.monotonic()-started,
             'environment':{k:env.get(k) for k in ['PYTHONDONTWRITEBYTECODE','PYTHONNOUSERSITE','OMP_NUM_THREADS','MKL_NUM_THREADS','TREE_SITTER_LIB_DIR']},
             'log_sha256':hashlib.sha256(raw).hexdigest(),'log_bytes':len(raw),
             'gzip_sha256':hashlib.sha256((OUT/(name+'.log.gz')).read_bytes()).hexdigest()}
    write(name+'.json',receipt)
    print(raw.decode('utf8',errors='replace')[-7000:],flush=True)
    print(json.dumps(receipt),flush=True)
    if result.returncode:raise SystemExit(result.returncode)


def run_measurement(mode):
    command=['/home/zhao/miniconda3/envs/compile-repair-production/bin/python','-B',str(OUT/('run_'+mode+'.py'))]
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONNOUSERSITE='1',OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',
             TREE_SITTER_LIB_DIR='/home/zhao/SmartContract/ge-sc-llm/build/linux-x86_64')
    started=time.monotonic()
    with (OUT/(mode+'.log')).open('xb') as stream:
        result=subprocess.run(command,cwd=str(ROOT),env=env,stdout=stream,stderr=subprocess.STDOUT)
    raw=(OUT/(mode+'.log')).read_bytes()
    with (OUT/(mode+'.log.gz')).open('xb') as stream:
        with gzip.GzipFile(filename='',mode='wb',fileobj=stream,mtime=0) as compressed:compressed.write(raw)
    receipt={'command':command,'returncode':result.returncode,'elapsed_seconds':time.monotonic()-started,
             'environment':{k:env[k] for k in ['PYTHONDONTWRITEBYTECODE','PYTHONNOUSERSITE','OMP_NUM_THREADS','MKL_NUM_THREADS','TREE_SITTER_LIB_DIR']},
             'log_sha256':hashlib.sha256(raw).hexdigest(),'log_bytes':len(raw),
             'gzip_sha256':hashlib.sha256((OUT/(mode+'.log.gz')).read_bytes()).hexdigest()}
    write(mode+'.json',receipt)
    print(raw.decode('utf8',errors='replace')[-4000:],flush=True)
    print(json.dumps(receipt),flush=True)
    if result.returncode:raise SystemExit(result.returncode)


if __name__ == '__main__':
    mode=sys.argv[1]
    if mode=='production':run_tests('pytest_production','compile-repair-production','compile_repair/tests')
    elif mode=='mando':run_tests('pytest_mando','mando','compile_repair/tests')
    elif mode=='dfg':run_tests('pytest_dfg','mando','scripts/DFG/dfg_v2/tests')
    elif mode in ('sample','historical'):run_measurement(mode)
    else:raise SystemExit('Unknown check')
