#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
创建 prompt_templates 表并导入 23 套模板数据
"""
import psycopg2
import json
import uuid
from datetime import datetime

# 读取 JSON 文件
with open("data/templates_24.json", "r", encoding="utf-8") as f:
    templates_data = json.load(f)

print(f"📂 从 JSON 文件加载了 {len(templates_data)} 套模板")

try:
    conn = psycopg2.connect(
        host="localhost",
        user="postgres",
        password="password",
        database="novel_agent"
    )
    conn.autocommit = False
    cur = conn.cursor()
    
    # 1. 创建表
    print("\n📋 创建 prompt_templates 表...")
    cur.execute("""
        CREATE TABLE prompt_templates (
            id UUID PRIMARY KEY,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL,
            name VARCHAR(200) NOT NULL,
            tagline VARCHAR(300) NOT NULL,
            description TEXT NOT NULL,
            category VARCHAR(50) NOT NULL,
            sub_category VARCHAR(50),
            tags JSON NOT NULL DEFAULT '[]',
            content TEXT NOT NULL,
            variables JSON NOT NULL DEFAULT '[]',
            use_count INTEGER NOT NULL DEFAULT 0,
            is_system BOOLEAN NOT NULL DEFAULT false,
            is_active BOOLEAN NOT NULL DEFAULT true,
            user_id UUID,
            recommended_scenes JSON NOT NULL DEFAULT '[]',
            difficulty_level VARCHAR(20) NOT NULL DEFAULT 'intermediate'
        )
    """)
    
    # 创建索引
    cur.execute("CREATE INDEX ix_prompt_templates_category ON prompt_templates(category)")
    cur.execute("CREATE INDEX ix_prompt_templates_is_system ON prompt_templates(is_system)")
    cur.execute("CREATE INDEX ix_prompt_templates_name_search ON prompt_templates(name)")
    
    print("✅ 表创建成功！")
    
    # 2. 导入模板数据
    print(f"\n🚀 开始导入 {len(templates_data)} 套模板...")
    
    now = datetime.now().isoformat()
    
    for i, template in enumerate(templates_data, 1):
        template_id = str(uuid.uuid4())
        
        cur.execute("""
            INSERT INTO prompt_templates (
                id, created_at, updated_at, name, tagline, description,
                category, sub_category, tags, content, variables,
                use_count, is_system, is_active, user_id,
                recommended_scenes, difficulty_level
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            template_id,
            now,
            now,
            template["name"],
            template["tagline"],
            template["description"],
            template["category"],
            template.get("sub_category"),
            json.dumps(template["tags"]),
            template["content"],
            json.dumps(template["variables"]),
            0,
            True,  # is_system
            True,  # is_active
            None,  # user_id (NULL)
            json.dumps(template["recommended_scenes"]),
            template["difficulty_level"]
        ))
        
        if i % 5 == 0 or i == len(templates_data):
            print(f"  ✅ 已导入 {i}/{len(templates_data)} 套模板")
    
    conn.commit()
    
    # 3. 验证导入结果
    cur.execute("SELECT COUNT(*) FROM prompt_templates")
    count = cur.fetchone()[0]
    
    cur.execute("SELECT name FROM prompt_templates LIMIT 5")
    names = [row[0] for row in cur.fetchall()]
    
    print(f"\n🎉 导入完成！")
    print(f"   数据库中共有 {count} 套模板")
    print(f"   前 5 套模板:")
    for i, name in enumerate(names, 1):
        print(f"   {i}. {name}")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"\n❌ 错误：{e}")
    if 'conn' in locals():
        conn.rollback()
        conn.close()
