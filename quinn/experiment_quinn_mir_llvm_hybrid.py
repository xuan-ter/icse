import argparse
import csv
import json
import os
import shlex
import shutil
import subprocess
import time
from collections import defaultdict
from datetime import datetime
from statistics import mean, median


PROJECT_ROOT = "/root/MIR_LLVM/quinn"
WORKSPACE_ROOT = "/root/MIR_LLVM"
DEFAULT_JSON_ROOT = "/root/MIR_LLVM/table"
DEFAULT_JSON_BASENAME = "combined_experiment_matrix.json"
DEFAULT_RESULTS_ROOT = "/root/MIR_LLVM/quinn/results"
BENCH_VARIANT = "quinn"
BUILD_PACKAGE = "bench"
BUILD_BIN = "bulk"
DEFAULT_BENCH_ARGS = "--clients 1 --streams 1 --max_streams 1 --download-size 64M --upload-size 0"


def get_combinations(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("combinations", [])


def resolve_json_path(json_path_arg):
    candidate = os.path.abspath(json_path_arg.strip()) if json_path_arg.strip() else DEFAULT_JSON_ROOT

    if os.path.isfile(candidate):
        return candidate

    if os.path.isdir(candidate):
        preferred = os.path.join(candidate, "table_json", DEFAULT_JSON_BASENAME)
        if os.path.isfile(preferred):
            return preferred

        for root, _, files in os.walk(candidate):
            if DEFAULT_JSON_BASENAME in files:
                return os.path.join(root, DEFAULT_JSON_BASENAME)

        raise SystemExit(f"No JSON file named {DEFAULT_JSON_BASENAME} found under: {candidate}")

    raise SystemExit(f"JSON path not found: {candidate}")


def find_combo_start_index(combos, start_exp_id):
    if not start_exp_id:
        return None
    for idx, combo in enumerate(combos):
        name = combo.get("name") or combo.get("Experiment_ID")
        if name == start_exp_id:
            return idx
    return None


def compose_rustflags_from_combo(combo):
    parts = ["-C opt-level=3"]
    if combo.get("mir") and isinstance(combo["mir"], dict) and combo["mir"].get("switches"):
        switches = ",".join(combo["mir"]["switches"])
        parts.append(f"-Z mir-enable-passes={switches}")
    if combo.get("llvm") and isinstance(combo["llvm"], dict) and combo["llvm"].get("switches"):
        for switch in combo["llvm"]["switches"]:
            parts.append(f"-C llvm-args={switch}")
    if "RUSTFLAGS" in combo and combo["RUSTFLAGS"]:
        parts.append(combo["RUSTFLAGS"])
    return " ".join(parts)


def labels_from_combo(combo):
    mir_pass_label = "N/A"
    llvm_pass_label = "None"
    if combo.get("mir"):
        if isinstance(combo["mir"], dict):
            mir_pass_label = combo["mir"].get("pass", "N/A")
        else:
            mir_pass_label = str(combo["mir"])
    if combo.get("llvm"):
        if isinstance(combo["llvm"], dict):
            llvm_pass_label = combo["llvm"].get("pass", "None")
        else:
            llvm_pass_label = str(combo["llvm"])
    return llvm_pass_label, mir_pass_label


def clean_project(env=None):
    target_dir = os.path.join(PROJECT_ROOT, "target")
    if os.path.exists(target_dir):
        try:
            shutil.rmtree(target_dir)
            return
        except Exception:
            if env is None:
                env = os.environ.copy()
            subprocess.run(
                ["cargo", "+nightly", "clean"],
                cwd=PROJECT_ROOT,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )


def build_project(env, logf, retries=2):
    backoff = 0.5
    last_err = ""
    cmd = ["cargo", "+nightly", "build", "--release", "--quiet", "-p", BUILD_PACKAGE, "--bin", BUILD_BIN]
    for _ in range(retries + 1):
        r = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if r.returncode == 0:
            return True, "Success"
        err = r.stderr or ""
        last_err = err
        if err.strip():
            logf.write(err + "\n")
            logf.flush()
        if ("Text file busy (os error 26)" in err) or ("never executed" in err):
            time.sleep(backoff)
            backoff = min(backoff * 2, 4.0)
            continue
        return False, "BuildFailed"

    if ("Text file busy (os error 26)" in last_err) or ("never executed" in last_err) or ("failed to run custom build command" in last_err):
        return False, "Skipped"
    return False, "BuildFailed"


def get_exe_path():
    exe_name = f"{BUILD_BIN}.exe" if os.name == "nt" else BUILD_BIN
    exe_path = os.path.join(PROJECT_ROOT, "target", "release", exe_name)
    return exe_path if os.path.exists(exe_path) else None


def run_benchmark(exe_path, repeats, warmup, bench_args):
    args = [exe_path] + bench_args

    for _ in range(max(warmup, 0)):
        p = subprocess.run(args, cwd=PROJECT_ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if p.returncode != 0:
            return None

    total = 0.0
    for _ in range(repeats):
        t0 = time.perf_counter()
        p = subprocess.run(args, cwd=PROJECT_ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        t1 = time.perf_counter()
        if p.returncode != 0:
            return None
        total += t1 - t0
    return total


def aggregate_summary(rows):
    by = defaultdict(list)
    for row in rows:
        if row.get("Status") != "Success":
            continue
        key = (row.get("Variant", BENCH_VARIANT), row["ConfigName"])
        by[key].append(row)

    out = []
    for (variant, cfg), rs in sorted(by.items()):
        def values(key, cast=float):
            xs = []
            for row in rs:
                try:
                    xs.append(cast(row[key]))
                except Exception:
                    pass
            return sorted(xs)

        def avg_value(key, cast=float):
            xs = values(key, cast)
            return mean(xs) if xs else None

        def med_value(key, cast=float):
            xs = values(key, cast)
            return median(xs) if xs else None

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

        def iqr_value(key, cast=float):
            xs = values(key, cast)
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
                "runtime_mean": f"{avg_value('TotalRuntime(s)'):.6f}" if avg_value("TotalRuntime(s)") is not None else "",
                "runtime_med": f"{med_value('TotalRuntime(s)'):.6f}" if med_value("TotalRuntime(s)") is not None else "",
                "runtime_iqr": f"{iqr_value('TotalRuntime(s)'):.6f}" if iqr_value("TotalRuntime(s)") is not None else "",
                "compile_mean": f"{avg_value('CompileTime(s)'):.6f}" if avg_value("CompileTime(s)") is not None else "",
                "compile_med": f"{med_value('CompileTime(s)'):.6f}" if med_value("CompileTime(s)") is not None else "",
                "compile_iqr": f"{iqr_value('CompileTime(s)'):.6f}" if iqr_value("CompileTime(s)") is not None else "",
                "size_mean": f"{avg_value('BinarySize(Bytes)', int):.6f}" if avg_value("BinarySize(Bytes)", int) is not None else "",
                "size_med": f"{med_value('BinarySize(Bytes)', int):.0f}" if med_value("BinarySize(Bytes)", int) is not None else "",
            }
        )
    return out


def compute_interaction(summary_rows, metric_key, smaller_is_better=True):
    idx = {(row["Variant"], row["ConfigName"]): row for row in summary_rows}
    out = []
    for variant in sorted({row["Variant"] for row in summary_rows}):
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

        effect = (lambda x: -x) if smaller_is_better else (lambda x: x)
        delta = effect(a) - effect(b) - effect(c) + effect(d)
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
    def as_float(value):
        if value in ("", None):
            return None
        try:
            return float(value)
        except Exception:
            return None

    out = []
    for row in summary_rows:
        runtime_med = as_float(row.get("runtime_med"))
        runtime_iqr = as_float(row.get("runtime_iqr"))
        compile_med = as_float(row.get("compile_med"))
        compile_iqr = as_float(row.get("compile_iqr"))

        runtime_iqr_ratio = None
        if runtime_med not in (None, 0.0) and runtime_iqr is not None:
            runtime_iqr_ratio = runtime_iqr / runtime_med

        compile_iqr_ratio = None
        if compile_med not in (None, 0.0) and compile_iqr is not None:
            compile_iqr_ratio = compile_iqr / compile_med

        out.append(
            {
                "Variant": row["Variant"],
                "ConfigName": row["ConfigName"],
                "n": row["n"],
                "runtime_mean": row["runtime_mean"],
                "runtime_med": row["runtime_med"],
                "runtime_iqr": row["runtime_iqr"],
                "runtime_iqr_ratio": f"{runtime_iqr_ratio:.6f}" if runtime_iqr_ratio is not None else "",
                "compile_mean": row["compile_mean"],
                "compile_med": row["compile_med"],
                "compile_iqr": row["compile_iqr"],
                "compile_iqr_ratio": f"{compile_iqr_ratio:.6f}" if compile_iqr_ratio is not None else "",
                "size_mean": row["size_mean"],
                "size_med": row["size_med"],
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


def measure_combination(combo, runs, skip_clean, run_repeats, warmup, bench_args, logf):
    name = combo.get("name") or combo.get("Experiment_ID") or "Unknown"
    llvm_pass_label, mir_pass_label = labels_from_combo(combo)

    env = os.environ.copy()
    env.setdefault("RUSTUP_TOOLCHAIN", "nightly")
    cargo_bin = os.path.expanduser("~/.cargo/bin")
    if cargo_bin and cargo_bin not in env.get("PATH", ""):
        env["PATH"] = f"{cargo_bin}:{env.get('PATH', '')}"

    rustflags = compose_rustflags_from_combo(combo)
    env["RUSTFLAGS"] = rustflags

    results = []
    bench_args_str = shlex.join(bench_args)
    msg1 = f"[Exp] {name}"
    msg2 = f"[Flags] {rustflags}"
    msg3 = f"[Run] runs={runs}, repeats={run_repeats}, warmup={warmup}, args={bench_args_str}"
    print(msg1)
    print(msg2)
    print(msg3)
    logf.write(msg1 + "\n")
    logf.write(msg2 + "\n")
    logf.write(msg3 + "\n")
    logf.flush()

    if not skip_clean:
        clean_project(env)

    t0 = time.perf_counter()
    ok, status = build_project(env, logf)
    t1 = time.perf_counter()
    compile_time = t1 - t0

    if not ok:
        results.append(
            {
                "ConfigName": name,
                "Variant": BENCH_VARIANT,
                "RunID": 1,
                "LLVM_Pass": llvm_pass_label,
                "MIR_Pass": mir_pass_label,
                "BinarySize(Bytes)": 0,
                "TotalRuntime(s)": 0,
                "CompileTime(s)": f"{compile_time:.6f}",
                "RunRepeats": run_repeats,
                "Warmup": warmup,
                "BenchArgs": bench_args_str,
                "Status": status,
            }
        )
        return results

    exe_path = get_exe_path()
    if not exe_path:
        results.append(
            {
                "ConfigName": name,
                "Variant": BENCH_VARIANT,
                "RunID": 1,
                "LLVM_Pass": llvm_pass_label,
                "MIR_Pass": mir_pass_label,
                "BinarySize(Bytes)": 0,
                "TotalRuntime(s)": 0,
                "CompileTime(s)": f"{compile_time:.6f}",
                "RunRepeats": run_repeats,
                "Warmup": warmup,
                "BenchArgs": bench_args_str,
                "Status": "NoBinary",
            }
        )
        return results

    try:
        size = os.path.getsize(exe_path)
    except Exception:
        size = 0

    for run_id in range(1, runs + 1):
        run_msg = f"[Measure] {name} Run {run_id}/{runs}"
        print(run_msg)
        logf.write(run_msg + "\n")
        logf.flush()

        avg_runtime = run_benchmark(exe_path, run_repeats, warmup, bench_args)
        if avg_runtime is None:
            results.append(
                {
                    "ConfigName": name,
                    "Variant": BENCH_VARIANT,
                    "RunID": run_id,
                    "LLVM_Pass": llvm_pass_label,
                    "MIR_Pass": mir_pass_label,
                    "BinarySize(Bytes)": size,
                    "TotalRuntime(s)": 0,
                    "CompileTime(s)": f"{compile_time:.6f}",
                    "RunRepeats": run_repeats,
                    "Warmup": warmup,
                    "BenchArgs": bench_args_str,
                    "Status": "RunFailed",
                }
            )
            break

        print(f"[Result] Size={size}B, Compile={compile_time:.6f}s, RunTotal={avg_runtime:.6f}s")
        results.append(
            {
                "ConfigName": name,
                "Variant": BENCH_VARIANT,
                "RunID": run_id,
                "LLVM_Pass": llvm_pass_label,
                "MIR_Pass": mir_pass_label,
                "BinarySize(Bytes)": size,
                "TotalRuntime(s)": f"{avg_runtime:.6f}",
                "CompileTime(s)": f"{compile_time:.6f}",
                "RunRepeats": run_repeats,
                "Warmup": warmup,
                "BenchArgs": bench_args_str,
                "Status": "Success",
            }
        )

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("config_file", nargs="?", default=DEFAULT_JSON_ROOT)
    parser.add_argument("--json-path", default="")
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--start-exp", default="")
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--skip-clean", action="store_true")
    parser.add_argument("--run-repeats", type=int, default=5)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--bench-args", default=DEFAULT_BENCH_ARGS)
    args = parser.parse_args()

    bench_args = shlex.split(args.bench_args.strip()) if args.bench_args.strip() else []
    config_path = resolve_json_path(args.json_path.strip() or str(args.config_file))

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_out = args.out_dir.strip() or args.output_dir.strip() or os.path.join(DEFAULT_RESULTS_ROOT, ts)
    os.makedirs(base_out, exist_ok=True)

    results_csv = os.path.join(base_out, "experiment_results.csv")
    summary_csv = os.path.join(base_out, "summary_medians.csv")
    inter_csv = os.path.join(base_out, "interaction_delta.csv")
    volatility_csv = os.path.join(base_out, "volatility_summary.csv")
    exec_log = os.path.join(base_out, "experiment_execution.log")

    combos = get_combinations(config_path)
    start_index = 0
    if args.start_exp.strip():
        found = find_combo_start_index(combos, args.start_exp.strip())
        if found is None:
            raise SystemExit(f'--start-exp "{args.start_exp.strip()}" not found in combinations')
        start_index = found
    elif args.start > 0:
        start_index = args.start

    if start_index > 0:
        combos = combos[start_index:]
    if args.limit and args.limit > 0:
        combos = combos[: args.limit]

    with open(exec_log, "w", encoding="utf-8") as logf:
        print(f"Total Rows: {len(combos)}")
        logf.write(f"Total Rows: {len(combos)}\n")
        logf.flush()

        with open(results_csv, "w", encoding="utf-8", newline="") as outcsv:
            writer = csv.DictWriter(
                outcsv,
                fieldnames=[
                    "ConfigName",
                    "Variant",
                    "RunID",
                    "LLVM_Pass",
                    "MIR_Pass",
                    "BinarySize(Bytes)",
                    "TotalRuntime(s)",
                    "CompileTime(s)",
                    "RunRepeats",
                    "Warmup",
                    "BenchArgs",
                    "Status",
                ],
            )
            writer.writeheader()
            outcsv.flush()

            for combo in combos:
                rows = measure_combination(
                    combo,
                    args.runs,
                    args.skip_clean,
                    args.run_repeats,
                    args.warmup,
                    bench_args,
                    logf,
                )
                for row in rows:
                    writer.writerow(row)
                outcsv.flush()

    rows = []
    with open(results_csv, "r", encoding="utf-8") as incsv:
        reader = csv.DictReader(incsv)
        for row in reader:
            rows.append(row)

    summary = aggregate_summary(rows)
    with open(summary_csv, "w", encoding="utf-8", newline="") as outcsv:
        writer = csv.DictWriter(
            outcsv,
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
            ],
        )
        writer.writeheader()
        for row in summary:
            writer.writerow(row)

    volatility = build_volatility_summary(summary)
    with open(volatility_csv, "w", encoding="utf-8", newline="") as outcsv:
        writer = csv.DictWriter(
            outcsv,
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

    inter = compute_interaction(summary, "runtime_med", smaller_is_better=True)
    if inter:
        with open(inter_csv, "w", encoding="utf-8", newline="") as outcsv:
            writer = csv.DictWriter(
                outcsv,
                fieldnames=["Variant", "metric", "delta", "M_on_L_on", "M_on_L_off", "M_off_L_on", "M_off_L_off"],
            )
            writer.writeheader()
            for row in inter:
                writer.writerow(row)

    print(base_out)


if __name__ == "__main__":
    main()
