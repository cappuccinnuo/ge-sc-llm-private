# D2 difficult-function context review

## 中文结论与证据边界

本轮在 D1 门槛通过后，审计了 12 个固定案例、480 个来自冻结训练文件的精确重复来源。12 个案例的公共 SolidiFI / SmartBugs 对应源码 SHA 均与实际输入一致；447 个训练重复来源完成了完整函数级精确回映，33 个因多个 pragma 的既有前端限制只保留文件、源码 SHA、原节点 ID、标签和明确原因，不猜测源码位置。

**本次只借助 v1.1 Projector 修复精确源码对应；这里的标签、预测、DDG 入出边与两层影响范围，全部仍来自封存 E0/E1。没有把新 E2 边混入旧 F1 或宣称运行了 E2。**

- 重入 buggy_18 的节点2706：作者标签0；公共 CSV 的[111,116]覆盖原行115；37个精确训练同文本均为正例。这是可复核的标注上下文差异，但不能唯一反推作者转换算法，也不等于已证明作者标错。
- 访问控制 buggy_26 的节点2418/2421：作者标签0，而公共注入范围覆盖；各36个精确训练重复中35个为正例。其 owner_txorigin 参数已经有标量 DDG，不是尚未分析的 owner 状态。
- mapping_write.sol 的 map 实际为 uint256[] 数组；不能因为文件名就按 mapping 处理。其 SmartBugs 标注原行20的数组写，与原行27的 owner 检查是不同节点。
- arbitrary_location_write_simple.sol 的公共标注原行27是无效的无符号长度下界检查，紧邻原行28的长度递减；原行37的 owner 检查不在该标注行。
- AC buggy_18 节点1285为纯算术 mul，已有2条 DDG 入边仍预测错；R buggy_36 节点5961是标量 DDG 真正产生有益消息作用的例子。不能把所有问题归结为缺少状态依赖。
- 某些样例只有 to.call.value(amount) 的调用选项表达式，缺少最后的调用括号；不能未经绑定和执行语义核验就写成“已经执行外部调用”。

当前证据同时支持三类问题：D1 已验证的构图正确性问题、当前范围外的状态/控制/调用语义，以及重复片段的标签上下文歧义；没有证据给三者分配完整因果比例。本轮未更改标签，未完成正式漏洞标注认证，未编译样例，也未重新训练。


Codex, 2026-10-13. Original author labels; read-only; no training, relabeling, graph mutation or solc.

A = direct source/graph/archive evidence; B = supported semantic interpretation without independent execution; C = ambiguity requiring review; D = insufficient evidence.

Exact source SHA + saved AST identity + raw/compat token correspondence establish each location. Full functions and existing HCG IDs: results/D2_CASE_EVIDENCE.json. Named train-only duplicate sources: results/D2_TRAIN_DUPLICATES.json. Public CSV intervals are comparison evidence, not reconstructed author truth.

## Main implications

- Same text/opposite labels does not automatically prove wrong labels.
- map in mapping_write.sol is an ARRAY; names cannot select the abstraction.
- owner_txorigin parameters already have scalar DDG; not all AC errors are missing state flow.
- Owner guards and vulnerable array write sites are different statements.
- Selection includes scalar-only success and wrong nodes already covered by DDG, not only pro-extension cases.

## Cases

### reentrancy_author/buggy_18.sol/2706

- Source SHA256: b9e23563d26a4976a295154577358f01d63bf533c67775b065a877b934bef9ec
- Raw lines 115-115, bytes [4192:4269); AST ID 527; function buggy_18.sol:4004 lines 112-120.
- Compressed endpoints: [[75, 75]]; author label 0. Endpoints are not raw lines.
- E0 best 1 p=0.835074842; E1 best 1 p=0.834033906.
- DDG in/out/two-layer affected: 0/0/0; 37 exact train duplicates, 37 opposite.
- Frozen analysis: builtin_not_guaranteed_over_pragma_interval.
- State reading (A syntax/B semantics): READ userBalance_re_ent33[msg.sender] in external-call amount; WRITE same mapping element zero after call
- Controls: if !success then revert; possible callback before reset
- Missing candidate semantics: mapping-content identity, entry-state origin and external-call effect/order; not a backwards Def-Use edge
- Conclusion: B: call-before-reset pattern. C: negative author label while identical training snippets are positive; no formal vulnerability certification.
- Public annotation: A_exact_public_source; raw records retained.

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

### reentrancy_author/buggy_18.sol/2670

- Source SHA256: b9e23563d26a4976a295154577358f01d63bf533c67775b065a877b934bef9ec
- Raw lines 68-68, bytes [1893:1915); AST ID 214; function buggy_18.sol:1741 lines 63-69.
- Compressed endpoints: [[34, 34]]; author label 1. Endpoints are not raw lines.
- E0 best 0 p=0.357989073; E1 best 0 p=0.358373255.
- DDG in/out/two-layer affected: 0/0/0; 8 exact train duplicates, 0 opposite.
- Frozen analysis: builtin_not_guaranteed_over_pragma_interval.
- State reading (A syntax/B semantics): READ+WRITE counter_re_ent21 via +=1; earlier require(counter<=5), then send
- Controls: send failure -> revert, successful path increments later
- Missing candidate semantics: scalar STATE variable dependence, entry origin and call effect
- Conclusion: B: state guard/update sequencing absent. Frozen binding fallback is independent of D1 repairs.
- Public annotation: A_exact_public_source; raw records retained.

```solidity
function callme_re_ent21() public{
        require(counter_re_ent21<=5);
	if( ! (msg.sender.send(10 ether) ) ){
            revert();
        }
        counter_re_ent21 += 1;
    }
```

### reentrancy_author/buggy_18.sol/2675

- Source SHA256: b9e23563d26a4976a295154577358f01d63bf533c67775b065a877b934bef9ec
- Raw lines 75-75, bytes [2216:2257); AST ID 256; function buggy_18.sol:2044 lines 72-77.
- Compressed endpoints: [[40, 40]]; author label 1. Endpoints are not raw lines.
- E0 best 0 p=0.429793745; E1 best 0 p=0.432523608.
- DDG in/out/two-layer affected: 1/0/1; 85 exact train duplicates, 0 opposite.
- Frozen analysis: analyzed.
- State reading (A syntax/B semantics): READ balances_re_ent10[msg.sender] in guard; send parameter; READ+WRITE balance via -= parameter
- Controls: require balance >= parameter and require send; parameter data flow exists
- Missing candidate semantics: mapping contents and call-side-effect/order
- Conclusion: A: incoming parameter DDG exists yet FN persists. B: missing state is only one candidate explanation.
- Public annotation: A_exact_public_source; raw records retained.

```solidity
function withdrawFunds_re_ent10 (uint256 _weiToWithdraw) public {
        require(balances_re_ent10[msg.sender] >= _weiToWithdraw);
        // limit the withdrawal
        require(msg.sender.send(_weiToWithdraw));  //bug
        balances_re_ent10[msg.sender] -= _weiToWithdraw;
    }
```

### reentrancy_author/buggy_36.sol/5961

- Source SHA256: 64addaa381f3df0852487c66cc85730aa67affd7cd84f4fe616ff9d2ec9826fb
- Raw lines 179-179, bytes [6168:6186); AST ID 828; function buggy_36.sol:5819 lines 171-183.
- Compressed endpoints: [[143, 143]]; author label 0. Endpoints are not raw lines.
- E0 best 1 p=0.503772676; E1 best 0 p=0.494170934.
- DDG in/out/two-layer affected: 1/2/1; 17 exact train duplicates, 0 opposite.
- Frozen analysis: analyzed.
- State reading (A syntax/B semantics): No state access in SafeMath.mul; local c derives from parameters a,b
- Controls: a==0 early return; require(c/a==b), then return c
- Missing candidate semantics: No state dependency required for this function
- Conclusion: A: scalar DDG positive case: fixed-weight message removal changes correct output to FP. State expansion is not needed here.
- Public annotation: A_exact_public_source; raw records retained.

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

### reentrancy_author/buggy_36.sol/6101

- Source SHA256: 64addaa381f3df0852487c66cc85730aa67affd7cd84f4fe616ff9d2ec9826fb
- Raw lines 451-451, bytes [16276:16301); AST ID 2017; function buggy_36.sol:15870 lines 446-457.
- Compressed endpoints: [[337, 337]]; author label 0. Endpoints are not raw lines.
- E0 best 0 p=0.499244541; E1 best 1 p=0.502355397.
- DDG in/out/two-layer affected: 0/0/0; 1 exact train duplicates, 0 opposite.
- Frozen analysis: Unsupported non-scalar or inferred type: Token.
- State reading (A syntax/B semantics): Selected _minimumTokensToVote is a local parameter, normalized before assignment to contract minimumTokensToVote later
- Controls: onlyOwner modifier; Token parameter is first recorded scalar fallback
- Missing candidate semantics: modifier/control and later contract assignment context; selected statement is not a state write
- Conclusion: A: no direct/two-hop DDG at selected node. B: full function matters; do not invent a state edge on the local assignment.
- Public annotation: A_exact_public_source; raw records retained.

```solidity
function changeVotingRules(Token _tokenAddress, address _chairmanAddress, uint _minimumTokensToVote, uint _minimumPercentToPassAVote, uint _minutesForDebate) onlyOwner public {
        require(_chairmanAddress != address(0));
        require(_minimumPercentToPassAVote <= 51);
        tokenAddress = Token(_tokenAddress);
        chairmanAddress = _chairmanAddress;
        if (_minimumTokensToVote == 0 ) _minimumTokensToVote = 1;
        minimumTokensToVote = _minimumTokensToVote;
        if (_minimumPercentToPassAVote == 0 ) _minimumPercentToPassAVote = 51;
        minimumQuorum = _minimumPercentToPassAVote;
        debatingPeriodInMinutes = _minutesForDebate;
        emit ChangeOfRules(_minimumTokensToVote, minimumQuorum, debatingPeriodInMinutes, address(tokenAddress), chairmanAddress);
    }
```

### reentrancy_author/buggy_27.sol/4672

- Source SHA256: e47d29695de23df62ebfb68db99311a6b01b28f3844f78a37936277f3efc8043
- Raw lines 163-163, bytes [4956:5006); AST ID 792; function buggy_27.sol:4855 lines 161-167.
- Compressed endpoints: [[128, 128]]; author label 1. Endpoints are not raw lines.
- E0 best 0 p=0.399095476; E1 best 1 p=0.960331082.
- DDG in/out/two-layer affected: 0/0/0; 3 exact train duplicates, 1 opposite.
- Frozen analysis: analyzed.
- State reading (A syntax/B semantics): READ redeemableEther_re_ent18[msg.sender], copy to local transferValue, transfer, WRITE same element zero
- Controls: positive-balance require; transfer before reset
- Missing candidate semantics: entry state and access-order/call-effects; no prior concrete in-function balance definition
- Conclusion: A: E1 corrects but N/Z identical here. Cannot attribute correction to direct frozen DDG messages.
- Public annotation: A_exact_public_source; raw records retained.

```solidity
function claimReward_re_ent18() public {        
        // ensure there is a reward to give
        require(redeemableEther_re_ent18[msg.sender] > 0);
        uint transferValue_re_ent18 = redeemableEther_re_ent18[msg.sender];
        msg.sender.transfer(transferValue_re_ent18);   //bug
        redeemableEther_re_ent18[msg.sender] = 0;
    }
```

### access_control_author/mapping_write.sol/12963

- Source SHA256: a4c6ab0924feb97c929511f65e9f86a82ca5efa307aa29dcae69a21d2fc0fbd6
- Raw lines 27-27, bytes [701:730); AST ID 77; function mapping_write.sol:666 lines 26-29.
- Compressed endpoints: [[15, 15]]; author label 0. Endpoints are not raw lines.
- E0 best 0 p=0.014381564; E1 best 1 p=0.651479125.
- DDG in/out/two-layer affected: 0/0/0; 12 exact train duplicates, 0 opposite.
- Frozen analysis: analyzed.
- State reading (A syntax/B semantics): READ owner at require; withdraw transfers contract balance. Same contract set writes map[key]; map is uint256[] ARRAY, not mapping
- Controls: withdraw guarded by msg.sender==owner; set accepts user-controlled array length/index/value
- Missing candidate semantics: owner entry state, array length/location and cross-function arbitrary-write context
- Conclusion: A: SmartBugs annotation is line20 array write, not line27 guard. B: arbitrary slot reach requires bounds/layout/version analysis. Negative guard is not evidence of bad label.
- Public annotation: A_exact_public_source; raw records retained.

```solidity
function withdraw() public{
       require(msg.sender == owner);
       msg.sender.transfer(address(this).balance);
     }
```

### access_control_author/arbitrary_location_write_simple.sol/11479

- Source SHA256: bbbdb5367463fd3d1e11b2c569695d8b4734e3f88fcf937a34469a23121b01ab
- Raw lines 37-37, bytes [1002:1031); AST ID 110; function arbitrary_location_write_simple.sol:965 lines 36-39.
- Compressed endpoints: [[23, 23]]; author label 0. Endpoints are not raw lines.
- E0 best 1 p=0.508923292; E1 best 0 p=0.484181702.
- DDG in/out/two-layer affected: 0/0/0; 10 exact train duplicates, 0 opposite.
- Frozen analysis: analyzed.
- State reading (A syntax/B semantics): READ owner at Destroy guard; constructor writes owner; elsewhere bonusCodes.length-- and indexed writes
- Controls: Destroy guard then selfdestruct; PopBonusCode unsigned lower-bound check ineffective
- Missing candidate semantics: cross-function owner origin and array length/index context
- Conclusion: A: public annotation is line27 unsigned length check (adjacent decrement is line28), not line37 owner guard. B: local state Def-Use alone does not establish arbitrary-storage reach.
- Public annotation: A_exact_public_source; raw records retained.

```solidity
function Destroy() public {
         require(msg.sender == owner);
         selfdestruct(msg.sender);
     }
```

### access_control_author/buggy_18.sol/1285

- Source SHA256: d8505eecd2d5acd06a30006b1e163a08e5bc3a7918c69c86f809c4e9bdeb8ad4
- Raw lines 35-35, bytes [993:1023); AST ID 99; function buggy_18.sol:905 lines 33-36.
- Compressed endpoints: [[13, 13]]; author label 0. Endpoints are not raw lines.
- E0 best 1 p=0.622525096; E1 best 1 p=0.638674319.
- DDG in/out/two-layer affected: 2/0/1; 3 exact train duplicates, 0 opposite.
- Frozen analysis: analyzed.
- State reading (A syntax/B semantics): No state access: pure SafeMath.mul computes named local return c from a,b
- Controls: require(a==0 || c/a==b)
- Missing candidate semantics: No state variable dependence required; arithmetic scalar dataflow already present
- Conclusion: A: two incoming scalar DDG edges yet prediction wrong; this counterexample cannot be explained by missing state alone.
- Public annotation: A_exact_public_source; raw records retained.

```solidity
function mul(uint a, uint b) internal pure returns(uint c) {
        c = a * b;
        require(a == 0 || c / a == b);
    }
```

### access_control_author/buggy_18.sol/1306

- Source SHA256: d8505eecd2d5acd06a30006b1e163a08e5bc3a7918c69c86f809c4e9bdeb8ad4
- Raw lines 73-73, bytes [2344:2370); AST ID 287; function buggy_18.sol:2201 lines 71-74.
- Compressed endpoints: [[39, 39]]; author label 1. Endpoints are not raw lines.
- E0 best 0 p=0.362352431; E1 best 0 p=0.406356931.
- DDG in/out/two-layer affected: 1/0/1; 232 exact train duplicates, 3 opposite.
- Frozen analysis: analyzed.
- State reading (A syntax/B semantics): Injected function uses tx.origin and owner_txorigin parameter; parameter name owner does NOT make it contract state
- Controls: require(tx.origin==owner parameter); full function may transfer/call
- Missing candidate semantics: authority/provenance and guard/control, not necessarily a missing state-variable edge
- Conclusion: A: scalar DDG already reaches wrong node. B: adding state alone is not presumed to fix it. C: author/public interval context needs review.
- Public annotation: A_exact_public_source; raw records retained.

```solidity
function sendto_txorigin21(address payable receiver, uint amount,address owner_txorigin21) public {
	require (tx.origin == owner_txorigin21);
	receiver.transfer(amount);
}
```

### access_control_author/buggy_26.sol/2418

- Source SHA256: 129a0b4301ccaaba94cb50772fbfefe574f59ee088373a03380faa25ea0f6d74
- Raw lines 104-104, bytes [3869:3908); AST ID 620; function buggy_26.sol:3777 lines 103-106.
- Compressed endpoints: [[84, 84]]; author label 0. Endpoints are not raw lines.
- E0 best 1 p=0.909999788; E1 best 1 p=0.985810220.
- DDG in/out/two-layer affected: 1/0/1; 36 exact train duplicates, 35 opposite.
- Frozen analysis: analyzed.
- State reading (A syntax/B semantics): Injected function uses tx.origin and owner_txorigin parameter; parameter name owner does NOT make it contract state
- Controls: require(tx.origin==owner parameter); full function may transfer/call
- Missing candidate semantics: authority/provenance and guard/control, not necessarily a missing state-variable edge
- Conclusion: A: scalar DDG already reaches wrong node. B: adding state alone is not presumed to fix it. C: author/public interval context needs review.
- Public annotation: A_exact_public_source; raw records retained.

```solidity
function transferTo_txorigin31(address to, uint amount,address owner_txorigin31) public {
  require(tx.origin == owner_txorigin31);
  to.call.value(amount);
}
```

### access_control_author/buggy_26.sol/2421

- Source SHA256: 129a0b4301ccaaba94cb50772fbfefe574f59ee088373a03380faa25ea0f6d74
- Raw lines 110-110, bytes [4107:4147); AST ID 668; function buggy_26.sol:4006 lines 109-112.
- Compressed endpoints: [[89, 89]]; author label 0. Endpoints are not raw lines.
- E0 best 1 p=0.896818876; E1 best 1 p=0.993297398.
- DDG in/out/two-layer affected: 1/0/1; 36 exact train duplicates, 35 opposite.
- Frozen analysis: analyzed.
- State reading (A syntax/B semantics): Injected function uses tx.origin and owner_txorigin parameter; parameter name owner does NOT make it contract state
- Controls: require(tx.origin==owner parameter); full function may transfer/call
- Missing candidate semantics: authority/provenance and guard/control, not necessarily a missing state-variable edge
- Conclusion: A: scalar DDG already reaches wrong node. B: adding state alone is not presumed to fix it. C: author/public interval context needs review.
- Public annotation: A_exact_public_source; raw records retained.

```solidity
function sendto_txorigin13(address payable receiver, uint amount,address owner_txorigin13) public {
	require (tx.origin == owner_txorigin13);
	receiver.transfer(amount);
}
```

## Limits

Public injection intervals are not certification of every statement as a vulnerability location. Author payload remains separate; matching intervals cannot establish unpublished conversion rules.
No sample was compiled in D2. AST/source identity is not exploitability. Callback feasibility, gas, version and inherited effects need independent evidence.
D1 repairs do not add state/mapping/modifier/interprocedural semantics. Numbers here are archived E0/E1 predictions, not predictions on v1.1 graphs.
