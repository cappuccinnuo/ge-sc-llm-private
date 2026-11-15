pragma solidity ^0.4.24;
contract B { function f() internal returns (uint); }
contract D is B { function g() public returns (uint) { return f(); } }
