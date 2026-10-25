pragma solidity 0.5.11;
contract BareExpressions {
    function bare(uint x) public pure { x; }
    function unused(address payable to, uint amount) public { to.call.value(amount); }
    function called(address payable to, uint amount) public {
        (bool ok,) = to.call.value(amount)("");
        require(ok);
    }
}
