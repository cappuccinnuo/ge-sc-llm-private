pragma solidity ^0.5.11; contract Subject { uint a; function f(address t) public view returns(uint n) { assembly { n := extcodesize(t) } } }
