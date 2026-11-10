"""Analysis parameters and flag keys for spike-train recovery measures."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from .frozen import freeze_constant, frozen

DEFAULT_BIN_EDGES_S: tuple[float, ...] = tuple(float(x) for x in np.round(np.geomspace(0.003, 10.0, 41), 6))
FLAG_KEYS: tuple[str, ...] = (
    "t_half_peak_censored",
    "t_return_censored",
    "no_response",
    "overshoot_undefined",
    "baseline_zero",
    "no_excess",
)


@dataclass(frozen=True)
class AnalysisParams:
    """Parameters governing PSTH construction and recovery-kinetics measures.

    Time zero for every latency is ``onset + load_duration_s``; spikes during the load are not latencies.
    """

    post_stim_window_s: float
    pre_stim_window_s: float = 1.0
    load_duration_s: float = 0.0
    bin_edges_s: tuple[float, ...] = DEFAULT_BIN_EDGES_S
    return_x_baseline: float = 1.5
    half_peak_frac: float = 0.5
    residual_s: float = 1.0
    min_excess_z: float = 2.0

    def __post_init__(self) -> None:
        """Validate parameter ranges and coerce bin_edges_s to a tuple of floats."""
        edges = tuple(float(e) for e in self.bin_edges_s)
        object.__setattr__(self, "bin_edges_s", edges)
        if self.post_stim_window_s <= 0.0:
            raise ValueError(f"post_stim_window_s must be > 0, got {self.post_stim_window_s}.")
        if self.pre_stim_window_s <= 0.0:
            raise ValueError(f"pre_stim_window_s must be > 0, got {self.pre_stim_window_s}.")
        if self.load_duration_s < 0.0:
            raise ValueError(f"load_duration_s must be >= 0, got {self.load_duration_s}.")
        if (
            len(edges) < 2
            or edges[0] < 0.0
            or edges[0] >= self.post_stim_window_s
            or any(b <= a for a, b in zip(edges, edges[1:], strict=False))
        ):
            raise ValueError(f"bin_edges_s must be strictly increasing from >= 0, got {self.bin_edges_s}.")
        if not (0.0 < self.half_peak_frac < 1.0):
            raise ValueError(f"half_peak_frac must be in (0, 1), got {self.half_peak_frac}.")
        if self.return_x_baseline <= 1.0:
            raise ValueError(f"return_x_baseline must be > 1, got {self.return_x_baseline}.")
        if not (0.0 < self.residual_s <= self.post_stim_window_s):
            raise ValueError(f"residual_s must be in (0, post_stim_window_s], got {self.residual_s}.")
        if self.min_excess_z <= 0.0:
            raise ValueError(f"min_excess_z must be > 0, got {self.min_excess_z}.")

    @frozen("SPEC analysis parameters")
    def to_dict(self) -> dict[str, Any]:
        """Serialize parameters to a JSON-compatible dictionary."""
        return {**asdict(self), "bin_edges_s": list(self.bin_edges_s)}

    @classmethod
    def from_dict(cls, d: Mapping[str, Any]) -> AnalysisParams:
        """Construct an AnalysisParams instance from a dictionary."""
        kw = dict(d)
        if "bin_edges_s" in kw:
            kw["bin_edges_s"] = tuple(float(e) for e in kw["bin_edges_s"])
        return cls(**kw)

    @frozen("SPEC analysis parameters")
    def fingerprint(self) -> str:
        """Return the SHA-256 hex digest of ``json.dumps(to_dict(), sort_keys=True)``."""
        return hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True).encode("utf-8")).hexdigest()

    @frozen("SPEC analysis parameters")
    def effective_edges(self) -> np.ndarray:
        """Return stored edges below ``post_stim_window_s`` followed by the window end.

        If the gap from the last stored edge below ``post_stim_window_s`` to the window end
        is less than half the width of the preceding bin, that last edge is dropped before
        appending the window end: a sliver bin has the fewest spikes and the noisiest rate,
        and it sits where ``t_return``, ``residual``, and ``overshoot`` are read.
        """
        win = float(self.post_stim_window_s)
        inside = [e for e in self.bin_edges_s if e < win]
        if len(inside) >= 2 and (win - inside[-1]) < 0.5 * (inside[-1] - inside[-2]):
            inside.pop()
        return np.asarray([*inside, win], dtype=float)


DEFAULT_ANALYSIS_FINGERPRINT_2S = AnalysisParams(post_stim_window_s=2.0).fingerprint()
freeze_constant(__name__, "DEFAULT_ANALYSIS_FINGERPRINT_2S", "SPEC analysis parameters")
