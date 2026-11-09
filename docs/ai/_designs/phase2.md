# Phase 2 

Items marked "to confirm" at the end are places where the plan uses a term without pinning it.

## 1. The two layers: frozen and open

**Frozen layer (the core).** Everything that turns a table of per-unit numbers into a reliability verdict: the six requirements and their thresholds (min-dataset-1 to 6; 10/20 trials; 8/30 units), the inclusion rule, the odd/even split, Pearson r, Spearman-Brown, the headline rule (pooled-centered when there are two or more conditions), the Fisher-z interval, the permutation null, the positive control. Frozen at v0.1.0 means: it changes only with a version bump and a CHANGELOG entry, and never in response to what a dataset's number looks like.

Why it is frozen: the number is evidence only if the procedure was fixed before the data arrived. If a threshold or the split rule moves after a dataset has been seen, nobody, including us, can tell "the measure is reliable" from "the analysis was adjusted until it looked reliable." The Sharf run is the demonstration that the freeze holds: 13 recordings, zero changes to src/.

**Open layer.** Everything that gets data into the core and results out: adapters (a lab's file format in, benchmark CSVs out), report scripts, docs, and the measure library. Phase 2 is a new piece of the open layer (computing measures from spike times) plus one small addition to the core (a pre-stimulus window requirement). The core addition is why Phase 2 gets a version number instead of a patch.

## 2. Phases, versions, and the P2 numbering

| Term | Meaning |
|---|---|
| Phase 1 = v0.1.0 | The lab computes the per-trial measures with its own code and sends tables. The benchmark validates the tables and computes reliability. Shipped, with DOI. |
| Phase 2 = v0.2.0 | The benchmark computes the measures itself, from spike times, identically for everyone. Four work items, P2-1 to P2-4. |
| Phase 3 | The atlas holds rows from labs other than the pilot, from external conforming stimulation datasets. The plan uses the term without defining it; to confirm. |
| P2-n | Phase 2, work item n. |
| Competitions | Challenge-style events on fixed public datasets. Placed after Phase 3 because they spend data that already exists, and that data does not exist until Phase 3. |

## 3. The data flow in Phase 2, in words

Six boxes, left to right, arrows between each pair.

1. **Lab's native recording** (MaxWell h5, MCS, a FinalSpark export) goes through the **adapter** (P2-3) and comes out as benchmark files: units.csv, spikes.csv, preparation.json, conditions.json, and the new analysis.json.
2. **rrb-check** runs the contract: min-dataset-1 to 6 plus the new pre-stimulus window check (P2-2). Output: conforming, fully conforming, or the one violation.
3. **Split**: the trials of each (unit, condition) go to odd and even halves by position. Frozen rule, unchanged.
4. **measures.py** (P2-1): for each unit and each half, pool that half's trials into one PSTH and compute the recovery measures once per half. Output: one table of unit × half × measure.
5. **rrb-evaluate** (frozen): correlate the two halves across units, Spearman-Brown, interval, null, positive control.
6. **summary.md**: one figure and one paragraph, produced by the report generator (exception 1). That file is one atlas row.

The change from Phase 1 is box 4. In Phase 1 the lab computed the measure once per trial and the benchmark averaged within a half. In Phase 2 the trials of a half are pooled first and the measure is computed once. Reason: one trial of a 2 Hz unit holds about four spikes in two seconds, and a return-to-baseline time estimated from four spikes is noise. Ten pooled trials give forty spikes. Both routes end in one number per unit per half, so box 5 does not change.

## 4. The four P2 items

### P2-1 measures.py (exception 2: allowed before a dataset arrives)

Pure functions, no file I/O, tested on synthetic spike trains. The prompt is written.

- Inputs: spike times per unit, stimulus onset per trial, an AnalysisParams object.
- Functions: `trial_latencies` (spike times minus onset, per trial, inside the windows), `pre_counts` (spikes in the pre-stimulus window, per trial), `baseline_hz` (pre-stimulus rate), `psth_rate` (the binned post-stimulus rate from pooled trials), `recovery_measures` (the measures from one PSTH and one baseline), `make_spike_trains` (the synthetic generator for tests).
- Measures: `t_peak`, `peak_rate`, `t_half_peak`, `t_return`, `residual` from the pilot's gate1.py, plus `baseline_variance` and `overshoot` from the planned docs/model.md. Definitions in section 7.
- Gate: the ordering tests pass. Synthetic units generated with a longer true recovery time constant get a longer t_return and t_half_peak, in the generated order; a larger injected amplitude gives a larger peak_rate; the estimated baseline matches the generator's baseline within tolerance.
- Depends on nothing.

### P2-2 engine integration

Wires measures.py into the released tools. Waits for a stimulation dataset so the integration is shaped by a real format rather than a guess.

- `--spikes spikes.csv` on rrb-evaluate: compute the measures from spikes instead of reading responses.csv.
- analysis.json: the AnalysisParams written to disk beside the tables, loaded, validated, and hashed into the report. The analysis is declared before the run and the hash proves which one was used. Same idea as the protocol fingerprint.
- pre_stim_window_s check: a new requirement that each onset is preceded by a stimulus-free window long enough to estimate baseline_hz. It goes in a new check module because checks.py is at 298 lines. Value to confirm; 1.0 s proposed.
- Per-half PSTH measures: the split in box 3 happens before the measures in box 4.
- Gate: on the synthetic generator with a known injected reliability, `--spikes` reproduces the known ρ within the positive-control tolerance, and every existing test still passes.

### P2-3 the adapter

Reads the lab's files and writes units.csv, spikes.csv, and the sidecars. Written with the lab, because only they know their format's quirks. Contains no analysis of any kind. Gate: rrb-check passes on their data, or names the requirement it fails.

### P2-4 the pilot reproduction

Run the Phase 2 pipeline on the pilot dataset and compare with the number the pilot's own script produced (gate1.py, 0.779). Gate: agreement within a stated tolerance, or a written reason for the difference. Needs gate1_run.py and its saved output. Then tag v0.2.0.

## 5. Items that ride with v0.2.0

- **Sensitivity axis.** d = (mean of per-unit means, treated − control) / pooled SD across units within condition. Needs two conditions and an expected direction. Defined in the glossary prompt from this thread.
- **Reference row.** Baseline firing rate's ρ and d reported beside every submitted measure, so a submission has something to beat and a stable, meaningless measure is visible as such.
- **split_mode="random".** Alternative to odd/even: assign trials to halves at random, repeat over seeds, report the spread of ρ. Odd/even stays the headline because it is deterministic and robust to slow drift within a session; random is the robustness check.
- Why they wait: each needs a two-condition stimulation dataset to be shaped against, and none of them changes the headline number.

## 6. Exception 1: the report generator

`scripts/sharf2022_g0.py` becomes the template `scripts/<dataset>_g0.py`. g0 means gate 0: the pretest that asks whether the machinery runs on this dataset and what the number is, before any claim is made.

Steps in the template: locate the deposit (the public archive copy: Dryad, Zenodo, DANDI) → read the format doc → gap and unit check (inter-stimulus gap of at least 2 s and at least 8 units, read from the format doc or a quick pass; Wagenaar fails here, so no adapter is written for it) → adapter only if it passes → rrb-check and rrb-evaluate by subprocess (the CLI, not an import, so the report uses exactly the released tool) → summary.md with one figure and one paragraph.

One run of this script is the deliver-before-asking artifact for an email, the Step 8 two-week report for a lab that said yes, and one atlas row. Same code, three uses.

## 7. Glossary of every term in Track B

| Term | Meaning |
|---|---|
| Track A | Outreach. The main track until January 15. |
| Track B | Code. Written only in response to a specific dataset after Nov 24, with the two exceptions above. |
| Nov 24 gate | First count of replies to the first emails. Information, not a verdict. |
| Step 8 | Track A step: convert the first yes into a two-week reliability report on the lab's archived data. |
| Deliver before asking | Run the benchmark on a lab's public data first and lead the email with the result. |
| Deposit | The public archive copy of a dataset (Dryad, Zenodo, DANDI). |
| Format doc | The deposit's description of its files, columns, units and sampling. |
| Gap and unit check | Inter-stimulus gap ≥ 2 s and ≥ 8 units, checked before any adapter is written. |
| Adapter | Code that reads one lab's format and writes benchmark CSVs. No analysis inside. |
| rrb-check | CLI entry point for the contract (the six requirements). Exit 0 conforming, 1 violation. |
| rrb-evaluate | CLI entry point for reliability: split, correlate, correct, interval, null, positive control. |
| Subprocess | Calling the CLI as a separate process rather than importing the package, so the report runs the released tool unchanged. |
| summary.md | The report: one figure, one paragraph, the counts, the verdict. |
| Atlas, atlas row | The public table of results across datasets. One row = one dataset × condition × measure with ρ, interval, unit and trial counts, conformance level, protocol fingerprint. |
| g0 | Gate 0: the pretest run on a dataset before any claim. |
| Pilot | The first stimulation dataset, analyzed earlier in Stable Basin by gate1.py. Source to confirm. |
| gate1.py, gate1_run.py | The pilot's analysis script and its runner. gate1.py produced 0.779. |
| PSTH | Peri-stimulus time histogram. For one unit: take every spike's time since the stimulus onset of its own trial, pool across the trials in question, bin, divide the count in each bin by (number of trials × bin width). Result: firing rate in Hz as a function of time since stimulus. |
| Log-spaced bins | 40 bin edges spaced logarithmically from 3 ms to 10 s. Fine resolution early, where the peak is; coarse late, where the return is. Bins past the post-stimulus window are dropped. |
| pre_stim_window_s | Length of the stimulus-free window before each onset used for baseline. New requirement in P2-2. |
| post_stim_window_s | Length of the window after each onset; min-dataset-6 requires at least 2.0 s. |
| trial_latencies | Spike times minus the onset of their trial, kept if inside the pre or post window. |
| pre_counts | Spike count in the pre-stimulus window, per trial. |
| baseline_hz | Sum of pre_counts over the pooled trials / (number of trials × pre_stim_window_s). |
| psth_rate | The PSTH as an array of rates, one per bin. |
| recovery_measures | The function that turns one psth_rate and one baseline_hz into the measures below. |
| make_spike_trains | Synthetic generator: a Poisson process at baseline_hz, plus a post-stimulus rate bump that decays with a per-unit time constant. Used only in tests. |
| AnalysisParams | The dataclass holding bin edges, pre and post windows, return_x_baseline, half_peak_frac, residual_s. Serialized as analysis.json. |
| analysis.json | AnalysisParams on disk, beside preparation.json and conditions.json. Hashed into the report. |
| t_peak | Time (center of the bin) of the maximum post-stimulus rate. |
| peak_rate | That maximum, in Hz. |
| half_peak_frac = 0.5 | Fraction of the peak elevation above baseline that defines t_half_peak. |
| t_half_peak | First bin after t_peak where rate ≤ baseline_hz + half_peak_frac × (peak_rate − baseline_hz). |
| return_x_baseline = 1.5 | Multiple of baseline that counts as returned. |
| t_return | First bin after t_peak where rate ≤ return_x_baseline × baseline_hz. If never inside the window: censored at the window end and flagged. Censoring rule to confirm against gate1.py. |
| residual_s = 1.0 | Time after onset at which the residual is read. |
| residual | Rate at residual_s minus baseline_hz, as a multiple of baseline_hz. Exact form to confirm against gate1.py. |
| baseline_variance | Variance across trials of the pre-stimulus rate for one unit: the trial-to-trial wobble of the resting rate. |
| overshoot | Largest excursion below baseline after t_return, inside the window, as a fraction of baseline_hz. Proposed; to pin in P2-1. |
| Ordering tests | Tests on synthetic data that check each measure recovers the generator's known order (longer true time constant → longer t_return), not its exact value. |
| Per-half | Computed once from the pooled trials of one half, rather than once per trial and then averaged. |
| --spikes | The rrb-evaluate flag that switches on the compute-from-spikes path. |
| split_mode | "odd_even" (headline) or "random" (robustness check, v0.2.0). |
| Sensitivity axis, reference row | Section 5. |
| docs/model.md | Planned doc: a linear relaxation model with three parameters. A quantity relaxes toward baseline at rate Γ (time constant 1/Γ) while kicked by noise of intensity Q; its resting variance is Π = Q / (2Γ) in one dimension. baseline_variance estimates Π; t_return and t_half_peak estimate 1/Γ; overshoot says the return is not a single exponential. |
| v0.2.0 | The tag after P2-4 passes. |

## 8. To confirm

1. Phase 3: adopt the definition in section 2 or replace it.
2. Pilot dataset: which one, where gate1_run.py and its output live.
3. pre_stim_window_s value for the new check.
4. t_return censoring rule and the exact residual formula: take both verbatim from gate1.py when P2-1 runs.
5. overshoot definition.

## 9. Prompt Planning

Expected: About 12 to 15, of which 10 build something and the rest are fix-ups.

```markdown
| Step | Prompts | What each one does |
|---|---|---|
| 0 Guardrails | 1 (running) + 0–1 | fix-up if the agent's first pass misses a frozen function or breaks the 300-line rule |
| 1 measures.py | 2 | (a) bump version to 0.2.0 with a CHANGELOG heading, then the measures and the synthetic spike-train generator with ordering tests; (b) likely a split, since seven measures plus a generator will not fit in 300 lines |
| 2 Engine | 2–3 | (a) AnalysisParams, analysis.json, the pre-stimulus check in its new module, SPEC text; (b) the `--spikes` path with per-half measures and the known-answer test; (c) fix-up |
| 3 Report | 2 | (a) reference row and sensitivity with the injected-shift test; (b) `rrb-report` command and the Sharf script rewritten to call it |
| 4 Tag | 3 | (a) adapter for the pilot format and the comparison against 0.779; (b) SPEC, METHOD, GLOSSARY, CHANGELOG updates; (c) `freeze.py --update`, CHANGELOG `Frozen:` lines, tag text |
| Cleanup | 1–2 | the usual style and glossary pass before the tag |
| **Total** | **12–15** | about 10 build prompts, the rest fix-ups |
```
