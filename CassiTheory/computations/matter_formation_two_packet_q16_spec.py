"""Declarative schedule for the Q16 two-packet threshold probe.

This module contains preparation data only. The primary runner and the
independent verifier each assemble fields and operators separately.
"""
from __future__ import annotations

TOTAL_CHARGE = 16.0
NOMINAL_PACKET_CHARGE = TOTAL_CHARGE / 2.0
WIDTH = 4.0
CENTER = 12.0
WAVE_NUMBER = 1.0
OMEGA_OFFSET_SQUARED = 8.0
INITIAL_OVERLAP_MAX = 0.01
INITIAL_CORE_FRACTION_MAX = 0.10
CORE_RADIUS = 8.0

ARMS = ("single16", "pair16", "antiphase16", "uncoupled16")
COUPLED_CANDIDATES = ("pair16", "antiphase16")

ARM_SPECS = {
    "single16": {"kind": "single", "pair": False, "uncoupled": False},
    "pair16": {"kind": "pair", "pair": True, "uncoupled": False},
    "antiphase16": {"kind": "antiphase", "pair": True, "uncoupled": False},
    "uncoupled16": {"kind": "pair", "pair": True, "uncoupled": True},
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
