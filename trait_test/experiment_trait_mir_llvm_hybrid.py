import argparse
import csv
import json
import os
import shutil
import subprocess
import time
from collections import defaultdict
from datetime import datetime
from math import ceil
from statistics import mean, median


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)

PROJECT_ROOT = SCRIPT_DIR
DEFAULT_JSON_PATH = "/mnt/MIR_LLVM_Experiment/table/table_json/combined_experiment_matrix.json"
if not os.path.exists(DEFAULT_JSON_PATH):
    DEFAULT_JSON_PATH = os.path.join(REPO_ROOT, "table", "table_json", "combined_experiment_matrix.json")
DEFAULT_RESULTS_ROOT = os.path.join(PROJECT_ROOT, "results")

DEFAULT_BENCH_NAME = "trait_inline"
DEFAULT_BENCH_FILTERS = ["easy_case", "mir_dependent_case"]
DEFAULT_EASY_CASE_REPEAT = 100000
DEFAULT_MIR_DEPENDENT_CASE_REPEAT = 150000
WORKLOAD_LEN = 4096
WORKLOAD_ROUNDS = 64
WORKLOAD_BYTES_PER_ITER = WORKLOAD_LEN * 4 * WORKLOAD_ROUNDS
DEFAULT_TARGET_SECONDS = 10.0
DEFAULT_CALIBRATION_REPEAT = 5000
DEFAULT_MAX_BENCH_REPEAT = 200000


def get_combinations(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("combinations", [])


def get_combo_name(combo):
    return combo.get("name") or combo.get("Experiment_ID") or "Unknown"


def pick_baseline_combo(combos):
    for combo in combos:
        name = get_combo_name(combo)
        if name == "EXP_000_ALL_OFF":
            return combo
    for combo in combos:
        name = get_combo_name(combo)
        if name == "CORE_BASELINE":
            return combo
    return combos[0] if combos else None


def get_core4_combinations():
    return [
        {
            "name": "CORE_BASELINE",
            "group": "Baseline",
            "llvm": {"pass": "baseline", "switches": [], "parameters": {}},
            "mir": None,
        },
        {
            "name": "CORE_NO_MIR_INLINE",
            "group": "No-MIR-Inline",
            "llvm": {"pass": "baseline", "switches": [], "parameters": {}},
            "mir": {"pass": "Inline", "switches": ["-Inline"], "parameters": {}},
        },
        {
            "name": "CORE_NO_LLVM_INLINE_INSTCOMBINE",
            "group": "No-LLVM-Inline/InstCombine",
            "llvm": {"pass": "NoLLVM", "switches": ["--inline-threshold=0"], "parameters": {}},
            "mir": None,
            "RUSTFLAGS": "-C no-prepopulate-passes",
        },
        {
            "name": "CORE_DUAL_DISABLE",
            "group": "Dual-disable",
            "llvm": {"pass": "NoLLVM", "switches": ["--inline-threshold=0"], "parameters": {}},
            "mir": {"pass": "Inline", "switches": ["-Inline"], "parameters": {}},
            "RUSTFLAGS": "-C no-prepopulate-passes",
        },
    ]


def clean_project(env=None):
    target_dir = os.path.join(PROJECT_ROOT, "target")
    if os.path.exists(target_dir):
        try:
            shutil.rmtree(target_dir)
        except Exception:
            if env is None:
                env = os.environ.copy()
            subprocess.run(
                ["cargo", "clean"],
                cwd=PROJECT_ROOT,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )


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


def extract_ir_blocks(raw_text, wanted_substrings):
    blocks = []
    current = []
    keep = False
    for line in raw_text.splitlines(True):
        if line.startswith("; *** IR Dump After "):
            if current and keep:
                blocks.append("".join(current))
            current = [line]
            keep = any(s in line for s in wanted_substrings)
            continue
        if current:
            current.append(line)
    if current and keep:
        blocks.append("".join(current))
    return "".join(blocks)


def dump_ir_sample(combo, bench_name, base_out, logf, passes):
    name = get_combo_name(combo)
    group = combo.get("group") or "Matrix"
    ir_dir = os.path.join(base_out, "ir_samples")
    os.makedirs(ir_dir, exist_ok=True)

    env = os.environ.copy()
    cargo_bin = os.path.expanduser("~/.cargo/bin")
    if cargo_bin and cargo_bin not in env.get("PATH", ""):
        env["PATH"] = f"{cargo_bin}:{env.get('PATH', '')}"

    extra = [
        "-Z unstable-options",
        "-C symbol-mangling-version=legacy",
    ]
    for p in passes:
        extra.append(f"-C llvm-args=-print-after={p}")

    rustflags = compose_rustflags_from_combo(combo) + " " + " ".join(extra)
    env["RUSTFLAGS"] = rustflags

    msg = f"[IRSample] {name} ({group}) passes={','.join(passes)}"
    print(msg)
    logf.write(msg + "\n")
    logf.flush()

    clean_project(env)
    cmd = ["cargo", "+nightly", "build", "--release", "--bin", bench_name]
    r = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    raw_path = os.path.join(ir_dir, f"{name}__{group}__raw_ir_dump.txt")
    with open(raw_path, "w", encoding="utf-8") as f:
        f.write((r.stdout or "") + "\n")
        f.write(r.stderr or "")

    if r.returncode != 0:
        logf.write(f"[IRSampleError] rustc failed for {name} ({group})\n")
        logf.write((r.stderr or "").strip() + "\n")
        logf.flush()
        return False

    wanted = ["trait_test", "kernel_", "wrap_", "apply_", "transform"]
    filtered = extract_ir_blocks(r.stderr or "", wanted)
    filtered_path = os.path.join(ir_dir, f"{name}__{group}__filtered_ir_dump.txt")
    with open(filtered_path, "w", encoding="utf-8") as f:
        f.write(filtered)
    logf.write(f"[IRSampleSaved] raw={raw_path} filtered={filtered_path}\n")
    logf.flush()
    return True


def build_bench(env, bench_name, logf, retries=2):
    backoff = 0.5
    last_err = ""
    cmd = [
        "cargo",
        "+nightly",
        "build",
        "--release",
        "--bin",
        bench_name,
        "--quiet",
    ]
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
            return True, "Success", ""
        err = r.stderr or ""
        last_err = err
        logf.write(err + "\n")
        logf.flush()
        if ("Text file busy (os error 26)" in err) or ("never executed" in err):
            time.sleep(backoff)
            backoff = min(backoff * 2, 4.0)
            continue
        return False, "BuildFailed", err.strip()
    if ("Text file busy (os error 26)" in last_err) or ("never executed" in last_err) or ("failed to run custom build command" in last_err):
        return False, "Skipped", last_err.strip()
    return False, "BuildFailed", last_err.strip()


def find_bench_exe(bench_name):
    exe_path = os.path.join(PROJECT_ROOT, "target", "release", bench_name)
    if os.name == "nt":
        exe_path += ".exe"
    if os.path.isfile(exe_path) and os.access(exe_path, os.X_OK):
        return exe_path
    return None


def run_benchmark(exe_path, bench_filter, repeat):
    repeat = max(int(repeat), 1)
    last_err = ""
    t0 = time.perf_counter()
    p = subprocess.run(
        [exe_path, "--case", bench_filter, "--repeat", str(repeat)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    t1 = time.perf_counter()
    if p.returncode != 0:
        last_err = (p.stderr or "").strip()
        return None, "", "", last_err

    total_wall = t1 - t0
    if total_wall <= 0:
        return None, "", "", "Invalid wall time"

    ns_per_iter = (total_wall * 1_000_000_000.0) / float(repeat)
    mbps = (WORKLOAD_BYTES_PER_ITER * repeat) / (total_wall * 1_000_000.0)
    return total_wall, f"{ns_per_iter:.2f}", f"{mbps:.0f}", last_err


def prepare_combo_env(combo):
    env = os.environ.copy()
    cargo_bin = os.path.expanduser("~/.cargo/bin")
    if cargo_bin and cargo_bin not in env.get("PATH", ""):
        env["PATH"] = f"{cargo_bin}:{env.get('PATH', '')}"
    env["RUSTFLAGS"] = compose_rustflags_from_combo(combo)
    return env


def calibrate_case_repeats(combo, bench_name, bench_filters, target_seconds, probe_repeat, max_repeat, logf):
    repeats_by_case = {case: max(1, int(probe_repeat)) for case in bench_filters}
    if combo is None:
        return repeats_by_case
    if target_seconds is None or float(target_seconds) <= 0:
        return repeats_by_case

    name = get_combo_name(combo)
    env = prepare_combo_env(combo)

    msg = f"[Calibration] baseline={name} target={target_seconds:.3f}s probe_repeat={probe_repeat}"
    print(msg)
    logf.write(msg + "\n")
    logf.flush()

    clean_project(env)
    ok, status, build_err = build_bench(env, bench_name, logf)
    if not ok:
        logf.write(f"[CalibrationSkip] build failed: {status}\n")
        if build_err:
            logf.write("[CalibrationBuildError] " + build_err + "\n")
        logf.flush()
        return repeats_by_case

    exe_path = find_bench_exe(bench_name)
    if not exe_path:
        logf.write("[CalibrationSkip] no binary produced\n")
        logf.flush()
        return repeats_by_case

    warmup_repeat = max(1, min(int(probe_repeat), 500))
    for bench_filter in bench_filters:
        warmup_time, _, _, warmup_err = run_benchmark(exe_path, bench_filter, warmup_repeat)
        if warmup_time is None:
            if warmup_err:
                logf.write(f"[CalibrationWarmupError:{bench_filter}] " + warmup_err + "\n")
            logf.flush()
            continue

        wall_time, _, _, run_err = run_benchmark(exe_path, bench_filter, probe_repeat)
        if wall_time is None or wall_time <= 0:
            if run_err:
                logf.write(f"[CalibrationRunError:{bench_filter}] " + run_err + "\n")
            logf.flush()
            continue

        repeat = int(ceil(float(target_seconds) * float(probe_repeat) / float(wall_time)))
        repeat = max(1, min(int(max_repeat), repeat))
        repeats_by_case[bench_filter] = repeat

        detail = f"[CalibrationResult:{bench_filter}] wall={wall_time:.6f}s repeat={repeat}"
        print(detail)
        logf.write(detail + "\n")
        logf.flush()

    return repeats_by_case


def measure_combination(combo, runs, bench_name, bench_filters, repeats_by_case, logf):
    name = get_combo_name(combo)
    group = combo.get("group") or "Matrix"

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

    env = prepare_combo_env(combo)
    rustflags = env["RUSTFLAGS"]

    rows = []
    msg1 = f"[Exp] {name} Build + Warmup"
    msg2 = f"[Flags] {rustflags}"
    repeat_desc = ",".join(f"{case}:x{repeats_by_case.get(case, 1)}" for case in bench_filters)
    msg3 = f"[Bench] {bench_name}::{','.join(bench_filters)} {repeat_desc}"
    print(msg1)
    print(msg2)
    print(msg3)
    logf.write(msg1 + "\n")
    logf.write(msg2 + "\n")
    logf.write(msg3 + "\n")
    logf.flush()

    clean_project(env)

    t0 = time.perf_counter()
    ok, status, build_err = build_bench(env, bench_name, logf)
    t1 = time.perf_counter()
    compile_time = t1 - t0

    if not ok:
        logf.write(f"[SkipConfig] Build failed: {status}\n")
        if build_err:
            logf.write("[BuildError] " + build_err + "\n")
        logf.flush()
        for bench_filter in bench_filters:
            rows.append(
                {
                    "ConfigName": name,
                    "Group": group,
                    "Case": bench_filter,
                    "RunID": 1,
                    "LLVM_Pass": llvm_pass,
                    "MIR_Pass": mir_pass,
                    "BinarySize(Bytes)": 0,
                    "NsPerIter": "",
                    "MBps": "",
                    "TotalRuntime(s)": 0,
                    "CompileTime(s)": f"{compile_time:.6f}",
                    "Status": status,
                }
            )
        return rows

    exe_path = find_bench_exe(bench_name)
    if not exe_path:
        logf.write("[SkipConfig] Build produced no bench binary\n")
        logf.flush()
        for bench_filter in bench_filters:
            rows.append(
                {
                    "ConfigName": name,
                    "Group": group,
                    "Case": bench_filter,
                    "RunID": 1,
                    "LLVM_Pass": llvm_pass,
                    "MIR_Pass": mir_pass,
                    "BinarySize(Bytes)": 0,
                    "NsPerIter": "",
                    "MBps": "",
                    "TotalRuntime(s)": 0,
                    "CompileTime(s)": f"{compile_time:.6f}",
                    "Status": "NoBinary",
                }
            )
        return rows

    try:
        size = os.path.getsize(exe_path)
    except Exception:
        size = 0

    for bench_filter in bench_filters:
        bench_repeat = repeats_by_case.get(bench_filter, 1)
        warmup_msg = f"[Exp] {name} Warmup {bench_filter}"
        print(warmup_msg)
        logf.write(warmup_msg + "\n")
        logf.flush()

        wall_time, ns_per_iter, mbps, run_err = run_benchmark(exe_path, bench_filter, bench_repeat)
        if wall_time is None:
            if run_err:
                logf.write(f"[RunError:{bench_filter}] " + run_err + "\n")
                logf.flush()
            logf.write(f"[SkipConfig] Warmup run failed for {bench_filter}\n")
            logf.flush()
            return rows

        print(
            f"[WarmupResult:{bench_filter}] Size={size}B, Compile={compile_time:.6f}s, Wall={wall_time:.6f}s, NsPerIter={ns_per_iter}, MBps={mbps}"
        )

        for run_id in range(1, runs + 1):
            msg1 = f"[Exp] {name} {bench_filter} Iteration {run_id}/{runs}"
            msg2 = f"[Flags] {rustflags}"
            msg3 = f"[Bench] {bench_name}::{bench_filter} x{bench_repeat}"
            print(msg1)
            print(msg2)
            print(msg3)
            logf.write(msg1 + "\n")
            logf.write(msg2 + "\n")
            logf.write(msg3 + "\n")
            logf.flush()

            wall_time, ns_per_iter, mbps, run_err = run_benchmark(exe_path, bench_filter, bench_repeat)
            if wall_time is None:
                if run_err:
                    logf.write(f"[RunError:{bench_filter}] " + run_err + "\n")
                    logf.flush()
                rows.append(
                    {
                        "ConfigName": name,
                        "Group": group,
                        "Case": bench_filter,
                        "RunID": run_id,
                        "LLVM_Pass": llvm_pass,
                        "MIR_Pass": mir_pass,
                        "BinarySize(Bytes)": size,
                        "NsPerIter": "",
                        "MBps": "",
                        "TotalRuntime(s)": 0,
                        "CompileTime(s)": f"{compile_time:.6f}",
                        "Status": "RunFailed",
                    }
                )
                continue

            print(
                f"[Result:{bench_filter}] Size={size}B, Compile={compile_time:.6f}s, Wall={wall_time:.6f}s, NsPerIter={ns_per_iter}, MBps={mbps}"
            )
            rows.append(
                {
                    "ConfigName": name,
                    "Group": group,
                    "Case": bench_filter,
                    "RunID": run_id,
                    "LLVM_Pass": llvm_pass,
                    "MIR_Pass": mir_pass,
                    "BinarySize(Bytes)": size,
                    "NsPerIter": ns_per_iter,
                    "MBps": mbps,
                    "TotalRuntime(s)": f"{wall_time:.6f}",
                    "CompileTime(s)": f"{compile_time:.6f}",
                    "Status": "Success",
                }
            )

    return rows


def aggregate_summary(rows):
    by = defaultdict(list)
    for row in rows:
        if row.get("Status") != "Success":
            continue
        key = (row["Case"], row["ConfigName"], row["Group"])
        by[key].append(row)

    out = []
    for (case, cfg, group), rs in sorted(by.items()):
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
                "Case": case,
                "ConfigName": cfg,
                "Group": group,
                "n": str(len(rs)),
                "wall_mean": f"{avg_value('TotalRuntime(s)'):.6f}" if avg_value("TotalRuntime(s)") is not None else "",
                "wall_med": f"{med_value('TotalRuntime(s)'):.6f}" if med_value("TotalRuntime(s)") is not None else "",
                "wall_iqr": f"{iqr_value('TotalRuntime(s)'):.6f}" if iqr_value("TotalRuntime(s)") is not None else "",
                "compile_mean": f"{avg_value('CompileTime(s)'):.6f}" if avg_value("CompileTime(s)") is not None else "",
                "compile_med": f"{med_value('CompileTime(s)'):.6f}" if med_value("CompileTime(s)") is not None else "",
                "compile_iqr": f"{iqr_value('CompileTime(s)'):.6f}" if iqr_value("CompileTime(s)") is not None else "",
                "ns_mean": f"{avg_value('NsPerIter'):.6f}" if avg_value("NsPerIter") is not None else "",
                "ns_med": f"{med_value('NsPerIter'):.6f}" if med_value("NsPerIter") is not None else "",
                "ns_iqr": f"{iqr_value('NsPerIter'):.6f}" if iqr_value("NsPerIter") is not None else "",
                "mbps_mean": f"{avg_value('MBps'):.6f}" if avg_value("MBps") is not None else "",
                "mbps_med": f"{med_value('MBps'):.6f}" if med_value("MBps") is not None else "",
                "mbps_iqr": f"{iqr_value('MBps'):.6f}" if iqr_value("MBps") is not None else "",
                "size_mean": f"{avg_value('BinarySize(Bytes)', int):.6f}" if avg_value("BinarySize(Bytes)", int) is not None else "",
                "size_med": f"{med_value('BinarySize(Bytes)', int):.0f}" if med_value("BinarySize(Bytes)", int) is not None else "",
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
        ns_med = as_float(row.get("ns_med"))
        ns_iqr = as_float(row.get("ns_iqr"))
        mbps_med = as_float(row.get("mbps_med"))
        mbps_iqr = as_float(row.get("mbps_iqr"))

        wall_iqr_ratio = None
        if wall_med not in (None, 0.0) and wall_iqr is not None:
            wall_iqr_ratio = wall_iqr / wall_med

        compile_iqr_ratio = None
        if compile_med not in (None, 0.0) and compile_iqr is not None:
            compile_iqr_ratio = compile_iqr / compile_med

        ns_iqr_ratio = None
        if ns_med not in (None, 0.0) and ns_iqr is not None:
            ns_iqr_ratio = ns_iqr / ns_med

        mbps_iqr_ratio = None
        if mbps_med not in (None, 0.0) and mbps_iqr is not None:
            mbps_iqr_ratio = mbps_iqr / mbps_med

        out.append(
            {
                "Case": row["Case"],
                "ConfigName": row["ConfigName"],
                "Group": row["Group"],
                "n": row["n"],
                "wall_mean": row["wall_mean"],
                "wall_med": row["wall_med"],
                "wall_iqr": row["wall_iqr"],
                "wall_iqr_ratio": f"{wall_iqr_ratio:.6f}" if wall_iqr_ratio is not None else "",
                "compile_mean": row["compile_mean"],
                "compile_med": row["compile_med"],
                "compile_iqr": row["compile_iqr"],
                "compile_iqr_ratio": f"{compile_iqr_ratio:.6f}" if compile_iqr_ratio is not None else "",
                "ns_mean": row["ns_mean"],
                "ns_med": row["ns_med"],
                "ns_iqr": row["ns_iqr"],
                "ns_iqr_ratio": f"{ns_iqr_ratio:.6f}" if ns_iqr_ratio is not None else "",
                "mbps_mean": row["mbps_mean"],
                "mbps_med": row["mbps_med"],
                "mbps_iqr": row["mbps_iqr"],
                "mbps_iqr_ratio": f"{mbps_iqr_ratio:.6f}" if mbps_iqr_ratio is not None else "",
                "size_mean": row["size_mean"],
                "size_med": row["size_med"],
            }
        )

    def sort_key(row):
        ns_ratio = as_float(row["ns_iqr_ratio"])
        ns_iqr = as_float(row["ns_iqr"])
        wall_ratio = as_float(row["wall_iqr_ratio"])
        wall_iqr = as_float(row["wall_iqr"])
        return (
            ns_ratio if ns_ratio is not None else -1.0,
            ns_iqr if ns_iqr is not None else -1.0,
            wall_ratio if wall_ratio is not None else -1.0,
            wall_iqr if wall_iqr is not None else -1.0,
            row["Case"],
            row["ConfigName"],
        )

    out.sort(key=sort_key, reverse=True)
    return out


def compute_core4_interaction(summary_rows, metric_key, smaller_is_better=True):
    idx = {(row["Case"], row["ConfigName"]): row for row in summary_rows}
    out = []
    for case in sorted({row["Case"] for row in summary_rows}):
        def get(cfg):
            row = idx.get((case, cfg))
            if not row:
                return None
            value = row.get(metric_key, "")
            if value == "":
                return None
            try:
                return float(value)
            except Exception:
                return None

        baseline = get("CORE_BASELINE")
        no_mir_inline = get("CORE_NO_MIR_INLINE")
        no_llvm_inline_instcombine = get("CORE_NO_LLVM_INLINE_INSTCOMBINE")
        dual_disable = get("CORE_DUAL_DISABLE")
        if None in (baseline, no_mir_inline, no_llvm_inline_instcombine, dual_disable):
            continue

        effect = (lambda x: -x) if smaller_is_better else (lambda x: x)
        delta = (
            effect(baseline)
            - effect(no_mir_inline)
            - effect(no_llvm_inline_instcombine)
            + effect(dual_disable)
        )
        out.append(
            {
                "Case": case,
                "metric": metric_key,
                "delta": f"{delta:.6f}",
                "CORE_BASELINE": f"{baseline:.6f}",
                "CORE_NO_MIR_INLINE": f"{no_mir_inline:.6f}",
                "CORE_NO_LLVM_INLINE_INSTCOMBINE": f"{no_llvm_inline_instcombine:.6f}",
                "CORE_DUAL_DISABLE": f"{dual_disable:.6f}",
            }
        )
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("config_file", nargs="?", default=DEFAULT_JSON_PATH)
    parser.add_argument("--json-path", default="")
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--bench-name", default=DEFAULT_BENCH_NAME)
    parser.add_argument("--bench-repeat", type=int, default=0)
    parser.add_argument("--easy-repeat", type=int, default=DEFAULT_EASY_CASE_REPEAT)
    parser.add_argument("--mir-repeat", type=int, default=DEFAULT_MIR_DEPENDENT_CASE_REPEAT)
    parser.add_argument("--auto-calibrate", action="store_true")
    parser.add_argument("--target-seconds", type=float, default=DEFAULT_TARGET_SECONDS)
    parser.add_argument("--calibration-repeat", type=int, default=DEFAULT_CALIBRATION_REPEAT)
    parser.add_argument("--max-bench-repeat", type=int, default=DEFAULT_MAX_BENCH_REPEAT)
    parser.add_argument("--core4", action="store_true")
    parser.add_argument("--ir-sample-count", type=int, default=-1)
    parser.add_argument("--ir-passes", default="inline,instcombine")
    args = parser.parse_args()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_out = args.out_dir or args.output_dir or os.path.join(DEFAULT_RESULTS_ROOT, ts)
    os.makedirs(base_out, exist_ok=True)

    results_csv = os.path.join(base_out, "experiment_results.csv")
    summary_csv = os.path.join(base_out, "summary_medians.csv")
    inter_csv = os.path.join(base_out, "interaction_delta.csv")
    volatility_csv = os.path.join(base_out, "volatility_summary.csv")
    exec_log = os.path.join(base_out, "experiment_execution.log")

    config_path = args.json_path.strip() or args.config_file.strip()
    if args.core4:
        combos = get_core4_combinations()
    else:
        if not os.path.exists(config_path):
            print(f"Error: JSON path {config_path} does not exist.")
            return
        combos = get_combinations(config_path)
    if args.start > 0:
        combos = combos[args.start:]
    if args.limit and args.limit > 0:
        combos = combos[: args.limit]

    with open(exec_log, "w", encoding="utf-8") as logf:
        print(f"Total Rows: {len(combos)}")
        logf.write(f"Total Rows: {len(combos)}\n")
        logf.flush()

        if args.bench_repeat > 0:
            repeats_by_case = {case: int(args.bench_repeat) for case in DEFAULT_BENCH_FILTERS}
            logf.write(f"[RepeatMode] manual x{args.bench_repeat}\n")
            logf.flush()
        elif args.auto_calibrate:
            baseline_combo = pick_baseline_combo(combos)
            repeats_by_case = calibrate_case_repeats(
                combo=baseline_combo,
                bench_name=args.bench_name,
                bench_filters=DEFAULT_BENCH_FILTERS,
                target_seconds=args.target_seconds,
                probe_repeat=max(1, int(args.calibration_repeat)),
                max_repeat=max(1, int(args.max_bench_repeat)),
                logf=logf,
            )
        else:
            repeats_by_case = {
                "easy_case": max(1, int(args.easy_repeat)),
                "mir_dependent_case": max(1, int(args.mir_repeat)),
            }
            logf.write(
                f"[RepeatMode] fixed easy_case:x{repeats_by_case['easy_case']} "
                f"mir_dependent_case:x{repeats_by_case['mir_dependent_case']}\n"
            )
            logf.flush()

        passes = [p.strip() for p in args.ir_passes.split(",") if p.strip()]
        sample_count = args.ir_sample_count
        if sample_count < 0:
            sample_count = 4 if args.core4 else 0
        for combo in combos[:sample_count]:
            dump_ir_sample(combo, args.bench_name, base_out, logf, passes)

        with open(results_csv, "w", encoding="utf-8", newline="") as outcsv:
            writer = csv.DictWriter(
                outcsv,
                fieldnames=[
                    "ConfigName",
                    "Group",
                    "Case",
                    "RunID",
                    "LLVM_Pass",
                    "MIR_Pass",
                    "BinarySize(Bytes)",
                    "NsPerIter",
                    "MBps",
                    "TotalRuntime(s)",
                    "CompileTime(s)",
                    "Status",
                ],
            )
            writer.writeheader()
            outcsv.flush()

            for combo in combos:
                rows = measure_combination(
                    combo,
                    args.runs,
                    args.bench_name,
                    DEFAULT_BENCH_FILTERS,
                    repeats_by_case,
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
                "Case",
                "ConfigName",
                "Group",
                "n",
                "wall_mean",
                "wall_med",
                "wall_iqr",
                "compile_mean",
                "compile_med",
                "compile_iqr",
                "ns_mean",
                "ns_med",
                "ns_iqr",
                "mbps_mean",
                "mbps_med",
                "mbps_iqr",
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
                "Case",
                "ConfigName",
                "Group",
                "n",
                "wall_mean",
                "wall_med",
                "wall_iqr",
                "wall_iqr_ratio",
                "compile_mean",
                "compile_med",
                "compile_iqr",
                "compile_iqr_ratio",
                "ns_mean",
                "ns_med",
                "ns_iqr",
                "ns_iqr_ratio",
                "mbps_mean",
                "mbps_med",
                "mbps_iqr",
                "mbps_iqr_ratio",
                "size_mean",
                "size_med",
            ],
        )
        writer.writeheader()
        for row in volatility:
            writer.writerow(row)

    inter = []
    inter += compute_core4_interaction(summary, "wall_med", smaller_is_better=True)
    inter += compute_core4_interaction(summary, "ns_med", smaller_is_better=True)
    inter += compute_core4_interaction(summary, "mbps_med", smaller_is_better=False)
    if inter:
        with open(inter_csv, "w", encoding="utf-8", newline="") as outcsv:
            writer = csv.DictWriter(
                outcsv,
                fieldnames=[
                    "Case",
                    "metric",
                    "delta",
                    "CORE_BASELINE",
                    "CORE_NO_MIR_INLINE",
                    "CORE_NO_LLVM_INLINE_INSTCOMBINE",
                    "CORE_DUAL_DISABLE",
                ],
            )
            writer.writeheader()
            for row in inter:
                writer.writerow(row)

    print(base_out)


if __name__ == "__main__":
    main()
