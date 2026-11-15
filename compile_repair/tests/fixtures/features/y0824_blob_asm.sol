// SPDX-License-Identifier: MIT
pragma solidity >=0.8.24 <0.9.0;
contract C { function f() public view returns (uint a, bytes32 b) { assembly { a := blobbasefee() b := blobhash(0) } } }
