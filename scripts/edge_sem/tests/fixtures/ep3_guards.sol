pragma solidity ^0.5.11;
contract Base {
    uint baseValue;
    constructor(uint n) public { baseValue = n; }
    modifier baseGate() { require(msg.sender != address(0)); _; }
}
contract Guards is Base {
    address owner;
    uint deadline;
    uint x;
    uint y;
    uint z;
    address payable[] arr;
    constructor() Base(1) public { x = 7; }
    modifier onlyOwner() { require(msg.sender == owner); _; }
    modifier readyGate() { require(x > 0); _; }
    function direct(address n) public {
        require(msg.sender == owner);
        owner = n;
    }
    function timed() public {
        if (now > deadline) { x = 1; }
    }
    function branch(bool c) public {
        if (c) { x = 1; } else { y = 2; }
    }
    function _check() internal view {
        require(x > 0);
        require(y > 0);
    }
    function internalGuard() public {
        _check();
        z = 1;
    }
    function two(address n) public onlyOwner readyGate {
        owner = n;
        x = 1;
    }
    function single(address n) public onlyOwner {
        owner = n;
        x = 1;
    }
    function inherited(bool c) public baseGate {
        if (c) { x = 2; }
    }
    function early(bool ok) public {
        if (!ok) revert();
        y = 2;
    }
    function arithmetic(uint a, uint b) public {
        require(a + b >= a);
        z = a + b;
    }
    function loop() public {
        for (uint i = 0; i < arr.length; i++) { arr[i].transfer(1); }
    }
    function nested(bool c) public {
        require(x > 0);
        if (c) { while (x > 1) { x--; } }
    }
    function uncertain(address n) public onlyOwner missing {
        owner = n;
    }
}
