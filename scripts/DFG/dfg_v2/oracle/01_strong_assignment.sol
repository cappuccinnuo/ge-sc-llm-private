pragma solidity 0.5.17;
contract StrongAssignment {
    function run() public pure returns (uint) {
        uint x = 1;
        x = 2;
        uint answer = x;
        return answer;
    }
}
