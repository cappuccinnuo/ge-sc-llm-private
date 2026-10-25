pragma solidity 0.5.17;
contract InheritedBase {
    uint inherited;
}
contract InheritedChild is InheritedBase {
    function writeValue() public { inherited = 7; }
    function readValue() public view returns (uint) { return inherited; }
}
