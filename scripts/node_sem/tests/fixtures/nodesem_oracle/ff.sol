pragma solidity ^0.4.24; contract A { address owner; uint x; function f(bool a) public { if (a || msg.sender == owner) { x = 1; } } }
