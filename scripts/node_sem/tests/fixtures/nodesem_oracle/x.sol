pragma solidity ^0.4.24; contract A { function f() public { if (now % 15 == 0) { msg.sender.transfer(this.balance); } } }
