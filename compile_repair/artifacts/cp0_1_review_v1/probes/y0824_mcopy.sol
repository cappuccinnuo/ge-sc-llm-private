// SPDX-License-Identifier: MIT
pragma solidity >=0.8.24 <0.9.0;
contract C { function f() public pure { assembly { mcopy(0, 32, 32) } } }
