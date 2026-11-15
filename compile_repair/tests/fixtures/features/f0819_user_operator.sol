pragma solidity >=0.8.19 <0.9.0;
type U is uint256;
using {add as +} for U global;
function add(U a, U b) pure returns (U) { return U.wrap(U.unwrap(a) + U.unwrap(b)); }
contract P { function f(U a, U b) public pure returns (U) { return a + b; } }
