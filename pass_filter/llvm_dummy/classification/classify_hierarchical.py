"""
分层分类工具
功能：实现双层分类（Analysis/Transform -> Functional Category），生成结构化的参数列表。
"""
import os

def classify_hierarchical():
    base_dir = r'c:\Users\21101\Desktop\实验\llvm_dummy\classification'
    
    # Input files
    file_transform = os.path.join(base_dir, 'llvm_args_transform.txt')
    file_analysis = os.path.join(base_dir, 'llvm_args_analysis.txt')
    
    # Check existence
    if not os.path.exists(file_transform) or not os.path.exists(file_analysis):
        print("Missing input files.")
        return

    # Load data
    def load_args(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
            return [l for l in lines if not l.startswith("LLVM") and not l.startswith("===")]

    args_transform = load_args(file_transform)
    args_analysis = load_args(file_analysis)

    # Categories Definition
    # We use a shared categorization logic for both lists
    categories = {
        'Vectorization': ['vec', 'slp'],
        'Loop': ['loop', 'licm', 'lsr', 'lftr', 'indvar', 'iv-users', 'cycle'],
        'Inlining': ['inline'],
        'Control Flow': ['branch', 'block', 'tail', 'jump', 'switch', 'cfg', 'ifcvt', 'sink', 'hoist', 'placement', 'demotion', 'goto'],
        'Data Flow/Simplification': ['cse', 'dce', 'copy', 'const', 'instcombine', 'simplify', 'combine', 'redundant', 'elim'],
        'Memory': ['memcpy', 'memmove', 'load', 'store', 'gep', 'sroa', 'dse', 'memop', 'stack', 'aa', 'alias'],
        'CodeGen/Backend': ['sched', 'reg', 'alloc', 'peephole', 'layout', 'ra-', 'post-ra', 'spill', 'packetizer', 'fixup', 'gisel'],
        'Debug/Metadata': ['debug', 'dwarf', 'symbol', 'verify', 'print', 'view', 'dot-'],
    }

    # Target Keywords for filtering (Optional, but good to separate)
    target_keywords = ['hexagon', 'arm', 'a15', 'a57', 'mips', 'nvptx', 'ppc', 'p10', 'bpf', 'wasm', 'riscv', 'amdgpu', 'systemz', 'x86', 'sse', 'avx']

    def classify_list(arg_list):
        classified = {k: [] for k in categories.keys()}
        others = []
        target_specific = []

        for arg in arg_list:
            lower_arg = arg.lower()
            
            # 1. Target Check
            is_target = False
            for kw in target_keywords:
                 if f"-{kw}-" in lower_arg or lower_arg.startswith(f"-{kw}") or f"_{kw}_" in lower_arg:
                     target_specific.append(arg)
                     is_target = True
                     break
            if is_target:
                continue

            # 2. Functional Check
            matched = False
            for cat, keywords in categories.items():
                if any(k in lower_arg for k in keywords):
                    classified[cat].append(arg)
                    matched = True
                    break
            
            if not matched:
                others.append(arg)
        
        return classified, others, target_specific

    # Process both lists
    res_transform = classify_list(args_transform) # (classified, others, targets)
    res_analysis = classify_list(args_analysis)

    # Output
    output_file = os.path.join(base_dir, 'llvm_args_hierarchical.txt')
    with open(output_file, 'w', encoding='utf-8') as f:
        
        def write_section(title, data_tuple):
            cat_dict, other_list, target_list = data_tuple
            f.write(f"##################################################\n")
            f.write(f"# {title}\n")
            f.write(f"##################################################\n\n")
            
            # 1. Functional Categories
            for cat, items in cat_dict.items():
                if items:
                    f.write(f"=== {cat} ===\n")
                    for item in sorted(items):
                        f.write(f"{item}\n")
                    f.write("\n")
            
            # 2. Others
            if other_list:
                f.write(f"=== Others (Unclassified) ===\n")
                for item in sorted(other_list):
                    f.write(f"{item}\n")
                f.write("\n")

            # 3. Target Specific (Collapsed at bottom of section)
            if target_list:
                f.write(f"=== Target Specific (Filtered) ===\n")
                for item in sorted(target_list):
                    f.write(f"{item}\n")
                f.write("\n")

        write_section("TRANSFORM ARGS (Optimization Passes)", res_transform)
        f.write("\n\n")
        write_section("ANALYSIS ARGS (Information Gathering)", res_analysis)

    print(f"Hierarchical classification written to {output_file}")

if __name__ == '__main__':
    classify_hierarchical()
