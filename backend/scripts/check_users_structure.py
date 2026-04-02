#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查 users 表结构
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
    
    cur.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'users'
        ORDER BY ordinal_position
    """)
    
    columns = cur.fetchall()
    
    print("users 表结构:")
    for col_name, data_type, is_nullable in columns:
        nullable = "NULL" if is_nullable == "YES" else "NOT NULL"
        print(f"  - {col_name}: {data_type} ({nullable})")
    
    cur.close()
    conn.close()
    
except Exception as e:
    print(f"❌ 错误：{e}")
