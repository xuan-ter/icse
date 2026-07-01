import os
import re
import subprocess
from pathlib import Path


def run_dump_mir(project_dir: Path) -> Path:
    dump_dir = project_dir / "mir_dump_dummy"
    if dump_dir.exists():
        for path in dump_dir.glob("*.mir"):
            if path.is_file():
                path.unlink()
    else:
        dump_dir.mkdir()
    env = os.environ.copy()
    env["RUSTFLAGS"] = "-Z dump-mir=main -Z mir-opt-level=3 -Z dump-mir-dir=mir_dump_dummy"
    result = subprocess.run(
        ["cargo", "+nightly", "build", "--release", "--quiet"],
        cwd=project_dir,
        env=env,
    )
    if result.returncode != 0:
        raise SystemExit(f"dump-mir build failed with code {result.returncode}")
    return dump_dir


def extract_passes(dump_dir: Path) -> list[str]:
    names: set[str] = set()
    pattern = re.compile(r"\b(before|after)\s+([A-Za-z0-9_-]+)")
    for path in dump_dir.glob("*.mir"):
        if not path.is_file():
            continue
        with path.open(encoding="utf-8") as f:
            first = f.readline().strip()
        m = pattern.search(first)
        if m:
            names.add(m.group(2))
    return sorted(names)


def write_pass_list(project_dir: Path, passes: list[str]) -> None:
    out_path = project_dir / "mir_passes_dumped.txt"
    with out_path.open("w", encoding="utf-8") as f:
        f.write("从 mir_dummy 使用 -Z dump-mir=main 提取的 MIR pass 名称（按字典序去重）\n")
        for name in passes:
            f.write(name + "\n")


def main() -> None:
    project_dir = Path(__file__).resolve().parent
    dump_dir = project_dir / "mir_dump_dummy"
    if not dump_dir.is_dir():
        raise SystemExit("dump directory 'mir_dump_dummy' does not exist; run cargo with -Z dump-mir first")
    passes = extract_passes(dump_dir)
    if not passes:
        raise SystemExit("no MIR passes extracted from dump directory")
    write_pass_list(project_dir, passes)


if __name__ == "__main__":
    main()
