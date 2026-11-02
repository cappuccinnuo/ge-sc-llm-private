pragma solidity ^0.4.24; contract A { address target; function() public { target.delegatecall(msg.data); } }
