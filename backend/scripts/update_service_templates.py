#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 JSON 文件更新 prompt_template_service.py 中的 SYSTEM_TEMPLATES
正确处理多行字符串
"""
import json

# 读取 JSON 文件
with open("data/templates_24.json", "r", encoding="utf-8") as f:
    templates = json.load(f)

# 生成 Python 代码，手动格式化
lines = ["SYSTEM_TEMPLATES = ["]

for i, template in enumerate(templates):
    lines.append("    {")
    
    # 普通字段
    for key in ["name", "tagline", "description", "category", "sub_category", "difficulty_level"]:
        value = template[key]
        lines.append(f'        "{key}": "{value}",')
    
    # tags 数组
    tags_str = ", ".join([f'"{t}"' for t in template["tags"]])
    lines.append(f'        "tags": [{tags_str}],')
    
    # recommended_scenes 数组
    scenes_str = ", ".join([f'"{s}"' for s in template["recommended_scenes"]])
    lines.append(f'        "recommended_scenes": [{scenes_str}],')
    
    # variables 数组
    vars_list = []
    for var in template["variables"]:
        req = "True" if var["required"] else "False"
        vars_list.append(f'{{"name": "{var["name"]}", "description": "{var["description"]}", "required": {req}}}')
    vars_str = ", ".join(vars_list)
    lines.append(f'        "variables": [{vars_str}],')
    
    # content 字段 - 使用三引号
    content = template["content"].replace('"""', '\\"\\"\\"')  # 转义已有的三引号
    lines.append(f'        "content": """{content}""",')
    
    lines.append("    },")

lines.append("]")

python_code = "\n".join(lines)

# 读取原文件
with open("services/prompt_template_service.py", "r", encoding="utf-8") as f:
    content = f.read()

# 找到 SYSTEM_TEMPLATES 的位置并替换
import re
pattern = r'SYSTEM_TEMPLATES = \[.*?\](?=\n\n|\Z)'

# 替换
new_content = re.sub(pattern, python_code, content, flags=re.DOTALL)

# 写回文件
with open("services/prompt_template_service.py", "w", encoding="utf-8") as f:
    f.write(new_content)

print(f"✅ 成功更新 SYSTEM_TEMPLATES，共 {len(templates)} 套模板")
