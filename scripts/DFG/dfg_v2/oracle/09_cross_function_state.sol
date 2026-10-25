pragma solidity 0.4.26;
contract CrossFunctionState {
    mapping(address => uint) balances;
    function deposit() public payable {
        balances[msg.sender] += msg.value;
    }
    function withdraw() public {
        uint amount = balances[msg.sender];
        msg.sender.call.value(amount)("");
        balances[msg.sender] = 0;
    }
}
