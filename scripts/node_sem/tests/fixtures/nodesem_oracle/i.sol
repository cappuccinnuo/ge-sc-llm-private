pragma solidity ^0.4.24; contract A { address[] users; function f() public { for (uint i = 0; i < users.length; i++) users[i].transfer(1); } }
