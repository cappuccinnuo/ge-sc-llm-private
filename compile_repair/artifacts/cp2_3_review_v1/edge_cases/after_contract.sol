pragma solidity ^0.4.24;
contract A { string s = "}"; function f() public { assembly { let x := 1 } } }
pragma solidity >=0.4.20;
