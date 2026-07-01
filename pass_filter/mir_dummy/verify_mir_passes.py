import subprocess
import os
import sys

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    passes_file = os.path.join(base_dir, "mir_passes_dumped.txt")
    test_file = os.path.join(base_dir, "test_mir_switches.rs")
    
    # Ensure test file exists
    if not os.path.exists(test_file):
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("fn main() { println!(\"Hello\"); }")

    # Read passes
    with open(passes_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    # Skip header
    passes = [line.strip() for line in lines[1:] if line.strip()]

    print(f"Testing {len(passes)} MIR passes...")
    
    valid_passes = []
    invalid_passes = []

    for p in passes:
        # Try to disable the pass using -Z mir-enable-passes=-<pass>
        # If the pass is unknown, rustc emits a warning: "warning: MIR pass `...` is unknown and will be ignored"
        cmd = ["rustc", "+nightly", f"-Z", f"mir-enable-passes=-{p}", test_file, "--crate-type", "bin", "-o", "test_dummy.exe"]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
            stderr = result.stderr
            
            if f"MIR pass `{p}` is unknown" in stderr:
                print(f"[INVALID] {p}")
                invalid_passes.append(p)
            else:
                # Also check if command succeeded
                if result.returncode == 0:
                    print(f"[VALID]   {p}")
                    valid_passes.append(p)
                else:
                    print(f"[ERROR]   {p} (Compilation failed)")
                    # Treat compilation failure as invalid for safety, or print stderr
                    print(stderr)
                    invalid_passes.append(p)

        except Exception as e:
            print(f"[EXCEPTION] {p}: {e}")

    # Clean up
    if os.path.exists("test_dummy.exe"):
        os.remove("test_dummy.exe")
    if os.path.exists("test_dummy.pdb"):
        os.remove("test_dummy.pdb")

    # Report
    print("\n" + "="*40)
    print(f"Summary: {len(valid_passes)} valid, {len(invalid_passes)} invalid.")
    print("="*40)
    
    print("\nInvalid Passes (Cannot be controlled via -Z mir-enable-passes):")
    for p in invalid_passes:
        print(f"  {p}")

    # Write valid passes to a new file
    output_file = os.path.join(base_dir, "mir_passes_valid_switches.txt")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("Valid MIR passes controllable via -Z mir-enable-passes\n")
        for p in valid_passes:
            f.write(f"{p}\n")
    
    print(f"\nValid passes written to: {output_file}")

if __name__ == "__main__":
    main()
