pragma solidity ^0.5.11; contract Subject { address owner; uint x; function f() public { require(msg.sender == owner || msg.sender == address(this)); x = 1; } }
