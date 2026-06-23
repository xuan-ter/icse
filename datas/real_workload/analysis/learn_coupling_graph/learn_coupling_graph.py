import os
import glob
import math
import csv

try:
    import pandas as pd
    import numpy as np
    from sklearn.linear_model import LassoCV, Lasso
    import matplotlib.pyplot as plt
    import seaborn as sns
    import networkx as nx
    from matplotlib.lines import Line2D
    HAVE_LASSO_STACK = True
except Exception:
    HAVE_LASSO_STACK = False

from PIL import Image, ImageDraw, ImageFont

# Configuration
DATA_DIR = os.path.abspath(r"d:\MIR_LLVM_NEW\datas\real_workload")
OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(OUTPUT_DIR, exist_ok=True)
N_BOOTSTRAP = 50
EDGE_STABILITY_THRESHOLD = 0.4
MIN_EDGES_PER_BENCH = 50
TOPK_REQUIRE_NONZERO = True
TOPK_COEF_EPS = 1e-12
EDGE_METHOD = "auto"
ANOVA_MIN_PAIR_COUNT = 2
ANOVA_WEIGHT_EPS = 1e-12
ANOVA_TOPK_EDGES = 300
ANOVA_SELECT_MODE = "auto"
ANOVA_AUTO_MIN_EDGES = 200
ANOVA_AUTO_MAX_EDGES = 800
ANOVA_AUTO_SCORE_QUANTILE = 0.95
ANOVA_SAVE_ALL_EDGES = True
AUTO_SKIP_LASSO_MAX_PAIR_COUNT_LT = 10

def _load_font(size, bold=False):
    candidates = []
    if bold:
        candidates.extend([
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ])
    candidates.extend([
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ])
    for p in candidates:
        try:
            return ImageFont.truetype(p, size=size)
        except Exception:
            continue
    return ImageFont.load_default()

def plot_coupling_matrix_from_edges_csv(
    edges_csv_path,
    output_png_path,
    top_mir=25,
    top_llvm=25,
):
    if not os.path.exists(edges_csv_path):
        raise FileNotFoundError(edges_csv_path)

    edges = []
    with open(edges_csv_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            src = str(r.get("Source", "")).strip()
            tgt = str(r.get("Target", "")).strip()
            if not src or not tgt:
                continue
            try:
                w = float(r.get("Weight"))
            except Exception:
                continue
            try:
                s = float(r.get("Stability"))
            except Exception:
                s = 0.0
            edges.append((src, tgt, w, s))

    if not edges:
        return

    mir_strength = {}
    llvm_strength = {}
    for src, tgt, w, s in edges:
        strength = abs(w) * (0.2 + 0.8 * max(0.0, min(1.0, s)))
        mir_strength[src] = mir_strength.get(src, 0.0) + strength
        llvm_strength[tgt] = llvm_strength.get(tgt, 0.0) + strength

    mir_top = [k for k, _ in sorted(mir_strength.items(), key=lambda x: x[1], reverse=True)[: max(1, int(top_mir))]]
    llvm_top = [k for k, _ in sorted(llvm_strength.items(), key=lambda x: x[1], reverse=True)[: max(1, int(top_llvm))]]

    edge_map = {}
    max_mag = 0.0
    for src, tgt, w, s in edges:
        if src not in mir_top or tgt not in llvm_top:
            continue
        edge_map[(src, tgt)] = (w, s)
        max_mag = max(max_mag, abs(w))
    max_mag = max(max_mag, 1e-9)

    ROT_PAD = 10

    def draw_rotated_text(x, y, text, font, angle=90, fill=(0, 0, 0, 255)):
        pad = ROT_PAD
        try:
            _d = ImageDraw.Draw(Image.new("RGBA", (1, 1), (255, 255, 255, 0)))
            tb = _d.textbbox((0, 0), text, font=font)
            tw = tb[2] - tb[0]
            th = tb[3] - tb[1]
        except Exception:
            tw = 10 * len(text)
            th = 18
            tb = (0, 0, tw, th)
        tmp = Image.new("RGBA", (max(1, tw + pad * 2), max(1, th + pad * 2)), (255, 255, 255, 0))
        tmp_draw = ImageDraw.Draw(tmp)
        tmp_draw.text((pad - tb[0], pad - tb[1]), text, fill=fill, font=font)
        rot = tmp.rotate(angle, expand=True, resample=Image.BICUBIC)
        img.alpha_composite(rot, (int(x), int(y)))
        return rot.size

    cell = 30
    right = 90
    bottom = 170
    top_text = 150

    font_title = _load_font(36, bold=True)
    font_sub = _load_font(20, bold=False)
    font_axis = _load_font(20, bold=True)
    font_lbl = _load_font(16, bold=False)
    font_tick = _load_font(12, bold=False)

    llvm_labels = [s[:18] for s in llvm_top]
    mir_labels = [s[:42] for s in mir_top]

    max_mir_w = 0
    max_mir_h = 0
    dummy = Image.new("RGBA", (10, 10), (255, 255, 255, 0))
    dummy_draw = ImageDraw.Draw(dummy)
    for s in mir_labels:
        try:
            tb = dummy_draw.textbbox((0, 0), s, font=font_tick)
            tw = tb[2] - tb[0]
            th = tb[3] - tb[1]
        except Exception:
            tw = 10 * len(s)
            th = 14
        if tw > max_mir_w:
            max_mir_w = tw
        if th > max_mir_h:
            max_mir_h = th

    max_rot_h = 0
    max_rot_w = 0
    for s in llvm_labels:
        try:
            tb = dummy_draw.textbbox((0, 0), s, font=font_tick)
            tw = tb[2] - tb[0]
            th = tb[3] - tb[1]
        except Exception:
            tw = 10 * len(s)
            th = 14
        rot_w = th + ROT_PAD * 2
        rot_h = tw + ROT_PAD * 2
        if rot_h > max_rot_h:
            max_rot_h = rot_h
        if rot_w > max_rot_w:
            max_rot_w = rot_w

    mir_axis_lbl = "MIR Passes"
    try:
        tb = dummy_draw.textbbox((0, 0), mir_axis_lbl, font=font_axis)
        mir_axis_w = tb[2] - tb[0]
        mir_axis_h = tb[3] - tb[1]
    except Exception:
        mir_axis_w = 10 * len(mir_axis_lbl)
        mir_axis_h = 20
    mir_axis_rot_w = mir_axis_h + ROT_PAD * 2
    mir_axis_rot_h = mir_axis_w + ROT_PAD * 2

    outer_pad_x = 80
    outer_pad_right = 80
    gap_axis_to_labels = 18
    gap_labels_to_grid = 18
    top = max(240, top_text + max_rot_h + 30)

    grid_w = cell * len(llvm_top)
    grid_h = cell * len(mir_top)
    content_w = mir_axis_rot_w + gap_axis_to_labels + max_mir_w + gap_labels_to_grid + grid_w
    width = outer_pad_x + content_w + outer_pad_right
    height = top + grid_h + bottom

    img = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)

    draw.text((70, 40), "Lasso Coupling Matrix (Alternative View)", fill=(0, 0, 0), font=font_title)
    draw.text((70, 92), f"Top MIR={len(mir_top)} by strength; Top LLVM={len(llvm_top)} by strength", fill=(70, 70, 70), font=font_sub)
    draw.text((70, 124), "Cell color: red=conflict(+), blue=synergy(-); opacity ~ stability; intensity ~ |weight|", fill=(70, 70, 70), font=font_sub)

    left = outer_pad_x + mir_axis_rot_w + gap_axis_to_labels + max_mir_w + gap_labels_to_grid

    draw.rectangle([left, top, left + grid_w, top + grid_h], fill=(248, 248, 248, 255))

    for j, lbl in enumerate(llvm_labels):
        x = left + j * cell
        draw.line([(x, top), (x, top + grid_h)], fill=(230, 230, 230, 255), width=1)
        try:
            tb = draw.textbbox((0, 0), lbl, font=font_tick)
            txt_w = tb[2] - tb[0]
            txt_h = tb[3] - tb[1]
        except Exception:
            txt_w = 10 * len(lbl)
            txt_h = 14
        rot_w = txt_h + ROT_PAD * 2
        rot_h = txt_w + ROT_PAD * 2
        x_txt = x + cell // 2 - rot_w // 2
        y_txt = top - 10 - rot_h
        draw_rotated_text(x_txt, y_txt, lbl, font_tick, angle=90, fill=(0, 0, 0, 255))
    draw.line([(left + grid_w, top), (left + grid_w, top + grid_h)], fill=(230, 230, 230, 255), width=1)

    for i, mir in enumerate(mir_labels):
        y = top + i * cell
        draw.line([(left, y), (left + grid_w, y)], fill=(230, 230, 230, 255), width=1)
        try:
            tb = draw.textbbox((0, 0), mir, font=font_tick)
            tw = tb[2] - tb[0]
            th = tb[3] - tb[1]
        except Exception:
            tw = 10 * len(mir)
            th = 14
        x_txt = left - gap_labels_to_grid - tw
        y_txt = y + cell // 2 - th // 2
        draw.text((x_txt, y_txt), mir, fill=(0, 0, 0), font=font_tick)
    draw.line([(left, top + grid_h), (left + grid_w, top + grid_h)], fill=(230, 230, 230, 255), width=1)

    for i, mir in enumerate(mir_top):
        for j, llvm in enumerate(llvm_top):
            key = (mir, llvm)
            if key not in edge_map:
                continue
            w, s = edge_map[key]
            mag = min(1.0, abs(w) / max_mag)
            stab = max(0.0, min(1.0, s))
            alpha = int(35 + 220 * stab)
            base = int(40 + 180 * mag)
            if w >= 0:
                col = (220, 30, 30, alpha)
            else:
                col = (30, 90, 220, alpha)
            x0 = left + j * cell + 1
            y0 = top + i * cell + 1
            x1 = x0 + cell - 2
            y1 = y0 + cell - 2
            draw.rectangle([x0, y0, x1, y1], fill=col, outline=(0, 0, 0, 30), width=1)

    llvm_axis_lbl = "LLVM Passes"
    try:
        tb = draw.textbbox((0, 0), llvm_axis_lbl, font=font_axis)
        llvm_axis_w = tb[2] - tb[0]
        llvm_axis_h = tb[3] - tb[1]
    except Exception:
        llvm_axis_w = 10 * len(llvm_axis_lbl)
        llvm_axis_h = 20
    x_llvm_axis = left + grid_w // 2 - llvm_axis_w // 2
    y_llvm_axis = top - max_rot_h - 26
    draw.text((x_llvm_axis, y_llvm_axis), llvm_axis_lbl, fill=(0, 0, 0), font=font_axis)

    x_mir_col = outer_pad_x
    x_mir = x_mir_col + (mir_axis_rot_w - mir_axis_rot_w) // 2
    y_mir = top + grid_h // 2 - mir_axis_rot_h // 2
    draw_rotated_text(x_mir, y_mir, mir_axis_lbl, font_axis, angle=90, fill=(0, 0, 0, 255))

    conflict_lbl = "Conflict (+)"
    synergy_lbl = "Synergy (-)"
    try:
        tb = draw.textbbox((0, 0), conflict_lbl, font=font_lbl)
        w_conf = tb[2] - tb[0]
        h_conf = tb[3] - tb[1]
    except Exception:
        w_conf = 10 * len(conflict_lbl)
        h_conf = 16
    try:
        tb = draw.textbbox((0, 0), synergy_lbl, font=font_lbl)
        w_syn = tb[2] - tb[0]
        h_syn = tb[3] - tb[1]
    except Exception:
        w_syn = 10 * len(synergy_lbl)
        h_syn = 16

    sw, sh = 30, 18
    gap_box_text = 10
    gap_items = 40
    legend_w = (sw + gap_box_text + w_conf) + gap_items + (sw + gap_box_text + w_syn)

    lx = left + grid_w // 2 - legend_w // 2
    ly = top + grid_h + 40
    draw.rectangle([lx, ly, lx + sw, ly + sh], fill=(220, 30, 30, 200), outline=(0, 0, 0, 120), width=1)
    draw.text((lx + sw + gap_box_text, ly + sh // 2 - h_conf // 2), conflict_lbl, fill=(0, 0, 0), font=font_lbl)
    lx2 = lx + (sw + gap_box_text + w_conf) + gap_items
    draw.rectangle([lx2, ly, lx2 + sw, ly + sh], fill=(30, 90, 220, 200), outline=(0, 0, 0, 120), width=1)
    draw.text((lx2 + sw + gap_box_text, ly + sh // 2 - h_syn // 2), synergy_lbl, fill=(0, 0, 0), font=font_lbl)

    img.convert("RGB").save(output_png_path)
    pdf_path = os.path.splitext(output_png_path)[0] + ".pdf"
    img.convert("RGB").save(pdf_path, "PDF", resolution=300.0)

def load_and_preprocess_data(csv_path):
    """
    Loads raw CSV data and converts it into a feature matrix X and target vector y
    suitable for Lasso regression.
    
    X: Binary matrix where 1 means the Pass is DISABLED.
    y: Log-transformed runtime.
    """
    print(f"Loading data: {csv_path}")
    if not os.path.exists(csv_path):
        raise FileNotFoundError(csv_path)
    full_df = pd.read_csv(csv_path)
    if "Status" in full_df.columns:
        full_df = full_df[full_df["Status"] == "Success"]
    full_df["TotalRuntime(s)"] = pd.to_numeric(full_df["TotalRuntime(s)"], errors="coerce")
    full_df = full_df[full_df["TotalRuntime(s)"] > 0]
    if full_df.empty:
        raise ValueError(f"No valid rows after filtering: {csv_path}")
    full_df = full_df.copy()
    full_df["_y"] = np.log(full_df["TotalRuntime(s)"])
    
    # Normalize pass names
    def clean_name(name):
        try:
            if pd.isna(name):
                return None
            s = str(name).strip()
            if s.lower() in ["none", "baseline", "nan", "", "all"]:
                return None
            return s
        except:
            return None

    full_df['MIR_Pass'] = full_df['MIR_Pass'].apply(clean_name)
    full_df['LLVM_Pass'] = full_df['LLVM_Pass'].apply(clean_name)
    
    # Identify all unique passes
    # Filter out None values before sorting
    mir_passes = [p for p in full_df['MIR_Pass'].unique() if p is not None]
    llvm_passes = [p for p in full_df['LLVM_Pass'].unique() if p is not None]
    
    # Sort them, ensuring all are strings
    mir_passes = sorted([str(p) for p in mir_passes])
    llvm_passes = sorted([str(p) for p in llvm_passes])
    
    all_passes = mir_passes + llvm_passes
    print(f"Features: {len(mir_passes)} MIR passes + {len(llvm_passes)} LLVM passes = {len(all_passes)} total features.")
    
    # Build Feature Matrix X
    # Each row is a run. 
    # Columns: [MIR_Pass_1, ..., MIR_Pass_N, LLVM_Pass_1, ..., LLVM_Pass_M]
    # Value 1 means Disabled, 0 means Enabled.
    
    X_rows = []
    y = []
    
    # Map pass name to column index
    pass_to_idx = {p: i for i, p in enumerate(all_passes)}
    
    for _, row in full_df.iterrows():
        x_vec = np.zeros(len(all_passes))
        
        m_pass = row['MIR_Pass']
        l_pass = row['LLVM_Pass']
        
        if m_pass is not None and m_pass in pass_to_idx:
            x_vec[pass_to_idx[m_pass]] = 1
        if l_pass is not None and l_pass in pass_to_idx:
            x_vec[pass_to_idx[l_pass]] = 1
            
        X_rows.append(x_vec)
        y.append(row["_y"])
        
    X = np.array(X_rows)
    y = np.array(y)
    
    # Generate Interaction Features (Cross-Level Only for efficiency)
    # We only care about MIR x LLVM interactions as per paper
    print("Generating interaction features...")
    interaction_features = []
    interaction_names = []
    
    for i, m_pass in enumerate(mir_passes):
        for j, l_pass in enumerate(llvm_passes):
            # Find indices in X
            idx_m = pass_to_idx[m_pass]
            idx_l = pass_to_idx[l_pass]
            
            # Interaction term: x_i * x_j (1 only if BOTH are disabled)
            interaction_col = X[:, idx_m] * X[:, idx_l]
            
            # Optimization: Only add if this interaction actually appears in data
            if np.sum(interaction_col) > 0:
                interaction_features.append(interaction_col)
                interaction_names.append(f"{m_pass}|{l_pass}")
    
    if interaction_features:
        X_inter = np.column_stack(interaction_features)
        X_full = np.hstack([X, X_inter])
        feature_names = all_passes + interaction_names
    else:
        X_full = X
        feature_names = all_passes
        
    print(f"Final Feature Matrix shape: {X_full.shape}")
    return X_full, y, feature_names, mir_passes, llvm_passes, full_df

def compute_anova_interaction_edges(
    full_df,
    min_pair_count=2,
    topk=0,
    select_mode="topk",
    auto_min_edges=50,
    auto_max_edges=500,
    auto_score_quantile=0.98,
):
    df = full_df.dropna(subset=["MIR_Pass", "LLVM_Pass", "_y"])
    if df.empty:
        return pd.DataFrame(columns=["Source", "Target", "Type", "Weight", "Stability", "SelectedBy", "Count"])

    mu = float(df["_y"].mean())
    mean_m = df.groupby("MIR_Pass")["_y"].mean()
    mean_l = df.groupby("LLVM_Pass")["_y"].mean()

    pair = df.groupby(["MIR_Pass", "LLVM_Pass"])["_y"].agg(["mean", "count"]).reset_index()
    pair = pair[pair["count"] >= int(min_pair_count)]
    if pair.empty:
        return pd.DataFrame(columns=["Source", "Target", "Type", "Weight", "Stability", "SelectedBy", "Count"])

    max_count = int(pair["count"].max())
    denom = math.log1p(max_count)
    if denom <= 0:
        denom = 1.0

    pair_mean_m = pair["MIR_Pass"].map(mean_m).astype(float)
    pair_mean_l = pair["LLVM_Pass"].map(mean_l).astype(float)
    pair_weight = pair["mean"].astype(float) - pair_mean_m - pair_mean_l + mu
    pair_stability = pair["count"].astype(float).map(lambda c: min(1.0, math.log1p(float(c)) / denom))

    out = pd.DataFrame(
        {
            "Source": pair["MIR_Pass"].astype(str),
            "Target": pair["LLVM_Pass"].astype(str),
            "Type": "Interaction",
            "Weight": pair_weight,
            "Stability": pair_stability,
            "SelectedBy": "anova",
            "Count": pair["count"].astype(int),
        }
    )
    out = out[(out["Weight"].abs() > ANOVA_WEIGHT_EPS) | (out["Stability"] > 0.0)]
    if out.empty:
        return out

    score = (out["Weight"].abs() * (0.2 + 0.8 * out["Stability"].clip(0.0, 1.0))).astype(float)
    out = out.assign(_score=score)

    mode = str(select_mode or "topk").lower().strip()
    if mode == "all":
        out = out.sort_values("_score", ascending=False).drop(columns=["_score"])
        out = out.assign(SelectedBy="anova_all")
        return out

    if mode == "auto":
        auto_min = max(0, int(auto_min_edges))
        auto_max = max(auto_min, int(auto_max_edges))
        q = float(auto_score_quantile)
        q = max(0.0, min(1.0, q))

        cur = out
        if len(cur) > 0:
            q_down = q
            q_up = q
            for _ in range(50):
                thr = float(cur["_score"].quantile(q))
                sel = cur[cur["_score"] >= thr]
                if len(sel) < auto_min and q_down > 0.0:
                    q_down = max(0.0, q_down - 0.02)
                    q = q_down
                    continue
                if len(sel) > auto_max and q_up < 1.0:
                    q_up = min(1.0, q_up + 0.01)
                    q = q_up
                    continue
                cur = sel
                break

        cur = cur.sort_values("_score", ascending=False)
        if auto_max > 0 and len(cur) > auto_max:
            cur = cur.head(auto_max)
        if auto_min > 0 and len(cur) < auto_min and len(out) >= auto_min:
            cur = out.sort_values("_score", ascending=False).head(auto_min)

        return cur.drop(columns=["_score"]).assign(SelectedBy="anova_auto")

    if int(topk) > 0 and len(out) > int(topk):
        out = out.sort_values("_score", ascending=False).head(int(topk)).drop(columns=["_score"])
        out = out.assign(SelectedBy="anova_topk")
    else:
        out = out.sort_values("_score", ascending=False).drop(columns=["_score"])
        out = out.assign(SelectedBy="anova")

    return out

def save_edges_dataframe(df_edges, output_dir, filename="coupling_edges.csv"):
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, filename)
    df_edges.to_csv(output_path, index=False)
    return output_path

def run_lasso_stability_selection(X, y, feature_names, n_bootstrap=100):
    """
    Runs Lasso with stability selection (Bootstrap).
    """
    print(f"Running Stability Selection with {n_bootstrap} bootstraps...")
    
    n_samples, n_features = X.shape
    stability_scores = np.zeros(n_features)
    
    # Use LassoCV to automatically find alpha for each bootstrap? 
    # Or fix alpha based on a pilot run? LassoCV is safer but slower.
    # To speed up, we use a fixed alpha estimated from the whole dataset, or a small LassoCV per run.
    # Let's use LassoCV on full data first to get a sense of alpha.
    
    print("Tuning hyperparameters on full dataset...")
    # Standardize features? 
    # Our features are 0/1, but standardization is usually good for Lasso.
    # However, interaction terms (product of binary) are also 0/1.
    # Let's just fit intercept.
    
    model_cv = LassoCV(cv=5, random_state=42, n_jobs=-1, max_iter=10000)
    model_cv.fit(X, y)
    best_alpha = model_cv.alpha_
    print(f"Best alpha found: {best_alpha}")
    
    # Now run bootstrap with this alpha (or slightly randomized)
    coeffs_list = []
    
    for i in range(n_bootstrap):
        if i % 10 == 0:
            print(f"Bootstrap {i}/{n_bootstrap}")
            
        # Resample
        indices = np.random.choice(n_samples, n_samples, replace=True)
        X_res = X[indices]
        y_res = y[indices]
        
        # Fit Lasso
        # We use a slightly randomized alpha to encourage stability exploration? 
        # Or just fixed alpha. Standard Stability Selection uses RandomizedLasso, 
        # but here we just do Bootstrap + Lasso.
        lasso = Lasso(alpha=best_alpha, max_iter=10000)
        lasso.fit(X_res, y_res)
        
        # Record non-zero coefficients
        nonzero = np.abs(lasso.coef_) > 1e-5
        stability_scores[nonzero] += 1
        coeffs_list.append(lasso.coef_)
        
    stability_scores /= n_bootstrap
    avg_coeffs = np.mean(coeffs_list, axis=0)
    
    return stability_scores, avg_coeffs

def save_coupling_graph(stability_scores, avg_coeffs, feature_names, output_dir, threshold=0.5, min_edges=0):
    """
    Extracts significant interactions and saves them.
    """
    print("Extracting significant interactions...")
    interaction_rows = []
    for i, score in enumerate(stability_scores):
        name = feature_names[i]
        if "|" not in name:
            continue
        parts = name.split("|", 1)
        if len(parts) != 2:
            continue
        mir = parts[0]
        llvm = parts[1]
        try:
            weight = float(avg_coeffs[i])
        except Exception:
            weight = avg_coeffs[i]
        interaction_rows.append((mir, llvm, weight, float(score)))

    columns = ["Source", "Target", "Type", "Weight", "Stability", "SelectedBy"]
    edges = []
    selected = set()

    for mir, llvm, weight, score in interaction_rows:
        if score >= threshold:
            edges.append(
                {
                    "Source": mir,
                    "Target": llvm,
                    "Type": "Interaction",
                    "Weight": weight,
                    "Stability": score,
                    "SelectedBy": "threshold",
                }
            )
            selected.add((mir, llvm))

    if int(min_edges) > 0 and len(edges) < int(min_edges):
        remaining = [r for r in interaction_rows if (r[0], r[1]) not in selected]
        if TOPK_REQUIRE_NONZERO:
            remaining = [r for r in remaining if (r[3] > 0.0) or (abs(r[2]) > TOPK_COEF_EPS)]
        remaining.sort(key=lambda r: (r[3], abs(r[2])), reverse=True)
        need = int(min_edges) - len(edges)
        for mir, llvm, weight, score in remaining[:need]:
            edges.append(
                {
                    "Source": mir,
                    "Target": llvm,
                    "Type": "Interaction",
                    "Weight": weight,
                    "Stability": score,
                    "SelectedBy": "topk",
                }
            )
            selected.add((mir, llvm))

    df_edges = pd.DataFrame(edges, columns=columns)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "coupling_edges.csv")
    df_edges.to_csv(output_path, index=False)
    if df_edges.empty:
        print(f"Saved 0 edges to {output_path}")
    else:
        n_threshold = int((df_edges["SelectedBy"] == "threshold").sum())
        n_topk = int((df_edges["SelectedBy"] == "topk").sum())
        print(f"Saved {len(df_edges)} edges to {output_path} (threshold={n_threshold}, topk={n_topk})")
    return df_edges

def plot_coupling_graph(df_edges, mir_passes, llvm_passes, output_dir, title_prefix=None):
    if df_edges.empty:
        print("No significant edges to plot.")
        return

    plt.figure(figsize=(22, 18))
    G = nx.Graph()
    
    # Identify node types
    mir_set = set(mir_passes)
    llvm_set = set(llvm_passes)
    
    # Add nodes and edges
    nodes_in_graph = set()
    for _, row in df_edges.iterrows():
        u, v = row['Source'], row['Target']
        G.add_edge(u, v, weight=abs(row['Weight']), color='red' if row['Weight'] > 0 else 'blue')
        nodes_in_graph.add(u)
        nodes_in_graph.add(v)
        
    pos = nx.spring_layout(G, k=0.6, iterations=200, seed=42)
    
    # Split nodes for drawing
    mir_nodes = [n for n in nodes_in_graph if n in mir_set]
    llvm_nodes = [n for n in nodes_in_graph if n in llvm_set]
    # Handle nodes not in either set (fallback)
    other_nodes = [n for n in nodes_in_graph if n not in mir_set and n not in llvm_set]
    
    # Draw MIR nodes (Square 's', Yellow)
    nx.draw_networkx_nodes(G, pos, nodelist=mir_nodes, node_shape='s', 
                           node_color='yellow', node_size=1100, alpha=0.7, label='MIR Pass')
                           
    # Draw LLVM nodes (Circle 'o', LightBlue)
    nx.draw_networkx_nodes(G, pos, nodelist=llvm_nodes, node_shape='o', 
                           node_color='lightblue', node_size=1100, alpha=0.7, label='LLVM Pass')
                           
    if other_nodes:
        nx.draw_networkx_nodes(G, pos, nodelist=other_nodes, node_shape='o', 
                               node_color='lightgrey', node_size=900, alpha=0.5)

    # Draw edges
    edges = G.edges()
    colors = [G[u][v]['color'] for u,v in edges]
    weights = [max(0.2, min(G[u][v]['weight'] * 40, 6.0)) for u,v in edges]
    
    nx.draw_networkx_edges(G, pos, edge_color=colors, width=weights, alpha=0.55)
    
    # Draw labels
    nx.draw_networkx_labels(G, pos, font_size=8, font_family='sans-serif')
    
    # Create custom legend handles to avoid overlap and ensure clarity
    legend_elements = [
        Line2D([0], [0], marker='s', color='w', label='MIR Pass',
               markerfacecolor='yellow', markersize=15, alpha=0.7),
        Line2D([0], [0], marker='o', color='w', label='LLVM Pass',
               markerfacecolor='lightblue', markersize=15, alpha=0.7),
        Line2D([0], [0], color='red', lw=2, label='Conflict (+)', alpha=0.55),
        Line2D([0], [0], color='blue', lw=2, label='Synergy (-)', alpha=0.55)
    ]
    
    # Place legend outside the plot area
    plt.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(1, 1), 
               title="Node/Edge Types", fontsize=10, title_fontsize=12)
    
    title = "Cross-Level Coupling Graph\nSquare=MIR, Circle=LLVM | Red=Conflict(+), Blue=Synergy(-)"
    if title_prefix:
        title = f"{title_prefix}\n{title}"
    plt.title(title)
    plt.axis('off')
    os.makedirs(output_dir, exist_ok=True)
    plt.savefig(os.path.join(output_dir, "lasso_coupling_graph.png"), dpi=220, bbox_inches="tight")
    plt.savefig(os.path.join(output_dir, "lasso_coupling_graph.pdf"), bbox_inches="tight")
    print("Graph plot saved.")

if __name__ == "__main__":
    if HAVE_LASSO_STACK:
        csv_files = sorted(glob.glob(os.path.join(DATA_DIR, "*.csv")))
        if not csv_files:
            raise ValueError(f"No CSV files found in {DATA_DIR}")
        for csv_path in csv_files:
            bench = os.path.splitext(os.path.basename(csv_path))[0]
            out_dir = os.path.join(OUTPUT_DIR, bench)
            try:
                print(f"\n=== Processing: {bench} ===")
                X, y, feature_names, mir_passes, llvm_passes, full_df = load_and_preprocess_data(csv_path)

                df_edges = pd.DataFrame()
                method_used = None
                pair_counts = full_df.dropna(subset=["MIR_Pass", "LLVM_Pass"]).groupby(["MIR_Pass", "LLVM_Pass"]).size()
                max_pair_count = int(pair_counts.max()) if not pair_counts.empty else 0
                use_lasso = EDGE_METHOD in ("lasso", "auto")
                if EDGE_METHOD == "auto" and max_pair_count < int(AUTO_SKIP_LASSO_MAX_PAIR_COUNT_LT):
                    use_lasso = False

                if use_lasso:
                    stability, coeffs = run_lasso_stability_selection(X, y, feature_names, n_bootstrap=N_BOOTSTRAP)
                    df_edges = save_coupling_graph(
                        stability,
                        coeffs,
                        feature_names,
                        output_dir=out_dir,
                        threshold=EDGE_STABILITY_THRESHOLD,
                        min_edges=MIN_EDGES_PER_BENCH,
                    )
                    method_used = "lasso"

                if EDGE_METHOD == "anova" or (EDGE_METHOD == "auto" and df_edges.empty):
                    if bool(ANOVA_SAVE_ALL_EDGES):
                        df_edges_all = compute_anova_interaction_edges(
                            full_df,
                            min_pair_count=ANOVA_MIN_PAIR_COUNT,
                            topk=0,
                            select_mode="all",
                        )
                        save_edges_dataframe(df_edges_all, out_dir, filename="coupling_edges_all.csv")

                    df_edges = compute_anova_interaction_edges(
                        full_df,
                        min_pair_count=ANOVA_MIN_PAIR_COUNT,
                        topk=ANOVA_TOPK_EDGES,
                        select_mode=ANOVA_SELECT_MODE,
                        auto_min_edges=ANOVA_AUTO_MIN_EDGES,
                        auto_max_edges=ANOVA_AUTO_MAX_EDGES,
                        auto_score_quantile=ANOVA_AUTO_SCORE_QUANTILE,
                    )
                    save_edges_dataframe(df_edges, out_dir, filename="coupling_edges.csv")
                    method_used = "anova"

                plot_coupling_graph(df_edges, mir_passes, llvm_passes, output_dir=out_dir, title_prefix=f"{bench} ({method_used})")
                edges_csv = os.path.join(out_dir, "coupling_edges.csv")
                out_png = os.path.join(out_dir, "lasso_coupling_matrix_top25x25.png")
                plot_coupling_matrix_from_edges_csv(edges_csv, out_png, top_mir=25, top_llvm=25)
                print("\n=== Top Recovered Interactions ===")
                if not df_edges.empty:
                    print(df_edges.sort_values("Stability", ascending=False).head(10))
            except Exception as e:
                print(f"An error occurred for {bench}: {e}")
    else:
        for edges_csv in sorted(glob.glob(os.path.join(OUTPUT_DIR, "*", "coupling_edges.csv"))):
            out_dir = os.path.dirname(edges_csv)
            out_png = os.path.join(out_dir, "lasso_coupling_matrix_top25x25.png")
            plot_coupling_matrix_from_edges_csv(edges_csv, out_png, top_mir=25, top_llvm=25)
            print(f"Saved alternative matrix view to {out_png}")
            print(f"Saved alternative matrix view to {os.path.splitext(out_png)[0] + '.pdf'}")
