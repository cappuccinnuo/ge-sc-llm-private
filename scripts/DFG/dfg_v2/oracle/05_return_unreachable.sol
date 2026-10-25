pragma solidity 0.5.17;
contract ReturnUnreachable {
    function run() public pure returns (uint) {
        uint x = 4;
        return x;
        x = 9;
    }
}
