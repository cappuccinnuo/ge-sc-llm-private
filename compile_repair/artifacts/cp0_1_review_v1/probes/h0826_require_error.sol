// SPDX-License-Identifier: MIT
pragma solidity >=0.8.26 <0.9.0;
error Bad(uint v); contract C { function f(uint v) public pure { require(v > 1, Bad(v)); } }
