pragma solidity ^0.5.11; contract A { function f() public { uint r = uint(keccak256(abi.encodePacked(block.timestamp))) % 2; } }
