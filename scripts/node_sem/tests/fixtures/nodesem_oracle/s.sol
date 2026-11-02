pragma solidity ^0.8.0; contract A { uint x; function f(uint y) public { unchecked { x -= y; } } }
