# Story Engine 模型接入

这份文档只讲后台模型接入与角色路由，不面向写手前台。

## 1. 先明确边界

当前约定是：

- 写手前台不显示模型组合、不显示推理强度、不显示供应商名称
- 模型选择属于后台管理员 / 系统配置能力
- Story Engine 会按角色把不同模型分给不同职责

当前角色包括：

- `outline`
- `guardian`
- `logic_debunker`
- `commercial`
- `style_guardian`
- `anchor`
- `arbitrator`
- `stream_writer`

## 2. 配置入口在哪里

### 全局预设定义

文件：

- [story_engine_model_profiles.json](../../backend/config/story_engine_model_profiles.json)

这个文件负责：

- 声明可用模型列表
- 定义默认 preset
- 定义每个 preset 下，各角色使用什么模型和推理强度
- 定义 `guardian_consensus`，用于后台“双守护交叉校验”策略

### 项目级模型路由

服务：

- [story_engine_settings_service.py](../../backend/services/story_engine_settings_service.py)

接口：

- `GET /api/v1/story-engine/model-routing/preset-catalog`
- `GET /api/v1/projects/{project_id}/story-engine/model-routing`
- `PUT /api/v1/projects/{project_id}/story-engine/model-routing`

这些接口是给后台管理能力或未来管理员页面准备的，不应该直接暴露给写手工作台。

## 3. 环境变量怎么填

### 本机直跑

```bash
cp backend/.env.example backend/.env
```

### Docker Compose

```bash
cp backend/.env.compose.example backend/.env.compose
```

然后至少补这些字段：

```env
MODEL_GATEWAY_BASE_URL=https://yunwu.ai/v1
MODEL_GATEWAY_API_KEY=请填你的网关密钥

DEFAULT_MODEL=gpt-5.4
STORY_ENGINE_OUTLINE_MODEL=gpt-5.4
STORY_ENGINE_GUARDIAN_MODEL=gpt-5.4
STORY_ENGINE_LOGIC_MODEL=claude-opus-4-6
STORY_ENGINE_COMMERCIAL_MODEL=deepseek-v3.2
STORY_ENGINE_STYLE_MODEL=gemini-3.1-pro-preview
STORY_ENGINE_ANCHOR_MODEL=gpt-5.4
STORY_ENGINE_ARBITRATOR_MODEL=gpt-5.4
STORY_ENGINE_STREAM_MODEL=gpt-5.4
```

## 4. 当前推荐组合

来自当前默认 `balanced` preset：

- `gpt-5.4`
  负责大纲拆解、设定守护、自动记设定、终局收束、正文起稿
- `claude-opus-4-6`
  负责逻辑挑刺、长线矛盾和时间线压力测试
- `deepseek-v3.2`
  负责爽点、节奏、章末钩子和连载推进感
- `gemini-3.1-pro-preview`
  负责文风贴合、语言层修法和气口保持

另外，设定守护现在默认启用后台双守护交叉校验：

- 主守护默认走 `guardian` 角色绑定模型
- 副守护默认走 `guardian_consensus.shadow_model`
- 两路结论不一致时，会自动拉起 `logic_debunker` 做第三方裁定

对应配置在：

- [story_engine_model_profiles.json](../../backend/config/story_engine_model_profiles.json)

可调字段包括：

- `guardian_consensus.enabled`
- `guardian_consensus.shadow_model`
- `guardian_consensus.shadow_reasoning_effort`
- `guardian_consensus.outline_enabled`
- `guardian_consensus.realtime_enabled`
- `guardian_consensus.final_enabled`

## 5. 校验命令

### 校验当前配置的模型是否能被网关识别

```bash
cd backend
PYTHONPATH=. python3 scripts/verify_story_engine_models.py
```

### 直接跑一遍 Story Engine 烟雾测试

```bash
cd backend
PYTHONPATH=. STORY_ENGINE_SMOKE_BASE_URL=http://127.0.0.1:8000/api/v1 python3 scripts/story_engine_live_smoke.py
```

这条烟雾测试会覆盖：

- 模板导入
- 工作区加载
- 实时守护
- 流式章节生成
- 终稿优化

## 6. 调整策略时优先改哪里

### 如果你只是想换默认模型

优先改：

- `backend/.env`
- `backend/.env.compose`

### 如果你想新增一种官方推荐组合

优先改：

- [story_engine_model_profiles.json](../../backend/config/story_engine_model_profiles.json)

### 如果你想按项目单独覆盖

优先走：

- `PUT /api/v1/projects/{project_id}/story-engine/model-routing`

## 7. 注意事项

- 所有模型请求都必须从后端发出，不要把真实密钥暴露到前端
- Compose 容器里的 Chroma 地址应使用 `chroma:8000`
- 如果网关不可用，部分能力会回退到本地启发式逻辑，但质量会下降
- 写手前台不应该看到“均衡稳稿”“逻辑极限”这类 preset 名称，除非未来单独做管理员后台
