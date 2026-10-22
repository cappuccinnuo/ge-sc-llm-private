# reentrancy/buggy_18.sol
Source SHA: b9e23563d26a4976a295154577358f01d63bf533c67775b065a877b934bef9ec
This is a source/label review. Model predictions were not used.

## Summary
~~~json
{
  "source": "/home/zhao/SmartContract/ge-sc-llm/data/SolidiFI-benchmark/buggy_contracts/Re-entrancy/buggy_18.sol",
  "source_sha256": "b9e23563d26a4976a295154577358f01d63bf533c67775b065a877b934bef9ec",
  "source_provenance": {
    "path": "/home/zhao/SmartContract/ge-sc-llm/data/SolidiFI-benchmark/buggy_contracts/Re-entrancy/buggy_18.sol",
    "sha256": "b9e23563d26a4976a295154577358f01d63bf533c67775b065a877b934bef9ec",
    "equals_git_head": true
  },
  "public_input_provenance": [
    {
      "path": "/home/zhao/SmartContract/ge-sc-llm/data/SolidiFI-benchmark/buggy_contracts/Re-entrancy/BugLog_18.csv",
      "sha256": "3141b06ab00204469600650c8a77f341b048d199659a0d2b04601078b7247532",
      "equals_git_head": true
    },
    {
      "path": "/home/zhao/SmartContract/ge-sc-transformer/data/solidifi_buggy_contracts/reentrancy/buggy_18.sol",
      "sha256": "b9e23563d26a4976a295154577358f01d63bf533c67775b065a877b934bef9ec",
      "equals_git_head": true
    },
    {
      "path": "/home/zhao/SmartContract/ge-sc-transformer/data/solidifi_buggy_contracts/reentrancy/BugLog_18.csv",
      "sha256": "3141b06ab00204469600650c8a77f341b048d199659a0d2b04601078b7247532",
      "equals_git_head": true
    },
    {
      "path": "/home/zhao/SmartContract/ge-sc-transformer/data/solidifi_buggy_contracts/reentrancy/vulnerabilities.json",
      "sha256": "48e0c5733f4fdcb776d2930982855fb877e2c32b4dc82d3945b4ae4ca5530aa8",
      "equals_git_head": true
    }
  ],
  "source_check": {
    "local_source": "/home/zhao/SmartContract/ge-sc-llm/experiments/ge-sc-data/source_code/reentrancy/source_files/buggy_18.sol",
    "canonical_source": "/home/zhao/SmartContract/ge-sc-llm/data/SolidiFI-benchmark/buggy_contracts/Re-entrancy/buggy_18.sol",
    "local_sha256": "b9e23563d26a4976a295154577358f01d63bf533c67775b065a877b934bef9ec",
    "canonical_sha256": "b9e23563d26a4976a295154577358f01d63bf533c67775b065a877b934bef9ec",
    "source_comparison": "byte_identical",
    "changed_original_line_ranges": [],
    "local_original_lines": 738,
    "canonical_original_lines": 738,
    "local_preprocessed_lines": 525,
    "canonical_preprocessed_lines": 525,
    "mapping_basis": "canonical_source_original_1based",
    "csv": "/home/zhao/SmartContract/ge-sc-llm/data/SolidiFI-benchmark/buggy_contracts/Re-entrancy/BugLog_18.csv",
    "csv_rows": 42,
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
    "overlapping_annotation_lines": 4,
    "duplicate_line_occurrences": 4,
    "annotation_lines": 324,
    "csv_bug_type_values": [
      "Re+AC0-erntrancy"
    ],
    "csv_approach_values": [
      "code snippet injection"
    ],
    "interval_rule": "[loc, loc+length-1], merged per file",
    "dataset": "SolidiFI",
    "contract_target": 1,
    "hgt_annotation": "/home/zhao/SmartContract/ge-sc-transformer/data/solidifi_buggy_contracts/reentrancy/vulnerabilities.json",
    "hgt_annotation_compare": "raw_line_sets_equal",
    "hgt_record_count": 1
  },
  "contract_target": 1,
  "original_lines": 738,
  "processed_lines": 525,
  "annotation_original": [
    {
      "category": "reentrancy",
      "lines": [
        62,
        63,
        64,
        65,
        66,
        67,
        68,
        69,
        71,
        72,
        73,
        74,
        75,
        76,
        77,
        79,
        80,
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
        92,
        93,
        94,
        96,
        97,
        98,
        99,
        100,
        101,
        102,
        103,
        105,
        106,
        107,
        108,
        109,
        110,
        111,
        112,
        113,
        114,
        115,
        116,
        122,
        123,
        124,
        125,
        126,
        127,
        128,
        129,
        143,
        144,
        145,
        146,
        147,
        148,
        149,
        150,
        163,
        164,
        165,
        166,
        167,
        168,
        169,
        175,
        176,
        177,
        178,
        179,
        180,
        181,
        182,
        192,
        193,
        194,
        195,
        196,
        197,
        198,
        199,
        207,
        208,
        209,
        210,
        211,
        212,
        213,
        214,
        245,
        246,
        247,
        248,
        249,
        250,
        251,
        252,
        254,
        255,
        256,
        257,
        258,
        260,
        261,
        262,
        263,
        264,
        265,
        266,
        267,
        269,
        270,
        271,
        272,
        273,
        274,
        275,
        276,
        278,
        279,
        280,
        281,
        282,
        283,
        284,
        286,
        287,
        288,
        289,
        290,
        291,
        292,
        293,
        294,
        296,
        297,
        298,
        299,
        300,
        303,
        304,
        305,
        306,
        307,
        308,
        309,
        310,
        312,
        313,
        314,
        315,
        316,
        317,
        318,
        319,
        322,
        323,
        324,
        325,
        326,
        327,
        328,
        329,
        330,
        358,
        359,
        360,
        361,
        362,
        363,
        364,
        365,
        391,
        392,
        393,
        394,
        395,
        396,
        397,
        398,
        420,
        421,
        422,
        423,
        424,
        425,
        426,
        427,
        428,
        461,
        462,
        463,
        464,
        465,
        466,
        467,
        468,
        474,
        475,
        476,
        477,
        478,
        479,
        480,
        481,
        482,
        488,
        489,
        490,
        491,
        492,
        493,
        494,
        495,
        496,
        497,
        502,
        503,
        504,
        505,
        506,
        507,
        508,
        509,
        518,
        519,
        520,
        521,
        522,
        523,
        524,
        525,
        532,
        533,
        534,
        535,
        536,
        537,
        538,
        546,
        547,
        548,
        549,
        550,
        551,
        552,
        553,
        562,
        563,
        564,
        565,
        566,
        567,
        568,
        569,
        578,
        579,
        580,
        581,
        582,
        583,
        584,
        585,
        609,
        610,
        611,
        612,
        613,
        614,
        615,
        616,
        632,
        633,
        634,
        635,
        636,
        637,
        638,
        639,
        662,
        663,
        664,
        665,
        666,
        667,
        677,
        678,
        679,
        680,
        681,
        682,
        683,
        684,
        698,
        699,
        700,
        701,
        702,
        711,
        712,
        713,
        714,
        715,
        716,
        717,
        718,
        727,
        728,
        729,
        730,
        731,
        732,
        733,
        734,
        735,
        736
      ]
    }
  ],
  "public_original_unique": 324,
  "public_processed_lines": [
    28,
    29,
    30,
    31,
    32,
    33,
    34,
    35,
    37,
    38,
    39,
    40,
    41,
    42,
    44,
    45,
    46,
    47,
    48,
    49,
    51,
    52,
    53,
    54,
    55,
    56,
    57,
    59,
    60,
    61,
    62,
    63,
    64,
    65,
    67,
    68,
    69,
    70,
    71,
    72,
    73,
    74,
    75,
    76,
    82,
    83,
    84,
    85,
    86,
    87,
    88,
    89,
    94,
    95,
    96,
    97,
    98,
    99,
    100,
    101,
    106,
    107,
    108,
    109,
    110,
    111,
    116,
    117,
    118,
    119,
    120,
    121,
    122,
    123,
    131,
    132,
    133,
    134,
    135,
    136,
    137,
    138,
    145,
    146,
    147,
    148,
    149,
    150,
    151,
    168,
    169,
    170,
    171,
    172,
    173,
    174,
    176,
    177,
    178,
    179,
    180,
    182,
    183,
    184,
    185,
    186,
    187,
    188,
    189,
    191,
    192,
    193,
    194,
    195,
    196,
    197,
    198,
    200,
    201,
    202,
    203,
    204,
    205,
    207,
    208,
    209,
    210,
    211,
    212,
    213,
    215,
    216,
    217,
    218,
    219,
    222,
    223,
    224,
    225,
    226,
    227,
    228,
    229,
    231,
    232,
    233,
    234,
    235,
    236,
    237,
    238,
    240,
    241,
    242,
    243,
    244,
    245,
    246,
    247,
    248,
    265,
    266,
    267,
    268,
    269,
    270,
    271,
    272,
    291,
    292,
    293,
    294,
    295,
    296,
    297,
    309,
    310,
    311,
    312,
    313,
    314,
    315,
    316,
    317,
    341,
    342,
    343,
    344,
    345,
    346,
    347,
    351,
    352,
    353,
    354,
    355,
    356,
    357,
    361,
    362,
    363,
    364,
    365,
    366,
    367,
    368,
    372,
    373,
    374,
    375,
    376,
    377,
    378,
    379,
    383,
    384,
    385,
    386,
    387,
    388,
    389,
    394,
    395,
    396,
    397,
    398,
    399,
    405,
    406,
    407,
    408,
    409,
    410,
    411,
    415,
    416,
    417,
    418,
    419,
    420,
    421,
    422,
    426,
    427,
    428,
    429,
    430,
    431,
    432,
    433,
    444,
    445,
    446,
    447,
    448,
    449,
    450,
    451,
    457,
    458,
    459,
    460,
    461,
    462,
    463,
    464,
    476,
    477,
    478,
    479,
    480,
    481,
    485,
    486,
    487,
    488,
    489,
    490,
    491,
    498,
    499,
    500,
    501,
    502,
    506,
    507,
    508,
    509,
    510,
    511,
    512,
    513,
    517,
    518,
    519,
    520,
    521,
    522,
    523,
    524
  ],
  "public_processed_unique": 300,
  "embedded_records": [
    {
      "lines": [
        28,
        29,
        30,
        31,
        32,
        33,
        34,
        35,
        37,
        38,
        39,
        40,
        41,
        42,
        44,
        45,
        46,
        47,
        48,
        49,
        51,
        52,
        53,
        54,
        55,
        56,
        57,
        59,
        60,
        61,
        62,
        63,
        64,
        65,
        67,
        68,
        69,
        70,
        71,
        72,
        73,
        583,
        584,
        585,
        586,
        592,
        593,
        594,
        595,
        596,
        597,
        598,
        599,
        623,
        624,
        625,
        627,
        672,
        673,
        674,
        675,
        676,
        677,
        707,
        708,
        709,
        711,
        728,
        731,
        735,
        751,
        767,
        775,
        776,
        777,
        779,
        815,
        819,
        821,
        837,
        838,
        840
      ],
      "category": "reentrancy"
    }
  ],
  "embedded_all_unique": 82,
  "embedded_target_unique": 82,
  "embedded_categories": [
    "reentrancy"
  ],
  "public_only_processed": [
    74,
    75,
    76,
    82,
    83,
    84,
    85,
    86,
    87,
    88,
    89,
    94,
    95,
    96,
    97,
    98,
    99,
    100,
    101,
    106,
    107,
    108,
    109,
    110,
    111,
    116,
    117,
    118,
    119,
    120,
    121,
    122,
    123,
    131,
    132,
    133,
    134,
    135,
    136,
    137,
    138,
    145,
    146,
    147,
    148,
    149,
    150,
    151,
    168,
    169,
    170,
    171,
    172,
    173,
    174,
    176,
    177,
    178,
    179,
    180,
    182,
    183,
    184,
    185,
    186,
    187,
    188,
    189,
    191,
    192,
    193,
    194,
    195,
    196,
    197,
    198,
    200,
    201,
    202,
    203,
    204,
    205,
    207,
    208,
    209,
    210,
    211,
    212,
    213,
    215,
    216,
    217,
    218,
    219,
    222,
    223,
    224,
    225,
    226,
    227,
    228,
    229,
    231,
    232,
    233,
    234,
    235,
    236,
    237,
    238,
    240,
    241,
    242,
    243,
    244,
    245,
    246,
    247,
    248,
    265,
    266,
    267,
    268,
    269,
    270,
    271,
    272,
    291,
    292,
    293,
    294,
    295,
    296,
    297,
    309,
    310,
    311,
    312,
    313,
    314,
    315,
    316,
    317,
    341,
    342,
    343,
    344,
    345,
    346,
    347,
    351,
    352,
    353,
    354,
    355,
    356,
    357,
    361,
    362,
    363,
    364,
    365,
    366,
    367,
    368,
    372,
    373,
    374,
    375,
    376,
    377,
    378,
    379,
    383,
    384,
    385,
    386,
    387,
    388,
    389,
    394,
    395,
    396,
    397,
    398,
    399,
    405,
    406,
    407,
    408,
    409,
    410,
    411,
    415,
    416,
    417,
    418,
    419,
    420,
    421,
    422,
    426,
    427,
    428,
    429,
    430,
    431,
    432,
    433,
    444,
    445,
    446,
    447,
    448,
    449,
    450,
    451,
    457,
    458,
    459,
    460,
    461,
    462,
    463,
    464,
    476,
    477,
    478,
    479,
    480,
    481,
    485,
    486,
    487,
    488,
    489,
    490,
    491,
    498,
    499,
    500,
    501,
    502,
    506,
    507,
    508,
    509,
    510,
    511,
    512,
    513,
    517,
    518,
    519,
    520,
    521,
    522,
    523,
    524
  ],
  "author_only_processed": [
    583,
    584,
    585,
    586,
    592,
    593,
    594,
    595,
    596,
    597,
    598,
    599,
    623,
    624,
    625,
    627,
    672,
    673,
    674,
    675,
    676,
    677,
    707,
    708,
    709,
    711,
    728,
    731,
    735,
    751,
    767,
    775,
    776,
    777,
    779,
    815,
    819,
    821,
    837,
    838,
    840
  ],
  "out_of_bounds_all": [
    583,
    584,
    585,
    586,
    592,
    593,
    594,
    595,
    596,
    597,
    598,
    599,
    623,
    624,
    625,
    627,
    672,
    673,
    674,
    675,
    676,
    677,
    707,
    708,
    709,
    711,
    728,
    731,
    735,
    751,
    767,
    775,
    776,
    777,
    779,
    815,
    819,
    821,
    837,
    838,
    840
  ],
  "overlap_processed": [
    28,
    29,
    30,
    31,
    32,
    33,
    34,
    35,
    37,
    38,
    39,
    40,
    41,
    42,
    44,
    45,
    46,
    47,
    48,
    49,
    51,
    52,
    53,
    54,
    55,
    56,
    57,
    59,
    60,
    61,
    62,
    63,
    64,
    65,
    67,
    68,
    69,
    70,
    71,
    72,
    73
  ],
  "nodes": 424,
  "author_positive": 35,
  "public_endpoint_positive": 249,
  "public_full_span_positive": 253,
  "disagreements": 214,
  "disagreement_types": {
    "function_definition": 36,
    "new_variable": 54,
    "if": 26,
    "end_if": 26,
    "expression_statement": 72
  },
  "disagreement_direction": {
    "0->1": 214
  },
  "self_endpoint_replay_mismatches": [],
  "projection_verified": {
    "ordinary_nodes_checked": 383,
    "synthetic_nodes": 41
  },
  "source_token_sequence_unchanged": true,
  "old_mapper_annotation_projection_equal": true,
  "csv_overlap_lines": [
    111,
    112,
    113,
    114
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
  62 -> 28           [public] uint256 counter_re_ent21 =0;
  63 -> 29           [public] function callme_re_ent21() public{
  64 -> 30           [public]         require(counter_re_ent21<=5);
  65 -> 31           [public] 	if( ! (msg.sender.send(10 ether) ) ){
  66 -> 32           [public]             revert();
  67 -> 33           [public]         }
  68 -> 34           [public]         counter_re_ent21 += 1;
  69 -> 35           [public]     }
  70 -> 36           [      ]     function balanceOf(address tokenOwner) public view returns(uint balance);
  71 -> 37           [public] mapping(address => uint) balances_re_ent10;
  72 -> 38           [public] function withdrawFunds_re_ent10 (uint256 _weiToWithdraw) public {
  73 -> 39           [public]         require(balances_re_ent10[msg.sender] >= _weiToWithdraw);
  74 ->              [public]         // limit the withdrawal
  75 -> 40           [public]         require(msg.sender.send(_weiToWithdraw));  //bug
  76 -> 41           [public]         balances_re_ent10[msg.sender] -= _weiToWithdraw;
  77 -> 42           [public]     }
  78 -> 43           [      ]     function allowance(address tokenOwner, address spender) public view returns(uint remaining);
  79 -> 44           [public] mapping(address => uint) balances_re_ent21;
  80 -> 45           [public]     function withdraw_balances_re_ent21 () public {
  81 -> 46           [public]        (bool success,)= msg.sender.call.value(balances_re_ent21[msg.sender ])("");
  82 -> 47           [public]        if (success)
  83 -> 48           [public]           balances_re_ent21[msg.sender] = 0;
  84 -> 49           [public]       }
  85 -> 50           [      ]     function transfer(address to, uint tokens) public returns(bool success);
  86 -> 51           [public] mapping(address => uint) userBalance_re_ent12;
  87 -> 52           [public] function withdrawBalance_re_ent12() public{
  88 ->              [public]         // send userBalance[msg.sender] ethers to msg.sender
  89 ->              [public]         // if mgs.sender is a contract, it will call its fallback function
  90 -> 53           [public]         if( ! (msg.sender.send(userBalance_re_ent12[msg.sender]) ) ){
  91 -> 54           [public]             revert();
  92 -> 55           [public]         }
  93 -> 56           [public]         userBalance_re_ent12[msg.sender] = 0;
  94 -> 57           [public]     }
  95 -> 58           [      ]     function approve(address spender, uint tokens) public returns(bool success);
  96 -> 59           [public] mapping(address => uint) redeemableEther_re_ent11;
  97 -> 60           [public] function claimReward_re_ent11() public {        
  98 ->              [public]         // ensure there is a reward to give
  99 -> 61           [public]         require(redeemableEther_re_ent11[msg.sender] > 0);
 100 -> 62           [public]         uint transferValue_re_ent11 = redeemableEther_re_ent11[msg.sender];
 101 -> 63           [public]         msg.sender.transfer(transferValue_re_ent11);   //bug
 102 -> 64           [public]         redeemableEther_re_ent11[msg.sender] = 0;
 103 -> 65           [public]     }
 104 -> 66           [      ]     function transferFrom(address from, address to, uint tokens) public returns(bool success);
 105 -> 67           [public] mapping(address => uint) balances_re_ent1;
 106 -> 68           [public]     function withdraw_balances_re_ent1 () public {
 107 -> 69           [public]        (bool success,) =msg.sender.call.value(balances_re_ent1[msg.sender ])("");
 108 -> 70           [public]        if (success)
 109 -> 71           [public]           balances_re_ent1[msg.sender] = 0;
 110 -> 72           [public]       }
 111 -> 73           [public]   mapping(address => uint) userBalance_re_ent33;
 112 -> 74           [public] function withdrawBalance_re_ent33() public{
 113 ->              [public]         // send userBalance[msg.sender] ethers to msg.sender
 114 ->              [public]         // if mgs.sender is a contract, it will call its fallback function
 115 -> 75           [public]         (bool success,)= msg.sender.call.value(userBalance_re_ent33[msg.sender])("");
 116 -> 76           [public]         if( ! success ){
 117 -> 77           [      ]             revert();
 118 -> 78           [      ]         }
 119 -> 79           [      ]         userBalance_re_ent33[msg.sender] = 0;
 120 -> 80           [      ]     }
 121 -> 81           [      ]   event Transfer(address indexed from, address indexed to, uint tokens);
 122 -> 82           [public]   bool not_called_re_ent27 = true;
 123 -> 83           [public] function bug_re_ent27() public{
 124 -> 84           [public]         require(not_called_re_ent27);
 125 -> 85           [public]         if( ! (msg.sender.send(1 ether) ) ){
 126 -> 86           [public]             revert();
 127 -> 87           [public]         }
 128 -> 88           [public]         not_called_re_ent27 = false;
 129 -> 89           [public]     }
 130 -> 90           [      ]   event Approval(address indexed tokenOwner, address indexed spender, uint tokens);
 131 ->              [      ] 
 132 -> 91           [      ] }
 133 ->              [      ] 
 134 ->              [      ] // ----------------------------------------------------------------------------
 135 ->              [      ] // Contract function to receive approval and execute function in one call
 136 ->              [      ] //
 137 ->              [      ] // Borrowed from MiniMeToken
 138 ->              [      ] // ----------------------------------------------------------------------------
 139 ->              [      ] 
 140 -> 92           [      ] contract ApproveAndCallFallBack {
 141 ->              [      ] 
 142 -> 93           [      ]     function receiveApproval(address from, uint256 tokens, address token, bytes memory data) public;
 143 -> 94           [public] bool not_called_re_ent41 = true;
 144 -> 95           [public] function bug_re_ent41() public{
 145 -> 96           [public]         require(not_called_re_ent41);
 146 -> 97           [public]         if( ! (msg.sender.send(1 ether) ) ){
 147 -> 98           [public]             revert();
 148 -> 99           [public]         }
 149 -> 100          [public]         not_called_re_ent41 = false;
 150 -> 101          [public]     }
 151 ->              [      ] 
 152 -> 102          [      ] }
 153 ->              [      ] 
 154 ->              [      ] // ----------------------------------------------------------------------------
 155 ->              [      ] // Owned contract
 156 ->              [      ] // ----------------------------------------------------------------------------
 157 ->              [      ] 
 158 -> 103          [      ] contract Owned {
 159 ->              [      ] 
 160 -> 104          [      ]     address public owner;
 161 -> 105          [      ]     address public newOwner;
 162 ->              [      ] 
 163 -> 106          [public]   mapping(address => uint) balances_re_ent31;
 164 -> 107          [public] function withdrawFunds_re_ent31 (uint256 _weiToWithdraw) public {
 165 -> 108          [public]         require(balances_re_ent31[msg.sender] >= _weiToWithdraw);
 166 ->              [public]         // limit the withdrawal
 167 -> 109          [public]         require(msg.sender.send(_weiToWithdraw));  //bug
 168 -> 110          [public]         balances_re_ent31[msg.sender] -= _weiToWithdraw;
 169 -> 111          [public]     }
 170 -> 112          [      ]   event OwnershipTransferred(address indexed _from, address indexed _to);
 171 ->              [      ] 
 172 -> 113          [      ]     constructor() public {
 173 -> 114          [      ]         owner = msg.sender;
 174 -> 115          [      ]     }
 175 -> 116          [public] uint256 counter_re_ent42 =0;
 176 -> 117          [public] function callme_re_ent42() public{
 177 -> 118          [public]         require(counter_re_ent42<=5);
 178 -> 119          [public] 	if( ! (msg.sender.send(10 ether) ) ){
 179 -> 120          [public]             revert();
 180 -> 121          [public]         }
 181 -> 122          [public]         counter_re_ent42 += 1;
 182 -> 123          [public]     }
 183 ->              [      ] 
 184 -> 124          [      ]     modifier onlyOwner {
 185 -> 125          [      ]         require(msg.sender == owner);
 186 -> 126          [      ]         _;
 187 -> 127          [      ]     }
 188 ->              [      ] 
 189 -> 128          [      ]     function transferOwnership(address _newOwner) public onlyOwner {
 190 -> 129          [      ]         newOwner = _newOwner;
 191 -> 130          [      ]     }
 192 -> 131          [public] address payable lastPlayer_re_ent2;
 193 -> 132          [public]       uint jackpot_re_ent2;
 194 -> 133          [public] 	  function buyTicket_re_ent2() public{
 195 -> 134          [public] 	    if (!(lastPlayer_re_ent2.send(jackpot_re_ent2)))
 196 -> 135          [public]         revert();
 197 -> 136          [public]       lastPlayer_re_ent2 = msg.sender;
 198 -> 137          [public]       jackpot_re_ent2    = address(this).balance;
 199 -> 138          [public]     }
 200 ->              [      ] 
 201 -> 139          [      ]     function acceptOwnership() public {
 202 -> 140          [      ]         require(msg.sender == newOwner);
 203 -> 141          [      ]         emit OwnershipTransferred(owner, newOwner);
 204 -> 142          [      ]         owner = newOwner;
 205 -> 143          [      ]         newOwner = address(0);
 206 -> 144          [      ]     }
 207 -> 145          [public] mapping(address => uint) balances_re_ent17;
 208 -> 146          [public] function withdrawFunds_re_ent17 (uint256 _weiToWithdraw) public {
 209 -> 147          [public]         require(balances_re_ent17[msg.sender] >= _weiToWithdraw);
 210 ->              [public]         // limit the withdrawal
 211 -> 148          [public]         (bool success,)=msg.sender.call.value(_weiToWithdraw)("");
 212 -> 149          [public]         require(success);  //bug
 213 -> 150          [public]         balances_re_ent17[msg.sender] -= _weiToWithdraw;
 214 -> 151          [public]     }
 215 ->              [      ] 
 216 -> 152          [      ] }
 217 ->              [      ] 
 218 ->              [      ] // ----------------------------------------------------------------------------
 219 ->              [      ] // ERC20 Token, with the addition of symbol, name and decimals and an
 220 ->              [      ] // initial fixed supply
 221 ->              [      ] // ----------------------------------------------------------------------------
 222 ->              [      ] 
 223 -> 153          [      ] contract _Yesbuzz is ERC20Interface, Owned {
 224 ->              [      ] 
 225 -> 154          [      ]     using SafeMath for uint;
 226 -> 155          [      ]     using ExtendedMath for uint;
 227 ->              [      ] 
 228 -> 156          [      ]     string public symbol;
 229 -> 157          [      ]     string public name;
 230 -> 158          [      ]     uint8 public decimals;
 231 -> 159          [      ]     uint public _totalSupply;
 232 -> 160          [      ]     uint public latestDifficultyPeriodStarted;
 233 -> 161          [      ]     uint public epochCount; //number of 'blocks' mined
 234 -> 162          [      ]     uint public _BLOCKS_PER_READJUSTMENT = 1024;
 235 ->              [      ] 
 236 ->              [      ]     //a little number
 237 -> 163          [      ]     uint public _MINIMUM_TARGET = 2 ** 16;
 238 ->              [      ] 
 239 ->              [      ]     //a big number is easier ; just find a solution that is smaller
 240 ->              [      ]     //uint public  _MAXIMUM_TARGET = 2**224;  bitcoin uses 224
 241 -> 164          [      ]     uint public _MAXIMUM_TARGET = 2 ** 234;
 242 -> 165          [      ]     uint public miningTarget;
 243 -> 166          [      ]     bytes32 public challengeNumber; //generate a new one when a new reward is minted
 244 -> 167          [      ]     uint public rewardEra;
 245 -> 168          [public]   mapping(address => uint) redeemableEther_re_ent18;
 246 -> 169          [public] function claimReward_re_ent18() public {        
 247 ->              [public]         // ensure there is a reward to give
 248 -> 170          [public]         require(redeemableEther_re_ent18[msg.sender] > 0);
 249 -> 171          [public]         uint transferValue_re_ent18 = redeemableEther_re_ent18[msg.sender];
 250 -> 172          [public]         msg.sender.transfer(transferValue_re_ent18);   //bug
 251 -> 173          [public]         redeemableEther_re_ent18[msg.sender] = 0;
 252 -> 174          [public]     }
 253 -> 175          [      ]   uint public maxSupplyForEra;
 254 -> 176          [public]   mapping(address => uint) balances_re_ent29;
 255 -> 177          [public]     function withdraw_balances_re_ent29 () public {
 256 -> 178          [public]        if (msg.sender.send(balances_re_ent29[msg.sender ]))
 257 -> 179          [public]           balances_re_ent29[msg.sender] = 0;
 258 -> 180          [public]       }
 259 -> 181          [      ]   address public lastRewardTo;
 260 -> 182          [public]   bool not_called_re_ent6 = true;
 261 -> 183          [public] function bug_re_ent6() public{
 262 -> 184          [public]         require(not_called_re_ent6);
 263 -> 185          [public]         if( ! (msg.sender.send(1 ether) ) ){
 264 -> 186          [public]             revert();
 265 -> 187          [public]         }
 266 -> 188          [public]         not_called_re_ent6 = false;
 267 -> 189          [public]     }
 268 -> 190          [      ]   uint public lastRewardAmount;
 269 -> 191          [public]   address payable lastPlayer_re_ent16;
 270 -> 192          [public]       uint jackpot_re_ent16;
 271 -> 193          [public] 	  function buyTicket_re_ent16() public{
 272 -> 194          [public] 	    if (!(lastPlayer_re_ent16.send(jackpot_re_ent16)))
 273 -> 195          [public]         revert();
 274 -> 196          [public]       lastPlayer_re_ent16 = msg.sender;
 275 -> 197          [public]       jackpot_re_ent16    = address(this).balance;
 276 -> 198          [public]     }
 277 -> 199          [      ]   uint public lastRewardEthBlockNumber;
 278 -> 200          [public]   mapping(address => uint) balances_re_ent24;
 279 -> 201          [public] function withdrawFunds_re_ent24 (uint256 _weiToWithdraw) public {
 280 -> 202          [public]         require(balances_re_ent24[msg.sender] >= _weiToWithdraw);
 281 ->              [public]         // limit the withdrawal
 282 -> 203          [public]         require(msg.sender.send(_weiToWithdraw));  //bug
 283 -> 204          [public]         balances_re_ent24[msg.sender] -= _weiToWithdraw;
 284 -> 205          [public]     }
 285 -> 206          [      ]   bool locked = false;
 286 -> 207          [public]   mapping(address => uint) userBalance_re_ent5;
 287 -> 208          [public] function withdrawBalance_re_ent5() public{
 288 ->              [public]         // send userBalance[msg.sender] ethers to msg.sender
 289 ->              [public]         // if mgs.sender is a contract, it will call its fallback function
 290 -> 209          [public]         if( ! (msg.sender.send(userBalance_re_ent5[msg.sender]) ) ){
 291 -> 210          [public]             revert();
 292 -> 211          [public]         }
 293 -> 212          [public]         userBalance_re_ent5[msg.sender] = 0;
 294 -> 213          [public]     }
 295 -> 214          [      ]   mapping(bytes32 => bytes32) solutionForChallenge;
 296 -> 215          [public]   mapping(address => uint) balances_re_ent15;
 297 -> 216          [public]     function withdraw_balances_re_ent15 () public {
 298 -> 217          [public]        if (msg.sender.send(balances_re_ent15[msg.sender ]))
 299 -> 218          [public]           balances_re_ent15[msg.sender] = 0;
 300 -> 219          [public]       }
 301 -> 220          [      ]   uint public tokensMinted;
 302 -> 221          [      ]     mapping(address => uint) balances;
 303 -> 222          [public]   uint256 counter_re_ent28 =0;
 304 -> 223          [public] function callme_re_ent28() public{
 305 -> 224          [public]         require(counter_re_ent28<=5);
 306 -> 225          [public] 	if( ! (msg.sender.send(10 ether) ) ){
 307 -> 226          [public]             revert();
 308 -> 227          [public]         }
 309 -> 228          [public]         counter_re_ent28 += 1;
 310 -> 229          [public]     }
 311 -> 230          [      ]   mapping(address => mapping(address => uint)) allowed;
 312 -> 231          [public]   bool not_called_re_ent34 = true;
 313 -> 232          [public] function bug_re_ent34() public{
 314 -> 233          [public]         require(not_called_re_ent34);
 315 -> 234          [public]         if( ! (msg.sender.send(1 ether) ) ){
 316 -> 235          [public]             revert();
 317 -> 236          [public]         }
 318 -> 237          [public]         not_called_re_ent34 = false;
 319 -> 238          [public]     }
 320 -> 239          [      ]   uint public burnPercent;
 321 ->              [      ] 
 322 -> 240          [public]   bool not_called_re_ent13 = true;
 323 -> 241          [public] function bug_re_ent13() public{
 324 -> 242          [public]         require(not_called_re_ent13);
 325 -> 243          [public]         (bool success,)=msg.sender.call.value(1 ether)("");
 326 -> 244          [public]         if( ! success ){
 327 -> 245          [public]             revert();
 328 -> 246          [public]         }
 329 -> 247          [public]         not_called_re_ent13 = false;
 330 -> 248          [public]     }
 331 -> 249          [      ]   event Mint(address indexed from, uint reward_amount, uint epochCount, bytes32 newChallengeNumber);
 332 ->              [      ] 
 333 ->              [      ]     // ------------------------------------------------------------------------
 334 ->              [      ]     // Constructor
 335 ->              [      ]     // ------------------------------------------------------------------------
 336 ->              [      ] 
 337 -> 250          [      ]     constructor() public onlyOwner {
 338 ->              [      ] 
 339 -> 251          [      ]         symbol = "YESBUZ";
 340 -> 252          [      ]         name = "Yesbuzz";
 341 -> 253          [      ]         decimals = 8;
 342 -> 254          [      ]         _totalSupply = 21000000 * 10 ** uint(decimals);
 343 -> 255          [      ]         if (locked) revert();
 344 -> 256          [      ]         locked = true;
 345 -> 257          [      ]         tokensMinted = 0;
 346 -> 258          [      ]         rewardEra = 0;
 347 -> 259          [      ]         maxSupplyForEra = _totalSupply.div(2);
 348 -> 260          [      ]         miningTarget = _MAXIMUM_TARGET;
 349 -> 261          [      ]         latestDifficultyPeriodStarted = block.number;
 350 -> 262          [      ]         burnPercent = 10; //it's divided by 1000, then 10/1000 = 0.01 = 1%
 351 -> 263          [      ]         _startNewMiningEpoch();
 352 ->              [      ] 
 353 ->              [      ]         //The owner gets nothing! You must mine this ERC20 token
 354 ->              [      ]         //balances[owner] = _totalSupply;
 355 ->              [      ]         //Transfer(address(0), owner, _totalSupply);
 356 ->              [      ] 
 357 -> 264          [      ]     }
 358 -> 265          [public] address payable lastPlayer_re_ent37;
 359 -> 266          [public]       uint jackpot_re_ent37;
 360 -> 267          [public] 	  function buyTicket_re_ent37() public{
 361 -> 268          [public] 	    if (!(lastPlayer_re_ent37.send(jackpot_re_ent37)))
 362 -> 269          [public]         revert();
 363 -> 270          [public]       lastPlayer_re_ent37 = msg.sender;
 364 -> 271          [public]       jackpot_re_ent37    = address(this).balance;
 365 -> 272          [public]     }
 366 ->              [      ] 
 367 -> 273          [      ]     function mint(uint256 nonce, bytes32 challenge_digest) public returns(bool success) {
 368 ->              [      ]         //the PoW must contain work that includes a recent ethereum block hash (challenge number) and the msg.sender's address to prevent MITM attacks
 369 -> 274          [      ]         bytes32 digest = keccak256(abi.encodePacked(challengeNumber, msg.sender, nonce));
 370 ->              [      ]         //the challenge digest must match the expected
 371 -> 275          [      ]         if (digest != challenge_digest) revert();
 372 ->              [      ]         //the digest must be smaller than the target
 373 -> 276          [      ]         if (uint256(digest) > miningTarget) revert();
 374 ->              [      ]         //only allow one reward for each challenge
 375 -> 277          [      ]         bytes32 solution = solutionForChallenge[challengeNumber];
 376 -> 278          [      ]         solutionForChallenge[challengeNumber] = digest;
 377 -> 279          [      ]         if (solution != 0x0) revert(); //prevent the same answer from awarding twice
 378 -> 280          [      ]         uint reward_amount = getMiningReward();
 379 -> 281          [      ]         balances[msg.sender] = balances[msg.sender].add(reward_amount);
 380 -> 282          [      ]         tokensMinted = tokensMinted.add(reward_amount);
 381 ->              [      ]         //Cannot mint more tokens than there are
 382 -> 283          [      ]         assert(tokensMinted <= maxSupplyForEra);
 383 ->              [      ]         //set readonly diagnostics data
 384 -> 284          [      ]         lastRewardTo = msg.sender;
 385 -> 285          [      ]         lastRewardAmount = reward_amount;
 386 -> 286          [      ]         lastRewardEthBlockNumber = block.number;
 387 -> 287          [      ]         _startNewMiningEpoch();
 388 -> 288          [      ]         emit Mint(msg.sender, reward_amount, epochCount, challengeNumber);
 389 -> 289          [      ]         return true;
 390 -> 290          [      ]     }
 391 -> 291          [public] mapping(address => uint) balances_re_ent3;
 392 -> 292          [public] function withdrawFunds_re_ent3 (uint256 _weiToWithdraw) public {
 393 -> 293          [public]         require(balances_re_ent3[msg.sender] >= _weiToWithdraw);
 394 ->              [public]         // limit the withdrawal
 395 -> 294          [public] 	(bool success,)= msg.sender.call.value(_weiToWithdraw)("");
 396 -> 295          [public]         require(success);  //bug
 397 -> 296          [public]         balances_re_ent3[msg.sender] -= _weiToWithdraw;
 398 -> 297          [public]     }
 399 ->              [      ] 
 400 ->              [      ]     //a new 'block' to be mined
 401 -> 298          [      ]     function _startNewMiningEpoch() internal {
 402 ->              [      ]         //if max supply for the era will be exceeded next reward round then enter the new era before that happens
 403 ->              [      ]         //40 is the final reward era, almost all tokens minted
 404 ->              [      ]         //once the final era is reached, more tokens will not be given out because the assert function
 405 -> 299          [      ]         if (tokensMinted.add(getMiningReward()) > maxSupplyForEra && rewardEra < 39) {
 406 -> 300          [      ]             rewardEra = rewardEra + 1;
 407 -> 301          [      ]         }
 408 ->              [      ]         //set the next minted supply at which the era will change
 409 ->              [      ]         // total supply is 2100000000000000  because of 8 decimal places
 410 -> 302          [      ]         maxSupplyForEra = _totalSupply - _totalSupply.div(2 ** (rewardEra + 1));
 411 -> 303          [      ]         epochCount = epochCount.add(1);
 412 ->              [      ]         //every so often, readjust difficulty. Dont readjust when deploying
 413 -> 304          [      ]         if (epochCount % _BLOCKS_PER_READJUSTMENT == 0) {
 414 -> 305          [      ]             _reAdjustDifficulty();
 415 -> 306          [      ]         }
 416 ->              [      ]         //make the latest ethereum block hash a part of the next challenge for PoW to prevent pre-mining future blocks
 417 ->              [      ]         //do this last since this is a protection mechanism in the mint() function
 418 -> 307          [      ]         challengeNumber = blockhash(block.number - 1);
 419 -> 308          [      ]     }
 420 -> 309          [public] address payable lastPlayer_re_ent9;
 421 -> 310          [public]       uint jackpot_re_ent9;
 422 -> 311          [public] 	  function buyTicket_re_ent9() public{
 423 -> 312          [public] 	    (bool success,) = lastPlayer_re_ent9.call.value(jackpot_re_ent9)("");
 424 -> 313          [public] 	    if (!success)
 425 -> 314          [public] 	        revert();
 426 -> 315          [public]       lastPlayer_re_ent9 = msg.sender;
 427 -> 316          [public]       jackpot_re_ent9    = address(this).balance;
 428 -> 317          [public]     }
 429 ->              [      ]     //https://en.bitcoin.it/wiki/Difficulty#What_is_the_formula_for_difficulty.3F
 430 ->              [      ]     //as of 2017 the bitcoin difficulty was up to 17 zeroes, it was only 8 in the early days
 431 ->              [      ]     //readjust the target by 5 percent
 432 -> 318          [      ]     function _reAdjustDifficulty() internal {
 433 -> 319          [      ]         uint ethBlocksSinceLastDifficultyPeriod = block.number - latestDifficultyPeriodStarted;
 434 ->              [      ]         //assume 360 ethereum blocks per hour
 435 ->              [      ]         //we want miners to spend 10 minutes to mine each 'block', about 60 ethereum blocks = one BitcoinSoV epoch
 436 -> 320          [      ]         uint epochsMined = _BLOCKS_PER_READJUSTMENT; //256
 437 -> 321          [      ]         uint targetEthBlocksPerDiffPeriod = epochsMined * 60; //should be 60 times slower than ethereum
 438 ->              [      ]         //if there were less eth blocks passed in time than expected
 439 -> 322          [      ]         if (ethBlocksSinceLastDifficultyPeriod < targetEthBlocksPerDiffPeriod) {
 440 -> 323          [      ]             uint excess_block_pct = (targetEthBlocksPerDiffPeriod.mul(100)).div(ethBlocksSinceLastDifficultyPeriod);
 441 -> 324          [      ]             uint excess_block_pct_extra = excess_block_pct.sub(100).limitLessThan(1000);
 442 ->              [      ]             // If there were 5% more blocks mined than expected then this is 5.  If there were 100% more blocks mined than expected then this is 100.
 443 ->              [      ]             //make it harder
 444 -> 325          [      ]             miningTarget = miningTarget.sub(miningTarget.div(2000).mul(excess_block_pct_extra)); //by up to 50 %
 445 -> 326          [      ]         } else {
 446 -> 327          [      ]             uint shortage_block_pct = (ethBlocksSinceLastDifficultyPeriod.mul(100)).div(targetEthBlocksPerDiffPeriod);
 447 -> 328          [      ]             uint shortage_block_pct_extra = shortage_block_pct.sub(100).limitLessThan(1000); //always between 0 and 1000
 448 ->              [      ]             //make it easier
 449 -> 329          [      ]             miningTarget = miningTarget.add(miningTarget.div(2000).mul(shortage_block_pct_extra)); //by up to 50 %
 450 -> 330          [      ]         }
 451 -> 331          [      ]         latestDifficultyPeriodStarted = block.number;
 452 -> 332          [      ]         if (miningTarget < _MINIMUM_TARGET) //very difficult
 453 -> 333          [      ]         {
 454 -> 334          [      ]             miningTarget = _MINIMUM_TARGET;
 455 -> 335          [      ]         }
 456 -> 336          [      ]         if (miningTarget > _MAXIMUM_TARGET) //very easy
 457 -> 337          [      ]         {
 458 -> 338          [      ]             miningTarget = _MAXIMUM_TARGET;
 459 -> 339          [      ]         }
 460 -> 340          [      ]     }
 461 -> 341          [public] mapping(address => uint) redeemableEther_re_ent25;
 462 -> 342          [public] function claimReward_re_ent25() public {        
 463 ->              [public]         // ensure there is a reward to give
 464 -> 343          [public]         require(redeemableEther_re_ent25[msg.sender] > 0);
 465 -> 344          [public]         uint transferValue_re_ent25 = redeemableEther_re_ent25[msg.sender];
 466 -> 345          [public]         msg.sender.transfer(transferValue_re_ent25);   //bug
 467 -> 346          [public]         redeemableEther_re_ent25[msg.sender] = 0;
 468 -> 347          [public]     }
 469 ->              [      ] 
 470 ->              [      ]     //this is a recent ethereum block hash, used to prevent pre-mining future blocks
 471 -> 348          [      ]     function getChallengeNumber() public view returns(bytes32) {
 472 -> 349          [      ]         return challengeNumber;
 473 -> 350          [      ]     }
 474 -> 351          [public] mapping(address => uint) userBalance_re_ent19;
 475 -> 352          [public] function withdrawBalance_re_ent19() public{
 476 ->              [public]         // send userBalance[msg.sender] ethers to msg.sender
 477 ->              [public]         // if mgs.sender is a contract, it will call its fallback function
 478 -> 353          [public]         if( ! (msg.sender.send(userBalance_re_ent19[msg.sender]) ) ){
 479 -> 354          [public]             revert();
 480 -> 355          [public]         }
 481 -> 356          [public]         userBalance_re_ent19[msg.sender] = 0;
 482 -> 357          [public]     }
 483 ->              [      ] 
 484 ->              [      ]     //the number of zeroes the digest of the PoW solution requires.  Auto adjusts
 485 -> 358          [      ]     function getMiningDifficulty() public view returns(uint) {
 486 -> 359          [      ]         return _MAXIMUM_TARGET.div(miningTarget);
 487 -> 360          [      ]     }
 488 -> 361          [public] mapping(address => uint) userBalance_re_ent26;
 489 -> 362          [public] function withdrawBalance_re_ent26() public{
 490 ->              [public]         // send userBalance[msg.sender] ethers to msg.sender
 491 ->              [public]         // if mgs.sender is a contract, it will call its fallback function
 492 -> 363          [public]         (bool success,)= msg.sender.call.value(userBalance_re_ent26[msg.sender])("");
 493 -> 364          [public]         if( ! success ){
 494 -> 365          [public]             revert();
 495 -> 366          [public]         }
 496 -> 367          [public]         userBalance_re_ent26[msg.sender] = 0;
 497 -> 368          [public]     }
 498 ->              [      ] 
 499 -> 369          [      ]     function getMiningTarget() public view returns(uint) {
 500 -> 370          [      ]         return miningTarget;
 501 -> 371          [      ]     }
 502 -> 372          [public] bool not_called_re_ent20 = true;
 503 -> 373          [public] function bug_re_ent20() public{
 504 -> 374          [public]         require(not_called_re_ent20);
 505 -> 375          [public]         if( ! (msg.sender.send(1 ether) ) ){
 506 -> 376          [public]             revert();
 507 -> 377          [public]         }
 508 -> 378          [public]         not_called_re_ent20 = false;
 509 -> 379          [public]     }
 510 ->              [      ] 
 511 ->              [      ]     //21m coins total
 512 ->              [      ]     //reward begins at 50 and is cut in half every reward era (as tokens are mined)
 513 -> 380          [      ]     function getMiningReward() public view returns(uint) {
 514 ->              [      ]         //once we get half way thru the coins, only get 25 per block
 515 ->              [      ]         //every reward era, the reward amount halves.
 516 -> 381          [      ]         return (50 * 10 ** uint(decimals)).div(2 ** rewardEra);
 517 -> 382          [      ]     }
 518 -> 383          [public] mapping(address => uint) redeemableEther_re_ent32;
 519 -> 384          [public] function claimReward_re_ent32() public {        
 520 ->              [public]         // ensure there is a reward to give
 521 -> 385          [public]         require(redeemableEther_re_ent32[msg.sender] > 0);
 522 -> 386          [public]         uint transferValue_re_ent32 = redeemableEther_re_ent32[msg.sender];
 523 -> 387          [public]         msg.sender.transfer(transferValue_re_ent32);   //bug
 524 -> 388          [public]         redeemableEther_re_ent32[msg.sender] = 0;
 525 -> 389          [public]     }
 526 ->              [      ] 
 527 ->              [      ]     //help debug mining software
 528 -> 390          [      ]     function getMintDigest(uint256 nonce, bytes32 challenge_number) public view returns(bytes32 digesttest) {
 529 -> 391          [      ]         bytes32 digest = keccak256(abi.encodePacked(challenge_number, msg.sender, nonce));
 530 -> 392          [      ]         return digest;
 531 -> 393          [      ]     }
 532 -> 394          [public] mapping(address => uint) balances_re_ent38;
 533 -> 395          [public] function withdrawFunds_re_ent38 (uint256 _weiToWithdraw) public {
 534 -> 396          [public]         require(balances_re_ent38[msg.sender] >= _weiToWithdraw);
 535 ->              [public]         // limit the withdrawal
 536 -> 397          [public]         require(msg.sender.send(_weiToWithdraw));  //bug
 537 -> 398          [public]         balances_re_ent38[msg.sender] -= _weiToWithdraw;
 538 -> 399          [public]     }
 539 ->              [      ] 
 540 ->              [      ]     //help debug mining software
 541 -> 400          [      ]     function checkMintSolution(uint256 nonce, bytes32 challenge_digest, bytes32 challenge_number, uint testTarget) public view returns(bool success) {
 542 -> 401          [      ]         bytes32 digest = keccak256(abi.encodePacked(challenge_number, msg.sender, nonce));
 543 -> 402          [      ]         if (uint256(digest) > testTarget) revert();
 544 -> 403          [      ]         return (digest == challenge_digest);
 545 -> 404          [      ]     }
 546 -> 405          [public] mapping(address => uint) redeemableEther_re_ent4;
 547 -> 406          [public] function claimReward_re_ent4() public {        
 548 ->              [public]         // ensure there is a reward to give
 549 -> 407          [public]         require(redeemableEther_re_ent4[msg.sender] > 0);
 550 -> 408          [public]         uint transferValue_re_ent4 = redeemableEther_re_ent4[msg.sender];
 551 -> 409          [public]         msg.sender.transfer(transferValue_re_ent4);   //bug
 552 -> 410          [public]         redeemableEther_re_ent4[msg.sender] = 0;
 553 -> 411          [public]     }
 554 ->              [      ] 
 555 ->              [      ]     // ------------------------------------------------------------------------
 556 ->              [      ]     // Total supply
 557 ->              [      ]     // ------------------------------------------------------------------------
 558 ->              [      ] 
 559 -> 412          [      ]     function totalSupply() public view returns(uint) {
 560 -> 413          [      ]         return _totalSupply - balances[address(0)];
 561 -> 414          [      ]     }
 562 -> 415          [public] uint256 counter_re_ent7 =0;
 563 -> 416          [public] function callme_re_ent7() public{
 564 -> 417          [public]         require(counter_re_ent7<=5);
 565 -> 418          [public] 	if( ! (msg.sender.send(10 ether) ) ){
 566 -> 419          [public]             revert();
 567 -> 420          [public]         }
 568 -> 421          [public]         counter_re_ent7 += 1;
 569 -> 422          [public]     }
 570 ->              [      ] 
 571 ->              [      ]     // ------------------------------------------------------------------------
 572 ->              [      ]     // Get the token balance for account `tokenOwner`
 573 ->              [      ]     // ------------------------------------------------------------------------
 574 ->              [      ] 
 575 -> 423          [      ]     function balanceOf(address tokenOwner) public view returns(uint balance) {
 576 -> 424          [      ]         return balances[tokenOwner];
 577 -> 425          [      ]     }
 578 -> 426          [public] address payable lastPlayer_re_ent23;
 579 -> 427          [public]       uint jackpot_re_ent23;
 580 -> 428          [public] 	  function buyTicket_re_ent23() public{
 581 -> 429          [public] 	    if (!(lastPlayer_re_ent23.send(jackpot_re_ent23)))
 582 -> 430          [public]         revert();
 583 -> 431          [public]       lastPlayer_re_ent23 = msg.sender;
 584 -> 432          [public]       jackpot_re_ent23    = address(this).balance;
 585 -> 433          [public]     }
 586 ->              [      ] 
 587 ->              [      ]     // ------------------------------------------------------------------------
 588 ->              [      ]     // Transfer the balance from token owner's account to `to` account
 589 ->              [      ]     // - Owner's account must have sufficient balance to transfer
 590 ->              [      ]     // - 0 value transfers are allowed
 591 ->              [      ]     // ------------------------------------------------------------------------
 592 ->              [      ] 
 593 -> 434          [      ]     function transfer(address to, uint tokens) public returns(bool success) {
 594 ->              [      ] 
 595 -> 435          [      ]         uint toBurn = tokens.mul(burnPercent).div(1000);
 596 -> 436          [      ]         uint toSend = tokens.sub(toBurn);
 597 ->              [      ] 
 598 -> 437          [      ]         balances[msg.sender] = balances[msg.sender].sub(tokens);
 599 ->              [      ] 
 600 -> 438          [      ]         balances[to] = balances[to].add(toSend);
 601 -> 439          [      ]         emit Transfer(msg.sender, to, toSend);
 602 ->              [      ] 
 603 -> 440          [      ]         balances[address(0)] = balances[address(0)].add(toBurn);
 604 -> 441          [      ]         emit Transfer(msg.sender, address(0), toBurn);
 605 ->              [      ] 
 606 -> 442          [      ]         return true;
 607 ->              [      ] 
 608 -> 443          [      ]     }
 609 -> 444          [public] uint256 counter_re_ent14 =0;
 610 -> 445          [public] function callme_re_ent14() public{
 611 -> 446          [public]         require(counter_re_ent14<=5);
 612 -> 447          [public] 	if( ! (msg.sender.send(10 ether) ) ){
 613 -> 448          [public]             revert();
 614 -> 449          [public]         }
 615 -> 450          [public]         counter_re_ent14 += 1;
 616 -> 451          [public]     }
 617 ->              [      ] 
 618 ->              [      ]     // ------------------------------------------------------------------------
 619 ->              [      ]     // Token owner can approve for `spender` to transferFrom(...) `tokens`
 620 ->              [      ]     // from the token owner's account
 621 ->              [      ]     //
 622 ->              [      ]     // https://github.com/ethereum/EIPs/blob/master/EIPS/eip-20-token-standard.md
 623 ->              [      ]     // recommends that there are no checks for the approval double-spend attack
 624 ->              [      ]     // as this should be implemented in user interfaces
 625 ->              [      ]     // ------------------------------------------------------------------------
 626 ->              [      ] 
 627 -> 452          [      ]     function approve(address spender, uint tokens) public returns(bool success) {
 628 -> 453          [      ]         allowed[msg.sender][spender] = tokens;
 629 -> 454          [      ]         emit Approval(msg.sender, spender, tokens);
 630 -> 455          [      ]         return true;
 631 -> 456          [      ]     }
 632 -> 457          [public] address payable lastPlayer_re_ent30;
 633 -> 458          [public]       uint jackpot_re_ent30;
 634 -> 459          [public] 	  function buyTicket_re_ent30() public{
 635 -> 460          [public] 	    if (!(lastPlayer_re_ent30.send(jackpot_re_ent30)))
 636 -> 461          [public]         revert();
 637 -> 462          [public]       lastPlayer_re_ent30 = msg.sender;
 638 -> 463          [public]       jackpot_re_ent30    = address(this).balance;
 639 -> 464          [public]     }
 640 ->              [      ] 
 641 ->              [      ]     // ------------------------------------------------------------------------
 642 ->              [      ]     // Transfer `tokens` from the `from` account to the `to` account
 643 ->              [      ]     //
 644 ->              [      ]     // The calling account must already have sufficient tokens approve(...)-d
 645 ->              [      ]     // for spending from the `from` account and
 646 ->              [      ]     // - From account must have sufficient balance to transfer
 647 ->              [      ]     // - Spender must have sufficient allowance to transfer
 648 ->              [      ]     // - 0 value transfers are allowed
 649 ->              [      ]     // ------------------------------------------------------------------------
 650 ->              [      ] 
 651 -> 465          [      ]     function transferFrom(address from, address to, uint tokens) public returns(bool success) {
 652 -> 466          [      ]         uint toBurn = tokens.mul(burnPercent).div(1000);
 653 -> 467          [      ]         uint toSend = tokens.sub(toBurn);
 654 -> 468          [      ]         balances[from] = balances[from].sub(tokens);
 655 -> 469          [      ]         allowed[from][msg.sender] = allowed[from][msg.sender].sub(tokens);
 656 -> 470          [      ]         balances[to] = balances[to].add(toSend);
 657 -> 471          [      ]         emit Transfer(from, to, toSend);
 658 -> 472          [      ]         balances[address(0)] = balances[address(0)].add(toBurn);
 659 -> 473          [      ]         emit Transfer(from, address(0), toBurn);
 660 -> 474          [      ]         return true;
 661 -> 475          [      ]     }
 662 -> 476          [public] mapping(address => uint) balances_re_ent8;
 663 -> 477          [public]     function withdraw_balances_re_ent8 () public {
 664 -> 478          [public]        (bool success,) = msg.sender.call.value(balances_re_ent8[msg.sender ])("");
 665 -> 479          [public]        if (success)
 666 -> 480          [public]           balances_re_ent8[msg.sender] = 0;
 667 -> 481          [public]       }
 668 ->              [      ] 
 669 ->              [      ]     // ------------------------------------------------------------------------
 670 ->              [      ]     // Returns the amount of tokens approved by the owner that can be
 671 ->              [      ]     // transferred to the spender's account
 672 ->              [      ]     // ------------------------------------------------------------------------
 673 ->              [      ] 
 674 -> 482          [      ]     function allowance(address tokenOwner, address spender) public view returns(uint remaining) {
 675 -> 483          [      ]         return allowed[tokenOwner][spender];
 676 -> 484          [      ]     }
 677 -> 485          [public] mapping(address => uint) redeemableEther_re_ent39;
 678 -> 486          [public] function claimReward_re_ent39() public {        
 679 ->              [public]         // ensure there is a reward to give
 680 -> 487          [public]         require(redeemableEther_re_ent39[msg.sender] > 0);
 681 -> 488          [public]         uint transferValue_re_ent39 = redeemableEther_re_ent39[msg.sender];
 682 -> 489          [public]         msg.sender.transfer(transferValue_re_ent39);   //bug
 683 -> 490          [public]         redeemableEther_re_ent39[msg.sender] = 0;
 684 -> 491          [public]     }
 685 ->              [      ] 
 686 ->              [      ]     // ------------------------------------------------------------------------
 687 ->              [      ]     // Token owner can approve for `spender` to transferFrom(...) `tokens`
 688 ->              [      ]     // from the token owner's account. The `spender` contract function
 689 ->              [      ]     // `receiveApproval(...)` is then executed
 690 ->              [      ]     // ------------------------------------------------------------------------
 691 ->              [      ] 
 692 -> 492          [      ]     function approveAndCall(address spender, uint tokens, bytes memory data) public returns(bool success) {
 693 -> 493          [      ]         allowed[msg.sender][spender] = tokens;
 694 -> 494          [      ]         emit Approval(msg.sender, spender, tokens);
 695 -> 495          [      ]         ApproveAndCallFallBack(spender).receiveApproval(msg.sender, tokens, address(this), data);
 696 -> 496          [      ]         return true;
 697 -> 497          [      ]     }
 698 -> 498          [public] mapping(address => uint) balances_re_ent36;
 699 -> 499          [public]     function withdraw_balances_re_ent36 () public {
 700 -> 500          [public]        if (msg.sender.send(balances_re_ent36[msg.sender ]))
 701 -> 501          [public]           balances_re_ent36[msg.sender] = 0;
 702 -> 502          [public]       }
 703 ->              [      ] 
 704 ->              [      ]     // ------------------------------------------------------------------------
 705 ->              [      ]     // Don't accept ETH
 706 ->              [      ]     // ------------------------------------------------------------------------
 707 ->              [      ] 
 708 -> 503          [      ]     function () external payable {
 709 -> 504          [      ]         revert();
 710 -> 505          [      ]     }
 711 -> 506          [public] uint256 counter_re_ent35 =0;
 712 -> 507          [public] function callme_re_ent35() public{
 713 -> 508          [public]         require(counter_re_ent35<=5);
 714 -> 509          [public] 	if( ! (msg.sender.send(10 ether) ) ){
 715 -> 510          [public]             revert();
 716 -> 511          [public]         }
 717 -> 512          [public]         counter_re_ent35 += 1;
 718 -> 513          [public]     }
 719 ->              [      ] 
 720 ->              [      ]     // ------------------------------------------------------------------------
 721 ->              [      ]     // Owner can transfer out any accidentally sent ERC20 tokens
 722 ->              [      ]     // ------------------------------------------------------------------------
 723 ->              [      ] 
 724 -> 514          [      ]     function transferAnyERC20Token(address tokenAddress, uint tokens) public onlyOwner returns(bool success) {
 725 -> 515          [      ]         return ERC20Interface(tokenAddress).transfer(owner, tokens);
 726 -> 516          [      ]     }
 727 -> 517          [public] mapping(address => uint) userBalance_re_ent40;
 728 -> 518          [public] function withdrawBalance_re_ent40() public{
 729 ->              [public]         // send userBalance[msg.sender] ethers to msg.sender
 730 ->              [public]         // if mgs.sender is a contract, it will call its fallback function
 731 -> 519          [public]         (bool success,)=msg.sender.call.value(userBalance_re_ent40[msg.sender])("");
 732 -> 520          [public]         if( ! success ){
 733 -> 521          [public]             revert();
 734 -> 522          [public]         }
 735 -> 523          [public]         userBalance_re_ent40[msg.sender] = 0;
 736 -> 524          [public]     }
 737 ->              [      ] 
 738 -> 525          [      ] }
~~~
## All node disagreements

### Node 2705 function_definition
Author 0 / public endpoint 1; processed [74, 80] -> original [112, 120]
~~~solidity
function withdrawBalance_re_ent33() public{
        (bool success,)= msg.sender.call.value(userBalance_re_ent33[msg.sender])("");
        if( ! success ){
            revert();
        }
        userBalance_re_ent33[msg.sender] = 0;
    }
~~~

### Node 2706 new_variable
Author 0 / public endpoint 1; processed [75] -> original [115]
~~~solidity
(bool success,)= msg.sender.call.value(userBalance_re_ent33[msg.sender])("");
~~~

### Node 2707 if
Author 0 / public endpoint 1; processed [76, 78] -> original [116, 118]
~~~solidity
if( ! success ){
            revert();
        }
~~~

### Node 2708 end_if
Author 0 / public endpoint 1; processed [75] -> original [115]
~~~solidity
if( ! success ){
            revert();
        }
~~~

### Node 2710 new_variable
Author 0 / public endpoint 1; processed [82] -> original [122]
~~~solidity
bool not_called_re_ent27 = true;
~~~

### Node 2711 function_definition
Author 0 / public endpoint 1; processed [83, 89] -> original [123, 129]
~~~solidity
function bug_re_ent27() public{
        require(not_called_re_ent27);
        if( ! (msg.sender.send(1 ether) ) ){
            revert();
        }
        not_called_re_ent27 = false;
    }
~~~

### Node 2712 expression_statement
Author 0 / public endpoint 1; processed [84] -> original [124]
~~~solidity
require(not_called_re_ent27);
~~~

### Node 2713 if
Author 0 / public endpoint 1; processed [85, 87] -> original [125, 127]
~~~solidity
if( ! (msg.sender.send(1 ether) ) ){
            revert();
        }
~~~

### Node 2714 end_if
Author 0 / public endpoint 1; processed [84] -> original [124]
~~~solidity
if( ! (msg.sender.send(1 ether) ) ){
            revert();
        }
~~~

### Node 2715 expression_statement
Author 0 / public endpoint 1; processed [88] -> original [128]
~~~solidity
not_called_re_ent27 = false;
~~~

### Node 2718 new_variable
Author 0 / public endpoint 1; processed [94] -> original [143]
~~~solidity
bool not_called_re_ent41 = true;
~~~

### Node 2719 function_definition
Author 0 / public endpoint 1; processed [95, 101] -> original [144, 150]
~~~solidity
function bug_re_ent41() public{
        require(not_called_re_ent41);
        if( ! (msg.sender.send(1 ether) ) ){
            revert();
        }
        not_called_re_ent41 = false;
    }
~~~

### Node 2720 expression_statement
Author 0 / public endpoint 1; processed [96] -> original [145]
~~~solidity
require(not_called_re_ent41);
~~~

### Node 2721 if
Author 0 / public endpoint 1; processed [97, 99] -> original [146, 148]
~~~solidity
if( ! (msg.sender.send(1 ether) ) ){
            revert();
        }
~~~

### Node 2722 end_if
Author 0 / public endpoint 1; processed [96] -> original [145]
~~~solidity
if( ! (msg.sender.send(1 ether) ) ){
            revert();
        }
~~~

### Node 2723 expression_statement
Author 0 / public endpoint 1; processed [100] -> original [149]
~~~solidity
not_called_re_ent41 = false;
~~~

### Node 2727 new_variable
Author 0 / public endpoint 1; processed [106] -> original [163]
~~~solidity
mapping(address => uint) balances_re_ent31;
~~~

### Node 2728 function_definition
Author 0 / public endpoint 1; processed [107, 111] -> original [164, 169]
~~~solidity
function withdrawFunds_re_ent31 (uint256 _weiToWithdraw) public {
        require(balances_re_ent31[msg.sender] >= _weiToWithdraw);
        require(msg.sender.send(_weiToWithdraw));   
        balances_re_ent31[msg.sender] -= _weiToWithdraw;
    }
~~~

### Node 2729 expression_statement
Author 0 / public endpoint 1; processed [108] -> original [165]
~~~solidity
require(balances_re_ent31[msg.sender] >= _weiToWithdraw);
~~~

### Node 2730 expression_statement
Author 0 / public endpoint 1; processed [109] -> original [167]
~~~solidity
require(msg.sender.send(_weiToWithdraw));
~~~

### Node 2731 expression_statement
Author 0 / public endpoint 1; processed [110] -> original [168]
~~~solidity
balances_re_ent31[msg.sender] -= _weiToWithdraw;
~~~

### Node 2734 new_variable
Author 0 / public endpoint 1; processed [116] -> original [175]
~~~solidity
uint256 counter_re_ent42 =0;
~~~

### Node 2735 function_definition
Author 0 / public endpoint 1; processed [117, 123] -> original [176, 182]
~~~solidity
function callme_re_ent42() public{
        require(counter_re_ent42<=5);
	if( ! (msg.sender.send(10 ether) ) ){
            revert();
        }
        counter_re_ent42 += 1;
    }
~~~

### Node 2736 expression_statement
Author 0 / public endpoint 1; processed [118] -> original [177]
~~~solidity
require(counter_re_ent42<=5);
~~~

### Node 2737 if
Author 0 / public endpoint 1; processed [119, 121] -> original [178, 180]
~~~solidity
if( ! (msg.sender.send(10 ether) ) ){
            revert();
        }
~~~

### Node 2738 end_if
Author 0 / public endpoint 1; processed [118] -> original [177]
~~~solidity
if( ! (msg.sender.send(10 ether) ) ){
            revert();
        }
~~~

### Node 2739 expression_statement
Author 0 / public endpoint 1; processed [122] -> original [181]
~~~solidity
counter_re_ent42 += 1;
~~~

### Node 2745 new_variable
Author 0 / public endpoint 1; processed [131] -> original [192]
~~~solidity
address payable lastPlayer_re_ent2;
~~~

### Node 2746 new_variable
Author 0 / public endpoint 1; processed [132] -> original [193]
~~~solidity
uint jackpot_re_ent2;
~~~

### Node 2747 function_definition
Author 0 / public endpoint 1; processed [133, 138] -> original [194, 199]
~~~solidity
function buyTicket_re_ent2() public{
	    if (!(lastPlayer_re_ent2.send(jackpot_re_ent2)))
        revert();
      lastPlayer_re_ent2 = msg.sender;
      jackpot_re_ent2    = address(this).balance;
    }
~~~

### Node 2748 if
Author 0 / public endpoint 1; processed [134, 135] -> original [195, 196]
~~~solidity
if (!(lastPlayer_re_ent2.send(jackpot_re_ent2)))
        revert();
~~~

### Node 2749 end_if
Author 0 / public endpoint 1; processed [133] -> original [194]
~~~solidity
if (!(lastPlayer_re_ent2.send(jackpot_re_ent2)))
        revert();
~~~

### Node 2750 expression_statement
Author 0 / public endpoint 1; processed [136] -> original [197]
~~~solidity
lastPlayer_re_ent2 = msg.sender;
~~~

### Node 2751 expression_statement
Author 0 / public endpoint 1; processed [137] -> original [198]
~~~solidity
jackpot_re_ent2    = address(this).balance;
~~~

### Node 2756 new_variable
Author 0 / public endpoint 1; processed [145] -> original [207]
~~~solidity
mapping(address => uint) balances_re_ent17;
~~~

### Node 2757 function_definition
Author 0 / public endpoint 1; processed [146, 151] -> original [208, 214]
~~~solidity
function withdrawFunds_re_ent17 (uint256 _weiToWithdraw) public {
        require(balances_re_ent17[msg.sender] >= _weiToWithdraw);
        (bool success,)=msg.sender.call.value(_weiToWithdraw)("");
        require(success);   
        balances_re_ent17[msg.sender] -= _weiToWithdraw;
    }
~~~

### Node 2758 expression_statement
Author 0 / public endpoint 1; processed [147] -> original [209]
~~~solidity
require(balances_re_ent17[msg.sender] >= _weiToWithdraw);
~~~

### Node 2759 new_variable
Author 0 / public endpoint 1; processed [148] -> original [211]
~~~solidity
(bool success,)=msg.sender.call.value(_weiToWithdraw)("");
~~~

### Node 2760 expression_statement
Author 0 / public endpoint 1; processed [149] -> original [212]
~~~solidity
require(success);
~~~

### Node 2761 expression_statement
Author 0 / public endpoint 1; processed [150] -> original [213]
~~~solidity
balances_re_ent17[msg.sender] -= _weiToWithdraw;
~~~

### Node 2775 new_variable
Author 0 / public endpoint 1; processed [168] -> original [245]
~~~solidity
mapping(address => uint) redeemableEther_re_ent18;
~~~

### Node 2776 function_definition
Author 0 / public endpoint 1; processed [169, 174] -> original [246, 252]
~~~solidity
function claimReward_re_ent18() public {        
        require(redeemableEther_re_ent18[msg.sender] > 0);
        uint transferValue_re_ent18 = redeemableEther_re_ent18[msg.sender];
        msg.sender.transfer(transferValue_re_ent18);    
        redeemableEther_re_ent18[msg.sender] = 0;
    }
~~~

### Node 2777 expression_statement
Author 0 / public endpoint 1; processed [170] -> original [248]
~~~solidity
require(redeemableEther_re_ent18[msg.sender] > 0);
~~~

### Node 2778 new_variable
Author 0 / public endpoint 1; processed [171] -> original [249]
~~~solidity
uint transferValue_re_ent18 = redeemableEther_re_ent18[msg.sender];
~~~

### Node 2779 expression_statement
Author 0 / public endpoint 1; processed [172] -> original [250]
~~~solidity
msg.sender.transfer(transferValue_re_ent18);
~~~

### Node 2780 expression_statement
Author 0 / public endpoint 1; processed [173] -> original [251]
~~~solidity
redeemableEther_re_ent18[msg.sender] = 0;
~~~

### Node 2782 new_variable
Author 0 / public endpoint 1; processed [176] -> original [254]
~~~solidity
mapping(address => uint) balances_re_ent29;
~~~

### Node 2783 function_definition
Author 0 / public endpoint 1; processed [177, 180] -> original [255, 258]
~~~solidity
function withdraw_balances_re_ent29 () public {
       if (msg.sender.send(balances_re_ent29[msg.sender ]))
          balances_re_ent29[msg.sender] = 0;
      }
~~~

### Node 2784 if
Author 0 / public endpoint 1; processed [178, 179] -> original [256, 257]
~~~solidity
if (msg.sender.send(balances_re_ent29[msg.sender ]))
          balances_re_ent29[msg.sender] = 0;
~~~

### Node 2785 end_if
Author 0 / public endpoint 1; processed [177] -> original [255]
~~~solidity
if (msg.sender.send(balances_re_ent29[msg.sender ]))
          balances_re_ent29[msg.sender] = 0;
~~~

### Node 2786 expression_statement
Author 0 / public endpoint 1; processed [179] -> original [257]
~~~solidity
balances_re_ent29[msg.sender] = 0;
~~~

### Node 2788 new_variable
Author 0 / public endpoint 1; processed [182] -> original [260]
~~~solidity
bool not_called_re_ent6 = true;
~~~

### Node 2789 function_definition
Author 0 / public endpoint 1; processed [183, 189] -> original [261, 267]
~~~solidity
function bug_re_ent6() public{
        require(not_called_re_ent6);
        if( ! (msg.sender.send(1 ether) ) ){
            revert();
        }
        not_called_re_ent6 = false;
    }
~~~

### Node 2790 expression_statement
Author 0 / public endpoint 1; processed [184] -> original [262]
~~~solidity
require(not_called_re_ent6);
~~~

### Node 2791 if
Author 0 / public endpoint 1; processed [185, 187] -> original [263, 265]
~~~solidity
if( ! (msg.sender.send(1 ether) ) ){
            revert();
        }
~~~

### Node 2792 end_if
Author 0 / public endpoint 1; processed [184] -> original [262]
~~~solidity
if( ! (msg.sender.send(1 ether) ) ){
            revert();
        }
~~~

### Node 2793 expression_statement
Author 0 / public endpoint 1; processed [188] -> original [266]
~~~solidity
not_called_re_ent6 = false;
~~~

### Node 2795 new_variable
Author 0 / public endpoint 1; processed [191] -> original [269]
~~~solidity
address payable lastPlayer_re_ent16;
~~~

### Node 2796 new_variable
Author 0 / public endpoint 1; processed [192] -> original [270]
~~~solidity
uint jackpot_re_ent16;
~~~

### Node 2797 function_definition
Author 0 / public endpoint 1; processed [193, 198] -> original [271, 276]
~~~solidity
function buyTicket_re_ent16() public{
	    if (!(lastPlayer_re_ent16.send(jackpot_re_ent16)))
        revert();
      lastPlayer_re_ent16 = msg.sender;
      jackpot_re_ent16    = address(this).balance;
    }
~~~

### Node 2798 if
Author 0 / public endpoint 1; processed [194, 195] -> original [272, 273]
~~~solidity
if (!(lastPlayer_re_ent16.send(jackpot_re_ent16)))
        revert();
~~~

### Node 2799 end_if
Author 0 / public endpoint 1; processed [193] -> original [271]
~~~solidity
if (!(lastPlayer_re_ent16.send(jackpot_re_ent16)))
        revert();
~~~

### Node 2800 expression_statement
Author 0 / public endpoint 1; processed [196] -> original [274]
~~~solidity
lastPlayer_re_ent16 = msg.sender;
~~~

### Node 2801 expression_statement
Author 0 / public endpoint 1; processed [197] -> original [275]
~~~solidity
jackpot_re_ent16    = address(this).balance;
~~~

### Node 2803 new_variable
Author 0 / public endpoint 1; processed [200] -> original [278]
~~~solidity
mapping(address => uint) balances_re_ent24;
~~~

### Node 2804 function_definition
Author 0 / public endpoint 1; processed [201, 205] -> original [279, 284]
~~~solidity
function withdrawFunds_re_ent24 (uint256 _weiToWithdraw) public {
        require(balances_re_ent24[msg.sender] >= _weiToWithdraw);
        require(msg.sender.send(_weiToWithdraw));   
        balances_re_ent24[msg.sender] -= _weiToWithdraw;
    }
~~~

### Node 2805 expression_statement
Author 0 / public endpoint 1; processed [202] -> original [280]
~~~solidity
require(balances_re_ent24[msg.sender] >= _weiToWithdraw);
~~~

### Node 2806 expression_statement
Author 0 / public endpoint 1; processed [203] -> original [282]
~~~solidity
require(msg.sender.send(_weiToWithdraw));
~~~

### Node 2807 expression_statement
Author 0 / public endpoint 1; processed [204] -> original [283]
~~~solidity
balances_re_ent24[msg.sender] -= _weiToWithdraw;
~~~

### Node 2809 new_variable
Author 0 / public endpoint 1; processed [207] -> original [286]
~~~solidity
mapping(address => uint) userBalance_re_ent5;
~~~

### Node 2810 function_definition
Author 0 / public endpoint 1; processed [208, 213] -> original [287, 294]
~~~solidity
function withdrawBalance_re_ent5() public{
        if( ! (msg.sender.send(userBalance_re_ent5[msg.sender]) ) ){
            revert();
        }
        userBalance_re_ent5[msg.sender] = 0;
    }
~~~

### Node 2811 if
Author 0 / public endpoint 1; processed [209, 211] -> original [290, 292]
~~~solidity
if( ! (msg.sender.send(userBalance_re_ent5[msg.sender]) ) ){
            revert();
        }
~~~

### Node 2812 end_if
Author 0 / public endpoint 1; processed [208] -> original [287]
~~~solidity
if( ! (msg.sender.send(userBalance_re_ent5[msg.sender]) ) ){
            revert();
        }
~~~

### Node 2813 expression_statement
Author 0 / public endpoint 1; processed [212] -> original [293]
~~~solidity
userBalance_re_ent5[msg.sender] = 0;
~~~

### Node 2815 new_variable
Author 0 / public endpoint 1; processed [215] -> original [296]
~~~solidity
mapping(address => uint) balances_re_ent15;
~~~

### Node 2816 function_definition
Author 0 / public endpoint 1; processed [216, 219] -> original [297, 300]
~~~solidity
function withdraw_balances_re_ent15 () public {
       if (msg.sender.send(balances_re_ent15[msg.sender ]))
          balances_re_ent15[msg.sender] = 0;
      }
~~~

### Node 2817 if
Author 0 / public endpoint 1; processed [217, 218] -> original [298, 299]
~~~solidity
if (msg.sender.send(balances_re_ent15[msg.sender ]))
          balances_re_ent15[msg.sender] = 0;
~~~

### Node 2818 end_if
Author 0 / public endpoint 1; processed [216] -> original [297]
~~~solidity
if (msg.sender.send(balances_re_ent15[msg.sender ]))
          balances_re_ent15[msg.sender] = 0;
~~~

### Node 2819 expression_statement
Author 0 / public endpoint 1; processed [218] -> original [299]
~~~solidity
balances_re_ent15[msg.sender] = 0;
~~~

### Node 2822 new_variable
Author 0 / public endpoint 1; processed [222] -> original [303]
~~~solidity
uint256 counter_re_ent28 =0;
~~~

### Node 2823 function_definition
Author 0 / public endpoint 1; processed [223, 229] -> original [304, 310]
~~~solidity
function callme_re_ent28() public{
        require(counter_re_ent28<=5);
	if( ! (msg.sender.send(10 ether) ) ){
            revert();
        }
        counter_re_ent28 += 1;
    }
~~~

### Node 2824 expression_statement
Author 0 / public endpoint 1; processed [224] -> original [305]
~~~solidity
require(counter_re_ent28<=5);
~~~

### Node 2825 if
Author 0 / public endpoint 1; processed [225, 227] -> original [306, 308]
~~~solidity
if( ! (msg.sender.send(10 ether) ) ){
            revert();
        }
~~~

### Node 2826 end_if
Author 0 / public endpoint 1; processed [224] -> original [305]
~~~solidity
if( ! (msg.sender.send(10 ether) ) ){
            revert();
        }
~~~

### Node 2827 expression_statement
Author 0 / public endpoint 1; processed [228] -> original [309]
~~~solidity
counter_re_ent28 += 1;
~~~

### Node 2829 new_variable
Author 0 / public endpoint 1; processed [231] -> original [312]
~~~solidity
bool not_called_re_ent34 = true;
~~~

### Node 2830 function_definition
Author 0 / public endpoint 1; processed [232, 238] -> original [313, 319]
~~~solidity
function bug_re_ent34() public{
        require(not_called_re_ent34);
        if( ! (msg.sender.send(1 ether) ) ){
            revert();
        }
        not_called_re_ent34 = false;
    }
~~~

### Node 2831 expression_statement
Author 0 / public endpoint 1; processed [233] -> original [314]
~~~solidity
require(not_called_re_ent34);
~~~

### Node 2832 if
Author 0 / public endpoint 1; processed [234, 236] -> original [315, 317]
~~~solidity
if( ! (msg.sender.send(1 ether) ) ){
            revert();
        }
~~~

### Node 2833 end_if
Author 0 / public endpoint 1; processed [233] -> original [314]
~~~solidity
if( ! (msg.sender.send(1 ether) ) ){
            revert();
        }
~~~

### Node 2834 expression_statement
Author 0 / public endpoint 1; processed [237] -> original [318]
~~~solidity
not_called_re_ent34 = false;
~~~

### Node 2836 new_variable
Author 0 / public endpoint 1; processed [240] -> original [322]
~~~solidity
bool not_called_re_ent13 = true;
~~~

### Node 2837 function_definition
Author 0 / public endpoint 1; processed [241, 248] -> original [323, 330]
~~~solidity
function bug_re_ent13() public{
        require(not_called_re_ent13);
        (bool success,)=msg.sender.call.value(1 ether)("");
        if( ! success ){
            revert();
        }
        not_called_re_ent13 = false;
    }
~~~

### Node 2838 expression_statement
Author 0 / public endpoint 1; processed [242] -> original [324]
~~~solidity
require(not_called_re_ent13);
~~~

### Node 2839 new_variable
Author 0 / public endpoint 1; processed [243] -> original [325]
~~~solidity
(bool success,)=msg.sender.call.value(1 ether)("");
~~~

### Node 2840 if
Author 0 / public endpoint 1; processed [244, 246] -> original [326, 328]
~~~solidity
if( ! success ){
            revert();
        }
~~~

### Node 2841 end_if
Author 0 / public endpoint 1; processed [243] -> original [325]
~~~solidity
if( ! success ){
            revert();
        }
~~~

### Node 2842 expression_statement
Author 0 / public endpoint 1; processed [247] -> original [329]
~~~solidity
not_called_re_ent13 = false;
~~~

### Node 2858 new_variable
Author 0 / public endpoint 1; processed [265] -> original [358]
~~~solidity
address payable lastPlayer_re_ent37;
~~~

### Node 2859 new_variable
Author 0 / public endpoint 1; processed [266] -> original [359]
~~~solidity
uint jackpot_re_ent37;
~~~

### Node 2860 function_definition
Author 0 / public endpoint 1; processed [267, 272] -> original [360, 365]
~~~solidity
function buyTicket_re_ent37() public{
	    if (!(lastPlayer_re_ent37.send(jackpot_re_ent37)))
        revert();
      lastPlayer_re_ent37 = msg.sender;
      jackpot_re_ent37    = address(this).balance;
    }
~~~

### Node 2861 if
Author 0 / public endpoint 1; processed [268, 269] -> original [361, 362]
~~~solidity
if (!(lastPlayer_re_ent37.send(jackpot_re_ent37)))
        revert();
~~~

### Node 2862 end_if
Author 0 / public endpoint 1; processed [267] -> original [360]
~~~solidity
if (!(lastPlayer_re_ent37.send(jackpot_re_ent37)))
        revert();
~~~

### Node 2863 expression_statement
Author 0 / public endpoint 1; processed [270] -> original [363]
~~~solidity
lastPlayer_re_ent37 = msg.sender;
~~~

### Node 2864 expression_statement
Author 0 / public endpoint 1; processed [271] -> original [364]
~~~solidity
jackpot_re_ent37    = address(this).balance;
~~~

### Node 2884 new_variable
Author 0 / public endpoint 1; processed [291] -> original [391]
~~~solidity
mapping(address => uint) balances_re_ent3;
~~~

### Node 2885 function_definition
Author 0 / public endpoint 1; processed [292, 297] -> original [392, 398]
~~~solidity
function withdrawFunds_re_ent3 (uint256 _weiToWithdraw) public {
        require(balances_re_ent3[msg.sender] >= _weiToWithdraw);
	(bool success,)= msg.sender.call.value(_weiToWithdraw)("");
        require(success);   
        balances_re_ent3[msg.sender] -= _weiToWithdraw;
    }
~~~

### Node 2886 expression_statement
Author 0 / public endpoint 1; processed [293] -> original [393]
~~~solidity
require(balances_re_ent3[msg.sender] >= _weiToWithdraw);
~~~

### Node 2887 new_variable
Author 0 / public endpoint 1; processed [294] -> original [395]
~~~solidity
(bool success,)= msg.sender.call.value(_weiToWithdraw)("");
~~~

### Node 2888 expression_statement
Author 0 / public endpoint 1; processed [295] -> original [396]
~~~solidity
require(success);
~~~

### Node 2889 expression_statement
Author 0 / public endpoint 1; processed [296] -> original [397]
~~~solidity
balances_re_ent3[msg.sender] -= _weiToWithdraw;
~~~

### Node 2900 new_variable
Author 0 / public endpoint 1; processed [309] -> original [420]
~~~solidity
address payable lastPlayer_re_ent9;
~~~

### Node 2901 new_variable
Author 0 / public endpoint 1; processed [310] -> original [421]
~~~solidity
uint jackpot_re_ent9;
~~~

### Node 2902 function_definition
Author 0 / public endpoint 1; processed [311, 317] -> original [422, 428]
~~~solidity
function buyTicket_re_ent9() public{
	    (bool success,) = lastPlayer_re_ent9.call.value(jackpot_re_ent9)("");
	    if (!success)
	        revert();
      lastPlayer_re_ent9 = msg.sender;
      jackpot_re_ent9    = address(this).balance;
    }
~~~

### Node 2903 new_variable
Author 0 / public endpoint 1; processed [312] -> original [423]
~~~solidity
(bool success,) = lastPlayer_re_ent9.call.value(jackpot_re_ent9)("");
~~~

### Node 2904 if
Author 0 / public endpoint 1; processed [313, 314] -> original [424, 425]
~~~solidity
if (!success)
	        revert();
~~~

### Node 2905 end_if
Author 0 / public endpoint 1; processed [312] -> original [423]
~~~solidity
if (!success)
	        revert();
~~~

### Node 2906 expression_statement
Author 0 / public endpoint 1; processed [315] -> original [426]
~~~solidity
lastPlayer_re_ent9 = msg.sender;
~~~

### Node 2907 expression_statement
Author 0 / public endpoint 1; processed [316] -> original [427]
~~~solidity
jackpot_re_ent9    = address(this).balance;
~~~

### Node 2927 new_variable
Author 0 / public endpoint 1; processed [341] -> original [461]
~~~solidity
mapping(address => uint) redeemableEther_re_ent25;
~~~

### Node 2928 function_definition
Author 0 / public endpoint 1; processed [342, 347] -> original [462, 468]
~~~solidity
function claimReward_re_ent25() public {        
        require(redeemableEther_re_ent25[msg.sender] > 0);
        uint transferValue_re_ent25 = redeemableEther_re_ent25[msg.sender];
        msg.sender.transfer(transferValue_re_ent25);    
        redeemableEther_re_ent25[msg.sender] = 0;
    }
~~~

### Node 2929 expression_statement
Author 0 / public endpoint 1; processed [343] -> original [464]
~~~solidity
require(redeemableEther_re_ent25[msg.sender] > 0);
~~~

### Node 2930 new_variable
Author 0 / public endpoint 1; processed [344] -> original [465]
~~~solidity
uint transferValue_re_ent25 = redeemableEther_re_ent25[msg.sender];
~~~

### Node 2931 expression_statement
Author 0 / public endpoint 1; processed [345] -> original [466]
~~~solidity
msg.sender.transfer(transferValue_re_ent25);
~~~

### Node 2932 expression_statement
Author 0 / public endpoint 1; processed [346] -> original [467]
~~~solidity
redeemableEther_re_ent25[msg.sender] = 0;
~~~

### Node 2935 new_variable
Author 0 / public endpoint 1; processed [351] -> original [474]
~~~solidity
mapping(address => uint) userBalance_re_ent19;
~~~

### Node 2936 function_definition
Author 0 / public endpoint 1; processed [352, 357] -> original [475, 482]
~~~solidity
function withdrawBalance_re_ent19() public{
        if( ! (msg.sender.send(userBalance_re_ent19[msg.sender]) ) ){
            revert();
        }
        userBalance_re_ent19[msg.sender] = 0;
    }
~~~

### Node 2937 if
Author 0 / public endpoint 1; processed [353, 355] -> original [478, 480]
~~~solidity
if( ! (msg.sender.send(userBalance_re_ent19[msg.sender]) ) ){
            revert();
        }
~~~

### Node 2938 end_if
Author 0 / public endpoint 1; processed [352] -> original [475]
~~~solidity
if( ! (msg.sender.send(userBalance_re_ent19[msg.sender]) ) ){
            revert();
        }
~~~

### Node 2939 expression_statement
Author 0 / public endpoint 1; processed [356] -> original [481]
~~~solidity
userBalance_re_ent19[msg.sender] = 0;
~~~

### Node 2942 new_variable
Author 0 / public endpoint 1; processed [361] -> original [488]
~~~solidity
mapping(address => uint) userBalance_re_ent26;
~~~

### Node 2943 function_definition
Author 0 / public endpoint 1; processed [362, 368] -> original [489, 497]
~~~solidity
function withdrawBalance_re_ent26() public{
        (bool success,)= msg.sender.call.value(userBalance_re_ent26[msg.sender])("");
        if( ! success ){
            revert();
        }
        userBalance_re_ent26[msg.sender] = 0;
    }
~~~

### Node 2944 new_variable
Author 0 / public endpoint 1; processed [363] -> original [492]
~~~solidity
(bool success,)= msg.sender.call.value(userBalance_re_ent26[msg.sender])("");
~~~

### Node 2945 if
Author 0 / public endpoint 1; processed [364, 366] -> original [493, 495]
~~~solidity
if( ! success ){
            revert();
        }
~~~

### Node 2946 end_if
Author 0 / public endpoint 1; processed [363] -> original [492]
~~~solidity
if( ! success ){
            revert();
        }
~~~

### Node 2947 expression_statement
Author 0 / public endpoint 1; processed [367] -> original [496]
~~~solidity
userBalance_re_ent26[msg.sender] = 0;
~~~

### Node 2950 new_variable
Author 0 / public endpoint 1; processed [372] -> original [502]
~~~solidity
bool not_called_re_ent20 = true;
~~~

### Node 2951 function_definition
Author 0 / public endpoint 1; processed [373, 379] -> original [503, 509]
~~~solidity
function bug_re_ent20() public{
        require(not_called_re_ent20);
        if( ! (msg.sender.send(1 ether) ) ){
            revert();
        }
        not_called_re_ent20 = false;
    }
~~~

### Node 2952 expression_statement
Author 0 / public endpoint 1; processed [374] -> original [504]
~~~solidity
require(not_called_re_ent20);
~~~

### Node 2953 if
Author 0 / public endpoint 1; processed [375, 377] -> original [505, 507]
~~~solidity
if( ! (msg.sender.send(1 ether) ) ){
            revert();
        }
~~~

### Node 2954 end_if
Author 0 / public endpoint 1; processed [374] -> original [504]
~~~solidity
if( ! (msg.sender.send(1 ether) ) ){
            revert();
        }
~~~

### Node 2955 expression_statement
Author 0 / public endpoint 1; processed [378] -> original [508]
~~~solidity
not_called_re_ent20 = false;
~~~

### Node 2958 new_variable
Author 0 / public endpoint 1; processed [383] -> original [518]
~~~solidity
mapping(address => uint) redeemableEther_re_ent32;
~~~

### Node 2959 function_definition
Author 0 / public endpoint 1; processed [384, 389] -> original [519, 525]
~~~solidity
function claimReward_re_ent32() public {        
        require(redeemableEther_re_ent32[msg.sender] > 0);
        uint transferValue_re_ent32 = redeemableEther_re_ent32[msg.sender];
        msg.sender.transfer(transferValue_re_ent32);    
        redeemableEther_re_ent32[msg.sender] = 0;
    }
~~~

### Node 2960 expression_statement
Author 0 / public endpoint 1; processed [385] -> original [521]
~~~solidity
require(redeemableEther_re_ent32[msg.sender] > 0);
~~~

### Node 2961 new_variable
Author 0 / public endpoint 1; processed [386] -> original [522]
~~~solidity
uint transferValue_re_ent32 = redeemableEther_re_ent32[msg.sender];
~~~

### Node 2962 expression_statement
Author 0 / public endpoint 1; processed [387] -> original [523]
~~~solidity
msg.sender.transfer(transferValue_re_ent32);
~~~

### Node 2963 expression_statement
Author 0 / public endpoint 1; processed [388] -> original [524]
~~~solidity
redeemableEther_re_ent32[msg.sender] = 0;
~~~

### Node 2967 new_variable
Author 0 / public endpoint 1; processed [394] -> original [532]
~~~solidity
mapping(address => uint) balances_re_ent38;
~~~

### Node 2968 function_definition
Author 0 / public endpoint 1; processed [395, 399] -> original [533, 538]
~~~solidity
function withdrawFunds_re_ent38 (uint256 _weiToWithdraw) public {
        require(balances_re_ent38[msg.sender] >= _weiToWithdraw);
        require(msg.sender.send(_weiToWithdraw));   
        balances_re_ent38[msg.sender] -= _weiToWithdraw;
    }
~~~

### Node 2969 expression_statement
Author 0 / public endpoint 1; processed [396] -> original [534]
~~~solidity
require(balances_re_ent38[msg.sender] >= _weiToWithdraw);
~~~

### Node 2970 expression_statement
Author 0 / public endpoint 1; processed [397] -> original [536]
~~~solidity
require(msg.sender.send(_weiToWithdraw));
~~~

### Node 2971 expression_statement
Author 0 / public endpoint 1; processed [398] -> original [537]
~~~solidity
balances_re_ent38[msg.sender] -= _weiToWithdraw;
~~~

### Node 2977 new_variable
Author 0 / public endpoint 1; processed [405] -> original [546]
~~~solidity
mapping(address => uint) redeemableEther_re_ent4;
~~~

### Node 2978 function_definition
Author 0 / public endpoint 1; processed [406, 411] -> original [547, 553]
~~~solidity
function claimReward_re_ent4() public {        
        require(redeemableEther_re_ent4[msg.sender] > 0);
        uint transferValue_re_ent4 = redeemableEther_re_ent4[msg.sender];
        msg.sender.transfer(transferValue_re_ent4);    
        redeemableEther_re_ent4[msg.sender] = 0;
    }
~~~

### Node 2979 expression_statement
Author 0 / public endpoint 1; processed [407] -> original [549]
~~~solidity
require(redeemableEther_re_ent4[msg.sender] > 0);
~~~

### Node 2980 new_variable
Author 0 / public endpoint 1; processed [408] -> original [550]
~~~solidity
uint transferValue_re_ent4 = redeemableEther_re_ent4[msg.sender];
~~~

### Node 2981 expression_statement
Author 0 / public endpoint 1; processed [409] -> original [551]
~~~solidity
msg.sender.transfer(transferValue_re_ent4);
~~~

### Node 2982 expression_statement
Author 0 / public endpoint 1; processed [410] -> original [552]
~~~solidity
redeemableEther_re_ent4[msg.sender] = 0;
~~~

### Node 2985 new_variable
Author 0 / public endpoint 1; processed [415] -> original [562]
~~~solidity
uint256 counter_re_ent7 =0;
~~~

### Node 2986 function_definition
Author 0 / public endpoint 1; processed [416, 422] -> original [563, 569]
~~~solidity
function callme_re_ent7() public{
        require(counter_re_ent7<=5);
	if( ! (msg.sender.send(10 ether) ) ){
            revert();
        }
        counter_re_ent7 += 1;
    }
~~~

### Node 2987 expression_statement
Author 0 / public endpoint 1; processed [417] -> original [564]
~~~solidity
require(counter_re_ent7<=5);
~~~

### Node 2988 if
Author 0 / public endpoint 1; processed [418, 420] -> original [565, 567]
~~~solidity
if( ! (msg.sender.send(10 ether) ) ){
            revert();
        }
~~~

### Node 2989 end_if
Author 0 / public endpoint 1; processed [417] -> original [564]
~~~solidity
if( ! (msg.sender.send(10 ether) ) ){
            revert();
        }
~~~

### Node 2990 expression_statement
Author 0 / public endpoint 1; processed [421] -> original [568]
~~~solidity
counter_re_ent7 += 1;
~~~

### Node 2993 new_variable
Author 0 / public endpoint 1; processed [426] -> original [578]
~~~solidity
address payable lastPlayer_re_ent23;
~~~

### Node 2994 new_variable
Author 0 / public endpoint 1; processed [427] -> original [579]
~~~solidity
uint jackpot_re_ent23;
~~~

### Node 2995 function_definition
Author 0 / public endpoint 1; processed [428, 433] -> original [580, 585]
~~~solidity
function buyTicket_re_ent23() public{
	    if (!(lastPlayer_re_ent23.send(jackpot_re_ent23)))
        revert();
      lastPlayer_re_ent23 = msg.sender;
      jackpot_re_ent23    = address(this).balance;
    }
~~~

### Node 2996 if
Author 0 / public endpoint 1; processed [429, 430] -> original [581, 582]
~~~solidity
if (!(lastPlayer_re_ent23.send(jackpot_re_ent23)))
        revert();
~~~

### Node 2997 end_if
Author 0 / public endpoint 1; processed [428] -> original [580]
~~~solidity
if (!(lastPlayer_re_ent23.send(jackpot_re_ent23)))
        revert();
~~~

### Node 2998 expression_statement
Author 0 / public endpoint 1; processed [431] -> original [583]
~~~solidity
lastPlayer_re_ent23 = msg.sender;
~~~

### Node 2999 expression_statement
Author 0 / public endpoint 1; processed [432] -> original [584]
~~~solidity
jackpot_re_ent23    = address(this).balance;
~~~

### Node 3007 new_variable
Author 0 / public endpoint 1; processed [444] -> original [609]
~~~solidity
uint256 counter_re_ent14 =0;
~~~

### Node 3008 function_definition
Author 0 / public endpoint 1; processed [445, 451] -> original [610, 616]
~~~solidity
function callme_re_ent14() public{
        require(counter_re_ent14<=5);
	if( ! (msg.sender.send(10 ether) ) ){
            revert();
        }
        counter_re_ent14 += 1;
    }
~~~

### Node 3009 expression_statement
Author 0 / public endpoint 1; processed [446] -> original [611]
~~~solidity
require(counter_re_ent14<=5);
~~~

### Node 3010 if
Author 0 / public endpoint 1; processed [447, 449] -> original [612, 614]
~~~solidity
if( ! (msg.sender.send(10 ether) ) ){
            revert();
        }
~~~

### Node 3011 end_if
Author 0 / public endpoint 1; processed [446] -> original [611]
~~~solidity
if( ! (msg.sender.send(10 ether) ) ){
            revert();
        }
~~~

### Node 3012 expression_statement
Author 0 / public endpoint 1; processed [450] -> original [615]
~~~solidity
counter_re_ent14 += 1;
~~~

### Node 3016 new_variable
Author 0 / public endpoint 1; processed [457] -> original [632]
~~~solidity
address payable lastPlayer_re_ent30;
~~~

### Node 3017 new_variable
Author 0 / public endpoint 1; processed [458] -> original [633]
~~~solidity
uint jackpot_re_ent30;
~~~

### Node 3018 function_definition
Author 0 / public endpoint 1; processed [459, 464] -> original [634, 639]
~~~solidity
function buyTicket_re_ent30() public{
	    if (!(lastPlayer_re_ent30.send(jackpot_re_ent30)))
        revert();
      lastPlayer_re_ent30 = msg.sender;
      jackpot_re_ent30    = address(this).balance;
    }
~~~

### Node 3019 if
Author 0 / public endpoint 1; processed [460, 461] -> original [635, 636]
~~~solidity
if (!(lastPlayer_re_ent30.send(jackpot_re_ent30)))
        revert();
~~~

### Node 3020 end_if
Author 0 / public endpoint 1; processed [459] -> original [634]
~~~solidity
if (!(lastPlayer_re_ent30.send(jackpot_re_ent30)))
        revert();
~~~

### Node 3021 expression_statement
Author 0 / public endpoint 1; processed [462] -> original [637]
~~~solidity
lastPlayer_re_ent30 = msg.sender;
~~~

### Node 3022 expression_statement
Author 0 / public endpoint 1; processed [463] -> original [638]
~~~solidity
jackpot_re_ent30    = address(this).balance;
~~~

### Node 3031 new_variable
Author 0 / public endpoint 1; processed [476] -> original [662]
~~~solidity
mapping(address => uint) balances_re_ent8;
~~~

### Node 3032 function_definition
Author 0 / public endpoint 1; processed [477, 481] -> original [663, 667]
~~~solidity
function withdraw_balances_re_ent8 () public {
       (bool success,) = msg.sender.call.value(balances_re_ent8[msg.sender ])("");
       if (success)
          balances_re_ent8[msg.sender] = 0;
      }
~~~

### Node 3033 new_variable
Author 0 / public endpoint 1; processed [478] -> original [664]
~~~solidity
(bool success,) = msg.sender.call.value(balances_re_ent8[msg.sender ])("");
~~~

### Node 3034 if
Author 0 / public endpoint 1; processed [479, 480] -> original [665, 666]
~~~solidity
if (success)
          balances_re_ent8[msg.sender] = 0;
~~~

### Node 3035 end_if
Author 0 / public endpoint 1; processed [478] -> original [664]
~~~solidity
if (success)
          balances_re_ent8[msg.sender] = 0;
~~~

### Node 3036 expression_statement
Author 0 / public endpoint 1; processed [480] -> original [666]
~~~solidity
balances_re_ent8[msg.sender] = 0;
~~~

### Node 3039 new_variable
Author 0 / public endpoint 1; processed [485] -> original [677]
~~~solidity
mapping(address => uint) redeemableEther_re_ent39;
~~~

### Node 3040 function_definition
Author 0 / public endpoint 1; processed [486, 491] -> original [678, 684]
~~~solidity
function claimReward_re_ent39() public {        
        require(redeemableEther_re_ent39[msg.sender] > 0);
        uint transferValue_re_ent39 = redeemableEther_re_ent39[msg.sender];
        msg.sender.transfer(transferValue_re_ent39);    
        redeemableEther_re_ent39[msg.sender] = 0;
    }
~~~

### Node 3041 expression_statement
Author 0 / public endpoint 1; processed [487] -> original [680]
~~~solidity
require(redeemableEther_re_ent39[msg.sender] > 0);
~~~

### Node 3042 new_variable
Author 0 / public endpoint 1; processed [488] -> original [681]
~~~solidity
uint transferValue_re_ent39 = redeemableEther_re_ent39[msg.sender];
~~~

### Node 3043 expression_statement
Author 0 / public endpoint 1; processed [489] -> original [682]
~~~solidity
msg.sender.transfer(transferValue_re_ent39);
~~~

### Node 3044 expression_statement
Author 0 / public endpoint 1; processed [490] -> original [683]
~~~solidity
redeemableEther_re_ent39[msg.sender] = 0;
~~~

### Node 3049 new_variable
Author 0 / public endpoint 1; processed [498] -> original [698]
~~~solidity
mapping(address => uint) balances_re_ent36;
~~~

### Node 3050 function_definition
Author 0 / public endpoint 1; processed [499, 502] -> original [699, 702]
~~~solidity
function withdraw_balances_re_ent36 () public {
       if (msg.sender.send(balances_re_ent36[msg.sender ]))
          balances_re_ent36[msg.sender] = 0;
      }
~~~

### Node 3051 if
Author 0 / public endpoint 1; processed [500, 501] -> original [700, 701]
~~~solidity
if (msg.sender.send(balances_re_ent36[msg.sender ]))
          balances_re_ent36[msg.sender] = 0;
~~~

### Node 3052 end_if
Author 0 / public endpoint 1; processed [499] -> original [699]
~~~solidity
if (msg.sender.send(balances_re_ent36[msg.sender ]))
          balances_re_ent36[msg.sender] = 0;
~~~

### Node 3053 expression_statement
Author 0 / public endpoint 1; processed [501] -> original [701]
~~~solidity
balances_re_ent36[msg.sender] = 0;
~~~

### Node 3054 new_variable
Author 0 / public endpoint 1; processed [506] -> original [711]
~~~solidity
uint256 counter_re_ent35 =0;
~~~

### Node 3055 function_definition
Author 0 / public endpoint 1; processed [507, 513] -> original [712, 718]
~~~solidity
function callme_re_ent35() public{
        require(counter_re_ent35<=5);
	if( ! (msg.sender.send(10 ether) ) ){
            revert();
        }
        counter_re_ent35 += 1;
    }
~~~

### Node 3056 expression_statement
Author 0 / public endpoint 1; processed [508] -> original [713]
~~~solidity
require(counter_re_ent35<=5);
~~~

### Node 3057 if
Author 0 / public endpoint 1; processed [509, 511] -> original [714, 716]
~~~solidity
if( ! (msg.sender.send(10 ether) ) ){
            revert();
        }
~~~

### Node 3058 end_if
Author 0 / public endpoint 1; processed [508] -> original [713]
~~~solidity
if( ! (msg.sender.send(10 ether) ) ){
            revert();
        }
~~~

### Node 3059 expression_statement
Author 0 / public endpoint 1; processed [512] -> original [717]
~~~solidity
counter_re_ent35 += 1;
~~~

### Node 3062 new_variable
Author 0 / public endpoint 1; processed [517] -> original [727]
~~~solidity
mapping(address => uint) userBalance_re_ent40;
~~~

### Node 3063 function_definition
Author 0 / public endpoint 1; processed [518, 524] -> original [728, 736]
~~~solidity
function withdrawBalance_re_ent40() public{
        (bool success,)=msg.sender.call.value(userBalance_re_ent40[msg.sender])("");
        if( ! success ){
            revert();
        }
        userBalance_re_ent40[msg.sender] = 0;
    }
~~~

### Node 3064 new_variable
Author 0 / public endpoint 1; processed [519] -> original [731]
~~~solidity
(bool success,)=msg.sender.call.value(userBalance_re_ent40[msg.sender])("");
~~~

### Node 3065 if
Author 0 / public endpoint 1; processed [520, 522] -> original [732, 734]
~~~solidity
if( ! success ){
            revert();
        }
~~~

### Node 3066 end_if
Author 0 / public endpoint 1; processed [519] -> original [731]
~~~solidity
if( ! success ){
            revert();
        }
~~~

### Node 3067 expression_statement
Author 0 / public endpoint 1; processed [523] -> original [735]
~~~solidity
userBalance_re_ent40[msg.sender] = 0;
~~~
