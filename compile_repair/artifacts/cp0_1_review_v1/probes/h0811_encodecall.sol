// SPDX-License-Identifier: MIT
pragma solidity >=0.8.12 <0.9.0;
interface I { function g(uint) external; } contract C { function f() public pure returns (bytes memory, string memory) { return (abi.encodeCall(I.g, (1)), string.concat("a", "b")); } }
