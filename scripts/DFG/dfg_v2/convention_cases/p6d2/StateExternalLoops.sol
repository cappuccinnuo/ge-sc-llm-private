pragma solidity >=0.4.24 <=0.5.11;
contract StateExternalLoops {
    uint balance;
    function withSend(uint x) public {
        while (balance > x) { msg.sender.send(1); balance -= 1; }
    }
    function withoutSend(uint x) public {
        while (balance > x) { balance -= 1; }
    }
}
