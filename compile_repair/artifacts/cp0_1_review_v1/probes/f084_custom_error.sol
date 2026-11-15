pragma solidity >=0.8.4 <0.9.0;
contract P { error TooSmall(uint a); function f(uint x) public pure returns (uint) { if (x == 0) revert TooSmall(x); return x; } }
