pragma solidity ^0.4.24; contract A { function f(uint x) public { if (!msg.sender.send(x)) throw; } }
