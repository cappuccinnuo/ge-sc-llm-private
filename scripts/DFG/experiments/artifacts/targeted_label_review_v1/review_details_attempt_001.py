"""Bounded semantic/range review. Candidate ranges are audit-only, never new ground truth."""
import ast, hashlib, importlib.util, json, subprocess, sys
from collections import Counter
from pathlib import Path
P=Path(__file__).resolve().parent
O=Path('/home/zhao/SmartContract/ge-sc-llm')
H=O.parent/'ge-sc-transformer'
def mod(name,path):
    spec=importlib.util.spec_from_file_location(name,str(path))
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
co=mod('range_review_coords',O/'Test_code/label_pipeline/coordinates.py')
def read(stem): return json.loads((P/(stem+'.json')).read_text())
def projected(lines,mapping): return {p+1 for p,origins in enumerate(mapping) if set(origins)&set(lines)}
review={'candidate_boundary_policy':'Audit-only comparison to visible injection declaration/function boundaries, not adopted labels',
        'prediction_data_used':False,'range_candidates':{},'endpoint_vs_full_span':{}}
edits={
 'reentrancy__buggy_18':{7:((105,10),(105,6)),8:((111,6),(111,10))},
 'access_control__buggy_18':{7:((86,4),(86,3)),8:((89,3),(89,4)),21:((223,4),(225,4))},
 'access_control__buggy_26':{8:((100,4),(100,3)),9:((103,3),(103,4))}
for stem,changes in edits.items():
    d=read(stem); before={n for rec in d['summary']['annotation_original'] for n in rec['lines']}
    after=set(); log=[]
    for row in d['csv_intervals']:
        original=(row['start'],row['length']); replacement=original
        if row['csv_row'] in changes:
            expected,replacement=changes[row['csv_row']]
            assert expected==original
            log.append({'csv_row':row['csv_row'],'before':original,'candidate':replacement,
                        'original_function_intersection':row['overlapping_functions']})
        after.update(range(replacement[0],replacement[0]+replacement[1]))
    mapped=projected(after,d['processed_to_original'])
    node_changes=[]
    for n in d['nodes']:
        candidate=int(bool(mapped & set(n['endpoints'])))
        if candidate!=n['public_endpoint_label']:
            node_changes.append({'node_id':n['node_id'],'node_type':n['node_type'],'code':n['code'],
                'origins':n['endpoint_original_origins'],'public':n['public_endpoint_label'],'candidate':candidate,
                'author':n['author_label']})
    review['range_candidates'][stem]={'edits':log,'raw_added':sorted(after-before),'raw_removed':sorted(before-after),
        'node_changes':node_changes,'public_positive_before':d['summary']['public_endpoint_positive'],
        'candidate_positive':sum(int(bool(mapped & set(n['endpoints']))) for n in d['nodes'])}
for p in sorted(P.glob('*__*.json')):
    d=json.loads(p.read_text())
    review['endpoint_vs_full_span'][p.stem]=[
        {k:n[k] for k in ('node_id','node_type','endpoints','code','public_endpoint_label','public_full_span_label')}
        for n in d['nodes'] if n['public_endpoint_label']!=n['public_full_span_label']]
name='0x627fa62ccbb1c1b04ffaecd72a53e37fc0e17839.sol'
sb_root=O/'data/smartbug-dataset'
sb=json.loads((sb_root/'vulnerabilities.json').read_text())
hgt_json=H/'data/smartbug-dataset/vulnerabilities.json'
hgt=json.loads(hgt_json.read_text())
codepath=H/'process_graphs/control_flow_graph_generator.py'
code=codepath.read_text()
assert subprocess.check_output(['git','-C',str(H),'show','HEAD:process_graphs/control_flow_graph_generator.py'])==codepath.read_bytes()
tree=ast.parse(code)
tree.body=[fn for fn in tree.body if isinstance(fn,ast.FunctionDef) and fn.name=='get_vulnerabilities']
assert len(tree.body)==1
scope={}; exec(compile(tree,str(codepath),'exec'),scope)
legacy=scope['get_vulnerabilities'](name,hgt)
candidate_records=[r for r in sb if r['name']==name]
comparisons=[]
texts=[]
for record in candidate_records:
    src=sb_root/record['path']
    assert src.read_bytes()==subprocess.check_output(['git','-C',str(sb_root),'show','HEAD:'+record['path']])
    txt,map_=co.preprocess_with_map(src.read_text()); texts.append(txt)
    comparisons.append({'path':str(src),'sha256':hashlib.sha256(src.read_bytes()).hexdigest(),
        'records':record['vulnerabilities'],
        'projected':[{**v,'lines':sorted(projected(v['lines'],map_))} for v in record['vulnerabilities']]})
assert legacy==[{'lines':[44],'category':'unchecked_low_level_calls'}]
assert len(texts)==2 and texts[0]==texts[1]
review['same_basename_category_selection']={
    'source_code':str(codepath),'source_code_sha256':hashlib.sha256(codepath.read_bytes()).hexdigest(),
    'legacy_function_output':legacy,'category_snapshots':comparisons,
    'preprocessed_text_byte_equal':True,
    'conclusion':'Legacy basename-only last-match lookup reproduces foreign-category selection; does not explain released processed coordinate 11'}
review['compilation_or_runtime_validation']='Not executed; AST/static source checks do not prove compilation or exploitability.'
with (P/'range_and_category_review.json').open('x',encoding='utf8') as f: json.dump(review,f,ensure_ascii=False,indent=2)
for k,v in review['range_candidates'].items():
 print(k,'raw added/removed',v['raw_added'],v['raw_removed'],'node_changes',len(v['node_changes']),
       'positive',v['public_positive_before'],v['candidate_positive'])
print('legacy basename lookup:',legacy)
print('category-specific projected annotations:',[x['projected'] for x in comparisons])
