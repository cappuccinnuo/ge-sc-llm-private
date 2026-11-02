pragma solidity ^0.4.24; contract A { function f(address a, bytes b) public { uint t = now; bytes32 h = sha3(b); a.call.value(1)(); suicide(a); } function stop() public { throw; } }
