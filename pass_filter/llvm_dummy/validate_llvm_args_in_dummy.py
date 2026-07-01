"""
LLVM参数验证工具
功能：在Dummy项目中批量验证LLVM参数的有效性，分类为支持/不支持列表。
"""
import os
import subprocess
import sys
from pathlib import Path


def load_list(path: Path) -> list[str]:
    items: list[str] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            if s.startswith("当前 "):
                continue
            items.append(s)
    return items


def validate_supported(dummy_dir: Path, configs_dir: Path) -> None:
    src_path = configs_dir / "llvm_args_probed_supported.txt"
    if not src_path.exists():
        raise SystemExit(f"supported list not found: {src_path}")
    options = load_list(src_path)
    if not options:
        raise SystemExit("no supported llvm-args options loaded")
    succeeded: list[str] = []
    failed: list[str] = []
    for opt in options:
        env = os.environ.copy()
        env["RUSTFLAGS"] = f"-C opt-level=3 -C llvm-args={opt}"
        print(f"Checking {opt} ...", flush=True)
        result = subprocess.run(
            ["cargo", "+nightly", "build", "--release", "--quiet"],
            cwd=dummy_dir,
            env=env,
        )
        if result.returncode == 0:
            succeeded.append(opt)
        else:
            failed.append(opt)
    out_path = dummy_dir / "llvm_args_supported_validation.txt"
    with out_path.open("w", encoding="utf-8") as f:
        f.write("使用 llvm_dummy 项目验证 configs/llvm_args_probed_supported.txt 中条目\n")
        f.write(f"总数: {len(options)}, 成功: {len(succeeded)}, 失败: {len(failed)}\n")
        if failed:
            f.write("失败选项:\n")
            for opt in failed:
                f.write(opt + "\n")
        else:
            f.write("所有选项在 dummy 项目下均编译通过\n")
    print(f"Done. Result written to {out_path}")


def validate_unsupported(dummy_dir: Path, configs_dir: Path) -> None:
    src_path = configs_dir / "llvm_args_probed_unsupported.txt"
    if not src_path.exists():
        raise SystemExit(f"unsupported list not found: {src_path}")
    options = load_list(src_path)
    if not options:
        raise SystemExit("no unsupported llvm-args options loaded")
    succeeded: list[str] = []
    failed: list[str] = []
    for opt in options:
        env = os.environ.copy()
        env["RUSTFLAGS"] = f"-C opt-level=3 -C llvm-args={opt}"
        print(f"Checking {opt} ...", flush=True)
        result = subprocess.run(
            ["cargo", "+nightly", "build", "--release", "--quiet"],
            cwd=dummy_dir,
            env=env,
        )
        if result.returncode == 0:
            succeeded.append(opt)
        else:
            failed.append(opt)
    out_path = dummy_dir / "llvm_args_unsupported_validation.txt"
    with out_path.open("w", encoding="utf-8") as f:
        f.write("使用 llvm_dummy 项目验证 configs/llvm_args_probed_unsupported.txt 中条目\n")
        f.write(f"总数: {len(options)}, 仍失败: {len(failed)}, 意外成功: {len(succeeded)}\n")
        if failed:
            f.write("仍然失败的选项:\n")
            for opt in failed:
                f.write(opt + "\n")
        if succeeded:
            f.write("在 dummy 项目下意外成功的选项:\n")
            for opt in succeeded:
                f.write(opt + "\n")
    print(f"Done. Result written to {out_path}")


def main() -> None:
    dummy_dir = Path(__file__).resolve().parent
    root_dir = dummy_dir.parent
    configs_dir = root_dir / "configs"
    mode = "supported"
    if len(sys.argv) > 1:
        mode = sys.argv[1]
    if mode == "supported":
        validate_supported(dummy_dir, configs_dir)
    elif mode == "unsupported":
        validate_unsupported(dummy_dir, configs_dir)
    else:
        raise SystemExit(f"unknown mode: {mode}")


if __name__ == "__main__":
    main()
