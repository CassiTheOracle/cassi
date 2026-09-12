"""Declarative schedule for the fixed-charge packet charge-partition probe."""
from __future__ import annotations

TOTAL_CHARGE = 16.0
CENTER = 12.0
WIDTH = 4.0
WAVE_NUMBER = 1.0
OMEGA_OFFSET_SQUARED = 8.0
INWARD_PHASE_SIGN = 1.0
OUTWARD_PHASE_SIGN = -1.0
ETA_PLUS_VALUES = (0.25, 0.5, 0.75)
SIGNED_SHARE_TOL = 1.0e-12
MIRROR_SWAP_TOL = 1.0e-10
INITIAL_OVERLAP_MAX = 0.01
INITIAL_CORE_FRACTION_MAX = 0.10
CORE_RADIUS = 8.0
RETAINED_FRACTION = 0.25
BINDING_RATIO_MAX = 0.99

ARMS = (
    "single16_w4",
    "pair_split25",
    "pair_split50",
    "pair_split75",
    "uncoupled_split50",
    "outward_split50",
)
COUPLED_CANDIDATES = ("pair_split25", "pair_split50", "pair_split75")
RULE_CONTROL_ARM = "outward_split50"
UNCOUPLED_CONTROL_ARM = "uncoupled_split50"
ROBUST_COMPARISON_OBSERVABLES = (
    "energy",
    "charge",
    "core_fraction",
    "core_rms",
    "core_energy",
    "shell_energy_fraction",
)

ARM_SPECS = {
    "single16_w4": {"kind": "single", "pair": False, "uncoupled": False, "rule_control": False, "center": 0.0, "width": WIDTH, "wave_number": 0.0, "phase_sign": 0.0, "relative_phase": 0.0, "eta_plus": None, "orientation": "single"},
    "pair_split25": {"kind": "pair", "pair": True, "uncoupled": False, "rule_control": False, "center": CENTER, "width": WIDTH, "wave_number": WAVE_NUMBER, "phase_sign": INWARD_PHASE_SIGN, "relative_phase": 0.0, "eta_plus": 0.25, "orientation": "inward_split25"},
    "pair_split50": {"kind": "pair", "pair": True, "uncoupled": False, "rule_control": False, "center": CENTER, "width": WIDTH, "wave_number": WAVE_NUMBER, "phase_sign": INWARD_PHASE_SIGN, "relative_phase": 0.0, "eta_plus": 0.5, "orientation": "inward_split50"},
    "pair_split75": {"kind": "pair", "pair": True, "uncoupled": False, "rule_control": False, "center": CENTER, "width": WIDTH, "wave_number": WAVE_NUMBER, "phase_sign": INWARD_PHASE_SIGN, "relative_phase": 0.0, "eta_plus": 0.75, "orientation": "inward_split75"},
    "uncoupled_split50": {"kind": "pair", "pair": True, "uncoupled": True, "rule_control": False, "center": CENTER, "width": WIDTH, "wave_number": WAVE_NUMBER, "phase_sign": INWARD_PHASE_SIGN, "relative_phase": 0.0, "eta_plus": 0.5, "orientation": "inward_uncoupled_split50"},
    "outward_split50": {"kind": "pair", "pair": True, "uncoupled": False, "rule_control": True, "center": CENTER, "width": WIDTH, "wave_number": WAVE_NUMBER, "phase_sign": OUTWARD_PHASE_SIGN, "relative_phase": 0.0, "eta_plus": 0.5, "orientation": "outward_rule_control_split50"},
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
