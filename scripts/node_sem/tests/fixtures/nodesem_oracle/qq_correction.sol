pragma solidity ^0.5.11; contract Subject { bool paused; address owner; uint x; function f() public { require(paused && tx.origin == owner); x = 1; } }
