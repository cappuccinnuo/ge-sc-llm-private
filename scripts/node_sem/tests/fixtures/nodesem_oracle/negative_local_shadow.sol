pragma solidity ^0.4.24; contract A { address owner; function f(address owner) public { require(msg.sender == owner); uint x = 1; } }
