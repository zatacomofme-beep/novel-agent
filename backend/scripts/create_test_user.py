#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
创建测试用户
"""
import psycopg2
import uuid
from datetime import datetime
import bcrypt

email = "test_admin@test.com"
password = "admin123456"

# 使用 bcrypt 生成密码哈希
password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

try:
    conn = psycopg2.connect(
        host="localhost",
        user="postgres",
        password="password",
        database="novel_agent"
    )
    conn.autocommit = False
    cur = conn.cursor()
    
    # 检查用户是否已存在
    cur.execute("SELECT id FROM users WHERE email = %s", (email,))
    existing = cur.fetchone()
    
    if existing:
        print(f"⚠️  用户 {email} 已存在")
        cur.close()
        conn.close()
        exit(0)
    
    # 创建用户
    user_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    
    cur.execute("""
        INSERT INTO users (id, email, password_hash, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s)
    """, (user_id, email, password_hash, now, now))
    
    conn.commit()
    
    print(f"✅ 测试用户创建成功！")
    print(f"   邮箱：{email}")
    print(f"   密码：{password}")
    print(f"   用户 ID: {user_id}")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"❌ 错误：{e}")
    if 'conn' in locals():
        conn.rollback()
        conn.close()
