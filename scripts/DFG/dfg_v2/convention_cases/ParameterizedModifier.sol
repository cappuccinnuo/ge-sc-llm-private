pragma solidity 0.5.11;
contract ParameterizedModifier {
    uint public threshold;
    uint public value;
    modifier above(uint n) { require(n > threshold); _; }
    function set(uint v) public above(v) { value = v; }
}
