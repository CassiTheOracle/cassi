"""Declarative preparation schedule for the Q=256 incoming-wave probe."""
from __future__ import annotations

TOTAL_CHARGE = 256.0
NOMINAL_PACKET_CHARGE = TOTAL_CHARGE / 2.0
WIDTH = 4.0
CENTER = 12.0
WAVE_NUMBERS = (0.25, 0.5, 1.0)
OMEGA_OFFSET_SQUARED = 8.0
INITIAL_OVERLAP_MAX = 0.01
INITIAL_CORE_FRACTION_MAX = 0.10
CORE_RADIUS = 8.0

ARMS = ("single256", "pair_k025", "pair_k05", "pair_k10", "antiphase_k05", "uncoupled_k05")
COUPLED_CANDIDATES = ("pair_k025", "pair_k05", "pair_k10", "antiphase_k05")
ROBUST_COMPARISON_OBSERVABLES = (
    "energy", "charge", "core_fraction", "core_rms", "core_energy", "shell_energy_fraction",
)

ARM_SPECS = {
    "single256": {"kind": "single", "pair": False, "uncoupled": False, "center": 0.0, "wave_number": 0.0},
    "pair_k025": {"kind": "pair", "pair": True, "uncoupled": False, "center": CENTER, "wave_number": 0.25},
    "pair_k05": {"kind": "pair", "pair": True, "uncoupled": False, "center": CENTER, "wave_number": 0.5},
    "pair_k10": {"kind": "pair", "pair": True, "uncoupled": False, "center": CENTER, "wave_number": 1.0},
    "antiphase_k05": {"kind": "antiphase", "pair": True, "uncoupled": False, "center": CENTER, "wave_number": 0.5},
    "uncoupled_k05": {"kind": "pair", "pair": True, "uncoupled": True, "center": CENTER, "wave_number": 0.5},
}

GRID_SPECS = {
    "S1": (192, 0.25, 1.0 / 128.0),
    "S2": (192, 0.125, 1.0 / 256.0),
    "T1": (192, 0.25, 1.0 / 256.0),
}
SNAPSHOT_TIMES = (0.0, 32.0, 40.0, 48.0)
T_FINAL = 48.0
SAMPLE_DT = 0.5
LATE_START = 32.0
