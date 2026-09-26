"""Declarative schedule for the fixed-charge packet-separation probe.

This module contains preparation data only. The primary runner and the
independent verifier assemble fields and operators separately.
"""
from __future__ import annotations

TOTAL_CHARGE = 16.0
NOMINAL_PACKET_CHARGE = TOTAL_CHARGE / 2.0
WIDTH = 4.0
WAVE_NUMBER = 1.0
OMEGA_OFFSET_SQUARED = 8.0
INITIAL_OVERLAP_MAX = 0.01
INITIAL_CORE_FRACTION_MAX = 0.10
CORE_RADIUS = 8.0

ARMS = ("single16", "pair_c10", "pair_c12", "pair_c14", "antiphase_c12", "uncoupled_c12")
COUPLED_CANDIDATES = ("pair_c10", "pair_c12", "pair_c14", "antiphase_c12")

ARM_SPECS = {
    "single16": {"kind": "single", "pair": False, "uncoupled": False, "center": 0.0},
    "pair_c10": {"kind": "pair", "pair": True, "uncoupled": False, "center": 10.0},
    "pair_c12": {"kind": "pair", "pair": True, "uncoupled": False, "center": 12.0},
    "pair_c14": {"kind": "pair", "pair": True, "uncoupled": False, "center": 14.0},
    "antiphase_c12": {"kind": "antiphase", "pair": True, "uncoupled": False, "center": 12.0},
    "uncoupled_c12": {"kind": "pair", "pair": True, "uncoupled": True, "center": 12.0},
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
