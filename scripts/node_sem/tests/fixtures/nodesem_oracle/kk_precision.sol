pragma solidity ^0.5.11; contract Subject { address owner; bool paused; uint x; function f() public { require(msg.sender == owner || paused == false); x = 1; } }
