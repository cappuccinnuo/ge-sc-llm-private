"""Final independent D2 identity/evidence validation; read-only original inputs."""
import csv, hashlib, json, os, subprocess, sys, time
from pathlib import Path
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[5]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text())
def main():
    audit=read(HERE/'results/D2_INPUT_AUDIT.json')
    changed=[p for p,s in audit['input_sha256'].items() if sha(p)!=s]
    if changed:raise ValueError('Input drift: '+str(changed))
    cases=read(HERE/'results/D2_CASE_EVIDENCE.json')['cases']
    duplicates=read(HERE/'results/D2_TRAIN_DUPLICATES.json')
    oracle=read(HERE/'D3_ORACLE_CANDIDATES.json')['oracles']
    count=0
    for c in cases:
        s=c['source'];raw=Path(s['source_path']).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==s['source_sha256']
        for item in (s['node'],s['function']):
            assert raw[item['start_byte']:item['end_byte']].decode('utf8')==item['text']
            count+=1
        assert c['public_annotation']['source_sha_matches']
        assert c['predictions']['E0']['target']==c['predictions']['E1']['target']==c['author_label']
    for d in duplicates:
        raw=Path(d['source_path']).read_bytes()
        assert hashlib.sha256(raw).hexdigest()==d['source_sha256']
        if d['mapping_status']=='A_exact':
            s=d['exact_context']
            for item in (s['node'],s['function']):
                assert raw[item['start_byte']:item['end_byte']].decode('utf8')==item['text']
                count+=1
        else:
            assert d['mapping_reason'].startswith('MappingUnavailable: Multiple Solidity pragmas')
    rows=list(csv.DictReader((HERE/'results/D2_CASE_AUDIT.csv').open()))
    assert len(rows)==len(cases)==12
    required={'state_reads_writes','modifier_or_permission','missing_dependencies','label_source',
              'human_review_required','compilation_validation'}
    assert required<=set(rows[0])
    assert sum(o['origin']=='exact_corpus_source' for o in oracle)==9
    assert sum(o['origin']=='synthetic_specification' for o in oracle)==5
    assert all(o['independent_validation']=='pending' and not o['compiled'] for o in oracle)
    cmd=[sys.executable,'-B','-m','pytest','-q','-p','no:cacheprovider',
      'scripts/DFG/experiments/audit/ddg_v11_correctness/context_design/test_context_audit.py']
    start=time.time();r=subprocess.run(cmd,cwd=str(REPO),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,universal_newlines=True)
    (HERE/'D2_TEST_RESULTS.log').write_text(r.stdout)
    if r.returncode:raise RuntimeError(r.stdout)
    result=dict(status='passed',cases=12,training_duplicates=len(duplicates),
        exact_context_duplicates=sum(d['mapping_status']=='A_exact' for d in duplicates),
        unresolved_duplicate_contexts=sum(d['mapping_status']!='A_exact' for d in duplicates),
        exact_byte_span_checks=count,original_input_hashes_checked=len(audit['input_sha256']),
        original_inputs_unchanged=True,no_training=True,no_label_or_graph_changes=True,
        source_correspondence='v1.1 Projector only; metrics/labels/DDG coverage from frozen E0/E1',
        source_correspondence_code_sha256={str(p.relative_to(REPO)):sha(p) for p in [
          REPO/'scripts/DFG/frontend.py',REPO/'scripts/DFG/projection.py']},
        pytest=dict(command=cmd,returncode=r.returncode,elapsed_seconds=time.time()-start,stdout=r.stdout),
        oracles=dict(actual_source_candidates=9,synthetic_specifications=5,independently_approved=0,compiler_validated=0))
    with (HERE/'D2_FINAL_VALIDATION.json').open('x') as f:json.dump(result,f,indent=2)
    print(json.dumps({k:v for k,v in result.items() if k not in ('source_correspondence_code_sha256','pytest')}))
if __name__=='__main__':main()
