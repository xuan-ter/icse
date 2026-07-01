"""
Pass影响分类工具
功能：分析Pass对性能（Performance）和代码尺寸（Size）的潜在影响，生成分类列表。
"""
import os

def classify_llvm_impact():
    base_dir = r'c:\Users\21101\Desktop\实验\llvm_dummy\classification'
    input_file = os.path.join(base_dir, 'llvm_args_transform.txt')
    
    out_perf = os.path.join(base_dir, 'llvm_args_impact_performance.txt')
    out_size = os.path.join(base_dir, 'llvm_args_impact_size.txt')
    out_both = os.path.join(base_dir, 'llvm_args_impact_both.txt')

    with open(input_file, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
        if lines and "LLVM Transform Args" in lines[0]:
            args = lines[1:]
        else:
            args = lines

    # 1. Performance Keywords (Speed/Throughput)
    # Focus: Vectorization, Inlining, Scheduling, Loop Opts, Memcpy Opts
    perf_keywords = [
        'vector', 'slp', 'unroll', 'inline', 'licm', 'lsr', 'sched',
        'peephole', 'combine', 'cse', 'gvn', 'reassociate', 'sink',
        'hoist', 'promote', 'prefetch', 'fma', 'bypass', 'branch-fold',
        'ifcvt', 'tail-dup', 'jump-threading', 'placement', 'align',
        'memop', 'memcpy', 'memmove', 'store-forward', 'fusion', 'fusing'
    ]

    # 2. Size Keywords (Code Size/Cleanup)
    # Focus: DCE, Merging, Outlining, Stripping, Simplification
    size_keywords = [
        'dce', 'dead', 'strip', 'prune', 'merge', 'const-hoist',
        'global-opt', 'ipo', 'dedup', 'outline', 'tail-call',
        'opt-size', 'shrink', 'clean', 'elim', 'reduce', 'remove'
    ]

    # 3. Explicit Multi-Impact (Core)
    # Passes that are fundamental to both or trade-off heavily
    # e.g. Inlining (Perf++ Size--), but here we look for POSITIVE impact on both
    # OR fundamental transforms that enable everything else.
    # Note: 'disable-tail-calls' affects both (stack size vs jump).
    # 'peephole' is often small cleanup but good for perf.
    # 'cse' reduces calc (perf) and size.
    multi_impact_keywords = [
        'cse', 'gvn', 'peephole', 'combine', 'simplify', 'reassociate', 'dce'
    ]

    cat_perf = set()
    cat_size = set()

    for arg in args:
        lower_arg = arg.lower()
        
        # Check Perf
        if any(k in lower_arg for k in perf_keywords):
            cat_perf.add(arg)
            
        # Check Size
        if any(k in lower_arg for k in size_keywords):
            cat_size.add(arg)
            
        # Specific Heuristics for "disable-" flags
        # If it disables a loop optimization, it's definitely a Perf flag.
        if 'loop' in lower_arg or 'cycle' in lower_arg:
            cat_perf.add(arg)
            
        # Hexagon/PPC/MIPS specific machine opts are usually Perf
        if any(arch in lower_arg for arch in ['hexagon', 'ppc', 'mips', 'arm', 'x86', 'nvptx']):
            # Most backend flags are sched/peephole/packetizer -> Perf
            # Unless explicitly about size
            if 'size' not in lower_arg:
                cat_perf.add(arg)

    # Intersection for Both
    # But wait, keywords overlap. Let's refine.
    # We want "Both" to contain things that are good for BOTH speed and size.
    # Examples: DCE, CSE, Peephole, Merge.
    
    # Calculate initial intersection based on keywords
    cat_both = cat_perf.intersection(cat_size)
    
    # Force add explicit multi-impact ones if they are in args
    for arg in args:
        lower_arg = arg.lower()
        if any(k in lower_arg for k in multi_impact_keywords):
            if arg in cat_perf or arg in cat_size:
                cat_both.add(arg)

    # Clean up lists
    # Remove "Both" items from Only lists
    cat_perf_only = sorted(list(cat_perf - cat_both))
    cat_size_only = sorted(list(cat_size - cat_both))
    cat_both_final = sorted(list(cat_both))

    # Write outputs
    def write_list(filepath, name, data):
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"{name}\n")
            for item in data:
                f.write(f"{item}\n")
        print(f"Written {len(data)} items to {filepath}")

    write_list(out_perf, "LLVM Performance-Only Args", cat_perf_only)
    write_list(out_size, "LLVM Size-Only Args", cat_size_only)
    write_list(out_both, "LLVM Performance AND Size (Core) Args", cat_both_final)

if __name__ == '__main__':
    classify_llvm_impact()
