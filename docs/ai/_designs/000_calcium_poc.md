Task: add a calcium-imaging front end to the benchmark, so a recording of ΔF/F traces with
repeated stimulus onsets becomes units.csv and responses.csv, passes rrb-check, and scores in
rrb-evaluate. Open layer only: no change to any frozen function, constant, snapshot or
manifest; no change to SPEC.md or METHOD.md. SPEC §2 already defines an ROI as a recording
unit and §6 says calcium imaging qualifies; this is the code that makes that sentence true.

Read first: src/recovery_reliability_benchmark/ (contract.py, synthetic.py, measures.py),
scripts/sharf2022_g0.py, examples/, tests/, and the CLI entry points in pyproject.toml.
Follow the repo's existing conventions.

Step 0 — one measure definition for both modalities.
measures.py must exist with recovery_measures(...) taking a sampled curve plus a baseline.
If it does not, stop and report; the P2-1 prompt runs first. The calcium path calls the same
recovery_measures the spike path calls, so t_peak, t_half_peak, t_return, residual and
overshoot have one definition. Measure column names must be modality-neutral: if measures.py
names the peak `peak_rate`, rename it `peak_value` there (measures.py is not frozen until
v0.2.0) and fix its tests.

Step 1 — src/recovery_reliability_benchmark/traces.py, under 300 lines.
Pure functions; file I/O only in the CLI function.
- trace_baseline(frame_times_s, dff_values, onset_s, pre_stim_window_s) -> float:
  mean of the samples in [onset_s - pre_stim_window_s, onset_s).
- trial_curve(frame_times_s, dff_values, onset_s, post_stim_window_s)
  -> tuple[np.ndarray, np.ndarray]: samples in [onset_s, onset_s + post_stim_window_s) as
  (time_since_onset_s, values). Intent comment: frames are the bins; a frame belongs to the
  window when its timestamp falls inside it.
- trial_measures(frame_times_s, dff_values, onset_s, params) -> dict: baseline, then
  recovery_measures on the trial curve. No-response and censoring encodings are whatever
  recovery_measures already defines; invent nothing new (SPEC §15).
- traces_to_tables(frame_times_s, dff_by_unit: dict[str, np.ndarray], onsets_s,
  conditions: list[str], ids: TableIds, params) -> tuple[pd.DataFrame, pd.DataFrame]:
  units.csv and responses.csv exactly as SPEC §9 defines them; stim_time_ns =
  round(onset_s * 1e9); exactly one row per unit per trial.
- CLI rrb-traces:
    rrb-traces traces.csv stims.csv --frame-rate-hz 10 --post-stim-window-s 5.0
               --pre-stim-window-s 1.0 --out-dir .
  traces.csv is wide: first column `frame` (integer) or `time_s`, then one column per ROI,
  header row = unit ids. stims.csv: trial_index, onset_frame or onset_s, condition. Writes
  units.csv and responses.csv and prints the rrb-check command to run next. Exit 2 when an
  input cannot be read. Wide is what imaging software exports; the lab reshapes nothing.
Every public function carries a per-argument @param docstring. Names say what they are:
inter_pulse_interval_s, decay_time_constant_s, never tau.

Step 2 — src/recovery_reliability_benchmark/synthetic_traces.py, under 300 lines.
synthetic.py stays byte-identical.
- calcium_transient(time_since_onset_s, peak_dff, rise_time_constant_s,
  decay_time_constant_s) -> np.ndarray: difference of exponentials scaled so its maximum
  equals peak_dff. Intent comment: an indicator-shaped transient, fast rise, slow decay.
- make_calcium_traces(n_cells, n_pulses, frame_rate_hz, inter_pulse_interval_s,
  decay_time_constant_range_s, per_trial_jitter_sd, noise_sd, seed)
  -> tuple[np.ndarray, dict[str, np.ndarray], np.ndarray]: frame times, ΔF/F per cell with
  baseline 0, onsets at inter_pulse_interval_s * (k + 1). Each cell draws one true
  decay_time_constant_s from the range; each trial multiplies it by
  exp(per_trial_jitter_sd * e), e standard normal; additive Gaussian noise with noise_sd.
  per_trial_jitter_sd = 0 and noise_sd = 0 is the positive-control case: both halves
  identical, reliability 1. numpy default_rng(seed).

Step 3 — tests/test_traces.py, seeds fixed, each test under 2 s.
- test_ordering: jitter 0, noise 0; cells sorted by true decay constant are in the same
  order by measured t_return.
- test_reliability_monotone_in_jitter: split-half reliability of t_return, computed with the
  evaluate function the repo already exposes, is 1.0 within tolerance at jitter 0 and
  decreases monotonically over jitter_sd in (0, 0.3, 0.6, 1.0).
- test_generated_tables_conform: contract.validate on traces_to_tables output with
  20 pulses, 30 cells, 10 Hz, 30 s spacing, 5 s window returns fully_conforming; with
  6 pulses it raises naming min-dataset-2.
- test_no_response_encoding: a cell with peak_dff 0 yields the encoding recovery_measures
  defines for no response, never a null.
- test_cli_roundtrip: write traces.csv and stims.csv to tmp_path, run rrb-traces, run
  rrb-check on its outputs by subprocess, exit code 0.

Step 4 — examples/calcium_hello_world/.
run.py, under 150 lines: make_calcium_traces (30 cells, 20 pulses, 10 Hz, 30 s spacing,
jitter 0.3, noise 0.05); write traces.csv and stims.csv as a lab would; run rrb-traces,
rrb-check --json and rrb-evaluate by subprocess; write summary.md with the verdict, the
counts, the reliability with its interval, and one figure (per-cell mean trace with the
window marked). README.md in the folder: who this is for (calcium imaging labs), the two
input files and their columns, the three commands, what the output means. One line in the
top-level README pointing here. CHANGELOG entry under Unreleased: added, open layer, no
frozen change.

Gates, pytest after each; stop at the first failure and report the diff:
0. measures.py present, existing suite green.
1–2. traces.py and synthetic_traces.py import; existing suite unchanged.
3. test_traces.py all green.
4. run.py produces summary.md with verdict fully_conforming. Expected reliability of
   t_return at jitter 0.3 is above 0.9; if it is lower, report the number rather than
   adjusting the generator.
