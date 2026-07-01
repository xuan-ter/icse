"""
基础参数分类器
功能：将探测到的支持参数划分为Analysis（分析）和Transform（变换）两大类。
"""
import os

def classify_args():
    input_file = r'c:\Users\21101\Desktop\实验\llvm_dummy\llvm_args_probed_supported.txt'
    output_file = r'c:\Users\21101\Desktop\实验\llvm_dummy\classification\llvm_args_classified.txt'

    with open(input_file, 'r', encoding='utf-8') as f:
        # Skip header if present (first line usually description)
        lines = [line.strip() for line in f.readlines() if line.strip()]
        # Check if first line is a header (doesn't start with -)
        if lines and not lines[0].startswith('-'):
            header = lines[0]
            args = lines[1:]
        else:
            header = "LLVM Args Classification"
            args = lines

    classified = []
    
    # Known Analysis keywords/exact matches
    # Most flags here are disable-optimization, so they are Transforms.
    # We look for exceptions.
    analysis_keywords = [
        'analysis',
        'info', # check context
        'verify',
        'lint',
        'print',
        'dot-',
        'view-',
        'aa' # BasicAA
    ]

    # Explicit map for tricky ones
    # Key: arg string (including -disable-)
    # Value: 'Analysis' or 'Transform'
    override_map = {
        '-disable-basic-aa': 'Analysis',
        '-disable-aa-sched-mi': 'Analysis', # Sched machine instr analysis?
        '-disable-ppc-ctrloop-analysis': 'Analysis',
        '-disable-auto-upgrade-debug-info': 'Transform', # Upgrades are transforms
        '-disable-check-noreturn-call': 'Analysis', # Sounds like a check/analysis
        '-disable-verify': 'Analysis',
        '-disable-gisel-legality-check': 'Analysis', # Checking legality is analysis
        '-disable-nofree-inference': 'Transform', # Inference that annotates (FunctionAttrs) is Transform
        '-disable-nounwind-inference': 'Transform',
        '-disable-symbolication': 'Analysis', # Mapping addr to symbol is analysis
        '-disable-sched-critical-path': 'Analysis', # Computing critical path is analysis
        '-disable-sched-cycles': 'Analysis',
        '-disable-sched-hazard': 'Analysis',
        '-disable-sched-height': 'Analysis',
        '-disable-sched-live-uses': 'Analysis',
        '-disable-sched-physreg-join': 'Analysis',
        '-disable-sched-reg-pressure': 'Analysis',
        '-disable-sched-stalls': 'Analysis',
        '-disable-sched-vrcycle': 'Analysis',
        '-disable-machine-cse': 'Transform',
        '-disable-machine-licm': 'Transform',
        '-disable-machine-sink': 'Transform',
    }

    for arg in args:
        category = 'Transform' # Default
        
        # Check override
        if arg in override_map:
            category = override_map[arg]
        else:
            # Heuristics
            lower_arg = arg.lower()
            
            # If it ends with 'aa' and is not in overrides, check logic
            if lower_arg.endswith('-aa'):
                 category = 'Analysis'
            elif 'analysis' in lower_arg:
                 category = 'Analysis'
            
        classified.append((arg, category))

    # Write output to two separate files
    output_analysis = r'c:\Users\21101\Desktop\实验\llvm_dummy\classification\llvm_args_analysis.txt'
    output_transform = r'c:\Users\21101\Desktop\实验\llvm_dummy\classification\llvm_args_transform.txt'

    count_analysis = 0
    count_transform = 0

    with open(output_analysis, 'w', encoding='utf-8') as f_analysis, \
         open(output_transform, 'w', encoding='utf-8') as f_transform:
        
        # Write headers if desired, or just raw lists.
        # Let's write raw lists for easier usage, or with a simple header.
        f_analysis.write("LLVM Analysis Args\n")
        f_transform.write("LLVM Transform Args\n")

        for arg, cat in classified:
            if cat == 'Analysis':
                f_analysis.write(f"{arg}\n")
                count_analysis += 1
            else:
                f_transform.write(f"{arg}\n")
                count_transform += 1

    print(f"Classified {len(classified)} args.")
    print(f"  Analysis:  {count_analysis} -> {output_analysis}")
    print(f"  Transform: {count_transform} -> {output_transform}")

if __name__ == "__main__":
    classify_args()
