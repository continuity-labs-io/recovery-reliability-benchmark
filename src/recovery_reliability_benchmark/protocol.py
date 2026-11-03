"""Commanded stimulation protocol schema for the Recovery Reliability Benchmark.

This schema describes the commanded stimulation protocol so two labs can assert
they delivered the same conditioning load. It does not describe the delivered
dose at the tissue, which also depends on electrode count, impedance and return
configuration.
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

CHARGE_BALANCE_REL_TOL = 1e-6


class Pulse(BaseModel):
    """Single stimulation pulse waveform parameters.

    In current mode, biphasic pulses are checked for charge balance between
    phase 1 and phase 2. Delivered charge in voltage mode depends on electrode
    impedance and is not known from the protocol, so no charge balance check is
    performed in voltage mode.
    """

    model_config = ConfigDict(frozen=True)

    waveform_shape: Literal["biphasic_square", "monophasic_square"] = "biphasic_square"
    polarity_order: Literal["cathodic_first", "anodic_first"] = "cathodic_first"  # for monophasic, the polarity of the single phase
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
        return (
            self.phase_1_amplitude_ua * self.phase_1_duration_us
            - self.phase_2_amplitude * self.phase_2_duration_us
        )

    @model_validator(mode="after")
    def _validate_pulse(self) -> Pulse:
        """Validate mode-unit pairing, waveform phase rules, and current-mode charge balance.

        Delivered charge in voltage mode depends on electrode impedance and is
        not known from the protocol, so charge balance is only checked in
        current mode.
        """
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
                raise ValueError(
                    "waveform_shape='monophasic_square' requires phase_2_duration_us == 0."
                )
            if self.inter_phase_gap_us != 0:
                raise ValueError(
                    "waveform_shape='monophasic_square' requires inter_phase_gap_us == 0."
                )
            if p2_amp not in (None, 0.0):
                raise ValueError(
                    f"waveform_shape='monophasic_square' requires {p2_amp_field} to be None or 0."
                )
        else:
            if self.phase_2_duration_us <= 0:
                raise ValueError(
                    "waveform_shape='biphasic_square' requires phase_2_duration_us > 0."
                )
            if p2_amp is None or p2_amp <= 0:
                raise ValueError(
                    f"waveform_shape='biphasic_square' requires {p2_amp_field} > 0."
                )

            if self.mode == "current":
                assert self.phase_1_amplitude_ua is not None and self.phase_2_amplitude_ua is not None
                q1_pc = self.phase_1_amplitude_ua * self.phase_1_duration_us
                q2_pc = self.phase_2_amplitude_ua * self.phase_2_duration_us
                if not math.isclose(q1_pc, q2_pc, rel_tol=CHARGE_BALANCE_REL_TOL):
                    raise ValueError(
                        "waveform_shape='biphasic_square' in current mode requires charge balance "
                        f"(phase_1 charge = {q1_pc} pC, phase_2 charge = {q2_pc} pC)."
                    )

        return self
