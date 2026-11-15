pragma solidity 0.5.0;

contract GraphBranches {
    uint public value;

    function emptyIf(address payable a) public {
        if (!a.send(1)) {}
    }

    function emptyElse(bool yes) public {
        if (yes) { value = 1; } else {}
    }

    function bothEmpty(bool yes) public {
        if (yes) {} else {}
    }

    function withElse(bool yes) public {
        if (yes) { value = 2; } else { value = 3; }
    }

    function whileLoop(uint n) public {
        while (value < n) { value++; }
    }

    function forLoop(uint n) public {
        for (uint i = 0; i < n; i++) { value += i; }
    }
}
