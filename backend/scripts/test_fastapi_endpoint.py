#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接测试 FastAPI 应用的 /api/v1/prompt-templates 端点
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ.setdefault(
    "DATABASE_URL",
    os.getenv("TEST_DATABASE_URL", "postgresql+asyncpg://postgres@localhost:5432/novel_agent"),
)
os.environ.setdefault(
    "JWT_SECRET_KEY",
    os.getenv("TEST_JWT_SECRET_KEY", "dev-secret-change-in-production"),
)

from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_endpoint():
    print("测试 /api/v1/prompt-templates 端点...")
    
    # 先测试不带认证的请求（应该返回 401）
    response = client.get("/api/v1/prompt-templates")
    print(f"无认证请求状态码：{response.status_code}")
    
    # 模拟登录获取 token
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": "test_admin@test.com", "password": "admin123456"}
    )
    print(f"登录请求状态码：{login_response.status_code}")
    
    if login_response.status_code == 200:
        token = login_response.json()["access_token"]
        print(f"✅ 登录成功，token: {token[:50]}...")
        
        # 带认证的请求
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/api/v1/prompt-templates?page=1&page_size=20", headers=headers)
        
        print(f"\n带认证请求状态码：{response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 请求成功！")
            print(f"   templates 数量：{len(data.get('templates', []))}")
            print(f"   total: {data.get('total')}")
            print(f"   categories: {data.get('categories')}")
        else:
            print(f"❌ 请求失败：{response.status_code}")
            print(f"   响应内容：{response.text}")
    else:
        print(f"登录失败：{login_response.text}")

if __name__ == "__main__":
    test_endpoint()
