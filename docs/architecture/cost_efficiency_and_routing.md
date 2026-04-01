# 成本效益与智能模型路由策略 (Cost Efficiency & Smart Routing Strategy)

为了在保持“产品级”创作成品质量的同时，将单章生成成本降低 60%-80%，本项目建议实施以下技术逻辑方案。

## 1. 任务敏感型模型路由 (Task-Sensitive Model Routing)

将小说创作任务按“逻辑密度”和“文学性要求”划分为三个层级，动态匹配不同能力的模型：

| 任务层级 | 任务类型 (Examples) | 推荐模型 | 核心逻辑 |
| :--- | :--- | :--- | :--- |
| **Tier 1: 高逻辑/决策** | 卷纲设计、伏笔埋设、逻辑闭环校验、关键剧情转折 | Claude 3.5 Sonnet / GPT-4o | 保证故事不崩盘，逻辑严密，处理复杂 Context。 |
| **Tier 2: 文学性描写** | 角色对话、环境渲染、动作描写、情感抒发 | Claude 3.5 Haiku / DeepSeek-V3 | 兼顾文笔与成本，在已有逻辑框架下填充高质量文字。 |
| **Tier 3: 基础/工具类** | 格式检查、拼写纠错、初步摘要生成、RAG 片段预筛选 | GPT-4o-mini / Llama 3 (Local) | 极低成本处理海量琐碎任务。 |

## 2. 智能 Token 管理与缓存 (Intelligent Token Management)

*   **Prompt Caching (提示词缓存)**: 
    *   将小说“世界观设定”、“系统角色预设 (System Prompts)”等静态高频内容设置为缓存节点。
    *   利用 API 的缓存机制（如 Claude/OpenAI Caching），使重复部分的 Input Token 费用降低 50%-90%。
*   **语义上下文剪枝 (Semantic Context Pruning)**:
    *   **滚动窗口摘要**: 每一章仅携带前一章的完整内容 + 前 5-10 章的极简摘要。
    *   **动态 RAG 检索**: 仅在当前章节涉及特定角色或物品时，才从 Story Bible 中提取对应设定，而非全量挂载。

## 3. 异步批处理与按需评测 (Async Batching & On-demand Review)

*   **Batch API 模式**: 对于非实时性要求极高的“虚拟读者反馈”或“多维度审校”任务，使用 API 的 Batch 模式（通常提供 50% 的折扣）。
*   **按需触发 Critic 机制**:
    *   默认情况下开启“快速生成模式”。
    *   仅当 **Narrative Tension Sensor (张力传感器)** 检测到逻辑偏差或情感断层时，才激活高成本的 Critic/Debate 智能体组。

## 4. 成本监控与熔断系统 (Cost Monitoring & Circuit Breaker)

*   **单章预算控制**: 为每一章设置 $ 阈值。若 AI 进入循环生成或 Token 异常飙升，系统自动熔断并报警。
*   **实时成本回传**: 在 `story-room` 编辑器前端实时显示当前创作任务的预估/已消耗金额，提升成本透明度。
