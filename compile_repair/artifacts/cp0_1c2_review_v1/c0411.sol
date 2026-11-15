pragma solidity ^0.4.11;
contract C {
    uint x;
    function set(uint v) public { if (v > 1) { x = v; } else { x = 1; } }
}
