"""
Pass名称清洗工具 v2
功能：增强版Pass名称清洗，支持更多格式（如冒号分隔），过滤非Pass关键词。
"""
import re

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
            
        # Skip lines starting with Chinese (headers/descriptions)
        if re.match(r'^[\u4e00-\u9fa5]', line):
            continue
            
        pass_name = ""
        
        # Strategy 1: Check for colon separator
        # Covers: "aa-eval：...", "deadarghaX0r：..."
        if '：' in line or ':' in line:
            parts = re.split(r'[：:]', line, maxsplit=1)
            pass_name = parts[0].strip()
        else:
            # Strategy 2: No colon. Assume pass name is lowercase alphanumeric + hyphens.
            # Covers: "basiccg基本...", "kernel-infoGPU..."
            # Note: We strictly match lowercase to avoid capturing "GPU", "Always" etc.
            match = re.match(r'^([a-z0-9][a-z0-9-]*)', line)
            if match:
                pass_name = match.group(1)
            else:
                # Fallback: if it doesn't match lowercase start, maybe it is a weird line?
                # e.g. "GPU..." (unlikely as we filtered lines starting with Chinese)
                # Just keep the original split by first non-ascii?
                # Let's log it or just take the whole first word?
                # For now, if regex fails, we skip or take strictly up to Chinese.
                match_all = re.match(r'^([a-zA-Z0-9-]+)', line)
                if match_all:
                    pass_name = match_all.group(1)
                else:
                    # Should not happen given the structure
                    continue
        
        # Final cleanup
        pass_name = pass_name.strip()
        
        # Filter out purely descriptive words if they leaked (unlikely with above logic)
        # e.g. "Analysis", "Transform"
        if pass_name in ["Analysis", "Transform", "Pass", "Overview"]:
            continue
            
        if pass_name:
            cleaned_passes.append(pass_name)
            
    # Write to output file
    with open(output_file, 'w', encoding='utf-8') as f:
        for p in cleaned_passes:
            f.write(f"{p}\n")
            
    print(f"Cleaned {len(cleaned_passes)} pass names. Saved to {output_file}")

if __name__ == '__main__':
    clean_pass_names()
