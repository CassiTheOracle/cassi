"""Declarative schedule for the axisymmetric four-to-six packet extension."""
from __future__ import annotations

import math

TOTAL_CHARGE = 16.0
R0 = 20.0
WIDTH = 4.0
WAVE_NUMBER = 1.0
INITIAL_OVERLAP_MAX = 0.01
INITIAL_CORE_FRACTION_MAX = 0.10
SHARE_TOL = 1.0e-12
RETAINED_FRACTION = 0.25
BINDING_RATIO_MAX = 0.99
GRID_SPECS = {
    "G0": (192, 0.5, 1.0 / 64.0),
    "G1": (192, 0.25, 1.0 / 64.0),
    "T1": (192, 0.5, 1.0 / 128.0),
}
SNAPSHOT_TIMES = (0.0, 32.0, 40.0, 48.0)
SAMPLE_DT = 0.5
T_FINAL = 48.0
LATE_START = 32.0
COMPARISON_OBSERVABLES = (
    "energy",
    "charge",
    "core_fraction",
    "core_rms",
    "core_energy",
    "shell_energy_fraction",
)
PACKET_COUNT_CANDIDATES = (4, 5, 6)


def semicircle_geometry(count: int) -> tuple[tuple[float, float], ...]:
    if count not in PACKET_COUNT_CANDIDATES:
        raise ValueError(f"unsupported count: {count}")
    return tuple(
        (
            R0 * abs(math.cos(-math.pi / 2.0 + j * math.pi / (count - 1))),
            R0 * math.sin(-math.pi / 2.0 + j * math.pi / (count - 1)),
        )
        for j in range(count)
    )


GEOMETRIES = {count: semicircle_geometry(count) for count in PACKET_COUNT_CANDIDATES}


def _arms() -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for count in PACKET_COUNT_CANDIDATES:
        result[f"n{count}_inward"] = {
            "count": count,
            "coupled": True,
            "candidate": True,
            "uncoupled": False,
            "phase_sign": 1.0,
            "orientation": "inward",
        }
        result[f"n{count}_uncoupled"] = {
            "count": count,
            "coupled": False,
            "candidate": False,
            "uncoupled": True,
            "phase_sign": 1.0,
            "orientation": "uncoupled_inward",
        }
    result["n6_outward"] = {
        "count": 6,
        "coupled": True,
        "candidate": False,
        "uncoupled": False,
        "phase_sign": -1.0,
        "orientation": "outward",
    }
    return result


ARM_SPECS = _arms()
ARMS = tuple(ARM_SPECS)
CANDIDATE_ARMS = tuple(f"n{count}_inward" for count in PACKET_COUNT_CANDIDATES)
CONTROL_ARMS = tuple(arm for arm in ARMS if arm not in CANDIDATE_ARMS)

# Bound immutable identities from the completed independently verified N=2/N=3 probe.
LOWER_PRIMARY_RECEIPT_SHA256 = "697c770f64e074690d2dd8cc496745884037438197986047c1887471e7e39295"
LOWER_VERIFICATION_RECEIPT_SHA256 = "b1786ec532b35fd45061063398ff5549f3edfc20c0db4ef80953a6558712d7ac"
