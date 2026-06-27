from pathlib import Path
import csv
import sys
import os


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
    "__pycache__",
    ".git",
    "build",
    "dist",
    "out",
    "node_modules",
    "venv",
    ".venv",
}

BINARY_EXTS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".bmp",
    ".ico",
    ".pdf",
    ".zip",
    ".gz",
    ".7z",
    ".rar",
    ".dll",
    ".exe",
    ".so",
    ".dylib",
    ".a",
    ".lib",
    ".o",
    ".obj",
    ".class",
    ".jar",
    ".wasm",
    ".bin",
    ".woff",
    ".woff2",
    ".ttf",
    ".otf",
    ".eot",
    ".mp4",
    ".mp3",
    ".wav",
    ".flac",
    ".svgz",
    ".psd",
}

OUTPUT_CSV = Path(os.environ.get("LOC_OUTPUT_CSV", r"d:\MIR_LLVM_NEW\loc_batch_stats_tmp.csv"))


def count_lines(data: bytes) -> int:
    if not data:
        return 0
    return data.count(b"\n") + (0 if data.endswith(b"\n") else 1)


def is_excluded(root: Path, path: Path) -> bool:
    return any(part in EXCLUDED_DIRS for part in path.relative_to(root).parts)


def is_probably_binary(data: bytes, suffix: str) -> bool:
    if suffix in BINARY_EXTS:
        return True
    return b"\x00" in data[:8192]


def summarize_project(root_str: str):
    root = Path(root_str)
    files = []
    for path in root.rglob("*"):
        if path.is_file() and not is_excluded(root, path):
            files.append(path)

    text_files = 0
    loc = 0
    for path in files:
        try:
            data = path.read_bytes()
        except Exception:
            continue
        if is_probably_binary(data, path.suffix.lower()):
            continue
        text_files += 1
        loc += count_lines(data)

    return {
        "project": root.name,
        "root": root_str,
        "files": len(files),
        "text_files": text_files,
        "loc": loc,
    }


def main():
    roots = sys.argv[1:] if len(sys.argv) > 1 else ROOTS
    rows = [summarize_project(root) for root in roots]
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["project", "root", "files", "text_files", "loc"])
        writer.writeheader()
        writer.writerows(rows)
    for row in rows:
        print(f"{row['project']},{row['files']},{row['text_files']},{row['loc']}")


if __name__ == "__main__":
    main()
