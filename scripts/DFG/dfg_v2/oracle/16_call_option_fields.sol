pragma solidity 0.6.12;
contract CallOptionFields {
    address payable target;
    uint value;
    uint gas;
    uint salt;
    function run() public {
        uint x = 1;
        target.call{value: x}("");
    }
}
