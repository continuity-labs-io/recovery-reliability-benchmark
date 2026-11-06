Task: restructure validate() in src/recovery_reliability_benchmark/contract.py as an ordered registry of checks. Identical behavior: same order, same messages, same return dict. The existing tests are the gate and must pass unchanged except for import paths.

1. Introduce a context object:
   @dataclass
   class ValidationContext:
       units: pd.DataFrame            # working copy, ids cast to str
       responses: pd.DataFrame        # working copy
       measures: list[str]
       post_stim_window_s: float
       load_duration_s: float
       forbidden: frozenset[str]
       preparation: Preparation | None
       conditions: dict[str, Condition] | None
       spikes: pd.DataFrame | None
       # derived, filled by checks in order:
       conditions_info: dict[str, dict] = field(default_factory=dict)
       trials: pd.DataFrame | None = None     # distinct (trial_index, condition, stim_time_ns), sorted
       gaps_s: list[float] = field(default_factory=list)

2. A check is a function (ctx: ValidationContext) -> None that raises ContractViolation. Register them in order:
   CHECKS: tuple[tuple[Requirement, str, Callable[[ValidationContext], None]], ...] = (
     (Requirement.SCHEMA, "required_columns", ...),
     (Requirement.SCHEMA, "measures_allowed_and_numeric", ...),
     (Requirement.SCHEMA, "identifiers", ...),              # cast, unique unit_id, no orphans, null trial_index
     (Requirement.SCHEMA, "measures_vary_within_groups", ...),
     (Requirement.SCHEMA, "sidecars", ...),                 # preparation id, exclusions contradictions, conditions coverage, spikes
     (Requirement.MD1, "single_session", ...),
     (Requirement.MD2, "trials_per_condition", ...),        # fills conditions_info
     (Requirement.MD3, "active_units", ...),
     (Requirement.MD4, "stimulus_timeline", ...),           # fills trials
     (Requirement.MD5, "one_row_per_unit_trial", ...),
     (Requirement.MD6, "post_stimulus_window", ...),        # fills gaps_s
   )
   Each check function has a Google-style docstring: what it checks, which SPEC section, what it fills in on the context. The Requirement in the tuple is documentation and a test target; the function raises with the same Requirement.

3. validate() becomes: build the context (copies, casts), run CHECKS in order, then build the return dict from the context in a separate function build_report(ctx) -> dict (SHOULD levels, best condition, inclusion counts, metadata). validate() itself under 40 lines, with a Google-style docstring listing every argument and every key of the returned dict.

4. The preparation-id sidecar check compares against the set of preparation ids in units, not iloc[0], so a two-preparation table fails min-dataset-1 with the right message rather than the sidecar check with a confusing one. (Order stays: SCHEMA before MD1; the sidecar check passes when the declared id is in the set and MD1 then reports the real problem.)

5. Tests:
   - tests/test_contract.py::test_checks_registry: CHECKS has 11 entries; the Requirement sequence is [SCHEMA x5, MD1, MD2, MD3, MD4, MD5, MD6]; names are unique; every function has a docstring.
   - test_each_check_raises_its_own_requirement: for every (req, name, fn) with req != SCHEMA, the existing violating fixture for that requirement raises ContractViolation with exc.requirement is req (reuse the fixtures already in the file).
   - test_two_preparations_with_matching_sidecar_reports_md1: units with prep0 and prep1, preparation.json preparation_id "prep1" -> exc.requirement is Requirement.MD1.
   - Everything else unchanged.

Run the full suite and ruff; make both pass. Report validate()'s line count and the longest check function's line count.
