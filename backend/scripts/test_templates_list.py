#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试获取模板列表
"""
import requests

email = "test_admin@test.com"
password = "admin123456"

try:
    # 登录获取 token
    login_response = requests.post(
        "http://localhost:8000/api/v1/auth/login",
        json={"email": email, "password": password}
    )
    token = login_response.json()["access_token"]

    # 获取模板列表
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        "http://localhost:8000/api/v1/prompt-templates?page=1&page_size=20",
        headers=headers
    )

    print(f"状态码：{response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"✅ 请求成功！")
        print(f"   templates 数量：{len(data.get('templates', []))}")
        print(f"   total: {data.get('total')}")
        print(f"   categories: {data.get('categories')}")

        if data.get('templates'):
            print(f"\n   前 3 套模板:")
            for i, t in enumerate(data['templates'][:3], 1):
                print(f"   {i}. {t['name']} - {t['tagline']}")
    else:
        print(f"❌ 请求失败：{response.text}")

except Exception as e:
    print(f"❌ 错误：{e}")
