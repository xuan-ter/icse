# MIR/LLVM Interaction Experiment Reproduction Guide

## 1. Purpose

This document describes how to reproduce the current MIR/LLVM interaction experiment workflow in `d:\MIR_LLVM_NEW`.

The repository currently contains three layers of work:

1. Per-project batch experiment scripts that generate raw runtime data under each project's `results` directory.
2. Per-project DiD analysis scripts under `analysis/did` or `analysis_new/did` that transform raw runs into interaction tables and figures.
3. A global summary script that scans all projects and aggregates them into one cross-project table.

This guide is written to match the code and data processing logic currently used in the workspace, including:

- bootstrap-based difference-in-differences (DiD)
- log-runtime analysis
- significance rule: `BH-adjusted p < 0.05` and `95% bootstrap CI excludes 0`
- project-specific baseline normalization for datasets that record the all-off baseline as `LLVM_Pass=None, MIR_Pass=All`


## 2. Directory Layout

At a high level, the workflow is organized as follows:

```text
d:\MIR_LLVM_NEW\
  <project>\
    experiment_*            # raw experiment driver
    results\                # raw experiment outputs
    analysis\did\           # project-level DID analysis
    analysis_new\did\       # project-level DID analysis (newer variant for some projects)

  datas\interaction_stats\
    summarize_interactions.py
    interaction_summary.csv
    interaction_summary_zh.csv
```

Representative experiment drivers already present in the workspace include:

- `bat\experiment_bat_mir_llvm_hybrid.py`
- `eza\experiment_eza_mir_llvm_hybrid.py`
- `ripgrep\experiment_rg_mir_llvm_hybrid.py`
- `hyper\experiment_hyper_mir_llvm_hybrid.py`
- `rustls\experiment_rustls_mir_llvm_hybrid.py`
- `quinn\experiment_quinn_mir_llvm_hybrid.py`
- `aho-corasick\experiment_aho_mir_llvm_hybrid.py`
- `loop_hoisting_bench\experiment_loop_mir_llvm_hybrid.py`


## 3. Environment

### 3.1 Python

The analysis scripts depend on Python 3 and the following packages:

- `pandas`
- `numpy`
- `matplotlib`
- `seaborn`
- `networkx`
- `Pillow`

Recommended setup:

```powershell
cd d:\MIR_LLVM_NEW
.\.venv\Scripts\activate
pip install pandas numpy matplotlib seaborn networkx pillow
```

### 3.2 Rust toolchain

The experiment drivers compile Rust projects repeatedly with custom MIR and LLVM settings.

At minimum you should have:

- `rustup`
- a usable `nightly` toolchain
- `cargo`

Check:

```powershell
rustup show
cargo --version
rustc +nightly --version
```

### 3.3 Platform note

This workspace is currently being operated on Windows. Some older experiment drivers contain Linux-style hard-coded paths and may need one-time path correction before reuse. For example, `quinn\experiment_quinn_mir_llvm_hybrid.py` still contains `/root/...` defaults and should be adjusted if run directly on Windows.


## 4. End-to-End Workflow

The full reproduction pipeline is:

1. Run a project-level experiment script to generate raw `experiment_results.csv`.
2. Run the project's DiD analysis scripts under `analysis/did` or `analysis_new/did`.
3. Inspect per-project outputs such as `interaction_results.csv`, forest plots, classification plots, and coupling plots.
4. Run the global summary script to regenerate the cross-project summary table.


## 5. Step 1: Generate Raw Results

### 5.1 What the experiment drivers do

The raw experiment scripts:

- load a MIR/LLVM pass combination matrix from JSON
- rebuild the project with a specific pass configuration
- execute benchmark runs repeatedly
- record runtime, compile time, binary size, labels, and status
- write raw results to a timestamped subdirectory under `results`

For example, `rustls\experiment_rustls_mir_llvm_hybrid.py` accepts:

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

For example, `quinn\experiment_quinn_mir_llvm_hybrid.py` accepts:

- `--runs`
- `--limit`
- `--start`
- `--start-exp`
- `--run-repeats`
- `--warmup`
- `--bench-args`

### 5.2 Example command: rustls

```powershell
cd d:\MIR_LLVM_NEW\rustls
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

Typical raw outputs:

- `results\<timestamp>\experiment_results.csv`
- `results\<timestamp>\summary_medians.csv`
- `results\<timestamp>\volatility_summary.csv`
- `results\<timestamp>\experiment_execution.log`


## 6. Step 2: Run Project-Level DID Analysis

### 6.1 Standard output directory

Each analyzed project should have one of:

- `<project>\analysis\did\`
- `<project>\analysis_new\did\`

The core script is always:

- `analyze_interaction.py`

and is typically followed by:

- `classify_and_plot.py`
- `plot_coupling.py`
- `plot_knowledge_graph.py`

### 6.2 Current DiD formula

The current scripts use log runtime:

```text
z = log(runtime)
```

and the interaction effect is:

```text
delta = (mean(z01) - mean(z11)) - (mean(z00) - mean(z10))
```

where:

- `y00`: baseline
- `y10`: MIR ablated only
- `y01`: LLVM ablated only
- `y11`: MIR and LLVM ablated jointly

### 6.3 Current significance rule

The current code classifies a pair as significant only if both conditions hold:

```text
BH-adjusted p-value < 0.05
and
95% bootstrap CI excludes 0
```

This rule is implemented in project analysis scripts such as:

- [analyze_interaction.py](file:///d:/MIR_LLVM_NEW/rustls/analysis/did/analyze_interaction.py#L134-L139)

### 6.4 Bootstrap settings

The current project scripts use:

```text
BOOTSTRAP_SAMPLES = 2000
BOOTSTRAP_SEED = 42
```

### 6.5 Example command: rustls

```powershell
cd d:\MIR_LLVM_NEW\rustls\analysis\did
python .\analyze_interaction.py
python .\classify_and_plot.py
python .\plot_coupling.py
python .\plot_knowledge_graph.py
```

### 6.6 Example command: quinn

```powershell
cd d:\MIR_LLVM_NEW\quinn\analysis\did
python .\analyze_interaction.py
python .\classify_and_plot.py
python .\plot_coupling.py
python .\plot_knowledge_graph.py
```


## 7. Baseline Handling

### 7.1 Why this matters

Not all projects record the baseline in the same way.

The DiD scripts expect the analysis baseline to exist as:

```text
(MIR_Pass=None, LLVM_Pass=None)
```

However, some projects record the "all-off" experimental baseline as:

```text
LLVM_Pass=None, MIR_Pass=All
```

### 7.2 Current normalization rule

For such datasets, the correct reproduction behavior is:

1. read raw rows as recorded
2. remap `(MIR_Pass=All, LLVM_Pass=None)` to analysis baseline `(None, None)`
3. drop any remaining `All` labels if they are not the baseline row

This is currently the correct handling for at least:

- `rustls`
- `quinn`
- `aho-corasick`

If this remapping is omitted, the script may fail to construct `y00`, or it may silently analyze the wrong baseline.


## 8. Step 3: Interpret Per-Project Outputs

After running the DID scripts, each project should produce:

- `interaction_results.csv`
- `interaction_heatmap.png`
- `interaction_heatmap.pdf`
- `top_interactions_forest.png`
- `top_interactions_forest.pdf`
- `classified_results\...`
- `coupling_plots\...`

### 8.1 `interaction_results.csv`

This is the main machine-readable result file. Important columns include:

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

### 8.2 Classification outputs

`classify_and_plot.py` separates results into:

- `classified_results\negative_interaction\negative_interactions.csv`
- `classified_results\positive_interaction\positive_interactions.csv`
- `classified_results\independent\independent_pairs.csv`

### 8.3 Coupling plots

`plot_coupling.py` and `plot_knowledge_graph.py` only use significant interactions.

If a project has no significant interactions under the current rule, they will print messages such as:

- `No significant interactions found for heatmap.`
- `No significant interactions found for network.`
- `No significant interactions found.`

and no significant-edge coupling figure will be produced.


## 9. Step 4: Rebuild the Global Summary Table

### 9.1 Script location

The current summary script is:

- `d:\MIR_LLVM_NEW\datas\interaction_stats\summarize_interactions.py`

### 9.2 Important implementation detail

Although the script is stored under `datas\interaction_stats`, it is currently configured to write output to:

```text
d:\MIR_LLVM_NEW\analysis_all\interaction_stats\
```

because the script contains:

```python
OUTPUT_DIR = ROOT / "analysis_all" / "interaction_stats"
```

If you want the output CSVs to be written back into `datas\interaction_stats`, adjust that constant before running.

### 9.3 Scan rule

The current script scans:

- `*/analysis/did/interaction_results.csv`
- `*/analysis_new/did/interaction_results.csv`

and prefers `analysis_new` over `analysis` when both exist for the same project.

### 9.4 Summary command

```powershell
cd d:\MIR_LLVM_NEW\datas\interaction_stats
python .\summarize_interactions.py
```

### 9.5 Current summary fields

The global summary includes:

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

These fields are designed to capture both:

- how many interactions are significant
- how strong the significant interactions are


## 10. Suggested Minimal Reproduction Checklist

For one project:

1. run the experiment driver
2. confirm `results\<timestamp>\experiment_results.csv` exists
3. create or update `analysis/did` or `analysis_new/did`
4. run `analyze_interaction.py`
5. run `classify_and_plot.py`
6. run `plot_coupling.py`
7. run `plot_knowledge_graph.py`
8. inspect `interaction_results.csv`

For the whole workspace:

1. make sure each project has a valid `interaction_results.csv`
2. run `datas\interaction_stats\summarize_interactions.py`
3. inspect:
   - `interaction_summary.csv`
   - `interaction_summary_zh.csv`
   - optional compare tables such as `interaction_summary_bh_ci_compare.csv`


## 11. Known Reproduction Pitfalls

### 11.1 Hard-coded result directories

Some project analysis scripts still point to a fixed result subdirectory. Before reproducing, check the `DATA_DIR` setting in each `analyze_interaction.py`.

### 11.2 Baseline encoding mismatch

Do not assume every project stores baseline as `(None, None)`. For `rustls`, `quinn`, and `aho-corasick`, the raw CSV baseline can be encoded as `(All, None)` in `(MIR_Pass, LLVM_Pass)` terms and must be normalized.

### 11.3 Path style mismatch

Some scripts were originally authored on Linux and may still contain `/root/...` paths. Normalize them to Windows paths before rerunning on this machine.

### 11.4 No significant interactions does not mean no strong effects

A project may have large `delta` values and `CI` excluding zero, but still end up with `significant=False` everywhere because `p_adj >= 0.05` after BH correction across 1660 simultaneous tests.

This is currently the case for `rustls`.


## 12. Recommended Reproduction Order

If you want the cleanest full rerun, use this order:

1. generate or refresh raw results for the target project
2. adapt baseline handling in `analyze_interaction.py` if needed
3. rerun the project-level DID pipeline
4. verify `interaction_results.csv`
5. rerun the global summary script
6. compare the project row in `interaction_summary.csv`


## 13. Example: rustls Reproduction

Current `rustls` reproduction uses:

- raw results: `d:\MIR_LLVM_NEW\rustls\results\run_20260619_210845`
- analysis directory: `d:\MIR_LLVM_NEW\rustls\analysis\did`
- analysis baseline convention: recorded `(All, None)` remapped to analysis `(None, None)`

Commands:

```powershell
cd d:\MIR_LLVM_NEW\rustls\analysis\did
python .\analyze_interaction.py
python .\classify_and_plot.py
python .\plot_coupling.py
python .\plot_knowledge_graph.py
```

Then rebuild the global summary:

```powershell
cd d:\MIR_LLVM_NEW\datas\interaction_stats
python .\summarize_interactions.py
```


## 14. Deliverables to Archive

For paper-ready or audit-ready reproduction, archive at least:

- the exact raw result directory for each project
- the exact `analyze_interaction.py` used for that run
- `interaction_results.csv`
- generated per-project figures
- `interaction_summary.csv`
- `interaction_summary_zh.csv`
- any compare tables used in the write-up


## 15. One-Paragraph Short Version

To reproduce the current experiment, first run each project's `experiment_*` script to generate raw `experiment_results.csv` under `results\<timestamp>`, then run the corresponding `analysis/did` or `analysis_new/did` scripts to compute bootstrap DiD interaction effects on log runtime, classify them using `BH-adjusted p < 0.05` and `95% bootstrap CI excludes 0`, and finally run `datas\interaction_stats\summarize_interactions.py` to regenerate the cross-project summary table. For projects such as `rustls`, `quinn`, and `aho-corasick`, make sure the raw baseline recorded as `LLVM_Pass=None, MIR_Pass=All` is normalized to the analysis baseline `(None, None)` before the DiD step.
