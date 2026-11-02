pragma solidity ^0.4.24; contract A { uint deadline; uint state; function f() public { if (now > deadline) { state = 1; } } }
