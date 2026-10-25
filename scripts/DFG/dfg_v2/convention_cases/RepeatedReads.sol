pragma solidity 0.5.11;
contract RepeatedReads {
    mapping(uint => uint) public m;
    uint public s;
    function repeated(uint k) public view returns (uint) { return m[k] + m[k]; }
    function scalar() public view returns (uint) { return s + s; }
}
