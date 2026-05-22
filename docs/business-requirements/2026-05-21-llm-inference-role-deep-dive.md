# LLM 大模型推理岗位深挖报告

> 输入文件：`C:\Users\Administrator\Downloads\LLM大模型推理.md`
> 产出时间：2026-05-21
> 范围：仅做岗位需求深挖和寻访策略分析，不进入 `maimai-talent-search-campaign`，不创建 campaign，不执行平台搜索，不写数据库。

## 1. 结论摘要

这个岗位本质上不是“单点 CUDA 算子优化岗”，也不是“纯模型训练/强化学习岗”，而是 **大模型在线推理系统工程岗**：核心目标是在 DeepSeek、Qwen 等主流大模型上，面向长文本、Agent 调用、高并发业务流量，把推理服务做到低延迟、高吞吐、可观测、稳定且成本可控。

最优人选画像是：既懂 vLLM / SGLang / TensorRT-LLM 等推理框架源码和服务化链路，又真实做过线上大模型推理负载治理的人。候选人需要能解释请求调度、Continuous Batching、KV Cache、显存管理、Prefill/Decode 拆分、量化、CUDA Graph、服务弹性和 SLA，而不是只会部署模型或只会写业务 API。

JD 的关键取舍是：高性能算子是加分项，但不是第一优先级。当前业务更需要在框架、调度、缓存、显存、批处理和稳定性上拿 ROI。短期 NVIDIA H100/H200 深度优化优先，国产卡/异构适配不是主线。前期以推理为主，后期会延展到训练/推理协同或强化学习相关能力，因此要找“推理系统根基强、训练生态不陌生”的工程师。

## 2. 岗位真实问题

这不是一个泛 AI Infra 岗。它要解决的是大模型进入真实业务流量后的系统效率问题：

- 长上下文和 Agent 调用会放大 Prefill 成本、KV Cache 占用和尾延迟。
- 高并发请求下，调度策略、批处理形态、显存碎片和抢占机制会直接决定吞吐。
- 模型不断变化，DeepSeek、Qwen、MoE、量化格式、上下文长度和业务 SLA 都会变化，框架不能只“会用”，必须能二开。
- 成本治理不是单一 GPU 利用率，而是吞吐、延迟、失败率、卡型、量化、缓存命中率和业务效果之间的综合优化。

因此，这个岗位的成功标准可以定义为：

1. 能把主流模型稳定部署到高负载在线服务。
2. 能针对业务负载修改或调优推理框架关键模块。
3. 能用数据证明优化收益，例如吞吐提升、P95/P99 降低、GPU 利用率提升、单 token 成本下降。
4. 能建立线上可观测、降级、容错和弹性机制。
5. 能与算法团队共同评估模型效果、性能和成本，而不是只做运维部署。

## 3. 能力模型

### 必须具备

| 维度 | 判断标准 | 典型证据 |
| --- | --- | --- |
| 推理框架能力 | 不只是使用 vLLM/SGLang/TensorRT-LLM，而是能读源码、改调度、改缓存、改 serving 逻辑 | 讲得清 scheduler、block manager、KV cache、batching、prefill/decode、worker/executor |
| 在线服务能力 | 做过真实线上 LLM serving，而不是 demo 部署 | 有 QPS、P95/P99、吞吐、错误率、GPU 利用率、扩缩容指标 |
| 性能调优能力 | 能从瓶颈定位到方案落地 | profile、压测、显存分析、batch tuning、CUDA Graph、torch compile、量化评估 |
| 成本意识 | 以业务 SLA 为约束优化性价比 | 能比较 FP16/BF16/FP8/AWQ/GPTQ、缓存命中、卡型利用率、模型组合成本 |
| 稳定性意识 | 能做高负载可用性建设 | 熔断、降级、重试、隔离、排队、超时、自动容错、监控告警 |
| NVIDIA 生态 | 当前主线是 H100/H200 | 熟悉 CUDA/NCCL/TensorRT/显存/多卡推理，不要求国产卡优先 |

### 强加分

- 长上下文、Prefix KV Cache、Paged Attention、Chunked Prefill、Speculative Decoding、Disaggregated Prefill/Decode 经验。
- MoE 推理优化经验，包括 fused-MoE、专家并行、通信优化、DeepEP 或类似能力。
- 做过 Agent 场景服务优化，理解工具调用、多轮上下文、请求 burst、缓存复用和尾延迟。
- 做过模型评测平台或模型路由，能参与基座模型选型。
- 有训练框架、RLHF/RL、分布式训练基础，能支撑后期职责扩展。

### 不应过度加权

- 单纯 CUDA 算子能力。JD 提到 attention/gemm/fused-MoE/deepep，但 Q&A 明确说算子优化 ROI 未必最高，框架和调度优化更重要。
- 单纯异构计算能力。当前主要是 NVIDIA H100/H200，华为/国产卡经验只有在候选人同时熟悉开源推理生态时才值得看。
- 单纯模型算法背景。算法强但没做过线上推理框架/服务治理，容易不匹配。

## 4. 候选人类型

### A 类：推理框架二开型

这是最贴近岗位的第一优先级人选。

画像：
- 在基模公司、大厂 AI Infra、云厂商 AI 平台或 GPU 服务团队做过推理框架。
- 能深入 vLLM、SGLang、TensorRT-LLM、Triton Inference Server、Ray Serve、KServe 等框架或周边系统。
- 能改 Continuous Batching、调度器、KV Cache、显存分配、worker 通信和模型加载。

识别信号：
- 简历里出现 `vLLM`, `SGLang`, `TensorRT-LLM`, `PagedAttention`, `KV Cache`, `continuous batching`, `scheduler`, `serving`, `throughput`, `P99`。
- 能讲具体线上收益，而不是只写“负责模型部署”。

风险：
- 有些人只做包装层/API 层，没有改过核心模块。
- 有些人只做离线 benchmark，没有真实业务 SLA。

### B 类：大模型在线服务平台型

这是第二优先级，尤其适合偏工程落地和稳定性建设。

画像：
- 做过 LLM 网关、推理服务平台、模型服务化、弹性伸缩、监控告警、限流降级。
- 不一定深改 kernel，但能把大模型服务跑稳、跑便宜。

识别信号：
- 简历里出现 `LLM serving`, `model serving`, `GPU utilization`, `autoscaling`, `observability`, `SLA`, `latency`, `throughput`, `Kubernetes`, `NCCL`, `multi-GPU`。
- 能解释流量形态、排队策略、批处理策略和服务降级。

风险：
- 如果只是传统后端/SRE，没有模型推理框架知识，会缺核心深度。
- 如果只做平台控制面，不碰推理数据面，也要降权。

### C 类：GPU 性能优化/算子型

这是高潜加分型，不是唯一主线。

画像：
- 做过 CUDA/Triton kernel、attention/gemm/MoE/fusion、TensorRT 插件、算子库优化。
- 如果同时理解推理框架和业务负载，是强候选。

识别信号：
- `CUDA`, `Triton`, `TensorRT`, `GEMM`, `attention`, `FlashAttention`, `fused MoE`, `cutlass`, `profiling`, `Nsight`。

风险：
- 只做底层算子但不了解在线服务，可能与岗位短期 ROI 不一致。
- 只做训练侧算子，不熟悉推理批处理和 KV Cache，需要谨慎。

### D 类：训练/强化学习/分布式训练型

这是后期储备型，不能作为当前主线。

画像：
- 熟悉训练框架、RLHF/RL、分布式训练、Megatron/DeepSpeed/FSDP。
- 如果有推理部署经验，可以看；如果没有，暂列二线。

识别信号：
- `Megatron`, `DeepSpeed`, `FSDP`, `RLHF`, `PPO`, `GRPO`, `distributed training`。

风险：
- JD 前期是推理为主，纯训练候选人短期上手成本高。

## 5. 寻访关键点

### 关键点 1：从“部署”追问到“二开”

很多候选人会写“部署 DeepSeek/Qwen/vLLM 服务”。真正要筛的是：

- 是否读过或改过 vLLM/SGLang/TensorRT-LLM 源码。
- 是否改过 scheduler、batching、KV cache、memory manager、executor。
- 是否处理过长文本、Agent、多轮上下文、并发 burst。
- 是否能解释某次优化的瓶颈、方案、收益和副作用。

### 关键点 2：从“性能优化”追问到“成本治理”

该岗位不是只看 benchmark 分数。要看候选人是否能在 SLA 下做性价比：

- 单 token 成本如何计算。
- P95/P99、吞吐、GPU 利用率之间如何取舍。
- 量化后效果损失如何评估。
- KV Cache 命中率、复用策略和显存压力如何权衡。
- H100/H200 资源怎么排布，何时扩容，何时降级。

### 关键点 3：从“算子能力”追问到“ROI 判断”

JD 明确说算子优化会涉及，但 ROI 不一定最高。优秀候选人应该能判断：

- 哪些问题适合框架调度解决。
- 哪些问题适合量化/缓存/批处理解决。
- 哪些问题才值得做 CUDA/Triton kernel。
- 如何证明一两个月算子投入值得做。

### 关键点 4：从“模型能力”追问到“业务负载”

候选人要能理解不同业务负载：

- 长文本：Prefill 代价、KV Cache、上下文截断/复用。
- Agent：多轮调用、工具调用、短请求 burst、尾延迟。
- 高并发：排队、批处理、抢占、限流、熔断。
- 多模型：模型路由、大小模型组合、成本/效果权衡。

## 6. 公司池与团队优先级

### 第一梯队：基模公司推理/Infra 团队

目标公司：
- DeepSeek、MiniMax、Kimi/月之暗面、阶跃星辰、智谱、零一万物。

优先团队：
- 推理框架、模型服务、AI Infra、GPU 平台、Serving 平台、工程效率、模型评测平台。

为什么优先：
- 这些团队更可能处理大模型真实线上流量、长上下文、MoE、模型迭代和成本压力。

### 第二梯队：大厂 AI Infra / 云平台 / 搜广推大模型化团队

目标公司：
- 字节、阿里、百度、腾讯。

优先团队：
- 火山/阿里云/百度智能云/腾讯云 AI 平台。
- 大模型平台、模型服务、搜索/广告/推荐中的 LLM 推理服务、机器学习平台。

为什么优先：
- 工程体系、线上稳定性、资源调度、压测和可观测性更强。

### 第三梯队：AI 应用公司但有自研推理平台的团队

目标公司：
- 昆仑万维、爱诗科技、LoveArt 等。

优先判断：
- 是否有真实大模型服务负载。
- 是否自建推理服务，而不是调用外部 API。
- 是否有 GPU 资源治理和线上 SLA。

### 可谨慎看：华为/国产卡相关团队

判断标准：
- 不能因为“华为”直接排除。
- 如果候选人熟悉 vLLM/SGLang/TensorRT-LLM、NVIDIA 生态或开源推理框架，仍可看。
- 如果主要经验限定在 Ascend/CANN，且缺少开源推理生态和 NVIDIA 经验，应降权。

## 7. 搜索关键词建议

### 核心关键词

- 大模型推理
- LLM serving
- 模型推理部署
- 推理框架
- vLLM
- SGLang
- TensorRT-LLM
- DeepSeek 部署
- Qwen 部署
- 高并发推理
- 低延迟推理

### 框架与调度关键词

- Continuous Batching
- PagedAttention
- KV Cache
- Prefix Cache
- Chunked Prefill
- Prefill Decode
- Disaggregated Prefill
- request scheduler
- memory manager
- block manager
- speculative decoding

### 成本与性能关键词

- GPU 利用率
- 推理成本
- P95 / P99 延迟
- 吞吐优化
- CUDA Graph
- torch compile
- AWQ
- GPTQ
- FP8
- 模型量化
- 显存优化

### 算子关键词

- CUDA
- Triton
- attention kernel
- GEMM
- fused MoE
- FlashAttention
- TensorRT plugin
- Nsight
- DeepEP

### 稳定性关键词

- SLA
- observability
- autoscaling
- 限流
- 熔断
- 降级
- 容错
- 监控告警
- Kubernetes GPU

### 职位名关键词

- 推理框架工程师
- 大模型推理工程师
- AI Infra 工程师
- LLM Serving 工程师
- 模型服务工程师
- GPU 平台工程师
- 机器学习系统工程师
- 高性能计算工程师
- CUDA 工程师
- 分布式系统工程师

## 8. 硬性筛选规则

### A 档

满足以下大部分条件：

- 1-7 年，985/211 或同等强技术背景。
- 来自基模公司或大厂 AI Infra/模型服务团队。
- 有 vLLM/SGLang/TensorRT-LLM 任一框架的真实工程经验。
- 做过线上 LLM 推理服务，高并发/低延迟/成本治理有可量化结果。
- 能讲清 KV Cache、batching、显存管理、调度或 prefill/decode 至少两个核心模块。
- NVIDIA GPU 经验明确。

### B 档

满足以下条件：

- 有模型服务平台或 GPU 平台经验。
- 了解推理框架，但二开深度有限。
- 有稳定性、可观测、服务治理能力。
- 缺少部分核心优化经验，但学习曲线可接受。

### C 档

可观察但不优先：

- 纯 CUDA/算子优化，缺在线推理服务经验。
- 纯训练框架/分布式训练，缺推理服务经验。
- 纯 AI 应用后端，只做 API/RAG/Agent 应用层。
- 仅国产卡/异构优化，缺 NVIDIA 和开源推理生态。

### 淘汰

- 只会部署开源模型 demo。
- 只做传统后端或 Kubernetes 运维，无法解释推理框架。
- 只做算法研究，没有系统落地。
- 只做模型调用/API 编排，没有 GPU、显存、调度、延迟或成本经验。

## 9. 面试验证问题

### 推理框架深度

1. 你在 vLLM/SGLang/TensorRT-LLM 中具体改过哪些模块？为什么要改？
2. Continuous Batching 在什么场景下会提升吞吐？什么时候会伤害延迟？
3. KV Cache 的显存管理瓶颈通常在哪里？你怎么定位和解决？
4. Prefill 和 Decode 的资源特征有什么不同？什么时候需要拆分部署？

### 性能与成本

1. 你做过最有效的一次推理成本优化是什么？收益怎么量化？
2. 如果 P99 延迟不稳定，你会从哪些层面排查？
3. FP8/AWQ/GPTQ 量化怎么评估效果损失和收益？
4. 如何判断该做算子优化，还是该做调度/缓存/批处理优化？

### 业务负载

1. 长文本场景和短问答场景的推理系统设计有什么不同？
2. Agent 调用场景为什么容易出现尾延迟？怎么治理？
3. 多模型组合时，模型路由和成本控制怎么设计？

### 稳定性

1. GPU 推理服务的核心监控指标有哪些？
2. 如果部分 GPU 节点异常，如何自动容错和降级？
3. 如何设计高负载下的限流、排队和熔断？

## 10. Offer 风险与吸引点

### 候选人关心点

- 是否能接触真实大模型线上流量，而不是部署工具人。
- 是否有足够 GPU 资源和 H100/H200 优化空间。
- 是否能改框架核心模块，而不是只做平台包装层。
- 是否有明确性能指标和工程影响力。
- 后期是否能延展到训练/推理一体、RL 或更底层系统。

### 风险点

- 1-7 年候选人里真正做过框架二开的比例不高，简历噪音会很大。
- 基模公司候选人薪酬和机会成本较高，必须强调技术挑战和资源密度。
- 纯算子强人可能不愿做服务稳定性和成本治理，需要确认动机。
- 大厂平台候选人可能控制面经验多、推理数据面经验少，需要面试深挖。

## 11. 寻访口径

推荐外联话术的核心不是“我们做大模型推理”，而是：

> 面向 DeepSeek/Qwen 等主流模型的高并发在线推理服务，重点做 vLLM/SGLang/TensorRT-LLM 级别的框架二开、请求调度、KV Cache、显存治理、量化和成本优化，短期聚焦 NVIDIA H100/H200 上的真实业务负载。

这句话能筛掉三类不合适人群：纯应用层、纯算法层、纯运维层；同时能吸引真正关心推理系统深度的人。

## 12. 建议的岗位画像一句话

寻找 1-7 年、强学校背景、来自基模公司或大厂 AI Infra/模型服务团队，做过 vLLM/SGLang/TensorRT-LLM 等推理框架二开和线上 LLM serving 优化，能围绕高并发、低延迟、KV Cache、调度、显存、量化、NVIDIA GPU 和 SLA 做系统性成本治理的工程师。
