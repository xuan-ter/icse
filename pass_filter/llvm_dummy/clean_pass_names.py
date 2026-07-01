"""
Pass名称清洗工具
功能：从LLVM_passes.txt中提取并清洗Pass名称，移除中文描述和非法字符。
"""
import re
import os

def clean_pass_names():
    input_file = r'c:\Users\21101\Desktop\实验\llvm_dummy\LLVM_passes.txt'
    output_file = r'c:\Users\21101\Desktop\实验\llvm_dummy\LLVM_passes_cleaned.txt'
    
    cleaned_passes = []
    
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Skip known header lines or descriptions that are purely Chinese/text
        # "概述..." starts with Chinese
        # "分析", "变换" are headers
        if re.match(r'^[\u4e00-\u9fa5]', line):
            continue
            
        # Extract pass name
        # Pattern: Start with alphanumeric/hyphen, stop at first non-alphanumeric/hyphen (like space, colon, or Chinese)
        match = re.match(r'^([a-zA-Z0-9][a-zA-Z0-9-]*)', line)
        if match:
            pass_name = match.group(1)
            
            # Filter out obviously wrong ones if any (e.g. if the file has some English text descriptions)
            # But based on the file snippet, lines starting with English are usually passes.
            
            # Remove trailing hyphens if any (unlikely based on regex)
            pass_name = pass_name.strip('-')
            
            # Optional: Filter out 'dot-', 'view-', 'print-' if we only want optimization passes?
            # User didn't strictly say so, but usually "Pass清洗" for tuning implies optimization passes.
            # However, the user said "清洗 Pass 名", so I should probably keep all valid passes but just clean the string.
            # I will keep them all.
            
            cleaned_passes.append(pass_name)
            
    # Write to output file
    with open(output_file, 'w', encoding='utf-8') as f:
        for p in cleaned_passes:
            f.write(f"{p}\n")
            
    print(f"Cleaned {len(cleaned_passes)} pass names. Saved to {output_file}")

if __name__ == '__main__':
    clean_pass_names()
