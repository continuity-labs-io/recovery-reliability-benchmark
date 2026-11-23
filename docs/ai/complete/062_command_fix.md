Task: tighten how the across-day command handles unmatched and unreadable inputs, before its functions are frozen. Change only src/recovery_reliability_benchmark/across_days.py, src/recovery_reliability_benchmark/across_days_cli.py and tests/test_across_days.py. Do not bump the version. Do not edit frozen/manifest.json or frozen/snapshots/.

1. No unit in common. In _check_days_compatible, raise ValueError when no unit_id appears in both days' units tables. Message: "No unit_id appears on both days (first: <n> units, second: <m> units). Units are matched by unit_id, so both days must come from one sort." The command then exits 2.

2. Undefined within-session values. In across_day_comparison, set within_session "first" or "second" to None when reliability_ceiling reports r_undefined for that day's rows. Set "geometric_mean" to None when either is None. fraction_of_within_session is None in that case. In the plain output, print "undefined" for a None value.

3. Exit-2 messages name the day and the file. Every input error raised while inspecting or loading one day prints "error: first day: ..." or "error: second day: ...", and the text names the path at fault:
- a missing folder: "folder not found: <path>"
- a missing file: "missing file: <path>"
- an empty or unparseable CSV, or a non-integer trial_index, stim_time_ns or spike_time_ns: "<path>: <reason>"
Errors about the pair of days, such as different analysis.json, keep their current text.

4. Tests in tests/test_across_days.py:
- Two days with no unit_id in common: across_day_comparison raises ValueError, and the command exits 2.
- A second day where only two unit ids match the first day and the other units are renamed: r_undefined is True, the within_session values and fraction_of_within_session are None, and the plain output shows "undefined" on the within_session line.
- Second day with text in spike_time_ns: exit 2, and stderr contains "second day" and "spikes.csv".
- Second day without analysis.json: exit 2, and stderr contains "second day" and "analysis.json".
- First folder missing: exit 2, and stderr contains "first day".

Keep every existing assertion. Run ruff check ., ruff format --check ., and pytest. Tests in tests/test_frozen.py that were already failing before this task may stay failing. Report the result.
