#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清理 prompt_template_service.py，删除硬编码的 SYSTEM_TEMPLATES
"""

# 读取文件
with open("services/prompt_template_service.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

# 找到 recommend_templates 方法的结尾
# 然后删除之后的所有内容
new_lines = []
in_recommend = False
found_return = False

for i, line in enumerate(lines):
    # 检测是否在 recommend_templates 方法中
    if "async def recommend_templates" in line:
        in_recommend = True
    
    if in_recommend:
        new_lines.append(line)
        # 检测方法的返回语句（最后一个 return）
        if "return [t for _, t in scored_templates[:5]]" in line:
            found_return = True
            # 添加一个空行
            new_lines.append("\n")
            break
    else:
        new_lines.append(line)

# 写回文件
with open("services/prompt_template_service.py", "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print(f"✅ 清理完成，从 {len(lines)} 行减少到 {len(new_lines)} 行")
