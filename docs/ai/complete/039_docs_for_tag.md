Task: documentation for v0.2.0. No source changes. Every number quoted comes from
docs/spikes_path_checks.json or from the examples, and a test pins it.

1. README.md, in this order:
   - What this is: two sentences and the anchor claim, as now.
   - Run the example: install with the report extra; the rrb-report line for examples/two_conditions;
     the two-axis table; three sentences on reading it (the reliability column; the sensitivity
     column; the reference row is baseline firing rate, the most repeatable number in the report,
     and it does not move when recovery slows).
   - Run it on your recordings: what a lab provides (spike times per unit, stimulus onset times, a
     condition label per stimulus); scripts/adapter_template.py; the protocol asks (2 s of recording
     after each stimulus, 1 s of quiet before, 20 trials per condition, 30 units recommended);
     rrb-check, then rrb-report. "Nothing leaves your machine."
   - If you only have per-trial numbers: the tables path, two lines.
   - What the report does not say: reliability is not validity; nothing here measures age or
     health; a conforming dataset can still score low.
   - Links to SPEC, METHOD, GLOSSARY, FROZEN, CONTRIBUTING.

2. SPEC.md:
   - "Measures computed by the benchmark": table of name | one-line definition | status. Lead:
     t_half_excess, excess_per_trial. Reference: baseline_hz. Secondary, read from single histogram
     bins and needing many spikes per bin: t_return, t_half_peak, peak_rate, t_peak, residual,
     overshoot. Also spikes_per_trial, baseline_variance_hz2. Give t_half_excess as three lines:
     N(t) = spikes over all n trials within t seconds of the load; E(t) = N(t) - b*n*t; the measure
     is the smallest t with E(t) >= E(W) / 2.
   - "What conformance guarantees on the spikes path": the trial and unit thresholds were set by
     simulation for per-trial measures; on the spikes path reliability also depends on how many
     spikes each unit contributes. From docs/spikes_path_checks.json at 20 trials: strong responses
     0.97 with 29 of 30 units scored; weak responses 0.68 with 21 of 30; sparse firing 0.73 with 20
     of 30; at 40 trials the last two reach 0.81. The interval, the shuffled null and the
     units-scored counts in the report are the guide; conformance does not promise a narrow interval.

3. METHOD.md:
   - "Split-half on pooled measures": on the spikes path each half's measure is computed once from
     that half's pooled trials, and Spearman-Brown is applied as on the tables path. Checked against
     the correlation between two independent sessions of the same units
     (docs/spikes_path_checks.json): within 0.01 for strong responses on every measure; for weak
     responses t_half_excess reads 0.05 low (0.68 against 0.73 at 20 trials), so the correction errs
     low for the lead measure; other measures stay within about 0.02.
   - "What the number does not say" gains two sentences: on the spikes path a low ceiling can come
     from too few spikes rather than from the tissue; sensitivity's per-unit noise has two degrees
     of freedom, which is why every value is printed beside its shuffled null.

4. CONTRIBUTING.md: "What to send" updated for the spikes path; "Protocol advice": 2 s after and 1 s
   before each stimulus, 20 or more trials, the same load on every trial, the protocol recorded in
   conditions.json.

5. GLOSSARY.md: check every entry added since v0.1.0 against the code; fix wording only.

6. tests/test_docs.py: README contains "rrb-report", "examples/two_conditions", "Nothing leaves your
   machine" and "adapter_template"; SPEC contains both new section titles; METHOD contains
   "Split-half on pooled measures"; a new test checks each number quoted in those SPEC and METHOD
   sections against docs/spikes_path_checks.json rounded to two decimals, as test_thresholds does.

CHANGELOG Unreleased: "Docs for the spikes path: measures table, what conformance guarantees,
split-half on pooled measures." Run the suite and ruff.
