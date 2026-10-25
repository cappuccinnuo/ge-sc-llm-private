pragma solidity 0.5.17;
contract ConstantAndShadow {
    uint credit;
    uint constant LIMIT = 3;
    function read(uint credit) public pure returns (uint) { return credit + LIMIT; }
}
