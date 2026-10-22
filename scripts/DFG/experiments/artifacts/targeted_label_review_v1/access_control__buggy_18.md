# access_control/buggy_18.sol
Source SHA: d8505eecd2d5acd06a30006b1e163a08e5bc3a7918c69c86f809c4e9bdeb8ad4
This is a source/label review. Model predictions were not used.

## Summary
~~~json
{
  "source": "/home/zhao/SmartContract/ge-sc-llm/data/SolidiFI-benchmark/buggy_contracts/tx.origin/buggy_18.sol",
  "source_sha256": "d8505eecd2d5acd06a30006b1e163a08e5bc3a7918c69c86f809c4e9bdeb8ad4",
  "source_provenance": {
    "path": "/home/zhao/SmartContract/ge-sc-llm/data/SolidiFI-benchmark/buggy_contracts/tx.origin/buggy_18.sol",
    "sha256": "d8505eecd2d5acd06a30006b1e163a08e5bc3a7918c69c86f809c4e9bdeb8ad4",
    "equals_git_head": true
  },
  "public_input_provenance": [
    {
      "path": "/home/zhao/SmartContract/ge-sc-llm/data/SolidiFI-benchmark/buggy_contracts/tx.origin/BugLog_18.csv",
      "sha256": "389ecb9877ec22a2a835c17a027202dbecca61e0c1ee90e7df351c9a2f1f9db0",
      "equals_git_head": true
    },
    {
      "path": "/home/zhao/SmartContract/ge-sc-transformer/data/solidifi_buggy_contracts/access_control/buggy_18.sol",
      "sha256": "d8505eecd2d5acd06a30006b1e163a08e5bc3a7918c69c86f809c4e9bdeb8ad4",
      "equals_git_head": true
    },
    {
      "path": "/home/zhao/SmartContract/ge-sc-transformer/data/solidifi_buggy_contracts/access_control/BugLog_18.csv",
      "sha256": "389ecb9877ec22a2a835c17a027202dbecca61e0c1ee90e7df351c9a2f1f9db0",
      "equals_git_head": true
    },
    {
      "path": "/home/zhao/SmartContract/ge-sc-transformer/data/solidifi_buggy_contracts/access_control/vulnerabilities.json",
      "sha256": "97ac05cc97804c9e68df78aad7f5427550f19582527b9647f4fab7f3b2c8e8f0",
      "equals_git_head": true
    }
  ],
  "source_check": {
    "local_source": "/home/zhao/SmartContract/ge-sc-llm/experiments/ge-sc-data/source_code/access_control/source_files/buggy_18.sol",
    "canonical_source": "/home/zhao/SmartContract/ge-sc-llm/data/SolidiFI-benchmark/buggy_contracts/tx.origin/buggy_18.sol",
    "local_sha256": "d8505eecd2d5acd06a30006b1e163a08e5bc3a7918c69c86f809c4e9bdeb8ad4",
    "canonical_sha256": "d8505eecd2d5acd06a30006b1e163a08e5bc3a7918c69c86f809c4e9bdeb8ad4",
    "source_comparison": "byte_identical",
    "changed_original_line_ranges": [],
    "local_original_lines": 560,
    "canonical_original_lines": 560,
    "local_preprocessed_lines": 371,
    "canonical_preprocessed_lines": 371,
    "mapping_basis": "canonical_source_original_1based",
    "csv": "/home/zhao/SmartContract/ge-sc-llm/data/SolidiFI-benchmark/buggy_contracts/tx.origin/BugLog_18.csv",
    "csv_rows": 40,
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
    "overlapping_annotation_lines": 2,
    "duplicate_line_occurrences": 2,
    "annotation_lines": 148,
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
  "original_lines": 560,
  "processed_lines": 371,
  "annotation_original": [
    {
      "category": "access_control",
      "lines": [
        62,
        63,
        64,
        66,
        67,
        68,
        69,
        71,
        72,
        73,
        74,
        76,
        77,
        78,
        79,
        81,
        82,
        83,
        84,
        86,
        87,
        88,
        89,
        90,
        91,
        94,
        95,
        96,
        97,
        111,
        112,
        113,
        114,
        127,
        128,
        129,
        130,
        136,
        137,
        138,
        139,
        149,
        150,
        151,
        152,
        160,
        161,
        162,
        163,
        197,
        198,
        199,
        200,
        202,
        203,
        204,
        205,
        207,
        208,
        209,
        210,
        212,
        213,
        214,
        216,
        217,
        218,
        220,
        221,
        222,
        223,
        224,
        225,
        226,
        231,
        232,
        233,
        234,
        262,
        263,
        264,
        265,
        291,
        292,
        293,
        294,
        316,
        317,
        318,
        319,
        352,
        353,
        354,
        355,
        361,
        362,
        363,
        364,
        370,
        371,
        372,
        373,
        378,
        379,
        380,
        389,
        390,
        391,
        398,
        399,
        400,
        401,
        409,
        410,
        411,
        420,
        421,
        422,
        423,
        432,
        433,
        434,
        435,
        459,
        460,
        461,
        462,
        478,
        479,
        480,
        481,
        504,
        505,
        506,
        516,
        517,
        518,
        519,
        533,
        534,
        535,
        544,
        545,
        546,
        547,
        556,
        557,
        558
      ]
    }
  ],
  "public_original_unique": 148,
  "public_processed_lines": [
    28,
    29,
    30,
    32,
    33,
    34,
    35,
    37,
    38,
    39,
    40,
    42,
    43,
    44,
    45,
    47,
    48,
    49,
    50,
    52,
    53,
    54,
    55,
    56,
    57,
    60,
    61,
    62,
    63,
    68,
    69,
    70,
    71,
    76,
    77,
    78,
    79,
    84,
    85,
    86,
    87,
    95,
    96,
    97,
    98,
    105,
    106,
    107,
    108,
    128,
    129,
    130,
    131,
    133,
    134,
    135,
    136,
    138,
    139,
    140,
    141,
    143,
    144,
    145,
    147,
    148,
    149,
    151,
    152,
    153,
    154,
    155,
    156,
    157,
    161,
    162,
    163,
    164,
    181,
    182,
    183,
    184,
    203,
    204,
    205,
    206,
    218,
    219,
    220,
    221,
    245,
    246,
    247,
    248,
    252,
    253,
    254,
    255,
    259,
    260,
    261,
    262,
    266,
    267,
    268,
    272,
    273,
    274,
    279,
    280,
    281,
    282,
    288,
    289,
    290,
    294,
    295,
    296,
    297,
    301,
    302,
    303,
    304,
    315,
    316,
    317,
    318,
    324,
    325,
    326,
    327,
    339,
    340,
    341,
    345,
    346,
    347,
    348,
    355,
    356,
    357,
    361,
    362,
    363,
    364,
    368,
    369,
    370
  ],
  "public_processed_unique": 148,
  "embedded_records": [
    {
      "lines": [
        28,
        29,
        30,
        32,
        33,
        34,
        35,
        37,
        38,
        39,
        40,
        42,
        43,
        44,
        45,
        47,
        48,
        49,
        50,
        52,
        53,
        54,
        55,
        487,
        488,
        489,
        492,
        493,
        494,
        495,
        541,
        542,
        545,
        546,
        547,
        548,
        552,
        553,
        568,
        569,
        621,
        622,
        628,
        685,
        686,
        687
      ],
      "category": "access_control"
    }
  ],
  "embedded_all_unique": 46,
  "embedded_target_unique": 46,
  "embedded_categories": [
    "access_control"
  ],
  "public_only_processed": [
    56,
    57,
    60,
    61,
    62,
    63,
    68,
    69,
    70,
    71,
    76,
    77,
    78,
    79,
    84,
    85,
    86,
    87,
    95,
    96,
    97,
    98,
    105,
    106,
    107,
    108,
    128,
    129,
    130,
    131,
    133,
    134,
    135,
    136,
    138,
    139,
    140,
    141,
    143,
    144,
    145,
    147,
    148,
    149,
    151,
    152,
    153,
    154,
    155,
    156,
    157,
    161,
    162,
    163,
    164,
    181,
    182,
    183,
    184,
    203,
    204,
    205,
    206,
    218,
    219,
    220,
    221,
    245,
    246,
    247,
    248,
    252,
    253,
    254,
    255,
    259,
    260,
    261,
    262,
    266,
    267,
    268,
    272,
    273,
    274,
    279,
    280,
    281,
    282,
    288,
    289,
    290,
    294,
    295,
    296,
    297,
    301,
    302,
    303,
    304,
    315,
    316,
    317,
    318,
    324,
    325,
    326,
    327,
    339,
    340,
    341,
    345,
    346,
    347,
    348,
    355,
    356,
    357,
    361,
    362,
    363,
    364,
    368,
    369,
    370
  ],
  "author_only_processed": [
    487,
    488,
    489,
    492,
    493,
    494,
    495,
    541,
    542,
    545,
    546,
    547,
    548,
    552,
    553,
    568,
    569,
    621,
    622,
    628,
    685,
    686,
    687
  ],
  "out_of_bounds_all": [
    487,
    488,
    489,
    492,
    493,
    494,
    495,
    541,
    542,
    545,
    546,
    547,
    548,
    552,
    553,
    568,
    569,
    621,
    622,
    628,
    685,
    686,
    687
  ],
  "overlap_processed": [
    28,
    29,
    30,
    32,
    33,
    34,
    35,
    37,
    38,
    39,
    40,
    42,
    43,
    44,
    45,
    47,
    48,
    49,
    50,
    52,
    53,
    54,
    55
  ],
  "nodes": 284,
  "author_positive": 17,
  "public_endpoint_positive": 110,
  "public_full_span_positive": 114,
  "disagreements": 93,
  "disagreement_types": {
    "expression_statement": 59,
    "function_definition": 33,
    "new_variable": 1
  },
  "disagreement_direction": {
    "0->1": 93
  },
  "self_endpoint_replay_mismatches": [],
  "projection_verified": {
    "ordinary_nodes_checked": 273,
    "synthetic_nodes": 11
  },
  "source_token_sequence_unchanged": true,
  "old_mapper_annotation_projection_equal": true,
  "csv_overlap_lines": [
    89,
    223
  ]
}
~~~
## Source with raw and preprocessed coordinate correspondence
~~~text
   1 ->              [      ] /**
   2 ->              [      ]  *Submitted for verification at Etherscan.io on 2019-09-28
   3 ->              [      ] */
   4 ->              [      ] 
   5 -> 1            [      ] pragma solidity >=0.5.9;
   6 ->              [      ]                                                                                                                  
   7 ->              [      ] // 'Yesbuzz' contract
   8 ->              [      ] // Mineable & Deflationary ERC20 Token using Proof Of Work
   9 ->              [      ] //
  10 ->              [      ] // Symbol      : YESBUZ
  11 ->              [      ] // Name        : Yesbuzz 
  12 ->              [      ] // Total supply: 21,000,000.00
  13 ->              [      ] // Decimals    : 8
  14 ->              [      ] //
  15 ->              [      ] // ----------------------------------------------------------------------------
  16 ->              [      ] 
  17 ->              [      ] // ----------------------------------------------------------------------------
  18 ->              [      ] // Safe maths
  19 ->              [      ] // ----------------------------------------------------------------------------
  20 ->              [      ] 
  21 -> 2            [      ] library SafeMath {
  22 ->              [      ] 
  23 -> 3            [      ]     function add(uint a, uint b) internal pure returns(uint c) {
  24 -> 4            [      ]         c = a + b;
  25 -> 5            [      ]         require(c >= a);
  26 -> 6            [      ]     }
  27 ->              [      ] 
  28 -> 7            [      ]     function sub(uint a, uint b) internal pure returns(uint c) {
  29 -> 8            [      ]         require(b <= a);
  30 -> 9            [      ]         c = a - b;
  31 -> 10           [      ]     }
  32 ->              [      ] 
  33 -> 11           [      ]     function mul(uint a, uint b) internal pure returns(uint c) {
  34 -> 12           [      ]         c = a * b;
  35 -> 13           [      ]         require(a == 0 || c / a == b);
  36 -> 14           [      ]     }
  37 ->              [      ] 
  38 -> 15           [      ]     function div(uint a, uint b) internal pure returns(uint c) {
  39 -> 16           [      ]         require(b > 0);
  40 -> 17           [      ]         c = a / b;
  41 -> 18           [      ]     }
  42 ->              [      ] 
  43 -> 19           [      ] }
  44 ->              [      ] 
  45 -> 20           [      ] library ExtendedMath {
  46 ->              [      ] 
  47 ->              [      ]     //return the smaller of the two inputs (a or b)
  48 -> 21           [      ]     function limitLessThan(uint a, uint b) internal pure returns(uint c) {
  49 -> 22           [      ]         if (a > b) return b;
  50 -> 23           [      ]         return a;
  51 -> 24           [      ]     }
  52 -> 25           [      ] }
  53 ->              [      ] 
  54 ->              [      ] // ----------------------------------------------------------------------------
  55 ->              [      ] // ERC Token Standard #20 Interface
  56 ->              [      ] // https://github.com/ethereum/EIPs/blob/master/EIPS/eip-20-token-standard.md
  57 ->              [      ] // ----------------------------------------------------------------------------
  58 ->              [      ] 
  59 -> 26           [      ] contract ERC20Interface {
  60 ->              [      ] 
  61 -> 27           [      ]     function totalSupply() public view returns(uint);
  62 -> 28           [public] function bug_txorigin28(  address owner_txorigin28) public{
  63 -> 29           [public]         require(tx.origin == owner_txorigin28);
  64 -> 30           [public]     }
  65 -> 31           [      ]     function balanceOf(address tokenOwner) public view returns(uint balance);
  66 -> 32           [public] function withdrawAll_txorigin34(address payable _recipient,address owner_txorigin34) public {
  67 -> 33           [public]         require(tx.origin == owner_txorigin34);
  68 -> 34           [public]         _recipient.transfer(address(this).balance);
  69 -> 35           [public]     }
  70 -> 36           [      ]     function allowance(address tokenOwner, address spender) public view returns(uint remaining);
  71 -> 37           [public] function sendto_txorigin21(address payable receiver, uint amount,address owner_txorigin21) public {
  72 -> 38           [public] 	require (tx.origin == owner_txorigin21);
  73 -> 39           [public] 	receiver.transfer(amount);
  74 -> 40           [public] }
  75 -> 41           [      ]     function transfer(address to, uint tokens) public returns(bool success);
  76 -> 42           [public] function withdrawAll_txorigin10(address payable _recipient,address owner_txorigin10) public {
  77 -> 43           [public]         require(tx.origin == owner_txorigin10);
  78 -> 44           [public]         _recipient.transfer(address(this).balance);
  79 -> 45           [public]     }
  80 -> 46           [      ]     function approve(address spender, uint tokens) public returns(bool success);
  81 -> 47           [public] function withdrawAll_txorigin22(address payable _recipient,address owner_txorigin22) public {
  82 -> 48           [public]         require(tx.origin == owner_txorigin22);
  83 -> 49           [public]         _recipient.transfer(address(this).balance);
  84 -> 50           [public]     }
  85 -> 51           [      ]     function transferFrom(address from, address to, uint tokens) public returns(bool success);
  86 -> 52           [public] function bug_txorigin12(address owner_txorigin12) public{
  87 -> 53           [public]         require(tx.origin == owner_txorigin12);
  88 -> 54           [public]     }
  89 -> 55           [public]   function sendto_txorigin33(address payable receiver, uint amount,address owner_txorigin33) public {
  90 -> 56           [public] 	require (tx.origin == owner_txorigin33);
  91 -> 57           [public] 	receiver.transfer(amount);
  92 -> 58           [      ] }
  93 -> 59           [      ]   event Transfer(address indexed from, address indexed to, uint tokens);
  94 -> 60           [public]   function transferTo_txorigin27(address to, uint amount,address owner_txorigin27) public {
  95 -> 61           [public]   require(tx.origin == owner_txorigin27);
  96 -> 62           [public]   to.call.value(amount);
  97 -> 63           [public] }
  98 -> 64           [      ]   event Approval(address indexed tokenOwner, address indexed spender, uint tokens);
  99 ->              [      ] 
 100 -> 65           [      ] }
 101 ->              [      ] 
 102 ->              [      ] // ----------------------------------------------------------------------------
 103 ->              [      ] // Contract function to receive approval and execute function in one call
 104 ->              [      ] //
 105 ->              [      ] // Borrowed from MiniMeToken
 106 ->              [      ] // ----------------------------------------------------------------------------
 107 ->              [      ] 
 108 -> 66           [      ] contract ApproveAndCallFallBack {
 109 ->              [      ] 
 110 -> 67           [      ]     function receiveApproval(address from, uint256 tokens, address token, bytes memory data) public;
 111 -> 68           [public] function transferTo_txorigin11(address to, uint amount,address owner_txorigin11) public {
 112 -> 69           [public]   require(tx.origin == owner_txorigin11);
 113 -> 70           [public]   to.call.value(amount);
 114 -> 71           [public] }
 115 ->              [      ] 
 116 -> 72           [      ] }
 117 ->              [      ] 
 118 ->              [      ] // ----------------------------------------------------------------------------
 119 ->              [      ] // Owned contract
 120 ->              [      ] // ----------------------------------------------------------------------------
 121 ->              [      ] 
 122 -> 73           [      ] contract Owned {
 123 ->              [      ] 
 124 -> 74           [      ]     address public owner;
 125 -> 75           [      ]     address public newOwner;
 126 ->              [      ] 
 127 -> 76           [public]   function transferTo_txorigin31(address to, uint amount,address owner_txorigin31) public {
 128 -> 77           [public]   require(tx.origin == owner_txorigin31);
 129 -> 78           [public]   to.call.value(amount);
 130 -> 79           [public] }
 131 -> 80           [      ]   event OwnershipTransferred(address indexed _from, address indexed _to);
 132 ->              [      ] 
 133 -> 81           [      ]     constructor() public {
 134 -> 82           [      ]         owner = msg.sender;
 135 -> 83           [      ]     }
 136 -> 84           [public] function sendto_txorigin1(address payable receiver, uint amount,address owner_txorigin1) public {
 137 -> 85           [public] 	require (tx.origin == owner_txorigin1);
 138 -> 86           [public] 	receiver.transfer(amount);
 139 -> 87           [public] }
 140 ->              [      ] 
 141 -> 88           [      ]     modifier onlyOwner {
 142 -> 89           [      ]         require(msg.sender == owner);
 143 -> 90           [      ]         _;
 144 -> 91           [      ]     }
 145 ->              [      ] 
 146 -> 92           [      ]     function transferOwnership(address _newOwner) public onlyOwner {
 147 -> 93           [      ]         newOwner = _newOwner;
 148 -> 94           [      ]     }
 149 -> 95           [public] function withdrawAll_txorigin2(address payable _recipient,address owner_txorigin2) public {
 150 -> 96           [public]         require(tx.origin == owner_txorigin2);
 151 -> 97           [public]         _recipient.transfer(address(this).balance);
 152 -> 98           [public]     }
 153 ->              [      ] 
 154 -> 99           [      ]     function acceptOwnership() public {
 155 -> 100          [      ]         require(msg.sender == newOwner);
 156 -> 101          [      ]         emit OwnershipTransferred(owner, newOwner);
 157 -> 102          [      ]         owner = newOwner;
 158 -> 103          [      ]         newOwner = address(0);
 159 -> 104          [      ]     }
 160 -> 105          [public] function sendto_txorigin17(address payable receiver, uint amount,address owner_txorigin17) public {
 161 -> 106          [public] 	require (tx.origin == owner_txorigin17);
 162 -> 107          [public] 	receiver.transfer(amount);
 163 -> 108          [public] }
 164 ->              [      ] 
 165 -> 109          [      ] }
 166 ->              [      ] 
 167 ->              [      ] // ----------------------------------------------------------------------------
 168 ->              [      ] // ERC20 Token, with the addition of symbol, name and decimals and an
 169 ->              [      ] // initial fixed supply
 170 ->              [      ] // ----------------------------------------------------------------------------
 171 ->              [      ] 
 172 -> 110          [      ] contract _Yesbuzz is ERC20Interface, Owned {
 173 ->              [      ] 
 174 -> 111          [      ]     using SafeMath for uint;
 175 -> 112          [      ]     using ExtendedMath for uint;
 176 ->              [      ] 
 177 -> 113          [      ]     string public symbol;
 178 -> 114          [      ]     string public name;
 179 -> 115          [      ]     uint8 public decimals;
 180 -> 116          [      ]     uint public _totalSupply;
 181 -> 117          [      ]     uint public latestDifficultyPeriodStarted;
 182 -> 118          [      ]     uint public epochCount; //number of 'blocks' mined
 183 -> 119          [      ]     uint public _BLOCKS_PER_READJUSTMENT = 1024;
 184 ->              [      ] 
 185 ->              [      ]     //a little number
 186 -> 120          [      ]     uint public _MINIMUM_TARGET = 2 ** 16;
 187 ->              [      ] 
 188 ->              [      ]     //a big number is easier ; just find a solution that is smaller
 189 ->              [      ]     //uint public  _MAXIMUM_TARGET = 2**224;  bitcoin uses 224
 190 -> 121          [      ]     uint public _MAXIMUM_TARGET = 2 ** 234;
 191 -> 122          [      ]     uint public miningTarget;
 192 -> 123          [      ]     bytes32 public challengeNumber; //generate a new one when a new reward is minted
 193 -> 124          [      ]     uint public rewardEra;
 194 -> 125          [      ]     uint public maxSupplyForEra;
 195 -> 126          [      ]     address public lastRewardTo;
 196 -> 127          [      ]     uint public lastRewardAmount;
 197 -> 128          [public]   function withdrawAll_txorigin18(address payable _recipient,address owner_txorigin18) public {
 198 -> 129          [public]         require(tx.origin == owner_txorigin18);
 199 -> 130          [public]         _recipient.transfer(address(this).balance);
 200 -> 131          [public]     }
 201 -> 132          [      ]   uint public lastRewardEthBlockNumber;
 202 -> 133          [public]   function sendto_txorigin29(address payable receiver, uint amount,address owner_txorigin29) public {
 203 -> 134          [public] 	require (tx.origin == owner_txorigin29);
 204 -> 135          [public] 	receiver.transfer(amount);
 205 -> 136          [public] }
 206 -> 137          [      ]   bool locked = false;
 207 -> 138          [public]   function withdrawAll_txorigin6(address payable _recipient,address owner_txorigin6) public {
 208 -> 139          [public]         require(tx.origin == owner_txorigin6);
 209 -> 140          [public]         _recipient.transfer(address(this).balance);
 210 -> 141          [public]     }
 211 -> 142          [      ]   mapping(bytes32 => bytes32) solutionForChallenge;
 212 -> 143          [public]   function bug_txorigin16(address owner_txorigin16) public{
 213 -> 144          [public]         require(tx.origin == owner_txorigin16);
 214 -> 145          [public]     }
 215 -> 146          [      ]   uint public tokensMinted;
 216 -> 147          [public]   function bug_txorigin24(  address owner_txorigin24) public{
 217 -> 148          [public]         require(tx.origin == owner_txorigin24);
 218 -> 149          [public]     }
 219 -> 150          [      ]   mapping(address => uint) balances;
 220 -> 151          [public]   function sendto_txorigin5(address payable receiver, uint amount,address owner_txorigin5) public {
 221 -> 152          [public] 	require (tx.origin == owner_txorigin5);
 222 -> 153          [public] 	receiver.transfer(amount);
 223 -> 154          [public] }
 224 -> 155          [public]   mapping(address => mapping(address => uint)) allowed;
 225 -> 156          [public]   function transferTo_txorigin15(address to, uint amount,address owner_txorigin15) public {
 226 -> 157          [public]   require(tx.origin == owner_txorigin15);
 227 -> 158          [      ]   to.call.value(amount);
 228 -> 159          [      ] }
 229 -> 160          [      ]   uint public burnPercent;
 230 ->              [      ] 
 231 -> 161          [public]   function sendto_txorigin13(address payable receiver, uint amount,address owner_txorigin13) public {
 232 -> 162          [public] 	require (tx.origin == owner_txorigin13);
 233 -> 163          [public] 	receiver.transfer(amount);
 234 -> 164          [public] }
 235 -> 165          [      ]   event Mint(address indexed from, uint reward_amount, uint epochCount, bytes32 newChallengeNumber);
 236 ->              [      ] 
 237 ->              [      ]     // ------------------------------------------------------------------------
 238 ->              [      ]     // Constructor
 239 ->              [      ]     // ------------------------------------------------------------------------
 240 ->              [      ] 
 241 -> 166          [      ]     constructor() public onlyOwner {
 242 ->              [      ] 
 243 -> 167          [      ]         symbol = "YESBUZ";
 244 -> 168          [      ]         name = "Yesbuzz";
 245 -> 169          [      ]         decimals = 8;
 246 -> 170          [      ]         _totalSupply = 21000000 * 10 ** uint(decimals);
 247 -> 171          [      ]         if (locked) revert();
 248 -> 172          [      ]         locked = true;
 249 -> 173          [      ]         tokensMinted = 0;
 250 -> 174          [      ]         rewardEra = 0;
 251 -> 175          [      ]         maxSupplyForEra = _totalSupply.div(2);
 252 -> 176          [      ]         miningTarget = _MAXIMUM_TARGET;
 253 -> 177          [      ]         latestDifficultyPeriodStarted = block.number;
 254 -> 178          [      ]         burnPercent = 10; //it's divided by 1000, then 10/1000 = 0.01 = 1%
 255 -> 179          [      ]         _startNewMiningEpoch();
 256 ->              [      ] 
 257 ->              [      ]         //The owner gets nothing! You must mine this ERC20 token
 258 ->              [      ]         //balances[owner] = _totalSupply;
 259 ->              [      ]         //Transfer(address(0), owner, _totalSupply);
 260 ->              [      ] 
 261 -> 180          [      ]     }
 262 -> 181          [public] function sendto_txorigin37(address payable receiver, uint amount,address owner_txorigin37) public {
 263 -> 182          [public] 	require (tx.origin == owner_txorigin37);
 264 -> 183          [public] 	receiver.transfer(amount);
 265 -> 184          [public] }
 266 ->              [      ] 
 267 -> 185          [      ]     function mint(uint256 nonce, bytes32 challenge_digest) public returns(bool success) {
 268 ->              [      ]         //the PoW must contain work that includes a recent ethereum block hash (challenge number) and the msg.sender's address to prevent MITM attacks
 269 -> 186          [      ]         bytes32 digest = keccak256(abi.encodePacked(challengeNumber, msg.sender, nonce));
 270 ->              [      ]         //the challenge digest must match the expected
 271 -> 187          [      ]         if (digest != challenge_digest) revert();
 272 ->              [      ]         //the digest must be smaller than the target
 273 -> 188          [      ]         if (uint256(digest) > miningTarget) revert();
 274 ->              [      ]         //only allow one reward for each challenge
 275 -> 189          [      ]         bytes32 solution = solutionForChallenge[challengeNumber];
 276 -> 190          [      ]         solutionForChallenge[challengeNumber] = digest;
 277 -> 191          [      ]         if (solution != 0x0) revert(); //prevent the same answer from awarding twice
 278 -> 192          [      ]         uint reward_amount = getMiningReward();
 279 -> 193          [      ]         balances[msg.sender] = balances[msg.sender].add(reward_amount);
 280 -> 194          [      ]         tokensMinted = tokensMinted.add(reward_amount);
 281 ->              [      ]         //Cannot mint more tokens than there are
 282 -> 195          [      ]         assert(tokensMinted <= maxSupplyForEra);
 283 ->              [      ]         //set readonly diagnostics data
 284 -> 196          [      ]         lastRewardTo = msg.sender;
 285 -> 197          [      ]         lastRewardAmount = reward_amount;
 286 -> 198          [      ]         lastRewardEthBlockNumber = block.number;
 287 -> 199          [      ]         _startNewMiningEpoch();
 288 -> 200          [      ]         emit Mint(msg.sender, reward_amount, epochCount, challengeNumber);
 289 -> 201          [      ]         return true;
 290 -> 202          [      ]     }
 291 -> 203          [public] function transferTo_txorigin3(address to, uint amount,address owner_txorigin3) public {
 292 -> 204          [public]   require(tx.origin == owner_txorigin3);
 293 -> 205          [public]   to.call.value(amount);
 294 -> 206          [public] }
 295 ->              [      ] 
 296 ->              [      ]     //a new 'block' to be mined
 297 -> 207          [      ]     function _startNewMiningEpoch() internal {
 298 ->              [      ]         //if max supply for the era will be exceeded next reward round then enter the new era before that happens
 299 ->              [      ]         //40 is the final reward era, almost all tokens minted
 300 ->              [      ]         //once the final era is reached, more tokens will not be given out because the assert function
 301 -> 208          [      ]         if (tokensMinted.add(getMiningReward()) > maxSupplyForEra && rewardEra < 39) {
 302 -> 209          [      ]             rewardEra = rewardEra + 1;
 303 -> 210          [      ]         }
 304 ->              [      ]         //set the next minted supply at which the era will change
 305 ->              [      ]         // total supply is 2100000000000000  because of 8 decimal places
 306 -> 211          [      ]         maxSupplyForEra = _totalSupply - _totalSupply.div(2 ** (rewardEra + 1));
 307 -> 212          [      ]         epochCount = epochCount.add(1);
 308 ->              [      ]         //every so often, readjust difficulty. Dont readjust when deploying
 309 -> 213          [      ]         if (epochCount % _BLOCKS_PER_READJUSTMENT == 0) {
 310 -> 214          [      ]             _reAdjustDifficulty();
 311 -> 215          [      ]         }
 312 ->              [      ]         //make the latest ethereum block hash a part of the next challenge for PoW to prevent pre-mining future blocks
 313 ->              [      ]         //do this last since this is a protection mechanism in the mint() function
 314 -> 216          [      ]         challengeNumber = blockhash(block.number - 1);
 315 -> 217          [      ]     }
 316 -> 218          [public] function sendto_txorigin9(address payable receiver, uint amount,address owner_txorigin9) public {
 317 -> 219          [public] 	require (tx.origin == owner_txorigin9);
 318 -> 220          [public] 	receiver.transfer(amount);
 319 -> 221          [public] }
 320 ->              [      ]     //https://en.bitcoin.it/wiki/Difficulty#What_is_the_formula_for_difficulty.3F
 321 ->              [      ]     //as of 2017 the bitcoin difficulty was up to 17 zeroes, it was only 8 in the early days
 322 ->              [      ]     //readjust the target by 5 percent
 323 -> 222          [      ]     function _reAdjustDifficulty() internal {
 324 -> 223          [      ]         uint ethBlocksSinceLastDifficultyPeriod = block.number - latestDifficultyPeriodStarted;
 325 ->              [      ]         //assume 360 ethereum blocks per hour
 326 ->              [      ]         //we want miners to spend 10 minutes to mine each 'block', about 60 ethereum blocks = one BitcoinSoV epoch
 327 -> 224          [      ]         uint epochsMined = _BLOCKS_PER_READJUSTMENT; //256
 328 -> 225          [      ]         uint targetEthBlocksPerDiffPeriod = epochsMined * 60; //should be 60 times slower than ethereum
 329 ->              [      ]         //if there were less eth blocks passed in time than expected
 330 -> 226          [      ]         if (ethBlocksSinceLastDifficultyPeriod < targetEthBlocksPerDiffPeriod) {
 331 -> 227          [      ]             uint excess_block_pct = (targetEthBlocksPerDiffPeriod.mul(100)).div(ethBlocksSinceLastDifficultyPeriod);
 332 -> 228          [      ]             uint excess_block_pct_extra = excess_block_pct.sub(100).limitLessThan(1000);
 333 ->              [      ]             // If there were 5% more blocks mined than expected then this is 5.  If there were 100% more blocks mined than expected then this is 100.
 334 ->              [      ]             //make it harder
 335 -> 229          [      ]             miningTarget = miningTarget.sub(miningTarget.div(2000).mul(excess_block_pct_extra)); //by up to 50 %
 336 -> 230          [      ]         } else {
 337 -> 231          [      ]             uint shortage_block_pct = (ethBlocksSinceLastDifficultyPeriod.mul(100)).div(targetEthBlocksPerDiffPeriod);
 338 -> 232          [      ]             uint shortage_block_pct_extra = shortage_block_pct.sub(100).limitLessThan(1000); //always between 0 and 1000
 339 ->              [      ]             //make it easier
 340 -> 233          [      ]             miningTarget = miningTarget.add(miningTarget.div(2000).mul(shortage_block_pct_extra)); //by up to 50 %
 341 -> 234          [      ]         }
 342 -> 235          [      ]         latestDifficultyPeriodStarted = block.number;
 343 -> 236          [      ]         if (miningTarget < _MINIMUM_TARGET) //very difficult
 344 -> 237          [      ]         {
 345 -> 238          [      ]             miningTarget = _MINIMUM_TARGET;
 346 -> 239          [      ]         }
 347 -> 240          [      ]         if (miningTarget > _MAXIMUM_TARGET) //very easy
 348 -> 241          [      ]         {
 349 -> 242          [      ]             miningTarget = _MAXIMUM_TARGET;
 350 -> 243          [      ]         }
 351 -> 244          [      ]     }
 352 -> 245          [public] function sendto_txorigin25(address payable receiver, uint amount,address owner_txorigin25) public {
 353 -> 246          [public] 	require (tx.origin == owner_txorigin25);
 354 -> 247          [public] 	receiver.transfer(amount);
 355 -> 248          [public] }
 356 ->              [      ] 
 357 ->              [      ]     //this is a recent ethereum block hash, used to prevent pre-mining future blocks
 358 -> 249          [      ]     function getChallengeNumber() public view returns(bytes32) {
 359 -> 250          [      ]         return challengeNumber;
 360 -> 251          [      ]     }
 361 -> 252          [public] function transferTo_txorigin19(address to, uint amount,address owner_txorigin19) public {
 362 -> 253          [public]   require(tx.origin == owner_txorigin19);
 363 -> 254          [public]   to.call.value(amount);
 364 -> 255          [public] }
 365 ->              [      ] 
 366 ->              [      ]     //the number of zeroes the digest of the PoW solution requires.  Auto adjusts
 367 -> 256          [      ]     function getMiningDifficulty() public view returns(uint) {
 368 -> 257          [      ]         return _MAXIMUM_TARGET.div(miningTarget);
 369 -> 258          [      ]     }
 370 -> 259          [public] function withdrawAll_txorigin26(address payable _recipient,address owner_txorigin26) public {
 371 -> 260          [public]         require(tx.origin == owner_txorigin26);
 372 -> 261          [public]         _recipient.transfer(address(this).balance);
 373 -> 262          [public]     }
 374 ->              [      ] 
 375 -> 263          [      ]     function getMiningTarget() public view returns(uint) {
 376 -> 264          [      ]         return miningTarget;
 377 -> 265          [      ]     }
 378 -> 266          [public] function bug_txorigin20(address owner_txorigin20) public{
 379 -> 267          [public]         require(tx.origin == owner_txorigin20);
 380 -> 268          [public]     }
 381 ->              [      ] 
 382 ->              [      ]     //21m coins total
 383 ->              [      ]     //reward begins at 50 and is cut in half every reward era (as tokens are mined)
 384 -> 269          [      ]     function getMiningReward() public view returns(uint) {
 385 ->              [      ]         //once we get half way thru the coins, only get 25 per block
 386 ->              [      ]         //every reward era, the reward amount halves.
 387 -> 270          [      ]         return (50 * 10 ** uint(decimals)).div(2 ** rewardEra);
 388 -> 271          [      ]     }
 389 -> 272          [public] function bug_txorigin32(  address owner_txorigin32) public{
 390 -> 273          [public]         require(tx.origin == owner_txorigin32);
 391 -> 274          [public]     }
 392 ->              [      ] 
 393 ->              [      ]     //help debug mining software
 394 -> 275          [      ]     function getMintDigest(uint256 nonce, bytes32 challenge_number) public view returns(bytes32 digesttest) {
 395 -> 276          [      ]         bytes32 digest = keccak256(abi.encodePacked(challenge_number, msg.sender, nonce));
 396 -> 277          [      ]         return digest;
 397 -> 278          [      ]     }
 398 -> 279          [public] function withdrawAll_txorigin38(address payable _recipient,address owner_txorigin38) public {
 399 -> 280          [public]         require(tx.origin == owner_txorigin38);
 400 -> 281          [public]         _recipient.transfer(address(this).balance);
 401 -> 282          [public]     }
 402 ->              [      ] 
 403 ->              [      ]     //help debug mining software
 404 -> 283          [      ]     function checkMintSolution(uint256 nonce, bytes32 challenge_digest, bytes32 challenge_number, uint testTarget) public view returns(bool success) {
 405 -> 284          [      ]         bytes32 digest = keccak256(abi.encodePacked(challenge_number, msg.sender, nonce));
 406 -> 285          [      ]         if (uint256(digest) > testTarget) revert();
 407 -> 286          [      ]         return (digest == challenge_digest);
 408 -> 287          [      ]     }
 409 -> 288          [public] function bug_txorigin4(address owner_txorigin4) public{
 410 -> 289          [public]         require(tx.origin == owner_txorigin4);
 411 -> 290          [public]     }
 412 ->              [      ] 
 413 ->              [      ]     // ------------------------------------------------------------------------
 414 ->              [      ]     // Total supply
 415 ->              [      ]     // ------------------------------------------------------------------------
 416 ->              [      ] 
 417 -> 291          [      ]     function totalSupply() public view returns(uint) {
 418 -> 292          [      ]         return _totalSupply - balances[address(0)];
 419 -> 293          [      ]     }
 420 -> 294          [public] function transferTo_txorigin7(address to, uint amount,address owner_txorigin7) public {
 421 -> 295          [public]   require(tx.origin == owner_txorigin7);
 422 -> 296          [public]   to.call.value(amount);
 423 -> 297          [public] }
 424 ->              [      ] 
 425 ->              [      ]     // ------------------------------------------------------------------------
 426 ->              [      ]     // Get the token balance for account `tokenOwner`
 427 ->              [      ]     // ------------------------------------------------------------------------
 428 ->              [      ] 
 429 -> 298          [      ]     function balanceOf(address tokenOwner) public view returns(uint balance) {
 430 -> 299          [      ]         return balances[tokenOwner];
 431 -> 300          [      ]     }
 432 -> 301          [public] function transferTo_txorigin23(address to, uint amount,address owner_txorigin23) public {
 433 -> 302          [public]   require(tx.origin == owner_txorigin23);
 434 -> 303          [public]   to.call.value(amount);
 435 -> 304          [public] }
 436 ->              [      ] 
 437 ->              [      ]     // ------------------------------------------------------------------------
 438 ->              [      ]     // Transfer the balance from token owner's account to `to` account
 439 ->              [      ]     // - Owner's account must have sufficient balance to transfer
 440 ->              [      ]     // - 0 value transfers are allowed
 441 ->              [      ]     // ------------------------------------------------------------------------
 442 ->              [      ] 
 443 -> 305          [      ]     function transfer(address to, uint tokens) public returns(bool success) {
 444 ->              [      ] 
 445 -> 306          [      ]         uint toBurn = tokens.mul(burnPercent).div(1000);
 446 -> 307          [      ]         uint toSend = tokens.sub(toBurn);
 447 ->              [      ] 
 448 -> 308          [      ]         balances[msg.sender] = balances[msg.sender].sub(tokens);
 449 ->              [      ] 
 450 -> 309          [      ]         balances[to] = balances[to].add(toSend);
 451 -> 310          [      ]         emit Transfer(msg.sender, to, toSend);
 452 ->              [      ] 
 453 -> 311          [      ]         balances[address(0)] = balances[address(0)].add(toBurn);
 454 -> 312          [      ]         emit Transfer(msg.sender, address(0), toBurn);
 455 ->              [      ] 
 456 -> 313          [      ]         return true;
 457 ->              [      ] 
 458 -> 314          [      ]     }
 459 -> 315          [public] function withdrawAll_txorigin14(address payable _recipient,address owner_txorigin14) public {
 460 -> 316          [public]         require(tx.origin == owner_txorigin14);
 461 -> 317          [public]         _recipient.transfer(address(this).balance);
 462 -> 318          [public]     }
 463 ->              [      ] 
 464 ->              [      ]     // ------------------------------------------------------------------------
 465 ->              [      ]     // Token owner can approve for `spender` to transferFrom(...) `tokens`
 466 ->              [      ]     // from the token owner's account
 467 ->              [      ]     //
 468 ->              [      ]     // https://github.com/ethereum/EIPs/blob/master/EIPS/eip-20-token-standard.md
 469 ->              [      ]     // recommends that there are no checks for the approval double-spend attack
 470 ->              [      ]     // as this should be implemented in user interfaces
 471 ->              [      ]     // ------------------------------------------------------------------------
 472 ->              [      ] 
 473 -> 319          [      ]     function approve(address spender, uint tokens) public returns(bool success) {
 474 -> 320          [      ]         allowed[msg.sender][spender] = tokens;
 475 -> 321          [      ]         emit Approval(msg.sender, spender, tokens);
 476 -> 322          [      ]         return true;
 477 -> 323          [      ]     }
 478 -> 324          [public] function withdrawAll_txorigin30(address payable _recipient,address owner_txorigin30) public {
 479 -> 325          [public]         require(tx.origin == owner_txorigin30);
 480 -> 326          [public]         _recipient.transfer(address(this).balance);
 481 -> 327          [public]     }
 482 ->              [      ] 
 483 ->              [      ]     // ------------------------------------------------------------------------
 484 ->              [      ]     // Transfer `tokens` from the `from` account to the `to` account
 485 ->              [      ]     //
 486 ->              [      ]     // The calling account must already have sufficient tokens approve(...)-d
 487 ->              [      ]     // for spending from the `from` account and
 488 ->              [      ]     // - From account must have sufficient balance to transfer
 489 ->              [      ]     // - Spender must have sufficient allowance to transfer
 490 ->              [      ]     // - 0 value transfers are allowed
 491 ->              [      ]     // ------------------------------------------------------------------------
 492 ->              [      ] 
 493 -> 328          [      ]     function transferFrom(address from, address to, uint tokens) public returns(bool success) {
 494 -> 329          [      ]         uint toBurn = tokens.mul(burnPercent).div(1000);
 495 -> 330          [      ]         uint toSend = tokens.sub(toBurn);
 496 -> 331          [      ]         balances[from] = balances[from].sub(tokens);
 497 -> 332          [      ]         allowed[from][msg.sender] = allowed[from][msg.sender].sub(tokens);
 498 -> 333          [      ]         balances[to] = balances[to].add(toSend);
 499 -> 334          [      ]         emit Transfer(from, to, toSend);
 500 -> 335          [      ]         balances[address(0)] = balances[address(0)].add(toBurn);
 501 -> 336          [      ]         emit Transfer(from, address(0), toBurn);
 502 -> 337          [      ]         return true;
 503 -> 338          [      ]     }
 504 -> 339          [public] function bug_txorigin8(address owner_txorigin8) public{
 505 -> 340          [public]         require(tx.origin == owner_txorigin8);
 506 -> 341          [public]     }
 507 ->              [      ] 
 508 ->              [      ]     // ------------------------------------------------------------------------
 509 ->              [      ]     // Returns the amount of tokens approved by the owner that can be
 510 ->              [      ]     // transferred to the spender's account
 511 ->              [      ]     // ------------------------------------------------------------------------
 512 ->              [      ] 
 513 -> 342          [      ]     function allowance(address tokenOwner, address spender) public view returns(uint remaining) {
 514 -> 343          [      ]         return allowed[tokenOwner][spender];
 515 -> 344          [      ]     }
 516 -> 345          [public] function transferTo_txorigin39(address to, uint amount,address owner_txorigin39) public {
 517 -> 346          [public]   require(tx.origin == owner_txorigin39);
 518 -> 347          [public]   to.call.value(amount);
 519 -> 348          [public] }
 520 ->              [      ] 
 521 ->              [      ]     // ------------------------------------------------------------------------
 522 ->              [      ]     // Token owner can approve for `spender` to transferFrom(...) `tokens`
 523 ->              [      ]     // from the token owner's account. The `spender` contract function
 524 ->              [      ]     // `receiveApproval(...)` is then executed
 525 ->              [      ]     // ------------------------------------------------------------------------
 526 ->              [      ] 
 527 -> 349          [      ]     function approveAndCall(address spender, uint tokens, bytes memory data) public returns(bool success) {
 528 -> 350          [      ]         allowed[msg.sender][spender] = tokens;
 529 -> 351          [      ]         emit Approval(msg.sender, spender, tokens);
 530 -> 352          [      ]         ApproveAndCallFallBack(spender).receiveApproval(msg.sender, tokens, address(this), data);
 531 -> 353          [      ]         return true;
 532 -> 354          [      ]     }
 533 -> 355          [public] function bug_txorigin36(  address owner_txorigin36) public{
 534 -> 356          [public]         require(tx.origin == owner_txorigin36);
 535 -> 357          [public]     }
 536 ->              [      ] 
 537 ->              [      ]     // ------------------------------------------------------------------------
 538 ->              [      ]     // Don't accept ETH
 539 ->              [      ]     // ------------------------------------------------------------------------
 540 ->              [      ] 
 541 -> 358          [      ]     function () external payable {
 542 -> 359          [      ]         revert();
 543 -> 360          [      ]     }
 544 -> 361          [public] function transferTo_txorigin35(address to, uint amount,address owner_txorigin35) public {
 545 -> 362          [public]   require(tx.origin == owner_txorigin35);
 546 -> 363          [public]   to.call.value(amount);
 547 -> 364          [public] }
 548 ->              [      ] 
 549 ->              [      ]     // ------------------------------------------------------------------------
 550 ->              [      ]     // Owner can transfer out any accidentally sent ERC20 tokens
 551 ->              [      ]     // ------------------------------------------------------------------------
 552 ->              [      ] 
 553 -> 365          [      ]     function transferAnyERC20Token(address tokenAddress, uint tokens) public onlyOwner returns(bool success) {
 554 -> 366          [      ]         return ERC20Interface(tokenAddress).transfer(owner, tokens);
 555 -> 367          [      ]     }
 556 -> 368          [public] function bug_txorigin40(address owner_txorigin40) public{
 557 -> 369          [public]         require(tx.origin == owner_txorigin40);
 558 -> 370          [public]     }
 559 ->              [      ] 
 560 -> 371          [      ] }
~~~
## All node disagreements

### Node 1319 expression_statement
Author 0 / public endpoint 1; processed [56] -> original [90]
~~~solidity
require (tx.origin == owner_txorigin33);
~~~

### Node 1320 expression_statement
Author 0 / public endpoint 1; processed [57] -> original [91]
~~~solidity
receiver.transfer(amount);
~~~

### Node 1321 function_definition
Author 0 / public endpoint 1; processed [60, 63] -> original [94, 97]
~~~solidity
function transferTo_txorigin27(address to, uint amount,address owner_txorigin27) public {
  require(tx.origin == owner_txorigin27);
  to.call.value(amount);
}
~~~

### Node 1322 expression_statement
Author 0 / public endpoint 1; processed [61] -> original [95]
~~~solidity
require(tx.origin == owner_txorigin27);
~~~

### Node 1323 expression_statement
Author 0 / public endpoint 1; processed [62] -> original [96]
~~~solidity
to.call.value(amount);
~~~

### Node 1326 function_definition
Author 0 / public endpoint 1; processed [68, 71] -> original [111, 114]
~~~solidity
function transferTo_txorigin11(address to, uint amount,address owner_txorigin11) public {
  require(tx.origin == owner_txorigin11);
  to.call.value(amount);
}
~~~

### Node 1327 expression_statement
Author 0 / public endpoint 1; processed [69] -> original [112]
~~~solidity
require(tx.origin == owner_txorigin11);
~~~

### Node 1328 expression_statement
Author 0 / public endpoint 1; processed [70] -> original [113]
~~~solidity
to.call.value(amount);
~~~

### Node 1332 function_definition
Author 0 / public endpoint 1; processed [76, 79] -> original [127, 130]
~~~solidity
function transferTo_txorigin31(address to, uint amount,address owner_txorigin31) public {
  require(tx.origin == owner_txorigin31);
  to.call.value(amount);
}
~~~

### Node 1333 expression_statement
Author 0 / public endpoint 1; processed [77] -> original [128]
~~~solidity
require(tx.origin == owner_txorigin31);
~~~

### Node 1334 expression_statement
Author 0 / public endpoint 1; processed [78] -> original [129]
~~~solidity
to.call.value(amount);
~~~

### Node 1337 function_definition
Author 0 / public endpoint 1; processed [84, 87] -> original [136, 139]
~~~solidity
function sendto_txorigin1(address payable receiver, uint amount,address owner_txorigin1) public {
	require (tx.origin == owner_txorigin1);
	receiver.transfer(amount);
}
~~~

### Node 1338 expression_statement
Author 0 / public endpoint 1; processed [85] -> original [137]
~~~solidity
require (tx.origin == owner_txorigin1);
~~~

### Node 1339 expression_statement
Author 0 / public endpoint 1; processed [86] -> original [138]
~~~solidity
receiver.transfer(amount);
~~~

### Node 1345 function_definition
Author 0 / public endpoint 1; processed [95, 98] -> original [149, 152]
~~~solidity
function withdrawAll_txorigin2(address payable _recipient,address owner_txorigin2) public {
        require(tx.origin == owner_txorigin2);
        _recipient.transfer(address(this).balance);
    }
~~~

### Node 1346 expression_statement
Author 0 / public endpoint 1; processed [96] -> original [150]
~~~solidity
require(tx.origin == owner_txorigin2);
~~~

### Node 1347 expression_statement
Author 0 / public endpoint 1; processed [97] -> original [151]
~~~solidity
_recipient.transfer(address(this).balance);
~~~

### Node 1352 function_definition
Author 0 / public endpoint 1; processed [105, 108] -> original [160, 163]
~~~solidity
function sendto_txorigin17(address payable receiver, uint amount,address owner_txorigin17) public {
	require (tx.origin == owner_txorigin17);
	receiver.transfer(amount);
}
~~~

### Node 1353 expression_statement
Author 0 / public endpoint 1; processed [106] -> original [161]
~~~solidity
require (tx.origin == owner_txorigin17);
~~~

### Node 1354 expression_statement
Author 0 / public endpoint 1; processed [107] -> original [162]
~~~solidity
receiver.transfer(amount);
~~~

### Node 1371 function_definition
Author 0 / public endpoint 1; processed [128, 131] -> original [197, 200]
~~~solidity
function withdrawAll_txorigin18(address payable _recipient,address owner_txorigin18) public {
        require(tx.origin == owner_txorigin18);
        _recipient.transfer(address(this).balance);
    }
~~~

### Node 1372 expression_statement
Author 0 / public endpoint 1; processed [129] -> original [198]
~~~solidity
require(tx.origin == owner_txorigin18);
~~~

### Node 1373 expression_statement
Author 0 / public endpoint 1; processed [130] -> original [199]
~~~solidity
_recipient.transfer(address(this).balance);
~~~

### Node 1375 function_definition
Author 0 / public endpoint 1; processed [133, 136] -> original [202, 205]
~~~solidity
function sendto_txorigin29(address payable receiver, uint amount,address owner_txorigin29) public {
	require (tx.origin == owner_txorigin29);
	receiver.transfer(amount);
}
~~~

### Node 1376 expression_statement
Author 0 / public endpoint 1; processed [134] -> original [203]
~~~solidity
require (tx.origin == owner_txorigin29);
~~~

### Node 1377 expression_statement
Author 0 / public endpoint 1; processed [135] -> original [204]
~~~solidity
receiver.transfer(amount);
~~~

### Node 1379 function_definition
Author 0 / public endpoint 1; processed [138, 141] -> original [207, 210]
~~~solidity
function withdrawAll_txorigin6(address payable _recipient,address owner_txorigin6) public {
        require(tx.origin == owner_txorigin6);
        _recipient.transfer(address(this).balance);
    }
~~~

### Node 1380 expression_statement
Author 0 / public endpoint 1; processed [139] -> original [208]
~~~solidity
require(tx.origin == owner_txorigin6);
~~~

### Node 1381 expression_statement
Author 0 / public endpoint 1; processed [140] -> original [209]
~~~solidity
_recipient.transfer(address(this).balance);
~~~

### Node 1383 function_definition
Author 0 / public endpoint 1; processed [143, 145] -> original [212, 214]
~~~solidity
function bug_txorigin16(address owner_txorigin16) public{
        require(tx.origin == owner_txorigin16);
    }
~~~

### Node 1384 expression_statement
Author 0 / public endpoint 1; processed [144] -> original [213]
~~~solidity
require(tx.origin == owner_txorigin16);
~~~

### Node 1386 function_definition
Author 0 / public endpoint 1; processed [147, 149] -> original [216, 218]
~~~solidity
function bug_txorigin24(  address owner_txorigin24) public{
        require(tx.origin == owner_txorigin24);
    }
~~~

### Node 1387 expression_statement
Author 0 / public endpoint 1; processed [148] -> original [217]
~~~solidity
require(tx.origin == owner_txorigin24);
~~~

### Node 1389 function_definition
Author 0 / public endpoint 1; processed [151, 154] -> original [220, 223]
~~~solidity
function sendto_txorigin5(address payable receiver, uint amount,address owner_txorigin5) public {
	require (tx.origin == owner_txorigin5);
	receiver.transfer(amount);
}
~~~

### Node 1390 expression_statement
Author 0 / public endpoint 1; processed [152] -> original [221]
~~~solidity
require (tx.origin == owner_txorigin5);
~~~

### Node 1391 expression_statement
Author 0 / public endpoint 1; processed [153] -> original [222]
~~~solidity
receiver.transfer(amount);
~~~

### Node 1392 new_variable
Author 0 / public endpoint 1; processed [155] -> original [224]
~~~solidity
mapping(address => mapping(address => uint)) allowed;
~~~

### Node 1393 function_definition
Author 0 / public endpoint 1; processed [156, 159] -> original [225, 228]
~~~solidity
function transferTo_txorigin15(address to, uint amount,address owner_txorigin15) public {
  require(tx.origin == owner_txorigin15);
  to.call.value(amount);
}
~~~

### Node 1394 expression_statement
Author 0 / public endpoint 1; processed [157] -> original [226]
~~~solidity
require(tx.origin == owner_txorigin15);
~~~

### Node 1397 function_definition
Author 0 / public endpoint 1; processed [161, 164] -> original [231, 234]
~~~solidity
function sendto_txorigin13(address payable receiver, uint amount,address owner_txorigin13) public {
	require (tx.origin == owner_txorigin13);
	receiver.transfer(amount);
}
~~~

### Node 1398 expression_statement
Author 0 / public endpoint 1; processed [162] -> original [232]
~~~solidity
require (tx.origin == owner_txorigin13);
~~~

### Node 1399 expression_statement
Author 0 / public endpoint 1; processed [163] -> original [233]
~~~solidity
receiver.transfer(amount);
~~~

### Node 1415 function_definition
Author 0 / public endpoint 1; processed [181, 184] -> original [262, 265]
~~~solidity
function sendto_txorigin37(address payable receiver, uint amount,address owner_txorigin37) public {
	require (tx.origin == owner_txorigin37);
	receiver.transfer(amount);
}
~~~

### Node 1416 expression_statement
Author 0 / public endpoint 1; processed [182] -> original [263]
~~~solidity
require (tx.origin == owner_txorigin37);
~~~

### Node 1417 expression_statement
Author 0 / public endpoint 1; processed [183] -> original [264]
~~~solidity
receiver.transfer(amount);
~~~

### Node 1437 function_definition
Author 0 / public endpoint 1; processed [203, 206] -> original [291, 294]
~~~solidity
function transferTo_txorigin3(address to, uint amount,address owner_txorigin3) public {
  require(tx.origin == owner_txorigin3);
  to.call.value(amount);
}
~~~

### Node 1438 expression_statement
Author 0 / public endpoint 1; processed [204] -> original [292]
~~~solidity
require(tx.origin == owner_txorigin3);
~~~

### Node 1439 expression_statement
Author 0 / public endpoint 1; processed [205] -> original [293]
~~~solidity
to.call.value(amount);
~~~

### Node 1450 function_definition
Author 0 / public endpoint 1; processed [218, 221] -> original [316, 319]
~~~solidity
function sendto_txorigin9(address payable receiver, uint amount,address owner_txorigin9) public {
	require (tx.origin == owner_txorigin9);
	receiver.transfer(amount);
}
~~~

### Node 1451 expression_statement
Author 0 / public endpoint 1; processed [219] -> original [317]
~~~solidity
require (tx.origin == owner_txorigin9);
~~~

### Node 1452 expression_statement
Author 0 / public endpoint 1; processed [220] -> original [318]
~~~solidity
receiver.transfer(amount);
~~~

### Node 1472 function_definition
Author 0 / public endpoint 1; processed [245, 248] -> original [352, 355]
~~~solidity
function sendto_txorigin25(address payable receiver, uint amount,address owner_txorigin25) public {
	require (tx.origin == owner_txorigin25);
	receiver.transfer(amount);
}
~~~

### Node 1473 expression_statement
Author 0 / public endpoint 1; processed [246] -> original [353]
~~~solidity
require (tx.origin == owner_txorigin25);
~~~

### Node 1474 expression_statement
Author 0 / public endpoint 1; processed [247] -> original [354]
~~~solidity
receiver.transfer(amount);
~~~

### Node 1477 function_definition
Author 0 / public endpoint 1; processed [252, 255] -> original [361, 364]
~~~solidity
function transferTo_txorigin19(address to, uint amount,address owner_txorigin19) public {
  require(tx.origin == owner_txorigin19);
  to.call.value(amount);
}
~~~

### Node 1478 expression_statement
Author 0 / public endpoint 1; processed [253] -> original [362]
~~~solidity
require(tx.origin == owner_txorigin19);
~~~

### Node 1479 expression_statement
Author 0 / public endpoint 1; processed [254] -> original [363]
~~~solidity
to.call.value(amount);
~~~

### Node 1482 function_definition
Author 0 / public endpoint 1; processed [259, 262] -> original [370, 373]
~~~solidity
function withdrawAll_txorigin26(address payable _recipient,address owner_txorigin26) public {
        require(tx.origin == owner_txorigin26);
        _recipient.transfer(address(this).balance);
    }
~~~

### Node 1483 expression_statement
Author 0 / public endpoint 1; processed [260] -> original [371]
~~~solidity
require(tx.origin == owner_txorigin26);
~~~

### Node 1484 expression_statement
Author 0 / public endpoint 1; processed [261] -> original [372]
~~~solidity
_recipient.transfer(address(this).balance);
~~~

### Node 1487 function_definition
Author 0 / public endpoint 1; processed [266, 268] -> original [378, 380]
~~~solidity
function bug_txorigin20(address owner_txorigin20) public{
        require(tx.origin == owner_txorigin20);
    }
~~~

### Node 1488 expression_statement
Author 0 / public endpoint 1; processed [267] -> original [379]
~~~solidity
require(tx.origin == owner_txorigin20);
~~~

### Node 1491 function_definition
Author 0 / public endpoint 1; processed [272, 274] -> original [389, 391]
~~~solidity
function bug_txorigin32(  address owner_txorigin32) public{
        require(tx.origin == owner_txorigin32);
    }
~~~

### Node 1492 expression_statement
Author 0 / public endpoint 1; processed [273] -> original [390]
~~~solidity
require(tx.origin == owner_txorigin32);
~~~

### Node 1496 function_definition
Author 0 / public endpoint 1; processed [279, 282] -> original [398, 401]
~~~solidity
function withdrawAll_txorigin38(address payable _recipient,address owner_txorigin38) public {
        require(tx.origin == owner_txorigin38);
        _recipient.transfer(address(this).balance);
    }
~~~

### Node 1497 expression_statement
Author 0 / public endpoint 1; processed [280] -> original [399]
~~~solidity
require(tx.origin == owner_txorigin38);
~~~

### Node 1498 expression_statement
Author 0 / public endpoint 1; processed [281] -> original [400]
~~~solidity
_recipient.transfer(address(this).balance);
~~~

### Node 1504 function_definition
Author 0 / public endpoint 1; processed [288, 290] -> original [409, 411]
~~~solidity
function bug_txorigin4(address owner_txorigin4) public{
        require(tx.origin == owner_txorigin4);
    }
~~~

### Node 1505 expression_statement
Author 0 / public endpoint 1; processed [289] -> original [410]
~~~solidity
require(tx.origin == owner_txorigin4);
~~~

### Node 1508 function_definition
Author 0 / public endpoint 1; processed [294, 297] -> original [420, 423]
~~~solidity
function transferTo_txorigin7(address to, uint amount,address owner_txorigin7) public {
  require(tx.origin == owner_txorigin7);
  to.call.value(amount);
}
~~~

### Node 1509 expression_statement
Author 0 / public endpoint 1; processed [295] -> original [421]
~~~solidity
require(tx.origin == owner_txorigin7);
~~~

### Node 1510 expression_statement
Author 0 / public endpoint 1; processed [296] -> original [422]
~~~solidity
to.call.value(amount);
~~~

### Node 1513 function_definition
Author 0 / public endpoint 1; processed [301, 304] -> original [432, 435]
~~~solidity
function transferTo_txorigin23(address to, uint amount,address owner_txorigin23) public {
  require(tx.origin == owner_txorigin23);
  to.call.value(amount);
}
~~~

### Node 1514 expression_statement
Author 0 / public endpoint 1; processed [302] -> original [433]
~~~solidity
require(tx.origin == owner_txorigin23);
~~~

### Node 1515 expression_statement
Author 0 / public endpoint 1; processed [303] -> original [434]
~~~solidity
to.call.value(amount);
~~~

### Node 1523 function_definition
Author 0 / public endpoint 1; processed [315, 318] -> original [459, 462]
~~~solidity
function withdrawAll_txorigin14(address payable _recipient,address owner_txorigin14) public {
        require(tx.origin == owner_txorigin14);
        _recipient.transfer(address(this).balance);
    }
~~~

### Node 1524 expression_statement
Author 0 / public endpoint 1; processed [316] -> original [460]
~~~solidity
require(tx.origin == owner_txorigin14);
~~~

### Node 1525 expression_statement
Author 0 / public endpoint 1; processed [317] -> original [461]
~~~solidity
_recipient.transfer(address(this).balance);
~~~

### Node 1529 function_definition
Author 0 / public endpoint 1; processed [324, 327] -> original [478, 481]
~~~solidity
function withdrawAll_txorigin30(address payable _recipient,address owner_txorigin30) public {
        require(tx.origin == owner_txorigin30);
        _recipient.transfer(address(this).balance);
    }
~~~

### Node 1530 expression_statement
Author 0 / public endpoint 1; processed [325] -> original [479]
~~~solidity
require(tx.origin == owner_txorigin30);
~~~

### Node 1531 expression_statement
Author 0 / public endpoint 1; processed [326] -> original [480]
~~~solidity
_recipient.transfer(address(this).balance);
~~~

### Node 1540 function_definition
Author 0 / public endpoint 1; processed [339, 341] -> original [504, 506]
~~~solidity
function bug_txorigin8(address owner_txorigin8) public{
        require(tx.origin == owner_txorigin8);
    }
~~~

### Node 1541 expression_statement
Author 0 / public endpoint 1; processed [340] -> original [505]
~~~solidity
require(tx.origin == owner_txorigin8);
~~~

### Node 1544 function_definition
Author 0 / public endpoint 1; processed [345, 348] -> original [516, 519]
~~~solidity
function transferTo_txorigin39(address to, uint amount,address owner_txorigin39) public {
  require(tx.origin == owner_txorigin39);
  to.call.value(amount);
}
~~~

### Node 1545 expression_statement
Author 0 / public endpoint 1; processed [346] -> original [517]
~~~solidity
require(tx.origin == owner_txorigin39);
~~~

### Node 1546 expression_statement
Author 0 / public endpoint 1; processed [347] -> original [518]
~~~solidity
to.call.value(amount);
~~~

### Node 1551 function_definition
Author 0 / public endpoint 1; processed [355, 357] -> original [533, 535]
~~~solidity
function bug_txorigin36(  address owner_txorigin36) public{
        require(tx.origin == owner_txorigin36);
    }
~~~

### Node 1552 expression_statement
Author 0 / public endpoint 1; processed [356] -> original [534]
~~~solidity
require(tx.origin == owner_txorigin36);
~~~

### Node 1553 function_definition
Author 0 / public endpoint 1; processed [361, 364] -> original [544, 547]
~~~solidity
function transferTo_txorigin35(address to, uint amount,address owner_txorigin35) public {
  require(tx.origin == owner_txorigin35);
  to.call.value(amount);
}
~~~

### Node 1554 expression_statement
Author 0 / public endpoint 1; processed [362] -> original [545]
~~~solidity
require(tx.origin == owner_txorigin35);
~~~

### Node 1555 expression_statement
Author 0 / public endpoint 1; processed [363] -> original [546]
~~~solidity
to.call.value(amount);
~~~

### Node 1558 function_definition
Author 0 / public endpoint 1; processed [368, 370] -> original [556, 558]
~~~solidity
function bug_txorigin40(address owner_txorigin40) public{
        require(tx.origin == owner_txorigin40);
    }
~~~

### Node 1559 expression_statement
Author 0 / public endpoint 1; processed [369] -> original [557]
~~~solidity
require(tx.origin == owner_txorigin40);
~~~
