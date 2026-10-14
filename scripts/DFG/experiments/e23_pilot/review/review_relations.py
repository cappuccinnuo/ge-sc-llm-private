"""Finite frozen-evidence review; JSON/source only, no graph regeneration or pickle load."""
import collections,hashlib,json,random,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[5]
OUT=Path(__file__).resolve().parent
F=ROOT/'scripts/DFG/experiments/audit/state_aware_ddg_stage_f'
ORIG=ROOT.parent/'ge-sc-llm'
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def alias(a,b):
 if a['root']['id']!=b['root']['id']:return 'NO_ALIAS'
 if a['id']==b['id'] and a['certainty']==b['certainty']=='EXACT':return 'EXACT'
 if a['key_kind']==b['key_kind']=='constant' and a['key_type']==b['key_type'] and a['key_value']!=b['key_value']:return 'NO_ALIAS'
 return 'MAY'
def graph(rec):
 by=collections.defaultdict(list)
 for ev in rec['events']:by[ev['block']].append(ev['id'])
 evs={x['id']:x for x in rec['events']}
 # Keep empty blocks explicit to avoid inventing adjacency over branch junctions.
 adj={}
 for b,ss in rec['cfg'].items():
  seq=['block:'+b]+by[b]
  for a,z in zip(seq,seq[1:]):adj[a]=[z]
  adj[seq[-1]]=['block:'+s for s in ss]
 return evs,adj
def check_path(rec,path):
 evs,adj=graph(rec)
 assert path[0] in evs
 for a,b in zip(path,path[1:]):assert b in adj[a],(a,b)
 return evs
def reaching_path(rec,start,end):
 evs,adj=graph(rec);root=evs[start]['location'];q=collections.deque([(start,[start])]);seen=set()
 while q:
  cur,path=q.popleft()
  if cur==end:return path
  if cur in seen:continue
  seen.add(cur)
  if cur!=start and cur in evs:
   ev=evs[cur]
   if ev['kind']=='HAVOC':continue
   if ev['kind']=='WRITE' and alias(root,ev['location'])=='EXACT':continue
  for nxt in adj[cur]:q.append((nxt,path+[nxt]))
 raise AssertionError('No reaching path without HAVOC / strong KILL')
def norm(s):
 s=re.sub(r'/\*.*?\*/|//[^\n]*','',s,flags=re.S)
 s=re.sub(r'\b([A-Za-z_][A-Za-z_0-9]*?)_re_ent\d+\b',r'\1_TEMPLATE',s)
 s=re.sub(r'\b\d+\b','N',s)
 return re.sub(r'\s+',' ',s).strip()
def main():
 proofs=read(F/'F3_attempt_002/F3_EDGE_PROVENANCE.json');cache={};sources={};rows=[];inputs={}
 for item in proofs:
  co=item['cohort'];mp=ORIG/'scripts/DFG/experiments/artifacts/20261012_v1'/co/'prepared/manifest.json';m=read(mp)
  rp=F/'F1_attempt_002'/(co+'_results.json');cache[co]=read(rp)
  inputs[str(mp)]=sha(mp);inputs[str(rp)]=sha(rp)
  grouped=collections.defaultdict(list)
  for i,e in enumerate(item['evidence']):grouped[(e['relation'],e['source_node'],e['target_node'])].append((i,e))
  for key,es in grouped.items():
   idx,e=es[0];file=e['definition']['anchor']['file'];src=Path(m['sources'][file]['path']);raw=src.read_bytes()
   assert hashlib.sha256(raw).hexdigest()==m['sources'][file]['sha256']==e['source_sha256']
   rec=next(x for x in cache[co][file]['functions'] if x['function']==e['function'])
   def snippet(span):return raw[span['start']:span['end']].decode('utf-8')
   s,t=e['definition'],e['use'];texts=[snippet(x['anchor']) for x in (s,t)]
   branch=any(len(v)>1 for v in rec['cfg'].values())
   template=norm(' -> '.join(texts))
   row=dict(cohort=co,relation=key[0],source_node=key[1],target_node=key[2],evidence_indices=[i for i,_ in es],file=file,function=e['function'],source_path=str(src),source_sha256=sha(src),source_line=raw.count(b'\n',0,s['anchor']['start'])+1,target_line=raw.count(b'\n',0,t['anchor']['start'])+1,source_text=texts[0],target_text=texts[1],has_branch=branch,source_kind=s['kind'],target_kind=t['kind'],source_detail=s['detail'],target_detail=t['detail'],template=template,source_location=s.get('location'),target_location=t.get('location'),_evidence=es)
   rows.append(row);sources[(co,file)]=raw
 # Shuffle once at frozen seed; maximize explicit semantic diversity, not outcome/label.
 rng=random.Random(1);chosen=[x for x in rows if x['relation']=='STATE_DEF_USE'];selection={}
 for rel in ('STATE_ACCESS_ORDER','EXTERNAL_CALL_BEFORE_STATE_WRITE'):
  pool=[r for r in rows if r['relation']==rel];rng.shuffle(pool);got=[];covered=[set() for _ in range(7)]
  def strata(r):return (r['cohort'],r['source_kind']+'-'+r['target_kind'],str(r['has_branch']),r['source_detail'],r['target_location']['key_kind'],r['template'],r['function'])
  for _ in range(min(8,len(pool))):
   scored=[(sum(w*(v not in cs) for w,v,cs in zip((7,6,5,4,3,2,1),strata(r),covered)),-i,r) for i,r in enumerate(pool)]
   pick=max(scored,key=lambda x:(x[0],x[1]))[2];pool.remove(pick);got.append(pick)
   for st,v in zip(covered,strata(pick)):st.add(v)
  chosen.extend(got);selection[rel]={'count':len(got),'function_count':len(set(r['function'] for r in got)),'template_count':len(set(r['template'] for r in got)),'branch_functions':sum(r['has_branch'] for r in got),'cohorts':dict(collections.Counter(r['cohort'] for r in got))}
 checks=[]
 for n,r in enumerate(chosen):
  co=r['cohort'];raw=sources[(co,r['file'])];rec=next(x for x in cache[co][r['file']]['functions'] if x['function']==r['function']);witnesses=[]
  for idx,e in r.pop('_evidence'):
   s,t=e['definition'],e['use'];evs={x['id']:x for x in rec['events']}
   assert s==evs[s['id']] and t==evs[t['id']]
   assert s['function']==t['function']==r['function'] and e['certainty']=='EXACT'
   assert r['source_node']!=r['target_node']
   for x in (s,t):
    if x['location']:
     root=x['location']['root'];a=root['declaration'];assert 0<=a['start']<a['end']<=len(raw)
     assert root['source_sha256']==r['source_sha256']
     assert re.search(r'\b'+re.escape(root['name'])+r'\b',raw[a['start']:a['end']].decode())
   if r['relation']=='STATE_DEF_USE':
    assert s['kind']=='WRITE' and t['kind']=='READ' and alias(s['location'],t['location'])=='EXACT'
    path=reaching_path(rec,s['id'],t['id'])
   else:
    path=e['cfg_witness'];check_path(rec,path);assert path[0]==s['id'] and path[-1]==t['id']
    if r['relation']=='STATE_ACCESS_ORDER':
     assert alias(s['location'],t['location'])=='EXACT'
     assert not any(x in evs and evs[x]['kind'] in ('READ','WRITE') and alias(s['location'],evs[x]['location'])!='NO_ALIAS' for x in path[1:-1])
    else:
     assert s['kind']=='HAVOC' and s['detail'].startswith('EXTERNAL_CALL:') and t['kind']=='WRITE' and t['location']['certainty']=='EXACT'
     assert not any(x in evs and evs[x]['kind']=='WRITE' for x in path[1:-1])
   witnesses.append({'evidence_index':idx,'independently_checked_cfg_path':path})
  r.update(review_id='G%02d'%(n+1),automated_check='passed',independent_human_approved=False,compiled=False,review_kind='Codex_static_review_plus_JSON_adjacency_checks',path_claim='structural_CFG_may_reach_not_transaction_feasibility',witnesses=witnesses)
  # Bind declaration text and minimal entire source interval for static inspection.
  r['declaration_text']=[raw[x['root']['declaration']['start']:x['root']['declaration']['end']].decode() for x in (r['source_location'],r['target_location']) if x]
  lo=min(evs[witnesses[0]['independently_checked_cfg_path'][0]]['anchor']['start'],evs[witnesses[0]['independently_checked_cfg_path'][-1]]['anchor']['start'])
  hi=max(evs[witnesses[0]['independently_checked_cfg_path'][0]]['anchor']['end'],evs[witnesses[0]['independently_checked_cfg_path'][-1]]['anchor']['end'])
  r['source_interval']=raw[lo:hi].decode();inputs[r['source_path']]=r['source_sha256'];checks.append(r)
 for name in ('F3_EDGE_PROVENANCE.json','GRAPH_MANIFEST.json','F2_ORACLE_RESULTS.json'):
  p=F/'F3_attempt_002'/name;inputs[str(p)]=sha(p)
 oracle=read(F/'F3_attempt_002/F2_ORACLE_RESULTS.json')
 payload={'schema':'stage-g-finite-relation-review-v1','seed':1,'selection_policy':'all projected contract STATE_DEF_USE; deterministic semantic-diversity greedy ordering after seed1 shuffle; no labels or predictions used','inputs':inputs,'selection':selection,'state_def_use_count':sum(r['relation']=='STATE_DEF_USE' for r in checks),'review_count':len(checks),'oracle_status_counts':dict(collections.Counter(x.get('analysis',{}).get('status','fallback') for x in oracle)),'human_approved':False,'compiled':False,'evidence':checks}
 assert payload['state_def_use_count']==17 and payload['review_count']==33
 (OUT/'relation_evidence_index.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
 lines=['# Fixed finite source review snippets','']
 for r in checks:
  lines+=['## '+r['review_id']+' '+r['cohort']+' '+r['relation'],r['file']+':'+str(r['source_line'])+' -> '+str(r['target_line']),'function: '+r['function'],'nodes: '+str(r['source_node'])+' -> '+str(r['target_node']),'declarations: '+repr(r['declaration_text']),'```solidity',r['source_interval'],'```','']
 (OUT/'source_snippets.md').write_text('\n'.join(lines)+'\n')
 print(json.dumps({k:v for k,v in payload.items() if k not in ('inputs','evidence')},indent=2))
if __name__=='__main__':main()
