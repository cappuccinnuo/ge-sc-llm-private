# Fixed finite source review snippets

## G01 reentrancy_author STATE_DEF_USE
0xa4f9fe0ad9b9765dc0364444332fa4c69923a6d3.sol:54 -> 55
function: 0xa4f9fe0ad9b9765dc0364444332fa4c69923a6d3.sol:1475
nodes: 11053 -> 11054
declarations: ['address public admin;', 'address public admin;']
```solidity
admin = 0x6585b849371A40005F9dCda57668C832a5be1777; //Set initial admin
        level[admin] = 2;
```

## G02 reentrancy_author STATE_DEF_USE
0xa5b91fbfec2f9a708592f9cd3c9e20becdfcb816.sol:27 -> 28
function: 0xa5b91fbfec2f9a708592f9cd3c9e20becdfcb816.sol:760
nodes: 26 -> 27
declarations: ['address private owner = address(0);', 'address private owner = address(0);']
```solidity
owner = msg.sender;
    balances[owner] = totalSupply;
```

## G03 reentrancy_author STATE_DEF_USE
0xa8ec550c291993a450ea525d90863e61a7ebef5c.sol:74 -> 75
function: 0xa8ec550c291993a450ea525d90863e61a7ebef5c.sol:2371
nodes: 14918 -> 14919
declarations: ['address public owner;', 'address public owner;']
```solidity
owner = msg.sender;
         balances[owner] = _totalSupply;
```

## G04 reentrancy_author STATE_DEF_USE
buggy_32.sol:291 -> 292
function: buggy_32.sol:10896
nodes: 4167 -> 4168
declarations: ['uint256 public totalSupply;', 'uint256 public totalSupply;']
```solidity
totalSupply = 180000000 * (10**uint256(decimals)); //initial token creation
        balances[initialOwner] = totalSupply;
```

## G05 reentrancy_author STATE_DEF_USE
buggy_47.sol:149 -> 150
function: buggy_47.sol:5597
nodes: 9216 -> 9217
declarations: ['address public founder;', 'address public founder;']
```solidity
founder = msg.sender;
        balances[founder] = supply;
```

## G06 reentrancy_author STATE_DEF_USE
buggy_47.sol:148 -> 150
function: buggy_47.sol:5597
nodes: 9215 -> 9217
declarations: ['uint public supply;', 'uint public supply;']
```solidity
supply = 200000000;
        founder = msg.sender;
        balances[founder] = supply;
```

## G07 access_control_author STATE_DEF_USE
0x0c6e8a8358cbde54f8e4cd7f07d5ac38aec8c5a4.sol:116 -> 117
function: 0x0c6e8a8358cbde54f8e4cd7f07d5ac38aec8c5a4.sol:3051
nodes: 9776 -> 9777
declarations: ['address public owner;', 'address public owner;']
```solidity
owner = msg.sender;
       balances[owner] = totalSaleSupply;
```

## G08 access_control_author STATE_DEF_USE
0x0da9326d7da81f8b19a8ec2d3255ab7076768c2d.sol:150 -> 151
function: 0x0da9326d7da81f8b19a8ec2d3255ab7076768c2d.sol:4490
nodes: 12198 -> 12199
declarations: ['uint bonusCalculationFactor;', 'uint bonusCalculationFactor;']
```solidity
bonusCalculationFactor = (block.timestamp.sub(ico_startdate)).div(3600); //time period in seconds
        if (bonusCalculationFactor== 0) 
            price_tokn = 70;                     //30 % Discount
        else if (bonusCalculationFactor >= 1 && bonusCalculationFactor < 24) 
            price_tokn = 75;                     //25 % Discount
        else if (bonusCalculationFactor >= 24 && bonusCalculationFactor < 168) 
            price_tokn = 80;                      //20 % Discount
        else if (bonusCalculationFactor >= 168 && bonusCalculationFactor < 336) 
            price_tokn = 90;                     //10 % Discount
        else if (bonusCalculationFactor >= 336) 
            price_tokn = 100;
```

## G09 access_control_author STATE_DEF_USE
0x0da9326d7da81f8b19a8ec2d3255ab7076768c2d.sol:150 -> 153
function: 0x0da9326d7da81f8b19a8ec2d3255ab7076768c2d.sol:4490
nodes: 12198 -> 12202
declarations: ['uint bonusCalculationFactor;', 'uint bonusCalculationFactor;']
```solidity
bonusCalculationFactor = (block.timestamp.sub(ico_startdate)).div(3600); //time period in seconds
        if (bonusCalculationFactor== 0) 
            price_tokn = 70;                     //30 % Discount
        else if (bonusCalculationFactor >= 1 && bonusCalculationFactor < 24) 
            price_tokn = 75;                     //25 % Discount
        else if (bonusCalculationFactor >= 24 && bonusCalculationFactor < 168) 
            price_tokn = 80;                      //20 % Discount
        else if (bonusCalculationFactor >= 168 && bonusCalculationFactor < 336) 
            price_tokn = 90;                     //10 % Discount
        else if (bonusCalculationFactor >= 336) 
            price_tokn = 100;
```

## G10 access_control_author STATE_DEF_USE
0x0da9326d7da81f8b19a8ec2d3255ab7076768c2d.sol:150 -> 155
function: 0x0da9326d7da81f8b19a8ec2d3255ab7076768c2d.sol:4490
nodes: 12198 -> 12204
declarations: ['uint bonusCalculationFactor;', 'uint bonusCalculationFactor;']
```solidity
bonusCalculationFactor = (block.timestamp.sub(ico_startdate)).div(3600); //time period in seconds
        if (bonusCalculationFactor== 0) 
            price_tokn = 70;                     //30 % Discount
        else if (bonusCalculationFactor >= 1 && bonusCalculationFactor < 24) 
            price_tokn = 75;                     //25 % Discount
        else if (bonusCalculationFactor >= 24 && bonusCalculationFactor < 168) 
            price_tokn = 80;                      //20 % Discount
        else if (bonusCalculationFactor >= 168 && bonusCalculationFactor < 336) 
            price_tokn = 90;                     //10 % Discount
        else if (bonusCalculationFactor >= 336) 
            price_tokn = 100;
```

## G11 access_control_author STATE_DEF_USE
0x0da9326d7da81f8b19a8ec2d3255ab7076768c2d.sol:150 -> 157
function: 0x0da9326d7da81f8b19a8ec2d3255ab7076768c2d.sol:4490
nodes: 12198 -> 12206
declarations: ['uint bonusCalculationFactor;', 'uint bonusCalculationFactor;']
```solidity
bonusCalculationFactor = (block.timestamp.sub(ico_startdate)).div(3600); //time period in seconds
        if (bonusCalculationFactor== 0) 
            price_tokn = 70;                     //30 % Discount
        else if (bonusCalculationFactor >= 1 && bonusCalculationFactor < 24) 
            price_tokn = 75;                     //25 % Discount
        else if (bonusCalculationFactor >= 24 && bonusCalculationFactor < 168) 
            price_tokn = 80;                      //20 % Discount
        else if (bonusCalculationFactor >= 168 && bonusCalculationFactor < 336) 
            price_tokn = 90;                     //10 % Discount
        else if (bonusCalculationFactor >= 336) 
            price_tokn = 100;
```

## G12 access_control_author STATE_DEF_USE
0x0da9326d7da81f8b19a8ec2d3255ab7076768c2d.sol:150 -> 159
function: 0x0da9326d7da81f8b19a8ec2d3255ab7076768c2d.sol:4490
nodes: 12198 -> 12208
declarations: ['uint bonusCalculationFactor;', 'uint bonusCalculationFactor;']
```solidity
bonusCalculationFactor = (block.timestamp.sub(ico_startdate)).div(3600); //time period in seconds
        if (bonusCalculationFactor== 0) 
            price_tokn = 70;                     //30 % Discount
        else if (bonusCalculationFactor >= 1 && bonusCalculationFactor < 24) 
            price_tokn = 75;                     //25 % Discount
        else if (bonusCalculationFactor >= 24 && bonusCalculationFactor < 168) 
            price_tokn = 80;                      //20 % Discount
        else if (bonusCalculationFactor >= 168 && bonusCalculationFactor < 336) 
            price_tokn = 90;                     //10 % Discount
        else if (bonusCalculationFactor >= 336) 
            price_tokn = 100;
```

## G13 access_control_author STATE_DEF_USE
0x0ef23ae0a27130999bf9d886e9598ff355ecf323.sol:20 -> 22
function: 0x0ef23ae0a27130999bf9d886e9598ff355ecf323.sol:272
nodes: 7915 -> 7917
declarations: ['uint private created_at;', 'uint private created_at;']
```solidity
created_at = now;
        updated_at = now;
        expires_at = created_at + (_lifetime * 60*60*24);
```

## G14 access_control_author STATE_DEF_USE
buggy_32.sol:209 -> 210
function: buggy_32.sol:7935
nodes: 2590 -> 2591
declarations: ['uint256 public totalSupply;', 'uint256 public totalSupply;']
```solidity
totalSupply = 180000000 * (10**uint256(decimals)); //initial token creation
        balances[initialOwner] = totalSupply;
```

## G15 access_control_author STATE_DEF_USE
buggy_47.sol:96 -> 97
function: buggy_47.sol:3777
nodes: 6500 -> 6501
declarations: ['address public founder;', 'address public founder;']
```solidity
founder = msg.sender;
        balances[founder] = supply;
```

## G16 access_control_author STATE_DEF_USE
buggy_47.sol:95 -> 97
function: buggy_47.sol:3777
nodes: 6499 -> 6501
declarations: ['uint public supply;', 'uint public supply;']
```solidity
supply = 200000000;
        founder = msg.sender;
        balances[founder] = supply;
```

## G17 access_control_author STATE_DEF_USE
multiowned_vulnerable.sol:21 -> 22
function: multiowned_vulnerable.sol:521
nodes: 3169 -> 3170
declarations: ['address public root;', 'address public root;']
```solidity
root = msg.sender;
    owners[root] = root;
```

## G18 reentrancy_author STATE_ACCESS_ORDER
buggy_43.sol:92 -> 94
function: buggy_43.sol:2917
nodes: 11430 -> 11432
declarations: ['address payable lastPlayer_re_ent37;', 'address payable lastPlayer_re_ent37;']
```solidity
if (!(lastPlayer_re_ent37.send(jackpot_re_ent37)))
        revert();
      lastPlayer_re_ent37 = msg.sender;
```

## G19 access_control_author STATE_ACCESS_ORDER
multiowned_vulnerable.sol:21 -> 22
function: multiowned_vulnerable.sol:521
nodes: 3169 -> 3170
declarations: ['address public root;', 'address public root;']
```solidity
root = msg.sender;
    owners[root] = root;
```

## G20 reentrancy_author STATE_ACCESS_ORDER
buggy_45.sol:156 -> 160
function: buggy_45.sol:5055
nodes: 9776 -> 9779
declarations: ['mapping(address => uint) balances_re_ent3;', 'mapping(address => uint) balances_re_ent3;']
```solidity
require(balances_re_ent3[msg.sender] >= _weiToWithdraw);
        // limit the withdrawal
	(bool success,)= msg.sender.call.value(_weiToWithdraw)("");
        require(success);  //bug
        balances_re_ent3[msg.sender] -= _weiToWithdraw;
```

## G21 reentrancy_author STATE_ACCESS_ORDER
reentrancy_bonus.sol:17 -> 18
function: reentrancy_bonus.sol:372
nodes: 5 -> 6
declarations: ['mapping (address => uint) private rewardsForA;', 'mapping (address => uint) private rewardsForA;']
```solidity
uint amountToWithdraw = rewardsForA[recipient];
        rewardsForA[recipient] = 0;
```

## G22 reentrancy_author STATE_ACCESS_ORDER
buggy_24.sol:872 -> 873
function: buggy_24.sol:34387
nodes: 2004 -> 2006
declarations: ['mapping(address => uint) balances_re_ent36;', 'mapping(address => uint) balances_re_ent36;']
```solidity
if (msg.sender.send(balances_re_ent36[msg.sender ]))
          balances_re_ent36[msg.sender] = 0;
```

## G23 reentrancy_author STATE_ACCESS_ORDER
buggy_45.sol:37 -> 41
function: buggy_45.sol:1084
nodes: 9700 -> 9703
declarations: ['mapping(address => uint) userBalance_re_ent40;', 'mapping(address => uint) userBalance_re_ent40;']
```solidity
(bool success,)=msg.sender.call.value(userBalance_re_ent40[msg.sender])("");
        if( ! success ){
            revert();
        }
        userBalance_re_ent40[msg.sender] = 0;
```

## G24 reentrancy_author STATE_ACCESS_ORDER
buggy_2.sol:227 -> 229
function: buggy_2.sol:8167
nodes: 5127 -> 5129
declarations: ['mapping(address => uint) redeemableEther_re_ent39;', 'mapping(address => uint) redeemableEther_re_ent39;']
```solidity
uint transferValue_re_ent39 = redeemableEther_re_ent39[msg.sender];
        msg.sender.transfer(transferValue_re_ent39);   //bug
        redeemableEther_re_ent39[msg.sender] = 0;
```

## G25 reentrancy_author STATE_ACCESS_ORDER
buggy_49.sol:60 -> 64
function: buggy_49.sol:2041
nodes: 13596 -> 13599
declarations: ['uint256 counter_re_ent35 =0;', 'uint256 counter_re_ent35 =0;']
```solidity
require(counter_re_ent35<=5);
	if( ! (msg.sender.send(10 ether) ) ){
            revert();
        }
        counter_re_ent35 += 1;
```

## G26 reentrancy_author EXTERNAL_CALL_BEFORE_STATE_WRITE
buggy_45.sol:128 -> 130
function: buggy_45.sol:4040
nodes: 9753 -> 9755
declarations: ['address payable lastPlayer_re_ent2;']
```solidity
if (!(lastPlayer_re_ent2.send(jackpot_re_ent2)))
        revert();
      lastPlayer_re_ent2 = msg.sender;
```

## G27 reentrancy_author EXTERNAL_CALL_BEFORE_STATE_WRITE
buggy_2.sol:41 -> 42
function: buggy_2.sol:1268
nodes: 5013 -> 5014
declarations: ['mapping(address => uint) redeemableEther_re_ent25;']
```solidity
msg.sender.transfer(transferValue_re_ent25);   //bug
        redeemableEther_re_ent25[msg.sender] = 0;
```

## G28 reentrancy_author EXTERNAL_CALL_BEFORE_STATE_WRITE
buggy_43.sol:121 -> 124
function: buggy_43.sol:3972
nodes: 11450 -> 11453
declarations: ['address payable lastPlayer_re_ent9;']
```solidity
(bool success,) = lastPlayer_re_ent9.call.value(jackpot_re_ent9)("");
	    if (!success)
	        revert();
      lastPlayer_re_ent9 = msg.sender;
```

## G29 reentrancy_author EXTERNAL_CALL_BEFORE_STATE_WRITE
buggy_3.sol:269 -> 272
function: buggy_3.sol:9787
nodes: 3527 -> 3529
declarations: ['uint256 counter_re_ent35 =0;']
```solidity
if( ! (msg.sender.send(10 ether) ) ){
            revert();
        }
        counter_re_ent35 += 1;
```

## G30 reentrancy_author EXTERNAL_CALL_BEFORE_STATE_WRITE
buggy_16.sol:157 -> 160
function: buggy_16.sol:5331
nodes: 15888 -> 15890
declarations: ['bool not_called_re_ent41 = true;']
```solidity
if( ! (msg.sender.send(1 ether) ) ){
            revert();
        }
        not_called_re_ent41 = false;
```

## G31 reentrancy_author EXTERNAL_CALL_BEFORE_STATE_WRITE
buggy_7.sol:320 -> 321
function: buggy_7.sol:10141
nodes: 6757 -> 6758
declarations: ['mapping(address => uint) balances_re_ent31;']
```solidity
require(msg.sender.send(_weiToWithdraw));  //bug
        balances_re_ent31[msg.sender] -= _weiToWithdraw;
```

## G32 reentrancy_author EXTERNAL_CALL_BEFORE_STATE_WRITE
buggy_25.sol:350 -> 352
function: buggy_25.sol:13957
nodes: 672 -> 675
declarations: ['mapping(address => uint) balances_re_ent8;']
```solidity
(bool success,) = msg.sender.call.value(balances_re_ent8[msg.sender ])("");
       if (success)
          balances_re_ent8[msg.sender] = 0;
```

## G33 reentrancy_author EXTERNAL_CALL_BEFORE_STATE_WRITE
buggy_7.sol:20 -> 23
function: buggy_7.sol:464
nodes: 6572 -> 6574
declarations: ['mapping(address => uint) userBalance_re_ent12;']
```solidity
if( ! (msg.sender.send(userBalance_re_ent12[msg.sender]) ) ){
            revert();
        }
        userBalance_re_ent12[msg.sender] = 0;
```

