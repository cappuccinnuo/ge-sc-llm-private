# CP4.4 普通修复的逐节点名称对应

输入为 `compile-repair@8739c653` 与 PROMPTS r2.20 §4.6e。生产环境使用已安装的 solc 0.8.38、Slither 0.11.6 和 crytic-compile 0.4.2 编译手写夹具。分数包含按原样比较的 `raw`、主指标、`surviving` 和名称证明 `counter_correspondence`。本批次保留了按原判据停止的移动比较和用户随后确认的最终验收。

## 读取结果

- 两个审查夹具的六个方案有 CP4.3 基线、CP4.4 分数及节点证据。外部目录 `compile-repair-local/cp4_4_v1/review` 保存实际源码和工具输出。review_inputs 对每个文件记录 SHA256。[基线](review_baseline.json) · [新分数](review_scores.json) · [不等节点与跨节点错误](fixture_facts.json)
- 普通夹具的 A、B、C 分别为 7/7、6/7、6/7。B 中只有 k 的表达式发生真实改变。嵌套 switch 的三种方案分别为 16/16、16/16、14/16。注释导致三个节点的源码长度各增加 20 字节，这三项退出推导，其原始 IR 仍相等。错误 case 影响具体表达式和条件节点，exact 为 false。
- 比例性测试使用三个真实函数。损坏和修复均标记三个函数的入口字节，令每个 kept 节点都具有可独立编辑的整数字面量。恢复入口并插入中性函数后为 3/3，分别改动 11、22、33 中的一个后均为 2/3。收据中记录工具结果哈希及原始评分。[比例性](proportionality.json)
- 三组历史重算沿用固定的原始字节、编辑与工具收据，直接读取图。14,196 个精确还原和 114 个文件迁移均匹配。200 项移动中只有 cp3_00291 的指标变化；该样本仍有两处真实创建字节码差异。用户确认只接受这一项已证明差值。剩余 199 项移动逐项匹配。[精确还原](exact_summary.json) · [迁移](migration_summary.json) · [原判据停点](moves_summary.json) · [逐节点和调用比较](movement_difference.json)
- 状态和计数在每条普通分数的 `counter_correspondence` 内。`nodes` 记录最终参与数，以及因结构、冲突、定义、switch 移出的节点数。节点在它首次退出的阶段计一次。identical 表示没有应用改名，出现本地冲突时可同时有移出计数。partial 表示仍有名称通过核验，同时有节点因冲突、定义或 switch 被移出。源码名称碰撞时整项回到原分。是否整图精确还原由 `exact` 单独表示。
- 生产、mando 与 DFG v2 的结果和运行参数位于 suites。历史 22 个错误修复、缺节点对照与两种新跨节点错误均检出。名称交换负例另外验证了反转节点遍历顺序时结果一致。[错误修复](negative.json) · [回归](suites/) · [最后验收](acceptance.json)

## 只读复核

从仓库根运行下列命令核对本批次和交付文件的 SHA256。科学证据清单为 evidence_seal.json，文档检查后的最终清单为 seal.json。

```bash
q=compile_repair/artifacts/cp4_4_v1
pp=/home/zhao/miniconda3/envs/compile-repair-production/bin/python
"$pp" -B "$q/delivery.py" verify
```

## 实验复现

下列命令为随当前版本保存的重算入口。输出文件独占创建，重算使用同级新目录。历史输入的绝对路径须可读。移动比较会对全部 200 项列出差异，并以退出码 2 标记 r2.20 原门槛；本次最终接受范围见 acceptance_authorization.json。重算分数与工具回归可各自执行。

```bash
cd /home/zhao/SmartContract/ge-sc-llm-compile
export PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 CUDA_VISIBLE_DEVICES=""
q=compile_repair/artifacts/cp4_4_v1
dest=$(mktemp -d compile_repair/artifacts/cp4_4_replay_XXXXXX)
cp "$q/replay_scores.py" "$q/negative.py" "$q/probe.py" "$q/review_sources.py" "$dest/"
pp=/home/zhao/miniconda3/envs/compile-repair-production/bin/python
mp=/home/zhao/miniconda3/envs/mando/bin/python
"$pp" -B "$dest/replay_scores.py" exact
"$pp" -B "$dest/replay_scores.py" migration
"$pp" -B "$dest/replay_scores.py" moves
"$pp" -B "$dest/negative.py"
export CP4_OUTPUT="$dest" CP4_SCRATCH=$(mktemp -d)
"$pp" -B compile_repair/artifacts/cp4_v1/run_suite.py production
"$mp" -B compile_repair/artifacts/cp4_v1/run_suite.py mando
"$mp" -B compile_repair/artifacts/cp4_v1/run_suite.py dfg
```

`probe.py capture` 在开发开始时由 CP4.3 评分器运行，保存了两个夹具的原始图和基线。实施后只在原图上运行 `probe.py score`。源文件、版本、两份源码的区间与图身份均可从 review_inputs、review_sources 和对应的 solc、Slither 收据追溯。变更范围、逐函数行数与 354 个 DFG 引用核对见 scope.json。[当前任务授权](authorization.json) · [两项用户决定](acceptance_authorization.json) · [代码范围](scope.json)
