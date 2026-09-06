#!/usr/bin/env python3
"""Independent verifier for the frozen smooth-density-trap stability calculation.

The verifier intentionally rebuilds the finite-volume operators from the frozen
radial NPZ fields.  It does not import the primary stability driver: source
identity is checked by hash, while every numerical quantity is recomputed here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from scipy.linalg import eigh, null_space

ROOT = Path(__file__).resolve().parents[1]
PREREG_PATH = ROOT / "computations" / "matter-formation-stability-prereg.md"
PRIMARY_SOURCE = ROOT / "computations" / "matter_formation_stability.py"
DEFAULT_RUN_DIR = ROOT / "runs" / "20260906_matter_formation_stability"
DEFAULT_INPUT_DIR = DEFAULT_RUN_DIR

COEFFICIENTS = {
    "u_rho": 4.0,
    "e_C": 0.75,
    "h_C": 2.9598260763447164,
    "u_C": 1.0,
}
SOURCE_ARTIFACTS: tuple[dict[str, str], ...] = (
    {
        "id": "q16_R12_n192_w2",
        "artifact": "runs/20260906_matter_formation_radial/q16_R12_n192_w2.npz",
        "sha256": "52540cf2cc11fcb313ecf689ffb5115c72480813cb7c866f348050bee33ad777",
    },
    {
        "id": "q16_R12_n384_refine",
        "artifact": "runs/20260906_matter_formation_radial/q16_R12_n384_refine.npz",
        "sha256": "2e21fa2158d7fc7f9bff65bf337558af1bc0ca76520ea441611b37ab91e9d770",
    },
    {
        "id": "q16_R12_n768_refine",
        "artifact": "runs/20260906_matter_formation_radial/q16_R12_n768_refine.npz",
        "sha256": "335364c4e655de4a34b51c0558c3a7559f45311d7f2973b262de4fd2c61db7be",
    },
    {
        "id": "q16_R24_n768_refine",
        "artifact": "runs/20260906_matter_formation_radial/q16_R24_n768_refine.npz",
        "sha256": "92c49919d8fb748dffb7a9e3d4ba497214beb883fb837195dcc8a321ec06096b",
    },
)
EXPECTED_IDS = tuple(item["id"] for item in SOURCE_ARTIFACTS)
REQUIRED_NPZ = ("r", "volumes", "f", "c", "R", "q")
EIGEN_COUNT = 6
EIGEN_RESIDUAL_TOL = 1.0e-8
EIGEN_MATCH_TOL = 1.0e-7
SYMMETRY_OVERLAP_TOL = 0.99
SCALAR_MATCH_TOL = 1.0e-9


def canonical_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes().replace(b"\r\n", b"\n"))
    return digest.hexdigest()


def byte_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def json_safe(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return value


def write_json(path: Path, value: Mapping[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to replace existing verifier receipt: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(json_safe(value), handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    os.replace(temporary, path)


def mismatch(failures: list[dict[str, Any]], path: str, expected: Any, actual: Any, reason: str) -> None:
    failures.append({"path": path, "expected": json_safe(expected), "actual": json_safe(actual), "reason": reason})


def finite_scalar(value: Any) -> bool:
    return isinstance(value, (int, float, np.number)) and not isinstance(value, bool) and math.isfinite(float(value))


def relative_close(actual: Any, expected: Any, tolerance: float) -> bool:
    return finite_scalar(actual) and finite_scalar(expected) and abs(float(actual) - float(expected)) <= tolerance * max(1.0, abs(float(actual)), abs(float(expected)))


def second_order_derivative(values: np.ndarray, dr: float) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    if values.size < 3:
        raise ValueError("second-order sampled derivative requires at least three cells")
    result = np.empty_like(values)
    result[0] = (-3.0 * values[0] + 4.0 * values[1] - values[2]) / (2.0 * dr)
    result[1:-1] = (values[2:] - values[:-2]) / (2.0 * dr)
    result[-1] = (3.0 * values[-1] - 4.0 * values[-2] + values[-3]) / (2.0 * dr)
    return result


def expected_geometry(R: float, n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    dr = R / n
    faces = np.arange(n + 1, dtype=np.float64) * dr
    centers = (np.arange(n, dtype=np.float64) + 0.5) * dr
    volumes = (4.0 * math.pi / 3.0) * (faces[1:] ** 3 - faces[:-1] ** 3)
    return centers, volumes, faces


def face_stiffness(R: float, n: int) -> tuple[np.ndarray, float]:
    dr = R / n
    conductances = np.empty(n, dtype=np.float64)
    if n > 1:
        faces = np.arange(1, n, dtype=np.float64) * dr
        conductances[:-1] = 4.0 * math.pi * faces * faces / dr
    conductances[-1] = 8.0 * math.pi * R * R / dr
    incidence = np.zeros((n, n), dtype=np.float64)
    if n > 1:
        indices = np.arange(n - 1)
        incidence[indices, indices] = -1.0
        incidence[indices, indices + 1] = 1.0
    incidence[-1, -1] = 1.0
    stiffness = incidence.T @ (conductances[:, None] * incidence)
    return stiffness, float(dr)


def stationary_and_operators(
    r: np.ndarray, volumes: np.ndarray, f: np.ndarray, c: np.ndarray, R: float, q_target: float
) -> dict[str, Any]:
    n = int(f.size)
    K, dr = face_stiffness(R, n)
    sqrt_v = np.sqrt(volumes)
    inv_sqrt_v = 1.0 / sqrt_v
    D0 = (inv_sqrt_v[:, None] * K) * inv_sqrt_v[None, :]
    angular_unit = 4.0 * math.pi * dr / volumes
    e = COEFFICIENTS["e_C"]
    h = COEFFICIENTS["h_C"]
    urho = COEFFICIENTS["u_rho"]
    uC = COEFFICIENTS["u_C"]
    gf = K @ (f - 1.0) + volumes * (urho * f * (f * f - 1.0) + 2.0 * h * f * c * c)
    potential_c = 2.0 * (e - h * (1.0 - f * f)) * c + 2.0 * uC * c**3
    gc = K @ c + volumes * potential_c
    charge = float(np.dot(volumes, c * c))
    omega = float(np.dot(c, gc) / (2.0 * charge)) if charge > 0.0 else float("nan")
    rf = gf / volumes
    rc = gc / (2.0 * volumes) - omega * c
    f_scale = max(1.0, math.sqrt(float(np.dot(volumes, (1.0 - f) ** 2))))
    residual_f = math.sqrt(float(np.dot(volumes, rf * rf))) / f_scale
    residual_c = math.sqrt(float(np.dot(volumes, rc * rc))) / math.sqrt(q_target)
    charge_relative_error = abs(charge - q_target) / q_target
    source_qualified = bool(
        math.isfinite(charge_relative_error)
        and charge_relative_error < 1.0e-10
        and math.isfinite(residual_f)
        and math.isfinite(residual_c)
        and residual_f < 1.0e-4
        and residual_c < 1.0e-4
    )
    eta = max(5.0e-4, 10.0 * residual_f, 10.0 * residual_c)

    def build_hessian(ell: int) -> np.ndarray:
        D = D0 + np.diag(ell * (ell + 1.0) * angular_unit)
        hff = D + np.diag(urho * (3.0 * f * f - 1.0) + 2.0 * h * c * c)
        hcc = D + np.diag(2.0 * (e - h * (1.0 - f * f) - omega) + 6.0 * uC * c * c)
        hfc = np.diag(4.0 * h * f * c)
        return np.block([[hff, hfc], [hfc, hcc]])

    H0 = build_hessian(0)
    H1 = build_hessian(1)
    Hphase = D0 + np.diag(2.0 * (e - h * (1.0 - f * f) - omega) + 2.0 * uC * c * c)
    charge_row = np.zeros((1, 2 * n), dtype=np.float64)
    charge_row[0, n:] = sqrt_v * c
    basis = null_space(charge_row)
    reduced = basis.T @ H0 @ basis
    values0, vectors0 = eigh(reduced, driver="evd", check_finite=True)
    values1, vectors1 = eigh(H1, driver="evd", check_finite=True)
    valuesp, vectorsp = eigh(Hphase, driver="evd", check_finite=True)
    values0 = values0[:EIGEN_COUNT]
    vectors0 = vectors0[:, :EIGEN_COUNT]
    values1 = values1[:EIGEN_COUNT]
    vectors1 = vectors1[:, :EIGEN_COUNT]
    valuesp = valuesp[:EIGEN_COUNT]
    vectorsp = vectorsp[:, :EIGEN_COUNT]
    residuals0 = [float(np.linalg.norm(reduced @ vectors0[:, i] - values0[i] * vectors0[:, i]) / max(1.0, abs(values0[i]))) for i in range(EIGEN_COUNT)]
    residuals1 = [float(np.linalg.norm(H1 @ vectors1[:, i] - values1[i] * vectors1[:, i]) / max(1.0, abs(values1[i]))) for i in range(EIGEN_COUNT)]
    residualsp = [float(np.linalg.norm(Hphase @ vectorsp[:, i] - valuesp[i] * vectorsp[:, i]) / max(1.0, abs(valuesp[i]))) for i in range(EIGEN_COUNT)]
    phase_symmetry = sqrt_v * c
    phase_symmetry /= np.linalg.norm(phase_symmetry)
    translation = np.concatenate((sqrt_v * second_order_derivative(f, dr), sqrt_v * second_order_derivative(c, dr)))
    translation_norm = float(np.linalg.norm(translation))
    if translation_norm > 0.0:
        translation /= translation_norm
    phase_overlap = abs(float(np.dot(phase_symmetry, vectorsp[:, 0]))) if np.linalg.norm(phase_symmetry) else 0.0
    translation_overlap = abs(float(np.dot(translation, vectors1[:, 0]))) if translation_norm > 0.0 else 0.0
    return {
        "omega": omega,
        "residual_f": residual_f,
        "residual_c": residual_c,
        "eta": eta,
        "charge_relative_error": charge_relative_error,
        "source_qualified": source_qualified,
        "amplitude0": {"eigenvalues": values0.tolist(), "residuals": residuals0},
        "amplitude1": {"eigenvalues": values1.tolist(), "residuals": residuals1},
        "phase": {"eigenvalues": valuesp.tolist(), "residuals": residualsp},
        "phase_overlap": float(phase_overlap),
        "translation_overlap": float(translation_overlap),
        "pass_eigenpairs": bool(max(residuals0 + residuals1 + residualsp) < EIGEN_RESIDUAL_TOL),
        "pass_symmetry": bool(abs(values1[0]) <= eta and abs(valuesp[0]) <= eta and phase_overlap > SYMMETRY_OVERLAP_TOL and translation_overlap > SYMMETRY_OVERLAP_TOL),
        "pass_spectrum": bool(values0[0] > eta and values1[0] >= -eta and valuesp[0] >= -eta),
    }


def load_npz(path: Path, expected: Mapping[str, str], failures: list[dict[str, Any]]) -> dict[str, np.ndarray] | None:
    if not path.exists():
        mismatch(failures, expected["id"], "existing frozen NPZ", str(path), "infrastructure")
        return None
    actual_hash = byte_sha256(path)
    if actual_hash != expected["sha256"]:
        mismatch(failures, f"{expected['id']}.artifact_sha256", expected["sha256"], actual_hash, "frozen NPZ hash")
        return None
    try:
        with np.load(path, allow_pickle=False) as archive:
            missing = [key for key in REQUIRED_NPZ if key not in archive]
            if missing:
                mismatch(failures, f"{expected['id']}.npz.keys", REQUIRED_NPZ, missing, "schema")
                return None
            arrays = {key: np.asarray(archive[key], dtype=np.float64) for key in REQUIRED_NPZ}
    except Exception as exc:
        mismatch(failures, expected["id"], "readable NPZ", repr(exc), "infrastructure")
        return None
    R = float(arrays["R"])
    q = float(arrays["q"])
    f = arrays["f"]
    c = arrays["c"]
    r = arrays["r"]
    volumes = arrays["volumes"]
    if f.ndim != 1 or c.shape != f.shape or r.shape != f.shape or volumes.shape != f.shape:
        mismatch(failures, f"{expected['id']}.npz.shape", "matching one-dimensional fields", {key: value.shape for key, value in arrays.items()}, "schema")
        return None
    if not all(math.isfinite(float(value)) for value in (R, q)) or R <= 0.0 or q <= 0.0 or not all(np.all(np.isfinite(arrays[key])) for key in ("r", "volumes", "f", "c")):
        mismatch(failures, f"{expected['id']}.npz.finite", True, False, "non-finite input")
        return None
    n = int(f.size)
    exp_r, exp_v, _ = expected_geometry(R, n)
    if not np.allclose(r, exp_r, rtol=2.0e-12, atol=2.0e-14) or not np.allclose(volumes, exp_v, rtol=2.0e-12, atol=2.0e-14):
        mismatch(failures, f"{expected['id']}.geometry", "exact spherical cell geometry", "mismatch", "frozen geometry")
        return None
    arrays["R"] = np.array(R)
    arrays["q"] = np.array(q)
    return arrays


def compare_primary_field(
    failures: list[dict[str, Any]], path: str, independent: Any, primary: Any, tolerance: float = SCALAR_MATCH_TOL
) -> None:
    if isinstance(independent, (list, tuple)):
        if not isinstance(primary, (list, tuple)) or len(independent) != len(primary):
            mismatch(failures, path, independent, primary, "primary comparison")
            return
        for index, (actual, expected) in enumerate(zip(independent, primary)):
            compare_primary_field(failures, f"{path}[{index}]", actual, expected, tolerance)
        return
    if not relative_close(independent, primary, tolerance):
        mismatch(failures, path, independent, primary, "primary comparison")


def row_decision(metrics: Mapping[str, Any]) -> str:
    if not metrics["source_qualified"] or not metrics["pass_eigenpairs"] or not metrics["pass_symmetry"]:
        return "INCONCLUSIVE"
    values0 = metrics["amplitude0"]["eigenvalues"]
    values1 = metrics["amplitude1"]["eigenvalues"]
    valuesp = metrics["phase"]["eigenvalues"]
    eta = float(metrics["eta"])
    if float(values0[0]) < -eta or float(values1[0]) < -eta or float(valuesp[0]) < -eta:
        return "CONTRADICTS"
    if not metrics["pass_spectrum"]:
        return "INCONCLUSIVE"
    return "SUPPORTS"


def independent_comparisons(rows: Mapping[str, Mapping[str, Any]], failures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def make(name: str, left: str, right: str) -> dict[str, Any]:
        a = float(rows[left]["amplitude0"]["eigenvalues"][0])
        b = float(rows[right]["amplitude0"]["eigenvalues"][0])
        eta_a = float(rows[left]["eta"])
        eta_b = float(rows[right]["eta"])
        tolerance = max(0.01 * max(abs(a), abs(b)), eta_a, eta_b)
        difference = abs(a - b)
        relative = difference / max(1.0, abs(a), abs(b))
        passed = bool(difference <= tolerance)
        result = {
            "name": name,
            "a": left,
            "b": right,
            "lambda_a": a,
            "lambda_b": b,
            "absolute_difference": difference,
            "relative_difference": relative,
            "tolerance": tolerance,
            "pass": passed,
        }
        return result

    return [
        make("R12_n384_vs_R12_n768", "q16_R12_n384_refine", "q16_R12_n768_refine"),
        make("R12_n384_vs_R24_n768_same_spacing", "q16_R12_n384_refine", "q16_R24_n768_refine"),
    ]


def verify(input_dir: Path, output_dir: Path) -> tuple[dict[str, Any], int]:
    failures: list[dict[str, Any]] = []
    primary_path = input_dir / "results.json"
    primary: Mapping[str, Any] = {}
    if not primary_path.exists():
        mismatch(failures, "results.json", "existing primary stability receipt", str(primary_path), "infrastructure")
    else:
        try:
            loaded = json.loads(primary_path.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                raise ValueError("primary receipt is not an object")
            primary = loaded
        except Exception as exc:
            mismatch(failures, "results.json", "valid JSON object", repr(exc), "infrastructure")
    if not PREREG_PATH.exists():
        mismatch(failures, "prereg", "existing preregistration", str(PREREG_PATH), "infrastructure")
    if not PRIMARY_SOURCE.exists():
        mismatch(failures, "source", "existing primary source", str(PRIMARY_SOURCE), "infrastructure")
    expected_prereg = canonical_sha256(PREREG_PATH) if PREREG_PATH.exists() else ""
    expected_source = canonical_sha256(PRIMARY_SOURCE) if PRIMARY_SOURCE.exists() else ""
    expected_verifier = canonical_sha256(Path(__file__))
    if primary.get("prereg_sha256") != expected_prereg:
        mismatch(failures, "prereg_sha256", expected_prereg, primary.get("prereg_sha256"), "source identity")
    if primary.get("source_sha256") != expected_source:
        mismatch(failures, "source_sha256", expected_source, primary.get("source_sha256"), "source identity")
    if primary.get("schema") != "matter-formation-stability-v1":
        mismatch(failures, "schema", "matter-formation-stability-v1", primary.get("schema"), "schema")
    if not isinstance(primary.get("rows"), list):
        mismatch(failures, "rows", "list", primary.get("rows"), "schema")
        primary_rows: list[Any] = []
    else:
        primary_rows = primary["rows"]
    primary_by_id: dict[str, Mapping[str, Any]] = {}
    for index, row in enumerate(primary_rows):
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            mismatch(failures, f"rows[{index}]", "row with string id", row, "schema")
            continue
        if row["id"] in primary_by_id:
            mismatch(failures, f"rows[{index}].id", "unique id", row["id"], "identity")
        primary_by_id[row["id"]] = row
    if set(primary_by_id) != set(EXPECTED_IDS):
        mismatch(failures, "rows.ids", EXPECTED_IDS, sorted(primary_by_id), "exact source set")

    independent: dict[str, dict[str, Any]] = {}
    for expected in SOURCE_ARTIFACTS:
        path = ROOT / expected["artifact"]
        arrays = load_npz(path, expected, failures)
        if arrays is None:
            continue
        identifier = expected["id"]
        n = int(arrays["f"].size)
        metrics = stationary_and_operators(arrays["r"], arrays["volumes"], arrays["f"], arrays["c"], float(arrays["R"]), float(arrays["q"]))
        metrics = {key: value for key, value in metrics.items() if key not in {"pass_eigenpairs", "pass_symmetry", "pass_spectrum"}}
        metrics["verdict"] = row_decision({**metrics, "pass_eigenpairs": bool(max(metrics["amplitude0"]["residuals"] + metrics["amplitude1"]["residuals"] + metrics["phase"]["residuals"]) < EIGEN_RESIDUAL_TOL), "pass_symmetry": bool(abs(metrics["amplitude1"]["eigenvalues"][0]) <= metrics["eta"] and abs(metrics["phase"]["eigenvalues"][0]) <= metrics["eta"] and metrics["phase_overlap"] > SYMMETRY_OVERLAP_TOL and metrics["translation_overlap"] > SYMMETRY_OVERLAP_TOL), "pass_spectrum": bool(metrics["amplitude0"]["eigenvalues"][0] > metrics["eta"] and metrics["amplitude1"]["eigenvalues"][0] >= -metrics["eta"] and metrics["phase"]["eigenvalues"][0] >= -metrics["eta"])})
        source_row = primary_by_id.get(identifier)
        if source_row is not None:
            expected_artifact = expected["artifact"]
            if "R" in source_row:
                compare_primary_field(failures, f"rows.{identifier}.R", float(arrays["R"]), source_row["R"])
            if "n" in source_row:
                compare_primary_field(failures, f"rows.{identifier}.n", n, source_row["n"])
            if "q" in source_row:
                compare_primary_field(failures, f"rows.{identifier}.q", float(arrays["q"]), source_row["q"])
            if source_row.get("artifact") != expected_artifact:
                mismatch(failures, f"rows.{identifier}.artifact", expected_artifact, source_row.get("artifact"), "frozen source set")
            if source_row.get("artifact_sha256") != expected["sha256"]:
                mismatch(failures, f"rows.{identifier}.artifact_sha256", expected["sha256"], source_row.get("artifact_sha256"), "frozen source hash")
            for key in ("omega", "residual_f", "residual_c", "eta", "phase_overlap", "translation_overlap"):
                compare_primary_field(failures, f"rows.{identifier}.{key}", metrics[key], source_row.get(key))
            if "charge_relative_error" in source_row:
                compare_primary_field(failures, f"rows.{identifier}.charge_relative_error", metrics["charge_relative_error"], source_row["charge_relative_error"])
            for block in ("amplitude0", "amplitude1", "phase"):
                primary_block = source_row.get(block)
                if not isinstance(primary_block, dict):
                    mismatch(failures, f"rows.{identifier}.{block}", "object", primary_block, "schema")
                    continue
                compare_primary_field(
                    failures,
                    f"rows.{identifier}.{block}.eigenvalues",
                    metrics[block]["eigenvalues"],
                    primary_block.get("eigenvalues"),
                    EIGEN_MATCH_TOL,
                )
                compare_primary_field(failures, f"rows.{identifier}.{block}.residuals", metrics[block]["residuals"], primary_block.get("residuals"))
            if source_row.get("verdict") != metrics["verdict"]:
                mismatch(failures, f"rows.{identifier}.verdict", metrics["verdict"], source_row.get("verdict"), "independent decision")
        metrics_row = {
            "id": identifier,
            "artifact": expected["artifact"],
            "artifact_sha256": expected["sha256"],
            "omega": metrics["omega"],
            "residual_f": metrics["residual_f"],
            "residual_c": metrics["residual_c"],
            "eta": metrics["eta"],
            "charge_relative_error": metrics["charge_relative_error"],
            "source_qualified": metrics["source_qualified"],
            "amplitude0": metrics["amplitude0"],
            "amplitude1": metrics["amplitude1"],
            "phase": metrics["phase"],
            "phase_overlap": metrics["phase_overlap"],
            "translation_overlap": metrics["translation_overlap"],
            "verdict": metrics["verdict"],
        }
        independent[identifier] = metrics_row

    comparisons = independent_comparisons(independent, failures) if set(independent) == set(EXPECTED_IDS) else []
    reported = primary.get("comparisons", [])
    if not isinstance(reported, list) or len(reported) != len(comparisons):
        mismatch(failures, "comparisons", f"list with {len(comparisons)} entries", reported, "schema")
    else:
        reported_by_name = {
            item.get("name"): item for item in reported if isinstance(item, dict) and isinstance(item.get("name"), str)
        }
        for comparison in comparisons:
            name = comparison["name"]
            item = reported_by_name.get(name)
            if item is None:
                mismatch(failures, f"comparisons.{name}", comparison, "missing", "independent comparison")
                continue
            for key in ("a", "b"):
                if item.get(key) != comparison[key]:
                    mismatch(failures, f"comparisons.{name}.{key}", comparison[key], item.get(key), "primary comparison")
            for key in ("absolute_difference", "relative_difference", "tolerance"):
                compare_primary_field(failures, f"comparisons.{name}.{key}", comparison[key], item.get(key))
            for key in ("lambda_a", "lambda_b"):
                compare_primary_field(failures, f"comparisons.{name}.{key}", comparison[key], item.get(key), EIGEN_MATCH_TOL)
            if bool(item.get("pass")) != bool(comparison["pass"]):
                mismatch(failures, f"comparisons.{name}.pass", comparison["pass"], item.get("pass"), "independent decision")
    rows = [independent[identifier] for identifier in EXPECTED_IDS if identifier in independent]
    scientific = "SUPPORTS"
    if any(row["verdict"] == "CONTRADICTS" for row in rows):
        scientific = "CONTRADICTS"
    elif len(rows) != len(EXPECTED_IDS) or any(row["verdict"] != "SUPPORTS" for row in rows) or any(not item.get("pass", False) for item in comparisons):
        scientific = "INCONCLUSIVE"
    verdict = "INCONCLUSIVE" if failures else scientific
    report: dict[str, Any] = {
        "schema": "matter-formation-stability-verification-v1",
        "pass": not failures,
        "failures": failures,
        "rows": rows,
        "comparisons": comparisons,
        "verdict": verdict,
        "source_sha256": expected_source,
        "verifier_sha256": expected_verifier,
        "prereg_sha256": expected_prereg,
    }
    write_json(output_dir / "verification.json", report)
    return report, 1 if failures or verdict == "INCONCLUSIVE" else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    input_dir = args.input_dir if args.input_dir.is_absolute() else ROOT / args.input_dir
    explicit_output = args.output_dir is not None
    output_dir = args.output_dir if explicit_output else input_dir
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    input_dir = input_dir.resolve()
    output_dir = output_dir.resolve()
    if (output_dir / "verification.json").exists():
        parser.error("refusing to replace existing verifier receipt; use a distinct --output-dir")
    if explicit_output and output_dir == input_dir:
        parser.error("--output-dir must be separate from --input-dir")
    report, status = verify(input_dir, output_dir)
    print(
        f"stability verification: pass={report['pass']} verdict={report['verdict']} "
        f"rows={len(report['rows'])} failures={len(report['failures'])}"
    )
    return status


if __name__ == "__main__":
    raise SystemExit(main())
