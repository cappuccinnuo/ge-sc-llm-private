pragma solidity >=0.7.1 <0.8.0;

function increment(uint value) pure returns (uint) {
    return value + 1;
}

contract UsesFreeFunction {
    function next(uint value) public pure returns (uint) {
        return increment(value);
    }
}
