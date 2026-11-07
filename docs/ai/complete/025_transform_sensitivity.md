Task: test whether the reliability ceiling is invariant to a monotone but non-affine
re-expression of a measure. No changes under src/ unless the finding requires it;
this prompt is a measurement, and any code change is a separate follow-up.

Background: METHOD.md's gaming table states "Variance inflation | None: Pearson r is
invariant to scaling and shifting a measure". That is true for affine transforms and
tests/test_invariance.py covers them. A log transform is monotone but not affine, so
the claim does not extend to it. Firing rates in the Sharf recordings span two orders
of magnitude, which makes Pearson r leverage-prone: a few high-rate units can carry
the correlation. If a submitter can raise their score by choosing a transform, that is
a missing row in the gaming table.

1. Extend scripts/sharf2022_g0.py with a --transforms flag (default off, so the
   existing G0 run is unchanged). When set, responses.csv gains, alongside
   firing_rate_hz:
     log_firing_rate_hz  = log10(firing_rate_hz + 0.2)
     sqrt_firing_rate_hz = sqrt(firing_rate_hz)
     rank_firing_rate_hz = within-epoch rank of the unit across units, average ties
   The 0.2 offset is one spike in a 5.0 s epoch: the smallest nonzero rate the data
   can express, so it is the natural floor rather than an arbitrary epsilon. Derive it
   from epoch_s rather than hardcoding it, and comment why.
   Rank is included because it is the extreme case: it discards magnitude entirely and
   keeps only the ordering, so it bounds how far a transform can move the number.

2. Run rrb-evaluate once per recording with all four measures together, so they share
   one split and one set of included units and the comparison is like for like.

3. Write output/sharf2022/transforms.md: one row per recording, columns organoid, stem,
   n_units, then rho and null_p95_rho for each of the four measures, then
   rho_max_minus_min across the four.

4. Report back, in the handoff: the table, the largest rho_max_minus_min seen, and
   whether the ordering of recordings by rho changes between the raw and the
   transformed measures.

Repo guidelines apply: under 300 lines per file, Google-style docstrings with Args and
Returns, intent comment before anything non-obvious.

GATE: all four measures evaluate without r_undefined or r_nonpositive on any
recording that passed the G0 run.

Interpretation, for the next agent, not for the script to decide:
- Spread under 0.02 across all four: the ceiling is robust to re-expression here, the
  gaming table needs no change, and 0.99 is the honest reference-row number.
- Spread above 0.05 on any recording: a submitter can move their score by choosing a
  transform. That is a new attack row for METHOD.md ("Measure re-expression"), and the
  countermeasure is a question for the next session, not this one. Do not edit
  METHOD.md in this prompt.
