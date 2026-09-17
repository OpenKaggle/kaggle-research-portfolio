# 调研 A 组交叉投递日志

更新时间：2026-09-11 06:55 CST  
状态：滚动投递中；关键回执已入账，未决项继续按门禁跟踪

## 当前项目任务

| 战线 | 任务标题/用途 | 任务 ID |
|---|---|---|
| 协调源 | 寻找适合的新 Kaggle 比赛 | `01a07fa6-9de8-7831-9fb0-c417d63b4221` |
| Kaggriculture | 策略与仿真 | `01a0816b-e758-7c51-b8f9-a8fd9d80cedd` |
| ARC-AGI-2 | 技术提分 | `01a0816c-108d-7e01-8896-6078fafe9c66` |
| ARC Paper | 论文赛道 | `01a0816c-42c4-7610-a23b-eb8119d0f776` |
| Poker | PU 检测与证据排序 | `01a082ad-18f0-7802-8c73-6a5fedfad3dc` |
| Traffic | 时空状态、队列与物理一致性 | `01a082ad-680c-7cb3-b6b9-e2b6db06da78` |

## 投递准则

- 只投递能改变下一步实验排序的证据；普通网页摘要不打扰项目线。
- 每次投递必须含：来源、事实/推断、最小实验、预期指标、成本、风险和停止条件。
- 项目线的“收到”不等于验证；只有代码/日志/封存结果可改变证据等级。
- 纠错优先级高于新线索；发现错归因时立即投递，不等待日报。
- 无新增高价值证据时保持静默。

## 已发送：2026-09-09 首轮

### X-KAGG-001 → Kaggriculture（已送达任务）

- **来源**：Maze Crawler 多锚点/大样本经验；Kaggriculture 社区 rating 收敛讨论；当前 KG-001/KG-002 账本。
- **事实**：短局排名噪声与座位/对手差异可制造假阳性；KG-001 已有本地支持，Pizza/Smoothie 扩展尚无配对因果证据。
- **建议**：固定 KG-001，只对 Pizza、Smoothie 分别做同一批新种子、9 对手、双座位的单因素消融。
- **预期指标**：配对分差中位数、rating、P10、最坏分差、双座位差异。
- **成本/风险**：中等仿真；风险是未知种子噪声和 fallback 互相覆盖。
- **停止条件**：P10/最坏值退化或新种子收益不稳定即停，不用单次远程 rating 放行。
- **回执**：消息已成功送达；实验回执待项目线产生。

### X-ARC-001 → ARC-AGI-2 技术线（已送达任务）

- **来源**：NeuroGolf 小 swap/覆盖瓶颈；官方 Pass@2；权威 Kaggle 数据差异；公开 NVARC/TRM 锚点。
- **事实**：每题两次尝试；V175 在权威 172 输出上 0 命中；盲增候选不自动增加边际覆盖。
- **建议**：固定 slot-1，对 slot-2 的 NVARC2、checkpoint-agreed TRM1、最佳有效不同候选做等预算消融，并按结构族审计。
- **预期指标**：sealed pass@2、有效输出率、重复率、残差新增命中、运行时。
- **成本/风险**：中等重跑；风险是 selector 过拟合与结构标签泄漏。
- **停止条件**：封存集 <+1.0pp 或破坏有效率/12h 约束即保留最简锚点。
- **回执**：消息已成功送达；实验回执待项目线产生。

### X-PAPER-001 → ARC Paper（已送达任务）

- **来源**：ARC 权威数据差异、V175 负结果、ROGII 提交作为测量、Nemotron 锚点保护。
- **事实**：公开训练内精确性不能推出 evaluation 泛化；当前主张需靠残差 slot-2 消融而不是候选数量支撑。
- **建议**：将 residual slot-2 allocator 作为主论点，完成一致性门、结构分层、随机 slot-2、总是第二候选四项消融。
- **预期指标**：≥3 个新增权威 evaluation 精确输出，或 sealed pass@2 ≥+1.0pp，且消融能解释原因。
- **成本/风险**：中等实验/写作；风险是论文叙事先于证据。
- **停止条件**：Go 条件未满足则降级为负结果/方法论论文。
- **回执**：消息已成功送达；实验回执待项目线产生。

### X-POKER-001 → Poker（已送达任务）

- **来源**：官方 PU 标签语义与三指标权重；Nemotron 尾部修复；NeuroGolf 隐藏安全失败。
- **事实**：未标注不等于负例；当前 0.946934 group CV 需要玩家隔离与特征来源审计。
- **建议**：同特征/容量下做 naive negative、PU 重加权、PU bagging 三套 OOF；比较统一与 family-conditioned evidence ranker。
- **预期指标**：Pair AP、Evidence MAP@5、Behavior macro AP、未见玩家表现、校准。
- **成本/风险**：中等 OOF；风险为玩家/ID/行序/生成器代理泄漏。
- **停止条件**：收益在完全未见玩家或移除代理特征后消失即回滚。
- **回执**：消息已成功送达；实验回执待项目线产生。

### X-TRAFFIC-001 → Traffic（已送达任务）

- **来源**：官方四组件权重；V32 公开锚点；Maze Crawler off-by-one 教训；公开网络/物理诊断参考。
- **事实**：Task 1 同时影响 State 与 Physics，共 50%；queue 实现存在待核验的 +25/+30 边界问题。
- **建议**：先冻结其他组件，只做 Task 1 时间锚点 vs 拓扑+同时间段回退；之后拆 onset/ongoing queue 并逐 horizon 单测。
- **预期指标**：State、Physics、守恒残差、高缺失桶；随后 Queue 与逐 horizon 校准。
- **成本/风险**：中等计算；风险为拓扑方向错、时间泄漏和伪标签。
- **停止条件**：State/Physics 不能同时保持，或 queue 改变应固定正例计数，即回滚并先修索引。
- **回执**：消息已成功送达；实验回执待项目线产生。

## 已发送：2026-09-09 增量与动态快照

### X-KAGG-002 → Kaggriculture（已送达任务）

- **来源**：公开 v43 Sparse Shop Hybrid，<https://www.kaggle.com/code/kaitofukami/103-128-fresh-public-v43-sparse-shop-hybrid/comments?scriptVersionId=344404785>。
- **事实/边界**：Apache-2.0；可迁移的是可见 YARN 条件、prefix-compatible 和专家状态同步，不是三条 tape；作者 103/128 不是 LB 保证。
- **最小实验**：KG-001 上三个机制分别作为独立开关，同新种子、9 对手、双座位验证。
- **预期指标**：配对胜率/分差、P10、worst、非法动作、状态漂移。
- **成本/风险**：中等仿真；风险是 tape 过拟合和 state sync 错误。
- **停止条件**：任一开关未见种子不稳或尾部/合法性退化即回滚；分别过门前不组合。
- **回执**：项目线已核正文：首次分歧 step 88/153，三控制器持续同步，103/128 为 8×8×双座位本地矩阵；正在结案 KG-002 并准备状态/前缀审计。

### X-ARC-002 → ARC-AGI-2 技术线（已送达任务）

- **来源**：Confluence 与 ARCgentica 公开仓库。
- **事实/边界**：高 public-eval 结果依赖外部模型/API、沙箱、高并发 agents 和显著成本，只是云端资源上界，不是 Kaggle offline baseline。
- **最小实验**：只移植 demo-execution 一次反馈与 attempt diversity，在现有候选上做等预算 A/B。
- **预期指标**：sealed pass@2、有效率、重复率、runtime。
- **成本/风险**：中等本地实验；风险是不可复现外部依赖和 public-eval/holdout 污染。
- **停止条件**：runner >11h30、sealed <+1.0pp 或依赖外部 API 即不纳入 baseline。
- **回执**：消息已成功送达；实验回执待项目线产生。

### X-PAPER-002 → ARC Paper（已送达任务）

- **来源**：同 X-ARC-002。
- **事实/边界**：云端分数仅作 related-work 上界；论文必须披露外部模型、沙箱、成本与 holdout 污染风险。
- **最小实验**：无反馈/一次 demo 修复 × 重复/独立 slot-2 的等预算 sealed 消融。
- **预期指标**：pass@2、有效率、重复率、成本/runtime。
- **成本/风险**：中等；风险是把资源规模误写成算法创新。
- **停止条件**：未达到 ≥1pp sealed 或 ≥3 个新增权威 eval exact，仅保留为上界讨论。
- **回执**：消息已成功送达；实验回执待项目线产生。

### X-POKER-002 → Poker（已送达任务）

- **来源**：2026-09-09 上游人工赛况快照。
- **事实/边界**：截止 2026-09-20 22:00 UTC；top 3 约 0.93601/0.90098/0.89765，随时会变化。
- **最小实验**：先拿合规真实分数，再做三套玩家隔离 PU OOF。
- **预期指标**：首个真实总分、三子指标和完全未见玩家 OOF。
- **成本/风险**：低至中；风险是为追榜过度提交或忽视泄漏。
- **停止条件**：首个真实模型 <0.75 时停止提交，先查 schema/PU/CV；≥0.75 才继续消融。
- **回执**：E003 已完成并按门槛判失败、不提交。Pair AP 0.94839→0.95437，但关键 positive-vs-unknown 百分位 1.0→1.0、未达 +0.02；转入 60%/40% exposure drift 审计。

### X-TRAFFIC-002 → Traffic（已送达任务）

- **来源**：2026-09-09 上游人工赛况快照。
- **事实/边界**：截止 2026-11-07 06:55 UTC；top 3 约 0.92332/0.92116/0.87742，随时会变化。
- **最小实验**：V32 上先做 Task 1 时空/拓扑插补，再做 Queue onset/ongoing。
- **预期指标**：State、Physics、守恒、高缺失桶；随后 Queue 与 horizon 校准。
- **成本/风险**：中等；风险是因榜差大而并行重写四组件。
- **停止条件**：Task 1 公开增益 <+0.010 或不能同时保持 State+Physics 即停；Queue <+0.015 或正例边界异常即停。
- **回执**：submission `56107311` Public 0.74210，较 0.71846 提升 +0.02364，超过 +0.015 门。精确 160 行 queue 1→0，其他任务逐字节不变，故升级为已验证可归因增益。

### X-KAGG-003 → 协调源（已送达；项目线自产生）

- **来源**：KG-002 432 局配对矩阵与 seed-cluster bootstrap。
- **事实**：Y+Pizza/Y+Smoothie/组合分别净少 13/3/16 计分点；三者 95% 区间上界均为 0，Pizza 尾部从零败恶化为 15 败。
- **结论**：远端非配对首店胜率是假方向；冻结 Pizza/Smoothie。
- **最小实验**：只测试 Yarn-second 可见条件；prefix/state sync 先独立审计。
- **预期指标**：配对计分率、P10/worst、双座位、前缀逐动作一致。
- **成本/风险**：中等仿真；Yarn-second 稀疏、状态漂移风险。
- **停止条件**：前缀/state 不一致不跑；无稳定正向或尾部退化即停。
- **回执**：协调源已收到完整数值；Kaggriculture 项目已将 KG-002 标记停止。

### X-POKER-004 → Poker / 协调源（已送达）

- **来源**：`E004_pool_rank_validation.json`。
- **事实**：全特征百分位化严格 FAIL；score KS 0.06129→0.08231，恶化 34.3%，|Spearman(shared_hands)|=0.10215>0.10。
- **最小实验**：只把 exposure-sensitive counts 变为 per-opportunity rates，其余 95 特征/learner/folds 不变。
- **预期指标**：Pair AP、worst fold、score KS、shared-hands Spearman、P95 tail。
- **成本/风险**：低至中；风险是再次抹掉有效幅度或以次级指标掩盖域漂移。
- **停止条件**：KS 不降 30% 或 |Spearman|>0.10 即停该表征家族。
- **回执**：已提醒 Poker 线按现有 validation 文件立即归档 E004；E005 已按下条精确预注册。

### X-TRAFFIC-003 → 协调源（已送达；项目线自产生）

- **来源**：官方 submission receipt `56107311` 与逐字节 diff。
- **事实**：Public 0.74210，较锚点 +0.02364；仅 160 个 queue cells 改变。
- **最小动作**：冻结新锚点，等待全量数据/哈希后做只读分层误差审计。
- **预期指标**：可复现失败桶、两个时间块方向一致、State/Physics 守恒 proxy。
- **成本/风险**：低；风险是把 withheld 组件 plausibility 当真值或在成功邻域过拟合。
- **停止条件**：无跨时间块复现的单一失败桶，不开启下一候选。
- **回执**：协调源已收到；Traffic 线已写入 campaign/submission/experiment ledger。

### X-KAGG-004 → 协调源（已送达；项目线自产生）

- **来源**：route0/route1 动作差分与 8 个 Yarn-second 历史双座位单元。
- **事实/推断**：两路动作到 step 167 完全一致；Yarn-second 上 route0 相对 route1 为 6 改善/2 恶化、mean margin delta +2205.5。样本很小，只足以启动验证，不能宣称胜出。
- **最小实验**：KG-004 仅在 Yarn-second 保留 route0；seeds 15001–15024 × 9 opponents × 双座位，过门后才做至少 32 新种子确认。
- **预期指标**：总计分率、逐 opponent 净变化、P10/worst delta、Yarn-second 命中数与目标失败率。
- **成本/风险**：中等仿真；Yarn-second 稀疏、8 单元小样本及隐含 controller 状态风险。
- **停止条件**：总计分率不严格提高、任一 opponent 净退化、P10<-500、worst<-2500、命中<8 或失败未降 30%，任一触发即停止。
- **回执**：精确条件和历史数值已送达协调源；KG-004 正在项目线运行。

### X-KAGG-005 → 协调源（已送达停止收据）

- **来源**：KG-004 的 432 局比较 JSON 与实验账本。
- **事实**：66 个 Yarn-second 命中单元中，KG-001 失败 6、route0 失败 28，净少 18 计分点；P10 -11,356、worst -13,397 delta；全局 mean margin -1,155.61，bootstrap score-rate 95% `[-9.26%,-0.23%]`。
- **结论**：历史 8 单元正收益是抽样反转；冻结 Yarn-second route0，不确认、不提交。
- **最小实验**：只读分类 KG-001 失败，要求 step168 前可见状态桶覆盖至少 8 单元、两类对手与双座位，另种子方向一致后才生成 guard。
- **预期指标**：桶支持/覆盖、失败率、margin/P10/worst、首次分歧与 replay 索引。
- **成本/风险**：低审计；失败反向选桶、seed 重用、off-by-one 与远端非配对偏差。
- **停止条件**：无跨对手/座位重复桶即保持 KG-001；Pizza/Smoothie/Yarn-second route0 不重开。
- **回执**：完整反转数值与冻结结论已送达协调源。

### X-KAGG-006 → Kaggriculture / 协调源（已送达官方最终评分策略）

- **来源**：Kaggle staff discussion 732931/739410，访问 2026-09-09。
- **事实**：Final B-T 只计双方最终仍 active 的全赛期 episodes；team 取两个 active submissions 中较好者，第二槽无下行；ties=half-win。
- **最小动作**：KG-001 锁一槽；第二槽只从 error-free 安全 anchor 与通过状态桶门的互补 guard 中选，用 paired seeds×双座位×两类以上对手比较单槽 W/T/L、独占胜局与 union coverage。
- **预期指标**：双槽 union win coverage、各槽独占胜局、P10/worst、运行错误率；live rating/margin 不作主指标。
- **成本/风险**：低中配对仿真；对手退场会让历史不计，第三次提交会挤掉旧 active agent。
- **停止条件**：第二候选无独占胜局、出错或尾部退化即保持安全 anchor；禁止为 rating reroll 淘汰冻结槽。
- **回执**：官方规则、双槽含义和最小选择门已送达项目线与协调源。

### X-KAGG-007 → 协调源（已送达 KG-005 停止收据）

- **来源**：`kaggriculture/reports/experiment_ledger.md`；KG-005 的 432×2 配对开发矩阵。
- **事实**：公开 TOMATO-heavy、step576 late-switch 只命中 4 单元，低于支持门 8；KG-001 目标层 4-0-0、mean +6,751，候选 0-0-4、mean -10,191，mean delta -16,942。其余 428 局相同；全局 score rate -0.926pp，cluster bootstrap 95% `[-2.31%,0]`。
- **结论**：该公开状态只是失败相关量，不能证明同步 continuation 应切换；冻结阈值与 late-switch 家族，不确认、不提交、不重调。
- **最小动作**：只读对齐 KG-000/KG-001 的 `(opponent, seed, seat)` 共享键，计算各槽 W/T/L、独占胜局、union coverage、P10/worst 与错误；共享支持不足时才跑一个固定双锚点批次。
- **预期指标**：第二槽必须贡献重复、跨对手/双座位的独占胜局，且不恶化尾部或错误率。
- **成本/风险**：低成本审计，必要时中等固定仿真；风险是非配对键、稀疏独占胜局及把分差当最终 B-T 主目标。
- **停止条件**：无可靠共享支持、无独占胜局、尾部恶化或有运行错误，即保持 KG-001+KG-000，不生成第三代理。
- **回执**：停止数值和下一步双槽互补性门已送达协调源。

### X-KAGG-008 → 协调源（已送达 100 局成熟门决策）

- **来源**：`kaggriculture/reports/remote_maturity_gate_100_2026-09-09.json`；source summary SHA-256 `8188d401…`。
- **事实**：public 101 局 70-6-25、72.28%、rating 2325.0、P10 −3,268、worst −14,465；hybrid 100 局 74-7-19、77.50%、rating 2584.2、P10 −1,393.1、worst −20,432。两者全 `DONE`、零 stderr。
- **结论**：hybrid 是当前较强 live submission；public 保留独立策略和更好的已观察 worst，符合官方 best-of-two hedge。live 局非配对，不声称 union/因果收益。
- **最小动作**：继续只读监控两个冻结槽，不上传、替换或停用；只有先过固定多对手双座位保护门的新机制才允许挑战槽位。
- **预期指标**：每槽 W/T/L、rating、P10/worst、双座位、非 `DONE`、stderr 与动作时延；新候选另需独占胜局和 union coverage。
- **成本/风险**：低成本同步；风险是短期 rating 噪声、非配对归因和对手最终退场。
- **停止条件**：无合格配对新候选就保持两槽静默；任何新候选尾部恶化、无重复独占胜局或有运行错误即停。
- **回执**：成熟门数值与“保留两槽、零远端变更”决策已送达协调源。

### X-KAGG-009 → 协调源（已送达 KG-006 终局现金实验门）

- **来源**：官方环境结算审计、100 局自有公开回放、`prefix_audit_smoke_kg006_16999.json`。
- **事实**：public/hybrid 有 34/11 局终局留下可卖库存；step718 是最后行动，市场随后执行，final reward 只取 cash。seed16999 双座位 smoke 均 `DONE`、first diff=718。
- **单一变更**：step0–717 不变；step718 保留 farmer/hands/market 顺序，只把已有 SELL 提足并按固定产品序填剩余≤10 slots。
- **最小实验**：17001–17024×9 opponents×双座位，保存分歧前状态；过门后才进不重叠≥32 seeds。
- **预期指标**：总体/逐对手 W/T/L、P10/worst、目标命中/失败减少、额外 cash、first diff、运行错误。
- **成本/风险**：中等 432×2 仿真；10-slot 限制、执行顺序、极大数量与库存相关性。
- **停止条件**：总体不严格提高、任一对手净少、P10<−500、worst<−2500、命中<8、失败未减30%、first diff≠718 或错误即停；不提交。
- **回执**：假设、环境因果边界与固定开发门已送达协调源。

### X-KAGG-010 → Kaggriculture / 协调源（已送达 KG-006 严格停止收据）

- **来源**：`compare_dev17001_17024_terminal_sweep_vs_v1.json`，SHA-256 `a87ac48c…`。
- **事实**：432×2 全 `DONE`；baseline/candidate 都是 360-38-34、379 分、87.73%。候选 50 格 margin 改善、382 不变、0 退化，均值 +51.61，bootstrap mean-delta 95% CI `[+6.28,+105.80]`；但 score-rate delta 恒为 0。
- **目标边界**：50 个库存命中格 mean +445.88、P10 +483、worst +5，但基线本来就是 50-0-0，失败减少门不可满足。
- **结论/停止**：现金回收机制成立，胜分改进未成立；严格停止，不确认、不提交、不事后改门。public+hybrid 两槽保持冻结。
- **回执**：精确门失败、哈希和“margin 不等于 W/T/L”边界已送达 Kaggriculture 与协调源。

### X-KAGG-011 → Kaggriculture / 协调源（已送达 149/140 局成熟更新）

- **来源**：`remote_maturity_update_149_140_2026-09-09.json`，SHA-256 `6bd09ec9…`。
- **事实**：public 149 局 86-11-52、61.41%、rating2272、P10 −6,419.8、worst −35,237；hybrid 140 局 85-16-39、66.43%、rating2554.4、P10 −2,516.4、worst −20,432。hybrid 在 rating/rate/mean/P10/worst 全领先。
- **纠错/边界**：旧“public observed worst 更好”已失效；自 100 局门后两槽新增计平局胜率都约 38.5%，live games 非配对，不能作因果 union。
- **结论/停止**：无新候选过本地门，仍保留两槽且零远端变更；不因回落追涨杀跌，只读监控。
- **回执**：新成熟数值、旧叙述纠错与保持两槽理由已送达两任务。

### X-KAGG-012 → 协调源（已送达 155/144 局成熟与失败分层更新）

- **来源**：latest summary SHA `7046576e…`；`remote_failure_audit_155_144_2026-09-09.json` SHA `7b5af91c…`，只读且无 submission change。
- **事实**：public 155 局 89-11-55、60.97%、rating 2273.1、mean 6,350、P10 −7,754、worst −52,908；hybrid 144 局 87-16-41、65.97%、rating 2552.5、mean 6,831、P10 −2,639、worst −20,432。hybrid 仍全指标领先。
- **成熟解释**：100 局后增量计分率约 39.81%/39.77%，两槽同步遇到更难赛场；非配对 aggregate 不作因果 A/B。两者各有 5 局 step718 cash gap 非负仍输，不能据此复活 KG006。
- **停止**：两槽继续 active；KG006 保持失败，不立 KG007、不确认、不调阈值、不上传/替换/停用。
- **回执**：精确读数、隐私边界与 HOLD 决策已送达协调源。

### X-KAGG-013 → Kaggriculture / 协调源（已送达官方终局与订单上限语义）

- **来源**：Kaggle 官方 `kaggle-environments` 的 AGENTS/README/source；本地固定 1.32.7，核心 source SHA `bc8a5487…`，访问 2026-09-09。
- **事实**：默认 720 turns；季末 reward 直接取 bank money，unsold inventory 不计；最终周期先处理 market 再写 reward。每方 market 只执行前 10 单，之后静默丢弃。
- **决策影响**：KG006 的 +51.606 margin/零 W/T/L delta 继续是严格停止，不以 cash-only 复活。若未来另立实验，只能预先固定含 baseline tie/loss 的双座位池，并冻结已有订单顺序与清仓插入规则。
- **指标/风险/停止**：逐格记录 `order_slots_before`、清仓单 index、accepted sell qty/value、dropped-order count、final W/T/L；订单落到第 11 项以后、first-diff/合法性异常或无 W/T/L 翻转即停。不得从当前 50 个全胜命中格事后挑样本，不自动生成候选/提交。
- **回执**：官方链接、引擎顺序、10-slot 风险与继续冻结判决已送达 Kaggriculture 和协调源。

### X-KAGG-014 → Kaggriculture / 协调源（已送达 157/146 动态与封存边界）

- **来源**：latest summary/maturity/failure SHA `756db359…` / `70b2a9b4…` / `99f1cece…`；campaign completion audit SHA `a9929421…`。
- **事实**：public 157 局 90-11-56/rating2273.6/60.83%/P10−8,215.8；hybrid 146 局 88-16-42/rating2554.5/65.75%/P10−2,822。相对 155/144 两边均新增 1-0-1，仍非配对。
- **边界/停止**：completion audit 只关闭 cutoff 155/144 的既定 research scope；157/146 是后续 heartbeat 动态，不可用旧 completion receipt 冒充当前数字。零 candidate/confirmation/submission/slot change，继续双槽冻结。
- **回执**：精确新读数、收据时点差和只读监控决策已送达 Kaggriculture 与协调源。

### X-POKER-005 → Poker / 协调源（已送达）

- **来源**：`poker/EXPERIMENT_LEDGER.md` 的 E005 预注册与 E004 负结果。
- **事实/干预**：只移除 KS≥0.075 的 `__max`/time-bin，开发集 `shared_hands_calc×2/3`，`dominant_flow_bb` 改为每 100 shared hands；其余 E001 特征、learner、标签、种子、folds 不变。
- **最小实验**：同一 whole-pool OOF 重跑一次；通过后只做 time-block stability，不直接提交。
- **预期指标**：Pair AP delta≥-0.015、worst≥-0.03、score KS reduction≥30%、P95 delta≥-0.02、|Spearman|≤0.10。
- **成本/风险**：低至中；风险是 exposure 校正错误或损失有效幅度。
- **停止条件**：任一门失败即冻结 exposure-normalization 家族；`MI_proxy` 继续延后。
- **回执**：E005 的精确改动与门槛已送达 Poker 和协调源。

### X-TRAFFIC-004 → Traffic（已送达质量门）

- **来源**：0.74210 锚点、Task 1 density smoothing -0.0000155 负结果，以及 Traffic 提出的 onset top1/top2 bottleneck 探针。
- **事实/边界**：此前 topology、density smoothing、complex queue 均已失败；只允许再回答一个 Queue 问题，不能与其他组件联改。
- **最小实验**：结果前独立入账，记录自然键/精确改行；只改 onset 最终时间戳的 top1 vs top2，检查两个互斥封存日期和 8 corridors，其他 Queue 与 State/Physics/ODME 逐字节不变。
- **预期指标**：两个日期和各 corridor 的同向 proxy 改善，以及预注册远端最小总分增益。
- **成本/风险**：低成本窄探针、至多一个提交槽；风险为榜邻域过拟合和局部 corridor 损伤。
- **停止条件**：日期冲突、corridor 退化或无正向 proxy 下界即本地停止；完成该探针后无独立证据不得再开 Queue。
- **回执**：质量门已送达 Traffic；等待其独立预注册或停止收据。

### X-POKER-006 → 协调源（已送达停止收据）

- **来源**：`poker/work/E005_exposure_validation.json` 与实验账本。
- **事实**：E005 的 Pair AP +0.002633、worst +0.002232、P95 +0.008065、|Spearman|=0.082221；但 score KS 0.061287→0.168920，恶化 175.62%，严格 FAIL。
- **最小动作**：冻结 E004/E005 和 exposure/rank normalization；当前仅原参数复现公开 PU notebook，建立带来源、许可证、哈希及时间块审计的参考锚点。
- **预期指标**：confirmed Pair AP、PU stress、Behavior/Evidence OOF、coverage、最差折和 early/late 稳定性。
- **成本/风险**：中等五折复现；风险是 PU proxy 冒充真值、复现时改参、ID/行序泄漏和 evidence hand 非共享。
- **停止条件**：任何合规/可重跑守卫失败即停；即使复现更强也不直接提交，必须做单特征族 owned ablation。
- **回执**：完整数值与“禁止继续调 exposure 家族”已送达协调源。

### X-POKER-007 → 协调源（已送达复现收据与新门）

- **来源**：`public_pu_ranker_repro_report.json` 与 E007 预注册。
- **事实/边界**：E006 原参数复现 Pair AP 0.934033，弱于 E001；Behavior MAP 0.831020、Evidence OOF MAP@5 0.443468，562,700/562,700 evidence hands 合法，ID features=0、unknown truth=0。只作公开参考，不提交。
- **最小实验**：E007 在 E001 raw95/confirmed-only/同 folds 上，只增加 41 个 partner/outsider action-response aggregates；不引入 E006 的 learner、PU weight 或 ranker。
- **预期指标**：Pair AP、worst fold、P95 separation、score KS 与 shared-hands Spearman。
- **成本/风险**：中等一次 OOF；风险为 interaction 隐含 exposure/时间漂移及来源归属混淆。
- **停止条件**：Pair AP delta<-0.005、worst<-0.02、P95<+0.01、KS 恶化>0.02 或 |Spearman|>0.10，任一触发即归档；通过仍需 early/late stability。
- **回执**：E006 全量数值、合规边界和 E007 精确门已送达协调源。

### X-POKER-008 → 协调源（已送达暂缓晋级提示）

- **来源**：E007 validation 与文件路径审计。
- **事实**：暂定指标全门通过，但 evaluation feature/score 曾同名，score 覆盖 feature；旧 validation 仍引用同一路径与同一 hash。
- **最小验证**：分离重建两份文件，校验独立 schema/row count/hash，并要求模型指标逐值复现。
- **预期指标**：Pair AP +0.010512、worst +0.016993、P95 +0.021505、KS delta +0.010646、|Spearman| 0.096058 均保持。
- **成本/风险**：低；风险是不可复核收据支撑漂亮结果。
- **停止条件**：任一文件或指标不一致即降回未验证/失败；修复前不做 early/late、不提交。
- **回执**：PROVISIONAL 风险已立即送达协调源。

### X-POKER-009 → 协调源（已送达修复确认与时间门）

- **来源**：修复后的 E007 validation、ledger 与 E007b 建模前 coverage 断言。
- **事实**：feature/score 已分离重建并有独立 hash，主数值逐值一致，E007 正式 PASS；E007b 因 10/1,860 pairs 单半段覆盖而在建模前中止，尚无结果。
- **最小实验**：只在前后半都有共享手的 label-blind 交集上做 early→late/late→early；单列排除 10 对标签/家族分布，其他门不变。
- **预期指标**：双向 delta、worst fold transfer、worst cross-time AP、方向 gap 与排除集富集。
- **成本/风险**：中等双向五折；时间/exposure 记忆与交集选择偏差。
- **停止条件**：双向 delta<-0.005、worst<-0.03、cross-time AP<0.90、gap>0.05 或排除富集，任一触发即撤销 E007；通过仍不直接提交。
- **回执**：暂缓提示已由修复确认替代；新时间门已送达协调源。

### X-POKER-010 → 协调源（已送达撤销晋级结论）

- **来源**：`E007_time_stability.json` 与 Poker 实验账本。
- **事实**：early→late/late→early 的 interaction delta 为 +0.028871/+0.037958，worst-fold delta +0.005628、方向 gap 0.011158；但 worst cross-time AP 0.852369 < 预注册 0.90，gate=false。
- **决策**：撤销 E007 提交资格，不生成候选、不接 PU；保留为真实但不足的机制证据。
- **最小下一步**：只读分层 held-out OOF；只有非 ID/时间/exposure 的残差族在双向与至少四折复现，才另立不同方法族 E008。
- **成本/风险/停止**：低成本审计；防事后挑子群和 exposure 代理。没有跨方向/折复现即停。
- **回执**：精确门值、哈希边界和换族结论已送达协调源。

### X-POKER-011 → Poker / 协调源（已送达条件互信息换族建议）

- **来源**：Bonjour et al., UAI 2022 / PMLR 180，<https://proceedings.mlr.press/v180/bonjour22a.html>。
- **事实/边界**：论文用 state-conditioned directional action MI 衡量顺序博弈 influence，并减去 outsider 对目标玩家的最大 influence；只在三人 Leduc/合成 collusion 上验证。
- **最小实验**：raw95 只加平滑 `i→j/j→i` CMI、outsider-max 净影响与 episodic concentration；严格 action-before 可见 state、same whole-pool OOF，不用 ID/row order/unknown negatives，并直接跑 early↔late。
- **预期指标**：Pair AP、worst fold、双向 transfer delta、worst cross-time AP、shared-hands 相关/消融。
- **成本/风险**：中等 CPU；稀疏 state、次序错位、曝光混杂、与 E007 重复。
- **停止条件**：支持不足、shared-hands 主导或旧主门/时间门任一失败即冻；绝对 cross-time AP 仍须≥0.90。
- **回执**：机制、Leduc 外推边界和完整门禁已送达 Poker 与协调源。

### X-POKER-012 → Poker / 协调源（已送达 E008 严格失败收据）

- **来源**：`poker/work/E008_marginal_impact_validation.json`，JSON SHA-256 `7ce5f569…`。
- **事实**：单一 marginal-impact scalar 的 confirmed AP +0.000373、worst fold +0.003156、P95 rate +0.005376，KS 小幅改善 0.000454，`|Spearman|=0.083209`；但 early→late delta −0.000284 未达预注册 +0.01，late→early +0.010547 刚过。worst time fold −0.012156、direction gap 0.012902 过门，仍不能覆盖单向失败。
- **合规边界**：whole-pool folds；E007 interaction 未混入；24,000 unknown labels assigned=0；ID 仅 join，不作特征。
- **结论**：E008 gate=false，不晋级、不提交、不调 shrink/winsor、不接 PU；保留为 outcome signal 时间方向不对称的负证据。
- **最小动作**：只读审计 raw95 的双向 drift/行为族支持；只有两方向、至少四折、非 shared-hands/exposure 的机制才允许立 E009，并直接跑 matched early↔late。
- **预期指标**：两方向 AP delta、worst time-fold、gap、主 OOF/worst fold、KS、Spearman 与支持数。
- **成本/风险**：低只读审计；有机制时一次中等 30-fit OOF。风险为时间暴露量漂移、稀疏行为族和事后挑桶。
- **停止条件**：无重复机制即停止新特征搜索；E009 任一方向 <+0.01 或任何旧守卫失败即冻结。
- **回执**：精确数值与“其他通过项不能覆盖 early→late 失败”已送达 Poker 和协调源。

### X-POKER-013 → 协调源（已送达 E009 预注册）

- **来源**：Poker E009 ledger；Bonjour et al. UAI 2022 机制约束。
- **单一变更**：折内 action-before-state conditional MI，`n/(n+50)` 收缩、减 max outsider，pair 只取双向净影响的最小值；full/eval/early/late 独立重算。
- **合规边界**：禁 result/cards/ID/order/label/future，unknown latent；E001 learner/seeds/folds 不变，不混旧特征族或 PU/evidence。
- **预期指标**：feature Spearman≤.20；AP≥+.003、P95≥+.005、双向 time≥+.01、worst CMI cross-time≥.84，且 worst fold/KS/model Spearman/time-fold/gap 全守卫。
- **成本/风险**：中等 matched OOF；稀疏 state、次序错位、outsider 支持和 exposure 混杂。
- **停止条件**：任一门失败即归档 exact feature，不调 shrink/threshold、不提交。
- **回执**：完整时序定义、合规边界与联合门已送达协调源；当前无结果主张。

### X-POKER-014 → Poker / 协调源（已送达 E009 严格失败收据）

- **来源**：`poker/work/E009_influence_validation.json`，SHA-256 `2dc72e4d…`。
- **事实**：confirmed AP delta `−0.000811`；early→late `−0.003672`；late→early `+0.001823`；worst influence-transfer AP `0.819826`。对应门分别为 `+0.003`、双向 `+0.01`、`0.84`，四项均失败。
- **保护项**：worst fold、P95、KS、feature/model Spearman、worst time-fold、direction gap 均过；unknown labels assigned=0。次级通过项不覆盖主门失败。
- **结论/停止**：冻结 same-street conditional-information/influence 特征族；不提交、不调 shrink/state buckets、不与旧族堆叠。局部结构特征搜索停止，先做零模型 drift 审计，未发现跨方向/四折机制就不立 E010。
- **回执**：机器收据、精确门和停止决策已送达 Poker 与协调源。

### X-POKER-015 → 协调源（已送达 E010 全局排序目标预注册）

- **来源**：Poker E010 ledger 与 pool-query feasibility audit。
- **事实**：397 个有 confirmed labels 的 pools 中 152 全负、5 全正、仅 240 正负混合；逐 pool ranker 会丢掉大量可信梯度。
- **单一变更**：E001 raw95/confirmed-only/whole-pool held-out 不变，只换成 deterministic LightGBM LambdaRank，全部 confirmed pairs 为一个 global query；冻结 280 trees、lr 0.035、15 leaves、min child 12、L2 3.0、feature fraction 0.9，固定 sigmoid、无拟合校准。
- **合规边界**：无 E007/8/9、PU、Behavior/Evidence、ID/order；unknown latent，仅 stress；baseline 不重训。
- **预期指标/停止**：沿用 AP、worst fold、P95、KS、Spearman、双向 time、worst transfer 与 gap 联合门。任一失败即冻结 objective，不调树/sigmoid/query；通过也不授权提交。
- **回执**：换族理由、固定参数、联合门与零提交边界已送达协调源。

### X-POKER-016 → Poker / 协调源（已送达 E010 灾难性失败收据）

- **来源**：`poker/work/E010_pairwise_validation.json`，SHA-256 `4504d433…`。
- **事实**：confirmed AP `−0.248896`、worst fold `−0.189394`、P95 `−0.319892`、KS `+0.459071`、`|Spearman|=0.120867`；两个时间方向 `−0.181126/−0.254473`，worst transfer 0.571096。所有主门失败，unknown labels assigned=0。
- **结论/停止**：global-query LambdaRank 与本题分类结构不匹配；冻结 objective，不调 query/tree/sigmoid、不提交。
- **回执**：完整灾难性失败向量与停止决策已送达 Poker、协调源。

### X-POKER-017 → 协调源（已送达 E011 分阶段 hard-negative 预注册）

- **来源**：Poker E011 ledger。
- **单一变更**：outer fold 内 pilot E001 只对 confirmed negatives 排序；最高四分位权重 2.5、其余负类 0.5、正类 1.0。E001 features/learner/folds 不变，global OOF/unknown/PU/旧特征族均不参与 mining 或 fit。
- **最小实验**：Stage A 先跑主 OOF、worst fold、P95、KS、Spearman；过门才各自在 early/late outer-training half 内重算 hardness 并跑双向时间门。
- **成本/风险**：中等 nested OOF，Stage A fail-fast；风险为 in-sample hardness 强调噪声、固定权重改校准、嵌套边界错误。
- **停止条件**：任一 Stage A 门失败即不做 time fits；时间门失败也归档，不调 quartile/weights；通过不授权提交。
- **回执**：嵌套信息边界、分阶段成本控制和联合门已送达协调源。

### X-POKER-018 → Poker / 协调源（已送达 E011 Stage A 停止收据）

- **来源**：`poker/work/E011_hard_negative_validation.json`，SHA-256 `6202cc35…`。
- **事实**：confirmed AP `−0.002598`、P95 `−0.005376`、`|Spearman|=0.117752` 三门失败；worst fold `−0.008371`、KS `+0.016531` 过线。unknown labels assigned=0。
- **成本控制**：`time_gate_status=not_run_stage_a_failed`，按设计没有支付双向 time fits。
- **结论/停止**：冻结 75% quantile 与 2.5/0.5 weights，不调参、不提交。E007b–E011 连续失败后暂停自动立实验；先做只读共同残差/边界综合，无独立双向/四折机制就保持 E001。
- **回执**：精确三门失败、fail-fast 状态和暂停搜索建议已送达 Poker 与协调源。

### X-POKER-019 → 协调源（已送达 E012 独立 PU 预注册）

- **来源**：post-E001 stop-loss plan、E003 收据与 Poker E012 ledger；不是 E011 的事后调参。
- **依据**：E003 bagged PU 的 AP/P95/P99 为 `+0.005981/+0.013441/+0.026882`，原计划已要求另测 Elkan–Noto；此前只因 median 指标饱和而停。
- **单一方法**：raw95/whole-pool outer folds 固定；临时 selector `s` 区分 confirmed target 与 confirmed-negative+latent unknown，unknown 总权重归一，outer-training 内三分 pool split 估 c，outer validation 不进 fit/c，indicator 不持久化。
- **最小实验/门**：Stage A 先检查 AP、worst、P95/P99、KS、Spearman；通过才独立跑 early/late，要求双向不退、worst transfer≥0.82、gap≤0.05。
- **成本/风险/停止**：中等 fail-fast；SCAR/c-estimation/selection-shift 风险。任一门失败不跑后段、不调参、不提交，unknown 保持 latent。
- **回执**：历史立项依据、PU 信息边界与分阶段门已送达协调源。

### X-POKER-020 → Poker / 协调源（已送达 E012 方法审计与 time 前停止）

- **来源**：Elkan–Noto 原论文、Bekker–Davis SAR 论文、`E012_elkan_noto_validation.json`（SHA `cac16b65…`）与纠正引文元数据后的 `E012_methodology_audit.json`（SHA `d41d4525…`）；数值、方法边界和 `STOP_BEFORE_TIME` 不变。
- **数值**：原 Stage A 的 AP/worst/P95/P99/KS/Spearman 均过；但 overall=false、time=`required_not_run`。
- **方法缺口**：inner g 估 c 后改用 full-refit g 出分；unknown aggregate downweight 改变自然 P∪U 基率；outer-valid clip-to-one 10.78%–15.55%，251/1,860 labelled scores=1、unique 仅 86.56%，对比 eval clip 0.26%，不符合 faithful constant-scaling 的同尺度条件。SCAR 本身也未证。
- **结论/停止**：只保留 unknown-aware selector 开发信号，标 method mismatch；不跑时间、不提交、不在同一编号修法。本轮禁止自动 E013；未来新 ID 必须 same-g/c rotation 或可证抽样权重及饱和/唯一值守卫。
- **回执**：在时间阶段尚未打开时，原文边界、数值与停止决策已送达 Poker、协调源。

### X-POKER-021 → 协调源（已送达五实验残差综合）

- **来源**：`E007_E011_failure_audit.json`，SHA `a82ce20e…`。
- **事实**：raw isolation AP 0.716667 远低于 directed/soft；E007 唯一 full 与双向 time 同增，isolation full 0.804722、双向 0.572214/0.497086，净去除 1,589 inversions，mixed pools 9 win/4 loss/227 tie。
- **下一提案**：只做 behavior-conditioned target 设计评审；directed/soft 用 raw E001，E007 interactions 只给 isolation head。先解决 evaluation family 未知造成的循环路由并预注册，不自动运行。
- **停止条件**：无法构造 solution-blind、无 ID/unknown-negative、跨时间可评的路由就保持 E001，不立 E013。
- **回执**：稳定瓶颈、局部真信号与设计评审边界已送达协调源。

### X-POKER-022 → 协调源（已送达 B001 行为可测性结果）

- **来源**：守卫加固后的 `B001_behavior_audit.json`，SHA `02e7e03e…`；OOF 数值未重跑，不是 E013、候选或提交。
- **最小审计**：冻结 E001 risk，只用 confirmed targets 在原 whole-pool folds 上做 raw95 三类 family OOF；固定 active-rate grid，不选择阈值、不打 evaluation、不加 interaction、unknown labels=0。
- **关键指标**：accuracy、macro/per-family recall、confusion、log loss/Brier，以及三家族 AP/MAP；official `pair_id` 零分并列顺序只作复现，同时报 512 次 random-tie 期望和解析 bounds，只有 random-tie 可用于诊断。
- **结果**：全期 accuracy/macro recall 0.943548/0.938447；双向为 0.852151/0.847081 与 0.879032/0.869046，isolation recall 0.804348/0.782609。4% random-tie MAP 为 0.262344/0.261408/0.259238，official-order 高出约 0.012595/0.012844/0.006635；100% random-tie 双向又比 full 低约 0.165–0.176。
- **完整性/停止**：time receipt SHA 与 full/time pair-fold 必须消费前精确匹配；confirmed labels 仅覆盖 397/400 gameplay pools，3 个空标注 pools 不可外推。routing 可测但有时间漂移；只足以进入新编号、结果前冻结的单模块设计评审，未证明 pair-risk/evaluation 提升。B001 不得触发 E013、risk fit、evidence reconstruction 或 submission；未来门只认 random-tie，另设 isolation 双向 stop。
- **回执**：更正后的 E012 audit SHA `d41d4525…`、B001 结果/完整性与停止边界已送达协调源。

### X-POKER-023 → 协调源（已送达公开刷新与 EV000 evidence 可行性）

- **来源**：public inventory SHA `9b3adde3…`；EV000 v2 audit SHA `85adea3b…`、状态 `PASS_CURRENT_BINDING`，绑定 implementation/report/draft-v2 为 `7518ed87…` / `27a8245e…` / `a689703b…`。
- **公开结论**：当前仅 3 个 public notebooks 且全已本地覆盖，无新方法族；public ranker 的可复用模式只有共同 outer fold + cross-fitted family routing，其同 OOF 调 rate/外层选树/Grouped-tie 等不能直接继承。
- **支持量**：372 targets、1,817 evidence hands、45,129 candidate rows；full/early/late pairwise preferences 为 212,888/82,266/42,763，early 有一个必须保留的 zero-preference directed query。cross-time 最小 source/validation pairs 为 early→late 68/7、late→early 35/15；late-isolation 五折 pairs 仅 7/11/12/10/7。
- **绑定纠错**：旧错绑 audit 以 `PROVISIONAL_HASH_MISMATCH`/`e5d8293a…` 保留，原 draft-v1 恢复，amendment 另存 v2；current audit 从 11 个 sources 重建，未覆盖历史。H0 full/双向跨 rank5 tie blocks 为 65/70/70，当前 timestamp 可解析；未来 timestamp 仍并列则 stop，无 ID/行序 fallback。
- **停止**：v2 PASS 只证明可实现；draft execution forbidden、无 E-number/model fit/performance/eval/submission。只有另行监督批准后才可评审 inner-only predicted-family 设计，禁止 true-family inner routing，并保留 late-isolation/zero-preference/tie stop。
- **回执**：公开负结果、绑定修复、结构薄点与执行锁已送达 Poker/协调源。

### X-POKER-024 → 协调源 / Poker（已送达 pool 依赖与 bootstrap 未定义反例）

- **来源**：pool provenance SHA `eb11f452…`；bootstrap support SHA `71b02ce0…`；均为绑定 v2 的只读 companion。
- **事实**：372 queries/245 pools，62 个 pool 跨 family、53 个 family-pool 含多 query，故唯一合法 cluster 是 `table_id`。ordinary pool bootstrap 在 early→late fold0 以 0.00145855 概率抽空 isolation，5,000 次期望 7.293 个空 replicate；fold4 期望 2.320 个。独立概率重算通过。
- **影响/停止**：v2 未冻结 reject/omit/zero-fill，family/macro CI 未完全定义；不得实现或运行，不得独立抽 hand/query、分 family 抽样或结果后丢空 replicate。
- **待审动作**：若监督另行允许，只起版本化 amendment，预先冻结 seed12673、5,000 次 paired Bayesian `table_id` bootstrap、共享 Exp(1) pool 权重与 exact weighted aggregation。amendment 本身不授权模型/evaluation/submission。
- **回执**：纠错、定量反例和安全替代已送达两任务。

### X-POKER-025 → 协调源 / Poker（已送达 Bayesian cluster-weight 区间语义纠错）

- **来源**：Rubin 1981 Bayesian bootstrap、Field & Welsh 2007 clustered bootstrap、Praestgaard & Wellner 1993 exchangeably weighted bootstrap；均为原论文/期刊来源，访问 2026-09-09。
- **事实/推断边界**：`Exp(1)`/Dirichlet positive pool weights可保留所有 family support，cluster 级抽样可保留组内依赖；但 Bayesian bootstrap 给后验权重分布，cluster 方差一致性依赖模型，exchangeably weighted CLT 也有条件，不能直接保证 34–52 pools/fold 上非线性 AP@5 的 frequentist coverage。
- **动作**：拟议 amendment 应冻结 query-weighted overall、family 内 weighted mean、三 family 等权 macro 与同 draw paired delta；无预注册 coverage simulation 时命名“90% paired Bayesian cluster-weight sensitivity interval”，不称 CI。
- **停止**：若区间语义仍写 frequentist CI、weighted aggregation 未固定，或用真实结果调模拟，则不运行。文献边界已送达两任务；仍无模型/evaluation/submission 授权。

### X-POKER-026 → 协调源（已送达 v2 withdrawal 与 v3 静态收据）

- **来源**：v2 withdrawal SHA `98b1cea1…`；Bayesian feasibility SHA `7a89801e…`；v3 draft/static-audit SHA `9464378b…` / `cfe4f8da…`。
- **事实**：v2 hash-binding PASS 保留，但方法执行资格因 bootstrap 空格未定义而撤销。v3 已冻结 seed/RNG、5,000 paired pool weights、共享配对、weighted query/macro、linear quantiles 与 no reject/omit/zero-fill；45 denominators 全正，最小 1.0232903，weight stream `c833ac7d…`。
- **边界/停止**：状态仅 `PASS_DRAFT_ONLY_AWAITING_SUPERVISION`；implementation/model/performance/evaluation/submission=false、无 E-number。结合一手文献，需先把 interval 明确为 Bayesian sensitivity interval；监督未接受前不得实现。
- **回执**：版本替代、静态完备度与剩余语义门已送达协调源。

### X-POKER-027 → Poker / 协调源（已送达 v3 区间语义闭环）

- **来源**：v3 draft/static-audit 最新 SHA `54776c54…` / `a45c55aa…`；状态仍 `PASS_DRAFT_ONLY_AWAITING_SUPERVISION`。
- **闭环事实**：名称已固定为 `90% paired Bayesian cluster-weight sensitivity interval`；lower endpoint 只作扰动鲁棒性门，明确不代表 confidence/credible/coverage/significance/posterior probability。误称会在 aggregate performance 可见前 stop。
- **边界/停止**：实现、fit、performance、evaluation、submission 仍全 false，无 E-number。语义缺口已关闭，但监督许可未关闭；静态 PASS 不得自授权执行。
- **回执**：新 current hashes、旧 hashes 历史化和剩余唯一审批门已送达 Poker 与协调源。

### X-POKER-028 → Poker / 协调源（已送达 implementation-only 授权纠正与 containment 门）

- **监督纠正**：协调源确认此前已有明确 `IMPLEMENTATION_ONLY_APPROVED`；因此 v3 代码实现本身不越权，我已撤回先前的相反边界判断并同步 Poker。
- **事实闭环**：旧 `EVP_prereg_v3_static_audit.json` 的 `implementation_created=false` 只代表实现前快照；新 containment receipt SHA `f04b1096…` 已以 `PASS_IMPLEMENTATION_PRESENT_UNEXECUTED` 绑定 core/runner `5871093c…` / `5a0f5aec…`，且不改旧文件。收据报告 17/17 EVP、23/23 repo tests 与 synthetic integration，real fit/performance=false。
- **仍未授权**：真实数据模型拟合、aggregate performance、evaluation rows、E-number 与 submission 均不在 implementation-only 范围；`preregistration_executed=false`。执行器在打开数据路径前拒绝 implementation-only receipt；未来 result-bearing receipt 必须精确绑定 draft、旧静态审计、core/runner 与 containment receipt，并只可消费一次。
- **独立只读核对/回执**：五个源码/测试 SHA 与当前文件相符；consumption 与 validation result/query/pairwise/model outputs 全部 absent。授权纠正、先行 containment 门和最终核验已送达 Poker 与协调源；未运行模型或查看聚合性能。

### X-POKER-029 → Poker / 协调源（已送达 v4 方法规范与 72-cell coverage 审计）

- **来源/判决**：v4 draft/coverage SHA `3a9f2093…` / `4e821092…`；独立结论 `PASS_METHOD_SPEC_ONLY`。
- **事实**：canonical containment 自构造并核 `f04b1096…`，替代路径拒绝；C 在每个 outer fold/view 上只用三 inner folds 的 eligible-query 等权 exact random-tie AP@5，平手取小 C，family 在 score/top5 hashes 后才连接；Stage0→1→2→3 严格单向、失败终止。
- **coverage**：3 views×(1 overall+3 family+5 folds+15 fold-family)=72 cells；query/candidate/evidence 三套聚合零不一致、below-floor=0，full/time floors 为 `(18,2058,90,14)` / `(7,458,17,6)`；两个 early→late isolation cells 恰为 7 queries，任何下降即停。
- **边界/回执**：只证明方法规范内部一致，不授权 implementation、真实数据 fit、performance、evaluation、E-number、candidate 或 submission。结论已送达 Poker 与协调源；未编辑 Poker 文件、未运行模型。下一步若获范围授权，先做实现/source audit，result-bearing run 仍需另批。

### X-POKER-030 → Poker / 协调源（待送达：workspace spend cap）

- **来源/纠错事实**：v4 draft SHA `3a9f2093…` 明示 Stage 1 不得 hash/open/inspect `phase_progress`；runner SHA `4737f3c4…` 却在 Stage 1 对包含该列的 `development_pair_hands.parquet` 做整文件 SHA，随后同文件到 Stage 3 才按列读取 `phase_progress`。列投影不消除先前整文件访问。
- **判决**：当前源码 `REJECT_SOURCE_AS_IS`；containment SHA `f8a2e27b…` 的自审 PASS 和 72-cell 方法 coverage 都不能替代独立 source audit。真实数据/model/performance/evaluation/E-number/submission 继续禁止。
- **最小动作/成本/风险/停止**：监督下修订合同，或结果执行前冻结 Stage-1-only companion/content digest，再独立审计；成本低至中。任何 source audit 未明确 PASS、仍 hash 含 phase 列或试图用测试覆盖合同冲突即停止。
- **送达状态**：已尝试回灌 Poker，但 workspace spend cap 拒绝消息；未重试或绕过，故不得标成已送达。

### X-KAGG-015 → Kaggriculture / 协调源（动态快照，未主动回灌）

- **来源/事实**：`summary_latest.json` SHA `6014c63b…`；public/hybrid 已到 238/231 evaluation games，score-rate 51.47%/50.22%，rating 2166.9/2348.0。相对 157/146，两者分别回落约 9.36pp/15.53pp；hybrid rating 更高但 score-rate略低、worst更差。
- **判决**：高样本成熟度纠正旧乐观快照，但仍是未配对 aggregate，不足以替换槽位或解释因果。两槽保持 active/frozen，KG006 失败不变，禁止 KG007。
- **最小动作/成本/风险/停止**：零新增计算，只读观察；风险是追涨杀跌和把 rating/score-rate差异当策略增量。无结果前冻结的配对机制与新授权即停止升级。为避免重复打扰，未向项目线主动发消息。

### X-HSI-001 → HSI Detection / 协调源（建议稿，未主动回灌）

- **来源/事实**：experiment ledger SHA `60e26ddd…`；CPU mount smoke 终态 `CANCEL_ACKNOWLEDGED`，只有 `Mounting files`，没有目录/list/image receipt；未启动 GPU、模型或提交。
- **建议**：另获授权后先做 5–10 分钟 CPU-only direct competition mount/path preflight，固定最小 listing 与一图 hash；不得直接上传/训练等待中的 B5813。
- **成本/风险/停止**：成本很低；风险是再次耗 notebook quota。限时无路径/list/一图 hash 即停。默认 recommendation-only，未向项目线主动推送。

### X-TARTAN-001 → 协调源（本地已验证，未主动回灌）

- **来源/事实**：E003 ledger 与 release receipt SHA `683f390e…`；只改 tree ceiling 600→1000，public/full-test 0.63142/0.53485。CPU/offline 冷启动 117.42 秒、最大 RSS 723,648,512 bytes，30,644 行输出 SHA `4644bb8e…` exact replay，无平台 routing。
- **迁移价值**：可复用“单变量 + 远端指标 + 资源预算 + exact cold replay”四门；不把 public 分外推私榜。
- **停止**：新候选不能在同级预算 exact replay或 full-test 方向不保留，即回滚 E003。现有项目工件已闭环，未重复打扰项目线。

### X-KAGG-016 → Kaggriculture / 协调源（项目已自收据，未重复回灌）

- **来源/事实**：最新 summary/maturity SHA `d3ce5222…` / `68b33421…`；public/hybrid 各 325 局，score-rate 45.85%/41.85%，rating 2023.8/2116.2。新增 30/34 局 cohort 仅 18.33%/26.47%。
- **判决**：早期乐观读数继续被成熟样本推翻，但两槽仍各占 score-rate/mean 与 rating/P10 优势，且数据未配对。继续 active/frozen，无 upload/replacement/deactivation，禁止 KG007。
- **成本/风险/停止**：零新增计算；风险是追涨杀跌或把 rating 当 causal A/B。无结果前配对机制与另行授权即不改槽。项目线已自产同一结论，故不重复打扰。

### X-CUHK-002 → CUHK Large / 协调源（项目已自收据，需用户补注册信息）

- **来源/事实**：Fresh20/final-freeze SHA `f709b47a…` / `f7d268a2…`。真正零历史重叠的 20 QA/clips 上，VLM 12/20，parent 13/20；overall −1、action +3/object −4、halves +1/−2、subject sign p=0.8125。所有晋级门失败，`REJECT_AND_REFREEZE_VLM`，无 candidate/submission。
- **动作/停止**：冻结两份 0.78070 finalists，不扩 VLM、不挑子切片。101/101 artifacts、16/16 model files、2/2 candidates 已通过 final freeze v3。
- **用户依赖**：外部 registration 尚缺 contact email、affiliation、country/region、exact team member names 及条款同意；deadline 2026-09-15 23:55 CST。自动化不得代填。项目线已生成结果收据，本条仅升级用户动作。

### X-BIOHUB-002 → Biohub / 协调源（项目已自收据，recommendation-only）

- **来源/事实**：BH-0003 finalization/validation/analysis SHA `aa7afd49…` / `6c62d8b2…` / `017da5bc…`。run COMPLETE、两方向 16 samples、combined 0.03002；edge Jaccard 0.02770、division 0、node ratio −0.94983、99.596% edge errors 为 missing edges。
- **判决**：有效 diagnostic，但 `do_not_submit`；下一单变量可检验 detection threshold downward calibration，不能再训练 recovery 或混改 tracker。
- **最小实验/成本/风险/停止**：若另获授权，在已下载 OOF 上做预注册小网格，要求两方向、combined、node/edge recall 同时改善并守 FP/fragmentation；成本低。任一方向不改善或 FP/碎片化越线即停。项目线已自产下一方向，未重复发消息。

### X-TREEHSI-001 → Tree HSI / 协调源（项目已自收据，未重复回灌）

- **来源/事实**：v4 report SHA `aa3377d4…`；只改 per-class cap 5k→10k，OA +0.00503，但 AA −0.00743。
- **判决**：按 both-must-improve 门拒绝并冻结，无 test predictions/submission；保留 v3 public 0.10387/rank31。
- **成本/风险/停止**：零新增计算；风险是主 OA 掩盖少数类退化。下一步只有独立方法族在同折同时提高 OA/AA 才重开。项目线已完成同一停止收据，不重复打扰。

### X-TARTAN-002 → 协调源（交付依赖提醒，未主动回灌）

- **来源/事实**：IEEE delivery receipt SHA `4424d258…`；5 页 PDF/source archive 已 content-complete、visual QA PASS，E003 指标与 exact offline replay 保持不变。
- **用户依赖**：仍缺 author name、affiliation、email、public Hugging Face URL、public prediction URL；这些是 final/report form 前置，自动化不得伪造。
- **停止**：placeholder 未清零前不得称 final 或提交。项目线工件已记录，未重复打扰。

### X-CUHK-001 → CUHK Large / 协调源（已送达 small20 小样本反例）

- **来源**：frozen protocol/selection SHA `cfcc3ac2…` / `c96d984b…`。
- **事实/判决**：设计虽是 20 unique QA、10 subjects×2、single/object 各 10、label-free selection，但排除本轮输出后 20/20 qa_id 已在过往 VLM 工件中出现；因此拒绝其作为新 performance/promotion evidence，只准作 reproducibility/pipeline smoke。有效独立单位最多 10 subjects。
- **动作/指标**：当前只读 exact repeat consistency、invalid rate；新的 20 题 screen 须先证明 qa_id+clip 对所有既有 VLM 工件零重叠，并以 subject 做 exact sign p≤0.05，同时类别/固定 halves 均正。
- **成本/风险/停止**：成本是 provenance inventory 和独立小样本运行；风险是重复样本伪独立、subject clustering 与 multiplicity。任一 subject 负、失败>1/20、历史重叠或无真正未见样本即停；通过也只触发更大 subject-disjoint validation，不直接提交。方法反例已送达两任务；未读取本轮性能来改门。

### X-BIOHUB-001 → 协调源（已送达 recovery OOF 活跃性收据）

- **来源/事实**：本地已落盘 runtime/status receipt SHA `d20f76d1…` / `86d63657…`；BH-0003 run `348522481` 在 13:36:01Z 为 fold0/epoch1 batch1196/1454，latest log lag 6.4 秒，`ACTIVE_PROGRESS`/`RUNNING`，output 仍 0 B。
- **含义**：证明该观察时刻真实推进且未卡死，不是 OOF 完成、metric、candidate 或 submission 证据。
- **动作/成本/停止**：沿用既有 hourly heartbeat，只等同一 run 的 terminal receipt；零新增计算，不并行重跑、不取消、不提交。仅 terminal state、工件校验失败或用户动作需求才升级。更新已送协调源；本研究任务未查询 authenticated Kaggle。

### X-TRAFFIC-005 → 协调源（已送达停止收据）

- **来源**：`queue_onset_breadth_receipt.json` 与 `experiment_ledger.csv`。
- **事实**：rank1 onset 相对 top2 在 development -0.083333、confirmation 0；日期方向负或平，只有一 panel，无正向下界。
- **最小动作**：不提交并冻结 Queue；保留 `56107311`/0.74210。下一步仅只读定位 Task1 congested transition 的可重复高残差时间结构。
- **预期指标**：跨互斥日期/8 corridors 的失败桶复现、congested RMSE、`S_state` 和守恒残差。
- **成本/风险**：低成本审计；风险是 truth-peeking、单 panel 外推和 State/Physics 冲突。
- **停止条件**：时间结构不复现，不生成候选；后续 event gate 确认不优或 corridor/守恒退化即停止。
- **回执**：停止收据及新方向已送达协调源。

### X-TRAFFIC-006 → Traffic / 协调源（已送达公开一手约束）

- **来源**：ASU 官方 CBI 与 data2SupplyModel 仓库，访问 2026-09-09。
- **事实/边界**：公开流程按 link-specific critical/cutoff speed 判定拥堵起止；缺失比例 >50% 的 link-period 被放弃。它不是比赛标签或成绩保证。
- **最小实验**：只读比较 fixed≤60 与 provided-cutoff crossing residual strata，过滤 >50% missingness；覆盖 validation/private 和全 panels，不生成预测。
- **预期指标**：有效覆盖、桶支持数、speed/flow RMSE、top-tail loss concentration、两个 split 与逐 panel 方向。
- **成本/风险**：低；cutoff 默认/未校准、truth 反算泄漏与过滤选择偏差。
- **停止条件**：cutoff 缺失/近常数、覆盖大降、集中度不复现或任一 panel 反转，则保持只读结论、不建 event gate。
- **回执**：来源、实验与禁止从 truth 反算 cutoff 的红线已送达 Traffic 和协调源。

### X-TRAFFIC-007 → 协调源（已送达 ODME 局部晋级与总分边界）

- **来源**：ODME focused receipt、全文件 key validation 与 parent-child diff。
- **事实**：λ=5 对 20 的 minimum split `S_link` gain +0.008185、minimum panel +0.001815、maximum prior-L1 ratio increase +0.030425，过本地门；候选 6,985,307 行有效，SHA `c3aea84e...`，仅 70,708 个 ODME `path_flow` cells 变化。
- **边界**：`S_link` 只占 Task 4 的 25%，其余三个子指标 unknown，不能声称总分会升。
- **最小验证**：若预算允许，只做一次隔离远端校准；Queue/State/Physics 固定，预先锁总分门与回滚点。
- **预期指标**：相对 0.74210 的总分变化；本地三项门与 exact diff 作为可归因收据。
- **成本/风险/停止**：一槽；风险是局部 `S_link` 改善损害未知子指标。远端不过预设总分门即回滚且不扫更多 λ。
- **回执**：本地前沿、包装与 unknown 边界已送达协调源。submission `56108199` 已由 Kaggle 接收，SHA `c3aea84e...`，当前 PENDING；继续门已锁为 public≥0.74410，否则回滚 `56107311`/0.74210 并停止减小 λ。

### X-TRAFFIC-008 → Traffic / 协调源（已送达新最佳远端收据）

- **来源**：Kaggle submission `56108199`，2026-09-09 读取。
- **事实**：状态 COMPLETE、public 0.74733；相对 `56107311`/0.74210 为 +0.00523，超过预注册 0.74410 门 +0.00323。
- **归因边界**：SHA `c3aea84e...`；仅 70,708 个 ODME `path_flow` cells 的 λ=20→5 改变，State/Queue 逐字节不变。可归因到该单变量，但不能分解 organizer-only ODME 子指标。
- **最小下一步**：以 0.74733 为新锚；只选一个更小 λ，经全 panel/split、资源、prior、no-reversal 门后才考虑下一远端槽。
- **预期指标**：本地 `S_link`/prior/最差 panel 与远端相对 0.74733 增益。
- **成本/风险/停止**：一次中等本地确认，至多一槽；小 λ 不收敛或损害未知子指标。任一本地门/远端门失败即停止减小 λ。
- **回执**：新最佳、精确增益和下一停止线已送达两任务。

### X-TRAFFIC-009 → 协调源（已送达低 λ 与 cutoff 双停止收据）

- **来源**：λ=1 failure、λ=2.5 smoke、10-panel cutoff audit 三份机器收据。
- **事实**：λ=1 在 300 iterations 后仍不收敛且无 partial；λ=2.5 相对 λ=5 的 minimum split `S_link` gain 仅 +0.001274<+0.005。cutoff 非退化且 coverage=100%，但 minimum concentration-lift delta=-1.781729，跨 panel/split 反转。
- **决策**：λ=5/0.74733 固定；低 λ 与 cutoff-gated State family 均停止，不扩全量、不提交。
- **最小下一步**：新 State/Physics 族只比较 temporal-only 与输入期 innovation 驱动的两状态稳健 Kalman/smoother；一 panel 互斥日期先验门，其他提交 cells 不变。
- **预期指标**：`S_state`、speed/flow RMSE、逐日期/最差 panel delta、守恒 residual、runtime/memory、changed-key count。
- **成本/风险/停止**：低成本单 panel；状态误识别、目标窗口偷看、State/Physics 冲突。confirmation 不优、日期退化>0.005、守恒恶化或泄漏即冻。
- **回执**：两个失败族、精确门差和新族边界已送达协调源。

### X-TRAFFIC-010 → Traffic / 协调源（已送达 switching-filter 外部约束）

- **来源**：Sun & Work <https://arxiv.org/abs/1608.00917>；Treiber & Helbing <https://arxiv.org/abs/cond-mat/0210050>。
- **事实/边界**：公开方法将 switching dynamics 建立在 conservation 上，并按 free-flow 下游/拥堵上游传播；可观测性与传感器间距制约滤波稳定性。不是比赛正证据。
- **最小实验**：先以 released network+input masks 做无 truth 的上下游邻居、最长间距、不可观测段、双方向覆盖 audit；通过后才做一 panel input-likelihood/innovation switching filter，不复活 cutoff。
- **预期指标**：observability coverage/spacing、State macro/day/panel、FD/守恒 residual、runtime/memory。
- **成本/风险**：低审计+一 panel 中等原型；外部距离条件不可迁移、mode 错识别、目标窗口偷看、State/Physics 冲突。
- **停止条件**：coverage/spacing 不成立、confirmation不优、任一日期退化>0.005或守恒恶化即冻。
- **回执**：方法约束、迁移边界和 preflight-first 顺序已送达两任务。

### X-TRAFFIC-011 → 协调源（已送达可观测性停止与 baseline 纠错）

- **来源**：directional preflight receipt SHA `1b78fb78…`；grouped temporal receipt/ledger SHA `01a5cded…`。
- **事实一**：预设的 3 km、上/下游 90%、双向 80%、任一方向 99% 门仅 10/20 panel×split 通过；worst spacing 7.771 km，最低覆盖 85.07%/84.80%/73.95%/95.92%。无 truth、无预测、无提交。
- **事实二**：首版 grouped temporal 虽有 dev/confirm `S_state` 0.908699/0.911208，但七日 fallback 在月内后续日期使用同一封存月较早 truth；Kaggle 不提供这种滚动标签，故追认 `INVALID_DEPLOYMENT_MISMATCH`。
- **结论**：冻结 directional switching，不把局部通过事后变成 selector；首版 temporal 数值不得参与模型选择。
- **最小动作**：仅重建 pre-block frozen profile 的全月 control，先做每个输入的时间可用性、全 panel/regime、key/schema/coverage 守卫，不叠加新 State 机制。
- **预期指标**：合法 control 的总体/逐 panel/regime/date `S_state`、公开 `S_FD`、RMSE、P10/worst、runtime/memory；organizer-only Physics 保持 unknown。
- **成本/风险**：中等一次全月重算；风险是月内 truth 泄漏、冻结 profile 失去覆盖及公开 FD 冒充榜 Physics。
- **停止条件**：任何月内 truth dependency、缺键/NaN、confirmation cell 缺失或不可复现即停；合法 control 前不开新 State family。
- **回执**：两项停止/纠错及 corrected-control 门已送达协调源。

### X-TRAFFIC-012 → 协调源（已送达合法 V32 State control）

- **来源**：frozen-profile receipt SHA `079c2bb7…`；anchor reproduction SHA `49222bdf…`。
- **事实**：Jan/Feb profile 分别只用 block 前 214/245 天；7,089,289 cells、0 missing、60 panel-regime 全覆盖。dev/confirm `S_state` .908792/.911292，public `S_FD` .986250/.986470；runtime 99.63s、457.8MB。
- **复现边界**：5,884 V32 sample keys/speed 全匹配；仅 1 flow cell 差 .104587 vph，当前 rowwise V32 与 matrix implementation 精确匹配。公开 FD 不是 organizer Physics。
- **结论**：该 receipt 是唯一 deployable State control；rolling-seven-day receipt 永久 INVALID。
- **最小动作**：只在 January development 对 prediction-source/mask/history support 做残差归因，固定唯一跨-panel 机制后一次打开 February confirmation。
- **预期指标**：总体/逐 panel-regime-date `S_state`、FD、RMSE、P10/worst、changed keys、runtime/memory。
- **成本/风险/停止**：低审计+至多一次中等 A/B；防 development 选桶与 same-block truth。总体不优、panel regression>.005、FD/尾部恶化或泄漏即停。
- **回执**：合法 control 与下一单因素门已送达协调源。

### X-TRAFFIC-013 → 协调源（已送达 profile/nearest 双停止收据）

- **来源**：source coverage receipt SHA `c6c2afbc…`；temporal-mode receipt SHA `a5c6d53c…`。
- **事实**：6,740,599 scored targets 中 0 个使用 historical profile；99.995253% temporal-complete，320 cells spatial fallback。nearest blend 的 development/confirmation pure-nearest 相对 linear 分别 −0.021596/−0.017527，向 nearest 单调变差。
- **结论**：robust-profile 与 mode-preserving nearest-fill 都冻结，不拟合/不扩/不提交。
- **最小下一步**：若仍攻 State，只做一个 pre-block mask-matched nonlinear residual interpolator：历史日模拟官方 masks，same-day visible endpoints/slopes/time/static capacity 作非 ID 特征，预测相对 V32 linear residual；单 panel Jan 选、Feb 一次确认。
- **预期指标**：confirmation `S_state` ≥+0.01、worst day≥−0.005、FD≥−0.001，且全 key/coverage、runtime 过门。
- **成本/风险**：中等一次低容量拟合；mask shift、link-ID 泄漏、拥堵稀疏和模型收益不足以覆盖榜 gap。
- **停止条件**：dev 不选非 control、confirm <+0.01、任何日/FD/泄漏守卫失败即停止 State 微调，保留 λ=5/0.74733。
- **回执**：两项精确停止数值与唯一剩余的独立 State family 门已送达协调源。

### X-TRAFFIC-014 → 协调源（已送达 ongoing-trend 停止收据）

- **来源**：Queue ongoing-trend receipt SHA `bcf58e37…`。
- **事实**：development 选择 disabled control 0.667678；steps2–4同分，5–6略差。confirmation step3 为 .528761 vs control .505043，但仅2/8 panels改善，不能后验反选。
- **边界**：只用 released noisy observation IoU proxy，official `S_queue` unknown；onset 与 queued-now persistence 固定。
- **结论/停止**：selected delta=0、changed rows=0；冻结 isolated ongoing-trend family，不扩、不提交。
- **回执**：精确门失败与“confirmation 正信号不能覆盖 development/breadth 失败”已送达协调源。

### X-TRAFFIC-015 → Traffic / 协调源（已送达 nonlinear residual 停止收据）

- **来源**：`task1_nonlinear_residual_receipt.json`，SHA-256 `d1a69a29…`。
- **事实**：January 选 strength1.0；February `S_state` 0.913191→0.917719（`+0.004528`），低于 `+0.01` 门。transition `+0.005370`、public FD `+0.001432`、worst day `+0.002864`、0 missing，估算 State-only total `+0.001585`。
- **边界**：训练标签只来自已发布 train layer；无 scored-split labels/link ID，February 未后调。organizer LWR/Physics 仍 unknown。
- **结论/停止**：稳定正向但幅度不足；不扩全 panel、不生成候选、不提交、不降门。本轮 State 微调结束，λ=5/0.74733 保持。
- **回执**：availability proof、精确正向/失败读数及停止决策已送达 Traffic 与协调源。

### X-TRAFFIC-016 → Traffic / 协调源（已送达组件机会审计）

- **来源**：`component_opportunity_receipt.json`，SHA `6481e142…`。
- **事实**：固定总分 cost floor 0.0035；State 当前信号 0.001585、FD 最大余量 0.000677、λ5 S_link 满分余量 0.000254；ODME nullspace 94.44%–98.02%。0 qualifying independent families，未读 truth/hidden labels。
- **结论/停止**：`HOLD_LAMBDA5_NO_NEW_EXPERIMENT_OR_SUBMISSION`；理论 organizer-only 权重不是本地下界。独立复核当前套件 31/31 tests 通过，提交账本仍三条。
- **回执**：机会排序、固定成本门与 HOLD 决策已送达 Traffic、协调源。

### X-TRAFFIC-017 → 协调源（已送达当前最佳全表 lineage）

- **来源**：`current_best_lineage_receipt.json`，SHA `a6acab84…`。
- **事实**：6,985,307 行仅 Queue 160 cells（全 `1→0`）与 ODME 70,708 `path_flow` cells 变化；State 6,740,599 行零变化，无意外 task/column，schema/key/domain VALID。
- **归因/决策**：Queue +0.02364、ODME +0.00523，总 +0.02887；锁定 `56108199` / 0.74733 / SHA `c3aea84e…`，不再 microtune。
- **回执**：精确 cell lineage、文件完整性与 HOLD 决策已送达协调源。

### X-TRAFFIC-018 → 协调源（已送达冻结参数纠错与 byte-identical replay）

- **来源**：`current_best_freeze_v1.json` SHA `ddf2da9c…`；`current_best_full_replay_receipt.json` SHA `ca275b57…`。
- **纠错**：ODME 脚本默认曾漂离提交参数；现显式固定 `tol=1e-9/lsmr_tol=1e-10/max_iter=200`，避免同 λ 重放不一致。
- **结果**：20 个 ODME panel-splits、Queue 160 cells、ODME 70,708 cells 全量重算；6,985,307 行 rebuilt 与 canonical 均 SHA `c3aea84e…`、逐字节一致，153.91 秒/434.16 MB；独立回归 33/33 通过。
- **边界/结论**：无 target truth、hidden Queue/ODME/Physics 信息；复现路径有效但不是新候选，仍 HOLD 56108199/0.74733。

### X-TRAFFIC-019 → 协调源（已送达 campaign readiness v2 时间边界）

- **来源**：v2 `campaign_readiness_receipt.json` SHA `35776c2e…`。
- **结果**：15 PASS、0 WARN、0 FAIL；原始 archive SHA 已重验。七个 legacy gaps 由分离的 current-machine replay 旁证覆盖，原账本空值不改。当前为 `RESEARCH_BEFORE_D30`、`goal_complete=false`。
- **下一动作/停止**：2026-10-08 14:55 CST 重跑只读 readiness；D3=2026-11-04 14:55 才做最终选择检查。无 ≥0.0035 独立本地下界，不重开实验、不提交。
- **回执**：复现、资源和 deadline 边界已送达协调源；未把“当前就绪”误报为目标完成。

### X-TRAFFIC-020 → 协调源（已送达 legacy resource 旁证重放）

- **来源**：`legacy_resource_replay_receipt.json` SHA `ae9eb30e…`。
- **事实**：五个正常历史步骤复现既有 SHA/结构；λ=1 仅以 exit1 重现既定 numerical failure。七个资源空值全部有 current-machine 旁证，总计 176.83 秒/723.45 MB，hidden truth 未读。
- **边界/停止**：不回填原历史字段、不把旁证冒充原测量、不生成候选/分数比较、不重开低 λ。Traffic suite 独立 34/34 通过，HOLD 56108199/0.74733 不变。
- **回执**：资源闭环及 readiness v2 15/0/0 已送达协调源。

### X-TRAFFIC-021 → 协调源（已送达 readiness v3 与 final-selector dry-run）

- **来源**：readiness v3 receipt SHA `38e9e987…`；final preview v4 receipt SHA `6ddd42dc…`。
- **事实**：v3 为 `READY`、19 PASS/0 WARN/0 FAIL，但仍 `RESEARCH_BEFORE_D30`、`goal_complete=false`。v4 为 `PREVIEW_READY_NOT_FINAL`、dry-run，选中既有 `56108199`/0.74733 并保留 `56107311`/0.74210 rollback；lineage/replay/readiness/候选哈希全过。
- **时间/安全边界**：无 Kaggle 动作，`selection_final=false`、`internal_selection_complete=false`。D3 前拒绝 non-dry；D3 后要求 ≤15 分钟的新鲜 readiness、live-clock 守卫和 postselection readiness。无 ≥0.0035 新下界，不重开实验或提交。
- **回执**：控制平面与“preview 不等于 final”的边界已送达协调源。

### X-TRAFFIC-022 → 协调源（已送达 lifecycle evidence registry）

- **来源**：registry receipt SHA `ab5d1fc3…`；source/test SHA `8d272052…` / `dd9943ad…`。
- **事实**：14 个隔离测试验证 readiness 显式激活、final 自动登记、幂等重试、原子写和 existing receipt 不覆盖；测试前后 live campaign 三个哈希不变。当前完整 Traffic suite 46/46。
- **边界/动作**：0 predictions/Kaggle/hidden actions。D30 仅在新目录 activate readiness；D3 才依次 activate preselection、15 分钟内内部选择、postselection readiness。时钟或哈希漂移立即本地停止，registry 不扩大提交权限。
- **回执**：幂等生命周期动作、失败恢复和权限边界已送达协调源。

### X-TRAFFIC-023 → Traffic / 协调源（已送达四任务合同与 readiness v5）

- **来源**：four-task receipt/matrix SHA `58a0cc1d…` / `5b1d109e…`；readiness v5/checklist SHA `ed45c04c…` / `ae5075b6…`。
- **独立复核**：四任务 audit 重跑后 matrix byte-identical，去时间/资源字段的 receipt exact-match；Traffic suite 52/52 PASS。State 60 groups、Queue 16 panel-splits/160 changes、ODME 20 panel-splits/70,708 rows 均由哈希绑定直接计算。
- **边界**：Physics 仅 public FD；`S_queue/S_LWR/S_physics/S_od/S_dev/S_attr` 均保持 null。readiness 21/0/0 仍是 `RESEARCH_BEFORE_D30`、`goal_complete=false`，下一 checkpoint 10-08 14:55 CST；没有预测或 Kaggle 动作。
- **停止**：VALID/READY 不等于四任务官方分数或 final selection；无 ≥0.0035 独立下界继续冻结 56108199/0.74733。
- **回执**：证据矩阵、确定性重放、测试基线与时间门已送达 Traffic 和协调源。

### X-TRAFFIC-024 → Traffic / 协调源（已送达最终 control-plane 收口与停止门）

- **来源**：policy receipt SHA `5af856f4…`；runtime v3 receipt/capability SHA `197b1d69…` / `b409935f…`；system manifest receipt/CSV SHA `5b30c7a5…` / `b6c84afb…`；readiness v8/checklist SHA `e24b1e0a…` / `8f9665af…`。v1/v2 runtime 与 v6/v7 readiness 已按后续源码哈希漂移历史化。
- **独立复核**：policy 三张输出 CSV byte-identical，3 deadline receipts、8 probes、0 violations；runtime 临时重跑为 `VALID`，10 包、11 CLI、7 capabilities、64 tests；87-file/15-receipt system manifest CSV byte-identical；相同 as-of readiness 再跑仍 24 PASS/0 WARN/0 FAIL。激活后 checklist 仅因 v8 自身入账而从 44 变 45 rows。
- **边界/停止**：全部只证明 local gates、current-machine closure 与 drift detection；readiness 仍 `RESEARCH_BEFORE_D30`、`goal_complete=false`，隐藏六项指标保持 null，无预测/Kaggle/final-selection 动作。连续元审计会递归制造哈希级联，故除真实 drift、赛规变化或 ≥0.0035 新下界，控制面冻结到 D30。
- **回执**：级联失败、v2/v7 中间闭环、最终 v3/v8 和机会成本停止门均已送达 Traffic 与协调源。

### X-ARC-003 → ARC-AGI-2 技术线（已送达任务）

- **来源**：PoTRE <https://arxiv.org/html/2607.20268>；Compositional Neuro-Symbolic Reasoning <https://arxiv.org/html/2604.02434>。
- **事实/边界**：public-eval 研究显示明显 exclusive solves、oracle-final gap 和无放回两次选择收益，但依赖 Gemini/Grok/o4-mini 等外部 API，不能当 offline 正证据。
- **最小实验**：在现有 NVARC/TRM/program 缓存上计算各族 exclusive、overlap、oracle pass@2，再比较 top2、best-distinct、折内 complementarity selector。
- **预期指标**：sealed pass@2、exclusive coverage、oracle-gap 回收率、重复率和 runtime。
- **成本/风险**：低成本缓存审计；风险是 public-eval 条件化、置信不可比和 selector 过拟合。
- **停止条件**：sealed oracle 上界 <+1pp 或外族无独占解则不训练 selector；回收不足 25% gap 则保持 best-distinct。
- **回执**：消息已成功送达；技术线尚未返回实验收据。

### X-ARC-004 → 协调源 / ARC-AGI-2 / ARC Paper（已送达三任务）

- **来源**：run `348340917` 的 run manifest、benchmark receipt、paired summary 与 TRM log。
- **事实/边界**：run COMPLETE；48 tasks/50 outputs、schema 有效、4,548 秒。四个策略同为 48/50 且文件同 SHA、delta=0、bootstrap CI=[0,0]；但 TRM 因 `AdamAtan2(lr=0)` 断言在 47.88 秒退出、零候选，另有一题 3/4 decode，因此不是有效 selector 零结果。
- **最小实验**：只把 AdamAtan2 constructor 初始 lr 改为 `config.lr`、保留 scheduler；先同镜像 1-task/1-step smoke，过后才同 frozen48 重跑一次。
- **预期指标**：TRM rc=0、有效覆盖、NVARC/TRM exclusive/overlap/oracle、attempt1 不变、runtime/memory；oracle 至少 +1 output 才训练 selector。
- **成本/风险**：低 smoke+一次 L4x4；checkpoint/puzzle embedding/ABI/超时与错归因风险。
- **停止条件**：smoke 失败不重跑；TRM 无独占解、oracle<+1、coverage/grid/6h 失败即停，不进 sealed。
- **回执**：终局、根因、最小修复与停止线已送达协调源及 ARC 两线。

### X-ARC-005 → 协调源 / ARC-AGI-2 / ARC Paper（已送达 smoke 二阶段故障）

- **来源**：`trm_adam_lr_compat_smoke_failed_2026-09-09.json` 与 Kaggle log。
- **事实**：`lr=0→config.lr` 已成功越过 checkpoint load 和 optimizer construction；随后 `print(payload, step=0)` TypeError 在首个 optimizer step 前失败，kernel ERROR、无 grid/submission。
- **边界**：只证明原 constructor 故障被修复且出现新的独立 runtime blocker；不产生 accuracy/diversity/selector 证据，full48/sealed 未授权。
- **最小实验**：v2 只把离线日志改成接受 payload/optional step 的 stdout helper，其他均冻结；private/internet-off/公开训练题/1 task/1 step/无 solutions。
- **预期指标**：kernel COMPLETE、rc=0、checkpoint/optimizer/scheduler/首步/step_1 checkpoint/grid/schema/hash 全守卫通过。
- **成本/风险/停止**：低成本单 smoke；但外部上传需用户明确批准。任一 guard 失败即永久停止 TRM 兼容路径，不做第三补丁。
- **回执**：故障、证据边界、v2 准备状态与审批红线已同步三任务。

### X-ARC-006 → 协调源 / ARC-AGI-2 / ARC Paper（已送达 V2 边界、V3 post-hoc 与日期复核）

- **来源**：V2 local boundary SHA `60d6c77b…`、local regression；V3 post-hoc receipt；ARC Prize 官方三页面 14:25 只读复核。
- **事实**：V2 已在后来 local-only boundary 前 push，最后获授权状态 06:27:41 CST `RUNNING`；06:34:25 后终态 UNKNOWN，未再做外部动作。本地 logger/lr/scheduler/private/offline/1-task/1-step guards 全过，但不是 passing runtime。V3 development 50/50 来自看过 misses 后的两规则，只是实现证据。
- **日期**：官方页列技术 11/02、Paper 11/08；旧 authenticated Kaggle 快照列 Paper 11/09 23:59 UTC，内部保守 cutoff 用 11/08。
- **最小动作**：不重复上传；只有用户明确授权后只读查现有 V2 status/download artifacts。V2 runtime guards 全过后才决定 frozen48；V3 不开 sealed holdout。
- **预期指标**：step1 checkpoint、合法 grid、rc0、hash、runtime；之后才谈 exclusive/oracle/selector。Paper 只报告非训练集结果。
- **成本/风险**：低 status/artifact read；后续中等 frozen48。风险是把 local regression/50-of-50 development 写成 runtime/泛化，或误用页面日期时区。
- **停止条件**：V2 任一 guard 失败永久停 TRM route；无 oracle +1 output 不训练 selector；V3 未获明确授权不碰 sealed。
- **回执**：边界纠错发到三任务，日期/V3 另同步给 Paper。

### X-ARC-007 → 协调源 / ARC Paper（已送达 Writeup fail-closed 审计）

- **来源**：`audit_writeup.py`、evidence contract、独立 regression；当前本地实跑均 PASS。
- **事实**：DRAFT 为 1,217 words、9 claim bindings、10 public links、0 training/development performance mentions；仍有 3 placeholders、Accuracy missing、四维 partial，`final_ready=false`。
- **保护机制**：注入 development 48/50 会触发 `train_performance_reported`；FINAL 另拒绝 placeholder、unsupported dimension、缺 platform count 与缺最终资源绑定。
- **最小动作**：保持 DRAFT；只有 V2 runtime、sealed/public-eval 与 Kaggle notebook/submission/source/cover/project/Writeup 全有权威 receipt 才转 FINAL。
- **预期指标**：0 placeholders、六维有证据、platform count、所有 final bindings、0 training-score mentions。
- **成本/风险/停止**：低成本每次改稿重跑；风险是窄 regex 漏掉语义等价训练成绩或把 DRAFT pass 当提交证据。任一缺项即 fail closed。
- **回执**：当前数值、局限与 final gate 已送达协调源和 Paper 线。

### X-ARC-008 → 协调源 / ARC-AGI-2 / ARC Paper（已送达三阶段合同复核）

- **来源**：active three-stage manifest、auditor、normalized receipt schema 与三组回归。
- **事实**：本地独立重跑均 exit0；contract passes=true 但 pipeline_complete=false，runtime smoke UNKNOWN、development pending prerequisite、sealed/competition not authorized，唯一 next action 是获授权的只读 status receipt。
- **守卫**：强制 stage order、task/output/attempt、七 family、runtime/format/hash；competition correctness 必须为 null，只记录 aggregate score/receipt/reference gap，拒绝 leaderboard tuning。
- **边界/停止**：结构通过不是 accuracy/runtime/holdout/submission。用户未明确授权前不查询 Kaggle；terminal receipt 不过就不进入 development。
- **回执**：四项实跑结果与证据边界已送达三任务。

### X-ARC-009 → 协调源 / ARC-AGI-2 / ARC Paper（已送达截止时间与写作边界）

- **来源**：`official_arc_prize_deadline_recheck_2026-09-09.json` SHA `98f84b66…`；ARC Prize 三个公开页面与既有 authenticated Kaggle snapshot，本轮未重新查询 Kaggle。
- **事实/冲突**：官方页列技术 11-02、Paper 11-08；旧 Kaggle snapshot 列 Paper 11-09 23:59 UTC，内部保守按 11-08。内部冻结 10-12/10-26/10-30 分别对应架构、Notebook/依赖、只验证/最终选择。
- **Paper 门**：必须绑定实际 Kaggle code submission，结果来自 leaderboard/public evaluation，禁止报告 train-set performance；当前 1,217-word draft 已为 0 training/development mentions，但仍有 3 placeholders、Accuracy missing、`final_ready=false`。
- **当时的独立复核/停止**：paper suite 18/18 tests 通过，只证明工具和边界一致；新增 terminal-receipt tests 后的当前基线见 X-ARC-010。V2 status 未获授权仍不查询；日期冲突在 final binding 前需授权复核，未复核则按更早日期停。

### X-ARC-010 → 协调源 / ARC-AGI-2 / ARC Paper（已送达 V2 本地微型复现与 terminal receipt 工具）

- **来源**：CPU micro-smoke receipt SHA `49ee14c2…`；terminal build/commit tool SHA `b3a29a40…` / `1385cdb7…`，test SHA `13ef4575…`。
- **本地事实**：冻结的 AdamAtan2 包已实际完成正 lr 构造、scheduler 覆盖、一次 step/参数更新与 `step=0` logger，10/10 guards；但未实例化 TRM、加载 2.16 GB checkpoint、运行 CUDA/数据/评估，不能替代 Kaggle smoke。
- **接收门**：build/commit 只处理已获授权的终态观察，重验 V2 身份、source/artifact hashes 与 guards，拒绝 RUNNING/漂移/项目外路径；commit 只改变 smoke prerequisite，不启动 development。paper suite 22/22 通过。
- **发送时边界/停止**：active pipeline incomplete，smoke UNKNOWN、development pending、sealed/competition not authorized。用户未授权前不查 Kaggle；当时 next action 为 `AUTHORIZED_READ_ONLY_RUNTIME_SMOKE_STATUS`，当前动作已由完整性反例改写，见 X-ARC-015。
- **回执**：事实、局限和授权边界已送达三任务。

### X-ARC-011 → 协调源 / ARC-AGI-2 / ARC Paper（已送达公开 Kaggle 截止日 reconciliation）

- **来源**：public Kaggle deadline receipt SHA `1ac2df00…`，consistency test SHA `15fc3415…`；观察 2026-09-09 18:41:21 CST，未使用 authenticated Kaggle。
- **事实**：公开 Kaggle Paper final 11-09 23:59 UTC、ARC entry/team 10-26 23:59 UTC、ARC final 11-02 23:59 UTC，与旧 authenticated snapshot 完全一致；ARC Prize overview 仍列 Paper 11-08。
- **判决**：controlling submission surface 采用 11-09 23:59 UTC，内部安全 hard stop 仍 11-08 23:59 UTC；多出一天不是新实验预算。
- **边界/停止**：private kernel status/download/mutation/submission/sealed 均 false，不解除 V2 UNKNOWN。日期口径升级已送达三任务。

### X-ARC-012 → 协调源 / ARC-AGI-2 / ARC Paper（已送达全阶段 measurement bridge）

- **来源**：measurement builder/competition schema/当时的 contract SHA `eabcafd1…` / `3b703330…` / `97517c16…`；后续 current contract binding 见 X-ARC-013。
- **独立复核**：3 个新增 standalone end-to-end regressions PASS，既有 paper unittest 22/22 PASS。有标签 stage 可独立重算两次尝试与七 family；competition 只接 COMPLETE/read-only receipt，correctness 与本地 delta 必须全为 null；隐藏字段注入和 identity/scope 漂移 fail closed。
- **发送时边界**：active audit 当时 `pipeline_complete=false`、smoke UNKNOWN、development pending、sealed/competition unauthorized；Paper readiness 当时有 8 类 blocker。工具不查询 Kaggle、不授权/启动 stage、不产生 accuracy/score/submission；当前完整性反例见 X-ARC-015。
- **回执**：功能证据、防泄漏边界和“stage authorization schema 尚非授权 receipt”已送达三任务。

### X-ARC-013 → 协调源 / ARC-AGI-2 / ARC Paper（已送达逐阶段授权桥）

- **来源**：authorization tool/schema/当时 active-contract SHA `9ba09d4c…` / `a8e457a6…` / `f05cea35…`；当前 contract 见 X-ARC-015。
- **独立复核**：22/22 unittest 加 5 个 standalone regressions PASS。工具只消费绑定当前 contract-before hash、冻结 notebook、已完成前置与单一 action 的用户 receipt；每次只能把一个 eligible stage 原子改为 `RUNNING`，并返回 `external_action_performed=false`。
- **安全边界**：`one_run_only=true`、leaderboard-selection=false、future-stages=false；旧 receipt、替换 notebook、错误 action、越级与项目外路径 fail closed。工具/schema 的存在不等于用户授权。
- **发送时状态/回执**：smoke 仍 UNKNOWN、当时 next action 是获用户批准的只读 V2 status/artifact receipt，三个实证 stage 未运行；机制与边界已送达三任务。当前动作已被完整性反例改写，见 X-ARC-015。

### X-ARC-014 → 协调源 / ARC-AGI-2 / ARC Paper（已送达失败收据原子封存门）

- **来源**：failure-commit tool SHA `dc453dc5…`；three-stage auditor SHA `bc127447…`；对应 standalone regression 已 PASS，完整 paper unittest 22/22。
- **机制**：只把当前 `RUNNING` 且无 receipt 的单 stage 与合法失败收据绑定为 `FAILED`；授权前启动、wrong stage、COMPLETE 冒充失败、项目外 receipt 与 non-running target 都保持原 contract bytes。成功后唯一 next action 为 `STOP_CANDIDATE_AND_VERSION_FROM_FAILURE_RECEIPT`，不自动重试或放行后续 stage。
- **边界/回执**：工具本身 `external_action_performed=false`；active pipeline 仍 smoke UNKNOWN、无 stage 运行或失败。本次只送达失败历史不可覆盖的门禁，不构成 runtime/accuracy 证据；当前 next action 见 X-ARC-015。

### X-ARC-015 → 协调源 / ARC-AGI-2 / ARC Paper（已送达 V3 holdout 污染反例与晋级阻断）

- **来源**：holdout-integrity receipt SHA `d04c5599…`；当前 three-stage contract/auditor SHA `1fedbc61…` / `8e94757b…`；submission-readiness manifest SHA `bf3534f5…`。
- **事实**：历史审计读取过全 1000 个 training solutions，V176 选中 2 题且两题都在 development；现有 48-task holdout 虽与 development ID-disjoint，但 V176 在其上会全 abstain 在运行前已可知。当前审计未读 holdout solutions、未披露 IDs、未做外部动作。
- **判决**：禁止从该切片声称 V176 sealed contribution、新题泛化、Progress 或 Novelty；它只可承载 unchanged-parent runtime/format/artifact-integrity。重洗同一 1000 题无效。pipeline promotion 已阻断；当时 next action=`REPLACE_CONTAMINATED_HOLDOUT_BEFORE_EXTERNAL_RUN`，readiness 为 9 类 blocker、`final_ready=false`。当前负面转向见 X-ARC-016。
- **独立复核/回执**：修订后 23/23 unittest 与 4 个核心 standalone regression 全 PASS；精确结论与“不查询 Kaggle”边界已送达三任务。当时的分叉是取得 method-unseen labeled corpus，否则删除 V176 泛化/Progress/Novelty；语料审计现已触发后者，见 X-ARC-016。V2 terminal receipt 只能回答 runtime，不能修复污染。

### X-ARC-016 → 协调源 / ARC-AGI-2 / ARC Paper（已送达“无合格新语料”负面结论）

- **本地来源**：父源码 README SHA `c823d8c5…`；V175 exact-rule receipt SHA `62a2c6ab…`。后者覆盖 ARC-AGI-1 train/eval、ARC-AGI-2 train/eval、ConceptARC，共 2,080 tasks / 2,563 outputs；ConceptARC 为 160/160 tasks、480/480 outputs。README 明示规则在这些官方/重复分区/ConceptARC 上测试。
- **公开一手交叉核验**：ConceptARC 官方仓库确为 16 groups×10 tasks、每题 3 test inputs，但本项目父系统已完全使用；1D-ARC 为 18 类一维合成变换，MiniARC 为不同 playground/object interface。它们可作域外机制压力测试，却没有证据证明与 ARC-AGI-2 目标分布等价。
- **判决**：截至当前，没有找到合规、带标签、在规则冻结后对项目/上游源码均 method-unseen、且可支撑 ARC-AGI-2 泛化的可验证语料。当前 next action 从“寻找或负面转向”收敛为 systems-negative：删除 V176 泛化、Progress、Novelty，不跑 selector/holdout 性能；现有 V2 smoke 即使以后获批也只回答 runtime/format/artifact integrity。
- **重开门/停止**：取数或看答案前冻结 solver/规则/指标/纳入/许可；第三方独立创建、content/hash overlap=0、license compatible、solutions 从未被项目或上游访问，只跑一次。任何历史 solution access、重叠、许可不清或分布不可比即停止主分布主张。1D/Mini/community 只能固定标为 `domain-shift mechanistic stress test`。
- **回执**：精确证据、行动/指标/成本/风险/停止条件已送达三任务；未查询或下载 Kaggle 私有状态/工件，未启动外部运行。

### X-PAPER-003 → ARC Paper（已送达任务）

- **来源**：同 X-ARC-003。
- **事实/边界**：外部论文可支持“覆盖不等于选择回收”的研究问题，但所有正结果来自 public eval/外部 API。
- **最小实验**：frozen folds+sealed48 上报告 solver-family 独占解、重叠、oracle、selector 回收率；消融 top2/best-distinct/complementarity selector。
- **预期指标**：sealed pass@2、oracle-gap recovery、等预算 runtime。
- **成本/风险**：低至中；风险是把公开资源上界写成论文正结果。
- **停止条件**：oracle 上界不足 +1pp 则主张 NO-GO；有上界但回收 <25% 时只报告 verification bottleneck 负结果。
- **回执**：消息已成功送达；论文线尚未返回实验收据。

### X-POKER-003 → Poker（已送达任务）

- **来源**：AAAI 2013 collusion-table 主论文 <https://ojs.aaai.org/index.php/AAAI/article/view/8674>。
- **事实/边界**：Marginal Impact 衡量对 partner 的动作影响相对对其他玩家的平均影响，双向相加且不预设行为模式；原实验是三人限注/合成策略，不能直接外推。
- **最小实验**：折内价值代理生成双向 MI_proxy，只作为一个新特征和 evidence-hand rank score，对当前 residual anchor 做单因素 OOF。
- **预期指标**：Pair AP、Evidence MAP@5、Behavior macro AP、未见玩家折和与 shared-hand count 的相关性。
- **成本/风险**：中等；座位/牌力/水平/共享手数混杂与价值模型跨折泄漏。
- **停止条件**：严格 pool/player OOF 无增益，或 MI_proxy 主要由共享手数/座位解释即删除。
- **回执**：消息已成功送达；Poker 现有 E003 进程仍在运行。

## 立即纠错：MPT 多视角证据

### X-ARC-CORR-002 → 协调源 / ARC-AGI-2 / ARC Paper（已送达三任务）

- **纠错来源**：registration snapshot、competition manifest、development run manifest；均为当前本地权威文件。
- **纠错事实**：两个 ARC 赛道都已加入，团队身份一致；线程中的 `userHasEntered=False` 已过时。private run `348340917` 正在 frozen dev48 上运行，不能重复启动。
- **最小动作**：继续观察同一 run；完成后先校验 coverage/grid/runtime，再读取 pass@2 与 candidate receipt。
- **预期指标**：完整 48 题、有效输出、六小时内、相对 KGMon top2 至少新增 1 个 development 输出。
- **成本/风险**：零新增计算；风险是因旧摘要重复 Join/重启，或把哈希收据误当性能。
- **停止条件**：运行终局若覆盖不全、grid 无效、超六小时或无净新增，不进入 sealed holdout。
- **回执**：纠错已送达协调源和 ARC 两线；等待 run 终局。

### X-ARC-CORR-001 → ARC-AGI-2 / ARC Paper（已送达两个任务）

- **来源**：MPT 论文表格，<https://arxiv.org/html/2605.01154v1>，发布 2026-05-01，访问 2026-09-09。
- **纠错事实**：21.7% 属于 pretrained-only；TTT、PoE、TTT+PoE 的 evaluation 都是 0，失败生成率都是 100%。
- **撤销**：撤销“多视角已有正向结果”的任何表述。
- **保留的低优先级推断**：若模型专门学过多视角表示，跨视图一致性可能成为 selector 的置信特征；目前无正证据。
- **最小实验**：先在 sealed holdout 测有效生成率，再测把一致性只作为 selector feature 的增量。
- **预期指标**：有效输出率、exact、pass@2 与运行时。
- **成本/风险**：中高；主要风险是再次生成失败或错归因。
- **停止条件**：不能先恢复有效输出和 exact，立即停止。
- **回执**：纠错消息已成功送达两个任务；验证回执待项目线产生。

## 上游输入记录

### IN-001 — 协调源首批优先级

- 来自：协调源任务。
- 内容：ARC consensus+best-distinct、结构分层审计、多视角一致性；Kaggriculture shop-router 新种子反证；Paper residual slot-2 selector 与 Go 条件。
- 处理：已拆成 X-KAGG-001、X-ARC-001、X-PAPER-001；多视角随后依据论文全文纠错为 X-ARC-CORR-001。

### IN-002 — 协调源第二批优先级

- 来自：协调源任务。
- 内容：Poker family-conditioned evidence 与 PU 三套 OOF；Traffic 优先 Task 1 时空/拓扑插补，再拆 onset/ongoing queue。
- 处理：已形成 X-POKER-001、X-TRAFFIC-001 并送达。

### IN-003 — 协调源 MPT 纠错

- 来自：协调源任务。
- 内容：21.7% 是 pretrained-only，PoE/TTT/TTT+PoE evaluation=0。
- 处理：已核论文全文并立即向 ARC 两线发纠错；账本永久保留为负例。

### IN-004 — 人工验读历史手册

- 来自：协调源任务；文件：`reports/internal_kaggle_playbook_2026-09-09.md`。
- 内容：ENVDA `0.86→0.50/0.51→MoE 0.84/0.85`，CRAW 同 v51 `1184.5→940.8`，ONNX 本地/LB 近乎精确匹配但方法族触顶，ROGII 强标题包实测失真；同时确认旧目录无 Git、旧聊天正文不可读。
- 处理：已进入 `EXPERIENCE_PLAYBOOK.md` 和 `INTEL_LEDGER.md`；没有伪造 commit 或聊天证据。

### IN-005 — Poker/Traffic 动态赛况

- 来自：协调源任务，人工核验日期 2026-09-09。
- 内容：两赛已参赛，截止时间和 top 3 快照。
- 处理：作为不可覆盖的时间戳快照入账，并形成 X-POKER-002、X-TRAFFIC-002；不用于选模。

### IN-006 — Kaggriculture v43 Sparse Shop Hybrid

- 来自：协调源任务与公开 Kaggle notebook。
- 内容：可见 YARN 条件、prefix compatibility、state sync；禁止把 tape/103/128 当可迁移成绩。
- 处理：已形成 X-KAGG-002。

### IN-007 — ARC 云端资源上界

- 来自：协调源任务、Confluence 和 Symbolica 公开仓库。
- 内容：高 public-eval 方案依赖外部模型/API、沙箱、高并发与高成本；只能迁移 demo-execution feedback 和 attempt diversity 抽象。
- 处理：已形成 X-ARC-002、X-PAPER-002。

### X-CUHK-003 → CUHK Large / 协调源（传感器—语义严格拒绝，已转下一主线）

- **来源/事实**：rejection receipt SHA `85b9f06d…`；replay verification SHA `a5d756e4…`；v4 manifest/verification SHA `e34c0ecf…` / `baa113ce…`。HAU/emotion 809 clips、18 折 LOSO、三模态独立 option-ranker；owned RF OOF 作父，未知 0.77777 与 Fresh20 均未进入。
- **结果**：270 分歧上 candidate `0.37407`、parent `0.32222`；半区 `+15/-1`，环境代理 `-1/+7/+8`；19,416 permutation、809 synonym 均 0 mismatch，invalid=0。
- **判决/停止**：`REJECT_NO_TEST_NO_SUBMISSION`。禁止置信度/subject/环境/模态后验挖掘，不生成 test/candidate、不提交。两次复放离散结果与判决完全一致；只存在 ≤`3.89e-16` margin 末位差。
- **后续**：finalists 与 final selection 不变。Large 2 小时 heartbeat 已写入本负结果和 Fresh20 永久冻结边界；下一未完成主线仅为 HAU Depth 安全续传与结构优先协议。

## 回执与升级规则

项目线返回以下任一信息时升级：

1. 有固定哈希、代码版本和封存结果：从“已送达”改为“已验证/已否定”。
2. 结果与建议相反：优先追加反例，更新先验，不要求项目线为旧假设辩护。
3. 仅有公开 LB 单点：记作“校准信号”，不升级为因果证据。
4. 风险守卫触发：立即建议回滚锚点，并同步其他可能受同类风险影响的战线。
5. 新外部来源若不能改变实验选择、停止规则或合规判断：仅入 `INTEL_LEDGER.md`，不打扰项目线。
