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

Representative experiment drivers currently present in the workspace include:

- `bat\experiment_bat_mir_llvm_hybrid.py`
- `eza\experiment_eza_mir_llvm_hybrid.py`
- `ripgrep\experiment_rg_mir_llvm_hybrid.py`
- `hyper\experiment_hyper_mir_llvm_hybrid.py`
- `rustls\experiment_rustls_mir_llvm_hybrid.py`
- `quinn\experiment_quinn_mir_llvm_hybrid.py`
- `aho-corasick\experiment_aho_mir_llvm_hybrid.py`
- `loop_hoisting_bench\experiment_loop_mir_llvm_hybrid.py`
- `tokio\experiment_tokio_mir_llvm_hybrid.py`
- `serde\experiment_expanded_llvm_mir.py`
- `image\experiment_image_mir_llvm_hybrid.py`
- `fast_image_resize\experiment_fast_image_resize.py`
- `trait_test\experiment_trait_mir_llvm_hybrid.py`
- `aggregate_scalarization_bench\experiment_aggregate_scalarization_mir_llvm.py`
- `async_state_machine_bench\experiment_async_state_machine_mir_llvm.py`
- `branch_cfg_bench\experiment_cfg_mir_llvm_hybrid.py`
- `iterator_pipeline_bench\experiment_iterator_pipeline_mir_llvm_hybrid.py`

The main project directories currently covered by this workflow are:

- `aggregate_scalarization_bench`
- `aho-corasick`
- `async_state_machine_bench`
- `bat`
- `branch_cfg_bench`
- `eza`
- `fast_image_resize`
- `hyper`
- `image`
- `iterator_pipeline_bench`
- `loop_hoisting_bench`
- `quinn`
- `regex`
- `ripgrep`
- `rustls`
- `serde`
- `tokio`
- `trait_test`

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

Use `pass_filter\pass.txt` to check pass names and switches. Note that `pass_filter\combined_experiment_matrix.json` and `table\table_json\combined_experiment_matrix.json` are different files: the former has 1,765 entries, while the latter has 1,766 and includes the additional `EXP_000_ALL_OFF` entry. Many project scripts currently default to the file under `table\table_json`, but the actual input is determined by the target script's `DEFAULT_JSON_PATH` or command-line arguments. The paper reports 1,766 configurations, matching the count in the `table\table_json` file. Record the actual matrix path and its SHA-256 hash for every run, then check results against the configuration names in that file. Do not treat the two matrix sizes as interchangeable.

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

- [analyze_interaction.py](rustls/analysis/did/analyze_interaction.py)

### 6.4 Bootstrap settings

Bootstrap settings are project-specific. The current Rustls analysis uses:

```text
BOOTSTRAP_SAMPLES = 50000
BOOTSTRAP_SEED = 42
```

Check the settings in the target project's `analyze_interaction.py` before reproducing its results.

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

### 8.4 Large-|Δ| Case Reproduction

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


## 9. Step 4: Rebuild the Global Summary Table

### 9.1 Script location

The current summary script is:

- `d:\MIR_LLVM_NEW\datas\interaction_stats\summarize_interactions.py`

### 9.2 Important implementation detail

The current script is configured to write output directly to:

```text
d:\MIR_LLVM_NEW\datas\interaction_stats\
```

because the script contains:

```python
OUTPUT_DIR = ROOT / "datas" / "interaction_stats"
```

The script also hard-codes preferred result sources for some projects:

- `serde -> serde\analysis_new\did\interaction_results.csv`
- `fast_image_resize -> fast_image_resize\analysis\did\interaction_results.csv`
- `image -> image\analysis\did\interaction_results.csv`

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
- `total_positive_delta_count`
- `total_negative_delta_count`
- `zero_count`
- `independent_count`
- `independent_positive_delta_count`
- `independent_negative_delta_count`
- `highlighted_count`
- `positive_interaction_count`
- `negative_interaction_count`
- `highlighted_ratio`
- `sig_mean_abs_delta`
- `sig_median_abs_delta`
- `sig_p99_abs_delta`
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

To reproduce the current experiment, first run each project's `experiment_*` script to generate raw `experiment_results.csv` under `results\<timestamp>`, then run the corresponding `analysis/did` or `analysis_new/did` scripts to compute bootstrap DiD interaction effects on log runtime, classify them using `BH-adjusted p < 0.05` and `95% bootstrap CI excludes 0`, and finally run `datas\interaction_stats\summarize_interactions.py` to regenerate the cross-project summary table.
