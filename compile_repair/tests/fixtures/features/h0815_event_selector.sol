// SPDX-License-Identifier: MIT
pragma solidity >=0.8.15 <0.9.0;
contract C { event E(uint); function f() public pure returns (bytes32) { return E.selector; } }
