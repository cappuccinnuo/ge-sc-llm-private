pragma solidity ^0.5.11; contract A { function f(address payable c) public { c.call.value(1 ether); c.send(1); } }
