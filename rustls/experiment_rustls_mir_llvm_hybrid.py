import argparse
import csv
import json
import os
import shutil
import subprocess
import time
from collections import defaultdict
from datetime import datetime
from statistics import mean, median


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_ROOT = os.path.dirname(SCRIPT_DIR)
PROJECT_ROOT = SCRIPT_DIR
DEFAULT_JSON_PATH = os.path.join(WORKSPACE_ROOT, "table", "table_json", "combined_experiment_matrix.json")
DEFAULT_RESULTS_ROOT = os.path.join(PROJECT_ROOT, "results")
DEFAULT_TOOLCHAIN = "nightly"
DEFAULT_START_NAME = ""
BENCH_VARIANT = "rustls"


def get_combinations(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("combinations", [])


def get_combo_name(combo):
    return combo.get("name") or combo.get("Experiment_ID") or "Unknown"


def find_combo_start_index(combos, start_name):
    if not start_name:
        return None
    for idx, combo in enumerate(combos):
        name = get_combo_name(combo)
        if name == start_name or name.startswith(start_name):
            return idx
    return None


def labels_from_combo(combo):
    mir_pass_label = "N/A"
    if combo.get("mir"):
        if isinstance(combo["mir"], dict):
            mir_pass_label = combo["mir"].get("pass", "N/A")
        else:
            mir_pass_label = str(combo["mir"])

    llvm_pass_label = "None"
    if combo.get("llvm"):
        if isinstance(combo["llvm"], dict):
            llvm_pass_label = combo["llvm"].get("pass", "None")
        else:
            llvm_pass_label = str(combo["llvm"])

    return llvm_pass_label, mir_pass_label


def compose_rustflags_from_combo(combo):
    flags = ["-C opt-level=3"]

    if combo.get("mir") and isinstance(combo["mir"], dict) and combo["mir"].get("switches"):
        switches = ",".join(combo["mir"]["switches"])
        flags.append(f"-Z mir-enable-passes={switches}")

    if combo.get("llvm") and isinstance(combo["llvm"], dict) and combo["llvm"].get("switches"):
        for switch in combo["llvm"]["switches"]:
            flags.append(f"-C llvm-args={switch}")

    if combo.get("RUSTFLAGS"):
        flags.append(str(combo["RUSTFLAGS"]))

    return " ".join(flags)


def run_capture(cmd, env, logf):
    logf.write(f"[EXEC] {' '.join(cmd)}\n")
    logf.flush()
    p = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if p.stdout:
        logf.write(f"[STDOUT] {p.stdout}\n")
    if p.stderr:
        logf.write(f"[STDERR] {p.stderr}\n")
    logf.flush()
    return p


def clean_project(env):
    target_dir = os.path.join(PROJECT_ROOT, "target")
    if os.path.exists(target_dir):
        try:
            shutil.rmtree(target_dir)
            return True
        except Exception:
            pass
        p = subprocess.run(
            ["cargo", "clean"],
            cwd=PROJECT_ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return p.returncode == 0
    return True


def get_exe_path():
    exe_base = os.path.join(PROJECT_ROOT, "target", "release", "rustls-bench")
    candidates = [exe_base]
    if os.name == "nt":
        candidates = [exe_base + ".exe", exe_base]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def build_project(env, logf, retries=3):
    cmd = ["cargo", "build", "-p", "rustls-bench", "--release", "--features", "ring", "--quiet"]
    last_err = ""
    backoff = 0.5
    for _ in range(max(retries, 1)):
        t0 = time.perf_counter()
        p = run_capture(cmd, env, logf)
        t1 = time.perf_counter()
        if p.returncode == 0:
            return True, t1 - t0
        last_err = (p.stderr or "") + "\n" + (p.stdout or "")
        if "Text file busy (os error 26)" in last_err:
            time.sleep(backoff)
            backoff = min(backoff * 2, 4.0)
            continue
        break
    return False, 0.0


def run_bench_once(exe_path, bench_args):
    args = [exe_path] + bench_args
    t0 = time.perf_counter()
    p = subprocess.run(args, cwd=PROJECT_ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t1 = time.perf_counter()
    if p.returncode != 0:
        return None
    return t1 - t0


def run_benchmark(exe_path, repeats, bench_args):
    total = 0.0
    for _ in range(max(repeats, 1)):
        elapsed = run_bench_once(exe_path, bench_args)
        if elapsed is None:
            return None
        total += elapsed
    return total


def parse_bench_args(mode, cipher_suite, multiplier, threads, api):
    base = ["--multiplier", str(multiplier), "--threads", str(threads), "--api", api]
    if mode == "all-tests":
        return base + ["all-tests"]
    if mode == "handshake":
        return base + ["handshake", cipher_suite]
    if mode == "handshake-resume":
        return base + ["handshake-resume", cipher_suite]
    if mode == "handshake-ticket":
        return base + ["handshake-ticket", cipher_suite]
    if mode == "bulk":
        return base + ["bulk", cipher_suite]
    return base + ["handshake", cipher_suite]


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
                "wall_mean": f"{avg_value('TotalRuntime(s)'):.6f}" if avg_value("TotalRuntime(s)") is not None else "",
                "wall_med": f"{med_value('TotalRuntime(s)'):.6f}" if med_value("TotalRuntime(s)") is not None else "",
                "wall_iqr": f"{iqr_value('TotalRuntime(s)'):.6f}" if iqr_value("TotalRuntime(s)") is not None else "",
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
        wall_med = as_float(row.get("wall_med"))
        wall_iqr = as_float(row.get("wall_iqr"))
        compile_med = as_float(row.get("compile_med"))
        compile_iqr = as_float(row.get("compile_iqr"))

        wall_iqr_ratio = None
        if wall_med not in (None, 0.0) and wall_iqr is not None:
            wall_iqr_ratio = wall_iqr / wall_med

        compile_iqr_ratio = None
        if compile_med not in (None, 0.0) and compile_iqr is not None:
            compile_iqr_ratio = compile_iqr / compile_med

        out.append(
            {
                "Variant": row["Variant"],
                "ConfigName": row["ConfigName"],
                "n": row["n"],
                "wall_mean": row["wall_mean"],
                "wall_med": row["wall_med"],
                "wall_iqr": row["wall_iqr"],
                "wall_iqr_ratio": f"{wall_iqr_ratio:.6f}" if wall_iqr_ratio is not None else "",
                "compile_mean": row["compile_mean"],
                "compile_med": row["compile_med"],
                "compile_iqr": row["compile_iqr"],
                "compile_iqr_ratio": f"{compile_iqr_ratio:.6f}" if compile_iqr_ratio is not None else "",
                "size_mean": row["size_mean"],
                "size_med": row["size_med"],
            }
        )

    def sort_key(row):
        wall_ratio = as_float(row["wall_iqr_ratio"])
        wall_iqr = as_float(row["wall_iqr"])
        compile_ratio = as_float(row["compile_iqr_ratio"])
        compile_iqr = as_float(row["compile_iqr"])
        return (
            wall_ratio if wall_ratio is not None else -1.0,
            wall_iqr if wall_iqr is not None else -1.0,
            compile_ratio if compile_ratio is not None else -1.0,
            compile_iqr if compile_iqr is not None else -1.0,
            row["Variant"],
            row["ConfigName"],
        )

    out.sort(key=sort_key, reverse=True)
    return out


def measure_combination(combo, runs, skip_clean, bench_args, run_repeats, warmup, mode, logf, toolchain):
    name = get_combo_name(combo)
    llvm_pass_label, mir_pass_label = labels_from_combo(combo)

    env = os.environ.copy()
    cargo_bin = os.path.join(os.path.expanduser("~"), ".cargo", "bin")
    if os.path.isdir(cargo_bin):
        current_path = env.get("PATH", "")
        parts = current_path.split(os.pathsep) if current_path else []
        if cargo_bin not in parts:
            env["PATH"] = cargo_bin + (os.pathsep + current_path if current_path else "")

    if toolchain:
        env["RUSTUP_TOOLCHAIN"] = toolchain

    rustflags = compose_rustflags_from_combo(combo)
    env["RUSTFLAGS"] = rustflags

    rows = []
    msg1 = f"[Exp] {name}"
    msg2 = f"[Flags] {rustflags}"
    msg3 = f"[Run] repeats={run_repeats}, warmup={warmup}, args={' '.join(bench_args)}"
    print(msg1)
    print(msg2)
    print(msg3)
    logf.write(msg1 + "\n")
    logf.write(msg2 + "\n")
    logf.write(msg3 + "\n")
    logf.flush()

    if not skip_clean:
        clean_ok = clean_project(env)
        if not clean_ok:
            return [
                {
                    "ConfigName": name,
                    "Variant": BENCH_VARIANT,
                    "RunID": 1,
                    "LLVM_Pass": llvm_pass_label,
                    "MIR_Pass": mir_pass_label,
                    "BinarySize(Bytes)": 0,
                    "TotalRuntime(s)": 0,
                    "CompileTime(s)": "0.000000",
                    "Mode": mode,
                    "Status": "CleanFailed",
                }
            ]

    ok, compile_time = build_project(env, logf)
    exe_path = get_exe_path()
    if not ok:
        return [
            {
                "ConfigName": name,
                "Variant": BENCH_VARIANT,
                "RunID": 1,
                "LLVM_Pass": llvm_pass_label,
                "MIR_Pass": mir_pass_label,
                "BinarySize(Bytes)": 0,
                "TotalRuntime(s)": 0,
                "CompileTime(s)": f"{compile_time:.6f}",
                "Mode": mode,
                "Status": "BuildFailed",
            }
        ]
    if not exe_path:
        return [
            {
                "ConfigName": name,
                "Variant": BENCH_VARIANT,
                "RunID": 1,
                "LLVM_Pass": llvm_pass_label,
                "MIR_Pass": mir_pass_label,
                "BinarySize(Bytes)": 0,
                "TotalRuntime(s)": 0,
                "CompileTime(s)": f"{compile_time:.6f}",
                "Mode": mode,
                "Status": "NoBinary",
            }
        ]

    size_bytes = os.path.getsize(exe_path)

    for warmup_id in range(1, max(warmup, 0) + 1):
        warmup_msg = f"[Exp] {name} Warmup {warmup_id}/{warmup}"
        print(warmup_msg)
        logf.write(warmup_msg + "\n")
        logf.flush()
        warmup_elapsed = run_bench_once(exe_path, bench_args)
        if warmup_elapsed is None:
            return [
                {
                    "ConfigName": name,
                    "Variant": BENCH_VARIANT,
                    "RunID": 1,
                    "LLVM_Pass": llvm_pass_label,
                    "MIR_Pass": mir_pass_label,
                    "BinarySize(Bytes)": size_bytes,
                    "TotalRuntime(s)": 0,
                    "CompileTime(s)": f"{compile_time:.6f}",
                    "Mode": mode,
                    "Status": "WarmupFailed",
                }
            ]
        warmup_result = f"[WarmupResult] Size={size_bytes}B, Compile={compile_time:.6f}s, RunTotal={warmup_elapsed:.6f}s"
        print(warmup_result)
        logf.write(warmup_result + "\n")
        logf.flush()

    for run_id in range(1, runs + 1):
        iter_msg = f"[Exp] {name} Iteration {run_id}/{runs}"
        print(iter_msg)
        logf.write(iter_msg + "\n")
        logf.flush()

        runtime_total = run_benchmark(exe_path, run_repeats, bench_args)
        if runtime_total is None:
            rows.append(
                {
                    "ConfigName": name,
                    "Variant": BENCH_VARIANT,
                    "RunID": run_id,
                    "LLVM_Pass": llvm_pass_label,
                    "MIR_Pass": mir_pass_label,
                    "BinarySize(Bytes)": size_bytes,
                    "TotalRuntime(s)": 0,
                    "CompileTime(s)": f"{compile_time:.6f}",
                    "Mode": mode,
                    "Status": "RunFailed",
                }
            )
            break

        rows.append(
            {
                "ConfigName": name,
                "Variant": BENCH_VARIANT,
                "RunID": run_id,
                "LLVM_Pass": llvm_pass_label,
                "MIR_Pass": mir_pass_label,
                "BinarySize(Bytes)": size_bytes,
                "TotalRuntime(s)": f"{runtime_total:.6f}",
                "CompileTime(s)": f"{compile_time:.6f}",
                "Mode": mode,
                "Status": "Success",
            }
        )

        msg4 = f"[Result] Size={size_bytes}B, Compile={compile_time:.6f}s, RunTotal={runtime_total:.6f}s"
        print(msg4)
        logf.write(msg4 + "\n")
        logf.flush()

    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("config_file", nargs="?", default=DEFAULT_JSON_PATH)
    parser.add_argument("--json-path", default="")
    parser.add_argument("--toolchain", default=DEFAULT_TOOLCHAIN)
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--start-name", "--start-exp", dest="start_name", default=DEFAULT_START_NAME)
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--skip-clean", action="store_true")
    parser.add_argument("--mode", default="handshake", choices=["handshake", "handshake-resume", "handshake-ticket", "bulk", "all-tests"])
    parser.add_argument("--cipher-suite", default="TLS13_AES_128_GCM_SHA256")
    parser.add_argument("--multiplier", type=float, default=10.0)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--api", default="both", choices=["both", "buffered", "unbuffered"])
    parser.add_argument("--run-repeats", type=int, default=1)
    parser.add_argument("--warmup", type=int, default=1)
    args = parser.parse_args()

    config_path = args.json_path.strip() or str(args.config_file)
    if not os.path.exists(config_path):
        raise SystemExit(f"JSON path not found: {config_path}")

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
    if args.start_name.strip():
        found = find_combo_start_index(combos, args.start_name.strip())
        if found is None:
            raise SystemExit(f'--start-name "{args.start_name.strip()}" not found in combinations')
        start_index = found
    elif args.start > 0:
        start_index = args.start

    if start_index > 0:
        combos = combos[start_index:]
    if args.limit and args.limit > 0:
        combos = combos[: args.limit]

    bench_args = parse_bench_args(args.mode, args.cipher_suite, args.multiplier, args.threads, args.api)

    with open(exec_log, "w", encoding="utf-8") as logf:
        logf.write(f"Total Rows: {len(combos)}\n")
        logf.flush()
        print(f"Total Rows: {len(combos)}")

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
                    "Mode",
                    "Status",
                ],
            )
            writer.writeheader()
            outcsv.flush()

            for combo in combos:
                rows = measure_combination(
                    combo=combo,
                    runs=args.runs,
                    skip_clean=args.skip_clean,
                    bench_args=bench_args,
                    run_repeats=args.run_repeats,
                    warmup=args.warmup,
                    mode=args.mode,
                    logf=logf,
                    toolchain=args.toolchain,
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
                "wall_mean",
                "wall_med",
                "wall_iqr",
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
                "wall_mean",
                "wall_med",
                "wall_iqr",
                "wall_iqr_ratio",
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

    inter = compute_interaction(summary, "wall_med", smaller_is_better=True)
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

