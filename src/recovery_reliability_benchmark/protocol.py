"""Commanded stimulation protocol schema for the Recovery Reliability Benchmark.

This schema describes the commanded stimulation protocol so two labs can assert they delivered the
same conditioning load. It does not describe the delivered dose at the tissue, which also depends on
electrode count, impedance and return configuration.
Timing convention: an interval is onset-to-onset; a gap is end-to-onset. intra_burst_frequency_hz
and inter_burst_interval_ms are intervals; inter_train_gap_s is a gap.
"""

from __future__ import annotations

import hashlib
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

CHARGE_BALANCE_REL_TOL = 1e-6


class Pulse(BaseModel):
    """Single stimulation pulse waveform parameters.

    In current mode, biphasic pulses are checked for charge balance between phase 1 and phase 2.
    Delivered charge in voltage mode depends on electrode impedance and is not known from the
    protocol, so no charge balance check is performed in voltage mode.
    """

    model_config = ConfigDict(frozen=True)

    waveform_shape: Literal["biphasic_square", "monophasic_square"] = "biphasic_square"
    # for monophasic, the polarity of the single phase
    polarity_order: Literal["cathodic_first", "anodic_first"] = "cathodic_first"
    mode: Literal["current", "voltage"] = "current"
    phase_1_duration_us: float = Field(gt=0)
    inter_phase_gap_us: float = Field(default=0.0, ge=0)
    phase_2_duration_us: float = Field(default=0.0, ge=0)
    phase_1_amplitude_ua: float | None = Field(default=None, gt=0)
    phase_2_amplitude_ua: float | None = Field(default=None, ge=0)
    phase_1_amplitude_mv: float | None = Field(default=None, gt=0)
    phase_2_amplitude_mv: float | None = Field(default=None, ge=0)

    @property
    def amplitude_unit(self) -> str:
        """Return the active amplitude unit ('uA' or 'mV')."""
        return "uA" if self.mode == "current" else "mV"

    @property
    def phase_1_amplitude(self) -> float:
        """Return the phase-1 amplitude in the active unit."""
        amp = self.phase_1_amplitude_ua if self.mode == "current" else self.phase_1_amplitude_mv
        assert amp is not None
        return amp

    @property
    def phase_2_amplitude(self) -> float:
        """Return the phase-2 amplitude in the active unit, or 0.0 if None."""
        amp = self.phase_2_amplitude_ua if self.mode == "current" else self.phase_2_amplitude_mv
        return 0.0 if amp is None else amp

    @property
    def total_pulse_duration_us(self) -> float:
        """Return the total pulse duration in microseconds."""
        return self.phase_1_duration_us + self.inter_phase_gap_us + self.phase_2_duration_us

    @property
    def charge_per_phase_nc(self) -> float | None:
        """Return phase-1 charge in nanocoulombs in current mode, or None in voltage mode."""
        if self.mode != "current" or self.phase_1_amplitude_ua is None:
            return None
        return self.phase_1_amplitude_ua * self.phase_1_duration_us * 1e-3

    @property
    def net_charge_imbalance_pc(self) -> float | None:
        """Return net charge imbalance in picocoulombs in current mode, or None in voltage mode."""
        if self.mode != "current" or self.phase_1_amplitude_ua is None:
            return None
        q1 = self.phase_1_amplitude_ua * self.phase_1_duration_us
        return q1 - self.phase_2_amplitude * self.phase_2_duration_us

    @model_validator(mode="after")
    def _validate_pulse(self) -> Pulse:
        """Validate mode-unit pairing, waveform phase rules, and current-mode charge balance."""
        if self.mode == "current":
            if self.phase_1_amplitude_ua is None:
                raise ValueError("mode='current' requires phase_1_amplitude_ua to be given.")
            if self.phase_1_amplitude_mv is not None or self.phase_2_amplitude_mv is not None:
                raise ValueError(
                    "mode='current' requires phase_1_amplitude_mv and phase_2_amplitude_mv to be None."
                )
        else:
            if self.phase_1_amplitude_mv is None:
                raise ValueError("mode='voltage' requires phase_1_amplitude_mv to be given.")
            if self.phase_1_amplitude_ua is not None or self.phase_2_amplitude_ua is not None:
                raise ValueError(
                    "mode='voltage' requires phase_1_amplitude_ua and phase_2_amplitude_ua to be None."
                )
        p2_amp_field = "phase_2_amplitude_ua" if self.mode == "current" else "phase_2_amplitude_mv"
        p2_amp = self.phase_2_amplitude_ua if self.mode == "current" else self.phase_2_amplitude_mv
        if self.waveform_shape == "monophasic_square":
            if self.phase_2_duration_us != 0:
                raise ValueError("waveform_shape='monophasic_square' requires phase_2_duration_us == 0.")
            if self.inter_phase_gap_us != 0:
                raise ValueError("waveform_shape='monophasic_square' requires inter_phase_gap_us == 0.")
            if p2_amp not in (None, 0.0):
                raise ValueError(
                    f"waveform_shape='monophasic_square' requires {p2_amp_field} to be None or 0."
                )
        else:
            if self.phase_2_duration_us <= 0:
                raise ValueError("waveform_shape='biphasic_square' requires phase_2_duration_us > 0.")
            if p2_amp is None or p2_amp <= 0:
                raise ValueError(f"waveform_shape='biphasic_square' requires {p2_amp_field} > 0.")
            if self.mode == "current":
                assert self.phase_1_amplitude_ua is not None and self.phase_2_amplitude_ua is not None
                q1_pc = self.phase_1_amplitude_ua * self.phase_1_duration_us
                q2_pc = self.phase_2_amplitude_ua * self.phase_2_duration_us
                if not math.isclose(q1_pc, q2_pc, rel_tol=CHARGE_BALANCE_REL_TOL):
                    msg = (
                        "waveform_shape='biphasic_square' in current mode requires charge balance "
                        f"(phase_1 charge = {q1_pc} pC, phase_2 charge = {q2_pc} pC)."
                    )
                    raise ValueError(msg)
        return self


def default_pulse() -> Pulse:
    """Return the default biphasic current-mode pulse (100 us phases, 20 us gap, 50 uA).
    Returns:
        Default biphasic square current-mode Pulse instance.
    """
    return Pulse(
        waveform_shape="biphasic_square",
        mode="current",
        phase_1_duration_us=100.0,
        inter_phase_gap_us=20.0,
        phase_2_duration_us=100.0,
        phase_1_amplitude_ua=50.0,
        phase_2_amplitude_ua=50.0,
    )


class Burst(BaseModel):
    """A burst of identical stimulation pulses at a fixed intra-burst frequency."""

    model_config = ConfigDict(frozen=True)

    pulse: Pulse
    pulses_per_burst: int = Field(ge=1)
    intra_burst_frequency_hz: float = Field(gt=0)

    @property
    def intra_burst_interval_us(self) -> float:
        """Return the onset-to-onset interval between pulses in microseconds."""
        return 1e6 / self.intra_burst_frequency_hz

    @property
    def active_burst_duration_ms(self) -> float:
        """Return the duration from the first pulse onset to the last pulse end in milliseconds."""
        span_ms = (self.pulses_per_burst - 1) * (1000.0 / self.intra_burst_frequency_hz)
        return span_ms + self.pulse.total_pulse_duration_us * 1e-3

    @property
    def n_pulses(self) -> int:
        """Return the number of pulses in the burst."""
        return self.pulses_per_burst

    @model_validator(mode="after")
    def _validate_burst(self) -> Burst:
        """Validate that consecutive pulses in the burst do not overlap."""
        if self.pulses_per_burst > 1 and self.pulse.total_pulse_duration_us >= self.intra_burst_interval_us:
            raise ValueError(
                f"Pulses in burst overlap: total_pulse_duration_us ({self.pulse.total_pulse_duration_us}) "
                f"must be < intra_burst_interval_us ({self.intra_burst_interval_us})."
            )
        return self


class Train(BaseModel):
    """A train of identical bursts separated by a fixed onset-to-onset interval."""

    model_config = ConfigDict(frozen=True)

    burst: Burst
    bursts_per_train: int = Field(ge=1)
    inter_burst_interval_ms: float = Field(default=0.0, ge=0)

    @property
    def inter_burst_frequency_hz(self) -> float:
        """Return the burst repetition frequency in Hz, or 0.0 for a single-burst train."""
        return 1000.0 / self.inter_burst_interval_ms if self.bursts_per_train > 1 else 0.0

    @property
    def train_duration_s(self) -> float:
        """Return the duration from the first burst onset to the last burst end in seconds."""
        span_ms = (self.bursts_per_train - 1) * self.inter_burst_interval_ms
        return (span_ms + self.burst.active_burst_duration_ms) * 1e-3

    @property
    def n_pulses(self) -> int:
        """Return the total number of pulses in the train."""
        return self.burst.n_pulses * self.bursts_per_train

    @model_validator(mode="after")
    def _validate_train(self) -> Train:
        """Validate inter-burst interval when multiple bursts are present."""
        if self.bursts_per_train > 1:
            if self.inter_burst_interval_ms <= 0:
                msg = f"bursts_per_train > 1 requires inter_burst_interval_ms > 0 (got {self.inter_burst_interval_ms})."
                raise ValueError(msg)
            if self.burst.active_burst_duration_ms >= self.inter_burst_interval_ms:
                raise ValueError(
                    f"Bursts in train collide: active_burst_duration_ms ({self.burst.active_burst_duration_ms}) "
                    f"must be < inter_burst_interval_ms ({self.inter_burst_interval_ms})."
                )
        return self


class Protocol(BaseModel):
    """Complete commanded stimulation protocol consisting of one or more trains.

    Pass ``total_duration_s`` as ``load_duration_s`` to ``contract.validate()``.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    train: Train
    trains_per_protocol: int = Field(ge=1)
    inter_train_gap_s: float = Field(default=0.0, ge=0)

    @property
    def n_pulses(self) -> int:
        """Return the total number of pulses across the entire protocol."""
        return self.train.n_pulses * self.trains_per_protocol

    @property
    def total_duration_s(self) -> float:
        """Return the total duration from the first train onset to the last train end in seconds."""
        active_s = self.trains_per_protocol * self.train.train_duration_s
        return active_s + (self.trains_per_protocol - 1) * self.inter_train_gap_s

    @property
    def total_charge_nc(self) -> float | None:
        """Return the sum of phase-1 charge over all pulses in nC in current mode, or None in voltage mode."""
        charge_per_phase = self.train.burst.pulse.charge_per_phase_nc
        return None if charge_per_phase is None else self.n_pulses * charge_per_phase

    @model_validator(mode="after")
    def _validate_protocol(self) -> Protocol:
        """Validate inter-train gap when multiple trains are present."""
        if self.trains_per_protocol > 1 and self.inter_train_gap_s <= 0:
            raise ValueError(
                f"trains_per_protocol > 1 requires inter_train_gap_s > 0 (got {self.inter_train_gap_s})."
            )
        return self

    def fingerprint(self) -> str:
        """Return the SHA-256 hex digest of the protocol JSON excluding ``name``.

        Identifies the commanded load, not its label; two protocols with equal
        fields and different names share a fingerprint. Labs put this string in
        their dataset metadata.
        """
        payload = self.model_dump_json(exclude={"name"})
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @classmethod
    def standard_hfs(cls, pulse: Pulse | None = None) -> Protocol:
        """Return a standard 100 Hz high-frequency stimulation protocol (1 train of 100 pulses)."""
        p = default_pulse() if pulse is None else pulse
        burst = Burst(pulse=p, pulses_per_burst=100, intra_burst_frequency_hz=100.0)
        return cls(name="standard_hfs", train=Train(burst=burst, bursts_per_train=1), trains_per_protocol=1)

    @classmethod
    def spaced_hfs(
        cls, trains: int = 4, inter_train_gap_s: float = 20.0, pulse: Pulse | None = None
    ) -> Protocol:
        """Return a spaced HFS protocol with multiple 100-pulse 100 Hz trains separated by a gap."""
        p = default_pulse() if pulse is None else pulse
        burst = Burst(pulse=p, pulses_per_burst=100, intra_burst_frequency_hz=100.0)
        train = Train(burst=burst, bursts_per_train=1)
        return cls(
            name="spaced_hfs", train=train, trains_per_protocol=trains, inter_train_gap_s=inter_train_gap_s
        )

    @classmethod
    def theta_burst(
        cls, trains: int = 1, inter_train_gap_s: float = 0.0, pulse: Pulse | None = None
    ) -> Protocol:
        """Return a theta-burst stimulation protocol (10 bursts of 4 pulses at 100 Hz, 200 ms inter-burst interval)."""
        p = default_pulse() if pulse is None else pulse
        burst = Burst(pulse=p, pulses_per_burst=4, intra_burst_frequency_hz=100.0)
        train = Train(burst=burst, bursts_per_train=10, inter_burst_interval_ms=200.0)
        return cls(
            name="theta_burst", train=train, trains_per_protocol=trains, inter_train_gap_s=inter_train_gap_s
        )
