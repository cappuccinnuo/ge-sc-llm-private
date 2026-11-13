// SPDX-License-Identifier: MIT
pragma solidity >=0.8.22 <0.9.0;
event Ping(uint v); contract C { function f() public { emit Ping(1); } }
