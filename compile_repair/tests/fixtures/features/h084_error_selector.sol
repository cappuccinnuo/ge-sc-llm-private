// SPDX-License-Identifier: MIT
pragma solidity >=0.8.4 <0.9.0;
error Bad(); contract C { function f() public pure returns (bytes4) { return Bad.selector; } }
