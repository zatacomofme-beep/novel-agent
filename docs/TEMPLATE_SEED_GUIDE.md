# 提示词模板种子数据导入指南

## 概述

本项目包含 24 套精心设计的网文写作模板，涵盖 10 个大类。这些模板通过数据库种子数据的方式初始化，不是硬编码在代码中。

## 模板分类

### 一、世界观构建类（3 套）
1. 玄幻修真世界观模板
2. 都市异能世界观模板
3. 科幻星际世界观模板

### 二、角色塑造类（3 套）
4. 主角人设模板
5. 反派角色模板
6. 配角群像模板

### 三、情节设计类（4 套）
7. 三幕式结构模板
8. 章节公式模板
9. 打脸套路模板
10. 伏笔悬念模板

### 四、打斗战斗类（3 套）
11. 打斗场面模板
12. 越级战斗模板
13. 群战模板

### 五、情感描写类（3 套）
14. 感情线升温模板
15. 虐心情节模板
16. 对话描写模板

### 六、升级进化类（2 套）
17. 玄幻升级递进模板
18. 系统流升级模板

### 七、章尾钩子类（2 套）
19. 章尾钩子模板
20. 断章技巧模板

### 八、高潮设计类（2 套）
21. 高潮设计模板
22. 爽点密集模板

### 九、场景转换类（1 套）
23. 场景转换模板

### 十、起承转合类（1 套）
24. 起承转合模板

## 导入方法

### 方法一：自动种子（推荐）

系统会在首次访问模板列表时自动导入所有 24 套模板。这是通过 `PromptTemplateService._ensure_system_templates_seeded()` 方法实现的。

```python
# 在 prompt_template_service.py 中
async def _ensure_system_templates_seeded(self, session: AsyncSession) -> None:
    result = await session.execute(
        select(PromptTemplate).where(PromptTemplate.is_system == True).limit(1)
    )
    if result.scalar_one_or_none():
        return  # 已有模板，跳过
    
    # 导入所有 24 套模板
    for template_data in SYSTEM_TEMPLATES:
        template = PromptTemplate(is_system=True, **template_data)
        session.add(template)
    await session.commit()
```

### 方法二：手动导入脚本

运行种子数据导入脚本：

```bash
cd /Users/libenshi/Desktop/novels/backend
python scripts/seed_templates.py
```

### 方法三：通过 API 创建

使用创建模板的 API 端点手动创建：

```bash
curl -X POST http://localhost:8000/api/v1/prompt-templates \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "name": "模板名称",
    "tagline": "一句话简介",
    "description": "详细描述",
    "category": "分类",
    "tags": ["标签 1", "标签 2"],
    "content": "模板内容...",
    "difficulty_level": "intermediate",
    "recommended_scenes": ["场景 1", "场景 2"],
    "variables": []
  }'
```

## 模板数据结构

每套模板包含以下字段：

```python
{
    "name": str,              # 模板名称（最多 200 字符）
    "tagline": str,           # 一句话简介（最多 300 字符）
    "description": str,       # 详细描述
    "category": str,          # 分类（最多 50 字符）
    "sub_category": str,      # 子分类（可选）
    "tags": list[str],        # 标签列表
    "content": str,           # 模板内容（支持 Markdown）
    "variables": list[dict],  # 变量列表
    "recommended_scenes": list[str],  # 推荐场景
    "difficulty_level": str,  # 难度（beginner/intermediate/advanced）
    "is_system": bool,        # 是否系统模板
    "is_active": bool,        # 是否激活
}
```

### 变量结构

```python
{
    "name": str,              # 变量名称
    "description": str,       # 变量说明
    "required": bool,         # 是否必填
}
```

## 难度级别

- **beginner** (入门): 基础技巧，适合新手作者
- **intermediate** (进阶): 中等难度，适合有一定经验的作者
- **advanced** (高级): 高级技巧，适合资深作者

## 分类体系

系统支持以下 12 个分类：

1. 世界观构建
2. 角色塑造
3. 情节设计
4. 打斗战斗
5. 情感描写
6. 升级进化
7. 伏笔悬念
8. 章尾钩子
9. 起承转合
10. 场景转换
11. 高潮设计
12. 结局收束

## 使用建议

1. **首次启动**: 系统会自动导入所有 24 套模板
2. **自定义模板**: 用户可以通过前端界面创建自己的模板
3. **模板推荐**: 系统会根据章节内容智能推荐相关模板
4. **模板应用**: 一键应用模板到当前章节

## 数据来源

所有模板基于以下资源整理：
- 网文写作理论
- 知名写作平台教程
- 热门网文套路分析
- 专业作者经验分享

## 维护说明

- **系统模板**: `is_system=True`，用户不能删除或修改
- **用户模板**: `is_system=False`，用户可以管理自己的模板
- **模板更新**: 修改 `SYSTEM_TEMPLATES` 列表后，需要清除数据库重新导入

## 数据库表结构

模板数据存储在 `prompt_templates` 表中：

```sql
CREATE TABLE prompt_templates (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    name VARCHAR(200) NOT NULL,
    tagline VARCHAR(300) NOT NULL,
    description TEXT NOT NULL,
    category VARCHAR(50) NOT NULL,
    sub_category VARCHAR(50),
    tags TEXT[] NOT NULL,
    content TEXT NOT NULL,
    variables JSONB NOT NULL,
    recommended_scenes TEXT[],
    difficulty_level VARCHAR(20) NOT NULL,
    use_count INTEGER DEFAULT 0,
    is_system BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

## 故障排查

### 问题 1: 模板未自动导入

检查日志，确认 `_ensure_system_templates_seeded()` 方法被调用。

### 问题 2: 模板内容为空

检查 `SYSTEM_TEMPLATES` 列表是否完整，确保每套模板的 `content` 字段有内容。

### 问题 3: 分类不显示

访问 `/api/v1/prompt-templates/categories` 端点查看分类列表。

## 扩展模板

如需添加更多模板，可以：

1. 在 `SYSTEM_TEMPLATES` 列表中添加新模板数据
2. 通过前端界面创建用户模板
3. 调用 API 创建模板

## 联系支持

如有问题，请查看项目文档或联系开发团队。
