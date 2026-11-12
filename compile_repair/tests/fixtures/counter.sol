pragma solidity ^0.4.11;
contract Counter {
    uint public count;
    modifier allowed() { _; }
    function increment(uint value) public allowed { count += value; }
}
