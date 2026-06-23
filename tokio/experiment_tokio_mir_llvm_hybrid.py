import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import time
from collections import defaultdict
from datetime import datetime
from glob import glob
from statistics import mean, median


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE_ROOT = os.path.dirname(SCRIPT_DIR)
PROJECT_ROOT = SCRIPT_DIR
TABLE_ROOT = os.path.join(WORKSPACE_ROOT, "table")
DEFAULT_JSON_PATH = os.path.join(TABLE_ROOT, "table_json", "combined_experiment_matrix.json")
DEFAULT_RESULTS_ROOT = os.path.join(PROJECT_ROOT, "results")
DEFAULT_TOOLCHAIN = "nightly"
BENCH_VARIANT = "tokio"


def get_combinations(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("combinations", [])


def resolve_json_path(path_value):
    raw = (path_value or "").strip()
    if not raw:
        return DEFAULT_JSON_PATH

    if os.path.isfile(raw):
        return raw

    if os.path.isdir(raw):
        candidates = [
            os.path.join(raw, "combined_experiment_matrix.json"),
            os.path.join(raw, "table_json", "combined_experiment_matrix.json"),
        ]
        for candidate in candidates:
            if os.path.isfile(candidate):
                return candidate

    return raw


def find_combo_start_index(combos, start_exp_id):
    if not start_exp_id:
        return None
    for idx, combo in enumerate(combos):
        name = combo.get("name") or combo.get("Experiment_ID")
        if name == start_exp_id:
            return idx
    return None


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
    return " ".join(parts)


def clean_project(env=None):
    target_dir = os.path.join(PROJECT_ROOT, "target")
    if os.path.exists(target_dir):
        try:
            shutil.rmtree(target_dir)
            return
        except Exception:
            pass
    if env is None:
        env = os.environ.copy()
    subprocess.run(
        ["cargo", "clean"],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def run_capture(cmd, env, logf, log_streams):
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
    if log_streams or p.returncode != 0:
        if p.stdout:
            out = p.stdout if log_streams else p.stdout[-4000:]
            logf.write(f"[STDOUT] {out}\n")
        if p.stderr:
            err = p.stderr if log_streams else p.stderr[-4000:]
            logf.write(f"[STDERR] {err}\n")
    logf.flush()
    return p


def build_bench(env, bench_name, logf, log_cargo_output, retries=3):
    cmd = ["cargo", "bench", "-p", "benches", "--bench", bench_name, "--no-run"]
    last_err = ""
    last_compile_time = 0.0
    backoff = 0.5
    for _ in range(max(retries, 1)):
        t0 = time.perf_counter()
        p = run_capture(cmd, env, logf, log_cargo_output)
        t1 = time.perf_counter()
        last_compile_time = t1 - t0
        if p.returncode == 0:
            exe = extract_bench_exe_path(p.stdout + "\n" + p.stderr, bench_name)
            return True, last_compile_time, exe

        last_err = (p.stderr or "") + "\n" + (p.stdout or "")
        if "Text file busy (os error 26)" in last_err:
            time.sleep(backoff)
            backoff = min(backoff * 2, 4.0)
            continue
        break

    if "Text file busy (os error 26)" in last_err:
        return False, last_compile_time, "Skipped"
    return False, last_compile_time, "BuildFailed"


def extract_bench_exe_path(build_output, bench_name):
    match = re.findall(r"Executable\s+.+?\s+\((target[\\/].+?)\)", build_output)
    if match:
        rel = match[-1].strip().replace("/", os.sep).replace("\\", os.sep)
        return os.path.join(PROJECT_ROOT, rel)

    candidates = []
    for path in glob(os.path.join(PROJECT_ROOT, "target", "release", "deps", f"{bench_name}-*")):
        if path.endswith(".d"):
            continue
        if os.path.isfile(path) and os.access(path, os.X_OK):
            candidates.append(path)

    if candidates:
        candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        return candidates[0]
    return None


def parse_bench_args(raw):
    if not raw.strip():
        return ["--bench"]
    return raw.strip().split()


def parse_time_to_ns(value, unit):
    unit_scale = {
        "ps": 1e-3,
        "ns": 1.0,
        "us": 1e3,
        "µs": 1e3,
        "ms": 1e6,
        "s": 1e9,
    }
    scale = unit_scale.get(unit)
    if scale is None:
        return ""
    return f"{float(value.replace(',', '')) * scale:.6f}"


def parse_throughput_to_mbps(value, unit):
    unit_scale = {
        "B/s": 1.0 / 1_000_000.0,
        "KiB/s": 1024.0 / 1_000_000.0,
        "MiB/s": (1024.0 ** 2) / 1_000_000.0,
        "GiB/s": (1024.0 ** 3) / 1_000_000.0,
        "KB/s": 1_000.0 / 1_000_000.0,
        "MB/s": 1.0,
        "GB/s": 1_000.0,
    }
    scale = unit_scale.get(unit)
    if scale is None:
        return ""
    return f"{float(value.replace(',', '')) * scale:.6f}"


def extract_criterion_metrics(output):
    ns_per_iter = ""
    mbps = ""

    time_match = re.search(
        r"time:\s*\[\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*([a-zA-Zµ/]+)\s+([0-9][0-9,]*(?:\.[0-9]+)?)\s*([a-zA-Zµ/]+)\s+([0-9][0-9,]*(?:\.[0-9]+)?)\s*([a-zA-Zµ/]+)\s*\]",
        output,
    )
    if time_match:
        ns_per_iter = parse_time_to_ns(time_match.group(3), time_match.group(4))
    else:
        alt_time_match = re.search(r"time:\s*\[\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*([a-zA-Zµ/]+)\s*\]", output)
        if alt_time_match:
            ns_per_iter = parse_time_to_ns(alt_time_match.group(1), alt_time_match.group(2))

    thrpt_match = re.search(
        r"thrpt:\s*\[\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*([A-Za-z/]+)\s+([0-9][0-9,]*(?:\.[0-9]+)?)\s*([A-Za-z/]+)\s+([0-9][0-9,]*(?:\.[0-9]+)?)\s*([A-Za-z/]+)\s*\]",
        output,
    )
    if thrpt_match:
        mbps = parse_throughput_to_mbps(thrpt_match.group(3), thrpt_match.group(4))
    else:
        alt_thrpt_match = re.search(r"throughput:\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*([A-Za-z/]+)", output)
        if alt_thrpt_match:
            mbps = parse_throughput_to_mbps(alt_thrpt_match.group(1), alt_thrpt_match.group(2))

    return ns_per_iter, mbps


def run_benchmark(exe_path, bench_filter, bench_args, repeat):
    total_wall = 0.0
    last_err = ""
    ns_per_iter = ""
    mbps = ""

    for _ in range(max(repeat, 1)):
        cmd = [exe_path]
        if bench_filter:
            cmd.append(bench_filter)
        cmd.extend(bench_args)

        t0 = time.perf_counter()
        p = subprocess.run(
            cmd,
            cwd=PROJECT_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        t1 = time.perf_counter()
        if p.returncode != 0:
            last_err = (p.stdout or "").strip()
            return None, "", "", last_err

        total_wall += (t1 - t0)
        run_ns, run_mbps = extract_criterion_metrics(p.stdout or "")
        if run_ns:
            ns_per_iter = run_ns
        if run_mbps:
            mbps = run_mbps

    return total_wall, ns_per_iter, mbps, last_err


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
                    value = row[key]
                    if value == "":
                        continue
                    xs.append(cast(value))
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
                "ns_mean": f"{avg_value('NsPerIter'):.6f}" if avg_value("NsPerIter") is not None else "",
                "ns_med": f"{med_value('NsPerIter'):.6f}" if med_value("NsPerIter") is not None else "",
                "ns_iqr": f"{iqr_value('NsPerIter'):.6f}" if iqr_value("NsPerIter") is not None else "",
                "mbps_mean": f"{avg_value('MBps'):.6f}" if avg_value("MBps") is not None else "",
                "mbps_med": f"{med_value('MBps'):.6f}" if med_value("MBps") is not None else "",
                "mbps_iqr": f"{iqr_value('MBps'):.6f}" if iqr_value("MBps") is not None else "",
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
        ns_med = as_float(row.get("ns_med"))
        ns_iqr = as_float(row.get("ns_iqr"))
        compile_med = as_float(row.get("compile_med"))
        compile_iqr = as_float(row.get("compile_iqr"))

        ns_iqr_ratio = None
        if ns_med not in (None, 0.0) and ns_iqr is not None:
            ns_iqr_ratio = ns_iqr / ns_med

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
                "ns_mean": row["ns_mean"],
                "ns_med": row["ns_med"],
                "ns_iqr": row["ns_iqr"],
                "ns_iqr_ratio": f"{ns_iqr_ratio:.6f}" if ns_iqr_ratio is not None else "",
                "mbps_mean": row["mbps_mean"],
                "mbps_med": row["mbps_med"],
                "mbps_iqr": row["mbps_iqr"],
                "compile_mean": row["compile_mean"],
                "compile_med": row["compile_med"],
                "compile_iqr": row["compile_iqr"],
                "compile_iqr_ratio": f"{compile_iqr_ratio:.6f}" if compile_iqr_ratio is not None else "",
                "size_mean": row["size_mean"],
                "size_med": row["size_med"],
            }
        )

    def sort_key(row):
        ns_ratio = as_float(row["ns_iqr_ratio"])
        ns_iqr = as_float(row["ns_iqr"])
        compile_ratio = as_float(row["compile_iqr_ratio"])
        compile_iqr = as_float(row["compile_iqr"])
        return (
            ns_ratio if ns_ratio is not None else -1.0,
            ns_iqr if ns_iqr is not None else -1.0,
            compile_ratio if compile_ratio is not None else -1.0,
            compile_iqr if compile_iqr is not None else -1.0,
            row["Variant"],
            row["ConfigName"],
        )

    out.sort(key=sort_key, reverse=True)
    return out


def make_result_row(name, llvm_pass, mir_pass, bench_name, bench_filter, bench_repeat, compile_time, status, size=0, run_id=1, total_runtime=0, ns_per_iter="", mbps=""):
    return {
        "ConfigName": name,
        "Variant": BENCH_VARIANT,
        "RunID": run_id,
        "LLVM_Pass": llvm_pass,
        "MIR_Pass": mir_pass,
        "BinarySize(Bytes)": size,
        "NsPerIter": ns_per_iter,
        "MBps": mbps,
        "TotalRuntime(s)": f"{float(total_runtime):.6f}",
        "CompileTime(s)": f"{compile_time:.6f}",
        "BenchName": bench_name,
        "BenchFilter": bench_filter,
        "BenchRepeat": bench_repeat,
        "Status": status,
    }


def measure_combination(combo, runs, skip_clean, bench_name, bench_filter, bench_repeat, warmup_runs, bench_args, logf, toolchain, log_cargo_output):
    name = combo.get("name") or combo.get("Experiment_ID") or "Unknown"
    llvm_pass, mir_pass = labels_from_combo(combo)

    env = os.environ.copy()
    cargo_bin = os.path.join(os.path.expanduser("~"), ".cargo", "bin")
    if os.path.isdir(cargo_bin):
        current_path = env.get("PATH", "")
        parts = current_path.split(os.pathsep) if current_path else []
        if cargo_bin not in parts:
            env["PATH"] = cargo_bin + (os.pathsep + current_path if current_path else "")
    if toolchain:
        env.setdefault("RUSTUP_TOOLCHAIN", toolchain)

    rustflags = compose_rustflags_from_combo(combo)
    env["RUSTFLAGS"] = rustflags

    msg1 = f"[Exp] {name}"
    msg2 = f"[Flags] {rustflags}"
    msg3 = f"[Bench] {bench_name}::{bench_filter or '*'} x{bench_repeat}"
    print(msg1)
    print(msg2)
    print(msg3)
    logf.write(msg1 + "\n")
    logf.write(msg2 + "\n")
    logf.write(msg3 + "\n")
    logf.flush()

    if not skip_clean:
        clean_project(env)

    ok, compile_time, exe_path = build_bench(env, bench_name, logf, log_cargo_output)
    if not ok:
        return [
            make_result_row(
                name=name,
                llvm_pass=llvm_pass,
                mir_pass=mir_pass,
                bench_name=bench_name,
                bench_filter=bench_filter,
                bench_repeat=bench_repeat,
                compile_time=compile_time,
                status=exe_path,
            )
        ]

    if not exe_path or not os.path.exists(exe_path):
        return [
            make_result_row(
                name=name,
                llvm_pass=llvm_pass,
                mir_pass=mir_pass,
                bench_name=bench_name,
                bench_filter=bench_filter,
                bench_repeat=bench_repeat,
                compile_time=compile_time,
                status="NoBinary",
            )
        ]

    try:
        size_bytes = os.path.getsize(exe_path)
    except Exception:
        size_bytes = 0

    for warmup_id in range(1, max(warmup_runs, 0) + 1):
        warmup_msg = f"[Exp] {name} Warmup {warmup_id}/{warmup_runs}"
        print(warmup_msg)
        logf.write(warmup_msg + "\n")
        logf.flush()
        wall_time, ns_per_iter, mbps, run_err = run_benchmark(exe_path, bench_filter, bench_args, bench_repeat)
        if wall_time is None:
            if run_err:
                logf.write("[RunError] " + run_err + "\n")
                logf.flush()
            logf.write("[SkipConfig] Warmup run failed\n")
            logf.flush()
            return []
        print(f"[WarmupResult] Size={size_bytes}B, Compile={compile_time:.6f}s, Wall={wall_time:.6f}s, NsPerIter={ns_per_iter}, MBps={mbps}")

    results = []
    for run_id in range(1, runs + 1):
        run_msg = f"[Exp] {name} Iteration {run_id}/{runs}"
        print(run_msg)
        logf.write(run_msg + "\n")
        logf.flush()

        wall_time, ns_per_iter, mbps, run_err = run_benchmark(exe_path, bench_filter, bench_args, bench_repeat)
        if wall_time is None:
            if run_err:
                logf.write("[RunError] " + run_err + "\n")
                logf.flush()
            results.append(
                make_result_row(
                    name=name,
                    llvm_pass=llvm_pass,
                    mir_pass=mir_pass,
                    bench_name=bench_name,
                    bench_filter=bench_filter,
                    bench_repeat=bench_repeat,
                    compile_time=compile_time,
                    status="RunFailed",
                    size=size_bytes,
                    run_id=run_id,
                )
            )
            break

        print(f"[Result] Size={size_bytes}B, Compile={compile_time:.6f}s, Wall={wall_time:.6f}s, NsPerIter={ns_per_iter}, MBps={mbps}")
        results.append(
            make_result_row(
                name=name,
                llvm_pass=llvm_pass,
                mir_pass=mir_pass,
                bench_name=bench_name,
                bench_filter=bench_filter,
                bench_repeat=bench_repeat,
                compile_time=compile_time,
                status="Success",
                size=size_bytes,
                run_id=run_id,
                total_runtime=wall_time,
                ns_per_iter=ns_per_iter,
                mbps=mbps,
            )
        )

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("config_file", nargs="?", default=DEFAULT_JSON_PATH)
    parser.add_argument("--json-path", default="")
    parser.add_argument("--toolchain", default=DEFAULT_TOOLCHAIN)
    parser.add_argument("--log-cargo-output", action="store_true")
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--start-exp", default="")
    parser.add_argument("--start-name", default="")
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--skip-clean", action="store_true")
    parser.add_argument("--bench-name", default="spawn")
    parser.add_argument("--bench-filter", default="")
    parser.add_argument("--bench-args", default="--bench --warm-up-time 1 --measurement-time 1 --sample-size 30 --noplot")
    parser.add_argument("--bench-repeat", type=int, default=1)
    parser.add_argument("--run-repeats", type=int, default=0)
    parser.add_argument("--warmup", type=int, default11)
    args = parser.parse_args()

    config_path = resolve_json_path(args.json_path.strip() or str(args.config_file))
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
    start_exp = args.start_exp.strip() or args.start_name.strip()
    start_index = 0
    if start_exp:
        found = find_combo_start_index(combos, start_exp)
        if found is None:
            raise SystemExit(f'--start-exp "{start_exp}" not found in combinations')
        start_index = found
    elif args.start > 0:
        start_index = args.start

    if start_index > 0:
        combos = combos[start_index:]
    if args.limit and args.limit > 0:
        combos = combos[: args.limit]

    bench_repeat = args.bench_repeat if args.bench_repeat > 0 else max(args.run_repeats, 1)
    bench_args = parse_bench_args(args.bench_args)

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
                    "NsPerIter",
                    "MBps",
                    "TotalRuntime(s)",
                    "CompileTime(s)",
                    "BenchName",
                    "BenchFilter",
                    "BenchRepeat",
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
                    bench_name=args.bench_name,
                    bench_filter=args.bench_filter.strip(),
                    bench_repeat=bench_repeat,
                    warmup_runs=args.warmup,
                    bench_args=bench_args,
                    logf=logf,
                    toolchain=args.toolchain,
                    log_cargo_output=args.log_cargo_output,
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
                "ns_mean",
                "ns_med",
                "ns_iqr",
                "mbps_mean",
                "mbps_med",
                "mbps_iqr",
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
                "ns_mean",
                "ns_med",
                "ns_iqr",
                "ns_iqr_ratio",
                "mbps_mean",
                "mbps_med",
                "mbps_iqr",
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

    inter = compute_interaction(summary, "ns_med", smaller_is_better=True)
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
