# Prompt 6d：机械归类样例与证据

本页按每个非空的“任务 × 层 × FP/FN × 类别”确定性取前5条，不足5条全部列出，共119例、25组。这是机械类别样例，**不是 seed=0 的172条随机人工审阅样本**，不填写人工 verdict，也不等同于DDG边精度、漏洞检测精度或已确认的分析器缺陷。

来源为封存的 alignment_v3，旧6c行口径指标未替换。FP/FN仅表示本次一对一跨度比较的未匹配候选/参考事件。字节区间均是原始 UTF-8 源码的半开区间 [start,end)，行号从1开始。

Slither列的文本来自报告中已记录的CFG节点区间对原始源码的切片；不是重新执行Slither得到的字符串。另一侧未匹配时明确写“未匹配”，不会把 nearby 的相交上下文当作配对。源码片段为便于阅读可压成单行、截短，完整原文和证据见JSON。

完整证据: [category_examples.json](../experiments/artifacts/dfg_v2/prompt6d_v1/category_examples.json) / [alignment_v3/report.json](../experiments/artifacts/dfg_v2/prompt6d_v1/alignment_v3/report.json)

JSON为本地审计产物，未随Git提交的大文件需在已有WSL工作树中查看。

输入JSON SHA256: `b1d08702ce9db766fc138c47022ba3fa7c6577630eeb2835a15dc2e0f7d046ad`

alignment_v3报告 SHA256: `c1f68cd9ea37d00653700545d3cce322114f132ce29db127f6222f8ae6cbd22a`

## 重入 / L1 / FP / entry_initialization (5)

### 001 `0x01f8c4e3fa3edeb29e514cba738d87ce8c091d3f.sol` : 19

- 源码 SHA256: `0196d033850b295690465d0f7d2baae8b3570df29c9d03d507496b45155a84e5`
- 精确证据身份 / difference_id: `7bdd7f474b29a4b18a95b7ef1b362d12cbc8e27fb93f1e2062c64ff5cfc68a66`
- 原始行: 19; 字节区间: `[347, 356]`; 事件: `_val DEF`; scope=`supported`
- 源码短片段: `uint _val`

v2候选: `DEF _val`; 声明 `[347, 356] uint _val`; 函数起点 `328`; IR事件 `0x01f8c4e3fa3edeb29e514cba738d87ce8c091d3f.sol:328:e0`; kind=`entry`; 分析路径 `legacy`; anchor=`{'file': '0x01f8c4e3fa3edeb29e514cba738d87ce8c091d3f.sol', 'start': 328, 'end': 436, 'role': 'function_definition'}`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `sealed_entry_initialization_tag`.

### 002 `0x01f8c4e3fa3edeb29e514cba738d87ce8c091d3f.sol` : 26

- 源码 SHA256: `0196d033850b295690465d0f7d2baae8b3570df29c9d03d507496b45155a84e5`
- 精确证据身份 / difference_id: `2380394bca867dbf9b9b3d181c8d446df5cc236d8acd5f2d4fc1c7a573cea990`
- 原始行: 26; 字节区间: `[466, 478]`; 事件: `_log DEF`; scope=`supported`
- 源码短片段: `address _log`

v2候选: `DEF _log`; 声明 `[466, 478] address _log`; 函数起点 `446`; IR事件 `0x01f8c4e3fa3edeb29e514cba738d87ce8c091d3f.sol:446:e0`; kind=`entry`; 分析路径 `legacy`; anchor=`{'file': '0x01f8c4e3fa3edeb29e514cba738d87ce8c091d3f.sol', 'start': 446, 'end': 564, 'role': 'function_definition'}`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `sealed_entry_initialization_tag`.

### 003 `0x01f8c4e3fa3edeb29e514cba738d87ce8c091d3f.sol` : 47

- 源码 SHA256: `0196d033850b295690465d0f7d2baae8b3570df29c9d03d507496b45155a84e5`
- 精确证据身份 / difference_id: `147d1f8eb1c3d19c9a5cf5e688047c11cc330c953b352e073962275a14811b14`
- 原始行: 47; 字节区间: `[831, 839]`; 事件: `_am DEF`; scope=`supported`
- 源码短片段: `uint _am`

v2候选: `DEF _am`; 声明 `[831, 839] uint _am`; 函数起点 `814`; IR事件 `0x01f8c4e3fa3edeb29e514cba738d87ce8c091d3f.sol:814:e0`; kind=`entry`; 分析路径 `legacy`; anchor=`{'file': '0x01f8c4e3fa3edeb29e514cba738d87ce8c091d3f.sol', 'start': 814, 'end': 1180, 'role': 'function_definition'}`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `sealed_entry_initialization_tag`.

### 004 `0x01f8c4e3fa3edeb29e514cba738d87ce8c091d3f.sol` : 87

- 源码 SHA256: `0196d033850b295690465d0f7d2baae8b3570df29c9d03d507496b45155a84e5`
- 精确证据身份 / difference_id: `f15c9065fefa002045696feba8d41b0cb58fb2a5fbbfc3ea2e4200ea51d96759`
- 原始行: 87; 字节区间: `[1491, 1503]`; 事件: `_adr DEF`; scope=`supported`
- 源码短片段: `address _adr`

v2候选: `DEF _adr`; 声明 `[1491, 1503] address _adr`; 函数起点 `1471`; IR事件 `0x01f8c4e3fa3edeb29e514cba738d87ce8c091d3f.sol:1471:e0`; kind=`entry`; 分析路径 `v2`; anchor=`{'file': '0x01f8c4e3fa3edeb29e514cba738d87ce8c091d3f.sol', 'start': 1471, 'end': 1698, 'role': 'function_definition'}`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `sealed_entry_initialization_tag`.

### 005 `0x01f8c4e3fa3edeb29e514cba738d87ce8c091d3f.sol` : 87

- 源码 SHA256: `0196d033850b295690465d0f7d2baae8b3570df29c9d03d507496b45155a84e5`
- 精确证据身份 / difference_id: `4d64777b6851c12fd4c6ba22e2d15465244340309d5ef18955c084584dc8686c`
- 原始行: 87; 字节区间: `[1504, 1513]`; 事件: `_val DEF`; scope=`supported`
- 源码短片段: `uint _val`

v2候选: `DEF _val`; 声明 `[1504, 1513] uint _val`; 函数起点 `1471`; IR事件 `0x01f8c4e3fa3edeb29e514cba738d87ce8c091d3f.sol:1471:e0`; kind=`entry`; 分析路径 `v2`; anchor=`{'file': '0x01f8c4e3fa3edeb29e514cba738d87ce8c091d3f.sol', 'start': 1471, 'end': 1698, 'role': 'function_definition'}`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `sealed_entry_initialization_tag`.

## 重入 / L1 / FP / declaration_without_initializer (5)

### 006 `0x4927643162fe6d18c7f046b3d155d8da0eee80e8.sol` : 148

- 源码 SHA256: `72f2f65fabb1882b877cd469def4062297f1127c0e99ea355a34d5fd57f053ef`
- 精确证据身份 / difference_id: `afd94b905f4848d5fbae47e9e24b7b23c8e7c8772621bef843cc7929fc794aaf`
- 原始行: 148; 字节区间: `[4435, 4455]`; 事件: `releaseTime DEF`; scope=`supported`
- 源码短片段: `uint256 releaseTime;`

v2候选: `DEF releaseTime`; 声明 `[4435, 4454] uint256 releaseTime`; 函数起点 `4053`; IR事件 `0x4927643162fe6d18c7f046b3d155d8da0eee80e8.sol:4053:e8`; kind=`declaration`; 分析路径 `v2`; anchor=`{'file': '0x4927643162fe6d18c7f046b3d155d8da0eee80e8.sol', 'start': 4435, 'end': 4455, 'role': 'variable_declaration_statement'}`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `DEF_in_exact_declaration_statement_without_value`.

### 007 `0x4927643162fe6d18c7f046b3d155d8da0eee80e8.sol` : 149

- 源码 SHA256: `72f2f65fabb1882b877cd469def4062297f1127c0e99ea355a34d5fd57f053ef`
- 精确证据身份 / difference_id: `5403c900c01c31332b52b997c6bdcc1333119f1cf3ee7fe8fc444559e6ec6f73`
- 原始行: 149; 字节区间: `[4460, 4479]`; 事件: `nolockRate DEF`; scope=`supported`
- 源码短片段: `uint256 nolockRate;`

v2候选: `DEF nolockRate`; 声明 `[4460, 4478] uint256 nolockRate`; 函数起点 `4053`; IR事件 `0x4927643162fe6d18c7f046b3d155d8da0eee80e8.sol:4053:e9`; kind=`declaration`; 分析路径 `v2`; anchor=`{'file': '0x4927643162fe6d18c7f046b3d155d8da0eee80e8.sol', 'start': 4460, 'end': 4479, 'role': 'variable_declaration_statement'}`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `DEF_in_exact_declaration_statement_without_value`.

### 008 `0x4927643162fe6d18c7f046b3d155d8da0eee80e8.sol` : 150

- 源码 SHA256: `72f2f65fabb1882b877cd469def4062297f1127c0e99ea355a34d5fd57f053ef`
- 精确证据身份 / difference_id: `7f4cb0ff33872b774ee7ea325de33408205315c045d87fd600b03cd765c287fd`
- 原始行: 150; 字节区间: `[4484, 4504]`; 事件: `releaseRate DEF`; scope=`supported`
- 源码短片段: `uint256 releaseRate;`

v2候选: `DEF releaseRate`; 声明 `[4484, 4503] uint256 releaseRate`; 函数起点 `4053`; IR事件 `0x4927643162fe6d18c7f046b3d155d8da0eee80e8.sol:4053:e10`; kind=`declaration`; 分析路径 `v2`; anchor=`{'file': '0x4927643162fe6d18c7f046b3d155d8da0eee80e8.sol', 'start': 4484, 'end': 4504, 'role': 'variable_declaration_statement'}`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `DEF_in_exact_declaration_statement_without_value`.

### 009 `buggy_21.sol` : 436

- 源码 SHA256: `7a25559a3b3670044bb18db38c2450a7ad4a2df3b88436a436922d79f4591355`
- 精确证据身份 / difference_id: `98dda0cff940e092ffdea86ea25d15f7458b22649c6b3039f4f5052298d87b4b`
- 原始行: 436; 字节区间: `[15273, 15290]`; 事件: `amount__ DEF`; scope=`supported`
- 源码短片段: `uint256 amount__;`

v2候选: `DEF amount__`; 声明 `[15273, 15289] uint256 amount__`; 函数起点 `14659`; IR事件 `buggy_21.sol:14659:e4`; kind=`declaration`; 分析路径 `v2`; anchor=`{'file': 'buggy_21.sol', 'start': 15273, 'end': 15290, 'role': 'variable_declaration_statement'}`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `DEF_in_exact_declaration_statement_without_value`.

### 010 `buggy_35.sol` : 589

- 源码 SHA256: `ef0be568a9870bd223f6a8665f09384d4458d3f0c41c716b6062219a131cc2a0`
- 精确证据身份 / difference_id: `5770c56bbfc3de8bacd493a921205931d69ec49191f19ab24c90163e7d589e3e`
- 原始行: 589; 字节区间: `[23745, 23761]`; 事件: `available1 DEF`; scope=`supported`
- 源码短片段: `uint available1;`

v2候选: `DEF available1`; 声明 `[23745, 23760] uint available1`; 函数起点 `23433`; IR事件 `buggy_35.sol:23433:e2`; kind=`declaration`; 分析路径 `legacy`; anchor=`{'file': 'buggy_35.sol', 'start': 23745, 'end': 23761, 'role': 'variable_declaration_statement'}`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `DEF_in_exact_declaration_statement_without_value`.

## 重入 / L1 / FP / other (5)

### 011 `0x980358360409b1cc913a916bc0bf6f52f775242a.sol` : 30

- 源码 SHA256: `c7b5cf3582ebd622ab9446faa418b984fe1137e6baa2848dde8389732bf8b120`
- 精确证据身份 / difference_id: `9a492ba9c6035132fd494f7afd6b0483051b0d365a6e913cad0d4ca4cb7a80e0`
- 原始行: 30; 字节区间: `[788, 796]`; 事件: `eosAddr USE`; scope=`supported`
- 源码短片段: `eosAddr;`

v2候选: `USE eosAddr`; 声明 `[714, 735] string memory eosAddr`; 函数起点 `690`; IR事件 `0x980358360409b1cc913a916bc0bf6f52f775242a.sol:690:e1`; kind=`expression`; 分析路径 `v2`; anchor=`{'file': '0x980358360409b1cc913a916bc0bf6f52f775242a.sol', 'start': 788, 'end': 796, 'role': 'expression_statement'}`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `no_prior_mechanical_predicate`.

此类别仅表示前序机械判据均未成立；不在本页自动判为分析器错误。

### 012 `buggy_24.sol` : 586

- 源码 SHA256: `56a65952a6be4eaf4f21d09d2e2c10d99dfebfb0cf85bf16b7e085af76197bdb`
- 精确证据身份 / difference_id: `c8bf26ed760dbf7a66802ce424022ead0f354e23fa4dccb439dcb0bd87e155ce`
- 原始行: 586; 字节区间: `[20296, 20320]`; 事件: `records USE`; scope=`supported`
- 源码短片段: `records[i] = prevRecord;`

v2候选: `USE records`; 声明 `[20113, 20144] InvestRecord[9] storage records`; 函数起点 `20004`; IR事件 `buggy_24.sol:20004:e6`; kind=`assignment`; 分析路径 `v2`; anchor=`{'file': 'buggy_24.sol', 'start': 20296, 'end': 20320, 'role': 'expression_statement'}`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `no_prior_mechanical_predicate`.

此类别仅表示前序机械判据均未成立；不在本页自动判为分析器错误。

### 013 `buggy_24.sol` : 588

- 源码 SHA256: `56a65952a6be4eaf4f21d09d2e2c10d99dfebfb0cf85bf16b7e085af76197bdb`
- 精确证据身份 / difference_id: `b718c9db09a076adf39554bef6a2e5964f7294396559ee9782739dc58b630855`
- 原始行: 588; 字节区间: `[20339, 20386]`; 事件: `records USE`; scope=`supported`
- 源码短片段: `records[0] = InvestRecord(time, amount, cycle);`

v2候选: `USE records`; 声明 `[20113, 20144] InvestRecord[9] storage records`; 函数起点 `20004`; IR事件 `buggy_24.sol:20004:e7`; kind=`assignment`; 分析路径 `v2`; anchor=`{'file': 'buggy_24.sol', 'start': 20339, 'end': 20386, 'role': 'expression_statement'}`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `no_prior_mechanical_predicate`.

此类别仅表示前序机械判据均未成立；不在本页自动判为分析器错误。

### 014 `buggy_24.sol` : 605

- 源码 SHA256: `56a65952a6be4eaf4f21d09d2e2c10d99dfebfb0cf85bf16b7e085af76197bdb`
- 精确证据身份 / difference_id: `26dafbd38e6e1fa0d9712488d16b76ae9b2d7a7e9b183c7f854b64033d92a61a`
- 原始行: 605; 字节区间: `[21125, 21149]`; 事件: `records USE`; scope=`supported`
- 源码短片段: `records[i] = prevRecord;`

v2候选: `USE records`; 声明 `[20924, 20959] CommissionRecord[9] storage records`; 函数起点 `20820`; IR事件 `buggy_24.sol:20820:e6`; kind=`assignment`; 分析路径 `v2`; anchor=`{'file': 'buggy_24.sol', 'start': 21125, 'end': 21149, 'role': 'expression_statement'}`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `no_prior_mechanical_predicate`.

此类别仅表示前序机械判据均未成立；不在本页自动判为分析器错误。

### 015 `buggy_24.sol` : 607

- 源码 SHA256: `56a65952a6be4eaf4f21d09d2e2c10d99dfebfb0cf85bf16b7e085af76197bdb`
- 精确证据身份 / difference_id: `2ce22f9b85aaf9a707f8a89bc4992e2b9194735a0bc29ccdc39d867e984213f5`
- 原始行: 607; 字节区间: `[21168, 21212]`; 事件: `records USE`; scope=`supported`
- 源码短片段: `records[0] = CommissionRecord(time, amount);`

v2候选: `USE records`; 声明 `[20924, 20959] CommissionRecord[9] storage records`; 函数起点 `20820`; IR事件 `buggy_24.sol:20820:e7`; kind=`assignment`; 分析路径 `v2`; anchor=`{'file': 'buggy_24.sol', 'start': 21168, 'end': 21212, 'role': 'expression_statement'}`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `no_prior_mechanical_predicate`.

此类别仅表示前序机械判据均未成立；不在本页自动判为分析器错误。

## 重入 / L1 / FN / v2_fallback (5)

### 016 `0x12345678979f29ebc99e00bdc5693ddea564ca80.sol` : 145

- 源码 SHA256: `91befce38f736998521fcbcfa1c6b42db1f71d1ba7a5cb2f0909273a73c92a64`
- 精确证据身份 / difference_id: `31bad553675889088f4008d4e7cc0942785bb9de07368701a7487fa53f218055`
- 原始行: 145; 字节区间: `[7171, 7187]`; 事件: `_active USE`; scope=`fallback`
- 源码短片段: `active = _active`

Slither参考: `USE _active`; CFG text=`active = _active`; 声明 `[7118, 7130] bool _active`; function=`Treasury.setActive(bool)`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `exact_function_start_status_fallback`.

### 017 `0x12345678979f29ebc99e00bdc5693ddea564ca80.sol` : 151

- 源码 SHA256: `91befce38f736998521fcbcfa1c6b42db1f71d1ba7a5cb2f0909273a73c92a64`
- 精确证据身份 / difference_id: `900c135b321b814826afc065c6b10550aa06eb24e8909b58b36ef3841ecc615d`
- 原始行: 151; 字节区间: `[7338, 7424]`; 事件: `tokenCode USE`; scope=`fallback`
- 源码短片段: `require (tokenCode != 0, "Token code of zero is reserved for Ether.")`

Slither参考: `USE tokenCode`; CFG text=`require (tokenCode != 0, "Token code of zero is reserved for Ether.")`; 声明 `[7258, 7274] uint16 tokenCode`; function=`Treasury.changeTokenInfo(uint16,address)`; context_count=1; 标签=`['multiline_cfg_location']`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `exact_function_start_status_fallback`.

### 018 `0x12345678979f29ebc99e00bdc5693ddea564ca80.sol` : 154

- 源码 SHA256: `91befce38f736998521fcbcfa1c6b42db1f71d1ba7a5cb2f0909273a73c92a64`
- 精确证据身份 / difference_id: `3b18fe014c07d0f59200ce30b935f334827ad8e7fcdb99b13a6d091a2df72cf8`
- 原始行: 154; 字节区间: `[7435, 7554]`; 事件: `tokenCode USE`; scope=`fallback`
- 源码短片段: `require (tokenContracts[tokenCode] == address(0), "Token contract address can be assigned only once.")`

Slither参考: `USE tokenCode`; CFG text=`require (tokenContracts[tokenCode] == address(0), "Token contract address can be assigned only once.")`; 声明 `[7258, 7274] uint16 tokenCode`; function=`Treasury.changeTokenInfo(uint16,address)`; context_count=1; 标签=`['multiline_cfg_location']`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `exact_function_start_status_fallback`.

### 019 `0x12345678979f29ebc99e00bdc5693ddea564ca80.sol` : 157

- 源码 SHA256: `91befce38f736998521fcbcfa1c6b42db1f71d1ba7a5cb2f0909273a73c92a64`
- 精确证据身份 / difference_id: `0c2a1593931cba317e908d22c8b6df9a5ed93cde42a243a29e188eb662a23d87`
- 原始行: 157; 字节区间: `[7565, 7606]`; 事件: `tokenContract USE`; scope=`fallback`
- 源码短片段: `tokenContracts[tokenCode] = tokenContract`

Slither参考: `USE tokenContract`; CFG text=`tokenContracts[tokenCode] = tokenContract`; 声明 `[7276, 7297] address tokenContract`; function=`Treasury.changeTokenInfo(uint16,address)`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `exact_function_start_status_fallback`.

### 020 `0x12345678979f29ebc99e00bdc5693ddea564ca80.sol` : 157

- 源码 SHA256: `91befce38f736998521fcbcfa1c6b42db1f71d1ba7a5cb2f0909273a73c92a64`
- 精确证据身份 / difference_id: `a63e5f03af33e9af53a8b7866b35e9d9a2c3b60ae3e4d25c1818457863d5d433`
- 原始行: 157; 字节区间: `[7565, 7606]`; 事件: `tokenCode USE`; scope=`fallback`
- 源码短片段: `tokenContracts[tokenCode] = tokenContract`

Slither参考: `USE tokenCode`; CFG text=`tokenContracts[tokenCode] = tokenContract`; 声明 `[7258, 7274] uint16 tokenCode`; function=`Treasury.changeTokenInfo(uint16,address)`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `exact_function_start_status_fallback`.

## 重入 / L1 / FN / other (5)

### 021 `0x12345678979f29ebc99e00bdc5693ddea564ca80.sol` : 41

- 源码 SHA256: `91befce38f736998521fcbcfa1c6b42db1f71d1ba7a5cb2f0909273a73c92a64`
- 精确证据身份 / difference_id: `3f442c722510d99ab499bc76d0583d3ae8f2caa4d3092bde14519eb1655ec292`
- 原始行: 41; 字节区间: `[1960, 2091]`; 事件: `trader USE`; scope=`unmapped`
- 源码短片段: `require (getRegistry().contractApproved(trader), "onlyApprovedExchange() requires approval of the latest contract code by trader.")`

Slither参考: `USE trader`; CFG text=`require (getRegistry().contractApproved(trader), "onlyApprovedExchange() requires approval of the latest contract code by trader.")`; 声明 `[1832, 1846] address trader`; function=`AccessModifiers.onlyApprovedExchange(address)`; context_count=2; 标签=`['inheritance', 'modifier_inlining']`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `no_prior_mechanical_predicate`.

此类别仅表示前序机械判据均未成立；不在本页自动判为分析器错误。

### 022 `0x12345678979f29ebc99e00bdc5693ddea564ca80.sol` : 48

- 源码 SHA256: `91befce38f736998521fcbcfa1c6b42db1f71d1ba7a5cb2f0909273a73c92a64`
- 精确证据身份 / difference_id: `679d68ab60a8220f7ef74ae706cd49021cdb41f6974b662db9aad25df92db3b5`
- 原始行: 48; 字节区间: `[2373, 2528]`; 事件: `trader1 USE`; scope=`unmapped`
- 源码短片段: `require (getRegistry().contractApprovedBoth(trader1, trader2), "onlyApprovedExchangeBoth() requires approval of the latest contract code by both traders.")`

Slither参考: `USE trader1`; CFG text=`require (getRegistry().contractApprovedBoth(trader1, trader2), "onlyApprovedExchangeBoth() requires approval of the latest contract code by both traders.")`; 声明 `[2227, 2242] address trader1`; function=`AccessModifiers.onlyApprovedExchangeBoth(address,address)`; context_count=2; 标签=`['inheritance', 'modifier_inlining']`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `no_prior_mechanical_predicate`.

此类别仅表示前序机械判据均未成立；不在本页自动判为分析器错误。

### 023 `0x12345678979f29ebc99e00bdc5693ddea564ca80.sol` : 48

- 源码 SHA256: `91befce38f736998521fcbcfa1c6b42db1f71d1ba7a5cb2f0909273a73c92a64`
- 精确证据身份 / difference_id: `44f368b334fd8a52a4612451dc54f3d4d262506b6a1488bd2dc2d6c2e293ea22`
- 原始行: 48; 字节区间: `[2373, 2528]`; 事件: `trader2 USE`; scope=`unmapped`
- 源码短片段: `require (getRegistry().contractApprovedBoth(trader1, trader2), "onlyApprovedExchangeBoth() requires approval of the latest contract code by both traders.")`

Slither参考: `USE trader2`; CFG text=`require (getRegistry().contractApprovedBoth(trader1, trader2), "onlyApprovedExchangeBoth() requires approval of the latest contract code by both traders.")`; 声明 `[2244, 2259] address trader2`; function=`AccessModifiers.onlyApprovedExchangeBoth(address,address)`; context_count=2; 标签=`['inheritance', 'modifier_inlining']`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `no_prior_mechanical_predicate`.

此类别仅表示前序机械判据均未成立；不在本页自动判为分析器错误。

### 024 `0x12345678979f29ebc99e00bdc5693ddea564ca80.sol` : 137

- 源码 SHA256: `91befce38f736998521fcbcfa1c6b42db1f71d1ba7a5cb2f0909273a73c92a64`
- 精确证据身份 / difference_id: `cbe22c9e1a70a01d6661342fc44984d07b3246bd728738c41c5b4c9cf322e5c7`
- 原始行: 137; 字节区间: `[6864, 6909]`; 事件: `trader USE`; scope=`unmapped`
- 源码短片段: `uint deadline = emergencyReleaseSince[trader]`

Slither参考: `USE trader`; CFG text=`uint deadline = emergencyReleaseSince[trader]`; 声明 `[6838, 6852] address trader`; function=`Treasury.emergencyReleasePossible(address)`; context_count=1; 标签=`['modifier_inlining']`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `no_prior_mechanical_predicate`.

此类别仅表示前序机械判据均未成立；不在本页自动判为分析器错误。

### 025 `0x12345678979f29ebc99e00bdc5693ddea564ca80.sol` : 137

- 源码 SHA256: `91befce38f736998521fcbcfa1c6b42db1f71d1ba7a5cb2f0909273a73c92a64`
- 精确证据身份 / difference_id: `56613918e2855e19ad2dea0aeeed265ea74aa1a136a4ea9a32c261da623248d2`
- 原始行: 137; 字节区间: `[6864, 6909]`; 事件: `deadline DEF`; scope=`unmapped`
- 源码短片段: `uint deadline = emergencyReleaseSince[trader]`

Slither参考: `DEF deadline`; CFG text=`uint deadline = emergencyReleaseSince[trader]`; 声明 `[6864, 6909] uint deadline = emergencyReleaseSince[trader]`; function=`Treasury.emergencyReleasePossible(address)`; context_count=1; 标签=`['modifier_inlining']`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `no_prior_mechanical_predicate`.

此类别仅表示前序机械判据均未成立；不在本页自动判为分析器错误。

## 重入 / L2 / FP / alias (5)

### 026 `0x7541b76cb60f4c60af330c208b0623b7f54bf615.sol` : 16

- 源码 SHA256: `5bb1f99cb610a037d71ed227b6ee68e9d76eaf4846e8c67952919ca11b0ec0ee`
- 精确证据身份 / difference_id: `81e8b7e63eba3c247dce5222bc5cefbda809d3fdcda2b3cede4d774f0cf05f76`
- 原始行: 16; 字节区间: `[227, 238]`; 事件: `Acc READ`; scope=`supported`
- 源码短片段: `acc.balance`

v2候选: `READ Acc`; 声明 `[935, 974] mapping (address => Holder) public Acc;`; 函数起点 `124`; relation=`READS_STATE`; status=`projected`; via_alias=`True`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `sealed_6c_tag`.

### 027 `0x7541b76cb60f4c60af330c208b0623b7f54bf615.sol` : 26

- 源码 SHA256: `5bb1f99cb610a037d71ed227b6ee68e9d76eaf4846e8c67952919ca11b0ec0ee`
- 精确证据身份 / difference_id: `6690e20a639c59c44bdf5d9a00c65804f7c1be3db77efa37f4aed62c3d041708`
- 原始行: 26; 字节区间: `[481, 492]`; 事件: `Acc READ`; scope=`supported`
- 源码短片段: `acc.balance`

v2候选: `READ Acc`; 声明 `[935, 974] mapping (address => Holder) public Acc;`; 函数起点 `378`; relation=`READS_STATE`; status=`projected`; via_alias=`True`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `sealed_6c_tag`.

### 028 `0x7541b76cb60f4c60af330c208b0623b7f54bf615.sol` : 26

- 源码 SHA256: `5bb1f99cb610a037d71ed227b6ee68e9d76eaf4846e8c67952919ca11b0ec0ee`
- 精确证据身份 / difference_id: `a4e9a60ed492b78102274646d99e35bb1226a9499eb2c457590ddcd27c542451`
- 原始行: 26; 字节区间: `[528, 542]`; 事件: `Acc READ`; scope=`supported`
- 源码短片段: `acc.unlockTime`

v2候选: `READ Acc`; 声明 `[935, 974] mapping (address => Holder) public Acc;`; 函数起点 `378`; relation=`READS_STATE`; status=`projected`; via_alias=`True`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `sealed_6c_tag`.

### 029 `0x7541b76cb60f4c60af330c208b0623b7f54bf615.sol` : 31

- 源码 SHA256: `5bb1f99cb610a037d71ed227b6ee68e9d76eaf4846e8c67952919ca11b0ec0ee`
- 精确证据身份 / difference_id: `86c627b1922648e09d53effa0cd5eba6357f2e5bc04f27f0e42dcfb43b7a92e9`
- 原始行: 31; 字节区间: `[670, 681]`; 事件: `Acc READ`; scope=`supported`
- 源码短片段: `acc.balance`

v2候选: `READ Acc`; 声明 `[935, 974] mapping (address => Holder) public Acc;`; 函数起点 `378`; relation=`READS_STATE`; status=`projected`; via_alias=`True`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `sealed_6c_tag`.

### 030 `0x7b368c4e805c3870b6c49a3f1f49f69af8662cf3.sol` : 16

- 源码 SHA256: `df9a3f0d481d394c2d03d72853c6091be2acab93cd8f3512fbf7244dbb2d3118`
- 精确证据身份 / difference_id: `e61baeb167044dee04920a2d2fb8b2a998e76eff8cd4caae1636e2b6b2ec5464`
- 原始行: 16; 字节区间: `[229, 240]`; 事件: `Acc READ`; scope=`supported`
- 源码短片段: `acc.balance`

v2候选: `READ Acc`; 声明 `[937, 976] mapping (address => Holder) public Acc;`; 函数起点 `126`; relation=`READS_STATE`; status=`projected`; via_alias=`True`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `sealed_6c_tag`.

## 重入 / L2 / FP / other (5)

### 031 `0x01f8c4e3fa3edeb29e514cba738d87ce8c091d3f.sol` : 51

- 源码 SHA256: `0196d033850b295690465d0f7d2baae8b3570df29c9d03d507496b45155a84e5`
- 精确证据身份 / difference_id: `fc2779652b2605550939e1d25eb584232d866e766eb026cff97301c2c4d28cd8`
- 原始行: 51; 字节区间: `[913, 921]`; 事件: `balances READ`; scope=`supported`
- 源码短片段: `balances`

v2候选: `READ balances`; 声明 `[131, 174] mapping (address=>uint256) public balances;`; 函数起点 `814`; relation=`READS_STATE`; status=`projected`; via_alias=`False`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `no_prior_mechanical_predicate`.

此类别仅表示前序机械判据均未成立；不在本页自动判为分析器错误。

### 032 `0x12345678982cb986dd291b50239295e3cb10cdf6.sol` : 142

- 源码 SHA256: `9244254fab737e50d9585933f32d9ae8c0dced6bc554544bb2faf9ffa51c0f27`
- 精确证据身份 / difference_id: `12f8ec6cd2eceb11e2707b331153db9e104d6af53010ab8495a9440f322922b4`
- 原始行: 142; 字节区间: `[6015, 6038]`; 事件: `exchangeContractVersion READ`; scope=`supported`
- 源码短片段: `exchangeContractVersion`

v2候选: `READ exchangeContractVersion`; 声明 `[2193, 2230] uint private exchangeContractVersion;`; 函数起点 `5607`; relation=`READS_STATE`; status=`projected`; via_alias=`False`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `no_prior_mechanical_predicate`.

此类别仅表示前序机械判据均未成立；不在本页自动判为分析器错误。

### 033 `0x12345678982cb986dd291b50239295e3cb10cdf6.sol` : 142

- 源码 SHA256: `9244254fab737e50d9585933f32d9ae8c0dced6bc554544bb2faf9ffa51c0f27`
- 精确证据身份 / difference_id: `507f4dd01ba0ff15e1562c55bd42153cab962516fc6778a0d3b8d4aa612daf8d`
- 原始行: 142; 字节区间: `[6042, 6057]`; 事件: `traderApprovals READ`; scope=`supported`
- 源码短片段: `traderApprovals`

v2候选: `READ traderApprovals`; 声明 `[3277, 3327] mapping (address => uint) private traderApprovals;`; 函数起点 `5607`; relation=`READS_STATE`; status=`projected`; via_alias=`False`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `no_prior_mechanical_predicate`.

此类别仅表示前序机械判据均未成立；不在本页自动判为分析器错误。

### 034 `0x198482924b5ed2c8dd5a0c824fcd618c6b49e6e8.sol` : 217

- 源码 SHA256: `148fd81c72eab98cca6a7f34a6658633b0eb64b29ba73c7eb7d88670100e9888`
- 精确证据身份 / difference_id: `c3ade39eb81615671660c549ba3d6ca396af84e38fd19ea77cf6fe286ce3bdcb`
- 原始行: 217; 字节区间: `[6592, 6597]`; 事件: `owner READ`; scope=`supported`
- 源码短片段: `owner`

v2候选: `READ owner`; 声明 `[2257, 2278] address public owner;`; 函数起点 `6455`; relation=`READS_STATE`; status=`projected`; via_alias=`False`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `no_prior_mechanical_predicate`.

此类别仅表示前序机械判据均未成立；不在本页自动判为分析器错误。

### 035 `0x198482924b5ed2c8dd5a0c824fcd618c6b49e6e8.sol` : 218

- 源码 SHA256: `148fd81c72eab98cca6a7f34a6658633b0eb64b29ba73c7eb7d88670100e9888`
- 精确证据身份 / difference_id: `5a7c07dd02db73e402c93a0cacdcf6bf1f7af23b89f1d463102bb29ff58c99cf`
- 原始行: 218; 字节区间: `[6660, 6675]`; 事件: `contractAddress READ`; scope=`supported`
- 源码短片段: `contractAddress`

v2候选: `READ contractAddress`; 声明 `[3477, 3509] address private contractAddress;`; 函数起点 `6455`; relation=`READS_STATE`; status=`projected`; via_alias=`False`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `no_prior_mechanical_predicate`.

此类别仅表示前序机械判据均未成立；不在本页自动判为分析器错误。

## 重入 / L2 / FN / constant_excluded (5)

### 036 `0x12345678979f29ebc99e00bdc5693ddea564ca80.sol` : 10

- 源码 SHA256: `91befce38f736998521fcbcfa1c6b42db1f71d1ba7a5cb2f0909273a73c92a64`
- 精确证据身份 / difference_id: `a1c32416ba18320f90b916d0baf985355b9a9c0e2f86a4b98a4810c71d7039d8`
- 原始行: 10; 字节区间: `[487, 561]`; 事件: `ProxyAddress WRITE`; scope=`unmapped`
- 源码短片段: `address constant ProxyAddress = 0x1234567896326230a28ee368825D11fE6571Be4a`

Slither参考: `WRITE ProxyAddress`; CFG text=`address constant ProxyAddress = 0x1234567896326230a28ee368825D11fE6571Be4a`; 声明 `[487, 561] address constant ProxyAddress = 0x1234567896326230a28ee368825D11fE6571Be4a`; function=`AccessModifiers.slitherConstructorConstantVariables()`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `is_constant_or_exact_constant_declaration`.

### 037 `0x12345678979f29ebc99e00bdc5693ddea564ca80.sol` : 10

- 源码 SHA256: `91befce38f736998521fcbcfa1c6b42db1f71d1ba7a5cb2f0909273a73c92a64`
- 精确证据身份 / difference_id: `be94228e5db6c98a012b071ba948efef8b8cfb0b20d5d62fdaea4e4644a66063`
- 原始行: 10; 字节区间: `[487, 561]`; 事件: `ProxyAddress WRITE`; scope=`unmapped`
- 源码短片段: `address constant ProxyAddress = 0x1234567896326230a28ee368825D11fE6571Be4a`

Slither参考: `WRITE ProxyAddress`; CFG text=`address constant ProxyAddress = 0x1234567896326230a28ee368825D11fE6571Be4a`; 声明 `[487, 561] address constant ProxyAddress = 0x1234567896326230a28ee368825D11fE6571Be4a`; function=`Treasury.slitherConstructorConstantVariables()`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `is_constant_or_exact_constant_declaration`.

### 038 `0x12345678979f29ebc99e00bdc5693ddea564ca80.sol` : 10

- 源码 SHA256: `91befce38f736998521fcbcfa1c6b42db1f71d1ba7a5cb2f0909273a73c92a64`
- 精确证据身份 / difference_id: `93ce19feb4fb063e15c1eb361335e164b0b36ac5db91d030c957b82a6b3dc912`
- 原始行: 10; 字节区间: `[487, 561]`; 事件: `ProxyAddress WRITE`; scope=`unmapped`
- 源码短片段: `address constant ProxyAddress = 0x1234567896326230a28ee368825D11fE6571Be4a`

Slither参考: `WRITE ProxyAddress`; CFG text=`address constant ProxyAddress = 0x1234567896326230a28ee368825D11fE6571Be4a`; 声明 `[487, 561] address constant ProxyAddress = 0x1234567896326230a28ee368825D11fE6571Be4a`; function=`FixedAddress.slitherConstructorConstantVariables()`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `is_constant_or_exact_constant_declaration`.

### 039 `0x12345678979f29ebc99e00bdc5693ddea564ca80.sol` : 11

- 源码 SHA256: `91befce38f736998521fcbcfa1c6b42db1f71d1ba7a5cb2f0909273a73c92a64`
- 精确证据身份 / difference_id: `51acb61587d3be954bd9702d3e36a026a100c5bdd09f948a05d3df6096016234`
- 原始行: 11; 字节区间: `[567, 644]`; 事件: `TreasuryAddress WRITE`; scope=`unmapped`
- 源码短片段: `address constant TreasuryAddress = 0x12345678979f29eBc99E00bdc5693ddEa564cA80`

Slither参考: `WRITE TreasuryAddress`; CFG text=`address constant TreasuryAddress = 0x12345678979f29eBc99E00bdc5693ddEa564cA80`; 声明 `[567, 644] address constant TreasuryAddress = 0x12345678979f29eBc99E00bdc5693ddEa564cA80`; function=`AccessModifiers.slitherConstructorConstantVariables()`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `is_constant_or_exact_constant_declaration`.

### 040 `0x12345678979f29ebc99e00bdc5693ddea564ca80.sol` : 11

- 源码 SHA256: `91befce38f736998521fcbcfa1c6b42db1f71d1ba7a5cb2f0909273a73c92a64`
- 精确证据身份 / difference_id: `1f97d032a3a24e85adf8a850e69240f0ee605004f3d44bd38708636a94ff4314`
- 原始行: 11; 字节区间: `[567, 644]`; 事件: `TreasuryAddress WRITE`; scope=`unmapped`
- 源码短片段: `address constant TreasuryAddress = 0x12345678979f29eBc99E00bdc5693ddEa564cA80`

Slither参考: `WRITE TreasuryAddress`; CFG text=`address constant TreasuryAddress = 0x12345678979f29eBc99E00bdc5693ddEa564cA80`; 声明 `[567, 644] address constant TreasuryAddress = 0x12345678979f29eBc99E00bdc5693ddEa564cA80`; function=`Treasury.slitherConstructorConstantVariables()`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `is_constant_or_exact_constant_declaration`.

## 重入 / L2 / FN / state_initializer (5)

### 041 `0x01f8c4e3fa3edeb29e514cba738d87ce8c091d3f.sol` : 13

- 源码 SHA256: `0196d033850b295690465d0f7d2baae8b3570df29c9d03d507496b45155a84e5`
- 精确证据身份 / difference_id: `66ebdb7a3a0a97598a0e70105d2860e16e89ea0721809360a0a8f231d51c4fd5`
- 原始行: 13; 字节区间: `[186, 214]`; 事件: `MinSum WRITE`; scope=`unmapped`
- 源码短片段: `uint public MinSum = 1 ether`

Slither参考: `WRITE MinSum`; CFG text=`uint public MinSum = 1 ether`; 声明 `[186, 214] uint public MinSum = 1 ether`; function=`PERSONAL_BANK.slitherConstructorVariables()`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `synthetic_constructor_or_state_declaration_span`.

### 042 `0x01f8c4e3fa3edeb29e514cba738d87ce8c091d3f.sol` : 15

- 源码 SHA256: `0196d033850b295690465d0f7d2baae8b3570df29c9d03d507496b45155a84e5`
- 精确证据身份 / difference_id: `c7c4d3bc56956952b312f0debd0a3a916d603f617a4e3cc8b04cd66c180d7491`
- 原始行: 15; 字节区间: `[225, 290]`; 事件: `Log WRITE`; scope=`unmapped`
- 源码短片段: `LogFile Log = LogFile(0x0486cF65A2F2F3A392CBEa398AFB7F5f0B72FF46)`

Slither参考: `WRITE Log`; CFG text=`LogFile Log = LogFile(0x0486cF65A2F2F3A392CBEa398AFB7F5f0B72FF46)`; 声明 `[225, 290] LogFile Log = LogFile(0x0486cF65A2F2F3A392CBEa398AFB7F5f0B72FF46)`; function=`PERSONAL_BANK.slitherConstructorVariables()`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `synthetic_constructor_or_state_declaration_span`.

### 043 `0x12345678979f29ebc99e00bdc5693ddea564ca80.sol` : 99

- 源码 SHA256: `91befce38f736998521fcbcfa1c6b42db1f71d1ba7a5cb2f0909273a73c92a64`
- 精确证据身份 / difference_id: `6ab865a632f6dee73f1aa0b9cc1803f8b20a1d594b9844bc485aa9269fdf05de`
- 原始行: 99; 字节区间: `[5437, 5456]`; 事件: `active WRITE`; scope=`unmapped`
- 源码短片段: `bool active = false`

Slither参考: `WRITE active`; CFG text=`bool active = false`; 声明 `[5437, 5456] bool active = false`; function=`Treasury.slitherConstructorVariables()`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `synthetic_constructor_or_state_declaration_span`.

### 044 `0x173566176a1deebb47569c8366e84ba7b10b3b8b.sol` : 116

- 源码 SHA256: `090d4794a6139bbd1320b8012db06847057fec25d9da2f82c115337fc2ff0873`
- 精确证据身份 / difference_id: `310a2a31ee2acbe144960153bf2a9de8f41e0e32ba8483e72745bf6dda97492e`
- 原始行: 116; 字节区间: `[3213, 3243]`; 事件: `isCrowdsalePaused WRITE`; scope=`unmapped`
- 源码短片段: `bool isCrowdsalePaused = false`

Slither参考: `WRITE isCrowdsalePaused`; CFG text=`bool isCrowdsalePaused = false`; 声明 `[3213, 3243] bool isCrowdsalePaused = false`; function=`KRCPreSaleContract.slitherConstructorVariables()`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `synthetic_constructor_or_state_declaration_span`.

### 045 `0x173566176a1deebb47569c8366e84ba7b10b3b8b.sol` : 118

- 源码 SHA256: `090d4794a6139bbd1320b8012db06847057fec25d9da2f82c115337fc2ff0873`
- 精确证据身份 / difference_id: `519bf58cfa98ee1629d602625fcbdb2e3c1d0b3291285a8583e6c9fda555f7e5`
- 原始行: 118; 字节区间: `[3250, 3287]`; 事件: `totalDurationInDays WRITE`; scope=`unmapped`
- 源码短片段: `uint256 totalDurationInDays = 30 days`

Slither参考: `WRITE totalDurationInDays`; CFG text=`uint256 totalDurationInDays = 30 days`; 声明 `[3250, 3287] uint256 totalDurationInDays = 30 days`; function=`KRCPreSaleContract.slitherConstructorVariables()`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `synthetic_constructor_or_state_declaration_span`.

## 重入 / L2 / FN / write_base_read (5)

### 046 `0x01f8c4e3fa3edeb29e514cba738d87ce8c091d3f.sol` : 90

- 源码 SHA256: `0196d033850b295690465d0f7d2baae8b3570df29c9d03d507496b45155a84e5`
- 精确证据身份 / difference_id: `095a57b648c8b49667a3064208b3be6460aab1538fa25e1e390f073d6ed1e2c4`
- 原始行: 90; 字节区间: `[1553, 1574]`; 事件: `LastMsg READ`; scope=`supported`
- 源码短片段: `LastMsg.Sender = _adr`

Slither参考: `READ LastMsg`; CFG text=`LastMsg.Sender = _adr`; 声明 `[1445, 1460] Message LastMsg`; function=`LogFile.AddMessage(address,uint256,string)`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `same_node_chain_root_WRITE_without_READ`.

判据引用的v2写入（类型不同，**不是该READ的配对**）: `LastMsg WRITE` `[1553, 1567]` `LastMsg.Sender`; 声明 `[1445, 1461] Message LastMsg;`.

### 047 `0x01f8c4e3fa3edeb29e514cba738d87ce8c091d3f.sol` : 91

- 源码 SHA256: `0196d033850b295690465d0f7d2baae8b3570df29c9d03d507496b45155a84e5`
- 精确证据身份 / difference_id: `bb969bbda2d013d8e6f3c3f4f184099afda0b5417c60fe43b167cab41109fefd`
- 原始行: 91; 字节区间: `[1584, 1602]`; 事件: `LastMsg READ`; scope=`supported`
- 源码短片段: `LastMsg.Time = now`

Slither参考: `READ LastMsg`; CFG text=`LastMsg.Time = now`; 声明 `[1445, 1460] Message LastMsg`; function=`LogFile.AddMessage(address,uint256,string)`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `same_node_chain_root_WRITE_without_READ`.

判据引用的v2写入（类型不同，**不是该READ的配对**）: `LastMsg WRITE` `[1584, 1596]` `LastMsg.Time`; 声明 `[1445, 1461] Message LastMsg;`.

### 048 `0x01f8c4e3fa3edeb29e514cba738d87ce8c091d3f.sol` : 92

- 源码 SHA256: `0196d033850b295690465d0f7d2baae8b3570df29c9d03d507496b45155a84e5`
- 精确证据身份 / difference_id: `7c5772db19d3562bb7bd54f37dbd452c9ccb9a221a60493be994e076b39c02c6`
- 原始行: 92; 字节区间: `[1612, 1630]`; 事件: `LastMsg READ`; scope=`supported`
- 源码短片段: `LastMsg.Val = _val`

Slither参考: `READ LastMsg`; CFG text=`LastMsg.Val = _val`; 声明 `[1445, 1460] Message LastMsg`; function=`LogFile.AddMessage(address,uint256,string)`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `same_node_chain_root_WRITE_without_READ`.

判据引用的v2写入（类型不同，**不是该READ的配对**）: `LastMsg WRITE` `[1612, 1623]` `LastMsg.Val`; 声明 `[1445, 1461] Message LastMsg;`.

### 049 `0x01f8c4e3fa3edeb29e514cba738d87ce8c091d3f.sol` : 93

- 源码 SHA256: `0196d033850b295690465d0f7d2baae8b3570df29c9d03d507496b45155a84e5`
- 精确证据身份 / difference_id: `29774afc5797f1eeac7aa252bdfb3c6f9e55510443289f0c69ae35e88095efc7`
- 原始行: 93; 字节区间: `[1640, 1660]`; 事件: `LastMsg READ`; scope=`supported`
- 源码短片段: `LastMsg.Data = _data`

Slither参考: `READ LastMsg`; CFG text=`LastMsg.Data = _data`; 声明 `[1445, 1460] Message LastMsg`; function=`LogFile.AddMessage(address,uint256,string)`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `same_node_chain_root_WRITE_without_READ`.

判据引用的v2写入（类型不同，**不是该READ的配对**）: `LastMsg WRITE` `[1640, 1652]` `LastMsg.Data`; 声明 `[1445, 1461] Message LastMsg;`.

### 050 `0x23a91059fdc9579a9fbd0edc5f2ea0bfdb70deb4.sol` : 68

- 源码 SHA256: `bcd0fdfad9f6594fdbc940967321856490ed4bffbe8b6ab9c75c6b85072528a5`
- 精确证据身份 / difference_id: `d3e88dc244276f884ae1e6fd5abdbdef3c33e2ba8e881468ae751286007ae045`
- 原始行: 68; 字节区间: `[1239, 1260]`; 事件: `LastMsg READ`; scope=`supported`
- 源码短片段: `LastMsg.Sender = _adr`

Slither参考: `READ LastMsg`; CFG text=`LastMsg.Sender = _adr`; 声明 `[1131, 1146] Message LastMsg`; function=`Log.AddMessage(address,uint256,string)`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `same_node_chain_root_WRITE_without_READ`.

判据引用的v2写入（类型不同，**不是该READ的配对**）: `LastMsg WRITE` `[1239, 1253]` `LastMsg.Sender`; 声明 `[1131, 1147] Message LastMsg;`.

## 重入 / L2 / FN / alias (2)

### 051 `buggy_24.sol` : 939

- 源码 SHA256: `56a65952a6be4eaf4f21d09d2e2c10d99dfebfb0cf85bf16b7e085af76197bdb`
- 精确证据身份 / difference_id: `2e9cab626e2177704bf5f425f7ef377d70f2b9fc60939881ed9b504e36579cb7`
- 原始行: 939; 字节区间: `[38385, 38421]`; 事件: `userMapping WRITE`; scope=`supported`
- 源码短片段: `user.calcDynamicCommissionAmount = 0`

Slither参考: `WRITE userMapping`; CFG text=`user.calcDynamicCommissionAmount = 0`; 声明 `[10633, 10678] mapping (address => User) private userMapping`; function=`FomoFeast.calcDynamicCommission()`; context_count=1; 标签=`['alias']`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `sealed_6c_tag`.

### 052 `buggy_24.sol` : 981

- 源码 SHA256: `56a65952a6be4eaf4f21d09d2e2c10d99dfebfb0cf85bf16b7e085af76197bdb`
- 精确证据身份 / difference_id: `f8c70ad1d33fece4e3e343bd882183c23045cdec3cd8460ccdc9737d9f875386`
- 原始行: 981; 字节区间: `[40745, 40844]`; 事件: `userMapping WRITE`; scope=`supported`
- 源码短片段: `user.dynamicCommissionBalance = user.dynamicCommissionBalance.add(user.calcDynamicCommissionAmount)`

Slither参考: `WRITE userMapping`; CFG text=`user.dynamicCommissionBalance = user.dynamicCommissionBalance.add(user.calcDynamicCommissionAmount)`; 声明 `[10633, 10678] mapping (address => User) private userMapping`; function=`FomoFeast.calcDynamicCommission()`; context_count=1; 标签=`['alias']`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `sealed_6c_tag`.

## 重入 / L2 / FN / v2_binding_unresolved (5)

### 053 `0x424646690d85aae60bb1f14c7a7c0ae98c459593.sol` : 75

- 源码 SHA256: `e13a04bb0fc4c68cbee5d0ec138e35c648cbffb8f13d182f9bac6ab7a82aecdc`
- 精确证据身份 / difference_id: `7d62973f3d2a46a760263bd2589e71f09b7ad4dbf0a51d425b00a2b3abc474e8`
- 原始行: 75; 字节区间: `[1968, 2052]`; 事件: `balanceOf READ`; scope=`fallback`
- 源码短片段: `require(balanceOf[msg.sender] >= _value && balanceOf[_to] + _value > balanceOf[_to])`

Slither参考: `READ balanceOf`; CFG text=`require(balanceOf[msg.sender] >= _value && balanceOf[_to] + _value > balanceOf[_to])`; 声明 `[1528, 1573] mapping (address => uint256) public balanceOf`; function=`StandardToken.transfer(address,uint256)`; context_count=2; 标签=`['inheritance']`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `same_name_overlapping_sealed_binding_diagnostic`.

判据引用诊断: `state_binding_unresolved` / `state_name_ambiguous` / name=`balanceOf` / `[1976, 1985]`; `state_binding_unresolved` / `state_name_ambiguous` / name=`balanceOf` / `[2011, 2020]`; `state_binding_unresolved` / `state_name_ambiguous` / name=`balanceOf` / `[2037, 2046]`.

### 054 `0x424646690d85aae60bb1f14c7a7c0ae98c459593.sol` : 77

- 源码 SHA256: `e13a04bb0fc4c68cbee5d0ec138e35c648cbffb8f13d182f9bac6ab7a82aecdc`
- 精确证据身份 / difference_id: `b9fdc4ae915667dd0886ff5cc04629ef13cc7300bb9d8c3c639008695b83e286`
- 原始行: 77; 字节区间: `[2072, 2134]`; 事件: `balanceOf READ`; scope=`fallback`
- 源码短片段: `balanceOf[msg.sender] = safeSub(balanceOf[msg.sender], _value)`

Slither参考: `READ balanceOf`; CFG text=`balanceOf[msg.sender] = safeSub(balanceOf[msg.sender], _value)`; 声明 `[1528, 1573] mapping (address => uint256) public balanceOf`; function=`StandardToken.transfer(address,uint256)`; context_count=2; 标签=`['inheritance']`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `same_name_overlapping_sealed_binding_diagnostic`.

判据引用诊断: `state_binding_unresolved` / `state_name_ambiguous` / name=`balanceOf` / `[2072, 2081]`; `state_binding_unresolved` / `state_name_ambiguous` / name=`balanceOf` / `[2104, 2113]`.

### 055 `0x424646690d85aae60bb1f14c7a7c0ae98c459593.sol` : 77

- 源码 SHA256: `e13a04bb0fc4c68cbee5d0ec138e35c648cbffb8f13d182f9bac6ab7a82aecdc`
- 精确证据身份 / difference_id: `24449d1897ed1117c5c5326c5836586ba9c9915b50aca3768be666ebf1f239da`
- 原始行: 77; 字节区间: `[2072, 2134]`; 事件: `balanceOf WRITE`; scope=`fallback`
- 源码短片段: `balanceOf[msg.sender] = safeSub(balanceOf[msg.sender], _value)`

Slither参考: `WRITE balanceOf`; CFG text=`balanceOf[msg.sender] = safeSub(balanceOf[msg.sender], _value)`; 声明 `[1528, 1573] mapping (address => uint256) public balanceOf`; function=`StandardToken.transfer(address,uint256)`; context_count=2; 标签=`['inheritance']`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `same_name_overlapping_sealed_binding_diagnostic`.

判据引用诊断: `state_binding_unresolved` / `state_name_ambiguous` / name=`balanceOf` / `[2072, 2081]`; `state_binding_unresolved` / `state_name_ambiguous` / name=`balanceOf` / `[2104, 2113]`.

### 056 `0x424646690d85aae60bb1f14c7a7c0ae98c459593.sol` : 78

- 源码 SHA256: `e13a04bb0fc4c68cbee5d0ec138e35c648cbffb8f13d182f9bac6ab7a82aecdc`
- 精确证据身份 / difference_id: `958b4f640a1dbd251b173824b9eeb5ecda9d29bb166c7ebc80de6a6f47cfc4c3`
- 原始行: 78; 字节区间: `[2144, 2192]`; 事件: `balanceOf WRITE`; scope=`fallback`
- 源码短片段: `balanceOf[_to] = safeAdd(balanceOf[_to], _value)`

Slither参考: `WRITE balanceOf`; CFG text=`balanceOf[_to] = safeAdd(balanceOf[_to], _value)`; 声明 `[1528, 1573] mapping (address => uint256) public balanceOf`; function=`StandardToken.transfer(address,uint256)`; context_count=2; 标签=`['inheritance']`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `same_name_overlapping_sealed_binding_diagnostic`.

判据引用诊断: `state_binding_unresolved` / `state_name_ambiguous` / name=`balanceOf` / `[2144, 2153]`; `state_binding_unresolved` / `state_name_ambiguous` / name=`balanceOf` / `[2169, 2178]`.

### 057 `0x424646690d85aae60bb1f14c7a7c0ae98c459593.sol` : 78

- 源码 SHA256: `e13a04bb0fc4c68cbee5d0ec138e35c648cbffb8f13d182f9bac6ab7a82aecdc`
- 精确证据身份 / difference_id: `8354abdfed22465f2375f6b07b1c9efa751741d56a69ae3528f53df8510596e0`
- 原始行: 78; 字节区间: `[2144, 2192]`; 事件: `balanceOf READ`; scope=`fallback`
- 源码短片段: `balanceOf[_to] = safeAdd(balanceOf[_to], _value)`

Slither参考: `READ balanceOf`; CFG text=`balanceOf[_to] = safeAdd(balanceOf[_to], _value)`; 声明 `[1528, 1573] mapping (address => uint256) public balanceOf`; function=`StandardToken.transfer(address,uint256)`; context_count=2; 标签=`['inheritance']`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `same_name_overlapping_sealed_binding_diagnostic`.

判据引用诊断: `state_binding_unresolved` / `state_name_ambiguous` / name=`balanceOf` / `[2144, 2153]`; `state_binding_unresolved` / `state_name_ambiguous` / name=`balanceOf` / `[2169, 2178]`.

## 访问控制 / L1 / FP / entry_initialization (5)

### 058 `0x0000000fdf9eb269b38e39e058f45d7d0ddb60f9.sol` : 77

- 源码 SHA256: `2052d9b6f7f80ad6cb848091271d91194c9272e72aa792e11f83765ff4d513ab`
- 精确证据身份 / difference_id: `317fedc530d1ae39572b8734fa1396db4df673cd7ac0e48b6399de343f88e205`
- 原始行: 77; 字节区间: `[2201, 2217]`; 事件: `newOwner DEF`; scope=`supported`
- 源码短片段: `address newOwner`

v2候选: `DEF newOwner`; 声明 `[2201, 2217] address newOwner`; 函数起点 `2173`; IR事件 `0x0000000fdf9eb269b38e39e058f45d7d0ddb60f9.sol:2173:e0`; kind=`entry`; 分析路径 `v2`; anchor=`{'file': '0x0000000fdf9eb269b38e39e058f45d7d0ddb60f9.sol', 'start': 2173, 'end': 2356, 'role': 'function_definition'}`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `sealed_entry_initialization_tag`.

### 059 `0x0000000fdf9eb269b38e39e058f45d7d0ddb60f9.sol` : 100

- 源码 SHA256: `2052d9b6f7f80ad6cb848091271d91194c9272e72aa792e11f83765ff4d513ab`
- 精确证据身份 / difference_id: `53f1a3ce485411b6207342241a1b31fbf442242671fb82dcfd9ec6fae1fd17b4`
- 原始行: 100; 字节区间: `[2701, 2718]`; 事件: `role DEF`; scope=`supported`
- 源码短片段: `Role storage role`

v2候选: `DEF role`; 声明 `[2701, 2718] Role storage role`; 函数起点 `2688`; IR事件 `0x0000000fdf9eb269b38e39e058f45d7d0ddb60f9.sol:2688:e0`; kind=`entry`; 分析路径 `v2`; anchor=`{'file': '0x0000000fdf9eb269b38e39e058f45d7d0ddb60f9.sol', 'start': 2688, 'end': 2869, 'role': 'function_definition'}`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `sealed_entry_initialization_tag`.

### 060 `0x0000000fdf9eb269b38e39e058f45d7d0ddb60f9.sol` : 100

- 源码 SHA256: `2052d9b6f7f80ad6cb848091271d91194c9272e72aa792e11f83765ff4d513ab`
- 精确证据身份 / difference_id: `c6b608f01e8e911498597b621e4a382d08b8e7a3c1425d0c24b278303f83236d`
- 原始行: 100; 字节区间: `[2720, 2735]`; 事件: `account DEF`; scope=`supported`
- 源码短片段: `address account`

v2候选: `DEF account`; 声明 `[2720, 2735] address account`; 函数起点 `2688`; IR事件 `0x0000000fdf9eb269b38e39e058f45d7d0ddb60f9.sol:2688:e0`; kind=`entry`; 分析路径 `v2`; anchor=`{'file': '0x0000000fdf9eb269b38e39e058f45d7d0ddb60f9.sol', 'start': 2688, 'end': 2869, 'role': 'function_definition'}`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `sealed_entry_initialization_tag`.

### 061 `0x0000000fdf9eb269b38e39e058f45d7d0ddb60f9.sol` : 110

- 源码 SHA256: `2052d9b6f7f80ad6cb848091271d91194c9272e72aa792e11f83765ff4d513ab`
- 精确证据身份 / difference_id: `8901fa2c4935487bf583250dcee1483ba444c1adbbbff96d319677e209fc1dcd`
- 原始行: 110; 字节区间: `[2959, 2976]`; 事件: `role DEF`; scope=`supported`
- 源码短片段: `Role storage role`

v2候选: `DEF role`; 声明 `[2959, 2976] Role storage role`; 函数起点 `2943`; IR事件 `0x0000000fdf9eb269b38e39e058f45d7d0ddb60f9.sol:2943:e0`; kind=`entry`; 分析路径 `v2`; anchor=`{'file': '0x0000000fdf9eb269b38e39e058f45d7d0ddb60f9.sol', 'start': 2943, 'end': 3127, 'role': 'function_definition'}`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `sealed_entry_initialization_tag`.

### 062 `0x0000000fdf9eb269b38e39e058f45d7d0ddb60f9.sol` : 110

- 源码 SHA256: `2052d9b6f7f80ad6cb848091271d91194c9272e72aa792e11f83765ff4d513ab`
- 精确证据身份 / difference_id: `9c5afe81ec5dd50cfd0154028bb9cc389ad38a534dc2f54f2c1729ea9ed7d916`
- 原始行: 110; 字节区间: `[2978, 2993]`; 事件: `account DEF`; scope=`supported`
- 源码短片段: `address account`

v2候选: `DEF account`; 声明 `[2978, 2993] address account`; 函数起点 `2943`; IR事件 `0x0000000fdf9eb269b38e39e058f45d7d0ddb60f9.sol:2943:e0`; kind=`entry`; 分析路径 `v2`; anchor=`{'file': '0x0000000fdf9eb269b38e39e058f45d7d0ddb60f9.sol', 'start': 2943, 'end': 3127, 'role': 'function_definition'}`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `sealed_entry_initialization_tag`.

## 访问控制 / L1 / FP / declaration_without_initializer (5)

### 063 `0x000adad69101420129a64715a1a52b7348c5e633.sol` : 131

- 源码 SHA256: `c593dcc130ec6f48fe0daaf060590d2487079331e87aa2506a292b7c777aa25a`
- 精确证据身份 / difference_id: `0010aad727b66e71ea6707beb071826d25fd6f20e42743b97f40d8a7c1f46e75`
- 原始行: 131; 字节区间: `[3799, 3820]`; 事件: `myGrant DEF`; scope=`supported`
- 源码短片段: `grant memory myGrant;`

v2候选: `DEF myGrant`; 声明 `[3799, 3819] grant memory myGrant`; 函数起点 `3759`; IR事件 `0x000adad69101420129a64715a1a52b7348c5e633.sol:3759:e1`; kind=`declaration`; 分析路径 `v2`; anchor=`{'file': '0x000adad69101420129a64715a1a52b7348c5e633.sol', 'start': 3799, 'end': 3820, 'role': 'variable_declaration_statement'}`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `DEF_in_exact_declaration_statement_without_value`.

### 064 `0x000adad69101420129a64715a1a52b7348c5e633.sol` : 132

- 源码 SHA256: `c593dcc130ec6f48fe0daaf060590d2487079331e87aa2506a292b7c777aa25a`
- 精确证据身份 / difference_id: `32ec3fa94be553d905b46128e4ffc2b7949220dc9829b4298e370fee1c217ab1`
- 原始行: 132; 字节区间: `[3829, 3844]`; 事件: `amount DEF`; scope=`supported`
- 源码短片段: `uint256 amount;`

v2候选: `DEF amount`; 声明 `[3829, 3843] uint256 amount`; 函数起点 `3759`; IR事件 `0x000adad69101420129a64715a1a52b7348c5e633.sol:3759:e2`; kind=`declaration`; 分析路径 `v2`; anchor=`{'file': '0x000adad69101420129a64715a1a52b7348c5e633.sol', 'start': 3829, 'end': 3844, 'role': 'variable_declaration_statement'}`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `DEF_in_exact_declaration_statement_without_value`.

### 065 `0x00c8162c86a977edc10c641636bdff1c59327983.sol` : 187

- 源码 SHA256: `2be42f2983a7e2a7b9be255bbab1f68606a0048b8c8f0d2b8bc173c11978fd0d`
- 精确证据身份 / difference_id: `c9d02cb0e58fdc5ea07efc0961234e8eaf9bd545775947b197c813c79899f059`
- 原始行: 187; 字节区间: `[7667, 7681]`; 事件: `image DEF`; scope=`supported`
- 源码短片段: `bytes32 image;`

v2候选: `DEF image`; 声明 `[7667, 7680] bytes32 image`; 函数起点 `7346`; IR事件 `0x00c8162c86a977edc10c641636bdff1c59327983.sol:7346:e2`; kind=`declaration`; 分析路径 `legacy`; anchor=`{'file': '0x00c8162c86a977edc10c641636bdff1c59327983.sol', 'start': 7667, 'end': 7681, 'role': 'variable_declaration_statement'}`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `DEF_in_exact_declaration_statement_without_value`.

### 066 `0x00c8162c86a977edc10c641636bdff1c59327983.sol` : 221

- 源码 SHA256: `2be42f2983a7e2a7b9be255bbab1f68606a0048b8c8f0d2b8bc173c11978fd0d`
- 精确证据身份 / difference_id: `14c286814f78a5c73c72a492a24833a6b527aba96124533f91b3cb7c75b85a62`
- 原始行: 221; 字节区间: `[9066, 9080]`; 事件: `image DEF`; scope=`supported`
- 源码短片段: `bytes32 image;`

v2候选: `DEF image`; 声明 `[9066, 9079] bytes32 image`; 函数起点 `8685`; IR事件 `0x00c8162c86a977edc10c641636bdff1c59327983.sol:8685:e2`; kind=`declaration`; 分析路径 `legacy`; anchor=`{'file': '0x00c8162c86a977edc10c641636bdff1c59327983.sol', 'start': 9066, 'end': 9080, 'role': 'variable_declaration_statement'}`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `DEF_in_exact_declaration_statement_without_value`.

### 067 `buggy_21.sol` : 340

- 源码 SHA256: `a56027eab5cd86b394c4af105aa36f7fc91f24aefa636eaa2b640eb164a0402f`
- 精确证据身份 / difference_id: `808fe9d9af600bedc001c7ba18a29a57c1ef71e117cd0bec4ddd4688dedd26d2`
- 原始行: 340; 字节区间: `[12101, 12118]`; 事件: `amount__ DEF`; scope=`supported`
- 源码短片段: `uint256 amount__;`

v2候选: `DEF amount__`; 声明 `[12101, 12117] uint256 amount__`; 函数起点 `11487`; IR事件 `buggy_21.sol:11487:e4`; kind=`declaration`; 分析路径 `v2`; anchor=`{'file': 'buggy_21.sol', 'start': 12101, 'end': 12118, 'role': 'variable_declaration_statement'}`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `DEF_in_exact_declaration_statement_without_value`.

## 访问控制 / L1 / FP / other (5)

### 068 `0x1a4e76811d9c319a953eada36f1def25156c8d93.sol` : 174

- 源码 SHA256: `fb4ea67de1decdd5585e74fe96b6bbe15af910e40353c86e512661c2c2da7072`
- 精确证据身份 / difference_id: `fee6ffe2c41dfb4106a469e391d70ae0ceeeb608e88cd4765928e61cd4abf2ff`
- 原始行: 174; 字节区间: `[4490, 4496]`; 事件: `from_ USE`; scope=`supported`
- 源码短片段: `from_;`

v2候选: `USE from_`; 声明 `[4431, 4444] address from_`; 函数起点 `4408`; IR事件 `0x1a4e76811d9c319a953eada36f1def25156c8d93.sol:4408:e1`; kind=`expression`; 分析路径 `v2`; anchor=`{'file': '0x1a4e76811d9c319a953eada36f1def25156c8d93.sol', 'start': 4490, 'end': 4496, 'role': 'expression_statement'}`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `no_prior_mechanical_predicate`.

此类别仅表示前序机械判据均未成立；不在本页自动判为分析器错误。

### 069 `0x1a4e76811d9c319a953eada36f1def25156c8d93.sol` : 175

- 源码 SHA256: `fb4ea67de1decdd5585e74fe96b6bbe15af910e40353c86e512661c2c2da7072`
- 精确证据身份 / difference_id: `91bf54e0c4be4f61373413abad3c318f0f6ffe258fb966a6be19aa48915d6963`
- 原始行: 175; 字节区间: `[4501, 4508]`; 事件: `value_ USE`; scope=`supported`
- 源码短片段: `value_;`

v2候选: `USE value_`; 声明 `[4446, 4460] uint256 value_`; 函数起点 `4408`; IR事件 `0x1a4e76811d9c319a953eada36f1def25156c8d93.sol:4408:e2`; kind=`expression`; 分析路径 `v2`; anchor=`{'file': '0x1a4e76811d9c319a953eada36f1def25156c8d93.sol', 'start': 4501, 'end': 4508, 'role': 'expression_statement'}`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `no_prior_mechanical_predicate`.

此类别仅表示前序机械判据均未成立；不在本页自动判为分析器错误。

### 070 `0x1a4e76811d9c319a953eada36f1def25156c8d93.sol` : 176

- 源码 SHA256: `fb4ea67de1decdd5585e74fe96b6bbe15af910e40353c86e512661c2c2da7072`
- 精确证据身份 / difference_id: `b7a13efa38fbf3ffcefd5dcb917fbb34027b98bb79c1b805db8e2b241b3f3a3d`
- 原始行: 176; 字节区间: `[4513, 4519]`; 事件: `data_ USE`; scope=`supported`
- 源码短片段: `data_;`

v2候选: `USE data_`; 声明 `[4462, 4473] bytes data_`; 函数起点 `4408`; IR事件 `0x1a4e76811d9c319a953eada36f1def25156c8d93.sol:4408:e3`; kind=`expression`; 分析路径 `v2`; anchor=`{'file': '0x1a4e76811d9c319a953eada36f1def25156c8d93.sol', 'start': 4513, 'end': 4519, 'role': 'expression_statement'}`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `no_prior_mechanical_predicate`.

此类别仅表示前序机械判据均未成立；不在本页自动判为分析器错误。

### 071 `0x1a746a2228ec6ebd432194b03d0c3f38429c8ec7.sol` : 59

- 源码 SHA256: `a237e2388e2db38ec1d0cd6b3d8f2eae77e3772554e374d37ee121de1ba94243`
- 精确证据身份 / difference_id: `c7faba9fef6aa8ba8ddae02c7f6a4aa5dd97daec4117ad1e948647e4ecf58553`
- 原始行: 59; 字节区间: `[1278, 1284]`; 事件: `_from USE`; scope=`supported`
- 源码短片段: `_from;`

v2候选: `USE _from`; 声明 `[1218, 1231] address _from`; 函数起点 `1195`; IR事件 `0x1a746a2228ec6ebd432194b03d0c3f38429c8ec7.sol:1195:e1`; kind=`expression`; 分析路径 `v2`; anchor=`{'file': '0x1a746a2228ec6ebd432194b03d0c3f38429c8ec7.sol', 'start': 1278, 'end': 1284, 'role': 'expression_statement'}`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `no_prior_mechanical_predicate`.

此类别仅表示前序机械判据均未成立；不在本页自动判为分析器错误。

### 072 `0x1a746a2228ec6ebd432194b03d0c3f38429c8ec7.sol` : 60

- 源码 SHA256: `a237e2388e2db38ec1d0cd6b3d8f2eae77e3772554e374d37ee121de1ba94243`
- 精确证据身份 / difference_id: `8f922c7aa4bbef085fb78720a777199bafc8f4cdd80f2b97a22c08fb8e89ef53`
- 原始行: 60; 字节区间: `[1287, 1294]`; 事件: `_value USE`; scope=`supported`
- 源码短片段: `_value;`

v2候选: `USE _value`; 声明 `[1233, 1247] uint256 _value`; 函数起点 `1195`; IR事件 `0x1a746a2228ec6ebd432194b03d0c3f38429c8ec7.sol:1195:e2`; kind=`expression`; 分析路径 `v2`; anchor=`{'file': '0x1a746a2228ec6ebd432194b03d0c3f38429c8ec7.sol', 'start': 1287, 'end': 1294, 'role': 'expression_statement'}`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `no_prior_mechanical_predicate`.

此类别仅表示前序机械判据均未成立；不在本页自动判为分析器错误。

## 访问控制 / L1 / FN / v2_fallback (5)

### 073 `0x0000000fdf9eb269b38e39e058f45d7d0ddb60f9.sol` : 70

- 源码 SHA256: `2052d9b6f7f80ad6cb848091271d91194c9272e72aa792e11f83765ff4d513ab`
- 精确证据身份 / difference_id: `978538542d517943406937269c6fde46e9fd51cc1f73d4dc10d46e023df5c097`
- 原始行: 70; 字节区间: `[1994, 2022]`; 事件: `newOwner USE`; scope=`fallback`
- 源码短片段: `_transferOwnership(newOwner)`

Slither参考: `USE newOwner`; CFG text=`_transferOwnership(newOwner)`; 声明 `[1949, 1965] address newOwner`; function=`Ownable.transferOwnership(address)`; context_count=2; 标签=`['inheritance']`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `exact_function_start_status_fallback`.

### 074 `0x0000000fdf9eb269b38e39e058f45d7d0ddb60f9.sol` : 157

- 源码 SHA256: `2052d9b6f7f80ad6cb848091271d91194c9272e72aa792e11f83765ff4d513ab`
- 精确证据身份 / difference_id: `f543a504ac0ebbbf3202b057602f0b2b4dd88ae9b8656bcea7eba7b9c2c8e266`
- 原始行: 157; 字节区间: `[4231, 4258]`; 事件: `account USE`; scope=`fallback`
- 源码短片段: `_addWhitelistAdmin(account)`

Slither参考: `USE account`; CFG text=`_addWhitelistAdmin(account)`; 声明 `[4178, 4193] address account`; function=`WhitelistAdminRole.addWhitelistAdmin(address)`; context_count=3; 标签=`['inheritance']`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `exact_function_start_status_fallback`.

### 075 `0x0000000fdf9eb269b38e39e058f45d7d0ddb60f9.sol` : 203

- 源码 SHA256: `2052d9b6f7f80ad6cb848091271d91194c9272e72aa792e11f83765ff4d513ab`
- 精确证据身份 / difference_id: `888b240768b9541d07d6b6c3ba9c31772e7c675810b3e78b717483579f62acef`
- 原始行: 203; 字节区间: `[5623, 5647]`; 事件: `account USE`; scope=`fallback`
- 源码短片段: `_addWhitelisted(account)`

Slither参考: `USE account`; CFG text=`_addWhitelisted(account)`; 声明 `[5570, 5585] address account`; function=`WhitelistedRole.addWhitelisted(address)`; context_count=2; 标签=`['inheritance']`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `exact_function_start_status_fallback`.

### 076 `0x0000000fdf9eb269b38e39e058f45d7d0ddb60f9.sol` : 207

- 源码 SHA256: `2052d9b6f7f80ad6cb848091271d91194c9272e72aa792e11f83765ff4d513ab`
- 精确证据身份 / difference_id: `77ffe2048c981186c9ab06ab2fe1630861329092376236cd160867458b4004ab`
- 原始行: 207; 字节区间: `[5740, 5767]`; 事件: `account USE`; scope=`fallback`
- 源码短片段: `_removeWhitelisted(account)`

Slither参考: `USE account`; CFG text=`_removeWhitelisted(account)`; 声明 `[5687, 5702] address account`; function=`WhitelistedRole.removeWhitelisted(address)`; context_count=2; 标签=`['inheritance']`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `exact_function_start_status_fallback`.

### 077 `0x0000000fdf9eb269b38e39e058f45d7d0ddb60f9.sol` : 240

- 源码 SHA256: `2052d9b6f7f80ad6cb848091271d91194c9272e72aa792e11f83765ff4d513ab`
- 精确证据身份 / difference_id: `7f269bcb4b8da37fa6430f07a61b2a2bcd8cb847a177bdd2c2e708607f9a8c0f`
- 原始行: 240; 字节区间: `[6524, 6551]`; 事件: `participant USE`; scope=`fallback`
- 源码短片段: `!isWhitelisted(participant)`

Slither参考: `USE participant`; CFG text=`!isWhitelisted(participant)`; 声明 `[6463, 6482] address participant`; function=`InvictusWhitelist.verifyParticipant(address)`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `exact_function_start_status_fallback`.

## 访问控制 / L1 / FN / other (5)

### 078 `0x000c100050e98c91f9114fa5dd75ce6869bf4f53.sol` : 992

- 源码 SHA256: `92c0485bdce372158d7750676dbc375a49f9c1c335a9f6b68883fe8f1b28f63c`
- 精确证据身份 / difference_id: `560ce1a7688159bb3d334748df009ef542589da63f782846a1e354542a6e4d35`
- 原始行: 992; 字节区间: `[31501, 31516]`; 事件: `i DEF`; scope=`supported`
- 源码短片段: `i > endingIndex`

Slither参考: `DEF i`; CFG text=`i > endingIndex`; 声明 `[31474, 31499] uint256 i = startingIndex`; function=`C10Token.allocateTokens()`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `no_prior_mechanical_predicate`.

此类别仅表示前序机械判据均未成立；不在本页自动判为分析器错误。

### 079 `0x000c100050e98c91f9114fa5dd75ce6869bf4f53.sol` : 1021

- 源码 SHA256: `92c0485bdce372158d7750676dbc375a49f9c1c335a9f6b68883fe8f1b28f63c`
- 精确证据身份 / difference_id: `7832ad6352892bb939d4e65f56a4803c33e1ec5df15c1d514a095cd16a6067d4`
- 原始行: 1021; 字节区间: `[32560, 32575]`; 事件: `i DEF`; scope=`supported`
- 源码短片段: `i > endingIndex`

Slither参考: `DEF i`; CFG text=`i > endingIndex`; 声明 `[32533, 32558] uint256 i = startingIndex`; function=`C10Token.processWithdrawals()`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `no_prior_mechanical_predicate`.

此类别仅表示前序机械判据均未成立；不在本页自动判为分析器错误。

### 080 `0x00c8162c86a977edc10c641636bdff1c59327983.sol` : 98

- 源码 SHA256: `2be42f2983a7e2a7b9be255bbab1f68606a0048b8c8f0d2b8bc173c11978fd0d`
- 精确证据身份 / difference_id: `e1c7a59f2fa37005c17f02c4aa0b631f802096d220c86d0b4823c64f69fa10f7`
- 原始行: 98; 字节区间: `[3589, 3684]`; 事件: `_paymentNumber USE`; scope=`unmapped`
- 源码短片段: `require(payments[msg.sender][_paymentNumber].state == PaymentState.nil, "payment already made")`

Slither参考: `USE _paymentNumber`; CFG text=`require(payments[msg.sender][_paymentNumber].state == PaymentState.nil, "payment already made")`; 声明 `[3555, 3577] uint256 _paymentNumber`; function=`Payments.validPayment(uint256)`; context_count=1; 标签=`['modifier_inlining']`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `no_prior_mechanical_predicate`.

此类别仅表示前序机械判据均未成立；不在本页自动判为分析器错误。

### 081 `0x0a5dc2204dfc6082ef3bbcfc3a468f16318c4168.sol` : 180

- 源码 SHA256: `e07d228c9da9a9d2898b5673ed97d9e203d7dfc882cdac3ca3d3a73b0e411b0b`
- 精确证据身份 / difference_id: `96bbe04d358defb8df850533798486508a9322987ca7876a4a65e5e8eeb65316`
- 原始行: 180; 字节区间: `[5955, 5985]`; 事件: `_addr USE`; scope=`unmapped`
- 源码短片段: `require(!lockAddresses[_addr])`

Slither参考: `USE _addr`; CFG text=`require(!lockAddresses[_addr])`; 声明 `[5934, 5947] address _addr`; function=`PandaGoldToken.transferable(address)`; context_count=1; 标签=`['modifier_inlining']`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `no_prior_mechanical_predicate`.

此类别仅表示前序机械判据均未成立；不在本页自动判为分析器错误。

### 082 `0x0be4a987fd8dcbd2fff64ba4131d3a208307f667.sol` : 708

- 源码 SHA256: `b517b0099c3d0f48fb1891b4b103c883553a1e0ace61575b83f58370b4a90b77`
- 精确证据身份 / difference_id: `439452356a4aee9aa810c112c300ae7ca7e4f354f5bd3c2099890e27db8a3546`
- 原始行: 708; 字节区间: `[21047, 21074]`; 事件: `to USE`; scope=`unmapped`
- 源码短片段: `require(to != address(0x0))`

Slither参考: `USE to`; CFG text=`require(to != address(0x0))`; 声明 `[21024, 21034] address to`; function=`WitToken.validDestination(address)`; context_count=1; 标签=`['modifier_inlining']`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `no_prior_mechanical_predicate`.

此类别仅表示前序机械判据均未成立；不在本页自动判为分析器错误。

## 访问控制 / L2 / FP / alias (5)

### 083 `buggy_22.sol` : 398

- 源码 SHA256: `fe9c3fddfc9d98c90437e2fba629dd60d1f3c7216c0f8986a638676bfd9771b4`
- 精确证据身份 / difference_id: `ecbf41fa2400e3754330779be30d386c0b5e0f4df7139fd42250bf032baf3d1b`
- 原始行: 398; 字节区间: `[14438, 14452]`; 事件: `proposals READ`; scope=`supported`
- 源码短片段: `p.proposalHash`

v2候选: `READ proposals`; 声明 `[6379, 6407] Proposal[] public proposals;`; 函数起点 `14147`; relation=`READS_STATE`; status=`projected`; via_alias=`True`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `sealed_6c_tag`.

### 084 `buggy_22.sol` : 452

- 源码 SHA256: `fe9c3fddfc9d98c90437e2fba629dd60d1f3c7216c0f8986a638676bfd9771b4`
- 精确证据身份 / difference_id: `e22f1153dc576e8c7657592ee2db7fadff5a19104be54d8890c199836330c3fe`
- 原始行: 452; 字节区间: `[16087, 16106]`; 事件: `proposals READ`; scope=`fallback`
- 源码短片段: `p.voted[msg.sender]`

v2候选: `READ proposals`; 声明 `[6379, 6407] Proposal[] public proposals;`; 函数起点 `15867`; relation=`READS_STATE`; status=`projected`; via_alias=`True`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `sealed_6c_tag`.

### 085 `buggy_22.sol` : 454

- 源码 SHA256: `fe9c3fddfc9d98c90437e2fba629dd60d1f3c7216c0f8986a638676bfd9771b4`
- 精确证据身份 / difference_id: `0311ed2db5f8146d81036f21e44da4c1808a232e272184d35f73a023186fd375`
- 原始行: 454; 字节区间: `[16135, 16149]`; 事件: `proposals READ`; scope=`fallback`
- 源码短片段: `p.votes.length`

v2候选: `READ proposals`; 声明 `[6379, 6407] Proposal[] public proposals;`; 函数起点 `15867`; relation=`READS_STATE`; status=`projected`; via_alias=`True`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `sealed_6c_tag`.

### 086 `buggy_22.sol` : 478

- 源码 SHA256: `fe9c3fddfc9d98c90437e2fba629dd60d1f3c7216c0f8986a638676bfd9771b4`
- 精确证据身份 / difference_id: `c8a9e0364b1e86f8b3997802a64c8fe417e22e9d7878c5daa3a0db89bab0d363`
- 原始行: 478; 字节区间: `[17083, 17101]`; 事件: `proposals READ`; scope=`supported`
- 源码短片段: `p.minExecutionDate`

v2候选: `READ proposals`; 声明 `[6379, 6407] Proposal[] public proposals;`; 函数起点 `16885`; relation=`READS_STATE`; status=`projected`; via_alias=`True`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `sealed_6c_tag`.

### 087 `buggy_22.sol` : 479

- 源码 SHA256: `fe9c3fddfc9d98c90437e2fba629dd60d1f3c7216c0f8986a638676bfd9771b4`
- 精确证据身份 / difference_id: `e0557c14f01ef03ac03877d411684a09595ef2d57baa2ba6af3cef914a144b7d`
- 原始行: 479; 字节区间: `[17199, 17209]`; 事件: `proposals READ`; scope=`supported`
- 源码短片段: `p.executed`

v2候选: `READ proposals`; 声明 `[6379, 6407] Proposal[] public proposals;`; 函数起点 `16885`; relation=`READS_STATE`; status=`projected`; via_alias=`True`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `sealed_6c_tag`.

## 访问控制 / L2 / FP / other (5)

### 088 `0x000c100050e98c91f9114fa5dd75ce6869bf4f53.sol` : 867

- 源码 SHA256: `92c0485bdce372158d7750676dbc375a49f9c1c335a9f6b68883fe8f1b28f63c`
- 精确证据身份 / difference_id: `788cddfb8cc52dec08d471b5b157428a10b88ddac93377086a20c9971c0ab103`
- 原始行: 867; 字节区间: `[26818, 26835]`; 事件: `price READ`; scope=`fallback`
- 源码短片段: `price.denominator`

v2候选: `READ price`; 声明 `[23290, 23309] Price public price;`; 函数起点 `26552`; relation=`READS_STATE`; status=`unmapped`; via_alias=`False`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `no_prior_mechanical_predicate`.

此类别仅表示前序机械判据均未成立；不在本页自动判为分析器错误。

### 089 `0x000c100050e98c91f9114fa5dd75ce6869bf4f53.sol` : 1003

- 源码 SHA256: `92c0485bdce372158d7750676dbc375a49f9c1c335a9f6b68883fe8f1b28f63c`
- 精确证据身份 / difference_id: `d1844636b6fe1df3851b1b879c824766f694139613dcd144d03b20363aa51154`
- 原始行: 1003; 字节区间: `[31915, 31932]`; 事件: `price READ`; scope=`supported`
- 源码短片段: `price.denominator`

v2候选: `READ price`; 声明 `[23290, 23309] Price public price;`; 函数起点 `31583`; relation=`READS_STATE`; status=`projected`; via_alias=`False`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `no_prior_mechanical_predicate`.

此类别仅表示前序机械判据均未成立；不在本页自动判为分析器错误。

### 090 `0x000c100050e98c91f9114fa5dd75ce6869bf4f53.sol` : 1029

- 源码 SHA256: `92c0485bdce372158d7750676dbc375a49f9c1c335a9f6b68883fe8f1b28f63c`
- 精确证据身份 / difference_id: `08748c82a68f8675518e8126ee77cef46df7cec732439b21e0276bcde34dfcb0`
- 原始行: 1029; 字节区间: `[32874, 32889]`; 事件: `price READ`; scope=`supported`
- 源码短片段: `price.numerator`

v2候选: `READ price`; 声明 `[23290, 23309] Price public price;`; 函数起点 `32642`; relation=`READS_STATE`; status=`projected`; via_alias=`False`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `no_prior_mechanical_predicate`.

此类别仅表示前序机械判据均未成立；不在本页自动判为分析器错误。

### 091 `0x00cab00609e70f14e755524bd07e1c639665e796.sol` : 51

- 源码 SHA256: `c58fa1136771dbae49bf30c2b7871952e052f782bbe8328ed2f466778c5cb9d5`
- 精确证据身份 / difference_id: `80696781006f6be169bcf1a38ab13c4866896bbd03e318db51b327bd627c243d`
- 原始行: 51; 字节区间: `[1515, 1523]`; 事件: `balances READ`; scope=`supported`
- 源码短片段: `balances`

v2候选: `READ balances`; 声明 `[632, 677] mapping (address => uint256) public balances;`; 函数起点 `1333`; relation=`READS_STATE`; status=`projected`; via_alias=`False`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `no_prior_mechanical_predicate`.

此类别仅表示前序机械判据均未成立；不在本页自动判为分析器错误。

### 092 `0x00cab00609e70f14e755524bd07e1c639665e796.sol` : 52

- 源码 SHA256: `c58fa1136771dbae49bf30c2b7871952e052f782bbe8328ed2f466778c5cb9d5`
- 精确证据身份 / difference_id: `9d16b86aae594cf2f832988380b52d86bf824294caa5a833197943bba168f7a2`
- 原始行: 52; 字节区间: `[1579, 1587]`; 事件: `balances READ`; scope=`supported`
- 源码短片段: `balances`

v2候选: `READ balances`; 声明 `[632, 677] mapping (address => uint256) public balances;`; 函数起点 `1333`; relation=`READS_STATE`; status=`projected`; via_alias=`False`.

Slither：未匹配；没有可认定为本条对应的CFG事件/声明。相交参考上下文仅保留在JSON中。

机械判据: `no_prior_mechanical_predicate`.

此类别仅表示前序机械判据均未成立；不在本页自动判为分析器错误。

## 访问控制 / L2 / FN / constant_excluded (5)

### 093 `0x000adad69101420129a64715a1a52b7348c5e633.sol` : 104

- 源码 SHA256: `c593dcc130ec6f48fe0daaf060590d2487079331e87aa2506a292b7c777aa25a`
- 精确证据身份 / difference_id: `22e76988c53b6f6497662619cd755b7e1ad9228bea8ec8b839c49c748fe5a2b5`
- 原始行: 104; 字节区间: `[3048, 3077]`; 事件: `DIP WRITE`; scope=`unmapped`
- 源码短片段: `uint256 constant DIP = 10**18`

Slither参考: `WRITE DIP`; CFG text=`uint256 constant DIP = 10**18`; 声明 `[3048, 3077] uint256 constant DIP = 10**18`; function=`DIP_Team_Transfer.slitherConstructorConstantVariables()`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `is_constant_or_exact_constant_declaration`.

### 094 `0x000adad69101420129a64715a1a52b7348c5e633.sol` : 162

- 源码 SHA256: `c593dcc130ec6f48fe0daaf060590d2487079331e87aa2506a292b7c777aa25a`
- 精确证据身份 / difference_id: `b19cbc2f1628b2508d7b5c1e78562318b6e91f1418f05e20470add5b6758a241`
- 原始行: 162; 字节区间: `[5012, 5095]`; 事件: `DIP READ`; scope=`fallback`
- 源码短片段: `teamTokens[0x0024df2bE7524b132Ced68Ca2906eD1D9CdAbDA4] = grant(Pool_B, 84000 * DIP)`

Slither参考: `READ DIP`; CFG text=`teamTokens[0x0024df2bE7524b132Ced68Ca2906eD1D9CdAbDA4] = grant(Pool_B, 84000 * DIP)`; 声明 `[3048, 3077] uint256 constant DIP = 10**18`; function=`DIP_Team_Transfer.constructor()`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `is_constant_or_exact_constant_declaration`.

### 095 `0x000adad69101420129a64715a1a52b7348c5e633.sol` : 163

- 源码 SHA256: `c593dcc130ec6f48fe0daaf060590d2487079331e87aa2506a292b7c777aa25a`
- 精确证据身份 / difference_id: `00af0c82171eb8461fe912b9e517bdcc122310890504c43dd97f8e6831f2a96d`
- 原始行: 163; 字节区间: `[5105, 5190]`; 事件: `DIP READ`; scope=`fallback`
- 源码短片段: `teamTokens[0x025f020e2C1e540c3fBe3E80C23Cb192dFb65514] = grant(Pool_B, 2957000 * DIP)`

Slither参考: `READ DIP`; CFG text=`teamTokens[0x025f020e2C1e540c3fBe3E80C23Cb192dFb65514] = grant(Pool_B, 2957000 * DIP)`; 声明 `[3048, 3077] uint256 constant DIP = 10**18`; function=`DIP_Team_Transfer.constructor()`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `is_constant_or_exact_constant_declaration`.

### 096 `0x000adad69101420129a64715a1a52b7348c5e633.sol` : 164

- 源码 SHA256: `c593dcc130ec6f48fe0daaf060590d2487079331e87aa2506a292b7c777aa25a`
- 精确证据身份 / difference_id: `58a49e768ac2a3126218cd682376f860c88548d6f542c351e50b457111231a06`
- 原始行: 164; 字节区间: `[5200, 5284]`; 事件: `DIP READ`; scope=`fallback`
- 源码短片段: `teamTokens[0x1FeA19BA0Cd8e068Fb1C538B2C3a700965d1952e] = grant(Pool_B, 119000 * DIP)`

Slither参考: `READ DIP`; CFG text=`teamTokens[0x1FeA19BA0Cd8e068Fb1C538B2C3a700965d1952e] = grant(Pool_B, 119000 * DIP)`; 声明 `[3048, 3077] uint256 constant DIP = 10**18`; function=`DIP_Team_Transfer.constructor()`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `is_constant_or_exact_constant_declaration`.

### 097 `0x000adad69101420129a64715a1a52b7348c5e633.sol` : 165

- 源码 SHA256: `c593dcc130ec6f48fe0daaf060590d2487079331e87aa2506a292b7c777aa25a`
- 精确证据身份 / difference_id: `b9f4bfcdffb8f7bda1dad7da3a71e84d10646fe8f8465b0b4ed9a37bb8bbaf92`
- 原始行: 165; 字节区间: `[5294, 5378]`; 事件: `DIP READ`; scope=`fallback`
- 源码短片段: `teamTokens[0x2718874048aBcCEbE24693e689D31B011c6101EA] = grant(Pool_B, 314000 * DIP)`

Slither参考: `READ DIP`; CFG text=`teamTokens[0x2718874048aBcCEbE24693e689D31B011c6101EA] = grant(Pool_B, 314000 * DIP)`; 声明 `[3048, 3077] uint256 constant DIP = 10**18`; function=`DIP_Team_Transfer.constructor()`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `is_constant_or_exact_constant_declaration`.

## 访问控制 / L2 / FN / state_initializer (5)

### 098 `0x000adad69101420129a64715a1a52b7348c5e633.sol` : 110

- 源码 SHA256: `c593dcc130ec6f48fe0daaf060590d2487079331e87aa2506a292b7c777aa25a`
- 精确证据身份 / difference_id: `2ba646492ec9d8c66c23bd6663b795b4a5a369c84aebb8c102d876e605907fe1`
- 原始行: 110; 字节区间: `[3188, 3247]`; 事件: `Pool_B WRITE`; scope=`unmapped`
- 源码短片段: `address Pool_B = 0x7D96c657F5d721De12060cdc90e6ACa73A5a4E46`

Slither参考: `WRITE Pool_B`; CFG text=`address Pool_B = 0x7D96c657F5d721De12060cdc90e6ACa73A5a4E46`; 声明 `[3188, 3247] address Pool_B = 0x7D96c657F5d721De12060cdc90e6ACa73A5a4E46`; function=`DIP_Team_Transfer.slitherConstructorVariables()`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `synthetic_constructor_or_state_declaration_span`.

### 099 `0x000adad69101420129a64715a1a52b7348c5e633.sol` : 111

- 源码 SHA256: `c593dcc130ec6f48fe0daaf060590d2487079331e87aa2506a292b7c777aa25a`
- 精确证据身份 / difference_id: `32209c4aa52f0c36487d90b94e76df819740c30a62e4267d6f4c4029afaf399f`
- 原始行: 111; 字节区间: `[3282, 3341]`; 事件: `Pool_C WRITE`; scope=`unmapped`
- 源码短片段: `address Pool_C = 0x4B7B8c1d236D349D53b2Fb80c060FEF2544cE3E4`

Slither参考: `WRITE Pool_C`; CFG text=`address Pool_C = 0x4B7B8c1d236D349D53b2Fb80c060FEF2544cE3E4`; 声明 `[3282, 3341] address Pool_C = 0x4B7B8c1d236D349D53b2Fb80c060FEF2544cE3E4`; function=`DIP_Team_Transfer.slitherConstructorVariables()`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `synthetic_constructor_or_state_declaration_span`.

### 100 `0x000c100050e98c91f9114fa5dd75ce6869bf4f53.sol` : 769

- 源码 SHA256: `92c0485bdce372158d7750676dbc375a49f9c1c335a9f6b68883fe8f1b28f63c`
- 精确证据身份 / difference_id: `c5a49c3aa422ec69b8e46abfbb498dbadb2826bfb699594031265e7ef4369244`
- 原始行: 769; 字节区间: `[22997, 23034]`; 事件: `minimumWei WRITE`; scope=`unmapped`
- 源码短片段: `uint256 public minimumWei = 50 finney`

Slither参考: `WRITE minimumWei`; CFG text=`uint256 public minimumWei = 50 finney`; 声明 `[22997, 23034] uint256 public minimumWei = 50 finney`; function=`C10Token.slitherConstructorVariables()`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `synthetic_constructor_or_state_declaration_span`.

### 101 `0x000c100050e98c91f9114fa5dd75ce6869bf4f53.sol` : 770

- 源码 SHA256: `92c0485bdce372158d7750676dbc375a49f9c1c335a9f6b68883fe8f1b28f63c`
- 精确证据身份 / difference_id: `10228f01b7d1d85dab9824eafeda602fa5bbe7ebc31421933f452803c7f09e26`
- 原始行: 770; 字节区间: `[23040, 23068]`; 事件: `entryFee WRITE`; scope=`unmapped`
- 源码短片段: `uint256 public entryFee = 50`

Slither参考: `WRITE entryFee`; CFG text=`uint256 public entryFee = 50`; 声明 `[23040, 23068] uint256 public entryFee = 50`; function=`C10Token.slitherConstructorVariables()`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `synthetic_constructor_or_state_declaration_span`.

### 102 `0x000c100050e98c91f9114fa5dd75ce6869bf4f53.sol` : 771

- 源码 SHA256: `92c0485bdce372158d7750676dbc375a49f9c1c335a9f6b68883fe8f1b28f63c`
- 精确证据身份 / difference_id: `db44b4a1fefa78f7c4a2c8d3e1186dc1b627a0555d41af4694dddd392e3bddaf`
- 原始行: 771; 字节区间: `[23096, 23123]`; 事件: `exitFee WRITE`; scope=`unmapped`
- 源码短片段: `uint256 public exitFee = 50`

Slither参考: `WRITE exitFee`; CFG text=`uint256 public exitFee = 50`; 声明 `[23096, 23123] uint256 public exitFee = 50`; function=`C10Token.slitherConstructorVariables()`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `synthetic_constructor_or_state_declaration_span`.

## 访问控制 / L2 / FN / write_base_read (5)

### 103 `0x000c100050e98c91f9114fa5dd75ce6869bf4f53.sol` : 863

- 源码 SHA256: `92c0485bdce372158d7750676dbc375a49f9c1c335a9f6b68883fe8f1b28f63c`
- 精确证据身份 / difference_id: `a5c8e2d1ee03187834e4496da802b53540256e3ad231eec590b80faf9692efdd`
- 原始行: 863; 字节区间: `[26687, 26717]`; 事件: `price READ`; scope=`fallback`
- 源码短片段: `price.numerator = newNumerator`

Slither参考: `READ price`; CFG text=`price.numerator = newNumerator`; 声明 `[23290, 23308] Price public price`; function=`C10Token.updatePrice(uint256)`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `same_node_chain_root_WRITE_without_READ`.

判据引用的v2写入（类型不同，**不是该READ的配对**）: `price WRITE` `[26687, 26702]` `price.numerator`; 声明 `[23290, 23309] Price public price;`.

### 104 `0x000c100050e98c91f9114fa5dd75ce6869bf4f53.sol` : 874

- 源码 SHA256: `92c0485bdce372158d7750676dbc375a49f9c1c335a9f6b68883fe8f1b28f63c`
- 精确证据身份 / difference_id: `5c4a904059ab8f4072eb56e5a8a6a5aa15237d32163b2843f8148a995c3848c0`
- 原始行: 874; 字节区间: `[27038, 27072]`; 事件: `price READ`; scope=`fallback`
- 源码短片段: `price.denominator = newDenominator`

Slither参考: `READ price`; CFG text=`price.denominator = newDenominator`; 声明 `[23290, 23308] Price public price`; function=`C10Token.updatePriceDenominator(uint256)`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `same_node_chain_root_WRITE_without_READ`.

判据引用的v2写入（类型不同，**不是该READ的配对**）: `price WRITE` `[27038, 27055]` `price.denominator`; 声明 `[23290, 23309] Price public price;`.

### 105 `0x0b5828d786f397c73554c5b091aa9ea108fffc51.sol` : 132

- 源码 SHA256: `c3420de7f7e6f1caaa2f921407f39fd1ca7681f4bd21d1d6777d4b273184eda3`
- 精确证据身份 / difference_id: `f36763d8589b6b22fd1285ed7321a71a49f8dee9d19946c52aafc55abf1eeb2d`
- 原始行: 132; 字节区间: `[4178, 4218]`; 事件: `segments READ`; scope=`supported`
- 源码短片段: `segments[key][_row][_col].email = _email`

Slither参考: `READ segments`; CFG text=`segments[key][_row][_col].email = _email`; 声明 `[1670, 1751] mapping(bytes32 => mapping(uint32 => mapping(uint32 => Segment))) public segments`; function=`TilcoinStorage.setSegmentOwner(string,uint32,uint32,string,string)`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `same_node_chain_root_WRITE_without_READ`.

判据引用的v2写入（类型不同，**不是该READ的配对**）: `segments WRITE` `[4178, 4209]` `segments[key][_row][_col].email`; 声明 `[1670, 1752] mapping(bytes32 => mapping(uint32 => mapping(uint32 => Segment))) public segments;`.

### 106 `0x0b5828d786f397c73554c5b091aa9ea108fffc51.sol` : 133

- 源码 SHA256: `c3420de7f7e6f1caaa2f921407f39fd1ca7681f4bd21d1d6777d4b273184eda3`
- 精确证据身份 / difference_id: `15131a3b30a49bc0ca828686a4f02d0a77212decc377f6a1ab2a4ed46dc826af`
- 原始行: 133; 字节区间: `[4228, 4268]`; 事件: `segments READ`; scope=`supported`
- 源码短片段: `segments[key][_row][_col].login = _login`

Slither参考: `READ segments`; CFG text=`segments[key][_row][_col].login = _login`; 声明 `[1670, 1751] mapping(bytes32 => mapping(uint32 => mapping(uint32 => Segment))) public segments`; function=`TilcoinStorage.setSegmentOwner(string,uint32,uint32,string,string)`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `same_node_chain_root_WRITE_without_READ`.

判据引用的v2写入（类型不同，**不是该READ的配对**）: `segments WRITE` `[4228, 4259]` `segments[key][_row][_col].login`; 声明 `[1670, 1752] mapping(bytes32 => mapping(uint32 => mapping(uint32 => Segment))) public segments;`.

### 107 `0x0be4a987fd8dcbd2fff64ba4131d3a208307f667.sol` : 643

- 源码 SHA256: `b517b0099c3d0f48fb1891b4b103c883553a1e0ace61575b83f58370b4a90b77`
- 精确证据身份 / difference_id: `331f8e5dfb42af502fa1d64ec605d5ec04ceff925a814cdd190be7f00b305b89`
- 原始行: 643; 字节区间: `[18515, 18547]`; 事件: `params READ`; scope=`fallback`
- 源码短片段: `params[ISSUE_METHOD].state=false`

Slither参考: `READ params`; CFG text=`params[ISSUE_METHOD].state=false`; 声明 `[17754, 17792] mapping (string => MethodParam) params`; function=`TwoPhaseToken.comfirmIsses(uint256)`; context_count=2; 标签=`['inheritance']`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `same_node_chain_root_WRITE_without_READ`.

判据引用的v2写入（类型不同，**不是该READ的配对**）: `params WRITE` `[18515, 18541]` `params[ISSUE_METHOD].state`; 声明 `[17754, 17793] mapping (string => MethodParam) params;`.

## 访问控制 / L2 / FN / alias (2)

### 108 `buggy_24.sol` : 779

- 源码 SHA256: `1c5ac378add0c2d531237ca87366e49101a7002528c81a90f8355d9bc66c2a4b`
- 精确证据身份 / difference_id: `86c3e2e8a3689d445d9f64baa762f081f6af819f40572f27e7b815b61a77e79b`
- 原始行: 779; 字节区间: `[32852, 32888]`; 事件: `userMapping WRITE`; scope=`supported`
- 源码短片段: `user.calcDynamicCommissionAmount = 0`

Slither参考: `WRITE userMapping`; CFG text=`user.calcDynamicCommissionAmount = 0`; 声明 `[9083, 9128] mapping (address => User) private userMapping`; function=`FomoFeast.calcDynamicCommission()`; context_count=1; 标签=`['alias']`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `sealed_6c_tag`.

### 109 `buggy_24.sol` : 821

- 源码 SHA256: `1c5ac378add0c2d531237ca87366e49101a7002528c81a90f8355d9bc66c2a4b`
- 精确证据身份 / difference_id: `970c5e61dde768effb7200f3697f7439ff90e687eed50477707395a3cbb514c5`
- 原始行: 821; 字节区间: `[35212, 35311]`; 事件: `userMapping WRITE`; scope=`supported`
- 源码短片段: `user.dynamicCommissionBalance = user.dynamicCommissionBalance.add(user.calcDynamicCommissionAmount)`

Slither参考: `WRITE userMapping`; CFG text=`user.dynamicCommissionBalance = user.dynamicCommissionBalance.add(user.calcDynamicCommissionAmount)`; 声明 `[9083, 9128] mapping (address => User) private userMapping`; function=`FomoFeast.calcDynamicCommission()`; context_count=1; 标签=`['alias']`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `sealed_6c_tag`.

## 访问控制 / L2 / FN / v2_binding_unresolved (5)

### 110 `0x0da2c2f5bb8cef300e894f47532af79811f0e18a.sol` : 96

- 源码 SHA256: `bed1bbd122c867facae4d77ccf6463500b647d554c4a8eeb31a8a51a5d4350a2`
- 精确证据身份 / difference_id: `049927076d61c54298619c4ae935e85ab88e51a20bf899c313d35bc2ba2ee291`
- 原始行: 96; 字节区间: `[2740, 2791]`; 事件: `balanceOf WRITE`; scope=`fallback`
- 源码短片段: `balanceOf[msg.sender] = 100000000000000000000000000`

Slither参考: `WRITE balanceOf`; CFG text=`balanceOf[msg.sender] = 100000000000000000000000000`; 声明 `[2424, 2469] mapping (address => uint256) public balanceOf`; function=`DaEXCoin.constructor()`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `same_name_overlapping_sealed_binding_diagnostic`.

判据引用诊断: `state_binding_unresolved` / `state_name_ambiguous` / name=`balanceOf` / `[2740, 2749]`.

### 111 `0x0da2c2f5bb8cef300e894f47532af79811f0e18a.sol` : 97

- 源码 SHA256: `bed1bbd122c867facae4d77ccf6463500b647d554c4a8eeb31a8a51a5d4350a2`
- 精确证据身份 / difference_id: `6bd2d0e579fc287818ed770ba001ee6fad12eff0cd9507ebd630129ad5aaf6a7`
- 原始行: 97; 字节区间: `[2801, 2842]`; 事件: `totalSupply WRITE`; scope=`fallback`
- 源码短片段: `totalSupply = 100000000000000000000000000`

Slither参考: `WRITE totalSupply`; CFG text=`totalSupply = 100000000000000000000000000`; 声明 `[2391, 2417] uint256 public totalSupply`; function=`DaEXCoin.constructor()`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `same_name_overlapping_sealed_binding_diagnostic`.

判据引用诊断: `state_binding_unresolved` / `state_name_ambiguous` / name=`totalSupply` / `[2801, 2812]`.

### 112 `0x0da2c2f5bb8cef300e894f47532af79811f0e18a.sol` : 107

- 源码 SHA256: `bed1bbd122c867facae4d77ccf6463500b647d554c4a8eeb31a8a51a5d4350a2`
- 精确证据身份 / difference_id: `0219ece98d64afa9734d6cb13c12222068d49f76e4fbdddaba54f0e8c1bcffa1`
- 原始行: 107; 字节区间: `[3071, 3111]`; 事件: `balanceOf READ`; scope=`fallback`
- 源码短片段: `require(balanceOf[msg.sender] >= _value)`

Slither参考: `READ balanceOf`; CFG text=`require(balanceOf[msg.sender] >= _value)`; 声明 `[2424, 2469] mapping (address => uint256) public balanceOf`; function=`DaEXCoin.transfer(address,uint256)`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `same_name_overlapping_sealed_binding_diagnostic`.

判据引用诊断: `state_binding_unresolved` / `state_name_ambiguous` / name=`balanceOf` / `[3079, 3088]`.

### 113 `0x0da2c2f5bb8cef300e894f47532af79811f0e18a.sol` : 108

- 源码 SHA256: `bed1bbd122c867facae4d77ccf6463500b647d554c4a8eeb31a8a51a5d4350a2`
- 精确证据身份 / difference_id: `1fc9e59b6e09faea3145a7b9e8c65e5a0006ba749a4415b79de1e8058ff183f9`
- 原始行: 108; 字节区间: `[3121, 3171]`; 事件: `balanceOf READ`; scope=`fallback`
- 源码短片段: `require(balanceOf[_to] + _value >= balanceOf[_to])`

Slither参考: `READ balanceOf`; CFG text=`require(balanceOf[_to] + _value >= balanceOf[_to])`; 声明 `[2424, 2469] mapping (address => uint256) public balanceOf`; function=`DaEXCoin.transfer(address,uint256)`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `same_name_overlapping_sealed_binding_diagnostic`.

判据引用诊断: `state_binding_unresolved` / `state_name_ambiguous` / name=`balanceOf` / `[3129, 3138]`; `state_binding_unresolved` / `state_name_ambiguous` / name=`balanceOf` / `[3156, 3165]`.

### 114 `0x0da2c2f5bb8cef300e894f47532af79811f0e18a.sol` : 109

- 源码 SHA256: `bed1bbd122c867facae4d77ccf6463500b647d554c4a8eeb31a8a51a5d4350a2`
- 精确证据身份 / difference_id: `c448fc759d9daa27b6a0f5b2e83ff529bfac7f17454b3bea84d761deac05dad2`
- 原始行: 109; 字节区间: `[3175, 3237]`; 事件: `balanceOf READ`; scope=`fallback`
- 源码短片段: `uint previousBalances = balanceOf[msg.sender] + balanceOf[_to]`

Slither参考: `READ balanceOf`; CFG text=`uint previousBalances = balanceOf[msg.sender] + balanceOf[_to]`; 声明 `[2424, 2469] mapping (address => uint256) public balanceOf`; function=`DaEXCoin.transfer(address,uint256)`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `same_name_overlapping_sealed_binding_diagnostic`.

判据引用诊断: `state_binding_unresolved` / `state_name_ambiguous` / name=`balanceOf` / `[3199, 3208]`; `state_binding_unresolved` / `state_name_ambiguous` / name=`balanceOf` / `[3223, 3232]`.

## 访问控制 / L2 / FN / other (5)

### 115 `0x0a43edfe106d295e7c1e591a4b04b5598af9474c.sol` : 172

- 源码 SHA256: `3ed761cd6c5d3208b501dba8e1f263e4ff4a75abecef54cd4abf56986705207c`
- 精确证据身份 / difference_id: `51a3f02f4293d8dae9f628491ac59cf04351d17ec16cacd7885e867849e0aff8`
- 原始行: 172; 字节区间: `[5845, 5862]`; 事件: `tokens WRITE`; scope=`fallback`
- 源码短片段: `token.owner = _to`

Slither参考: `WRITE tokens`; CFG text=`token.owner = _to`; 声明 `[4768, 4810] mapping (bytes32 => TokenLib.Token) tokens`; function=`Devcon2Token.mint(address,string)`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `no_prior_mechanical_predicate`.

此类别仅表示前序机械判据均未成立；不在本页自动判为分析器错误。

### 116 `0x0a43edfe106d295e7c1e591a4b04b5598af9474c.sol` : 173

- 源码 SHA256: `3ed761cd6c5d3208b501dba8e1f263e4ff4a75abecef54cd4abf56986705207c`
- 精确证据身份 / difference_id: `ab115a362662a67e6e4a6340ad34d6f697ec575931647a49153533a3f3bd7d0c`
- 原始行: 173; 字节区间: `[5872, 5898]`; 事件: `tokens WRITE`; scope=`fallback`
- 源码短片段: `token.identity = _identity`

Slither参考: `WRITE tokens`; CFG text=`token.identity = _identity`; 声明 `[4768, 4810] mapping (bytes32 => TokenLib.Token) tokens`; function=`Devcon2Token.mint(address,string)`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `no_prior_mechanical_predicate`.

此类别仅表示前序机械判据均未成立；不在本页自动判为分析器错误。

### 117 `0x0a43edfe106d295e7c1e591a4b04b5598af9474c.sol` : 201

- 源码 SHA256: `3ed761cd6c5d3208b501dba8e1f263e4ff4a75abecef54cd4abf56986705207c`
- 精确证据身份 / difference_id: `b5e54200f84269926dbd9178f26583808efb4b08fbc97247c0a8dc6725d8912d`
- 原始行: 201; 字节区间: `[6636, 6664]`; 事件: `tokens WRITE`; scope=`fallback`
- 源码短片段: `tokenToDestroy.identity = ''`

Slither参考: `WRITE tokens`; CFG text=`tokenToDestroy.identity = ''`; 声明 `[4768, 4810] mapping (bytes32 => TokenLib.Token) tokens`; function=`Devcon2Token.destroy(bytes32)`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `no_prior_mechanical_predicate`.

此类别仅表示前序机械判据均未成立；不在本页自动判为分析器错误。

### 118 `0x0a43edfe106d295e7c1e591a4b04b5598af9474c.sol` : 202

- 源码 SHA256: `3ed761cd6c5d3208b501dba8e1f263e4ff4a75abecef54cd4abf56986705207c`
- 精确证据身份 / difference_id: `e03d23ad0adf27eb5672c1aaa48755824bfeb0e69b7900a9284075d42dd2417e`
- 原始行: 202; 字节区间: `[6674, 6700]`; 事件: `tokens WRITE`; scope=`fallback`
- 源码短片段: `tokenToDestroy.owner = 0x0`

Slither参考: `WRITE tokens`; CFG text=`tokenToDestroy.owner = 0x0`; 声明 `[4768, 4810] mapping (bytes32 => TokenLib.Token) tokens`; function=`Devcon2Token.destroy(bytes32)`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `no_prior_mechanical_predicate`.

此类别仅表示前序机械判据均未成立；不在本页自动判为分析器错误。

### 119 `0x0a43edfe106d295e7c1e591a4b04b5598af9474c.sol` : 268

- 源码 SHA256: `3ed761cd6c5d3208b501dba8e1f263e4ff4a75abecef54cd4abf56986705207c`
- 精确证据身份 / difference_id: `f7ceb9b532f4b122f14b87af246c98e085c77f7b20d1c16a80b91dad59bb794f`
- 原始行: 268; 字节区间: `[8541, 8568]`; 事件: `tokens WRITE`; scope=`fallback`
- 源码短片段: `tokenToTransfer.owner = _to`

Slither参考: `WRITE tokens`; CFG text=`tokenToTransfer.owner = _to`; 声明 `[4768, 4810] mapping (bytes32 => TokenLib.Token) tokens`; function=`Devcon2Token.transfer(address,bytes32)`; context_count=1; 标签=`[]`.

v2：未匹配；没有可认定为本条同名同类型的配对事件。相交候选上下文仅保留在JSON中。

机械判据: `no_prior_mechanical_predicate`.

此类别仅表示前序机械判据均未成立；不在本页自动判为分析器错误。

本页未修改图、源码、标签、6c报告或任何人工边审阅表。类别覆盖表中的零计数类别没有可列样例；其判据仍由正反例单元测试覆盖。
