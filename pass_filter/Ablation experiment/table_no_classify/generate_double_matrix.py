import os
import csv

# Input file paths
LLVM_FILE = r"c:\Users\21101\Desktop\实验\llvm_dummy\classification\llvm_args_categorized_7_classes.txt"
MIR_FILE = r"c:\Users\21101\Desktop\实验\mir_dummy\classify\mir_tunable_optimizations.txt"
OUTPUT_DIR = r"c:\Users\21101\Desktop\实验\Ablation experiment\table_no_classify"
OUTPUT_CSV = os.path.join(OUTPUT_DIR, "mir_llvm_double_disable_matrix.csv")

def parse_llvm_args(filepath):
    args = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line.startswith('-disable-'):
                args.append(line)
    return args

def parse_mir_passes(filepath):
    passes = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            if '| Tunable Optimization' in line:
                # Format: "PassName   | Tunable Optimization"
                pass_name = line.split('|')[0].strip()
                if pass_name and pass_name != "Pass Name":
                    passes.append(pass_name)
    return passes

def main():
    # Ensure output directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # 1. Parse Inputs
    llvm_args = parse_llvm_args(LLVM_FILE)
    mir_passes = parse_mir_passes(MIR_FILE)

    print(f"Found {len(llvm_args)} LLVM args.")
    print(f"Found {len(mir_passes)} MIR passes.")

    # 2. Generate Matrix
    # We want to disable 1 LLVM arg AND 1 MIR pass.
    # Total combinations = len(llvm_args) * len(mir_passes)
    
    headers = ["Experiment_ID", "Type", "LLVM_Arg", "MIR_Pass", "RUSTFLAGS", "Description"]
    rows = []

    # Optional: Add a Baseline (both enabled) and Single Disables?
    # User asked for "Double-disable matrix", implies the combinations.
    # But usually a matrix includes the axes. 
    # I'll stick to the core request: Double-disable. 
    # But I will add a Baseline at the top for convenience.
    
    # Baseline
    rows.append({
        "Experiment_ID": "EXP_DBL_000_BASELINE",
        "Type": "Baseline",
        "LLVM_Arg": "None",
        "MIR_Pass": "None",
        "RUSTFLAGS": "",
        "Description": "Default settings (All Enabled)"
    })

    count = 1
    for mir in mir_passes:
        for llvm in llvm_args:
            # Construct RUSTFLAGS
            # Note: We assume the user environment handles the base mir-opt-level if needed.
            # We strictly provide the disable switches.
            flags = f"-C llvm-args={llvm} -Z mir-enable-passes=-{mir}"
            
            exp_id = f"EXP_DBL_{count:04d}"
            rows.append({
                "Experiment_ID": exp_id,
                "Type": "Double_Disable",
                "LLVM_Arg": llvm,
                "MIR_Pass": mir,
                "RUSTFLAGS": flags,
                "Description": f"Disable LLVM {llvm} AND MIR {mir}"
            })
            count += 1

    # 3. Write CSV
    with open(OUTPUT_CSV, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generated {len(rows)} experiments (1 Baseline + {len(rows)-1} Double Disables).")
    print(f"Output saved to: {OUTPUT_CSV}")

if __name__ == "__main__":
    main()
