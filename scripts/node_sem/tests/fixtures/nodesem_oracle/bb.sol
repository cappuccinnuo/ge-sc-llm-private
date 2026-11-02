pragma solidity ^0.4.24; contract A { address owner; uint x; modifier onlyOwner { if (msg.sender == owner) _; } function f() public onlyOwner { x = 1; } }
