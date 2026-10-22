"""Five-file read-only label audit. No training, graph mutation or target replacement."""
import ast, csv, hashlib, importlib.util, io, json, re, subprocess, sys
from collections import Counter
from pathlib import Path

ROOT = Path('/home/zhao/SmartContract')
R = ROOT / 'ge-sc-llm-ddg-v11'
O = ROOT / 'ge-sc-llm'
H = ROOT / 'ge-sc-transformer'
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(R))
from scripts.DFG.frontend import parse_source, walk, text
from scripts.DFG.projection import Projector, decoded
from process_graphs.tree_sitter_codeviews.utils import preprocessor

def module(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

safe = module('review_safe', O/'scripts/labeling_v2/safe_graph.py')
coords = module('review_coordinates', O/'Test_code/label_pipeline/coordinates.py')
raw = module('review_raw', O/'Test_code/label_pipeline/raw_annotations.py')
old_map = module('review_old_map', O/'scripts/line_mapping.py')
FILES = {'reentrancy': ['buggy_18.sol', '0x627fa62ccbb1c1b04ffaecd72a53e37fc0e17839.sol'],
         'access_control': ['buggy_18.sol','buggy_26.sol','parity_wallet_bug_2.sol']}
SHAS = {'reentrancy':'6a9531542e8b053721ad20938bea5c548750153c0b6d8049aeb2cc454b47a483',
        'access_control':'6d40e6ffc59e8109813836229f7b5baa8cbf5f8542fc69f3a8d4a2b0e48980ad'}
inputs = {}
def protect(p):
    p=Path(p)
    value=hashlib.sha256(p.read_bytes()).hexdigest()
    if str(p) in inputs: assert inputs[str(p)]==value
    inputs[str(p)]=value
    return value

def git(root,*args):
    return subprocess.check_output(['git','-C',str(root)]+list(args))
def provenance(p,repo):
    protect(p)
    rel=p.relative_to(repo).as_posix()
    committed=git(repo,'show','HEAD:'+rel)
    assert committed==p.read_bytes(), 'Modified public input '+str(p)
    return {'path':str(p),'sha256':inputs[str(p)],'equals_git_head':True}

def lit(value):
    for _ in range(3):
        if not isinstance(value,str): break
        try: value=ast.literal_eval(value)
        except (ValueError,SyntaxError): break
    return value
def records(data):
    value=lit(data.get('node_info_vulnerabilities'))
    assert value is None or isinstance(value,list)
    return value or []
def flatten(value):
    if type(value) is int: return {value}
    assert isinstance(value,(tuple,list)),repr(value)
    result=set()
    for item in value: result.update(flatten(item))
    return result
def compact(nums):
    nums=sorted(set(nums)); out=[]
    for n in nums:
        if out and n==out[-1][1]+1: out[-1][1]=n
        else: out.append([n,n])
    return out
def write_json(name,value):
    with (OUT/name).open('x',encoding='utf8') as f:
        json.dump(value,f,ensure_ascii=False,indent=2)

report={'user_date':'2026-10-20','reviewer':'Codex','purpose':'source/annotation/coordinate audit without model predictions',
        'repositories':{},'files':{},'formal_labels_modified':False,'training_executed':False}
for repo in (R,O,H,O/'data/SolidiFI-benchmark',O/'data/smartbug-dataset'):
    report['repositories'][str(repo)]={'head':git(repo,'rev-parse','HEAD').decode().strip()}
for p in (O/'data/smartbug-dataset/vulnerabilities.json',H/'data/smartbug-dataset/vulnerabilities.json'):
    provenance(p,p.parents[0] if 'ge-sc-llm' in str(p) else H)
for cat,names in FILES.items():
    artifact=O/'Test_code/label_pipeline/artifacts/public_endpoints_verified_v1'/cat
    old_manifest_path=artifact/'manifest.json'
    old_manifest=json.loads(old_manifest_path.read_text())
    graph_path=Path(old_manifest['graph_input'])
    assert protect(graph_path)==SHAS[cat]
    graph=safe.read_graph(graph_path)
    label_path=O/'data/upstream_mando_llm/graph_detection'/(cat+'_graph_labels.json')
    labels=json.loads(label_path.read_text()); protect(label_path)
    print('contract labels shape',cat,type(labels).__name__)
    # Released labels use an explicit ordered record list.
    if isinstance(labels,list):
        assignments={x['contract_name']:int(x['targets']) for x in labels}
    else:
        assignments=labels
    for name in names: assert assignments[name]==1
    anns,sources,provs,hashes=raw.load_annotations(O,cat,names,assignments)
    for p,s in hashes.items(): assert protect(p)==s
    old_diffs=json.loads((artifact/'label_differences.json').read_text())
    old_original=json.loads((artifact/'annotations_original.json').read_text())
    old_processed=json.loads((artifact/'annotations_preprocessed.json').read_text())
    for p in (old_manifest_path,artifact/'label_differences.json',artifact/'annotations_original.json',artifact/'annotations_preprocessed.json'):
        protect(p)
    for name in names:
        source_path=sources[name]; source=source_path.read_text()
        source_sha=protect(source_path)
        source_repo=O/'data/SolidiFI-benchmark' if name.startswith('buggy_') else O/'data/smartbug-dataset'
        source_provenance=provenance(source_path,source_repo)
        original_lines=source.splitlines()
        processed,mapping=coords.preprocess_with_map(source)
        assert processed==preprocessor.remove_comments('solidity',preprocessor.remove_empty_lines(source))
        oldmap=old_map.build_line_map(source)
        raw_lines={n for rec in anns[name] for n in rec['lines']}
        mapped={i+1 for i,origin in enumerate(mapping) if raw_lines.intersection(origin)}
        oldmapped={i+1 for i,origin in enumerate(oldmap) if raw_lines.intersection(origin)}
        assert mapped==oldmapped, 'Old/current mapper differs on annotated lines'
        assert raw_lines=={n for rec in old_original[name] for n in rec['lines']}
        assert mapped=={n for rec in old_processed[name] for n in rec['lines']}
        view=parse_source(source,name)
        projector=Projector(graph,view)
        assert view.compat_source==processed
        functions=[]
        for fn in view.functions:
            identifier=fn.child_by_field_name('name')
            start,end=fn.start_point[0]+1,fn.end_point[0]+1
            functions.append({'name':text(source,identifier) if identifier else fn.type,
                              'start':start,'end':end,'code':text(source,fn)})
        nodes=[]; embedded={}; node_counts=Counter(); mismatch_counts=Counter()
        for node,data in graph.nodes(data=True):
            if data.get('source_file')!=name: continue
            endset=flatten(lit(data['node_source_code_lines']))
            assert endset==set(coords.graph_endpoints(data))
            recs=records(data)
            for rec in recs: embedded[json.dumps(rec,sort_keys=True)]=rec
            author=int(bool(recs)); public=int(bool(mapped & endset))
            typ=data['node_type']; synthetic=typ in ('end_if','end_loop')
            code=decoded(data.get('code',''))
            full=set(range(min(endset),max(endset)+1))
            if synthetic: full=set(endset) # compatibility marker only; not an AST body
            origins=sorted({x for p in endset if 1<=p<=len(mapping) for x in mapping[p-1]})
            item={'node_id':node,'node_type':typ,'label':decoded(data['label']),
                  'code':code,'author_records':recs,'endpoints':sorted(endset),
                  'endpoint_original_origins':origins,'synthetic_marker_not_physical_line':synthetic,
                  'author_label':author,'public_endpoint_label':public,
                  'public_full_span_label':int(bool(mapped & full)),
                  'public_hit_processed':sorted(mapped & endset),
                  'original_source_context':[{'line':n,'code':original_lines[n-1]} for n in origins]}
            nodes.append(item)
            node_counts[typ]+=1
            if author!=public: mismatch_counts[typ]+=1
        embedded_list=list(embedded.values())
        embedded_all={n for rec in embedded_list for n in rec['lines']}
        embedded_target={n for rec in embedded_list if rec['category']==cat for n in rec['lines']}
        self_errors=[n['node_id'] for n in nodes if int(bool(set(n['endpoints']) & embedded_all))!=n['author_label']]
        expected={x['node_id']:(x['author'],x['public']) for x in old_diffs if x['source_file']==name}
        actual={x['node_id']:(x['author_label'],x['public_endpoint_label']) for x in nodes if x['author_label']!=x['public_endpoint_label']}
        assert actual==expected, 'Disagreement changed from frozen audit'
        intervals=[]
        public_git=[]
        if name.startswith('buggy_'):
            csv_path=Path(provs[name]['csv'])
            public_git.append(provenance(csv_path,source_repo))
            hgt_dir=H/'data/solidifi_buggy_contracts'/cat
            for p in (hgt_dir/name,hgt_dir/('BugLog_'+name[6:-4]+'.csv'),hgt_dir/'vulnerabilities.json'):
                public_git.append(provenance(p,H))
            with csv_path.open() as f: rows=list(csv.DictReader(f))
            coverage=Counter()
            for idx,row in enumerate(rows,2):
                lo,length=int(row['loc']),int(row['length']); hi=lo+length-1
                coverage.update(range(lo,hi+1))
                overlapping=[{k:fn[k] for k in ('name','start','end')} for fn in functions if fn['start']<=hi and fn['end']>=lo]
                intervals.append({'csv_row':idx,'start':lo,'length':length,'end':hi,
                                  'overlapping_functions':overlapping,
                                  'source':[{'line':i,'code':original_lines[i-1]} for i in range(lo,hi+1)]})
            duplicates=sorted(n for n,k in coverage.items() if k>1)
        else: duplicates=[]
        key=cat+'/'+name
        summary={
            'source':str(source_path),'source_sha256':source_sha,'source_provenance':source_provenance,
            'public_input_provenance':public_git,'source_check':provs[name],
            'contract_target':assignments[name],'original_lines':len(original_lines),'processed_lines':len(mapping),
            'annotation_original':anns[name], 'public_original_unique':len(raw_lines),
            'public_processed_lines':sorted(mapped),'public_processed_unique':len(mapped),
            'embedded_records':embedded_list,'embedded_all_unique':len(embedded_all),
            'embedded_target_unique':len(embedded_target),'embedded_categories':sorted({x['category'] for x in embedded_list}),
            'public_only_processed':sorted(mapped-embedded_target),
            'author_only_processed':sorted(embedded_target-mapped),
            'out_of_bounds_all':sorted(n for n in embedded_all if n<1 or n>len(mapping)),
            'overlap_processed':sorted(mapped & embedded_target),
            'nodes':len(nodes),'author_positive':sum(n['author_label'] for n in nodes),
            'public_endpoint_positive':sum(n['public_endpoint_label'] for n in nodes),
            'public_full_span_positive':sum(n['public_full_span_label'] for n in nodes),
            'disagreements':len(actual),'disagreement_types':dict(mismatch_counts),
            'disagreement_direction':dict(Counter(str(a)+'->'+str(b) for a,b in actual.values())),
            'self_endpoint_replay_mismatches':self_errors,'projection_verified':projector.stats,
            'source_token_sequence_unchanged':True,'old_mapper_annotation_projection_equal':True,
            'csv_overlap_lines':duplicates,
        }
        detail={'summary':summary,'nodes':nodes,'preprocessed_source':processed,
                'processed_to_original':mapping,'functions':functions,'csv_intervals':intervals}
        stem=cat+'__'+name[:-4]
        write_json(stem+'.json',detail)
        lines=['# '+key,'Source SHA: '+source_sha,
               'This is a source/label review. Model predictions were not used.','',
               '## Summary','~~~json',json.dumps(summary,indent=2,ensure_ascii=False),'~~~',
               '## Source with raw and preprocessed coordinate correspondence','~~~text']
        raw_to_proc={}
        for p,origin in enumerate(mapping,1):
            for n in origin: raw_to_proc.setdefault(n,[]).append(p)
        for n,line in enumerate(original_lines,1):
            lines.append('%4d -> %-12s [%s] %s'%(n,','.join(map(str,raw_to_proc.get(n,[]))),
                         'public' if n in raw_lines else '      ',line))
        lines.extend(['~~~','## All node disagreements'])
        for n in nodes:
            if n['author_label']==n['public_endpoint_label']: continue
            lines.extend(['','### Node '+str(n['node_id'])+' '+n['node_type'],
                'Author '+str(n['author_label'])+' / public endpoint '+str(n['public_endpoint_label'])+
                '; processed '+str(n['endpoints'])+' -> original '+str(n['endpoint_original_origins']),
                '~~~solidity',str(n['code']),'~~~'])
        with (OUT/(stem+'.md')).open('x',encoding='utf8') as f: f.write('\n'.join(lines)+'\n')
        report['files'][key]=summary
        print(key,'public/author lines',len(mapped),len(embedded_all),'nodes pos',summary['author_positive'],
              summary['public_endpoint_positive'],'diff',len(actual),'self_errors',self_errors,
              'projection',projector.stats,'oob',len(summary['out_of_bounds_all']))
    del graph
report['inputs']=inputs
report['input_hashes_before_equal_after']=all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==s for p,s in inputs.items())
assert report['input_hashes_before_equal_after']
write_json('audit.json',report)
print('Completed source/coordinate/label replay for five files.')
