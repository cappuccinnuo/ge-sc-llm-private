pragma solidity ^0.4.24; contract A { address owner; modifier onlyOwner { require(msg.sender == owner); _; } function kill() public onlyOwner { selfdestruct(owner); } }
