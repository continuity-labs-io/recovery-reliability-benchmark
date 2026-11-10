# Recovery Reliability Benchmark

## Glossary

Terms as this repository uses them, grouped from the physical experiment up to the benchmark's claims. Each entry says where the term is defined or implemented. Plain definitions; where a term has a narrower technical meaning elsewhere, the entry says which one applies here.

---

## 1. The experiment

**Preparation.** One physical specimen: a dissociated culture, an organotypic slice, an organoid, or a piece of engineered neural tissue. One `preparation_id` per dataset. SPEC §2; `units.csv`.

**Session.** One continuous acquisition from one preparation, with no medium change, incubator opening or handling in between. The benchmark's unit of reliability is the session: everything is computed within one. SPEC §2, min-dataset-1.

**Recording.** One acquisition file. A session is continuous, so a conforming dataset has exactly one `recording_id`. A second recording is treated as a second session. SPEC §2, min-dataset-1.

**Recording unit (unit).** One spatially distinct channel of measurement: an electrode, a sorted unit, a cell, a region of interest, or a pixel group. The reliability correlation runs across units, so the unit is the axis of the whole computation. On an HD-MEA a unit is usually a sorted neuron or a single electrode; the spec does not care which, but one dataset must use one definition. SPEC §2; `unit_id`.

**Electrode.** A physical recording site. Not the same as a unit: one electrode may carry several sorted units, and one unit may be seen on several electrodes. The pilot analysis used electrodes as units.

**Spike sorting.** Assigning recorded voltage events to putative neurons. The benchmark accepts already-sorted output and does not sort; adapters that read instrument files will call an external sorter if the lab wants one.

**MEA, HD-MEA.** Microelectrode array; high-density microelectrode array (thousands of electrodes at tens of micrometers pitch, for example MaxWell MaxOne/MaxTwo, 3Brain, Axion Synexus). The benchmark is defined independently of the instrument; MEAs are the first modality it is used on.

**Modality.** How the response is recorded: extracellular electrodes, calcium imaging, voltage imaging, impedance. Conformance is defined by content, not container or modality. SPEC §6, §8.

**Stimulus, stimulus onset.** One delivery of the conditioning load and the instant it starts. The onset is the time origin of a trial and is stored as `stim_time_ns` on the same clock as the response data. SPEC min-dataset-4.

**Trial.** One stimulus delivery and the recorded response that follows it, identified by an integer `trial_index`. SPEC §2.

**Condition.** A stimulus parameter set. Two trials share a condition only when every stimulus parameter is equal. A condition is identified by a label; the parameters behind the label are described in `conditions.json` and identified by the protocol fingerprint. SPEC §2.

**Conditioning load.** The stimulus whose after-effects are measured: a defined pattern of pulses (for example 100 pulses at 100 Hz for one second) strong enough to push the tissue away from its baseline state. "Load" rather than "stimulus" to stress that it is a perturbation, not a probe. Described by `protocol.py`.

**Conditioning-and-probe protocol.** The established experimental pattern: deliver a conditioning load, then probe the tissue's state afterward. Long-term potentiation induction, paired-pulse protocols and cardiac restitution are all of this form. The benchmark uses the pattern but changes the readout to the time course of recovery.

**Recovery, recovery kinetics.** The return of a response variable toward its pre-load baseline after the conditioning load, and the time course of that return (how fast, how completely, with what shape). The measures in this benchmark are summaries of recovery kinetics.

**Post-stimulus window (`post_stim_window_s`).** The length of recording after each stimulus onset that is available for computing measures. Declared by the submitter; MUST be at least 2.0 s and MUST fit before the next onset. SPEC min-dataset-6.

**Load duration (`load_duration_s`).** The length of the conditioning load itself. When declared, the post-stimulus window is required after the load ends rather than after its onset, which only tightens min-dataset-6. Equal to `Protocol.total_duration_s`.

**Time zero (load end).** The reference timestamp `onset + load_duration_s` for post-stimulus latencies on each trial; spikes occurring during the conditioning load (`onset <= t < onset + load_duration_s`) are not latencies. `measures.trial_latencies`.

**Inter-stimulus interval.** Onset-to-onset time between consecutive stimuli. `min_inter_stimulus_s` in the conformance report is the smallest one in the dataset.

**Baseline.** The pre-load level of the response variable (for example firing rate) that recovery is measured against, computed over the pre-stimulus window `measures.AnalysisParams.pre_stim_window_s`, 1.0 s default (`measures.baseline_hz`).

**Baseline variance (`baseline_variance_hz2`).** Sample variance (`ddof=1`, in Hz²) across trials of a unit's pre-stimulus firing rate (`pre_counts / pre_stim_window_s`); `NaN` when fewer than two trials are present. `measures.baseline_variance_hz2`.

**Drift.** Slow change in a preparation's state across a session. Odd/even splitting exposes both halves to drift equally, which is why it is the default split.

---

## 2. The tables

**`unit_id`.** A single physical recording channel (an electrode on an array, a spike-sorted neuron, or an imaged region of interest) tracked across every trial of the session. The benchmark correlates recovery measures across `unit_id`s to test whether different channels on the same tissue consistently respond the same way from trial to trial.

**`recording_id`.** The single continuous acquisition file written by the instrument during a run. Because stopping and restarting acquisition breaks continuity, a conforming dataset has one `recording_id` matching its single session.

**`session_id`.** One uninterrupted experimental run on the tissue, during which the preparation stays on the rig without medium changes, incubator openings, or physical handling. All trials that get split into halves and compared come from a single `session_id`.

**`preparation_id`.** The physical piece of neural tissue under test: a single culture well, brain slice, organoid, or engineered construct. Every row in a conforming dataset shares one `preparation_id` because the benchmark scores reliability within one specimen at a time.

**`x_um`, `y_um`.** The physical coordinates of a recording unit on the array or imaging field of view, in micrometers. Optional and unused by the core reliability calculation, they record where each unit sits on the tissue so spatial patterns or distance from the stimulating electrode can be inspected.

**`trial_index`.** The sequential number of a single stimulus delivery and its subsequent recovery window within the session. In execution, `trial_index` orders the repeated deliveries of a condition so they can be dealt into even and odd halves for split-half correlation.

**`stim_time_ns`.** The timestamp, in nanoseconds on the recording clock, at the instant a conditioning stimulus begins on the tissue. It anchors the time origin of each trial and lets the validator verify that enough recovery time elapsed before the next stimulus was delivered.

**`condition`.** A label naming the exact experimental regime applied on a trial: the stimulation protocol together with any active compound and dose. Trials sharing a `condition` are physical repeats of the same perturbation and are grouped together when splitting trials into halves.

**`spike_time_ns`.** The timestamp, in nanoseconds on the same recording clock as `stim_time_ns`, of a single detected action potential on a unit. Subtracting a trial's `stim_time_ns` gives each spike's latency after stimulation, from which post-stimulus recovery curves and measures are built.

**`units.csv`.** One row per recording unit: `unit_id`, `recording_id`, `session_id`, `preparation_id`, optional `x_um`, `y_um`. SPEC §9.

**`responses.csv`.** One row per unit and trial: `unit_id`, `trial_index`, `stim_time_ns`, `condition`, and one column per measure. The table the contract and the ceiling run on. SPEC §9.

**`spikes.csv`.** One row per spike: `unit_id`, `spike_time_ns`, on the same clock as `stim_time_ns`. Requested now, required from v0.2.0, when the benchmark computes measures from spikes itself. SPEC "Raw data".

**Sidecar.** A small JSON file beside the tables carrying metadata: `preparation.json` (species, preparation type, age, line or donor, instrument) and `conditions.json` (per condition: protocol, compound, dose, vehicle). Optional at v0.1.x, validated when present. SPEC "Preparation and condition metadata"; `metadata.py`.

**`analysis.json`.** Sidecar JSON file declaring `measures.AnalysisParams` before the run, loaded by `metadata.load_analysis` and written by `metadata.write_analysis`; its SHA-256 fingerprint is printed in the report. SPEC "Preparation and condition metadata".

**Fate table (`fate.csv`).** Optional later observations of the same preparation (date, status, measure, value), so atlas rows can carry outcome labels. Defined, not yet checked. SPEC "Fate".

**Measure.** A scalar computed per unit per trial from the post-stimulus response; a column of `responses.csv`. Examples: time to return to baseline, peak rate, spike count in the window. SPEC §2.

**Per-trial measure.** A measure that exists for a single trial on its own, so that a unit's value over several trials is the mean of per-trial values. Spike count in the window and first-spike latency are per-trial measures. v0.1.0 handles only these.

**PSTH (peri-stimulus time histogram).** Spike counts in time bins after stimulus onset, pooled over a set of trials and divided by trial count and bin width to give a rate. The pilot's recovery measures are read off a PSTH, not off single trials. `measures.psth_rate`.

**PSTH-based measure.** A measure defined on the pooled PSTH of many trials rather than one trial at a time, computed by `measures.recovery_measures`: `t_peak` (bin center of the maximum rate), `peak_rate` (that maximum), `t_half_peak` (first bin center after the peak bin with rate at or below `baseline + half_peak_frac * (peak_rate - baseline)`), `t_return` (right edge of the last bin exceeding `return_x_baseline * baseline`), `residual` (mean rate over bins whose center is at least `post_stim_window_s - residual_s`, divided by baseline), and `overshoot`. Reads single bins, so it needs many spikes per bin; on the synthetic example at 20 trials `peak_rate`, `t_peak` and `t_half_peak` score near zero. Unresolved recovery inside the window is censored at `post_stim_window_s` with `t_half_peak_censored` or `t_return_censored` (never `NaN`); if no bin exceeds threshold, `t_return` is `0.0` with `no_response`. When baseline is `0.0`, `t_return`, `residual`, and `overshoot` are `NaN` with `baseline_zero` set while `t_peak`, `peak_rate`, and `t_half_peak` are still computed.

**Bin-free measure.** A recovery measure built on the running post-stimulus spike count without time bins (`excess.excess_measures`: `t_half_excess` and `excess_per_trial`, plus `spikes_per_trial`), invariant to `bin_edges_s`.

**Excess spikes.** Post-stimulus spikes above the count expected from the pre-stimulus baseline firing rate over the window: `excess_total = N - baseline * n * post_stim_window_s`, where `N` is the pooled post-stimulus spike count across `n` trials in `[0, post_stim_window_s)`. `excess.excess_measures`.

**`t_half_excess`.** Latency of the first pooled post-stimulus spike `k` (`k = 1..N`, sorted across `n` trials) whose running excess count `k - baseline * n * pooled[k - 1]` reaches `0.5 * excess_total`. For an exponential recovery with time constant `tau` and a window much longer than `tau`, `t_half_excess` estimates `tau * ln 2`. `NaN` with flag `no_excess` when `excess_total <= min_excess_z * sqrt(max(N, 1))`. `excess.excess_measures`.

**`excess_per_trial`.** Mean excess post-stimulus spikes per trial over `[0, post_stim_window_s)`, `excess_total / n`. Never `NaN` for `n >= 1`; may be negative. `excess.excess_measures`.

**Overshoot.** Pooled firing-rate deficit below baseline after `t_return`, computed over bins with center `> t_return` as `max(0, (baseline - r_after) / baseline)` where `r_after = sum(rate_i * width_i) / sum(width_i)`; `NaN` with `overshoot_undefined` when `t_return` is censored, no bin follows `t_return`, or baseline is zero. `measures.recovery_measures`.

**Spikes per trial (`spikes_per_trial`).** Mean over trials of the post-stimulus spike count (`len(lat)` per trial from `measures.trial_latencies`, so every spike in `[0, post_stim_window_s)` counts, not only those inside the bin edges). Computed by `measures.unit_measures`; never `NaN` when there is at least one trial.

**Spikes path.** Computing per-half measures directly from `spikes.csv` into the halves DataFrame consumed by `evaluate.reliability_ceiling` (enabled by `--spikes` and `--analysis` on `rrb-check` and `rrb-evaluate`, or `analysis` in `run.run`): `spikes.trial_table` extracts distinct `(trial_index, stim_time_ns, condition)` rows, `spikes.per_trial_counts_table` builds the per-trial post-stimulus spike-count table validated by `contract.validate`, `spikes.split_trials` partitions a condition's trials into odd and even halves by the same 1-based rule as `evaluate.split_halves`, `spikes.spike_times_by_unit` maps each unit to sorted spike timestamps in seconds, `spikes.halves_from_spikes` runs `measures.unit_measures` on each half to produce the `(halves, flags)` DataFrames, and `spikes.scored_units` identifies the scored units per condition. `spikes.py`.

**Scored unit.** On the spikes path: "A unit is scored for a measure in a condition when that measure is computed in both halves." (`spikes.scored_units`, non-`NaN`); a silent unit has no baseline and is excluded (`checks_spikes.check_scored_units`). SPEC "Inclusion and exclusion".

**Analysis parameters (`measures.AnalysisParams`).** The frozen dataclass holding the PSTH and recovery-measure parameters (`post_stim_window_s`, `pre_stim_window_s`, `load_duration_s`, `bin_edges_s`, `return_x_baseline`, `half_peak_frac`, `residual_s`, `min_excess_z`) and its SHA-256 JSON `fingerprint()`. `analysis.py`; `measures.py`.

**Bin edges.** The boundaries of the PSTH time bins, log-spaced in the pilot so that early fast dynamics and late slow return are both resolved. A declared analysis parameter, recorded in the report.

**Censored value.** A measure that could not be resolved inside the window (for example the rate never returned to baseline) and is reported as the window length with a flag, rather than as a missing value. SPEC "Nulls" requires this: a null means "not computed", never "did not recover".

**Null (NaN).** A missing measure value. A unit with a null in any trial of a condition is not active in that condition. SPEC "Nulls".

**Active (unit).** A unit is active in a condition when it has a row for every trial of that condition with every measure non-null. min-dataset-3 counts active units. SPEC min-dataset-3.

**Inclusion rule (`INCLUSION_RULE`).** The pre-registered rule applied identically by `validate()` and `evaluate()`: a unit is included in a condition if and only if it has a row for every trial of that condition with every measure non-null. All present trials are used; no trial is excluded by rule in v0.1.x. SPEC "Inclusion and exclusion"; `contract.py`; `evaluate.split_halves`.

**Declared exclusion (`exclusions`).** A unit or trial removed by the contributor before submission (for example a dead electrode, stimulation-artifact saturation, or a dropped trial), recorded in `preparation.json` under `exclusions` with `kind` (`"unit"` or `"trial"`), `id`, and a non-empty `reason`. Declaring a unit or trial ID that is still present in `units.csv` or `responses.csv` is a `SCHEMA` contradiction. SPEC "Inclusion and exclusion"; `metadata.Exclusion`; `contract.validate`.

**Identifier columns.** `unit_id`, `recording_id`, `session_id`, `preparation_id`, `condition`, `trial_index`, `stim_time_ns`. Compared as strings where they are labels; never allowed as measures.

**Forbidden measure.** A column that cannot be scored: the identifier columns, any non-numeric or all-null column, and any column constant within every (unit, condition) group, which would score as perfectly reliable while carrying no trial-to-trial information. SCHEMA check in `contract.py`.

---

## 3. The computation

**Reliability.** The fraction of a measure's observed variance across units that is true (reproducible) variance rather than measurement error: Var(T) / (Var(T) + Var(E)). Between 0 and 1. METHOD §1.

**Within-session reliability.** Reliability estimated from a single session by comparing two halves of its trials. The quantity the benchmark reports.

**Per-unit reliability.** Reliability of the vector of per-unit values, as opposed to the reproducibility of a well-level or dish-level average. The benchmark reports per-unit reliability; most published assays report well-level reproducibility or none.

**Reliability ceiling (ceiling).** Reliability as an upper bound: by the attenuation theorem, no correlation between a measure and anything else can exceed the measure's correlation with itself. A low ceiling means downstream results built on the measure are uninterpretable before they are run. METHOD §1; `evaluate.reliability_ceiling`.

**Attenuation theorem.** r(X, Y) ≤ sqrt(reliability(X) × reliability(Y)); the observed correlation between two noisy measures is attenuated by their reliabilities. The reason "ceiling" is the right word. METHOD §1.

**Split-half.** Dividing one session's trials into two halves, computing the measure on each, and correlating the two results across units. Two measurements of the same vector from one recording. METHOD §3; `evaluate.split_halves`.

**Odd/even split (`odd_even`).** Within each (unit, condition) group, trials are sorted by `trial_index` and assigned 1-based positions 1, 2, 3, ...; odd positions (1, 3, 5, ...) go to the odd half and even positions (2, 4, 6, ...) go to the even half. Balanced against drift. The only split mode in v0.1.0; `random` is planned.

**Half means (odd, even).** For each (unit, condition) group, the mean of the measure over the odd-half trials (`{measure}_odd`, count `n_odd`) and over the even-half trials (`{measure}_even`, count `n_even`); the two vectors that get correlated.

**Pearson r (`r_half`).** The correlation between the odd-half and even-half values across the pairs being scored. Reported raw, before correction.

**Spearman-Brown correction.** rho = 2r / (1 + r): converts the correlation between two half-length measurements into the reliability of the full-length measurement. METHOD §3.

**rho.** The reliability ceiling after Spearman-Brown. Reported as 0.0 when `r_half` is undefined (`r_undefined`) or non-positive (`r_nonpositive`), because the correction is not meaningful for non-positive correlations.

**Per-condition estimate.** The ceiling computed on one condition's units only. The simplest estimate; noisy at small unit counts.

**Pooled estimate.** The ceiling computed over (unit, condition) pairs across all evaluated conditions at once, as the pilot analysis did. More stable, but pairs sharing a unit are not independent.

**Condition-centering (centered).** Subtracting each condition's mean over units, within each half, before correlating the pooled pairs. Removes between-condition variance (for example a dose effect) that would otherwise inflate the pooled ceiling. Has no effect on a per-condition estimate. METHOD §4.

**Headline.** The ceiling reported first for a measure: pooled-centered when two or more conditions are evaluated, otherwise the per-condition estimate on the best condition. `evaluate.headline`; `run.run`.

**Fisher z interval.** The confidence interval on `r_half` (`r_ci_low`, `r_ci_high`) obtained by transforming r to z = atanh(r), using standard error 1/sqrt(n − 3) and normal critical value `z_crit`, and transforming back; then applied through Spearman-Brown to give `rho_ci_low`, `rho_ci_high`. METHOD §3.

**n_eff.** The sample size used for the interval: the number of units, never the number of (unit, condition) pairs, because pairs sharing a unit are not independent. Conservative for pooled estimates.

**Single-trial reliability (`rho_single_trial`).** The reliability one trial would have, recovered from rho and the trial count by inverting Spearman-Brown: rho1 = rho / (n − (n − 1) rho). Lets sessions with different trial counts be compared. `rho_at_20` is the same quantity re-expressed at 20 trials.

**Variance components (`var_between`, `var_within`, `moments_reliability`).** Over the units included in a condition, the variance across units of per-unit trial means (`var_between`, `ddof=1`), the mean across units of per-unit trial variances (`var_within`, `ddof=1`), and the ANOVA-style moments reliability estimate `max(0, (var_between - var_within / n_trials) / var_between)`. Reported next to each split-half ceiling: a ceiling driven by between-unit heterogeneity shows up as large `var_between` relative to `var_within`, and `moments_reliability` estimates the same quantity as `reliability_ceiling()`'s `rho`. METHOD §3; `evaluate.variance_components`.

**Sensitivity axis.** The companion axis to reliability: with two or more conditions, the between-condition effect per unit divided by that unit's split-half noise, summarized as the fraction of units moving more than twice their own noise band and the median standardized effect; with one condition, the same quantity between the post-load window and the pre-load baseline. Reported beside reliability, never merged into one score. Planned for v0.2.0 (`measures.py`). METHOD "How this benchmark can be gamed".

**Reference measure.** Baseline firing rate, reported as a reference row alongside every submitted measure so that a measure winning on reliability alone while saying nothing about recovery is visible; a submitted measure that does not beat the reference on the sensitivity axis is listed and marked. METHOD "How this benchmark can be gamed"; CONTRIBUTING "Submitting measures".

**Permutation null (label-permutation null).** Shuffling which unit's even-half values are paired with which unit's odd-half values, within each condition, and recomputing the ceiling many times through the same function. Shows what the estimate looks like when unit identity carries no information. METHOD §5.2; `controls.permutation_null`.

**Positive control.** A synthetic dataset with a known injected reliability run through the identical pipeline before any real data; if the pipeline does not recover the injected value within tolerance, every other number in the run is void. Fixed at 1,000 units × 20 trials, injected 0.85, tolerance 0.05. METHOD §5.1; `controls.positive_control`.

**Injected reliability.** The reliability a synthetic dataset is generated to have: unit true values T ~ N(0, 1), per-trial errors with variance n(1 − rho)/rho, so that the n-trial mean has reliability rho. `synthetic.make_tables(reliability=...)`.

**Independence census (independence accounting).** The report's explicit count at every level, preparations, sessions, recordings, units, conditions, trials, so a reader can see what was treated as one sample. Trials are not independent samples of a preparation; units are only partly so. METHOD §5.3.

**Pseudo-replication.** Counting non-independent observations (trials from one preparation, pairs sharing a unit) as if they were independent samples. The census exists to make it visible.

**Threshold simulation.** `scripts/thresholds.py`: synthetic sessions at the min-dataset-2/min-dataset-3 thresholds, 1,000 seeds per cell, reporting where the estimate lands. The basis for the MUST and SHOULD numbers and for the interval statements in SPEC §4–5. `docs/thresholds.md`.

---

## 4. Conformance

**Conformance.** Whether a dataset supports the computation. Necessary, not sufficient: a conforming dataset can still yield a ceiling of zero. SPEC §11, §13.

**Conformance check.** Running `rrb-check` on `units.csv` and `responses.csv`. Produces a verdict and counts, or the first violation. Runs locally; nothing leaves the machine.

**Minimum dataset requirements (min-dataset-1 to min-dataset-6).** The six requirements a dataset MUST meet: one preparation/session/recording (min-dataset-1), enough trials (min-dataset-2), enough active units (min-dataset-3), consistent stimulus timestamps (min-dataset-4), one row per unit and trial (min-dataset-5), enough recording after each stimulus (min-dataset-6). SPEC §4; `Requirement` enum.

**Pre-stimulus window (`min-dataset-7`).** Applies when measures are computed from spikes: the declared `pre_stim_window_s` is at least 1.0 s (`contract.MD7_MUST`), fits before the first onset on the recording clock, and fits between every previous load end and the next onset (`checks_spikes.check_pre_stimulus_window`). SPEC min-dataset-7; `contract.Requirement.MD7`.

**MUST, SHOULD, MAY.** RFC 2119 words. MUST thresholds are admission floors: below them the computation is undefined. SHOULD thresholds are where the estimate becomes precise enough to act on. SPEC header, §4.

**Conforming / fully conforming.** All MUST thresholds hold for at least one condition / all MUST and all SHOULD thresholds hold for at least one condition. Reported with the condition that achieved it and the SHOULD thresholds it misses. SPEC §5.

**Evaluated condition.** A condition that meets the MUST thresholds of min-dataset-2 and min-dataset-3; the ceiling is computed on evaluated conditions only. SPEC §2.

**Best condition.** Among evaluated conditions, the one missing the fewest SHOULD thresholds (ties: more active units, then more trials, then name). Determines the dataset's conformance level and the per-condition headline.

**SCHEMA checks.** Checks on the container rather than the dataset: required columns present, measures numeric and allowed, `unit_id` unique, no orphan rows, sidecars consistent. Reported under the name SCHEMA; not one of the six requirements. SPEC §9.

**Check registry (`checks.CHECKS`).** The ordered tuple of `(Requirement, name, check_fn)` entries that `contract.validate` runs from top to bottom, stopping at the first `ContractViolation`. Schema checks run before `min-dataset-1` through `min-dataset-6`; adding a requirement means adding a check function and a registry entry in `checks.py`.

**Validation context (`contract.ValidationContext`).** The dataclass holding working copies of the input tables, declared parameters, optional sidecars, and intermediate derived state (`conditions_info`, `trials`, `gaps_s`) that each check in `checks.CHECKS` reads and populates before `contract.build_report` assembles the conformance report.

**ContractViolation.** The exception (and CLI exit code 1) raised on the first failed check, naming the requirement, the value found and the value required. SPEC §11; `contract.ContractViolation`.

**Optional data (optional-dataset-1 to optional-dataset-5).** Items that add value without being required: multiple amplitudes, repeated sessions, both polarities, preparation metadata, raw signal. SPEC §7.

**Specification version vs package version.** SPEC v1.0 is the normative document; the package (`recovery-reliability-benchmark`) is at 0.1.x. Requirement IDs are stable across minor spec versions; thresholds change only in a major one. "Required from v0.2.0" refers to the package and will appear as SPEC v1.1. SPEC §14.

**Conformance report.** The JSON `rrb-check --json` prints: verdict, counts, spec version, arguments, SHA-256 of the input files. What a lab shares instead of data.

**SHA-256.** A cryptographic digest of a file. In the report it ties a verdict to the exact files it was computed on.

---

## 5. The protocol schema

**Pulse.** One stimulation waveform: shape (biphasic or monophasic square), polarity order, phase durations, inter-phase gap, amplitudes in µA (current mode) or mV (voltage mode). `protocol.py`.

**Current mode / voltage mode.** Whether the stimulator controls current or voltage. Charge is known only in current mode; in voltage mode delivered charge depends on electrode impedance.

**Charge balance.** For a biphasic pulse in current mode, equal charge in the two phases so the net injected charge is zero. Validated with a relative tolerance.

**Burst.** A number of identical pulses at an intra-burst frequency. **Train.** A number of bursts at an inter-burst interval. **Protocol.** A named set of trains at an inter-train gap. The four-level hierarchy Pulse → Burst → Train → Protocol.

**Interval vs gap.** An interval is onset-to-onset; a gap is end-to-onset. `intra_burst_frequency_hz` and `inter_burst_interval_ms` are intervals; `inter_train_gap_s` is a gap. Stated once in the module docstring so two labs encode the same timing the same way.

**Protocol fingerprint.** SHA-256 of the protocol's canonical JSON excluding its name. Two protocols with equal parameters and different names share a fingerprint. The key that says two labs delivered the same load. `Protocol.fingerprint()`.

**Commanded vs delivered.** The protocol describes what the stimulator was told to do. What the tissue received also depends on electrode count, impedance and return configuration (the planned `Delivery` model). The fingerprint identifies the command.

**Factory protocols.** `standard_hfs` (100 pulses at 100 Hz), `spaced_hfs` (four such trains 20 s apart), `theta_burst` (10 bursts of 4 pulses at 100 Hz, 5 Hz between bursts). Reference loads with conventional timing; amplitude is always the lab's.

---

## 6. The benchmark and the atlas

**Benchmark (as used here).** A fixed computation that every contributed dataset is scored by. The measures are what get scored; the datasets are the test set; the spec is the admission rule for the test set. Closer to an inter-laboratory ring trial than to an ImageNet-style benchmark. README.

**Frozen layer.** The functions and constants that implement the `METHOD.md` and `SPEC.md` procedure (`checks.CHECKS`, `contract.validate`, `contract.build_report`, `evaluate.split_halves`, `evaluate.reliability_ceiling`, `evaluate.variance_components`, `evaluate.headline`, `controls.permutation_null`, `controls.positive_control`, `controls.census`, `synthetic.make_tables`, `protocol.Protocol.fingerprint`, and the threshold and control constants), registered in `frozen.FROZEN_FUNCTIONS` and `frozen.FROZEN_CONSTANTS` and snapshotted under `frozen/`. Never modified in response to a dataset's result; any change requires a minor version bump, a `Frozen:` entry in `CHANGELOG.md`, and `python scripts/freeze.py --update`. `FROZEN.md`; `frozen.py`.

**Ring trial (inter-laboratory study).** Several laboratories run the same procedure on their own material and the results are compared. The benchmark's multi-lab phase is one.

**Test set.** The contributed datasets. A result on one dataset and a result on another are comparable only because both passed the same conformance spec.

**Submitted measure.** A proposed recovery measure registered as a named function from the raw inputs (spike times, stimulus times, declared parameters) to one value per unit per trial or per half. Scored on the fixed public datasets with splits chosen by the benchmark, never by the submitter, and reported on both reliability and the sensitivity axis (with its interval and inclusion counts) next to the baseline-firing-rate reference row; a measure that does not beat the reference on sensitivity is listed and marked. The leaderboard does not exist yet; this is the rule it will follow. CONTRIBUTING "Submitting measures".

**Atlas, atlas row.** The accumulating public collection of scored datasets. A row is keyed by (protocol fingerprint, condition, preparation): the commanded load, the condition label with its pharmacology, and the specimen. SPEC §1.

**Contributor, contribution.** A laboratory that supplies a conforming dataset; the dataset once deposited. Contributions are accepted only under CC0. CONTRIBUTING §5.

**Report-then-deposit.** The contribution sequence: data sent for analysis, written reliability report within two weeks, deposit in the public archive only when the lab confirms after reading it. Withdrawal is unconditional before deposit. CONTRIBUTING §6, §8.

**Deposit, embargo.** Placing a dataset in the public archive under CC0; a delay before deposit, offered in paid engagements in exchange for a reduced fee. `docs/terms.md`.

**Derived data.** Measures, reliability statistics, protocol metadata and models trained on them, as distinct from raw recordings. The paid-engagement clause retains rights to derived data; raw recordings stay confidential unless agreed. `docs/terms.md`.

**Synthetic data.** Data generated by `synthetic.make_tables` with known properties, used for tests, the positive control, the threshold simulation and the examples. Never presented as a result about tissue.

---

## 7. Context: endpoints, screening and release

**Endpoint.** A measured quantity used to make a decision: whether a compound is flagged, whether a batch is released. An endpoint has to be reliable before it can be anything else.

**Functional endpoint.** An endpoint based on what the tissue does (fires, beats, recovers) rather than on what it is made of (markers, viability, morphology).

**Surrogate endpoint.** A measurable stand-in for an outcome that is slow or hard to observe directly. The long-term aim is for a recovery measure to serve as a surrogate for the effect of an intervention: a measure whose change under a treatment tracks the treatment's effect on function and, in model organisms, on lifespan. Reliability is a precondition for that use, not evidence of it.

**Pharmacology screening (safety pharmacology, neurotoxicity screening).** Testing compounds on cultured tissue for adverse functional effects. Current MEA endpoints are statistics of spontaneous activity (firing rate, bursts, synchrony, field potential duration); recovery after a standardized load is not among them. `claude/assay-landscape.md`.

**Tissue release testing (release criteria, potency assay).** The tests a manufactured tissue product must pass before it is released for use: identity, purity, viability, sterility and a product-specific potency assay. Functional, non-destructive release criteria are rare. The second half of the anchor claim.

**GMP.** Good Manufacturing Practice: the regulated production regime under which release testing happens. A GMP pipeline for engineered tissue is where a release-grade functional endpoint would be used.

**Resilience (stress-and-recover).** In aging research, the capacity to return to baseline after a perturbation; measured in animals as recovery time after a challenge. The benchmark is the tissue-level, in-vitro version of that measurement, with reliability established first.

**Anchor claim.** "Recovery kinetics after a conditioning load are an established mechanistic measurement in synaptic and cardiac physiology. They are not used as an endpoint in pharmacology screening or tissue release testing, and their per-unit reliability has not been reported." README; SPEC §1.

**Restitution (cardiac).** The dependence of action potential duration on the preceding diastolic interval after a conditioning drive; the nearest established recovery-kinetics measurement in cardiac electrophysiology. A research measurement, not a screening endpoint as far as found.

**Recovery from short-term depression.** The time course over which a synapse regains its response after a depleting train; the nearest established recovery-kinetics measurement in synaptic physiology. Defined per lab, with time constants that vary with technique.

---

This document is licensed under CC BY 4.0; see [LICENSE-DOCS](LICENSE-DOCS).
