"""Declarative schedule for the fixed-charge relative-phase probe."""
from __future__ import annotations

import math

TOTAL_CHARGE = 16.0
NOMINAL_PACKET_CHARGE = TOTAL_CHARGE / 2.0
CENTER = 12.0
WIDTH = 4.0
WAVE_NUMBER = 1.0
OMEGA_OFFSET_SQUARED = 8.0
INWARD_PHASE_SIGN = 1.0
OUTWARD_PHASE_SIGN = -1.0
RELATIVE_PHASES = (0.0, math.pi / 2.0, math.pi)
INITIAL_OVERLAP_MAX = 0.01
INITIAL_CORE_FRACTION_MAX = 0.10
CORE_RADIUS = 8.0
RETAINED_FRACTION = 0.25
BINDING_RATIO_MAX = 0.99

ARMS = (
    "single16_w4",
    "pair_phase0",
    "pair_phase90",
    "pair_phase180",
    "uncoupled_phase0",
    "outward_phase0",
)
COUPLED_CANDIDATES = ("pair_phase0", "pair_phase90", "pair_phase180")
RULE_CONTROL_ARM = "outward_phase0"
UNCOUPLED_CONTROL_ARM = "uncoupled_phase0"
ROBUST_COMPARISON_OBSERVABLES = (
    "energy",
    "charge",
    "core_fraction",
    "core_rms",
    "core_energy",
    "shell_energy_fraction",
)

ARM_SPECS = {
    "single16_w4": {"kind": "single", "pair": False, "uncoupled": False, "rule_control": False, "center": 0.0, "width": WIDTH, "wave_number": 0.0, "phase_sign": 0.0, "relative_phase": 0.0, "orientation": "single"},
    "pair_phase0": {"kind": "pair", "pair": True, "uncoupled": False, "rule_control": False, "center": CENTER, "width": WIDTH, "wave_number": WAVE_NUMBER, "phase_sign": INWARD_PHASE_SIGN, "relative_phase": 0.0, "orientation": "inward_phase0"},
    "pair_phase90": {"kind": "pair", "pair": True, "uncoupled": False, "rule_control": False, "center": CENTER, "width": WIDTH, "wave_number": WAVE_NUMBER, "phase_sign": INWARD_PHASE_SIGN, "relative_phase": math.pi / 2.0, "orientation": "inward_phase90"},
    "pair_phase180": {"kind": "pair", "pair": True, "uncoupled": False, "rule_control": False, "center": CENTER, "width": WIDTH, "wave_number": WAVE_NUMBER, "phase_sign": INWARD_PHASE_SIGN, "relative_phase": math.pi, "orientation": "inward_phase180"},
    "uncoupled_phase0": {"kind": "pair", "pair": True, "uncoupled": True, "rule_control": False, "center": CENTER, "width": WIDTH, "wave_number": WAVE_NUMBER, "phase_sign": INWARD_PHASE_SIGN, "relative_phase": 0.0, "orientation": "inward_uncoupled_phase0"},
    "outward_phase0": {"kind": "pair", "pair": True, "uncoupled": False, "rule_control": True, "center": CENTER, "width": WIDTH, "wave_number": WAVE_NUMBER, "phase_sign": OUTWARD_PHASE_SIGN, "relative_phase": 0.0, "orientation": "outward_rule_control"},
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
