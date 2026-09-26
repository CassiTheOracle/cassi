#!/usr/bin/env python3
"""Independently verify the frozen QCD chiral matter-formation receipt.

This module deliberately contains its own lattice observables, regular-value
calculation, controls, and verdict reconstruction.  It never imports the
primary solver.  Evidence is consumed only after strict JSON, path, hash,
NPZ, and frozen-protocol checks have succeeded.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_REL = "computations/qcd-chiral-matter-formation-prereg.md"
PRIMARY_SOURCE_REL = "computations/qcd_chiral_matter_formation.py"
VERIFY_SCHEMA = "cassi.qcd-chiral-matter-formation.verification.v1"
PRIMARY_SCHEMA = "cassi.qcd-chiral-matter-formation.v1"
PROTOCOL_START = "<!-- qcd-chiral-formation-protocol:start -->"
PROTOCOL_END = "<!-- qcd-chiral-formation-protocol:end -->"

F_PI_MEV = 93.0
M_PI_MEV = 138.0
E_COUPLING = 4.25
KAPPA_SQ = 20.0
DELTA_OVER_F_PI = 0.3
HBARC_MEV_FM = 197.3269804
MU = 0.3491461100569260
LAMBDA = 1.1072664359861593
V_SQ = 0.8899063475546306
M_SIGMA_MEV = 604.1556090942134
L_FM = 5.0
N30 = 30
N40 = 40
DY30 = 0.3338367610271302
DY40 = 0.2503775707703476
EPSILON = 1.0e-6
RETAINED_S = (0.0, 0.05, 0.10, 0.25, 0.50, 1.0, 2.0, 4.0, 8.0)
SEEDS = (104729, 104759, 104761, 104773, 104779, 104789)
DIRECTIONAL_H = 1.0e-5
ATTEMPTED_DS = 2.0e-3
MAX_COMPONENT_CHANGE = 0.02
ENERGY_REL_TOL = 1.0e-9
MAX_HALVINGS = 24
DIRECTIONAL_RTOL = 3.0e-4
BOUNDARY_TOL = 1.0e-7
SCALAR_RTOL = 3.0e-5
SCALAR_ATOL = 3.0e-7
COEFF_TOL = 1.0e-10
DET_EXCLUDE_TOL = 1.0e-13
DET_AMBIGUITY_TOL = 1.0e-12
FACE_TOL = 1.0e-9
EDGE_LIMIT = math.pi / 2.0
MAX_STEPS = 100_000
RADIUS_MIN_FM = 0.20
RADIUS_MAX_FM = 1.20
TC_MEV = 156.5
TC_HALF_WIDTH_MEV = 1.5
GSTAR_MIN = 17.25
GSTAR_MAX = 61.75
M_PLANCK_GEV = 1.220890e19
GEV_INV_S = 6.582119569e-25
FM_C_S = 3.3356409519815204e-24
DIRECTIONAL_DY = E_COUPLING * F_PI_MEV * L_FM / HBARC_MEV_FM / 10.0

TETRAHEDRA_STR = (
    ("000", "100", "110", "111"),
    ("000", "110", "010", "111"),
    ("000", "010", "011", "111"),
    ("000", "011", "001", "111"),
    ("000", "001", "101", "111"),
    ("000", "101", "100", "111"),
)
CUBE_OFFSETS = np.asarray(
    [[int(bit) for bit in text] for text in ("000", "100", "110", "010", "011", "001", "101", "111")],
    dtype=np.int64,
)
TETS = np.asarray(
    [[next(i for i, value in enumerate(CUBE_OFFSETS) if np.array_equal(value, [int(bit) for bit in text])) for text in tet] for tet in TETRAHEDRA_STR],
    dtype=np.int64,
)
TARGETS = np.asarray(
    [
        values / np.linalg.norm(values)
        for m in range(1, 17)
        for values in (
            np.sin(float(m) * np.sqrt(np.asarray((2.0, 3.0, 5.0, 7.0))) + np.asarray((0.11, 0.23, 0.37, 0.53))),
        )
    ],
    dtype=np.float64,
)

EXPECTED_EVENT_IDS = ("prepared_positive", "prepared_negative") + tuple(f"random_{seed}" for seed in SEEDS)
GROUP_SPECS = {
    "N30_complete": {"N": N30, "dy": DY30, "include_u4": True},
    "N40_complete": {"N": N40, "dy": DY40, "include_u4": True},
    "N30_no_u4": {"N": N30, "dy": DY30, "include_u4": False},
}
REQUIRED_CONTROLS = ("vacuum", "directional_derivative", "checkerboard", "radial_profile", "cosmology")
REQUIRED_GROUPS = tuple(GROUP_SPECS)
VERDICT_KEYS = tuple(f"QCF{i}" for i in range(1, 7))
VERDICT_VALUES = {
    "QCF1": {"PASS", "FAIL", "INCONCLUSIVE"},
    "QCF2": {"SUPPORTS", "CONTRADICTS", "INCONCLUSIVE"},
    "QCF3": {"EMERGES", "DOES NOT EMERGE", "INCONCLUSIVE"},
    "QCF4": {"SUPPORTS", "CONTRADICTS", "INCONCLUSIVE"},
    "QCF5": {"SUPPORTS", "CONTRADICTS", "INCONCLUSIVE"},
    "QCF6": {"PASS", "FAIL", "INCONCLUSIVE"},
}


class EvidenceFailure(RuntimeError):
    """A malformed, missing, or otherwise unusable evidence package."""

    def __init__(self, kind: str, detail: str) -> None:
        super().__init__(f"{kind}: {detail}")
        self.kind = kind
        self.detail = detail


class MismatchBook:
    """Collect disagreements without allowing one bad scalar to hide others."""

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def add(self, path: str, expected: Any, actual: Any, reason: str = "disagreement") -> None:
        self.rows.append({"path": path, "expected": jsonable(expected), "actual": jsonable(actual), "reason": reason})

    def scalar(self, path: str, expected: Any, actual: Any) -> None:
        if isinstance(expected, bool) or isinstance(actual, bool) or not finite_number(expected) or not finite_number(actual):
            self.add(path, expected, actual, "nonfinite or nonnumeric scalar")
            return
        aa = float(expected)
        bb = float(actual)
        if not math.isclose(aa, bb, rel_tol=SCALAR_RTOL, abs_tol=SCALAR_ATOL):
            self.add(path, expected, actual, "scalar outside rtol=3e-5, atol=3e-7")

    def exact(self, path: str, expected: Any, actual: Any) -> None:
        if expected != actual:
            self.add(path, expected, actual, "exact value disagreement")

def compare_tree(path: str, expected: Any, actual: Any, mismatches: MismatchBook) -> None:
    """Compare a JSON-shaped record, using receipt scalar tolerances for floats."""
    if isinstance(expected, Mapping):
        if not isinstance(actual, Mapping):
            mismatches.add(path, expected, actual, "expected object")
            return
        expected_keys = set(expected)
        actual_keys = set(actual)
        if expected_keys != actual_keys:
            mismatches.add(f"{path}.__keys__", sorted(expected_keys), sorted(actual_keys), "object keys differ")
        for key in sorted(expected_keys & actual_keys):
            compare_tree(f"{path}.{key}", expected[key], actual[key], mismatches)
        return
    if isinstance(expected, (list, tuple)):
        if not isinstance(actual, list):
            mismatches.add(path, expected, actual, "expected array")
            return
        if len(expected) != len(actual):
            mismatches.add(f"{path}.__length__", len(expected), len(actual), "array lengths differ")
        for index, (expected_item, actual_item) in enumerate(zip(expected, actual)):
            compare_tree(f"{path}[{index}]", expected_item, actual_item, mismatches)
        return
    if isinstance(expected, float):
        mismatches.scalar(path, expected, actual)
        return
    mismatches.exact(path, expected, actual)


def jsonable(value: Any) -> Any:
    if isinstance(value, np.generic):
        return jsonable(value.item())
    if isinstance(value, np.ndarray):
        return [jsonable(item) for item in value.tolist()]
    if isinstance(value, Mapping):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return value


def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def strict_json(path: Path) -> tuple[dict[str, Any], bytes]:
    try:
        raw = path.read_bytes()
    except FileNotFoundError as exc:
        raise EvidenceFailure("MissingPrimaryEvidence", f"receipt does not exist: {path}") from exc
    except OSError as exc:
        raise EvidenceFailure("PrimaryReadFailure", f"cannot read receipt {path}: {exc}") from exc

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key {key!r}")
            result[key] = value
        return result

    def reject_constant(token: str) -> Any:
        raise ValueError(f"forbidden JSON constant {token}")

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=reject_constant)
    except Exception as exc:
        raise EvidenceFailure("MalformedPrimaryEvidence", f"strict JSON parse failed: {exc}") from exc
    if not isinstance(value, dict):
        raise EvidenceFailure("MalformedPrimaryEvidence", "primary receipt root is not an object")

    bad: list[str] = []

    def visit(node: Any, trail: str) -> None:
        if isinstance(node, float) and not math.isfinite(node):
            bad.append(trail)
        elif isinstance(node, dict):
            for key, child in node.items():
                visit(child, f"{trail}.{key}")
        elif isinstance(node, list):
            for index, child in enumerate(node):
                visit(child, f"{trail}[{index}]")

    visit(value, "$")
    if bad:
        raise EvidenceFailure("NonFiniteEvidence", f"nonfinite JSON values at {bad[:4]}")
    return value, raw


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError as exc:
        raise EvidenceFailure("MissingEvidence", f"cannot hash {path}: {exc}") from exc


def canonical_lf(raw: bytes) -> bytes:
    return raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def frozen_protocol_bytes(path: Path) -> bytes:
    try:
        raw = canonical_lf(path.read_bytes())
    except OSError as exc:
        raise EvidenceFailure("MissingProtocol", f"cannot read preregistration: {exc}") from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise EvidenceFailure("ProtocolStructureMismatch", f"preregistration is not UTF-8: {exc}") from exc
    if text.count(PROTOCOL_START) != 1 or text.count(PROTOCOL_END) != 1:
        raise EvidenceFailure("ProtocolStructureMismatch", "marker-delimited protocol markers are not unique")
    start = text.find(PROTOCOL_START)
    end = text.find(PROTOCOL_END)
    if start >= end:
        raise EvidenceFailure("ProtocolStructureMismatch", "protocol end marker does not follow start marker")
    frozen = text[start + len(PROTOCOL_START) : end]
    return frozen.encode("utf-8")



def strict_relative_path(base: Path, value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise EvidenceFailure("MalformedPrimaryEvidence", f"{label} path is missing or not a string")
    supplied = Path(value)
    if supplied.is_absolute() or supplied.drive:
        raise EvidenceFailure("PathEscape", f"{label} path is absolute: {value!r}")
    root = base.resolve()
    candidate = (root / supplied).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise EvidenceFailure("PathEscape", f"{label} path escapes receipt directory: {value!r}") from exc
    return candidate


def resolve_primary(value: str) -> tuple[Path, Path]:
    supplied = Path(value).expanduser().resolve()
    if supplied.is_dir():
        result = supplied / "results.json"
        base = supplied
    elif supplied.is_file():
        result = supplied
        base = supplied.parent
    else:
        raise EvidenceFailure("MissingPrimaryEvidence", f"primary input does not exist: {supplied}")
    if result.name != "results.json":
        raise EvidenceFailure("MalformedPrimaryEvidence", f"primary input must be results.json: {result}")
    if not result.is_file():
        raise EvidenceFailure("MissingPrimaryEvidence", f"results.json does not exist: {result}")
    return result, base


def descriptor_path(base: Path, descriptor: Any, label: str) -> tuple[Path, dict[str, Any]]:
    if not isinstance(descriptor, Mapping):
        raise EvidenceFailure("MalformedPrimaryEvidence", f"{label} artifact descriptor is not an object")
    path = strict_relative_path(base, descriptor.get("file"), label)
    if not path.is_file():
        raise EvidenceFailure("MissingEvidence", f"{label} artifact does not exist: {path}")
    declared_hash = descriptor.get("sha256")
    if not isinstance(declared_hash, str) or len(declared_hash) != 64 or any(ch not in "0123456789abcdef" for ch in declared_hash):
        raise EvidenceFailure("MalformedPrimaryEvidence", f"{label} artifact hash is malformed")
    actual_hash = sha256_file(path)
    if actual_hash != declared_hash:
        raise EvidenceFailure("ArtifactHashMismatch", f"{label} artifact hash mismatch")
    declared_bytes = descriptor.get("bytes")
    if not isinstance(declared_bytes, int) or isinstance(declared_bytes, bool) or declared_bytes < 0:
        raise EvidenceFailure("MalformedPrimaryEvidence", f"{label} artifact byte count is malformed")
    actual_bytes = path.stat().st_size
    if actual_bytes != declared_bytes:
        raise EvidenceFailure("ArtifactLengthMismatch", f"{label} artifact byte count mismatch")
    return path, {"file": descriptor["file"], "sha256": declared_hash, "bytes": declared_bytes}


def load_npz(path: Path, label: str) -> dict[str, np.ndarray]:
    try:
        with np.load(path, allow_pickle=False) as loaded:
            arrays = {name: np.asarray(loaded[name]).copy() for name in loaded.files}
    except Exception as exc:
        raise EvidenceFailure("MalformedNPZ", f"{label} cannot be loaded with allow_pickle=False: {exc}") from exc
    for name, array in arrays.items():
        if array.dtype.hasobject:
            raise EvidenceFailure("MalformedNPZ", f"{label}.{name} has object dtype")
        if array.dtype.kind in "fc" and not bool(np.all(np.isfinite(array))):
            raise EvidenceFailure("NonFiniteEvidence", f"{label}.{name} contains nonfinite values")
    return arrays


def require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise EvidenceFailure("MalformedPrimaryEvidence", f"{label} is not an object")
    return value


def require_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise EvidenceFailure("MalformedPrimaryEvidence", f"{label} is not boolean")
    return value


def require_float(value: Any, label: str) -> float:
    if not finite_number(value):
        raise EvidenceFailure("MalformedPrimaryEvidence", f"{label} is not a finite number")
    return float(value)


def require_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise EvidenceFailure("MalformedPrimaryEvidence", f"{label} is not an integer")
    return int(value)


def lookup(value: Any, aliases: Sequence[str]) -> Any:
    """Find a named value through direct or dotted keys, without fuzzy matches."""
    if not isinstance(value, Mapping):
        return None
    for alias in aliases:
        node: Any = value
        for part in alias.split("."):
            if not isinstance(node, Mapping) or part not in node:
                node = None
                break
            node = node[part]
        if node is not None:
            return node
    return None


def require_lookup(value: Mapping[str, Any], aliases: Sequence[str], label: str) -> Any:
    result = lookup(value, aliases)
    if result is None:
        raise EvidenceFailure("MalformedPrimaryEvidence", f"{label} is missing")
    return result


def scalar_array(arrays: Mapping[str, np.ndarray], name: str, dtype: np.dtype[Any], label: str) -> Any:
    if name not in arrays:
        raise EvidenceFailure("MalformedNPZ", f"{label} is missing NPZ array {name!r}")
    value = arrays[name]
    if value.shape != () or value.dtype != dtype:
        raise EvidenceFailure("MalformedNPZ", f"{label}.{name} must be scalar {dtype}, got {value.shape}/{value.dtype}")
    return value.item()


def float64_array(arrays: Mapping[str, np.ndarray], name: str, shape: tuple[int, ...] | None, label: str) -> np.ndarray:
    if name not in arrays:
        raise EvidenceFailure("MalformedNPZ", f"{label} is missing NPZ array {name!r}")
    value = arrays[name]
    if value.dtype != np.dtype(np.float64) or (shape is not None and value.shape != shape):
        raise EvidenceFailure("MalformedNPZ", f"{label}.{name} must be float64 {shape}, got {value.shape}/{value.dtype}")
    if not bool(np.all(np.isfinite(value))):
        raise EvidenceFailure("NonFiniteEvidence", f"{label}.{name} is nonfinite")
    return value


def check_close(value: Any, expected: float, label: str, rel: float = 1.0e-12, atol: float = 1.0e-12) -> None:
    actual = require_float(value, label)
    if not math.isclose(actual, expected, rel_tol=rel, abs_tol=atol):
        raise EvidenceFailure("FrozenConstantMismatch", f"{label}={actual!r}, expected {expected!r}")


def check_array_close(value: Any, expected: np.ndarray, label: str, rel: float = 1.0e-12, atol: float = 1.0e-12) -> None:
    try:
        actual = np.asarray(value, dtype=np.float64)
    except Exception as exc:
        raise EvidenceFailure("FrozenConstantMismatch", f"{label} is not numeric: {exc}") from exc
    if actual.shape != expected.shape or not bool(np.all(np.isfinite(actual))) or not bool(np.allclose(actual, expected, rtol=rel, atol=atol)):
        raise EvidenceFailure("FrozenConstantMismatch", f"{label} differs from the frozen value")


def validate_constants(constants: Mapping[str, Any]) -> dict[str, Any]:
    aliases: dict[str, tuple[str, ...]] = {
        "f_pi_mev": ("f_pi_mev", "f_pi", "fpi_mev"),
        "m_pi_mev": ("m_pi_mev", "m_pi", "mpi_mev"),
        "e": ("e", "skyrme_e"),
        "kappa_sq": ("kappa_sq", "kappa2", "kappa_squared"),
        "delta_over_f_pi": ("delta_over_f_pi", "delta_over_fpi", "hot_width_over_f_pi"),
        "hbar_c_mev_fm": ("hbar_c_mev_fm", "hbarc_mev_fm", "hbar_c"),
        "mu": ("mu",),
        "lambda": ("lambda", "lambda_"),
        "v_squared": ("v_squared", "v_sq", "v2"),
        "m_sigma_mev": ("m_sigma_mev", "m_sigma"),
        "L_fm": ("L_fm", "physical_side_fm", "side_length_fm"),
        "N30": ("N30", "primary_N", "N_primary"),
        "N40": ("N40", "refinement_N", "N_refinement"),
        "dy30": ("dy30", "dimensionless_spacing_30", "primary_dy"),
        "dy40": ("dy40", "dimensionless_spacing_40", "refinement_dy"),
        "epsilon": ("epsilon", "normalization_epsilon", "cutoff_epsilon"),
        "retained_s": ("retained_s", "retained_times"),
        "seeds": ("seeds", "random_seeds"),
        "targets": ("target_vectors", "targets"),
        "tetrahedra": ("tetrahedra", "freudenthal_tetrahedra", "tets"),
        "coeff_tol": ("coefficient_tolerance", "coefficient_tol", "coeff_tol"),
        "det_exclude_tol": ("determinant_exclusion_tolerance", "determinant_exclusion_tol", "det_exclude_tol"),
        "det_ambiguity_tol": ("determinant_ambiguity_tolerance", "determinant_ambiguity_tol", "det_ambiguity_tol"),
        "face_tol": ("face_tolerance", "face_tol"),
        "edge_limit": ("edge_angle_limit", "edge_angle_max", "edge_limit"),
        "boundary_tol": ("boundary_tolerance", "boundary_tol"),
        "directional_rtol": ("directional_relative_tolerance", "directional_rtol"),
        "scalar_rtol": ("scalar_rtol", "comparison_rtol"),
        "scalar_atol": ("scalar_atol", "comparison_atol"),
        "attempted_ds": ("attempted_ds", "initial_step", "maximum_attempted_step"),
        "max_component_change": ("max_component_change", "component_change_limit"),
        "energy_relative_tolerance": ("energy_relative_tolerance", "energy_rtol"),
        "max_halvings": ("max_halvings", "maximum_halvings"),
        "max_steps": ("max_accepted_steps", "max_steps"),
        "radial_initial_nodes": ("radial_initial_nodes", "radial_profile.initial_nodes", "profile_initial_nodes"),
        "radial_tol": ("radial_tol", "radial_profile.tol", "radial_profile.tolerance", "profile_tol"),
        "radial_max_nodes": ("radial_max_nodes", "radial_profile.max_nodes", "profile_max_nodes"),
        "radial_retained_samples": ("radial_retained_samples", "radial_profile.retained_samples", "profile_samples"),
        "radial_solve_r_min": ("radial_solve_r_min", "radial_profile.solve_r_min", "profile_r_min"),
        "radial_solve_r_max": ("radial_solve_r_max", "radial_profile.solve_r_max", "profile_r_max"),
        "radial_retained_r_min": ("radial_retained_r_min", "radial_profile.retained_r_min", "retained_profile_r_min"),
        "radial_retained_r_max": ("radial_retained_r_max", "radial_profile.retained_r_max", "retained_profile_r_max"),
        "radial_initial_guess_scale": ("radial_initial_guess_scale", "radial_profile.initial_guess_scale", "profile_initial_guess_scale"),
        "radius_bounds": ("radius_bounds_fm", "rms_radius_bounds_fm"),
        "Tc_mev": ("Tc_mev", "T_c_mev", "critical_temperature_mev"),
        "Tc_half_width_mev": ("Tc_half_width_mev", "Tc_uncertainty_mev", "critical_temperature_half_width_mev"),
        "gstar": ("g_star", "gstar", "g_star_bracket"),
        "M_planck_gev": ("M_Pl_gev", "M_planck_gev", "planck_mass_gev"),
        "gev_inv_s": ("gev_inv_s", "GeV_inverse_seconds"),
        "fm_c_s": ("fm_c_s", "fm_per_c_seconds", "fm_over_c_seconds"),
    }
    values: dict[str, Any] = {}
    for name, names in aliases.items():
        values[name] = require_lookup(constants, names, f"constants.{name}")

    check_close(values["f_pi_mev"], F_PI_MEV, "constants.f_pi_mev")
    check_close(values["m_pi_mev"], M_PI_MEV, "constants.m_pi_mev")
    check_close(values["e"], E_COUPLING, "constants.e")
    check_close(values["kappa_sq"], KAPPA_SQ, "constants.kappa_sq")
    check_close(values["delta_over_f_pi"], DELTA_OVER_F_PI, "constants.delta_over_f_pi")
    check_close(values["hbar_c_mev_fm"], HBARC_MEV_FM, "constants.hbar_c_mev_fm")
    check_close(values["mu"], MU, "constants.mu")
    check_close(values["lambda"], LAMBDA, "constants.lambda")
    check_close(values["v_squared"], V_SQ, "constants.v_squared")
    check_close(values["m_sigma_mev"], M_SIGMA_MEV, "constants.m_sigma_mev")
    check_close(values["L_fm"], L_FM, "constants.L_fm")
    if require_int(values["N30"], "constants.N30") != N30 or require_int(values["N40"], "constants.N40") != N40:
        raise EvidenceFailure("FrozenConstantMismatch", "grid sizes differ from frozen 30^3 and 40^3")
    check_close(values["dy30"], DY30, "constants.dy30")
    check_close(values["dy40"], DY40, "constants.dy40")
    check_close(values["epsilon"], EPSILON, "constants.epsilon")

    retained = values["retained_s"]
    if not isinstance(retained, list) or len(retained) != len(RETAINED_S) or any(not finite_number(item) or float(item) != frozen for item, frozen in zip(retained, RETAINED_S)):
        raise EvidenceFailure("FrozenConstantMismatch", "constants.retained_s differs from the nine exact retained times")
    seeds = values["seeds"]
    if not isinstance(seeds, list) or tuple(seeds) != SEEDS:
        raise EvidenceFailure("FrozenConstantMismatch", "constants.seeds differs from the six frozen PCG64 seeds")
    check_array_close(values["targets"], TARGETS, "constants.target_vectors")
    tetrahedra = values["tetrahedra"]
    if isinstance(tetrahedra, list) and all(isinstance(row, list) and all(isinstance(item, str) for item in row) for row in tetrahedra):
        if tuple(tuple(row) for row in tetrahedra) != TETRAHEDRA_STR:
            raise EvidenceFailure("FrozenConstantMismatch", "constants.tetrahedra differs from frozen strings")
    else:
        check_array_close(tetrahedra, CUBE_OFFSETS[TETS].astype(np.float64), "constants.tetrahedra")
    for name, expected in (("radial_initial_nodes", 1201), ("radial_max_nodes", MAX_STEPS), ("radial_retained_samples", 64001)):
        if require_int(values[name], f"constants.{name}") != expected:
            raise EvidenceFailure("FrozenConstantMismatch", f"constants.{name} differs from frozen radial reproducibility budget")
    check_close(values["radial_tol"], 1.0e-8, "constants.radial_tol")
    for name, expected in (("radial_solve_r_min", 1.0e-5), ("radial_solve_r_max", 64.0), ("radial_retained_r_min", 0.0), ("radial_retained_r_max", 64.0), ("radial_initial_guess_scale", 1.0 / math.sqrt(2.0))):
        check_close(values[name], expected, f"constants.{name}")

    for name, expected in (("coeff_tol", COEFF_TOL), ("det_exclude_tol", DET_EXCLUDE_TOL), ("det_ambiguity_tol", DET_AMBIGUITY_TOL), ("face_tol", FACE_TOL), ("edge_limit", EDGE_LIMIT), ("boundary_tol", BOUNDARY_TOL), ("directional_rtol", DIRECTIONAL_RTOL), ("scalar_rtol", SCALAR_RTOL), ("scalar_atol", SCALAR_ATOL)):
        check_close(values[name], expected, f"constants.{name}")
    for name, expected in (("attempted_ds", ATTEMPTED_DS), ("max_component_change", MAX_COMPONENT_CHANGE), ("energy_relative_tolerance", ENERGY_REL_TOL)):
        check_close(values[name], expected, f"constants.{name}")
    if require_int(values["max_halvings"], "constants.max_halvings") != MAX_HALVINGS:
        raise EvidenceFailure("FrozenConstantMismatch", "constants.max_halvings differs from 24")
    if require_int(values["max_steps"], "constants.max_steps") != MAX_STEPS:
        raise EvidenceFailure("FrozenConstantMismatch", "constants.max_steps differs from 100000")
    bounds = values["radius_bounds"]
    if not isinstance(bounds, list) or len(bounds) != 2 or any(not finite_number(item) for item in bounds) or not np.allclose(np.asarray(bounds, dtype=np.float64), (RADIUS_MIN_FM, RADIUS_MAX_FM), rtol=0.0, atol=1.0e-12):
        raise EvidenceFailure("FrozenConstantMismatch", "constants.radius_bounds differs from [0.20,1.20] fm")
    check_close(values["Tc_mev"], TC_MEV, "constants.Tc_mev")
    check_close(values["Tc_half_width_mev"], TC_HALF_WIDTH_MEV, "constants.Tc_half_width_mev")
    gstar = values["gstar"]
    if not isinstance(gstar, list) or len(gstar) != 2 or not np.allclose(np.asarray(gstar, dtype=np.float64), (GSTAR_MIN, GSTAR_MAX), rtol=0.0, atol=1.0e-12):
        raise EvidenceFailure("FrozenConstantMismatch", "constants.gstar differs from [17.25,61.75]")
    for name, expected in (("M_planck_gev", M_PLANCK_GEV), ("gev_inv_s", GEV_INV_S), ("fm_c_s", FM_C_S)):
        check_close(values[name], expected, f"constants.{name}")
    return values


def shell_mask(n: int) -> np.ndarray:
    mask = np.zeros((n, n, n), dtype=bool)
    mask[0, :, :] = True
    mask[-1, :, :] = True
    mask[:, 0, :] = True
    mask[:, -1, :] = True
    mask[:, :, 0] = True
    mask[:, :, -1] = True
    return mask


def impose_vacuum_shell(field: np.ndarray) -> np.ndarray:
    out = np.asarray(field, dtype=np.float64).copy()
    mask = shell_mask(out.shape[1])
    out[0, mask] = 1.0
    out[1:, mask] = 0.0
    return out


def forward_difference(field: np.ndarray, axis: int) -> np.ndarray:
    return np.roll(field, -1, axis=axis + 1) - field


def normalized_action_field(field: np.ndarray) -> np.ndarray:
    norm = np.sqrt(np.sum(field * field, axis=0))
    return field / np.maximum(norm, EPSILON)[None, ...]


def normalized_nonzero_field(field: np.ndarray) -> np.ndarray:
    norm = np.sqrt(np.sum(field * field, axis=0))
    return field / np.where(norm > 0.0, norm, EPSILON)[None, ...]


def energy_parts(field: np.ndarray, dy: float, include_u4: bool = True) -> dict[str, float]:
    phi = np.asarray(field, dtype=np.float64)
    differences = [forward_difference(phi, axis) / dy for axis in range(3)]
    e2_density = 0.5 * sum(np.sum(value * value, axis=0) for value in differences)
    if include_u4:
        unit = normalized_action_field(phi)
        unit_diff = [forward_difference(unit, axis) / dy for axis in range(3)]
        e4_density = np.zeros(phi.shape[1:], dtype=np.float64)
        for i in range(3):
            for j in range(i + 1, 3):
                first = np.sum(unit_diff[i] * unit_diff[i], axis=0)
                second = np.sum(unit_diff[j] * unit_diff[j], axis=0)
                cross = np.sum(unit_diff[i] * unit_diff[j], axis=0)
                e4_density += 0.5 * (first * second - cross * cross)
    else:
        e4_density = np.zeros(phi.shape[1:], dtype=np.float64)
    norm_sq = np.sum(phi * phi, axis=0)
    cvac = LAMBDA / 4.0 * (1.0 - V_SQ) ** 2 - MU * MU
    potential_density = LAMBDA / 4.0 * (norm_sq - V_SQ) ** 2 - MU * MU * phi[0] - cvac
    volume = dy**3
    e2 = float(volume * np.sum(e2_density))
    e4 = float(volume * np.sum(e4_density)) if include_u4 else 0.0
    potential = float(volume * np.sum(potential_density))
    return {"e2": e2, "e4": e4, "potential": potential, "total_energy": e2 + e4 + potential}


def edge_angle_max(field: np.ndarray) -> float:
    unit = normalized_nonzero_field(field)
    best = 0.0
    for axis in range(3):
        dot = np.sum(unit * np.roll(unit, -1, axis=axis + 1), axis=0)
        dot = np.clip(dot, -1.0, 1.0)
        value = float(np.max(np.arccos(dot)))
        if not math.isfinite(value):
            raise EvidenceFailure("NonFiniteEvidence", "edge angle is nonfinite")
        best = max(best, value)
    return best


def baryon_density(field: np.ndarray, dy: float) -> np.ndarray:
    unit = normalized_nonzero_field(field)
    central = [(np.roll(unit, -1, axis=axis + 1) - np.roll(unit, 1, axis=axis + 1)) / (2.0 * dy) for axis in range(3)]
    matrix = np.stack((unit, central[0], central[1], central[2]), axis=-1)
    matrix = np.transpose(matrix, (1, 2, 3, 0, 4))
    return np.linalg.det(matrix) / (2.0 * math.pi**2)


def baryon_radius(field: np.ndarray, dy: float) -> tuple[float, float, float | None]:
    density = baryon_density(field, dy)
    weights = np.abs(density)
    total = float(np.sum(weights))
    if not math.isfinite(total):
        raise EvidenceFailure("NonFiniteEvidence", "baryon-density weight is nonfinite")
    b = float(dy**3 * np.sum(density))
    bpos = float(dy**3 * np.sum(np.maximum(density, 0.0)))
    bneg = float(dy**3 * np.sum(np.maximum(-density, 0.0)))
    if total == 0.0:
        radius: float | None = None
    else:
        n = field.shape[1]
        indices = np.arange(n, dtype=np.float64)
        theta = 2.0 * math.pi * indices / n
        mesh = np.indices((n, n, n), dtype=np.float64)
        centre = np.empty(3, dtype=np.float64)
        for axis in range(3):
            sine = float(np.sum(weights * np.sin(theta).reshape((-1, 1, 1)) if axis == 0 else weights * np.sin(theta).reshape((1, -1, 1)) if axis == 1 else weights * np.sin(theta).reshape((1, 1, -1))))
            cosine = float(np.sum(weights * np.cos(theta).reshape((-1, 1, 1)) if axis == 0 else weights * np.cos(theta).reshape((1, -1, 1)) if axis == 1 else weights * np.cos(theta).reshape((1, 1, -1))))
            angle = math.atan2(sine, cosine)
            if angle < 0.0:
                angle += 2.0 * math.pi
            centre[axis] = n * angle / (2.0 * math.pi)
        delta = mesh - centre.reshape((3, 1, 1, 1))
        delta -= n * np.round(delta / n)
        distances_sq = (L_FM / n) ** 2 * np.sum(delta * delta, axis=0)
        radius = float(np.sqrt(np.sum(weights * distances_sq) / total))
    return b, bpos, bneg, radius


def metric_record(field: np.ndarray, dy: float, include_u4: bool) -> dict[str, Any]:
    phi = np.asarray(field, dtype=np.float64)
    if phi.shape[0] != 4 or phi.ndim != 4 or not bool(np.all(np.isfinite(phi))):
        raise EvidenceFailure("MalformedNPZ", "snapshot field must be finite float64 (4,N,N,N)")
    parts = energy_parts(phi, dy, include_u4)
    norms = np.sqrt(np.sum(phi * phi, axis=0))
    b, bpos, bneg, radius = baryon_radius(phi, dy)
    return {
        "total_energy": parts["total_energy"],
        "e2": parts["e2"],
        "e4": parts["e4"],
        "potential": parts["potential"],
        "mean_norm": float(np.mean(norms)),
        "min_norm": float(np.min(norms)),
        "cutoff_hits": int(np.count_nonzero(norms <= EPSILON)),
        "edge_angle_max": edge_angle_max(phi),
        "B": b,
        "Bpos": bpos,
        "Bneg": bneg,
        "rms_radius_fm": radius,
        "boundary_error": boundary_error(phi),
    }


def boundary_error(field: np.ndarray) -> float:
    n = field.shape[1]
    mask = shell_mask(n)
    values = np.asarray(field, dtype=np.float64)[:, mask]
    target = np.zeros_like(values)
    target[0, :] = 1.0
    return float(np.max(np.abs(values - target)))


def directional_derivative(field: np.ndarray, direction: np.ndarray, dy: float, include_u4: bool) -> float:
    phi = impose_vacuum_shell(field)
    d = np.asarray(direction, dtype=np.float64).copy()
    d[:, shell_mask(d.shape[1])] = 0.0
    differences = [forward_difference(phi, axis) / dy for axis in range(3)]
    direction_differences = [forward_difference(d, axis) / dy for axis in range(3)]
    derivative_density = sum(np.sum(a * b, axis=0) for a, b in zip(differences, direction_differences))
    if include_u4:
        norm = np.sqrt(np.sum(phi * phi, axis=0))
        dot = np.sum(phi * d, axis=0)
        denominator = np.maximum(norm, EPSILON)
        unit = phi / denominator[None, ...]
        unit_dot = d / denominator[None, ...] - phi * dot[None, ...] / denominator[None, ...] ** 3
        # The branch phi/max(|phi|,eps) has derivative d/eps below eps.
        small = norm <= EPSILON
        if np.any(small):
            unit_dot[:, small] = d[:, small] / EPSILON
        unit_diff = [forward_difference(unit, axis) / dy for axis in range(3)]
        unit_dot_diff = [forward_difference(unit_dot, axis) / dy for axis in range(3)]
        for i in range(3):
            for j in range(i + 1, 3):
                ai, aj = unit_diff[i], unit_diff[j]
                bi, bj = unit_dot_diff[i], unit_dot_diff[j]
                qi = np.sum(ai * ai, axis=0)
                qj = np.sum(aj * aj, axis=0)
                cij = np.sum(ai * aj, axis=0)
                derivative_density += np.sum(ai * bi, axis=0) * qj + qi * np.sum(aj * bj, axis=0) - cij * (np.sum(bi * aj, axis=0) + np.sum(ai * bj, axis=0))
    norm_sq = np.sum(phi * phi, axis=0)
    phi_dot = np.sum(phi * d, axis=0)
    derivative_density += LAMBDA * (norm_sq - V_SQ) * phi_dot - MU * MU * d[0]
    return float(dy**3 * np.sum(derivative_density))


def control_artifact(control: Mapping[str, Any], label: str) -> Mapping[str, Any]:
    descriptor = control.get("artifact")
    if descriptor is None:
        descriptor = control.get("npz")
    if descriptor is None and "file" in control:
        descriptor = control
    if not isinstance(descriptor, Mapping):
        raise EvidenceFailure("MalformedPrimaryEvidence", f"controls.{label} artifact descriptor is missing")
    return descriptor


def validate_vacuum_control(control: Mapping[str, Any], mismatches: MismatchBook) -> dict[str, Any]:
    residual_value = require_lookup(control, ("residual", "residual_max", "max_residual", "vacuum_residual"), "controls.vacuum.residual")
    if isinstance(residual_value, list):
        if not residual_value or any(not finite_number(item) for item in residual_value):
            raise EvidenceFailure("MalformedPrimaryEvidence", "controls.vacuum.residual list is malformed")
        residual = float(max(abs(float(item)) for item in residual_value))
    else:
        residual = require_float(residual_value, "controls.vacuum.residual")
    passed = residual < 1.0e-7
    recorded_pass = require_bool(require_lookup(control, ("pass", "passed", "passes"), "controls.vacuum.pass"), "controls.vacuum.pass")
    mismatches.scalar("controls.vacuum.residual", 0.0, residual)
    mismatches.exact("controls.vacuum.pass", passed, recorded_pass)
    return {"residual": residual, "pass": passed}


def validate_directional_control(control: Mapping[str, Any], base: Path, mismatches: MismatchBook) -> dict[str, Any]:
    artifact = control_artifact(control, "directional_derivative")
    path, descriptor = descriptor_path(base, artifact, "controls.directional_derivative")
    arrays = load_npz(path, "directional_control.npz")
    field = float64_array(arrays, "field", (4, 10, 10, 10), "directional_control.npz")
    direction = float64_array(arrays, "direction", (4, 10, 10, 10), "directional_control.npz")
    h = float(scalar_array(arrays, "h", np.dtype(np.float64), "directional_control.npz"))
    eta = float(scalar_array(arrays, "eta", np.dtype(np.float64), "directional_control.npz"))
    include_raw = scalar_array(arrays, "include_u4", np.dtype(np.int8), "directional_control.npz")
    if not math.isfinite(h) or not math.isfinite(eta):
        raise EvidenceFailure("NonFiniteEvidence", "directional control h/eta is nonfinite")
    if not math.isclose(h, DIRECTIONAL_DY, rel_tol=1.0e-12, abs_tol=1.0e-12):
        raise EvidenceFailure("FrozenConstantMismatch", f"directional control h={h!r} differs from frozen dimensionless spacing")
    # eta is the centered finite-difference displacement.
    if not math.isclose(eta, DIRECTIONAL_H, rel_tol=0.0, abs_tol=1.0e-14):
        raise EvidenceFailure("FrozenConstantMismatch", f"directional control eta={eta!r} differs from 1e-5")
    if int(include_raw) != 1:
        raise EvidenceFailure("FrozenConstantMismatch", "directional control must include U4")
    include_u4 = True
    phi = impose_vacuum_shell(field)
    d = direction.copy()
    d[:, shell_mask(10)] = 0.0
    direction_norm = float(np.linalg.norm(d.ravel()))
    automatic = directional_derivative(phi, d, h, include_u4)
    plus = impose_vacuum_shell(phi + eta * d)
    minus = impose_vacuum_shell(phi - eta * d)
    finite_difference = float((energy_parts(plus, h, include_u4)["total_energy"] - energy_parts(minus, h, include_u4)["total_energy"]) / (2.0 * eta))
    relative_error = abs(automatic - finite_difference) / max(1.0, abs(automatic), abs(finite_difference))
    direction_ok = math.isclose(direction_norm, 1.0, rel_tol=0.0, abs_tol=1.0e-10)
    passed = bool(direction_ok and relative_error < DIRECTIONAL_RTOL)
    for key, aliases, value in (
        ("automatic", ("automatic", "analytic", "analytic_directional", "gradient_directional", "derivative"), automatic),
        ("finite_difference", ("finite_difference", "finite", "fd"), finite_difference),
        ("relative_error", ("relative_error", "relative_err", "error"), relative_error),
        ("direction_norm", ("direction_norm", "norm"), direction_norm),
    ):
        recorded = lookup(control, aliases)
        if recorded is None:
            raise EvidenceFailure("MalformedPrimaryEvidence", f"controls.directional_derivative.{key} is missing")
        mismatches.scalar(f"controls.directional_derivative.{key}", value, require_float(recorded, f"controls.directional_derivative.{key}"))
    recorded_pass = require_bool(require_lookup(control, ("pass", "passed", "passes"), "controls.directional_derivative.pass"), "controls.directional_derivative.pass")
    mismatches.exact("controls.directional_derivative.pass", passed, recorded_pass)
    return {"artifact": descriptor, "automatic": automatic, "finite_difference": finite_difference, "relative_error": relative_error, "direction_norm": direction_norm, "eta": eta, "pass": passed}


def checkerboard_field(n: int = 16) -> np.ndarray:
    out = np.zeros((4, n, n, n), dtype=np.float64)
    out[0, ...] = 1.0
    ix, iy, iz = np.indices((n, n, n), dtype=np.int64)
    out[1, ...] = 0.1 * ((-1.0) ** (ix + iy + iz))
    return impose_vacuum_shell(out)


def validate_checkerboard_control(control: Mapping[str, Any], mismatches: MismatchBook) -> dict[str, Any]:
    spacing_value = lookup(control, ("spacing", "dimensionless_spacing", "dy"))
    spacing = 1.0 if spacing_value is None else require_float(spacing_value, "controls.checkerboard.spacing")
    if spacing <= 0.0:
        raise EvidenceFailure("MalformedPrimaryEvidence", "controls.checkerboard.spacing must be positive")
    parts = energy_parts(checkerboard_field(), spacing, True)
    energy = parts["total_energy"]
    e2 = parts["e2"]
    recorded_energy = require_lookup(control, ("energy", "total_energy", "total"), "controls.checkerboard.energy")
    recorded_e2 = lookup(control, ("e2", "two_derivative_energy"))
    mismatches.scalar("controls.checkerboard.energy", energy, require_float(recorded_energy, "controls.checkerboard.energy"))
    if recorded_e2 is not None:
        mismatches.scalar("controls.checkerboard.e2", e2, require_float(recorded_e2, "controls.checkerboard.e2"))
    passed = energy > 0.0
    recorded_pass = require_bool(require_lookup(control, ("pass", "passed", "passes"), "controls.checkerboard.pass"), "controls.checkerboard.pass")
    mismatches.exact("controls.checkerboard.pass", passed, recorded_pass)
    return {"energy": energy, "e2": e2, "spacing": spacing, "pass": passed}


def validate_radial_control(control: Mapping[str, Any], base: Path, mismatches: MismatchBook) -> dict[str, Any]:
    artifact = control_artifact(control, "radial_profile")
    path, descriptor = descriptor_path(base, artifact, "controls.radial_profile")
    arrays = load_npz(path, "radial_profile.npz")
    r = float64_array(arrays, "r", None, "radial_profile.npz")
    F = float64_array(arrays, "F", r.shape, "radial_profile.npz")
    F_prime = float64_array(arrays, "F_prime", r.shape, "radial_profile.npz")
    mu = float(scalar_array(arrays, "mu", np.dtype(np.float64), "radial_profile.npz"))
    if r.ndim != 1 or r.size != 64001 or not bool(np.all(np.diff(r) > 0.0)):
        raise EvidenceFailure("MalformedNPZ", "radial_profile.npz.r must be 64,001 strictly increasing float64 samples")
    if not math.isclose(float(r[0]), 0.0, rel_tol=0.0, abs_tol=1.0e-14) or not math.isclose(float(r[-1]), 64.0, rel_tol=0.0, abs_tol=1.0e-10) or not bool(np.allclose(np.diff(r), 64.0 / 64000.0, rtol=0.0, atol=1.0e-12)):
        raise EvidenceFailure("FrozenConstantMismatch", "retained radial profile domain is not the frozen uniform [0,64] grid")
    if not math.isclose(mu, MU, rel_tol=1.0e-12, abs_tol=1.0e-12):
        raise EvidenceFailure("FrozenConstantMismatch", "radial profile mu differs from frozen mu")
    origin_residual = float((math.pi - F[0]) + r[0] * F_prime[0])
    outer_residual = float(F[-1])
    passed = bool(abs(origin_residual) <= 1.0e-6 and abs(outer_residual) <= 1.0e-8)
    for key, aliases, value in (("origin_residual", ("origin_residual", "regular_origin_residual"), origin_residual), ("outer_residual", ("outer_residual", "boundary_residual"), outer_residual)):
        recorded = lookup(control, aliases)
        if recorded is not None:
            mismatches.scalar(f"controls.radial_profile.{key}", value, require_float(recorded, f"controls.radial_profile.{key}"))
    recorded_pass = require_bool(require_lookup(control, ("pass", "passed", "passes"), "controls.radial_profile.pass"), "controls.radial_profile.pass")
    mismatches.exact("controls.radial_profile.pass", passed, recorded_pass)
    return {"artifact": descriptor, "nodes": int(r.size), "mu": mu, "origin_residual": origin_residual, "outer_residual": outer_residual, "pass": passed}


def cosmology_values() -> dict[str, Any]:
    temperatures = (TC_MEV - TC_HALF_WIDTH_MEV, TC_MEV + TC_HALF_WIDTH_MEV)
    g_values = (GSTAR_MIN, GSTAR_MAX)
    corners: list[dict[str, float]] = []
    for temperature in temperatures:
        T_gev = temperature / 1000.0
        for g_star in g_values:
            hubble = 1.66 * math.sqrt(g_star) * T_gev**2 / M_PLANCK_GEV
            inverse_s = (1.0 / hubble) * GEV_INV_S
            corners.append({"T_MeV": temperature, "g_star": g_star, "H_inverse_s": inverse_s, "ratio_2fm_c": inverse_s / (2.0 * FM_C_S)})
    inverse_values = [row["H_inverse_s"] for row in corners]
    ratio_values = [row["ratio_2fm_c"] for row in corners]
    return {"corners": corners, "H_inverse_s_min": min(inverse_values), "H_inverse_s_max": max(inverse_values), "ratio_2fm_c_min": min(ratio_values), "ratio_2fm_c_max": max(ratio_values)}


def validate_cosmology_control(control: Mapping[str, Any], mismatches: MismatchBook) -> dict[str, Any]:
    calculated = cosmology_values()
    classification = require_lookup(control, ("classification", "transition_order", "order", "transition"), "controls.cosmology.classification")
    if not isinstance(classification, str):
        raise EvidenceFailure("MalformedPrimaryEvidence", "controls.cosmology.classification is not a string")
    normalized = classification.strip().lower()
    if normalized not in {"crossover", "first-order", "first_order", "first order"}:
        raise EvidenceFailure("MalformedPrimaryEvidence", f"unknown cosmology transition classification {classification!r}")
    if normalized != "crossover":
        raise EvidenceFailure(
            "FrozenConstantMismatch",
            "physical-mass QCD transition classification must be crossover",
        )
    for key, aliases in (("H_inverse_s_min", ("H_inverse_s_min", "hubble_inverse_min_s", "minimum_H_inverse_s")), ("H_inverse_s_max", ("H_inverse_s_max", "hubble_inverse_max_s", "maximum_H_inverse_s")), ("ratio_2fm_c_min", ("ratio_2fm_c_min", "minimum_ratio", "min_ratio_H_inverse_2fm_c")), ("ratio_2fm_c_max", ("ratio_2fm_c_max", "maximum_ratio", "max_ratio_H_inverse_2fm_c"))):
        value = require_lookup(control, aliases, f"controls.cosmology.{key}")
        mismatches.scalar(f"controls.cosmology.{key}", calculated[key], require_float(value, f"controls.cosmology.{key}"))
    recorded_pass = require_bool(require_lookup(control, ("pass", "passed", "passes"), "controls.cosmology.pass"), "controls.cosmology.pass")
    # The control itself passes when its finite bracket is present; QCF5 carries
    # the scientific crossover/first-order classification separately.
    mismatches.exact("controls.cosmology.pass", True, recorded_pass)
    calculated["classification"] = normalized
    calculated["pass"] = True
    return calculated


def validate_controls(primary: Mapping[str, Any], base: Path, mismatches: MismatchBook) -> dict[str, Any]:
    controls = require_mapping(primary.get("controls"), "controls")
    for name in REQUIRED_CONTROLS:
        if name not in controls:
            raise EvidenceFailure("MalformedPrimaryEvidence", f"controls.{name} is missing")
    return {
        "vacuum": validate_vacuum_control(require_mapping(controls["vacuum"], "controls.vacuum"), mismatches),
        "directional_derivative": validate_directional_control(require_mapping(controls["directional_derivative"], "controls.directional_derivative"), base, mismatches),
        "checkerboard": validate_checkerboard_control(require_mapping(controls["checkerboard"], "controls.checkerboard"), mismatches),
        "radial_profile": validate_radial_control(require_mapping(controls["radial_profile"], "controls.radial_profile"), base, mismatches),
        "cosmology": validate_cosmology_control(require_mapping(controls["cosmology"], "controls.cosmology"), mismatches),
    }


def metric_lookup(metric: Mapping[str, Any], key: str, label: str) -> Any:
    aliases = {
        "total_energy": ("total_energy", "total", "energy"),
        "e2": ("e2", "two_derivative_energy"),
        "e4": ("e4", "four_derivative_energy"),
        "potential": ("potential", "potential_energy"),
        "mean_norm": ("mean_norm", "norm_mean"),
        "min_norm": ("min_norm", "norm_min"),
        "cutoff_hits": ("cutoff_hits", "cutoff_count"),
        "edge_angle_max": ("edge_angle_max", "max_edge_angle", "maximum_edge_angle"),
        "B": ("B", "baryon"),
        "Bpos": ("Bpos", "B_pos", "baryon_positive"),
        "Bneg": ("Bneg", "B_neg", "baryon_negative"),
        "rms_radius_fm": ("rms_radius_fm", "baryon_rms_fm", "baryon_density_rms_radius_fm", "rms_radius"),
        "boundary_error": ("boundary_error", "fixed_boundary_error"),
    }
    value = lookup(metric, aliases[key])
    if value is None and key != "rms_radius_fm":
        raise EvidenceFailure("MalformedPrimaryEvidence", f"{label}.{key} is missing")
    if key == "rms_radius_fm" and value is None and any(alias in metric for alias in aliases[key]):
        return None
    if key == "rms_radius_fm" and value is None:
        raise EvidenceFailure("MalformedPrimaryEvidence", f"{label}.{key} is missing")
    return value


def compare_metric(primary_metric: Mapping[str, Any], actual: Mapping[str, Any], label: str, mismatches: MismatchBook) -> None:
    for key in ("total_energy", "e2", "e4", "potential", "mean_norm", "min_norm", "edge_angle_max", "B", "Bpos", "Bneg", "boundary_error"):
        expected = require_float(metric_lookup(primary_metric, key, label), f"{label}.{key}")
        mismatches.scalar(f"{label}.{key}", actual[key], expected)
    cutoff = metric_lookup(primary_metric, "cutoff_hits", label)
    if isinstance(cutoff, bool) or not isinstance(cutoff, int):
        raise EvidenceFailure("MalformedPrimaryEvidence", f"{label}.cutoff_hits is not an integer")
    mismatches.exact(f"{label}.cutoff_hits", actual["cutoff_hits"], int(cutoff))
    radius = metric_lookup(primary_metric, "rms_radius_fm", label)
    if radius is None:
        if actual["rms_radius_fm"] is not None:
            mismatches.add(f"{label}.rms_radius_fm", actual["rms_radius_fm"], None, "null radius disagreement")
    else:
        mismatches.scalar(f"{label}.rms_radius_fm", actual["rms_radius_fm"], require_float(radius, f"{label}.rms_radius_fm"))


def regular_value(field: np.ndarray) -> dict[str, Any]:
    n = field.shape[1]
    spatial_signs = np.asarray([int(np.sign(np.linalg.det(CUBE_OFFSETS[tet[1:]].astype(np.float64) - CUBE_OFFSETS[tet[0]].astype(np.float64)))) for tet in TETS], dtype=np.int8)
    positive = np.zeros(16, dtype=np.int64)
    negative = np.zeros(16, dtype=np.int64)
    ambiguity = np.zeros(16, dtype=np.int64)
    slab = 4
    for low in range(0, n, slab):
        high = min(n, low + slab)
        ii, jj, kk = np.meshgrid(np.arange(low, high), np.arange(n), np.arange(n), indexing="ij")
        base = np.stack((ii, jj, kk), axis=-1).reshape(-1, 3)
        inds = (base[:, None, None, :] + CUBE_OFFSETS[TETS][None, :, :, :]) % n
        values = field[:, inds[..., 0], inds[..., 1], inds[..., 2]]
        matrices = np.transpose(values, (1, 2, 0, 3))
        determinants = np.linalg.det(matrices)
        usable = np.abs(determinants) > DET_EXCLUDE_TOL
        for target_index, target in enumerate(TARGETS):
            if not np.any(usable):
                continue
            flat_matrices = matrices[usable]
            flat_determinants = determinants[usable]
            try:
                coefficients = np.linalg.solve(
                    flat_matrices,
                    np.broadcast_to(target, (flat_matrices.shape[0], 4))[..., None],
                )[..., 0]
            except np.linalg.LinAlgError as exc:
                raise EvidenceFailure("RegularValueFailure", f"regular-value linear solve failed: {exc}") from exc
            if not bool(np.all(np.isfinite(coefficients))):
                raise EvidenceFailure("NonFiniteEvidence", "regular-value coefficients are nonfinite")
            near_simplex = np.all(coefficients > -FACE_TOL, axis=1)
            near_face = near_simplex & np.any(np.abs(coefficients) <= FACE_TOL, axis=1)
            covered = np.all(coefficients > COEFF_TOL, axis=1)
            near_det = covered & (np.abs(flat_determinants) < DET_AMBIGUITY_TOL)
            ambiguity[target_index] += int(np.count_nonzero(near_face | near_det))
            signs = np.sign(flat_determinants).astype(np.int8) * np.broadcast_to(spatial_signs, determinants.shape)[usable]
            positive[target_index] += int(np.count_nonzero(covered & (signs > 0)))
            negative[target_index] += int(np.count_nonzero(covered & (signs < 0)))
    degrees = positive - negative
    rows = [{"index": int(index + 1), "positive_hits": int(positive[index]), "negative_hits": int(negative[index]), "signed_degree": int(degrees[index])} for index in range(16)]
    common: int | None = int(degrees[0]) if bool(np.all(degrees == degrees[0])) else None
    resolved = bool(
        np.all(positive > 0)
        and np.all(negative > 0)
        and np.all(ambiguity == 0)
        and common is not None
        and edge_angle_max(field) < EDGE_LIMIT
    )
    return {"targets": rows, "ambiguity_count": int(np.sum(ambiguity)), "common_degree": common, "resolved_positive_negative": resolved}


def compare_regular(primary_record: Mapping[str, Any], actual: Mapping[str, Any], label: str, mismatches: MismatchBook) -> None:
    rows = primary_record.get("targets")
    if not isinstance(rows, list) or len(rows) != 16:
        raise EvidenceFailure("MalformedPrimaryEvidence", f"{label}.targets must contain 16 rows")
    actual_rows = actual["targets"]
    by_index: dict[int, Mapping[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise EvidenceFailure("MalformedPrimaryEvidence", f"{label}.targets row is not an object")
        index_value = lookup(row, ("index", "m", "target"))
        if isinstance(index_value, bool) or not isinstance(index_value, int) or index_value in by_index:
            raise EvidenceFailure("MalformedPrimaryEvidence", f"{label}.targets has malformed or duplicate indices")
        by_index[int(index_value)] = row
    if set(by_index) != set(range(1, 17)):
        raise EvidenceFailure("MalformedPrimaryEvidence", f"{label}.targets indices are not 1..16")
    for expected_row in actual_rows:
        index = int(expected_row["index"])
        recorded = by_index[index]
        for key in ("positive_hits", "negative_hits", "signed_degree"):
            value = lookup(recorded, (key,))
            if isinstance(value, bool) or not isinstance(value, int):
                raise EvidenceFailure("MalformedPrimaryEvidence", f"{label}.targets[{index}].{key} is not an integer")
            mismatches.exact(f"{label}.targets[{index}].{key}", expected_row[key], int(value))
    ambiguity = primary_record.get("ambiguity_count")
    if isinstance(ambiguity, bool) or not isinstance(ambiguity, int):
        raise EvidenceFailure("MalformedPrimaryEvidence", f"{label}.ambiguity_count is not an integer")
    mismatches.exact(f"{label}.ambiguity_count", actual["ambiguity_count"], int(ambiguity))
    common = primary_record.get("common_degree")
    if common is not None and (isinstance(common, bool) or not isinstance(common, int)):
        raise EvidenceFailure("MalformedPrimaryEvidence", f"{label}.common_degree is not integer or null")
    mismatches.exact(f"{label}.common_degree", actual["common_degree"], common)
    resolved = primary_record.get("resolved_positive_negative")
    if not isinstance(resolved, bool):
        raise EvidenceFailure("MalformedPrimaryEvidence", f"{label}.resolved_positive_negative is not boolean")
    mismatches.exact(f"{label}.resolved_positive_negative", actual["resolved_positive_negative"], resolved)


def event_metadata(group: Mapping[str, Any], group_name: str) -> list[dict[str, Any]]:
    entries = group.get("events")
    if not isinstance(entries, list) or len(entries) != len(EXPECTED_EVENT_IDS):
        raise EvidenceFailure("MalformedPrimaryEvidence", f"groups.{group_name}.events must contain the eight frozen events")
    result: list[dict[str, Any]] = []
    for index, row in enumerate(entries):
        if not isinstance(row, Mapping):
            raise EvidenceFailure("MalformedPrimaryEvidence", f"groups.{group_name}.events[{index}] is not an object")
        ident = row.get("id")
        if ident != EXPECTED_EVENT_IDS[index]:
            raise EvidenceFailure("MalformedPrimaryEvidence", f"groups.{group_name}.events order differs from the frozen event order")
        kind = row.get("kind")
        expected_kind = "prepared" if index < 2 else "random"
        if kind != expected_kind:
            raise EvidenceFailure("MalformedPrimaryEvidence", f"groups.{group_name}.events[{index}].kind differs from frozen metadata")
        seed = row.get("seed")
        expected_seed = None if index < 2 else SEEDS[index - 2]
        if seed != expected_seed:
            raise EvidenceFailure("MalformedPrimaryEvidence", f"groups.{group_name}.events[{index}].seed differs from frozen metadata")
        result.append({"id": ident, "kind": kind, "seed": seed})
    return result


def validate_snapshot_npz(path: Path, group_name: str, snapshot_index: int, expected_s: float, expected_n: int, expected_dy: float, expected_include: bool, event_ids: Sequence[str]) -> np.ndarray:
    arrays = load_npz(path, f"{group_name}.snapshot[{snapshot_index}]")
    field = float64_array(arrays, "field", (len(event_ids), 4, expected_n, expected_n, expected_n), f"{group_name}.snapshot[{snapshot_index}]")
    event_array = arrays.get("event_ids")
    if event_array is None or event_array.dtype.kind != "U" or event_array.shape != (len(event_ids),) or tuple(str(item) for item in event_array.tolist()) != tuple(event_ids):
        raise EvidenceFailure("MalformedNPZ", f"{group_name}.snapshot[{snapshot_index}].event_ids differs from group event order")
    s = scalar_array(arrays, "s", np.dtype(np.float64), f"{group_name}.snapshot[{snapshot_index}]")
    if float(s) != expected_s:
        raise EvidenceFailure("MalformedNPZ", f"{group_name}.snapshot[{snapshot_index}].s is not the exact retained time")
    dy = scalar_array(arrays, "dimensionless_spacing", np.dtype(np.float64), f"{group_name}.snapshot[{snapshot_index}]")
    if not math.isclose(float(dy), expected_dy, rel_tol=1.0e-12, abs_tol=1.0e-12):
        raise EvidenceFailure("FrozenConstantMismatch", f"{group_name}.snapshot[{snapshot_index}] dimensionless spacing mismatch")
    physical = scalar_array(arrays, "physical_spacing_fm", np.dtype(np.float64), f"{group_name}.snapshot[{snapshot_index}]")
    if not math.isclose(float(physical), L_FM / expected_n, rel_tol=1.0e-12, abs_tol=1.0e-12):
        raise EvidenceFailure("FrozenConstantMismatch", f"{group_name}.snapshot[{snapshot_index}] physical spacing mismatch")
    n_value = scalar_array(arrays, "N", np.dtype(np.int64), f"{group_name}.snapshot[{snapshot_index}")
    if int(n_value) != expected_n:
        raise EvidenceFailure("FrozenConstantMismatch", f"{group_name}.snapshot[{snapshot_index}] N mismatch")
    include_value = scalar_array(arrays, "include_u4", np.dtype(np.int8), f"{group_name}.snapshot[{snapshot_index}]")
    if int(include_value) != int(expected_include):
        raise EvidenceFailure("FrozenConstantMismatch", f"{group_name}.snapshot[{snapshot_index}] include_u4 mismatch")
    return field


def validate_history(group: Mapping[str, Any], group_name: str, base: Path, expected_n: int, expected_dy: float, event_ids: Sequence[str], observed: Mapping[float, Mapping[str, Mapping[str, Any]]], mismatches: MismatchBook) -> dict[str, Any]:
    path, descriptor = descriptor_path(base, group.get("history"), f"groups.{group_name}.history")
    arrays = load_npz(path, f"{group_name}.history")
    s = float64_array(arrays, "s", None, f"{group_name}.history")
    ds = float64_array(arrays, "ds", None, f"{group_name}.history")
    energies = float64_array(arrays, "energies", None, f"{group_name}.history")
    halvings = arrays.get("halvings")
    cutoff_hits = arrays.get("cutoff_hits")
    min_norm = arrays.get("min_norm")
    if halvings is None or halvings.dtype != np.dtype(np.int64) or halvings.ndim != 1:
        raise EvidenceFailure("MalformedNPZ", f"{group_name}.history.halvings must be int64 one-dimensional")
    if cutoff_hits is None or cutoff_hits.dtype != np.dtype(np.int64):
        raise EvidenceFailure("MalformedNPZ", f"{group_name}.history.cutoff_hits must be int64")
    if min_norm is None or min_norm.dtype != np.dtype(np.float64):
        raise EvidenceFailure("MalformedNPZ", f"{group_name}.history.min_norm must be float64")
    if s.ndim != 1 or ds.ndim != 1 or energies.ndim != 2 or ds.shape != s.shape or halvings.shape != s.shape or energies.shape != (s.size, len(event_ids)) or cutoff_hits.shape != energies.shape or min_norm.shape != energies.shape:
        raise EvidenceFailure("MalformedNPZ", f"{group_name}.history arrays have inconsistent shapes")
    if bool(np.any(halvings < 0)) or bool(np.any(halvings > MAX_HALVINGS)):
        raise EvidenceFailure("MalformedNPZ", f"{group_name}.history.halvings lies outside the frozen per-step range")
    if bool(np.any(cutoff_hits < 0)) or bool(np.any(cutoff_hits > expected_n**3)):
        raise EvidenceFailure("MalformedNPZ", f"{group_name}.history.cutoff_hits lies outside the physical count range")
    if bool(np.any(min_norm < 0.0)):
        raise EvidenceFailure("MalformedNPZ", f"{group_name}.history.min_norm is negative")
    accepted_steps = require_int(group.get("accepted_steps"), f"groups.{group_name}.accepted_steps")
    if accepted_steps < 0 or accepted_steps > MAX_STEPS or s.size != accepted_steps + 1:
        raise EvidenceFailure("MalformedPrimaryEvidence", f"{group_name}.history length is not accepted_steps+1 within budget")
    if float(s[0]) != 0.0 or float(ds[0]) != 0.0 or int(halvings[0]) != 0 or float(s[-1]) != 8.0:
        raise EvidenceFailure("MalformedNPZ", f"{group_name}.history lacks exact initial/final retained times")
    if np.any(np.diff(s) <= 0.0) or np.any(ds[1:] <= 0.0) or np.any(ds[1:] > ATTEMPTED_DS + 1.0e-14):
        raise EvidenceFailure("MalformedNPZ", f"{group_name}.history has invalid accepted-step schedule")
    if not bool(np.allclose(np.diff(s), ds[1:], rtol=0.0, atol=2.0e-12)):
        raise EvidenceFailure("MalformedNPZ", f"{group_name}.history ds does not reproduce s increments")
    declared_halvings = group.get("halvings")
    if isinstance(declared_halvings, int) and not isinstance(declared_halvings, bool):
        if int(np.sum(halvings, dtype=np.int64)) != int(declared_halvings):
            raise EvidenceFailure("MalformedPrimaryEvidence", f"{group_name}.halvings disagrees with history")
    else:
        raise EvidenceFailure("MalformedPrimaryEvidence", f"groups.{group_name}.halvings is not an integer")
    energy_rule_passes = True
    max_energy_tolerance_excess = 0.0
    for row in range(1, energies.shape[0]):
        delta = energies[row] - energies[row - 1]
        tolerance = ENERGY_REL_TOL * np.maximum(1.0, np.abs(energies[row - 1]))
        excess = delta - tolerance
        max_energy_tolerance_excess = max(max_energy_tolerance_excess, float(np.max(excess)), 0.0)
        if bool(np.any(excess > 0.0)):
            energy_rule_passes = False
    declared_rule = group.get("history_energy_rule_passes")
    if not isinstance(declared_rule, bool):
        raise EvidenceFailure("MalformedPrimaryEvidence", f"groups.{group_name}.history_energy_rule_passes is not boolean")
    mismatches.exact(f"groups.{group_name}.history_energy_rule_passes", energy_rule_passes, declared_rule)
    declared_excess = group.get("max_energy_tolerance_excess")
    if not finite_number(declared_excess):
        raise EvidenceFailure("MalformedPrimaryEvidence", f"groups.{group_name}.max_energy_tolerance_excess is not finite")
    mismatches.scalar(f"groups.{group_name}.max_energy_tolerance_excess", max_energy_tolerance_excess, float(declared_excess))
    coverage: dict[str, int] = {}
    for retained in RETAINED_S:
        matches = np.flatnonzero(np.isclose(s, retained, rtol=0.0, atol=2.0e-12))
        if matches.size != 1:
            raise EvidenceFailure("MalformedNPZ", f"{group_name}.history does not contain exactly one row at retained s={retained}")
        row = int(matches[0])
        coverage[str(retained)] = row
        for event_index, ident in enumerate(event_ids):
            expected_metric = observed[retained][ident]["total_energy"]
            mismatches.scalar(f"groups.{group_name}.history.energies[{row},{event_index}]", expected_metric, float(energies[row, event_index]))
    persistence_rows = s >= 4.0
    persistent_cutoff_hits = [int(np.max(cutoff_hits[persistence_rows, event_index])) if np.any(persistence_rows) else 0 for event_index in range(len(event_ids))]
    persistent_min_norm = [float(np.min(min_norm[persistence_rows, event_index])) if np.any(persistence_rows) else math.inf for event_index in range(len(event_ids))]
    return {"artifact": descriptor, "rows": int(s.size), "accepted_steps": accepted_steps, "halvings": int(declared_halvings), "monotone": energy_rule_passes, "history_energy_rule_passes": energy_rule_passes, "max_energy_tolerance_excess": max_energy_tolerance_excess, "retained_rows": coverage, "persistent_cutoff_hits": persistent_cutoff_hits, "persistent_min_norm": persistent_min_norm}


def validate_group(primary_group: Mapping[str, Any], group_name: str, base: Path, mismatches: MismatchBook) -> dict[str, Any]:
    spec = GROUP_SPECS[group_name]
    if require_int(primary_group.get("N"), f"groups.{group_name}.N") != spec["N"]:
        raise EvidenceFailure("FrozenConstantMismatch", f"groups.{group_name}.N differs from frozen grid")
    spacing_value = require_lookup(primary_group, ("dimensionless_spacing", "spacing", "dy"), f"groups.{group_name}.spacing")
    check_close(spacing_value, spec["dy"], f"groups.{group_name}.spacing")
    if require_bool(primary_group.get("include_u4"), f"groups.{group_name}.include_u4") != spec["include_u4"]:
        raise EvidenceFailure("FrozenConstantMismatch", f"groups.{group_name}.include_u4 differs from frozen arm")
    metadata = event_metadata(primary_group, group_name)
    snapshots = primary_group.get("snapshots")
    if not isinstance(snapshots, list) or len(snapshots) != len(RETAINED_S):
        raise EvidenceFailure("MalformedPrimaryEvidence", f"groups.{group_name}.snapshots must contain exactly nine snapshots")
    observed: dict[float, dict[str, dict[str, Any]]] = {}
    for snapshot_index, snapshot in enumerate(snapshots):
        if not isinstance(snapshot, Mapping):
            raise EvidenceFailure("MalformedPrimaryEvidence", f"groups.{group_name}.snapshots[{snapshot_index}] is not an object")
        s_value = require_float(snapshot.get("s"), f"groups.{group_name}.snapshots[{snapshot_index}].s")
        expected_s = RETAINED_S[snapshot_index]
        if s_value != expected_s:
            raise EvidenceFailure("MalformedPrimaryEvidence", f"groups.{group_name}.snapshots are not in exact retained order")
        path, _ = descriptor_path(base, snapshot.get("artifact", snapshot.get("file")), f"groups.{group_name}.snapshots[{snapshot_index}]")
        fields = validate_snapshot_npz(path, group_name, snapshot_index, expected_s, spec["N"], spec["dy"], spec["include_u4"], EXPECTED_EVENT_IDS)
        primary_events = snapshot.get("events")
        if not isinstance(primary_events, Mapping) or tuple(primary_events.keys()) != EXPECTED_EVENT_IDS:
            raise EvidenceFailure("MalformedPrimaryEvidence", f"groups.{group_name}.snapshots[{snapshot_index}].events order is malformed")
        event_rows: dict[str, dict[str, Any]] = {}
        for event_index, ident in enumerate(EXPECTED_EVENT_IDS):
            metric = primary_events[ident]
            if not isinstance(metric, Mapping):
                raise EvidenceFailure("MalformedPrimaryEvidence", f"groups.{group_name}.snapshots[{snapshot_index}].events.{ident} is not an object")
            actual = metric_record(fields[event_index], spec["dy"], spec["include_u4"])
            compare_metric(metric, actual, f"groups.{group_name}.snapshots[{snapshot_index}].events.{ident}", mismatches)
            if snapshot_index in (7, 8):
                regular = metric.get("regular_value")
                if not isinstance(regular, Mapping):
                    raise EvidenceFailure("MalformedPrimaryEvidence", f"groups.{group_name}.snapshots[{snapshot_index}].events.{ident}.regular_value is missing")
                actual_regular = regular_value(fields[event_index])
                compare_regular(regular, actual_regular, f"groups.{group_name}.snapshots[{snapshot_index}].events.{ident}.regular_value", mismatches)
                actual["regular_value"] = actual_regular
            elif "regular_value" in metric:
                raise EvidenceFailure("MalformedPrimaryEvidence", f"regular_value is present before s=4 in {group_name}/{ident}")
            event_rows[ident] = actual
        observed[expected_s] = event_rows
    history = validate_history(primary_group, group_name, base, spec["N"], spec["dy"], EXPECTED_EVENT_IDS, observed, mismatches)
    completed = require_bool(primary_group.get("completed"), f"groups.{group_name}.completed")
    if not completed:
        raise EvidenceFailure("IncompletePrimaryEvidence", f"groups.{group_name} is not completed")
    if "stop_reason" in primary_group and primary_group["stop_reason"] not in (None, "", "completed", "reached_s8"):
        raise EvidenceFailure("IncompletePrimaryEvidence", f"groups.{group_name} records a numerical stop: {primary_group['stop_reason']!r}")
    return {"N": spec["N"], "dy": spec["dy"], "include_u4": spec["include_u4"], "events": metadata, "snapshots": observed, "history": history}


def qualified(metrics: Mapping[str, Any], persistent_cutoff_hits: int = 0) -> bool:
    regular = metrics.get("regular_value")
    return bool(isinstance(regular, Mapping) and regular.get("resolved_positive_negative") is True and regular.get("ambiguity_count") == 0 and metrics.get("edge_angle_max", math.inf) < EDGE_LIMIT and metrics.get("cutoff_hits") == 0 and persistent_cutoff_hits == 0)


def reconstruct_formation(groups: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    random_ids = tuple(f"random_{seed}" for seed in SEEDS)
    endpoint_counts: dict[str, int] = {}
    persistent_counts: dict[str, int] = {}
    for group_name in REQUIRED_GROUPS:
        snapshots = groups[group_name]["snapshots"]
        history = groups[group_name]["history"]
        endpoint_counts[group_name] = sum(
            qualified(
                snapshots[8.0][ident],
                history["persistent_cutoff_hits"][EXPECTED_EVENT_IDS.index(ident)],
            )
            for ident in random_ids
        )
        persistent_counts[group_name] = sum(
            qualified(
                snapshots[4.0][ident],
                history["persistent_cutoff_hits"][EXPECTED_EVENT_IDS.index(ident)],
            )
            and qualified(
                snapshots[8.0][ident],
                history["persistent_cutoff_hits"][EXPECTED_EVENT_IDS.index(ident)],
            )
            for ident in random_ids
        )

    prepared_rows: list[dict[str, Any]] = []
    radius_count = 0
    all_prepared_ok = True
    sign_absent = False
    for group_name in ("N30_complete", "N40_complete"):
        snapshots = groups[group_name]["snapshots"]
        history = groups[group_name]["history"]
        for ident, expected_degree in (
            ("prepared_positive", 1),
            ("prepared_negative", -1),
        ):
            event_index = EXPECTED_EVENT_IDS.index(ident)
            persistent_cutoff_hits = history["persistent_cutoff_hits"][event_index]
            event_pass = True
            radius_pass = True
            time_rows: list[dict[str, Any]] = []
            for retained in (4.0, 8.0):
                metrics = snapshots[retained][ident]
                regular = metrics["regular_value"]
                degree = regular["common_degree"]
                topology_pass = bool(
                    degree == expected_degree
                    and regular["ambiguity_count"] == 0
                    and metrics["edge_angle_max"] < EDGE_LIMIT
                    and metrics["cutoff_hits"] == 0
                    and persistent_cutoff_hits == 0
                    and abs(metrics["B"]) >= 0.65
                )
                radius = metrics["rms_radius_fm"]
                radius_here = bool(
                    radius is not None
                    and RADIUS_MIN_FM <= float(radius) <= RADIUS_MAX_FM
                )
                event_pass = event_pass and topology_pass
                radius_pass = radius_pass and radius_here
                time_rows.append(
                    {
                        "s": retained,
                        "degree": degree,
                        "B": metrics["B"],
                        "radius_fm": radius,
                        "topology_pass": topology_pass,
                        "radius_pass": radius_here,
                    }
                )
            all_prepared_ok = all_prepared_ok and event_pass
            radius_count += int(radius_pass)
            sign_absent = sign_absent or (
                snapshots[8.0][ident]["regular_value"]["common_degree"]
                != expected_degree
            )
            prepared_rows.append(
                {
                    "group": group_name,
                    "event": ident,
                    "expected_degree": expected_degree,
                    "times": time_rows,
                    "retains_sign": event_pass,
                    "radius_qualified": radius_pass,
                }
            )

    qcf4_candidates: list[dict[str, Any]] = []
    qualified_events: list[dict[str, Any]] = []
    zero_with_boundary = False
    for group_name in ("N30_complete", "N40_complete"):
        snapshots = groups[group_name]["snapshots"]
        history = groups[group_name]["history"]
        for ident in random_ids:
            event_index = EXPECTED_EVENT_IDS.index(ident)
            persistent_cutoff_hits = history["persistent_cutoff_hits"][event_index]
            at4 = snapshots[4.0][ident]
            at8 = snapshots[8.0][ident]
            if not (
                qualified(at4, persistent_cutoff_hits)
                and qualified(at8, persistent_cutoff_hits)
            ):
                continue
            degree4 = at4["regular_value"]["common_degree"]
            degree8 = at8["regular_value"]["common_degree"]
            boundary = any(
                snapshots[retained][ident]["min_norm"] <= 10.0 * EPSILON
                or snapshots[retained][ident]["edge_angle_max"] >= EDGE_LIMIT
                for retained in RETAINED_S
                if retained < 4.0
            )
            candidate = {
                "group": group_name,
                "event": ident,
                "degree_s4": degree4,
                "degree_s8": degree8,
                "boundary_interval": bool(boundary),
            }
            qcf4_candidates.append(candidate)
            qualified_events.append(
                {
                    **candidate,
                    "persistent_cutoff_hits": persistent_cutoff_hits,
                    "persistent_min_norm": history["persistent_min_norm"][event_index],
                }
            )
            if degree4 == 0 and degree8 == 0 and boundary:
                zero_with_boundary = True

    qcf4_verdict = (
        "SUPPORTS"
        if zero_with_boundary
        else "CONTRADICTS"
        if qcf4_candidates
        else "INCONCLUSIVE"
    )
    return {
        "prepared": prepared_rows,
        "persistent_random_counts": persistent_counts,
        "endpoint_random_counts": endpoint_counts,
        "qcf4_candidates": qcf4_candidates,
        "endpoint_contrast_N30": (
            endpoint_counts["N30_complete"] - endpoint_counts["N30_no_u4"]
        ),
        "fractions": {
            name: persistent_counts[name] / 6.0 for name in REQUIRED_GROUPS
        },
        "qualified_events": qualified_events,
        "qcf2": {
            "prepared": prepared_rows,
            "radius_count": radius_count,
            "all_prepared_ok": all_prepared_ok,
            "sign_absent_at_s8": sign_absent,
        },
        "qcf4": {
            "zero_degree_with_boundary": zero_with_boundary,
            "qualified_events": qualified_events,
            "verdict": qcf4_verdict,
        },
    }

def compare_formation_summary(
    primary: Mapping[str, Any],
    actual: Mapping[str, Any],
    mismatches: MismatchBook,
) -> None:
    expected_keys = {
        "prepared",
        "persistent_random_counts",
        "endpoint_random_counts",
        "qcf4_candidates",
    }
    if set(primary) != expected_keys:
        raise EvidenceFailure(
            "MalformedPrimaryEvidence",
            "formation_summary keys differ from the executable receipt contract",
        )
    for key in sorted(expected_keys):
        compare_tree(
            f"formation_summary.{key}",
            actual[key],
            primary[key],
            mismatches,
        )


def reconstruct_verdicts(
    controls: Mapping[str, Any],
    groups: Mapping[str, Mapping[str, Any]],
    formation: Mapping[str, Any],
    primary_gates: Mapping[str, Any],
) -> tuple[dict[str, str], dict[str, Any]]:
    history_ok = all(
        bool(groups[name]["history"]["monotone"]) for name in REQUIRED_GROUPS
    )
    maximum_boundary_error = max(
        float(metrics["boundary_error"])
        for group_name in REQUIRED_GROUPS
        for metrics_by_event in groups[group_name]["snapshots"].values()
        for metrics in metrics_by_event.values()
    )
    no_numerical_stop = True
    qcf1_inputs = {
        "vacuum": controls["vacuum"]["pass"],
        "directional_derivative": controls["directional_derivative"]["pass"],
        "checkerboard": controls["checkerboard"]["pass"],
        "histories_monotone": history_ok,
        "maximum_boundary_error": maximum_boundary_error,
        "no_numerical_stop": no_numerical_stop,
    }
    qcf1_pass = bool(
        qcf1_inputs["vacuum"]
        and qcf1_inputs["directional_derivative"]
        and qcf1_inputs["checkerboard"]
        and qcf1_inputs["histories_monotone"]
        and maximum_boundary_error < BOUNDARY_TOL
        and no_numerical_stop
    )

    qcf2_summary = formation["qcf2"]
    qcf2_pass = bool(
        qcf1_pass
        and qcf2_summary["all_prepared_ok"]
        and qcf2_summary["radius_count"] >= 3
    )
    qcf2 = (
        "INCONCLUSIVE"
        if not qcf1_pass
        else "SUPPORTS"
        if qcf2_pass
        else "CONTRADICTS"
        if qcf2_summary["sign_absent_at_s8"]
        else "INCONCLUSIVE"
    )
    qcf2_inputs = {
        "retained_signs": qcf2_summary["all_prepared_ok"],
        "radius_qualified_textures": qcf2_summary["radius_count"],
        "endpoint_sign_absent": qcf2_summary["sign_absent_at_s8"],
    }

    c30 = formation["persistent_random_counts"]["N30_complete"]
    c40 = formation["persistent_random_counts"]["N40_complete"]
    e30 = formation["endpoint_random_counts"]["N30_complete"]
    e40 = formation["endpoint_random_counts"]["N40_complete"]
    e0 = formation["endpoint_random_counts"]["N30_no_u4"]
    qcf3_pass = bool(
        qcf1_pass
        and c30 >= 4
        and c40 >= 4
        and abs(c30 - c40) <= 2
        and e30 - e0 >= 3
    )
    qcf3 = (
        "INCONCLUSIVE"
        if not qcf1_pass
        else "EMERGES"
        if qcf3_pass
        else "DOES NOT EMERGE"
        if e30 == 0 and e40 == 0
        else "INCONCLUSIVE"
    )
    qcf3_inputs = {
        "persistent_counts": formation["persistent_random_counts"],
        "endpoint_counts": formation["endpoint_random_counts"],
    }

    qcf4_pass = bool(
        qcf1_pass and formation["qcf4"]["zero_degree_with_boundary"]
    )
    qcf4 = (
        "INCONCLUSIVE"
        if not qcf1_pass
        else formation["qcf4"]["verdict"]
    )
    qcf4_inputs = {"candidates": formation["qcf4_candidates"]}

    cosmology = controls["cosmology"]
    qcf5_contradicts = bool(
        cosmology["classification"] == "crossover"
        and cosmology["ratio_2fm_c_min"] > 1.0e12
    )
    qcf5_pass = bool(
        cosmology["classification"] == "first-order"
        and cosmology["ratio_2fm_c_max"] < 1.0e3
    )
    qcf5 = (
        "CONTRADICTS"
        if qcf5_contradicts
        else "SUPPORTS"
        if qcf5_pass
        else "INCONCLUSIVE"
    )
    qcf5_inputs = {
        "classification": cosmology["classification"],
        "minimum_ratio_to_2_fm_over_c": cosmology["ratio_2fm_c_min"],
        "maximum_ratio_to_2_fm_over_c": cosmology["ratio_2fm_c_max"],
    }

    qcf6_inputs = primary_gates["QCF6"]["inputs"]
    expected_qcf6_flags = {
        "microscopic_qcd_selection": False,
        "baryon_current_transport": False,
        "fermionic_spin_statistics": False,
        "density_operator_occupations": False,
        "cosmological_initial_state": False,
    }
    for name, expected in expected_qcf6_flags.items():
        value = qcf6_inputs.get(name)
        if not isinstance(value, bool):
            raise EvidenceFailure(
                "MalformedPrimaryEvidence",
                f"gates.QCF6.inputs.{name} is missing or not boolean",
            )
        if value is not expected:
            raise EvidenceFailure(
                "UnsupportedCompletionClaim",
                f"gates.QCF6.inputs.{name} claims evidence absent from the frozen calculation",
            )
    expected_requirements = (
        (
            "Cassi selection of microscopic QCD action and quantum state",
            "QCD is an empirical input and no Cassi-to-QCD selection rule is supplied.",
        ),
        (
            "quark baryon-current transport through chiral zeros",
            "The classical order-parameter calculation has no quark-current transport observable.",
        ),
        (
            "fermionic spin and statistics of late textures",
            "The classical fields are not collectively quantized with a Finkelstein-Rubinstein sector.",
        ),
        (
            "density-operator occupation numbers and production probabilities",
            "The dissipative ensemble is classical and carries no density operator.",
        ),
        (
            "unfitted cosmological initial state and cooling history",
            "The random hot field is stipulated and relaxation coordinate s has no cosmological-time map.",
        ),
    )
    requirements = qcf6_inputs.get("requirements")
    if not isinstance(requirements, list) or len(requirements) != len(
        expected_requirements
    ):
        raise EvidenceFailure(
            "MalformedPrimaryEvidence",
            "gates.QCF6.inputs.requirements must contain five frozen rows",
        )
    for index, (row, (requirement, evidence)) in enumerate(
        zip(requirements, expected_requirements)
    ):
        expected_row = {
            "requirement": requirement,
            "present": False,
            "evidence": evidence,
        }
        if row != expected_row:
            raise EvidenceFailure(
                "MalformedPrimaryEvidence",
                f"gates.QCF6.inputs.requirements[{index}] differs from the frozen row",
            )

    verdicts = {
        "QCF1": "PASS" if qcf1_pass else "FAIL",
        "QCF2": qcf2,
        "QCF3": qcf3,
        "QCF4": qcf4,
        "QCF5": qcf5,
        "QCF6": "FAIL",
    }
    return verdicts, {
        "QCF1": qcf1_inputs,
        "QCF2": qcf2_inputs,
        "QCF3": qcf3_inputs,
        "QCF4": qcf4_inputs,
        "QCF5": qcf5_inputs,
        "QCF6": expected_qcf6_flags,
        "passes": {
            "QCF1": qcf1_pass,
            "QCF2": qcf2_pass,
            "QCF3": qcf3_pass,
            "QCF4": qcf4_pass,
            "QCF5": qcf5_pass,
            "QCF6": False,
        },
    }

def validate_environment(value: Any) -> dict[str, Any]:
    environment = require_mapping(value, "environment")
    required = {
        "python",
        "numpy",
        "scipy",
        "torch",
        "torch_hip",
        "platform",
        "requested_device",
        "resolved_device",
        "torch_dtype",
        "pid",
    }
    if set(environment) != required:
        raise EvidenceFailure(
            "MalformedPrimaryEvidence",
            "environment keys differ from the executable receipt contract",
        )
    for key in (
        "python",
        "numpy",
        "scipy",
        "torch",
        "platform",
        "requested_device",
        "resolved_device",
        "torch_dtype",
    ):
        if not isinstance(environment[key], str) or not environment[key]:
            raise EvidenceFailure(
                "MalformedPrimaryEvidence", f"environment.{key} is not a nonempty string"
            )
    if environment["requested_device"] not in {"cpu", "cuda"}:
        raise EvidenceFailure(
            "MalformedPrimaryEvidence", "environment.requested_device is invalid"
        )
    if environment["resolved_device"] != environment["requested_device"]:
        raise EvidenceFailure(
            "MalformedPrimaryEvidence",
            "environment resolved device differs from requested device",
        )
    if environment["torch_dtype"] != "float32":
        raise EvidenceFailure(
            "FrozenConstantMismatch", "environment.torch_dtype must be float32"
        )
    if environment["torch_hip"] is not None and (
        not isinstance(environment["torch_hip"], str) or not environment["torch_hip"]
    ):
        raise EvidenceFailure(
            "MalformedPrimaryEvidence", "environment.torch_hip is malformed"
        )
    pid = environment["pid"]
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        raise EvidenceFailure("MalformedPrimaryEvidence", "environment.pid is invalid")
    return dict(environment)


def validate_primary_envelope(primary: Mapping[str, Any], protocol_body: bytes, protocol_path: Path) -> dict[str, Any]:
    required = ("schema", "completed", "scientific_execution_started", "wall_s", "protocol", "sources", "environment", "constants", "controls", "groups", "gates", "verdicts", "complete_physical_matter_formation", "formation_summary")
    missing = [key for key in required if key not in primary]
    if missing:
        raise EvidenceFailure("IncompletePrimaryEvidence", f"primary receipt missing required keys: {missing}")
    if primary.get("schema") != PRIMARY_SCHEMA:
        raise EvidenceFailure("MalformedPrimaryEvidence", "primary schema mismatch")
    if primary.get("completed") is not True or primary.get("scientific_execution_started") is not True:
        raise EvidenceFailure("IncompletePrimaryEvidence", "primary execution is not completed")
    require_float(primary.get("wall_s"), "wall_s")
    validate_environment(primary["environment"])
    if not isinstance(primary.get("complete_physical_matter_formation"), bool):
        raise EvidenceFailure("MalformedPrimaryEvidence", "complete_physical_matter_formation is not boolean")
    protocol = require_mapping(primary["protocol"], "protocol")
    if protocol.get("path") != PROTOCOL_REL:
        raise EvidenceFailure("ProtocolMismatch", "primary protocol path differs from frozen path")
    if protocol.get("sha256") != sha256_bytes(protocol_body):
        raise EvidenceFailure("ProtocolMismatch", "primary protocol hash differs from marker-delimited bytes")
    if protocol.get("bytes") != len(protocol_body):
        raise EvidenceFailure("ProtocolMismatch", "primary protocol byte count differs from marker-delimited bytes")
    sources = require_mapping(primary["sources"], "sources")
    for source_path, descriptor in sources.items():
        if not isinstance(source_path, str) or not source_path:
            raise EvidenceFailure("MalformedPrimaryEvidence", "sources key is not a nonempty string")
        supplied_source = Path(source_path)
        if (
            supplied_source.is_absolute()
            or ".." in supplied_source.parts
            or supplied_source.as_posix() != source_path
        ):
            raise EvidenceFailure(
                "PathEscape",
                f"source identity path is not root-relative POSIX form: {source_path!r}",
            )
        path = (ROOT / supplied_source).resolve()
        try:
            path.relative_to(ROOT)
        except ValueError as exc:
            raise EvidenceFailure("PathEscape", f"source path escapes repository: {source_path!r}") from exc
        if not path.is_file() or not isinstance(descriptor, Mapping):
            raise EvidenceFailure("MissingEvidence", f"source identity file is missing or malformed: {source_path}")
        declared_hash = descriptor.get("sha256")
        declared_bytes = descriptor.get("bytes")
        if not isinstance(declared_hash, str) or declared_hash != sha256_file(path) or not isinstance(declared_bytes, int) or isinstance(declared_bytes, bool) or declared_bytes != path.stat().st_size:
            raise EvidenceFailure("SourceHashMismatch", f"source identity mismatch: {source_path}")
    for source_path in (PRIMARY_SOURCE_REL, PROTOCOL_REL):
        if source_path not in sources:
            raise EvidenceFailure("IncompletePrimaryEvidence", f"sources is missing {source_path}")
    if sources[PRIMARY_SOURCE_REL]["sha256"] != sha256_file(ROOT / PRIMARY_SOURCE_REL):
        raise EvidenceFailure("SourceHashMismatch", "primary source hash does not match current source")
    if sources[PROTOCOL_REL]["sha256"] != sha256_file(protocol_path):
        raise EvidenceFailure("SourceHashMismatch", "protocol source hash does not match current protocol")
    groups = require_mapping(primary["groups"], "groups")
    if set(groups) != set(REQUIRED_GROUPS):
        raise EvidenceFailure("IncompletePrimaryEvidence", "primary groups are not exactly N30_complete, N40_complete, N30_no_u4")
    gates = require_mapping(primary["gates"], "gates")
    if set(gates) != set(VERDICT_KEYS):
        raise EvidenceFailure("MalformedPrimaryEvidence", "primary gates do not contain exactly QCF1-QCF6")
    gate_rows: dict[str, dict[str, Any]] = {}
    for key in VERDICT_KEYS:
        row = gates[key]
        if not isinstance(row, Mapping) or not isinstance(row.get("passed"), bool) or not isinstance(row.get("inputs"), Mapping):
            raise EvidenceFailure("MalformedPrimaryEvidence", f"gates.{key} must contain boolean passed and object inputs")
        gate_rows[key] = {"passed": bool(row["passed"]), "inputs": dict(row["inputs"])}
    verdicts = require_mapping(primary["verdicts"], "verdicts")
    if set(verdicts) != set(VERDICT_KEYS):
        raise EvidenceFailure("MalformedPrimaryEvidence", "primary verdict keys are not exactly QCF1-QCF6")
    for key in VERDICT_KEYS:
        value = verdicts[key]
        if not isinstance(value, str) or value not in VERDICT_VALUES[key]:
            raise EvidenceFailure("MalformedPrimaryEvidence", f"primary {key} verdict is outside frozen vocabulary")
    if verdicts["QCF6"] == "PASS" and primary["complete_physical_matter_formation"] is not True:
        raise EvidenceFailure("MalformedPrimaryEvidence", "QCF6 PASS must set complete_physical_matter_formation=true")
    if verdicts["QCF6"] != "PASS" and primary["complete_physical_matter_formation"] is not False:
        raise EvidenceFailure("MalformedPrimaryEvidence", "complete_physical_matter_formation must be false unless QCF6 passes")
    return gate_rows


def verification_identity(path: Path) -> dict[str, Any]:
    return {"path": path.resolve().relative_to(ROOT).as_posix() if path.resolve().is_relative_to(ROOT) else str(path.resolve()), "sha256": sha256_file(path), "bytes": path.stat().st_size}


def failure_receipt(error: EvidenceFailure, primary_path: Path | None = None) -> dict[str, Any]:
    own = verification_identity(Path(__file__)) if Path(__file__).is_file() else {"path": PRIMARY_SOURCE_REL, "sha256": None, "bytes": None}
    primary_identity: dict[str, Any] = {}
    if primary_path is not None and primary_path.is_file():
        primary_identity = {"path": str(primary_path), "sha256": sha256_file(primary_path), "bytes": primary_path.stat().st_size}
    return {
        "schema": VERIFY_SCHEMA,
        "failure_only": True,
        "failure": {"type": error.kind, "detail": error.detail},
        "error": f"{error.kind}: {error.detail}",
        "source_identity": own,
        "primary_identity": primary_identity,
        "protocol_identity": {"path": PROTOCOL_REL, "sha256": None, "bytes": None},
        "evidence_gates": {},
        "verdicts": {"QCF1": "INCONCLUSIVE", "QCF2": "INCONCLUSIVE", "QCF3": "INCONCLUSIVE", "QCF4": "INCONCLUSIVE", "QCF5": "INCONCLUSIVE", "QCF6": "FAIL"},
        "complete_physical_matter_formation": False,
        "exact_agreement": {"status": "NOT_RUN", "mismatches": []},
        "numerical_pass": False,
    }


def verify_primary(primary: Mapping[str, Any], primary_path: Path, primary_raw: bytes, base: Path) -> dict[str, Any]:
    protocol_path = ROOT / PROTOCOL_REL
    protocol_body = frozen_protocol_bytes(protocol_path)
    gate_rows = validate_primary_envelope(primary, protocol_body, protocol_path)
    constants = validate_constants(require_mapping(primary["constants"], "constants"))
    mismatches = MismatchBook()
    controls = validate_controls(primary, base, mismatches)
    groups: dict[str, dict[str, Any]] = {}
    for group_name in REQUIRED_GROUPS:
        groups[group_name] = validate_group(require_mapping(primary["groups"][group_name], f"groups.{group_name}"), group_name, base, mismatches)
    formation = reconstruct_formation(groups)
    compare_formation_summary(require_mapping(primary["formation_summary"], "formation_summary"), formation, mismatches)
    reconstructed_verdicts, evidence_gate_details = reconstruct_verdicts(controls, groups, formation, gate_rows)
    for key in VERDICT_KEYS:
        mismatches.exact(
            f"verdicts.{key}", reconstructed_verdicts[key], primary["verdicts"][key]
        )
        expected_gate = evidence_gate_details["passes"][key]
        mismatches.exact(
            f"gates.{key}.passed", expected_gate, gate_rows[key]["passed"]
        )
        if key != "QCF6":
            compare_tree(
                f"gates.{key}.inputs",
                evidence_gate_details[key],
                gate_rows[key]["inputs"],
                mismatches,
            )
        else:
            for name, expected in evidence_gate_details["QCF6"].items():
                mismatches.exact(
                    f"gates.QCF6.inputs.{name}",
                    expected,
                    gate_rows["QCF6"]["inputs"][name],
                )
    complete_expected = reconstructed_verdicts["QCF6"] == "PASS"
    mismatches.exact("complete_physical_matter_formation", complete_expected, primary["complete_physical_matter_formation"])
    protocol_identity = {"path": PROTOCOL_REL, "sha256": sha256_bytes(protocol_body), "bytes": len(protocol_body), "source_sha256": sha256_file(protocol_path)}
    agreement = {"status": "PASS" if not mismatches.rows else "FAIL", "mismatches": mismatches.rows}
    numerical_pass = not mismatches.rows
    return {
        "schema": VERIFY_SCHEMA,
        "failure_only": False,
        "source_identity": verification_identity(Path(__file__)),
        "primary_identity": {"path": str(primary_path), "sha256": sha256_bytes(primary_raw), "bytes": len(primary_raw)},
        "protocol_identity": protocol_identity,
        "constants": {"N30": N30, "N40": N40, "dy30": DY30, "dy40": DY40, "epsilon": EPSILON, "retained_s": list(RETAINED_S), "seeds": list(SEEDS), "targets": TARGETS.tolist(), "tetrahedra": [list(row) for row in TETRAHEDRA_STR]},
        "controls": controls,
        "groups": {name: {"N": row["N"], "dy": row["dy"], "include_u4": row["include_u4"], "history": row["history"], "snapshots": {str(s): {ident: metrics for ident, metrics in rows.items()} for s, rows in row["snapshots"].items()}} for name, row in groups.items()},
        "formation_summary": formation,
        "evidence_gates": evidence_gate_details,
        "gates": {key: {"passed": evidence_gate_details["passes"][key], "inputs": evidence_gate_details.get(key, {})} for key in VERDICT_KEYS},
        "verdicts": reconstructed_verdicts,
        "complete_physical_matter_formation": complete_expected,
        "exact_agreement": agreement,
        "numerical_pass": bool(numerical_pass),
    }


def prepare_output(path: Path) -> None:
    if path.exists():
        if not path.is_dir() or any(path.iterdir()):
            raise EvidenceFailure("OutputDirectoryNotFresh", f"output must be absent or empty: {path}")
    else:
        try:
            path.mkdir(parents=True, exist_ok=False)
        except OSError as exc:
            raise EvidenceFailure("OutputDirectoryFailure", f"cannot create output directory: {exc}") from exc


def write_receipt(path: Path, payload: Mapping[str, Any]) -> None:
    try:
        text = json.dumps(jsonable(payload), indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
    except Exception as exc:
        raise EvidenceFailure("VerificationWriteFailure", f"cannot write verification receipt: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="primary results.json or its containing directory")
    parser.add_argument("--output", required=True, help="absent or empty directory receiving verification.json")
    args = parser.parse_args(argv)
    output = Path(args.output).expanduser().resolve()
    try:
        prepare_output(output)
    except EvidenceFailure as exc:
        print(f"{exc.kind}: {exc.detail}", file=sys.stderr)
        return 1

    primary_path: Path | None = None
    try:
        primary_path, base = resolve_primary(args.input)
        primary, raw = strict_json(primary_path)
        result = verify_primary(primary, primary_path, raw, base)
        exit_code = 0 if result["numerical_pass"] else 1
    except EvidenceFailure as exc:
        result = failure_receipt(exc, primary_path)
        exit_code = 1
    except Exception as exc:
        error = EvidenceFailure("UnexpectedVerifierFailure", f"{type(exc).__name__}: {exc}")
        result = failure_receipt(error, primary_path)
        exit_code = 1
    try:
        write_receipt(output / "verification.json", result)
    except EvidenceFailure as exc:
        print(f"{exc.kind}: {exc.detail}", file=sys.stderr)
        return 1
    print(json.dumps({"schema": VERIFY_SCHEMA, "numerical_pass": result.get("numerical_pass", False), "verdicts": result.get("verdicts", {}), "failure_only": result.get("failure_only", False)}, allow_nan=False, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
