# Stage K：开放pragma的分析范围修复

2026-10-19，Codex。原Stage F/J源码与已封存图不修改；本目录是新版本入口。

## 修复的问题

原分析器将pragma允许的整个区间用于内建调用判断。对于`>=0.5.9`，上界是未限定的未来版本，而已知内建语义表止于0.9.0之前。结果包括：
- revert/selfdestruct等终止调用可能使函数回退；
- 普通require/assert可能被当作未知调用产生HAVOC；
- transfer/send/call等可能被标为UNKNOWN_CALL_VERSION，失去确定外部调用顺序证据；
- modifier的guard绑定确认失败。

这些是新增分析器的保守策略，不是Solidity编译失败；原MANDO的tree-sitter路径没有新增编译要求。

## 当前策略

复用已有分析器声明的语义支持域`[0.4.0, 0.9.0)`。将已核验pragma/版本记录与此域求交，明确记录原区间、分析区间和未覆盖未来区间。

该区间不是作者实际编译版本，也不是宣称每份源码能在区间内所有版本编译。这里只在既有语义子集上分析；不执行solc，不改变源码或pragma。若需要完整语言合法性保证，仍需独立编译器验证。

先执行原前端的证据、作用域和源码检查。因此：
- 缺版本证据、版本记录与pragma冲突、legacy/modern作用域跨度不明仍回退；
- 纯未来版本、无支持区间仍拒绝；
- suicide等具有独立版本窗口的调用不会被一概放开；
- 同名用户函数、函数指针、成员调用及声明绑定保护不变。

`profile.py`实现显式支持域；`pipeline.py`通过局部函数上下文复用Stage J原构图函数体，仅替换SourceView和生产者版本。没有全局monkeypatch，没有复制修改HGT或训练代码。

调用：
```python
from scripts.DFG.state.stage_k.pipeline import prepare_graph
from scripts.DFG.state.stage_j.configuration import DDGConfig
graph, audit = prepare_graph(e2_graph, sources, DDGConfig(recovery="modifiers"), metadata)
```

原HCG可用`add_scalar=True`复用旧标量模块，但本次修复作用于状态分析；已有标量模块的版本判断并未改动。完整原节点、标签、token和CFG/CG保持。use_ddg=False精确复制传入图。

必要回归包括开放范围修复前函数回退/修复后支持、闭区间不变、未来/跨作用域拒绝、旧内建限制及同名用户函数正常后继。测试为静态解析夹具，未执行编译验证。

本轮不为每个小修复分别训练消融。整体实验见`scripts/DFG/experiments/stage_k_pilot/README.md`。
