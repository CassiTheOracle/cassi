"""Declarative schedule for the fixed-charge incoming-momentum probe.

This module contains preparation data only. The primary runner and the
independent verifier assemble fields and operators separately.
"""
from __future__ import annotations

TOTAL_CHARGE = 16.0
NOMINAL_PACKET_CHARGE = TOTAL_CHARGE / 2.0
WIDTH = 4.0
CENTER = 12.0
WAVE_NUMBERS = (0.5, 1.0, 1.5)
OMEGA_OFFSET_SQUARED = 8.0
INITIAL_OVERLAP_MAX = 0.01
INITIAL_CORE_FRACTION_MAX = 0.10
CORE_RADIUS = 8.0

ARMS = ("single16", "pair_k05", "pair_k10", "pair_k15", "antiphase_k10", "uncoupled_k10")
COUPLED_CANDIDATES = ("pair_k05", "pair_k10", "pair_k15", "antiphase_k10")

ARM_SPECS = {
    "single16": {"kind": "single", "pair": False, "uncoupled": False, "center": 0.0, "wave_number": 0.0},
    "pair_k05": {"kind": "pair", "pair": True, "uncoupled": False, "center": CENTER, "wave_number": 0.5},
    "pair_k10": {"kind": "pair", "pair": True, "uncoupled": False, "center": CENTER, "wave_number": 1.0},
    "pair_k15": {"kind": "pair", "pair": True, "uncoupled": False, "center": CENTER, "wave_number": 1.5},
    "antiphase_k10": {"kind": "antiphase", "pair": True, "uncoupled": False, "center": CENTER, "wave_number": 1.0},
    "uncoupled_k10": {"kind": "pair", "pair": True, "uncoupled": True, "center": CENTER, "wave_number": 1.0},
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
