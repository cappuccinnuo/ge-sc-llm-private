# D3 candidate oracle specification

Codex, 2026-10-13. **Proposed expectations, not independently certified state-analysis ground truth.**

O1-O9 are exact SHA/AST-associated corpus functions. Their raw Solidity and existing HCG identities are retained below. The new state facts are reasoned expectations (B) requiring independent reviewer sign-off. No state algorithm or solc validation was run.

O10-O14 are synthetic negative/positive fixtures specified as text only: no parser run, no compilation, no generated HCG, and therefore no real HCG IDs. They must pass later parser/compiler/projection gates; no invented numeric IDs are provided.

Expected facts are derived from source/control semantics, never from prediction correctness. Formal acceptance requires a reviewer, version, rationale, exact expected events/edges and explicit unsupported outcomes.

## O1: Reentrancy balance/read/call/reset

- Source: /home/zhao/SmartContract/ge-sc-llm/experiments/ge-sc-data/source_code/reentrancy/source_files/buggy_18.sol; SHA256 b9e23563d26a4976a295154577358f01d63bf533c67775b065a877b934bef9ec
- Function raw lines 112-120; bytes [4004:4378).
- Original HCG: 2705:function_definition@112, 2706:new_variable@115, 2707:if@116, 2709:expression_statement@119
- State/access expectations: Read userBalance_re_ent33[msg.sender] before external call; write same element after successful call.
- Required/forbidden Def-Use: No concrete in-function state definition reaches the earlier read: its origin is ENTRY_UNKNOWN. Do not create reset -> earlier call/read. Call invalidates pre-call state assumptions.
- Alias/uncertainty: msg.sender stable in one frame, but unknown callback may change state; binding fallback remains explicit.
- Current gap and projection: Mapping/call state outside scalar scope. Existing statement nodes can anchor accesses; entry unknown has no concrete definition node. Access order is metadata, not state DEF_USE.

```solidity
function withdrawBalance_re_ent33() public{
        // send userBalance[msg.sender] ethers to msg.sender
        // if mgs.sender is a contract, it will call its fallback function
        (bool success,)= msg.sender.call.value(userBalance_re_ent33[msg.sender])("");
        if( ! success ){
            revert();
        }
        userBalance_re_ent33[msg.sender] = 0;
    }
```

## O2: Same mapping key compound update

- Source: /home/zhao/SmartContract/ge-sc-llm/experiments/ge-sc-data/source_code/reentrancy/source_files/buggy_18.sol; SHA256 b9e23563d26a4976a295154577358f01d63bf533c67775b065a877b934bef9ec
- Function raw lines 72-77; bytes [2044:2327).
- Original HCG: 2673:function_definition@72, 2674:expression_statement@73, 2675:expression_statement@75, 2676:expression_statement@76
- State/access expectations: READ balances_re_ent10[msg.sender] in guard and compound -=; WRITE same element in compound statement; read _weiToWithdraw parameter separately.
- Required/forbidden Def-Use: Keep parameter -> guard/send/update scalar facts. No backward later-write -> earlier guard. A compound write cannot define its own preceding RHS read.
- Alias/uncertainty: Send may hand control away; state origin after call requires call policy. Same spelling of mapping root alone does not prove binding.
- Current gap and projection: State contents absent although scalar parameter dependencies exist. Compound RHS and write may project to one node; retain facts even when self edge is filtered.

```solidity
function withdrawFunds_re_ent10 (uint256 _weiToWithdraw) public {
        require(balances_re_ent10[msg.sender] >= _weiToWithdraw);
        // limit the withdrawal
        require(msg.sender.send(_weiToWithdraw));  //bug
        balances_re_ent10[msg.sender] -= _weiToWithdraw;
    }
```

## O3: Different symbolic keys / may alias

- Source: /home/zhao/SmartContract/ge-sc-llm/experiments/ge-sc-data/source_code/reentrancy/source_files/buggy_27.sol; SHA256 e47d29695de23df62ebfb68db99311a6b01b28f3844f78a37936277f3efc8043
- Function raw lines 459-513; bytes [15479:17272).
- Original HCG: 4863:function_definition@459, 4864:expression_statement@460, 4865:expression_statement@461, 4866:expression_statement@462, 4867:if@466, 4869:return@468, 4870:new_variable@473, 4871:new_variable@474, 4872:new_variable@475, 4873:expression_statement@478, 4874:if@482, 4876:expression_statement@484, 4877:expression_statement@485, 4878:expression_statement@488, 4879:expression_statement@491, 4880:expression_statement@496, 4881:expression_statement@503, 4882:expression_statement@506, 4883:expression_statement@507, 4884:return@512
- State/access expectations: READ/WRITE _balances[from], _balances[DanPanAddress], _balances[to]; nested _allowed[from][msg.sender].
- Required/forbidden Def-Use: No MUST alias or NO_ALIAS from different variable names. Earlier from write may reach later to read only under a sound may-alias summary; do not assert a must fact.
- Alias/uncertainty: from==to or to==DanPanAddress is possible absent proof. Internal SafeMath/fee calls require summaries; first subset must fall back state analysis here.
- Current gap and projection: Useful negative support boundary: these real statements are projected but complete key/call semantics are not implemented.

```solidity
function transferFrom(address from, address to, uint256 value) public returns (bool) {
    require(value <= _balances[from]);
    require(value <= _allowed[from][msg.sender]);
    require(to != address(0));
    
    // If transfer amount is zero
        // emit event and stop execution
        if (value == 0) {
            emit Transfer(from, to, 0);
            return true;
        }

    // Calculate receiver balance
        // initial receive is full value
        uint256 tokensToTransfer = value;
        uint256 tokensToBurn = 0;
        uint256 tokensToDanPan = 0;
    
    // Change sender balance
        _balances[from] = _balances[from].sub(value);

        // If the transaction is not whitelisted
        // calculate fees
        if (!_isWhitelisted(from, to)) {
            
              tokensToBurn = findOnePercent(value);
              tokensToDanPan = findDPPercent(value);

            // Subtract fees from receiver amount
             tokensToTransfer = value.sub(tokensToBurn).sub(tokensToDanPan);

            // Burn tokens
            _totalSupply = _totalSupply.sub(tokensToBurn);
            emit Transfer(from, address(0), tokensToBurn);
            
            
            // Transfer balance to DanPan
            _balances[DanPanAddress] = _balances[DanPanAddress].add(tokensToDanPan);
           emit Transfer(from, DanPanAddress, tokensToDanPan);

        }

        // Sanity checks
        // no tokens where created
        assert(tokensToBurn.add(tokensToTransfer).add(tokensToDanPan) == value);

        // Add tokens to receiver
        _balances[to] = _balances[to].add(tokensToTransfer);
	_allowed[from][msg.sender] = _allowed[from][msg.sender].sub(value);
        emit Transfer(from, to, tokensToTransfer);
    
    
    
    return true;
  }
```

## O4: Owner entry-state read

- Source: /home/zhao/SmartContract/ge-sc-llm/experiments/ge-sc-data/source_code/access_control/source_files/mapping_write.sol; SHA256 a4c6ab0924feb97c929511f65e9f86a82ca5efa307aa29dcae69a21d2fc0fbd6
- Function raw lines 26-29; bytes [666:788).
- Original HCG: 12962:function_definition@26, 12963:expression_statement@27, 12964:expression_statement@28
- State/access expectations: READ owner in require; withdraw subsequently transfers balance. map in same contract is an ARRAY.
- Required/forbidden Def-Use: Owner is ENTRY_UNKNOWN here. No constructor/local owner definition may be fabricated in withdraw. require -> transfer is a control constraint, not owner DEF_USE.
- Alias/uncertainty: Cross-function array arbitrary-write effects require bounds/layout/version analysis; no exact EVM slot claim.
- Current gap and projection: Guard HCG node 12963 exists; no same-function concrete owner-def node. New state module should report the missing origin instead of promising an edge.

```solidity
function withdraw() public{
       require(msg.sender == owner);
       msg.sender.transfer(address(this).balance);
     }
```

## O5: Modifier control of state update

- Source: /home/zhao/SmartContract/ge-sc-llm/experiments/ge-sc-data/source_code/access_control/source_files/buggy_18.sol; SHA256 d8505eecd2d5acd06a30006b1e163a08e5bc3a7918c69c86f809c4e9bdeb8ad4
- Function raw lines 146-148; bytes [5005:5105).
- Original HCG: 1343:function_definition@146, 1344:expression_statement@147
- State/access expectations: Modifier onlyOwner READ owner, compare msg.sender; function WRITE newOwner from _newOwner.
- Required/forbidden Def-Use: Parameter -> write is scalar/value flow. Owner predicate -> newOwner write is CONTROL_DEPENDENCE, not state DEF_USE. Entry owner not locally defined.
- Alias/uncertainty: Full source modifier text retained separately. Unique invocation/binding/underscore and path semantics must be established before expansion.
- Current gap and projection: Original function/statement nodes exist (1343,1344). Do not invent modifier node IDs; actual modifier HCG mapping remains a separate exact-projection requirement.

```solidity
function transferOwnership(address _newOwner) public onlyOwner {
        newOwner = _newOwner;
    }
```

## O6: Branch-dependent state write

- Source: /home/zhao/SmartContract/ge-sc-llm/experiments/ge-sc-data/source_code/access_control/source_files/mapping_write.sol; SHA256 a4c6ab0924feb97c929511f65e9f86a82ca5efa307aa29dcae69a21d2fc0fbd6
- Function raw lines 15-21; bytes [359:563).
- Original HCG: 12955:function_definition@15, 12956:if@16, 12958:expression_statement@17, 12959:expression_statement@20
- State/access expectations: READ map.length at if; branch WRITE map.length=key+1; unconditional WRITE map[key]=value.
- Required/forbidden Def-Use: Conditional length write is not a reaching definition for the earlier condition. Branch union must retain ENTRY_UNKNOWN on bypass. map.length and map[key] are distinct locations.
- Alias/uncertainty: Dynamic array bounds/overflow and key identity remain version-sensitive; branch condition is not a data dependency from length write to element write.
- Current gap and projection: Existing condition 12956, length write 12958 and element write12959 can anchor events. Existing graph already conveys control; first mapping-only subset does not claim array support.

```solidity
function set(uint256 key, uint256 value) public {
         if (map.length <= key) {
             map.length = key + 1;
         }
        // <yes> <report> ACCESS_CONTROL
         map[key] = value;
     }
```

## O7: Scalar-only positive control

- Source: /home/zhao/SmartContract/ge-sc-llm/experiments/ge-sc-data/source_code/reentrancy/source_files/buggy_36.sol; SHA256 64addaa381f3df0852487c66cc85730aa67affd7cd84f4fe616ff9d2ec9826fb
- Function raw lines 171-183; bytes [5819:6258).
- Original HCG: 5957:function_definition@171, 5958:if@175, 5960:return@176, 5961:new_variable@179, 5962:expression_statement@180, 5963:return@182
- State/access expectations: Parameters a,b define local c; c used by require and return. No state events.
- Required/forbidden Def-Use: Keep entry->c and c->require/return facts; no STATE_DEF_USE edges.
- Alias/uncertainty: No state alias question. Existing local scalar algorithm suffices.
- Current gap and projection: Existing HCG 5957/5961/5962/5963; a state module disabled or enabled must leave these scalar edges unchanged.

```solidity
function mul(uint256 a, uint256 b) internal pure returns (uint256) {
        // Gas optimization: this is cheaper than requiring 'a' not being zero, but the
        // benefit is lost if 'b' is also tested.
        // See: https://github.com/OpenZeppelin/openzeppelin-solidity/pull/522
        if (a == 0) {
            return 0;
        }

        uint256 c = a * b;
        require(c / a == b, "Safe mul error");

        return c;
    }
```

## O8: Already-covered parameter authority error

- Source: /home/zhao/SmartContract/ge-sc-llm/experiments/ge-sc-data/source_code/access_control/source_files/buggy_26.sol; SHA256 129a0b4301ccaaba94cb50772fbfefe574f59ee088373a03380faa25ea0f6d74
- Function raw lines 103-106; bytes [3777:3935).
- Original HCG: 2417:function_definition@103, 2418:expression_statement@104, 2419:expression_statement@105
- State/access expectations: READ owner_txorigin31 PARAMETER and tx.origin; function evaluates to.call.value(amount) expression.
- Required/forbidden Def-Use: Keep parameter data dependencies. Do not reinterpret owner_txorigin31 as owner state and do not invent owner-state DEF_USE.
- Alias/uncertainty: The displayed expression is a call-options expression; do not assert an actual external invocation unless AST/call semantics prove it. Authority guard context differs from state flow.
- Current gap and projection: Existing DDG already reaches selected wrong node. This is a counterexample to state expansion as universal explanation.

```solidity
function transferTo_txorigin31(address to, uint amount,address owner_txorigin31) public {
  require(tx.origin == owner_txorigin31);
  to.call.value(amount);
}
```

## O9: Owner check versus public length annotation

- Source: /home/zhao/SmartContract/ge-sc-llm/experiments/ge-sc-data/source_code/access_control/source_files/arbitrary_location_write_simple.sol; SHA256 bbbdb5367463fd3d1e11b2c569695d8b4734e3f88fcf937a34469a23121b01ab
- Function raw lines 25-29; bytes [514:768).
- Original HCG: 11471:function_definition@25, 11472:expression_statement@27, 11473:expression_statement@28, 11474:expression_statement@28
- State/access expectations: READ unsigned bonusCodes.length at require; READ+WRITE length in --.
- Required/forbidden Def-Use: Earlier read origin unknown; decrement is not its definition. No reverse def-use. Public annotation line27 is require; decrement occupies line28.
- Alias/uncertainty: Arithmetic underflow behavior requires declared compiler semantics. No claim that storage slots are solved.
- Current gap and projection: Two HCG expression nodes 11473 and11474 both cover decrement forms. Projection must choose exact AST/event anchor, not duplicate by nearest line.

```solidity
function PopBonusCode() public {
         // <yes> <report> ACCESS_CONTROL
         require(0 <= bonusCodes.length); // this condition is always true since array lengths are unsigned
         bonusCodes.length--; // an underflow can be caused here
     }
```

## O10: Distinct constant keys; exact positive then negative

- Origin: synthetic specification, not a corpus modification.
- Existing HCG: none. Build in an isolated future fixture and assign AST-derived anchors; missing anchors cannot be guessed.
- Expected/forbidden: m[1] write -> later m[1] read required; no m[1] write -> m[2] read. Both typed constants verified.
- Status: not parsed, not compiled, not independently reviewed.

```solidity
pragma solidity 0.5.17; contract T { mapping(uint=>uint) m; function f() public returns(uint,uint){ m[1]=7; uint a=m[1]; uint b=m[2]; return(a,b); } }
```

## O11: Uncertain storage reference alias

- Origin: synthetic specification, not a corpus modification.
- Existing HCG: none. Build in an isolated future fixture and assign AST-derived anchors; missing anchors cannot be guessed.
- Expected/forbidden: r binding is reference alias, not storage content definition. k/j MAY equal; no MUST fact. Initial subset falls back state analysis; no guessed graph edge.
- Status: not parsed, not compiled, not independently reviewed.

```solidity
pragma solidity 0.5.17; contract T { struct S { uint v; } mapping(uint=>S) m; function f(uint k,uint j) public returns(uint){ S storage r=m[k]; r.v=7; return m[j].v; } }
```

## O12: Strong KILL and branch alternatives

- Origin: synthetic specification, not a corpus modification.
- Existing HCG: none. Build in an isolated future fixture and assign AST-derived anchors; missing anchors cannot be guessed.
- Expected/forbidden: Return has alternative definitions s=1/s=2. s=2 strongly kills s=1 only on branch; union preserves bypass. Add paired unconditional s=2 negative fixture excluding s=1.
- Status: not parsed, not compiled, not independently reviewed.

```solidity
pragma solidity 0.5.17; contract T { uint s; function f(bool b) public returns(uint){ s=1; if(b){s=2;} return s; } }
```

## O13: Changing key definition

- Origin: synthetic specification, not a corpus modification.
- Existing HCG: none. Build in an isolated future fixture and assign AST-derived anchors; missing anchors cannot be guessed.
- Expected/forbidden: Same key variable spelling with changed definition is not same exact key; no unproved MUST relation. Include uint overflow/version and MAY/UNKNOWN policy.
- Status: not parsed, not compiled, not independently reviewed.

```solidity
pragma solidity 0.5.17; contract T { mapping(uint=>uint) m; function f(uint k) public returns(uint){ m[k]=1; k=k+1; return m[k]; } }
```

## O14: External call clobber after local state write

- Origin: synthetic specification, not a corpus modification.
- Existing HCG: none. Build in an isolated future fixture and assign AST-derived anchors; missing anchors cannot be guessed.
- Expected/forbidden: Do not claim pre-call s=1 is a must-reaching post-call definition. Record unknown callback effects/HAVOC or state fallback; preserve scalar ok->require.
- Status: not parsed, not compiled, not independently reviewed.

```solidity
pragma solidity 0.5.17; contract T { uint s; function f(address a) public returns(uint){ s=1; (bool ok,)=a.call(""); require(ok); return s; } }
```

## Mandatory acceptance per oracle

Check event extraction, location identity, key-version proof, strong/weak KILL, branch/loop result, call uncertainty, exact projection and no original-node/label/token/base-edge changes. Validate unsupported outcome explicitly; no dependency returned can be a correct result.
Fixtures O10-O14 require their own graph generation and code legality check when an approved trusted compiler is available. A complete parser-only result is still not compiler verification.
Do not discard a fixture because it supplies no extra model edges or because a state extension cannot explain an existing error.
