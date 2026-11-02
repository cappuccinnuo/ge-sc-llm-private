pragma solidity ^0.5.11; contract Subject { event Log(uint time); function f() public { emit Log(now); } }
