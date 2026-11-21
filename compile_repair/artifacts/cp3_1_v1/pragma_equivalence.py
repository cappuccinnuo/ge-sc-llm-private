"""Verify old accepted expressions and MANDO plans against the actual base revision."""
from batch import *
from compile_repair.rules import environment as current
from compile_repair.toolchain.solc import load_trusted_compilers, pragma_evidence
from scripts.DFG.models import Unsupported
import types
original=types.ModuleType('cp31_base_environment')
path='compile_repair/rules/environment.py'
blob=subprocess.check_output(['git','show','61c94e00:'+path])
exec(compile(blob,path,'exec'),original.__dict__)
compilers,frozen,_=load_trusted_compilers()
units,refs=members()
expressions={}
seen_sources={}
counts=Counter();groups=Counter()
changed=set()
def examine(raw):
    digest=sha(raw)
    if digest not in seen_sources:
        item_counts=Counter()
        for evidence in pragma_evidence(raw):
            literal=bytes.fromhex(evidence['expression_hex'])
            expr=current.code_only(literal).decode('latin1').strip()
            if expr not in expressions:
                try:before=original._expression_interval([expr])
                except Unsupported:before='unsupported'
                try:after=current._expression_interval([expr])
                except Unsupported:after='unsupported'
                if before!='unsupported':
                    assert before==after,('old expression changed',expr,before,after)
                expressions[expr]=(before,after)
            item_counts['old_evaluable' if expressions[expr][0]!='unsupported' else 'old_unsupported']+=1
        seen_sources[digest]=item_counts
    return seen_sources[digest]

unsupported=set(saved('unsupported_units.json'))
for item in units:
    uid=item['unit_id']
    if uid in refs:
        ref=refs[uid];rec=json.loads(verified(ref['result_path'],ref['result_sha256']))
        inputs=[verified(s['path'],s['sha256']) for s in rec['inputs']]
    else:
        inputs=[verified(item['path'],item['entry_sha256'])]
    for raw in inputs:counts.update(examine(raw))
    groups[item['corpus']]+=1
    if item['corpus']=='MANDO':
        raw=inputs[0];known,_=current.mando_known_version(raw,frozen)
        for order in ('ascending','descending'):
            assert original.make_plan(inputs,compilers,known,'mando',order)==current.make_plan(inputs,compilers,known,'mando',order),uid
        counts['mando_plan_comparisons']+=2
    if uid in unsupported:
        try:bounds=current.pragma_interval(inputs)
        except Unsupported:continue
        changed.add(uid)
for path in sorted((MOD/'tests/fixtures').rglob('*')):
    if path.is_file():
        raw=path.read_bytes()
        counts.update(examine(raw));counts['fixtures']+=1
        try:old=original.pragma_interval([raw])
        except Unsupported:continue
        assert current.pragma_interval([raw])==old,path
assert counts['mando_plan_comparisons']==1692
# Source spellings can include snippets following a malformed directive.
# Publish hashes and intervals; exact bytes stay in the local research workspace.
stats=[dict(expression_sha256=sha(expr.encode('latin1')),old=old,new=new) for expr,(old,new) in expressions.items()]
save('pragma_equivalence.json',dict(base_module_sha256=sha(blob),counts=dict(counts),units=dict(groups),distinct_source_hashes=len(seen_sources),distinct_expressions=len(expressions),expression_audit=stats,old_supported_equal=True,formerly_unsupported_units=sorted(unsupported),newly_evaluable_units=sorted(changed)))
print(counts,'newly_evaluable',len(changed))
