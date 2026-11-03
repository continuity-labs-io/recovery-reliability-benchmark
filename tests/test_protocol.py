"""Tests for the commanded stimulation protocol schema."""

from __future__ import annotations

import pytest

from recovery_reliability_benchmark.protocol import Pulse


def test_symmetric_biphasic() -> None:
    p = Pulse(
        phase_1_duration_us=100,
        inter_phase_gap_us=20,
        phase_2_duration_us=100,
        phase_1_amplitude_ua=50,
        phase_2_amplitude_ua=50,
    )
    assert p.total_pulse_duration_us == 220
    assert p.charge_per_phase_nc == 5.0
    assert p.net_charge_imbalance_pc == 0.0
    assert p.amplitude_unit == "uA"
    assert p.phase_1_amplitude == 50
    assert p.phase_2_amplitude == 50


def test_asymmetric_balanced_biphasic() -> None:
    p = Pulse(
        phase_1_duration_us=100,
        phase_2_duration_us=200,
        phase_1_amplitude_ua=50,
        phase_2_amplitude_ua=25,
    )
    assert p.net_charge_imbalance_pc == pytest.approx(0.0)


def test_charge_imbalance_raises() -> None:
    with pytest.raises(ValueError, match="charge"):
        Pulse(
            phase_1_duration_us=100,
            inter_phase_gap_us=20,
            phase_2_duration_us=100,
            phase_1_amplitude_ua=50,
            phase_2_amplitude_ua=40,
        )


def test_monophasic() -> None:
    p = Pulse(
        waveform_shape="monophasic_square",
        phase_1_duration_us=100,
        phase_1_amplitude_ua=50,
    )
    assert p.total_pulse_duration_us == 100
    assert p.charge_per_phase_nc == 5.0
    assert p.net_charge_imbalance_pc == 5000.0
    assert p.phase_2_amplitude == 0.0


def test_monophasic_with_phase_2_raises() -> None:
    with pytest.raises(ValueError, match="monophasic"):
        Pulse(
            waveform_shape="monophasic_square",
            phase_1_duration_us=100,
            phase_2_duration_us=100,
            phase_1_amplitude_ua=50,
        )


def test_biphasic_without_phase_2_raises() -> None:
    with pytest.raises(ValueError, match="biphasic"):
        Pulse(
            waveform_shape="biphasic_square",
            phase_1_duration_us=100,
            phase_2_duration_us=0,
            phase_1_amplitude_ua=50,
        )


def test_voltage_mode() -> None:
    p = Pulse(
        mode="voltage",
        phase_1_duration_us=100,
        phase_2_duration_us=100,
        phase_1_amplitude_mv=500,
        phase_2_amplitude_mv=300,
    )
    assert p.charge_per_phase_nc is None
    assert p.net_charge_imbalance_pc is None
    assert p.amplitude_unit == "mV"
    assert p.phase_1_amplitude == 500
    assert p.phase_2_amplitude == 300


def test_mode_amplitude_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="mode"):
        Pulse(
            mode="current",
            phase_1_duration_us=100,
            phase_2_duration_us=100,
            phase_1_amplitude_mv=500,
            phase_2_amplitude_mv=500,
        )

    with pytest.raises(ValueError, match="mode"):
        Pulse(
            mode="current",
            phase_1_duration_us=100,
            phase_2_duration_us=100,
            phase_1_amplitude_ua=50,
            phase_2_amplitude_ua=50,
            phase_1_amplitude_mv=500,
        )

    with pytest.raises(ValueError, match="mode"):
        Pulse(
            mode="voltage",
            phase_1_duration_us=100,
            phase_2_duration_us=100,
            phase_1_amplitude_ua=50,
            phase_2_amplitude_ua=50,
        )


def test_negative_duration_raises() -> None:
    with pytest.raises(ValueError):
        Pulse(
            phase_1_duration_us=0,
            phase_2_duration_us=100,
            phase_1_amplitude_ua=50,
            phase_2_amplitude_ua=50,
        )


def test_frozen() -> None:
    p = Pulse(
        phase_1_duration_us=100,
        inter_phase_gap_us=20,
        phase_2_duration_us=100,
        phase_1_amplitude_ua=50,
        phase_2_amplitude_ua=50,
    )
    with pytest.raises(ValueError):
        p.phase_1_duration_us = 200  # type: ignore[misc]


def test_json_round_trip() -> None:
    p = Pulse(
        phase_1_duration_us=100,
        inter_phase_gap_us=20,
        phase_2_duration_us=100,
        phase_1_amplitude_ua=50,
        phase_2_amplitude_ua=50,
    )
    dumped = p.model_dump_json()
    assert "total_pulse_duration_us" not in dumped
    assert "charge_per_phase_nc" not in dumped
    assert Pulse.model_validate_json(dumped) == p
