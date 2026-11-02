pragma solidity ^0.4.24; contract A { address owner; function f(address x) public { if (msg.sender != owner) throw; owner = x; } }
