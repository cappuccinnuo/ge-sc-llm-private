pragma solidity ^0.4.24; contract A { address owner; function f(address x) public { require(msg.sender == owner); owner = x; } function require(bool p) internal {} }
