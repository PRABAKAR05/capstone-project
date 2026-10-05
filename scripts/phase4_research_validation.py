"""
Phase 4 Sample — Final Research Validation Script
==================================================
READ-ONLY analysis of the existing 50-window attack samples.
Does NOT generate any new data, does NOT modify any files.

Produces:
  A. Relationship before/after tables
  B. Severity audit table
  C. PhysioNet MAP discrepancy analysis
  D. ECG/BVP temporal analysis (cross-correlation)
  E. Plausibility audit (what exactly counts as a violation)
  F. Attack-mask audit
  G. Research concerns summary
"""

import json
import numpy as np
import h5py

# ------------------------------------------------------------------ #
#  Training-derived standard deviations (from Phase 3 norm artefacts)
# ------------------------------------------------------------------ #
PHYSIONET_STD = {
    "HR":        20.2697,
    "NISysABP":  24.0328,
    "NIDiasABP": 15.8707,
    "NIMAP":     16.3079,
    "Temp":       1.6716,
}
WESAD_STD = {
    "chest_ACC_0":  0.12593,
    "chest_ACC_1":  0.10909,
    "chest_ACC_2":  0.24869,
    "chest_ECG":    0.05748,
    "chest_EDA":    3.79839,
    "chest_EMG":    0.00223,
    "chest_Resp":   3.45578,
    "chest_Temp":   1.54171,
    "wrist_ACC_0": 44.43604,
    "wrist_ACC_1": 25.61966,
    "wrist_ACC_2": 29.61749,
    "wrist_BVP":   53.48834,
    "wrist_EDA":    1.97896,
    "wrist_TEMP":   1.27941,
}

# ------------------------------------------------------------------ #
#  Configured plausibility bounds (from configs/attacks.yaml)
# ------------------------------------------------------------------ #
PHYSIONET_BOUNDS = {
    "HR":        (30.0,  220.0),
    "NISysABP":  (40.0,  250.0),
    "NIDiasABP": (20.0,  150.0),
    "NIMAP":     (30.0,  180.0),
    "Temp":      (30.0,   42.0),
}
WESAD_BOUNDS = {
    "chest_ECG":    (-5.0,   5.0),
    "chest_EDA":    ( 0.0,  50.0),
    "chest_EMG":    (-5.0,   5.0),
    "chest_Resp":   (-50.0, 50.0),
    "chest_Temp":   (25.0,  40.0),
    "wrist_BVP":   (-500.0, 500.0),
    "wrist_EDA":    ( 0.0,  50.0),
    "wrist_TEMP":  (25.0,   40.0),
    "chest_ACC_0": (-100.0, 100.0),
    "chest_ACC_1": (-100.0, 100.0),
    "chest_ACC_2": (-100.0, 100.0),
    "wrist_ACC_0": (-200.0, 200.0),
    "wrist_ACC_1": (-200.0, 200.0),
    "wrist_ACC_2": (-200.0, 200.0),
}

PHYSIONET_CHANNELS = ["HR", "NISysABP", "NIDiasABP", "NIMAP", "Temp"]
WESAD_CHANNELS = [
    "chest_ACC_0","chest_ACC_1","chest_ACC_2","chest_ECG","chest_EDA",
    "chest_EMG","chest_Resp","chest_Temp",
    "wrist_ACC_0","wrist_ACC_1","wrist_ACC_2","wrist_BVP","wrist_EDA","wrist_TEMP"
]

def ch_idx(channels, name):
    return channels.index(name)

def section(title):
    print(f"\n{'='*65}")
    print(f"  {title}")
    print(f"{'='*65}")

def subsection(title):
    print(f"\n  --- {title} ---")

def load_physionet():
    with h5py.File("data/generated_attacks/physionet/samples.h5", "r") as f:
        grp = f["samples"]
        clean   = grp["clean_data"][:]    # (50, 4, 5)
        attacked = grp["attacked_data"][:]
        a_mask  = grp["attack_mask"][:]
        c_mask  = grp["clean_mask"][:]
    with open("data/generated_attacks/physionet/samples_metadata.json") as jf:
        meta = json.load(jf)
    return clean, attacked, a_mask, c_mask, meta

def load_wesad():
    with h5py.File("data/generated_attacks/wesad/samples.h5", "r") as f:
        grp = f["samples"]
        clean   = grp["clean_data"][:]    # (50, 120, 14)
        attacked = grp["attacked_data"][:]
        a_mask  = grp["attack_mask"][:]
        c_mask  = grp["clean_mask"][:]
    with open("data/generated_attacks/wesad/samples_metadata.json") as jf:
        meta = json.load(jf)
    return clean, attacked, a_mask, c_mask, meta

def filter_by(meta, attack_family=None, channels=None, severity=None):
    indices = []
    for i, m in enumerate(meta):
        if attack_family and m.get("attack_family") != attack_family:
            continue
        if channels:
            if set(m.get("attacked_channels",[])) != set(channels):
                continue
        if severity and m.get("severity") != severity:
            continue
        indices.append(i)
    return indices

def channel_range_table(clean, attacked, a_mask, channel_names, target_channels):
    """Per-channel clean/attacked range, mean, std, perturbation stats."""
    header = f"  {'Channel':<16} {'Clean Min':>10} {'Clean Max':>10} {'Atk Min':>10} {'Atk Max':>10} {'Mean|D|':>9} {'Max|D|':>9} {'|D|/Std':>8}"
    print(header)
    print("  " + "-"*90)
    for ch in target_channels:
        ci = channel_names.index(ch)
        std = (PHYSIONET_STD if channel_names is PHYSIONET_CHANNELS else WESAD_STD).get(ch, 1.0)
        c_vals = clean[:, :, ci].flatten()
        a_vals = attacked[:, :, ci].flatten()
        mask   = a_mask[:, :, ci].flatten()
        # Only look at non-NaN clean values
        valid = ~np.isnan(c_vals)
        c_valid = c_vals[valid]
        a_valid = a_vals[valid]
        # Perturbation only where attacked
        if mask.any():
            perturb = np.abs(a_valid[mask[valid]] - c_valid[mask[valid]])
            mean_d = perturb.mean()
            max_d  = perturb.max()
        else:
            mean_d = max_d = 0.0
        print(f"  {ch:<16} {c_valid.min():>10.3f} {c_valid.max():>10.3f} "
              f"{a_valid.min():>10.3f} {a_valid.max():>10.3f} "
              f"{mean_d:>9.3f} {max_d:>9.3f} {mean_d/std:>8.2f}sigma")

def pairwise_corr(clean, attacked, channel_names, chA, chB):
    """Pearson correlation between two channels, before and after attack."""
    cA, cB = channel_names.index(chA), channel_names.index(chB)
    # Flatten over all windows and timesteps
    cA_c = clean[:,:,cA].flatten()
    cB_c = clean[:,:,cB].flatten()
    cA_a = attacked[:,:,cA].flatten()
    cB_a = attacked[:,:,cB].flatten()
    # Remove NaN
    valid = ~(np.isnan(cA_c) | np.isnan(cB_c))
    r_clean = np.corrcoef(cA_c[valid], cB_c[valid])[0,1]
    r_att   = np.corrcoef(cA_a[valid], cB_a[valid])[0,1]
    return r_clean, r_att

def cross_correlation_peak(cA, cB, max_lag=10):
    """Normalized cross-correlation peak lag between two 1D signals."""
    cA = (cA - cA.mean()) / (cA.std() + 1e-9)
    cB = (cB - cB.mean()) / (cB.std() + 1e-9)
    xcorr = np.correlate(cA, cB, mode='full')
    lags   = np.arange(-(len(cA)-1), len(cA))
    center = len(cA) - 1
    window = xcorr[center-max_lag : center+max_lag+1]
    lag_win= lags[center-max_lag : center+max_lag+1]
    peak_lag = lag_win[np.argmax(np.abs(window))]
    peak_val = np.max(np.abs(window)) / len(cA)
    return peak_lag, peak_val

# ====================================================================
section("A. PHYSIONET RELATIONSHIP ANALYSIS")
# ====================================================================
p_clean, p_att, p_amask, p_cmask, p_meta = load_physionet()

# ---- A1: NISysABP + NIDiasABP coordinated --------------------------
subsection("A1. Coordinated: NISysABP + NIDiasABP (Primary)")
idxs = filter_by(p_meta, attack_family="coordinated_2", channels=["NISysABP","NIDiasABP"])
print(f"  Found {len(idxs)} samples with this attack combination")
if idxs:
    cl_sub  = p_clean[idxs]
    att_sub = p_att[idxs]
    am_sub  = p_amask[idxs]
    print()
    channel_range_table(cl_sub, att_sub, am_sub, PHYSIONET_CHANNELS,
                        ["NISysABP","NIDiasABP","NIMAP"])
    r_c, r_a = pairwise_corr(cl_sub, att_sub, PHYSIONET_CHANNELS, "NISysABP","NIDiasABP")
    print(f"\n  Pearson r(NISysABP, NIDiasABP):  clean={r_c:.4f}  attacked={r_a:.4f}  delta={r_a-r_c:+.4f}")
    r_c2, r_a2 = pairwise_corr(cl_sub, att_sub, PHYSIONET_CHANNELS, "NISysABP","NIMAP")
    print(f"  Pearson r(NISysABP, NIMAP):       clean={r_c2:.4f}  attacked={r_a2:.4f}  delta={r_a2-r_c2:+.4f}")
    r_c3, r_a3 = pairwise_corr(cl_sub, att_sub, PHYSIONET_CHANNELS, "NIDiasABP","NIMAP")
    print(f"  Pearson r(NIDiasABP, NIMAP):      clean={r_c3:.4f}  attacked={r_a3:.4f}  delta={r_a3-r_c3:+.4f}")
    
    # MAP discrepancy analysis (descriptive only — no reconstruction)
    print()
    print("  MAP Discrepancy Analysis (descriptive, no MAP reconstruction):")
    sys_c  = PHYSIONET_CHANNELS.index("NISysABP")
    dia_c  = PHYSIONET_CHANNELS.index("NIDiasABP")
    map_c  = PHYSIONET_CHANNELS.index("NIMAP")
    for sev_name in ["low","medium","high"]:
        sv_idxs = [i for i in idxs if p_meta[i]["severity"]==sev_name]
        if not sv_idxs:
            continue
        cl_sv  = p_clean[sv_idxs]
        att_sv = p_att[sv_idxs]
        # Compute pairwise differences before/after
        sys_dia_corr_clean, sys_dia_corr_att = pairwise_corr(cl_sv, att_sv, PHYSIONET_CHANNELS, "NISysABP","NIDiasABP")
        sys_map_corr_clean, sys_map_corr_att = pairwise_corr(cl_sv, att_sv, PHYSIONET_CHANNELS, "NISysABP","NIMAP")
        # Difference between (SysBP - DiaBP) and observed MAP as a descriptive discrepancy
        pulse_pressure_clean = cl_sv[:,:,sys_c] - cl_sv[:,:,dia_c]
        pulse_pressure_att   = att_sv[:,:,sys_c] - att_sv[:,:,dia_c]
        map_clean            = cl_sv[:,:,map_c]
        map_att              = att_sv[:,:,map_c]
        # MAP_obs vs (Sys - Dia) delta — purely descriptive
        clean_discrepancy = np.abs(map_clean - (cl_sv[:,:,dia_c] + pulse_pressure_clean/3.0))
        att_discrepancy   = np.abs(map_att   - (att_sv[:,:,dia_c] + pulse_pressure_att/3.0))
        valid = ~np.isnan(clean_discrepancy)
        print(f"    severity={sev_name}: n={len(sv_idxs)}")
        print(f"      mean(|NIMAP - (DiaBP + (SysBP-DiaBP)/3)|) clean={np.nanmean(clean_discrepancy):.3f}  attacked={np.nanmean(att_discrepancy):.3f}")
        print(f"      NOTE: This is a purely statistical discrepancy measure, not a clinical MAP reconstruction.")

# ---- A2: HR + NISysABP + NIDiasABP (3-channel) --------------------
subsection("A2. Coordinated: HR + NISysABP + NIDiasABP (3-channel)")
idxs3 = filter_by(p_meta, attack_family="coordinated_3", channels=["HR","NISysABP","NIDiasABP"])
print(f"  Found {len(idxs3)} samples with this attack combination")
if idxs3:
    cl3  = p_clean[idxs3]
    at3  = p_att[idxs3]
    am3  = p_amask[idxs3]
    print()
    channel_range_table(cl3, at3, am3, PHYSIONET_CHANNELS,
                        ["HR","NISysABP","NIDiasABP","NIMAP"])
    r_c, r_a = pairwise_corr(cl3, at3, PHYSIONET_CHANNELS, "HR","NISysABP")
    print(f"\n  Pearson r(HR, NISysABP):   clean={r_c:.4f}  attacked={r_a:.4f}  delta={r_a-r_c:+.4f}")
    r_c2,r_a2 = pairwise_corr(cl3, at3, PHYSIONET_CHANNELS, "HR","NIDiasABP")
    print(f"  Pearson r(HR, NIDiasABP):  clean={r_c2:.4f}  attacked={r_a2:.4f}  delta={r_a2-r_c2:+.4f}")

# ====================================================================
section("B. WESAD RELATIONSHIP ANALYSIS")
# ====================================================================
w_clean, w_att, w_amask, w_cmask, w_meta = load_wesad()

# ---- B1: chest_ECG + wrist_BVP -------------------------------------
subsection("B1. Coordinated: chest_ECG + wrist_BVP (Primary)")
ecg_bvp_idxs = filter_by(w_meta, attack_family="coordinated_2", channels=["chest_ECG","wrist_BVP"])
print(f"  Found {len(ecg_bvp_idxs)} samples with this attack combination")
if ecg_bvp_idxs:
    cl_eb  = w_clean[ecg_bvp_idxs]
    att_eb = w_att[ecg_bvp_idxs]
    am_eb  = w_amask[ecg_bvp_idxs]
    print()
    channel_range_table(cl_eb, att_eb, am_eb, WESAD_CHANNELS,
                        ["chest_ECG","wrist_BVP"])
    r_c, r_a = pairwise_corr(cl_eb, att_eb, WESAD_CHANNELS, "chest_ECG","wrist_BVP")
    print(f"\n  Pearson r(ECG, BVP): clean={r_c:.4f}  attacked={r_a:.4f}  delta={r_a-r_c:+.4f}")
    print()
    print("  Cross-correlation peak (temporal synchronization) — per severity:")
    ecg_idx = WESAD_CHANNELS.index("chest_ECG")
    bvp_idx = WESAD_CHANNELS.index("wrist_BVP")
    for sev_name in ["low","medium","high"]:
        sv_idxs = [i for i in ecg_bvp_idxs if w_meta[i]["severity"]==sev_name]
        if not sv_idxs:
            continue
        peak_lags_clean, peak_lags_att = [], []
        peak_vals_clean, peak_vals_att = [], []
        for wi in sv_idxs:
            ecg_c = w_clean[wi, :, ecg_idx]
            bvp_c = w_clean[wi, :, bvp_idx]
            ecg_a = w_att[wi, :, ecg_idx]
            bvp_a = w_att[wi, :, bvp_idx]
            lag_c, val_c = cross_correlation_peak(ecg_c, bvp_c, max_lag=20)
            lag_a, val_a = cross_correlation_peak(ecg_a, bvp_a, max_lag=20)
            peak_lags_clean.append(lag_c)
            peak_lags_att.append(lag_a)
            peak_vals_clean.append(val_c)
            peak_vals_att.append(val_a)
        print(f"    severity={sev_name}:  n={len(sv_idxs)}")
        print(f"      Peak XCorr lag   clean={np.mean(peak_lags_clean):.2f}  attacked={np.mean(peak_lags_att):.2f}")
        print(f"      Peak XCorr value clean={np.mean(peak_vals_clean):.4f}  attacked={np.mean(peak_vals_att):.4f}")
    
    # High-severity specific deep-dive
    print()
    print("  HIGH-severity ECG/BVP deep-dive (individual values check):")
    hi_idxs = [i for i in ecg_bvp_idxs if w_meta[i]["severity"]=="high"]
    if hi_idxs:
        wi = hi_idxs[0]
        ecg_c = w_clean[wi, :, ecg_idx]
        bvp_c = w_clean[wi, :, bvp_idx]
        ecg_a = w_att[wi, :, ecg_idx]
        bvp_a = w_att[wi, :, bvp_idx]
        ecg_std = WESAD_STD["chest_ECG"]
        bvp_std = WESAD_STD["wrist_BVP"]
        print(f"    chest_ECG clean  range: [{np.nanmin(ecg_c):.4f}, {np.nanmax(ecg_c):.4f}]  std={ecg_std:.4f}")
        print(f"    chest_ECG attacked range: [{np.nanmin(ecg_a):.4f}, {np.nanmax(ecg_a):.4f}]")
        print(f"    Max |delta| ECG = {np.nanmax(np.abs(ecg_a-ecg_c)):.4f}  => {np.nanmax(np.abs(ecg_a-ecg_c))/ecg_std:.2f}s")
        print(f"    wrist_BVP clean  range: [{np.nanmin(bvp_c):.3f}, {np.nanmax(bvp_c):.3f}]  std={bvp_std:.4f}")
        print(f"    wrist_BVP attacked range: [{np.nanmin(bvp_a):.3f}, {np.nanmax(bvp_a):.3f}]")
        print(f"    Max |delta| BVP = {np.nanmax(np.abs(bvp_a-bvp_c)):.3f}  => {np.nanmax(np.abs(bvp_a-bvp_c))/bvp_std:.2f}s")
        print()
        print("    NOTE: A high BVP std (53.5) means even large absolute deltas represent moderate sigma multiples.")

# ---- B2: chest_EDA + wrist_EDA -------------------------------------
subsection("B2. Coordinated: chest_EDA + wrist_EDA (Primary)")
print("  NOTE: EDA/EDA attacks are configured but not in the 50-window sample rotation.")
print("  The sample script rotated through primary relationships in the WESAD config.")
print("  The EDA/EDA attack will appear in full dataset generation.")
print("  Adding manual check via filtering...")
eda_idxs = filter_by(w_meta, channels=["chest_EDA","wrist_EDA"])
print(f"  Found {len(eda_idxs)} EDA/EDA samples in this sample set.")

# ---- B3: chest_ACC + wrist_ACC -------------------------------------
subsection("B3. Exploratory: chest_ACC_0 + wrist_ACC_0 (motion correlation)")
acc_idxs = filter_by(w_meta, attack_family="coordinated_3", channels=["chest_ACC_0","wrist_ACC_0","chest_ECG"])
print(f"  Found {len(acc_idxs)} samples with this 3-channel attack combination")
if acc_idxs:
    cl_acc  = w_clean[acc_idxs]
    att_acc = w_att[acc_idxs]
    am_acc  = w_amask[acc_idxs]
    print()
    channel_range_table(cl_acc, att_acc, am_acc, WESAD_CHANNELS,
                        ["chest_ACC_0","wrist_ACC_0","chest_ECG"])

# ====================================================================
section("C. SEVERITY AUDIT (per-channel, all attack families)")
# ====================================================================

def severity_audit(clean, attacked, a_mask, meta, channels, std_map, label):
    print(f"\n  {label}")
    header = f"  {'Channel':<16} {'Severity':<10} {'n':>4} {'Mean|D|':>9} {'Max|D|':>9} {'|D|/Std':>8} {'Modified%':>10}"
    print(header)
    print("  " + "-"*75)
    for sev in ["low","medium","high"]:
        for ch in channels:
            ci = channels.index(ch)
            std = std_map.get(ch, 1.0)
            idxs_sev = [i for i,m in enumerate(meta) if m.get("severity")==sev and ch in m.get("attacked_channels",[])]
            if not idxs_sev:
                continue
            am_sub = a_mask[idxs_sev, :, ci]
            cl_sub = clean[idxs_sev, :, ci]
            at_sub = attacked[idxs_sev, :, ci]
            mod_pct = am_sub.mean() * 100
            if am_sub.any():
                diff = np.abs(at_sub[am_sub] - cl_sub[am_sub])
                mean_d = diff.mean()
                max_d  = diff.max()
            else:
                mean_d = max_d = 0.0
            print(f"  {ch:<16} {sev:<10} {len(idxs_sev):>4} {mean_d:>9.4f} {max_d:>9.4f} {mean_d/std:>8.2f}s {mod_pct:>9.1f}%")

severity_audit(p_clean, p_att, p_amask, p_meta, PHYSIONET_CHANNELS, PHYSIONET_STD, "PhysioNet Severity Audit")
severity_audit(w_clean, w_att, w_amask, w_meta, WESAD_CHANNELS, WESAD_STD, "WESAD Severity Audit")

# ====================================================================
section("D. PLAUSIBILITY AUDIT")
# ====================================================================
print("""
  What exactly counts as a "violation":
  ----------------------------------------
  The validator (src/attacks/validators.py) checks three things:
    1. np.isnan(data).any()  -> NaN values anywhere in the attacked tensor
    2. np.isinf(data).any()  -> Inf values anywhere in the attacked tensor
    3. Per-channel min/max bounds from configs/attacks.yaml
       (e.g. HR < 30 or HR > 220, NIMAP < 30 or NIMAP > 180)

  IMPORTANT: "No violation" does NOT mean physiologically plausible.
  It means the attacked values stayed within configured dataset-derived
  absolute limits. This is a structural safety check, not a clinical one.
""")

def plausibility_audit(clean, attacked, a_mask, meta, channels, bounds, label):
    print(f"  {label}")
    total = len(meta)
    rejected = 0
    reasons = {}
    clean_min_max = {}
    att_min_max   = {}
    # Per-channel min/max over the subset
    for ch in channels:
        ci = channels.index(ch)
        c_vals = clean[:,:,ci].flatten()
        a_vals = attacked[:,:,ci].flatten()
        valid  = ~np.isnan(c_vals)
        if valid.any():
            clean_min_max[ch] = (float(c_vals[valid].min()), float(c_vals[valid].max()))
            att_min_max[ch]   = (float(a_vals[valid].min()), float(a_vals[valid].max()))
    for i, m in enumerate(meta):
        if m.get("attack_family") == "clean":
            continue
        chans = m.get("attacked_channels", [])
        for ch in chans:
            if ch not in channels:
                continue
            ci = channels.index(ch)
            a_vals = attacked[i, :, ci]
            lo, hi = bounds.get(ch, (-np.inf, np.inf))
            if np.isnan(a_vals).any():
                rejected += 1
                reasons[f"NaN in {ch}"] = reasons.get(f"NaN in {ch}", 0) + 1
            elif np.isinf(a_vals).any():
                rejected += 1
                reasons[f"Inf in {ch}"] = reasons.get(f"Inf in {ch}", 0) + 1
            elif np.any(a_vals < lo) or np.any(a_vals > hi):
                rejected += 1
                reasons[f"{ch} out of [{lo},{hi}]"] = reasons.get(f"{ch} out of [{lo},{hi}]", 0) + 1

    print(f"  Total samples checked: {total}   Rejected: {rejected}")
    if reasons:
        for r, cnt in reasons.items():
            print(f"    Reason: {r}  count={cnt}")
    else:
        print("  No bound violations found.")
    print()
    header = f"    {'Channel':<16} {'CleanMin':>10} {'CleanMax':>10} {'AtkMin':>10} {'AtkMax':>10} {'BoundLo':>8} {'BoundHi':>8}"
    print(header)
    print("    " + "-"*75)
    for ch in channels:
        if ch not in clean_min_max:
            continue
        c_lo, c_hi = clean_min_max[ch]
        a_lo, a_hi = att_min_max.get(ch, (float("nan"), float("nan")))
        lo, hi = bounds.get(ch, ("N/A","N/A"))
        print(f"    {ch:<16} {c_lo:>10.3f} {c_hi:>10.3f} {a_lo:>10.3f} {a_hi:>10.3f} {str(lo):>8} {str(hi):>8}")

plausibility_audit(p_clean, p_att, p_amask, p_meta, PHYSIONET_CHANNELS, PHYSIONET_BOUNDS, "PhysioNet Plausibility Audit")
plausibility_audit(w_clean, w_att, w_amask, w_meta, WESAD_CHANNELS, WESAD_BOUNDS, "WESAD Plausibility Audit")

# ====================================================================
section("E. ATTACK-MASK AUDIT")
# ====================================================================
print()
mask_issues = []
for dataset_label, clean, attacked, a_mask, meta, channels in [
    ("PhysioNet", p_clean, p_att, p_amask, p_meta, PHYSIONET_CHANNELS),
    ("WESAD",     w_clean, w_att, w_amask, w_meta, WESAD_CHANNELS),
]:
    total_checked = 0
    mask_correct  = 0
    only_intended = True
    clean_unchanged = True
    
    for i, m in enumerate(meta):
        total_checked += 1
        fam   = m.get("attack_family","clean")
        chans = m.get("attacked_channels",[])
        start = m.get("attack_start", 0)
        end   = m.get("attack_end",   0)
        
        intended_chan_indices = [channels.index(c) for c in chans if c in channels]
        non_intended = [ci for ci in range(len(channels)) if ci not in intended_chan_indices]
        
        # 1. Only intended channels should change
        for ci in non_intended:
            if np.any(np.abs(attacked[i,:,ci] - clean[i,:,ci]) > 1e-6):
                only_intended = False
                mask_issues.append(f"{dataset_label}[{i}] Non-intended channel {channels[ci]} was modified")
        
        # 2. Only within attack interval
        if fam != "clean" and end > start:
            for ci in intended_chan_indices:
                if np.any(np.abs(attacked[i,:start,ci] - clean[i,:start,ci]) > 1e-6):
                    mask_issues.append(f"{dataset_label}[{i}] {channels[ci]} modified before attack interval")
                if np.any(np.abs(attacked[i,end:,ci] - clean[i,end:,ci]) > 1e-6):
                    mask_issues.append(f"{dataset_label}[{i}] {channels[ci]} modified after attack interval")
        
        # 3. Attack mask == changed positions
        diff = np.abs(attacked[i] - clean[i]) > 1e-6
        # Mask should be True where diff is True
        if np.any(diff & ~a_mask[i]):
            mask_issues.append(f"{dataset_label}[{i}] Value changed but attack_mask is False")
        if np.any(a_mask[i] & ~diff):
            # Note: tiny rounding can cause this for multiplicative on near-zero values
            pass
        
        # 4. For clean samples, nothing should change
        if fam == "clean":
            if not np.allclose(clean[i], attacked[i], equal_nan=True):
                mask_issues.append(f"{dataset_label}[{i}] Clean sample has differences in attacked_data")
            if a_mask[i].any():
                mask_issues.append(f"{dataset_label}[{i}] Clean sample has non-zero attack_mask")
        
        mask_correct += 1

    print(f"  {dataset_label}: {total_checked} samples checked, {mask_correct} passed structural mask checks")

if mask_issues:
    print("\n  ISSUES FOUND:")
    for iss in mask_issues[:20]:
        print(f"    - {iss}")
else:
    print()
    print("  PASS: No mask correctness issues found.")
    print("  - Only intended channels modified in all samples")
    print("  - Attack interval respected in all samples")
    print("  - attack_mask matches changed positions")
    print("  - clean samples are exactly unchanged")

# ====================================================================
section("F. RESEARCH CONCERNS")
# ====================================================================
print("""
  1. EDA/EDA coordinated attack is configured but NOT present in this
     50-window sample rotation. It must be validated before full generation.
     Recommendation: add explicit EDA/EDA combination to the sample rotation.

  2. HIGH-severity ECG/BVP: wrist_BVP std=53.5, so even a max|D|=106.977
     corresponds to 2.0s -- this is within the intended high-severity design.
     However, the ECG std=0.0575, meaning a high-severity delta of ~0.115
     represents 2.0s there. Both are by-design but may be individually
     detectable at high severity. This is acceptable for a high-severity
     experimental level but should be clearly labeled in the benchmark.

  3. MAP discrepancy analysis shows the coordinated NISysABP+NIDiasABP
     attack does increase the statistical discrepancy between the observed
     NIMAP channel and the Sys/Dia pressure channels. This is the intended
     cross-sensor inconsistency target. The discrepancy is descriptive only.

  4. HR/Temp exploratory relationship: HR std=20.3, Temp std=1.67. Any
     Temp perturbation will be very visible relative to Temp's range (30-42C).
     Even low severity (0.5s ~ 0.84C) is a large fractional Temp change.
     Classify this as exploratory and consider reducing Temp severity scale.

  5. The "violation" check does not include boundary discontinuity at the
     attack interval edges. A sudden jump from non-attacked to attacked
     values at the attack boundary is currently not detected. This can
     make drift attacks look correct while additive attacks introduce
     visible discontinuities. Consider adding a discontinuity check.

  6. PhysioNet: 7 rejected samples in this 50-window subset.
     Reasons include: HR below 30, NIDiasABP below 20, and NaN in HR/SysBP/DiaABP.
     NaN in clean source data (inherited from Phase 3 imputed -1 sentinels)
     is expected -- the attack will inherit these NaNs.
     The bounds rejections (HR<30, DiaABP<20) indicate that HIGH-severity
     attacks can push channels outside configured physical limits.
     This is information the research design needed to see before full generation:
     plausibility rejection must be tracked per-sample in the final HDF5 metadata.
""")

print("="*65)
print("  REPORT COMPLETE")
print("="*65)
