"""Declarative schedule for the axisymmetric one-to-three packet probe."""
from __future__ import annotations

import math

TOTAL_CHARGE = 16.0
R0 = 20.0
WIDTH = 4.0
WAVE_NUMBER = 1.0
OMEGA_OFFSET_SQUARED = 8.0
INWARD_PHASE_SIGN = 1.0
OUTWARD_PHASE_SIGN = -1.0
INITIAL_OVERLAP_MAX = 0.01
INITIAL_CORE_FRACTION_MAX = 0.10
SHARE_TOL = 1.0e-12
CORE_RADIUS = 8.0
RETAINED_FRACTION = 0.25
BINDING_RATIO_MAX = 0.99

ARMS = (
    "single_center",
    "pair_inward",
    "pair_uncoupled",
    "triple_inward",
    "triple_uncoupled",
    "triple_outward",
)
PACKET_COUNT_CANDIDATES = ("pair_inward", "triple_inward")
COUPLED_ARMS = ("pair_inward", "triple_inward", "triple_outward")
UNCOUPLED_ARMS = ("pair_uncoupled", "triple_uncoupled")

# Coordinates are (radial coordinate r, axial coordinate z) in the
# axisymmetric meridional plane.  A radial offset represents a toroidal ring
# in the full three-dimensional interpretation.
GEOMETRIES = {
    1: ((0.0, 0.0),),
    2: ((0.0, -R0), (0.0, R0)),
    3: (
        (R0, 0.0),
        (0.5 * R0, 0.5 * math.sqrt(3.0) * R0),
        (0.5 * R0, -0.5 * math.sqrt(3.0) * R0),
    ),
}

ARM_SPECS = {
    "single_center": {
        "count": 1,
        "coupled": True,
        "candidate": False,
        "uncoupled": False,
        "phase_sign": 0.0,
        "orientation": "stationary_single",
    },
    "pair_inward": {
        "count": 2,
        "coupled": True,
        "candidate": True,
        "uncoupled": False,
        "phase_sign": INWARD_PHASE_SIGN,
        "orientation": "pair_inward",
    },
    "pair_uncoupled": {
        "count": 2,
        "coupled": False,
        "candidate": False,
        "uncoupled": True,
        "phase_sign": INWARD_PHASE_SIGN,
        "orientation": "pair_uncoupled",
    },
    "triple_inward": {
        "count": 3,
        "coupled": True,
        "candidate": True,
        "uncoupled": False,
        "phase_sign": INWARD_PHASE_SIGN,
        "orientation": "triple_inward",
    },
    "triple_uncoupled": {
        "count": 3,
        "coupled": False,
        "candidate": False,
        "uncoupled": True,
        "phase_sign": INWARD_PHASE_SIGN,
        "orientation": "triple_uncoupled",
    },
    "triple_outward": {
        "count": 3,
        "coupled": True,
        "candidate": False,
        "uncoupled": False,
        "phase_sign": OUTWARD_PHASE_SIGN,
        "orientation": "triple_outward",
    },
}

GRID_SPECS = {
    "G0": (192, 0.5, 1.0 / 64.0),
    "G1": (192, 0.25, 1.0 / 64.0),
    "T1": (192, 0.5, 1.0 / 128.0),
}
SNAPSHOT_TIMES = (0.0, 32.0, 40.0, 48.0)
T_FINAL = 48.0
SAMPLE_DT = 0.5
LATE_START = 32.0
COMPARISON_OBSERVABLES = (
    "energy",
    "charge",
    "core_fraction",
    "core_rms",
    "core_energy",
    "shell_energy_fraction",
)
