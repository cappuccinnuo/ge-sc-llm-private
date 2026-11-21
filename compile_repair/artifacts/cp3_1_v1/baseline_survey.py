"""Audit each saved CP3 result before reclassification. Only reads corpus and artifacts."""
from batch import *
from compile_repair.evaluation.report import classify_record, primary_causes, aggregate_failures
from compile_repair.toolchain.project import standard_json_input

units, refs = members()
wrappers, primary, any_counts = {}, [], []
old = json.loads(committed(ART/'cp3_paths_v1/failure_summary.json'))
verified_sources = set()
projects, needs_ast, seen_asts = {}, {}, {}
unsupported = []
original_categories = {}
LOCAL.mkdir(parents=True, exist_ok=True)
saved_count = 0
with (LOCAL/'old_classifications.jsonl').open('x') as log:
    for item in units:
        uid = item['unit_id']
        raw = verified(item['path'], item['entry_sha256'])
        fmt = standard_json_input(raw)
        if fmt:
            wrappers[uid] = dict(fmt, corpus=item['corpus'], old_categories=[])
        if uid not in refs:
            assert not item['language_evidence']['is_solidity']
            continue
        ref = refs[uid]
        data = json.loads(verified(ref['result_path'],ref['result_sha256']))
        assert data['unit_id'] == uid and item['entry_sha256'] == data['inputs'][0]['sha256']
        for src in data['inputs']:
            identity = (src['path'], src['sha256'])
            if identity not in verified_sources:
                verified(*identity)
                verified_sources.add(identity)
        saved_count += 1
        failures = classify_record(data)
        causes = primary_causes(data, failures)
        categories = sorted({f['category'] for f in failures})
        if 'unsupported_expression' in categories:
            unsupported.append(uid)
        if fmt:
            wrappers[uid]['old_categories'] = categories
        row = dict(unit_id=uid, status=data['status'], corpus=item['corpus'], entry_sha256=item['entry_sha256'])
        if item['corpus'] == 'MANDO' and data['status'] != 'success':
            assert causes['categories'] == ['slither_incomplete'],uid
        log.write(json.dumps(dict(row, any_categories=categories,primary=causes,original_ref=ref['result_sha256']))+'\n')
        primary.append(dict(row, failures=[{'category':x} for x in causes['categories']]))
        any_counts.append(dict(row, failures=[{'category':x} for x in categories]))
        if item['project_root']:
            # CP3 D3(b) stores exact definition counts per AST and its SHA.
            members_by_relative = {str(Path(s['path']).relative_to(item['project_root'])):s['sha256'] for s in data['inputs']}
            evidence = []
            for a in data['attempts']:
                coverage = (a.get('slither') or {}).get('contract_coverage') or {}
                if not coverage.get('asts'):
                    continue
                evidence.append(coverage['expected'])
                for ast in coverage['asts']:
                    rel = str(Path(ast['path']).relative_to(a['solc']['cwd']))
                    digest = members_by_relative[rel]
                    counts = ast['contracts']
                    if digest in seen_asts:
                        assert counts == seen_asts[digest]['definitions'],(uid,rel)
                    else:
                        seen_asts[digest] = dict(definitions=counts, unit_id=uid, ast_sha256=ast['ast_sha256'], version=a['version'])
            if evidence:
                duplicates = sorted({k for names in evidence for k,v in names.items() if v>1})
                projects[uid] = dict(duplicate_names=duplicates,status=data['status'],method='saved_unit_ast_counts')
            else:
                needs_ast[uid] = dict(inputs=data['inputs'],status=data['status'],reason=data['reason'],origin=item['project_root'],entry=item['path'])
categories=[r['category'] for r in old['category_unit_counts']]
rows=aggregate_failures(any_counts,categories)
assert {r['category']:r['units'] for r in rows['category_unit_counts']} == {r['category']:r['units'] for r in old['category_unit_counts']}
assert saved_count==31071 and sum(rows['remaining_failures'].values())==9911
save('baseline_classification.json',dict(verified_result_count=saved_count,verified_input_pairs=len(verified_sources), inventory_count=len(units),any_candidate=rows,primary=aggregate_failures(primary,categories+['version_dependent']),subset_log=str(LOCAL/'old_classifications.jsonl'),subset_log_sha256=sha((LOCAL/'old_classifications.jsonl').read_bytes()),mando_primary_check='slither_incomplete only for three remaining'))
save('wrapper_scan.json',dict(total_scanned=len(units),hits=wrappers,by_corpus={c:sum(x['corpus']==c for x in wrappers.values()) for c in sorted({i['corpus'] for i in units})}))
save('unsupported_units.json',unsupported)
for name,payload in [('direct_ast',projects),('need_ast',needs_ast),('source_ast',seen_asts)]:
    with (LOCAL/(name+'.json')).open('x') as fp:json.dump(payload,fp)
print('saved_results',saved_count,'direct_ast',len(projects),'needs_ast',len(needs_ast),'distinct_ast',len(seen_asts),'wrappers',len(wrappers))
