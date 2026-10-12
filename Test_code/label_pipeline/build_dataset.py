"""Independent public annotations -> node labels; Codex, 2026-10-10.

Only files below the requested new output directory are written.
Author node annotations are used exclusively AFTER new labels have been computed,
as a comparator. No graph generation, tokenizer or training code is changed.
"""
import argparse
import copy
import hashlib
import json
import pickle
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path[:0] = [str(HERE), str(REPO/'scripts/labeling_v2')]
import networkx as nx
from safe_graph import read_graph, write_graph, sha256
from label_rules import parse_records, canonical_code, align_graphs
from coordinates import coordinates_for_node, graph_endpoints, preprocess_with_map
from raw_annotations import load_annotations

CATEGORIES = ['access_control','arithmetic','denial_of_service','front_running',
              'reentrancy','time_manipulation','unchecked_low_level_calls']

def dump(path, value):
    with path.open('x',encoding='utf8') as f:
        json.dump(value,f,indent=2,ensure_ascii=False); f.write('\n')

def structural_digest(graph):
    h=hashlib.sha256()
    h.update(pickle.dumps(graph.graph,protocol=4))
    for n,d in graph.nodes(data=True):
        h.update(pickle.dumps((n,{k:v for k,v in d.items() if k!='node_info_vulnerabilities'}),protocol=4))
    for edge in graph.edges(keys=True,data=True):h.update(pickle.dumps(edge,protocol=4))
    return h.hexdigest()

def graph_stats(g):
    return dict(nodes=len(g),edges=g.number_of_edges(),
        source_files=len({d['source_file'] for _,d in g.nodes(data=True)}),
        positive_nodes=sum(bool(parse_records(d.get('node_info_vulnerabilities'))) for _,d in g.nodes(data=True)),
        edge_types=dict(Counter(d.get('edge_type') for _,_,d in g.edges(data=True))),
        token_nodes=sum('token' in d for _,d in g.nodes(data=True)),
        token_widths=sorted({len(d['token']) for _,d in g.nodes(data=True) if 'token' in d}))

def projection_tokens(text):
    # Both graph serialization and original source represent escape sequences
    # differently. Decode the same displayed escapes for this comparison only.
    text=text.replace(r'\n','\n').replace(r'\"','"')
    text=re.sub(r"\\x([0-9a-fA-F]{2})",lambda m:chr(int(m.group(1),16)),text)
    return re.findall(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[A-Za-z_$][A-Za-z_0-9$]*|[0-9]+|[^\s]',text)

def token_subsequence(needle,haystack):
    return bool(needle) and any(haystack[i:i+len(needle)]==needle for i in range(len(haystack)-len(needle)+1))

def project_annotations(records,line_map):
    mapped=[];evidence=[]
    for i,rec in enumerate(records):
        raw=set(rec['lines'])
        pre=[p+1 for p,origins in enumerate(line_map) if raw.intersection(origins)]
        mapped.append(dict(category=rec['category'],lines=pre))
        represented={n for origins in line_map for n in origins}
        evidence.append(dict(record_index=i,raw_lines=len(raw),mapped_lines=len(pre),
                             raw_lines_without_surviving_code=sorted(raw-represented)))
    return mapped,evidence

def node_targets(g,annotations,sources,category,policy):
    """Independent builder: never inspect the input's existing vulnerability field."""
    projected={};maps={};texts={};projection={};source_hashes={}
    for name,path in sources.items():
        if any(rec['category']!=category for rec in annotations[name]):
            raise ValueError('Foreign category in annotation input: '+name)
        text=path.read_text(encoding='utf8')
        prepared,mapping=preprocess_with_map(text)
        maps[name]=mapping;texts[name]=prepared.split('\n') if prepared else []
        projected[name],projection[name]=project_annotations(annotations[name],mapping)
        source_hashes[name]=sha256(path)
    target={};evidence=[];compatibility=Counter();diagnostics=[]
    for n,d in g.nodes(data=True):
        name=d['source_file']
        cover=coordinates_for_node(d,policy)
        synthetic=d['node_type'] in ('end_if','end_loop')
        if not cover:raise ValueError('Missing coordinates for node '+str(n))
        if any((x<1 and not (synthetic and policy=='author-endpoints' and x==0)) or x>len(maps[name]) for x in cover):
            raise ValueError('Node coordinates out of canonical-source bounds: '+name+' '+str(n)+' '+str(cover))
        marker=graph_endpoints(d)
        if not synthetic:
            code=canonical_code(d.get('code',''))
            fragment='\n'.join(texts[name][min(marker)-1:max(marker)])
            # Source projection verification tolerates whitespace and a changed pragma only.
            # This verifies each snippet at its saved location; it does not resolve call semantics.
            normalized_code=projection_tokens(code)
            normalized_fragment=projection_tokens(fragment)
            if d['node_type']=='external_function' and code.startswith('function_call:'):
                compatibility['generated_external_nodes']+=1
            elif token_subsequence(normalized_code,normalized_fragment):
                compatibility['source_projection_matches']+=1
            elif normalized_code[:2]==['pragma','solidity'] and normalized_fragment[:2]==['pragma','solidity'] and normalized_code[-1:]==[';'] and normalized_fragment[-1:]==[';']:
                compatibility['pragma_projection_exceptions']+=1
            else:
                compatibility['source_projection_mismatches']+=1
                diagnostics.append(dict(node_id=n,file=name,node_type=d['node_type'],
                    label=d.get('label'),code=code,canonical_source_fragment=fragment))
        else:
            compatibility['synthetic_legacy_markers' if policy=='author-endpoints' else 'synthetic_source_spans']+=1
        matched=[i for i,rec in enumerate(projected[name]) if set(cover).intersection(rec['lines'])]
        # Keep authors' file-record attachment layout, but only target-category public records.
        # Exact matched IDs are explicitly kept in the sidecar.
        target[n]=copy.deepcopy(projected[name]) if matched else None
        evidence.append(dict(node_id=n,source_file=name,node_type=d['node_type'],
            coordinate_policy=policy,used_preprocessed_coordinates=cover,
            original_lines_at_coordinates=sorted({v for p in cover if p>0 for v in maps[name][p-1]}),
            synthetic_marker_is_not_executable_source=synthetic and policy=='author-endpoints',
            matched_record_indices=matched,label=int(bool(matched)),canonical_source_sha256=source_hashes[name]))
    return target,projected,evidence,dict(projection=projection,source_projection=dict(compatibility),
                                        source_projection_issues=diagnostics)

def validate_labels(entries,filenames):
    if not isinstance(entries,list) or any(not isinstance(x,dict) for x in entries):
        raise ValueError('Contract labels must be a list of objects')
    names=[x['contract_name'] for x in entries]
    if len(names)!=len(set(names)) or set(names)!=set(filenames):
        raise ValueError('Contract label coverage differs from graph source files')
    if any(type(x['targets']) is not int or x['targets'] not in (0,1) for x in entries):
        raise ValueError('Contract labels must be integer 0/1')
    return {x['contract_name']:x['targets'] for x in entries}

def verify_training_consumer(g):
    sys.path.insert(0,str(REPO))
    from sco_models.graph_utils import get_node_label
    actual,_,_=get_node_label(g)
    expected=[int(bool(parse_records(d.get('node_info_vulnerabilities')))) for _,d in g.nodes(data=True)]
    if actual!=expected:raise AssertionError('Existing training consumer reads different labels')

def build_one(category,out,graph_path=None,label_path=None,policy='author-endpoints',emit=True):
    official=REPO/'data/upstream_mando_llm/graph_detection'
    reference_path=official/(category+'_tree_sitter_cfg_cg_compressed_graphs.gpickle')
    graph_path=graph_path or reference_path
    label_path=label_path or official/(category+'_graph_labels.json')
    g=read_graph(graph_path)
    filenames=sorted({d['source_file'] for _,d in g.nodes(data=True)})
    if any(Path(f).name!=f for f in filenames):raise ValueError('source_file must be a basename')
    if any(g.nodes[s]['source_file']!=g.nodes[t]['source_file'] for s,t in g.edges()):
        raise ValueError('Unexpected inter-file edges')
    contract_entries=json.loads(label_path.read_text())
    labels=validate_labels(contract_entries,filenames)
    frozen=structural_digest(g)
    annotations,sources,provenance,input_hashes=load_annotations(REPO,category,filenames,labels)
    input_hashes.update({str(graph_path):sha256(graph_path),str(label_path):sha256(label_path)})
    target,projected,evidence,coordinate_checks=node_targets(g,annotations,sources,category,policy)
    # Existing saved labels affect neither the above coordinates nor annotations.
    # The public source snapshot is canonical. Projection failures block export.
    result=g.copy()
    for n in result:result.nodes[n]['node_info_vulnerabilities']=target[n]
    if structural_digest(result)!=frozen:raise AssertionError('Non-label graph content changed')
    positive_files={d['source_file'] for _,d in result.nodes(data=True) if d['node_info_vulnerabilities']}
    known_buggy={f for f,y in labels.items() if y}
    if positive_files-known_buggy:raise ValueError('Annotated positives in an explicitly clean contract')
    zero_hit_buggy=sorted(known_buggy-positive_files)
    # Retain positive contracts even if no node label was hit; never infer contract targets from nodes.
    keep=[n for n,d in result.nodes(data=True) if d['source_file'] in known_buggy]
    raw_line=result.subgraph(keep).copy()
    old_ids=list(raw_line.nodes())
    line=nx.relabel_nodes(raw_line,{n:i for i,n in enumerate(old_ids)},copy=True)
    reference=read_graph(reference_path)
    input_hashes[str(reference_path)]=sha256(reference_path)
    try:
        mapping=align_graphs(g,reference)
        alignment=dict(exact_node_identity=True,untyped_edges_equal=True)
    except ValueError as exc:
        # Local graph topology must be aligned before attributing label differences.
        mapping=None; alignment=dict(exact_node_identity=False,error=str(exc))
    changed=[];counts=Counter()
    if mapping is not None:
        for n,ref in mapping.items():
            before=bool(parse_records(reference.nodes[ref].get('node_info_vulnerabilities')))
            after=bool(target[n])
            if before!=after:
                counts['author_positive_to_public_negative' if before else 'author_negative_to_public_positive']+=1
                changed.append(dict(node_id=n,author_node_id=ref,source_file=g.nodes[n]['source_file'],
                    node_type=g.nodes[n]['node_type'],author=int(before),public=int(after),
                    used_coordinates=coordinates_for_node(g.nodes[n],policy)))
    for path in HERE.glob('*.py'):input_hashes[str(path)]=sha256(path)
    for path in [REPO/'scripts/labeling_v2/safe_graph.py',REPO/'scripts/labeling_v2/label_rules.py']:
        input_hashes[str(path)]=sha256(path)
    assert all(sha256(Path(p))==h for p,h in input_hashes.items()), 'Input changed during build'
    ready=(coordinate_checks['source_projection']['source_projection_mismatches']
           if 'source_projection_mismatches' in coordinate_checks['source_projection'] else 0)==0
    out.mkdir(parents=True,exist_ok=False)
    manifest=dict(created_utc=datetime.now(timezone.utc).isoformat(),user_date='2026-10-10',modified_by_ai='Codex',
        category=category,coordinate_policy=policy,graph_input=str(graph_path),
        canonical_public_annotations=True,author_node_labels_used_for_generation=False,
        graph_was_regenerated=False,token_features_regenerated=False,
        synthetic_policy='Retain historical zero-based root marker for author-endpoints; do not call it a true previous statement.',
        record_attachment='Any endpoint hit -> all target-category records for that file; matched indices in node evidence.',
        contract_membership='Independent input graph_labels.json; node labels never redefine contract targets.',
        annotation_source_policy='Public interval annotations are benchmark ground truth, not independently proven minimal vulnerable statements.',
        stats=dict(author=graph_stats(reference),input=graph_stats(g),contractlevel=graph_stats(result),linelevel=graph_stats(line)),
        source_checks=provenance,coordinate_checks=coordinate_checks,
        alignment_to_author=alignment,binary_differences_vs_author=len(changed) if mapping is not None else None,
        change_directions=dict(counts),positive_contracts_with_no_positive_nodes=zero_hit_buggy,
        input_sha256=input_hashes,inputs_unchanged=True,non_label_attributes_and_edges_preserved=True,
        export_ready=ready,exported=False,output_sha256={})
    dump(out/'annotations_original.json',annotations)
    dump(out/'annotations_preprocessed.json',projected)
    dump(out/'label_differences.json',changed)
    dump(out/'line_node_ids.json',[dict(line_node_id=i,input_node_id=n) for i,n in enumerate(old_ids)])
    with (out/'node_label_evidence.jsonl').open('x',encoding='utf8') as f:
        for row in evidence:f.write(json.dumps(row,ensure_ascii=False)+'\n')
    if emit and ready:
        verify_training_consumer(line)
        full_path,line_path=out/'contractlevel.gpickle',out/'linelevel.gpickle'
        write_graph(result,full_path);write_graph(line,line_path)
        for expected,path in [(result,full_path),(line,line_path)]:
            reloaded=read_graph(path)
            assert structural_digest(reloaded)==structural_digest(expected)
            assert [parse_records(d.get('node_info_vulnerabilities')) for _,d in reloaded.nodes(data=True)]==[
                parse_records(d.get('node_info_vulnerabilities')) for _,d in expected.nodes(data=True)]
        (out/'graph_labels.json').write_bytes(label_path.read_bytes())
        manifest['exported']=True;manifest['training_label_consumer_verified']=True
    manifest['output_sha256']={p.name:sha256(p) for p in sorted(out.iterdir()) if p.is_file()}
    dump(out/'manifest.json',manifest)
    row=dict(category=category,policy=policy,nodes=len(g),author_positive=graph_stats(reference)['positive_nodes'],
        public_positive=len([n for n in target if target[n]]),different_nodes=manifest['binary_differences_vs_author'],
        zero_hit_positive_contracts=len(zero_hit_buggy),source_projection_issues=len(coordinate_checks['source_projection_issues']),
        exported=manifest['exported'],output=str(out))
    print(json.dumps(row),flush=True)
    return row

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--categories',nargs='+',default=['all'],choices=['all']+CATEGORIES)
    p.add_argument('--graph',type=Path,help='Alternative local input for one category; labels are rebuilt from public annotations')
    p.add_argument('--contract-labels',type=Path)
    p.add_argument('--policy',choices=['author-endpoints','source-range'],default='author-endpoints')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--audit-only',action='store_true')
    args=p.parse_args()
    cats=CATEGORIES if args.categories==['all'] else args.categories
    if 'all' in cats or len(set(cats))!=len(cats):p.error('Choose all or unique category names')
    if (args.graph or args.contract_labels) and len(cats)!=1:p.error('Custom inputs require one category')
    if args.output.exists():p.error('Output exists; choose a fresh output directory')
    args.output.mkdir(parents=True)
    rows=[]
    for cat in cats:
        print('BUILD',cat,flush=True)
        rows.append(build_one(cat,args.output/cat,args.graph,args.contract_labels,args.policy,not args.audit_only))
    dump(args.output/'summary.json',rows)
    if any(row['source_projection_issues'] for row in rows):
        raise SystemExit('Some exports blocked by graph/source projection mismatches; see manifests')

if __name__=='__main__':main()
