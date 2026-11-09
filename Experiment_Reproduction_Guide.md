# Experiment Reproduction Guide

## 1. Purpose

This guide describes how to reproduce the MIR/LLVM interaction experiment in the current `D:\MIR_LLVM_NEW` workspace. It reflects the scripts and data-processing conventions currently present in the repository and covers three stages:

1. Run project-level experiments and produce `results\<timestamp>\experiment_results.csv`.
2. Run project-level DiD analysis and produce `interaction_results.csv` and plots.
3. Aggregate interaction results across projects into `interaction_summary.csv` and `interaction_summary_zh.csv`.

The current default analysis conventions are:

- Bootstrap DiD on `log(runtime)`.
- An interaction is significant when `BH-adjusted p < 0.05` and the `95% bootstrap CI excludes 0`.
- For some projects, normalize the baseline recorded in the raw data as `LLVM_Pass=None, MIR_Pass=All` to `(None, None)` for analysis.

## 2. Directory Layout

The workspace is organized approximately as follows:

```text
D:\MIR_LLVM_NEW\
  <project>\
    experiment_*.py
    results\
    analysis\did\
    analysis_new\did\

  datas\interaction_stats\
    summarize_interactions.py
    interaction_summary.csv
    interaction_summary_zh.csv
```

Representative experiment entry-point scripts currently in the workspace include:

- `bat\experiment_bat_mir_llvm_hybrid.py`
- `eza\experiment_eza_mir_llvm_hybrid.py`
- `ripgrep\experiment_rg_mir_llvm_hybrid.py`
- `hyper\experiment_hyper_mir_llvm_hybrid.py`
- `rustls\experiment_rustls_mir_llvm_hybrid.py`
- `quinn\experiment_quinn_mir_llvm_hybrid.py`
- `aho-corasick\experiment_aho_mir_llvm_hybrid.py`
- `loop_hoisting_bench\experiment_loop_mir_llvm_hybrid.py`

### 2.1 Pass List and Experiment Matrix

The `pass_filter` directory contains the pass list and machine-readable experiment matrix used in this experiment:

- `pass_filter\pass.txt`: A human-readable list of the 20 MIR passes and 83 LLVM passes selected for the experiment, together with their disable switches. MIR passes use switches in the form `-PassName`; LLVM passes use `-disable-pass-name`.
- `pass_filter\combined_experiment_matrix.json`: The machine-readable matrix stored under `pass_filter`. Its top-level fields are `description` and `combinations`. Each combination has `name`, `description`, `mir`, and `llvm` fields; the `mir` and `llvm` objects contain pass names, `switches`, and `parameters`.

`pass_filter\combined_experiment_matrix.json` contains 1,765 combinations:

- 20 single-factor MIR ablation combinations;
- 83 single-factor LLVM ablation combinations;
- 1 `EXP_DBL_000_BASELINE` baseline combination;
- 1,660 MIR×LLVM two-factor combinations (20 × 83);
- 1 special `EXP_001_DISABLE_ALL` combination that disables all LLVM controls.

Use `pass.txt` to check pass names and switches. Note that `pass_filter\combined_experiment_matrix.json` and `table\table_json\combined_experiment_matrix.json` are different files: the former has 1,765 entries, while the latter has 1,766 and includes the additional `EXP_000_ALL_OFF` entry. Many project scripts currently default to the file under `table\table_json`, but the actual input is determined by the target script's `DEFAULT_JSON_PATH` or command-line arguments. The paper reports 1,766 configurations, matching the count in the `table\table_json` file. Record the actual matrix path and its SHA-256 hash for every run, then check results against the configuration names in that file. Do not treat the two matrix sizes as interchangeable.

### 2.2 The 12 Real-World Projects and Their Versions

The 12 real-world Rust workloads listed in Table II of the paper correspond to project directories in the current workspace. The package versions below are the main package versions resolved from each project's root Cargo workspace using `cargo metadata --locked --offline --no-deps`; they can be verified against the current experiment copy. The paper says that its artifact also records benchmark revisions; those revisions should be retrieved from the artifact when exact source recovery is required.

| Paper project | Main Cargo package | Package version in experiment copy | Local verification location |
| --- | --- | --- | --- |
| image | image | 0.25.9 | `image\Cargo.toml`, `image\.git_embedded_backup` |
| fast_image_resize | fast_image_resize | 6.0.0 | `fast_image_resize\Cargo.toml`, `fast_image_resize\.git_embedded_backup` |
| ripgrep | ripgrep | 15.1.0 | `ripgrep\Cargo.toml`, `ripgrep\Cargo.lock` |
| bat | bat | 0.26.1 | `bat\Cargo.toml`, `bat\Cargo.lock` |
| eza | eza | 0.23.4 | `eza\Cargo.toml`, `eza\Cargo.lock` |
| serde | serde | 1.0.228 | `serde\serde\Cargo.toml`, `serde\.git` |
| aho-corasick | aho-corasick | 1.1.4 | `aho-corasick\Cargo.toml`, `aho-corasick\.git_embedded_backup` |
| regex | regex | 1.12.3 | `regex\Cargo.toml`, `regex\Cargo.lock` |
| tokio | tokio | 1.50.0 | `tokio\tokio\Cargo.toml`, `tokio\Cargo.lock` |
| hyper | hyper | 1.8.1 | `hyper\Cargo.toml`, `hyper\Cargo.lock` |
| rustls | rustls | 0.24.0-dev.0 | `rustls\rustls\Cargo.toml`, `rustls\.git_embedded_backup` |
| quinn | quinn | 0.12.0 | `quinn\Cargo.toml`, `quinn\.git_embedded_backup` |

The package versions and local verification paths above come from the current experiment directories. Upstream repositories: [image-rs/image](https://github.com/image-rs/image), [fast_image_resize](https://github.com/cykooz/fast_image_resize), [ripgrep](https://github.com/BurntSushi/ripgrep), [bat](https://github.com/sharkdp/bat), [eza](https://github.com/eza-community/eza), [serde](https://github.com/serde-rs/serde), [aho-corasick](https://github.com/BurntSushi/aho-corasick), [regex](https://github.com/rust-lang/regex), [tokio](https://github.com/tokio-rs/tokio), [hyper](https://github.com/hyperium/hyper), [rustls](https://github.com/rustls/rustls), and [quinn](https://github.com/quinn-rs/quinn). To reproduce the exact source used for the paper, retrieve the benchmark revisions recorded in the anonymous artifact referenced by the paper's Data Availability statement: https://anonymous.4open.science/r/icse-2BF2. Archive those revisions alongside package versions and the corresponding raw results.

### 2.3 Default Workloads in the Current Scripts

The table below summarizes the defaults visible in the scripts and benchmarks in the current experiment copy. It is intended to help verify that each script points to the expected input. These defaults may not match the complete parameters used in the paper: source revisions, command-line overrides, and generated data can all change them. For a formal reproduction, use the commands and benchmark revisions in the paper artifact, and record data-generation commands, random seeds, and file hashes.

| Project | Benchmark / default workload in current copy | Parameters or inputs to record |
| --- | --- | --- |
| image | `decode`; EXR fixture: `tests/images/exr/cropping - uncropped original.exr` | Fixture hash and format-decoding options |
| fast_image_resize | `bench_resize` | Runner defaults: `--runs=6`, sample size 10, warm-up time 0, and measurement time 0. These are different measurement levels from the paper's 10 independent measurements per configuration and must not be treated as equivalent. |
| ripgrep | Search for `Sherlock` in a generated file of approximately 1 GiB | Input-generation method, file size/hash, and search arguments |
| bat | Syntax-highlight a generated Rust source file of approximately 10 MiB | Input-file hash and terminal/output-format options |
| eza | List a directory; runner default path is `/root/MIR_LLVM/bat`; repeat 500 times | On Windows, pass a valid `--list-path` explicitly; record directory contents and filesystem state. |
| serde | `test_ser`; enable the `unstable` feature; `test-repeat` is 1000 | Test filter, feature set, and test repetition count |
| aho-corasick | `words5000`, `default/standard`; uses the Sherlock benchmark definition by default | Benchmark definition, word list/input, and hashes |
| regex | `regex-cli find match regex --no-utf8-syntax -p Sherlock`; run against a generated file of approximately 500 MiB | File-generation method, command arguments, and input hash |
| tokio | Criterion `spawn` benchmark | Defaults: 1 s warm-up, 1 s measurement, sample size 30; record the runner's outer repetitions separately. |
| hyper | `end_to_end`; filter `http1_consecutive_x1_both_100mb` | HTTP/1 configuration, concurrency/connection parameters, and request-body size |
| rustls | `rustls-bench` with the `ring` feature; defaults to `handshake`, TLS 1.3 AES-128-GCM, multiplier 10, 1 thread, API `both` | Cipher suite, API, thread count, multiplier, and mode |
| quinn | `bulk` binary in the `bench` package; downloads 64 MiB by default and uploads nothing | `--bench-args`, download/upload sizes, and network/local endpoint configuration |

These defaults describe the current copy. Changes to the runner, upstream source, or command-line arguments can alter the workload. Confirm that workloads match before comparing results across machines.

## 3. Environment Setup

### 3.1 Python Environment

The analysis scripts currently depend on these Python packages:

- `pandas`
- `numpy`
- `matplotlib`
- `seaborn`
- `networkx`
- `Pillow`

Recommended setup:

```powershell
cd D:\MIR_LLVM_NEW
.\.venv\Scripts\activate
pip install pandas numpy matplotlib seaborn networkx pillow
```

### 3.2 Rust Environment

The raw experiment scripts repeatedly build Rust projects and use custom MIR/LLVM settings. At minimum, install:

- `rustup`
- `cargo`
- A `nightly` toolchain

Check the installation with:

```powershell
rustup show
cargo --version
rustc +nightly --version
```

### 3.3 Platform Notes

The current workspace runs on Windows, but some older scripts still contain hard-coded Linux paths. The `ripgrep`, `bat`, `eza`, `regex`, and `quinn` runners are confirmed to contain `/root/MIR_LLVM` paths. Before running them, replace these with paths on the current machine or use supported path arguments. The `eza` runner also requires an explicit `--list-path` value.

### 3.4 Paper Environment and Current Workstation

The paper describes a cloud x86-64 machine with an Intel Xeon Gold 5318Y, 14 GB of memory, and 100 GB of disk. The experiment used a fixed Rust nightly toolchain, built with `cargo +nightly build --release`, set `CARGO_INCREMENTAL=0`, and ran `cargo clean` before a clean build for each configuration. Each configuration had one warm-up followed by 10 independent measurements. Internal benchmark repetitions were calibrated against the baseline and held constant within each workload variant. The 10 measurements are outer independent measurements; they are not the same as a Criterion sample size, `test-repeat`, or runner-internal iterations.

The workstation check recorded on 2026-11-06 reports Windows NT `10.0.19045.0` and Rust host `x86_64-pc-windows-msvc`. `rustc +nightly -Vv` reports `1.101.0-nightly`, commit `75a75c3e0a67d3fa3d03982775f5bb0356e7b510`, and LLVM `23.1.1`; `cargo +nightly -V` reports `1.101.0-nightly (3d7cf6e93 2026-09-25)`. These are current workstation values, not the historical environment or nightly version used for the paper. The current workstation's CPU model and memory capacity have not yet been verified and should be added to reproduction records. Obtain the exact nightly, OS image, target triple, and benchmark revisions used for the paper from its artifact; do not infer them from the current installation.

## 4. End-to-End Workflow

The standard reproduction order is:

1. Run the raw experiment script for the target project.
2. Run the project's DiD analysis script.
3. Check the project-level outputs.
4. Run the cross-project aggregation script.
5. Check the summary tables.

## 5. Step 1: Run the Raw Experiment

### 5.1 What the Raw Experiment Script Does

The project-level experiment scripts generally:

- Read a MIR/LLVM configuration matrix from JSON.
- Rebuild the project for each configuration.
- Run the benchmark repeatedly.
- Record runtime, build time, binary size, configuration name, pass labels, and status.
- Write results to a `results\<timestamp>` directory.

### 5.2 rustls Script Arguments

The main arguments currently supported by `rustls\experiment_rustls_mir_llvm_hybrid.py` include:

- `--toolchain`
- `--runs`
- `--limit`
- `--start`
- `--start-name`
- `--mode`
- `--cipher-suite`
- `--multiplier`
- `--threads`
- `--api`
- `--run-repeats`
- `--warmup`

### 5.3 quinn Script Arguments

The main arguments currently supported by `quinn\experiment_quinn_mir_llvm_hybrid.py` include:

- `--runs`
- `--limit`
- `--start`
- `--start-exp`
- `--run-repeats`
- `--warmup`
- `--bench-args`

### 5.4 rustls Run Example

```powershell
cd D:\MIR_LLVM_NEW\rustls
python .\experiment_rustls_mir_llvm_hybrid.py `
  --toolchain nightly `
  --runs 10 `
  --mode handshake `
  --cipher-suite TLS13_AES_128_GCM_SHA256 `
  --multiplier 10 `
  --threads 1 `
  --api both `
  --run-repeats 1 `
  --warmup 1
```

Typical outputs include:

- `results\<timestamp>\experiment_results.csv`
- `results\<timestamp>\summary_medians.csv`
- `results\<timestamp>\volatility_summary.csv`
- `results\<timestamp>\experiment_execution.log`

### 5.5 Measurement Counts and Run Metadata

The paper's measurement method has at least three levels that should be recorded separately: warm-up count per configuration, the number of outer independent measurements, and the internal repetitions or sampling parameters used by the workload/benchmark itself. To match the paper, the target is one warm-up plus 10 independent measurements per configuration. However, project-specific arguments such as `--runs`, `--run-repeats`, Criterion sample size, or test-framework repetition options can mean different things. Do not infer compliance with the paper's method from any single parameter. Preserve the individual measurement records rather than archiving only median summaries.

For each run, save a `run_metadata` file (JSON or CSV) in the result directory with at least:

- Date, OS version, CPU model/core count, memory, complete Rust/Cargo versions, and target triple.
- Cargo package version and source commit for the project (mark the commit as unknown if Git metadata is unavailable), plus the experiment script version or SHA-256 hash.
- Actual matrix path and SHA-256 hash, full command line, and all environment variables.
- Workload variant, input source/data-generation command/random seed/file hash, and outer run, warm-up, and internal repetition settings.
- Logs, process exit code, result CSV, and the analysis scripts/parameters used for the run.

Use these PowerShell commands to hash key files:

```powershell
Get-FileHash .\table\table_json\combined_experiment_matrix.json -Algorithm SHA256
Get-FileHash .\<project>\<experiment-script>.py -Algorithm SHA256
```

If the script actually reads the matrix under `pass_filter` or another JSON file, hash that file instead of copying the example path.

## 6. Step 2: Run Project-Level DiD Analysis

### 6.1 Standard Analysis Directories

Each project should use one of these directories:

- `<project>\analysis\did\`
- `<project>\analysis_new\did\`

The standard scripts usually include:

- `analyze_interaction.py`
- `classify_and_plot.py`
- `plot_coupling.py`
- `plot_knowledge_graph.py`

### 6.2 Current DiD Formula

The current analysis first takes the logarithm of runtime:

```text
z = log(runtime)
```

It then applies this DiD formula:

```text
delta = (mean(z01) - mean(z11)) - (mean(z00) - mean(z10))
```

Where:

- `y00`: baseline
- `y10`: MIR-only change
- `y01`: LLVM-only change
- `y11`: simultaneous MIR and LLVM change

### 6.3 Current Significance Rule

In the current code, an interaction pair is significant only when both conditions hold:

```text
BH-adjusted p-value < 0.05
and
95% bootstrap CI excludes 0
```

### 6.4 Current Bootstrap Settings

The current project scripts use:

```text
BOOTSTRAP_SAMPLES = 2000
BOOTSTRAP_SEED = 42
```

### 6.5 rustls Analysis Example

```powershell
cd D:\MIR_LLVM_NEW\rustls\analysis\did
python .\analyze_interaction.py
python .\classify_and_plot.py
python .\plot_coupling.py
python .\plot_knowledge_graph.py
```

### 6.6 quinn Analysis Example

```powershell
cd D:\MIR_LLVM_NEW\quinn\analysis\did
python .\analyze_interaction.py
python .\classify_and_plot.py
python .\plot_coupling.py
python .\plot_knowledge_graph.py
```

## 7. Baseline Handling

### 7.1 Why This Needs Special Attention

DiD analysis requires an analysis baseline `(None, None)`, meaning:

- `MIR_Pass=None`
- `LLVM_Pass=None`

Some projects do not encode the baseline this way in the raw CSV. Instead, they record the "all disabled" baseline as:

- `LLVM_Pass=None`
- `MIR_Pass=All`

### 7.2 Correct Handling in the Current Workflow

For these data, the current correct reproduction procedure is:

1. Read the raw results.
2. Map `(MIR_Pass=All, LLVM_Pass=None)` to `(None, None)` for analysis.
3. Then construct `y00/y10/y01/y11`.

At least these projects need this baseline normalization:

- `rustls`
- `quinn`
- `aho-corasick`

Without this step, either:

- the analysis cannot find `y00`, or
- the script runs but uses the wrong baseline.

## 8. Step 3: Check Project-Level Outputs

After project-level analysis, the scripts usually generate:

- `interaction_results.csv`
- `interaction_heatmap.png`
- `interaction_heatmap.pdf`
- `top_interactions_forest.png`
- `top_interactions_forest.pdf`
- `classified_results\...`
- `coupling_plots\...`

### 8.1 `interaction_results.csv`

This is the primary results table. Common fields include:

- `mir_pass`
- `llvm_pass`
- `delta`
- `ci_low`
- `ci_high`
- `p_value`
- `p_adj`
- `significant`
- `interaction_type`
- `y00_mean`
- `y10_mean`
- `y01_mean`
- `y11_mean`

### 8.2 Classification Results

`classify_and_plot.py` produces:

- `classified_results\negative_interaction\negative_interactions.csv`
- `classified_results\positive_interaction\positive_interactions.csv`
- `classified_results\independent\independent_pairs.csv`

### 8.3 Coupling Plots and Knowledge Graphs

`plot_coupling.py` and `plot_knowledge_graph.py` currently plot only interactions with `significant == True`.

If a project has no significant interactions under the strict rule, the scripts may print messages such as:

- `No significant interactions found for heatmap.`
- `No significant interactions found for network.`
- `No significant interactions found.`

In this case, the absence of a significant-edge plot is expected.

### 8.4 Validate the Raw Experiment Results

Before analysis, check that the raw experiment is complete:

1. Use the matrix that was actually used at runtime and confirm that every expected configuration appears in the CSV. The expected matrix has 1,766 entries when using `table\table_json`, and 1,765 when using `pass_filter`.
2. Check the number of outer measurement records for each configuration. Confirm that each has 10 valid independent measurements and that the warm-up was not counted as a measurement.
3. Check the CSV `Status`, logs, and process exit code to distinguish successful measurements from build failures, benchmark failures, and result-parsing failures. The presence of a result directory or CSV file alone does not prove that the run succeeded.
4. For `NoParsedResults`, missing values, duplicate configurations, missing rounds, or unusual runtimes, inspect the corresponding logs and input files. A retained `fast_image_resize` result currently contains `NoParsedResults`; verify the CSV format/parser and logs before deciding whether to include it in the analysis.

Only valid runs that pass these checks should enter DiD analysis. Save reruns or repaired results separately and document how they differ from the original results.

### 8.5 Large-|Δ| Case Reproduction

The paper's per-subject maximum-|Δ| cases are preserved in the [curated large-delta bundle](datas/large_delta/). It contains frozen inputs and the analysis needed to reproduce 18 evaluation subjects, with 1,660 planned pairwise comparisons per subject (29,880 interaction rows in total). BH adjustment is performed separately within each subject; the confidence intervals and q-values do not account for maximum-based selection, so these cases are exploratory.

Run the statistical checks from the bundle directory:

```powershell
cd D:\MIR_LLVM_NEW\datas\large_delta
python analyze_large_delta.py
python -m unittest discover -s tests -v
```

The subject maxima, four-cell medians, and paper table are in `results\large_delta_summary\subject_max.csv`, `results\case_cell_medians.csv`, and `paper_revision_20261102\tables\big_delta.tex`. The two cases discussed in the paper are:

- `ripgrep`: `ForceInline × -disable-cleanups`, Δ=`+0.5125`, 95% CI `[+0.4405,+0.5922]`, q=`6.28×10^-5`; medians `(00,10,01,11) = (9.715, 11.976, 12.565, 9.674)` seconds, `n=10` per cell.
- `bat`: `ImpossiblePredicates × -disable-vp`, Δ=`-0.4237`, 95% CI `[-0.4687,-0.3620]`, q=`2.59×10^-4`; medians `(23.183, 23.285, 23.219, 36.365)` seconds, `n=10` per cell.

Compiler summaries are under `datas\large_delta\evidence\representative_runs\run_20261023_full_graph\analysis\`, and sampled profiles are under `datas\large_delta\evidence\hot_paths_wsl_20261105\`. These are supplemental observations: the raw compiler `cases` are not included, the compiler capture uses a supplemental toolchain/source snapshot, and the stripped `bat` executable supports address-level profiling only. They support consistency checks but do not establish a causal mechanism for the historical runtime interaction.

The saved compiler summaries report no corresponding cell-specific shared LLVM-IR or assembly-module changes for `ripgrep`. For `bat`, the shared-module changes relative to cell `00` are `21/165`, `19/165`, and `18/165` for cells `10`, `01`, and `11`, respectively, in both LLVM IR and assembly; the MIR summary counts are unchanged. The `bat_fast` profile captures contain approximately 1,000 samples per cell.

## 9. Step 4: Re-run Cross-Project Aggregation

### 9.1 Script Location

The current aggregation script is located at:

- `D:\MIR_LLVM_NEW\datas\interaction_stats\summarize_interactions.py`

### 9.2 An Easy-to-Miss Detail

Although the script is stored under `datas\interaction_stats`, its output directory is currently hard-coded as:

```text
D:\MIR_LLVM_NEW\analysis_all\interaction_stats\
```

The script sets it with:

```python
OUTPUT_DIR = ROOT / "analysis_all" / "interaction_stats"
```

To write the outputs directly back to `datas\interaction_stats`, change this constant first.

### 9.3 Current Scan Rules

The aggregation script currently scans:

- `*/analysis/did/interaction_results.csv`
- `*/analysis_new/did/interaction_results.csv`

For each project:

- If both `analysis` and `analysis_new` exist, prefer `analysis_new`.
- If multiple files exist within the same directory type, select the most recently modified one.

### 9.4 Aggregation Command

```powershell
cd D:\MIR_LLVM_NEW\datas\interaction_stats
python .\summarize_interactions.py
```

### 9.5 Current Summary Fields

In addition to interaction counts, the current summary includes interaction-strength metrics:

- `total_pairs`
- `independent_count`
- `highlighted_count`
- `positive_interaction_count`
- `negative_interaction_count`
- `highlighted_ratio`
- `sig_mean_abs_delta`
- `sig_median_abs_delta`
- `sig_p95_abs_delta`
- `sig_max_abs_delta`
- `sig_mean_rel_strength`
- `top10_abs_delta_share`

These fields address two questions:

- How many interactions are there?
- How strong are those interactions?

## 10. Minimal Reproduction Checklist

To reproduce a single project, use this order:

1. Run its `experiment_*.py` script.
2. Confirm that `results\<timestamp>\experiment_results.csv` was created.
3. Prepare `analysis\did` or `analysis_new\did`.
4. Run `analyze_interaction.py`.
5. Run `classify_and_plot.py`.
6. Run `plot_coupling.py`.
7. Run `plot_knowledge_graph.py`.
8. Check `interaction_results.csv`.

To rebuild the cross-workspace summary:

1. Make sure the project-level DiD results are up to date.
2. Run `datas\interaction_stats\summarize_interactions.py`.
3. Check:
   - `interaction_summary.csv`
   - `interaction_summary_zh.csv`
   - If needed, comparison tables such as `interaction_summary_bh_ci_compare.csv`.

## 11. Common Pitfalls

### 11.1 `analyze_interaction.py` Points to an Old Results Directory

Many projects hard-code `DATA_DIR` in `analyze_interaction.py`. Before rerunning analysis, confirm that it points to the results from the intended run.

### 11.2 Baseline Encoding Does Not Match the Analysis Convention

Do not assume that every project has a `(None, None)` baseline. Projects such as `rustls`, `quinn`, and `aho-corasick` usually need `(All, None) -> (None, None)` normalization first.

### 11.3 Linux Paths Remain in the Scripts

Some older scripts still contain `/root/MIR_LLVM` paths. The `ripgrep`, `bat`, `eza`, `regex`, and `quinn` runners are confirmed to have such hard-coded paths. Before running on Windows, replace them with paths in the current workspace or pass supported path arguments. Set `--list-path` explicitly for `eza` to avoid its default path to an old `bat` directory.

### 11.4 "No Significant Interaction" Does Not Mean "No Strong Signal"

A project may have:

- a large `delta`;
- a CI that does not cross 0;
- but `p_adj >= 0.05`.

Common reasons include:

- a large number of tests;
- strict BH correction;
- limited resolution of the bootstrap `p_value`.

The current `rustls` results are a typical example.

## 12. Recommended Reproduction Order

For a clean, full reproduction, proceed as follows:

1. Generate or update raw results for the target project.
2. Check the data directory configured in that project's `analyze_interaction.py`.
3. Fix baseline normalization if needed.
4. Rerun project-level DiD analysis.
5. Check `interaction_results.csv`.
6. Rerun the cross-project aggregation script.
7. Compare the target project's row in the summary table.

## 13. Current rustls Reproduction Example

One currently valid `rustls` reproduction configuration uses:

- Raw results directory: `D:\MIR_LLVM_NEW\rustls\results\run_20260619_210845`
- Analysis directory: `D:\MIR_LLVM_NEW\rustls\analysis\did`
- Baseline handling: normalize raw `(All, None)` records to `(None, None)` for analysis.

Commands:

```powershell
cd D:\MIR_LLVM_NEW\rustls\analysis\did
python .\analyze_interaction.py
python .\classify_and_plot.py
python .\plot_coupling.py
python .\plot_knowledge_graph.py
```

Then rerun the cross-project aggregation:

```powershell
cd D:\MIR_LLVM_NEW\datas\interaction_stats
python .\summarize_interactions.py
```

## 14. Results to Archive

For paper reproduction, result auditing, or later comparisons, retain at least:

- The raw results directory actually used for each project.
- The `analyze_interaction.py` used for that run.
- `interaction_results.csv`.
- Project-level plot outputs.
- `interaction_summary.csv`.
- `interaction_summary_zh.csv`.
- Comparison tables if the analysis method changed.

## 15. One-Paragraph Summary

The complete workflow is to run each project's `experiment_*` script to generate raw measurements under `results\<timestamp>`, then enter that project's `analysis\did` or `analysis_new\did` directory and run `analyze_interaction.py` to perform bootstrap DiD on `log(runtime)`. Classify interactions as significant when `BH-adjusted p < 0.05` and the `95% bootstrap CI excludes 0`, then run the classification, coupling, and knowledge-graph scripts. Finally, run `datas\interaction_stats\summarize_interactions.py` to generate the cross-project summary. For projects such as `rustls`, `quinn`, and `aho-corasick`, whose raw baseline is encoded as `LLVM_Pass=None, MIR_Pass=All`, normalize it to `(None, None)` before analysis; otherwise, the DiD baseline will be inconsistent.
