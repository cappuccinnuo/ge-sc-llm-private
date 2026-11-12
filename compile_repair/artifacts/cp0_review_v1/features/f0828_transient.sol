pragma solidity >=0.8.28 <0.9.0;
contract P { uint256 transient lock; function f() public { require(lock == 0); lock = 1; lock = 0; } }
