pragma solidity 0.5.17;
contract PrefixModifier {
    address owner;
    modifier onlyOwner() {
        require(msg.sender == owner);
        _;
    }
    function run() public onlyOwner returns (uint) {
        uint ticket = 5;
        uint copied = ticket;
        return copied;
    }
}
