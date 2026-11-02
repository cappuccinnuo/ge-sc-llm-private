pragma solidity ^0.4.24; contract Subject { mapping(address=>uint) balances; function f(bool ok) public { if (!ok) throw; balances[msg.sender] = 0; } function g() public { { throw; } } }
