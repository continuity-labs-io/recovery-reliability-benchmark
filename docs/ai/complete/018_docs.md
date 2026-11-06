Task: document the inclusion rule, the gaming analysis, and the measure-submission rule. No source changes; tests in test_docs.py only.

1. SPEC.md, new section after "Preparation and condition metadata": "## Inclusion and exclusion".
   - The rule, verbatim from contract.py's inclusion["rule"].
   - Contributors MUST NOT exclude units or trials after seeing results. Any exclusion made before submission (dead electrodes, stimulation-artifact saturation, a dropped trial) MUST be declared in preparation.json under `exclusions`, one entry per unit or trial with a reason; the report prints the counts. An exclusion that names a unit or trial still present in the tables is a SCHEMA violation.
   - Every report prints: units in the tables, units included by rule, units excluded by rule, rows missing from the full grid, and contributor-declared exclusions.
   - From v0.2.0, measures are computed by the benchmark from spikes.csv for every unit in units.csv, which removes per-trial row selection as a lever; unit-level selection remains covered by declaration.
   - Add `exclusions` to the preparation.json field list in the metadata section.

2. METHOD.md
   - §3: after Spearman-Brown and the interval, add "Variance components": the report shows between-unit variance, within-unit (trial) variance and the moments estimate next to the split-half ceiling, with the sentence from the variance_components docstring.
   - New section before "What the number does not say": "## How this benchmark can be gamed". One sentence of context: Arc's Virtual Cell Challenge used a scale-sensitive perturbation discrimination score and was climbed by inflating the variance of random predictions; the split-half correlation is scale-invariant, so that attack fails, and the table lists its neighbors. Then the table, columns Attack | Effect on the score | Countermeasure | Status:
       Variance inflation | None: Pearson r is invariant to scaling and shifting a measure | Scale-invariant score | Not applicable
       Unit selection (drop low-variance units, keep heterogeneous ones) | Raises between-unit variance, raises the ceiling | Pre-registered inclusion rule; inclusion counts and declared exclusions in every report; variance components printed next to the ceiling | Implemented (v0.1.0)
       Trial exclusion after seeing results | Removes noisy trials, raises the ceiling | No trial exclusion by rule; missing rows make a unit inactive; declared exclusions required; benchmark computes measures from spikes from v0.2.0 | Implemented (counts); tightened in v0.2.0
       Stable-but-meaningless measures (baseline firing rate) | Wins a reliability-only ranking while saying nothing about recovery | Sensitivity axis reported next to reliability, never combined; baseline firing rate as a reference row every submitted measure is compared with | Planned (v0.2.0)
       Submitter-chosen data or splits | Cherry-picked datasets or favorable halves | Submitted measures are scored on fixed public datasets with splits chosen by the benchmark | Documented (CONTRIBUTING.md); leaderboard planned
       Something we have not thought of | Unknown | Adversarial review requested: open an issue titled "gaming:" with the attack and, if possible, a synthetic dataset that demonstrates it | Open
   - Sensitivity axis definition, as a short paragraph under the table: with two or more conditions, the between-condition effect per unit divided by that unit's split-half noise, summarized as the fraction of units moving more than twice their own noise band and the median standardized effect; with one condition, the same quantity between the post-load window and the pre-load baseline. Reported beside reliability, never merged into one score. Status: planned for v0.2.0 with measures.py.

3. CONTRIBUTING.md, new section "## Submitting measures" (before "Starting"): a submitted measure is a named function from the raw inputs (spike times, stimulus times, declared parameters) to one value per unit per trial or per half; it is scored on the fixed public datasets with splits chosen by the benchmark, never by the submitter; it is reported on both axes, reliability and sensitivity, with its interval and inclusion counts, next to the baseline-firing-rate reference row; a measure that does not beat the reference on sensitivity is listed and marked. The leaderboard does not exist yet; this is the rule it will follow.

4. GLOSSARY.md: add entries for inclusion rule, declared exclusion, variance components, sensitivity axis, reference measure, submitted measure (update the existing one).

5. CHANGELOG.md Unreleased: "Inclusion rule made explicit and applied identically by rrb-check and rrb-evaluate; inclusion counts and contributor-declared exclusions reported." "Variance components reported next to each ceiling." "METHOD.md: 'How this benchmark can be gamed' section; CONTRIBUTING.md: measure-submission rule."

6. tests/test_docs.py: SPEC contains "## Inclusion and exclusion" and the rule sentence from contract.py (import it); METHOD contains "## How this benchmark can be gamed" and the six attack names; CONTRIBUTING contains "## Submitting measures"; GLOSSARY contains "Sensitivity axis".

Run the suite.
