# F1 绑定、版本与调用副作用

日期：2026-10-14；Codex。全部新核心在 scripts/DFG/state/stage_f/，没有覆盖 Stage E。

## 修改位置与原因

| 文件 | 作用 |
|---|---|
| versioning.py | 多 pragma 求交；来源哈希一致的 versions.csv 版本证据；内建可用区间 |
| frontend.py | 原始源码和兼容 AST 双映射，注入新版本证据；不改源码来绕过解析 |
| binding.py | 同编译单元唯一声明、单继承链、可见性、遮蔽和内建绑定证据 |
| analyzer.py | 适配原 SymbolTable、CFGBuilder、状态事件提取和 RD；每函数原子回退 |
| tests/test_binding.py | 声明顺序、私有成员、冲突、多继承、导入、版本、假内建等正反例 |

单继承链不需要猜测多基类线性化。多继承、接口/库作为基类、构造参数、循环、
未定位基类、import 未解析继续回退。状态位置身份包含源码 SHA、声明合约与声明字节跨度；
同名参数/局部遮蔽状态声明；祖先 private 不作为可见状态成员。
继承覆盖/重载造成不能唯一确定调用时，仍然 UNKNOWN/回退，不选择第一个文本匹配。

所有 pragma 按 AND 求交，保留上下界；不支持的表达式、空交集和跨词法作用域版本边界继续拒绝。
SmartBugs versions.csv 只有在 CSV 行、CSV SHA、原始源码 SHA 和当前输入源码完全匹配时才采用。
这是数据集记录的编译版本，不是本轮编译验证。没有任意选 solc，也没有下载或执行新编译器。
无元数据且开放上界的 pragma 不能证明未来版本的 builtin，仍记录 UNKNOWN。

require/assert 的身份与参数表达式分开：只有版本和声明均支持才视为内建；
require(foo()) 中 foo 的副作用仍保留。
send/transfer/call 仍用保守 HAVOC；staticcall 也保守处理，尚不细分只读效应摘要。
旧式 call.value 配置与最后的实际调用严格区分；未知调用不能凭名字视为纯调用。

## 实际发现并修复的问题

已有事件提取器把非内建用户函数 revert() 的 revert_statement 形式当作只有参数读取，
没有留下 HAVOC。即使语义 CFG 已保留普通后继，状态到达定义仍可能跨过该调用。

Stage F 的 extract 现在检查 B1 绑定：确认 NON_BUILTIN 时追加 UNKNOWN_CALL HAVOC；
真内建保留终止语义及参数读取；没有绑定证据则回退。
Stage E 冻结源码没有修改，因此它仍是有已知限制的历史对照。

修复前：review_regression_before.log，1 failed。
修复后：review_tests_after.log，45 passed / 4 warnings。
没有删除断言、改成错误预期或改变训练逻辑。

## 比较口径修正

第一次 F1 比较遗漏了前后均在文件前端失败的 121 个函数行；图和样本没有被删除。
最终加入 F0 原始函数身份并核验总数 6,552（重入 3,404；访问控制 3,148）。
最终结果使用 F1_attempt_002；旧结果保留，不覆盖。

新增恢复函数、READ/WRITE、位置、MAY/UNKNOWN 和旧事实保留在 FINAL_ANALYSIS.json。
本批旧事实丢失 0、新增函数回退 0。测试中的错误绑定反例通过，
不等于真实语料错误绑定率已由独立 ground truth 测得为零。

## 语义参考

require/assert/transfer 的版本边界参考 Solidity 官方
[0.4.10 发布说明](https://www.soliditylang.org/blog/2017/03/15/solidity-0.4.10-release-announcement/)；
继承、可见性参考
[Contracts 文档](https://docs.soliditylang.org/en/v0.5.7/contracts.html)。
本实现选择更小的保守子集，不宣称覆盖该语言文档的全部语义。
