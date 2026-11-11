pragma solidity ^0.5.11;
library Maths { function twice(uint p) internal pure returns(uint) { return p*2; } }
contract Subject {
    using Maths for uint;
    address payable owner;
    uint value;
    bool locked;
    mapping(address=>uint) balances;
    modifier gate() { require(msg.sender == owner); _; }
    modifier timed() { require(block.number > value); _; }
    modifier lock() { locked = true; _; locked = false; }
    function dual(uint p) public gate timed { value = p; }
    function lockedCall() public lock { value = 1; }
    function helper(uint p) internal { value = p; }
    function calls(uint p) public {
        uint x = p + 1;
        owner.call.value(x)("");
        balances[msg.sender] -= x;
        helper(x);
        uint y = x.twice();
        value = y;
    }
    function loops(uint n) public {
        uint i = 0;
        while (i < n) { i++; }
        value = i;
    }
    function product(uint a, uint b) public {
        uint ax = a;
        uint bx = b;
        uint c = ax * bx;
        require(a + b >= a);
        value = c;
    }
    function checked(address payable a, uint p) public {
        address payable target = a;
        uint amount = p;
        if (!target.send(amount)) revert();
        value = p;
    }
    function uncheckedCall(address a, bytes memory d) public {
        (bool ok, ) = a.call(d);
        require(d.length > 0);
    }
    function unused(address a, bytes memory d) public {
        address receiver = a;
        bytes memory payload = d;
        (bool success, ) = receiver.call(payload);
    }
    function noBody() public gate timed;
}
