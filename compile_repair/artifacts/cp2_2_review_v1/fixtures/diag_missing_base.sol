pragma solidity >=0.4.12;
// SPDX-License-Identifier: MIT
contract A is B {
  function f() public { X(msg.sender).foo(); undefinedVar = 1; }
}
