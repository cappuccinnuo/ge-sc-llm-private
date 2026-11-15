"""CP1 r2.6 section 6: measure historical D3 only; do not change policy floor."""
import gc
import json
import os
from pathlib import Path
import sys
import time
from dataclasses import asdict

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from compile_repair.core.store import ArtifactStore, emit, read_checked_json, sha256
from compile_repair.toolchain.solc import CP0_SHA256, compile_file, load_trusted_compilers
from compile_repair.toolchain.slither import check_profile, run_slither


def execute():
    os.chdir(str(ROOT))
    store=ArtifactStore(ROOT/'compile_repair/artifacts/cp1_historical_v1')
    cp0=read_checked_json(ROOT/'compile_repair/artifacts/cp0_v2/recon.json',CP0_SHA256)
    compilers,_,refs=load_trusted_compilers()
    profile=check_profile('production')
    jobs=[]
    for version in ['0.4.0','0.4.2','0.4.9','0.4.11']:
        fixture=ROOT/'compile_repair/tests/fixtures/compat_04.sol'
        jobs.append({'version':version,'path':str(fixture),'sha256':sha256(fixture),'scope':'compat_04'})
        for row in cp0['inputs']:
            if row['matrix'].get(version,{}).get('returncode')==0:
                jobs.append({'version':version,'path':str(ROOT/row['path']),'sha256':row['sha256'],'scope':'cp0_rc0'})
    store.write_json('plan.json',{'jobs':jobs,'cwd':[str(ROOT),'/'],'compile_cwd':str(ROOT),
                                 'rule':'One preceding solc invocation at repository root; run_slither independently in both CWDs',
                                 'trusted_compilers':refs,'profile':profile,'floor_unchanged':'0.4.12'})
    started=time.monotonic();records=[];error=None
    with store.journal('invocations.jsonl') as journal:
        for index,job in enumerate(jobs,1):
            try:
                path=Path(job['path']);os.chdir(str(ROOT))
                if sha256(path)!=job['sha256']:raise ValueError('Historical input identity mismatch')
                compilation=compile_file(path,compilers[job['version']])
                emit(journal,dict(kind='solc',scope=job['scope'],**asdict(compilation)))
                if compilation.returncode!=0 or compilation.timed_out:raise ValueError('Previously compiling historical input no longer compiles')
                for cwd in [str(ROOT),'/']:
                    os.chdir(cwd)
                    analysis=run_slither(compilation,profile='production')
                    emit(journal,dict(kind='slither',actual_cwd=cwd,scope=job['scope'],**analysis))
                    records.append(dict(job,cwd=cwd,d3=analysis['d3'],d3_a=analysis['d3_a'],d3_b=analysis['d3_b'],
                        missing_filename=analysis.get('counts',{}).get('missing_filename'),
                        nodes=analysis.get('counts',{}).get('nodes'),exception_type=analysis.get('exception_type'),
                        error_first_line=analysis.get('error_first_line')))
                if sha256(path)!=job['sha256']:raise ValueError('Historical source changed')
                print('HISTORICAL {}/{}'.format(index,len(jobs)),flush=True);gc.collect()
            except Exception as exc:
                error=dict(job,exception_type=type(exc).__name__,message=str(exc));break
            finally:os.chdir(str(ROOT))
    summary={'status':'stopped' if error else 'complete','planned_compilations':len(jobs),'records':records,
             'error':error,'elapsed_seconds':time.monotonic()-started,'floor_unchanged':'0.4.12','cost_usd':0}
    store.write_json('results.json',summary)
    print(json.dumps({k:v for k,v in summary.items() if k!='records'}),flush=True)
    if error:raise SystemExit(2)


if __name__=='__main__':execute()
