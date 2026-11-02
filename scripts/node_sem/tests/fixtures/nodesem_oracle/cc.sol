pragma solidity ^0.4.24; contract A { address owner; uint x; function _check() internal { require(msg.sender == owner); } function f() public { _check(); x = 1; } }
