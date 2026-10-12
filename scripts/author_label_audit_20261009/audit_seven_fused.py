"""Codex 2026-10-09: read-only audit of seven official CFG+CG graph labels.
Distinguishes artifact replay from independently reconstructed public annotations.
No input graph, source, annotation or training code is modified.
"""
import ast, csv, importlib.util, json, re, sys
from collections import Counter, defaultdict
from pathlib import Path

sys.dont_write_bytecode = True
REPO = Path('/home/zhao/SmartContract/ge-sc-llm')
HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(REPO/'scripts/labeling_v2'), str(REPO/'scripts')]
from safe_graph import read_graph, sha256
from label_rules import parse_records, endpoints, unique_records, canonical_code, unquote, verify_source_pair
from line_mapping import build_line_map

def canonical(records):
    return sorted((rec['category'], tuple(sorted(set(rec['lines'])))) for rec in unique_records(records))

def lines(records, category=None):
    return {n for rec in records if category is None or rec['category']==category for n in rec['lines']}

def main():
    base=REPO/'data/upstream_mando_llm/graph_detection'
    categories=['access_control','arithmetic','denial_of_service','front_running','reentrancy','time_manipulation','unchecked_low_level_calls']
    sbpath=REPO/'data/smartbug-dataset/vulnerabilities.json'
    smartbugs=json.loads(sbpath.read_text())
    solidifi=REPO/'data/SolidiFI-benchmark/buggy_contracts'
    spec=importlib.util.spec_from_file_location('audit_preprocessor',str(REPO/'process_graphs/tree_sitter_codeviews/utils/preprocessor.py'))
    pre=importlib.util.module_from_spec(spec); spec.loader.exec_module(pre)
    inputs={str(sbpath):sha256(sbpath)}
    summary=[]; details={}
    for category in categories:
        print('AUDITING',category,flush=True)
        path=base/(category+'_tree_sitter_cfg_cg_compressed_graphs.gpickle')
        inputs[str(path)]=sha256(path)
        labelpath=base/(category+'_graph_labels.json'); inputs[str(labelpath)]=sha256(labelpath)
        contract_labels={x['contract_name']:int(x['targets']) for x in json.loads(labelpath.read_text())}
        g=read_graph(path); by_file=defaultdict(list); recovered=defaultdict(list)
        cached={}; spans={}; saved={}; counters=Counter(); cases=defaultdict(list)
        for n,d in g.nodes(data=True):
            raw=d.get('node_info_vulnerabilities')
            if isinstance(raw,str):
                if raw not in cached:cached[raw]=parse_records(raw)
                records=cached[raw]
            else:records=parse_records(raw)
            saved[n]=records
            by_file[d['source_file']].append(n); recovered[d['source_file']].extend(records)
            coord=d['node_source_code_lines']; coord=ast.literal_eval(coord) if isinstance(coord,str) else coord
            spans[n]=coord
            # Strict validation of all saved endpoint coordinates.
            endpoints(coord)
            counters['coordinate_spans_'+str(len(coord))]+=1
            for span in coord:counters['span_length_'+str(len(span))]+=1
        assert set(by_file)==set(contract_labels)
        recovered={f:unique_records(v) for f,v in recovered.items()}
        author_sets={f:lines(v) for f,v in recovered.items()}
        author_category_sets={f:lines(v,category) for f,v in recovered.items()}
        source_dir=REPO/'experiments/ge-sc-data/source_code'/category/'source_files'
        public={}; provenance={}; annotation_differences=[]; source_coordinate_checks=Counter()
        counterpart=defaultdict(list)
        for n,d in g.nodes(data=True):
            if d['node_type'] not in ('end_if','end_loop'):
                counterpart[(d['source_file'],min(endpoints(spans[n])))].append(n)
        per_file={}
        for f,ids in sorted(by_file.items()):
            fs=Counter(); recs=recovered[f]; src=source_dir/f
            source_text=None; line_map=None; pre_lines=None
            if src.exists():
                inputs[str(src)]=sha256(src)
                source_text=src.read_text(encoding='utf8')
                line_map=build_line_map(source_text)
                pre_text=pre.remove_comments('solidity',pre.remove_empty_lines(source_text))
                pre_lines=pre_text.split('\n') if pre_text else []
                assert len(pre_lines)==len(line_map)
            raw_records=[]; verified=False; origin={}
            if re.fullmatch(r'buggy_\d+\.sol',f):
                candidates=[p for p in sorted(solidifi.glob('*/'+f)) if src.exists() and sha256(p)==inputs[str(src)]]
                if len(candidates)==1:
                    ds=candidates[0]; log=ds.with_name('BugLog_'+f[len('buggy_'):-len('.sol')]+'.csv')
                    if log.is_file():
                        inputs[str(ds)]=sha256(ds);inputs[str(log)]=sha256(log)
                        with log.open(newline='') as handle:
                            csv_rows=list(csv.DictReader(handle))
                        raw_lines=set()
                        for row in csv_rows:
                            loc,length=int(row['loc']),int(row['length'])
                            assert loc>=1 and length>=1
                            raw_lines.update(range(loc,loc+length))
                        raw_records=[dict(category=category,lines=sorted(raw_lines))]
                        verified=True;origin=dict(dataset='SolidiFI',source=str(ds),buglog=str(log),rows=len(csv_rows),byte_identical=True)
                if not verified:origin=dict(error='No unique exact source match and BugLog',matching_sources=[str(x) for x in candidates])
            elif contract_labels[f]:
                entries=[rec for rec in smartbugs if Path(rec['name']).name==f and any(v['category']==category for v in rec['vulnerabilities'])]
                try:
                    if not entries or source_text is None:raise ValueError('Missing SmartBugs annotation or local source')
                    checks=[]
                    for entry in entries:
                        relevant=[v for v in entry['vulnerabilities'] if v['category']==category]
                        ds=sbpath.parent/entry['path']
                        checked=verify_source_pair(src,ds,lines(relevant))
                        inputs[str(ds)]=sha256(ds)
                        checks.append(dict(source=str(ds),**checked))
                        raw_records.extend(relevant)
                    raw_records=unique_records(raw_records);verified=True
                    origin=dict(dataset='SmartBugs',checks=checks)
                except (ValueError,FileNotFoundError) as exc:origin=dict(error=str(exc))
            else:
                # Contract negatives are supplied by the released author label JSON.
                verified=True;origin=dict(dataset='selected_clean',basis='author contract label',absence_independently_proven=False)
            if verified and line_map is not None:
                raw_lines=lines(raw_records)
                public[f]={i+1 for i,origins in enumerate(line_map) if set(origins)&raw_lines}
                origin['raw_annotation_lines']=len(raw_lines)
                origin['preprocessed_annotation_lines']=len(public[f])
                origin['raw_out_of_bounds']=sorted(n for n in raw_lines if n>len(source_text.splitlines()))
                origin['author_out_of_preprocessed_bounds']=sorted(n for n in author_sets[f] if n>len(line_map))
                if public[f]!=author_category_sets[f]:
                    annotation_differences.append(dict(file=f,dataset=origin['dataset'],
                        author_count=len(author_category_sets[f]),public_mapped_count=len(public[f]),
                        author_only=sorted(author_category_sets[f]-public[f]),
                        public_only=sorted(public[f]-author_category_sets[f])))
            provenance[f]=origin
            for n in ids:
                d=g.nodes[n]; covered=set(endpoints(spans[n])); truth=bool(saved[n])
                ep=bool(covered&author_sets[f]); cat_ep=bool(covered&author_category_sets[f])
                full={i for span in spans[n] for i in range(min(span),max(span)+1)}
                fs['nodes']+=1;fs['author_positive']+=truth
                fs['endpoint_positive']+=ep; fs['endpoint_binary_mismatches']+=ep!=truth
                fs['category_endpoint_binary_mismatches']+=cat_ep!=truth
                fs['full_span_binary_mismatches']+=bool(full&author_sets[f])!=truth
                fs['whole_file_record_mismatches']+=canonical(recs if ep else [])!=canonical(saved[n])
                hit_records=[v for v in recs if covered&set(v['lines'])]
                fs['only_hit_record_mismatches']+=canonical(hit_records)!=canonical(saved[n])
                if ep!=truth and len(cases['endpoint_binary'])<10:cases['endpoint_binary'].append(dict(id=n,file=f))
                if cat_ep!=truth and len(cases['category_filtered'])<10:
                    cases['category_filtered'].append(dict(id=n,file=f,type=d['node_type'],
                        endpoints=sorted(covered),stored_records=saved[n]))
                if f in public:
                    pred=bool(covered&public[f]);fs['public_compared_nodes']+=1
                    fs['public_endpoint_positive']+=pred;fs['public_endpoint_mismatches']+=pred!=truth
                    if pred!=truth:
                        fs['public_false_positive' if pred else 'public_false_negative']+=1
                        if len(cases['public'])<20:
                            cases['public'].append(dict(id=n,file=f,type=d['node_type'],endpoints=sorted(covered),author=int(truth),public=int(pred)))
                if d['node_type'] in ('end_if','end_loop'):
                    fs['synthetic_nodes']+=1
                    label=unquote(d.get('label',''));match=re.match(r'(\d+)_ end_(if|loop)',label)
                    marker=int(match.group(1)) if match else None
                    fs['synthetic_single_marker_mismatches']+=not (marker is not None and spans[n]==[[marker]])
                    peers=counterpart[(f,marker+1)] if marker is not None else []
                    # An end_if can retain an else-if snippet while its marker belongs to the root if.
                    child_code=canonical_code(d.get('code','')).strip()
                    matched=[p for p in peers if child_code in canonical_code(g.nodes[p].get('code',''))
                        and (g.nodes[p]['node_type']=='if' if d['node_type']=='end_if'
                             else g.nodes[p]['node_type'] in ('for','while','do'))]
                    fs['synthetic_without_start_plus_one_counterpart']+=not bool(matched)
                    if not matched and len(cases['synthetic'])<10:cases['synthetic'].append(dict(file=f,id=n,marker=marker,peers=peers))
                if pre_lines is not None and d['node_type'] not in ('end_if','end_loop'):
                    source_coordinate_checks['compared_nodes']+=1
                    a,z=min(covered),max(covered)
                    code=canonical_code(d.get('code','')).strip()
                    fragment='\n'.join(pre_lines[a-1:z]).strip()
                    # Comparison is a diagnostic, not a source identity assertion.
                    exact=code==fragment
                    source_coordinate_checks['exact_code_span_matches']+=exact
                    if not exact and len(cases['code_span'])<5:
                        cases['code_span'].append(dict(file=f,id=n,type=d['node_type'],start=a,end=z,code=code[:120],source=fragment[:120]))
            per_file[f]=dict(fs);counters.update(fs)
        record_categories=Counter(v['category'] for vlist in recovered.values() for v in vlist)
        solidifi_records=Counter(len(v) for f,v in recovered.items() if re.fullmatch(r'buggy_\d+\.sol',f))
        row=dict(category=category,nodes=len(g),edges=g.number_of_edges(),files=len(by_file),
            **{k:counters[k] for k in ['author_positive','endpoint_positive','endpoint_binary_mismatches','category_endpoint_binary_mismatches','whole_file_record_mismatches','only_hit_record_mismatches','full_span_binary_mismatches','public_compared_nodes','public_endpoint_positive','public_endpoint_mismatches','public_false_positive','public_false_negative','synthetic_nodes','synthetic_single_marker_mismatches','synthetic_without_start_plus_one_counterpart']},
            public_annotation_different_files=len(annotation_differences),
            public_unverified_files=sum('error' in x for x in provenance.values()))
        summary.append(row)
        details[category]=dict(summary=row,coordinate_counts=dict(counters),
            recovered_record_categories=dict(record_categories),recovered_solidifi_records_per_file=dict(solidifi_records),
            source_coordinate_checks=dict(source_coordinate_checks),examples=dict(cases),
            public_annotation_differences=annotation_differences,public_provenance=provenance,per_file=per_file)
        print(json.dumps(row),flush=True)
    assert all(sha256(Path(p))==h for p,h in inputs.items())
    report=dict(audit_date='2026-10-09',reviewer='Codex',
        scope='Seven released tree-sitter CFG+CG graphs only',summary=summary,details=details,input_sha256=inputs,
        inputs_unchanged=True,
        limitations=['Author records are recovered from graph node metadata; they are not independent original ground truth.',
                     'Records that never occur on saved nodes cannot be recovered.',
                     'Endpoint replay demonstrates compatibility of artifacts, not authors unpublished conversion algorithm.',
                     'Public comparisons use current local public dataset snapshots and local source preprocessing; author original source snapshot is not available.',
                     'Synthetic coordinates are observed implementation markers, not necessarily meaningful preceding source lines.',
                     'False positive/negative fields describe differences against author saved labels, not independently verified vulnerability truth.'])
    (HERE/'audit.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    with (HERE/'summary.csv').open('w',newline='',encoding='utf8') as f:
        writer=csv.DictWriter(f,fieldnames=list(summary[0]));writer.writeheader();writer.writerows(summary)
    print('REPORT',str(HERE/'audit.json'),flush=True)

if __name__=='__main__':main()
