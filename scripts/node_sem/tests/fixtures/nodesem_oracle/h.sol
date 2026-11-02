pragma solidity ^0.4.24; contract Wallet { address owner; function Wallet() public { owner = msg.sender; } }
