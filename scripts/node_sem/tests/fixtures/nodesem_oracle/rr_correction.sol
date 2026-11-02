pragma solidity ^0.5.11; contract Subject { uint y; function f(uint b,address p) public { if (b > 0 && msg.sender != p) { y = 1; } } }
