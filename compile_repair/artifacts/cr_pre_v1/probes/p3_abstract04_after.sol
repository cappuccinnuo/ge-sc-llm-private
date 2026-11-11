pragma solidity ^0.4.24;
contract D is B { function g() public returns (uint) { return f(); } }
contract B { function f() internal returns (uint); }
