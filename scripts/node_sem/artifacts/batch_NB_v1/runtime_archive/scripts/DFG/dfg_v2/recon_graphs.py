"""Prompt 0 read-only graph/AST reconnaissance; no DFG construction changes."""
import argparse
import ast
from collections import Counter
from pathlib import Path
from scripts.DFG.frontend import SourceView, parse, walk, text
from scripts.DFG.models import Unsupported
from scripts.DFG.projection import Projector
from scripts.DFG.state.stage_k.profile import SupportedSourceView
from scripts.DFG.integration.io import read_json, checked, read_sources, sha256, write_json
from scripts.DFG.integration.rebuild import DEFAULT_MANIFEST
from scripts.labeling_v2.safe_graph import read_graph

ROOT = Path(__file__).resolve().parents[3]
TYPES = ('expression_statement', 'variable_declaration_statement', 'if_statement',
         'for_statement', 'while_statement', 'do_while_statement', 'return_statement',
         'emit_statement', 'revert_statement', 'throw_statement')


def anchor(node, view, projector):
    key = view.mapping.get((node.start_byte, node.end_byte, node.type))
    return projector.by_ast.get(view.compat_ids.get(key))


def describe(source, node):
    return {'line': node.start_point[0]+1, 'end_line': node.end_point[0]+1,
            'start_byte':node.start_byte, 'end_byte':node.end_byte,
            'ast_type':node.type, 'text':text(source,node)}


def dump(node, source):
    return {'type':node.type, 'text':text(source,node), 'children':[
        {'field':node.field_name_for_child(i),'node':dump(c,source)}
        for i,c in enumerate(node.children)]}


def audit_file(graph, name, source, metadata):
    result={'file':name, 'declarations':[], 'statements':[], 'views':{}}
    try:
        tree=parse(source)
    except Unsupported as exc:
        result['parse_error']=str(exc); return result
    all_nodes=list(walk(tree.root_node))
    declarations=[n for n in all_nodes if n.type=='state_variable_declaration']
    special=[]
    for parent in all_nodes:
        if parent.type in ('modifier_definition','constructor_definition'):
            body=parent.child_by_field_name('body')
            if body is not None:
                special.extend((parent.type+':'+n.type,n) for n in walk(body) if n.type in TYPES)
        if parent.type=='for_statement':
            update=parent.child_by_field_name('update')
            if update is not None:special.append(('for_update',update))
    statements=[(n.type,n) for n in all_nodes if n.type in TYPES]+special
    views={}
    for label,factory in [('source_view',lambda:SourceView(source,name)),
                          ('supported_view',lambda:SupportedSourceView(source,name,metadata))]:
        try:
            view=factory();projector=Projector(graph,view)
            views[label]=(view,projector)
            result['views'][label]=dict(projector.stats, status='verified')
        except Unsupported as exc:
            result['views'][label]={'status':'unsupported','reason':str(exc)}
    for n in declarations:
        entry=describe(source,n)
        for label in ('source_view','supported_view'):
            node_id=anchor(n,*views[label]) if label in views else None
            entry[label]={'node_id':node_id,'status':('view_unverified' if label not in views else
                'no_exact_hcg_node' if node_id is None else 'matched'),
                'node_type':graph.nodes[node_id]['node_type'] if node_id is not None else None}
        result['declarations'].append(entry)
    for typ,n in statements:
        entry=describe(source,n);entry['coverage_kind']=typ
        for label in ('source_view','supported_view'):
            node_id=anchor(n,*views[label]) if label in views else None
            entry[label]='view_unverified' if label not in views else 'no_exact_hcg_node' if node_id is None else 'matched'
        result['statements'].append(entry)
    return result


def summarize(files, view):
    decl=[d for f in files for d in f['declarations']]
    count=Counter(d[view]['status'] for d in decl)
    matched=sum(d[view]['status']=='matched' and d[view]['node_type']=='new_variable' for d in decl)
    statement={}
    for f in files:
        for s in f['statements']:statement.setdefault(s['coverage_kind'],Counter())[s[view]]+=1
    return {'declarations':len(decl),'new_variable_anchors':matched,
        'anchor_fraction_all_parsed_declarations':matched/len(decl) if decl else None,
        'declaration_status':dict(count),
        'ordinary_nodes_checked':sum(f.get('views',{}).get(view,{}).get('ordinary_nodes_checked',0) for f in files),
        'verified_files':sum(f.get('views',{}).get(view,{}).get('status')=='verified' for f in files),
        'unsupported_reasons':dict(Counter(f['views'][view]['reason'] for f in files if view in f['views'] and f['views'][view]['status']=='unsupported')),
        'statement_coverage':{k:dict(v) for k,v in statement.items()}}


def run(output):
    output=Path(output).resolve()
    if output.exists():raise FileExistsError(str(output))
    checked(DEFAULT_MANIFEST,read_json(DEFAULT_MANIFEST.with_name('manifest.seal.json'))['sha256'])
    manifest=read_json(DEFAULT_MANIFEST)
    paper_source=ROOT/'Test_code/author_graph_audit/audit_author_graphs.py'
    paper_ast=ast.parse(paper_source.read_text())
    paper=next(ast.literal_eval(n.value) for n in paper_ast.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PAPER' for t in n.targets))
    output.mkdir(parents=True);tasks=[]
    for ref in manifest['tasks']:
        tid=ref['task_id'];print(tid,flush=True)
        task=read_json(checked(ref['source_task_manifest'],ref['source_task_sha256']))
        rec=task['graphs']['HCG'];p=checked(rec['path'],rec['sha256']);graph=read_graph(p)
        sp=checked(ref['source_metadata_manifest'],ref['source_metadata_sha256'])
        sources,metadata,used,missing=read_sources(sp,graph)
        files=[audit_file(graph,n,code,metadata.get(n)) for n,code in sorted(sources.items())]
        category=ref['cohort'].replace('_author','')
        canonical=Counter((graph.nodes[s]['node_type'],d['edge_type'],graph.nodes[t]['node_type']) for s,t,d in graph.edges(data=True))
        ids=Counter(type(n).__name__ for n in graph.nodes)
        entry={'task_id':tid,'category':category,'task':ref['task'], 'graph':dict(rec),
          'source_manifest':{'path':str(sp),'sha256':sha256(sp)}, 'sources':used,'missing_sources':missing,
          'source_paths_unique':len({v['path'] for v in used.values()})==len(used),
          'nodes':len(graph),'edges':graph.number_of_edges(),'files':len({d['source_file'] for _,d in graph.nodes(data=True)}),
          'node_id_types':dict(ids),'node_types':dict(Counter(d['node_type'] for _,d in graph.nodes(data=True))),
          'edge_types':dict(Counter(d['edge_type'] for _,_,d in graph.edges(data=True))),
          'canonical_counts':[{'canonical':list(k),'edges':v} for k,v in sorted(canonical.items())],
          'node_attribute_keys':sorted({k for _,d in graph.nodes(data=True) for k in d}),
          'paper_table1':paper[category], 'paper_comparison_role':'full contract corpus only' if ref['task']=='contract' else 'buggy-file HCG subset; do not compare directly to full Table 1 counts',
          'source_view':summarize(files,'source_view'),'supported_view':summarize(files,'supported_view'),
          'parse_errors':[{'file':f['file'],'reason':f['parse_error']} for f in files if 'parse_error' in f]}
        entry['anchor_gate_passed']=not entry['parse_errors'] and not missing and entry['source_view']['anchor_fraction_all_parsed_declarations'] is not None and entry['source_view']['anchor_fraction_all_parsed_declarations']>=.9
        write_json(output/(tid+'.json'),{'summary':entry,'files':files})
        checked(p,rec['sha256'])
        for source in used.values():checked(source['path'],source['sha256'])
        tasks.append(entry);print(tid,entry['source_view']['new_variable_anchors'],entry['source_view']['declarations'],'gate',entry['anchor_gate_passed'],flush=True)
    legacy='pragma solidity ^0.4.24; contract C { struct A { uint x; } mapping(address=>A) Acc; function f() public { var acc = Acc[msg.sender]; } }'
    legacy_tree=parse(legacy)
    node=next(n for n in walk(legacy_tree.root_node) if n.type=='variable_declaration_statement')
    write_json(output/'legacy_var_ast.json',{'source':legacy,'ast':dump(node,legacy),'compiler_validation':False})
    other=[]
    for cat in sorted(set(paper)-{'reentrancy','access_control'}):
        record={'category':cat}
        for key,relative in [('author_hcg','data/upstream_mando_llm/graph_detection/'+cat+'_tree_sitter_cfg_cg_compressed_graphs.gpickle'),('author_cfg','data/upstream_mando_llm/node_detection/'+cat+'_tree_sitter_cfg_compressed_graphs.gpickle'),('sources','experiments/ge-sc-data/source_code/'+cat+'/source_files')]:
            paths=[ROOT/relative,ROOT.with_name('ge-sc-llm')/relative]
            record[key]=[{'path':str(p),'exists':p.exists()} for p in paths]
        other.append(record)
    result={'tasks':tasks,'other_categories_paths_only':other,'all_anchor_gates_passed':all(t['anchor_gate_passed'] for t in tasks),'view_policy':'SourceView is the requested primary measurement; SupportedSourceView reported separately without changing analyzer policy.', 'no_graph_mutation':True,'no_training':True}
    write_json(output/'summary.json',result);return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True)
    args=parser.parse_args();run(args.output)
