pragma solidity ^0.4.24; contract Wallet { address owner; function wallet() public { owner = msg.sender; } }
