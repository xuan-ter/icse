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


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)

PROJECT_ROOT = SCRIPT_DIR
DEFAULT_JSON_PATH = os.path.join(REPO_ROOT, "table", "table_json", "combined_experiment_matrix.json")
DEFAULT_RESULTS_ROOT = os.path.join(PROJECT_ROOT, "results")
DEFAULT_EXAMPLE_NAME = "decode"
DEFAULT_IMAGE_PATH = os.path.join(PROJECT_ROOT, "tests", "images", "exr", "cropping - uncropped original.exr")
DEFAULT_RECORD_REPEAT_MULTIPLIER = 5


def bench_build_cmd(example_name, quiet=False):
    cmd = ["cargo", "+nightly", "build", "--release", "--example", example_name]
    if quiet:
        cmd.append("--quiet")
    return cmd


def get_combinations(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("combinations", [])


def resolve_json_path(json_arg):
    candidate = (json_arg or "").strip()
    if not candidate:
        return DEFAULT_JSON_PATH
    if os.path.isdir(candidate):
        preferred = [
            os.path.join(candidate, "combined_experiment_matrix.json"),
            os.path.join(candidate, "table_json", "combined_experiment_matrix.json"),
        ]
        for path in preferred:
            if os.path.exists(path):
                return path
        matches = sorted(glob.glob(os.path.join(candidate, "**", "*.json"), recursive=True))
        if matches:
            return matches[0]
    return candidate


def resolve_image_path(image_arg):
    candidate = (image_arg or "").strip()
    if not candidate:
        return DEFAULT_IMAGE_PATH
    if os.path.isabs(candidate):
        return candidate
    candidates = [
        os.path.join(PROJECT_ROOT, candidate),
        os.path.join(PROJECT_ROOT, "tests", "images", candidate),
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return os.path.abspath(candidate)


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


def build_project(env, rustflags, example_name, logf, retries=2):
    env2 = dict(env)
    env2["RUSTFLAGS"] = rustflags
    env2["CARGO_INCREMENTAL"] = "0"

    backoff = 0.5
    last_err = ""
    t0 = time.perf_counter()
    for _ in range(retries + 1):
        r = subprocess.run(
            bench_build_cmd(example_name, quiet=True),
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


def get_exe_path(example_name):
    exe_path = os.path.join(PROJECT_ROOT, "target", "release", "examples", example_name)
    return exe_path if os.path.exists(exe_path) else None


def newest_llvm_ir_path(example_name):
    patterns = [
        os.path.join(PROJECT_ROOT, "target", "release", "examples", "deps", f"{example_name}-*.ll"),
        os.path.join(PROJECT_ROOT, "target", "release", "deps", "image-*.ll"),
        os.path.join(PROJECT_ROOT, "target", "release", "deps", "image_*-.ll"),
    ]
    candidates = []
    for pattern in patterns:
        candidates.extend(glob.glob(pattern))
    if not candidates:
        candidates.extend(glob.glob(os.path.join(PROJECT_ROOT, "target", "release", "deps", "*.ll")))
    if not candidates:
        return ""
    candidates = sorted(set(candidates), key=lambda path: os.path.getmtime(path), reverse=True)
    return candidates[0]


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
            stripped = line.strip()
            if not stripped:
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
            if stripped.endswith(":") and not stripped.startswith(";") and "!" not in stripped:
                metrics["IR_bb"] += 1
    return metrics


def run_benchmark_once(exe_path, image_path):
    t0 = time.perf_counter()
    p = subprocess.run(
        [exe_path, image_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    t1 = time.perf_counter()
    if p.returncode != 0:
        err = (p.stderr or p.stdout or "RunFailed")[:2000]
        return None, err
    output = (p.stdout or "").strip()
    if not output:
        return None, "Example produced no output"
    if not re.fullmatch(r"\d+", output.splitlines()[-1].strip()):
        return None, f"Unexpected example output: {output[:200]}"
    return t1 - t0, ""


def run_benchmark_repeated(exe_path, image_path, repeats):
    repeats = int(repeats) if repeats is not None else 1
    repeats = max(1, repeats)
    total = 0.0
    for _ in range(repeats):
        elapsed, err = run_benchmark_once(exe_path, image_path)
        if elapsed is None:
            return None, err
        total += elapsed
    return total, ""


def pick_baseline_combo(combos):
    for combo in combos:
        name = combo.get("name") or combo.get("Experiment_ID") or ""
        if name == "EXP_DBL_000_BASELINE":
            return combo
    for combo in combos:
        name = combo.get("name") or combo.get("Experiment_ID") or ""
        if name == "EXP_000_ALL_OFF":
            return combo
    return combos[0] if combos else None


def calibrate_repeats(env_base, baseline_combo, example_name, image_path, target_seconds, max_repeats, skip_clean, logf):
    if not baseline_combo:
        return 15
    if target_seconds is None or float(target_seconds) <= 0:
        return 15

    rustflags = compose_rustflags_from_combo(baseline_combo)
    if not skip_clean:
        clean_project(env_base)
    ok, _, _, status = build_project(env_base, rustflags, example_name, logf)
    if not ok:
        if logf is not None:
            logf.write(f"[Calibrate] baseline build failed with status={status}\n")
            logf.flush()
        return 1

    exe_path = get_exe_path(example_name)
    if not exe_path:
        return 1

    elapsed, _ = run_benchmark_once(exe_path, image_path)
    if elapsed is None or elapsed <= 0:
        return 1
    repeats = int(ceil(float(target_seconds) / float(elapsed)))
    return max(1, min(int(max_repeats), repeats))


def aggregate_summary(rows):
    by = defaultdict(list)
    for row in rows:
        key = (row["Variant"], row["ConfigName"])
        if row["Status"] != "Success":
            continue
        by[key].append(row)

    out = []
    for (variant, config_name), grouped_rows in sorted(by.items()):
        def values(key, cast=float):
            parsed = []
            for row in grouped_rows:
                try:
                    parsed.append(cast(row[key]))
                except Exception:
                    pass
            return sorted(parsed)

        def percentile(parsed, p):
            if not parsed:
                return None
            if len(parsed) == 1:
                return float(parsed[0])
            pos = (len(parsed) - 1) * p
            lo = int(pos)
            hi = min(lo + 1, len(parsed) - 1)
            frac = pos - lo
            return float(parsed[lo]) * (1.0 - frac) + float(parsed[hi]) * frac

        def iqr(key, cast=float):
            parsed = values(key, cast)
            if not parsed:
                return None
            q1 = percentile(parsed, 0.25)
            q3 = percentile(parsed, 0.75)
            if q1 is None or q3 is None:
                return None
            return q3 - q1

        runtime_values = values("TotalRuntime(s)")
        compile_values = values("CompileTime(s)")
        size_values = values("BinarySize(Bytes)", int)
        alloca_values = values("IR_alloca", int)
        load_values = values("IR_load", int)
        store_values = values("IR_store", int)
        gep_values = values("IR_gep", int)
        phi_values = values("IR_phi", int)
        bb_values = values("IR_bb", int)
        run_repeats_values = values("RunRepeats", int)

        out.append(
            {
                "Variant": variant,
                "ConfigName": config_name,
                "n": str(len(grouped_rows)),
                "runtime_mean": f"{mean(runtime_values):.6f}" if runtime_values else "",
                "runtime_med": f"{median(runtime_values):.6f}" if runtime_values else "",
                "runtime_iqr": f"{iqr('TotalRuntime(s)'):.6f}" if iqr("TotalRuntime(s)") is not None else "",
                "compile_mean": f"{mean(compile_values):.6f}" if compile_values else "",
                "compile_med": f"{median(compile_values):.6f}" if compile_values else "",
                "compile_iqr": f"{iqr('CompileTime(s)'):.6f}" if iqr("CompileTime(s)") is not None else "",
                "size_mean": f"{mean(size_values):.6f}" if size_values else "",
                "size_med": f"{median(size_values):.0f}" if size_values else "",
                "alloca_mean": f"{mean(alloca_values):.6f}" if alloca_values else "",
                "alloca_med": f"{median(alloca_values):.0f}" if alloca_values else "",
                "load_mean": f"{mean(load_values):.6f}" if load_values else "",
                "load_med": f"{median(load_values):.0f}" if load_values else "",
                "store_mean": f"{mean(store_values):.6f}" if store_values else "",
                "store_med": f"{median(store_values):.0f}" if store_values else "",
                "gep_mean": f"{mean(gep_values):.6f}" if gep_values else "",
                "gep_med": f"{median(gep_values):.0f}" if gep_values else "",
                "phi_mean": f"{mean(phi_values):.6f}" if phi_values else "",
                "phi_med": f"{median(phi_values):.0f}" if phi_values else "",
                "bb_mean": f"{mean(bb_values):.6f}" if bb_values else "",
                "bb_med": f"{median(bb_values):.0f}" if bb_values else "",
                "run_repeats_med": f"{median(run_repeats_values):.0f}" if run_repeats_values else "",
            }
        )
    return out


def compute_interaction(summary_rows, metric_key, smaller_is_better=True):
    index = {(row["Variant"], row["ConfigName"]): row for row in summary_rows}
    out = []
    for variant in sorted({row["Variant"] for row in summary_rows}):
        def get(config_name):
            row = index.get((variant, config_name))
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
                "run_repeats_med": row.get("run_repeats_med", ""),
            }
        )

    out.sort(
        key=lambda row: (
            as_float(row["runtime_iqr_ratio"]) if as_float(row["runtime_iqr_ratio"]) is not None else -1.0,
            as_float(row["runtime_iqr"]) if as_float(row["runtime_iqr"]) is not None else -1.0,
            as_float(row["compile_iqr_ratio"]) if as_float(row["compile_iqr_ratio"]) is not None else -1.0,
            as_float(row["compile_iqr"]) if as_float(row["compile_iqr"]) is not None else -1.0,
            row["Variant"],
            row["ConfigName"],
        ),
        reverse=True,
    )
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("config_file", nargs="?", default=DEFAULT_JSON_PATH)
    parser.add_argument("--json-path", default="")
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--target-seconds", type=float, default=0)
    parser.add_argument("--max-repeats", type=int, default=2000)
    parser.add_argument("--out-dir", default="")
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--skip-clean", action="store_true")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--start-name", default="")
    parser.add_argument("--example-name", default=DEFAULT_EXAMPLE_NAME)
    parser.add_argument("--image-path", default=DEFAULT_IMAGE_PATH)
    parser.add_argument("--variant-name", default="")
    parser.add_argument("--record-repeat-multiplier", type=int, default=DEFAULT_RECORD_REPEAT_MULTIPLIER)
    args = parser.parse_args()

    config_path = resolve_json_path(args.json_path.strip() or str(args.config_file))
    image_path = resolve_image_path(args.image_path)
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image path does not exist: {image_path}")

    combos = get_combinations(config_path)
    start_idx = find_start_index_by_name(combos, args.start_name)
    if start_idx is not None:
        combos = combos[start_idx:]

    start = max(int(args.start), 0)
    if int(args.limit) > 0:
        combos = combos[start : start + int(args.limit)]
    else:
        combos = combos[start:]

    variant_name = args.variant_name.strip() or os.path.relpath(image_path, PROJECT_ROOT).replace(os.sep, "/")
    variant_name = f"{args.example_name}:{variant_name}"

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = args.out_dir.strip() or args.output_dir.strip() or os.path.join(DEFAULT_RESULTS_ROOT, f"run_{ts}")
    os.makedirs(out_dir, exist_ok=True)

    results_csv = os.path.join(out_dir, "experiment_results.csv")
    summary_csv = os.path.join(out_dir, "summary_medians.csv")
    inter_csv = os.path.join(out_dir, "interaction_delta.csv")
    volatility_csv = os.path.join(out_dir, "volatility_summary.csv")
    exec_log = os.path.join(out_dir, "experiment_execution.log")

    env_base = os.environ.copy()
    cargo_bin = os.path.expanduser("~/.cargo/bin")
    if cargo_bin and cargo_bin not in env_base.get("PATH", ""):
        env_base["PATH"] = f"{cargo_bin}:{env_base.get('PATH', '')}"

    baseline_combo = pick_baseline_combo(combos)

    with open(exec_log, "w", encoding="utf-8") as logf:
        logf.write(f"Total Rows: {len(combos)}\n")
        logf.write(f"[Benchmark] example={args.example_name} image={image_path}\n")
        logf.flush()

        base_run_repeats = calibrate_repeats(
            env_base=env_base,
            baseline_combo=baseline_combo,
            example_name=args.example_name,
            image_path=image_path,
            target_seconds=args.target_seconds,
            max_repeats=args.max_repeats,
            skip_clean=args.skip_clean,
            logf=logf,
        )
        record_repeat_multiplier = max(int(args.record_repeat_multiplier), 1)
        run_repeats = max(1, base_run_repeats * record_repeat_multiplier)
        logf.write(
            f"[RepeatPlan] base_repeats={base_run_repeats} multiplier={record_repeat_multiplier} total_repeats={run_repeats}\n"
        )
        logf.flush()

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

        all_rows = []
        with open(results_csv, "w", encoding="utf-8", newline="") as outcsv:
            writer = csv.DictWriter(outcsv, fieldnames=fields)
            writer.writeheader()

            for combo in combos:
                name = combo.get("name") or combo.get("Experiment_ID") or "Unknown"
                llvm_pass, mir_pass = labels_from_combo(combo)
                rustflags = compose_rustflags_from_combo(combo)
                warmup_count = max(args.warmup, 0)
                run_count = max(args.runs, 1)

                msg1 = f"[Build] {name}"
                msg2 = f"[Flags] {rustflags}"
                msg3 = f"[Input] {image_path}"
                print(msg1)
                print(msg2)
                print(msg3)
                logf.write(msg1 + "\n")
                logf.write(msg2 + "\n")
                logf.write(msg3 + "\n")
                logf.flush()

                if not args.skip_clean:
                    clean_project(env_base)

                ok, compile_time, _, status = build_project(env_base, rustflags, args.example_name, logf)
                if not ok:
                    for run_id in range(1, run_count + 1):
                        row = {
                            "ConfigName": name,
                            "Variant": variant_name,
                            "RunID": run_id,
                            "LLVM_Pass": llvm_pass,
                            "MIR_Pass": mir_pass,
                            "BinarySize(Bytes)": 0,
                            "TotalRuntime(s)": 0,
                            "CompileTime(s)": f"{compile_time:.6f}",
                            "IR_alloca": 0,
                            "IR_load": 0,
                            "IR_store": 0,
                            "IR_gep": 0,
                            "IR_phi": 0,
                            "IR_bb": 0,
                            "LLVM_IR_Path": "",
                            "RunRepeats": run_repeats,
                            "TargetSeconds": f"{float(args.target_seconds):.6f}",
                            "Status": status,
                        }
                        writer.writerow(row)
                        all_rows.append(row)
                    outcsv.flush()
                    continue

                exe_path = get_exe_path(args.example_name)
                if not exe_path:
                    for run_id in range(1, run_count + 1):
                        row = {
                            "ConfigName": name,
                            "Variant": variant_name,
                            "RunID": run_id,
                            "LLVM_Pass": llvm_pass,
                            "MIR_Pass": mir_pass,
                            "BinarySize(Bytes)": 0,
                            "TotalRuntime(s)": 0,
                            "CompileTime(s)": f"{compile_time:.6f}",
                            "IR_alloca": 0,
                            "IR_load": 0,
                            "IR_store": 0,
                            "IR_gep": 0,
                            "IR_phi": 0,
                            "IR_bb": 0,
                            "LLVM_IR_Path": "",
                            "RunRepeats": run_repeats,
                            "TargetSeconds": f"{float(args.target_seconds):.6f}",
                            "Status": "NoBinary",
                        }
                        writer.writerow(row)
                        all_rows.append(row)
                    outcsv.flush()
                    continue

                try:
                    size = os.path.getsize(exe_path)
                except Exception:
                    size = 0

                ll_path = newest_llvm_ir_path(args.example_name)
                ir_metrics = count_llvm_ir_metrics(ll_path)

                for warmup_id in range(warmup_count):
                    warmup_msg = f"[Warmup] {name} {warmup_id + 1}/{warmup_count} x{run_repeats}"
                    print(warmup_msg)
                    logf.write(warmup_msg + "\n")
                    logf.flush()
                    wall_time, err = run_benchmark_repeated(exe_path, image_path, run_repeats)
                    if wall_time is None:
                        print(f"[Warmup] Failed for {name}: {err}")
                        logf.write(f"[WarmupError] {err}\n")
                        logf.flush()
                        break

                for run_id in range(1, run_count + 1):
                    run_msg = f"[Run] {name} {run_id}/{run_count} x{run_repeats}"
                    print(run_msg)
                    logf.write(run_msg + "\n")
                    logf.flush()

                    wall_time, err = run_benchmark_repeated(exe_path, image_path, run_repeats)
                    if wall_time is None:
                        row = {
                            "ConfigName": name,
                            "Variant": variant_name,
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
                            "TargetSeconds": f"{float(args.target_seconds):.6f}",
                            "Status": "RunFailed",
                        }
                        writer.writerow(row)
                        all_rows.append(row)
                        logf.write(f"[RunError] {err}\n")
                        logf.flush()
                        continue

                    row = {
                        "ConfigName": name,
                        "Variant": variant_name,
                        "RunID": run_id,
                        "LLVM_Pass": llvm_pass,
                        "MIR_Pass": mir_pass,
                        "BinarySize(Bytes)": size,
                        "TotalRuntime(s)": f"{wall_time:.6f}",
                        "CompileTime(s)": f"{compile_time:.6f}",
                        "IR_alloca": ir_metrics["IR_alloca"],
                        "IR_load": ir_metrics["IR_load"],
                        "IR_store": ir_metrics["IR_store"],
                        "IR_gep": ir_metrics["IR_gep"],
                        "IR_phi": ir_metrics["IR_phi"],
                        "IR_bb": ir_metrics["IR_bb"],
                        "LLVM_IR_Path": ll_path,
                        "RunRepeats": run_repeats,
                        "TargetSeconds": f"{float(args.target_seconds):.6f}",
                        "Status": "Success",
                    }
                    writer.writerow(row)
                    all_rows.append(row)
                    outcsv.flush()

        summary_rows = aggregate_summary(all_rows)
        with open(summary_csv, "w", encoding="utf-8", newline="") as f:
            if summary_rows:
                writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
                writer.writeheader()
                writer.writerows(summary_rows)
            else:
                writer = csv.writer(f)
                writer.writerow(["Variant", "ConfigName", "n"])

        volatility_rows = build_volatility_summary(summary_rows)
        with open(volatility_csv, "w", encoding="utf-8", newline="") as f:
            if volatility_rows:
                writer = csv.DictWriter(f, fieldnames=list(volatility_rows[0].keys()))
                writer.writeheader()
                writer.writerows(volatility_rows)
            else:
                writer = csv.writer(f)
                writer.writerow(["Variant", "ConfigName", "n"])

        interaction_rows = compute_interaction(summary_rows, "runtime_med", smaller_is_better=True)
        with open(inter_csv, "w", encoding="utf-8", newline="") as f:
            if interaction_rows:
                writer = csv.DictWriter(f, fieldnames=list(interaction_rows[0].keys()))
                writer.writeheader()
                writer.writerows(interaction_rows)
            else:
                writer = csv.writer(f)
                writer.writerow(["Variant", "metric", "delta"])

    print(out_dir)


if __name__ == "__main__":
    main()
