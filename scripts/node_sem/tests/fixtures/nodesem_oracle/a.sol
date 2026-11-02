pragma solidity ^0.4.24; contract A { function f(uint _am) public { msg.sender.call.value(_am)(); } }
