Task: define the requirement IDs as an enum in src/recovery_reliability_benchmark/contract.py and use it in ContractViolation. No behavior changes; all existing tests must still pass unchanged.

1. Add to contract.py, above ContractViolation:

    class Requirement(str, Enum):
        """Minimum Dataset (MD) requirements from SPEC.md.

        A dataset must satisfy every MD requirement's MUST threshold to be
        "conforming" and every SHOULD threshold to be "fully_conforming".
        validate() checks them in numeric order and raises ContractViolation
        on the first failure.
        """
        MD0 = "MD-0"  # Schema: required columns present, measures numeric and allowed, ids unique, no orphan responses.
        MD1 = "MD-1"  # Identity: exactly one preparation_id, session_id, and recording_id across the joined tables.
        MD2 = "MD-2"  # Trials: at least 10 trials per (unit_id, condition); SHOULD 20.
        MD3 = "MD-3"  # Units: at least 8 units active (all measures non-null) in every trial of each condition; SHOULD 15.
        MD4 = "MD-4"  # Timeline: stim_time_ns non-null and strictly increasing with trial_index; one stim_time_ns and one condition per trial_index across units.
        MD5 = "MD-5"  # Uniqueness: exactly one row per (unit_id, trial_index).
        MD6 = "MD-6"  # Window: post_stim_window_s >= 2.0 and, for every load except the last, the gap to the next load minus load_duration_s is at least post_stim_window_s.

    - Give each member a `description` property returning the comment text above (store the texts in a module-level dict keyed by member, or as a docstring-style mapping; either is fine).
    - The str mixin is required so that `exc.requirement == "MD-0"` keeps working.

2. ContractViolation
    - __init__(self, requirement: Requirement | str, message: str, found=None, required=None)
    - Normalize with Requirement(requirement) and store the enum member in self.requirement.
    - str(exc) and to_dict() emit the string value ("MD-0"), not the member name.

3. Replace every literal "MD-0" passed to ContractViolation inside validate() with Requirement.MD0.

4. tests/test_contract.py: add
    - test_requirement_enum: len(Requirement) == 7; Requirement("MD-3") is Requirement.MD3; Requirement.MD3 == "MD-3"; every member's description is a non-empty string.
    - test_contract_violation_accepts_string_or_enum: ContractViolation("MD-2", "m") and ContractViolation(Requirement.MD2, "m") both have requirement is Requirement.MD2 and to_dict()["requirement"] == "MD-2".

Run the suite and make it pass.
