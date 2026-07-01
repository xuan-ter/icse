"""
搜索空间生成器
功能：解析分析报告，提取Pass开关和参数，生成结构化的JSON搜索空间配置。
"""
import re
import json

def parse_analysis_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    passes = {}
    current_pass = None
    capture_mode = None # 'switches' or 'params'
    
    # We only care about "Fully Controllable" and "Tuning Only" sections
    # Let's just iterate line by line and state machine it
    
    lines = content.split('\n')
    in_relevant_section = False
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Detect sections
        if "### Fully Controllable" in line or "### Tuning Only" in line:
            in_relevant_section = True
            continue
        if "### Switch Only" in line or "### No Direct Control" in line:
            in_relevant_section = False
            continue
            
        if not in_relevant_section:
            continue
            
        # Parse Pass Header
        pass_match = re.match(r"Pass: \[(.*?)\]", line)
        if pass_match:
            current_pass = pass_match.group(1)
            passes[current_pass] = {'switches': [], 'params': []}
            capture_mode = None
            continue
            
        # Parse Mode Headers
        if line == "[Switches]:":
            capture_mode = 'switches'
            continue
        if line == "[Tuning Params]:":
            capture_mode = 'params'
            continue
            
        # Parse Items
        if current_pass and capture_mode:
            if line.startswith("... and"):
                continue
            
            if capture_mode == 'switches':
                passes[current_pass]['switches'].append(line)
            elif capture_mode == 'params':
                passes[current_pass]['params'].append(line)

    return passes

def guess_range(param_name):
    # Heuristic rules for parameter ranges
    param_lower = param_name.lower()
    
    if 'threshold' in param_lower:
        if 'inline' in param_lower:
            return {"min": 0, "max": 1000, "step": 50, "default": 225}
        return {"min": 0, "max": 500, "step": 10, "default": 50}
    
    if 'limit' in param_lower:
        return {"min": 0, "max": 1000, "step": 50, "default": 100}
        
    if 'depth' in param_lower:
        return {"min": 0, "max": 32, "step": 1, "default": 8}
        
    if 'count' in param_lower:
        return {"min": 0, "max": 100, "step": 5, "default": 10}
        
    if 'cost' in param_lower:
        return {"min": 0, "max": 200, "step": 10, "default": 0}
        
    if 'percent' in param_lower or 'probability' in param_lower:
        return {"min": 0, "max": 100, "step": 5, "default": 50}
        
    if 'size' in param_lower:
        return {"min": 0, "max": 2048, "step": 64, "default": 256}
    
    # Default fallback
    return {"min": 0, "max": 100, "step": 10, "default": 0}

def generate_search_space(passes, output_file):
    search_space = {
        "description": "LLVM Tuning Search Space",
        "passes": {}
    }
    
    for pass_name, info in passes.items():
        pass_config = {
            "switches": info['switches'],
            "parameters": {}
        }
        
        for param in info['params']:
            pass_config["parameters"][param] = guess_range(param)
            
        if pass_config["parameters"] or pass_config["switches"]:
            search_space["passes"][pass_name] = pass_config
            
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(search_space, f, indent=2)
    
    return search_space

import os

if __name__ == "__main__":
    base_dir = r"c:\Users\21101\Desktop\实验\llvm_dummy"
    input_file = os.path.join(base_dir, "pass_control_analysis.txt")
    output_file = os.path.join(base_dir, "llvm_search_space.json")
    
    print(f"Parsing {input_file}...")
    if not os.path.exists(input_file):
        print(f"Error: {input_file} does not exist!")
        exit(1)
        
    passes = parse_analysis_file(input_file)
    print(f"Found {len(passes)} controllable passes.")
    
    print(f"Generating search space to {output_file}...")
    generate_search_space(passes, output_file)
    print("Done.")
