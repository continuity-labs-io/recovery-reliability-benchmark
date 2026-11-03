Task: add Burst, Train and Protocol to src/recovery_reliability_benchmark/protocol.py on top of the existing Pulse, with factories and a fingerprint, and extend tests/test_protocol.py. Same style as Pulse: frozen, plain @property for derived values, model_validator(mode="after") raising ValueError, no logging.

Add to the module docstring: "Timing convention: an interval is onset-to-onset; a gap is end-to-onset. intra_burst_frequency_hz and inter_burst_interval_ms are intervals; inter_train_gap_s is a gap."

class Burst(BaseModel), frozen
    pulse: Pulse
    pulses_per_burst: int   # >= 1
    intra_burst_frequency_hz: float   # > 0
  properties:
    intra_burst_interval_us -> 1e6 / intra_burst_frequency_hz
    active_burst_duration_ms -> (pulses_per_burst - 1) * (1000.0 / intra_burst_frequency_hz) + pulse.total_pulse_duration_us * 1e-3
    n_pulses -> pulses_per_burst
  validation: when pulses_per_burst > 1, pulse.total_pulse_duration_us must be < intra_burst_interval_us. Message contains "overlap" and both numbers.

class Train(BaseModel), frozen
    burst: Burst
    bursts_per_train: int   # >= 1
    inter_burst_interval_ms: float = 0.0   # >= 0; onset-to-onset
  properties:
    inter_burst_frequency_hz -> 1000.0 / inter_burst_interval_ms if bursts_per_train > 1 else 0.0
    train_duration_s -> ((bursts_per_train - 1) * inter_burst_interval_ms + burst.active_burst_duration_ms) * 1e-3
    n_pulses -> burst.n_pulses * bursts_per_train
  validation: when bursts_per_train > 1, inter_burst_interval_ms must be > 0 and burst.active_burst_duration_ms must be < inter_burst_interval_ms. Message contains "collide" and both numbers.

class Protocol(BaseModel), frozen
    name: str
    train: Train
    trains_per_protocol: int   # >= 1
    inter_train_gap_s: float = 0.0   # >= 0; end-to-onset
  properties:
    n_pulses -> train.n_pulses * trains_per_protocol
    total_duration_s -> trains_per_protocol * train.train_duration_s + (trains_per_protocol - 1) * inter_train_gap_s
    total_charge_nc -> n_pulses * train.burst.pulse.charge_per_phase_nc in current mode (sum of phase-1 charge over all pulses); None in voltage mode
  validation: when trains_per_protocol > 1, inter_train_gap_s must be > 0.
  methods:
    fingerprint() -> str: sha256 hex digest of self.model_dump_json(exclude={"name"}). Docstring: identifies the commanded load, not its label; two protocols with equal fields and different names share a fingerprint. Labs put this string in their dataset metadata.
  Docstring note: pass total_duration_s as load_duration_s to contract.validate().

Module function default_pulse() -> Pulse: biphasic, current mode, 100 us per phase, 20 us gap, 50 uA both phases.

Factory classmethods on Protocol, each with pulse: Pulse | None = None (None means default_pulse()):
    standard_hfs(pulse=None): name "standard_hfs"; 100 pulses per burst at 100 Hz; 1 burst per train; 1 train.
    spaced_hfs(trains=4, inter_train_gap_s=20.0, pulse=None): name "spaced_hfs"; same burst as standard_hfs; 1 burst per train; `trains` trains with the given gap.
    theta_burst(trains=1, inter_train_gap_s=0.0, pulse=None): name "theta_burst"; 4 pulses per burst at 100 Hz; 10 bursts per train at inter_burst_interval_ms=200.0; `trains` trains with the given gap.

tests/test_protocol.py additions (use pytest.approx for durations):
    - test_standard_hfs: n_pulses == 100, total_duration_s == approx(0.99022), total_charge_nc == approx(500.0).
    - test_spaced_hfs: n_pulses == 400, total_duration_s == approx(4 * 0.99022 + 3 * 20.0).
    - test_theta_burst: n_pulses == 40, train.train_duration_s == approx(1.83022), total_duration_s == approx(1.83022); theta_burst(trains=3, inter_train_gap_s=10.0).total_duration_s == approx(3 * 1.83022 + 20.0).
    - test_factory_accepts_custom_pulse: a 20 uA default-shaped pulse passed to standard_hfs appears as train.burst.pulse.
    - test_pulse_overlap_raises: Burst(pulse=default_pulse(), pulses_per_burst=2, intra_burst_frequency_hz=5000.0); match "overlap".
    - test_burst_collision_raises: Train(burst=<theta burst of 4 at 100 Hz>, bursts_per_train=2, inter_burst_interval_ms=30.0); match "collide".
    - test_zero_inter_burst_with_multiple_bursts_raises: same burst, bursts_per_train=2, inter_burst_interval_ms=0.0 raises.
    - test_zero_gap_with_multiple_trains_raises: Protocol(name="x", train=<standard hfs train>, trains_per_protocol=2, inter_train_gap_s=0.0) raises.
    - test_single_burst_and_train_allow_zero_intervals: Train(bursts_per_train=1, inter_burst_interval_ms=0.0) and Protocol(trains_per_protocol=1, inter_train_gap_s=0.0) construct.
    - test_fingerprint: 64 hex chars; standard_hfs().fingerprint() == standard_hfs().fingerprint(); a copy with name="other" (model_copy(update={"name": "other"})) has the same fingerprint; spaced_hfs(inter_train_gap_s=30.0) differs from spaced_hfs().
    - test_total_charge_none_in_voltage_mode: standard_hfs(pulse=<voltage-mode pulse 100/100 us, 500/500 mV>).total_charge_nc is None.
    - test_protocol_json_round_trip: Protocol.model_validate_json(p.model_dump_json()) == p for theta_burst().
    - test_protocol_frozen: assigning name on a constructed Protocol raises ValueError.

Run the full suite and make it pass.
