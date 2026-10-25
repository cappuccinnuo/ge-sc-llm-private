pragma solidity 0.5.17;
contract WhileFixpoint {
    function run() public pure returns (uint) {
        uint x = 0;
        while (x < 3) { x = x + 1; }
        return x;
    }
}
