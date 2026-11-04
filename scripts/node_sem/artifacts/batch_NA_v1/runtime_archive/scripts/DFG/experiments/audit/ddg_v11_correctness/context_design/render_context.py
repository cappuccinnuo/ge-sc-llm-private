"""Render D2 reports from audited exact identities; no model or graph computation."""
import json, csv
from pathlib import Path
HERE=Path(__file__).resolve().parent
OUT=HERE/'results'
def read(p):return json.loads(p.read_text())
def write(name,text):
    with (HERE/name).open('x',encoding='utf8') as f:f.write(text)
def semantic(c):
    n=c['node_id'];fn=c['source']['function']['text']
    if c['cohort']=='reentrancy_author':
        if n==2706:
            return dict(state='READ userBalance_re_ent33[msg.sender] in external-call amount; WRITE same mapping element zero after call',
                controls='if !success then revert; possible callback before reset',
                missing='mapping-content identity, entry-state origin and external-call effect/order; not a backwards Def-Use edge',
                interpretation='B: call-before-reset pattern. C: negative author label while identical training snippets are positive; no formal vulnerability certification.')
        if n==2670:
            return dict(state='READ+WRITE counter_re_ent21 via +=1; earlier require(counter<=5), then send',
                controls='send failure -> revert, successful path increments later',
                missing='scalar STATE variable dependence, entry origin and call effect',
                interpretation='B: state guard/update sequencing absent. Frozen binding fallback is independent of D1 repairs.')
        if n==2675:
            return dict(state='READ balances_re_ent10[msg.sender] in guard; send parameter; READ+WRITE balance via -= parameter',
                controls='require balance >= parameter and require send; parameter data flow exists',
                missing='mapping contents and call-side-effect/order',
                interpretation='A: incoming parameter DDG exists yet FN persists. B: missing state is only one candidate explanation.')
        if n==5961:
            return dict(state='No state access in SafeMath.mul; local c derives from parameters a,b',
                controls='a==0 early return; require(c/a==b), then return c',
                missing='No state dependency required for this function',
                interpretation='A: scalar DDG positive case: fixed-weight message removal changes correct output to FP. State expansion is not needed here.')
        if n==6101:
            return dict(state='Selected _minimumTokensToVote is a local parameter, normalized before assignment to contract minimumTokensToVote later',
                controls='onlyOwner modifier; Token parameter is first recorded scalar fallback',
                missing='modifier/control and later contract assignment context; selected statement is not a state write',
                interpretation='A: no direct/two-hop DDG at selected node. B: full function matters; do not invent a state edge on the local assignment.')
        if n==4672:
            return dict(state='READ redeemableEther_re_ent18[msg.sender], copy to local transferValue, transfer, WRITE same element zero',
                controls='positive-balance require; transfer before reset',
                missing='entry state and access-order/call-effects; no prior concrete in-function balance definition',
                interpretation='A: E1 corrects but N/Z identical here. Cannot attribute correction to direct frozen DDG messages.')
    if c['file']=='mapping_write.sol':
        return dict(state='READ owner at require; withdraw transfers contract balance. Same contract set writes map[key]; map is uint256[] ARRAY, not mapping',
            controls='withdraw guarded by msg.sender==owner; set accepts user-controlled array length/index/value',
            missing='owner entry state, array length/location and cross-function arbitrary-write context',
            interpretation='A: SmartBugs annotation is line20 array write, not line27 guard. B: arbitrary slot reach requires bounds/layout/version analysis. Negative guard is not evidence of bad label.')
    if c['file']=='arbitrary_location_write_simple.sol':
        return dict(state='READ owner at Destroy guard; constructor writes owner; elsewhere bonusCodes.length-- and indexed writes',
            controls='Destroy guard then selfdestruct; PopBonusCode unsigned lower-bound check ineffective',
            missing='cross-function owner origin and array length/index context',
            interpretation='A: public annotation is line27 unsigned length check (adjacent decrement is line28), not line37 owner guard. B: local state Def-Use alone does not establish arbitrary-storage reach.')
    if c['cohort']=='access_control_author' and c['node_id']==1285:
        return dict(state='No state access: pure SafeMath.mul computes named local return c from a,b',
            controls='require(a==0 || c/a==b)',
            missing='No state variable dependence required; arithmetic scalar dataflow already present',
            interpretation='A: two incoming scalar DDG edges yet prediction wrong; this counterexample cannot be explained by missing state alone.')
    if 'txorigin' in fn:
        return dict(state='Injected function uses tx.origin and owner_txorigin parameter; parameter name owner does NOT make it contract state',
            controls='require(tx.origin==owner parameter); full function may transfer/call',
            missing='authority/provenance and guard/control, not necessarily a missing state-variable edge',
            interpretation='A: scalar DDG already reaches wrong node. B: adding state alone is not presumed to fix it. C: author/public interval context needs review.')
    return dict(state='Exact function/declarations below; no automatic state binding asserted',
        controls='See full function',missing='Unresolved program/label context',
        interpretation='C: independent semantic/annotation review needed')

def main():
    data=read(OUT/'D2_CASE_EVIDENCE.json');audit=read(OUT/'D2_INPUT_AUDIT.json')
    if audit['status']!='passed':raise ValueError('Unaccepted D2')
    cases=data['cases'];missing=[]
    lines=['# D2 difficult-function context review','','Codex, 2026-10-13. Original author labels; read-only; no training, relabeling, graph mutation or solc.',
        '', 'A = direct source/graph/archive evidence; B = supported semantic interpretation without independent execution; C = ambiguity requiring review; D = insufficient evidence.',
        '', 'Exact source SHA + saved AST identity + raw/compat token correspondence establish each location. Full functions and existing HCG IDs: results/D2_CASE_EVIDENCE.json. Named train-only duplicate sources: results/D2_TRAIN_DUPLICATES.json. Public CSV intervals are comparison evidence, not reconstructed author truth.',
        '', '## Main implications','',
        '- Same text/opposite labels does not automatically prove wrong labels.',
        '- map in mapping_write.sol is an ARRAY; names cannot select the abstraction.',
        '- owner_txorigin parameters already have scalar DDG; not all AC errors are missing state flow.',
        '- Owner guards and vulnerable array write sites are different statements.',
        '- Selection includes scalar-only success and wrong nodes already covered by DDG, not only pro-extension cases.',
        '', '## Cases']
    ambiguity=['# D2 label ambiguity and provenance','','Codex, 2026-10-13. No labels changed; no formal annotation certification.','','| Case | Author label | Public SHA match | Public location | Train matches / opposite | Review |','|---|---:|---|---|---|---|']
    for c in cases:
        s=semantic(c);missing.append(dict(case_id=c['case_id'],**s));src=c['source'];fun=src['function'];n=src['node'];p=c['predictions'];pr=c['public_annotation'];dup=c['train_duplicate_counts']
        lines.extend(['','### '+c['case_id'],'',
          '- Source SHA256: '+src['source_sha256'],
          '- Raw lines {}-{}, bytes [{}:{}); AST ID {}; function {} lines {}-{}.'.format(n['start_line'],n['end_line'],n['start_byte'],n['end_byte'],src['ast_id'],fun['identity'],fun['start_line'],fun['end_line']),
          '- Compressed endpoints: '+json.dumps(c['graph_stored_source_lines'])+'; author label '+str(c['author_label'])+'. Endpoints are not raw lines.',
          '- E0 best {} p={:.9f}; E1 best {} p={:.9f}.'.format(p['E0']['best'],p['E0']['best_positive_probability'],p['E1']['best'],p['E1']['best_positive_probability']),
          '- DDG in/out/two-layer affected: {}/{}/{}; {} exact train duplicates, {} opposite.'.format(c['coverage']['ddg_in'],c['coverage']['ddg_out'],c['coverage']['ddg_affected_within_two'],dup['total'],dup['opposite']),
          '- Frozen analysis: '+('; '.join(x['fallback_reason'] or 'analyzed' for x in c['frozen_function_analysis']) or 'no row')+'.',
          '- State reading (A syntax/B semantics): '+s['state'],'- Controls: '+s['controls'],
          '- Missing candidate semantics: '+s['missing'],'- Conclusion: '+s['interpretation'],
          '- Public annotation: '+pr['status']+'; raw records retained.','',chr(96)*3+'solidity',fun['text'],chr(96)*3])
        loc=('CSV '+str([(r['start'],r['end']) for r in pr['intervals_at_node']])) if 'intervals_at_node' in pr else 'SmartBugs '+str(pr.get('annotated_lines',[]))
        ambiguity.append('| {} | {} | {} | {} | {} / {} | C: no automatic correction |'.format(c['case_id'],c['author_label'],pr.get('source_sha_matches'),loc,dup['total'],dup['opposite']))
    lines.extend(['','## Limits','',
        'Public injection intervals are not certification of every statement as a vulnerability location. Author payload remains separate; matching intervals cannot establish unpublished conversion rules.',
        'No sample was compiled in D2. AST/source identity is not exploitability. Callback feasibility, gas, version and inherited effects need independent evidence.',
        'D1 repairs do not add state/mapping/modifier/interprocedural semantics. Numbers here are archived E0/E1 predictions, not predictions on v1.1 graphs.'])
    ambiguity.extend(['','## Follow-up evidence','',
        'Request author source SHA, annotation records, coordinate map and conversion script for disputed nodes. Preserve overlapping CSV records; overlap alone is not corruption.',
        'Inspect named train file+node matches and full functions. Equal text does not establish equal state, callers, modifiers, storage roots or ground-truth scope.',
        'SmartBugs examples demonstrate a vulnerable contract can contain a correctly labeled negative owner guard. Do not mark all statements positive.',
        'Model error/confidence never suffices to replace a label.'])
    rows=list(csv.DictReader((OUT/'D2_CASE_AUDIT.csv').open()))
    bycase={c['case_id']:c for c in cases}
    for row in rows:
        c=bycase[row['case_id']];sem=semantic(c)
        row.update(state_reads_writes=sem['state'],modifier_or_permission=sem['controls'],
            missing_dependencies=sem['missing'],label_source=json.dumps({
                'actual_label_version':'released_author_node_labels',
                'author_node_info_vulnerabilities':c['author_label_payload'],
                'public_annotation_comparison_only':c['public_annotation'],
                'frozen_author_graphs':{path:digest for path,digest in audit['input_sha256'].items()
                    if path.endswith(c['cohort'].replace('_author','')+'_tree_sitter_cfg_cg_compressed_graphs.gpickle')}
            },sort_keys=True),
            label_conclusion='C: no automatic correction',human_review_required=True,
            compilation_validation='not_executed',interpretation=sem['interpretation'])
    with (OUT/'D2_CASE_AUDIT.csv').open('w',encoding='utf8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    write('D2_CONTEXT_REVIEW.md','\n'.join(lines)+'\n');write('D2_LABEL_AMBIGUITY.md','\n'.join(ambiguity)+'\n')
    with (HERE/'D2_MISSING_DEPENDENCIES.json').open('x') as f:json.dump(dict(status='design_candidates_not_ground_truth',cases=missing),f,indent=2)
    print(json.dumps(dict(status='rendered',cases=len(cases))))
if __name__=='__main__':main()
