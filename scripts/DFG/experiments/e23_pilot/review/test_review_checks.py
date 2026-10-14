import importlib.util
from pathlib import Path
import pytest
spec=importlib.util.spec_from_file_location('finite_review',str(Path(__file__).with_name('review_relations.py')))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def loc(name='s',key='',kind='scalar'):
 return {'id':name+key,'root':{'id':name},'certainty':'EXACT','key_kind':kind,'key_value':key,'key_type':'uint256'}
def rec(kill=None,branch=False):
 ev=[{'id':'d','block':'b0','kind':'WRITE','location':loc()}, {'id':'u','block':'b2','kind':'READ','location':loc()}]
 if kill:ev.insert(1,{'id':'k','block':'b1','kind':kill,'location':loc() if kill=='WRITE' else None})
 return {'events':ev,'cfg':{'b0':['b1','b2'] if branch else ['b1'],'b1':['b2'],'b2':[]}}
def test_reaching_rejects_havoc():
 with pytest.raises(AssertionError):m.reaching_path(rec('HAVOC'),'d','u')
def test_reaching_rejects_strong_kill():
 with pytest.raises(AssertionError):m.reaching_path(rec('WRITE'),'d','u')
def test_reaching_keeps_bypass_union():
 assert m.reaching_path(rec('WRITE',True),'d','u')==['d','block:b2','u']
def test_forged_nonadjacent_witness_rejected():
 with pytest.raises(AssertionError):m.check_path(rec(),['d','u'])
def test_verified_witness_uses_empty_cfg_blocks():
 assert m.check_path(rec(),['d','block:b1','block:b2','u'])
def test_alias_never_uses_different_names_as_key_inequality():
 assert m.alias(loc('m','1','constant'),loc('m','2','constant'))=='NO_ALIAS'
 assert m.alias(loc('m','k','parameter'),loc('m','j','parameter'))=='MAY'
