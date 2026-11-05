Task: scope statement, atlas framing, optional metadata sidecars (validated only when provided), raw-data and fate table definitions. No change to MD requirements, thresholds or the Requirement enum.

1. SPEC.md
 a. New "## 0. Scope" directly after the header block: "Version 0.x of the benchmark covers neural preparations: dissociated cultures, organotypic slices, organoids and engineered neural tissue, on any recording modality. Other tissue types are a later major version." In §6 replace "Any particular tissue type, species or cell source" with "Any particular neural preparation type, species or cell source".
 b. §1, add a paragraph: "A conforming dataset contributes rows to a public atlas. A row is keyed by (protocol fingerprint, condition, preparation): the commanded load, the condition label with its pharmacology, and the specimen. Reliability is computed per row set, and rows accumulate across laboratories."
 c. New section "Preparation and condition metadata", after the reference tables section. Optional in SPEC v1.0 (benchmark v0.1.x); required from SPEC v1.1 (benchmark v0.2.0). Two JSON sidecars:
    preparation.json: preparation_id (must match units.csv), species, preparation_type (dissociated_culture | organotypic_slice | organoid | engineered_neural_tissue), age_days (number >= 0), age_basis (DIV | days_post_plating | days_post_differentiation), line_or_donor_id (anonymized string), instrument (string), raw_data_url (optional).
    conditions.json: {"<condition label>": {"protocol": <Protocol JSON from protocol.py, optional>, "compound": string|null, "dose": number|null, "dose_unit": string|null, "vehicle": string|null}}. Every condition in responses.csv must have an entry when the file is provided. The atlas row's protocol fingerprint is computed from "protocol".
 d. New section "Raw data": spikes.csv (unit_id, spike_time_ns; one row per spike; same clock as stim_time_ns) is requested for every contribution at v0.1.x and required from v0.2.0; raw traces by persistent link (Zenodo or DANDI DOI) when available, recorded as raw_data_url.
 e. New section "Fate" (optional): fate.csv with preparation_id, observed_at (ISO 8601 date), status (string), measure (string), value (number): later observations of the same preparation so atlas rows can carry outcome labels. Defined here; not checked by the validator in v0.1.x.
 f. Versioning section: add that SPEC versions (1.0) and benchmark package versions (0.1.0) are distinct; "required from v0.2.0" statements refer to the package and will appear as SPEC v1.1.

2. src/recovery_reliability_benchmark/metadata.py (pydantic v2, frozen):
   class Preparation: fields per 1c, Literal types for preparation_type and age_basis, age_days >= 0, raw_data_url: str | None = None.
   class Condition: protocol: Protocol | None = None; compound: str | None = None; dose: float | None = None; dose_unit: str | None = None; vehicle: str | None = None; property fingerprint -> protocol.fingerprint() if protocol else None.
   load_preparation(path) -> Preparation and load_conditions(path) -> dict[str, Condition]; wrap pydantic ValidationError and JSON errors into ContractViolation(Requirement.SCHEMA, "preparation.json: <first error>") / "conditions.json: <first error>".

3. contract.py
   validate(..., preparation: Preparation | None = None, conditions: dict[str, Condition] | None = None, spikes: pd.DataFrame | None = None). Defaults None; behavior unchanged when None. After the existing SCHEMA checks, under Requirement.SCHEMA:
   - preparation.preparation_id must equal the units preparation_id. Message: "preparation.json preparation_id 'X' does not match units ('Y')."
   - every condition in responses must be a key of conditions. Message: "condition 'B' in responses has no entry in conditions.json."
   - spikes: columns unit_id and spike_time_ns present; spike_time_ns non-null; every spikes.unit_id in units; messages in the existing style.
   Return dict adds "metadata": {"preparation": model_dump() or None, "conditions": {label: {"fingerprint", "compound", "dose", "dose_unit", "vehicle"}} or None, "n_spikes": int or None}.
   CLI: --preparation PATH, --conditions PATH, --spikes PATH, all optional; read spikes with dtype {"unit_id": str, "spike_time_ns": "Int64"}.
   evaluate.run() and rrb-evaluate accept and pass through the same three.

4. README.md "What is being benchmarked": add the atlas paragraph from 1b and one sentence that contributed data are released under CC0 (link CONTRIBUTING.md). Quickstart: a second command line showing --preparation and --conditions on the examples.

5. examples/: add preparation.json (species "Rattus norvegicus", preparation_type "dissociated_culture", age_days 21, age_basis "DIV", line_or_donor_id "example", instrument "synthetic") and conditions.json ({"A": {"protocol": Protocol.standard_hfs() JSON, "compound": null, "dose": null, "dose_unit": null, "vehicle": null}}). Extend make_examples.py to write both.

6. CHANGELOG.md Unreleased: "Scope: v0.x covers neural preparations only." "Atlas framing: a dataset contributes rows keyed by (protocol fingerprint, condition, preparation)." "Optional sidecars preparation.json, conditions.json and spikes.csv are validated when provided; fate.csv is defined."

7. Tests
   tests/test_metadata.py: Preparation round-trip; bad preparation_type rejected; Condition without protocol has fingerprint None and with protocol has a 64-hex fingerprint equal to the Protocol's; load_* on malformed JSON raise ContractViolation with requirement SCHEMA and the file name in the message.
   tests/test_contract.py: test_preparation_id_mismatch; test_condition_missing_from_sidecar; test_spikes_orphan_unit; test_sidecars_absent_unchanged (metadata values all None; every other key present as before); test_examples_with_sidecars (rrb-check main on examples with --preparation and --conditions, exit 0, and in --json mode metadata.conditions["A"]["fingerprint"] == Protocol.standard_hfs().fingerprint()).
   tests/test_docs.py: SPEC.md contains "## 0. Scope", "Preparation and condition metadata", "Raw data" and "Fate"; README contains "protocol fingerprint, condition, preparation"; CHANGELOG contains "Scope".

Run the full suite and make it pass.
