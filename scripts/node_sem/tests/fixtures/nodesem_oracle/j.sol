pragma solidity ^0.4.24; contract A { uint state; function f() public { state = 1; msg.sender.call(); } }
