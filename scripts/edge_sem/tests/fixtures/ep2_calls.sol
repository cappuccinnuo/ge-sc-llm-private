pragma solidity ^0.5.11;
library Calc {
    function sub(uint a, uint b) internal pure returns (uint) { return a-b; }
    function sub(uint a, uint b, uint c) internal pure returns (uint) { return a-b-c; }
}
interface Token {
    function transfer(address a, uint b) external returns (bool);
}
contract Base {
    modifier inheritedGate(uint a) { require(a > 0); _; }
}
contract Target is Base {
    using Calc for uint;
    Token token;
    uint x;
    modifier localGate() { _; }
    modifier callsHelper() { helper(1); _; }
    constructor() public inheritedGate(1) {}
    function helper(uint a) internal returns (uint) { return a; }
    function transfer(address a, uint b) internal returns (bool) { return true; }
    function overloaded(uint a) internal returns (uint) { return a; }
    function overloaded(uint a, uint b) internal returns (uint) { return a+b; }
    function run(uint a, address recipient) public inheritedGate(a) localGate {
        x = helper(a);
        x = helper(a) + helper(a);
        token.transfer(recipient, a);
        msg.sender.call.value(a)("");
        a.sub(1);
        a.sub(1, 2);
        overloaded(a);
        overloaded(a, a);
    }
    function bad() public missing {}
}
