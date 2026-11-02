pragma solidity ^0.4.24; contract A { address ownerState; function f(address _param) public { require(tx.origin == ownerState); require(tx.origin == _param); } }
