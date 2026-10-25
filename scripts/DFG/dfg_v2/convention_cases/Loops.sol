pragma solidity 0.5.11;
contract Loops {
    uint public s;
    function whileLocal(uint n) public pure returns (uint) {
        uint i = 0;
        while (i < n) { i = i + 1; }
        return i;
    }
    function forLocal(uint n) public pure returns (uint) {
        uint total = 0;
        for (uint i = 0; i < n; i = i + 1) { total = total + i; }
        return total;
    }
    function whileState(uint n) public {
        while (s < n) { s = s + 1; }
    }
}
