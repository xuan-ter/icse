"""
LLVM参数快速验证器
功能：快速验证probed列表中的参数是否导致编译错误，生成有效参数白名单。
"""
import subprocess
import os
import sys

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    args_file = os.path.join(base_dir, "llvm_args_probed_supported.txt")
    test_file = os.path.join(base_dir, "test_llvm_switches.rs")
    
    # Ensure test file exists
    if not os.path.exists(test_file):
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("fn main() { println!(\"Hello LLVM\"); }")

    # Read args
    with open(args_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    # Skip header
    args = [line.strip() for line in lines[1:] if line.strip()]

    print(f"Testing {len(args)} LLVM args...")
    
    valid_args = []
    invalid_args = []

    for arg in args:
        # Try to use the arg using -C llvm-args=<arg>
        cmd = ["rustc", "+nightly", f"-C", f"llvm-args={arg}", test_file, "--crate-type", "bin", "-o", "test_llvm_dummy.exe"]
        
        try:
            # We need to capture stderr to check for warnings/errors
            # LLVM args often fail with "Unknown command line argument" or similar in stderr if invalid
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
            stderr = result.stderr
            stdout = result.stdout
            
            # Common failure patterns for LLVM args:
            # "Unknown command line argument"
            # "for the -... option: may only occur zero or one times!" (if we somehow duplicated it, but shouldn't happen here)
            # "clang: error: ..." (though we are running rustc)
            
            is_valid = True
            
            if result.returncode != 0:
                is_valid = False
                print(f"[ERROR]   {arg} (Compilation failed)")
                # print(stderr)
            elif "Unknown command line argument" in stderr or "not a valid option" in stderr:
                 is_valid = False
                 print(f"[INVALID] {arg} (Unknown/Invalid)")
            else:
                print(f"[VALID]   {arg}")
            
            if is_valid:
                valid_args.append(arg)
            else:
                invalid_args.append(arg)

        except Exception as e:
            print(f"[EXCEPTION] {arg}: {e}")
            invalid_args.append(arg)

    # Clean up
    if os.path.exists("test_llvm_dummy.exe"):
        os.remove("test_llvm_dummy.exe")
    if os.path.exists("test_llvm_dummy.pdb"):
        os.remove("test_llvm_dummy.pdb")

    # Report
    print("\n" + "="*40)
    print(f"Summary: {len(valid_args)} valid, {len(invalid_args)} invalid.")
    print("="*40)
    
    if invalid_args:
        print("\nInvalid Args:")
        for arg in invalid_args:
            print(f"  {arg}")

    # Write valid args to a new file
    output_file = os.path.join(base_dir, "llvm_args_valid_switches.txt")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("Valid LLVM args controllable via -C llvm-args\n")
        for arg in valid_args:
            f.write(f"{arg}\n")
    
    print(f"\nValid args written to: {output_file}")

if __name__ == "__main__":
    main()
