"""Tests for the commanded stimulation protocol schema."""

from __future__ import annotations

import pytest

from recovery_reliability_benchmark.protocol import (
    Burst,
    Protocol,
    Pulse,
    Train,
    default_pulse,
)


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


def test_standard_hfs() -> None:
    p = Protocol.standard_hfs()
    assert p.n_pulses == 100
    assert p.total_duration_s == pytest.approx(0.99022)
    assert p.total_charge_nc == pytest.approx(500.0)


def test_spaced_hfs() -> None:
    p = Protocol.spaced_hfs()
    assert p.n_pulses == 400
    assert p.total_duration_s == pytest.approx(4 * 0.99022 + 3 * 20.0)


def test_theta_burst() -> None:
    p = Protocol.theta_burst()
    assert p.n_pulses == 40
    assert p.train.train_duration_s == pytest.approx(1.83022)
    assert p.total_duration_s == pytest.approx(1.83022)

    p3 = Protocol.theta_burst(trains=3, inter_train_gap_s=10.0)
    assert p3.total_duration_s == pytest.approx(3 * 1.83022 + 20.0)


def test_factory_accepts_custom_pulse() -> None:
    custom = Pulse(
        phase_1_duration_us=100.0,
        inter_phase_gap_us=20.0,
        phase_2_duration_us=100.0,
        phase_1_amplitude_ua=20.0,
        phase_2_amplitude_ua=20.0,
    )
    p = Protocol.standard_hfs(pulse=custom)
    assert p.train.burst.pulse == custom


def test_pulse_overlap_raises() -> None:
    with pytest.raises(ValueError, match="overlap"):
        Burst(
            pulse=default_pulse(),
            pulses_per_burst=2,
            intra_burst_frequency_hz=5000.0,
        )


def test_burst_collision_raises() -> None:
    burst = Burst(
        pulse=default_pulse(),
        pulses_per_burst=4,
        intra_burst_frequency_hz=100.0,
    )
    with pytest.raises(ValueError, match="collide"):
        Train(
            burst=burst,
            bursts_per_train=2,
            inter_burst_interval_ms=30.0,
        )


def test_zero_inter_burst_with_multiple_bursts_raises() -> None:
    burst = Burst(
        pulse=default_pulse(),
        pulses_per_burst=4,
        intra_burst_frequency_hz=100.0,
    )
    with pytest.raises(ValueError):
        Train(
            burst=burst,
            bursts_per_train=2,
            inter_burst_interval_ms=0.0,
        )


def test_zero_gap_with_multiple_trains_raises() -> None:
    train = Protocol.standard_hfs().train
    with pytest.raises(ValueError):
        Protocol(
            name="x",
            train=train,
            trains_per_protocol=2,
            inter_train_gap_s=0.0,
        )


def test_single_burst_and_train_allow_zero_intervals() -> None:
    burst = Burst(
        pulse=default_pulse(),
        pulses_per_burst=4,
        intra_burst_frequency_hz=100.0,
    )
    train = Train(
        burst=burst,
        bursts_per_train=1,
        inter_burst_interval_ms=0.0,
    )
    assert train.inter_burst_frequency_hz == 0.0
    protocol = Protocol(
        name="single",
        train=train,
        trains_per_protocol=1,
        inter_train_gap_s=0.0,
    )
    assert protocol.trains_per_protocol == 1


def test_fingerprint() -> None:
    p1 = Protocol.standard_hfs()
    fp1 = p1.fingerprint()
    assert len(fp1) == 64
    assert all(c in "0123456789abcdef" for c in fp1)
    assert fp1 == Protocol.standard_hfs().fingerprint()

    p_other = p1.model_copy(update={"name": "other"})
    assert p_other.fingerprint() == fp1

    assert Protocol.spaced_hfs(inter_train_gap_s=30.0).fingerprint() != Protocol.spaced_hfs().fingerprint()


def test_total_charge_none_in_voltage_mode() -> None:
    vp = Pulse(
        mode="voltage",
        phase_1_duration_us=100.0,
        phase_2_duration_us=100.0,
        phase_1_amplitude_mv=500.0,
        phase_2_amplitude_mv=500.0,
    )
    assert Protocol.standard_hfs(pulse=vp).total_charge_nc is None


def test_protocol_json_round_trip() -> None:
    p = Protocol.theta_burst()
    assert Protocol.model_validate_json(p.model_dump_json()) == p


def test_protocol_frozen() -> None:
    p = Protocol.standard_hfs()
    with pytest.raises(ValueError):
        p.name = "modified"  # type: ignore[misc]
