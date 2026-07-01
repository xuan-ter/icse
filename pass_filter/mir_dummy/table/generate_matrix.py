import os
import csv

# Define paths
base_dir = r"c:\Users\21101\Desktop\实验\mir_dummy"
input_file = os.path.join(base_dir, "classify", "mir_tunable_optimizations.txt")
output_dir = os.path.join(base_dir, "table")
output_csv = os.path.join(output_dir, "mir_experiment_matrix.csv")

def parse_tunable_passes(filepath):
    passes = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip headers and separators
            if not line or line.startswith("MIR") or line.startswith("===") or line.startswith("---") or line.startswith("Pass Name"):
                continue
            
            # Extract pass name (before the pipe)
            if "|" in line:
                pass_name = line.split("|")[0].strip()
                if pass_name:
                    passes.append(pass_name)
    return passes

def generate_matrix(passes):
    rows = []
    
    # 1. Baseline (Compiler Default)
    rows.append({
        "Experiment_ID": "EXP_000_DEFAULT",
        "Type": "Baseline",
        "Target_Pass": "N/A",
        "RUSTFLAGS": "",
        "Description": "Default compiler settings (control group)"
    })

    # Construct "All Enabled" string
    # Format: -Z mir-enable-passes=+Pass1,+Pass2,...
    all_on_flags = "-Z mir-enable-passes=" + ",".join([f"+{p}" for p in passes])
    
    # 2. All Tunable Passes ON
    rows.append({
        "Experiment_ID": "EXP_001_ALL_ON",
        "Type": "Global_Config",
        "Target_Pass": "All",
        "RUSTFLAGS": all_on_flags,
        "Description": "Force enable all 20 tunable optimizations"
    })

    # Construct "All Disabled" string
    all_off_flags = "-Z mir-enable-passes=" + ",".join([f"-{p}" for p in passes])
    
    # 3. All Tunable Passes OFF
    rows.append({
        "Experiment_ID": "EXP_002_ALL_OFF",
        "Type": "Global_Config",
        "Target_Pass": "All",
        "RUSTFLAGS": all_off_flags,
        "Description": "Force disable all 20 tunable optimizations"
    })

    # 4. Ablation Study (Leave-One-Out)
    # Start with ALL ON, turn ONE OFF
    for i, p in enumerate(passes):
        # List all + except current is -
        # logic: +P1, +P2, -Target, +P4...
        flags_list = []
        for other in passes:
            if other == p:
                flags_list.append(f"-{other}")
            else:
                flags_list.append(f"+{other}")
        
        flags = "-Z mir-enable-passes=" + ",".join(flags_list)
        
        rows.append({
            "Experiment_ID": f"EXP_ABL_{i+1:03d}_{p}",
            "Type": "Ablation (Leave-One-Out)",
            "Target_Pass": p,
            "RUSTFLAGS": flags,
            "Description": f"All ON except {p} is OFF"
        })

    # 5. Isolation Study (Add-One-In)
    # Start with ALL OFF, turn ONE ON
    for i, p in enumerate(passes):
        # List all - except current is +
        flags_list = []
        for other in passes:
            if other == p:
                flags_list.append(f"+{other}")
            else:
                flags_list.append(f"-{other}")
        
        flags = "-Z mir-enable-passes=" + ",".join(flags_list)
        
        rows.append({
            "Experiment_ID": f"EXP_ISO_{i+1:03d}_{p}",
            "Type": "Isolation (Add-One-In)",
            "Target_Pass": p,
            "RUSTFLAGS": flags,
            "Description": f"All OFF except {p} is ON"
        })

    return rows

def main():
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    print(f"Parsing passes from: {input_file}")
    passes = parse_tunable_passes(input_file)
    print(f"Found {len(passes)} tunable passes.")
    
    matrix = generate_matrix(passes)
    
    # Write to CSV
    headers = ["Experiment_ID", "Type", "Target_Pass", "RUSTFLAGS", "Description"]
    
    with open(output_csv, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(matrix)
        
    print(f"Experiment matrix generated at: {output_csv}")
    print(f"Total experiments defined: {len(matrix)}")

if __name__ == "__main__":
    main()
