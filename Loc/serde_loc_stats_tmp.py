from pathlib import Path
import sys

root = Path(r'd:\MIR_LLVM_NEW\serde')
excluded = {'target', 'results', '__pycache__', '.git', 'build', 'dist', 'out', 'node_modules', 'venv', '.venv'}
binary_ext = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp', '.ico', '.pdf', '.zip', '.gz', '.7z', '.rar', '.dll', '.exe', '.so', '.dylib', '.a', '.lib', '.o', '.obj', '.class', '.jar', '.wasm', '.bin', '.woff', '.woff2', '.ttf', '.otf', '.eot', '.mp4', '.mp3', '.wav', '.flac', '.svgz', '.psd'}

files = []
for p in root.rglob('*'):
    if p.is_file() and not any(part in excluded for part in p.relative_to(root).parts):
        files.append(p)

text_files = 0
loc = 0
for p in files:
    try:
        data = p.read_bytes()
    except Exception:
        continue
    if p.suffix.lower() in binary_ext:
        continue
    if b'\x00' in data[:8192]:
        continue
    text_files += 1
    if data:
        loc += data.count(b'\n') + (0 if data.endswith(b'\n') else 1)

print(f"serde,{len(files)},{text_files},{loc}", file=sys.stderr)
