#!/usr/bin/env python3
"""Independent verifier for the preregistered physical normalization calculation."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SELF_PATH = Path(__file__).resolve()
PREREG_PATH = ROOT / "computations" / "matter-formation-normalization-prereg.md"
DEFAULT_SOURCE_DIR = ROOT / "runs" / "20260906_matter_formation_radial"
DEFAULT_SPATIAL_DIR = ROOT / "runs" / "20260906_matter_formation_parent_spatial"
DEFAULT_OUTPUT_DIR = ROOT / "runs" / "20260906_matter_formation_normalization"
SCHEMA = "cassi.matter-formation.normalization.v1"
VERIFY_SCHEMA = "cassi.matter-formation.normalization.verification.v1"
SOURCE_ID = "q256_R12_n768_refine"
SOURCE_HASH = "95df301fcea98304434b95e9dd63a9cec987495ddda9af46e5940891672dc77a"
SPATIAL_RESULTS_HASH = "9445ff33b33b664bf15e09b499bb185f18bfeb9f8a9393c388afef7c7affa79c"
SPATIAL_VERIFY_HASH = "2994e44ee2566ecc4e7ce660dc5d0510a088b694e0224086792eda2854f148dd"
SPATIAL_SCHEMA = "cassi.matter-formation.parent-spatial.v1"
SPATIAL_VERIFY_SCHEMA = "cassi.matter-formation.parent-spatial.verification.v1"
COEFFICIENTS = {"u_rho": 4.0, "u_C": 1.0, "k_Cx": 1.0, "e_C": 0.75, "h_C": 2.9598260763447164}
A_VALUES = (1.0 / 64.0, 1.0 / 32.0, 1.0 / 16.0)
RAW_KEYS = ("r", "volumes", "f", "c", "R", "q")
C = 299792458.0
HBAR = 1.054571817e-34
MEV_J = 1.602176634e-13
TARGET_MEV = 0.511
PLANCK_MEV = 1.2209e22
PHI = (1.0 + math.sqrt(5.0)) / 2.0
NUM_TOL = 1.0e-10
RESIDUAL_TOL = 1.0e-10


def raw_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def canonical_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def relpath(path: Path) -> str:
    try:
        return os.path.relpath(path.resolve(), ROOT.resolve()).replace("\\", "/")
    except ValueError:
        return str(path.resolve()).replace("\\", "/")


def finite(value: Any) -> bool:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, float, np.number)):
        return False
    return math.isfinite(float(value))


def finite_tree(value: Any) -> bool:
    if isinstance(value, Mapping):
        return all(isinstance(k, str) and finite_tree(v) for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return all(finite_tree(v) for v in value)
    if isinstance(value, (int, float, np.number)) and not isinstance(value, (bool, np.bool_)):
        return math.isfinite(float(value))
    return True


def close(a: Any, b: Any, factor: float = NUM_TOL) -> bool:
    return finite(a) and finite(b) and abs(float(a) - float(b)) <= factor * max(1.0, abs(float(a)), abs(float(b)))


def physical_close(a: Any, b: Any) -> bool:
    return finite(a) and finite(b) and abs(float(a) - float(b)) <= NUM_TOL * max(abs(float(a)), abs(float(b)), 1.0e-300)


def json_load(path: Path) -> Any:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return json.load(stream)


def identity(path: Path) -> dict[str, str]:
    return {"path": relpath(path), "sha256": canonical_sha256(path) if path.suffix in {".py", ".md"} else raw_sha256(path)}


def write_exclusive(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    if path.exists() or tmp.exists():
        raise FileExistsError(f"refusing existing receipt or temporary file: {path}")
    created = False
    try:
        with tmp.open("x", encoding="utf-8", newline="\n") as stream:
            created = True
            json.dump(payload, stream, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
        os.replace(tmp, path)
    except Exception:
        if created:
            tmp.unlink(missing_ok=True)
        raise


def empty_payload(ids: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {
        "schema": VERIFY_SCHEMA,
        "identities": dict(ids or {}),
        "inherited_spatial": {},
        "source": {},
        "constants": {},
        "source_summary": {},
        "unit_family": [],
        "core_assignment": {},
        "unit_rescaling": {},
        "dirac": {},
        "verdicts": {
            "normalization": "INCONCLUSIVE",
            "core_assignment": "INCONCLUSIVE",
            "density_identification": "INCONCLUSIVE",
            "projection_action": "INCONCLUSIVE",
            "spatial_parent": "INCONCLUSIVE",
        },
        "numerical_pass": False,
        "failures": [],
        "input_sha256": "",
        "independent_checks": {},
    }


def finish_receipt(receipt: dict[str, Any], failures: list[str], path: Path) -> tuple[dict[str, Any], int]:
    if not finite_tree(receipt):
        failures.append("nonfinite independent numerical payload")
    receipt["failures"] = failures
    receipt["numerical_pass"] = not failures
    if failures:
        for key in ("source_summary", "core_assignment", "unit_rescaling", "dirac"):
            receipt[key] = {}
        receipt["unit_family"] = []
        receipt["verdicts"] = {key: "INCONCLUSIVE" for key in receipt["verdicts"]}
    write_exclusive(path, receipt)
    return receipt, 0 if receipt["numerical_pass"] else 1


def expected_geometry(R: float, n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    dr = R / n
    faces = np.arange(n + 1, dtype=np.float64) * dr
    r = (np.arange(n, dtype=np.float64) + 0.5) * dr
    volumes = (4.0 * math.pi / 3.0) * (faces[1:] ** 3 - faces[:-1] ** 3)
    conductance = 4.0 * math.pi * faces[1:-1] ** 2 / dr
    return r, volumes, faces, conductance


def load_selected_source(source_dir: Path, selected_row: Mapping[str, Any], failures: list[str]) -> dict[str, Any] | None:
    path = source_dir / f"{SOURCE_ID}.npz"
    if not path.is_file():
        fail_msg = f"missing source artifact: {path}"
        failures.append(fail_msg)
        return None
    actual = raw_sha256(path)
    if actual != SOURCE_HASH:
        failures.append(f"source byte hash mismatch: {actual}")
    try:
        archive = np.load(path, allow_pickle=False)
        with archive:
            if set(archive.files) != set(RAW_KEYS):
                failures.append("source NPZ keys mismatch")
                return None
            arrays = {key: archive[key] for key in RAW_KEYS}
            for key in RAW_KEYS[:4]:
                if arrays[key].dtype != np.dtype("float64") or arrays[key].ndim != 1:
                    failures.append(f"source array dtype/shape mismatch: {key}")
            if arrays["R"].ndim != 0 or arrays["q"].ndim != 0:
                failures.append("source scalar shape mismatch")
            r, volumes, faces, conductance = expected_geometry(12.0, 768)
            if any(arrays[k].shape != (768,) for k in RAW_KEYS[:4]):
                failures.append("source vector length mismatch")
                return None
            for key, expected in (("r", r), ("volumes", volumes)):
                if not np.allclose(arrays[key], expected, rtol=2e-13, atol=2e-15):
                    failures.append(f"source geometry mismatch: {key}")
            if not finite(float(arrays["R"])) or float(arrays["R"]) != 12.0:
                failures.append("source radius mismatch")
            if not finite(float(arrays["q"])) or float(arrays["q"]) != 256.0:
                failures.append("source population metadata mismatch")
            for key in RAW_KEYS[:4]:
                if not np.all(np.isfinite(arrays[key])):
                    failures.append(f"nonfinite source array: {key}")
            if not np.all(np.asarray(arrays["f"]) >= 0.0) or not np.all(np.asarray(arrays["c"]) >= 0.0):
                failures.append("negative source profile sample")
            if not close(float(selected_row.get("R", math.nan)), 12.0) or int(selected_row.get("n", -1)) != 768:
                failures.append("selected spatial geometry mismatch")
            if selected_row.get("id") != SOURCE_ID or selected_row.get("artifact_sha256") != SOURCE_HASH:
                failures.append("selected spatial source identity mismatch")
            return {"path": path, "sha256": actual, "r": np.asarray(arrays["r"], dtype=np.float64), "volumes": np.asarray(arrays["volumes"], dtype=np.float64), "f": np.asarray(arrays["f"], dtype=np.float64), "c": np.asarray(arrays["c"], dtype=np.float64), "R": 12.0, "n": 768, "q": 256.0, "faces": faces, "conductance": conductance}
    except Exception as exc:
        failures.append(f"source load failure: {exc}")
        return None


def load_spatial(spatial_dir: Path, failures: list[str]) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any]]:
    results_path, verify_path = spatial_dir / "results.json", spatial_dir / "verification.json"
    meta = {"results": {"path": relpath(results_path), "sha256": ""}, "verification": {"path": relpath(verify_path), "sha256": ""}}
    if not results_path.is_file() or not verify_path.is_file():
        failures.append("missing inherited spatial receipt")
        return None, None, meta
    meta["results"]["sha256"] = raw_sha256(results_path)
    meta["verification"]["sha256"] = raw_sha256(verify_path)
    if meta["results"]["sha256"] != SPATIAL_RESULTS_HASH:
        failures.append("inherited spatial results hash mismatch")
    if meta["verification"]["sha256"] != SPATIAL_VERIFY_HASH:
        failures.append("inherited spatial verification hash mismatch")
    try:
        primary, verifier = json_load(results_path), json_load(verify_path)
    except Exception as exc:
        failures.append(f"inherited spatial JSON failure: {exc}")
        return None, None, meta
    if not isinstance(primary, dict) or not isinstance(verifier, dict):
        failures.append("inherited spatial receipts are not objects")
        return None, None, meta
    if primary.get("schema") != SPATIAL_SCHEMA or verifier.get("schema") != SPATIAL_VERIFY_SCHEMA:
        failures.append("inherited spatial schema mismatch")
    if primary.get("coefficients") != COEFFICIENTS or verifier.get("coefficients") != COEFFICIENTS:
        failures.append("inherited spatial coefficient mismatch")
    if primary.get("numerical_pass") is not True or verifier.get("numerical_pass") is not True:
        failures.append("inherited spatial numerical failure")
    if primary.get("failures") != [] or verifier.get("failures") != []:
        failures.append("inherited spatial failures are nonempty")
    if verifier.get("input_sha256") != SPATIAL_RESULTS_HASH:
        failures.append("inherited spatial primary linkage mismatch")
    current_prereg = canonical_sha256(ROOT / "computations/matter-formation-parent-spatial-prereg.md")
    current_primary = canonical_sha256(ROOT / "computations/matter_formation_parent_spatial.py")
    current_verifier = canonical_sha256(ROOT / "computations/verify_matter_formation_parent_spatial.py")
    ids = verifier.get("identities", {})
    pids = primary.get("identities", {})
    for label, item in (("primary", pids), ("verifier", ids)):
        if not isinstance(item, dict) or item.get("prereg", {}).get("sha256") != current_prereg or item.get("primary", {}).get("sha256") != current_primary or item.get("verifier", {}).get("sha256") != current_verifier:
            failures.append(f"inherited spatial canonical identities mismatch: {label}")
        if not isinstance(item, dict) or item.get("prereg", {}).get("path") != "computations/matter-formation-parent-spatial-prereg.md" or item.get("primary", {}).get("path") != "computations/matter_formation_parent_spatial.py" or item.get("verifier", {}).get("path") != "computations/verify_matter_formation_parent_spatial.py":
            failures.append(f"inherited spatial identity paths mismatch: {label}")
    rows = primary.get("rows")
    row = next((item for item in rows if isinstance(item, dict) and item.get("id") == SOURCE_ID), None) if isinstance(rows, list) else None
    vrows = verifier.get("rows")
    vrow = next((item for item in vrows if isinstance(item, dict) and item.get("id") == SOURCE_ID), None) if isinstance(vrows, list) else None
    if row is None or vrow is None:
        failures.append("selected spatial row missing")
    if isinstance(row, dict) and isinstance(vrow, dict):
        for candidate in (row, vrow):
            if candidate.get("source_qualified") is not True or candidate.get("sector_verdict") != "SUPPORTS—finite-grid scalar angular and phase energetic qualification":
                failures.append("selected spatial source qualification mismatch")
        if float(row.get("R", math.nan)) != 12.0 or int(row.get("n", -1)) != 768 or row.get("artifact") != "runs/20260906_matter_formation_radial/q256_R12_n768_refine.npz" or row.get("artifact_sha256") != SOURCE_HASH:
            failures.append("selected spatial primary geometry/path/hash mismatch")
        if float(vrow.get("R", math.nan)) != 12.0 or int(vrow.get("n", -1)) != 768 or vrow.get("artifact") != "runs/20260906_matter_formation_radial/q256_R12_n768_refine.npz":
            failures.append("selected spatial verifier geometry/path mismatch")
        if vrow.get("id") != SOURCE_ID or vrow.get("artifact_sha256") != SOURCE_HASH:
            failures.append("selected spatial verifier row identity mismatch")
        if not finite(vrow.get("omega_C")) or not finite(row.get("omega_C")):
            failures.append("selected spatial omega_C missing or nonfinite")
        if not close(row.get("omega_C"), vrow.get("omega_C")):
            failures.append("selected spatial omega_C linkage mismatch")
        if primary.get("parent_verdict") != "INCONCLUSIVE—finite-grid scalar parent spatial energetic qualification" or verifier.get("parent_verdict") != "INCONCLUSIVE—finite-grid scalar parent spatial energetic qualification":
            failures.append("selected spatial parent verdict mismatch")
    return primary, verifier, meta


def static_energy(source: Mapping[str, Any]) -> tuple[float, float, float]:
    f, c, V, faces, conductance = source["f"], source["c"], source["volumes"], source["faces"], source["conductance"]
    dr, R = source["R"] / source["n"], source["R"]
    gradient_terms = [0.5 * float(g) * ((float(f[i + 1]) - float(f[i])) ** 2 + COEFFICIENTS["k_Cx"] * (float(c[i + 1]) - float(c[i])) ** 2) for i, g in enumerate(conductance)]
    outer = 0.5 * (8.0 * math.pi * R * R / dr) * ((float(f[-1]) - 1.0) ** 2 + COEFFICIENTS["k_Cx"] * float(c[-1]) ** 2)
    gradient = math.fsum(gradient_terms) + outer
    local = []
    for i in range(source["n"]):
        rho = float(f[i]) ** 2 - 1.0
        A = COEFFICIENTS["e_C"] - COEFFICIENTS["h_C"] * (1.0 - float(f[i]) ** 2)
        density = COEFFICIENTS["u_rho"] / 4.0 * rho * rho + A * float(c[i]) ** 2 + COEFFICIENTS["u_C"] / 2.0 * float(c[i]) ** 4
        local.append(float(V[i]) * density)
    return float(math.fsum(local) + gradient), float(gradient), float(math.fsum(local))


def complex_pair(z: complex) -> list[float]:
    return [float(z.real), float(z.imag)]


def dirac_payload() -> dict[str, Any]:
    witnesses = [
        ("complex", (1.0 + 0j, 0j), (1j, 0j)),
        ("negative", (1.0 + 0j, 0j), (-1.0 + 0j, 0j)),
        ("equal_positive", (1.0 + 0j, 0j), (1.0 + 0j, 0j)),
        ("pure_left", (1.0 + 0j, 0j), (0j, 0j)),
        ("positive_frame_ratio", (1.0 + 0j, 0j), (math.sqrt(PHI) + 0j, 0j)),
    ]
    rows = []
    for ident, L, R in witnesses:
        br = sum(l.conjugate() * r for l, r in zip(L, R))
        bl = sum(r.conjugate() * l for l, r in zip(L, R))
        nr = math.fsum(abs(r) ** 2 for r in R)
        nl = math.fsum(abs(l) ** 2 for l in L)
        rows.append({"id": ident, "B_R": complex_pair(br), "B_L": complex_pair(bl), "n_R": nr, "n_L": nl})
    basis = [tuple(complex(i == j) for j in range(4)) for i in range(4)]
    adjoint_residual = 0.0
    for left in basis:
        for right in basis:
            br_reverse = sum(right[j].conjugate() * left[j + 2] for j in range(2))
            bl_forward = sum(left[j + 2].conjugate() * right[j] for j in range(2))
            adjoint_residual = max(adjoint_residual, abs(br_reverse.conjugate() - bl_forward))
    br = complex(*rows[0]["B_R"])
    bl = complex(*rows[0]["B_L"])
    return {
        "convention": "Weyl; gamma5=(-I2,+I2); psi=(L,R)",
        "witnesses": rows,
        "adjoint_residual": adjoint_residual,
        "golden_ratio_determinant": 1.0 - PHI * PHI,
        "linear_interaction": complex_pair(PHI * br + bl),
        "squared_interaction": complex_pair(0.5 * ((br - PHI) ** 2 + (bl - 1.0) ** 2)),
        "scalar_rotation_phase": math.cos(0.0),
        "dirac_rotation_phase": math.cos(math.pi),
    }


def compare_recursive(actual: Any, expected: Any, path: str, failures: list[str], physical: bool = False) -> None:
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(actual) != set(expected):
            failures.append(f"primary payload keys mismatch: {path}")
            return
        for key in expected:
            compare_recursive(actual[key], expected[key], f"{path}.{key}", failures, physical or key in {"ell_Q_m", "t_Q_s", "K_x", "rho_0", "E_Q_J", "ell_tail_m", "lambda_target_m", "cell_lower_m", "cell_upper_m", "minimum_core_length_m", "hbar_J_s", "MeV_J", "target_energy_MeV", "planck_energy_MeV", "factor"})
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            failures.append(f"primary payload length mismatch: {path}")
            return
        for i, value in enumerate(expected):
            compare_recursive(actual[i], value, f"{path}[{i}]", failures, physical)
    elif isinstance(expected, (bool, int, str)) or expected is None:
        if type(actual) is not type(expected) or actual != expected:
            failures.append(f"primary payload mismatch: {path}")
    elif finite(expected):
        if not (physical_close(actual, expected) if physical else close(actual, expected)):
            failures.append(f"primary numeric mismatch: {path}")
    else:
        failures.append(f"nonfinite expected primary value: {path}")


def run(input_dir: Path, source_dir: Path, spatial_dir: Path, output_dir: Path) -> tuple[dict[str, Any], int]:
    output_dir, input_dir, source_dir, spatial_dir = (p.resolve() for p in (output_dir, input_dir, source_dir, spatial_dir))
    out_path = output_dir / "verification.json"
    if out_path.exists() or out_path.with_name(out_path.name + ".tmp").exists():
        raise FileExistsError(f"refusing existing verifier receipt or temporary file: {out_path}")
    failures: list[str] = []
    base_ids = {}
    for key, path in (("primary", ROOT / "computations/matter_formation_normalization.py"), ("verifier", SELF_PATH), ("prereg", PREREG_PATH)):
        base_ids[key] = {"path": relpath(path), "sha256": ""}
        try:
            base_ids[key] = identity(path)
        except Exception as exc:
            failures.append(f"missing canonical {key} identity: {exc}")
    receipt = empty_payload(base_ids)
    receipt["constants"] = {"c_m_s": C, "hbar_J_s": HBAR, "MeV_J": MEV_J, "target_energy_MeV": TARGET_MEV, "planck_energy_MeV": PLANCK_MEV, "varphi": PHI, "coefficients": dict(COEFFICIENTS)}
    source_path = source_dir / f"{SOURCE_ID}.npz"
    receipt["source"] = {"path": relpath(source_path), "sha256": "", "id": SOURCE_ID}
    primary_path = input_dir / "results.json"
    try:
        if not primary_path.is_file():
            failures.append(f"missing primary receipt: {primary_path}")
            return finish_receipt(receipt, failures, out_path)
        primary = json_load(primary_path)
        receipt["input_sha256"] = raw_sha256(primary_path)
        if not isinstance(primary, dict) or primary.get("schema") != SCHEMA:
            failures.append("primary schema mismatch")
        if isinstance(primary, dict):
            if primary.get("numerical_pass") is not True:
                failures.append("primary numerical_pass is false")
            if primary.get("failures") != []:
                failures.append(f"primary failures: {primary.get('failures')!r}")
            if primary.get("identities") != base_ids:
                failures.append("primary canonical identities mismatch")
        if not finite_tree(primary):
            failures.append("primary contains nonfinite JSON value")
        if failures:
            return finish_receipt(receipt, failures, out_path)

        spatial_primary, spatial_verify, inherited = load_spatial(spatial_dir, failures)
        receipt["inherited_spatial"] = inherited
        if failures or spatial_primary is None or spatial_verify is None:
            return finish_receipt(receipt, failures, out_path)
        selected = next(item for item in spatial_primary["rows"] if item["id"] == SOURCE_ID)
        source = load_selected_source(source_dir, selected, failures)
        if source is None or failures:
            return finish_receipt(receipt, failures, out_path)
        receipt["source"] = {"path": relpath(source["path"]), "sha256": source["sha256"], "id": SOURCE_ID}
        E_sc, gradient, _local = static_energy(source)
        N = math.fsum(float(v) * float(c) ** 2 for v, c in zip(source["volumes"], source["c"]))
        omega_C = float(selected["omega_C"])
        if not finite(N) or N <= 0.0 or not close(N, selected.get("population")):
            failures.append("recomputed population disagrees with inherited source")
            return finish_receipt(receipt, failures, out_path)
        receipt["source_summary"] = {"R": 12.0, "n": 768, "N": N, "omega_C": omega_C, "static_energy": E_sc, "gradient_energy": gradient}
        target_J = TARGET_MEV * MEV_J
        lambda_target = HBAR * C / target_J
        k = COEFFICIENTS["k_Cx"]
        e = COEFFICIENTS["e_C"]
        h = COEFFICIENTS["h_C"]
        sqrt_term = math.sqrt(COEFFICIENTS["u_rho"] * COEFFICIENTS["u_C"] / 2.0)
        a_dep = 1.0 / (4.0 * (h - e))
        a_vac = 1.0 / (4.0 * (h - e - sqrt_term))
        family = []
        for a in A_VALUES:
            if not (0.0 < a <= a_dep and a <= a_vac):
                failures.append(f"temporal witness is not admissible: {a}")
                continue
            D = 1.0 + 4.0 * a * omega_C
            if D <= 0.0:
                failures.append(f"nonpositive D at a={a}")
                continue
            charge = math.sqrt(D) * N
            N_Q = 1.0 / charge
            M = math.sqrt(1.0 + 4.0 * a * e) / (2.0 * a)
            t_Q = HBAR * M / target_J
            ell_Q = C * t_Q * math.sqrt(2.0 * a / k)
            K_x = HBAR * ell_Q * ell_Q / t_Q
            rho_0 = N_Q / ell_Q ** 3
            E_Q = K_x * rho_0 * ell_Q
            omega = 2.0 * omega_C / (1.0 + math.sqrt(D))
            Omega = math.sqrt(D) / (2.0 * a)
            H_original = E_sc + a * omega * omega * N
            H_canonical = E_sc + (a * Omega * Omega + 1.0 / (4.0 * a)) * N
            shift = charge / (2.0 * a)
            row = {
                "a": a, "D": D, "charge": charge, "N_Q": N_Q,
                "ell_Q_m": ell_Q, "t_Q_s": t_Q, "K_x": K_x, "rho_0": rho_0, "E_Q_J": E_Q,
                "ell_tail_m": ell_Q * math.sqrt(k / (2.0 * (e - omega_C))),
                "canonical_frequency": Omega, "exterior_mass": M, "original_frequency": omega,
                "H_original": H_original, "H_canonical": H_canonical,
                "canonical_energy_over_target": E_Q * H_canonical / target_J,
                "mass_residual": abs(HBAR * M / (t_Q * target_J) - 1.0),
                "speed_residual": abs(ell_Q * math.sqrt(k / (2.0 * a)) / (C * t_Q) - 1.0),
                "charge_residual": abs(N_Q * charge - 1.0),
                "energy_shift_residual": abs(H_canonical - H_original - shift) / max(1.0, abs(H_canonical), abs(H_original), abs(shift)),
                "chemical_energy_residual": abs(H_canonical - Omega * charge - E_sc + omega_C * N) / max(1.0, abs(H_canonical), abs(Omega * charge), abs(E_sc), abs(omega_C * N)),
            }
            if any(not finite(value) for value in row.values()):
                failures.append(f"nonfinite unit-family value at a={a}")
            if any(row[key] >= RESIDUAL_TOL for key in ("mass_residual", "speed_residual", "charge_residual", "energy_shift_residual", "chemical_energy_residual")):
                failures.append(f"normalization identity residual at a={a}")
            family.append(row)
        receipt["unit_family"] = family
        planck_length = HBAR * C / (PLANCK_MEV * MEV_J)
        cell_lower = planck_length * PHI ** 107
        cell_upper = planck_length * PHI ** 108
        minimum_length = lambda_target * math.sqrt((1.0 + 4.0 * a_vac * e) / (2.0 * a_vac * k))
        core = {
            "a_depleted": a_dep, "a_vacuum": a_vac, "lambda_target_m": lambda_target,
            "target_cascade_coordinate": math.log(lambda_target / planck_length) / math.log(PHI),
            "cell_lower_m": cell_lower, "cell_upper_m": cell_upper,
            "exact_core_root_denominator": 2.0 * (k - 2.0 * e),
            "minimum_core_length_m": minimum_length,
            "minimum_core_cascade_coordinate": math.log(minimum_length / planck_length) / math.log(PHI),
        }
        receipt["core_assignment"] = core
        matching = [item for item in spatial_primary["comparisons"] if item["metric"] == "amp1_gap" and item["pair"] == "domain" and item["left"] == "q256_R12_n384_refine" and item["right"] == "q256_R24_n768_refine"]
        if len(matching) != 1:
            failures.append("accepted amp1_gap domain comparison missing or ambiguous")
            return finish_receipt(receipt, failures, out_path)
        original = matching[0]
        left = next(item for item in spatial_primary["rows"] if item["id"] == original["left"])["metrics"]["amp1_gap"]
        right = next(item for item in spatial_primary["rows"] if item["id"] == original["right"])["metrics"]["amp1_gap"]
        tolerance = float(original["tolerance"])
        if not finite(tolerance) or tolerance <= 0.0 or original["pass"] is not False or not close(abs(left - right), original["absolute_difference"]):
            failures.append("accepted failed comparison has inconsistent endpoints")
            return finish_receipt(receipt, failures, out_path)
        reference_ratio = abs(left - right) / tolerance
        rescale_rows = []
        for factor in (1.0e-12, 1.0, 1.0e12):
            difference = abs(factor * left - factor * right)
            converted_tolerance = factor * tolerance
            row = {"factor": factor, "ratio": difference / converted_tolerance, "pass": difference <= converted_tolerance}
            if row["pass"] is not False or not close(row["ratio"], reference_ratio):
                failures.append(f"unit rescaling changes the accepted comparison: {factor}")
            rescale_rows.append(row)
        receipt["unit_rescaling"] = {"comparison": original, "rows": rescale_rows}
        receipt["dirac"] = dirac_payload()
        if receipt["dirac"]["adjoint_residual"] >= RESIDUAL_TOL:
            failures.append("chiral-scalar adjoint identity failed")
        complex_br = complex(*receipt["dirac"]["witnesses"][0]["B_R"])
        negative_br = complex(*receipt["dirac"]["witnesses"][1]["B_R"])
        density_bad = abs(complex_br.imag) > NUM_TOL and negative_br.real < 0.0 and abs(receipt["dirac"]["golden_ratio_determinant"]) > NUM_TOL
        interaction_bad = abs(receipt["dirac"]["linear_interaction"][1]) > NUM_TOL or abs(receipt["dirac"]["squared_interaction"][1]) > NUM_TOL
        ident_support = len(family) == 3 and len({row["ell_Q_m"] for row in family}) == 3 and all(max(row[key] for key in ("mass_residual", "speed_residual", "charge_residual")) < RESIDUAL_TOL for row in family)
        receipt["verdicts"] = {
            "normalization": "SUPPORTS—conditional one-mass normalization nonuniqueness" if ident_support else "INCONCLUSIVE—normalization identifiability",
            "core_assignment": "CONTRADICTS—selected scalar electron-core assignment" if core["exact_core_root_denominator"] <= 0.0 and minimum_length > cell_upper else "INCONCLUSIVE—selected scalar electron-core assignment",
            "density_identification": "CONTRADICTS—chiral-scalar nonnegative-density identification" if density_bad else "INCONCLUSIVE—chiral-scalar density identification",
            "projection_action": "CONTRADICTS—displayed chiral projection interaction as a physical real action" if interaction_bad else "INCONCLUSIVE—chiral projection action",
            "spatial_parent": spatial_primary["parent_verdict"],
        }
        receipt["independent_checks"] = {
            "static_energy_method": "direct_face_and_local_potential_loops",
            "dirac_method": "two_component_contractions_and_polarized_basis_adjunction",
            "spatial_primary_hash": SPATIAL_RESULTS_HASH,
            "spatial_verification_hash": SPATIAL_VERIFY_HASH,
            "primary_input_sha256": receipt["input_sha256"],
        }
        receipt["numerical_pass"] = True
        expected = {key: value for key, value in receipt.items() if key not in {"schema", "identities", "input_sha256", "independent_checks"}}
        actual = {key: value for key, value in primary.items() if key not in {"schema", "identities"}}
        compare_recursive(actual, expected, "receipt", failures)
    except Exception as exc:
        failures.append(f"independent calculation failed: {type(exc).__name__}: {exc}")
    return finish_receipt(receipt, failures, out_path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--spatial-dir", type=Path, default=DEFAULT_SPATIAL_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    try:
        receipt, code = run(args.input_dir, args.source_dir, args.spatial_dir, args.output_dir)
    except Exception as exc:
        print(f"normalization verification failed before receipt: {type(exc).__name__}: {exc}")
        return 1
    print(json.dumps({"numerical_pass": receipt["numerical_pass"], "failures": receipt["failures"], "verdicts": receipt["verdicts"]}, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
