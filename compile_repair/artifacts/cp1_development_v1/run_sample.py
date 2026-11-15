"""CP1 r2.6 section 5: common CLI, frozen sample plan, fail at first mismatch."""
import gc
import gzip
import hashlib
import json
from pathlib import Path
import random
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from compile_repair.cli import main
from compile_repair.core.store import ArtifactStore, emit, read_checked_json, sha256
from compile_repair.toolchain.solc import CP0_SHA256, version_tuple


def execute():
    output=ROOT/'compile_repair/artifacts/cp1_sample_v1'
    store=ArtifactStore(output)
    cp0=read_checked_json(ROOT/'compile_repair/artifacts/cp0_v2/recon.json',CP0_SHA256)
    failures=[r for r in cp0['inputs'] if r['rule_a_result']['status']!='passed']
    selected=[]
    for category in sorted({r['category'] for r in cp0['inputs']}):
        pool=sorted([r for r in cp0['inputs'] if r['category']==category and r['rule_a_result']['status']=='passed'],key=lambda r:r['sha256'])
        selected.extend(random.Random(0).sample(pool,10))
    known=[r for r in cp0['inputs'] if r['category']=='reentrancy' and r['file'] in
           ('reentrancy_bonus.sol','reentrancy_cross_function.sol','reentrancy_insecure.sol')]
    known_paths={r['path'] for r in known}
    paths={r['path']:r for r in failures+selected+known}
    plan={'cp0_sha256':CP0_SHA256,'method':'For each sorted category, sort passing files by SHA256, then Random(0).sample(pool,10). Union all rule A nonpasses and 3 reviewed failures; sort final paths.',
          'rule_a_nonpass':len(failures),'passing_sample':len(selected),'known_failures':len(known),'total':len(paths),
          'inputs':[{'path':p,'sha256':r['sha256'],'expected':'slither_side_failure' if p in known_paths else 'success',
                     'cp0_ascending':r['selection']['ascending']} for p,r in sorted(paths.items())]}
    store.write_json('sample_plan.json',plan)
    results=[];started=time.monotonic();status='complete';error=None
    with store.journal('acceptance.jsonl') as journal:
        for index,(relative,row) in enumerate(sorted(paths.items()),1):
            try:
                path=ROOT/relative
                if sha256(path)!=row['sha256']:raise ValueError('Sample source identity mismatch')
                case=output/'cases'/('{:03d}'.format(index))
                argv=['repair',str(path),'--output',str(case),'--regression','mando','--order','ascending']
                case_start=time.monotonic();rc=main(argv)
                manifests=[json.loads(line) for line in (case/'manifest.jsonl').read_text().splitlines()]
                if len(manifests)!=1:raise ValueError('Expected one completed manifest record')
                record=manifests[0];version=record['selected_version'];old=row['selection']['ascending']
                attribution=None
                if relative in known_paths:
                    if rc!=2 or record['reason']!='slither_side_failure':raise ValueError('Known Slither failure differs from expected')
                    attribution='expected_slither_side_failure'
                else:
                    if rc!=0 or record['status']!='success':raise ValueError('Unexpected unrepaired sample')
                    final=record['attempts'][-1]
                    if final['solc']['returncode']!=0 or not final['slither']['d3']:raise ValueError('Selected version lacks rc0/D3')
                    v=version_tuple(version)
                    if v<(0,4,12) or row['interval'] and not tuple(row['interval'][0])<=v<tuple(row['interval'][1]):
                        raise ValueError('Selected compiler violates declared interval/floor')
                    if 'pragma_overridden' in record['flags'] or 'crossed_minor' in record['flags']:
                        raise ValueError('Unexpected override/minor crossing in this MANDO sample')
                    if version==old:attribution='same_version'
                    elif version not in cp0['compilers'] and v<version_tuple(old):attribution='a_new_lower_installed_version'
                    elif record['settings'] and final['settings_retry']:attribution='c_settings_retry'
                    else:raise ValueError('Version difference not attributable to allowed evidence categories')
                if sha256(path)!=row['sha256']:raise ValueError('Original source changed')
                result={'path':relative,'source_sha256':row['sha256'],'case':str(case.relative_to(output)),
                        'cli_argv':argv,'returncode':rc,'status':record['status'],'reason':record['reason'],
                        'selected_version':version,'cp0_ascending':old,'attribution':attribution,'flags':record['flags'],
                        'solc_invocations':len(record['attempts']),
                        'slither_invocations':sum(a.get('slither') is not None for a in record['attempts']),
                        'elapsed_seconds':time.monotonic()-case_start}
                results.append(result);emit(journal,result)
                print('ACCEPT {}/{} {}'.format(index,len(paths),attribution),flush=True)
                gc.collect()
            except Exception as exc:
                status='stopped';error={'path':relative,'exception_type':type(exc).__name__,'message':str(exc)}
                emit(journal,{'failure':error});break
    from collections import Counter
    summary={'status':status,'planned':len(paths),'completed':len(results),'unrun':len(paths)-len(results),
             'counts':dict(Counter(r['attribution'] for r in results)),
             'solc_invocations':sum(r['solc_invocations'] for r in results),
             'slither_invocations':sum(r['slither_invocations'] for r in results),
             'error':error,'elapsed_seconds':time.monotonic()-started,'results':results,'llm_calls':0,'cost_usd':0}
    store.write_json('acceptance_summary.json',summary)
    if status!='complete':raise SystemExit(2)
    print(json.dumps({k:v for k,v in summary.items() if k!='results'}),flush=True)


if __name__=='__main__':execute()
