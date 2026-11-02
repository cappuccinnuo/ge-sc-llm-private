pragma solidity ^0.4.24; contract A { address[] addrs; function f(address bidder, uint bid) public { for (uint i = 0; i < addrs.length; i++) { addrs[i].send(1); } require(bidder.send(bid)); } }
