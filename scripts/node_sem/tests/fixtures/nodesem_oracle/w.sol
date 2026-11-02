pragma solidity ^0.4.24; contract A { address owner; uint reward; function f() public payable { owner.transfer(reward); reward = msg.value; } }
