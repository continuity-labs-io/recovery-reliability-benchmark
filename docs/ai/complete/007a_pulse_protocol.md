Task: create src/recovery_reliability_benchmark/protocol.py with the Pulse model only, and tests/test_protocol.py. Burst, Train and Protocol come in the next step. Pydantic v2: BaseModel, Field, ConfigDict(frozen=True), model_validator(mode="after"). No logging. Docstrings and error messages in plain, calm language.

Module docstring: this schema describes the commanded stimulation protocol so two labs can assert they delivered the same conditioning load. It does not describe the delivered dose at the tissue, which also depends on electrode count, impedance and return configuration.

Module constant: CHARGE_BALANCE_REL_TOL = 1e-6

class Pulse(BaseModel), frozen.

Fields (all with Field constraints where stated):
    waveform_shape: Literal["biphasic_square", "monophasic_square"] = "biphasic_square"
    polarity_order: Literal["cathodic_first", "anodic_first"] = "cathodic_first"   # for monophasic, the polarity of the single phase
    mode: Literal["current", "voltage"] = "current"
    phase_1_duration_us: float   # > 0
    inter_phase_gap_us: float = 0.0   # >= 0
    phase_2_duration_us: float = 0.0   # >= 0
    phase_1_amplitude_ua: float | None = None   # > 0 when given
    phase_2_amplitude_ua: float | None = None   # >= 0 when given
    phase_1_amplitude_mv: float | None = None   # > 0 when given
    phase_2_amplitude_mv: float | None = None   # >= 0 when given

Properties (plain @property, not computed_field, so model_dump_json() contains input fields only):
    amplitude_unit -> "uA" if mode == "current" else "mV"
    phase_1_amplitude -> the amplitude in the active unit
    phase_2_amplitude -> the phase-2 amplitude in the active unit, or 0.0 if None
    total_pulse_duration_us -> phase_1_duration_us + inter_phase_gap_us + phase_2_duration_us
    charge_per_phase_nc -> phase_1_amplitude_ua * phase_1_duration_us * 1e-3 in current mode; None in voltage mode
    net_charge_imbalance_pc -> phase_1_amplitude_ua * phase_1_duration_us - phase_2_amplitude * phase_2_duration_us in current mode (uA·us = pC); None in voltage mode

Validation (one model_validator, raise ValueError with a message naming the field and the rule):
    a. mode == "current": phase_1_amplitude_ua must be given; phase_1_amplitude_mv and phase_2_amplitude_mv must be None.
       mode == "voltage": phase_1_amplitude_mv must be given; phase_1_amplitude_ua and phase_2_amplitude_ua must be None.
    b. waveform_shape == "monophasic_square": phase_2_duration_us must be 0, inter_phase_gap_us must be 0, and the phase-2 amplitude must be None or 0.
    c. waveform_shape == "biphasic_square": phase_2_duration_us must be > 0 and the phase-2 amplitude must be given and > 0.
    d. waveform_shape == "biphasic_square" and mode == "current": the pulse must be charge balanced: math.isclose(phase_1_amplitude_ua * phase_1_duration_us, phase_2_amplitude_ua * phase_2_duration_us, rel_tol=CHARGE_BALANCE_REL_TOL). Message includes both charges in pC and the word "charge". No charge check in voltage mode; say in the docstring that delivered charge in voltage mode depends on electrode impedance and is not known from the protocol.

tests/test_protocol.py (pydantic's ValidationError subclasses ValueError, so pytest.raises(ValueError, match=...) works):
    - test_symmetric_biphasic: Pulse(phase_1_duration_us=100, inter_phase_gap_us=20, phase_2_duration_us=100, phase_1_amplitude_ua=50, phase_2_amplitude_ua=50): total_pulse_duration_us == 220, charge_per_phase_nc == 5.0, net_charge_imbalance_pc == 0.0, amplitude_unit == "uA".
    - test_asymmetric_balanced_biphasic: 100 us at 50 uA then 200 us at 25 uA constructs; net_charge_imbalance_pc == pytest.approx(0.0).
    - test_charge_imbalance_raises: phase_2_amplitude_ua=40 with the symmetric durations; match "charge".
    - test_monophasic: Pulse(waveform_shape="monophasic_square", phase_1_duration_us=100, phase_1_amplitude_ua=50): total 100, charge_per_phase_nc == 5.0, net_charge_imbalance_pc == 5000.0.
    - test_monophasic_with_phase_2_raises: monophasic with phase_2_duration_us=100; match "monophasic".
    - test_biphasic_without_phase_2_raises: biphasic with phase_2_duration_us=0; match "biphasic".
    - test_voltage_mode: Pulse(mode="voltage", phase_1_duration_us=100, phase_2_duration_us=100, phase_1_amplitude_mv=500, phase_2_amplitude_mv=300) constructs (no charge check); charge_per_phase_nc is None, net_charge_imbalance_pc is None, amplitude_unit == "mV".
    - test_mode_amplitude_mismatch_raises: current mode with only _mv fields raises, match "mode"; current mode with both _ua and _mv given raises; voltage mode with only _ua fields raises.
    - test_negative_duration_raises: phase_1_duration_us=0 raises.
    - test_frozen: assigning to phase_1_duration_us on a constructed Pulse raises ValueError.
    - test_json_round_trip: Pulse.model_validate_json(p.model_dump_json()) == p for the symmetric biphasic pulse.

Run the full suite and make it pass.
