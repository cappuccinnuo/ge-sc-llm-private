pragma solidity 0.5.17;
contract TupleStatement {
    function run() public pure returns (uint) {
        uint x = 4;
        uint y = 8;
        uint a = 0;
        uint b = 1;
        (a, b) = (x, y);
        uint left = a;
        uint right = b;
        return left + right;
    }
}
