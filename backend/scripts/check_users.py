#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查数据库用户
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
    
    cur.execute("SELECT id, email FROM users LIMIT 5")
    users = cur.fetchall()
    
    if users:
        print("数据库中的用户:")
        for i, (uid, email) in enumerate(users, 1):
            print(f"  {i}. {email} (ID: {uid})")
    else:
        print("数据库中没有用户")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"❌ 错误：{e}")
