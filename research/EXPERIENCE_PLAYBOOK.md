# 调研 A 组经验手册

更新时间：2026-09-11 06:55 CST  
状态：内部首版（滚动维护）

## 目标与证据纪律

本手册把旧 Kaggle/benchmark 项目的成功、失败和失效假设，转成 Kaggriculture、ARC-AGI-2、ARC Paper、Poker、Traffic 五条战线可直接执行的小实验。

统一证据层级：

1. **已复现事实**：有本地工件、固定数据切分、哈希、官方分数或可重跑日志。
2. **外部事实**：来自官方规则、官方数据、公开论文或可访问的公开代码；必须保留 URL 与访问日期。
3. **待验证推断**：能解释现象，但还未通过封存留出集、配对种子或提交验证。
4. **反例/否定结果**：优先保留；不得因新叙事而从账本删除。

任何建议都必须说明适用项目、最小实验、预期指标、成本、风险和停止条件。未知标签保持未知；禁止把未标注样本当负例，禁止使用私有日志、隐藏标签、ID/行序或生成器痕迹作捷径。

证据限制：四个历史目录都不是 Git 仓库，最近任务列表也没有暴露 ENVDA/CRAW/ONNX 的旧聊天正文。因此本手册只引用带时间戳的报告、submission ref、公开分数、回放、哈希收据和本地产物，不伪造 commit 或对话证据。

## 旧项目的可迁移证据

| 旧项目 | 可复核事实 | 可迁移教训 | 对当前项目的约束 |
|---|---|---|---|
| ROGII Well Log | AeroRidge v34 实测 9.150；“强标题”公开包实测为 9.537、9.959、18.245、65.479；静态可见样本写法隐藏格式不兼容；随机 PF 同 family 出现 8.188/8.354/8.438 | 不信标题，只信原样提交收据；提交槽是测量仪器；隐藏格式运行时适配；随机算法先固定 seed-bag；输出先去重 | Traffic/ARC 提交先做格式与行数守卫；Kaggriculture 用配对种子；Poker 不以一次公开分数选模型 |
| NVIDIA Nemotron | Kienngx 锚点 0.86；广谱 SFT 为 0.50，改 config/完整 key 重写也仅 0.51；只恢复 5,888 个损坏 MoE expert 张量回到 0.84，全 MoE 0.85；极小 `in_proj` 训练保持 0.86 | 先做张量值审计和 byte-identical 消融；均值 loss 会掩盖 hard tail；先保护容易多数，再修明确困难尾部 | ARC slot-2 和 Poker evidence 分支只在明确残差上触发；默认保留稳定锚点 |
| Maze Crawler | 同一 v51 公开 ref 曾为 1184.5，重提为 940.8；80 局噪声可到 abs(z)=1.15；单对 v37 中性但对第二锚点为 +1.94；replay 动作 off-by-one 曾使决策树结论失效 | rating 单点不是因果证据；必须多锚点、双座位、扩大样本；先验证观测—动作对齐；宽 guard 会杀死有利 tiebreak | Kaggriculture 同时对多个对手、双座位、同种子比较；任何 replay 分析先做时间索引单元测试 |
| NeuroGolf ONNX | 本地/LB 从 6255.96 到 6260.89 逐次近乎精确匹配，说明 sealed semantic/cost harness 可信；但距当时 top-10 仍约 1,079 分且局部 sweep 无候选；更大 visible-clean 批次又曾隐藏崩塌 | 本地/LB 匹配可节省提交槽；小步编译器变换能复利，但方法族触顶就停止；覆盖原语比盲目加深搜索重要；推断必须可撤销 | ARC 先扩展变换覆盖、再加深；每条规则单独消融；Paper 把方法上界与被证伪假设写入威胁项 |

## 最小可靠循环

1. **锁锚点**：冻结代码、数据哈希、运行环境、随机种子、预算和提交格式。
2. **只问一个问题**：一次实验仅改变一个机制；组合栈需等每层单独通过。
3. **建立反事实**：同数据、同种子、同对手/折，只替换被测组件。
4. **多轴读数**：主指标之外，至少记录尾部分位、最坏值、有效输出率、各组/座位表现和运行时。
5. **先过本地门**：封存留出集、配对检验或组间 OOF 通过后才占用提交槽。
6. **提交只做校准**：每个槽回答一个预先写下的问题；至少留一个恢复/格式槽。
7. **立即回滚**：触发停止条件即恢复锚点，不通过“再加一层补丁”拯救坏分支。
8. **更新反例账本**：负结果与被证伪推断永久保留，并降低同类尝试优先级。

## 五条战线的首轮动作卡

### A1. Kaggriculture：终局现金机制成立但不增胜分；两槽继续冻结

- **适用项目**：Kaggriculture。
- **当前证据**：KG-001 仍是唯一有配对支持的 hedge；KG-002/004/005/006 均未过胜分门。2026-09-10 21:07 UTC 的最新只读 live 样本已对齐到 public/hybrid 各 325 个 evaluation games：public 132-34-159、45.85%、rating 2023.8、mean 1,596.81、P10 −8,940.6、worst −52,908；hybrid 120-32-173、41.85%、rating 2116.2、mean 1,193.80、P10 −5,695.6、worst −96,701，均全 `DONE`、零 stderr。相对 295/291 快照，新增 public 30 局仅 18.33% score-rate、mean −3,178.13；hybrid 新增 34 局为 26.47%、mean −1,655.94。hybrid 仍高 92.4 rating与 3,245 P10，但低 4.0pp score-rate、mean 低 403.01 且 worst 更差。这进一步推翻早期 live 乐观读数，却仍是未配对 causal A/B，故不触发换槽或 KG007。KG-006 的 432×2 配对开发仍只证明 step718 cash/margin +51.61，W/T/L 与 379 分完全不变。官方 `kaggle-environments==1.32.7` 又明确：季末 reward 直接等于银行余额，未售库存不计；最终周期先处理 market 再写 reward；每方每回合只截取 market 前 10 单，后续单静默丢弃。
- **最小实验**：public+hybrid 两枚 active 槽继续只读冻结。KG-006 按原门停止，不进确认、不提交、不在揭示结果后把 margin 改成通过标准。只有新实验能在结果前固定一个包含镜像与强对手、且确有基线平/负局的辨识池时，才可重新检验“终局现金是否翻转胜分”；同时必须冻结已有 market 顺序和清仓单插入规则，逐格记录 `order_slots_before`、清仓单索引、accepted sell qty/value 与 dropped-order count。否则不再开 Kaggriculture 策略搜索。
- **预期指标**：总体/逐对手 W/T/L、score-rate、P10/worst、目标命中与失败减少、每局额外 cash、双座位、非 `DONE`、stderr、动作时延、first-diff step，以及订单上限命中/静默丢弃计数。
- **成本**：当前零新仿真；该项目线的既定 research scope 已由 completion audit 关闭，只保留每 6 小时、无变化静默的低成本只读成熟度监控。新机制先有辨识池和另行授权才承担配对仿真。
- **风险**：把确定的 cash/margin 增益误写成胜分增益、把非配对 live aggregate 当因果比较、追加清仓单被 10-slot 截断却误判为机制失败、因近期回落追涨杀跌，以及新提交挤掉 active 锚点。
- **停止条件**：KG-006 已因总体计分不严格提高且目标失败减少不可满足而停止；KG-002/004/005/006 均不确认、不提交、不调阈值。短期 rating 波动不触发换槽。
- **回滚/沉淀**：public archive SHA-256 `8031d51a…`；hybrid archive SHA-256 `0166b066…`；最新 source summary/maturity update SHA-256 `d3ce5222…` / `68b33421…`；旧 238/231 source summary `6014c63b…` 保留为历史；campaign completion audit SHA `a9929421…` 仅关闭既定 research scope，不能覆盖之后的动态快照；KG-006 comparison SHA-256 `a87ac48c…`。

### A2. ARC-AGI-2：把第二次尝试分配给残差，而不是盲增候选

- **适用项目**：ARC-AGI-2 技术线。
- **当前证据**：private run `348340917` 为 48 tasks/50 outputs、wall 上界 4,548 秒、schema 全有效，但四策略同 SHA、attempt1/2 changed=0；这是 runtime failure，不是 selector 否定。V1 smoke 的 `lr` 修复越过 optimizer constructor 后死于 offline logger。V2 只修 stdout helper，已在后来 local-only safety boundary 前 push；最后获授权观测为 06:27:41 CST `RUNNING`，06:34:25 后 current terminal status=UNKNOWN。本地 behavioral regression 对 logger、lr、scheduler、private/offline、1-task/1-step、solution-blind 全过。新增 CPU 微型复现又实际验证了 `adam_atan2_pytorch==0.2.4` 的正学习率构造、scheduler 在 `step()` 前覆盖、参数更新与 `step=0` logger，10/10 guards 通过，receipt SHA `49ee14c2…`；但它没有实例化 TRM、加载 2.16 GB checkpoint、执行 CUDA/数据构建，仍不能证明 Kaggle runtime 或 accuracy。
- **最小实验**：不重复上传。只有用户明确批准后，先只读查询现有 private V2 kernel 的终态并下载 artifacts；再由 fail-closed build/commit 工具生成并绑定 terminal receipt。工具会拒绝非终态、V2 notebook/runtime/metadata 身份漂移、缺 guard、源哈希漂移与项目外路径，且 commit 只改变 smoke prerequisite、不启动 development。若 `COMPLETE` 且 step1 checkpoint、合法 grid、return code 与全部哈希守卫通过，才另行决定 frozen48 重跑；否则按预注册永久停止 TRM compatibility route。
- **预期指标**：TRM return code=0、48 题候选覆盖/有效率、NVARC+TRM exclusive/overlap/oracle pass@2、attempt1 零变化、运行时与峰值显存。只有 oracle 相对 KGMon top2 至少 +1 output，才比较 best-distinct/selector。
- **成本**：低成本 smoke；通过后一次 L4x4 frozen48 重跑。
- **风险**：puzzle embedding reset、ABI/依赖、TRM 运行时超限、NVARC 高工作题再超时，以及把 runtime failure 错写成 selector failure。
- **停止条件**：v2 任一 guard 失败则永久停止 TRM 兼容路径，不做第三个补丁/full48/sealed；full run 的 TRM 无独占解、oracle <+1 output、coverage/grid/6h 失败，则不训练 selector并保留 KGMon 两槽。
- **回滚/沉淀**：锁定权威 Kaggle 文件哈希；所有选择器仅使用 demonstrations 与候选本身，不使用任务 ID、来源或公开答案记忆。

### A3. ARC Paper：当前没有合格新语料，转入 systems-negative

- **适用项目**：ARC Prize 2026 Paper Track。
- **当前证据**：训练集 GitHub/Kaggle 1000/1000 一致；evaluation 有 6 个任务内容变化、167→172 outputs，V175 为 0/172。V2 smoke 当前终态未知；本地 regression 与 CPU 微型复现只支持 compatibility/API-path guards。`conservative_exact_overlay_v3` 在 development 从 48/50 到 50/50 仍是 post-hoc 实现证据。历史完整性审计证明，原拟定的 48-task V3 holdout 虽与 development 的 task ID 不重叠，却已对 V176 方法泛化失去封存性：此前 source audit 加载了全部 1000 个 training solutions，V176 选中的 2 题都落在 development，而且该候选在这 48 题上会“全 abstain”在运行前已可知。进一步的独立语料审计又确认，父源码/规则收据已覆盖 ARC-AGI-1 train/eval、ARC-AGI-2 train/eval 与 ConceptARC，共 2,080 tasks / 2,563 outputs；ConceptARC 更已覆盖 160/160 tasks、480/480 outputs。因此截至当前，没有找到“合规、带标签、规则冻结后 solutions 对项目/上游源码均未见、且可支撑 ARC-AGI-2 分布泛化”的可验证语料。1D-ARC、MiniARC 与社区/合成集最多只能作 domain-shift mechanistic stress test，不能支撑 V176 Progress/Novelty。active contract SHA `1fedbc61…` 仍阻止 sealed promotion；runtime smoke=`UNKNOWN`、development=`PENDING_PREREQUISITE`、sealed/competition=`NOT_AUTHORIZED`。Writeup 仍仅 DRAFT pass，readiness 有 9 类 blocker。
- **官方时间/写作边界**：ARC Prize 当前公开页列技术提交 2026-11-02、Paper 2026-11-08；2026-09-09 18:41 的公开 Kaggle 官方页面复核则列 ARC-AGI-2 entry/team merger 10-26 23:59 UTC、final 11-02 23:59 UTC，Paper final 11-09 23:59 UTC，并与旧 authenticated Kaggle 快照完全一致。故 controlling submission surface 记 11-09，但与 ARC Prize overview 的一天冲突仍在，内部 hard stop 继续采用 11-08 23:59 UTC。内部冻结为 10-12（D-21 架构）、10-26（D-7 notebook/依赖）、10-30（D-3 只验证与最终选择）。Paper 必须绑定实际 Kaggle code submission，结果来自 leaderboard/public evaluation，并禁止报告训练集 performance；当前草稿已清除训练/开发比例，完整 paper tests 本轮 22/22 通过，但这仍不是结果证据。
- **最小实验**：当前采用方案 B：删除 V176 泛化、Progress 与 Novelty 主张，把论文转为 runtime/control-plane systems negative；同一 1000 题重洗无效。只读 V2 terminal receipt 仍只可在用户明确批准后回答 runtime path，不能修复污染；不重复上传。只有未来在取数或查看答案前冻结 solver、规则、指标、纳入/排除和许可，并证明第三方语料独立创建、内容/hash 不重叠、solutions 从未被项目或上游源码访问时，才可重开一次性正向验证。
- **预期指标**：当前只报告 runtime/format/artifact integrity、provenance/solution-access 审计与否定结果，不报告 V176 sealed pass@2。若未来合格语料出现，先要求 provenance chain 完整、content/hash overlap=0，再一次性报告 TRM 有效率、exclusive coverage、oracle gain、selector recovery、paired bootstrap 与等预算 runtime。
- **成本**：当前停止 selector/holdout 性能实验，只保留低成本 systems/control-plane 写作；未来语料获取与运行必须另行授权。
- **风险**：将 ID-disjoint 误当 method-unseen、用同一 1000 题重洗伪造封存性、将训练内 0.96 高分外推、把 runtime failure 当算法负结果、用任务 ID/来源构造 selector、把外部 API public-eval 上界写成本地证据，或把 schema/tool 的存在误当用户已经批准某个 stage。
- **停止条件**：当前“无合格新语料”已触发 systems-negative；不得用现有 48 题、ConceptARC、ARC-1/2 重洗或域外合成任务补写 sealed 结论。任何未来候选语料出现历史 solution access、内容重叠、许可不清或分布不可比，立即停止主分布主张。v2 smoke 失败仍不做第三个兼容补丁；任何已授权 stage 若提交规范化 failure receipt，就将该 candidate 固定为 `FAILED`、从收据另起版本，禁止覆盖历史后原地重跑。
- **回滚/沉淀**：论文中保留数据版本差异、否定结果、选择偏差和 sealed-holdout 协议。

### A4. Poker：E012 有开发信号但不满足原方法边界；停止在时间门前

- **适用项目**：Detect Suspicious Value Transfers in Poker。
- **当前证据**：E007/E008/E009 已因时间迁移或主门失败冻结；E010 global-query LambdaRank 又在全部主门灾难性失败。E011 回到 E001 learner/raw95，只做 outer-fold 内 trusted hard-negative weighting；Stage A 仍使 confirmed AP 0.948387→0.945789（−0.002598）、P95 rate −0.005376，evaluation `|Spearman|=0.117752`。worst fold −0.008371 与 KS +0.016531 虽在保护线内，但三项关键门失败；fail-fast 正确阻止了 time fits。
- **当前证据补充**：E012 原门下 Stage A 数值全过：confirmed AP +0.009996、worst fold +0.002138、P95 +0.016129、P99 +0.064516、KS 改善 0.029483、`|Spearman|=0.033481`。但独立原论文审计显示，Elkan–Noto 要求 SCAR、同一个 calibrated `g` 在独立同分布 labeled-positive validation 上估 c；当前运行用 inner 模型估 c、full-refit 另一模型出分，并把 24,000 unknown 总权重压到 confirmed-negative 数，故不是原理论的自然 P∪U 概率校正。机器诊断也显示 outer-valid 10.78%–15.55% 被 clip 到 1，而 evaluation 仅 0.26%；labelled OOF 有 251/1,860 精确等于 1，unique 仅 86.56%，尺度失配明显。
- **最小实验与结果**：B001 只读行为基线已完成：冻结 E001 risk，只用 confirmed targets 在原五个 whole-pool folds 上做 raw95 三类 family OOF；unknown used/labels=0，evaluation 未打分，risk/evidence 未改。全期 accuracy/macro recall 为 0.943548/0.938447，isolation/directed/soft recall 为 0.891304/0.939189/0.984848；early→late 为 0.852151/0.847081，late→early 为 0.879032/0.869046，isolation 时间 recall 仍有 0.804348/0.782609。独立核验 1,860+1,860 行、五折、risk 精确相等、概率 simplex 与 artifact hashes 全过；time receipt SHA 与 full/time pair-fold 也在消费前强制一致。confirmed labels 只覆盖 397/400 gameplay pools，另外 3 个 label-empty pools 不可外推。
- **指标解释**：冻结 4% active risk 下，random-tie Behavior MAP 为 full/early→late/late→early `0.262344/0.261408/0.259238`，而 official-order 为 `0.274939/0.274252/0.265873`，ID 并列顺序分别虚增约 `0.012595/0.012844/0.006635`，不得作为选模证据。100% random-tie MAP 为 `0.854915/0.689634/0.679294`，说明 family routing 确实可测但存在时间漂移；它通过“值得另行设计评审”的前置条件，却没有证明 pair-risk 或 evaluation 提升。
- **Evidence 可行性与绑定修复**：最新公开 Kaggle inventory 只有 3 份 notebook，全部已在本地：官方 metric、官方 tutorial 与已复现 PU/evidence ranker，没有新方法族。EV000 v2 独立重建现以 `PASS_CURRENT_BINDING` 绑定 implementation `7518ed87…`、report `27a8245e…` 和另存的 draft-v2 `a689703b…`；audit SHA `85adea3b…`。它重验 11 个输入哈希、372 个 confirmed targets、1,817 evidence hands、45,129 candidate rows、20 个有限且非恒定冻结特征；directed/soft/isolation candidate/evidence hands 为 18,150/725、15,699/632、11,280/460，full/early/late pairwise preferences 为 212,888/82,266/42,763。early 有 347 个 evidence-bearing query、仅 346 个可训练 query，其中 outer fold 3 的一个 directed query 是必须保留的 zero-preference 反例；cross-time 最小 source-train/target-valid pair 数 early→late 68/7、late→early 35/15。旧的错绑 audit `e5d8293a…` 继续以 `PROVISIONAL_HASH_MISMATCH` 留档，不能再当 PASS。
- **不确定性门**：pool provenance companion（SHA `eb11f452…`）证明 372 queries 只占 245 个 `table_id` pools；62 pools 含多个 family，53 个 family-pool 含多个 query，因此唯一合法 cluster 是 `table_id`，独立抽 hand/query 或分 family 抽样都会破坏依赖。bootstrap support audit（SHA `71b02ce0…`）又发现 v2 的 ordinary cluster bootstrap 可能产生空 family：early→late fold0 的 7 个 isolation queries 只占 6/38 pools，单次空格概率 0.00145855，5,000 次期望 7.293 个；fold4 期望 2.320 个。v2 没有预注册 reject/omit/zero-fill，family/macro CI 因而未完全定义。
- **v3 文档与授权状态**：v2 methodology 已以 SHA `98b1cea1…` 撤销执行资格；proposal-only 5,000-draw 结构审计（SHA `7a89801e…`）使 45 个 view/fold/family denominator 全为正，最小 1.0232903，weight stream SHA `c833ac7d…`。`EVP-DRAFT-03` 最新 SHA `54776c54…` 已冻结 RNG、pool 权重、共享配对、weighted query/macro 与 quantile，并把输出严格命名为 `90% paired Bayesian cluster-weight sensitivity interval`；误称 confidence/credible/coverage interval 会在查看聚合性能前停止。协调源随后明确批准 `IMPLEMENTATION_ONLY_APPROVED`；实现 containment receipt 已以 `PASS_IMPLEMENTATION_PRESENT_UNEXECUTED` 闭环，SHA `f04b1096…`，并把旧文档 static audit 中当时为真的 `implementation_created=false` 历史化而不改原件。core/runner SHA `5871093c…` / `5a0f5aec…`，17/17 EVP 与 23/23 repository tests 由收据报告通过；测试只拟合 synthetic model。只读独立核对确认 receipt 内五个源码/测试哈希与当前文件一致，authorization-consumption 与 validation result/query/pairwise/model outputs 均不存在。真实数据模型拟合、聚合性能、evaluation、E-number、candidate 或 submission 仍全 false，`preregistration_executed=false`。
- **v4 方法与源码审计**：draft/coverage contract SHA `3a9f2093…` / `4e821092…` 达到 `PASS_METHOD_SPEC_ONLY`。但当前 runner SHA `4737f3c4…` 在 Stage 1 把 `development_pair_hands.parquet` 纳入整文件 SHA，而该文件在 Stage 3 才按列读取 `phase_progress`；这与 draft 明示 Stage 1 不得 hash/open/inspect `phase_progress` 的门冲突。列投影读取不能撤销此前对整文件 bytes 的访问。现有 containment SHA `f8a2e27b…` 只是实现自审，且独立 source audit 尚不存在，因此 v4 源码必须 `REJECT_SOURCE_AS_IS`，不得真实运行。最小修复只能是监督下修改方法合同，或在结果执行前另行冻结不含该列的 Stage-1 companion/digest，再做独立 source audit；不能用已有 72-cell coverage PASS 覆盖此问题。
- **成本**：B001 只付 confirmed-only OOF 与只读双向时间审计，不支付 E012 time fits、不打 evaluation、不占提交槽；加固守卫后的 receipt SHA `02e7e03e…`，OOF 数值未重跑。
- **风险**：SCAR/自然样本假设不成立、不同模型的 g/c 尺度错配、clipping ties、用 family target 造成循环选择，以及看到 E012 正开发信号后放宽方法边界。
- **停止条件**：E012 原运行停止在 time 前；本轮禁止自动 E013。B001 只能支持下一步设计评审；EV000 v2 的 hash-binding PASS 仍是历史事实，但 v2 方法执行资格已撤销。`EVP-DRAFT-03` 仅获 implementation-only 许可，result-bearing execution 仍禁止、没有 E-number；实现静态 PASS 也不能自授权真实数据运行。Rubin 原始 Bayesian bootstrap 模拟的是后验并依赖模型假设；cluster-bootstrap 一手研究也强调一致性依赖模型。因此没有另行覆盖模拟时，v3 的区间只能明确称“90% paired Bayesian cluster-weight sensitivity interval”，不能冒充 frequentist CI；weighted overall/family/macro 与 paired delta 已冻结。其余门仍为 random-tie、inner-only predicted-family、无 true-family routing；timestamp-unresolved tie、late-isolation 7/11/12/10/7、early zero-preference 都立即停止。future PU correction 必须新 ID、结果前固定 same-`g_k/c_k` rotation 或可验证 case-control 权重、饱和/唯一值门；否则保持 E001。
- **回滚/沉淀**：保留 E001 raw95；E012 validation/method-audit SHA 为 `cac16b65…` / `d41d4525…`，只作 selector 开发信号，不作 faithful Elkan–Noto 或晋级证据。方法审计中的 Bekker–Davis 引文元数据已纠正，数值、边界判断与 `STOP_BEFORE_TIME` 均未变化。

### A5. Traffic：nonlinear residual 稳定正向但低于扩展门；λ=5 继续冻结

- **适用项目**：Traffic Flow Benchmark。
- **当前证据**：Queue off-by-one `56107311` 为 0.74210（+0.02364），只改 160 cells；后续 Queue、Task1 topology 与 density smoothing 均冻结。ODME λ=5 的本地最小 split/panel `S_link` 增益为 +0.008185/+0.001815，最大 prior-L1 ratio 增幅 +0.030425；submission `56108199` 已 COMPLETE，public 0.74733，比 0.74210 提高 +0.00523 并超过预注册 0.74410 门。6,985,307 行 key 有效，SHA `c3aea84e...`，唯一变化是 70,708 个 ODME `path_flow` cells。它支持 λ=20→5 这一单变量远端有效，但仍不能分解 organizer-only `S_od/S_dev/S_attr`。
- **补充反证**：低 λ 与 provided-cutoff 已停止。directional observability preflight 也按结果前门冻结：20 个 panel×split 仅 10 个通过；worst adjacent spacing 7.771 km，最低 upstream/downstream/both/either coverage 为 85.07%/84.80%/73.95%/95.92%，未达到逐 split 的 3 km、90%/90%/80%/99% 门，因此没有生成 switching-filter 预测。另一个关键纠错是，首版 grouped temporal baseline 的七日滚动 fallback 会在封存月后续日期使用同月较早 truth；尽管 dev/confirm `S_state` 为 0.908699/0.911208，仍被标为 `INVALID_DEPLOYMENT_MISMATCH`，不能作为 Kaggle 对照。
- **合法对照**：pre-block frozen V32 profile 已完成：每 panel 对 January/February 只用此前 214/245 天，same-day 只读 masked inputs。7,089,289 target cells、0 missing、60 panel-regime 全覆盖；dev/confirm `S_state` 0.908792/0.911292，公开 `S_FD` 0.986250/0.986470。5,884-cell archived-anchor 样本 keys/speed 全匹配，仅 1 个 flow cell 相差 0.104587 vph（官方 600-vph normalizer 的 0.00256%），当前 rowwise V32 与新实现精确匹配。
- **新反证**：source audit 显示 6,740,599 scored targets 中 0 个会使用 historical profile；nearest-fill 与 Queue ongoing-trend 均已失败。最后一个 State 方向——link-agnostic nonlinear residual——在 January 选择 full correction，`S_state` 0.903327→0.907732；untouched February 也从 0.913191→0.917719（+0.004528），每一天均改善，transition +0.005370、public FD +0.001432、0 missing。训练标签均来自发布的 train layer，未用 scored-split labels；但 +0.004528 明显低于预注册 +0.01，估算仅 State 带来的总分贡献约 +0.001585。
- **机会审计**：固定提交成本下界为总分 0.0035；20 个 ODME panel-split 的算子 nullspace fraction 为 94.44%–98.02%，State 理论余量虽为 0.031048，但已有单 panel 下界仅 0.001585，FD 余量 0.000677，λ=5 的 `S_link` 即使满分最多再贡献 0.000254。没有 qualifying independent family。全表 lineage 又验证 6,985,307 行仅 Queue 160 cells（全 `1→0`）与 ODME 70,708 `path_flow` cells 改变，State 6,740,599 行零变化，文件/schema/domain 全 VALID。
- **可重放性纠错**：审计发现 ODME 生产脚本默认 solver 参数曾从实际提交的 `tol=1e-9/lsmr_tol=1e-10/max_iter=200` 漂到 `1e-8/1e-8/300`。现已用 `current_best_freeze_v1.json`（SHA `ddf2da9c…`）显式钉死；从 V32/public inputs 完整重算 20 个 panel-splits、Queue 160 cells 与 ODME 70,708 cells，最终 6,985,307 行与 canonical `c3aea84e…` 逐字节相同。full-replay receipt SHA `ca275b57…`，153.91 秒、434.16 MB；独立回归 33/33 通过。
- **最小实验**：`HOLD_LAMBDA5_NO_NEW_EXPERIMENT_OR_SUBMISSION`；冻结 Queue、State 微调和 ODME λ=5，不再生成候选。当前只保留显式配置下的只读健康/lineage/replay；出现真正独立且超过 0.0035 本地下界的新机制证据才重开。
- **预期指标**：当前只核验 submission ID/hash、6,985,307 行、task/column lineage、值域/非有限值、冻结参数、byte-identical replay 与公开状态；`S_LWR/S_physics` 保持 unknown。
- **成本**：日常只读 audit 约 6.62–26.4 秒；完整最佳重放 153.91 秒/434.16 MB，只在里程碑或代码/环境变化后执行。历史资源旁证重放一次为 176.83 秒/723.45 MB。
- **风险**：把稳定但很小的 State 正向当成足够榜分、公开 FD 冒充 organizer Physics、跨 panel 外推、solver 默认值漂移，以及因为离 0.78 仍差 0.03267 而堆叠多个未过门补丁。
- **停止条件**：没有独立组件级下界，故保持 λ=5/0.74733，不提交、不继续 microtuning。七个历史空资源字段已由单独的 current-machine deterministic replay 旁证覆盖，原账本空值保持不改；λ=1 只复现既定 numerical failure。四任务 baseline contract（receipt SHA `58a0cc1d…`）把 State 60 groups、Queue 16 eligible panel-splits、ODME 20 panel-splits 和 public-only Physics 绑定成可重放矩阵；独立重跑 matrix byte-identical，去除时间/资源字段后 receipt 全等，但 `S_queue/S_LWR/S_physics/S_od/S_dev/S_attr` 仍全是 unknown/null。lifecycle-policy audit（receipt SHA `5af856f4…`）现场验证 D30/D14/D7 三个 deadline receipts、8 个阶段动作探针与零 late violations，三张输出表独立重跑 byte-identical。最终一次性控制面收口使用 runtime v3（receipt SHA `197b1d69…`）：CPython 3.13.2、pip 26.1.2、10 个精确包、Darwin arm64/Accelerate、11 个 CLI 入口、7 项 capability、64/64 tests；system manifest（receipt/CSV SHA `5b30c7a5…` / `b6c84afb…`）又固定 87 个实现/证据文件与 15 份 canonical receipts，独立重跑 CSV byte-identical。campaign readiness v8 为 24 PASS/0 WARN/0 FAIL（receipt SHA `e24b1e0a…`），同一 as-of 独立重跑仍为 24/0/0；激活后 checklist 仅因 ledger 自身新增一行而从 44 变 45，不冒充 byte-identical。当前仍是 `RESEARCH_BEFORE_D30`、`goal_complete=false`。final selector v4 仅做 dry-run preview：`PREVIEW_READY_NOT_FINAL`，把 `56108199`/0.74733 选为当前候选、`56107311`/0.74210 留作 rollback，SHA `6ddd42dc…`，没有 Kaggle 动作、`selection_final=false`、`internal_selection_complete=false`。至此控制面冻结到 D30；除真实 hash drift、赛规变化或 ≥0.0035 独立提分下界，不再增加元审计。下一只读检查点为 2026-10-08 14:55 CST。
- **回滚/沉淀**：保留 V32 工件哈希和逐任务组件分数；所有提交先过 ID 连续、行数、无 NaN、值域与运行时守卫。

### A6. CUHK Large：Fresh20 真独立但负增益，VLM 重新冻结

- **适用项目**：CUHK Large 的 Qwen3-VL-4B screen 与最终候选冻结。
- **当前证据**：旧 small20 因 20/20 命中过往工件，仅可作 smoke。随后完整 HARn archive/1,524 videos/524 training units 通过 CRC 与抽取，先冻结历史 inventory，再从 374 个 QA+clip 均未见的 eligible rows 中选出 10 subjects×2 的真正 Fresh20，overlap=0。运行 20/20 input/read/parse、0 failure、0 retry，但 VLM 12/20=0.60，低于 subject-disjoint parent 13/20=0.65；overall net −1，action +3、object interaction −4，固定 halves +1/−2，subject deltas 2 positive/3 negative/5 tied，one-sided exact sign p=0.8125。所有 promotion gate 均失败，判决 `REJECT_AND_REFREEZE_VLM`。
- **最小动作**：不再扩 VLM、不生成 candidate、不提交；冻结两份既有 0.78070 finalists（`56122653`/`56108595`）。若未来重开，必须是新的方法族与新的 subject-disjoint、历史零重叠协议，不能在 Fresh20 结果上改门。
- **成本/风险/停止**：当前零新增推理；风险是把 action 子类 +3 拆出来追涨、忽略 object/half/subject 反转，或将 provenance PASS 误当 accuracy PASS。Fresh20 已触发停止；final freeze v3 只保留 101/101 artifacts、16/16 model files、2/2 candidates 的可复现交付。外部注册仍缺 contact email、affiliation、country/region 与 exact team member names，且 final deadline 为 2026-09-15 23:55 CST；这些需用户提供并同意条款，自动化不得代填。

### A7. HSI Detection：数据路径未证明，GPU 前先停在访问门

- **适用项目**：Hyperspectral Object Detection 2026。
- **当前证据**：CPU-only `hsi26_data_mount_smoke_v2` 于 2026-09-10 03:07:53 UTC 以 `mount_smoke_failed` 结束；官方状态为 `CANCEL_ACKNOWLEDGED`，KaggleHub 一直停在 `Mounting files`，没有目录、文件清单或单图 hash 收据。它不是模型失败，也没有启动 GPU、训练或提交。
- **最小可证伪步骤**：若另获授权，只做 5–10 分钟、CPU、零模型的数据访问 preflight：优先验证官方 notebook 环境直接 competition dataset mount/path，输出最小目录清单和一张图的 hash；不下载全量、不训练。
- **成本/风险/停止**：成本很低；风险是再次浪费 notebook 配额或把 UI 挂载提示误当数据可读。限时内拿不到确定路径、文件清单和一图 hash 就停止，不上传 `hsi26_b5813_yolo11m_v1`，更不进入 GPU 训练。

### A8. TartanIMU：小幅单变量改动已完成公开分与冷重放闭环

- **适用项目**：TartanIMU 与其他受官方复跑约束的轻量表格/序列项目。
- **当前证据**：E003 只把 E002 的 tree ceiling 从 600 改到 1000，无平台输入、分类器或 routing；Kaggle ref `56117057` public 0.63142，官方 full-test 0.53485（lower is better）。冷启动 CPU/offline 重放用 117.42 秒、最大 RSS 723,648,512 bytes，30,644 行输出 SHA `4644bb8e…` 与提交逐字节一致；官方 checkpoint/model SHA `ca8cc3e…` / `4cc94cf4…`。
- **迁移规则**：只有单变量差异、官方/本地指标绑定、资源收据和冷启动 exact replay 同时成立，才把远端分数视为可交付候选；不能把 public 分单独外推到私榜。
- **成本/风险/停止**：当前无需再算；技术报告已成为 5 页 content-complete draft，PDF/source archive 与 visual QA 完成，但仍缺作者姓名、单位、邮箱、公开 Hugging Face URL 与公开 prediction URL。风险是追逐 public 分、混入平台路由、破坏 exact replay，或把 placeholder 版本误交付。任何新候选若不能在既定 CPU/offline 预算内复现，或 full-test 方向不保留，就回滚 E003；身份与公开 URL 未补齐前不得称 final。

### A9. Biohub：一轮 recovery OOF 完成，但跨胚胎检测召回近乎崩塌

- **适用项目**：Biohub Cell Tracking During Development。
- **当前证据**：BH-0003 official run `348522481` 已 COMPLETE 并通过 receipt/metric/split/log 校验；两方向 16 holdout samples，runtime 13,491.46 秒，fold scores 0.05588/0.01865，combined 0.03002。edge Jaccard micro 0.02770、division Jaccard 0，mean node ratio −0.94983，99.596% edge errors 来自 missing edges；16/16 samples 均 node underprediction、16/16 edge-recall-limited，11/16 division-limited。它只是 diagnostic，远低于已冻结 public baseline 0.944，明确 `diagnostic_only_do_not_submit`。
- **最小可证伪步骤**：若项目线另获实验授权，只改变 detection threshold，预先冻结少量下降网格并在同一两方向/16 samples 上测；主门必须同时提高 combined score、两 fold 下界、node recall 与 edge recall，且 false-positive/track fragmentation 不越线。不得改 tracker、训练轮数或提交。
- **成本/风险/停止**：可复用已下载输出，先做低成本阈值重评分；风险是阈值下降只制造孤立节点/短轨、过拟合 16 samples 或把 public 0.944 当此模型锚点。若任一方向不改善、division 仍为 0 且 edge gain不足、或 FP/碎片化显著恶化即停止该模型族，不再训练 recovery。

### A10. Tree HSI：扩大每类训练上限只抬 OA、伤 AA，按门冻结

- **适用项目**：Hyperspectral Tree Species Identification Challenge 2026。
- **当前证据**：v4 只把 v3 的 per-class cap 5,000→10,000，其余 radius=1、160 trees、features、folds、seed 全固定。connected-region OOF OA 0.68814→0.69317（+0.00503），但 AA 0.62649→0.61906（−0.00743）；fold OA/AA ranges 0.04122/0.01652。因预注册要求 OA 与 AA 同时改善，候选已拒绝，未生成 test predictions、未占 Kaggle slot。
- **最小动作/成本/风险/停止**：保留 v3 public 0.10387/rank31；不继续扩大 cap。后续只有独立方法族、固定相同区域折且同时提升 OA/AA 才可重开。成本当前为零；风险是用 +0.005 OA 掩盖 minority-class 退化。任一 AA 下降或单类崩塌即停。

## 通用保护机制

- **格式守卫**：从运行时官方样例推导行与字段；禁止硬编码可见样本长度。
- **封存留出集**：在看实验结果前固定任务/玩家/种子集合与哈希；只允许在预定节点评估。
- **多锚点评估**：至少两个独立锚点或对手；对博弈任务还要双座位。
- **尾部守卫**：主指标提升但 P10、最坏值、有效输出率或物理约束显著恶化，一律不晋级。
- **等预算原则**：候选数、运行时、训练数据与提交次数不相等时，不得把提升归因于算法。
- **负结果复用**：失败不是“无信息”；用于缩小后续搜索空间和修改先验。
- **回滚点**：每条线只保留一个已验证锚点和少量独立开关；组合失败可精确撤回。
- **停止规则**：连续两轮封存集无收益、收益小于噪声或风险守卫触发，即转移到新的误差族，不继续参数微调。

## 下一轮研究问题

1. Kaggriculture：两槽各 325 局已降到 45.85%/41.85%；是否继续坚持只有新的配对本地机制而非非配对 live aggregate 才足以触发替换？当前答案仍是“是”。
2. ARC 技术：已经通过本地 API-path 微型复现的 V2，能否在获授权的权威 terminal receipt 中恢复 TRM runtime；并且在另有真正未见 labeled holdout 后，才检验是否形成至少 1 个 oracle 新输出？
3. ARC Paper：当前已转 systems-negative；未来只有先证明第三方语料独立、零内容重叠、许可清晰且 solutions 从未可见，才重开一次性正向验证。
4. Poker：v4 当前源码因 Stage 1 整文件 hash 越过 `phase_progress` 门而应被独立 source audit 拒绝；先修合同/数据分层并重做 source audit，之后才可能讨论 result-bearing development run。
5. Traffic：在没有超过 0.0035 本地下界的新族时，能否只维护 λ=5 的显式冻结配置、byte-identical replay 与 D30/D3 新鲜度门，而停止自动搜索？
6. Biohub：单变量阈值下降能否同时修复两胚胎方向的节点/边召回而不制造 FP 与碎片化；否则是否应直接停止该模型族？
7. CUHK/Tartan：用户身份、外部注册同意与公开 URL 这些非算法依赖能否在各自截止日前补齐，而不由自动化代填？
