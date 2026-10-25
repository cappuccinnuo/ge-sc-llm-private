pragma solidity 0.5.17;
contract DeleteIncrement {
    mapping(address => uint) balances;
    mapping(uint => uint) counts;
    function run() public {
        uint k = 7;
        delete balances[msg.sender];
        ++counts[k];
    }
}
