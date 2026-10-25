pragma solidity 0.4.26;
contract EnvironmentShadow {
    function read(uint now) public pure returns (uint) { return now; }
}
