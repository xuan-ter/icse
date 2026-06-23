import csv
import math
import os
from collections import Counter


HYPER_EXPERIMENT_CSV = r"d:\MIR_LLVM_NEW\hyper\results\20260531_191832\experiment_results.csv"


def _to_float(value):
    if value is None:
        return math.nan
    s = str(value).strip()
    if not s:
        return math.nan
    try:
        return float(s)
    except ValueError:
        return math.nan


def _load_rows(csv_path):
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _clean_pass(value):
    s = str(value or "").strip()
    if not s or s.lower() in {"none", "baseline", "nan", "n/a"}:
        return "None"
    return s


def _fmt_row(row):
    return (
        f"ConfigName={row.get('ConfigName')}, "
        f"RunID={row.get('RunID')}, "
        f"LLVM_Pass={row.get('LLVM_Pass')}, "
        f"MIR_Pass={row.get('MIR_Pass')}, "
        f"TotalRuntime(s)={row.get('TotalRuntime(s)')}, "
        f"CompileTime(s)={row.get('CompileTime(s)')}, "
        f"BinarySize(Bytes)={row.get('BinarySize(Bytes)')}, "
        f"Status={row.get('Status')}"
    )


def main() -> int:
    csv_path = HYPER_EXPERIMENT_CSV
    if not os.path.exists(csv_path):
        raise SystemExit(f"CSV not found: {csv_path}")

    rows = _load_rows(csv_path)
    statuses = Counter(str(r.get("Status", "")).strip() or "<empty>" for r in rows)
    success_rows = [r for r in rows if str(r.get("Status", "")).strip().lower() == "success"]

    for r in success_rows:
        r["_runtime"] = _to_float(r.get("TotalRuntime(s)"))
        r["_compile"] = _to_float(r.get("CompileTime(s)"))
        r["_size"] = _to_float(r.get("BinarySize(Bytes)"))
        r["_mir"] = _clean_pass(r.get("MIR_Pass"))
        r["_llvm"] = _clean_pass(r.get("LLVM_Pass"))

    valid_runtime = [r for r in success_rows if r["_runtime"] == r["_runtime"] and r["_runtime"] > 0]
    valid_compile = [r for r in success_rows if r["_compile"] == r["_compile"] and r["_compile"] > 0]
    valid_size = [r for r in success_rows if r["_size"] == r["_size"] and r["_size"] > 0]

    baseline_rows = [r for r in success_rows if r["_mir"] == "None" and r["_llvm"] == "None"]
    fastest = min(valid_runtime, key=lambda r: r["_runtime"]) if valid_runtime else None
    shortest_compile = min(valid_compile, key=lambda r: r["_compile"]) if valid_compile else None
    smallest = min(valid_size, key=lambda r: r["_size"]) if valid_size else None

    print(f"CSV: {csv_path}")
    print(f"Rows total: {len(rows)}")
    print(f"Rows success: {len(success_rows)}")
    print(f"Configs total: {len({str(r.get('ConfigName', '')).strip() for r in rows if str(r.get('ConfigName', '')).strip()})}")
    print("")

    print("Status distribution:")
    for status, count in sorted(statuses.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"- {status}: {count}")
    print("")

    print(f"Baseline rows (MIR=None, LLVM=None): {len(baseline_rows)}")
    if baseline_rows:
        print(f"Baseline example: {_fmt_row(baseline_rows[0])}")
    print("")

    if fastest:
        print(f"Fastest row: {_fmt_row(fastest)}")
    if shortest_compile:
        print(f"Shortest compile row: {_fmt_row(shortest_compile)}")
    if smallest:
        print(f"Smallest binary row: {_fmt_row(smallest)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
