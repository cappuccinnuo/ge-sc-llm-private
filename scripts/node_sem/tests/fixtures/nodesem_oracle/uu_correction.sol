pragma solidity ^0.5.11; contract Subject { struct Rec { uint v; } Rec[] recs; uint a; function f(uint i) public { Rec storage r = recs[i]; { Rec storage r = recs[i]; } r.v = 1; } }
