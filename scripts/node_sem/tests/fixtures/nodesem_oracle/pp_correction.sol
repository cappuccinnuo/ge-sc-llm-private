pragma solidity ^0.5.11; contract Subject { uint deadline; address owner; uint x; function f() public { require(now > deadline && msg.sender == owner); x = 1; } }
