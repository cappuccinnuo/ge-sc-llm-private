pragma solidity >=0.8.8 <0.9.0;
type Price is uint256;
contract P { function f(Price p) public pure returns (uint256) { return Price.unwrap(p) + 1; } }
