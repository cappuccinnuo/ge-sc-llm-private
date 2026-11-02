pragma solidity ^0.5.11; contract Subject { address owner; function f(address newOwner) public { assert(msg.sender == owner && msg.sender != newOwner); owner = newOwner; } }
