"""Extract compact, identity-checked Prompt8D report facts; no forwards."""
from pathlib import Path
import json,hashlib
A=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def one(rows,**fields):
 found=[r for r in rows if all(r.get(k)==v for k,v in fields.items())]
 if len(found)!=1:raise ValueError((fields,len(found)))
 return found[0]
def main():
 d=read(A/'BC_run/summary/summary.json')
 if d['status']!='complete' or d['inference_count']!=300:raise ValueError('incomplete')
 means=d['cohort_fold_means']; pooled=d['cohort_pooled_metrics']
 out={'summary_sha256':sha(A/'BC_run/summary/summary.json'),'main':[],
      'cohort_scores':[],'comparisons':[],'resources':{},'unchanged':{}}
 for task in ['reentrancy_node','access_control_node']:
  for profile in ['G0','G1R','G2R','G3R','G3']:
   row={'task':task,'profile':profile}
   for mode in ['B_full','B_matched','C_matched']:
    m=one(means,task=task,profile=profile,intervention=mode,cohort='all',view='orig',prediction_state='renamed')
    row[mode]={k:m[k] for k in ['buggy_f1','macro_f1','precision','recall']}
   orig=one(means,task=task,profile=profile,intervention='B_full',cohort='all',view='orig',prediction_state='original')
   row['original']={k:orig[k] for k in ['buggy_f1','macro_f1','precision','recall']}
   contrast=one(d['contrast_fold_means'],task=task,profile=profile,left='8C_idN',right='B_full',cohort='all',view='orig')
   row['Bfull_minus_idN']=contrast['metric_delta_pp']
   out['main'].append(row)
 for r in pooled:
  if r['prediction_state']=='renamed':out['cohort_scores'].append(r)
 out['comparisons']=d['contrast_pooled_metrics']
 reports=[]
 for item in d['inputs']:
  p=Path(item['report']['path'])
  if sha(p)!=item['report']['sha256']:raise ValueError('changed report')
  reports.append(read(p))
 completion=read(A/'BC_run/execution_complete.json')
 statuses=completion['statuses']
 if len(reports)!=300 or len(statuses)!=300 or any(r['returncode']!=0 for r in statuses):raise ValueError('incomplete')
 out['resources']={'jobs':300,'failures':0,'retry_count':0,
    'worker_internal_seconds_sum':sum(r['seconds'] for r in reports),
    'subprocess_seconds_sum':sum(r['seconds'] for r in statuses),
    'peak_allocated_bytes':max(r['peak_allocated_bytes'] for r in reports),
    'peak_reserved_bytes':max(r['peak_reserved_bytes'] for r in reports)}
 views=read(A.parent/'prompt8c_v1/A/node_views.json')
 lookup={task:{(r['file'],r['original_graph_node_id']):r for r in rows} for task,rows in views.items()}
 for task in lookup:
  for mode in ['B_full','B_matched','C_matched']:
   rows=[r for p in reports if p['job']['task_id']==task and p['intervention']==mode for r in p['predictions']
     if not lookup[task][(r['file'],r['original_graph_node_id'])]['solidifi']]
   out['unchanged'][task+'/'+mode]={'rows_across_five_profiles':len(rows),
    'class_changes':sum(r['original_best']!=r['renamed_best'] for r in rows),
    'probability_changes':sum(r['original_probability']!=r['renamed_probability'] for r in rows)}
   if out['unchanged'][task+'/'+mode]['class_changes'] or out['unchanged'][task+'/'+mode]['probability_changes']:raise AssertionError('Unexpected nonSolidiFI change')
 with (A/'report_facts.json').open('x') as f:json.dump(out,f,indent=2,allow_nan=False)
 print(json.dumps({'main':out['main'],'resources':out['resources'],'unchanged':out['unchanged']},indent=2))
if __name__=='__main__':main()
