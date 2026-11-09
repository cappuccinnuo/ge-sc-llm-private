# NodeSem 本机阶段汇总与持续漏报分析（NS-P9，Codex）

本轮完成只读汇总：N-A/N-B/N-C1/N-C2共450次已有正式拟合、900条best/last逐折记录，660条历史重复引用逐位一致；四项指标的等权折均值及样本标准差也与来源逐位一致。新增训练、模型eval、LLM调用、特征均为0。S3m未运行；S4-noG保留真实G0、零HGT层身份。

**当前证据支持保留多个基线候选，不支持把全部持续漏报归结为缺边。** 主终点为重入节点G3R、best、L-audit外层折BF1。S2相对S0o的原预登记Holm p=0.03906；S4相对S0o校正p=0.07422，S4相对S2没有改善；S5相对S4差+0.00814pp、校正p=0.64560。访问控制节点S5去掉10个非SolidiFI误报，却仍漏18/20个正例；S6识别5/20。报告不替用户决定下一基线。

S0o/S2/S4/S6/S5/S8均漏报：重入6个、访问控制15个HCG节点。这不等于21个独立漏洞实例；函数与语句节点、同一行可能覆盖同一漏洞位置。21例均沿用作者原标签，没有通过本轮确立新的金标准。

## 1. 范围、来源与协议

- 依据PROMPTS r29 §5.1/§5.12和EXPERIMENT_POLICY，起始HEAD a5702240；原名original主视图，匿名N-D取消。
- 分组嵌套CV：inner_train训练，inner_val选best，outer_test仅评分。这里是CV外层留出折，不是外部独立测试集。节点按HCG节点、合约按文件计分。
- 合约5折、节点10折、seed=1。四任务分开汇总；best是预定主结果，last辅助且不得择优替换。pooled OOF与等权折均值分表。
- N-A 240、N-B 120、N-C1 30、N-C2 60个正式结果；NS-P6c/6c2/7c诊断只读引用。逐来源SHA见source_inventory.json及各阶段收据。
- N-A的480份best/last权重此前由用户删除。本轮只引用封存预测/收据，未重载或补训，不能声称重新验收了这些已删除权重。
- 用户批准S3m标为未运行、不补训不替代；S4-noG保留G0身份。后者HGT层数0，不同于N-A的G0/S4。

## 2. best主表：等权折均值 ± 样本标准差（%）

S0o=原512维token ID直接Linear；S1o=可训练token嵌入与池化；S2=CodeT5+ CODE；S3=CODE+CTX；S4=CODE+CTX+STATIC（本批封存245维）；S4g为门控融合；S4m为masked CTX，源码仍为原名；S6增加教师向量；S5增加折内学生向量；S8为同初值同训练随机起点的学生向量置换对照。

### 重入合约

|图/配置|Buggy-F1|Macro-F1|Precision|Recall|
|---|---:|---:|---:|---:|
|G0/S0o|95.1016 ± 5.2643|95.1271 ± 5.2475|95.9615 ± 5.7852|94.3810 ± 5.9514|
|G0/S1o|95.9080 ± 1.4393|95.7838 ± 1.5040|93.3333 ± 0.0000|98.6667 ± 2.9814|
|G0/S2|97.8818 ± 3.1811|97.8818 ± 3.1811|97.2381 ± 3.7856|98.5714 ± 3.1944|
|G0/S4|97.1921 ± 2.9741|97.1921 ± 2.9741|97.2381 ± 3.7856|97.2381 ± 3.7856|
|G0/S4-noG|97.2414 ± 1.5421|97.1903 ± 1.5720|96.0000 ± 3.6515|98.6667 ± 2.9814|
|G3R/S0o|94.9188 ± 4.2129|95.0877 ± 3.9714|97.0330 ± 4.0674|92.9524 ± 5.0553|
|G3R/S1o|97.2414 ± 1.5421|97.1903 ± 1.5720|96.0000 ± 3.6515|98.6667 ± 2.9814|
|G3R/S2|97.2348 ± 1.5550|97.1870 ± 1.5737|96.0833 ± 3.5795|98.5714 ± 3.1944|
|G3R/S3|97.2414 ± 1.5421|97.1903 ± 1.5720|96.0000 ± 3.6515|98.6667 ± 2.9814|
|G3R/S4|96.5977 ± 2.3579|96.4696 ± 2.5394|94.8333 ± 5.2836|98.6667 ± 2.9814|
|G3R/S4g|97.1903 ± 1.5746|97.1903 ± 1.5720|97.3333 ± 3.6515|97.2381 ± 3.7856|
|G3R/S4m|96.5517 ± 0.0000|96.4751 ± 0.0700|94.6667 ± 2.9814|98.6667 ± 2.9814|
|G3R/S5|96.5517 ± 0.0000|96.4751 ± 0.0700|94.6667 ± 2.9814|98.6667 ± 2.9814|
|G3R/S6|97.2414 ± 1.5421|97.1903 ± 1.5720|96.0000 ± 3.6515|98.6667 ± 2.9814|
|G3R/S8|95.8588 ± 2.8939|95.7562 ± 3.0124|94.7381 ± 5.3216|97.2381 ± 3.7856|
|G3R/S3m|未运行|未运行|未运行|未运行|

### 访问控制合约

|图/配置|Buggy-F1|Macro-F1|Precision|Recall|
|---|---:|---:|---:|---:|
|G0/S0o|90.1781 ± 6.3092|91.1132 ± 5.4434|100.0000 ± 0.0000|82.5758 ± 10.0789|
|G0/S1o|91.1359 ± 2.9445|91.2121 ± 3.0673|93.1818 ± 7.0255|89.5455 ± 3.4881|
|G0/S2|89.7036 ± 4.7122|89.5106 ± 4.9028|88.4149 ± 6.4353|91.3636 ± 5.9071|
|G0/S4|92.2245 ± 3.3468|92.1060 ± 3.6268|91.7716 ± 5.4700|93.1818 ± 7.0255|
|G0/S4-noG|93.5893 ± 2.4525|93.8584 ± 2.3479|98.1818 ± 4.0656|89.5455 ± 3.4881|
|G3R/S0o|91.8961 ± 6.2196|92.0925 ± 6.4394|94.8485 ± 7.5454|89.3939 ± 7.2664|
|G3R/S1o|92.8750 ± 2.3710|92.9856 ± 2.3255|94.8485 ± 4.7128|91.3636 ± 5.9071|
|G3R/S2|92.9578 ± 2.4789|92.9922 ± 2.3349|93.1818 ± 3.8256|93.1818 ± 7.0255|
|G3R/S3|92.9578 ± 2.4789|92.9922 ± 2.3349|93.1818 ± 3.8256|93.1818 ± 7.0255|
|G3R/S4|92.2245 ± 3.3468|92.1060 ± 3.6268|91.6200 ± 5.4841|93.0303 ± 3.9145|
|G3R/S4g|90.2767 ± 3.5966|90.3868 ± 3.5618|91.0606 ± 0.3388|89.6970 ± 6.8935|
|G3R/S4m|91.0606 ± 0.3388|91.2121 ± 0.1694|92.8788 ± 3.9944|89.5455 ± 3.4881|
|G3R/S5|91.2759 ± 2.7517|91.2332 ± 3.0372|91.6200 ± 5.4841|91.3636 ± 5.9071|
|G3R/S6|92.1607 ± 1.9882|92.0850 ± 2.0009|91.3636 ± 0.4149|93.0303 ± 3.9145|
|G3R/S8|90.6303 ± 1.5184|90.3260 ± 1.9461|88.5431 ± 3.5988|93.0303 ± 3.9145|
|G3R/S3m|未运行|未运行|未运行|未运行|

### 重入节点

|图/配置|Buggy-F1|Macro-F1|Precision|Recall|
|---|---:|---:|---:|---:|
|G0/S0o|99.4203 ± 0.3418|99.3342 ± 0.3273|99.2127 ± 0.4749|99.6296 ± 0.3263|
|G0/S1o|99.3952 ± 0.4974|99.2953 ± 0.5684|99.0948 ± 0.7777|99.6992 ± 0.2989|
|G0/S2|99.7162 ± 0.2609|99.6792 ± 0.2702|99.5701 ± 0.4214|99.8634 ± 0.1772|
|G0/S4|99.7435 ± 0.2145|99.7055 ± 0.2448|99.6265 ± 0.4225|99.8620 ± 0.1773|
|G0/S4-noG|98.1741 ± 0.6996|97.8316 ± 0.6686|96.5210 ± 1.3178|99.8931 ± 0.1701|
|G3R/S0o|99.6247 ± 0.2818|99.5431 ± 0.3701|99.4884 ± 0.5200|99.7628 ± 0.2023|
|G3R/S1o|99.7894 ± 0.2299|99.7482 ± 0.2892|99.7324 ± 0.4229|99.8474 ± 0.2062|
|G3R/S2|99.8265 ± 0.1151|99.8000 ± 0.1233|99.7604 ± 0.2111|99.8931 ± 0.1701|
|G3R/S3|99.8308 ± 0.1441|99.8028 ± 0.1702|99.7829 ± 0.2509|99.8792 ± 0.1661|
|G3R/S4|99.7721 ± 0.1885|99.7347 ± 0.2242|99.6521 ± 0.3396|99.8931 ± 0.1701|
|G3R/S4g|99.7663 ± 0.1384|99.7297 ± 0.1474|99.6533 ± 0.2344|99.8801 ± 0.1770|
|G3R/S4m|99.8437 ± 0.1010|99.8175 ± 0.1120|99.8105 ± 0.1573|99.8773 ± 0.1824|
|G3R/S5|99.7803 ± 0.1538|99.7419 ± 0.1866|99.6683 ± 0.2954|99.8931 ± 0.1701|
|G3R/S6|99.7231 ± 0.2728|99.6823 ± 0.2984|99.5419 ± 0.5521|99.9067 ± 0.1608|
|G3R/S8|99.7198 ± 0.2151|99.6644 ± 0.2774|99.5480 ± 0.4214|99.8931 ± 0.1701|
|G3R/S3m|未运行|未运行|未运行|未运行|

### 访问控制节点

|图/配置|Buggy-F1|Macro-F1|Precision|Recall|
|---|---:|---:|---:|---:|
|G0/S0o|99.3753 ± 0.3460|99.4567 ± 0.3182|99.3880 ± 0.4766|99.3637 ± 0.3715|
|G0/S1o|99.5401 ± 0.2716|99.6078 ± 0.2199|99.6511 ± 0.5009|99.4316 ± 0.3898|
|G0/S2|99.2319 ± 1.2344|99.3233 ± 1.0982|99.0511 ± 2.1699|99.4316 ± 0.3898|
|G0/S4|99.6358 ± 0.2673|99.6841 ± 0.2322|99.8093 ± 0.2693|99.4637 ± 0.3963|
|G0/S4-noG|99.4514 ± 0.5903|99.5247 ± 0.5163|99.4737 ± 0.8994|99.4316 ± 0.3898|
|G3R/S0o|99.4998 ± 0.2182|99.5578 ± 0.2016|99.6380 ± 0.3844|99.3637 ± 0.3715|
|G3R/S1o|99.5388 ± 0.2543|99.6029 ± 0.2197|99.6476 ± 0.3587|99.4316 ± 0.3898|
|G3R/S2|99.5595 ± 0.2334|99.6184 ± 0.2084|99.6894 ± 0.3797|99.4316 ± 0.3898|
|G3R/S3|99.5758 ± 0.3270|99.6329 ± 0.2848|99.6891 ± 0.3865|99.4637 ± 0.3963|
|G3R/S4|99.5074 ± 0.3519|99.5730 ± 0.3049|99.5844 ± 0.4536|99.4316 ± 0.3898|
|G3R/S4g|99.5715 ± 0.3023|99.6299 ± 0.2579|99.7485 ± 0.3316|99.3958 ± 0.3847|
|G3R/S4m|99.5976 ± 0.3168|99.6538 ± 0.2706|99.7100 ± 0.3616|99.4865 ± 0.4300|
|G3R/S5|99.6853 ± 0.2322|99.7277 ± 0.2019|99.9408 ± 0.1252|99.4316 ± 0.3898|
|G3R/S6|99.6691 ± 0.2264|99.7118 ± 0.1985|99.8210 ± 0.2731|99.5191 ± 0.4308|
|G3R/S8|99.5541 ± 0.3250|99.6134 ± 0.2812|99.7106 ± 0.4168|99.3990 ± 0.3808|
|G3R/S3m|未运行|未运行|未运行|未运行|

## 3. last辅助结果与原预登记统计

last完整四指标见last_fold_means.csv；下表为BF1。原标签辅助四指标单列orig_all_fold_metrics.json，不与L-audit混算。

|图/配置|重入合约|访问控制合约|重入节点|访问控制节点|
|---|---:|---:|---:|---:|
|G0/S0o|94.6986 ± 4.2541|85.3723 ± 5.3678|99.3382 ± 0.3662|99.2137 ± 0.5094|
|G0/S1o|95.9540 ± 2.7758|92.9446 ± 2.4756|99.5554 ± 0.3500|99.4885 ± 0.2883|
|G0/S2|95.8128 ± 4.5350|91.3702 ± 3.0905|99.6625 ± 0.3156|99.5086 ± 0.3223|
|G0/S4|96.4514 ± 2.5276|89.3826 ± 2.8331|99.7232 ± 0.2804|99.5699 ± 0.2927|
|G0/S4-noG|97.9310 ± 1.8887|91.2121 ± 0.4149|98.1817 ± 0.7084|99.5875 ± 0.2612|
|G3R/S0o|94.5696 ± 5.0096|80.9302 ± 5.4004|99.7888 ± 0.1413|99.4712 ± 0.3282|
|G3R/S1o|97.2414 ± 1.5421|93.8932 ± 2.4085|99.8226 ± 0.1790|99.5553 ± 0.2473|
|G3R/S2|97.1410 ± 2.9900|91.2187 ± 3.0909|99.8078 ± 0.1721|99.6166 ± 0.2198|
|G3R/S3|97.1410 ± 2.9900|90.9703 ± 3.5369|99.8142 ± 0.1405|99.6027 ± 0.3368|
|G3R/S4|94.4335 ± 3.1136|91.8361 ± 4.0156|99.7562 ± 0.1872|99.5859 ± 0.2732|
|G3R/S4g|97.1410 ± 2.9900|88.2297 ± 3.6690|99.8126 ± 0.1414|99.5681 ± 0.4281|
|G3R/S4m|97.1921 ± 2.9741|88.0883 ± 4.8842|99.8496 ± 0.1177|99.5990 ± 0.3194|
|G3R/S5|96.5025 ± 2.5263|90.1910 ± 5.0778|99.7795 ± 0.1712|99.6858 ± 0.2319|
|G3R/S6|95.8588 ± 2.8939|89.7512 ± 6.5032|99.7348 ± 0.1868|99.6338 ± 0.3044|
|G3R/S8|97.8799 ± 1.9381|89.2424 ± 4.1632|99.7941 ± 0.1590|99.5539 ± 0.2502|

仅原样引用已有主终点检验，来源SciPy均为1.7.3。N-A四项与N-C2两项各自保留Holm家族；N-C1为单一预登记检验，不并入其他家族；N-B只有描述分析。本轮不计算新p值、不合并家族。

|批次|对照|折均差 pp|原p|Holm p|
|---|---|---:|---:|---:|
|NA|S4-S0o|+0.147412|0.03710938|0.07421875|
|NA|S1o-S0o|+0.164628|0.01443282|0.04329847|
|NA|S2-S0o|+0.201793|0.00976562|0.03906250|
|NA|S4-S2|-0.054381|0.22127182|0.22127182|
|NC1|S6-S4|-0.049008|0.95924774|单一检验|
|NC2|S5-S4|+0.008145|0.64560342|0.64560342|
|NC2|S5-S8|+0.060519|0.13683831|0.27367662|

折共享训练样本，标准差不是独立seed的方差；不把p值解释为纯语义贡献。访问控制上的事后改善不能替代预登记主终点。

## 4. 非SolidiFI逐节点表与错误变化

positive_nodes_best/last.csv包含重入32、访问控制20个正例×六配置的预测、概率、source SHA/source_id、HCG ID和fold，共104条宽表。与N-C1 104条、N-C2 312条既有配对记录逐身份和概率浮点值一致。

以下为pooled OOF，不是等权折均值，也不是外部独立测试。

|任务|配置|TP|FP|FN|BF1 %|
|---|---|---:|---:|---:|---:|
|访问控制节点|S0o|0|3|20|0.0000|
|访问控制节点|S2|2|9|18|12.9032|
|访问控制节点|S4|2|10|18|12.5000|
|访问控制节点|S5|2|0|18|18.1818|
|访问控制节点|S6|5|4|15|34.4828|
|访问控制节点|S8|1|7|19|7.1429|
|重入节点|S0o|20|11|12|63.4921|
|重入节点|S2|25|5|7|80.6452|
|重入节点|S4|25|7|7|78.1250|
|重入节点|S5|25|9|7|75.7576|
|重入节点|S6|26|8|6|78.7879|
|重入节点|S8|25|9|7|75.7576|

S5相对S4去掉的10个访问控制误报如下。纠错相对于冻结标签，不等于重新人工证明这些语句绝对安全。

|文件 / HCG ID|函数|原源码行|节点类型|S4概率→S5概率|
|---|---|---|---|---|
|incorrect_constructor_name3.sol / 8500|function withdraw()         public         onlyowner|[29, 29]|expression_statement|0.580176→0.046098|
|multiowned_vulnerable.sol / 3183|function withdrawAll() onlyOwner|[56, 58]|function_definition|0.620863→0.072906|
|mycontract.sol / 11608|function sendTo(address receiver, uint amount) public|[18, 22]|function_definition|0.879167→0.113022|
|mycontract.sol / 11610|function sendTo(address receiver, uint amount) public|[21, 21]|expression_statement|0.944003→0.177330|
|phishable.sol / 7563|function withdrawAll(address _recipient) public|[18, 22]|function_definition|0.986028→0.221727|
|phishable.sol / 7565|function withdrawAll(address _recipient) public|[21, 21]|expression_statement|0.997343→0.350760|
|rubixi.sol / 11394|function collectAllFees() onlyowner|[85, 85]|expression_statement|0.848846→0.007706|
|rubixi.sol / 11404|function collectFeesInEther(uint _amt) onlyowner|[95, 95]|expression_statement|0.683963→0.007441|
|rubixi.sol / 11419|function changeMultiplier(uint _mult) onlyowner|[115, 115]|expression_statement|0.596511→0.003005|
|wallet_02_refund_nosub.sol / 11916|function migrateTo(address to) public|[43, 43]|expression_statement|0.812309→0.012684|

## 5. 持续漏报逐例证据

源码行来自冻结ProjectionView+Projector的精确AST身份映射，raw_lines与作者图预处理后的graph_stored_lines分别保存。G3R消息方向通过冻结materialize检查，REV_*不能当反向执行依赖。两份完整图的跨文件边均为0，因此逐文件路径未遗漏经其他文件的连接。
路径存在不保证执行可行、授权保护或被模型利用；路径大于2跳也不证明完全无相关信息，CODE/CTX或共享声明可能提供其他线索。以下四类仅为附证据的初步判断，多因素可并存。
标签链为8G source_preparation→8C node_label_audit/node_views→8D label_views。21例均非SolidiFI，rule_target=null、C1=orig=1、C2_include=true。这是标签来源核验，不是漏洞真值复核。

### 访问控制节点：FibonacciBalance.sol / 10581

源码SHA：d54dc819f08b71f66ac36b5b5a97edbd66953f60576b14d3ebac115aa6da6c00。类型：expression_statement。函数：function withdraw()。
原源码行[31, 31]；图坐标[[13, 13]]；orig=1，L-audit=1。
初步分类(b)特定语义关系缺口：STATIC已识别delegatecall、state目标和返回值require检查。调用者与同文件FibonacciLib的setFibonacci之间无图路径，库写入对调用者storage上下文的关系也不存在；已有调用→付款一跳CFG。
候选：候选是受限delegatecall目标/存储上下文效果表达；动态目标无法唯一绑定时仍需unknown。
每折inner_train同类型非SolidiFI正例数（fold0–9）：[9, 8, 7, 9, 9, 8, 9, 8, 8, 9]。这是节点类型计数，不是完全相同漏洞模式的样本量。
STATIC/facts：external={"data_class": "other", "kinds": ["delegatecall"], "return_handling": "checked_in_require", "target_classes": ["state"], "uninvoked_call_value": false, "value_attached": false, "value_class": "none"}；state={"array_size_change": false, "reads": [{"auth": false, "shape": "address", "var": "fibonacciLibrary"}, {"auth": false, "shape": "integer", "var": "withdrawalCounter"}], "status": "supported", "writes": []}；order={"call_then_write": false, "dominated_by_ext_call": false, "ext_call_in_loop": false, "pre_ext_call": null, "reachable_from_ext_call": false, "status": "supported", "write_then_call": false}；guard_status=none；fn_summary={}。
全部激活STATIC位：external.kinds=delegatecall, external.target_classes=state, external.value_class=none, external.data_class=other, state.write_count=zero, state.read_count=many, guards.kinds=none, condition.present=true, self_condition.operand_classes=state, self_condition.operand_classes=external_result, external.return_handling=checked_in_require, loop.bound=none, function_ctx.visibility=default, state_decl.shape=not_applicable, state_decl.write_functions=not_applicable, contract_summary.kind=not_applicable。

- fallback delegatecall to library setter（10583→10587）：原始正向不可达；G3R消息路径None，关系[]。
- withdraw delegatecall to library function（10581→10589）：原始正向不可达；G3R消息路径None，关系[]。
- library write to caller storage address（10588→10572）：原始正向不可达；G3R消息路径None，关系[]。
- delegatecall to payout（10581→10582）：原始正向1跳；G3R消息路径[10581, 10582]，关系[['next_line']]。

原语句/函数：

    require(fibonacciLibrary.delegatecall(fibSig, withdrawalCounter));

### 访问控制节点：FibonacciBalance.sol / 10583

源码SHA：d54dc819f08b71f66ac36b5b5a97edbd66953f60576b14d3ebac115aa6da6c00。类型：expression_statement。函数：function() public。
原源码行[38, 38]；图坐标[[17, 17]]；orig=1，L-audit=1。
初步分类(b)特定语义关系缺口：fallback中的delegatecall(msg.data)已被STATIC识别。到同文件库setStart及其写入没有图路径，不能把库中普通状态变量边当成对调用者storage的写入关系。
候选：候选是委托调用的存储上下文，不能无依据把同文件库直接绑定为实际目标。
每折inner_train同类型非SolidiFI正例数（fold0–9）：[9, 8, 7, 9, 9, 8, 9, 8, 8, 9]。这是节点类型计数，不是完全相同漏洞模式的样本量。
STATIC/facts：external={"data_class": "msg.data", "kinds": ["delegatecall"], "return_handling": "checked_in_require", "target_classes": ["state"], "uninvoked_call_value": false, "value_attached": false, "value_class": "none"}；state={"array_size_change": false, "reads": [{"auth": false, "shape": "address", "var": "fibonacciLibrary"}], "status": "supported", "writes": []}；order={"call_then_write": false, "dominated_by_ext_call": false, "ext_call_in_loop": false, "pre_ext_call": null, "reachable_from_ext_call": false, "status": "supported", "write_then_call": false}；guard_status=none；fn_summary={}。
全部激活STATIC位：external.kinds=delegatecall, external.target_classes=state, external.value_class=none, external.data_class=msg.data, state.write_count=zero, state.read_count=one, guards.kinds=none, condition.present=true, self_condition.operand_classes=state, self_condition.operand_classes=external_result, env.merged=msg.data_sig, env.uses=guard, external.return_handling=checked_in_require, loop.bound=none, function_ctx.visibility=public, function_ctx.is_fallback=true, state_decl.shape=not_applicable, state_decl.write_functions=not_applicable, contract_summary.kind=not_applicable。

- fallback delegatecall to library setter（10583→10587）：原始正向不可达；G3R消息路径None，关系[]。
- withdraw delegatecall to library function（10581→10589）：原始正向不可达；G3R消息路径None，关系[]。
- library write to caller storage address（10588→10572）：原始正向不可达；G3R消息路径None，关系[]。
- delegatecall to payout（10581→10582）：原始正向1跳；G3R消息路径[10581, 10582]，关系[['next_line']]。

原语句/函数：

    require(fibonacciLibrary.delegatecall(msg.data));

### 访问控制节点：arbitrary_location_write_simple.sol / 11472

源码SHA：bbbdb5367463fd3d1e11b2c569695d8b4734e3f88fcf937a34469a23121b01ab。类型：expression_statement。函数：function PopBonusCode() public。
原源码行[27, 27]；图坐标[[15, 15]]；orig=1，L-audit=1。
初步分类(d)当前证据无法定位：标注位于 require(0 <= bonusCodes.length)，之后紧邻length--。CFG与状态读写存在，STATIC记录条件的state/literal类别，但没有表示该比较的恒真性、下溢和跨调用存储影响。局部文本仍包含运算符，因此不能称信息从全部输入消失。
候选：候选为数值约束与存储副作用核验；先证实所需语义，再决定边或节点表示。
每折inner_train同类型非SolidiFI正例数（fold0–9）：[9, 8, 7, 9, 9, 8, 9, 8, 8, 9]。这是节点类型计数，不是完全相同漏洞模式的样本量。
STATIC/facts：external={"data_class": "none", "kinds": [], "return_handling": "not_applicable", "target_classes": [], "uninvoked_call_value": false, "value_attached": false, "value_class": "none"}；state={"array_size_change": false, "reads": [{"auth": false, "shape": "array", "var": "bonusCodes"}], "status": "supported", "writes": []}；order={"call_then_write": false, "dominated_by_ext_call": false, "ext_call_in_loop": false, "pre_ext_call": null, "reachable_from_ext_call": false, "status": "supported", "write_then_call": false}；guard_status=none；fn_summary={}。
全部激活STATIC位：external.value_class=none, external.data_class=none, state.write_count=zero, state.read_count=one, state.read_indexed=true, guards.kinds=none, condition.present=true, self_condition.operand_classes=state, self_condition.operand_classes=literal, external.return_handling=not_applicable, loop.bound=none, function_ctx.visibility=public, syntax=literal, state_decl.shape=not_applicable, state_decl.write_functions=not_applicable, contract_summary.kind=not_applicable。

- bound check to decrement（11472→11473）：原始正向1跳；G3R消息路径[11472, 11473]，关系[['next_line']]。
- indexed write to owner storage declaration（11477→11465）：原始正向2跳；G3R消息路径[11477, 11464, 11465]，关系[['WRITES_STATE'], ['next_line']]。

原语句/函数：

    require(0 <= bonusCodes.length);

### 访问控制节点：mapping_write.sol / 12959

源码SHA：a4c6ab0924feb97c929511f65e9f86a82ca5efa307aa29dcae69a21d2fc0fbd6。类型：expression_statement。函数：function set(uint256 key, uint256 value) public。
原源码行[20, 20]；图坐标[[9, 9]]；orig=1，L-audit=1。
初步分类(b)特定语义关系缺口：无守卫的数组下标写已经识别，图可经数组声明和普通next_line到owner声明，但没有数组索引写入可能影响owner存储的别名关系。该普通拓扑连接不等于storage alias证明。
候选：候选为受限存储别名/写入效果；不猜测具体EVM槽位，不把普通相邻边当成别名边。
每折inner_train同类型非SolidiFI正例数（fold0–9）：[9, 8, 7, 9, 9, 8, 9, 8, 8, 9]。这是节点类型计数，不是完全相同漏洞模式的样本量。
STATIC/facts：external={"data_class": "none", "kinds": [], "return_handling": "not_applicable", "target_classes": [], "uninvoked_call_value": false, "value_attached": false, "value_class": "none"}；state={"array_size_change": false, "reads": [], "status": "supported", "writes": [{"auth": false, "shape": "array", "var": "map"}]}；order={"call_then_write": false, "dominated_by_ext_call": false, "ext_call_in_loop": false, "pre_ext_call": null, "reachable_from_ext_call": false, "status": "supported", "write_then_call": false}；guard_status=none；fn_summary={}。
全部激活STATIC位：external.value_class=none, external.data_class=none, state.write_count=one, state.read_count=zero, state.write_indexed=true, guards.kinds=none, external.return_handling=not_applicable, loop.bound=none, function_ctx.visibility=public, syntax=assign, syntax=index, state_decl.shape=not_applicable, state_decl.write_functions=not_applicable, contract_summary.kind=not_applicable。

- array write to owner declaration（12959→12953）：原始正向不可达；G3R消息路径[12959, 12954, 12953]，关系[['WRITES_STATE'], ['next_line']]。
- array write to withdrawal owner guard（12959→12963）：原始正向不可达；G3R消息路径[12959, 12954, 12953, 12963]，关系[['WRITES_STATE'], ['next_line'], ['READS_STATE']]。

原语句/函数：

    map[key] = value;

### 访问控制节点：multiowned_vulnerable.sol / 3174

源码SHA：ee0df823e630dd8fc538222bfb82ad97fd563b9f1185e3eba3d02dfefd812fc6。类型：function_definition。函数：function newOwner(address _owner) external returns (bool)。
原源码行[38, 42]；图坐标[[13, 17]]；orig=1，L-audit=1。
初步分类(c)相关输入存在、同类型正例少：函数摘要已经给出external、auth_write=true、state_write=true、sender_guard=false。到写owners节点有DATA_DEF_USE，写入到modifier检查有状态中转两跳路径；withdrawAll到onlyOwner则没有直接modifier应用边。当前正例的无保护授权写信息并非完全缺失。
候选：先区分函数摘要学习不足与modifier执行缺口；同类型训练正例5–7个不足以单独确定原因。
每折inner_train同类型非SolidiFI正例数（fold0–9）：[6, 5, 7, 6, 6, 7, 6, 7, 7, 5]。这是节点类型计数，不是完全相同漏洞模式的样本量。
STATIC/facts：external={}；state={}；order={}；guard_status=none；fn_summary={"auth_write": true, "call_then_write": false, "delegatecall": false, "ext_call_in_loop": false, "external_call": false, "loop": false, "selfdestruct": false, "sender_guard": false, "state_write": true, "status": "supported", "timestamp": false, "tx_origin": false, "unknown_fields": [], "write_then_call": false}。
全部激活STATIC位：external.value_class=not_applicable, external.data_class=not_applicable, state.write_count=not_applicable, state.read_count=not_applicable, external.return_handling=not_applicable, loop.bound=not_applicable, function_ctx.visibility=external, state_decl.shape=not_applicable, state_decl.write_functions=not_applicable, fn_summary.state_write=true, fn_summary.auth_write=true, contract_summary.kind=not_applicable。

- unprotected entry to owner mapping write（3174→3176）：原始正向1跳；G3R消息路径[3174, 3176]，关系[['DATA_DEF_USE']]。
- owner write to modifier check（3176→3172）：原始正向2跳；G3R消息路径[3176, 3167, 3172]，关系[['WRITES_STATE'], ['READS_STATE']]。
- withdraw entry to modifier（3183→3171）：原始正向不可达；G3R消息路径[3183, 3184, 13272, 3172, 3171]，关系[['next_line'], ['REV_ENV_FLOW'], ['ENV_FLOW'], ['next_line']]。

原语句/函数：

    function newOwner(address _owner) external returns (bool) {
        require(_owner != 0);
        owners[_owner] = msg.sender;
        return true;
      }

### 访问控制节点：proxy.sol / 8854

源码SHA：3016dcfca8050200ae9e64d9bfced9bfb6cb106268c10d714aa13d386c1d1e11。类型：expression_statement。函数：function forward(address callee, bytes _data) public。
原源码行[19, 19]；图坐标[[8, 8]]；orig=1，L-audit=1。
初步分类(c)相关输入存在、同类型正例少：已有param目标的delegatecall、param数据及无守卫事实，public入口到调用为一跳。实际动态callee的执行体未知，不能把未知目标虚构为已绑定函数。
候选：局部敏感调用信息已存在；稀有样本与动态效果均是候选因素，尚不能作因果归因。
每折inner_train同类型非SolidiFI正例数（fold0–9）：[9, 8, 7, 9, 9, 8, 9, 8, 8, 9]。这是节点类型计数，不是完全相同漏洞模式的样本量。
STATIC/facts：external={"data_class": "param", "kinds": ["delegatecall"], "return_handling": "checked_in_require", "target_classes": ["param"], "uninvoked_call_value": false, "value_attached": false, "value_class": "none"}；state={"array_size_change": false, "reads": [], "status": "supported", "writes": []}；order={"call_then_write": false, "dominated_by_ext_call": false, "ext_call_in_loop": false, "pre_ext_call": null, "reachable_from_ext_call": false, "status": "supported", "write_then_call": false}；guard_status=none；fn_summary={}。
全部激活STATIC位：external.kinds=delegatecall, external.target_classes=param, external.value_class=none, external.data_class=param, state.write_count=zero, state.read_count=zero, guards.kinds=none, condition.present=true, self_condition.operand_classes=param, self_condition.operand_classes=external_result, external.return_handling=checked_in_require, loop.bound=none, function_ctx.visibility=public, state_decl.shape=not_applicable, state_decl.write_functions=not_applicable, contract_summary.kind=not_applicable。

- public entry to delegatecall（8853→8854）：原始正向1跳；G3R消息路径[8853, 8854]，关系[['DATA_DEF_USE', 'next_line']]。

原语句/函数：

    require(callee.delegatecall(_data));

### 访问控制节点：rubixi.sol / 11356

源码SHA：a4c33aa1b035feff8e114e5afab6a15e524636d4ea4660459d3b5909272eabed。类型：function_definition。函数：function DynamicPyramid()。
原源码行[23, 25]；图坐标[[9, 11]]；orig=1，L-audit=1。
初步分类(c)相关输入存在、同类型正例少：DynamicPyramid是rubixi里的普通函数，摘要已记录可写授权状态、无sender_guard，且is_constructor=false。入口到creator赋值一跳，creator赋值到onlyowner检查两跳。
候选：不把源码函数名当唯一判据；现有授权写摘要与样本不足分别分析。
每折inner_train同类型非SolidiFI正例数（fold0–9）：[6, 5, 7, 6, 6, 7, 6, 7, 7, 5]。这是节点类型计数，不是完全相同漏洞模式的样本量。
STATIC/facts：external={}；state={}；order={}；guard_status=none；fn_summary={"auth_write": true, "call_then_write": false, "delegatecall": false, "ext_call_in_loop": false, "external_call": false, "loop": false, "selfdestruct": false, "sender_guard": false, "state_write": true, "status": "supported", "timestamp": false, "tx_origin": false, "unknown_fields": [], "write_then_call": false}。
全部激活STATIC位：external.value_class=not_applicable, external.data_class=not_applicable, state.write_count=not_applicable, state.read_count=not_applicable, external.return_handling=not_applicable, loop.bound=not_applicable, function_ctx.visibility=default, state_decl.shape=not_applicable, state_decl.write_functions=not_applicable, fn_summary.state_write=true, fn_summary.auth_write=true, contract_summary.kind=not_applicable。

- public initializer to creator write（11356→11357）：原始正向1跳；G3R消息路径[11356, 11357]，关系[['next_line']]。
- creator write to onlyowner check（11357→11359）：原始正向2跳；G3R消息路径[11357, 11355, 11359]，关系[['WRITES_STATE'], ['READS_STATE']]。
- protected function to modifier（11390→11358）：原始正向不可达；G3R消息路径[11390, 11349, 11358]，关系[['recursive_method_call'], ['recursive_method_call']]。

原语句/函数：

    function DynamicPyramid() {
                     creator = msg.sender; //anyone can call this
             }

### 访问控制节点：rubixi.sol / 11357

源码SHA：a4c33aa1b035feff8e114e5afab6a15e524636d4ea4660459d3b5909272eabed。类型：expression_statement。函数：function DynamicPyramid()。
原源码行[24, 24]；图坐标[[10, 10]]；orig=1，L-audit=1。
初步分类(c)相关输入存在、同类型正例少：creator=msg.sender已标记auth=true的状态写，既没有modifier也没有sender_guard；到onlyowner读取两跳。
候选：相关局部事实已存在，同类型训练正例7–9个；模型未利用或被其他信号掩盖尚无法区分。
每折inner_train同类型非SolidiFI正例数（fold0–9）：[9, 8, 7, 9, 9, 8, 9, 8, 8, 9]。这是节点类型计数，不是完全相同漏洞模式的样本量。
STATIC/facts：external={"data_class": "none", "kinds": [], "return_handling": "not_applicable", "target_classes": [], "uninvoked_call_value": false, "value_attached": false, "value_class": "none"}；state={"array_size_change": false, "reads": [], "status": "supported", "writes": [{"auth": true, "shape": "address", "var": "creator"}]}；order={"call_then_write": false, "dominated_by_ext_call": false, "ext_call_in_loop": false, "pre_ext_call": null, "reachable_from_ext_call": false, "status": "supported", "write_then_call": false}；guard_status=none；fn_summary={}。
全部激活STATIC位：external.value_class=none, external.data_class=none, state.write_count=one, state.read_count=zero, state.write_scalar=true, state.write_auth=true, guards.kinds=none, env.merged=msg.sender, env.uses=state, external.return_handling=not_applicable, loop.bound=none, function_ctx.visibility=default, syntax=assign, state_decl.shape=not_applicable, state_decl.write_functions=not_applicable, contract_summary.kind=not_applicable。

- public initializer to creator write（11356→11357）：原始正向1跳；G3R消息路径[11356, 11357]，关系[['next_line']]。
- creator write to onlyowner check（11357→11359）：原始正向2跳；G3R消息路径[11357, 11355, 11359]，关系[['WRITES_STATE'], ['READS_STATE']]。
- protected function to modifier（11390→11358）：原始正向不可达；G3R消息路径[11390, 11349, 11358]，关系[['recursive_method_call'], ['recursive_method_call']]。

原语句/函数：

    creator = msg.sender;

### 访问控制节点：simple_suicide.sol / 12756

源码SHA：07ab4f0b502c4d91859f2446f4dd3edf8330000c9e21ddb9940bb70580526300。类型：function_definition。函数：function sudicideAnyone()。
原源码行[12, 14]；图坐标[[3, 5]]；orig=1，L-audit=1。
初步分类(c)相关输入存在、同类型正例少：函数摘要有selfdestruct=true、external_call=true、sender_guard=false，函数到selfdestruct一跳；不需要额外跨函数路径才能看见这一局部模式。
候选：检查稀有危险操作与无保护模式的表示；不能默认更多边能解决。
每折inner_train同类型非SolidiFI正例数（fold0–9）：[6, 5, 7, 6, 6, 7, 6, 7, 7, 5]。这是节点类型计数，不是完全相同漏洞模式的样本量。
STATIC/facts：external={}；state={}；order={}；guard_status=none；fn_summary={"auth_write": false, "call_then_write": false, "delegatecall": false, "ext_call_in_loop": false, "external_call": true, "loop": false, "selfdestruct": true, "sender_guard": false, "state_write": false, "status": "supported", "timestamp": false, "tx_origin": false, "unknown_fields": [], "write_then_call": false}。
全部激活STATIC位：external.value_class=not_applicable, external.data_class=not_applicable, state.write_count=not_applicable, state.read_count=not_applicable, external.return_handling=not_applicable, loop.bound=not_applicable, function_ctx.visibility=default, state_decl.shape=not_applicable, state_decl.write_functions=not_applicable, fn_summary.external_call=true, fn_summary.selfdestruct=true, contract_summary.kind=not_applicable。

- public entry to selfdestruct（12756→12757）：原始正向1跳；G3R消息路径[12756, 12757]，关系[['next_line']]。

原语句/函数：

    function sudicideAnyone() {
        selfdestruct(msg.sender);
      }

### 访问控制节点：simple_suicide.sol / 12757

源码SHA：07ab4f0b502c4d91859f2446f4dd3edf8330000c9e21ddb9940bb70580526300。类型：expression_statement。函数：function sudicideAnyone()。
原源码行[13, 13]；图坐标[[4, 4]]；orig=1，L-audit=1。
初步分类(c)相关输入存在、同类型正例少：selfdestruct(msg.sender)及无守卫已在STATIC中，入口CFG与msg.sender环境边存在。
候选：目前没有证据把该漏报归因于缺失跨函数语义。
每折inner_train同类型非SolidiFI正例数（fold0–9）：[9, 8, 7, 9, 9, 8, 9, 8, 8, 9]。这是节点类型计数，不是完全相同漏洞模式的样本量。
STATIC/facts：external={"data_class": "none", "kinds": ["selfdestruct"], "return_handling": "ignored", "target_classes": ["msg.sender"], "uninvoked_call_value": false, "value_attached": false, "value_class": "none"}；state={"array_size_change": false, "reads": [], "status": "supported", "writes": []}；order={"call_then_write": false, "dominated_by_ext_call": false, "ext_call_in_loop": false, "pre_ext_call": null, "reachable_from_ext_call": false, "status": "supported", "write_then_call": false}；guard_status=none；fn_summary={}。
全部激活STATIC位：external.kinds=selfdestruct, external.target_classes=msg.sender, external.value_class=none, external.data_class=none, state.write_count=zero, state.read_count=zero, guards.kinds=none, env.merged=msg.sender, env.uses=call, external.return_handling=ignored, loop.bound=none, function_ctx.visibility=default, state_decl.shape=not_applicable, state_decl.write_functions=not_applicable, contract_summary.kind=not_applicable。

- public entry to selfdestruct（12756→12757）：原始正向1跳；G3R消息路径[12756, 12757]，关系[['next_line']]。

原语句/函数：

    selfdestruct(msg.sender);

### 访问控制节点：unprotected0.sol / 10847

源码SHA：8cfc8702a1a0afe407c2ea83e0c48e97909f66af1955ee5e1321f1dc2818a045。类型：function_definition。函数：function changeOwner(address _newOwner)          public。
原源码行[25, 29]；图坐标[[13, 17]]；orig=1，L-audit=1。
初步分类(c)相关输入存在、同类型正例少：changeOwner没有使用源码中已定义的onlyowner，摘要auth_write=true且has_modifier=false。入口到owner赋值一跳；与未使用modifier共享合约形成两跳连接，但这种连接不表示它受modifier保护。
候选：需要区分普通连接与实际保护关系；当前摘要已具有无保护写信息。
每折inner_train同类型非SolidiFI正例数（fold0–9）：[6, 5, 7, 6, 6, 7, 6, 7, 7, 5]。这是节点类型计数，不是完全相同漏洞模式的样本量。
STATIC/facts：external={}；state={}；order={}；guard_status=none；fn_summary={"auth_write": true, "call_then_write": false, "delegatecall": false, "ext_call_in_loop": false, "external_call": false, "loop": false, "selfdestruct": false, "sender_guard": false, "state_write": true, "status": "supported", "timestamp": false, "tx_origin": false, "unknown_fields": [], "write_then_call": false}。
全部激活STATIC位：external.value_class=not_applicable, external.data_class=not_applicable, state.write_count=not_applicable, state.read_count=not_applicable, external.return_handling=not_applicable, loop.bound=not_applicable, function_ctx.visibility=public, state_decl.shape=not_applicable, state_decl.write_functions=not_applicable, fn_summary.state_write=true, fn_summary.auth_write=true, contract_summary.kind=not_applicable。

- public entry to owner write（10847→10848）：原始正向1跳；G3R消息路径[10847, 10848]，关系[['DATA_DEF_USE', 'next_line']]。
- unprotected function to unused modifier（10847→10842）：原始正向不可达；G3R消息路径[10847, 10840, 10842]，关系[['recursive_method_call'], ['recursive_method_call']]。

原语句/函数：

    function changeOwner(address _newOwner)
             public
         {
            owner = _newOwner;
         }

### 访问控制节点：wallet_02_refund_nosub.sol / 11913

源码SHA：3bf849eea5a234dcf2755aa526f934b3edfa560ee7eac3d70385887e3bc6ff79。类型：expression_statement。函数：function refund() public。
原源码行[36, 36]；图坐标[[18, 18]]；orig=1，L-audit=1。
初步分类(d)当前证据无法定位：refund转出balances且函数内没有对应扣减，STATIC识别state金额transfer。到deposit和另一个withdraw内的写入均有共享声明两跳路径；这不能表达refund必须扣减余额的跨交易不变量，也不能据此将它判为安全。
候选：候选为状态更新完整性与多次调用语义；不能把缺失更新转成一条虚构写入边。
每折inner_train同类型非SolidiFI正例数（fold0–9）：[9, 8, 7, 9, 9, 8, 9, 8, 8, 9]。这是节点类型计数，不是完全相同漏洞模式的样本量。
STATIC/facts：external={"data_class": "none", "kinds": ["transfer"], "return_handling": "ignored", "target_classes": ["msg.sender"], "uninvoked_call_value": false, "value_attached": true, "value_class": "state"}；state={"array_size_change": false, "reads": [{"auth": false, "shape": "mapping", "var": "balances"}], "status": "supported", "writes": []}；order={"call_then_write": false, "dominated_by_ext_call": false, "ext_call_in_loop": false, "pre_ext_call": null, "reachable_from_ext_call": false, "status": "supported", "write_then_call": false}；guard_status=none；fn_summary={}。
全部激活STATIC位：external.kinds=transfer, external.value_attached=true, external.target_classes=msg.sender, external.value_class=state, external.data_class=none, state.write_count=zero, state.read_count=one, state.read_indexed=true, guards.kinds=none, env.merged=msg.sender, env.uses=call, external.return_handling=ignored, loop.bound=none, function_ctx.visibility=public, syntax=index, syntax=deep_member, state_decl.shape=not_applicable, state_decl.write_functions=not_applicable, contract_summary.kind=not_applicable。

- refund to deposit write through shared state（11913→11907）：原始正向不可达；G3R消息路径[11913, 11902, 11907]，关系[['REV_READS_STATE'], ['READS_STATE', 'REV_WRITES_STATE']]。
- refund to different function balance debit（11913→11911）：原始正向不可达；G3R消息路径[11913, 11902, 11911]，关系[['REV_READS_STATE'], ['READS_STATE', 'REV_WRITES_STATE']]。

原语句/函数：

    msg.sender.transfer(balances[msg.sender]);

### 访问控制节点：wallet_03_wrong_constructor.sol / 7893

源码SHA：6f5e18f2dbfb404c4bece60b475d17bd49d66ad3da34cffee8a47f7326ae0aa9。类型：function_definition。函数：function initWallet() public。
原源码行[19, 21]；图坐标[[5, 7]]；orig=1，L-audit=1。
初步分类(c)相关输入存在、同类型正例少：initWallet是public普通函数，is_constructor=false，摘要auth_write=true、sender_guard=false，入口到creator赋值一跳。
候选：函数是否可重复调用的局部线索已在输入；需与样本稀缺分开评估。
每折inner_train同类型非SolidiFI正例数（fold0–9）：[6, 5, 7, 6, 6, 7, 6, 7, 7, 5]。这是节点类型计数，不是完全相同漏洞模式的样本量。
STATIC/facts：external={}；state={}；order={}；guard_status=none；fn_summary={"auth_write": true, "call_then_write": false, "delegatecall": false, "ext_call_in_loop": false, "external_call": false, "loop": false, "selfdestruct": false, "sender_guard": false, "state_write": true, "status": "supported", "timestamp": false, "tx_origin": false, "unknown_fields": [], "write_then_call": false}。
全部激活STATIC位：external.value_class=not_applicable, external.data_class=not_applicable, state.write_count=not_applicable, state.read_count=not_applicable, external.return_handling=not_applicable, loop.bound=not_applicable, function_ctx.visibility=public, state_decl.shape=not_applicable, state_decl.write_functions=not_applicable, fn_summary.state_write=true, fn_summary.auth_write=true, contract_summary.kind=not_applicable。

- public initializer to creator write（7893→7894）：原始正向1跳；G3R消息路径[7893, 7894]，关系[['next_line']]。
- creator write to migration guard（7894→7903）：原始正向2跳；G3R消息路径[7894, 7891, 7903]，关系[['WRITES_STATE'], ['READS_STATE']]。

原语句/函数：

    function initWallet() public {
             creator = msg.sender;
         }

### 访问控制节点：wallet_03_wrong_constructor.sol / 7894

源码SHA：6f5e18f2dbfb404c4bece60b475d17bd49d66ad3da34cffee8a47f7326ae0aa9。类型：expression_statement。函数：function initWallet() public。
原源码行[20, 20]；图坐标[[6, 6]]；orig=1，L-audit=1。
初步分类(c)相关输入存在、同类型正例少：creator=msg.sender已识别授权状态写且无守卫；到migrateTo授权检查两跳状态关系。
候选：不是所有持续漏报都需要新边；本例已有相关状态与权限事实。
每折inner_train同类型非SolidiFI正例数（fold0–9）：[9, 8, 7, 9, 9, 8, 9, 8, 8, 9]。这是节点类型计数，不是完全相同漏洞模式的样本量。
STATIC/facts：external={"data_class": "none", "kinds": [], "return_handling": "not_applicable", "target_classes": [], "uninvoked_call_value": false, "value_attached": false, "value_class": "none"}；state={"array_size_change": false, "reads": [], "status": "supported", "writes": [{"auth": true, "shape": "address", "var": "creator"}]}；order={"call_then_write": false, "dominated_by_ext_call": false, "ext_call_in_loop": false, "pre_ext_call": null, "reachable_from_ext_call": false, "status": "supported", "write_then_call": false}；guard_status=none；fn_summary={}。
全部激活STATIC位：external.value_class=none, external.data_class=none, state.write_count=one, state.read_count=zero, state.write_scalar=true, state.write_auth=true, guards.kinds=none, env.merged=msg.sender, env.uses=state, external.return_handling=not_applicable, loop.bound=none, function_ctx.visibility=public, syntax=assign, state_decl.shape=not_applicable, state_decl.write_functions=not_applicable, contract_summary.kind=not_applicable。

- public initializer to creator write（7893→7894）：原始正向1跳；G3R消息路径[7893, 7894]，关系[['next_line']]。
- creator write to migration guard（7894→7903）：原始正向2跳；G3R消息路径[7894, 7891, 7903]，关系[['WRITES_STATE'], ['READS_STATE']]。

原语句/函数：

    creator = msg.sender;

### 访问控制节点：wallet_04_confused_sign.sol / 9865

源码SHA：5ec3d85c76b1f1a15ec1295085087f1d969742bdc2aaf9c6fb1a79bfffa8735d。类型：expression_statement。函数：function withdraw(uint256 amount) public。
原源码行[30, 30]；图坐标[[13, 13]]；orig=1，L-audit=1。
初步分类(d)当前证据无法定位：源码使用amount >= balances[msg.sender]，与付款和扣减节点分别相距一、两跳。STATIC只保留条件存在及参与者类别，没有专门比较方向位；CODE/CTX文本仍包含>=。
候选：可能需要精细数值条件表示，也可能是学习问题；现有证据不能区分，不修改本批特征。
每折inner_train同类型非SolidiFI正例数（fold0–9）：[9, 8, 7, 9, 9, 8, 9, 8, 8, 9]。这是节点类型计数，不是完全相同漏洞模式的样本量。
STATIC/facts：external={"data_class": "none", "kinds": [], "return_handling": "not_applicable", "target_classes": [], "uninvoked_call_value": false, "value_attached": false, "value_class": "none"}；state={"array_size_change": false, "reads": [{"auth": false, "shape": "mapping", "var": "balances"}], "status": "supported", "writes": []}；order={"call_then_write": false, "dominated_by_ext_call": false, "ext_call_in_loop": false, "pre_ext_call": null, "reachable_from_ext_call": false, "status": "supported", "write_then_call": false}；guard_status=none；fn_summary={}。
全部激活STATIC位：external.value_class=none, external.data_class=none, state.write_count=zero, state.read_count=one, state.read_indexed=true, guards.kinds=none, condition.present=true, self_condition.operand_classes=msg.sender, self_condition.operand_classes=state, self_condition.operand_classes=param, env.merged=msg.sender, env.uses=guard, external.return_handling=not_applicable, loop.bound=none, function_ctx.visibility=public, syntax=index, state_decl.shape=not_applicable, state_decl.write_functions=not_applicable, contract_summary.kind=not_applicable。

- comparison to payout（9865→9866）：原始正向1跳；G3R消息路径[9865, 9866]，关系[['next_line']]。
- comparison to balance debit（9865→9867）：原始正向2跳；G3R消息路径[9865, 9866, 9867]，关系[['next_line'], ['next_line']]。

原语句/函数：

    require(amount >= balances[msg.sender]);

### 重入节点：etherbank.sol / 15759

源码SHA：63d14a7dd1a1f2f6f5cdc04be0c509606012af3742dff18a671519c56a63ec36。类型：expression_statement。函数：function withdrawBalance()。
原源码行[21, 21]；图坐标[[12, 12]]；orig=1，L-audit=1。
初步分类(a)标签位置/范围待审：标签继承作者行级投影。调用和 throw 同在原源码第21行，正例同时落到内层 throw；该节点本身不是外部调用。可见调用条件→throw 的 CFG 边，不能把其漏报直接等同于漏掉一次独立攻击，也不能据此擅改标签。order.status 为 unknown。
候选：先复核语句级评价位置；不需要据此直接增加关系。
每折inner_train同类型非SolidiFI正例数（fold0–9）：[3, 2, 4, 2, 3, 5, 3, 2, 2, 2]。这是节点类型计数，不是完全相同漏洞模式的样本量。
STATIC/facts：external={"data_class": "none", "kinds": [], "return_handling": "not_applicable", "target_classes": [], "uninvoked_call_value": false, "value_attached": false, "value_class": "none"}；state={"array_size_change": false, "reads": [], "status": "supported", "writes": []}；order={"call_then_write": false, "dominated_by_ext_call": false, "ext_call_in_loop": false, "pre_ext_call": null, "reachable_from_ext_call": false, "status": "unknown", "write_then_call": false}；guard_status=present；fn_summary={}。
全部激活STATIC位：external.value_class=none, external.data_class=none, state.write_count=zero, state.read_count=zero, guards.kinds=if_branch, guards.operands=msg.sender, guards.operands=local, guards.operands=external_result, external.return_handling=not_applicable, loop.bound=none, function_ctx.visibility=default, syntax=exit, state_decl.shape=not_applicable, state_decl.write_functions=not_applicable, contract_summary.kind=not_applicable, unknown.order=true。

- call condition to throw（15757→15759）：原始正向1跳；G3R消息路径[15757, 15759]，关系[['pos_next']]。
- call condition to later balance clear（15757→15760）：原始正向2跳；G3R消息路径[15757, 15758, 15760]，关系[['neg_next'], ['next_line']]。

原语句/函数：

    throw;

### 重入节点：modifier_reentrancy.sol / 8498

源码SHA：5675bc25a679e6e3cae0252605b00ab569a66757e91fbcf8873b5994960cbef7。类型：function_definition。函数：function airDrop() hasNoBalance supportsToken  public。
原源码行[15, 17]；图坐标[[5, 7]]；orig=1，L-audit=1。
初步分类(b)特定语义关系缺口：airDrop 的头部有两个 modifier；支持检查包含外部调用，攻击合约中也有回调。图里存在函数级调用边和经 ENV_SOURCE 的两跳连接，但没有 airDrop→modifier 的显式应用/执行顺序关系。函数摘要 external_call=false，说明摘要没有合成 modifier 的外部调用效果。相同函数类型正例在 inner_train 只有0–1个。
候选：候选是受限 modifier 应用与调用效果摘要；不能称节点在图中完全不连通。
每折inner_train同类型非SolidiFI正例数（fold0–9）：[0, 0, 1, 1, 1, 0, 1, 1, 1, 1]。这是节点类型计数，不是完全相同漏洞模式的样本量。
STATIC/facts：external={}；state={}；order={}；guard_status=none；fn_summary={"auth_write": false, "call_then_write": false, "delegatecall": false, "ext_call_in_loop": false, "external_call": false, "loop": false, "selfdestruct": false, "sender_guard": true, "state_write": true, "status": "supported", "timestamp": false, "tx_origin": false, "unknown_fields": [], "write_then_call": false}。
全部激活STATIC位：external.value_class=not_applicable, external.data_class=not_applicable, state.write_count=not_applicable, state.read_count=not_applicable, external.return_handling=not_applicable, loop.bound=not_applicable, function_ctx.visibility=public, function_ctx.has_modifier=true, state_decl.shape=not_applicable, state_decl.write_functions=not_applicable, fn_summary.state_write=true, fn_summary.sender_guard=true, contract_summary.kind=not_applicable。

- airDrop to supportsToken modifier（8498→8500）：原始正向不可达；G3R消息路径[8498, 8511, 8500]，关系[['external_call'], ['internal_call']]。
- modifier check to body write（8501→8499）：原始正向不可达；G3R消息路径[8501, 18485, 8499]，关系[['REV_ENV_FLOW'], ['ENV_FLOW']]。
- callback callsite to airDrop（8515→8498）：原始正向不可达；G3R消息路径[8515, 18485, 8499, 8498]，关系[['REV_ENV_FLOW'], ['ENV_FLOW'], ['next_line']]。
- callback function to airDrop（8511→8498）：原始正向1跳；G3R消息路径[8511, 8498]，关系[['external_call']]。

原语句/函数：

    function airDrop() hasNoBalance supportsToken  public{
        tokenBalance[msg.sender] += 20;
      }

### 重入节点：reentrancy_bonus.sol / 12

源码SHA：628f60b16c878d8dfe5a271a26f6a83574fbeaae27a62a059467dab8974db332。类型：expression_statement。函数：function getFirstWithdrawalBonus(address recipient) public。
原源码行[28, 28]；图坐标[[15, 15]]；orig=1，L-audit=1。
初步分类(b)特定语义关系缺口：withdrawReward 内有外部调用，调用者随后写 claimedBonus。已有 caller 9→callee 4 的 internal_call；调用点12到callee4为两跳，callee外部调用7到后续写13为三跳。节点12的 external.kinds 为空、call_then_write=false；缺少调用效果及跨函数返回后顺序的显式表达。
候选：候选是调用点绑定及受限被调函数效果/返回后依赖；三跳只是当前两层消息传递的路径限制，不证明加边必然提升。
每折inner_train同类型非SolidiFI正例数（fold0–9）：[3, 2, 4, 2, 3, 5, 3, 2, 2, 2]。这是节点类型计数，不是完全相同漏洞模式的样本量。
STATIC/facts：external={"data_class": "none", "kinds": [], "return_handling": "not_applicable", "target_classes": [], "uninvoked_call_value": false, "value_attached": false, "value_class": "none"}；state={"array_size_change": false, "reads": [], "status": "supported", "writes": []}；order={"call_then_write": false, "dominated_by_ext_call": false, "ext_call_in_loop": false, "pre_ext_call": null, "reachable_from_ext_call": false, "status": "supported", "write_then_call": false}；guard_status=present；fn_summary={}。
全部激活STATIC位：external.value_class=none, external.data_class=none, state.write_count=zero, state.read_count=zero, guards.kinds=require, guards.operands=state, guards.operands=param, external.return_handling=not_applicable, loop.bound=none, function_ctx.visibility=public, state_decl.shape=not_applicable, state_decl.write_functions=not_applicable, contract_summary.kind=not_applicable。

- callsite to callee（12→4）：原始正向不可达；G3R消息路径[12, 9, 4]，关系[['REV_DATA_DEF_USE'], ['internal_call']]。
- caller function to callee（9→4）：原始正向1跳；G3R消息路径[9, 4]，关系[['internal_call']]。
- callee external call to caller post-call write（7→13）：原始正向不可达；G3R消息路径[7, 4, 9, 13]，关系[['REV_DATA_DEF_USE'], ['internal_call'], ['DATA_DEF_USE']]。

原语句/函数：

    withdrawReward(recipient);

### 重入节点：reentrancy_dao.sol / 8315

源码SHA：e507ae792671a38307734b38b8d35abf062a7e78889e0178f8647838a2527dd2。类型：new_variable。函数：function withdrawAll() public。
原源码行[18, 18]；图坐标[[9, 9]]；orig=1，L-audit=1。
初步分类(c)相关输入存在、同类型正例少：调用本身已被识别，金额来自local，assigned_checked、call_then_write=true；到清零节点8317有两跳CFG/DATA_DEF_USE路径。各折同类型非SolidiFI正例仅1–4个。这不支持把漏报直接归因于缺少局部调用后写信息。
候选：检查稀有模式与表示学习；小样本只是描述证据，不能确认为训练不足的因果解释。
每折inner_train同类型非SolidiFI正例数（fold0–9）：[3, 2, 3, 3, 3, 3, 2, 3, 4, 1]。这是节点类型计数，不是完全相同漏洞模式的样本量。
STATIC/facts：external={"data_class": "none", "kinds": ["call"], "return_handling": "assigned_checked", "target_classes": ["msg.sender"], "uninvoked_call_value": false, "value_attached": true, "value_class": "local"}；state={"array_size_change": false, "reads": [], "status": "supported", "writes": []}；order={"call_then_write": true, "dominated_by_ext_call": false, "ext_call_in_loop": false, "pre_ext_call": null, "reachable_from_ext_call": false, "status": "supported", "write_then_call": false}；guard_status=present；fn_summary={}。
全部激活STATIC位：external.kinds=call, external.value_attached=true, external.target_classes=msg.sender, external.value_class=local, external.data_class=none, state.write_count=zero, state.read_count=zero, order.call_then_write=true, guards.kinds=if_branch, guards.operands=local, guards.operands=literal, env.merged=msg.sender, env.uses=call, external.return_handling=assigned_checked, loop.bound=none, function_ctx.visibility=public, syntax=deep_member, state_decl.shape=not_applicable, state_decl.write_functions=not_applicable, contract_summary.kind=not_applicable。

- external call to balance clear（8315→8317）：原始正向2跳；G3R消息路径[8315, 8316, 8317]，关系[['DATA_DEF_USE', 'next_line'], ['next_line']]。

原语句/函数：

    bool callResult = msg.sender.call.value(oCredit)();

### 重入节点：spank_chain_payment.sol / 12958

源码SHA：15724a9aecd227749e4e3441bf408892ead6639d7c2830b116014183fb537d09。类型：expression_statement。函数：function LCOpenTimeout(bytes32 _lcID) public。
原源码行[426, 426]；图坐标[[293, 293]]；orig=1，L-audit=1。
初步分类(d)当前证据无法定位：ETH transfer 与后续 delete 均在原源码，STATIC已标记 call_then_write。到delete12962的两跳最短消息路径经函数参数DATA_DEF_USE形成，并非专门顺序边。需结合回调可执行性与调用类型判断，现有证据不足以定位失败原因。
候选：保留投影/状态诊断 unknown 与原标签；本轮不判断实际可利用性。
每折inner_train同类型非SolidiFI正例数（fold0–9）：[3, 2, 4, 2, 3, 5, 3, 2, 2, 2]。这是节点类型计数，不是完全相同漏洞模式的样本量。
STATIC/facts：external={"data_class": "none", "kinds": ["transfer"], "return_handling": "ignored", "target_classes": ["literal", "param", "state"], "uninvoked_call_value": false, "value_attached": true, "value_class": "state"}；state={"array_size_change": false, "reads": [{"auth": false, "shape": "mapping", "var": "Channels"}], "status": "supported", "writes": []}；order={"call_then_write": true, "dominated_by_ext_call": false, "ext_call_in_loop": false, "pre_ext_call": null, "reachable_from_ext_call": false, "status": "supported", "write_then_call": false}；guard_status=present；fn_summary={}。
全部激活STATIC位：external.kinds=transfer, external.value_attached=true, external.target_classes=param, external.target_classes=state, external.target_classes=literal, external.value_class=state, external.data_class=none, state.write_count=zero, state.read_count=one, state.read_indexed=true, order.call_then_write=true, guards.kinds=require, guards.kinds=if_branch, guards.operands=msg.sender, guards.operands=state, guards.operands=param, guards.operands=literal, guards.operands=timestamp, external.return_handling=ignored, loop.bound=none, function_ctx.visibility=public, syntax=index, syntax=literal, state_decl.shape=not_applicable, state_decl.write_functions=not_applicable, contract_summary.kind=not_applicable, unknown.projection=true。

- caller to stored token transfer target（12953→12891）：原始正向1跳；G3R消息路径[12953, 12891]，关系[['external_call']]。
- token callsite to stored transfer function（12961→12891）：原始正向不可达；G3R消息路径[12961, 12953, 12891]，关系[['REV_DATA_DEF_USE'], ['external_call']]。
- ETH transfer to channel deletion（12958→12962）：原始正向不可达；G3R消息路径[12958, 12953, 12962]，关系[['REV_DATA_DEF_USE'], ['DATA_DEF_USE']]。
- token transfer to channel deletion（12961→12962）：原始正向不可达；G3R消息路径[12961, 12953, 12962]，关系[['REV_DATA_DEF_USE'], ['DATA_DEF_USE']]。

原语句/函数：

    Channels[_lcID].partyAddresses[0].transfer(Channels[_lcID].ethBalances[0]);

### 重入节点：spank_chain_payment.sol / 12961

源码SHA：15724a9aecd227749e4e3441bf408892ead6639d7c2830b116014183fb537d09。类型：expression_statement。函数：function LCOpenTimeout(bytes32 _lcID) public。
原源码行[430, 430]；图坐标[[296, 296]]；orig=1，L-audit=1。
初步分类(d)当前证据无法定位：这是 token.transfer 调用，存在函数级 external_call 到12891，也有到delete的两跳消息路径。已有 facts 将它归入 transfer 且 value_attached=true，与12958原生金额转账共用粗类别；两类调用语义不可仅凭同名方法等同。发送者身份比较在结构成员访问上未识别为 sender_guard，且有投影诊断。
候选：候选是调用接收者类型和受限结构成员守卫的正确性核验；当前无法证明它们造成漏报，不能立即改本批输入。
每折inner_train同类型非SolidiFI正例数（fold0–9）：[3, 2, 4, 2, 3, 5, 3, 2, 2, 2]。这是节点类型计数，不是完全相同漏洞模式的样本量。
STATIC/facts：external={"data_class": "none", "kinds": ["transfer"], "return_handling": "checked_in_require", "target_classes": ["param", "state"], "uninvoked_call_value": false, "value_attached": true, "value_class": "state"}；state={"array_size_change": false, "reads": [{"auth": false, "shape": "mapping", "var": "Channels"}], "status": "supported", "writes": []}；order={"call_then_write": true, "dominated_by_ext_call": false, "ext_call_in_loop": false, "pre_ext_call": {"node": 12958, "offset": -2}, "reachable_from_ext_call": true, "status": "supported", "write_then_call": false}；guard_status=present；fn_summary={}。
全部激活STATIC位：external.kinds=transfer, external.value_attached=true, external.target_classes=param, external.target_classes=state, external.value_class=state, external.data_class=none, state.write_count=zero, state.read_count=one, state.read_indexed=true, order.reachable_from_ext_call=true, order.call_then_write=true, guards.kinds=require, guards.kinds=if_branch, guards.operands=msg.sender, guards.operands=state, guards.operands=param, guards.operands=literal, guards.operands=timestamp, condition.present=true, self_condition.operand_classes=state, self_condition.operand_classes=param, self_condition.operand_classes=literal, self_condition.operand_classes=external_result, external.return_handling=checked_in_require, loop.bound=none, function_ctx.visibility=public, syntax=index, syntax=deep_member, syntax=literal, state_decl.shape=not_applicable, state_decl.write_functions=not_applicable, contract_summary.kind=not_applicable, unknown.projection=true。

- caller to stored token transfer target（12953→12891）：原始正向1跳；G3R消息路径[12953, 12891]，关系[['external_call']]。
- token callsite to stored transfer function（12961→12891）：原始正向不可达；G3R消息路径[12961, 12953, 12891]，关系[['REV_DATA_DEF_USE'], ['external_call']]。
- ETH transfer to channel deletion（12958→12962）：原始正向不可达；G3R消息路径[12958, 12953, 12962]，关系[['REV_DATA_DEF_USE'], ['DATA_DEF_USE']]。
- token transfer to channel deletion（12961→12962）：原始正向不可达；G3R消息路径[12961, 12953, 12962]，关系[['REV_DATA_DEF_USE'], ['DATA_DEF_USE']]。

原语句/函数：

    require(Channels[_lcID].token.transfer(Channels[_lcID].partyAddresses[0], Channels[_lcID].erc20Balances[0]),"CreateChannel: token transfer failure");

分类计数：{"b": 5, "d": 5, "c": 10, "a": 1}。(c)不等于已证明小样本导致漏报，(b)不等于新增关系必然有效。

## 6. 既有诊断与解释边界

- NS-P6c只评估30个S4g，不用它替代已缺失权重的S4。移除CTX/STATIC会改变预测，说明对该干预敏感，不直接证明独立语义贡献。
- NS-P6c2限定字段适用节点后，CODE能线性预测部分STATIC；CTX来自同套facts，CTX高可预测性属于编码保真度，不是独立新信息。低AUC也不证明CODE不含该信息。
- NS-P7c教师仅用summary/函数意图，排除role。节点类型均值的余弦本身较高；教师重构残差可能包含信息、噪声和非线性部分，不能把不可重构成分全称为有效新语义。summary仍可能有错误。
- HGT的S6/S5结果才回答教师/学生是否转化为检测收益。S5访问控制收益主要体现为误报下降，非SolidiFI漏报仍18/20；S6正例覆盖更高，但主终点没有显著改善。

## 7. 已有成本与资源

fit小时从来源resources.csv的fit_seconds求和；成功进程小时是收据total_seconds之和，含装配等开销。两列不能相加，不是GPU利用率积分，未计失败attempt、诊断和控制器等待。

|批次|正式拟合|fit小时|成功进程小时|最小整卡空闲MiB|峰值allocated/reserved MiB|
|---|---:|---:|---:|---:|---:|
|NA|240|7.6805|10.4816|34|1958.70/2386|
|NB|120|4.5967|6.5309|40|2044.68/2386|
|NC1|30|1.1355|1.7129|42|2031.81/2422|
|NC2|60|2.3011|3.4624|34|2031.81/2368|

LLM生成26812.33秒（7.4479小时），教师句向量编码30.69秒；30个学生CPU拟合和诊断289.23秒，后者不含大部分SHA/最终导出准备。S8复用S5学生。共享成本不按任务重复累加，原引用见preprocessing_costs.json。NS-P9 GPU运行为0。

## 8. 下一阶段基线候选（由用户决定）

|候选|重入节点主终点BF1、已有检验|非SolidiFI 重入 / 访问控制 TP,FP,FN|依赖|平均fit秒（重入合约/访问控制合约/重入节点/访问控制节点）|
|---|---|---|---|---|
|S0o|99.6247%；参照，无自身检验|20,11,12 / 0,3,20|原tokenizer/512 token ID + HGT；不需要新增CODE/CTX/教师|106.4 / 98.5 / 140.2 / 120.3|
|S2|99.8265%；对S0o Holm p=0.03906|25,5,7 / 2,9,18|CodeT5+ CODE + HGT|119.9 / 101.3 / 119.9 / 119.6|
|S4|99.7721%；对S0o Holm p=0.07422；对S2 p=0.22127|25,7,7 / 2,10,18|CodeT5+ CODE/CTX + facts/STATIC + HGT|139.7 / 116.8 / 130.2 / 145.6|
|S5|99.7803%；对S4 Holm p=0.64560；对S8 p=0.27368|25,9,7 / 2,0,18|S4 + 折内CPU学生；学生训练需要教师，部署不需在线LLM|135.3 / 115.4 / 130.9 / 143.2|
|S6|99.7231%；对S4单一p=0.95925|26,8,6 / 5,4,15|S4 + LLM描述/BGE教师编码，可离线缓存|140.2 / 120.4 / 129.7 / 148.8|

完整候选四任务指标和时间范围见baseline_candidates.csv。不按当前最高分自动选择，也不把不同粒度合成总F1。

## 9. 局限与模板事实修正

- 单seed、本机RTX3050；fold标准差是描述统计，不是seed重复方差。当前分组嵌套CV与早期paper_kfold不同，不能直接用差值宣称超越论文。
- SolidiFI占主导，但不能统一声称所有FN为0：本次六配置节点表中，S0o重入best/last各4个SolidiFI FN，S6重入last有2个，其余所列条件为0。完整分母见cohort_scores.csv。高总F1与真实案例低召回可以同时存在。
- 重入合约142文件、每折28–29；访问控制114文件、每折22–23。单文件改变accuracy约100/n个百分点，不是BF1固定改变3.4个百分点。实际折大小见contract_fold_sizes.json。
- 3B本地LLM描述与过滤无法保证全部语义正确；不可核验教师保留unverified。排除role不代表summary无同类错误。
- L-audit不是金标准；图、标签、折、特征、初值及历史产物均不修改。保留每个争议节点，不删困难文件。
- 原名是主视图；G3R中的REV_*用于消息流，不等于反向依赖。路径、语义正确性、可行执行与模型实际利用分别讨论。
- **最终实验计划迁往具备充足显存的服务器；当前显存限制只是本地电脑条件。** 服务器实验另建批次，不与本机成绩混成配对结论。
- 本轮停止于只读汇总；不增加seed、漏洞类别、独立测试或新的模型/边扩展。下一基线和研究方向由用户选择。

## 10. 验收与复现

900条指标及其来源聚合逐位一致；缺失/SHA不符拒绝；输出排他创建；逐正例表与N-C1/N-C2一致。21个持续漏报和10个误报的AST、STATIC、图路径及标签链可复核。冻结8H load只读通过，354份计算源码与runtime_resume_v2一致。
开发期保留三处新汇总器接入失败：原标签辅助行附加字段、重复n字段、辅助环境节点row_key。只修正本轮汇总器，旧产物无修改；有效收集为collection_attempt3、案例采集为cases_attempt2。验证命令和结果见README与verification。没有把这些开发失败记为模型训练失败。
机器入口：fold_metrics.json、aggregates.json、registered_inference.json、positive_nodes_best/last.csv、reviewed_cases.json、paths_and_labels.json、baseline_candidates.csv；所有统计都可追到来源SHA。
