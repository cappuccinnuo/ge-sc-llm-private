"""Read-only D2 context audit after explicit D1 gate. Does not infer vulnerability truth."""
import argparse, bisect, csv, hashlib, json, re, sys
from collections import defaultdict, Counter
from pathlib import Path
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[5]
ORIGINAL = Path('/home/zhao/SmartContract/ge-sc-llm')
DIAG = ORIGINAL/'scripts/DFG/experiments/audit/ddg_diagnostics_v1'
if str(REPO) not in sys.path: sys.path.insert(0,str(REPO))
from scripts.DFG.frontend import SourceView, walk
from scripts.DFG.models import Unsupported

class MappingUnavailable(ValueError):
    """Known mapping/parse limitation, never a hash/identity validation failure."""
from scripts.DFG.projection import Projector, ANCHOR, decoded
from scripts.labeling_v2.safe_graph import read_graph

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path): return json.loads(Path(path).read_text(encoding='utf8'))
def write(path,obj):
    with Path(path).open('x',encoding='utf8') as f: json.dump(obj,f,indent=2,ensure_ascii=True)
def positive(d): return int(bool(d.get('node_info_vulnerabilities')))
def ensure_identity(graph, file, node_id, row):
    if type(node_id) is not int: raise ValueError('Original ID must retain integer type')
    d=graph.nodes[node_id]
    if d['source_file']!=file or row['file']!=file or row['original_graph_node_id']!=node_id:
        raise ValueError('File/original ID mismatch')
    if positive(d)!=row['target']: raise ValueError('Author graph target mismatch')
    return d
def exact_train_matches(graph, train_files, val_files, code):
    train,val=set(train_files),set(val_files)
    if train & val: raise ValueError('Split leakage')
    # Labels never participate in the matching key.
    return [n for n,d in graph.nodes(data=True) if d['source_file'] in train and d.get('code')==code]
def interval_rows(rows,start,end):
    result=[]
    for i,row in enumerate(rows,2):
        lo,length=int(row['loc']),int(row['length'])
        if lo<1 or length<1: raise ValueError('Invalid injection interval')
        hi=lo+length-1
        if max(lo,start)<=min(hi,end): result.append(dict(csv_line=i,raw=row,start=lo,end=hi))
    return result

class SourceIndex:
    def __init__(self,graph,manifest,inputs):
        self.graph,self.manifest,self.inputs=graph,manifest,inputs
        self.cache={}
    def file(self,file):
        if file in self.cache:return self.cache[file]
        spec=self.manifest['sources'][file];path=Path(spec['path']);digest=sha(path)
        if digest!=spec['sha256']:raise ValueError('Source SHA mismatch')
        self.inputs[str(path)]=digest
        try:
            view=SourceView(path.read_text(encoding='utf8'),file)
        except Unsupported as exc:
            reason=str(exc)
            allowed=('Multiple Solidity pragmas','Disjunctive pragma','Unsupported pragma constraint',
                     'Pragma crosses scope','Missing supported pragma','Solidity parser ERROR/MISSING')
            if reason.startswith(allowed):raise MappingUnavailable(reason)
            raise
        # Strict whole-file projection identity/source failures must stop the audit.
        try:proj=Projector(self.graph,view)
        except Unsupported as exc:raise ValueError('Integrity: '+str(exc))
        inverse=defaultdict(list)
        for rawkey,compatkey in view.mapping.items():inverse[compatkey].append(rawkey)
        byid={v:k for k,v in view.compat_ids.items()}
        value=(view,proj,inverse,byid,path,digest);self.cache[file]=value
        return value
    def node(self,file,nodeid):
        view,proj,inverse,byid,path,digest=self.file(file)
        data=self.graph.nodes[nodeid];m=ANCHOR.search(decoded(data['label']))
        if not m:raise MappingUnavailable('Synthetic/no exact anchor')
        astid=int(m.group(1))
        if proj.by_ast.get(astid)!=nodeid:raise ValueError('Projection identity mismatch')
        keys=inverse[byid[astid]]
        if len(keys)!=1:raise MappingUnavailable('Nonunique raw AST span')
        node=view.raw_nodes[keys[0]]
        fn=[n for n in walk(view.tree.root_node) if n.type in
            ('function_definition','constructor_definition','fallback_receive_definition','modifier_definition')
            and n.start_byte<=node.start_byte and node.end_byte<=n.end_byte]
        if len(fn)!=1:raise MappingUnavailable('No unique enclosing callable')
        func=fn[0]
        def descriptor(n):
            name=n.child_by_field_name('name')
            return dict(start_byte=n.start_byte,end_byte=n.end_byte,start_line=n.start_point[0]+1,
                end_line=n.end_point[0]+1,ast_type=n.type,text=n.text.decode('utf8'),
                name=name.text.decode('utf8') if name else None)
        # Full related contract declarations/modifiers are context, not binding proof.
        contract=func.parent
        while contract and contract.type not in ('contract_declaration','library_declaration','interface_declaration'):
            contract=contract.parent
        declarations=[];modifiers=[]
        if contract:
            for x in walk(contract):
                if x.type in ('state_variable_declaration','modifier_definition'):
                    (modifiers if x.type=='modifier_definition' else declarations).append(descriptor(x))
        fn_nodes=[]
        for cid,nid in proj.by_ast.items():
            ck=byid[cid];rks=inverse[ck]
            if len(rks)!=1:continue
            rn=view.raw_nodes[rks[0]]
            if func.start_byte<=rn.start_byte and rn.end_byte<=func.end_byte:
                fn_nodes.append(dict(node_id=nid,node_type=self.graph.nodes[nid]['node_type'],
                    label=positive(self.graph.nodes[nid]),**descriptor(rn)))
        return dict(source_path=str(path),source_sha256=digest,ast_id=astid,
            compat_span=list(byid[astid]),node=descriptor(node),
            function=dict(identity=file+':'+str(func.start_byte),**descriptor(func)),
            contract=descriptor(contract) if contract else None, # full contract will be trimmed below
            state_declarations=declarations,modifier_definitions=modifiers,function_hcg_nodes=fn_nodes)

def provenance(category,file,source,inputs):
    result={'author_label_rule':'released node_info_vulnerabilities; original conversion script not established'}
    if file.startswith('buggy_'):
        kind='Re-entrancy' if category=='reentrancy' else 'tx.origin'
        folder=ORIGINAL/'data/SolidiFI-benchmark/buggy_contracts'/kind
        sol=folder/file;csvpath=folder/('BugLog_'+file.split('_')[1].replace('.sol','.csv'))
        result.update(public_source=str(sol),public_csv=str(csvpath))
        if not sol.is_file() or not csvpath.is_file():return dict(result,status='D_missing_public_artifact')
        inputs[str(sol)]=sha(sol);inputs[str(csvpath)]=sha(csvpath)
        result['source_sha_matches']=inputs[str(sol)]==source['source_sha256']
        if not result['source_sha_matches']:return dict(result,status='D_source_version_diff')
        rows=list(csv.DictReader(csvpath.open(encoding='utf8')))
        result.update(status='A_exact_public_source',csv_rows=len(rows),
            intervals_at_node=interval_rows(rows,source['node']['start_line'],source['node']['end_line']),
            intervals_at_function=interval_rows(rows,source['function']['start_line'],source['function']['end_line']),
            interpretation='Public injection intervals are comparison evidence, not proof of author graph conversion rule.')
    else:
        p=ORIGINAL/'data/smartbug-dataset/vulnerabilities.json';inputs[str(p)]=sha(p)
        records=[x for x in read(p) if x.get('name')==file and x.get('path','').startswith('dataset/'+category+'/')]
        result.update(annotation_path=str(p),records=records)
        if len(records)!=1:return dict(result,status='D_ambiguous_annotation_record')
        sol=p.parent/records[0]['path'];inputs[str(sol)]=sha(sol)
        result.update(public_source=str(sol),source_sha_matches=inputs[str(sol)]==source['source_sha256'],
            annotated_lines=[line for v in records[0]['vulnerabilities'] if v['category']==category for line in v['lines']])
        result['status']='A_exact_public_source' if result['source_sha_matches'] else 'D_source_version_diff'
    return result

def main(gate):
    g=read(gate)
    if g.get('status')!='passed':raise ValueError('D1 did not pass')
    out=HERE/'results'
    out.mkdir(exist_ok=False)
    inputs={str(Path(gate).resolve()):sha(gate)}
    evidence=read(DIAG/'case_evidence.json')
    inventory=read(DIAG/'archive/asset_inventory.json')
    inputs[str(DIAG/'archive/asset_inventory.json')]=sha(DIAG/'archive/asset_inventory.json')
    inputs[str(DIAG/'case_evidence.json')]=sha(DIAG/'case_evidence.json')
    tasks={}
    for cohort in ('reentrancy_author','access_control_author'):
        jobs={j['fold']:j for j in inventory['jobs'] if j['cohort']==cohort and j['task']=='node'}
        prepared=Path(jobs[0]['prepared']);mp=prepared/'manifest.json';m=read(mp);inputs[str(mp)]=sha(mp)
        graphs={}
        for v in ('E0','E1'):
            spec=m['graphs'][v]['node'];p=prepared/spec['path']
            if sha(p)!=spec['sha256']:raise ValueError('Frozen graph hash mismatch')
            inputs[str(p)]=sha(p);graphs[v]=read_graph(p)
        raw=m['inputs']['raw_graph'];rawp=Path(raw['path'])
        if sha(rawp)!=raw['sha256']:raise ValueError('Author graph SHA mismatch')
        inputs[str(rawp)]=sha(rawp);rawgraph=read_graph(rawp)
        for n,d in graphs['E0'].nodes(data=True):
            rd=rawgraph.nodes[n]
            for field in ('source_file','node_type','label','code','node_info_vulnerabilities'):
                if d.get(field)!=rd.get(field):raise ValueError('Prepared/author label or identity mismatch')
        contexts={}
        cp=DIAG/'static'/(cohort+'_node_node_context.csv');inputs[str(cp)]=sha(cp)
        for row in csv.DictReader(cp.open()):contexts[int(row['node_id'])]=row
        fp=DIAG/'static/function_coverage.csv'
        if not fp.exists(): raise FileNotFoundError(str(fp))
        functions=[r for r in csv.DictReader(fp.open()) if r.get('task_key')==cohort+'_node']
        inputs[str(fp)]=sha(fp)
        tasks[cohort]=dict(jobs=jobs,manifest=m,graphs=graphs,index=SourceIndex(graphs['E0'],m,inputs),
            contexts=contexts,functions=functions,pred={},splits={})
    selected=[dict(cohort=x['cohort'],fold=x['fold'],node_id=x['node_id'],selection='prior_diagnostic_fixed_case') for x in evidence['cases']]
    # Deterministic extra cases: first wrong expression with incoming DDG in each requested AC file,
    # and first different-function wrong expression with incoming DDG. No p/F1 optimization.
    for file,fold in [('buggy_18.sol',7),('buggy_26.sol',8)]:
        t=tasks['access_control_author'];job=t['jobs'][fold]
        p=Path(job['variants']['E0']['paths']['cv_validation_predictions.json']);rows=read(p)
        valid=[r for r in rows if r['file']==file and r['best']!=r['target']
            and t['graphs']['E0'].nodes[r['original_graph_node_id']]['node_type']=='expression_statement'
            and int(t['contexts'][r['original_graph_node_id']]['ddg_in'])>0]
        seen=set()
        for r in sorted(valid,key=lambda r:r['original_graph_node_id']):
            n=r['original_graph_node_id'];s=t['index'].node(file,n);identity=s['function']['identity']
            if identity in seen:continue
            seen.add(identity);selected.append(dict(cohort='access_control_author',fold=fold,node_id=n,selection='lowest_original_id_wrong_expression_with_DDG_distinct_function'))
            if len(seen)==2:break
    cases=[];duplicates=[];table=[]
    for spec in selected:
        cohort,fold,n=spec['cohort'],spec['fold'],spec['node_id'];t=tasks[cohort];graph=t['graphs']['E0'];enh=t['graphs']['E1'];job=t['jobs'][fold]
        if fold not in t['pred']:
            t['pred'][fold]={}
            for v in ('E0','E1'):
                p=Path(job['variants'][v]['paths']['cv_validation_predictions.json'])
                expected=job['variants'][v]['hashes_from_receipt']['cv_validation_predictions.json']
                if sha(p)!=expected:raise ValueError('Prediction hash mismatch')
                inputs[str(p)]=sha(p);t['pred'][fold][v]={r['original_graph_node_id']:r for r in read(p)}
            splitp=Path(job['splits']);inputs[str(splitp)]=sha(splitp)
            t['splits'][fold]=next(x for x in read(splitp)['folds'] if x['fold']==fold)
        pred={v:t['pred'][fold][v][n] for v in ('E0','E1')}
        file=graph.nodes[n]['source_file']
        for v,r in pred.items():ensure_identity(graph,file,n,r)
        source=t['index'].node(file,n)
        # Avoid redundant complete-contract text: full function and relevant declarations retained.
        if source['contract']:source['contract'].pop('text')
        target=positive(graph.nodes[n]);caseid=cohort+'/'+file+'/'+str(n)
        ddg=[dict(source=a,target=b,key=k,attributes=d) for a,b,k,d in enh.edges(keys=True,data=True)
            if d.get('edge_type')=='DATA_DEF_USE' and (a==n or b==n)]
        fs=[r for r in t['functions'] if r['function']==source['function']['identity']]
        split=t['splits'][fold]
        if file not in split['val_files']:raise ValueError('Case not in frozen validation fold')
        match=exact_train_matches(graph,split['train_files'],split['val_files'],graph.nodes[n].get('code'))
        matchrows=[]
        for mid in match:
            md=graph.nodes[mid];mf=md['source_file']
            mr=dict(case_id=caseid,train_file=mf,train_original_node_id=mid,train_label=positive(md),
                same_label=positive(md)==target,match_key='exact_serialized_code',in_frozen_train=True,
                graph_stored_lines=md.get('node_source_code_lines'),label_payload=md.get('node_info_vulnerabilities'),
                source_path=t['manifest']['sources'][mf]['path'],source_sha256=t['manifest']['sources'][mf]['sha256'])
            try:
                ms=t['index'].node(mf,mid);ms.pop('contract',None);mr['exact_context']=ms;mr['mapping_status']='A_exact'
            except MappingUnavailable as exc:
                mr['mapping_status']='D_not_mapped';mr['mapping_reason']=type(exc).__name__+': '+str(exc)
            matchrows.append(mr);duplicates.append(mr)
        case=dict(spec,case_id=caseid,file=file,author_label=target,author_label_payload=graph.nodes[n].get('node_info_vulnerabilities'),
            graph_stored_source_lines=graph.nodes[n].get('node_source_code_lines'),stored_code=graph.nodes[n].get('code'),
            source=source,predictions=pred,coverage=t['contexts'][n],ddg_edges=ddg,
            frozen_function_analysis=fs,public_annotation=provenance(cohort.replace('_author',''),file,source,inputs),
            train_duplicate_counts=dict(total=len(matchrows),positive=sum(r['train_label'] for r in matchrows),
                opposite=sum(not r['same_label'] for r in matchrows),exact_contexts=sum(r['mapping_status']=='A_exact' for r in matchrows)),
            label_conclusion='C_annotation_context_requires_independent_review; no relabeling',
            compilation_validation='Not executed; Tree-sitter/source correspondence is not Solidity compiler verification')
        cases.append(case)
        table.append(dict(case_id=caseid,cohort=cohort,fold=fold,file=file,node_id=n,
            function=source['function']['identity'],function_name=source['function']['name'],source_sha256=source['source_sha256'],
            ast_id=source['ast_id'],raw_start=source['node']['start_line'],raw_end=source['node']['end_line'],
            label=target,E0_best=pred['E0']['best'],E1_best=pred['E1']['best'],
            E0_p=pred['E0']['best_positive_probability'],E1_p=pred['E1']['best_positive_probability'],
            ddg_in=t['contexts'][n]['ddg_in'],ddg_out=t['contexts'][n]['ddg_out'],
            ddg_two_hop=t['contexts'][n]['ddg_affected_within_two'],
            train_matches=len(matchrows),train_opposite=sum(not r['same_label'] for r in matchrows),
            public_annotation_status=case['public_annotation']['status'],evidence_level='A_identity_predictions;B_semantics;C_label_context'))
    oracle_contexts=[]
    requests=[
        ('access_control_author','mapping_write.sol',{'set','get','withdraw'}),
        ('access_control_author','arbitrary_location_write_simple.sol',{'PopBonusCode','UpdateBonusCodeAt','Destroy'}),
        ('access_control_author','buggy_18.sol',{'transferOwnership','acceptOwnership'}),
        ('reentrancy_author','buggy_36.sol',{'mul','changeVotingRules','transferOwnership'}),
        ('reentrancy_author','buggy_27.sol',{'transfer','transferFrom','claimReward_re_ent18'}),
    ]
    for cohort,file,names in requests:
        t=tasks[cohort];index=t['index']
        view,proj,inverse,byid,path,digest=index.file(file)
        for fn in view.functions:
            name=fn.child_by_field_name('name')
            if name is None or name.text.decode('utf8') not in names:continue
            rawkey=(fn.start_byte,fn.end_byte,fn.type)
            compatkey=view.mapping[rawkey]
            nid=proj.by_ast.get(view.compat_ids[compatkey])
            if nid is None:raise ValueError('Required oracle function lacks exact HCG entry')
            context=index.node(file,nid)
            if context['contract']:context['contract'].pop('text')
            # Include all source modifier definitions as context; do not assert inheritance binding.
            context['source_modifier_definitions']=[
                dict(start_byte=x.start_byte,end_byte=x.end_byte,start_line=x.start_point[0]+1,
                     end_line=x.end_point[0]+1,text=x.text.decode('utf8'))
                for x in walk(view.tree.root_node) if x.type=='modifier_definition']
            oracle_contexts.append(dict(cohort=cohort,file=file,function_entry_node=nid,source=context))
    for p,digest in inputs.items():
        if sha(p)!=digest:raise ValueError('Read-only input drift: '+p)
    write(out/'D3_SOURCE_CONTEXTS.json',dict(status='exact_source_context_not_validated_state_oracle',contexts=oracle_contexts))

    write(out/'D2_CASE_EVIDENCE.json',dict(protocol='ddg-v11-context-readonly-v1',cases=cases))
    write(out/'D2_TRAIN_DUPLICATES.json',duplicates)
    write(out/'D2_INPUT_AUDIT.json',dict(status='passed',input_sha256=inputs,cases=len(cases),
        train_duplicate_rows=len(duplicates),original_inputs_unchanged=True,no_training=True,no_graph_or_label_writes=True))
    with (out/'D2_CASE_AUDIT.csv').open('x',encoding='utf8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(table[0]));w.writeheader();w.writerows(table)
    print(json.dumps(dict(status='passed',cases=len(cases),duplicate_rows=len(duplicates),inputs=len(inputs))))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--d1-gate',required=True);a=p.parse_args();main(a.d1_gate)
