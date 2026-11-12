// Custom errors introduced in Solidity 0.8.4 release announcement.
pragma solidity >=0.8.4 <0.9.0;
contract ErrorProbe {
    error TooSmall(uint actual);
    function checked(uint x) public pure returns (uint) {
        if (x == 0) revert TooSmall(x);
        return x;
    }
}
