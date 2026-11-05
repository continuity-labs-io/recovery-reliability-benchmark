# Threshold Simulation

Simulated sampling distribution of the within-session reliability ceiling across the MD-2 (`n_trials`) and MD-3 (`n_units`) thresholds. Synthetic datasets were generated with `recovery_reliability_benchmark.synthetic.make_tables` (Gaussian unit true values and per-trial errors scaled to single-trial reliability `rho1`, with condition offsets `{A: 0.0, B: 1.0, C: 2.0}` when `n_conditions == 3`) and estimated with `split_halves` and `ceiling` from `recovery_reliability_benchmark.evaluate` (odd/even split-half Pearson correlation with Spearman-Brown correction, condition-centered for 3 conditions). Run across **1000 seeds** per cell with `python scripts/thresholds.py --seeds 1000 --out docs/thresholds`.

| rho1 | n_conditions | n_trials | n_units | true_rho | median_rho_hat | p2_5 | p97_5 | interval_95 | width | p_zero | ci_coverage | conformance |
|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---|
| 0.1 | 1 | 10 | 8 | 0.53 | 0.56 | 0.00 | 0.92 | [0.00, 0.92] | 0.92 | 0.193 | 0.944 | conforming |
| 0.1 | 1 | 10 | 15 | 0.53 | 0.54 | 0.00 | 0.83 | [0.00, 0.83] | 0.83 | 0.089 | 0.961 | conforming |
| 0.1 | 1 | 10 | 30 | 0.53 | 0.54 | 0.02 | 0.79 | [0.02, 0.79] | 0.77 | 0.023 | 0.941 | conforming |
| 0.1 | 1 | 20 | 8 | 0.69 | 0.69 | 0.00 | 0.95 | [0.00, 0.95] | 0.95 | 0.066 | 0.954 | conforming |
| 0.1 | 1 | 20 | 15 | 0.69 | 0.69 | 0.00 | 0.90 | [0.00, 0.90] | 0.90 | 0.027 | 0.942 | fully_conforming |
| 0.1 | 1 | 20 | 30 | 0.69 | 0.70 | 0.37 | 0.86 | [0.37, 0.86] | 0.49 | 0.002 | 0.951 | fully_conforming |
| 0.1 | 3 | 10 | 8 | 0.53 | 0.50 | 0.00 | 0.82 | [0.00, 0.82] | 0.82 | 0.081 | 1.000 | conforming |
| 0.1 | 3 | 10 | 15 | 0.53 | 0.52 | 0.06 | 0.75 | [0.06, 0.75] | 0.69 | 0.013 | 0.998 | conforming |
| 0.1 | 3 | 10 | 30 | 0.53 | 0.52 | 0.24 | 0.71 | [0.24, 0.71] | 0.47 | 0.002 | 0.998 | conforming |
| 0.1 | 3 | 20 | 8 | 0.69 | 0.68 | 0.07 | 0.88 | [0.07, 0.88] | 0.81 | 0.016 | 0.998 | conforming |
| 0.1 | 3 | 20 | 15 | 0.69 | 0.68 | 0.36 | 0.85 | [0.36, 0.85] | 0.49 | 0.001 | 0.997 | fully_conforming |
| 0.1 | 3 | 20 | 30 | 0.69 | 0.69 | 0.50 | 0.81 | [0.50, 0.81] | 0.31 | 0.000 | 0.993 | fully_conforming |
| 0.2 | 1 | 10 | 8 | 0.71 | 0.74 | 0.00 | 0.95 | [0.00, 0.95] | 0.95 | 0.070 | 0.942 | conforming |
| 0.2 | 1 | 10 | 15 | 0.71 | 0.72 | 0.21 | 0.90 | [0.21, 0.90] | 0.69 | 0.008 | 0.967 | conforming |
| 0.2 | 1 | 10 | 30 | 0.71 | 0.72 | 0.39 | 0.87 | [0.39, 0.87] | 0.49 | 0.001 | 0.941 | conforming |
| 0.2 | 1 | 20 | 8 | 0.83 | 0.84 | 0.22 | 0.97 | [0.22, 0.97] | 0.76 | 0.014 | 0.953 | conforming |
| 0.2 | 1 | 20 | 15 | 0.83 | 0.83 | 0.49 | 0.95 | [0.49, 0.95] | 0.46 | 0.000 | 0.950 | fully_conforming |
| 0.2 | 1 | 20 | 30 | 0.83 | 0.84 | 0.67 | 0.92 | [0.67, 0.92] | 0.26 | 0.000 | 0.953 | fully_conforming |
| 0.2 | 3 | 10 | 8 | 0.71 | 0.70 | 0.10 | 0.90 | [0.10, 0.90] | 0.80 | 0.018 | 1.000 | conforming |
| 0.2 | 3 | 10 | 15 | 0.71 | 0.71 | 0.40 | 0.86 | [0.40, 0.86] | 0.45 | 0.000 | 0.998 | conforming |
| 0.2 | 3 | 10 | 30 | 0.71 | 0.71 | 0.51 | 0.83 | [0.51, 0.83] | 0.32 | 0.000 | 0.993 | conforming |
| 0.2 | 3 | 20 | 8 | 0.83 | 0.83 | 0.46 | 0.94 | [0.46, 0.94] | 0.48 | 0.002 | 0.997 | conforming |
| 0.2 | 3 | 20 | 15 | 0.83 | 0.83 | 0.62 | 0.92 | [0.62, 0.92] | 0.30 | 0.000 | 0.995 | fully_conforming |
| 0.2 | 3 | 20 | 30 | 0.83 | 0.83 | 0.71 | 0.90 | [0.71, 0.90] | 0.19 | 0.000 | 0.992 | fully_conforming |
| 0.4 | 1 | 10 | 8 | 0.87 | 0.89 | 0.31 | 0.98 | [0.31, 0.98] | 0.67 | 0.009 | 0.949 | conforming |
| 0.4 | 1 | 10 | 15 | 0.87 | 0.87 | 0.64 | 0.95 | [0.64, 0.95] | 0.31 | 0.001 | 0.969 | conforming |
| 0.4 | 1 | 10 | 30 | 0.87 | 0.87 | 0.71 | 0.94 | [0.71, 0.94] | 0.23 | 0.000 | 0.938 | conforming |
| 0.4 | 1 | 20 | 8 | 0.93 | 0.94 | 0.68 | 0.99 | [0.68, 0.99] | 0.30 | 0.001 | 0.957 | conforming |
| 0.4 | 1 | 20 | 15 | 0.93 | 0.93 | 0.80 | 0.98 | [0.80, 0.98] | 0.18 | 0.000 | 0.963 | fully_conforming |
| 0.4 | 1 | 20 | 30 | 0.93 | 0.93 | 0.86 | 0.97 | [0.86, 0.97] | 0.11 | 0.000 | 0.952 | fully_conforming |
| 0.4 | 3 | 10 | 8 | 0.87 | 0.86 | 0.55 | 0.96 | [0.55, 0.96] | 0.41 | 0.000 | 0.999 | conforming |
| 0.4 | 3 | 10 | 15 | 0.87 | 0.87 | 0.70 | 0.94 | [0.70, 0.94] | 0.23 | 0.000 | 0.997 | conforming |
| 0.4 | 3 | 10 | 30 | 0.87 | 0.87 | 0.76 | 0.93 | [0.76, 0.93] | 0.16 | 0.000 | 0.989 | conforming |
| 0.4 | 3 | 20 | 8 | 0.93 | 0.93 | 0.74 | 0.98 | [0.74, 0.98] | 0.24 | 0.000 | 0.992 | conforming |
| 0.4 | 3 | 20 | 15 | 0.93 | 0.93 | 0.83 | 0.97 | [0.83, 0.97] | 0.13 | 0.000 | 0.994 | fully_conforming |
| 0.4 | 3 | 20 | 30 | 0.93 | 0.93 | 0.87 | 0.96 | [0.87, 0.96] | 0.09 | 0.000 | 0.988 | fully_conforming |

---

This document is licensed under CC BY 4.0; see [LICENSE-DOCS](../LICENSE-DOCS).
