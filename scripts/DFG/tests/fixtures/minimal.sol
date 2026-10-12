pragma solidity ^0.5.17;

contract DDGExample {
    function calc(uint x, bool change) public pure returns (uint) {
        uint y = x;
        if (change) {
            y = x + 1;
        } else {
            y = x + 2;
        }
        return y;
    }

    function clean() public pure returns (uint) {
        uint z = 7;
        return z;
    }
}
