# reentrancy/0x627fa62ccbb1c1b04ffaecd72a53e37fc0e17839.sol
Source SHA: 295dba1924e8d40f718aa97197ce45871ecae2cec07d13f1bc8ce4b887c06a19
This is a source/label review. Model predictions were not used.

## Summary
~~~json
{
  "source": "/home/zhao/SmartContract/ge-sc-llm/data/smartbug-dataset/dataset/reentrancy/0x627fa62ccbb1c1b04ffaecd72a53e37fc0e17839.sol",
  "source_sha256": "295dba1924e8d40f718aa97197ce45871ecae2cec07d13f1bc8ce4b887c06a19",
  "source_provenance": {
    "path": "/home/zhao/SmartContract/ge-sc-llm/data/smartbug-dataset/dataset/reentrancy/0x627fa62ccbb1c1b04ffaecd72a53e37fc0e17839.sol",
    "sha256": "295dba1924e8d40f718aa97197ce45871ecae2cec07d13f1bc8ce4b887c06a19",
    "equals_git_head": true
  },
  "public_input_provenance": [],
  "source_check": {
    "local_source": "/home/zhao/SmartContract/ge-sc-llm/experiments/ge-sc-data/source_code/reentrancy/source_files/0x627fa62ccbb1c1b04ffaecd72a53e37fc0e17839.sol",
    "canonical_source": "/home/zhao/SmartContract/ge-sc-llm/data/smartbug-dataset/dataset/reentrancy/0x627fa62ccbb1c1b04ffaecd72a53e37fc0e17839.sol",
    "local_sha256": "295dba1924e8d40f718aa97197ce45871ecae2cec07d13f1bc8ce4b887c06a19",
    "canonical_sha256": "295dba1924e8d40f718aa97197ce45871ecae2cec07d13f1bc8ce4b887c06a19",
    "source_comparison": "byte_identical",
    "changed_original_line_ranges": [],
    "local_original_lines": 100,
    "canonical_original_lines": 100,
    "local_preprocessed_lines": 81,
    "canonical_preprocessed_lines": 81,
    "mapping_basis": "canonical_source_original_1based",
    "dataset": "SmartBugs",
    "contract_target": 1,
    "annotation_json": "/home/zhao/SmartContract/ge-sc-llm/data/smartbug-dataset/vulnerabilities.json",
    "annotation_lines": 1,
    "annotation_paths": [
      "dataset/reentrancy/0x627fa62ccbb1c1b04ffaecd72a53e37fc0e17839.sol"
    ],
    "hgt_snapshot_line_differences": [],
    "hgt_snapshot_used_as_ground_truth": false
  },
  "contract_target": 1,
  "original_lines": 100,
  "processed_lines": 81,
  "annotation_original": [
    {
      "category": "reentrancy",
      "lines": [
        94
      ]
    }
  ],
  "public_original_unique": 1,
  "public_processed_lines": [
    75
  ],
  "public_processed_unique": 1,
  "embedded_records": [
    {
      "lines": [
        11
      ],
      "category": "unchecked_low_level_calls"
    }
  ],
  "embedded_all_unique": 1,
  "embedded_target_unique": 0,
  "embedded_categories": [
    "unchecked_low_level_calls"
  ],
  "public_only_processed": [
    75
  ],
  "author_only_processed": [],
  "out_of_bounds_all": [],
  "overlap_processed": [],
  "nodes": 39,
  "author_positive": 1,
  "public_endpoint_positive": 1,
  "public_full_span_positive": 4,
  "disagreements": 2,
  "disagreement_types": {
    "function_definition": 1,
    "if": 1
  },
  "disagreement_direction": {
    "1->0": 1,
    "0->1": 1
  },
  "self_endpoint_replay_mismatches": [],
  "projection_verified": {
    "ordinary_nodes_checked": 33,
    "synthetic_nodes": 6
  },
  "source_token_sequence_unchanged": true,
  "old_mapper_annotation_projection_equal": true,
  "csv_overlap_lines": []
}
~~~
## Source with raw and preprocessed coordinate correspondence
~~~text
   1 ->              [      ] /*
   2 ->              [      ]  * @source: etherscan.io 
   3 ->              [      ]  * @author: -
   4 ->              [      ]  * @vulnerable_at_lines: 94
   5 ->              [      ]  */
   6 ->              [      ] 
   7 -> 1            [      ] pragma solidity ^0.4.19;
   8 ->              [      ] 
   9 -> 2            [      ] contract Ownable
  10 -> 3            [      ] {
  11 -> 4            [      ]     address newOwner;
  12 -> 5            [      ]     address owner = msg.sender;
  13 ->              [      ]     
  14 -> 6            [      ]     function changeOwner(address addr)
  15 -> 7            [      ]     public
  16 -> 8            [      ]     onlyOwner
  17 -> 9            [      ]     {
  18 -> 10           [      ]         newOwner = addr;
  19 -> 11           [      ]     }
  20 ->              [      ]     
  21 -> 12           [      ]     function confirmOwner() 
  22 -> 13           [      ]     public
  23 -> 14           [      ]     {
  24 -> 15           [      ]         if(msg.sender==newOwner)
  25 -> 16           [      ]         {
  26 -> 17           [      ]             owner=newOwner;
  27 -> 18           [      ]         }
  28 -> 19           [      ]     }
  29 ->              [      ]     
  30 -> 20           [      ]     modifier onlyOwner
  31 -> 21           [      ]     {
  32 -> 22           [      ]         if(owner == msg.sender)_;
  33 -> 23           [      ]     }
  34 -> 24           [      ] }
  35 ->              [      ] 
  36 -> 25           [      ] contract Token is Ownable
  37 -> 26           [      ] {
  38 -> 27           [      ]     address owner = msg.sender;
  39 -> 28           [      ]     function WithdrawToken(address token, uint256 amount,address to)
  40 -> 29           [      ]     public 
  41 -> 30           [      ]     onlyOwner
  42 -> 31           [      ]     {
  43 -> 32           [      ]         token.call(bytes4(sha3("transfer(address,uint256)")),to,amount); 
  44 -> 33           [      ]     }
  45 -> 34           [      ] }
  46 ->              [      ] 
  47 -> 35           [      ] contract TokenBank is Token
  48 -> 36           [      ] {
  49 -> 37           [      ]     uint public MinDeposit;
  50 -> 38           [      ]     mapping (address => uint) public Holders;
  51 ->              [      ]     
  52 ->              [      ]      ///Constructor
  53 -> 39           [      ]     function initTokenBank()
  54 -> 40           [      ]     public
  55 -> 41           [      ]     {
  56 -> 42           [      ]         owner = msg.sender;
  57 -> 43           [      ]         MinDeposit = 1 ether;
  58 -> 44           [      ]     }
  59 ->              [      ]     
  60 -> 45           [      ]     function()
  61 -> 46           [      ]     payable
  62 -> 47           [      ]     {
  63 -> 48           [      ]         Deposit();
  64 -> 49           [      ]     }
  65 ->              [      ]    
  66 -> 50           [      ]     function Deposit() 
  67 -> 51           [      ]     payable
  68 -> 52           [      ]     {
  69 -> 53           [      ]         if(msg.value>MinDeposit)
  70 -> 54           [      ]         {
  71 -> 55           [      ]             Holders[msg.sender]+=msg.value;
  72 -> 56           [      ]         }
  73 -> 57           [      ]     }
  74 ->              [      ]     
  75 -> 58           [      ]     function WitdrawTokenToHolder(address _to,address _token,uint _amount)
  76 -> 59           [      ]     public
  77 -> 60           [      ]     onlyOwner
  78 -> 61           [      ]     {
  79 -> 62           [      ]         if(Holders[_to]>0)
  80 -> 63           [      ]         {
  81 -> 64           [      ]             Holders[_to]=0;
  82 -> 65           [      ]             WithdrawToken(_token,_amount,_to);     
  83 -> 66           [      ]         }
  84 -> 67           [      ]     }
  85 ->              [      ]    
  86 -> 68           [      ]     function WithdrawToHolder(address _addr, uint _wei) 
  87 -> 69           [      ]     public
  88 -> 70           [      ]     onlyOwner
  89 -> 71           [      ]     payable
  90 -> 72           [      ]     {
  91 -> 73           [      ]         if(Holders[_addr]>0)
  92 -> 74           [      ]         {
  93 ->              [      ]             // <yes> <report> REENTRANCY
  94 -> 75           [public]             if(_addr.call.value(_wei)())
  95 -> 76           [      ]             {
  96 -> 77           [      ]                 Holders[_addr]-=_wei;
  97 -> 78           [      ]             }
  98 -> 79           [      ]         }
  99 -> 80           [      ]     }
 100 -> 81           [      ] }
~~~
## All node disagreements

### Node 5814 function_definition
Author 1 / public endpoint 0; processed [6, 11] -> original [14, 19]
~~~solidity
function changeOwner(address addr)
    public
    onlyOwner
    {
        newOwner = addr;
    }
~~~

### Node 5847 if
Author 0 / public endpoint 1; processed [75, 78] -> original [94, 97]
~~~solidity
if(_addr.call.value(_wei)())
            {
                Holders[_addr]-=_wei;
            }
~~~
