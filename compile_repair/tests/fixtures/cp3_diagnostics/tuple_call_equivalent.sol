pragma solidity >=0.4.12 <0.5.0;
contract C { function pay() public { bool success = msg.sender.call.value(1)(""); require(success); } }
