pragma solidity >=0.8.13 <0.9.0;
library L { function inc(uint x) internal pure returns (uint) { return x + 1; } }
using L for uint;
contract P { function f(uint x) public pure returns (uint) { return x.inc(); } }
