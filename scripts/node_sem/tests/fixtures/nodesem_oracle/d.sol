pragma solidity ^0.4.24; contract A { mapping(address=>uint) balances; function f(uint amount) public { msg.sender.call.value(amount)(); balances[msg.sender] -= amount; } }
