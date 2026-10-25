pragma solidity 0.5.17;
contract PushReceiver {
    function push(uint value) public { }
}
contract ContractPush {
    PushReceiver target;
    function run() public { target.push(1); }
}
