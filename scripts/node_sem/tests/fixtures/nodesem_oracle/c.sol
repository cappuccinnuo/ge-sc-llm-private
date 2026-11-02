pragma solidity ^0.5.11; contract A { function f(address a, bytes memory data) public { (bool ok, ) = a.call(data); uint x = 1; } }
