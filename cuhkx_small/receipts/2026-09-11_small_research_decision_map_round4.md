# CUHK-X Small 第四轮定向研究决策地图

- 冻结时间：`2026-09-11T06:43:44Z`
- 结论：`NO_NEW_METHOD_FAMILY / KEEP_P2 / P3_CONDITIONAL / TRANSPORT_BLOCKED`
- 边界：只使用主办方材料、原论文/官方仓库、已登记 Kaggle 方案与本地可复现回执；不以 blog 数量、public leaderboard 或单个 notebook 分数代替决策证据。
- 可视路线图：`2026-09-11_small_research_decision_map_round4.svg`

## 一、问题定义决定方法，而不是反过来

Small 不是普通 40 类视频分类。它要求在未见主体上，用非 RGB 多模态传感器完成 HAR，同时满足单一推理 checkpoint `<100 MB`、非 LLM 推理、离线复现与 finalist 许可链。CUHK-X 原始材料还明确给出两类结构性困难：跨主体/跨环境性能下降，以及长尾和多模态融合。

因此真正的目标函数是：在固定 subject/clip-disjoint 验证上提升最差主体与 macro recall，同时保证新主体、真实缺失模态、传感器顺序/尺度漂移和单 checkpoint 约束下不崩溃。当前 public score 只用于判断 Top-15/Top-5 距离，不能选择特征、阈值、fold 或路线。

## 二、科研版图与覆盖状态

| 方法族 | 一手证据与开源工程 | 当前覆盖 | 对 Small 的决策 |
|---|---|---|---|
| 紧凑视觉时序 | CUHK-X benchmark；TSM 官方 MIT 仓库；TDN 原论文 | 已覆盖并已实现 scaffold | **活跃 P2。** 在完全相同的 MobileNetV3-Small、帧、初始化与优化器下，只比较 mean pooling 与零参数 TSM + 正/负 signed frame differences。它是当前最干净的结构杠杆。 |
| 3D 视频/人体裁剪 | R(2+1)D；K-KUNO 的 YOLO11n + 两折 R(2+1)D | 已覆盖、研究只读 | 公开方案证明该族可工作，但公开图包含两个权重文件、缺少冻结 subject/clip manifest 和逐主体/逐类证据，且 YOLO 为 AGPL；不得直接晋级或复包。 |
| 视觉模态互补 | CUHK-X 的 Thermal/Depth/IR 单模态结果；现有 compact-video 路线 | 已覆盖、实验锁定 | Thermal 是第一入口；Depth/IR 只有在 P2 完整过门后，且在同一 folds 上表现出独立互补才可开。简单增加模态或 backbone 不算新证据。 |
| IMU/Skeleton 时序 | CUHK-X baseline；本地 subject/clip split audit；IMU2CLIP 等已登记一手材料 | 已覆盖 | 单独准确率先验较弱，但存储小、误差源可能独立。只作为 P2 通过后的 gated IMU 分支；不以 metadata-only smoke 代替真实传感器结果。 |
| 多模态 late/gated fusion | HAMLET；显式 availability mask；训练期 modality dropout | 已覆盖、条件杠杆 | **真正可测的第二结构杠杆。** 冻结 Thermal 表征，只增加小 IMU encoder、mask 与 gate；必须单独报告完整/缺失模态切片。 |
| 缺失模态建模 | ActionMAE 的随机丢模态与预测编码；Missing-Modality Token 原论文 | 已覆盖、P3 锁定 | **第三个条件结构杠杆。** 只有 P2 独立过门后才能比较 dropout、mask/token 或轻量重构；不能同时换 backbone、fusion 与数据增强。 |
| 跨主体/跨域泛化 | CUHK-X LOSO/cross-domain；DomainBed；HAROOD | 已覆盖为评估与训练控制 | 不是新模型路线。可用杠杆是 train-only robust scaling、clip-consistent augmentation、domain/subject-balanced sampling 与 untouched subjects；任何 validation 自适应都禁止。 |
| 传感器—语言/大预训练 | SensorLLM、LanHAR、ImageBind 与相关仓库 | 已覆盖、拒绝/延期 | 与非 LLM 推理、单 checkpoint、许可/权重 lineage 或当前算力边界不匹配；不进入第四轮实验树。 |
| Kaggle public notebook/模型 | Small 当前已登记 11 个 Code 条目；0.711/0.716 K-KUNO；公开 Thermal 方法描述 | 全量登记、无完整新 lineage | notebook 分数只能提出可验证假设。缺训练数据、权重、许可、fold manifest、逐主体结果或单 checkpoint 任一项，均为 `RESEARCH_ONLY`。 |

一手材料的关键事实不等于我方结果。CUHK-X 官方 benchmark 的 Thermal `92.57%`、Depth `90.46%`、IR `90.22%`、Skeleton `79.08%`、IMU `45.52%` 是作者报告值；在我方 frozen LOSO 上复现前，不能写成候选性能。

## 三、第四轮真正新增的决策压缩

本轮没有新增方法族，也不改 P2/P3 顺序。新增的是把所有可用想法压缩成三个可证伪结构杠杆：

1. **时序交换而非更大 backbone：** TSM + signed local/global differences 对同一 Thermal base 做单变量比较；两折 subjects 6/18 均 `<+1pp` 即早停。
2. **显式可用性而非无条件拼接：** 只有 P2 四主体过门后，才允许冻结视觉支路并增加 IMU encoder + availability mask + gate；不能用 silent zero-fill。
3. **真实缺失机制而非随机 dropout 幻觉：** 只有 P2 通过且存在可核验的第二模态后，才比较 train-only modality dropout 或 learned missing token；门槛看真实缺失子集、完整模态损失与最差主体，而非总体平均一项。

Depth/IR、多专家、Deep CORAL、更大 3D backbone、TTA、重打包 public weights 都不是当前“真新增结构杠杆”：它们要么同时改变太多因素，要么增加主体/环境捷径风险，要么被单 checkpoint、许可或 lineage 卡住。

## 四、私榜与新主体崩溃边界

| 崩溃边界 | 典型假繁荣 | fail-closed 检查 |
|---|---|---|
| 主体身份/外观捷径 | random split 或相邻 clip 很高，LOSO 大幅跌；YOLO crop 学到体型/服装/背景 | subjects 6、18 快杀，随后 5、21；subject 与 canonical clip key 都零重叠；9、24 最终 untouched confirmation |
| 环境与 Thermal 标定漂移 | 相同动作在新房间、温度或相机增益下整体偏移 | scaler 仅在 train fold 拟合；逐环境、极端 robust-z 与 corruption slice；validation 不得回写统计量 |
| 时间顺序/采样捷径 | 固定长度或文件名顺序有效，真实帧率/缺帧后崩溃 | 严格 timestamp、去重复、自然数字帧序；clip-consistent 采样；顺序扰动作为拒绝测试 |
| 缺失模式转移 | zero-fill 被模型当标签；训练随机缺失与测试真实缺失分布不同 | availability mask 必须等于实际输入；完整/缺失模态分别报告；缺失切片过门前不得看总体均值晋级 |
| 长尾与主体×类别稀疏 | overall accuracy 高，少数类或某主体完全失守 | present-class macro recall、逐类/逐主体、最差主体阈值；fold 内缺类显式记录 |
| public/private 污染 | public LB 上升但 Stage2 新主体池回落 | public score 只在机制冻结后做整体验证；不逐行、不阈值扫、不反推；主办方已扩大 Stage2 池，离线 gate 优先 |
| 工程/许可边界 | 本地可跑但不能交付，或两文件权重合计 `<100 MB` 却不满足单 checkpoint | 一个权重文件、精确 SHA-256、离线双 replay、无网络、代码/权重/数据/finalist 包分层许可审计 |

这意味着私榜风险的首要预测量不是 public LB，而是四主体 gain 分布、最差主体、macro recall、真实缺失切片与 untouched confirmation。任何只提升平均值、但最差主体或缺失切片越界的分支都直接拒绝。

## 五、官方数据入口定向监控

`2026-09-11T06:40:47Z`–`06:43:44Z` 的第四轮只读检查没有发现入口解锁：

- 主办方 portal 的 Small 目录仍只列出 `Test` 与 `Train`；`Train` 返回 HTTP 200 空数组。
- 历史 `CUHK-S/HAR` 与 `CUHK-S/source_data` 也仍返回 HTTP 200 空数组。
- 九个 organizer-linked Google 分卷均返回 HTTP 200、`text/html`、2,009-byte quota page，无 `Content-Range`；状态仍为 `GOOGLE_QUOTA`。
- 机器回执：`artifacts/transport/google_parts_round4_2026-09-11.json`，SHA-256 `6185d05752e887c20e3ae96469930a5dfe450745b7ef5b5e6c6261807e3e43fb`。
- Hugging Face 路线未触发，因为仍需要向仓库作者披露账号邮箱/用户名；没有用户对该确切目的地的授权。
- 第三方 Kaggle Thermal copy 继续 quarantine；没有主办方授权就不得恢复、解压或训练。

只有以下变化算“数据入口变化”：portal 首次返回有名称/大小的训练对象；九个 Google 分卷全部返回精确 `206 bytes 0-0/<expected-size>`；或主办方明确给出无需联系信息、许可可核验的替代下载。普通 HTTP 波动、空目录 mtime、第三方转载或 blog 链接均不升级。

## 六、执行决策

推荐路线保持 **门控传感器阶梯**：官方最小 payload → 来源/许可/CRC gate → Thermal P2 两折快杀 → 四主体完整 gate → gated IMU → train-only 鲁棒化 → 单 checkpoint 与离线双 replay。

另外两条路线都是 P2 通过后的条件分支：Depth/IR 互补要先证明跨主体独立增益；missing-modality token 要先证明真实缺失切片需要它。数据未到时，三条路线的科学状态都保持 `NOT_RUN_PAYLOAD_BLOCKED`，工程 harness PASS 不得改写为模型 PASS。

## 一手来源

- CUHK-X paper/project/code: https://arxiv.org/abs/2512.07136 and https://github.com/openaiotlab/CUHK-X
- TSM official repository: https://github.com/mit-han-lab/temporal-shift-module
- TDN primary paper: https://openaccess.thecvf.com/content/CVPR2021/html/Wang_TDN_Temporal_Difference_Networks_for_Efficient_Action_Recognition_CVPR_2021_paper.html
- ActionMAE primary paper and official repository: https://arxiv.org/abs/2211.13916 and https://github.com/sangminwoo/ActionMAE
- HAMLET primary paper: https://arxiv.org/abs/2008.01148
- DomainBed official repository: https://github.com/facebookresearch/DomainBed
- Host/rule and Kaggle-code receipts are pinned in `../../reports/cuhk_x_incremental_radar_round3_sources.json` and the preceding Small receipts.
