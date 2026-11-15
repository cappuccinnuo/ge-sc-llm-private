pragma solidity >=0.7.1 <0.9.0;
function twice(uint x) pure returns (uint) { return 2 * x; }
contract P { function f(uint x) public pure returns (uint) { return twice(x); } }
