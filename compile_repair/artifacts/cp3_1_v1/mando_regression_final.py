from batch import *
from compile_repair.cli import main

old = ART/'cr_store_mando_v5'
seal_hash = 'db925ee1642b5f8eae79d20defbbec673ffbaa7b4a0bb37cc270027bb1a8372b'
assert seal_hash in committed(old/'README.md').decode()
seal = json.loads(verified(old/'seal.json', seal_hash))['files']
summary = json.loads(verified(old/'summary.json',seal['summary.json']))
sources = [s['path'] for s in summary['supplied']]
assert len(sources) == 846 and all(x['kind']=='file' for x in summary['supplied'])
out = LOCAL/'cr_store_mando_v6_final'
argv = ['repair'] + sources + ['--regression','mando','--order','ascending','--output',str(out)]
rows = []
def compare(record, folder):
    rel = 'units/'+record.unit_id+'/'
    previous = json.loads(verified(old/(rel+'result.json'),seal[rel+'result.json']))
    current = json.loads((folder/(rel+'result.json')).read_bytes())
    checks = {k:current[k]==previous[k] for k in ('status','selected_version','reason','flags','settings','inputs')}
    graph = folder/(rel+'graph.json')
    if record.status == 'success':
        ref = verified(old/(rel+'graph.json'),seal[rel+'graph.json'])
        checks['graph_bytes'] = graph.read_bytes() == ref
    else:
        checks['expected_failure'] = record.reason == 'slither_side_failure' and not graph.exists() and rel+'graph.json' not in seal
    rows.append(dict(unit_id=record.unit_id,checks=checks,previous=seal[rel+'result.json'],current=sha((folder/(rel+'result.json')).read_bytes())))
    if not all(checks.values()):
        raise ValueError('MANDO mismatch: '+record.unit_id+' '+str(checks))
t=time.monotonic()
rc=main(argv, result_check=compare)
success=sum('graph_bytes' in r['checks'] for r in rows)
ok=(rc==2 and len(rows)==846 and success==843 and all(all(r['checks'].values()) for r in rows))
save('mando_regression_final.json',dict(accepted=ok,cli_returncode=rc,argv=argv,records=rows,success=success,known_failures=len(rows)-success,elapsed_seconds=time.monotonic()-t,seal_sha256=sha((out/'seal.json').read_bytes())))
assert ok
