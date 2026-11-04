"""Source-defined assertions for frozen Oracle observations; not human certification."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[5];OUT=Path(__file__).resolve().parent
E=ROOT/'scripts/DFG/experiments/audit/state_aware_ddg_prototype_v1/ORACLE_EXPECTATIONS.json'
F=ROOT/'scripts/DFG/experiments/audit/state_aware_ddg_stage_f/F3_attempt_002/F2_ORACLE_RESULTS.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 expect=json.loads(E.read_text())['oracles'];obs={x['oracle_id']:x for x in json.loads(F.read_text())};rows=[]
 required_fallback={'O1','O3','O5','O6','O8','O9','O11'}
 # Predicates manually transcribed from source statements, never from labels/predictions.
 concrete={
 'O10':{('m[1]=7;','uint a=m[1];','EXACT')},
 'O12':{('s=1;','return s;','EXACT'),('s=2;','return s;','EXACT')},
 'O13':{('m[k]=1;','return m[k];','MAY')},
 'O15':{('s=1;','uint a=s;','EXACT')},
 'O18':{('s=1;','return s;','EXACT'),('s=2;','return s;','EXACT')},
 'O19':{('s=1;','require(s>0);','EXACT'),('t=2;','return t;','EXACT')},
 'O20':{('s=2;','return s;','EXACT'),('s=3;','return s;','EXACT')}}
 for o in expect:
  k=o['oracle_id'];raw=Path(o['source_path']).read_bytes() if o['source_path'] else o['source'].encode();assert hashlib.sha256(raw).hexdigest()==o['source_sha256']
  a=obs[k].get('analysis',{});facts=a.get('facts',[])
  def txt(ev):sp=ev['anchor'];return raw[sp['start']:sp['end']].decode().strip()
  actual={(txt(f['definition']),txt(f['use']),f['certainty']) for f in facts}
  if k in required_fallback:assert a['status']=='function_fallback' and not facts;check='unsupported function retains no partial facts'
  elif k in concrete:assert actual==concrete[k],(k,actual,concrete[k]);check='exact source-defined statement pairs and certainty'
  elif k=='O16':
   # Loop-carried s-- -> next s-- is valid over iterations; no transitive closure claim.
   assert len(facts)==6 and all(f['certainty']=='EXACT' for f in facts)
   assert {txt(f['definition']) for f in facts}=={'s=3;','s--;'}
   assert all(f['definition']['location']['root']['name']==f['use']['location']['root']['name']=='s' for f in facts)
   check='two possible definitions reach condition, decrement and return in structural loop CFG'
  else:assert not facts;check='no invented state definition from entry/control/local/call'
  rows.append({'oracle_id':k,'source_sha256':o['source_sha256'],'status':a['status'],'check':check,'passed':True,'facts':len(facts),'human_approved':False,'compiled':False})
 result={'schema':'stage-g-source-oracle-check-v1','frozen_expectations_sha256':sha(E),'frozen_observations_sha256':sha(F),'count':len(rows),'passed':len(rows),'new_human_approvals':0,'compilation_runs':0,'checks':rows}
 (OUT/'oracle_review.json').write_text(json.dumps(result,indent=2)+'\n');print('20 frozen source Oracle checks passed; human approval=0, compilation=0')
if __name__=='__main__':main()
