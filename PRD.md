# 长篇小说创作 Agent - 产品需求文档 (PRD)

**版本**: v1.0  
**创建日期**: 2026-03-18  
**最后更新**: 2026-03-18  
**状态**: 规划阶段

---

## 📋 目录

- [一、产品愿景与定位](#一产品愿景与定位)
- [二、目标用户画像](#二目标用户画像)
- [三、核心价值主张](#三核心价值主张)
- [四、功能需求](#四功能需求)
- [五、技术架构](#五技术架构)
- [六、多 Agent 系统设计](#六多-agent-系统设计)
- [七、质量评估体系](#七质量评估体系)
- [八、数据库设计](#八数据库设计)
- [九、开发路线图](#九开发路线图)
- [十、成本与风险](#十成本与风险)
- [十一、成功指标](#十一成功指标)

---

## 一、产品愿景与定位

### 1.1 产品愿景

> **打造全球首个能够独立创作高质量长篇小说的 AI Agent 系统**
> 
> 帮助想要写出"没有 AI 味道"小说的创作者，用时间换质量，打造可出版的精品内容。

### 1.2 产品定位

**面向严肃创作者的深度 AI 协作系统**

- **不是**简单的文字生成工具
- **不是**网文流水线工厂
- **而是**具备长期规划、一致性维护、艺术创作能力的创作伙伴

### 1.3 差异化定位

| 维度 | 炼字工坊 | 我们的产品 |
|------|---------|-----------|
| **定位** | 网文 IDE（工具） | 创作伙伴（Agent） |
| **目标** | 提高产量 | 提升质量 + 产量 |
| **核心价值** | 效率 | 严谨性 + 艺术性 |
| **用户角色** | 操作者 | 创意总监 |
| **技术重点** | RAG+ 工作流 | 多 Agent 反思 + 评估 |

### 1.4 不做的事情

❌ **不做**：
- 完全自动、无需人工参与的系统（现阶段不现实）
- 短视频脚本/文章生成（专注长篇）
- 同人小说生成（版权复杂）
- 追求速度牺牲质量

✅ **要做**：
- 人类创意 + AI 执行的协作系统
- 专注原创长篇小说
- 可控、可解释、可迭代
- 用时间换质量

---

## 二、目标用户画像

### 2.1 核心用户画像

#### 用户 A：有文学追求的业余作家

```
基本信息:
- 年龄：28-45 岁
- 职业：有稳定工作，写作是梦想/副业
- 收入：年收入 30-100 万
- 教育：本科及以上

特征:
- 有故事想法，但执行力不足
- 担心 AI 写的内容太"白"，缺乏文学性
- 愿意为质量花时间打磨
- 对 AI 技术持开放态度，但不盲目信任

痛点:
- 有时间但执行力不足
- 卡在开头或中期
- 质量不稳定
- 担心 AI 味太重

需求:
- 要的是"有灵魂"的文字
- 能把控故事走向
- AI 检测通过率要高
- 愿意为质量付费

付费意愿：强（¥99-299/月）
```

#### 用户 B：转型中的网文作者

```
基本信息:
- 年龄：25-35 岁
- 职业：职业/半职业网文作者
- 收入：不稳定，渴望提升
- 教育：大专及以上

特征:
- 已有作品，但想突破套路
- 日更压力大，灵感会枯竭
- 想保持个人风格的同时提升效率
- 对 AI 工具熟悉

痛点:
- AI 写的内容容易被识别
- 缺乏个人风格
- 平台对 AI 内容审核严格
- 质量波动大

需求:
- 去 AI 味
- 保持个人风格
- 稳定输出高质量内容
- 提高过稿率

付费意愿：强（¥199-299/月）
```

#### 用户 C：IP 内容工作室

```
基本信息:
- 规模：5-20 人团队
- 业务：IP 开发、内容定制
- 预算：企业级

特征:
- 需要高质量内容用于 IP 开发
- 人工创作成本高、周期长
- 需要可控的内容生产
- 对版权敏感

痛点:
- 人工成本高
- 创作周期长
- 质量不可控
- 版权归属复杂

需求:
- 批量生产高质量内容
- 版权清晰
- 可定制化
- 团队协作

付费意愿：很强（企业定制，¥5000+/月）
```

### 2.2 用户场景

#### 场景 1：业余作家创作长篇小说

```
用户：35 岁程序员，想写一部科幻小说

流程:
1. 注册账号，创建项目《星际归途》
2. 输入核心创意：人类首次星际移民的冒险故事
3. AI 辅助完善世界观设定
4. 生成三幕式大纲，用户调整关键节点
5. 开始第一章创作
   - AI 生成初稿（3000 字）
   - 质量评估显示 AI 味 0.35（偏高）
   - 自动润色后 AI 味降至 0.18
   - 用户手动调整部分对话
6. 持续创作，AI 自动追踪人物设定和伏笔
7. 完成 30 万字，AI 检测通过率 95%
8. 投稿出版社，获得出版意向

价值:
- 创作周期从 3 年缩短到 8 个月
- 质量稳定，无需反复修改
- 人物设定始终一致
```

#### 场景 2：网文作者日更

```
用户：28 岁全职网文作者，签约番茄小说

流程:
1. 早上 9 点，打开昨天创作到第 85 章
2. 查看 AI 生成的本章大纲（昨晚已生成）
3. 确认情感曲线设计
4. 启动生成，10 分钟后得到 3500 字初稿
5. 质量评估：一致性 0.92，AI 味 0.22
6. 快速浏览，修改 3 处细节
7. 发布更新，用时 20 分钟
8. 继续创作下一章

价值:
- 日更时间从 2 小时缩短到 20 分钟
- 质量稳定，读者反馈好
- 不再担心卡文
```

---

## 三、核心价值主张

### 3.1 三个关键词

| 价值 | 说明 | 如何衡量 | 目标值 |
|------|------|---------|--------|
| **无 AI 味** | 文字自然、有风格、有情感 | AI 检测通过率 | >90% |
| **严谨** | 百万字不崩坏 | 一致性评分 | >0.85 |
| **可控** | 用户是创意总监 | 用户满意度 | >4.5/5 |

### 3.2 价值实现路径

#### 无 AI 味的实现

```
技术手段:
1. 多轮反思改进
   - 初稿生成后，批判家 Agent 检测 AI 味
   - 编辑 Agent 针对性润色
   - 重复直到 AI 味低于阈值

2. 句式多样性优化
   - 强制增加句子长度变化
   - 避免 AI 高频词汇
   - 模拟人类写作的"突发性"

3. 情感深度增强
   - 情感设计师 Agent 设计情感曲线
   - 评估实际情感表达
   - 优化情感描写

4. 风格模型微调
   - 收集经典作品训练
   - 学习用户写作风格
   - 风格迁移应用
```

#### 严谨性的实现

```
技术手段:
1. RAG 检索增强
   - 向量数据库存储所有设定
   - 生成前自动检索相关设定
   - 动态注入 Prompt

2. 多 Agent 一致性检查
   - 批判家 Agent 检查人物一致性
   - 检查世界观约束
   - 检查时间线逻辑

3. 伏笔自动追踪
   - AI 自动识别伏笔
   - 记录埋下位置
   - 提醒回收

4. 版本控制
   - 所有章节版本可追溯
   - 变更原因记录
   - 支持回滚
```

#### 可控性的实现

```
产品手段:
1. 关键节点人工确认
   - 大纲必须人工审核
   - 重要剧情转折需确认
   - 人物重大变化需批准

2. 创作过程透明
   - 每个决策都有理由
   - Agent 辩论过程可见
   - 质量评分可视化

3. 灵活干预
   - 随时可暂停修改
   - 支持局部重写
   - 可调整生成方向

4. 用户偏好学习
   - 记录修改历史
   - 学习写作偏好
   - 个性化推荐
```

---

## 四、功能需求

### 4.1 功能优先级

#### P0 功能（MVP 必须有）

| 模块 | 功能 | 描述 | 验收标准 |
|------|------|------|---------|
| **用户系统** | 注册/登录 | 邮箱 + 密码，JWT 认证 | 可正常注册登录 |
| | 项目管理 | 创建/编辑/删除小说项目 | CRUD 操作正常 |
| **设定系统** | 人物档案 | 创建、编辑人物，支持关系 | 可完整记录人物信息 |
| | 世界观设定 | 规则、约束、背景设定 | 支持结构化存储 |
| | 大纲管理 | 三幕式/分卷大纲 | 可生成和编辑大纲 |
| | 伏笔记录 | 手动记录伏笔 | 可追踪状态 |
| **创作系统** | 章节规划 | 生成章节摘要和情感曲线 | 每章 200-300 字摘要 |
| | 多 Agent 生成 | 架构师 + 撰稿人 + 批判家 + 编辑 | 可生成 3000 字章节 |
| | 反思循环 | 至少 2 轮评估改进 | AI 味<0.3 |
| **质量评估** | 基础评估 | 5 维度（流畅/一致/逻辑/AI 味/情感） | 评分可视化 |
| | 一致性检查 | 人物/世界观/时间线 | 发现严重问题 |
| | AI 味检测 | 检测 AI 高频词和句式 | 评分准确 |
| **导出** | TXT/Markdown | 导出章节或全书 | 格式正确 |

#### P1 功能（V1.0 应该有）

| 模块 | 功能 | 描述 |
|------|------|------|
| **用户协作** | 关键节点确认 | 大纲、重要转折需人工确认 |
| | 局部重写 | 选中段落要求重写 |
| | 批注反馈 | 在文稿上做批注 |
| **版本控制** | 版本历史 | 查看章节所有版本 |
| | 版本对比 | 可视化差异 |
| | 回滚功能 | 恢复到历史版本 |
| **可视化** | 质量雷达图 | 14 维度可视化 |
| | 人物关系图 | 自动绘制关系网络 |
| | 情感曲线 | 显示章节情感起伏 |
| **学习系统** | 偏好记录 | 记录用户修改习惯 |
| | 个性化 | 推荐写作方向 |

#### P2 功能（V2.0 可以有）

| 模块 | 功能 | 描述 |
|------|------|------|
| **风格模型** | 文风定制 | 模仿特定作家风格 |
| | 风格迁移 | 将草稿转为目标风格 |
| **高级功能** | 多卷本规划 | 支持系列长篇 |
| | 平行宇宙 | 生成多个分支对比 |
| | 伏笔回收建议 | 智能提醒呼应 |
| **协作** | 多人协作 | 团队项目 |
| | 评论审核 | 第三方审阅 |

---

### 4.2 功能详细设计

#### 4.2.1 故事圣经（Story Bible）

**功能描述**：
结构化管理所有设定，支持版本控制和自动更新。

**数据结构**：
```typescript
interface StoryBible {
  // 基础信息
  title: string;
  genre: string;
  theme: string;
  tone: string;
  
  // 人物档案
  characters: Map<string, Character>;
  
  // 世界观
  worldSettings: Map<string, WorldSetting>;
  
  // 地点
  locations: Map<string, Location>;
  
  // 剧情线
  plotThreads: Map<string, PlotThread>;
  
  // 伏笔
  foreshadowing: Map<string, Foreshadowing>;
  
  // 时间线
  timeline: TimelineEvent[];
  
  // 已完成章节
  chapters: Map<number, Chapter>;
  
  // 元数据
  version: number;
  lastUpdated: Date;
}
```

**核心操作**：
- 创建/编辑/删除实体
- 版本追溯
- 自动更新（AI 提取新设定）
- 检索注入（生成时自动检索相关设定）

---

#### 4.2.2 章节创作流程

**流程图**：
```
用户确认大纲
    ↓
架构师规划本章目标
    ↓
情感设计师设计情感曲线
    ↓
撰稿人分场景生成初稿
    ↓
批判家多轮评估
    ├─ 一致性检查
    ├─ 逻辑检查
    ├─ AI 味检测
    └─ 情感评估
    ↓
是否达标？
 ├─ 是 → 架构师终审 → 完成
 └─ 否 → Agent 辩论 → 编辑润色 → 重新评估
```

**时间估算**：
- 规划阶段：1-2 分钟
- 生成阶段：5-8 分钟（3000 字）
- 评估阶段：2-3 分钟
- 修改阶段：2-5 分钟（如需）
- **总计**：10-18 分钟/章

---

#### 4.2.3 质量评估界面

**界面设计**：
```
┌─────────────────────────────────────────┐
│  第 15 章 质量评估报告                    │
├─────────────────────────────────────────┤
│                                         │
│  综合评分：8.5/10 ✅                     │
│  AI 味道：0.18 (优秀)                    │
│  一致性：0.92 (优秀)                     │
│                                         │
│  ┌────────────────────────────────┐    │
│  │     14 维度雷达图               │    │
│  │    （可视化图表）               │    │
│  └────────────────────────────────┘    │
│                                         │
│  详细评估：                             │
│  ✅ 语言流畅度：9.0/10                  │
│  ✅ 人物一致性：9.2/10                  │
│  ⚠️  情节紧凑度：7.5/10 (建议优化)      │
│  ✅ AI 味道：0.18 (低于阈值 0.3)         │
│                                         │
│  发现的问题：                           │
│  - 第 3 段节奏稍慢，建议删减             │
│  - 配角 C 的对话略显生硬                │
│                                         │
│  [查看原文] [一键优化] [手动修改]        │
└─────────────────────────────────────────┘
```

---

## 五、技术架构

### 5.1 整体架构

```
┌─────────────────────────────────────────────────┐
│              前端层 (Next.js 14 + TypeScript)    │
│   - App Router  - Server Components             │
│   - shadcn/ui  - Tailwind CSS                   │
│   - Recharts  - Zustand                         │
└─────────────────────────────────────────────────┘
                        ↓ HTTPS
┌─────────────────────────────────────────────────┐
│              API 层 (FastAPI + Python 3.11+)     │
│   - REST API  - WebSocket (实时推送)            │
│   - JWT 认证  - CORS                            │
└─────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────┐
│              任务队列 (Celery + Redis)           │
│   - 异步任务  - 进度追踪  - 重试机制            │
└─────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────┐
│              Agent 核心层 (Python)               │
│   - Agent 基类  - 消息总线  - 反思引擎          │
│   - 辩论协调器  - 工具函数                      │
└─────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────┐
│              记忆层                              │
│   - PostgreSQL 15+ (结构化数据)                 │
│   - Qdrant (向量检索)                           │
│   - Redis 7+ (缓存/会话)                        │
└─────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────┐
│              模型层                              │
│   - 主模型：Claude 3.5 / Gemini 2.0 (1M+)       │
│   - 备用：DeepSeek / 智谱 / 文心                │
│   - 路由：多模型负载均衡                        │
└─────────────────────────────────────────────────┘
```

### 5.2 技术栈详细

#### 前端技术栈

```json
{
  "framework": "Next.js 14",
  "language": "TypeScript 5.x",
  "ui": {
    "components": "shadcn/ui",
    "styling": "Tailwind CSS",
    "icons": "Lucide React"
  },
  "state": {
    "client": "Zustand",
    "server": "React Query"
  },
  "charts": "Recharts",
  "editor": "TipTap / Monaco Editor",
  "testing": "Jest + React Testing Library"
}
```

#### 后端技术栈

```python
# 核心框架
fastapi = "^0.109.0"
uvicorn = "^0.27.0"
pydantic = "^2.5.0"

# 数据库
sqlalchemy = "^2.0.0"
asyncpg = "^0.29.0"
alembic = "^1.13.0"

# 任务队列
celery = "^5.3.0"
redis = "^5.0.0"

# AI 相关
langchain = "^0.1.0"
qdrant-client = "^1.7.0"

# 认证
python-jose = "^3.3.0"
passlib = "^1.7.4"

# 测试
pytest = "^8.0.0"
pytest-asyncio = "^0.23.0"
```

#### 基础设施

```yaml
数据库:
  - PostgreSQL 15+
  - Qdrant 1.8+
  - Redis 7+

容器化:
  - Docker
  - Docker Compose

监控:
  - Prometheus
  - Grafana
  - ELK Stack

CI/CD:
  - GitHub Actions
  - Docker Registry
```

---

## 六、多 Agent 系统设计

### 6.1 Agent 角色定义

| Agent | 职责 | 核心能力 |
|-------|------|---------|
| **架构师** | 整体规划、终审 | 结构把控、主题一致性 |
| **撰稿人** | 具体写作 | 场景描写、对话生成 |
| **批判家** | 质量审核 | 一致性检查、AI 味检测 |
| **编辑** | 润色优化 | 去 AI 味、文风调整 |
| **情感设计师** | 情感曲线 | 情感设计、共鸣预测 |
| **资料员** | 记忆管理 | RAG 检索、设定更新 |
| **协调器** | 任务调度 | 流程控制、Agent 辩论 |

### 6.2 Agent 通信协议

**消息格式**：
```python
@dataclass
class AgentMessage:
    message_id: str
    sender: str
    recipients: list[str]
    message_type: MessageType  # STATE_UPDATE, INFO_REQUEST, etc.
    priority: Priority  # CRITICAL, HIGH, NORMAL, LOW
    subject: str
    content: dict[str, Any]
    requires_response: bool = False
    timestamp: datetime = field(default_factory=datetime.now)
```

**响应格式**：
```python
@dataclass
class AgentResponse:
    success: bool
    data: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    confidence: float = 1.0
    reasoning: str = ""  # 决策理由（可解释性）
```

### 6.3 反思循环引擎

**核心流程**：
```python
async def generate_with_reflection(chapter_number: int, context: dict):
    # 1. 架构师规划
    outline = await architect.plan_chapter(chapter_number, context)
    
    # 2. 情感设计师设计曲线
    emotion_curve = await emotion_designer.design(outline)
    
    # 3. 分场景生成
    scenes = []
    for scene in outline.scenes:
        scene = await writer.write_scene(scene, emotion_curve)
        scenes.append(scene)
    
    chapter_content = assemble_chapter(scenes)
    
    # 4. 多轮反思
    for round in range(3):
        # 多 Agent 评估
        evaluations = await multi_agent_evaluate(chapter_content, context)
        
        # 综合评分
        overall_score = calculate_overall_score(evaluations)
        
        # 检查是否达标
        if overall_score >= 0.85:
            break
        
        # 识别问题
        issues = identify_issues(evaluations)
        
        # Agent 辩论（关键问题）
        if issues.critical:
            debate_result = await agent_debate(issues, context)
            revision_plan = debate_result.revision_plan
        else:
            revision_plan = generate_revision_plan(issues)
        
        # 修改
        chapter_content = await editor.revise(chapter_content, revision_plan)
    
    # 5. 架构师终审
    final_review = await architect.review_chapter(chapter_content, outline)
    
    return {
        "content": chapter_content,
        "score": overall_score,
        "approved": final_review.approved
    }
```

---

## 七、质量评估体系

### 7.1 14 维度评估指标

```python
@dataclass
class QualityMetrics:
    # 基础质量（3 项）
    fluency: float = 0.0                    # 语言流畅度
    vocabulary_richness: float = 0.0        # 词汇丰富度
    sentence_variation: float = 0.0         # 句式变化
    
    # 叙事质量（3 项）
    plot_tightness: float = 0.0             # 情节紧凑度
    conflict_intensity: float = 0.0         # 冲突强度
    suspense: float = 0.0                   # 悬念设置
    
    # 一致性质量（4 项）
    character_consistency: float = 0.0      # 人物一致性
    world_consistency: float = 0.0          # 设定一致性
    logic_coherence: float = 0.0            # 逻辑连贯性
    timeline_consistency: float = 0.0       # 时间线一致性
    
    # 艺术质量（4 项）
    emotional_resonance: float = 0.0        # 情感共鸣
    imagery: float = 0.0                    # 意象营造
    dialogue_quality: float = 0.0           # 对话质量
    theme_depth: float = 0.0                # 主题深度
    
    # AI 味检测（单独）
    ai_taste_score: float = 0.0             # AI 味道（越低越好）
    
    def calculate_overall_score(self, weights: dict = None) -> float:
        """计算综合评分"""
        if weights is None:
            weights = {
                "basic": 0.15,
                "narrative": 0.20,
                "consistency": 0.35,
                "artistic": 0.30
            }
        
        basic = (self.fluency + self.vocabulary_richness + self.sentence_variation) / 3
        narrative = (self.plot_tightness + self.conflict_intensity + self.suspense) / 3
        consistency = (self.character_consistency + self.world_consistency + 
                      self.logic_coherence + self.timeline_consistency) / 4
        artistic = (self.emotional_resonance + self.imagery + 
                   self.dialogue_quality + self.theme_depth) / 4
        
        overall = (weights["basic"] * basic +
                  weights["narrative"] * narrative +
                  weights["consistency"] * consistency +
                  weights["artistic"] * artistic)
        
        # AI 味惩罚
        ai_penalty = max(0, self.ai_taste_score - 0.3) * 0.5
        
        return max(0.0, overall - ai_penalty)
```

### 7.2 质量等级标准

| 等级 | 综合评分 | 一致性 | AI 味 | 说明 |
|------|---------|--------|------|------|
| **草稿级** | ≥0.6 | ≥0.7 | ≤0.4 | 可以继续，需要后续修改 |
| **审核级** | ≥0.75 | ≥0.8 | ≤0.3 | 可以进入审核流程 |
| **发布级** | ≥0.85 | ≥0.85 | ≤0.2 | 可以直接发布 |

### 7.3 AI 味检测方法

**检测维度**：

1. **高频 AI 词汇**
   ```python
   AI_WORDS = [
       "令人不禁", "宛如", "总之", "可以说",
       "值得注意的是", "综上所述", "显而易见"
   ]
   
   def detect_ai_words(text: str) -> list[str]:
       return [word for word in AI_WORDS if word in text]
   ```

2. **句式单一性**
   ```python
   def analyze_sentence_variety(text: str) -> float:
       sentences = split_sentences(text)
       lengths = [len(s) for s in sentences]
       
       if len(lengths) < 2:
           return 0.0
       
       # 计算标准差
       mean = sum(lengths) / len(lengths)
       variance = sum((x - mean) ** 2 for x in lengths) / len(lengths)
       std_dev = variance ** 0.5
       
       # 标准差在 15-40 之间较好
       if 15 <= std_dev <= 40:
           return 1.0
       elif std_dev < 15:
           return std_dev / 15
       else:
           return max(0.0, 1.0 - (std_dev - 40) / 40)
   ```

3. **突发性（Burstiness）**
   ```python
   def calculate_burstiness(text: str) -> float:
       # 人类写作有明显的"突发"特征
       # AI 生成往往过于均匀
       
       paragraphs = split_paragraphs(text)
       para_lengths = [len(p) for p in paragraphs]
       
       # 计算变异系数
       mean = sum(para_lengths) / len(para_lengths)
       std = (sum((x - mean) ** 2 for x in para_lengths) / len(para_lengths)) ** 0.5
       cv = std / mean if mean > 0 else 0
       
       # 人类写作的 CV 通常在 0.5-1.5 之间
       if 0.5 <= cv <= 1.5:
           return 1.0
       elif cv < 0.5:
           return cv / 0.5
       else:
           return max(0.0, 1.0 - (cv - 1.5) / 1.5)
   ```

---

## 八、数据库设计

### 8.1 核心表结构

```sql
-- 用户表
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 项目表
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    title VARCHAR(255) NOT NULL,
    genre VARCHAR(100),
    theme TEXT,
    tone VARCHAR(100),
    status VARCHAR(50) DEFAULT 'draft',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 人物表
CREATE TABLE characters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id),
    name VARCHAR(255) NOT NULL,
    data JSONB NOT NULL,  -- 完整人物数据
    version INTEGER DEFAULT 1,
    created_chapter INTEGER,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 章节表
CREATE TABLE chapters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id),
    chapter_number INTEGER NOT NULL,
    title VARCHAR(255),
    content TEXT NOT NULL,
    outline JSONB,
    word_count INTEGER,
    status VARCHAR(50) DEFAULT 'draft',
    quality_metrics JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, chapter_number)
);

-- 章节版本表
CREATE TABLE chapter_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chapter_id UUID REFERENCES chapters(id),
    version_number INTEGER NOT NULL,
    content TEXT NOT NULL,
    change_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 伏笔表
CREATE TABLE foreshadowing (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID REFERENCES projects(id),
    content TEXT NOT NULL,
    planted_chapter INTEGER,
    payoff_chapter INTEGER,
    status VARCHAR(50) DEFAULT 'pending',
    importance INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 评估记录表
CREATE TABLE evaluations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chapter_id UUID REFERENCES chapters(id),
    metrics JSONB NOT NULL,
    overall_score FLOAT NOT NULL,
    ai_taste_score FLOAT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 索引优化
CREATE INDEX idx_chapters_project ON chapters(project_id, chapter_number);
CREATE INDEX idx_characters_project ON characters(project_id);
CREATE INDEX idx_foreshadowing_project ON foreshadowing(project_id, status);
CREATE INDEX idx_evaluations_chapter ON evaluations(chapter_id);
```

---

## 九、开发路线图

### 9.1 Phase 1: MVP（第 1-12 周）

```
第 1-2 周：项目初始化
├── 前端：Next.js 项目搭建
├── 后端：FastAPI 项目搭建
├── 数据库：PostgreSQL + Qdrant 部署
├── Docker：容器化配置
└── CI/CD：基础流水线

第 3-4 周：基础功能
├── 用户认证（JWT）
├── 项目管理 CRUD
├── 基础设定输入界面
└── 数据库模型实现

第 5-6 周：Agent 基类与消息总线
├── Agent 基类设计
├── 消息总线实现
├── 事件系统
└── 日志与监控

第 7-8 周：核心 Agent 实现
├── 架构师 Agent
├── 撰稿人 Agent
├── 批判家 Agent
└── 基础测试

第 9-10 周：记忆系统
├── 故事圣经实现
├── 向量数据库集成
├── RAG 检索
└── 设定注入

第 11-12 周：质量评估与测试
├── 14 维度评估实现
├── AI 味检测
├── 端到端测试
└── MVP 发布（内部测试）

里程碑:
- 能生成 3000 字章节
- 一致性评分>0.7
- AI 味<0.4
- 10 个种子用户测试
```

### 9.2 Phase 2: V1.0（第 13-24 周）

```
第 13-14 周：情感设计师 Agent
├── 情感曲线设计
├── 情感评估
└── 情感优化

第 15-16 周：编辑 Agent
├── 润色功能
├── 去 AI 味优化
└── 风格调整

第 17-18 周：反思循环引擎
├── 多轮评估
├── Agent 辩论
└── 自动重写

第 19-20 周：可视化
├── 质量雷达图
├── 人物关系图
├── 情感曲线可视化
└── 进度追踪

第 21-22 周：版本控制
├── 章节版本管理
├── 版本对比
└── 回滚功能

第 23-24 周：用户测试与优化
├── 种子用户测试（50 人）
├── 性能优化
└── V1.0 发布

里程碑:
- 完整多 Agent 系统
- 能生成 10 万字
- AI 味<0.3
- 50+ 活跃用户
```

### 9.3 Phase 3: V2.0（第 25-52 周）

```
第 25-30 周：学习系统
├── 用户偏好记录
├── 修改历史分析
└── 个性化推荐

第 31-36 周：风格模型
├── 训练数据收集
├── 模型微调
└── 风格迁移

第 37-42 周：高级功能
├── 多卷本规划
├── 平行宇宙
├── 伏笔自动回收
└── 协作编辑

第 43-52 周：完善与优化
├── 性能优化
├── 成本优化
├── 规模化测试
└── V2.0 发布

里程碑:
- 能生成 100 万字+
- AI 味<0.2
- 用户满意度>4.5
- 200+ 付费用户
```

---

## 十、成本与风险

### 10.1 成本估算

#### 开发成本（MVP 阶段）

| 项目 | 月度成本 | 备注 |
|------|---------|------|
| 人力 | $15000-25000 | 3 人团队 |
| 模型 API | $1000-3000 | 开发测试 |
| 服务器 | $500-1000 | 云服务器 + 数据库 |
| 其他服务 | $200-500 | 监控/日志/CDN |
| **合计** | **$16700-29500/月** | |

#### 运营成本（V1.0 后）

| 项目 | 月度成本 | 备注 |
|------|---------|------|
| 人力 | $30000-50000 | 6-8 人团队 |
| 模型 API | $5000-10000 | 100 付费用户 |
| 服务器 | $2000-5000 | 向量库 + 应用 |
| **合计** | **$37000-65000/月** | |

### 10.2 风险评估

#### 技术风险

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|---------|
| 多 Agent 成本过高 | 高 | 高 | 优化调用策略、缓存、批量处理 |
| 生成速度太慢 | 中 | 中 | 异步生成、进度可视化、可中断 |
| 质量评估不准确 | 中 | 高 | 人工标注、持续优化、用户反馈 |
| 向量检索性能 | 低 | 中 | 索引优化、分片、缓存热点 |

#### 产品风险

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|---------|
| 用户不愿等待 | 中 | 高 | 进度可视化、预估时间、可中断 |
| 质量达不到预期 | 中 | 高 | 明确定位、用户教育、人工审核点 |
| 炼字工坊跟进 | 高 | 中 | 快速迭代、建立用户壁垒 |
| 大厂进入赛道 | 高 | 高 | 专注垂直、做深做精 |

---

## 十一、成功指标

### 11.1 产品指标

| 指标 | MVP 目标 | V1.0 目标 | V2.0 目标 |
|------|---------|----------|----------|
| 生成质量 | 一致性>0.7 | 一致性>0.8 | 一致性>0.85 |
| AI 味 | <0.4 | <0.3 | <0.2 |
| 生成速度 | 3000 字/10 分钟 | 3000 字/8 分钟 | 3000 字/5 分钟 |
| 用户满意度 | >3.5/5 | >4.0/5 | >4.5/5 |

### 11.2 商业指标

| 指标 | MVP | V1.0 | V2.0 |
|------|-----|------|------|
| 活跃用户 | 50 | 500+ | 2000+ |
| 付费用户 | - | 50+ | 200+ |
| 月收入 | $0 | $5000+ | $20000+ |
| 付费率 | - | 10% | 10% |

### 11.3 技术指标

| 指标 | MVP | V1.0 | V2.0 |
|------|-----|------|------|
| API 响应时间 | <500ms | <300ms | <200ms |
| 任务完成率 | >90% | >95% | >98% |
| 系统可用性 | >95% | >99% | >99.9% |
| 模型调用成本 | $0.5/章 | $0.3/章 | $0.2/章 |

---

## 附录

### A. 竞品分析

#### 炼字工坊分析

**优势**：
- RAG 架构解决遗忘问题
- AI 消痕业内领先
- 全流程覆盖
- 免费策略获客

**不足**：
- Agent 协作深度不够
- 质量评估体系不完善
- 艺术性不足
- 可解释性弱

**我们的机会**：
- 实现真正的多 Agent 辩论与反思
- 建立 14 维度质量评估体系
- 引入情感曲线和风格模型
- 每个决策都有理由追溯

### B. 术语表

| 术语 | 解释 |
|------|------|
| RAG | Retrieval-Augmented Generation，检索增强生成 |
| AI 味 | AI 生成文本的特殊风格和痕迹 |
| Burstiness | 文本的突发性，人类写作特征 |
| OOC | Out Of Character，角色性格崩坏 |
| 伏笔 | 前文埋下的线索，后文回收 |

### C. 参考资料

1. [Attention Is All You Need](https://arxiv.org/abs/1706.03762)
2. [LangChain Documentation](https://python.langchain.com/)
3. [Qdrant Documentation](https://qdrant.tech/documentation/)
4. [Next.js Documentation](https://nextjs.org/docs)

---

**文档结束**

---

## 📝 变更日志

| 版本 | 日期 | 变更内容 | 作者 |
|------|------|---------|------|
| v1.0 | 2026-03-18 | 初始版本 | AI Assistant |

---

**审批**：

- [ ] 产品负责人
- [ ] 技术负责人
- [ ] 设计负责人
