"""Declarative schedule for the fixed-charge momentum-orientation probe.

This module contains preparation data only. The primary runner and the
independent verifier assemble fields and operators separately.
"""
from __future__ import annotations

TOTAL_CHARGE = 16.0
NOMINAL_PACKET_CHARGE = TOTAL_CHARGE / 2.0
WIDTH = 4.0
CENTER = 12.0
WAVE_NUMBER = 1.0
OMEGA_OFFSET_SQUARED = 8.0
INWARD_PHASE_SIGN = 1.0
OUTWARD_PHASE_SIGN = -1.0
INITIAL_OVERLAP_MAX = 0.01
INITIAL_CORE_FRACTION_MAX = 0.10
CORE_RADIUS = 8.0

ARMS = ("single16", "pair_inward", "pair_outward", "antiphase_inward", "uncoupled_inward")
COUPLED_CANDIDATES = ("pair_inward", "pair_outward", "antiphase_inward")
ROBUST_COMPARISON_OBSERVABLES = (
    "energy",
    "charge",
    "core_fraction",
    "core_rms",
    "core_energy",
    "shell_energy_fraction",
)

ARM_SPECS = {
    "single16": {"kind": "single", "pair": False, "uncoupled": False, "center": 0.0, "wave_number": 0.0, "phase_sign": 0.0, "orientation": "single"},
    "pair_inward": {"kind": "pair", "pair": True, "uncoupled": False, "center": CENTER, "wave_number": WAVE_NUMBER, "phase_sign": INWARD_PHASE_SIGN, "orientation": "inward"},
    "pair_outward": {"kind": "pair", "pair": True, "uncoupled": False, "center": CENTER, "wave_number": WAVE_NUMBER, "phase_sign": OUTWARD_PHASE_SIGN, "orientation": "outward"},
    "antiphase_inward": {"kind": "antiphase", "pair": True, "uncoupled": False, "center": CENTER, "wave_number": WAVE_NUMBER, "phase_sign": INWARD_PHASE_SIGN, "orientation": "inward_antiphase"},
    "uncoupled_inward": {"kind": "pair", "pair": True, "uncoupled": True, "center": CENTER, "wave_number": WAVE_NUMBER, "phase_sign": INWARD_PHASE_SIGN, "orientation": "inward_uncoupled"},
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
