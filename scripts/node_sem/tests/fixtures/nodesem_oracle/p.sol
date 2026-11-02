pragma solidity ^0.4.24; contract A { uint state; function f() public { assembly { let x := 1 } state = 1; } }
