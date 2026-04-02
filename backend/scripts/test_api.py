#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 API 是否正常返回模板数据
"""
import requests

# 测试登录获取 token
login_data = {
    "email": "smoke@test.com",
    "password": "test123456"
}

try:
    # 登录
    response = requests.post("http://localhost:8000/api/v1/auth/login", json=login_data)
    if response.status_code != 200:
        print(f"❌ 登录失败：{response.status_code}")
        print(f"   {response.text}")
        exit(1)
    
    token = response.json()["access_token"]
    print(f"✅ 登录成功")
    
    # 获取模板列表
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get("http://localhost:8000/api/v1/prompt-templates", headers=headers)
    
    if response.status_code != 200:
        print(f"❌ 获取模板失败：{response.status_code}")
        print(f"   {response.text}")
        exit(1)
    
    data = response.json()
    print(f"\n✅ API 返回成功！")
    print(f"   模板总数：{data['total']}")
    print(f"   返回模板数：{len(data['templates'])}")
    print(f"   分类：{data['categories']}")
    
    if data['templates']:
        print(f"\n   前 5 套模板:")
        for i, t in enumerate(data['templates'][:5], 1):
            print(f"   {i}. {t['name']} - {t['tagline']}")
    
except Exception as e:
    print(f"❌ 错误：{e}")
