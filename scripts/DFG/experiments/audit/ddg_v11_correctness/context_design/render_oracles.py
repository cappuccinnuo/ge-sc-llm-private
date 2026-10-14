"""Render candidate oracle specification; does not implement/analyze state dependencies."""
import json
from pathlib import Path
H=Path(__file__).resolve().parent
def main():
    cases=json.loads((H/'results/D2_CASE_EVIDENCE.json').read_text())['cases']
    ctx=json.loads((H/'results/D3_SOURCE_CONTEXTS.json').read_text())['contexts']
    bynode={(c['cohort'],c['node_id']):c['source'] for c in cases}
    def fn(cohort,file,name):
        found=[c['source'] for c in ctx if c['cohort']==cohort and c['file']==file and c['source']['function']['name']==name]
        assert len(found)==1
        return found[0]
    specs=[
      ('O1','Reentrancy balance/read/call/reset',bynode['reentrancy_author',2706],
       'Read userBalance_re_ent33[msg.sender] before external call; write same element after successful call.',
       'No concrete in-function state definition reaches the earlier read: its origin is ENTRY_UNKNOWN. Do not create reset -> earlier call/read. Call invalidates pre-call state assumptions.',
       'msg.sender stable in one frame, but unknown callback may change state; binding fallback remains explicit.',
       'Mapping/call state outside scalar scope. Existing statement nodes can anchor accesses; entry unknown has no concrete definition node. Access order is metadata, not state DEF_USE.'),
      ('O2','Same mapping key compound update',bynode['reentrancy_author',2675],
       'READ balances_re_ent10[msg.sender] in guard and compound -=; WRITE same element in compound statement; read _weiToWithdraw parameter separately.',
       'Keep parameter -> guard/send/update scalar facts. No backward later-write -> earlier guard. A compound write cannot define its own preceding RHS read.',
       'Send may hand control away; state origin after call requires call policy. Same spelling of mapping root alone does not prove binding.',
       'State contents absent although scalar parameter dependencies exist. Compound RHS and write may project to one node; retain facts even when self edge is filtered.'),
      ('O3','Different symbolic keys / may alias',fn('reentrancy_author','buggy_27.sol','transferFrom'),
       'READ/WRITE _balances[from], _balances[DanPanAddress], _balances[to]; nested _allowed[from][msg.sender].',
       'No MUST alias or NO_ALIAS from different variable names. Earlier from write may reach later to read only under a sound may-alias summary; do not assert a must fact.',
       'from==to or to==DanPanAddress is possible absent proof. Internal SafeMath/fee calls require summaries; first subset must fall back state analysis here.',
       'Useful negative support boundary: these real statements are projected but complete key/call semantics are not implemented.'),
      ('O4','Owner entry-state read',bynode['access_control_author',12963],
       'READ owner in require; withdraw subsequently transfers balance. map in same contract is an ARRAY.',
       'Owner is ENTRY_UNKNOWN here. No constructor/local owner definition may be fabricated in withdraw. require -> transfer is a control constraint, not owner DEF_USE.',
       'Cross-function array arbitrary-write effects require bounds/layout/version analysis; no exact EVM slot claim.',
       'Guard HCG node 12963 exists; no same-function concrete owner-def node. New state module should report the missing origin instead of promising an edge.'),
      ('O5','Modifier control of state update',fn('access_control_author','buggy_18.sol','transferOwnership'),
       'Modifier onlyOwner READ owner, compare msg.sender; function WRITE newOwner from _newOwner.',
       'Parameter -> write is scalar/value flow. Owner predicate -> newOwner write is CONTROL_DEPENDENCE, not state DEF_USE. Entry owner not locally defined.',
       'Full source modifier text retained separately. Unique invocation/binding/underscore and path semantics must be established before expansion.',
       'Original function/statement nodes exist (1343,1344). Do not invent modifier node IDs; actual modifier HCG mapping remains a separate exact-projection requirement.'),
      ('O6','Branch-dependent state write',fn('access_control_author','mapping_write.sol','set'),
       'READ map.length at if; branch WRITE map.length=key+1; unconditional WRITE map[key]=value.',
       'Conditional length write is not a reaching definition for the earlier condition. Branch union must retain ENTRY_UNKNOWN on bypass. map.length and map[key] are distinct locations.',
       'Dynamic array bounds/overflow and key identity remain version-sensitive; branch condition is not a data dependency from length write to element write.',
       'Existing condition 12956, length write 12958 and element write12959 can anchor events. Existing graph already conveys control; first mapping-only subset does not claim array support.'),
      ('O7','Scalar-only positive control',bynode['reentrancy_author',5961],
       'Parameters a,b define local c; c used by require and return. No state events.',
       'Keep entry->c and c->require/return facts; no STATE_DEF_USE edges.',
       'No state alias question. Existing local scalar algorithm suffices.',
       'Existing HCG 5957/5961/5962/5963; a state module disabled or enabled must leave these scalar edges unchanged.'),
      ('O8','Already-covered parameter authority error',bynode['access_control_author',2418],
       'READ owner_txorigin31 PARAMETER and tx.origin; function evaluates to.call.value(amount) expression.',
       'Keep parameter data dependencies. Do not reinterpret owner_txorigin31 as owner state and do not invent owner-state DEF_USE.',
       'The displayed expression is a call-options expression; do not assert an actual external invocation unless AST/call semantics prove it. Authority guard context differs from state flow.',
       'Existing DDG already reaches selected wrong node. This is a counterexample to state expansion as universal explanation.'),
      ('O9','Owner check versus public length annotation',fn('access_control_author','arbitrary_location_write_simple.sol','PopBonusCode'),
       'READ unsigned bonusCodes.length at require; READ+WRITE length in --.',
       'Earlier read origin unknown; decrement is not its definition. No reverse def-use. Public annotation line27 is require; decrement occupies line28.',
       'Arithmetic underflow behavior requires declared compiler semantics. No claim that storage slots are solved.',
       'Two HCG expression nodes 11473 and11474 both cover decrement forms. Projection must choose exact AST/event anchor, not duplicate by nearest line.'),
    ]
    synthetic=[
      ('O10','Distinct constant keys; exact positive then negative',
       'pragma solidity 0.5.17; contract T { mapping(uint=>uint) m; function f() public returns(uint,uint){ m[1]=7; uint a=m[1]; uint b=m[2]; return(a,b); } }',
       'm[1] write -> later m[1] read required; no m[1] write -> m[2] read. Both typed constants verified.'),
      ('O11','Uncertain storage reference alias',
       'pragma solidity 0.5.17; contract T { struct S { uint v; } mapping(uint=>S) m; function f(uint k,uint j) public returns(uint){ S storage r=m[k]; r.v=7; return m[j].v; } }',
       'r binding is reference alias, not storage content definition. k/j MAY equal; no MUST fact. Initial subset falls back state analysis; no guessed graph edge.'),
      ('O12','Strong KILL and branch alternatives',
       'pragma solidity 0.5.17; contract T { uint s; function f(bool b) public returns(uint){ s=1; if(b){s=2;} return s; } }',
       'Return has alternative definitions s=1/s=2. s=2 strongly kills s=1 only on branch; union preserves bypass. Add paired unconditional s=2 negative fixture excluding s=1.'),
      ('O13','Changing key definition',
       'pragma solidity 0.5.17; contract T { mapping(uint=>uint) m; function f(uint k) public returns(uint){ m[k]=1; k=k+1; return m[k]; } }',
       'Same key variable spelling with changed definition is not same exact key; no unproved MUST relation. Include uint overflow/version and MAY/UNKNOWN policy.'),
      ('O14','External call clobber after local state write',
       'pragma solidity 0.5.17; contract T { uint s; function f(address a) public returns(uint){ s=1; (bool ok,)=a.call(\"\"); require(ok); return s; } }',
       'Do not claim pre-call s=1 is a must-reaching post-call definition. Record unknown callback effects/HAVOC or state fallback; preserve scalar ok->require.'),
    ]
    text=['# D3 candidate oracle specification','','Codex, 2026-10-13. **Proposed expectations, not independently certified state-analysis ground truth.**',
      '', 'O1-O9 are exact SHA/AST-associated corpus functions. Their raw Solidity and existing HCG identities are retained below. The new state facts are reasoned expectations (B) requiring independent reviewer sign-off. No state algorithm or solc validation was run.',
      '', 'O10-O14 are synthetic negative/positive fixtures specified as text only: no parser run, no compilation, no generated HCG, and therefore no real HCG IDs. They must pass later parser/compiler/projection gates; no invented numeric IDs are provided.',
      '', 'Expected facts are derived from source/control semantics, never from prediction correctness. Formal acceptance requires a reviewer, version, rationale, exact expected events/edges and explicit unsupported outcomes.']
    output=[]
    for oid,title,s,events,facts,uncertain,projection in specs:
        f=s['function'];nodes=s['function_hcg_nodes']
        text.extend(['','## '+oid+' ? '+title,'',
          '- Source: '+s['source_path']+'; SHA256 '+s['source_sha256'],
          '- Function raw lines {}-{}; bytes [{}:{}).'.format(f['start_line'],f['end_line'],f['start_byte'],f['end_byte']),
          '- Original HCG: '+', '.join('{}:{}@{}'.format(n['node_id'],n['node_type'],n['start_line']) for n in nodes),
          '- State/access expectations: '+events,'- Required/forbidden Def-Use: '+facts,
          '- Alias/uncertainty: '+uncertain,'- Current gap and projection: '+projection,
          '',chr(96)*3+'solidity',f['text'],chr(96)*3])
        output.append(dict(id=oid,title=title,origin='exact_corpus_source',source=s,expected_accesses=events,
            expected_and_forbidden_facts=facts,uncertainty=uncertain,projection=projection,
            independent_validation='pending',compiled=False,state_algorithm_executed=False))
    for oid,title,source,expected in synthetic:
        text.extend(['','## '+oid+' ? '+title,'','- Origin: synthetic specification, not a corpus modification.',
          '- Existing HCG: none. Build in an isolated future fixture and assign AST-derived anchors; missing anchors cannot be guessed.',
          '- Expected/forbidden: '+expected,'- Status: not parsed, not compiled, not independently reviewed.',
          '',chr(96)*3+'solidity',source,chr(96)*3])
        output.append(dict(id=oid,title=title,origin='synthetic_specification',source=source,
            expected_and_forbidden_facts=expected,hcg_nodes=None,parsed=False,compiled=False,
            independent_validation='pending',state_algorithm_executed=False))
    text.extend(['','## Mandatory acceptance per oracle','',
        'Check event extraction, location identity, key-version proof, strong/weak KILL, branch/loop result, call uncertainty, exact projection and no original-node/label/token/base-edge changes. Validate unsupported outcome explicitly; no dependency returned can be a correct result.',
        'Fixtures O10-O14 require their own graph generation and code legality check when an approved trusted compiler is available. A complete parser-only result is still not compiler verification.',
        'Do not discard a fixture because it supplies no extra model edges or because a state extension cannot explain an existing error.'])
    with (H/'D3_ORACLE_SPEC.md').open('x',encoding='utf8') as f:f.write('\n'.join(text)+'\n')
    with (H/'D3_ORACLE_CANDIDATES.json').open('x') as f:json.dump(dict(status='design_only_not_approved_oracle',oracles=output),f,indent=2)
    print(json.dumps(dict(corpus_oracles=len(specs),synthetic_specifications=len(synthetic))))
if __name__=='__main__':main()
