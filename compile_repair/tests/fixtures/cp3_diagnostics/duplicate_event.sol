pragma solidity >=0.4.12 <0.9.0;
contract A { event E(uint x); } contract C is A { event E(uint x); }
