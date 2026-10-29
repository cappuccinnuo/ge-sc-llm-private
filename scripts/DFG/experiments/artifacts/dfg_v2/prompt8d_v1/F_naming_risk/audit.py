"""Read-only audit of selective idN replacement as a residual marker family."""
from pathlib import Path
import json, re, hashlib
from collections import Counter
from scripts.DFG.dfg_v2.diagnostics8d import stratification as scopes
from scripts.DFG.dfg_v2.diagnostics8d import keyword_baselines as keywords
from scripts.DFG.dfg_v2.diagnostics8c import scoring as s
from scripts.DFG.dfg_v2.diagnostics8c.inference import identifiers, replacement_map, rewrite_code, serialized_view
from scripts.labeling_v2.safe_graph import read_graph
from process_graphs.tree_sitter_codeviews.utils import preprocessor

ROOT=Path('/home/zhao/SmartContract/ge-sc-llm-ddg-v11')
OUT=ROOT/'scripts/DFG/experiments/artifacts/dfg_v2/prompt8d_v1/F_naming_risk'
PLAN=ROOT/'scripts/DFG/experiments/artifacts/dfg_v2/prompt8_v1/batch1/plan.json'
OLD=ROOT/'scripts/DFG/experiments/artifacts/dfg_v2/prompt8c_v1'
A=ROOT/'scripts/DFG/experiments/artifacts/dfg_v2/prompt8d_v1/A_v2/stratification.json'
PATTERN=re.compile(r'id[0-9]+')

def names(code, serialized=False):
    if code is None:return []
    logical=serialized_view(code)[0] if serialized else code
    return [word for word,_,_ in identifiers(logical) if PATTERN.fullmatch(word)]

def counts(code, function, introduced):
    own=names(code,True);fun=names(function)
    return dict(node_occurrences=len(own),function_occurrences=len(fun),
                introduced_node_occurrences=sum(x in introduced for x in own),
                introduced_function_occurrences=sum(x in introduced for x in fun),
                node_names=sorted(set(own)),function_names=sorted(set(fun)))

def predictions(value, introduced_only=False):
    prefix='introduced_' if introduced_only else ''
    own=int(value[prefix+'node_occurrences']>0);fun=int(value[prefix+'function_occurrences']>0)
    return dict(node_text=own,function_text=fun,node_or_function=int(own or fun))

def main():
    if (OUT/'risk.json').exists():raise FileExistsError('Existing risk report must not be overwritten')
    assert names('id0 + _id1 + xid2 + id3x + "id4" /* id5 */ // id6\nid7')==['id0','id7']
    plan,raw_views,reports=scopes.load_context(PLAN,OLD)
    inventory=s.read(A)
    if inventory['bindings']['plan']!=s.ref(PLAN):raise ValueError('Scope plan differs')
    files={};input_refs=[]
    for report in reports:
        task=report['job']['task_id']
        for file,mapping in report['mappings'].items():
            key=(task,file)
            value=(mapping,report['source_refs'][file])
            if key in files and files[key]!=value:raise ValueError('Frozen maps disagree across profiles')
            files[key]=value
    all_rows={};file_records=[];tables=[];graph_refs={}
    for task,items in inventory['inventories'].items():
        views=s.index_rows(raw_views[task])
        if set(views)!=set(s.index_rows(items)):raise ValueError('View identity differs')
        tref=plan['tasks'][task]['record']
        graph_refs[task]=tref['original_graph']
        graph=read_graph(scopes.checked(tref['original_graph']))
        source_data={};functions={};original_checks=0
        for file,ref in sorted(tref['sources'].items()):
            source=scopes.checked(ref).read_text(encoding='utf8')
            frozen_map,frozen_ref=files[(task,file)]
            if frozen_ref!=ref or replacement_map(source)!=frozen_map:
                raise ValueError('Source or frozen mapping differs')
            before_names=names(source)
            mapping=frozen_map
            if not all(PATTERN.fullmatch(v) for v in mapping.values()):
                raise ValueError('Replacement scheme is not idN')
            if set(mapping.values()) & {w for w,_,_ in identifiers(source)}:
                raise ValueError('Replacement collides with existing original identifier')
            renamed,edits=rewrite_code(source,mapping)
            compat=preprocessor.remove_comments('solidity',preprocessor.remove_empty_lines(source)).encode('utf8')
            source_data[file]=(ref,source,renamed,compat,mapping)
            file_records.append(dict(task=task,file=file,source=ref,solidifi=bool(re.fullmatch(r'buggy_\d+\.sol',file)),
                mapping=mapping,original_source_idN_occurrences=len(before_names),
                original_source_idN_names=sorted(set(before_names)),
                renamed_source_idN_occurrences=len(names(renamed)),
                renamed_source_idN_names=sorted(set(names(renamed))),
                introduced_unique_names=len(mapping),introduced_source_occurrences=len(edits),
                introduced_names_absent_from_original=True))
        rows=[]
        for item in items:
            file=item['file'];nid=item['original_graph_node_id'];ref,source,renamed,compat,mapping=source_data[file]
            if ref['sha256']!=item['source_sha256'] or item['source_sha256']!=views[s.identity(item)]['source_sha256']:
                raise ValueError('Source identity differs')
            attrs=graph.nodes[nid]
            if attrs['source_file']!=file or attrs['node_type']!=item['node_type']:
                raise ValueError('Graph identity differs')
            before=attrs['code']
            if rewrite_code(before,mapping)[0]!=item['renamed_code']:raise ValueError('Renamed node code differs')
            span=item['function_compat_span'];original_function=None
            if span is not None:
                original_function=compat[span[0]:span[1]].decode('utf8')
                if rewrite_code(original_function,mapping)[0]!=item['renamed_function_code']:
                    raise ValueError('Renamed function span differs')
                key=(file,tuple(span),item['function_ast_type'])
                pair=(original_function,item['renamed_function_code'])
                if key in functions and functions[key]!=pair:raise ValueError('Function duplicate differs')
                functions[key]=pair
            elif item['renamed_function_code'] is not None:
                raise ValueError('Function has no frozen span')
            original_checks+=1
            bc=counts(before,original_function,set(mapping.values()))
            ac=counts(item['renamed_code'],item['renamed_function_code'],set(mapping.values()))
            if bc['introduced_node_occurrences'] or bc['introduced_function_occurrences']:
                raise ValueError('Introduced name already in original graph code')
            row={k:item[k] for k in ('file','source_sha256','original_graph_node_id','node_type','solidifi','scope_verified')}
            row.update(fold=views[s.identity(item)]['fold'],before=bc,after=ac,
                original_prediction=predictions(bc),renamed_prediction=predictions(ac),
                introduced_only_prediction=predictions(ac,True))
            rows.append(row)
        all_rows[task]=rows
        for state in ('original','renamed','introduced_only'):
            scoring_rows=[dict(x,prediction=x[state+'_prediction']) for x in rows]
            tables.extend(dict(task=task,state=state,**x) for x in keywords.summarize(scoring_rows,views))
        for record in file_records:
            if record['task']!=task:continue
            subset=[x for x in rows if x['file']==record['file']]
            fs=[v for k,v in functions.items() if k[0]==record['file']]
            record.update(nodes=len(subset),unique_projected_functions=len(fs),
                original_node_code_idN_occurrences=sum(x['before']['node_occurrences'] for x in subset),
                renamed_node_code_idN_occurrences=sum(x['after']['node_occurrences'] for x in subset),
                original_unique_function_idN_occurrences=sum(len(names(v[0])) for v in fs),
                renamed_unique_function_idN_occurrences=sum(len(names(v[1])) for v in fs),
                original_node_or_function_positive=sum(x['original_prediction']['node_or_function'] for x in subset),
                renamed_node_or_function_positive=sum(x['renamed_prediction']['node_or_function'] for x in subset))
    totals=[]
    for task in sorted(all_rows):
        for cohort in ('SolidiFI','nonSolidiFI'):
            selected=[x for x in file_records if x['task']==task and x['solidifi']==(cohort=='SolidiFI')]
            row=dict(task=task,cohort=cohort,files=len(selected))
            for key in ('introduced_unique_names','introduced_source_occurrences','original_source_idN_occurrences',
                        'renamed_source_idN_occurrences','nodes','original_node_code_idN_occurrences',
                        'renamed_node_code_idN_occurrences','unique_projected_functions',
                        'original_unique_function_idN_occurrences','renamed_unique_function_idN_occurrences',
                        'original_node_or_function_positive','renamed_node_or_function_positive'):
                row[key]=sum(x[key] for x in selected)
            totals.append(row)
    result=dict(version='prompt8d-selective-idN-risk-audit-v1',training_count=0,model_forward_count=0,
        pattern='full identifier id[0-9]+ outside strings/comments; exact idN family',
        bindings=dict(plan=s.ref(PLAN),scopes=s.ref(A),old_summary=s.ref(OLD/'D/summary/summary.json'),
                      labels=s.ref(OLD/'A/node_views.json'),graphs=graph_refs,script=s.ref(Path(__file__))),
        validation=dict(frozen_maps_profiles_consistent=True,source_maps_equal_frozen=True,
                        original_node_codes_rewrite_exact=True,original_function_spans_rewrite_exact=True,
                        no_replacement_name_collision=True),
        totals=totals,files=file_records,predictions=all_rows,pooled_metrics=tables,
        notes=['Only this additional risk artifact is created; F feature view, fold plan, graphs, labels and maps are unchanged.',
               'All original node code and function spans are recovered from frozen inputs, not from inverse string guesses.',
               'Source counts are file-lexical counts; node code counts may duplicate source material in container nodes.',
               'Unique function counts deduplicate lexical AST spans; function baseline still assigns to each scored node.',
               'orig/C1/C2 retain frozen diagnostic semantics; C2 changes scoring population, not graph or labels.',
               'No-learning detectability demonstrates residual feature correlation, not measured retraining performance.',
               'Selective renaming removes original marker spelling but does not establish removal of injection identity.'])
    s.write(OUT/'risk.json',result)
    s._csv(OUT/'pooled_metrics.csv',tables)
    s._csv(OUT/'file_counts.csv',file_records)
    s._csv(OUT/'totals.csv',totals)
    print(json.dumps(dict(totals=totals,renamed_OR=[x for x in tables if x['state']=='renamed' and x['rule']=='node_or_function']),indent=2))
    return result

if __name__=='__main__':main()
