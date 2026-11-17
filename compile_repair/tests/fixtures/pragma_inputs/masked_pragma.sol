// pragma solidity ^0.4.0; { }
/* " } pragma solidity ^0.4.0; { " */
pragma solidity ^0.5.0;
contract C {
    string public text = "quoted \" } pragma solidity ^0.4.0; {";
    string public other = 'pragma solidity ^0.4.0;';
    function f() public pure returns (uint) { return 1; }
}
