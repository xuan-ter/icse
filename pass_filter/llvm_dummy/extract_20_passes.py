"""
Pass提取工具
功能：从验证过的搜索空间JSON中提取所有可控Pass名称，生成列表文件。
"""
import json
import os

base_dir = r"c:\Users\21101\Desktop\实验\llvm_dummy"
input_json = os.path.join(base_dir, "llvm_search_space_validated.json")
output_txt = os.path.join(base_dir, "controllable_passes.txt")

if not os.path.exists(input_json):
    print(f"Error: {input_json} not found.")
    exit(1)

with open(input_json, 'r', encoding='utf-8') as f:
    data = json.load(f)

passes = list(data.get("passes", {}).keys())
passes.sort()

with open(output_txt, 'w', encoding='utf-8') as f:
    for p in passes:
        f.write(f"{p}\n")

print(f"Successfully wrote {len(passes)} passes to {output_txt}")
for p in passes:
    print(f" - {p}")
