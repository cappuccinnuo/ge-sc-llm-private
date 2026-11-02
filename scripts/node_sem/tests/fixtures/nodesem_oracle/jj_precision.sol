pragma solidity ^0.5.11; contract Subject { address a; address b; uint y; function f() public { if (msg.sender != a && msg.sender != b) revert(); y = 1; } }
