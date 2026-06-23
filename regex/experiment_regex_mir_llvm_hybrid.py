import argparse
import csv
import glob
import json
import os
import re
import shutil
import subprocess
import time
from collections import defaultdict
from datetime import datetime
from math import ceil
from statistics import mean, median


PROJECT_ROOT = "/root/MIR_LLVM/regex"
BINARY_PATH = os.path.join(PROJECT_ROOT, "target", "release", "regex-cli")
DEFAULT_JSON_PATH = "/root/MIR_LLVM/table/table_json/combined_experiment_matrix.json"
DEFAULT_RESULTS_ROOT = "/root/MIR_LLVM/regex/results"
BENCH_VARIANT = "regex-cli"


def ensure_bench_file(project_root):
    bench_path = os.path.join(project_root, "benchmark_data.txt")
    desired_bytes = 500 * 1024 * 1024
    if os.path.exists(bench_path):
        try:
            size = os.path.getsize(bench_path)
        except Exception:
            size = 0
        if size >= desired_bytes and size < desired_bytes * 1.5:
            return bench_path
        try:
            os.remove(bench_path)
        except Exception:
            pass

    chunk = (
        "Sherlock Holmes took his bottle from the corner of the mantelpiece, "
        "and his hypodermic syringe from its neat morocco case. "
        "Contact us at support@example.com or visit 192.168.1.1 on 2023-10-27.\n"
    ) * 500
    chunk_bytes = len(chunk.encode("utf-8"))
    chunks_needed = (desired_bytes // chunk_bytes) + 1

    print(f"Generating benchmark file at {bench_path} (~{desired_bytes / 1024 / 1024:.0f}MB)...")
    with open(bench_path, "w", encoding="utf-8") as f:
        for _ in range(chunks_needed):
            f.write(chunk)
    return bench_path


def get_combinations(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("combinations", [])


def find_start_index_by_name(combos, start_name):
    if not start_name:
        return None
    if start_name.upper() in {"BEGIN", "START", "ALL"}:
        return None
    for i, combo in enumerate(combos):
        name = combo.get("name") or combo.get("Experiment_ID")
        if name == start_name:
            return i
    return None


def labels_from_combo(combo):
    mir_pass = "N/A"
    if combo.get("mir"):
        if isinstance(combo["mir"], dict):
            mir_pass = combo["mir"].get("pass", "N/A")
        else:
            mir_pass = str(combo["mir"])

    llvm_pass = "None"
    if combo.get("llvm"):
        if isinstance(combo["llvm"], dict):
            llvm_pass = combo["llvm"].get("pass", "None")
        else:
            llvm_pass = str(combo["llvm"])

    return llvm_pass, mir_pass


def clean_project(env):
    target_dir = os.path.join(PROJECT_ROOT, "target")
    if os.path.exists(target_dir):
        try:
            shutil.rmtree(target_dir)
        except Exception:
            subprocess.run(
                ["cargo", "clean"],
                cwd=PROJECT_ROOT,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    else:
        subprocess.run(
            ["cargo", "clean"],
            cwd=PROJECT_ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    time.sleep(0.25)


def compose_rustflags_from_combo(combo):
    parts = ["-C opt-level=3"]
    if combo.get("mir") and isinstance(combo["mir"], dict) and combo["mir"].get("switches"):
        switches = ",".join(combo["mir"]["switches"])
        parts.append(f"-Z mir-enable-passes={switches}")
    if combo.get("llvm") and isinstance(combo["llvm"], dict) and combo["llvm"].get("switches"):
        for switch in combo["llvm"]["switches"]:
            parts.append(f"-C llvm-args={switch}")
    if combo.get("RUSTFLAGS"):
        parts.append(str(combo["RUSTFLAGS"]))
    parts.append("-C codegen-units=1")
    parts.append("--emit=llvm-ir,link")
    return " ".join(parts)


def build_project(env, rustflags, logf, retries=2):
    env2 = dict(env)
    env2["RUSTFLAGS"] = rustflags
    env2["CARGO_INCREMENTAL"] = "0"

    backoff = 0.5
    last_err = ""
    t0 = time.perf_counter()
    for _ in range(retries + 1):
        r = subprocess.run(
            ["cargo", "+nightly", "build", "--release", "--package", "regex-cli", "--bin", "regex-cli", "--quiet"],
            cwd=PROJECT_ROOT,
            env=env2,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if r.returncode == 0:
            t1 = time.perf_counter()
            return True, (t1 - t0), env2, "Success"
        err = r.stderr or ""
        last_err = err
        if logf is not None:
            logf.write(err + "\n")
            logf.flush()
        if ("Text file busy (os error 26)" in err) or ("never executed" in err):
            time.sleep(backoff)
            backoff = min(backoff * 2, 4.0)
            continue
        t1 = time.perf_counter()
        return False, (t1 - t0), env2, "BuildFailed"

    t1 = time.perf_counter()
    if ("Text file busy (os error 26)" in last_err) or ("never executed" in last_err) or (
        "failed to run custom build command" in last_err
    ):
        return False, (t1 - t0), env2, "Skipped"
    return False, (t1 - t0), env2, "BuildFailed"


def newest_llvm_ir_path():
    patterns = [
        os.path.join(PROJECT_ROOT, "target", "release", "deps", "regex_cli-*.ll"),
        os.path.join(PROJECT_ROOT, "target", "release", "deps", "regex-*.ll"),
    ]
    cand = []
    for pattern in patterns:
        cand.extend(glob.glob(pattern))
    if not cand:
        return ""
    cand = sorted(set(cand), key=lambda p: os.path.getmtime(p), reverse=True)
    return cand[0]


def count_llvm_ir_metrics(ll_path):
    metrics = {
        "IR_alloca": 0,
        "IR_load": 0,
        "IR_store": 0,
        "IR_gep": 0,
        "IR_phi": 0,
        "IR_bb": 0,
    }
    if not ll_path or not os.path.exists(ll_path):
        return metrics
    with open(ll_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            if " alloca " in line:
                metrics["IR_alloca"] += 1
            if re.search(r"\bload\b", line):
                metrics["IR_load"] += 1
            if re.search(r"\bstore\b", line):
                metrics["IR_store"] += 1
            if "getelementptr" in line:
                metrics["IR_gep"] += 1
            if re.search(r"\bphi\b", line):
                metrics["IR_phi"] += 1
            if s.endswith(":") and not s.startswith(";") and "!" not in s:
                metrics["IR_bb"] += 1
    return metrics


def get_exe_path():
    return BINARY_PATH if os.path.exists(BINARY_PATH) else None


def run_benchmark_once(exe_path, bench_file):
    t0 = time.perf_counter()
    p = subprocess.run(
        [exe_path, "find", "match", "regex", "--no-utf8-syntax", "-p", "Sherlock", bench_file],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    t1 = time.perf_counter()
    if p.returncode != 0:
        return None, (p.stderr[:2000] if p.stderr else "RunFailed")
    return (t1 - t0), ""


def run_benchmark_repeated(exe_path, bench_file, repeats):
    repeats = int(repeats) if repeats is not None else 1
    repeats = max(1, repeats)
    total = 0.0
    for _ in range(repeats):
        t, err = run_benchmark_once(exe_path, bench_file)
        if t is None:
            return None, err
        total += t
    return total, ""


def pick_baseline_combo(combos):
    for c in combos:
        name = c.get("name") or c.get("Experiment_ID") or ""
        if name == "EXP_DBL_000_BASELINE":
            return c
    for c in combos:
        name = c.get("name") or c.get("Experiment_ID") or ""
        if name == "EXP_000_ALL_OFF":
            return c
    return combos[0] if combos else None


def calibrate_repeats(env_base, baseline_combo, bench_file, target_seconds, max_repeats, skip_clean, logf):
    if not baseline_combo:
        return 1
    if target_seconds is None or float(target_seconds) <= 0:
        return 1

    rustflags = compose_rustflags_from_combo(baseline_combo)
    if not skip_clean:
        clean_project(env_base)
    ok, _, _, status = build_project(env_base, rustflags, logf)
    if not ok:
        if logf is not None:
            logf.write(f"[Calibrate] baseline build failed with status={status}\n")
            logf.flush()
        return 1

    exe_path = get_exe_path()
    if not exe_path:
        return 1

    t, _ = run_benchmark_once(exe_path, bench_file)
    if t is None or t <= 0:
        return 1
    repeats = int(ceil(float(target_seconds) / float(t)))
    return max(1, min(int(max_repeats), repeats))


def aggregate_summary(rows):
    by = defaultdict(list)
    for r in rows:
        key = (r["Variant"], r["ConfigName"])
        if r["Status"] != "Success":
            continue
        by[key].append(r)

    out = []
    for (variant, cfg), rs in sorted(by.items()):
        def values(k, cast=float):
            xs = []
            for r in rs:
                try:
                    xs.append(cast(r[k]))
                except Exception:
                    pass
            return sorted(xs)

        def meds(k, cast=float):
            xs = values(k, cast)
            return median(xs) if xs else None

        def avgs(k, cast=float):
            xs = values(k, cast)
            return mean(xs) if xs else None

        def percentile(xs, p):
            if not xs:
                return None
            if len(xs) == 1:
                return float(xs[0])
            pos = (len(xs) - 1) * p
            lo = int(pos)
            hi = min(lo + 1, len(xs) - 1)
            frac = pos - lo
            return float(xs[lo]) * (1.0 - frac) + float(xs[hi]) * frac

        def iqr(k, cast=float):
            xs = values(k, cast)
            if not xs:
                return None
            q1 = percentile(xs, 0.25)
            q3 = percentile(xs, 0.75)
            if q1 is None or q3 is None:
                return None
            return q3 - q1

        out.append(
            {
                "Variant": variant,
                "ConfigName": cfg,
                "n": str(len(rs)),
                "runtime_mean": f"{avgs('TotalRuntime(s)'):.6f}" if avgs("TotalRuntime(s)") is not None else "",
                "runtime_med": f"{meds('TotalRuntime(s)'):.6f}" if meds("TotalRuntime(s)") is not None else "",
                "runtime_iqr": f"{iqr('TotalRuntime(s)'):.6f}" if iqr("TotalRuntime(s)") is not None else "",
                "compile_mean": f"{avgs('CompileTime(s)'):.6f}" if avgs("CompileTime(s)") is not None else "",
                "compile_med": f"{meds('CompileTime(s)'):.6f}" if meds("CompileTime(s)") is not None else "",
                "compile_iqr": f"{iqr('CompileTime(s)'):.6f}" if iqr("CompileTime(s)") is not None else "",
                "size_mean": f"{avgs('BinarySize(Bytes)', int):.6f}" if avgs("BinarySize(Bytes)", int) is not None else "",
                "size_med": f"{meds('BinarySize(Bytes)', int):.0f}" if meds("BinarySize(Bytes)", int) is not None else "",
                "alloca_mean": f"{avgs('IR_alloca', int):.6f}" if avgs("IR_alloca", int) is not None else "",
                "alloca_med": f"{meds('IR_alloca', int):.0f}" if meds("IR_alloca", int) is not None else "",
                "load_mean": f"{avgs('IR_load', int):.6f}" if avgs("IR_load", int) is not None else "",
                "load_med": f"{meds('IR_load', int):.0f}" if meds("IR_load", int) is not None else "",
                "store_mean": f"{avgs('IR_store', int):.6f}" if avgs("IR_store", int) is not None else "",
                "store_med": f"{meds('IR_store', int):.0f}" if meds("IR_store", int) is not None else "",
                "gep_mean": f"{avgs('IR_gep', int):.6f}" if avgs("IR_gep", int) is not None else "",
                "gep_med": f"{meds('IR_gep', int):.0f}" if meds("IR_gep", int) is not None else "",
                "phi_mean": f"{avgs('IR_phi', int):.6f}" if avgs("IR_phi", int) is not None else "",
                "phi_med": f"{meds('IR_phi', int):.0f}" if meds("IR_phi", int) is not None else "",
                "bb_mean": f"{avgs('IR_bb', int):.6f}" if avgs("IR_bb", int) is not None else "",
                "bb_med": f"{meds('IR_bb', int):.0f}" if meds("IR_bb", int) is not None else "",
            }
        )
    return out


def compute_interaction(summary_rows, metric_key, smaller_is_better=True):
    idx = {(r["Variant"], r["ConfigName"]): r for r in summary_rows}
    out = []
    for variant in sorted({r["Variant"] for r in summary_rows}):
        def get(cfg):
            row = idx.get((variant, cfg))
            if not row:
                return None
            value = row.get(metric_key, "")
            if value == "":
                return None
            try:
                return float(value)
            except Exception:
                return None

        a = get("M_on_L_on")
        b = get("M_on_L_off")
        c = get("M_off_L_on")
        d = get("M_off_L_off")
        if None in (a, b, c, d):
            continue

        eff = (lambda x: -x) if smaller_is_better else (lambda x: x)
        delta = eff(a) - eff(b) - eff(c) + eff(d)
        out.append(
            {
                "Variant": variant,
                "metric": metric_key,
                "delta": f"{delta:.6f}",
                "M_on_L_on": f"{a:.6f}",
                "M_on_L_off": f"{b:.6f}",
                "M_off_L_on": f"{c:.6f}",
                "M_off_L_off": f"{d:.6f}",
            }
        )
    return out


def build_volatility_summary(summary_rows):
    def as_float(v):
        if v in ("", None):
            return None
        try:
            return float(v)
        except Exception:
            return None

    out = []
    for r in summary_rows:
        runtime_med = as_float(r.get("runtime_med"))
        runtime_iqr = as_float(r.get("runtime_iqr"))
        compile_med = as_float(r.get("compile_med"))
        compile_iqr = as_float(r.get("compile_iqr"))

        runtime_iqr_ratio = None
        if runtime_med not in (None, 0.0) and runtime_iqr is not None:
            runtime_iqr_ratio = runtime_iqr / runtime_med

        compile_iqr_ratio = None
        if compile_med not in (None, 0.0) and compile_iqr is not None:
            compile_iqr_ratio = compile_iqr / compile_med

        out.append(
            {
                "Variant": r["Variant"],
                "ConfigName": r["ConfigName"],
                "n": r["n"],
                "runtime_mean": r["runtime_mean"],
                "runtime_med": r["runtime_med"],
                "runtime_iqr": r["runtime_iqr"],
                "runtime_iqr_ratio": f"{runtime_iqr_ratio:.6f}" if runtime_iqr_ratio is not None else "",
                "compile_mean": r["compile_mean"],
                "compile_med": r["compile_med"],
                "compile_iqr": r["compile_iqr"],
                "compile_iqr_ratio": f"{compile_iqr_ratio:.6f}" if compile_iqr_ratio is not None else "",
                "size_mean": r["size_mean"],
                "size_med": r["size_med"],
            }
        )

    def sort_key(row):
        runtime_ratio = as_float(row["runtime_iqr_ratio"])
        runtime_iqr = as_float(row["runtime_iqr"])
        compile_ratio = as_float(row["compile_iqr_ratio"])
        compile_iqr = as_float(row["compile_iqr"])
        return (
            runtime_ratio if runtime_ratio is not None else -1.0,
            runtime_iqr if runtime_iqr is not None else -1.0,
            compile_ratio if compile_ratio is not None else -1.0,
            compile_iqr if compile_iqr is not None else -1.0,
            row["Variant"],
            row["ConfigName"],
        )

    out.sort(key=sort_key, reverse=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("config_file", nargs="?", default=DEFAULT_JSON_PATH)
    ap.add_argument("--json-path", default="")
    ap.add_argument("--runs", type=int, default=10)
    ap.add_argument("--warmup", type=int, default=1)
    ap.add_argument("--target-seconds", type=float, default=0)
    ap.add_argument("--max-repeats", type=int, default=2000)
    ap.add_argument("--out-dir", default="")
    ap.add_argument("--output-dir", default="")
    ap.add_argument("--skip-clean", action="store_true")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--start-name", default="")
    args = ap.parse_args()

    bench_file = ensure_bench_file(PROJECT_ROOT)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = (
        args.out_dir.strip()
        or args.output_dir.strip()
        or os.path.join(DEFAULT_RESULTS_ROOT, f"run_{ts}")
    )
    os.makedirs(out_dir, exist_ok=True)

    results_csv = os.path.join(out_dir, "experiment_results.csv")
    summary_csv = os.path.join(out_dir, "summary_medians.csv")
    inter_csv = os.path.join(out_dir, "interaction_delta.csv")
    volatility_csv = os.path.join(out_dir, "volatility_summary.csv")
    exec_log = os.path.join(out_dir, "experiment_execution.log")

    config_path = args.json_path.strip() or str(args.config_file)
    combos = get_combinations(config_path)

    start_idx = find_start_index_by_name(combos, args.start_name)
    if start_idx is not None:
        combos = combos[start_idx:]

    start = max(int(args.start), 0)
    if int(args.limit) > 0:
        combos = combos[start : start + int(args.limit)]
    else:
        combos = combos[start:]

    env_base = os.environ.copy()
    cargo_bin = os.path.expanduser("~/.cargo/bin")
    if cargo_bin and cargo_bin not in env_base.get("PATH", ""):
        env_base["PATH"] = f"{cargo_bin}:{env_base.get('PATH', '')}"

    baseline_combo = pick_baseline_combo(combos)

    with open(exec_log, "w", encoding="utf-8") as logf:
        logf.write(f"Total Rows: {len(combos)}\n")
        logf.flush()

        run_repeats = calibrate_repeats(
            env_base=env_base,
            baseline_combo=baseline_combo,
            bench_file=bench_file,
            target_seconds=args.target_seconds,
            max_repeats=args.max_repeats,
            skip_clean=args.skip_clean,
            logf=logf,
        )

        fields = [
            "ConfigName",
            "Variant",
            "RunID",
            "LLVM_Pass",
            "MIR_Pass",
            "BinarySize(Bytes)",
            "TotalRuntime(s)",
            "CompileTime(s)",
            "IR_alloca",
            "IR_load",
            "IR_store",
            "IR_gep",
            "IR_phi",
            "IR_bb",
            "LLVM_IR_Path",
            "RunRepeats",
            "TargetSeconds",
            "Status",
        ]

        with open(results_csv, "w", encoding="utf-8", newline="") as outcsv:
            writer = csv.DictWriter(outcsv, fieldnames=fields)
            writer.writeheader()

            for combo in combos:
                name = combo.get("name") or combo.get("Experiment_ID") or "Unknown"
                llvm_pass, mir_pass = labels_from_combo(combo)
                rustflags = compose_rustflags_from_combo(combo)
                total_iters = max(args.warmup, 0) + max(args.runs, 1)

                for it in range(total_iters):
                    is_warmup = it < max(args.warmup, 0)
                    run_id = 0 if is_warmup else (it - max(args.warmup, 0) + 1)

                    msg1 = f"[Exp] {name} Iteration {it + 1}/{total_iters}"
                    msg2 = f"[Flags] {rustflags}"
                    print(msg1)
                    print(msg2)
                    logf.write(msg1 + "\n")
                    logf.write(msg2 + "\n")
                    logf.flush()

                    if not args.skip_clean:
                        clean_project(env_base)

                    ok, compile_time, _, status = build_project(env_base, rustflags, logf)
                    if not ok:
                        if not is_warmup:
                            writer.writerow(
                                {
                                    "ConfigName": name,
                                    "Variant": BENCH_VARIANT,
                                    "RunID": run_id,
                                    "LLVM_Pass": llvm_pass,
                                    "MIR_Pass": mir_pass,
                                    "BinarySize(Bytes)": 0,
                                    "TotalRuntime(s)": 0,
                                    "CompileTime(s)": f"{compile_time:.6f}",
                                    "IR_alloca": "",
                                    "IR_load": "",
                                    "IR_store": "",
                                    "IR_gep": "",
                                    "IR_phi": "",
                                    "IR_bb": "",
                                    "LLVM_IR_Path": "",
                                    "Status": status,
                                }
                            )
                        continue

                    exe_path = get_exe_path()
                    if not exe_path:
                        if not is_warmup:
                            writer.writerow(
                                {
                                    "ConfigName": name,
                                    "Variant": BENCH_VARIANT,
                                    "RunID": run_id,
                                    "LLVM_Pass": llvm_pass,
                                    "MIR_Pass": mir_pass,
                                    "BinarySize(Bytes)": 0,
                                    "TotalRuntime(s)": 0,
                                    "CompileTime(s)": f"{compile_time:.6f}",
                                    "IR_alloca": "",
                                    "IR_load": "",
                                    "IR_store": "",
                                    "IR_gep": "",
                                    "IR_phi": "",
                                    "IR_bb": "",
                                    "LLVM_IR_Path": "",
                                    "Status": "NoBinary",
                                }
                            )
                        continue

                    size = os.path.getsize(exe_path) if os.path.exists(exe_path) else 0
                    ll_path = newest_llvm_ir_path()
                    ir_metrics = count_llvm_ir_metrics(ll_path)

                    if is_warmup:
                        continue

                    wall, err = run_benchmark_repeated(exe_path, bench_file, run_repeats)
                    if wall is None:
                        print(f"[Run] Failed for {name}: {err}")
                        writer.writerow(
                            {
                                "ConfigName": name,
                                "Variant": BENCH_VARIANT,
                                "RunID": run_id,
                                "LLVM_Pass": llvm_pass,
                                "MIR_Pass": mir_pass,
                                "BinarySize(Bytes)": size,
                                "TotalRuntime(s)": 0,
                                "CompileTime(s)": f"{compile_time:.6f}",
                                "IR_alloca": ir_metrics["IR_alloca"],
                                "IR_load": ir_metrics["IR_load"],
                                "IR_store": ir_metrics["IR_store"],
                                "IR_gep": ir_metrics["IR_gep"],
                                "IR_phi": ir_metrics["IR_phi"],
                                "IR_bb": ir_metrics["IR_bb"],
                                "LLVM_IR_Path": ll_path,
                                "RunRepeats": run_repeats,
                                "TargetSeconds": f"{args.target_seconds:.6f}",
                                "Status": "RunFailed",
                            }
                        )
                        outcsv.flush()
                        continue

                    print(f"[Result] Size={size}B, Compile={compile_time:.6f}s, Run={wall:.6f}s")
                    writer.writerow(
                        {
                            "ConfigName": name,
                            "Variant": BENCH_VARIANT,
                            "RunID": run_id,
                            "LLVM_Pass": llvm_pass,
                            "MIR_Pass": mir_pass,
                            "BinarySize(Bytes)": size,
                            "TotalRuntime(s)": f"{wall:.6f}",
                            "CompileTime(s)": f"{compile_time:.6f}",
                            "IR_alloca": ir_metrics["IR_alloca"],
                            "IR_load": ir_metrics["IR_load"],
                            "IR_store": ir_metrics["IR_store"],
                            "IR_gep": ir_metrics["IR_gep"],
                            "IR_phi": ir_metrics["IR_phi"],
                            "IR_bb": ir_metrics["IR_bb"],
                            "LLVM_IR_Path": ll_path,
                            "RunRepeats": run_repeats,
                            "TargetSeconds": f"{args.target_seconds:.6f}",
                            "Status": "Success",
                        }
                    )
                    outcsv.flush()

    rows = []
    with open(results_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    summary = aggregate_summary(rows)
    with open(summary_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "Variant",
                "ConfigName",
                "n",
                "runtime_mean",
                "runtime_med",
                "runtime_iqr",
                "compile_mean",
                "compile_med",
                "compile_iqr",
                "size_mean",
                "size_med",
                "alloca_mean",
                "alloca_med",
                "load_mean",
                "load_med",
                "store_mean",
                "store_med",
                "gep_mean",
                "gep_med",
                "phi_mean",
                "phi_med",
                "bb_mean",
                "bb_med",
            ],
        )
        writer.writeheader()
        for row in summary:
            writer.writerow(row)

    volatility = build_volatility_summary(summary)
    with open(volatility_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "Variant",
                "ConfigName",
                "n",
                "runtime_mean",
                "runtime_med",
                "runtime_iqr",
                "runtime_iqr_ratio",
                "compile_mean",
                "compile_med",
                "compile_iqr",
                "compile_iqr_ratio",
                "size_mean",
                "size_med",
            ],
        )
        writer.writeheader()
        for row in volatility:
            writer.writerow(row)

    inter = []
    inter += compute_interaction(summary, "runtime_med", smaller_is_better=True)
    for key in ("alloca_med", "load_med", "store_med", "gep_med", "phi_med", "bb_med"):
        inter += compute_interaction(summary, key, smaller_is_better=True)

    if inter:
        with open(inter_csv, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["Variant", "metric", "delta", "M_on_L_on", "M_on_L_off", "M_off_L_on", "M_off_L_off"],
            )
            writer.writeheader()
            for row in inter:
                writer.writerow(row)

    print(out_dir)


if __name__ == "__main__":
    main()
