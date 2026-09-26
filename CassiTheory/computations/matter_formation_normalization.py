#!/usr/bin/env python3
"""Primary physical normalization and chiral-scalar identity calculation."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Mapping

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = ROOT / "runs" / "20260906_matter_formation_radial"
DEFAULT_SPATIAL_DIR = ROOT / "runs" / "20260906_matter_formation_parent_spatial"
DEFAULT_OUTPUT_DIR = ROOT / "runs" / "20260906_matter_formation_normalization"
PREREG_PATH = ROOT / "computations" / "matter-formation-normalization-prereg.md"
VERIFIER_PATH = ROOT / "computations" / "verify_matter_formation_normalization.py"
SCHEMA = "cassi.matter-formation.normalization.v1"
SPATIAL_SCHEMA = "cassi.matter-formation.parent-spatial.v1"
SPATIAL_VERIFY_SCHEMA = "cassi.matter-formation.parent-spatial.verification.v1"
SOURCE_ID = "q256_R12_n768_refine"
SOURCE_HASH = "95df301fcea98304434b95e9dd63a9cec987495ddda9af46e5940891672dc77a"
SPATIAL_RESULTS_HASH = "9445ff33b33b664bf15e09b499bb185f18bfeb9f8a9393c388afef7c7affa79c"
SPATIAL_VERIFICATION_HASH = "2994e44ee2566ecc4e7ce660dc5d0510a088b694e0224086792eda2854f148dd"
COEFFICIENTS = {"u_rho": 4.0, "u_C": 1.0, "k_Cx": 1.0, "e_C": 0.75, "h_C": 2.9598260763447164}
A_VALUES = (1.0 / 64.0, 1.0 / 32.0, 1.0 / 16.0)
SPATIAL_PARENT_VERDICT = "INCONCLUSIVE—finite-grid scalar parent spatial energetic qualification"
INCONCLUSIVE = "INCONCLUSIVE"

class ContractError(RuntimeError):
    pass


def raw_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def relative_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return os.path.relpath(path.resolve(), ROOT.resolve()).replace("\\", "/")


def finite_scalar(value: Any, label: str) -> float:
    array = np.asarray(value, dtype=np.float64)
    if array.size != 1:
        raise ContractError(f"{label} is not scalar")
    result = float(array.reshape(()))
    if not math.isfinite(result):
        raise ContractError(f"{label} is not finite")
    return result


def require_finite(value: Any, label: str = "payload") -> None:
    if isinstance(value, bool) or isinstance(value, int):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ContractError(f"nonfinite {label}")
        return
    if isinstance(value, complex):
        if not (math.isfinite(value.real) and math.isfinite(value.imag)):
            raise ContractError(f"nonfinite {label}")
        return
    if isinstance(value, Mapping):
        for key, item in value.items():
            require_finite(item, f"{label}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            require_finite(item, f"{label}[{index}]")


def close_value(left: float, right: float, physical: bool = False) -> bool:
    if not (math.isfinite(left) and math.isfinite(right)):
        return False
    scale = max(abs(left), abs(right), 1.0e-300 if physical else 1.0)
    return abs(left - right) <= 1.0e-10 * scale


def write_json_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    if path.exists() or temporary.exists():
        raise FileExistsError(f"refusing existing receipt or temporary artifact: {path}")
    created = False
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            created = True
            json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
        os.replace(temporary, path)
    except Exception:
        if created:
            temporary.unlink(missing_ok=True)
        raise


def identity(path: Path, label: str, failures: list[str]) -> dict[str, str]:
    result = {"path": relative_path(path), "sha256": ""}
    try:
        result["sha256"] = canonical_sha256(path)
    except Exception as exc:
        failures.append(f"missing {label} identity: {type(exc).__name__}: {exc}")
    return result


def identities(failures: list[str]) -> dict[str, dict[str, str]]:
    return {
        "primary": identity(Path(__file__).resolve(), "primary", failures),
        "verifier": identity(VERIFIER_PATH, "verifier", failures),
        "prereg": identity(PREREG_PATH, "preregistration", failures),
    }


def read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ContractError(f"missing {label}: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ContractError(f"invalid {label}: {type(exc).__name__}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"{label} is not an object")
    return value


def _check_identity_map(receipt: Mapping[str, Any], label: str, expected: Mapping[str, Mapping[str, str]]) -> None:
    actual = receipt.get("identities")
    if not isinstance(actual, Mapping):
        raise ContractError(f"{label} identities missing")
    for key in ("primary", "verifier", "prereg"):
        item = actual.get(key)
        if not isinstance(item, Mapping) or item.get("path") != expected[key]["path"] or item.get("sha256") != expected[key]["sha256"]:
            raise ContractError(f"{label} canonical identity mismatch: {key}")


def _row(receipt: Mapping[str, Any], identifier: str, label: str) -> Mapping[str, Any]:
    rows = receipt.get("rows")
    if not isinstance(rows, list):
        raise ContractError(f"{label} rows missing")
    found = [item for item in rows if isinstance(item, Mapping) and item.get("id") == identifier]
    if len(found) != 1:
        raise ContractError(f"{label} selected row mismatch: {identifier}")
    return found[0]


def validate_spatial(spatial_dir: Path, failures: list[str]) -> tuple[dict[str, Any], dict[str, Any], Mapping[str, Any], Mapping[str, Any]]:
    result_path = spatial_dir / "results.json"
    verification_path = spatial_dir / "verification.json"
    if not result_path.is_file() or not verification_path.is_file():
        raise ContractError("missing accepted spatial receipt")
    if raw_sha256(result_path) != SPATIAL_RESULTS_HASH or raw_sha256(verification_path) != SPATIAL_VERIFICATION_HASH:
        raise ContractError("accepted spatial receipt raw hash mismatch")
    result = read_json(result_path, "spatial results")
    verification = read_json(verification_path, "spatial verification")
    if result.get("schema") != SPATIAL_SCHEMA or verification.get("schema") != SPATIAL_VERIFY_SCHEMA:
        raise ContractError("accepted spatial schema mismatch")
    if result.get("numerical_pass") is not True or result.get("failures") != [] or verification.get("numerical_pass") is not True or verification.get("failures") != []:
        raise ContractError("accepted spatial receipt is not numerically clean")
    if verification.get("input_sha256") != SPATIAL_RESULTS_HASH:
        raise ContractError("accepted spatial verification linkage mismatch")
    expected = {
        "primary": {"path": relative_path(ROOT / "computations" / "matter_formation_parent_spatial.py"), "sha256": canonical_sha256(ROOT / "computations" / "matter_formation_parent_spatial.py")},
        "verifier": {"path": relative_path(ROOT / "computations" / "verify_matter_formation_parent_spatial.py"), "sha256": canonical_sha256(ROOT / "computations" / "verify_matter_formation_parent_spatial.py")},
        "prereg": {"path": relative_path(ROOT / "computations" / "matter-formation-parent-spatial-prereg.md"), "sha256": canonical_sha256(ROOT / "computations" / "matter-formation-parent-spatial-prereg.md")},
    }
    _check_identity_map(result, "spatial results", expected)
    _check_identity_map(verification, "spatial verification", expected)
    selected = _row(result, SOURCE_ID, "spatial results")
    selected_v = _row(verification, SOURCE_ID, "spatial verification")
    expected_artifact = relative_path(ROOT / "runs" / "20260906_matter_formation_radial" / f"{SOURCE_ID}.npz")
    for item, label in ((selected, "spatial primary row"), (selected_v, "spatial verifier row")):
        if item.get("artifact") != expected_artifact or item.get("artifact_sha256") != SOURCE_HASH or item.get("R") != 12.0 or item.get("n") != 768 or item.get("source_qualified") is not True or item.get("sector_verdict") != "SUPPORTS—finite-grid scalar angular and phase energetic qualification":
            raise ContractError(f"{label} selected-row inheritance mismatch")
    for key in ("omega_C", "population", "population_relative_error", "residual_f", "residual_c"):
        if not close_value(finite_scalar(selected[key], f"spatial {key}"), finite_scalar(selected_v[key], f"spatial verifier {key}")):
            raise ContractError(f"spatial selected-row disagreement: {key}")
    if result.get("parent_verdict") != SPATIAL_PARENT_VERDICT or verification.get("parent_verdict") != SPATIAL_PARENT_VERDICT:
        raise ContractError("spatial parent verdict changed")
    comparisons = result.get("comparisons")
    if not isinstance(comparisons, list):
        raise ContractError("spatial comparisons missing")
    accepted = [item for item in comparisons if isinstance(item, Mapping) and item.get("metric") == "amp1_gap" and item.get("pair") == "domain" and item.get("left") == "q256_R12_n384_refine" and item.get("right") == "q256_R24_n768_refine"]
    if len(accepted) != 1 or accepted[0].get("pass") is not False:
        raise ContractError("accepted amp1 domain comparison missing or changed")
    return result, verification, selected, selected_v


def load_source(source_dir: Path, selected: Mapping[str, Any]) -> dict[str, Any]:
    path = source_dir / f"{SOURCE_ID}.npz"
    if not path.is_file():
        raise ContractError(f"missing source artifact {path}")
    actual = raw_sha256(path)
    if actual != SOURCE_HASH:
        raise ContractError(f"source byte hash mismatch: {actual}")
    with np.load(path, allow_pickle=False) as archive:
        if set(archive.files) != {"r", "volumes", "f", "c", "R", "q"}:
            raise ContractError("source schema mismatch")
        if any(archive[key].dtype != np.dtype("float64") for key in ("r", "volumes", "f", "c")):
            raise ContractError("source dtype mismatch")
        arrays = {key: np.asarray(archive[key], dtype=np.float64) for key in archive.files}
    r, volumes, f, c = (arrays[name] for name in ("r", "volumes", "f", "c"))
    R, q = finite_scalar(arrays["R"], "source R"), finite_scalar(arrays["q"], "source q")
    if any(array.ndim != 1 for array in (r, volumes, f, c)) or not (r.size == volumes.size == f.size == c.size == 768):
        raise ContractError("source radial vector shape mismatch")
    if R != finite_scalar(selected["R"], "selected R") or q != 256.0:
        raise ContractError("source geometry metadata mismatch")
    dr = R / r.size
    faces = np.arange(r.size + 1, dtype=np.float64) * dr
    expected_r = (np.arange(r.size, dtype=np.float64) + 0.5) * dr
    expected_volumes = (4.0 * math.pi / 3.0) * (faces[1:] ** 3 - faces[:-1] ** 3)
    if not np.all(np.isfinite(r)) or not np.all(np.isfinite(volumes)) or not np.all(np.isfinite(f)) or not np.all(np.isfinite(c)):
        raise ContractError("source contains nonfinite values")
    if not np.allclose(r, expected_r, rtol=2.0e-13, atol=2.0e-15) or not np.allclose(volumes, expected_volumes, rtol=2.0e-13, atol=2.0e-15):
        raise ContractError("source geometry is not exact spherical cell geometry")
    if np.any(f < 0.0) or np.any(c < 0.0):
        raise ContractError("source amplitudes are negative")
    return {"path": path, "artifact_sha256": actual, "r": r, "volumes": volumes, "f": f, "c": c, "R": R, "q": q, "n": int(r.size), "dr": dr, "faces": faces}


def profile_measurements(source: Mapping[str, Any], omega_inherited: float) -> dict[str, float]:
    f, c, V, faces = source["f"], source["c"], source["volumes"], source["faces"]
    dr, R, n = float(source["dr"]), float(source["R"]), int(source["n"])
    interior = 4.0 * math.pi * faces[1:-1] ** 2 / dr
    outer = 8.0 * math.pi * R * R / dr
    jf, jc = np.diff(f), np.diff(c)
    gradient_f = 0.5 * (float(np.dot(interior, jf * jf)) + outer * (1.0 - f[-1]) ** 2)
    gradient_c = 0.5 * COEFFICIENTS["k_Cx"] * (float(np.dot(interior, jc * jc)) + outer * c[-1] ** 2)
    gradient = gradient_f + gradient_c
    rho = f * f - 1.0
    carrier_potential = COEFFICIENTS["e_C"] - COEFFICIENTS["h_C"] * (1.0 - f * f)
    potential_density = COEFFICIENTS["u_rho"] / 4.0 * rho * rho + carrier_potential * c * c + COEFFICIENTS["u_C"] / 2.0 * c ** 4
    potential = float(np.dot(V, potential_density))
    N = float(np.dot(V, c * c))
    if not math.isfinite(N) or N <= 0.0:
        raise ContractError("nonpositive source population")
    # Finite-volume gradient of the static functional, including the outer loads.
    kc = np.zeros(n, dtype=np.float64)
    if n > 1:
        flux = interior * (c[:-1] - c[1:])
        kc[:-1] += flux
        kc[1:] -= flux
    kc[-1] += outer * c[-1]
    gc = COEFFICIENTS["k_Cx"] * kc + V * (2.0 * carrier_potential * c + 2.0 * COEFFICIENTS["u_C"] * c ** 3)
    omega_calc = float(np.dot(c, gc) / (2.0 * N))
    if not close_value(omega_calc, omega_inherited):
        raise ContractError("selected stationary multiplier does not match source profile")
    values = {"R": R, "n": n, "N": N, "omega_C": omega_inherited, "static_energy": gradient + potential, "gradient_energy": gradient}
    require_finite(values, "source summary")
    return values


def ell_for_a(a: float, lambda_target: float) -> float:
    return lambda_target * math.sqrt((1.0 / (2.0 * a) + 2.0 * COEFFICIENTS["e_C"]) / COEFFICIENTS["k_Cx"])


def unit_family(a: float, summary: Mapping[str, float], constants: Mapping[str, Any]) -> dict[str, float]:
    omega_C, N, Esc = float(summary["omega_C"]), float(summary["N"]), float(summary["static_energy"])
    c_speed, hbar, MeV_J, target_MeV, Mpl_MeV, phi = (constants[name] for name in ("c_m_s", "hbar_J_s", "MeV_J", "target_energy_MeV", "planck_energy_MeV", "varphi"))
    target_J = target_MeV * MeV_J
    lambda_target = hbar * c_speed / target_J
    D = 1.0 + 4.0 * a * omega_C
    if D <= 0.0:
        raise ContractError(f"nonpositive canonical discriminant at a={a}")
    Omega = math.sqrt(D) / (2.0 * a)
    exterior_mass = math.sqrt(1.0 / (4.0 * a * a) + COEFFICIENTS["e_C"] / a)
    omega = Omega - 1.0 / (2.0 * a)
    charge = math.sqrt(D) * N
    N_Q = 1.0 / charge
    ell_Q = ell_for_a(a, lambda_target)
    t_Q = ell_Q / c_speed * math.sqrt(COEFFICIENTS["k_Cx"] / (2.0 * a))
    K_x = hbar * ell_Q * ell_Q / t_Q
    rho_0 = N_Q / ell_Q ** 3
    E_Q = hbar * N_Q / t_Q
    ell_tail = ell_Q * math.sqrt(COEFFICIENTS["k_Cx"] / (2.0 * (COEFFICIENTS["e_C"] - omega_C)))
    H_original = Esc + a * omega * omega * N
    H_canonical = Esc + (1.0 / (2.0 * a) + omega_C) * N
    canonical_energy = E_Q * H_canonical
    mass_residual = abs(hbar * exterior_mass / (t_Q * target_J) - 1.0)
    speed_residual = abs(ell_Q * math.sqrt(COEFFICIENTS["k_Cx"] / (2.0 * a)) / (c_speed * t_Q) - 1.0)
    charge_residual = abs(N_Q * charge - 1.0)
    shift = charge / (2.0 * a)
    energy_shift_residual = abs(H_canonical - H_original - shift) / max(1.0, abs(H_canonical), abs(H_original), abs(shift))
    chemical_energy_residual = abs(H_canonical - Omega * charge - Esc + omega_C * N) / max(1.0, abs(H_canonical), abs(Omega * charge), abs(Esc), abs(omega_C * N))
    row = {"a": a, "D": D, "charge": charge, "N_Q": N_Q, "ell_Q_m": ell_Q, "t_Q_s": t_Q, "K_x": K_x, "rho_0": rho_0, "E_Q_J": E_Q, "ell_tail_m": ell_tail, "canonical_frequency": Omega, "exterior_mass": exterior_mass, "original_frequency": omega, "H_original": H_original, "H_canonical": H_canonical, "canonical_energy_over_target": canonical_energy / target_J, "mass_residual": mass_residual, "speed_residual": speed_residual, "charge_residual": charge_residual, "energy_shift_residual": energy_shift_residual, "chemical_energy_residual": chemical_energy_residual}
    require_finite(row, f"unit family {a}")
    if any(row[name] >= 1.0e-10 for name in ("mass_residual", "speed_residual", "charge_residual", "energy_shift_residual", "chemical_energy_residual")):
        raise ContractError(f"normalization identity residual at a={a}")
    return row


def core_assignment(constants: Mapping[str, Any]) -> dict[str, float]:
    c_speed, hbar, MeV_J, target_MeV, Mpl_MeV, phi = (constants[name] for name in ("c_m_s", "hbar_J_s", "MeV_J", "target_energy_MeV", "planck_energy_MeV", "varphi"))
    lambda_target = hbar * c_speed / (target_MeV * MeV_J)
    s = math.sqrt(COEFFICIENTS["u_rho"] * COEFFICIENTS["u_C"] / 2.0)
    a_depleted = 1.0 / (4.0 * (COEFFICIENTS["h_C"] - COEFFICIENTS["e_C"]))
    a_vacuum = 1.0 / (4.0 * (COEFFICIENTS["h_C"] - COEFFICIENTS["e_C"] - s))
    cell_lower = hbar * c_speed / (Mpl_MeV * MeV_J * phi ** (-107))
    cell_upper = hbar * c_speed / (Mpl_MeV * MeV_J * phi ** (-108))
    base = hbar * c_speed / (Mpl_MeV * MeV_J)
    minimum = ell_for_a(a_vacuum, lambda_target)
    result = {"a_depleted": a_depleted, "a_vacuum": a_vacuum, "lambda_target_m": lambda_target, "target_cascade_coordinate": math.log(Mpl_MeV / target_MeV, phi), "cell_lower_m": cell_lower, "cell_upper_m": cell_upper, "exact_core_root_denominator": 2.0 * (COEFFICIENTS["k_Cx"] - 2.0 * COEFFICIENTS["e_C"]), "minimum_core_length_m": minimum, "minimum_core_cascade_coordinate": math.log(minimum / base, phi)}
    require_finite(result, "core assignment")
    return result


def unit_rescaling(spatial_result: Mapping[str, Any], left_row: Mapping[str, Any], right_row: Mapping[str, Any]) -> dict[str, Any]:
    comparisons = spatial_result.get("comparisons", [])
    comparison = next(item for item in comparisons if item.get("metric") == "amp1_gap" and item.get("pair") == "domain" and item.get("left") == "q256_R12_n384_refine" and item.get("right") == "q256_R24_n768_refine")
    difference = abs(float(left_row["metrics"]["amp1_gap"]) - float(right_row["metrics"]["amp1_gap"]))
    tolerance = float(comparison["tolerance"])
    if not (close_value(float(comparison["absolute_difference"]), difference) and math.isfinite(tolerance) and tolerance > 0.0):
        raise ContractError("accepted amp1 comparison endpoints disagree")
    ratio = difference / tolerance
    rows = []
    for factor in (1.0e-12, 1.0, 1.0e12):
        scaled_difference, scaled_tolerance = difference * factor, tolerance * factor
        rows.append({"factor": factor, "ratio": scaled_difference / scaled_tolerance, "pass": bool(scaled_difference <= scaled_tolerance)})
    result = {"comparison": dict(comparison), "rows": rows}
    require_finite(result, "unit rescaling")
    if not all(item["pass"] is False for item in rows):
        raise ContractError("unit-rescaling decision changed")
    if not close_value(ratio, rows[0]["ratio"]):
        raise ContractError("unit-rescaling ratio mismatch")
    return result


def pair(value: complex) -> list[float]:
    return [float(value.real), float(value.imag)]


def dirac_payload(phi: float) -> dict[str, Any]:
    identity2 = np.eye(2, dtype=np.complex128)
    zero2 = np.zeros((2, 2), dtype=np.complex128)
    gamma0 = np.block([[zero2, identity2], [identity2, zero2]])
    gamma5 = np.block([[-identity2, zero2], [zero2, identity2]])
    PR, PL = (np.eye(4, dtype=np.complex128) + gamma5) / 2.0, (np.eye(4, dtype=np.complex128) - gamma5) / 2.0
    adjoint_residual = float(np.max(np.abs((gamma0 @ PR).conj().T - gamma0 @ PL)))
    if adjoint_residual >= 1.0e-10:
        raise ContractError("chiral-scalar adjoint identity failed")
    witnesses = (("complex", (1.0 + 0j, 0j, 1j, 0j)), ("negative", (1.0 + 0j, 0j, -1.0 + 0j, 0j)), ("equal_positive", (1.0 + 0j, 0j, 1.0 + 0j, 0j)), ("pure_left", (1.0 + 0j, 0j, 0j, 0j)), ("positive_frame_ratio", (1.0 + 0j, 0j, math.sqrt(phi) + 0j, 0j)))
    rows = []
    for identifier, values in witnesses:
        psi = np.asarray(values, dtype=np.complex128)
        BR = np.vdot(psi, gamma0 @ PR @ psi)
        BL = np.vdot(psi, gamma0 @ PL @ psi)
        L, R = psi[:2], psi[2:]
        rows.append({"id": identifier, "B_R": pair(BR), "B_L": pair(BL), "n_R": float(np.vdot(R, R).real), "n_L": float(np.vdot(L, L).real)})
    complex_row = rows[0]
    BR = complex(complex_row["B_R"][0], complex_row["B_R"][1])
    BL = complex(complex_row["B_L"][0], complex_row["B_L"][1])
    linear = phi * BR + BL
    squared = ((BR - phi) ** 2 + (BL - 1.0) ** 2) / 2.0
    result = {"convention": "Weyl; gamma5=(-I2,+I2); psi=(L,R)", "witnesses": rows, "adjoint_residual": adjoint_residual, "golden_ratio_determinant": 1.0 - phi * phi, "linear_interaction": pair(linear), "squared_interaction": pair(squared), "scalar_rotation_phase": 1.0, "dirac_rotation_phase": -1.0}
    require_finite(result, "dirac")
    return result


def failed_receipt(ids: Mapping[str, Any], inherited: Mapping[str, Any], source_path: Path, failures: list[str]) -> dict[str, Any]:
    return {"schema": SCHEMA, "identities": ids, "inherited_spatial": inherited, "source": {"path": relative_path(source_path), "sha256": "", "id": SOURCE_ID}, "constants": {"c_m_s": 299792458.0, "hbar_J_s": 1.054571817e-34, "MeV_J": 1.602176634e-13, "target_energy_MeV": 0.511, "planck_energy_MeV": 1.2209e22, "varphi": (1.0 + math.sqrt(5.0)) / 2.0, "coefficients": dict(COEFFICIENTS)}, "source_summary": {}, "unit_family": [], "core_assignment": {}, "unit_rescaling": {}, "dirac": {}, "verdicts": {"normalization": INCONCLUSIVE, "core_assignment": INCONCLUSIVE, "density_identification": INCONCLUSIVE, "projection_action": INCONCLUSIVE, "spatial_parent": INCONCLUSIVE}, "numerical_pass": False, "failures": failures}


def run(source_dir: Path = DEFAULT_SOURCE_DIR, spatial_dir: Path = DEFAULT_SPATIAL_DIR, output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    source_dir, spatial_dir, output_dir = source_dir.resolve(), spatial_dir.resolve(), output_dir.resolve()
    output_path = output_dir / "results.json"
    if output_path.exists() or output_path.with_name(output_path.name + ".tmp").exists():
        raise FileExistsError(f"refusing existing receipt or temporary artifact: {output_path}")
    failures: list[str] = []
    ids = identities(failures)
    inherited = {"results": {"path": relative_path(spatial_dir / "results.json"), "sha256": SPATIAL_RESULTS_HASH}, "verification": {"path": relative_path(spatial_dir / "verification.json"), "sha256": SPATIAL_VERIFICATION_HASH}}
    source_path = source_dir / f"{SOURCE_ID}.npz"
    receipt = failed_receipt(ids, inherited, source_path, failures)
    try:
        spatial_result, spatial_verify, selected, selected_v = validate_spatial(spatial_dir, failures)
        source = load_source(source_dir, selected)
        actual_source = source["artifact_sha256"]
        receipt["source"]["sha256"] = actual_source
        constants = receipt["constants"]
        summary = profile_measurements(source, finite_scalar(selected["omega_C"], "omega_C"))
        if not close_value(summary["N"], finite_scalar(selected["population"], "inherited population")):
            raise ContractError("recomputed population disagrees with inherited profile")
        core = core_assignment(constants)
        if not all(0.0 < a <= core["a_vacuum"] and a <= core["a_depleted"] for a in A_VALUES):
            raise ContractError("normalization schedule exceeds fixed coefficient bounds")
        families = [unit_family(a, summary, constants) for a in A_VALUES]
        left = _row(spatial_result, "q256_R12_n384_refine", "spatial results")
        right = _row(spatial_result, "q256_R24_n768_refine", "spatial results")
        rescaling = unit_rescaling(spatial_result, left, right)
        dirac = dirac_payload(constants["varphi"])
        if len(families) != 3 or len({item["ell_Q_m"] for item in families}) != 3:
            raise ContractError("normalization witnesses are not distinct")
        normalization_ok = all(max(item[name] for name in ("mass_residual", "speed_residual", "charge_residual")) < 1.0e-10 for item in families)
        if not normalization_ok:
            raise ContractError("normalization witness failed")
        diff = COEFFICIENTS["k_Cx"] - 2.0 * COEFFICIENTS["e_C"]
        core_verdict = "CONTRADICTS—selected scalar electron-core assignment" if diff <= 0.0 and core["minimum_core_length_m"] > core["cell_upper_m"] else "INCONCLUSIVE—selected scalar electron-core assignment"
        density_verdict = "CONTRADICTS—chiral-scalar nonnegative-density identification" if any(abs(row["B_R"][1]) > 1.0e-10 or abs(row["B_L"][1]) > 1.0e-10 for row in dirac["witnesses"]) and any(row["B_R"][0] < 0.0 or row["B_L"][0] < 0.0 for row in dirac["witnesses"]) and abs(dirac["golden_ratio_determinant"]) > 1.0e-10 else "INCONCLUSIVE—chiral-scalar density identification"
        projection_verdict = "CONTRADICTS—displayed chiral projection interaction as a physical real action" if abs(dirac["linear_interaction"][1]) > 1.0e-10 or abs(dirac["squared_interaction"][1]) > 1.0e-10 else "INCONCLUSIVE—chiral projection action"
        payload = {"source_summary": summary, "unit_family": families, "core_assignment": core, "unit_rescaling": rescaling, "dirac": dirac, "verdicts": {"normalization": "SUPPORTS—conditional one-mass normalization nonuniqueness", "core_assignment": core_verdict, "density_identification": density_verdict, "projection_action": projection_verdict, "spatial_parent": SPATIAL_PARENT_VERDICT}}
        require_finite(payload, "successful payload")
        receipt.update(payload)
        receipt["numerical_pass"] = not failures
    except Exception as exc:
        failures.append(f"{type(exc).__name__}: {exc}")
        receipt = failed_receipt(ids, inherited, source_path, failures)
    receipt["failures"] = failures
    receipt["numerical_pass"] = bool(receipt["numerical_pass"] and not failures)
    if not receipt["numerical_pass"]:
        receipt["source_summary"], receipt["unit_family"], receipt["core_assignment"], receipt["unit_rescaling"], receipt["dirac"] = {}, [], {}, {}, {}
        receipt["verdicts"] = {key: INCONCLUSIVE for key in ("normalization", "core_assignment", "density_identification", "projection_action", "spatial_parent")}
    write_json_exclusive(output_path, receipt)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--spatial-dir", type=Path, default=DEFAULT_SPATIAL_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    try:
        receipt = run(args.source_dir, args.spatial_dir, args.output_dir)
    except Exception as exc:
        print(f"normalization failed before receipt: {type(exc).__name__}: {exc}")
        return 1
    print(json.dumps({"numerical_pass": receipt["numerical_pass"], "failures": receipt["failures"], "verdicts": receipt["verdicts"]}, sort_keys=True))
    return 0 if receipt["numerical_pass"] else 1

if __name__ == "__main__":
    raise SystemExit(main())
