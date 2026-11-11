052 — Inspect the Braingeneers deposit against SPEC v1.1 (inspection only)

Task: decide whether any recording in the Braingeneers deposit (Zenodo 10.5281/zenodo.17684862,
CC BY 4.0, "Goal-Directed Learning in Cortical Organoids") can conform to SPEC v1.1 on the
spikes path. Inspection only: no adapter, and no change under src/, adapters/, scripts/ or docs/.

Safety: the deposit is third-party code plus a pickle, and loading a pickle can run code.
1. Download the files one at a time (Zenodo rate-limits parallel fetches) into
   data/braingeneers2025/raw/ (data/ is gitignored). Check each file's md5 against the
   record's API listing at https://zenodo.org/api/records/17684862.
2. Before loading anything, list every module and name the pickle imports, using the
   standard library's pickletools.genops (GLOBAL opcodes, and for STACK_GLOBAL the two
   string pushes before it). Report the list. If it names anything beyond builtins, numpy,
   pandas, collections, datetime or the deposit's own modules, stop and report.
3. Read these, do not run them: README.txt, README_data_structure.md, data_loader.py,
   data_access_example.py, recording_exp_def.py, causal_exp_def.py, cartpole_exp_def.py,
   phases.py. Load the pickle with python -I from a throwaway script kept outside raw/
   (output/braingeneers2025/, gitignored), passing paths as arguments. Add raw/ to
   sys.path only if step 2 showed the pickle needs the deposit's own modules.

Structure:
4. Print the pickle's structure two levels deep (keys, types, shapes), then one full
   example of each phase for one organoid.

Answers, per phase (spontaneous recording, stimulus-response characterization,
training, any other), each backed by the field name or source line that proves it:
5. a. Spike times: per sorted unit or per electrode; time unit; clock.
   b. Stimulus onset times: whether stored; whether on the same clock as the spikes;
      whether re-zeroed at the first stimulus; seconds of recording before the first one.
   c. What one stimulus is: electrode(s), amplitude, pulse shape, and train length (the
      load). Group stimuli into conditions of identical parameters.
   d. Per condition: number of repeats within one continuous recording.
   e. Over every stimulus in the recording, of any condition: the interval from each onset
      to the next onset. Min, median and max in seconds, and the fraction of intervals that
      are at least load + 3.0 s. Use every stimulus delivered; never drop stimuli to make
      the spacing pass, because a dropped stimulus still perturbs the tissue.
   f. Per condition: units with at least one spike in the 2.0 s post-stimulus windows of
      both the odd and the even trials.

6. Verdict table, one row per (organoid, phase recording): min-dataset-1 to min-dataset-7,
   pass or fail with the number found, plus a column for "same load within a condition".
   The rows that decide it: onsets at least load + 3.0 s apart (min-dataset-6 and -7),
   at least 1.0 s of recording before the first stimulus (min-dataset-7), at least 10
   repeats of one condition (min-dataset-2), at least 8 units (min-dataset-3).

Gate: stop and report steps 2, 4 and 6. If any row passes, name the best candidate (most
trials × units). Do not write an adapter in this prompt.
