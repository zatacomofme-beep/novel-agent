#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试登录 API
"""
import requests
import json

email = "test_admin@test.com"
password = "admin123456"

try:
    response = requests.post(
        "http://localhost:8000/api/v1/auth/login",
        json={"email": email, "password": password},
        headers={"Content-Type": "application/json"}
    )
    
    print(f"状态码：{response.status_code}")
    print(f"响应内容：{json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    
except Exception as e:
    print(f"❌ 错误：{e}")
