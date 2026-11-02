pragma solidity ^0.4.24; contract A { bytes32 hash; function f(bytes solution) public { require(hash == sha3(solution)); msg.sender.transfer(1000 ether); } }
