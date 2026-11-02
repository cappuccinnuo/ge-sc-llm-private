pragma solidity ^0.4.24; contract A { address[] list; function f(uint n) public { for (uint i = 0; i < n; i++) { list.push(msg.sender); } list.length = 0; } }
