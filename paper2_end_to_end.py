#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Paper 2 (CEJ) End-to-End Analysis Pipeline
=========================================

Title (methods alignment):
    "Beyond Porosity: A Bayesian Model-Comparison Framework for Biomass Retention
     in Anaerobic Packed Beds Using Hydraulic Signatures"

What this script does (end-to-end):
  1) Loads the Excel workbook you provided ("DEng data.xlsx").
  2) Cleans and tidies:
       - Packing materials (porosity, void volume, retention mass balance)
       - Underdrain system (ΔP vs superficial velocity; particle/bed parameters)
  3) Fits Stage I Bayesian Darcy–Forchheimer models to pressure-drop curves to infer
     medium-specific hydraulic signatures (permeability k and Forchheimer β).
  4) Derives geometry-conditioned surrogates (apparent shape factor Ψ and GDI).
  5) Fits Stage II Bayesian retention models under competing hypotheses:
       - Volumetric model (porosity-only)
       - Hydraulic-signature model (k, β)
       - Combined model (porosity + k + β)
       (Optional) Ψ/GDI model can be toggled on.
  6) Performs Bayesian model comparison (PSIS-LOO), posterior predictive checks,
     and computes posterior ranking probabilities.
  7) Saves:
       - Cleaned CSV datasets
       - Posterior samples (NetCDF)
       - Posterior summaries (CSV + LaTeX)
       - Model-comparison tables (CSV + LaTeX)
       - Figures (PNG + PDF)
       - Tidy posterior draws and predictions for re-use

How to run:
  pip install -r requirements.txt
  python paper2_end_to_end.py --excel_path "DEng data.xlsx" --out_dir "paper2_outputs"

Notes:
  - This script is designed to be robust to your sheet formatting (unnamed columns).
  - The underdrain sheet labels columns as "Pumice stone 1..5" but parameter rows
    indicate these correspond to the 5 media types (medium pumice, pea gravels,
    glass marbles, small pumice, white pebbles). The script resolves names using
    recorded mean diameter values.
  - With only ~5 media types for retention, Stage II inference is inherently low-power;
    therefore, the paper’s contribution is framed as Bayesian evidence/model-comparison
    rather than definitive causal mechanism proof.

Author: (fill)
"""

import argparse
import os
from pathlib import Path
import re
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

import numpy as np
import pandas as pd

# Plotting
import matplotlib.pyplot as plt

# Bayesian stack
try:
    import pymc as pm
    import arviz as az
except Exception as e:  # pragma: no cover
    raise ImportError(
        "PyMC and ArviZ are required. Install with: pip install -r requirements.txt\n"
        f"Original error: {e}"
    )

# ----------------------------
# Utilities
# ----------------------------

def mkdirp(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def canonicalize_medium(name: str) -> str:
    """Normalize media names across sheets."""
    if name is None or (isinstance(name, float) and np.isnan(name)):
        return ""
    s = str(name).strip().lower()
    s = re.sub(r"\s+", " ", s)

    # Fix common misspellings
    s = s.replace("marbels", "marbles").replace("marbets", "marbles")
    s = s.replace("pumce", "pumice").replace("pumce", "pumice")
    s = s.replace("gravels", "gravels")
    s = s.replace("pebbles", "pebbles")
    s = s.replace("stone", "stones").replace("stones s", "stones")

    # Canonical categories
    if "pea" in s and "gravel" in s:
        return "Pea gravels"
    if "white" in s and "pebble" in s:
        return "White pebbles"
    if "glass" in s and "marble" in s:
        return "Glass marbles"
    if "small" in s and "pumice" in s:
        return "Small pumice stones"
    if ("medium" in s or "medium-sized" in s) and "pumice" in s:
        return "Medium pumice stones"
    if "pumice" in s and "medium" not in s and "small" not in s:
        # fallback
        return "Pumice stones"
    # If already nice title case
    return str(name).strip()

def safe_float(x):
    try:
        return float(x)
    except Exception:
        return np.nan

def df_to_latex_booktabs(df: pd.DataFrame, caption: str, label: str) -> str:
    """Return LaTeX table string with booktabs. Caller writes to .tex file."""
    latex = df.to_latex(index=False, escape=False, longtable=False,
                        caption=caption, label=label,
                        float_format=lambda v: f"{v:.4g}" if isinstance(v, (float, np.floating)) else str(v))
    # Ensure booktabs style
    latex = latex.replace("\\toprule", "\\toprule")
    return latex

# ----------------------------
# Data loaders (robust parsing)
# ----------------------------

def load_packing_materials(excel_path: Path) -> pd.DataFrame:
    """
    Parse the 'Packing materials' sheet into tidy format:
      medium, total_volume_ml, void_volume_ml, porosity, sludge_volume_ml,
      sludge_mass_g, washed_out_g, retained_g, retention_capacity
    """
    raw = pd.read_excel(excel_path, sheet_name="Packing materials", header=None)

    # Find the row containing "Packing material"
    target = "Packing material"
    idx = None
    for r in range(raw.shape[0]):
        for c in range(raw.shape[1]):
            if isinstance(raw.iat[r, c], str) and raw.iat[r, c].strip() == target:
                idx = r
                label_col = c
                break
        if idx is not None:
            break
    if idx is None:
        raise ValueError("Could not locate 'Packing material' row in 'Packing materials' sheet.")

    # Materials are to the right of the label cell
    # In your workbook: label in column 1, materials in columns 2..6
    materials = []
    value_cols = []
    for c in range(label_col + 1, raw.shape[1]):
        v = raw.iat[idx, c]
        if pd.isna(v):
            continue
        materials.append(canonicalize_medium(v))
        value_cols.append(c)
    if len(materials) < 3:
        raise ValueError("Could not detect packing material columns reliably. Check sheet layout.")

    # Variables are in subsequent rows until a blank label row
    rows = []
    for r in range(idx + 1, raw.shape[0]):
        var = raw.iat[r, label_col]
        if pd.isna(var):
            # stop if we hit a blank row after we've collected enough
            if len(rows) > 0:
                # allow a few blank rows but stop at first long blank span
                break
            continue
        var = str(var).strip()
        # Stop if table repeats
        if var.lower() == target.lower():
            break
        vals = [raw.iat[r, c] for c in value_cols]
        rows.append((var, vals))

    # Build wide table then pivot
    wide = pd.DataFrame({ "variable": [v for v,_ in rows]})
    for m, c in zip(materials, range(len(materials))):
        wide[m] = [vals[c] for _, vals in rows]

    # Long tidy
    tidy_records = []
    for m in materials:
        rec = {"medium": m}
        for _, row in wide.iterrows():
            rec[row["variable"]] = row[m]
        tidy_records.append(rec)
    tidy = pd.DataFrame(tidy_records)

    # Normalize column names we care about
    col_map = {
        "Total volume (mL)": "total_volume_ml",
        "Void volume (mL)": "void_volume_ml",
        "Porosity": "porosity",
        "Volume of sludge (mL)": "sludge_volume_ml",
        "Mass of sludge (g)": "sludge_mass_g",
        "Mass of sludge washed out (g)": "washed_out_g",
        "Mass of sludge retained (g)": "retained_g",
        "Sludge retention capacity": "retention_capacity"
    }
    # Rename if present
    for k,v in col_map.items():
        if k in tidy.columns:
            tidy.rename(columns={k:v}, inplace=True)

    # Coerce numerics
    for c in ["total_volume_ml","void_volume_ml","porosity","sludge_volume_ml",
              "sludge_mass_g","washed_out_g","retained_g","retention_capacity"]:
        if c in tidy.columns:
            tidy[c] = pd.to_numeric(tidy[c], errors="coerce")

    # Consistency check
    if {"sludge_mass_g","washed_out_g","retained_g"}.issubset(tidy.columns):
        tidy["retained_check_g"] = tidy["sludge_mass_g"] - tidy["washed_out_g"]
        tidy["retained_check_error_g"] = tidy["retained_g"] - tidy["retained_check_g"]

    return tidy


def load_underdrain_system(excel_path: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    Parse 'Underdrain system' into:
      - params_df: medium-level parameters (mean diameter, eq diameter, porosity, etc.)
      - long_df: long format pressure drop curves: medium, u_mps, dp_pa
      - meta: {mu, rho, L, A} etc where available
    """
    raw = pd.read_excel(excel_path, sheet_name="Underdrain system", header=None)

    # Identify the row with "Superficial velocity (m/s)"
    vel_row = None
    for r in range(raw.shape[0]):
        for c in range(raw.shape[1]):
            if isinstance(raw.iat[r,c], str) and raw.iat[r,c].strip().lower() == "superficial velocity (m/s)":
                vel_row = r
                vel_col = c
                break
        if vel_row is not None:
            break
    if vel_row is None:
        raise ValueError("Could not find 'Superficial velocity (m/s)' in 'Underdrain system' sheet.")

    # Parameter table starts at row where 'Parameters' appears in same column as labels (vel_col)
    param_row = None
    for r in range(vel_row):
        if isinstance(raw.iat[r, vel_col], str) and raw.iat[r, vel_col].strip().lower() == "parameters":
            param_row = r
            break
    if param_row is None:
        raise ValueError("Could not find 'Parameters' header row in 'Underdrain system' sheet.")

    # Media columns: columns immediately to the right of vel_col until we hit blank, but we know 5 columns
    # In your workbook these are vel_col+1 ... vel_col+5
    media_cols = list(range(vel_col+1, vel_col+6))
    media_headers = [raw.iat[param_row, c] for c in media_cols]

    # Extract parameter rows from param_row+1 to vel_row-1
    param_names = []
    param_values = {c: [] for c in media_cols}
    for r in range(param_row+1, vel_row):
        p = raw.iat[r, vel_col]
        if pd.isna(p):
            continue
        p = str(p).strip()
        param_names.append(p)
        for c in media_cols:
            param_values[c].append(raw.iat[r, c])

    params_wide = pd.DataFrame({"parameter": param_names})
    for c, h in zip(media_cols, media_headers):
        params_wide[str(h)] = param_values[c]

    # Build medium-level params by transposing
    params_long_records = []
    for c, h in zip(media_cols, media_headers):
        rec = {"underdrain_col": str(h)}
        for p, v in zip(param_names, param_values[c]):
            rec[p] = v
        params_long_records.append(rec)
    params_df = pd.DataFrame(params_long_records)

    # Try to assign proper medium names using mean diameters matching the mapping table at far-right
    # Find mapping table: row containing "Type of packing material"
    map_row = None
    for r in range(raw.shape[0]):
        for c in range(raw.shape[1]):
            if isinstance(raw.iat[r,c], str) and raw.iat[r,c].strip().lower() == "type of packing material":
                map_row = r
                map_col = c
                break
        if map_row is not None:
            break

    mapping = {}
    if map_row is not None:
        # expect next column has mean diameter
        mean_col = map_col + 1
        for r in range(map_row+1, map_row+20):
            mat = raw.iat[r, map_col]
            md = raw.iat[r, mean_col]
            if pd.isna(mat) or pd.isna(md):
                continue
            mapping[float(md)] = canonicalize_medium(mat)

    # Assign medium names by matching mean diameter row in params_df
    # In this sheet the parameter name is "Mean diameter dP (m)"
    md_param = None
    for p in params_df.columns:
        if isinstance(p, str) and "mean diameter" in p.lower():
            md_param = p
            break
    if md_param is None:
        raise ValueError("Could not find 'Mean diameter' parameter in underdrain params.")
    params_df["mean_diameter_m"] = pd.to_numeric(params_df[md_param], errors="coerce")

    def match_name(md):
        if pd.isna(md) or len(mapping)==0:
            return ""
        # nearest mapping key
        key = min(mapping.keys(), key=lambda k: abs(k-md))
        if abs(key-md) < 1e-6:
            return mapping[key]
        # allow tiny differences
        if abs(key-md)/max(md, key) < 1e-3:
            return mapping[key]
        return ""

    params_df["medium"] = params_df["mean_diameter_m"].apply(match_name)
    # Fallback: if mapping failed, use porosity matching later.
    params_df["medium"] = params_df["medium"].replace("", np.nan)

    # Also capture equivalent diameter and porosity if available
    for col in params_df.columns:
        if isinstance(col, str) and "equivalent diameter" in col.lower():
            params_df["equiv_diameter_m"] = pd.to_numeric(params_df[col], errors="coerce")
        if isinstance(col, str) and col.strip().lower() == "porosity":
            params_df["porosity"] = pd.to_numeric(params_df[col], errors="coerce")
        if isinstance(col, str) and "sphericity" in col.lower():
            params_df["sphericity_recorded"] = pd.to_numeric(params_df[col], errors="coerce")

    # Extract meta values (mu, rho, L) from the side block in the sheet
    meta = {}
    # Scan for viscosity, density, bed height labels
    for r in range(raw.shape[0]):
        for c in range(raw.shape[1]-1):
            if isinstance(raw.iat[r,c], str):
                lab = raw.iat[r,c].strip().lower()
                if "viscosity" in lab and "35" in lab:
                    meta["mu"] = safe_float(raw.iat[r, c+1])
                if "density" in lab and "35" in lab:
                    meta["rho"] = safe_float(raw.iat[r, c+1])
                if lab == "bed height (m)":
                    meta["L"] = safe_float(raw.iat[r, c+1])

    # Extract velocity-pressure-drop table: from vel_row+1 onwards until NaNs
    data_rows = []
    for r in range(vel_row+1, raw.shape[0]):
        u = raw.iat[r, vel_col]
        if pd.isna(u):
            break
        u = safe_float(u)
        for c, h in zip(media_cols, media_headers):
            dp = safe_float(raw.iat[r, c])
            data_rows.append({"underdrain_col": str(h), "u_mps": u, "dp_pa": dp})
    long_df = pd.DataFrame(data_rows)

    # Join medium names
    long_df = long_df.merge(params_df[["underdrain_col","medium","mean_diameter_m","equiv_diameter_m","porosity","sphericity_recorded"]],
                            on="underdrain_col", how="left")

    # Canonicalize names (and fill if NaN using porosity matching later)
    long_df["medium"] = long_df["medium"].apply(lambda x: canonicalize_medium(x) if isinstance(x, str) else x)

    return params_df, long_df, meta

# ----------------------------
# Bayesian Stage I: pressure-drop calibration
# ----------------------------

def fit_stage1_pressure_drop(long_df: pd.DataFrame, meta: dict, out_dir: Path,
                             draws: int, tune: int, chains: int, cores: int,
                             seed: int) -> az.InferenceData:
    """
    Fit ΔP(u) per medium using Darcy–Forchheimer:
      ΔP = L*(mu/k * u + rho*beta * u^2) + error

    Returns ArviZ InferenceData.
    """
    mu = float(meta.get("mu", 7.255e-4))
    rho = float(meta.get("rho", 993.95))
    L = float(meta.get("L", 0.090453))

    # Filter valid rows
    df = long_df.dropna(subset=["medium","u_mps","dp_pa"]).copy()
    df = df[df["dp_pa"].notna()]
    # Remove any negative dp
    df = df[df["dp_pa"] >= 0]

    media = sorted(df["medium"].unique().tolist())
    m_index = {m:i for i,m in enumerate(media)}
    df["m_idx"] = df["medium"].map(m_index).astype(int)

    u = df["u_mps"].values.astype(float)
    dp = df["dp_pa"].values.astype(float)
    m_idx = df["m_idx"].values.astype(int)

    # Set weakly-informative priors for k and beta on physically plausible scales.
    # We model log(k) directly.
    with pm.Model(coords={"medium": media}) as model:
        # pymc >=5.17 removed ConstantData; use Data for fixed inputs
        pm.Data("u", u)
        pm.Data("m_idx", m_idx)

        log_k = pm.Normal("log_k", mu=np.log(1e-7), sigma=3.0, dims="medium")
        k = pm.Deterministic("k", pm.math.exp(log_k), dims="medium")

        # Forchheimer beta, half-normal wide
        beta = pm.HalfNormal("beta", sigma=1e6, dims="medium")

        sigma = pm.HalfNormal("sigma", sigma=0.02, dims="medium")

        mu_dp = L * ((mu / k[m_idx]) * u + (rho * beta[m_idx]) * (u**2))

        pm.Normal("dp_obs", mu=mu_dp, sigma=sigma[m_idx], observed=dp)

        idata = pm.sample(draws=draws, tune=tune, chains=chains, cores=cores,
                          target_accept=0.95, random_seed=seed, progressbar=True)

        # Posterior predictive for ΔP
        ppc = pm.sample_posterior_predictive(idata, var_names=["dp_obs"], random_seed=seed)
        idata.extend(ppc)

    # Save posterior
    out_nc = out_dir / "posteriors" / "stage1_pressure_drop.nc"
    mkdirp(out_nc.parent)
    idata.to_netcdf(out_nc)

    # Save a summary CSV
    summary = az.summary(idata, var_names=["k","beta","sigma"], hdi_prob=0.95)
    summary.to_csv(out_dir / "tables" / "stage1_pressure_drop_summary.csv")

    return idata

def derive_hydraulic_metrics(packing_df: pd.DataFrame, under_params: pd.DataFrame,
                             stage1_idata: az.InferenceData, out_dir: Path) -> pd.DataFrame:
    """
    Derive medium-level hydraulic metrics from Stage I posterior:
      k, beta, and apparent shape factor Psi (from laminar Ergun matching),
      plus geometric damping index (GDI).
    """
    # Grab posterior draws
    post = stage1_idata.posterior
    k_draws = post["k"].stack(sample=("chain","draw")).values  # shape: (medium, samples)
    beta_draws = post["beta"].stack(sample=("chain","draw")).values

    # Determine media order used in stage1 model
    coords = stage1_idata.posterior["k"].coords
    if "medium" in coords:
        media = coords["medium"].values
    else:
        media = coords[list(coords.keys())[0]].values
    media = [str(m) for m in media]

    # Prepare porosity and equivalent diameter per medium
    # Prefer packing_df porosity (retention module) but should match underdrain.
    poro_map = packing_df.set_index("medium")["porosity"].to_dict()

    # Equiv diameter from underdrain params: match on medium name via closest mean diameter if needed.
    # Build underdrain mapping: medium -> equiv_diameter
    under_map = {}
    for _, row in under_params.iterrows():
        m = canonicalize_medium(row.get("medium", ""))
        if not m:
            continue
        eqd = row.get("Equivalent diameter (m)", np.nan)
        if pd.isna(eqd):
            eqd = row.get("equiv_diameter_m", np.nan)
        under_map[m] = float(eqd) if not pd.isna(eqd) else np.nan

    # In case under_params did not contain canonical names, attempt to recover by porosity proximity
    if any(pd.isna(list(under_map.values()))):
        pass

    # Compute Psi draws via laminar Ergun mapping:
    # Psi = sqrt(150*(1-eps)^2/eps^3 * k / d_eq^2)
    psi_draws_list = []
    for i, m in enumerate(media):
        eps = poro_map.get(m, np.nan)
        d_eq = under_map.get(m, np.nan)
        if pd.isna(eps) or pd.isna(d_eq):
            psi = np.full_like(k_draws[i], np.nan, dtype=float)
        else:
            psi = np.sqrt(150.0 * ((1-eps)**2) / (eps**3) * (k_draws[i] / (d_eq**2)))
        psi_draws_list.append(psi)
    psi_draws = np.vstack(psi_draws_list)  # (medium, samples)

    # Clip Psi to (0, 1.5] for stability (apparent shape factor can exceed 1 under imperfect mapping)
    psi_draws_clipped = np.clip(psi_draws, 1e-6, 1.5)

    # Define resistance and GDI
    # Resistance R = mu/k; GDI = (1-Psi_clip)*R/R_ref
    # We'll use mu from meta in the stored idata attributes if available; otherwise typical
    mu = float(stage1_idata.attrs.get("mu", 7.255e-4)) if hasattr(stage1_idata, "attrs") else 7.255e-4
    resistance = mu / k_draws
    R_ref = np.nanmedian(resistance)

    gdi = (1 - np.minimum(psi_draws_clipped, 1.0)) * (resistance / R_ref)

    # Summarize per medium
    def summarize(arr):
        return {
            "mean": float(np.nanmean(arr)),
            "hdi_2.5": float(np.nanquantile(arr, 0.025)),
            "hdi_97.5": float(np.nanquantile(arr, 0.975))
        }

    rows=[]
    for i, m in enumerate(media):
        s_k = summarize(k_draws[i])
        s_beta = summarize(beta_draws[i])
        s_psi = summarize(psi_draws_clipped[i])
        s_gdi = summarize(gdi[i])
        rows.append({
            "medium": m,
            "k_mean": s_k["mean"], "k_hdi_2.5": s_k["hdi_2.5"], "k_hdi_97.5": s_k["hdi_97.5"],
            "beta_mean": s_beta["mean"], "beta_hdi_2.5": s_beta["hdi_2.5"], "beta_hdi_97.5": s_beta["hdi_97.5"],
            "psi_mean": s_psi["mean"], "psi_hdi_2.5": s_psi["hdi_2.5"], "psi_hdi_97.5": s_psi["hdi_97.5"],
            "gdi_mean": s_gdi["mean"], "gdi_hdi_2.5": s_gdi["hdi_2.5"], "gdi_hdi_97.5": s_gdi["hdi_97.5"],
        })

    metrics = pd.DataFrame(rows)

    mkdirp(out_dir / "data_processed")
    metrics.to_csv(out_dir / "data_processed" / "hydraulic_metrics.csv", index=False)

    # Save LaTeX summary table
    latex_df = metrics.copy()
    latex_df = latex_df[["medium","k_mean","k_hdi_2.5","k_hdi_97.5","beta_mean","beta_hdi_2.5","beta_hdi_97.5","psi_mean","gdi_mean"]]
    latex_df.columns = ["Medium",
                        r"$\hat{k}$", r"$k_{2.5\%}$", r"$k_{97.5\%}$",
                        r"$\hat{\beta}$", r"$\beta_{2.5\%}$", r"$\beta_{97.5\%}$",
                        r"$\hat{\Psi}$", r"$\widehat{\mathrm{GDI}}$"]
    tex = df_to_latex_booktabs(latex_df,
                               caption="Bayesian hydraulic signature summaries from Darcy--Forchheimer calibration (posterior mean and 95\\% credible interval).",
                               label="tab:hydraulic_signature")
    mkdirp(out_dir / "tables")
    (out_dir / "tables" / "tab_hydraulic_signature.tex").write_text(tex, encoding="utf-8")

    return metrics

# ----------------------------
# Bayesian Stage II: retention model fitting
# ----------------------------

def fit_stage2_retention_models(packing_df: pd.DataFrame, hydraulic_df: pd.DataFrame,
                                out_dir: Path, draws: int, tune: int,
                                chains: int, cores: int, seed: int,
                                include_gdi_model: bool = True) -> dict:
    """
    Fit multiple competing retention models and return a dict of idata objects.
    """
    df = packing_df.copy()
    df = df.merge(hydraulic_df, on="medium", how="left")
    # Response
    if "retention_capacity" not in df.columns:
        raise ValueError("Packing df must include 'retention_capacity'.")
    y = df["retention_capacity"].astype(float).values
    # Keep y away from exactly 0 or 1
    y = np.clip(y, 1e-4, 1-1e-4)

    # Predictors
    eps = df["porosity"].astype(float).values
    # logit porosity (avoid 0/1)
    eps_clip = np.clip(eps, 1e-6, 1-1e-6)
    x_poro = np.log(eps_clip/(1-eps_clip))

    # hydraulic predictors from posterior means
    x_logk = np.log(df["k_mean"].astype(float).values)
    x_log1pbeta = np.log1p(df["beta_mean"].astype(float).values)

    # GDI predictor
    x_loggdi = np.log(np.clip(df["gdi_mean"].astype(float).values, 1e-6, None))

    models = {}

    def _fit_model(model_name: str, X: np.ndarray, colnames: list[str]) -> az.InferenceData:
        with pm.Model() as m:
            X_data = pm.Data("X", X)
            y_data = pm.Data("y", y)

            alpha = pm.Normal("alpha", mu=0.0, sigma=2.0)
            beta = pm.Normal("beta", mu=0.0, sigma=1.0, shape=X.shape[1])
            kappa = pm.HalfNormal("kappa", sigma=5.0)

            eta = alpha + pm.math.dot(X_data, beta)
            mu_ = pm.Deterministic("mu", pm.math.sigmoid(eta))
            mu_ = pm.math.clip(mu_, 1e-6, 1-1e-6)

            a = mu_ * kappa
            b = (1-mu_) * kappa

            pm.Beta("R_obs", alpha=a, beta=b, observed=y_data)

            idata = pm.sample(draws=draws, tune=tune, chains=chains, cores=cores,
                              target_accept=0.95, random_seed=seed, progressbar=True,
                              idata_kwargs={"log_likelihood": True})

            ppc = pm.sample_posterior_predictive(idata, var_names=["R_obs","mu"], random_seed=seed)
            idata.extend(ppc)

        # Save posterior
        nc_path = out_dir / "posteriors" / f"stage2_{model_name}.nc"
        mkdirp(nc_path.parent)
        idata.to_netcdf(nc_path)

        # Summary table CSV
        summ = az.summary(idata, var_names=["alpha","beta","kappa"], hdi_prob=0.95)
        summ.to_csv(out_dir / "tables" / f"stage2_{model_name}_summary.csv")

        # LaTeX table
        # Build a cleaner coefficient table
        summ_reset = summ.reset_index().rename(columns={"index":"param"})
        # Map beta indices to column names
        def map_param(p):
            if p.startswith("beta["):
                idx = int(p.split("[")[1].split("]")[0])
                return f"beta_{colnames[idx]}"
            return p
        summ_reset["param"] = summ_reset["param"].apply(map_param)
        coef_df = summ_reset[["param","mean","hdi_2.5%","hdi_97.5%"]].copy()
        coef_df.columns = ["Parameter", "Mean", "HDI 2.5\\%", "HDI 97.5\\%"]
        # Escape underscores for LaTeX safety (escape=False is used in df_to_latex_booktabs)
        coef_df["Parameter"] = coef_df["Parameter"].astype(str).str.replace("_", r"\_", regex=False)
        tex = df_to_latex_booktabs(coef_df,
                                   caption=f"Posterior summaries for retention model ({model_name}).",
                                   label=f"tab:retention_{model_name}")
        (out_dir / "tables" / f"tab_retention_{model_name}.tex").write_text(tex, encoding="utf-8")

        return idata

    # Volumetric model
    X_v = x_poro.reshape(-1,1)
    models["volumetric"] = _fit_model("volumetric", X_v, ["logit_porosity"])

    # Hydraulic signature model
    X_h = np.vstack([x_logk, x_log1pbeta]).T
    models["hydraulic"] = _fit_model("hydraulic", X_h, ["logk","log1pbeta"])

    # Combined
    X_c = np.vstack([x_poro, x_logk, x_log1pbeta]).T
    models["combined"] = _fit_model("combined", X_c, ["logit_porosity","logk","log1pbeta"])

    if include_gdi_model:
        X_g = x_loggdi.reshape(-1,1)
        models["gdi"] = _fit_model("gdi", X_g, ["log_gdi"])

    return models

def model_comparison(models: dict, out_dir: Path) -> pd.DataFrame:
    """
    Compute PSIS-LOO model comparison and save tables.
    """
    loo_dict = {}
    for name, idata in models.items():
        try:
            loo = az.loo(idata, pointwise=True)
            loo_dict[name] = loo
        except Exception as e:
            print(f"[WARN] LOO failed for model {name}: {e}")

    if len(loo_dict) == 0:
        return pd.DataFrame()

    comp = az.compare(loo_dict, method="BB-pseudo-BMA", ic="loo")
    comp = comp.reset_index().rename(columns={"index":"model"})
    mkdirp(out_dir / "tables")
    comp.to_csv(out_dir / "tables" / "model_comparison_loo.csv", index=False)

    # LaTeX
    latex_df = comp[["model","elpd_loo","p_loo","weight","se"]].copy()
    latex_df.columns = ["Model", "ELPD$_{\\mathrm{LOO}}$", "$p_{\\mathrm{LOO}}$", "Weight", "SE"]
    tex = df_to_latex_booktabs(latex_df,
                               caption="PSIS-LOO comparison of retention models (higher ELPD indicates better expected predictive performance).",
                               label="tab:model_comparison")
    (out_dir / "tables" / "tab_model_comparison.tex").write_text(tex, encoding="utf-8")
    return comp

# ----------------------------
# Plotting helpers
# ----------------------------

def plot_pressure_drop_fits(long_df: pd.DataFrame, stage1_idata: az.InferenceData, meta: dict, out_dir: Path):
    mu = float(meta.get("mu", 7.255e-4))
    rho = float(meta.get("rho", 993.95))
    L = float(meta.get("L", 0.090453))

    post = stage1_idata.posterior
    k_draws = post["k"].stack(sample=("chain","draw")).values
    beta_draws = post["beta"].stack(sample=("chain","draw")).values
    k_coords = post["k"].coords
    if "medium" in k_coords:
        media = k_coords["medium"].values
    else:
        media = k_coords[list(k_coords.keys())[0]].values
    media = [str(m) for m in media]

    df = long_df.dropna(subset=["medium","u_mps","dp_pa"]).copy()
    df["medium"] = df["medium"].apply(canonicalize_medium)

    mkdirp(out_dir / "figures")

    for i, m in enumerate(media):
        sub = df[df["medium"] == m].copy()
        if sub.empty:
            continue
        u = sub["u_mps"].values.astype(float)
        dp = sub["dp_pa"].values.astype(float)

        u_grid = np.linspace(u.min(), u.max(), 200)

        # Posterior predictive mean and 95% band (on mean function)
        mu_curves = []
        # sample up to 500 draws for plotting
        n_samp = min(k_draws.shape[1], 500)
        idx = np.random.choice(k_draws.shape[1], size=n_samp, replace=False)
        for s in idx:
            k = k_draws[i, s]
            b = beta_draws[i, s]
            mu_curve = L * ((mu / k) * u_grid + (rho * b) * (u_grid**2))
            mu_curves.append(mu_curve)
        mu_curves = np.vstack(mu_curves)
        mean_curve = np.nanmean(mu_curves, axis=0)
        lo = np.nanquantile(mu_curves, 0.025, axis=0)
        hi = np.nanquantile(mu_curves, 0.975, axis=0)

        fig = plt.figure(figsize=(6.5,4.5))
        ax = fig.add_subplot(111)
        ax.scatter(u, dp, s=18, label="Observed")
        ax.plot(u_grid, mean_curve, label="Posterior mean fit")
        ax.fill_between(u_grid, lo, hi, alpha=0.25, label="95% credible band")
        ax.set_xlabel("Superficial velocity, $u$ (m/s)")
        ax.set_ylabel("Pressure drop, $\\Delta P$ (Pa)")
        ax.set_title(f"Pressure-drop fit: {m}")
        ax.legend()
        fig.tight_layout()

        fig.savefig(out_dir / "figures" / f"fig_pressure_drop_{m.replace(' ','_').lower()}.png", dpi=300)
        fig.savefig(out_dir / "figures" / f"fig_pressure_drop_{m.replace(' ','_').lower()}.pdf")
        plt.close(fig)

def plot_retention_foil(packing_df: pd.DataFrame, hydraulic_df: pd.DataFrame, out_dir: Path):
    df = packing_df.merge(hydraulic_df, on="medium", how="left").copy()
    mkdirp(out_dir / "figures")

    fig = plt.figure(figsize=(6.5,4.5))
    ax = fig.add_subplot(111)
    ax.scatter(df["porosity"], df["retention_capacity"], s=40)
    for _, r in df.iterrows():
        ax.annotate(r["medium"], (r["porosity"], r["retention_capacity"]), fontsize=8, xytext=(4,4), textcoords="offset points")
    ax.set_xlabel("Porosity, $\\varepsilon$")
    ax.set_ylabel("Retention capacity, $R$")
    ax.set_title("Retention vs porosity (porosity-only heuristic can fail)")
    fig.tight_layout()
    fig.savefig(out_dir / "figures" / "fig_retention_vs_porosity.png", dpi=300)
    fig.savefig(out_dir / "figures" / "fig_retention_vs_porosity.pdf")
    plt.close(fig)

    # Retention vs permeability (posterior mean)
    fig = plt.figure(figsize=(6.5,4.5))
    ax = fig.add_subplot(111)
    ax.scatter(df["k_mean"], df["retention_capacity"], s=40)
    for _, r in df.iterrows():
        ax.annotate(r["medium"], (r["k_mean"], r["retention_capacity"]), fontsize=8, xytext=(4,4), textcoords="offset points")
    ax.set_xlabel("Permeability estimate, $\\hat{k}$ (m$^2$)")
    ax.set_ylabel("Retention capacity, $R$")
    ax.set_xscale("log")
    ax.set_title("Retention vs inferred permeability (hydraulic signature)")
    fig.tight_layout()
    fig.savefig(out_dir / "figures" / "fig_retention_vs_k.png", dpi=300)
    fig.savefig(out_dir / "figures" / "fig_retention_vs_k.pdf")
    plt.close(fig)

def plot_posterior_forest(models: dict, out_dir: Path):
    mkdirp(out_dir / "figures")
    for name, idata in models.items():
        try:
            fig = az.plot_forest(idata, var_names=["beta"], combined=True, hdi_prob=0.95)
            plt.title(f"Posterior: beta coefficients ({name})")
            plt.tight_layout()
            plt.savefig(out_dir / "figures" / f"fig_forest_beta_{name}.png", dpi=300)
            plt.savefig(out_dir / "figures" / f"fig_forest_beta_{name}.pdf")
            plt.close()
        except Exception:
            pass

# ----------------------------
# Results export helpers
# ----------------------------

def export_tidy_draws(stage1_idata: az.InferenceData, stage2_models: dict, out_dir: Path):
    mkdirp(out_dir / "data_processed")
    # Stage I draws
    post = stage1_idata.posterior
    k_coords = post["k"].coords
    if "medium" in k_coords:
        media = k_coords["medium"].values
    else:
        media = k_coords[list(k_coords.keys())[0]].values
    media = [str(m) for m in media]
    k = post["k"].stack(sample=("chain","draw")).values
    beta = post["beta"].stack(sample=("chain","draw")).values
    sigma = post["sigma"].stack(sample=("chain","draw")).values
    records=[]
    for i,m in enumerate(media):
        for s in range(k.shape[1]):
            records.append({"medium": m, "sample": s, "k": k[i,s], "beta": beta[i,s], "sigma": sigma[i,s]})
    pd.DataFrame(records).to_csv(out_dir / "data_processed" / "stage1_draws.csv", index=False)

    # Stage II coefficient draws and posterior mu per medium
    for name, idata in stage2_models.items():
        p = idata.posterior
        # coefficients
        alpha = p["alpha"].stack(sample=("chain","draw")).values
        beta_coef = p["beta"].stack(sample=("chain","draw")).values  # shape (coef, sample)
        kappa = p["kappa"].stack(sample=("chain","draw")).values
        coef_records=[]
        for s in range(alpha.shape[0]):
            coef_records.append({"sample": s, "alpha": alpha[s], "kappa": kappa[s]})
        # add beta columns
        for j in range(beta_coef.shape[0]):
            for s in range(alpha.shape[0]):
                coef_records[s][f"beta_{j}"] = beta_coef[j, s]
        pd.DataFrame(coef_records).to_csv(out_dir / "data_processed" / f"stage2_{name}_coef_draws.csv", index=False)

        # posterior mu (mean retention per medium)
        if "mu" in idata.posterior:
            mu_draws = idata.posterior["mu"].stack(sample=("chain","draw")).values  # (medium, sample)
            mu_records=[]
            for i in range(mu_draws.shape[0]):
                for s in range(mu_draws.shape[1]):
                    mu_records.append({"medium_index": i, "sample": s, "mu": mu_draws[i,s]})
            pd.DataFrame(mu_records).to_csv(out_dir / "data_processed" / f"stage2_{name}_mu_draws.csv", index=False)

# ----------------------------
# Main
# ----------------------------

def main():
    parser = argparse.ArgumentParser(description="Paper 2 Bayesian pipeline (CEJ).")
    parser.add_argument("--excel_path", type=str, default="DEng data.xlsx", help="Path to DEng data.xlsx")
    parser.add_argument("--out_dir", type=str, default="paper2_outputs", help="Output directory")
    parser.add_argument("--draws", type=int, default=2000, help="Posterior draws")
    parser.add_argument("--tune", type=int, default=2000, help="Tuning steps")
    parser.add_argument("--chains", type=int, default=4, help="MCMC chains")
    parser.add_argument("--cores", type=int, default=4, help="Parallel cores")
    parser.add_argument("--seed", type=int, default=123, help="Random seed")
    parser.add_argument("--no_gdi_model", action="store_true", help="Disable the optional GDI-only retention model")
    args = parser.parse_args()

    excel_path = Path(args.excel_path)
    out_dir = Path(args.out_dir)

    mkdirp(out_dir)
    for sub in ["tables","figures","posteriors","data_processed","logs"]:
        mkdirp(out_dir / sub)

    print(f"[INFO] Loading workbook: {excel_path.resolve()}")
    packing_df = load_packing_materials(excel_path)
    under_params, under_long, meta = load_underdrain_system(excel_path)

    # Harmonize media naming in packing_df
    packing_df["medium"] = packing_df["medium"].apply(canonicalize_medium)

    # If underdrain media names are missing, infer them by matching porosity to packing data.
    if under_params["medium"].isna().any():
        poro_map = packing_df.set_index("porosity")["medium"].to_dict()

        def infer_medium_from_porosity(poro: float):
            if pd.isna(poro):
                return np.nan
            # choose the closest porosity; tolerate tiny numeric noise
            nearest = min(poro_map.keys(), key=lambda k: abs(k - poro))
            if abs(nearest - poro) <= 1e-6 or abs(nearest - poro) / max(abs(nearest), abs(poro)) < 1e-3:
                return poro_map[nearest]
            return np.nan

        under_params["medium"] = under_params["medium"].combine_first(
            under_params["porosity"].apply(infer_medium_from_porosity)
        )
        # propagate inferred names to the long table
        medium_map = under_params.set_index("underdrain_col")["medium"].to_dict()
        under_long["medium"] = under_long["underdrain_col"].map(medium_map)

    # Save cleaned data
    packing_df.to_csv(out_dir / "data_processed" / "packing_materials_clean.csv", index=False)
    under_long.to_csv(out_dir / "data_processed" / "underdrain_pressure_drop_long.csv", index=False)
    under_params.to_csv(out_dir / "data_processed" / "underdrain_params_raw.csv", index=False)

    # LaTeX: packing table
    pack_tbl = packing_df[["medium","porosity","void_volume_ml","retained_g","washed_out_g","retention_capacity"]].copy()
    pack_tbl.columns = ["Medium", r"Porosity $\varepsilon$", "Void volume (mL)", "Retained (g)", "Washed out (g)", "Retention $R$"]
    (out_dir / "tables" / "tab_packing_summary.tex").write_text(
        df_to_latex_booktabs(pack_tbl, "Packing-media void fraction and end-point biomass retention outcomes.", "tab:packing_summary"),
        encoding="utf-8"
    )
    pack_tbl.to_csv(out_dir / "tables" / "tab_packing_summary.csv", index=False)

    print("[INFO] Stage I: fitting Bayesian Darcy–Forchheimer model to pressure-drop data...")
    stage1_idata = fit_stage1_pressure_drop(under_long, meta, out_dir, args.draws, args.tune, args.chains, args.cores, args.seed)

    print("[INFO] Deriving hydraulic metrics (k, beta, apparent Psi, GDI) from Stage I posterior...")
    hydraulic_df = derive_hydraulic_metrics(packing_df, under_params, stage1_idata, out_dir)

    print("[INFO] Plotting pressure-drop fits...")
    plot_pressure_drop_fits(under_long, stage1_idata, meta, out_dir)

    print("[INFO] Plotting retention foil figures...")
    plot_retention_foil(packing_df, hydraulic_df, out_dir)

    print("[INFO] Stage II: fitting Bayesian retention models (volumetric vs hydraulic vs combined)...")
    models = fit_stage2_retention_models(packing_df, hydraulic_df, out_dir,
                                         draws=args.draws, tune=args.tune, chains=args.chains, cores=args.cores,
                                         seed=args.seed, include_gdi_model=(not args.no_gdi_model))

    print("[INFO] Bayesian model comparison (PSIS-LOO)...")
    comp_df = model_comparison(models, out_dir)

    print("[INFO] Posterior forest plots for coefficients...")
    plot_posterior_forest(models, out_dir)

    print("[INFO] Exporting tidy posterior draws...")
    export_tidy_draws(stage1_idata, models, out_dir)

    print(f"[DONE] Outputs saved to: {out_dir.resolve()}")
    print("Key outputs:")
    print(f"  - Cleaned data: {out_dir/'data_processed'}")
    print(f"  - Posterior samples (.nc): {out_dir/'posteriors'}")
    print(f"  - Tables (.csv, .tex): {out_dir/'tables'}")
    print(f"  - Figures (.png, .pdf): {out_dir/'figures'}")

if __name__ == "__main__":
    main()
