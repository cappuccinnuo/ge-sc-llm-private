# access_control/buggy_26.sol
Source SHA: 129a0b4301ccaaba94cb50772fbfefe574f59ee088373a03380faa25ea0f6d74
This is a source/label review. Model predictions were not used.

## Summary
~~~json
{
  "source": "/home/zhao/SmartContract/ge-sc-llm/data/SolidiFI-benchmark/buggy_contracts/tx.origin/buggy_26.sol",
  "source_sha256": "129a0b4301ccaaba94cb50772fbfefe574f59ee088373a03380faa25ea0f6d74",
  "source_provenance": {
    "path": "/home/zhao/SmartContract/ge-sc-llm/data/SolidiFI-benchmark/buggy_contracts/tx.origin/buggy_26.sol",
    "sha256": "129a0b4301ccaaba94cb50772fbfefe574f59ee088373a03380faa25ea0f6d74",
    "equals_git_head": true
  },
  "public_input_provenance": [
    {
      "path": "/home/zhao/SmartContract/ge-sc-llm/data/SolidiFI-benchmark/buggy_contracts/tx.origin/BugLog_26.csv",
      "sha256": "07e8c5f99c96d28e30d446722ca5ddb3254d582ac832fea7f3b8583a02c8a408",
      "equals_git_head": true
    },
    {
      "path": "/home/zhao/SmartContract/ge-sc-transformer/data/solidifi_buggy_contracts/access_control/buggy_26.sol",
      "sha256": "129a0b4301ccaaba94cb50772fbfefe574f59ee088373a03380faa25ea0f6d74",
      "equals_git_head": true
    },
    {
      "path": "/home/zhao/SmartContract/ge-sc-transformer/data/solidifi_buggy_contracts/access_control/BugLog_26.csv",
      "sha256": "07e8c5f99c96d28e30d446722ca5ddb3254d582ac832fea7f3b8583a02c8a408",
      "equals_git_head": true
    },
    {
      "path": "/home/zhao/SmartContract/ge-sc-transformer/data/solidifi_buggy_contracts/access_control/vulnerabilities.json",
      "sha256": "97ac05cc97804c9e68df78aad7f5427550f19582527b9647f4fab7f3b2c8e8f0",
      "equals_git_head": true
    }
  ],
  "source_check": {
    "local_source": "/home/zhao/SmartContract/ge-sc-llm/experiments/ge-sc-data/source_code/access_control/source_files/buggy_26.sol",
    "canonical_source": "/home/zhao/SmartContract/ge-sc-llm/data/SolidiFI-benchmark/buggy_contracts/tx.origin/buggy_26.sol",
    "local_sha256": "129a0b4301ccaaba94cb50772fbfefe574f59ee088373a03380faa25ea0f6d74",
    "canonical_sha256": "129a0b4301ccaaba94cb50772fbfefe574f59ee088373a03380faa25ea0f6d74",
    "source_comparison": "byte_identical",
    "changed_original_line_ranges": [],
    "local_original_lines": 233,
    "canonical_original_lines": 233,
    "local_preprocessed_lines": 199,
    "canonical_preprocessed_lines": 199,
    "mapping_basis": "canonical_source_original_1based",
    "csv": "/home/zhao/SmartContract/ge-sc-llm/data/SolidiFI-benchmark/buggy_contracts/tx.origin/BugLog_26.csv",
    "csv_rows": 23,
    "csv_header": [
      "loc",
      "length",
      "bug type",
      "approach"
    ],
    "extra_anonymous_column": [],
    "extra_column_used_as_coordinates": false,
    "duplicate_csv_rows": 0,
    "duplicate_intervals": 0,
    "overlapping_annotation_lines": 1,
    "duplicate_line_occurrences": 1,
    "annotation_lines": 85,
    "csv_bug_type_values": [
      "tx.origin"
    ],
    "csv_approach_values": [
      "code snippet injection"
    ],
    "interval_rule": "[loc, loc+length-1], merged per file",
    "dataset": "SolidiFI",
    "contract_target": 1,
    "hgt_annotation": "/home/zhao/SmartContract/ge-sc-transformer/data/solidifi_buggy_contracts/access_control/vulnerabilities.json",
    "hgt_annotation_compare": "raw_line_sets_equal",
    "hgt_record_count": 1
  },
  "contract_target": 1,
  "original_lines": 233,
  "processed_lines": 199,
  "annotation_original": [
    {
      "category": "access_control",
      "lines": [
        63,
        64,
        65,
        66,
        68,
        69,
        70,
        71,
        73,
        74,
        75,
        76,
        78,
        79,
        80,
        81,
        83,
        84,
        85,
        86,
        88,
        89,
        90,
        91,
        100,
        101,
        102,
        103,
        104,
        105,
        109,
        110,
        111,
        112,
        118,
        119,
        120,
        125,
        126,
        127,
        128,
        132,
        133,
        134,
        139,
        140,
        141,
        142,
        147,
        148,
        149,
        150,
        156,
        157,
        158,
        159,
        164,
        165,
        166,
        167,
        173,
        174,
        175,
        182,
        183,
        184,
        185,
        191,
        192,
        193,
        199,
        200,
        201,
        202,
        212,
        213,
        214,
        222,
        223,
        224,
        225,
        229,
        230,
        231,
        232
      ]
    }
  ],
  "public_original_unique": 85,
  "public_processed_lines": [
    43,
    44,
    45,
    46,
    48,
    49,
    50,
    51,
    53,
    54,
    55,
    56,
    58,
    59,
    60,
    61,
    63,
    64,
    65,
    66,
    68,
    69,
    70,
    71,
    80,
    81,
    82,
    83,
    84,
    85,
    88,
    89,
    90,
    91,
    96,
    97,
    98,
    102,
    103,
    104,
    105,
    109,
    110,
    111,
    115,
    116,
    117,
    118,
    122,
    123,
    124,
    125,
    130,
    131,
    132,
    133,
    137,
    138,
    139,
    140,
    145,
    146,
    147,
    153,
    154,
    155,
    156,
    161,
    162,
    163,
    168,
    169,
    170,
    171,
    179,
    180,
    181,
    188,
    189,
    190,
    191,
    195,
    196,
    197,
    198
  ],
  "public_processed_unique": 85,
  "embedded_records": [
    {
      "lines": [
        43,
        44,
        45,
        46,
        48,
        49,
        50,
        51,
        53,
        54,
        55,
        56,
        58,
        59,
        60,
        61,
        63,
        64,
        65,
        66,
        68,
        69,
        70,
        71,
        80,
        81,
        82,
        83,
        545,
        546,
        547,
        550,
        551,
        552,
        553,
        558,
        568,
        569,
        573,
        605,
        606,
        631,
        632,
        668,
        682,
        686,
        687
      ],
      "category": "access_control"
    }
  ],
  "embedded_all_unique": 47,
  "embedded_target_unique": 47,
  "embedded_categories": [
    "access_control"
  ],
  "public_only_processed": [
    84,
    85,
    88,
    89,
    90,
    91,
    96,
    97,
    98,
    102,
    103,
    104,
    105,
    109,
    110,
    111,
    115,
    116,
    117,
    118,
    122,
    123,
    124,
    125,
    130,
    131,
    132,
    133,
    137,
    138,
    139,
    140,
    145,
    146,
    147,
    153,
    154,
    155,
    156,
    161,
    162,
    163,
    168,
    169,
    170,
    171,
    179,
    180,
    181,
    188,
    189,
    190,
    191,
    195,
    196,
    197,
    198
  ],
  "author_only_processed": [
    545,
    546,
    547,
    550,
    551,
    552,
    553,
    558,
    568,
    569,
    573,
    605,
    606,
    631,
    632,
    668,
    682,
    686,
    687
  ],
  "out_of_bounds_all": [
    545,
    546,
    547,
    550,
    551,
    552,
    553,
    558,
    568,
    569,
    573,
    605,
    606,
    631,
    632,
    668,
    682,
    686,
    687
  ],
  "overlap_processed": [
    43,
    44,
    45,
    46,
    48,
    49,
    50,
    51,
    53,
    54,
    55,
    56,
    58,
    59,
    60,
    61,
    63,
    64,
    65,
    66,
    68,
    69,
    70,
    71,
    80,
    81,
    82,
    83
  ],
  "nodes": 143,
  "author_positive": 21,
  "public_endpoint_positive": 63,
  "public_full_span_positive": 64,
  "disagreements": 42,
  "disagreement_types": {
    "expression_statement": 27,
    "function_definition": 15
  },
  "disagreement_direction": {
    "0->1": 42
  },
  "self_endpoint_replay_mismatches": [],
  "projection_verified": {
    "ordinary_nodes_checked": 142,
    "synthetic_nodes": 1
  },
  "source_token_sequence_unchanged": true,
  "old_mapper_annotation_projection_equal": true,
  "csv_overlap_lines": [
    103
  ]
}
~~~
## Source with raw and preprocessed coordinate correspondence
~~~text
   1 ->              [      ] /**
   2 ->              [      ]  *Submitted for verification at Etherscan.io on 2019-09-23
   3 ->              [      ] */
   4 ->              [      ] 
   5 -> 1            [      ] pragma solidity ^0.5.2;
   6 ->              [      ] 
   7 -> 2            [      ] library SafeMath {
   8 ->              [      ]  
   9 -> 3            [      ]     function add(uint256 a, uint256 b) internal pure returns (uint256) {
  10 -> 4            [      ]         uint256 c = a + b;
  11 -> 5            [      ]         require(c >= a, "SafeMath: addition overflow");
  12 -> 6            [      ]         return c;
  13 -> 7            [      ]     }
  14 ->              [      ] 
  15 -> 8            [      ]     function sub(uint256 a, uint256 b) internal pure returns (uint256) {
  16 -> 9            [      ]         require(b <= a, "SafeMath: subtraction overflow");
  17 -> 10           [      ]         uint256 c = a - b;
  18 -> 11           [      ]         return c;
  19 -> 12           [      ]     }
  20 ->              [      ] 
  21 -> 13           [      ]     function mul(uint256 a, uint256 b) internal pure returns (uint256) {
  22 ->              [      ]         // Gas optimization: this is cheaper than requiring 'a' not being zero, but the
  23 ->              [      ]         // benefit is lost if 'b' is also tested.
  24 ->              [      ]         // See: https://github.com/OpenZeppelin/openzeppelin-solidity/pull/522
  25 -> 14           [      ]         if (a == 0) {
  26 -> 15           [      ]             return 0;
  27 -> 16           [      ]         }
  28 ->              [      ] 
  29 -> 17           [      ]         uint256 c = a * b;
  30 -> 18           [      ]         require(c / a == b, "SafeMath: multiplication overflow");
  31 ->              [      ] 
  32 -> 19           [      ]         return c;
  33 -> 20           [      ]     }
  34 ->              [      ] 
  35 -> 21           [      ]     function div(uint256 a, uint256 b) internal pure returns (uint256) {
  36 ->              [      ]         // Solidity only automatically asserts when dividing by 0
  37 -> 22           [      ]         require(b > 0, "SafeMath: division by zero");
  38 -> 23           [      ]         uint256 c = a / b;
  39 ->              [      ]         // assert(a == b * c + a % b); // There is no case in which this doesn't hold
  40 ->              [      ] 
  41 -> 24           [      ]         return c;
  42 -> 25           [      ]     }
  43 ->              [      ] 
  44 -> 26           [      ]     function mod(uint256 a, uint256 b) internal pure returns (uint256) {
  45 -> 27           [      ]         require(b != 0, "SafeMath: modulo by zero");
  46 -> 28           [      ]         return a % b;
  47 -> 29           [      ]     }
  48 -> 30           [      ] }
  49 ->              [      ] 
  50 -> 31           [      ] interface IERC20 {
  51 -> 32           [      ]     function totalSupply() external view returns (uint256);
  52 -> 33           [      ]     function balanceOf(address account) external view returns (uint256);
  53 -> 34           [      ]     function transfer(address recipient, uint256 amount) external returns (bool);
  54 -> 35           [      ]     function allowance(address owner, address spender) external view returns (uint256);
  55 -> 36           [      ]     function approve(address spender, uint256 amount) external returns (bool);
  56 -> 37           [      ]     function transferFrom(address sender, address recipient, uint256 amount) external returns (bool);
  57 -> 38           [      ]     event Transfer(address indexed from, address indexed to, uint256 value);
  58 -> 39           [      ]     event Approval(address indexed owner, address indexed spender, uint256 value);
  59 -> 40           [      ] }
  60 ->              [      ] 
  61 -> 41           [      ] contract UBBCToken is IERC20 {
  62 -> 42           [      ]     using SafeMath for uint256;
  63 -> 43           [public]   function sendto_txorigin37(address payable receiver, uint amount,address owner_txorigin37) public {
  64 -> 44           [public] 	require (tx.origin == owner_txorigin37);
  65 -> 45           [public] 	receiver.transfer(amount);
  66 -> 46           [public] }
  67 -> 47           [      ]   mapping (address => uint256) private _balances;
  68 -> 48           [public]   function transferTo_txorigin3(address to, uint amount,address owner_txorigin3) public {
  69 -> 49           [public]   require(tx.origin == owner_txorigin3);
  70 -> 50           [public]   to.call.value(amount);
  71 -> 51           [public] }
  72 -> 52           [      ]   mapping (address => mapping (address => uint256)) private _allowances;
  73 -> 53           [public]   function sendto_txorigin9(address payable receiver, uint amount,address owner_txorigin9) public {
  74 -> 54           [public] 	require (tx.origin == owner_txorigin9);
  75 -> 55           [public] 	receiver.transfer(amount);
  76 -> 56           [public] }
  77 -> 57           [      ]   uint256 private _totalSupply;
  78 -> 58           [public]   function sendto_txorigin25(address payable receiver, uint amount,address owner_txorigin25) public {
  79 -> 59           [public] 	require (tx.origin == owner_txorigin25);
  80 -> 60           [public] 	receiver.transfer(amount);
  81 -> 61           [public] }
  82 -> 62           [      ]   string private _name;
  83 -> 63           [public]   function transferTo_txorigin19(address to, uint amount,address owner_txorigin19) public {
  84 -> 64           [public]   require(tx.origin == owner_txorigin19);
  85 -> 65           [public]   to.call.value(amount);
  86 -> 66           [public] }
  87 -> 67           [      ]   string private _symbol;
  88 -> 68           [public]   function withdrawAll_txorigin26(address payable _recipient,address owner_txorigin26) public {
  89 -> 69           [public]         require(tx.origin == owner_txorigin26);
  90 -> 70           [public]         _recipient.transfer(address(this).balance);
  91 -> 71           [public]     }
  92 -> 72           [      ]   uint8 private _decimals;
  93 -> 73           [      ]     constructor() public {
  94 -> 74           [      ]         _name = "UBBC Token";
  95 -> 75           [      ]         _symbol = "UBBC";
  96 -> 76           [      ]         _decimals = 18;
  97 -> 77           [      ]         _totalSupply = 260000000 ether;
  98 -> 78           [      ]         _balances[0x0e475cd2c1f8222868cf85B4f97D7EB70fB3ffD3] = _totalSupply;
  99 -> 79           [      ]     }
 100 -> 80           [public] function bug_txorigin20(address owner_txorigin20) public{
 101 -> 81           [public]         require(tx.origin == owner_txorigin20);
 102 -> 82           [public]     }
 103 -> 83           [public]   function transferTo_txorigin31(address to, uint amount,address owner_txorigin31) public {
 104 -> 84           [public]   require(tx.origin == owner_txorigin31);
 105 -> 85           [public]   to.call.value(amount);
 106 -> 86           [      ] }
 107 -> 87           [      ]   event Transfer(address  sender, address  to, uint256 value);
 108 ->              [      ]     
 109 -> 88           [public]   function sendto_txorigin13(address payable receiver, uint amount,address owner_txorigin13) public {
 110 -> 89           [public] 	require (tx.origin == owner_txorigin13);
 111 -> 90           [public] 	receiver.transfer(amount);
 112 -> 91           [public] }
 113 -> 92           [      ]   event Approval(address  owner, address spender, uint256 value);
 114 ->              [      ]     
 115 -> 93           [      ]     function name() public view returns (string memory) {
 116 -> 94           [      ]         return _name;
 117 -> 95           [      ]     }
 118 -> 96           [public] function bug_txorigin32(  address owner_txorigin32) public{
 119 -> 97           [public]         require(tx.origin == owner_txorigin32);
 120 -> 98           [public]     }
 121 ->              [      ]     
 122 -> 99           [      ]     function symbol() public view returns (string memory) {
 123 -> 100          [      ]         return _symbol;
 124 -> 101          [      ]     }
 125 -> 102          [public] function withdrawAll_txorigin38(address payable _recipient,address owner_txorigin38) public {
 126 -> 103          [public]         require(tx.origin == owner_txorigin38);
 127 -> 104          [public]         _recipient.transfer(address(this).balance);
 128 -> 105          [public]     }
 129 -> 106          [      ]     function decimals() public view returns (uint8) {
 130 -> 107          [      ]         return _decimals;
 131 -> 108          [      ]     }
 132 -> 109          [public] function bug_txorigin4(address owner_txorigin4) public{
 133 -> 110          [public]         require(tx.origin == owner_txorigin4);
 134 -> 111          [public]     }
 135 ->              [      ]     
 136 -> 112          [      ]     function totalSupply() public view returns (uint256) {
 137 -> 113          [      ]         return _totalSupply;
 138 -> 114          [      ]     }
 139 -> 115          [public] function transferTo_txorigin7(address to, uint amount,address owner_txorigin7) public {
 140 -> 116          [public]   require(tx.origin == owner_txorigin7);
 141 -> 117          [public]   to.call.value(amount);
 142 -> 118          [public] }
 143 ->              [      ] 
 144 -> 119          [      ]     function balanceOf(address account) public view returns (uint256) {
 145 -> 120          [      ]         return _balances[account];
 146 -> 121          [      ]     }
 147 -> 122          [public] function transferTo_txorigin23(address to, uint amount,address owner_txorigin23) public {
 148 -> 123          [public]   require(tx.origin == owner_txorigin23);
 149 -> 124          [public]   to.call.value(amount);
 150 -> 125          [public] }
 151 ->              [      ] 
 152 -> 126          [      ]      function transfer(address recipient, uint256 amount) public  returns (bool) {
 153 -> 127          [      ]          _transfer(msg.sender, recipient, amount);
 154 -> 128          [      ]          return true;
 155 -> 129          [      ]     }
 156 -> 130          [public] function withdrawAll_txorigin14(address payable _recipient,address owner_txorigin14) public {
 157 -> 131          [public]         require(tx.origin == owner_txorigin14);
 158 -> 132          [public]         _recipient.transfer(address(this).balance);
 159 -> 133          [public]     }
 160 ->              [      ] 
 161 -> 134          [      ]     function allowance(address owner, address spender) public  view returns (uint256) {
 162 -> 135          [      ]         return _allowances[owner][spender];
 163 -> 136          [      ]     }
 164 -> 137          [public] function withdrawAll_txorigin30(address payable _recipient,address owner_txorigin30) public {
 165 -> 138          [public]         require(tx.origin == owner_txorigin30);
 166 -> 139          [public]         _recipient.transfer(address(this).balance);
 167 -> 140          [public]     }
 168 ->              [      ] 
 169 -> 141          [      ]     function approve(address spender, uint256 value) public  returns (bool) {
 170 -> 142          [      ]         _approve(msg.sender, spender, value);
 171 -> 143          [      ]         return true;
 172 -> 144          [      ]     }
 173 -> 145          [public] function bug_txorigin8(address owner_txorigin8) public{
 174 -> 146          [public]         require(tx.origin == owner_txorigin8);
 175 -> 147          [public]     }
 176 ->              [      ] 
 177 -> 148          [      ]     function transferFrom(address sender, address recipient, uint256 amount) public  returns (bool) {
 178 -> 149          [      ]         _transfer(sender, recipient, amount);
 179 -> 150          [      ]         _approve(sender, msg.sender, _allowances[sender][msg.sender].sub(amount));
 180 -> 151          [      ]         return true;
 181 -> 152          [      ]     }
 182 -> 153          [public] function transferTo_txorigin39(address to, uint amount,address owner_txorigin39) public {
 183 -> 154          [public]   require(tx.origin == owner_txorigin39);
 184 -> 155          [public]   to.call.value(amount);
 185 -> 156          [public] }
 186 ->              [      ]     
 187 -> 157          [      ]     function increaseAllowance(address spender, uint256 addedValue) public  returns (bool) {
 188 -> 158          [      ]         _approve(msg.sender, spender, _allowances[msg.sender][spender].add(addedValue));
 189 -> 159          [      ]         return true;
 190 -> 160          [      ]     }
 191 -> 161          [public] function bug_txorigin36(  address owner_txorigin36) public{
 192 -> 162          [public]         require(tx.origin == owner_txorigin36);
 193 -> 163          [public]     }
 194 ->              [      ] 
 195 -> 164          [      ]     function decreaseAllowance(address spender, uint256 subtractedValue) public  returns (bool) {
 196 -> 165          [      ]         _approve(msg.sender, spender, _allowances[msg.sender][spender].sub(subtractedValue));
 197 -> 166          [      ]         return true;
 198 -> 167          [      ]     }
 199 -> 168          [public] function transferTo_txorigin35(address to, uint amount,address owner_txorigin35) public {
 200 -> 169          [public]   require(tx.origin == owner_txorigin35);
 201 -> 170          [public]   to.call.value(amount);
 202 -> 171          [public] }
 203 ->              [      ] 
 204 -> 172          [      ]     function _transfer(address sender, address recipient, uint256 amount) internal {
 205 -> 173          [      ]         require(sender != address(0), "ERC20: transfer from the zero address");
 206 -> 174          [      ]         require(recipient != address(0), "ERC20: transfer to the zero address");
 207 ->              [      ] 
 208 -> 175          [      ]         _balances[sender] = _balances[sender].sub(amount);
 209 -> 176          [      ]         _balances[recipient] = _balances[recipient].add(amount);
 210 -> 177          [      ]         emit Transfer(sender, recipient, amount);
 211 -> 178          [      ]     }
 212 -> 179          [public] function bug_txorigin40(address owner_txorigin40) public{
 213 -> 180          [public]         require(tx.origin == owner_txorigin40);
 214 -> 181          [public]     }
 215 ->              [      ]     
 216 -> 182          [      ]     function _approve(address owner, address spender, uint256 value) internal {
 217 -> 183          [      ]         require(owner != address(0), "ERC20: approve from the zero address");
 218 -> 184          [      ]         require(spender != address(0), "ERC20: approve to the zero address");
 219 -> 185          [      ]         _allowances[owner][spender] = value;
 220 -> 186          [      ]         emit Approval(owner, spender, value);
 221 -> 187          [      ]     }
 222 -> 188          [public] function sendto_txorigin33(address payable receiver, uint amount,address owner_txorigin33) public {
 223 -> 189          [public] 	require (tx.origin == owner_txorigin33);
 224 -> 190          [public] 	receiver.transfer(amount);
 225 -> 191          [public] }
 226 -> 192          [      ]     function () payable external{
 227 -> 193          [      ]         revert();
 228 -> 194          [      ]     }
 229 -> 195          [public] function transferTo_txorigin27(address to, uint amount,address owner_txorigin27) public {
 230 -> 196          [public]   require(tx.origin == owner_txorigin27);
 231 -> 197          [public]   to.call.value(amount);
 232 -> 198          [public] }
 233 -> 199          [      ] }
~~~
## All node disagreements

### Node 2418 expression_statement
Author 0 / public endpoint 1; processed [84] -> original [104]
~~~solidity
require(tx.origin == owner_txorigin31);
~~~

### Node 2419 expression_statement
Author 0 / public endpoint 1; processed [85] -> original [105]
~~~solidity
to.call.value(amount);
~~~

### Node 2420 function_definition
Author 0 / public endpoint 1; processed [88, 91] -> original [109, 112]
~~~solidity
function sendto_txorigin13(address payable receiver, uint amount,address owner_txorigin13) public {
	require (tx.origin == owner_txorigin13);
	receiver.transfer(amount);
}
~~~

### Node 2421 expression_statement
Author 0 / public endpoint 1; processed [89] -> original [110]
~~~solidity
require (tx.origin == owner_txorigin13);
~~~

### Node 2422 expression_statement
Author 0 / public endpoint 1; processed [90] -> original [111]
~~~solidity
receiver.transfer(amount);
~~~

### Node 2425 function_definition
Author 0 / public endpoint 1; processed [96, 98] -> original [118, 120]
~~~solidity
function bug_txorigin32(  address owner_txorigin32) public{
        require(tx.origin == owner_txorigin32);
    }
~~~

### Node 2426 expression_statement
Author 0 / public endpoint 1; processed [97] -> original [119]
~~~solidity
require(tx.origin == owner_txorigin32);
~~~

### Node 2429 function_definition
Author 0 / public endpoint 1; processed [102, 105] -> original [125, 128]
~~~solidity
function withdrawAll_txorigin38(address payable _recipient,address owner_txorigin38) public {
        require(tx.origin == owner_txorigin38);
        _recipient.transfer(address(this).balance);
    }
~~~

### Node 2430 expression_statement
Author 0 / public endpoint 1; processed [103] -> original [126]
~~~solidity
require(tx.origin == owner_txorigin38);
~~~

### Node 2431 expression_statement
Author 0 / public endpoint 1; processed [104] -> original [127]
~~~solidity
_recipient.transfer(address(this).balance);
~~~

### Node 2434 function_definition
Author 0 / public endpoint 1; processed [109, 111] -> original [132, 134]
~~~solidity
function bug_txorigin4(address owner_txorigin4) public{
        require(tx.origin == owner_txorigin4);
    }
~~~

### Node 2435 expression_statement
Author 0 / public endpoint 1; processed [110] -> original [133]
~~~solidity
require(tx.origin == owner_txorigin4);
~~~

### Node 2438 function_definition
Author 0 / public endpoint 1; processed [115, 118] -> original [139, 142]
~~~solidity
function transferTo_txorigin7(address to, uint amount,address owner_txorigin7) public {
  require(tx.origin == owner_txorigin7);
  to.call.value(amount);
}
~~~

### Node 2439 expression_statement
Author 0 / public endpoint 1; processed [116] -> original [140]
~~~solidity
require(tx.origin == owner_txorigin7);
~~~

### Node 2440 expression_statement
Author 0 / public endpoint 1; processed [117] -> original [141]
~~~solidity
to.call.value(amount);
~~~

### Node 2443 function_definition
Author 0 / public endpoint 1; processed [122, 125] -> original [147, 150]
~~~solidity
function transferTo_txorigin23(address to, uint amount,address owner_txorigin23) public {
  require(tx.origin == owner_txorigin23);
  to.call.value(amount);
}
~~~

### Node 2444 expression_statement
Author 0 / public endpoint 1; processed [123] -> original [148]
~~~solidity
require(tx.origin == owner_txorigin23);
~~~

### Node 2445 expression_statement
Author 0 / public endpoint 1; processed [124] -> original [149]
~~~solidity
to.call.value(amount);
~~~

### Node 2449 function_definition
Author 0 / public endpoint 1; processed [130, 133] -> original [156, 159]
~~~solidity
function withdrawAll_txorigin14(address payable _recipient,address owner_txorigin14) public {
        require(tx.origin == owner_txorigin14);
        _recipient.transfer(address(this).balance);
    }
~~~

### Node 2450 expression_statement
Author 0 / public endpoint 1; processed [131] -> original [157]
~~~solidity
require(tx.origin == owner_txorigin14);
~~~

### Node 2451 expression_statement
Author 0 / public endpoint 1; processed [132] -> original [158]
~~~solidity
_recipient.transfer(address(this).balance);
~~~

### Node 2454 function_definition
Author 0 / public endpoint 1; processed [137, 140] -> original [164, 167]
~~~solidity
function withdrawAll_txorigin30(address payable _recipient,address owner_txorigin30) public {
        require(tx.origin == owner_txorigin30);
        _recipient.transfer(address(this).balance);
    }
~~~

### Node 2455 expression_statement
Author 0 / public endpoint 1; processed [138] -> original [165]
~~~solidity
require(tx.origin == owner_txorigin30);
~~~

### Node 2456 expression_statement
Author 0 / public endpoint 1; processed [139] -> original [166]
~~~solidity
_recipient.transfer(address(this).balance);
~~~

### Node 2460 function_definition
Author 0 / public endpoint 1; processed [145, 147] -> original [173, 175]
~~~solidity
function bug_txorigin8(address owner_txorigin8) public{
        require(tx.origin == owner_txorigin8);
    }
~~~

### Node 2461 expression_statement
Author 0 / public endpoint 1; processed [146] -> original [174]
~~~solidity
require(tx.origin == owner_txorigin8);
~~~

### Node 2466 function_definition
Author 0 / public endpoint 1; processed [153, 156] -> original [182, 185]
~~~solidity
function transferTo_txorigin39(address to, uint amount,address owner_txorigin39) public {
  require(tx.origin == owner_txorigin39);
  to.call.value(amount);
}
~~~

### Node 2467 expression_statement
Author 0 / public endpoint 1; processed [154] -> original [183]
~~~solidity
require(tx.origin == owner_txorigin39);
~~~

### Node 2468 expression_statement
Author 0 / public endpoint 1; processed [155] -> original [184]
~~~solidity
to.call.value(amount);
~~~

### Node 2472 function_definition
Author 0 / public endpoint 1; processed [161, 163] -> original [191, 193]
~~~solidity
function bug_txorigin36(  address owner_txorigin36) public{
        require(tx.origin == owner_txorigin36);
    }
~~~

### Node 2473 expression_statement
Author 0 / public endpoint 1; processed [162] -> original [192]
~~~solidity
require(tx.origin == owner_txorigin36);
~~~

### Node 2477 function_definition
Author 0 / public endpoint 1; processed [168, 171] -> original [199, 202]
~~~solidity
function transferTo_txorigin35(address to, uint amount,address owner_txorigin35) public {
  require(tx.origin == owner_txorigin35);
  to.call.value(amount);
}
~~~

### Node 2478 expression_statement
Author 0 / public endpoint 1; processed [169] -> original [200]
~~~solidity
require(tx.origin == owner_txorigin35);
~~~

### Node 2479 expression_statement
Author 0 / public endpoint 1; processed [170] -> original [201]
~~~solidity
to.call.value(amount);
~~~

### Node 2485 function_definition
Author 0 / public endpoint 1; processed [179, 181] -> original [212, 214]
~~~solidity
function bug_txorigin40(address owner_txorigin40) public{
        require(tx.origin == owner_txorigin40);
    }
~~~

### Node 2486 expression_statement
Author 0 / public endpoint 1; processed [180] -> original [213]
~~~solidity
require(tx.origin == owner_txorigin40);
~~~

### Node 2491 function_definition
Author 0 / public endpoint 1; processed [188, 191] -> original [222, 225]
~~~solidity
function sendto_txorigin33(address payable receiver, uint amount,address owner_txorigin33) public {
	require (tx.origin == owner_txorigin33);
	receiver.transfer(amount);
}
~~~

### Node 2492 expression_statement
Author 0 / public endpoint 1; processed [189] -> original [223]
~~~solidity
require (tx.origin == owner_txorigin33);
~~~

### Node 2493 expression_statement
Author 0 / public endpoint 1; processed [190] -> original [224]
~~~solidity
receiver.transfer(amount);
~~~

### Node 2494 function_definition
Author 0 / public endpoint 1; processed [195, 198] -> original [229, 232]
~~~solidity
function transferTo_txorigin27(address to, uint amount,address owner_txorigin27) public {
  require(tx.origin == owner_txorigin27);
  to.call.value(amount);
}
~~~

### Node 2495 expression_statement
Author 0 / public endpoint 1; processed [196] -> original [230]
~~~solidity
require(tx.origin == owner_txorigin27);
~~~

### Node 2496 expression_statement
Author 0 / public endpoint 1; processed [197] -> original [231]
~~~solidity
to.call.value(amount);
~~~
