// SPDX-License-Identifier: MIT
pragma solidity >=0.8.7 <0.9.0;
contract C { function f() public view returns (uint x) { assembly { x := basefee() } } }
