from pathlib import Path
import sys


ROOTS = [
    r"d:\MIR_LLVM_NEW\aggregate_scalarization_bench",
    r"d:\MIR_LLVM_NEW\aho-corasick",
    r"d:\MIR_LLVM_NEW\async_state_machine_bench",
    r"d:\MIR_LLVM_NEW\bat",
    r"d:\MIR_LLVM_NEW\branch_cfg_bench",
    r"d:\MIR_LLVM_NEW\eza",
    r"d:\MIR_LLVM_NEW\fast_image_resize",
    r"d:\MIR_LLVM_NEW\hyper",
    r"d:\MIR_LLVM_NEW\image",
    r"d:\MIR_LLVM_NEW\iterator_pipeline_bench",
    r"d:\MIR_LLVM_NEW\loop_hoisting_bench",
    r"d:\MIR_LLVM_NEW\quinn",
    r"d:\MIR_LLVM_NEW\regex",
    r"d:\MIR_LLVM_NEW\ripgrep",
    r"d:\MIR_LLVM_NEW\rustls",
    r"d:\MIR_LLVM_NEW\serde",
    r"d:\MIR_LLVM_NEW\tokio",
    r"d:\MIR_LLVM_NEW\trait_test",
]

EXCLUDED_DIRS = {
    "target",
    "results",
    "results_expanded",
    "results_baseline_opt3",
    "__pycache__",
    ".git",
    "build",
    "dist",
    "out",
    "node_modules",
    "venv",
    ".venv",
    "analysis",
    "analysis_new",
    "docs",
    "doc",
    "data",
    "assets",
    "fuzz",
    "benches",
    "benchmarks",
    "benchmark",
    "tests",
    "examples",
    "perf",
    "book",
}


def should_skip(path: Path, root: Path) -> bool:
    try:
        rel = path.relative_to(root)
    except ValueError:
        return True
    return any(part in EXCLUDED_DIRS for part in rel.parts)


def count_lines(data: bytes) -> int:
    if not data:
        return 0
    return data.count(b"\n") + (0 if data.endswith(b"\n") else 1)


def collect_rust_files(root: Path) -> list[Path]:
    rust_files: set[Path] = set()
    for cargo_toml in root.rglob("Cargo.toml"):
        if should_skip(cargo_toml, root):
            continue
        crate_dir = cargo_toml.parent
        src_dir = crate_dir / "src"
        if src_dir.is_dir():
            for rs_file in src_dir.rglob("*.rs"):
                rust_files.add(rs_file)
        build_rs = crate_dir / "build.rs"
        if build_rs.is_file():
            rust_files.add(build_rs)
    return sorted(rust_files)


def summarize_project(root_str: str) -> dict[str, int | str]:
    root = Path(root_str)
    rust_files = collect_rust_files(root)
    loc = 0
    for path in rust_files:
        try:
            loc += count_lines(path.read_bytes())
        except Exception:
            continue
    return {
        "project": root.name,
        "rust_files": len(rust_files),
        "loc": loc,
    }


def main() -> None:
    roots = sys.argv[1:] if len(sys.argv) > 1 else ROOTS
    for root in roots:
        row = summarize_project(root)
        print(f"{row['project']},{row['rust_files']},{row['loc']}")


if __name__ == "__main__":
    main()
