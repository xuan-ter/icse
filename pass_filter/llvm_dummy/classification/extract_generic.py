"""
通用参数提取工具
功能：从 llvm_args_transform.txt 中提取 Generic 部分的参数，过滤掉特定架构的参数。
"""
import os

def extract_generic():
    base_dir = r'c:\Users\21101\Desktop\实验\llvm_dummy\classification'
    input_file = os.path.join(base_dir, 'llvm_args_transform.txt')
    output_file = os.path.join(base_dir, 'llvm_args_generic_only.txt')
    target_output_file = os.path.join(base_dir, 'llvm_args_target_specific.txt')
    
    if not os.path.exists(input_file):
        print(f"Input file not found: {input_file}")
        return

    # Define keywords to filter out architecture-specific parameters
    targets = {
        'Hexagon': ['hexagon', 'hcp', 'hsdr', 'packetizer', 'disable-mask', 'load-widen', 'store-widen', 'memcpy-idiom', 'memmove-idiom', 'const64', 'merge-into-combines'],
        'ARM': ['arm', 'a15', 'a57', 'thumb', 'shifter-op'],
        'MIPS': ['mips'],
        'NVPTX': ['nvptx', 'nv', 'nvjump', 'require-structured-cfg'],
        'PowerPC': ['ppc', 'p10', 'auto-paired-vec-st'],
        'BPF': ['bpf', 'bswap', 'gotol', 'sdiv-smod', 'storeimm'],
        'WebAssembly': ['wasm'],
        'RISCV': ['riscv'],
        'AMDGPU': ['amdgpu', 'r600', 'lds', 'ldsx'],
        'SystemZ': ['systemz'],
        'X86': ['x86', 'sse', 'avx', 'movsx'],
        'Sparc': ['sparc'],
        'Darwin': ['atexit-based-global-dtor-lowering']
    }

    generic_args = []
    target_specific_args = []
    
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
        
    for line in lines:
        # Skip headers
        if line.startswith("LLVM") or line.startswith("==="):
            continue
            
        lower_arg = line.lower()
        is_target = False
        
        for target_name, keywords in targets.items():
            for kw in keywords:
                # Check for -disable-arm- or just arm- inside or prefix
                # We want to match whole words roughly to avoid false positives
                # Patterns:
                # 1. -kw- (middle) e.g. -vecdbl-nv-stores
                # 2. -kw (start) e.g. -hexagon-...
                # 3. _kw_ (underscore separator)
                # 4. -kw (end) e.g. -promote-alloca-to-lds
                
                if (f"-{kw}-" in lower_arg or 
                    lower_arg.startswith(f"-{kw}") or 
                    f"_{kw}_" in lower_arg or 
                    lower_arg.endswith(f"-{kw}")):
                    is_target = True
                    break
            if is_target:
                break
        
        if not is_target:
            generic_args.append(line)
        else:
            target_specific_args.append(line)
    
    # Sort for consistency
    generic_args.sort()
    target_specific_args.sort()

    with open(output_file, 'w', encoding='utf-8') as f:
        for arg in generic_args:
            f.write(f"{arg}\n")

    with open(target_output_file, 'w', encoding='utf-8') as f:
        for arg in target_specific_args:
            f.write(f"{arg}\n")
            
    print(f"Processed {len(lines)} lines from {input_file}.")
    print(f"Extracted {len(generic_args)} generic arguments to {output_file}")
    print(f"Extracted {len(target_specific_args)} target-specific arguments to {target_output_file}")

if __name__ == '__main__':
    extract_generic()
