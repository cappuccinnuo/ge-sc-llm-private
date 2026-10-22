# access_control/parity_wallet_bug_2.sol
Source SHA: 3026bd9ff80d0a4b7d166c0d4d2aad07063d05a67e3df9267d9580933d1a529e
This is a source/label review. Model predictions were not used.

## Summary
~~~json
{
  "source": "/home/zhao/SmartContract/ge-sc-llm/data/smartbug-dataset/dataset/access_control/parity_wallet_bug_2.sol",
  "source_sha256": "3026bd9ff80d0a4b7d166c0d4d2aad07063d05a67e3df9267d9580933d1a529e",
  "source_provenance": {
    "path": "/home/zhao/SmartContract/ge-sc-llm/data/smartbug-dataset/dataset/access_control/parity_wallet_bug_2.sol",
    "sha256": "3026bd9ff80d0a4b7d166c0d4d2aad07063d05a67e3df9267d9580933d1a529e",
    "equals_git_head": true
  },
  "public_input_provenance": [],
  "source_check": {
    "local_source": "/home/zhao/SmartContract/ge-sc-llm/experiments/ge-sc-data/source_code/access_control/source_files/parity_wallet_bug_2.sol",
    "canonical_source": "/home/zhao/SmartContract/ge-sc-llm/data/smartbug-dataset/dataset/access_control/parity_wallet_bug_2.sol",
    "local_sha256": "3026bd9ff80d0a4b7d166c0d4d2aad07063d05a67e3df9267d9580933d1a529e",
    "canonical_sha256": "3026bd9ff80d0a4b7d166c0d4d2aad07063d05a67e3df9267d9580933d1a529e",
    "source_comparison": "byte_identical",
    "changed_original_line_ranges": [],
    "local_original_lines": 406,
    "canonical_original_lines": 406,
    "local_preprocessed_lines": 250,
    "canonical_preprocessed_lines": 250,
    "mapping_basis": "canonical_source_original_1based",
    "dataset": "SmartBugs",
    "contract_target": 1,
    "annotation_json": "/home/zhao/SmartContract/ge-sc-llm/data/smartbug-dataset/vulnerabilities.json",
    "annotation_lines": 2,
    "annotation_paths": [
      "dataset/access_control/parity_wallet_bug_2.sol"
    ],
    "hgt_snapshot_line_differences": [],
    "hgt_snapshot_used_as_ground_truth": false
  },
  "contract_target": 1,
  "original_lines": 406,
  "processed_lines": 250,
  "annotation_original": [
    {
      "category": "access_control",
      "lines": [
        226
      ]
    },
    {
      "category": "access_control",
      "lines": [
        233
      ]
    }
  ],
  "public_original_unique": 2,
  "public_processed_lines": [
    133,
    137
  ],
  "public_processed_unique": 2,
  "embedded_records": [],
  "embedded_all_unique": 0,
  "embedded_target_unique": 0,
  "embedded_categories": [],
  "public_only_processed": [
    133,
    137
  ],
  "author_only_processed": [],
  "out_of_bounds_all": [],
  "overlap_processed": [],
  "nodes": 237,
  "author_positive": 0,
  "public_endpoint_positive": 2,
  "public_full_span_positive": 3,
  "disagreements": 2,
  "disagreement_types": {
    "function_definition": 2
  },
  "disagreement_direction": {
    "0->1": 2
  },
  "self_endpoint_replay_mismatches": [],
  "projection_verified": {
    "ordinary_nodes_checked": 201,
    "synthetic_nodes": 36
  },
  "source_token_sequence_unchanged": true,
  "old_mapper_annotation_projection_equal": true,
  "csv_overlap_lines": []
}
~~~
## Source with raw and preprocessed coordinate correspondence
~~~text
   1 ->              [      ] /*
   2 ->              [      ]  * @source: https://smartcontractsecurity.github.io/SWC-registry/docs/SWC-106#walletlibrarysol
   3 ->              [      ]  * @author: -
   4 ->              [      ]  * @vulnerable_at_lines: 226,233
   5 ->              [      ]  */
   6 ->              [      ] 
   7 ->              [      ] //sol Wallet
   8 ->              [      ] // Multi-sig, daily-limited account proxy/wallet.
   9 ->              [      ] // @authors:
  10 ->              [      ] // Gav Wood <g@ethdev.com>
  11 ->              [      ] // inheritable "property" contract that enables methods to be protected by requiring the acquiescence of either a
  12 ->              [      ] // single, or, crucially, each of a number of, designated owners.
  13 ->              [      ] // usage:
  14 ->              [      ] // use modifiers onlyowner (just own owned) or onlymanyowners(hash), whereby the same hash must be provided by
  15 ->              [      ] // some number (specified in constructor) of the set of owners (specified in the constructor, modifiable) before the
  16 ->              [      ] // interior is executed.
  17 ->              [      ] 
  18 -> 1            [      ] pragma solidity ^0.4.9;
  19 ->              [      ] 
  20 -> 2            [      ] contract WalletEvents {
  21 ->              [      ]   // EVENTS
  22 ->              [      ] 
  23 ->              [      ]   // this contract only has six types of events: it can accept a confirmation, in which case
  24 ->              [      ]   // we record owner and operation (hash) alongside it.
  25 -> 3            [      ]   event Confirmation(address owner, bytes32 operation);
  26 -> 4            [      ]   event Revoke(address owner, bytes32 operation);
  27 ->              [      ] 
  28 ->              [      ]   // some others are in the case of an owner changing.
  29 -> 5            [      ]   event OwnerChanged(address oldOwner, address newOwner);
  30 -> 6            [      ]   event OwnerAdded(address newOwner);
  31 -> 7            [      ]   event OwnerRemoved(address oldOwner);
  32 ->              [      ] 
  33 ->              [      ]   // the last one is emitted if the required signatures change
  34 -> 8            [      ]   event RequirementChanged(uint newRequirement);
  35 ->              [      ] 
  36 ->              [      ]   // Funds has arrived into the wallet (record how much).
  37 -> 9            [      ]   event Deposit(address _from, uint value);
  38 ->              [      ]   // Single transaction going out of the wallet (record who signed for it, how much, and to whom it's going).
  39 -> 10           [      ]   event SingleTransact(address owner, uint value, address to, bytes data, address created);
  40 ->              [      ]   // Multi-sig transaction going out of the wallet (record who signed for it last, the operation hash, how much, and to whom it's going).
  41 -> 11           [      ]   event MultiTransact(address owner, bytes32 operation, uint value, address to, bytes data, address created);
  42 ->              [      ]   // Confirmation still needed for a transaction.
  43 -> 12           [      ]   event ConfirmationNeeded(bytes32 operation, address initiator, uint value, address to, bytes data);
  44 -> 13           [      ] }
  45 ->              [      ] 
  46 -> 14           [      ] contract WalletAbi {
  47 ->              [      ]   // Revokes a prior confirmation of the given operation
  48 -> 15           [      ]   function revoke(bytes32 _operation) external;
  49 ->              [      ] 
  50 ->              [      ]   // Replaces an owner `_from` with another `_to`.
  51 -> 16           [      ]   function changeOwner(address _from, address _to) external;
  52 ->              [      ] 
  53 -> 17           [      ]   function addOwner(address _owner) external;
  54 ->              [      ] 
  55 -> 18           [      ]   function removeOwner(address _owner) external;
  56 ->              [      ] 
  57 -> 19           [      ]   function changeRequirement(uint _newRequired) external;
  58 ->              [      ] 
  59 -> 20           [      ]   function isOwner(address _addr) constant returns (bool);
  60 ->              [      ] 
  61 -> 21           [      ]   function hasConfirmed(bytes32 _operation, address _owner) external constant returns (bool);
  62 ->              [      ] 
  63 ->              [      ]   // (re)sets the daily limit. needs many of the owners to confirm. doesn't alter the amount already spent today.
  64 -> 22           [      ]   function setDailyLimit(uint _newLimit) external;
  65 ->              [      ] 
  66 -> 23           [      ]   function execute(address _to, uint _value, bytes _data) external returns (bytes32 o_hash);
  67 -> 24           [      ]   function confirm(bytes32 _h) returns (bool o_success);
  68 -> 25           [      ] }
  69 ->              [      ] 
  70 -> 26           [      ] contract WalletLibrary is WalletEvents {
  71 ->              [      ]   // TYPES
  72 ->              [      ] 
  73 ->              [      ]   // struct for the status of a pending operation.
  74 -> 27           [      ]   struct PendingState {
  75 -> 28           [      ]     uint yetNeeded;
  76 -> 29           [      ]     uint ownersDone;
  77 -> 30           [      ]     uint index;
  78 -> 31           [      ]   }
  79 ->              [      ] 
  80 ->              [      ]   // Transaction structure to remember details of transaction lest it need be saved for a later call.
  81 -> 32           [      ]   struct Transaction {
  82 -> 33           [      ]     address to;
  83 -> 34           [      ]     uint value;
  84 -> 35           [      ]     bytes data;
  85 -> 36           [      ]   }
  86 ->              [      ] 
  87 ->              [      ]   // MODIFIERS
  88 ->              [      ] 
  89 ->              [      ]   // simple single-sig function modifier.
  90 -> 37           [      ]   modifier onlyowner {
  91 -> 38           [      ]     if (isOwner(msg.sender))
  92 -> 39           [      ]       _;
  93 -> 40           [      ]   }
  94 ->              [      ]   // multi-sig function modifier: the operation must have an intrinsic hash in order
  95 ->              [      ]   // that later attempts can be realised as the same underlying operation and
  96 ->              [      ]   // thus count as confirmations.
  97 -> 41           [      ]   modifier onlymanyowners(bytes32 _operation) {
  98 -> 42           [      ]     if (confirmAndCheck(_operation))
  99 -> 43           [      ]       _;
 100 -> 44           [      ]   }
 101 ->              [      ] 
 102 ->              [      ]   // METHODS
 103 ->              [      ] 
 104 ->              [      ]   // gets called when no other function matches
 105 -> 45           [      ]   function() payable {
 106 ->              [      ]     // just being sent some cash?
 107 -> 46           [      ]     if (msg.value > 0)
 108 -> 47           [      ]       Deposit(msg.sender, msg.value);
 109 -> 48           [      ]   }
 110 ->              [      ] 
 111 ->              [      ]   // constructor is given number of sigs required to do protected "onlymanyowners" transactions
 112 ->              [      ]   // as well as the selection of addresses capable of confirming them.
 113 -> 49           [      ]   function initMultiowned(address[] _owners, uint _required) only_uninitialized {
 114 -> 50           [      ]     m_numOwners = _owners.length + 1;
 115 -> 51           [      ]     m_owners[1] = uint(msg.sender);
 116 -> 52           [      ]     m_ownerIndex[uint(msg.sender)] = 1;
 117 -> 53           [      ]     for (uint i = 0; i < _owners.length; ++i)
 118 -> 54           [      ]     {
 119 -> 55           [      ]       m_owners[2 + i] = uint(_owners[i]);
 120 -> 56           [      ]       m_ownerIndex[uint(_owners[i])] = 2 + i;
 121 -> 57           [      ]     }
 122 -> 58           [      ]     m_required = _required;
 123 -> 59           [      ]   }
 124 ->              [      ] 
 125 ->              [      ]   // Revokes a prior confirmation of the given operation
 126 -> 60           [      ]   function revoke(bytes32 _operation) external {
 127 -> 61           [      ]     uint ownerIndex = m_ownerIndex[uint(msg.sender)];
 128 ->              [      ]     // make sure they're an owner
 129 -> 62           [      ]     if (ownerIndex == 0) return;
 130 -> 63           [      ]     uint ownerIndexBit = 2**ownerIndex;
 131 -> 64           [      ]     var pending = m_pending[_operation];
 132 -> 65           [      ]     if (pending.ownersDone & ownerIndexBit > 0) {
 133 -> 66           [      ]       pending.yetNeeded++;
 134 -> 67           [      ]       pending.ownersDone -= ownerIndexBit;
 135 -> 68           [      ]       Revoke(msg.sender, _operation);
 136 -> 69           [      ]     }
 137 -> 70           [      ]   }
 138 ->              [      ] 
 139 ->              [      ]   // Replaces an owner `_from` with another `_to`.
 140 -> 71           [      ]   function changeOwner(address _from, address _to) onlymanyowners(sha3(msg.data)) external {
 141 -> 72           [      ]     if (isOwner(_to)) return;
 142 -> 73           [      ]     uint ownerIndex = m_ownerIndex[uint(_from)];
 143 -> 74           [      ]     if (ownerIndex == 0) return;
 144 ->              [      ] 
 145 -> 75           [      ]     clearPending();
 146 -> 76           [      ]     m_owners[ownerIndex] = uint(_to);
 147 -> 77           [      ]     m_ownerIndex[uint(_from)] = 0;
 148 -> 78           [      ]     m_ownerIndex[uint(_to)] = ownerIndex;
 149 -> 79           [      ]     OwnerChanged(_from, _to);
 150 -> 80           [      ]   }
 151 ->              [      ] 
 152 -> 81           [      ]   function addOwner(address _owner) onlymanyowners(sha3(msg.data)) external {
 153 -> 82           [      ]     if (isOwner(_owner)) return;
 154 ->              [      ] 
 155 -> 83           [      ]     clearPending();
 156 -> 84           [      ]     if (m_numOwners >= c_maxOwners)
 157 -> 85           [      ]       reorganizeOwners();
 158 -> 86           [      ]     if (m_numOwners >= c_maxOwners)
 159 -> 87           [      ]       return;
 160 -> 88           [      ]     m_numOwners++;
 161 -> 89           [      ]     m_owners[m_numOwners] = uint(_owner);
 162 -> 90           [      ]     m_ownerIndex[uint(_owner)] = m_numOwners;
 163 -> 91           [      ]     OwnerAdded(_owner);
 164 -> 92           [      ]   }
 165 ->              [      ] 
 166 -> 93           [      ]   function removeOwner(address _owner) onlymanyowners(sha3(msg.data)) external {
 167 -> 94           [      ]     uint ownerIndex = m_ownerIndex[uint(_owner)];
 168 -> 95           [      ]     if (ownerIndex == 0) return;
 169 -> 96           [      ]     if (m_required > m_numOwners - 1) return;
 170 ->              [      ] 
 171 -> 97           [      ]     m_owners[ownerIndex] = 0;
 172 -> 98           [      ]     m_ownerIndex[uint(_owner)] = 0;
 173 -> 99           [      ]     clearPending();
 174 -> 100          [      ]     reorganizeOwners(); //make sure m_numOwner is equal to the number of owners and always points to the optimal free slot
 175 -> 101          [      ]     OwnerRemoved(_owner);
 176 -> 102          [      ]   }
 177 ->              [      ] 
 178 -> 103          [      ]   function changeRequirement(uint _newRequired) onlymanyowners(sha3(msg.data)) external {
 179 -> 104          [      ]     if (_newRequired > m_numOwners) return;
 180 -> 105          [      ]     m_required = _newRequired;
 181 -> 106          [      ]     clearPending();
 182 -> 107          [      ]     RequirementChanged(_newRequired);
 183 -> 108          [      ]   }
 184 ->              [      ] 
 185 ->              [      ]   // Gets an owner by 0-indexed position (using numOwners as the count)
 186 -> 109          [      ]   function getOwner(uint ownerIndex) external constant returns (address) {
 187 -> 110          [      ]     return address(m_owners[ownerIndex + 1]);
 188 -> 111          [      ]   }
 189 ->              [      ] 
 190 -> 112          [      ]   function isOwner(address _addr) constant returns (bool) {
 191 -> 113          [      ]     return m_ownerIndex[uint(_addr)] > 0;
 192 -> 114          [      ]   }
 193 ->              [      ] 
 194 -> 115          [      ]   function hasConfirmed(bytes32 _operation, address _owner) external constant returns (bool) {
 195 -> 116          [      ]     var pending = m_pending[_operation];
 196 -> 117          [      ]     uint ownerIndex = m_ownerIndex[uint(_owner)];
 197 ->              [      ] 
 198 ->              [      ]     // make sure they're an owner
 199 -> 118          [      ]     if (ownerIndex == 0) return false;
 200 ->              [      ] 
 201 ->              [      ]     // determine the bit to set for this owner.
 202 -> 119          [      ]     uint ownerIndexBit = 2**ownerIndex;
 203 -> 120          [      ]     return !(pending.ownersDone & ownerIndexBit == 0);
 204 -> 121          [      ]   }
 205 ->              [      ] 
 206 ->              [      ]   // constructor - stores initial daily limit and records the present day's index.
 207 -> 122          [      ]   function initDaylimit(uint _limit) only_uninitialized {
 208 -> 123          [      ]     m_dailyLimit = _limit;
 209 -> 124          [      ]     m_lastDay = today();
 210 -> 125          [      ]   }
 211 ->              [      ]   // (re)sets the daily limit. needs many of the owners to confirm. doesn't alter the amount already spent today.
 212 -> 126          [      ]   function setDailyLimit(uint _newLimit) onlymanyowners(sha3(msg.data)) external {
 213 -> 127          [      ]     m_dailyLimit = _newLimit;
 214 -> 128          [      ]   }
 215 ->              [      ]   // resets the amount already spent today. needs many of the owners to confirm.
 216 -> 129          [      ]   function resetSpentToday() onlymanyowners(sha3(msg.data)) external {
 217 -> 130          [      ]     m_spentToday = 0;
 218 -> 131          [      ]   }
 219 ->              [      ] 
 220 ->              [      ]   // throw unless the contract is not yet initialized.
 221 -> 132          [      ]   modifier only_uninitialized { if (m_numOwners > 0) throw; _; }
 222 ->              [      ] 
 223 ->              [      ]   // constructor - just pass on the owner array to the multiowned and
 224 ->              [      ]   // the limit to daylimit
 225 ->              [      ]   // <yes> <report> ACCESS_CONTROL
 226 -> 133          [public]   function initWallet(address[] _owners, uint _required, uint _daylimit) only_uninitialized {
 227 -> 134          [      ]     initDaylimit(_daylimit);
 228 -> 135          [      ]     initMultiowned(_owners, _required);
 229 -> 136          [      ]   }
 230 ->              [      ] 
 231 ->              [      ]   // kills the contract sending everything to `_to`.
 232 ->              [      ]   // <yes> <report> ACCESS_CONTROL
 233 -> 137          [public]   function kill(address _to) onlymanyowners(sha3(msg.data)) external {
 234 -> 138          [      ]     suicide(_to);
 235 -> 139          [      ]   }
 236 ->              [      ] 
 237 ->              [      ]   // Outside-visible transact entry point. Executes transaction immediately if below daily spend limit.
 238 ->              [      ]   // If not, goes into multisig process. We provide a hash on return to allow the sender to provide
 239 ->              [      ]   // shortcuts for the other confirmations (allowing them to avoid replicating the _to, _value
 240 ->              [      ]   // and _data arguments). They still get the option of using them if they want, anyways.
 241 -> 140          [      ]   function execute(address _to, uint _value, bytes _data) external onlyowner returns (bytes32 o_hash) {
 242 ->              [      ]     // first, take the opportunity to check that we're under the daily limit.
 243 -> 141          [      ]     if ((_data.length == 0 && underLimit(_value)) || m_required == 1) {
 244 ->              [      ]       // yes - just execute the call.
 245 -> 142          [      ]       address created;
 246 -> 143          [      ]       if (_to == 0) {
 247 -> 144          [      ]         created = create(_value, _data);
 248 -> 145          [      ]       } else {
 249 -> 146          [      ]         if (!_to.call.value(_value)(_data))
 250 -> 147          [      ]           throw;
 251 -> 148          [      ]       }
 252 -> 149          [      ]       SingleTransact(msg.sender, _value, _to, _data, created);
 253 -> 150          [      ]     } else {
 254 ->              [      ]       // determine our operation hash.
 255 -> 151          [      ]       o_hash = sha3(msg.data, block.number);
 256 ->              [      ]       // store if it's new
 257 -> 152          [      ]       if (m_txs[o_hash].to == 0 && m_txs[o_hash].value == 0 && m_txs[o_hash].data.length == 0) {
 258 -> 153          [      ]         m_txs[o_hash].to = _to;
 259 -> 154          [      ]         m_txs[o_hash].value = _value;
 260 -> 155          [      ]         m_txs[o_hash].data = _data;
 261 -> 156          [      ]       }
 262 -> 157          [      ]       if (!confirm(o_hash)) {
 263 -> 158          [      ]         ConfirmationNeeded(o_hash, msg.sender, _value, _to, _data);
 264 -> 159          [      ]       }
 265 -> 160          [      ]     }
 266 -> 161          [      ]   }
 267 ->              [      ] 
 268 -> 162          [      ]   function create(uint _value, bytes _code) internal returns (address o_addr) {
 269 ->              [      ]     /*
 270 ->              [      ]     assembly {
 271 ->              [      ]       o_addr := create(_value, add(_code, 0x20), mload(_code))
 272 ->              [      ]       jumpi(invalidJumpLabel, iszero(extcodesize(o_addr)))
 273 ->              [      ]     }
 274 ->              [      ]     */
 275 -> 163          [      ]   }
 276 ->              [      ] 
 277 ->              [      ]   // confirm a transaction through just the hash. we use the previous transactions map, m_txs, in order
 278 ->              [      ]   // to determine the body of the transaction from the hash provided.
 279 -> 164          [      ]   function confirm(bytes32 _h) onlymanyowners(_h) returns (bool o_success) {
 280 -> 165          [      ]     if (m_txs[_h].to != 0 || m_txs[_h].value != 0 || m_txs[_h].data.length != 0) {
 281 -> 166          [      ]       address created;
 282 -> 167          [      ]       if (m_txs[_h].to == 0) {
 283 -> 168          [      ]         created = create(m_txs[_h].value, m_txs[_h].data);
 284 -> 169          [      ]       } else {
 285 -> 170          [      ]         if (!m_txs[_h].to.call.value(m_txs[_h].value)(m_txs[_h].data))
 286 -> 171          [      ]           throw;
 287 -> 172          [      ]       }
 288 ->              [      ] 
 289 -> 173          [      ]       MultiTransact(msg.sender, _h, m_txs[_h].value, m_txs[_h].to, m_txs[_h].data, created);
 290 -> 174          [      ]       delete m_txs[_h];
 291 -> 175          [      ]       return true;
 292 -> 176          [      ]     }
 293 -> 177          [      ]   }
 294 ->              [      ] 
 295 ->              [      ]   // INTERNAL METHODS
 296 ->              [      ] 
 297 -> 178          [      ]   function confirmAndCheck(bytes32 _operation) internal returns (bool) {
 298 ->              [      ]     // determine what index the present sender is:
 299 -> 179          [      ]     uint ownerIndex = m_ownerIndex[uint(msg.sender)];
 300 ->              [      ]     // make sure they're an owner
 301 -> 180          [      ]     if (ownerIndex == 0) return;
 302 ->              [      ] 
 303 -> 181          [      ]     var pending = m_pending[_operation];
 304 ->              [      ]     // if we're not yet working on this operation, switch over and reset the confirmation status.
 305 -> 182          [      ]     if (pending.yetNeeded == 0) {
 306 ->              [      ]       // reset count of confirmations needed.
 307 -> 183          [      ]       pending.yetNeeded = m_required;
 308 ->              [      ]       // reset which owners have confirmed (none) - set our bitmap to 0.
 309 -> 184          [      ]       pending.ownersDone = 0;
 310 -> 185          [      ]       pending.index = m_pendingIndex.length++;
 311 -> 186          [      ]       m_pendingIndex[pending.index] = _operation;
 312 -> 187          [      ]     }
 313 ->              [      ]     // determine the bit to set for this owner.
 314 -> 188          [      ]     uint ownerIndexBit = 2**ownerIndex;
 315 ->              [      ]     // make sure we (the message sender) haven't confirmed this operation previously.
 316 -> 189          [      ]     if (pending.ownersDone & ownerIndexBit == 0) {
 317 -> 190          [      ]       Confirmation(msg.sender, _operation);
 318 ->              [      ]       // ok - check if count is enough to go ahead.
 319 -> 191          [      ]       if (pending.yetNeeded <= 1) {
 320 ->              [      ]         // enough confirmations: reset and run interior.
 321 -> 192          [      ]         delete m_pendingIndex[m_pending[_operation].index];
 322 -> 193          [      ]         delete m_pending[_operation];
 323 -> 194          [      ]         return true;
 324 -> 195          [      ]       }
 325 -> 196          [      ]       else
 326 -> 197          [      ]       {
 327 ->              [      ]         // not enough: record that this owner in particular confirmed.
 328 -> 198          [      ]         pending.yetNeeded--;
 329 -> 199          [      ]         pending.ownersDone |= ownerIndexBit;
 330 -> 200          [      ]       }
 331 -> 201          [      ]     }
 332 -> 202          [      ]   }
 333 ->              [      ] 
 334 -> 203          [      ]   function reorganizeOwners() private {
 335 -> 204          [      ]     uint free = 1;
 336 -> 205          [      ]     while (free < m_numOwners)
 337 -> 206          [      ]     {
 338 -> 207          [      ]       while (free < m_numOwners && m_owners[free] != 0) free++;
 339 -> 208          [      ]       while (m_numOwners > 1 && m_owners[m_numOwners] == 0) m_numOwners--;
 340 -> 209          [      ]       if (free < m_numOwners && m_owners[m_numOwners] != 0 && m_owners[free] == 0)
 341 -> 210          [      ]       {
 342 -> 211          [      ]         m_owners[free] = m_owners[m_numOwners];
 343 -> 212          [      ]         m_ownerIndex[m_owners[free]] = free;
 344 -> 213          [      ]         m_owners[m_numOwners] = 0;
 345 -> 214          [      ]       }
 346 -> 215          [      ]     }
 347 -> 216          [      ]   }
 348 ->              [      ] 
 349 ->              [      ]   // checks to see if there is at least `_value` left from the daily limit today. if there is, subtracts it and
 350 ->              [      ]   // returns true. otherwise just returns false.
 351 -> 217          [      ]   function underLimit(uint _value) internal onlyowner returns (bool) {
 352 ->              [      ]     // reset the spend limit if we're on a different day to last time.
 353 -> 218          [      ]     if (today() > m_lastDay) {
 354 -> 219          [      ]       m_spentToday = 0;
 355 -> 220          [      ]       m_lastDay = today();
 356 -> 221          [      ]     }
 357 ->              [      ]     // check to see if there's enough left - if so, subtract and return true.
 358 ->              [      ]     // overflow protection                    // dailyLimit check
 359 -> 222          [      ]     if (m_spentToday + _value >= m_spentToday && m_spentToday + _value <= m_dailyLimit) {
 360 -> 223          [      ]       m_spentToday += _value;
 361 -> 224          [      ]       return true;
 362 -> 225          [      ]     }
 363 -> 226          [      ]     return false;
 364 -> 227          [      ]   }
 365 ->              [      ] 
 366 ->              [      ]   // determines today's index.
 367 -> 228          [      ]   function today() private constant returns (uint) { return now / 1 days; }
 368 ->              [      ] 
 369 -> 229          [      ]   function clearPending() internal {
 370 -> 230          [      ]     uint length = m_pendingIndex.length;
 371 ->              [      ] 
 372 -> 231          [      ]     for (uint i = 0; i < length; ++i) {
 373 -> 232          [      ]       delete m_txs[m_pendingIndex[i]];
 374 ->              [      ] 
 375 -> 233          [      ]       if (m_pendingIndex[i] != 0)
 376 -> 234          [      ]         delete m_pending[m_pendingIndex[i]];
 377 -> 235          [      ]     }
 378 ->              [      ] 
 379 -> 236          [      ]     delete m_pendingIndex;
 380 -> 237          [      ]   }
 381 ->              [      ] 
 382 ->              [      ]   // FIELDS
 383 -> 238          [      ]   address constant _walletLibrary = 0xcafecafecafecafecafecafecafecafecafecafe;
 384 ->              [      ] 
 385 ->              [      ]   // the number of owners that must confirm the same operation before it is run.
 386 -> 239          [      ]   uint public m_required;
 387 ->              [      ]   // pointer used to find a free slot in m_owners
 388 -> 240          [      ]   uint public m_numOwners;
 389 ->              [      ] 
 390 -> 241          [      ]   uint public m_dailyLimit;
 391 -> 242          [      ]   uint public m_spentToday;
 392 -> 243          [      ]   uint public m_lastDay;
 393 ->              [      ] 
 394 ->              [      ]   // list of owners
 395 -> 244          [      ]   uint[256] m_owners;
 396 ->              [      ] 
 397 -> 245          [      ]   uint constant c_maxOwners = 250;
 398 ->              [      ]   // index on the list of owners to allow reverse lookup
 399 -> 246          [      ]   mapping(uint => uint) m_ownerIndex;
 400 ->              [      ]   // the ongoing operations.
 401 -> 247          [      ]   mapping(bytes32 => PendingState) m_pending;
 402 -> 248          [      ]   bytes32[] m_pendingIndex;
 403 ->              [      ] 
 404 ->              [      ]   // pending transactions we have at present.
 405 -> 249          [      ]   mapping (bytes32 => Transaction) m_txs;
 406 -> 250          [      ] }
~~~
## All node disagreements

### Node 9496 function_definition
Author 0 / public endpoint 1; processed [133, 136] -> original [226, 229]
~~~solidity
function initWallet(address[] _owners, uint _required, uint _daylimit) only_uninitialized {
    initDaylimit(_daylimit);
    initMultiowned(_owners, _required);
  }
~~~

### Node 9499 function_definition
Author 0 / public endpoint 1; processed [137, 139] -> original [233, 235]
~~~solidity
function kill(address _to) onlymanyowners(sha3(msg.data)) external {
    suicide(_to);
  }
~~~
