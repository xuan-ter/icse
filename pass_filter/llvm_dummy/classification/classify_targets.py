"""
目标架构分类工具
功能：分离特定目标架构（如Hexagon, ARM, MIPS）的参数，提取通用（Generic）参数。
"""
import os

def classify_by_target():
    base_dir = r'c:\Users\21101\Desktop\实验\llvm_dummy\classification'
    input_files = [
        os.path.join(base_dir, 'llvm_args_transform.txt'),
        os.path.join(base_dir, 'llvm_args_analysis.txt')
    ]
    
    args = []
    for input_file in input_files:
        if not os.path.exists(input_file):
            print(f"File not found: {input_file}")
            continue

        with open(input_file, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
            # Skip headers if present
            current_args = [l for l in lines if not l.startswith("LLVM") and not l.startswith("===")]
            args.extend(current_args)

    # Remove duplicates
    args = sorted(list(set(args)))

    # Target Keywords (Architecture prefixes often found in flags)
    targets = {
        'Hexagon': ['hexagon'],
        'ARM': ['arm', 'a15', 'a57', 'thumb'], # a15/a57 are specific ARM cores
        'MIPS': ['mips'],
        'NVPTX': ['nvptx'],
        'PowerPC': ['ppc', 'p10'], # p10 is Power10
        'BPF': ['bpf'],
        'WebAssembly': ['wasm'],
        'RISCV': ['riscv'],
        'AMDGPU': ['amdgpu', 'r600'],
        'SystemZ': ['systemz'],
        'X86': ['x86', 'sse', 'avx'], # We might want to KEEP these if on x86
    }

    # Categories
    generic_args = []
    target_args = {k: [] for k in targets.keys()}
    unknown_target_args = [] # For things that look target-specific but not in our list?

    for arg in args:
        lower_arg = arg.lower()
        matched = False
        
        for target_name, keywords in targets.items():
            for kw in keywords:
                # Check for -disable-arm- or just arm- inside
                # Heuristic: usually target is separated by dashes
                # e.g. -disable-arm-loloops
                if f"-{kw}-" in lower_arg or lower_arg.startswith(f"-{kw}") or f"_{kw}_" in lower_arg:
                    target_args[target_name].append(arg)
                    matched = True
                    break
            if matched:
                break
        
        if not matched:
            generic_args.append(arg)

    # Write output
    output_file = os.path.join(base_dir, 'llvm_args_by_target.txt')
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=== Generic (Architecture Independent) ===\n")
        for arg in sorted(generic_args):
            f.write(f"{arg}\n")
        
        f.write("\n")
        
        for target_name, t_args in target_args.items():
            if t_args:
                f.write(f"=== {target_name} Specific ===\n")
                for arg in sorted(t_args):
                    f.write(f"{arg}\n")
                f.write("\n")

    print(f"Classification Complete.")
    print(f"Generic: {len(generic_args)}")
    total_target = sum(len(v) for v in target_args.values())
    print(f"Target Specific: {total_target}")
    for k, v in target_args.items():
        if v:
            print(f"  - {k}: {len(v)}")
    print(f"Results written to {output_file}")

if __name__ == '__main__':
    classify_by_target()
