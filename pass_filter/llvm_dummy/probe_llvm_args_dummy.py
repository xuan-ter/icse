"""
LLVM参数探测工具
功能：通过编译dummy项目，探测并验证当前Rust工具链支持的LLVM隐藏参数。
"""
import os
import re
import subprocess
from pathlib import Path


def collect_help_text(project_dir: Path) -> str:
    env = os.environ.copy()
    env["RUSTFLAGS"] = "-C llvm-args=--help-hidden"
    result = subprocess.run(
        ["cargo", "+nightly", "build", "--release", "--quiet"],
        cwd=project_dir,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="ignore",
    )
    text = result.stdout or ""
    help_path = project_dir / "llvm-help.txt"
    help_path.write_text(text, encoding="utf-8")
    return text


def load_candidates_from_help(text: str) -> list[str]:
    pattern = re.compile(r"-(?:disable-[A-Za-z0-9\\-]+|vectorize-(?:loops|slp)=[A-Za-z0-9]+)")
    found = pattern.findall(text)
    return sorted(set(found))


def write_list(path: Path, header: str, items: list[str]) -> None:
    with path.open("w", encoding="utf-8") as f:
        if header:
            f.write(header + "\n")
        for it in items:
            f.write(it + "\n")


def main() -> None:
    project_dir = Path(__file__).resolve().parent
    help_text = collect_help_text(project_dir)
    candidates = load_candidates_from_help(help_text)
    if not candidates:
        raise SystemExit("no llvm-args candidates found from help-hidden output")
    supported: list[str] = []
    unsupported: list[str] = []
    for opt in candidates:
        env = os.environ.copy()
        env["RUSTFLAGS"] = f"-C opt-level=3 -C llvm-args={opt}"
        print(f"Probing {opt} ...", flush=True)
        result = subprocess.run(
            ["cargo", "+nightly", "build", "--release", "--quiet"],
            cwd=project_dir,
            env=env,
        )
        if result.returncode == 0:
            supported.append(opt)
        else:
            unsupported.append(opt)
    write_list(
        project_dir / "llvm_args_probed_supported.txt",
        "在 llvm_dummy 项目上可识别且编译通过的 llvm-args 禁用/参数项",
        supported,
    )
    write_list(
        project_dir / "llvm_args_probed_unsupported.txt",
        "在 llvm_dummy 项目上不识别或编译失败的 llvm-args 禁用/参数项",
        unsupported,
    )


if __name__ == "__main__":
    main()

