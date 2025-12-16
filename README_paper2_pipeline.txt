Paper 2 End-to-End Pipeline (CEJ)
================================

Files
-----
- paper2_end_to_end.py : end-to-end pipeline (data -> Bayesian models -> tables/figures)
- requirements.txt     : Python dependencies

Quick start
----------
1) Create and activate a virtual environment (recommended).
2) Install dependencies:
     pip install -r requirements.txt

3) Run:
     python paper2_end_to_end.py --excel_path "DEng data.xlsx" --out_dir "paper2_outputs"

Outputs
-------
paper2_outputs/
  data_processed/   cleaned CSVs + tidy posterior draws
  posteriors/       NetCDF posterior samples for Stage I + Stage II models
  tables/           CSV and LaTeX tables (booktabs) for direct \\input{}
  figures/          PNG and PDF figures for reporting

Tips
----
- If runtime is too slow, reduce --draws and --tune (e.g., 1000/1000).
- If you see sampling warnings, raise target_accept (inside the script) or increase tuning.
