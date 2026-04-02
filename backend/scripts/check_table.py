#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
使用 psycopg2 检查数据库表
"""
import psycopg2

try:
    conn = psycopg2.connect(
        host="localhost",
        user="postgres",
        password="password",
        database="novel_agent"
    )
    cur = conn.cursor()
    
    # 检查表是否存在
    cur.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name = 'prompt_templates'
    """)
    
    result = cur.fetchone()
    
    if result:
        print("✅ prompt_templates 表存在！")
        
        # 查询模板数量
        cur.execute("SELECT COUNT(*) FROM prompt_templates")
        count = cur.fetchone()[0]
        print(f"   数据库中有 {count} 套模板")
        
        # 查询前 3 套模板
        cur.execute("SELECT name FROM prompt_templates LIMIT 3")
        templates = cur.fetchall()
        if templates:
            print("   前 3 套模板:")
            for i, (name,) in enumerate(templates, 1):
                print(f"   {i}. {name}")
    else:
        print("❌ prompt_templates 表不存在！")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"❌ 错误：{e}")
