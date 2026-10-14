# F0 完整先导语料普查

名单从封存formal计划、prepared清单及固定任务折取得，逐一核验SHA。
原源码、图、标签、特征均不修改。共256文件路径、254个源码SHA。
重入合约142/节点71；访问控制合约114/节点57；节点是相应合约任务子集。

| Task | Files/functions | Syntax write-before-read | READ/WRITE | RMW reads | HAVOC | EXACT/MAY |
|---|---|---|---|---|---|---|
| reentrancy_author/contract | 142/3404 | 441 | 878/658 | 142 | 696 | 10/4 |
| reentrancy_author/node | 71/2045 | 209 | 777/577 | 138 | 566 | 5/4 |
| access_control_author/contract | 114/3148 | 407 | 155/158 | 11 | 420 | 12/5 |
| access_control_author/node | 57/1958 | 164 | 85/91 | 7 | 386 | 7/3 |

“文本先写后读”是AST语法需求盘点，可能包含遮蔽、不可达或有副作用调用，
不能解释为正确数据依赖；位置绑定、CFG次序、别名、RD与投影分别验证。
7个困难文件不能代表全体：冻结Stage E在全语料已有重入10、访问控制12条EXACT事实。

原主要覆盖瓶颈为继承/B1闭合绑定、modifier、多pragma，以及复杂存储和非标量类型。
本轮优先恢复同单元单继承链和pragma交集；不对modifier/复杂引用作猜测。

文件解析/pragma/import/继承/modifier分布见F0_CORPUS_INVENTORY.csv；
6,552个函数及第一回退原因、其他潜在限制见F0_FUNCTION_SUPPORT.csv。
语法候选与语义事件分开保存，不把tree-sitter可解析等同编译成功。
