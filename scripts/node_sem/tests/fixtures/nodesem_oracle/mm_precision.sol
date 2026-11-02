pragma solidity ^0.5.11; import "Outside.sol"; contract Subject is Outside { uint known; function f() public { inheritedVar = 1; known = 2; } }
