pragma solidity 0.5.17;
contract UnmappedEmit {
    event Seen(address sender);
    function run() public { emit Seen(msg.sender); }
}
