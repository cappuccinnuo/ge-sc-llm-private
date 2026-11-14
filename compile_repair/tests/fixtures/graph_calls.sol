pragma solidity 0.8.0;

function freeStep(uint256 x) pure returns (uint256) { return x + 2; }

library GraphLibrary {
    function step(uint256 x) external pure returns (uint256) { return x + 1; }
}

contract GraphTarget {
    function ping(uint256 x) external pure returns (uint256) { return x; }
}

contract GraphBase {
    modifier checked(uint256 x) { require(x > 0); _; }
}

contract GraphCalls is GraphBase {
    event Seen(uint256 value);
    uint256 public value;

    function internalStep(uint256 x) internal pure returns (uint256) { return x + 1; }

    function exercise(address payable receiver, GraphTarget target, uint256 x)
        public payable checked(x) returns (uint256)
    {
        function(uint256) internal pure returns (uint256) callback = internalStep;
        value = callback(x);
        value = internalStep(value);
        value = freeStep(value);
        value = GraphLibrary.step(value);
        value = target.ping(value);
        (bool ok, ) = receiver.call("");
        require(ok);
        bool sent = receiver.send(0);
        require(sent);
        receiver.transfer(0);
        emit Seen(value);
        GraphTarget created = new GraphTarget();
        value = created.ping(value);
        if (x > 1) { value += x; } else { value -= 1; }
        while (x > 2) { x--; }
        return value;
    }

    function ternary(uint256 a, uint256 b) public pure returns (uint256) {
        return a < b ? a : b;
    }
}
