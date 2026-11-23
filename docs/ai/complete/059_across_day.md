Task: add the across-day comparison. One computation module, one command, tests and docs.

Do not change any frozen function, any existing test assertion, the version, or docs/pass_rule.md. Do not register anything in the frozen layer in this task: no @frozen, register or freeze_constant on the new code. `python -m recovery_reliability_benchmark.frozen_manifest --check` must still pass. Read AGENTS.md and frozen/README.md first.

## 1. What it computes

Input: two spikes-path dataset folders for one preparation, a first day and a second day. Each folder is what writer.write_dataset writes: units.csv, trials_responses.csv, spikes.csv, analysis.json, and optionally preparation.json and conditions.json. Units are matched by unit_id.

Step 1. Load each day with writer.read_dataset. Load preparation.json and conditions.json with metadata.load_preparation and metadata.load_conditions when the files exist. Run inputs.from_spikes on each day for the one requested measure. A ContractViolation from either day stops the comparison.

Step 2. Check that the two days belong together. Raise ValueError naming the problem when:
- the two analysis.json fingerprints differ;
- the preparation_id values differ;
- the two days share a session_id;
- both days have conditions.json and a condition label present in both has different protocol fingerprints;
- no condition is in evaluated_conditions on both days.

Step 3. Build the across-day frame, indexed by (unit_id, condition) and sorted.
- Conditions: those evaluated on both days.
- Rows: units scored for the measure on both days in that condition, from inputs.scored.
- A unit's day value is the mean of its odd-half and even-half values in that day's inputs.halves.
- Store the first-day value in the column "<measure>_odd" and the second-day value in "<measure>_even", so the frozen functions can read the frame. Put an intent comment above this step that says so.

Step 4. Compute everything by calling the frozen functions. Write no second correlation, interval or shuffle routine.
- kind: "pooled_centered" when two or more conditions are evaluated on both days, else "per_condition".
- r_across_days, r_ci_low, r_ci_high, r_undefined, n_units, n_pairs: from evaluate.reliability_ceiling on the frame, with center true for pooled_centered and false otherwise. Use its r_half and the interval on r. Do not report rho.
- per_condition: for each condition, r_across_days and n_units from reliability_ceiling on that condition's rows with center false.
- pooled: r from reliability_ceiling on the whole frame, as "uncentered" and "centered".
- null: controls.permutation_null on the same frame and center flag with np.random.default_rng(seed). Report n_perm, p95_r and median_r. Silence the "All-NaN slice encountered" RuntimeWarning the way run.evaluate_measure does.
- above_null: r_across_days > p95_r, or None when r is undefined.
- within_session: for each day, rho from reliability_ceiling on that day's halves restricted to the frame's rows, with the same center flag. Report "first", "second" and "geometric_mean".
- fraction_of_within_session: r_across_days divided by the geometric mean, or None when r is undefined or the geometric mean is 0.
- Also report measure, conditions, preparation_id, session_ids for first and second, analysis_fingerprint, n_units_first, n_units_second, and n_units_matched, the number of unit_id values present in both units tables.

No pass threshold appears in the code. It reports numbers only.

## 2. Layout

- src/recovery_reliability_benchmark/across_days.py: a frozen dataclass DayInputs holding one loaded day, and the public functions load_day(directory, measure), across_day_frame(first_inputs, second_inputs, measure) and across_day_comparison(first, second, measure="t_half_excess", n_perm=controls.DEFAULT_N_PERM, seed=42). The last one runs steps 2 to 4 and returns the dict described above.
- src/recovery_reliability_benchmark/across_days_cli.py: main(argv) for the command.
- pyproject.toml, [project.scripts]: rrb-across-days = "recovery_reliability_benchmark.across_days_cli:main".
- tests/test_style.py: add "across_days" and "across_days_cli" to PACKAGE_MODULES.
- Each source file stays at or under 300 lines. Every public function and class has a Google-style docstring. Call the two days first and second. Names ending in _A or _B fail tests/test_style.py.
- Do not add anything to __all__ in __init__.py.

## 3. Command

rrb-across-days FIRST_DIR SECOND_DIR [--measure t_half_excess] [--n-perm 1000] [--seed 42] [--json]

- Exit 0: the comparison was computed. An undefined r still exits 0.
- Exit 1: a day violates the contract. Print "first day: " or "second day: " followed by the violation message. With --json, print the envelope with status "violation", the violation dict, and "day".
- Exit 2: input error: a missing folder or file, days that do not belong together, an unknown measure, or --n-perm below 1. Print "error: <message>" on stderr.
- Default output: plain lines in the style of text_report.print_evaluate_human. They cover package and SPEC version, analysis fingerprint, kind and conditions, r_across_days with its interval, the null p95 and above_null, n_units and n_pairs, the three unit counts, the two within-session values with their geometric mean, and fraction_of_within_session.
- --json: strict JSON through strict_json.dumps_strict with indent 2 and sorted keys. Envelope keys: spec_version, package_version, status, inputs, arguments, result. inputs has "first" and "second", each mapping every file that was read to its path and cli.file_sha256.

## 4. Docs. Use this wording exactly.

METHOD.md. Insert this section directly before "## 8. What the number does not say":

## Across-day comparison

Two sessions of one preparation, recorded on different days, are compared for one measure (`across_days.py`, run as `rrb-across-days`). Each session is a conforming spikes-path dataset and is checked on its own first. Units are matched by `unit_id`, so both sessions must come from one sort with one shared set of templates. Both sessions must carry the same `analysis.json`.

**Day value.** A unit's value on a day, in a condition, is the mean of its odd-half and even-half values from that day. The sensitivity axis uses the same unit value.

**Units.** A unit enters a condition when it is scored for the measure on both days in that condition, under the inclusion rule of the spikes path.

**Correlation.** Pearson `r` across units between the first-day and second-day values, with the Fisher interval of section 3 and `n_eff = n_units`. With one condition evaluated on both days, it is that condition's `r`. With two or more, it is the pooled, condition-centered `r`, as in the headline rule. No Spearman-Brown correction is applied, because each day's value already uses all of that day's trials.

**Null.** The second day's values are shuffled across units within each condition and `r` is recomputed `n_perm` times, as in section 5.2. `above_null` is true when `r` is above the 95th percentile of the shuffles.

**Fraction of within-session reliability.** `r` divided by the geometric mean of the two days' within-session reliabilities, each recomputed on the same units and conditions. By the attenuation relation in section 1 it estimates the correlation of the true values between the two days. It can exceed 1 by chance.

The correlation, its interval and the null are computed by `reliability_ceiling` and `permutation_null`, with the first day's value in the odd slot and the second day's value in the even slot. The across-day number runs through the same code as the within-session number.

The benchmark sets no bar on these numbers. A study that uses them sets its own bar in advance (docs/pass_rule.md).

Checked on simulated pairs of sessions (`tests/test_across_days.py`): with unchanged units the fraction is close to 1; with a known change in recovery time constants the fraction is close to the true correlation; with unit identities deliberately mismatched on the second day `r` is not above the null. No real second-day recording has been scored.

GLOSSARY.md. Append these entries at the end of "## 3. The computation":

**Across-day comparison.** For one preparation recorded on two days and sorted with one shared set of templates: the correlation across matched, scored units between each unit's first-day and second-day value of a measure, with its interval, a shuffled-unit null, and the correlation as a fraction of the within-session reliability. `across_days.across_day_comparison`; METHOD "Across-day comparison".

**Day value.** A unit's value of a measure on one day in one condition: the mean of its odd-half and even-half values. `across_days.across_day_frame`.

**Fraction of within-session reliability (`fraction_of_within_session`).** The across-day correlation divided by the geometric mean of the two days' within-session reliabilities on the same units. It estimates the correlation of true values between the two days. METHOD "Across-day comparison".

README.md. Insert this section after "## Run it on your recordings" and before "## If you only have per-trial numbers":

## Compare two days

When one preparation is recorded on two days and both recordings are sorted together, so each unit keeps its `unit_id`, compare the days:

```bash
rrb-across-days day1/ day2/
```

Each folder is a dataset written by `writer.write_dataset`, and both must use the same `analysis.json`. For `t_half_excess` the command reports the correlation across units between the two days, its 95% interval, a shuffled-unit null, and the correlation as a fraction of the within-session reliability. It has been checked on simulated sessions only. No real second-day recording has been scored.

CHANGELOG.md. Add under "## Unreleased":

- Across-day comparison (`across_days.py`, `rrb-across-days`): for two sessions of one preparation, the correlation across matched, scored units of a measure between days, its interval, a shuffled-unit null, and the correlation as a fraction of the within-session reliability, computed through `reliability_ceiling` and `permutation_null`. Checked on simulated session pairs with known answers. Not yet in the frozen layer; no real second-day recording has been scored.

## 5. Tests

tests/test_across_days.py. Build days with the repo's own generators and write them with writer.write_dataset into tmp_path. 30 units with ids u00 to u29, 40 trials, AnalysisParams(post_stim_window_s=2.0), inter-stimulus interval 5.0 s, preparation_id "prep0", and a different session_id and recording_id per day. The base population is spikes_path_checks.build_population("strong"). Build each simulated day once with module-scoped fixtures. Use n_perm=200 unless the test is about the null.

1. Same tissue. First day seed 0, second day seed 10000. Assert kind == "per_condition", r_across_days > 0.9, 0.9 <= fraction_of_within_session <= 1.1, above_null is True, n_units >= 25.
2. Known change. First-day time constants np.geomspace(0.05, 0.5, 30). Second-day time constants are the first-day ones times exp(0.6 * z), clipped to [0.03, 0.9], with z = np.random.default_rng(901).normal(size=30). Same baselines and 100 Hz peak as the strong population, built with synthetic.exponential_recovery. First day seed 1, second day seed 10001. true_r is np.corrcoef of the two time-constant vectors. Assert abs(fraction_of_within_session - true_r) <= 0.1 and above_null is True.
3. Wrong matching. As test 1, but on the second day unit i is written under the id of unit (i + 15) % 30. Assert r_across_days < 0 and above_null is False.
4. Two loads. Each day from synthetic.make_two_condition_spike_trains, conditions "control" and "slowed", the slowed time constants 1.5 times the control ones, seeds 3 and 10003. Assert kind == "pooled_centered", conditions == ["control", "slowed"], r_across_days > 0.9, both labels in per_condition, n_pairs >= n_units.
5. Same code path. Assert r_across_days equals reliability_ceiling(across_day_frame(...), measure, center)["r_half"], and the null p95_r equals permutation_null(frame, measure, center, n_perm, np.random.default_rng(seed))["p95_r"].
6. Guards. ValueError for each of: different analysis.json, different preparation_id, a shared session_id, a different protocol fingerprint for a shared condition, and no condition evaluated on both days.
7. A day that fails the contract. A second day with 5 trials: load_day raises ContractViolation, and the command exits 1 and prints a line starting "second day: ".
8. Invariance, in the manner of tests/test_invariance.py. Shuffled row order in the three tables of either day leaves the whole result unchanged. The same arbitrary unit relabeling on both days, the same condition relabeling on both days, and a trial_index offset leave everything unchanged except null, above_null and the labels themselves. Swapping the two days leaves r_across_days, its interval, n_units, n_pairs and fraction_of_within_session unchanged and swaps within_session first and second.
9. Command. Exit 0 with "r_across_days" in the plain output. The --json output parses with json.loads, contains no NaN, and holds the envelope keys. Exit 2 for a missing folder, for --n-perm 0, and for days that do not belong together.

tests/test_docs.py: add test_across_days_docs. It asserts that METHOD.md contains "## Across-day comparison", README.md contains "rrb-across-days day1/ day2/", GLOSSARY.md contains "`across_days.across_day_comparison`", CHANGELOG.md mentions rrb-across-days above the first released version heading, and pyproject.toml declares the rrb-across-days script.

## 6. Finish

Run ruff check ., ruff format --check ., and pytest. Report the pass and fail counts, the r_across_days and fraction_of_within_session from test 1, and every place where this prompt could not be followed as written.
