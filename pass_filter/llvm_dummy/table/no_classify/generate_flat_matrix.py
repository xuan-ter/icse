import os
import csv

# Define paths
base_dir = r"c:\Users\21101\Desktop\实验\llvm_dummy"
input_file = os.path.join(base_dir, "classification", "llvm_args_categorized_7_classes.txt")
output_dir = os.path.join(base_dir, "table", "no_classify")
output_csv = os.path.join(output_dir, "llvm_experiment_matrix_flat.csv")

def parse_llvm_args(filepath):
    """
    Parses the categorized LLVM args file but treats it as a flat list,
    ignoring the category headers for the 'no_classify' requirement.
    """
    args = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and headers
            if not line or line.startswith("==="):
                continue
            
            # Remove the leading hyphen if present in the stored format, 
            # but usually they are stored as "-disable-foo" or "disable-foo".
            # The input file shows they start with "-disable-..."
            # We keep them as-is for the parameter name.
            if line.startswith("-disable-"):
                args.append(line)
    return args

def generate_matrix(args):
    rows = []
    
    # 1. Baseline (Compiler Default)
    # Default means these "disable" flags are NOT passed (so the optimizations run)
    rows.append({
        "Experiment_ID": "EXP_000_DEFAULT",
        "Type": "Baseline",
        "Target_Arg": "N/A",
        "RUSTFLAGS": "",
        "Description": "Default compiler settings (Optimizations Enabled)"
    })

    # 2. All Disabled (Turn OFF all optimizations)
    # Since the flags are "disable-xxx", passing ALL of them means disabling ALL optimizations.
    # Format: -C llvm-args=-disable-foo -C llvm-args=-disable-bar ...
    # Or compact: -C llvm-args=-disable-foo ...
    
    # Note: RUSTFLAGS usually handles space-separated args.
    # We will construct a string like: "-C llvm-args=-disable-a -C llvm-args=-disable-b"
    # This can be very long. Rustc accepts multiple llvm-args.
    
    all_disable_flags = " ".join([f"-C llvm-args={arg}" for arg in args])
    
    rows.append({
        "Experiment_ID": "EXP_001_DISABLE_ALL",
        "Type": "Global_Config",
        "Target_Arg": "All",
        "RUSTFLAGS": all_disable_flags,
        "Description": "Force DISABLE all 83 optimizations"
    })

    # 3. Single Disable (Ablation Study)
    # Default is ON. We pass ONE "-disable-foo" flag to turn THAT optimization OFF.
    for i, arg in enumerate(args):
        # Clean arg name for ID (remove leading -)
        clean_name = arg.lstrip('-')
        
        flags = f"-C llvm-args={arg}"
        
        rows.append({
            "Experiment_ID": f"EXP_ABL_{i+1:03d}_{clean_name}",
            "Type": "Ablation (Single Disable)",
            "Target_Arg": arg,
            "RUSTFLAGS": flags,
            "Description": f"Default settings but DISABLE {arg}"
        })

    return rows

def main():
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    print(f"Parsing args from: {input_file}")
    args = parse_llvm_args(input_file)
    print(f"Found {len(args)} LLVM arguments.")
    
    matrix = generate_matrix(args)
    
    # Write to CSV
    headers = ["Experiment_ID", "Type", "Target_Arg", "RUSTFLAGS", "Description"]
    
    with open(output_csv, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(matrix)
        
    print(f"Experiment matrix generated at: {output_csv}")
    print(f"Total experiments defined: {len(matrix)}")

if __name__ == "__main__":
    main()
