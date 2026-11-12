pragma solidity >=0.4.12 <0.5.0;

contract Ternary {
    function min(uint a, uint b) public constant returns (uint) {
        return a < b ? a : b;
    }
}
