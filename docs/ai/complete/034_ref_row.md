Task: report baseline firing rate as a reference row on the spikes path. No frozen changes.

1. examples/make_examples.py, spikes example only: units get different baselines so the reference row
   means something. baselines = np.geomspace(1.0, 20.0, 30); unit i uses baselines[(7 * i) % 30].
   Taus, peak 100 Hz, 20 trials, isi 5 s and seed 0 stay. Regenerate examples/spikes.csv.

2. inputs.from_spikes always computes baseline_hz, requested or not. EvaluationInputs gains
   reference_measure: str | None ("baseline_hz" on the spikes path, None on the tables path). The
   reference measure is scored like any other, but the rule "raise MD3 only when no requested measure
   is scored" counts requested measures only.

3. run: result["reference"] = {"measure": "baseline_hz", **evaluate_measure(inputs, "baseline_hz",
   n_perm, seed)} on the spikes path; None on the tables path.

4. inclusion["spikes_path"] keeps exactly two keys, "rule" and "per_measure". Remove the duplicated
   top-level measure keys and update the two readers (text_report and tests/test_run_spikes.py).

5. text_report: after the measure lines, one line
   "reference (baseline_hz): rho=<rho> ci=[<lo>, <hi>] n_units=<n>". Nothing on the tables path.

6. Tests. Bounds were measured on the regenerated example. Do not change seeds, trial counts or
   bounds; if a test fails, report the numbers.
   - test_reference_row_on_example: run on the example files with measures ["t_half_excess"]:
     reference.measure == "baseline_hz"; reference headline rho > 0.95 with n_units == 30
     (measured 0.991); t_half_excess headline rho > 0.9 with n_units == 29 (measured 0.954).
   - test_reference_same_when_requested: with measures ["t_half_excess", "baseline_hz"], the
     reference headline equals measures["baseline_hz"]["headline"].
   - test_reference_none_on_tables_path.
   - test_reference_does_not_rescue_md3: 6 responsive units plus 4 silent ones, measures ["t_return"]:
     still raises the MD3 ContractViolation.
   - In the existing example test, overshoot's n_units on the regenerated example is 22 (was 27);
     t_return stays 30.
   - tests/test_cli.py: the human output contains "reference (baseline_hz): rho=".

7. Docs. GLOSSARY "Reference measure": implemented on the spikes path, printed as the reference row.
   METHOD gaming table, stable-but-meaningless row, status: "Reference row implemented; sensitivity
   planned (v0.2.0)". README "From spikes": show the reference line in the sample output.
   CHANGELOG Unreleased: "spikes path: baseline firing rate reported as a reference row."

Run the full suite, ruff and scripts/freeze.py --check. Report: the reference rho and n_units, the
t_half_excess rho and n_units, and the suite count.
