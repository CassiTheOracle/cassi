#!/usr/bin/env python3
"""Independently verify the preregistered PA32 Q2 recovery campaign."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "runs" / "20260901_particle_stationary_bvp"
RUN_DIR = ROOT / "runs" / "20260902_particle_stationary_q2_recovery"
SOURCE_RESULTS_PATH = SOURCE_DIR / "results.json"
SOURCE_VERIFICATION_PATH = SOURCE_DIR / "verification.json"
SOURCE_REPORT_PATH = ROOT / "computations" / "particle-stationary-bvp-report.md"
SOURCE_PREREG_PATH = ROOT / "computations" / "particle-stationary-bvp-pre-registration.md"
SOURCE_PROGRAM_PATH = ROOT / "computations" / "particle_stationary_bvp.py"
SOURCE_VERIFIER_PATH = ROOT / "computations" / "verify_particle_stationary_bvp.py"
RECOVERY_PREREG_PATH = ROOT / "computations" / "particle_stationary_q2_recovery_prereg.md"
RECOVERY_PROGRAM_PATH = ROOT / "computations" / "particle_stationary_q2_recovery.py"
RECOVERY_VERIFIER_PATH = Path(__file__).resolve()
PREFLIGHT_PATH = RUN_DIR / "preflight_verification.json"
RESULTS_PATH = RUN_DIR / "results.json"
VERIFICATION_PATH = RUN_DIR / "verification.json"
AUTHORITY_PATHS = {
    "authority_action": ROOT / "foundations" / "particle-stationary-action-closure.md",
    "authority_core_support": ROOT / "foundations" / "core-trapped-charge-support.md",
    "authority_magnetic_boundary": ROOT / "foundations" / "nonabelian-magnetic-core-boundary.md",
    "authority_matter_boundary": ROOT / "foundations" / "matter-completion-boundary.md",
}
PHI = (1.0 + math.sqrt(5.0)) / 2.0
Q_C = 4.0
ABS_TOL = 1.0e-8
REL_TOL = 1.0e-6
ROUNDTRIP_TOL = 5.0e-12
C4_TOL = 5.0e-12
BOUNDARY_TOL = 1.0e-12
COEFFICIENTS = {
    "phi": PHI,
    "alpha_s": 1.0,
    "u_rho": 4.0,
    "u_phi": 4.0,
    "gamma_x": 1.0,
    "gamma_s": 1.0,
    "u_H": 4.0,
    "k_Cx": 1.0,
    "k_Cs": 1.0,
    "e_C": 0.75,
    "h_C": 1.50,
    "u_C": 1.0,
    "q_C": Q_C,
    "L_s": 1.0,
    "xi_gf": 1.0,
}
BASINS = (
    "separated_core",
    "merged_core",
    "closed_loop",
    "carrier_lump",
    "delocalized",
    "split_multicore",
)
STRUCTURAL = tuple(basin for basin in BASINS if basin != "delocalized")
GRIDS = {"P": (4.0, 17), "D": (5.0, 21), "H": (4.0, 21)}
FIELD_KEYS = ("x", "psi_real", "psi_imag", "h", "a", "c")
COMPONENT_KEYS = (
    "psi_gradient",
    "rho_potential",
    "composition_potential",
    "curvature",
    "h_gradient",
    "h_potential",
    "carrier_gradient",
    "carrier_quadratic",
    "carrier_quartic",
)
CONTINUATION = {
    "max_iter": 880,
    "max_eval": 1100,
    "history_size": 20,
    "tolerance_grad": 1.0e-10,
    "tolerance_change": 1.0e-12,
    "line_search_fn": "strong_wolfe",
}
SIGMA = np.array(
    (
        ((0.0, 1.0), (1.0, 0.0)),
        ((0.0, -1.0j), (1.0j, 0.0)),
        ((1.0, 0.0), (0.0, -1.0)),
    ),
    dtype=np.complex128,
)
ROTATIONS = np.array(
    (
        ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        ((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
        ((-1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, 1.0)),
        ((0.0, 1.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
    ),
    dtype=np.float64,
)


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise TypeError(f"Expected a JSON object: {path}")
    return value


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    temporary.replace(path)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_safe(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, tuple):
        return [json_safe(item) for item in value]
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)


def mismatch(
    out: list[dict[str, Any]],
    path: str,
    expected: Any,
    actual: Any,
    kind: str = "mismatch",
    tolerance: float | None = None,
) -> None:
    row: dict[str, Any] = {
        "kind": kind,
        "path": path,
        "expected": json_safe(expected),
        "actual": json_safe(actual),
    }
    if tolerance is not None:
        row["tolerance"] = tolerance
    out.append(row)


def finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def compare_tree(
    out: list[dict[str, Any]], path: str, actual: Any, expected: Any
) -> None:
    if isinstance(expected, float):
        tolerance = ABS_TOL + REL_TOL * abs(expected)
        if not finite_number(actual) or abs(float(actual) - expected) > tolerance:
            mismatch(out, path, expected, actual, "tolerance", tolerance)
        return
    if isinstance(expected, bool):
        if not isinstance(actual, bool) or actual is not expected:
            mismatch(out, path, expected, actual, "exact")
        return
    if isinstance(expected, int):
        if not isinstance(actual, int) or isinstance(actual, bool) or actual != expected:
            mismatch(out, path, expected, actual, "exact")
        return
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            mismatch(out, path, expected, actual, "schema")
            return
        if set(actual) != set(expected):
            mismatch(out, f"{path}.keys", sorted(expected), sorted(actual), "exact")
        for key, value in expected.items():
            if key in actual:
                compare_tree(out, f"{path}.{key}", actual[key], value)
        return
    if isinstance(expected, (list, tuple)):
        if not isinstance(actual, list):
            mismatch(out, path, expected, actual, "schema")
            return
        if len(actual) != len(expected):
            mismatch(out, f"{path}.length", len(expected), len(actual), "exact")
        for index, value in enumerate(expected[: len(actual)]):
            compare_tree(out, f"{path}[{index}]", actual[index], value)
        return
    if actual != expected:
        mismatch(out, path, expected, actual, "exact")

def finite_nonnegative(value: Any) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    numeric = float(value)
    return math.isfinite(numeric) and numeric >= 0.0


def finite_in_closed_interval(value: Any, upper: float) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    numeric = float(value)
    return math.isfinite(numeric) and 0.0 <= numeric <= upper


def all_finite(value: Any) -> bool:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return True
    if isinstance(value, (int, float, np.generic)):
        return math.isfinite(float(value))
    if isinstance(value, np.ndarray):
        return bool(np.all(np.isfinite(value)))
    if isinstance(value, Mapping):
        return all(all_finite(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return all(all_finite(item) for item in value)
    return False


def source_artifact_path(source_arm: Mapping[str, Any]) -> Path:
    artifact = source_arm.get("artifact")
    if not isinstance(artifact, str):
        raise ValueError("Source arm has no artifact path")
    candidate = Path(artifact)
    if candidate.is_absolute():
        return candidate
    by_name = SOURCE_DIR / candidate.name
    return by_name if by_name.exists() else ROOT / candidate


def build_manifest(source_receipt: Mapping[str, Any]) -> dict[str, Any]:
    carried = {
        "source_preregistration": (SOURCE_PREREG_PATH, source_receipt["hashes"]["preregistration"]),
        "source_program": (SOURCE_PROGRAM_PATH, source_receipt["hashes"]["primary_program"]),
        "source_verifier": (SOURCE_VERIFIER_PATH, source_receipt["hashes"]["independent_verifier"]),
    }
    required_mismatches: list[str] = []
    immutable: dict[str, str] = {
        "source_results": sha256(SOURCE_RESULTS_PATH),
        "source_verification": sha256(SOURCE_VERIFICATION_PATH),
        "source_report": sha256(SOURCE_REPORT_PATH),
    }
    for name, (path, expected) in carried.items():
        actual = sha256(path)
        immutable[name] = actual
        if actual != expected:
            required_mismatches.append(f"{name}: source receipt {expected}, current bytes {actual}")
    expected_arms = {f"{family}:{basin}" for family in ("P", "D") for basin in BASINS}
    if set(source_receipt.get("arms", {})) != expected_arms:
        required_mismatches.append("source arm inventory differs from the frozen P/D set")
    source_artifacts: dict[str, str] = {}
    for key in sorted(expected_arms):
        arm = source_receipt.get("arms", {}).get(key)
        if not isinstance(arm, dict) or not arm.get("completed"):
            required_mismatches.append(f"{key}: source arm is missing or incomplete")
            continue
        path = source_artifact_path(arm)
        actual = sha256(path)
        expected = source_receipt["hashes"]["artifacts"].get(path.name)
        source_artifacts[path.name] = actual
        if actual != expected or actual != arm.get("artifact_sha256"):
            required_mismatches.append(f"{key}: source artifact hash mismatch")
    return {
        "immutable_source_snapshot": immutable,
        "source_artifacts": source_artifacts,
        "current_authority": {name: sha256(path) for name, path in AUTHORITY_PATHS.items()},
        "recovery_sources": {
            "preregistration": sha256(RECOVERY_PREREG_PATH),
            "primary_program": sha256(RECOVERY_PROGRAM_PATH),
            "independent_verifier": sha256(RECOVERY_VERIFIER_PATH),
        },
        "required_mismatches": required_mismatches,
    }


def shell_mask(n: int, width: int = 1) -> np.ndarray:
    indices = np.arange(n)
    ii, jj, kk = np.meshgrid(indices, indices, indices, indexing="ij")
    return (
        (ii < width) | (ii >= n - width) | (jj < width) | (jj >= n - width)
        | (kk < width) | (kk >= n - width)
    )


def project_scalar(field: np.ndarray) -> np.ndarray:
    projected = np.zeros_like(field)
    for k in range(4):
        projected = projected + np.rot90(field, k, axes=(0, 1))
    return projected / 4.0


def project_vector(field: np.ndarray) -> np.ndarray:
    projected = np.zeros_like(field)
    for k, rotation in enumerate(ROTATIONS):
        projected += np.einsum("ij,...ja->...ia", rotation, np.rot90(field, k, axes=(0, 1)))
    return projected / 4.0


def relative_inf(actual: np.ndarray, expected: np.ndarray) -> float:
    return float(np.max(np.abs(actual - expected))) / max(float(np.max(np.abs(expected))), 1.0e-12)


def fixed_boundary_residual(
    psi: np.ndarray, h: np.ndarray, a: np.ndarray, c: np.ndarray
) -> float:
    shell = shell_mask(psi.shape[0])
    psi_inf = np.array((PHI**-0.5, PHI**-1.0), dtype=np.float64)
    h_inf = np.array((0.0, 0.0, 1.0), dtype=np.float64)
    return max(
        float(np.max(np.abs(np.real(psi)[shell] - psi_inf))),
        float(np.max(np.abs(np.imag(psi)[shell]))),
        float(np.max(np.abs(h[shell] - h_inf))),
        float(np.max(np.abs(a[shell]))),
        float(np.max(np.abs(c[shell]))),
    )


def load_fields(
    path: Path, family: str, out: list[dict[str, Any]], label: str
) -> dict[str, np.ndarray] | None:
    try:
        with np.load(path, allow_pickle=False) as archive:
            files = set(archive.files)
            if files != set(FIELD_KEYS):
                mismatch(out, f"{label}.keys", sorted(FIELD_KEYS), sorted(files), "exact")
            if not set(FIELD_KEYS).issubset(files):
                return None
            fields = {name: np.array(archive[name], copy=True, order="K") for name in FIELD_KEYS}
    except Exception as error:
        mismatch(out, label, "readable NPZ", repr(error), "artifact_read")
        return None
    r_box, n = GRIDS[family]
    expected_shapes = {
        "x": (n,), "psi_real": (n, n, n, 2), "psi_imag": (n, n, n, 2),
        "h": (n, n, n, 3), "a": (n, n, n, 3, 3), "c": (n, n, n),
    }
    valid = True
    for name, expected_shape in expected_shapes.items():
        array = fields[name]
        if array.dtype != np.float64:
            mismatch(out, f"{label}.{name}.dtype", "float64", str(array.dtype), "schema")
            valid = False
        if array.shape != expected_shape:
            mismatch(out, f"{label}.{name}.shape", expected_shape, array.shape, "schema")
            valid = False
        if not array.flags.c_contiguous:
            mismatch(out, f"{label}.{name}.order", "C-contiguous", "non-C", "schema")
            valid = False
        if not np.all(np.isfinite(array)):
            mismatch(out, f"{label}.{name}", "all finite", "nonfinite values", "nonfinite")
            valid = False
    if not valid:
        return None
    expected_x = np.linspace(-r_box, r_box, n, dtype=np.float64)
    grid_matches = (
        np.array_equal(fields["x"], expected_x)
        if family in ("P", "D")
        else np.allclose(fields["x"], expected_x, rtol=0.0, atol=1.0e-15)
    )
    if not grid_matches:
        mismatch(out, f"{label}.x", "registered grid", fields["x"], "grid")
    expected_dx = 2.0 * r_box / (n - 1)
    actual_dx = float(fields["x"][1] - fields["x"][0])
    if not math.isclose(actual_dx, expected_dx, rel_tol=0.0, abs_tol=1.0e-15):
        mismatch(out, f"{label}.dx", expected_dx, actual_dx, "grid")
    return fields


def reconstruct_endpoint(fields: Mapping[str, np.ndarray]) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    x = fields["x"]
    n = len(x)
    dx = float(x[1] - x[0])
    interior = ~shell_mask(n)
    mask = interior.astype(np.float64)
    mask_component = mask[..., None]
    mask_connection = mask[..., None, None]
    psi_inf = np.array((PHI**-0.5, PHI**-1.0), dtype=np.float64)
    h_inf = np.array((0.0, 0.0, 1.0), dtype=np.float64)
    carrier = fields["c"]
    positive = carrier[interior]
    if not np.all(positive > 0.0):
        raise ValueError("carrier is not strictly positive on the interior")
    raw_w = np.zeros_like(carrier)
    raw_w[interior] = positive + np.log(-np.expm1(-positive))
    unnormalized = mask * np.logaddexp(0.0, project_scalar(raw_w))
    normalization = math.sqrt(float(np.sum(unnormalized**2) * dx**3))
    reconstructed = {
        "x": np.array(x, copy=True, order="K"),
        "psi_real": mask_component * project_scalar(fields["psi_real"]) + (1.0 - mask_component) * psi_inf,
        "psi_imag": mask_component * project_scalar(fields["psi_imag"]),
        "h": mask_component * project_scalar(fields["h"]) + (1.0 - mask_component) * h_inf,
        "a": mask_connection * project_vector(fields["a"]),
        "c": math.sqrt(Q_C) * unnormalized / normalization,
    }
    errors = {name: relative_inf(reconstructed[name], fields[name]) for name in FIELD_KEYS if name != "x"}
    raw_finite = all(np.all(np.isfinite(value)) for value in (
        fields["psi_real"], fields["psi_imag"], fields["h"], fields["a"], raw_w
    ))
    return reconstructed, {
        "relative_inf": errors,
        "maximum_relative_inf": max(errors.values()),
        "raw_finite": bool(raw_finite),
    }


def gradient(field: np.ndarray, dx: float) -> tuple[np.ndarray, ...]:
    return tuple(np.gradient(field, dx, dx, dx, axis=(0, 1, 2), edge_order=2))


def numpy_energy(
    psi: np.ndarray, h: np.ndarray, a: np.ndarray, c: np.ndarray, x: np.ndarray
) -> tuple[dict[str, float], float, dict[str, np.ndarray]]:
    dx = float(x[1] - x[0])
    dv = dx**3
    dpsi = np.stack(gradient(psi, dx), axis=-2)
    gauge_psi = np.einsum("...ia,abc,...c->...ib", a.astype(np.complex128), SIGMA / 2.0, psi)
    covariant_psi = dpsi - 1.0j * gauge_psi
    rho = np.sum(np.abs(psi) ** 2, axis=-1)
    spin = np.einsum("...b,abc,...c->...a", psi.conj(), SIGMA, psi).real
    delta_phi = 0.5 * ((1.0 - PHI) * rho + (1.0 + PHI) * np.sum(h * spin, axis=-1))
    da = gradient(a, dx)
    curvature = np.stack(tuple(
        np.stack(tuple(da[i][..., j, :] - da[j][..., i, :] + np.cross(a[..., i, :], a[..., j, :]) for j in range(3)), axis=-2)
        for i in range(3)
    ), axis=-3)
    dh = np.stack(gradient(h, dx), axis=-2)
    covariant_h = dh + np.cross(a, np.broadcast_to(h[..., None, :], a.shape))
    dc = np.stack(gradient(c, dx), axis=-1)
    divergence = np.stack(tuple(da[i][..., i, :] for i in range(3)), axis=0).sum(axis=0)
    components = {
        "psi_gradient": 0.5 * float(np.sum(np.abs(covariant_psi) ** 2) * dv),
        "rho_potential": float(np.sum((rho - 1.0) ** 2) * dv),
        "composition_potential": 2.0 * float(np.sum(delta_phi**2) * dv),
        "curvature": 0.25 * float(np.sum(curvature**2) * dv),
        "h_gradient": 0.5 * float(np.sum(covariant_h**2) * dv),
        "h_potential": float(np.sum((np.sum(h**2, axis=-1) - 1.0) ** 2) * dv),
        "carrier_gradient": 0.5 * float(np.sum(dc**2) * dv),
        "carrier_quadratic": float(np.sum((0.75 - 1.50 * (1.0 - rho)) * c**2) * dv),
        "carrier_quartic": 0.5 * float(np.sum(c**4) * dv),
    }
    gauge_fixing = 0.5 * float(np.sum(divergence**2) * dv)
    return components, gauge_fixing, {"rho": rho, "curvature": curvature, "divergence": divergence}


def torch_project_scalar(field: torch.Tensor) -> torch.Tensor:
    projected = torch.zeros_like(field)
    for k in range(4):
        projected = projected + torch.rot90(field, k, dims=(0, 1))
    return projected / 4.0


def torch_project_vector(field: torch.Tensor) -> torch.Tensor:
    rotations = torch.tensor(ROTATIONS, dtype=torch.float64)
    projected = torch.zeros_like(field)
    for k, rotation in enumerate(rotations):
        projected = projected + torch.einsum("ij,...ja->...ia", rotation, torch.rot90(field, k, dims=(0, 1)))
    return projected / 4.0


def torch_physical_energy(
    psi_real: torch.Tensor, psi_imag: torch.Tensor, h: torch.Tensor,
    a: torch.Tensor, c: torch.Tensor, dx: float
) -> torch.Tensor:
    psi = torch.complex(psi_real, psi_imag)
    sigma = torch.tensor(SIGMA, dtype=torch.complex128)
    dpsi = torch.stack(torch.gradient(psi, spacing=(dx, dx, dx), dim=(0, 1, 2), edge_order=2), dim=-2)
    gauge_psi = torch.einsum("...ia,abc,...c->...ib", a.to(torch.complex128), sigma / 2.0, psi)
    covariant_psi = dpsi - 1.0j * gauge_psi
    rho = torch.sum(torch.abs(psi) ** 2, dim=-1)
    spin = torch.einsum("...b,abc,...c->...a", psi.conj(), sigma, psi).real
    delta_phi = 0.5 * ((1.0 - PHI) * rho + (1.0 + PHI) * torch.sum(h * spin, dim=-1))
    da = torch.gradient(a, spacing=(dx, dx, dx), dim=(0, 1, 2), edge_order=2)
    curvature = torch.stack(tuple(
        torch.stack(tuple(da[i][..., j, :] - da[j][..., i, :] + torch.cross(a[..., i, :], a[..., j, :], dim=-1) for j in range(3)), dim=-2)
        for i in range(3)
    ), dim=-3)
    dh = torch.stack(torch.gradient(h, spacing=(dx, dx, dx), dim=(0, 1, 2), edge_order=2), dim=-2)
    covariant_h = dh + torch.cross(a, h[..., None, :].expand_as(a), dim=-1)
    dc = torch.stack(torch.gradient(c, spacing=(dx, dx, dx), dim=(0, 1, 2), edge_order=2), dim=-1)
    dv = dx**3
    terms = (
        0.5 * torch.sum(torch.abs(covariant_psi) ** 2) * dv,
        torch.sum((rho - 1.0) ** 2) * dv,
        2.0 * torch.sum(delta_phi**2) * dv,
        0.25 * torch.sum(curvature**2) * dv,
        0.5 * torch.sum(covariant_h**2) * dv,
        torch.sum((torch.sum(h**2, dim=-1) - 1.0) ** 2) * dv,
        0.5 * torch.sum(dc**2) * dv,
        torch.sum((0.75 - 1.50 * (1.0 - rho)) * c**2) * dv,
        0.5 * torch.sum(c**4) * dv,
    )
    return torch.stack(terms).sum()


def physical_gradient_rms(
    psi: np.ndarray, h: np.ndarray, a: np.ndarray, c: np.ndarray, x: np.ndarray
) -> float:
    dx = float(x[1] - x[0])
    dv = dx**3
    interior_np = (~shell_mask(len(x))).astype(np.float64)
    interior = torch.tensor(interior_np, dtype=torch.float64)
    psi_real = torch.tensor(np.real(psi), dtype=torch.float64, requires_grad=True)
    psi_imag = torch.tensor(np.imag(psi), dtype=torch.float64, requires_grad=True)
    h_t = torch.tensor(h, dtype=torch.float64, requires_grad=True)
    a_t = torch.tensor(a, dtype=torch.float64, requires_grad=True)
    c_t = torch.tensor(c, dtype=torch.float64, requires_grad=True)
    energy = torch_physical_energy(psi_real, psi_imag, h_t, a_t, c_t, dx)
    gradients = torch.autograd.grad(energy, (psi_real, psi_imag, h_t, a_t, c_t))
    projected = [
        torch_project_scalar(interior[..., None] * gradients[0] / dv),
        torch_project_scalar(interior[..., None] * gradients[1] / dv),
        torch_project_scalar(interior[..., None] * gradients[2] / dv),
        torch_project_vector(interior[..., None, None] * gradients[3] / dv),
    ]
    carrier_gradient = gradients[4] / dv
    inner = torch.sum(c_t * carrier_gradient) * dv
    norm = torch.sum(c_t**2) * dv
    tangent = interior * (carrier_gradient - c_t * inner / norm)
    projected.append(torch_project_scalar(tangent))
    squared = torch.stack(tuple(torch.sum(value**2) for value in projected)).sum()
    component_count = 17 * int(np.sum(interior_np))
    return float(torch.sqrt(squared / component_count).detach())


def virial_diagnostics(
    psi: np.ndarray, h: np.ndarray, a: np.ndarray, c: np.ndarray,
    x: np.ndarray, components: Mapping[str, float]
) -> tuple[float, float, dict[str, float]]:
    dx = float(x[1] - x[0])
    dv = dx**3
    r_box = max(abs(float(x[0])), abs(float(x[-1])))
    X, Y, Z = np.meshgrid(x, x, x, indexing="ij")
    chi = ((1.0 - (X / r_box) ** 2) ** 2 * (1.0 - (Y / r_box) ** 2) ** 2 * (1.0 - (Z / r_box) ** 2) ** 2)
    vector = chi[..., None] * np.stack((X, Y, Z), axis=-1)
    dpsi, dh, da, dvector = gradient(psi, dx), gradient(h, dx), gradient(a, dx), gradient(vector, dx)
    dot_psi = -sum(vector[..., j, None] * dpsi[j] for j in range(3))
    dot_h = -sum(vector[..., j, None] * dh[j] for j in range(3))
    advected_a = sum(vector[..., j, None, None] * da[j] for j in range(3))
    one_form = np.stack(tuple(np.einsum("...j,...ja->...a", dvector[i], a) for i in range(3)), axis=-2)
    dot_a = -advected_a - one_form
    dlog_c = gradient(np.log(c + 1.0e-12), dx)
    divergence_vector = sum(dvector[i][..., i] for i in range(3))
    scale_c = -sum(vector[..., j] * dlog_c[j] for j in range(3)) - 0.5 * divergence_vector
    shell = shell_mask(len(x))
    mask = (~shell).astype(np.float64)
    psi_inf = np.array((PHI**-0.5, PHI**-1.0), dtype=np.float64)
    h_inf = np.array((0.0, 0.0, 1.0), dtype=np.float64)
    perturbed: dict[int, dict[str, float]] = {}
    for sign in (-1, 1):
        step = sign * 1.0e-4
        psi_step = project_scalar(psi + step * dot_psi)
        psi_step[shell] = psi_inf
        h_step = project_scalar(h + step * dot_h)
        h_step[shell] = h_inf
        a_step = project_vector(a + step * dot_a) * mask[..., None, None]
        positive = mask * c * np.exp(step * scale_c)
        c_step = math.sqrt(Q_C) * positive / math.sqrt(float(np.sum(positive**2) * dv))
        perturbed[sign], _, _ = numpy_energy(psi_step, h_step, a_step, c_step, x)
    directional = {name: (perturbed[1][name] - perturbed[-1][name]) / 2.0e-4 for name in COMPONENT_KEYS}
    cutoff = abs(sum(directional.values())) / max(1.0e-12, sum(abs(value) for value in directional.values()))
    formal = (
        components["psi_gradient"] + components["h_gradient"] - components["curvature"]
        + 3.0 * (components["rho_potential"] + components["composition_potential"] + components["h_potential"])
        - 2.0 * components["carrier_gradient"] - 3.0 * components["carrier_quartic"]
    )
    return cutoff, formal, directional


def take_face(array: np.ndarray, axis: int, index: int) -> np.ndarray:
    selection: list[Any] = [slice(None)] * array.ndim
    selection[axis] = index
    return array[tuple(selection)]


def outer_magnetic_number(h: np.ndarray, a: np.ndarray, curvature: np.ndarray, dx: float) -> float:
    n = h.shape[0]
    weights_1d = np.ones(n, dtype=np.float64)
    weights_1d[0] = weights_1d[-1] = 0.5
    weights = weights_1d[:, None] * weights_1d[None, :]
    flux = 0.0
    for normal, tangent_j, tangent_k in ((0, 1, 2), (1, 2, 0), (2, 0, 1)):
        remaining = [axis for axis in range(3) if axis != normal]
        for index, sign in ((n - 1, 1.0), (0, -1.0)):
            h_face = take_face(h, normal, index)
            h_hat = h_face / np.linalg.norm(h_face, axis=-1, keepdims=True)
            dh_face = np.gradient(h_hat, dx, dx, axis=(0, 1), edge_order=2)
            a_face = take_face(a, normal, index)
            d_j = dh_face[remaining.index(tangent_j)] + np.cross(a_face[..., tangent_j, :], h_hat)
            d_k = dh_face[remaining.index(tangent_k)] + np.cross(a_face[..., tangent_k, :], h_hat)
            f_jk = take_face(curvature[..., tangent_j, tangent_k, :], normal, index)
            residual = np.sum(h_hat * f_jk, axis=-1) - np.sum(h_hat * np.cross(d_j, d_k), axis=-1)
            flux += sign * dx**2 * float(np.sum(weights * residual))
    return flux / (4.0 * math.pi)


def recompute_diagnostics(fields: Mapping[str, np.ndarray]) -> dict[str, Any]:
    x = fields["x"]
    psi = fields["psi_real"] + 1.0j * fields["psi_imag"]
    h, a, c = fields["h"], fields["a"], fields["c"]
    dx, dv = float(x[1] - x[0]), float(x[1] - x[0]) ** 3
    components, gauge_fixing, auxiliary = numpy_energy(psi, h, a, c, x)
    physical_energy = sum(components.values())
    charge = float(np.sum(c**2) * dv)
    depletion = np.maximum(1.0 - auxiliary["rho"], 0.0)
    depletion_weight = float(np.sum(depletion) * dv)
    X, Y, Z = np.meshgrid(x, x, x, indexing="ij")
    core_length = 0.0 if depletion_weight < 1.0e-12 else 2.0 * math.sqrt(float(np.sum(Z**2 * depletion) * dv) / depletion_weight)
    carrier_radius = math.sqrt(float(np.sum((X**2 + Y**2 + Z**2) * c**2) * dv) / charge)
    omega_c = (components["carrier_gradient"] + components["carrier_quadratic"] + 2.0 * components["carrier_quartic"]) / charge
    cutoff, formal, directional = virial_diagnostics(psi, h, a, c, x, components)
    independent_curvature = np.stack((
        auxiliary["curvature"][..., 0, 1, :], auxiliary["curvature"][..., 0, 2, :], auxiliary["curvature"][..., 1, 2, :]
    ), axis=-2)
    shell1, shell2 = shell_mask(len(x)), shell_mask(len(x), width=2)
    return {
        "physical_energy": physical_energy,
        "charge": charge,
        "charge_relative_error": abs(charge - Q_C) / Q_C,
        "omega_c": omega_c,
        "core_length": core_length,
        "carrier_radius": carrier_radius,
        "physical_gradient_rms": physical_gradient_rms(psi, h, a, c, x),
        "cutoff_virial": cutoff,
        "formal_virial": formal,
        "cutoff_directional_components": directional,
        "outer_flux_rms": float(np.sqrt(np.mean(independent_curvature[shell1] ** 2))),
        "outer_magnetic_number": outer_magnetic_number(h, a, auxiliary["curvature"], dx),
        "gauge_divergence_rms": float(np.sqrt(np.mean(auxiliary["divergence"] ** 2))),
        "gauge_fixing_energy": gauge_fixing,
        "gauge_fixing_fraction": gauge_fixing / max(abs(physical_energy), 1.0e-12),
        "outer_carrier_fraction": float(np.sum(c[shell2] ** 2) / np.sum(c**2)),
        "max_density_depletion": float(np.max(depletion)),
        "boundary_residual": fixed_boundary_residual(psi, h, a, c),
        "energy_components": components,
    }


def quality_gates(completed: bool, diagnostics: Mapping[str, Any] | None) -> dict[str, bool]:
    if not completed or diagnostics is None:
        return {"Q1": False, "Q2": False, "Q3": False, "Q4": False}
    return {
        "Q1": diagnostics["charge_relative_error"] <= 5.0e-12 and diagnostics["boundary_residual"] <= 1.0e-12,
        "Q2": diagnostics["physical_gradient_rms"] <= 3.0e-4 and diagnostics["cutoff_virial"] <= 0.08,
        "Q3": diagnostics["gauge_divergence_rms"] <= 0.02 and diagnostics["gauge_fixing_fraction"] <= 0.01,
        "Q4": diagnostics["outer_flux_rms"] <= 0.05 and abs(diagnostics["outer_magnetic_number"]) <= 1.0e-10,
    }


def all_quality(arm: Mapping[str, Any] | None) -> bool:
    return arm is not None and all(arm["gates"].values())


def localized(arm: Mapping[str, Any]) -> bool:
    values = arm.get("diagnostics")
    return bool(
        all_quality(arm) and values is not None
        and values["outer_carrier_fraction"] <= 1.0e-3
        and values["carrier_radius"] < arm["R"] / 2.0
        and values["omega_c"] < 0.73
        and values["max_density_depletion"] >= 0.10
    )


def relative_difference(left: float, right: float) -> float:
    return abs(left - right) / max(abs(left), abs(right), 1.0e-12)


def comparison_metrics(primary: Mapping[str, Any], other: Mapping[str, Any]) -> dict[str, Any]:
    p, o = primary["diagnostics"], other["diagnostics"]
    assert p is not None and o is not None
    localized_radius = p["outer_carrier_fraction"] <= 0.01 and o["outer_carrier_fraction"] <= 0.01
    radius_difference = (
        relative_difference(p["carrier_radius"], o["carrier_radius"])
        if localized_radius
        else relative_difference(p["carrier_radius"] / primary["R"], o["carrier_radius"] / other["R"])
    )
    result = {
        "energy_relative_difference": relative_difference(p["physical_energy"], o["physical_energy"]),
        "core_length_absolute_difference": abs(p["core_length"] - o["core_length"]),
        "omega_absolute_difference": abs(p["omega_c"] - o["omega_c"]),
        "radius_difference": radius_difference,
        "radius_branch": "absolute" if localized_radius else "normalized",
    }
    result["pass"] = (
        result["energy_relative_difference"] <= 0.05
        and result["core_length_absolute_difference"] <= 0.75
        and result["omega_absolute_difference"] <= 0.10
        and result["radius_difference"] <= 0.10
    )
    return result


def evaluate_quality(arms: Mapping[str, Mapping[str, Any]], selected: str | None) -> dict[str, Any]:
    structural_domain: dict[str, Any] = {}
    for basin in STRUCTURAL:
        primary, domain = arms.get(f"P:{basin}"), arms.get(f"D:{basin}")
        if all_quality(primary) and all_quality(domain):
            assert primary is not None and domain is not None
            structural_domain[basin] = comparison_metrics(primary, domain)
        else:
            structural_domain[basin] = {"pass": False, "reason": "Q1-Q4 failure"}
    primary_control, domain_control = arms.get("P:delocalized"), arms.get("D:delocalized")
    if not (all_quality(primary_control) and all_quality(domain_control)):
        control: dict[str, Any] = {"mode": "invalid", "pass": False, "reason": "Q1-Q4 failure"}
    else:
        assert primary_control is not None and domain_control is not None
        localized_primary, localized_domain = localized(primary_control), localized(domain_control)
        if localized_primary and localized_domain:
            control = {"mode": "localized", **comparison_metrics(primary_control, domain_control)}
        elif not localized_primary and not localized_domain:
            p, d = primary_control["diagnostics"], domain_control["diagnostics"]
            assert p is not None and d is not None
            radius_difference = relative_difference(p["carrier_radius"] / primary_control["R"], d["carrier_radius"] / domain_control["R"])
            quartic_ok = d["energy_components"]["carrier_quartic"] <= p["energy_components"]["carrier_quartic"] + 1.0e-6
            energy_target = abs(d["physical_energy"] - 0.75 * Q_C) / (0.75 * Q_C)
            control = {
                "mode": "dilution", "radius_difference": radius_difference,
                "quartic_nonincrease": quartic_ok,
                "energy_target_relative_difference": energy_target,
                "pass": radius_difference <= 0.10 and quartic_ok and energy_target <= 0.25,
            }
        else:
            control = {
                "mode": "localization_mismatch", "localized_P": localized_primary,
                "localized_D": localized_domain, "pass": False,
            }
    if selected is None or f"H:{selected}" not in arms:
        resolution: dict[str, Any] = {"pass": False, "reason": "no H arm"}
    else:
        primary, high = arms.get(f"P:{selected}"), arms.get(f"H:{selected}")
        if all_quality(primary) and all_quality(high):
            assert primary is not None and high is not None
            resolution = comparison_metrics(primary, high)
        else:
            resolution = {"pass": False, "reason": "Q1-Q4 failure"}
    return {
        "structural_domain": structural_domain,
        "delocalized_control": control,
        "resolution": resolution,
        "quality_all": all(bool(row.get("pass")) for row in structural_domain.values())
        and bool(control.get("pass")) and bool(resolution.get("pass")),
    }


def select_background(arms: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    eligible = [basin for basin in STRUCTURAL if all_quality(arms.get(f"P:{basin}"))]
    if not eligible:
        return {"basin": None, "eligible": []}
    minimum = min(arms[f"P:{basin}"]["diagnostics"]["physical_energy"] for basin in eligible)
    selected = next(
        basin for basin in STRUCTURAL
        if basin in eligible and arms[f"P:{basin}"]["diagnostics"]["physical_energy"] <= minimum + 1.0e-10
    )
    return {"basin": selected, "eligible": eligible}


def run_preflight() -> int:
    if PREFLIGHT_PATH.exists():
        raise FileExistsError(f"Refusing to overwrite frozen preflight: {PREFLIGHT_PATH}")
    source_receipt = read_json(SOURCE_RESULTS_PATH)
    manifest = build_manifest(source_receipt)
    global_failures = list(manifest["required_mismatches"])
    source_verification = read_json(SOURCE_VERIFICATION_PATH)
    if source_receipt.get("verdict") != "INCONCLUSIVE—NUMERICAL QUALITY":
        global_failures.append("source verdict differs from the registered result")
    if not source_verification.get("pass") or source_verification.get("mismatches"):
        global_failures.append("source independent verification receipt is not clean")
    arms: dict[str, Any] = {}
    for family in ("P", "D"):
        for basin in BASINS:
            key = f"{family}:{basin}"
            local: list[dict[str, Any]] = []
            arm = source_receipt.get("arms", {}).get(key)
            if not isinstance(arm, dict):
                mismatch(local, key, "source arm", arm, "missing")
                arms[key] = {"pass": False, "failures": local}
                global_failures.append(f"{key}: missing source arm")
                continue
            artifact_path = source_artifact_path(arm)
            digest = sha256(artifact_path)
            compare_tree(local, f"{key}.artifact_sha256", arm.get("artifact_sha256"), digest)
            fields = load_fields(artifact_path, family, local, f"{key}.artifact")
            reconstruction_receipt: dict[str, Any] | None = None
            c4_residuals: dict[str, float] | None = None
            if fields is not None:
                psi = fields["psi_real"] + 1.0j * fields["psi_imag"]
                c4_residuals = {
                    "psi_real": relative_inf(project_scalar(fields["psi_real"]), fields["psi_real"]),
                    "psi_imag": relative_inf(project_scalar(fields["psi_imag"]), fields["psi_imag"]),
                    "h": relative_inf(project_scalar(fields["h"]), fields["h"]),
                    "a": relative_inf(project_vector(fields["a"]), fields["a"]),
                    "c": relative_inf(project_scalar(fields["c"]), fields["c"]),
                }
                maximum_c4 = max(c4_residuals.values())
                if maximum_c4 > C4_TOL:
                    mismatch(local, f"{key}.C4_relative_inf", f"<= {C4_TOL}", maximum_c4, "symmetry")
                source_boundary = fixed_boundary_residual(psi, fields["h"], fields["a"], fields["c"])
                if source_boundary > BOUNDARY_TOL:
                    mismatch(local, f"{key}.source_boundary", f"<= {BOUNDARY_TOL}", source_boundary, "boundary")
                interior = ~shell_mask(len(fields["x"]))
                if not np.all(fields["c"][interior] > 0.0):
                    mismatch(local, f"{key}.carrier", "strictly positive interior", float(np.min(fields["c"][interior])), "constraint")
                try:
                    reconstructed, reconstruction_receipt = reconstruct_endpoint(fields)
                    if not reconstruction_receipt["raw_finite"]:
                        mismatch(local, f"{key}.raw", "all finite", False, "nonfinite")
                    if reconstruction_receipt["maximum_relative_inf"] > ROUNDTRIP_TOL:
                        mismatch(local, f"{key}.roundtrip", f"<= {ROUNDTRIP_TOL}", reconstruction_receipt["maximum_relative_inf"], "reconstruction")
                    if not all_finite(reconstructed):
                        mismatch(local, f"{key}.reconstructed", "all finite", "nonfinite", "nonfinite")
                    dv = float(fields["x"][1] - fields["x"][0]) ** 3
                    for label, carrier in (("source", fields["c"]), ("reconstructed", reconstructed["c"])):
                        charge_error = abs(float(np.sum(carrier**2) * dv) - Q_C) / Q_C
                        if charge_error > 5.0e-12:
                            mismatch(local, f"{key}.{label}_charge_relative_error", "<= 5e-12", charge_error, "constraint")
                    reconstructed_psi = reconstructed["psi_real"] + 1.0j * reconstructed["psi_imag"]
                    reconstructed_boundary = fixed_boundary_residual(reconstructed_psi, reconstructed["h"], reconstructed["a"], reconstructed["c"])
                    if reconstructed_boundary > BOUNDARY_TOL:
                        mismatch(local, f"{key}.reconstructed_boundary", f"<= {BOUNDARY_TOL}", reconstructed_boundary, "boundary")
                    diagnostics = recompute_diagnostics(reconstructed)
                    if not all_finite(diagnostics):
                        mismatch(local, f"{key}.diagnostics", "all finite", "nonfinite", "nonfinite")
                    reported = arm.get("diagnostics")
                    if not isinstance(reported, dict):
                        mismatch(local, f"{key}.diagnostics", "source diagnostics", reported, "schema")
                    else:
                        for name, expected in diagnostics.items():
                            compare_tree(local, f"{key}.diagnostics.{name}", reported.get(name), expected)
                        for name in ("objective_raw_gradient_rms", "objective_raw_gradient_max"):
                            if not finite_number(reported.get(name)):
                                mismatch(local, f"{key}.diagnostics.{name}", "finite number", reported.get(name), "schema")
                except Exception as error:
                    mismatch(local, f"{key}.reconstruction", "successful reconstruction", repr(error), "exception")
            arms[key] = {
                "artifact": artifact_path.name,
                "artifact_sha256": digest,
                "C4_relative_inf": c4_residuals,
                "reconstruction": reconstruction_receipt,
                "failures": local,
                "pass": not local,
            }
            global_failures.extend(f"{key}: {row['path']}" for row in local)
    report = {
        "schema_version": 1,
        "mode": "preflight",
        "manifest": manifest,
        "arms": arms,
        "failures": global_failures,
        "pass": not global_failures,
    }
    write_json(PREFLIGHT_PATH, report)
    print(json.dumps({"pass": report["pass"], "receipt": str(PREFLIGHT_PATH)}, sort_keys=True))
    return 0 if report["pass"] else 1


def validate_history(history: Any, path: str, out: list[dict[str, Any]]) -> bool:
    start = len(out)
    keys = {"closure", "objective", "physical_energy", "gauge_fixing_energy", "raw_gradient_rms", "raw_gradient_max"}
    if not isinstance(history, list):
        mismatch(out, path, "list", history, "schema")
        return False
    for index, row in enumerate(history):
        row_path = f"{path}[{index}]"
        if not isinstance(row, dict):
            mismatch(out, row_path, "object", row, "schema")
            continue
        if set(row) != keys:
            mismatch(out, f"{row_path}.keys", sorted(keys), sorted(row), "exact")
        compare_tree(out, f"{row_path}.closure", row.get("closure"), index + 1)
        for name in keys - {"closure"}:
            if not finite_number(row.get(name)):
                mismatch(out, f"{row_path}.{name}", "finite number", row.get(name), "nonfinite")
    return len(out) == start


def validate_continuation(continuation: Any, path: str, out: list[dict[str, Any]]) -> bool:
    start = len(out)
    keys = {"settings", "history", "iterations", "closure_calls", "function_evaluations", "wall_seconds", "final"}
    if not isinstance(continuation, dict):
        mismatch(out, path, "continuation object", continuation, "schema")
        return False
    if set(continuation) != keys:
        mismatch(out, f"{path}.keys", sorted(keys), sorted(continuation), "exact")
    compare_tree(out, f"{path}.settings", continuation.get("settings"), CONTINUATION)
    validate_history(continuation.get("history"), f"{path}.history", out)
    counts: dict[str, int] = {}
    for name, upper in (("iterations", 880), ("closure_calls", 1100), ("function_evaluations", 1100)):
        value = continuation.get(name)
        if not isinstance(value, int) or isinstance(value, bool) or value < 1 or value > upper:
            mismatch(out, f"{path}.{name}", f"integer in [1, {upper}]", value, "bound")
        else:
            counts[name] = value
    history = continuation.get("history")
    if isinstance(history, list) and "closure_calls" in counts and len(history) != counts["closure_calls"]:
        mismatch(out, f"{path}.history.length", counts["closure_calls"], len(history), "exact")
    if counts.get("closure_calls") != counts.get("function_evaluations"):
        mismatch(out, f"{path}.closure_evaluation_relation", counts.get("closure_calls"), counts.get("function_evaluations"), "exact")
    wall_seconds = continuation.get("wall_seconds")
    if not finite_nonnegative(wall_seconds):
        mismatch(out, f"{path}.wall_seconds", "finite nonnegative number", wall_seconds, "schema")
    final = continuation.get("final")
    final_keys = {"objective", "physical_energy", "gauge_fixing_energy", "raw_gradient_rms", "raw_gradient_max"}
    if not isinstance(final, dict):
        mismatch(out, f"{path}.final", "object", final, "schema")
    else:
        if set(final) != final_keys:
            mismatch(out, f"{path}.final.keys", sorted(final_keys), sorted(final), "exact")
        for name in final_keys:
            if not finite_number(final.get(name)):
                mismatch(out, f"{path}.final.{name}", "finite number", final.get(name), "nonfinite")
    return len(out) == start


def validate_initial_optimizer(optimizer: Any, path: str, out: list[dict[str, Any]]) -> bool:
    start = len(out)
    keys = {"adam_history", "lbfgs_history", "lbfgs_iterations", "lbfgs_closure_calls", "lbfgs_function_evaluations", "wall_seconds"}
    if not isinstance(optimizer, dict):
        mismatch(out, path, "initial optimizer object", optimizer, "schema")
        return False
    if set(optimizer) != keys:
        mismatch(out, f"{path}.keys", sorted(keys), sorted(optimizer), "exact")
    adam = optimizer.get("adam_history")
    expected_steps = list(range(0, 800, 20)) + [799]
    adam_keys = {"step", "objective", "physical_energy", "gauge_fixing_energy", "raw_gradient_rms", "raw_gradient_max"}
    if not isinstance(adam, list):
        mismatch(out, f"{path}.adam_history", "list", adam, "schema")
    else:
        if len(adam) != len(expected_steps):
            mismatch(out, f"{path}.adam_history.length", len(expected_steps), len(adam), "exact")
        for index, row in enumerate(adam):
            row_path = f"{path}.adam_history[{index}]"
            if not isinstance(row, dict):
                mismatch(out, row_path, "object", row, "schema")
                continue
            if set(row) != adam_keys:
                mismatch(out, f"{row_path}.keys", sorted(adam_keys), sorted(row), "exact")
            if index < len(expected_steps):
                compare_tree(out, f"{row_path}.step", row.get("step"), expected_steps[index])
            for name in adam_keys - {"step"}:
                if not finite_number(row.get(name)):
                    mismatch(out, f"{row_path}.{name}", "finite number", row.get(name), "nonfinite")
    validate_history(optimizer.get("lbfgs_history"), f"{path}.lbfgs_history", out)
    counts: dict[str, int] = {}
    for name, upper in (("lbfgs_iterations", 120), ("lbfgs_closure_calls", 150), ("lbfgs_function_evaluations", 150)):
        value = optimizer.get(name)
        if not isinstance(value, int) or isinstance(value, bool) or value < 1 or value > upper:
            mismatch(out, f"{path}.{name}", f"integer in [1, {upper}]", value, "bound")
        else:
            counts[name] = value
    lbfgs = optimizer.get("lbfgs_history")
    if isinstance(lbfgs, list) and "lbfgs_closure_calls" in counts and len(lbfgs) != counts["lbfgs_closure_calls"]:
        mismatch(out, f"{path}.lbfgs_history.length", counts["lbfgs_closure_calls"], len(lbfgs), "exact")
    if counts.get("lbfgs_closure_calls") != counts.get("lbfgs_function_evaluations"):
        mismatch(out, f"{path}.closure_evaluation_relation", counts.get("lbfgs_closure_calls"), counts.get("lbfgs_function_evaluations"), "exact")
    wall_seconds = optimizer.get("wall_seconds")
    if not finite_nonnegative(wall_seconds):
        mismatch(out, f"{path}.wall_seconds", "finite nonnegative number", wall_seconds, "schema")
    return len(out) == start


def validate_reconstruction(value: Any, path: str, out: list[dict[str, Any]]) -> bool:
    start = len(out)
    expected_fields = {"psi_real", "psi_imag", "h", "a", "c"}
    if not isinstance(value, dict):
        mismatch(out, path, "reconstruction object", value, "schema")
        return False
    if set(value) != {"relative_inf", "maximum_relative_inf", "raw_finite"}:
        mismatch(out, f"{path}.keys", ["maximum_relative_inf", "raw_finite", "relative_inf"], sorted(value), "exact")
    errors = value.get("relative_inf")
    if not isinstance(errors, dict) or set(errors) != expected_fields:
        mismatch(out, f"{path}.relative_inf", sorted(expected_fields), errors, "schema")
    else:
        for name in expected_fields:
            error = errors.get(name)
            if not finite_in_closed_interval(error, ROUNDTRIP_TOL):
                mismatch(out, f"{path}.relative_inf.{name}", f"finite in [0, {ROUNDTRIP_TOL}]", error, "bound")
    maximum = value.get("maximum_relative_inf")
    if not finite_in_closed_interval(maximum, ROUNDTRIP_TOL):
        mismatch(out, f"{path}.maximum_relative_inf", f"finite in [0, {ROUNDTRIP_TOL}]", maximum, "bound")
    compare_tree(out, f"{path}.raw_finite", value.get("raw_finite"), True)
    return len(out) == start


def verify_arm(
    key: str, row: Any, source_receipt: Mapping[str, Any], out: list[dict[str, Any]]
) -> dict[str, Any] | None:
    path = f"arms.{key}"
    expected_keys = {
        "family", "basin", "R", "N", "dx", "source_artifact", "source_artifact_sha256",
        "reconstruction", "artifact", "artifact_sha256", "completed", "error", "optimizer", "diagnostics", "gates",
    }
    if not isinstance(row, dict):
        mismatch(out, path, "arm object", row, "schema")
        return None
    if set(row) != expected_keys:
        mismatch(out, f"{path}.keys", sorted(expected_keys), sorted(row), "exact")
    if ":" not in key:
        mismatch(out, path, "family:basin key", key, "schema")
        return None
    family, basin = key.split(":", 1)
    if family not in GRIDS or basin not in BASINS:
        mismatch(out, path, "registered family and basin", key, "schema")
        return None
    compare_tree(out, f"{path}.family", row.get("family"), family)
    compare_tree(out, f"{path}.basin", row.get("basin"), basin)
    r_box, n = GRIDS[family]
    compare_tree(out, f"{path}.R", row.get("R"), r_box)
    compare_tree(out, f"{path}.N", row.get("N"), n)
    compare_tree(out, f"{path}.dx", row.get("dx"), 2.0 * r_box / (n - 1))
    completed = row.get("completed") is True
    if not isinstance(row.get("completed"), bool):
        mismatch(out, f"{path}.completed", "boolean", row.get("completed"), "schema")
    optimizer = row.get("optimizer")
    schedule_ok = True
    if not isinstance(optimizer, dict) or set(optimizer) != {"initial", "continuation"}:
        mismatch(out, f"{path}.optimizer", {"initial", "continuation"}, optimizer, "schema")
        schedule_ok = False
    else:
        if family == "H":
            schedule_ok = validate_initial_optimizer(optimizer.get("initial"), f"{path}.optimizer.initial", out) and schedule_ok
        else:
            compare_tree(out, f"{path}.optimizer.initial", optimizer.get("initial"), None)
        schedule_ok = validate_continuation(optimizer.get("continuation"), f"{path}.optimizer.continuation", out) and schedule_ok
    if not completed:
        for name in ("source_artifact", "source_artifact_sha256", "reconstruction", "artifact", "artifact_sha256", "diagnostics"):
            compare_tree(out, f"{path}.{name}", row.get(name), None)
        if not isinstance(row.get("error"), str) or not row.get("error"):
            mismatch(out, f"{path}.error", "nonempty string", row.get("error"), "schema")
        expected_gates = quality_gates(False, None)
        compare_tree(out, f"{path}.gates", row.get("gates"), expected_gates)
        return {"family": family, "basin": basin, "R": r_box, "N": n, "completed": False, "diagnostics": None, "gates": expected_gates, "schedule_ok": False}
    compare_tree(out, f"{path}.error", row.get("error"), None)
    if family in ("P", "D"):
        source_arm = source_receipt.get("arms", {}).get(key, {})
        expected_source = f"fields_{family}_{basin}.npz"
        compare_tree(out, f"{path}.source_artifact", row.get("source_artifact"), expected_source)
        compare_tree(out, f"{path}.source_artifact_sha256", row.get("source_artifact_sha256"), source_arm.get("artifact_sha256"))
        schedule_ok = validate_reconstruction(row.get("reconstruction"), f"{path}.reconstruction", out) and schedule_ok
    else:
        compare_tree(out, f"{path}.source_artifact", row.get("source_artifact"), None)
        compare_tree(out, f"{path}.source_artifact_sha256", row.get("source_artifact_sha256"), None)
        compare_tree(out, f"{path}.reconstruction", row.get("reconstruction"), None)
    artifact_name = f"fields_{family}_{basin}.npz"
    compare_tree(out, f"{path}.artifact", row.get("artifact"), artifact_name)
    artifact_path = RUN_DIR / artifact_name
    if not artifact_path.is_file():
        mismatch(out, f"{path}.artifact", "existing artifact", str(artifact_path), "missing")
        return None
    digest = sha256(artifact_path)
    compare_tree(out, f"{path}.artifact_sha256", row.get("artifact_sha256"), digest)
    fields = load_fields(artifact_path, family, out, f"{path}.artifact")
    if fields is None:
        return None
    psi = fields["psi_real"] + 1.0j * fields["psi_imag"]
    symmetry = max(
        relative_inf(project_scalar(fields["psi_real"]), fields["psi_real"]),
        relative_inf(project_scalar(fields["psi_imag"]), fields["psi_imag"]),
        relative_inf(project_scalar(fields["h"]), fields["h"]),
        relative_inf(project_vector(fields["a"]), fields["a"]),
        relative_inf(project_scalar(fields["c"]), fields["c"]),
    )
    if symmetry > C4_TOL:
        mismatch(out, f"{path}.C4_relative_inf", f"<= {C4_TOL}", symmetry, "symmetry")
    boundary = fixed_boundary_residual(psi, fields["h"], fields["a"], fields["c"])
    if boundary > BOUNDARY_TOL:
        mismatch(out, f"{path}.boundary", f"<= {BOUNDARY_TOL}", boundary, "boundary")
    try:
        diagnostics = recompute_diagnostics(fields)
    except Exception as error:
        mismatch(out, f"{path}.diagnostics", "independently recomputable", repr(error), "recompute")
        return None
    reported = row.get("diagnostics")
    expected_diagnostic_keys = set(diagnostics) | {"objective_raw_gradient_rms", "objective_raw_gradient_max"}
    if not isinstance(reported, dict):
        mismatch(out, f"{path}.diagnostics", "object", reported, "schema")
    else:
        if set(reported) != expected_diagnostic_keys:
            mismatch(out, f"{path}.diagnostics.keys", sorted(expected_diagnostic_keys), sorted(reported), "exact")
        for name, expected in diagnostics.items():
            if name in reported:
                compare_tree(out, f"{path}.diagnostics.{name}", reported[name], expected)
        for name in ("objective_raw_gradient_rms", "objective_raw_gradient_max"):
            value = reported.get(name)
            if not finite_nonnegative(value):
                mismatch(out, f"{path}.diagnostics.{name}", "finite nonnegative number", value, "nonfinite")
    gates = quality_gates(True, diagnostics)
    compare_tree(out, f"{path}.gates", row.get("gates"), gates)
    return {
        "family": family, "basin": basin, "R": r_box, "N": n,
        "completed": True, "diagnostics": diagnostics, "gates": gates,
        "schedule_ok": schedule_ok and all_finite(diagnostics),
    }


def preliminary_verdict(r1: bool, r2: bool, r3: bool, r5: bool, r6: bool) -> str:
    if not r1 or not r2:
        return "INCONCLUSIVE—IMPLEMENTATION PREFLIGHT"
    if not r3:
        return "INCONCLUSIVE—EXECUTION OR VERIFICATION"
    if not r5:
        return "FAIL—NO Q2-QUALIFIED PRIMARY BACKGROUND"
    if not r6:
        return "PASS—Q2-QUALIFIED PRIMARY BACKGROUND"
    return "PASS—Q2-QUALIFIED DOMAIN-AND-RESOLUTION BACKGROUND"


def run_final_verification() -> int:
    if VERIFICATION_PATH.exists():
        raise FileExistsError(f"Refusing to overwrite frozen verification: {VERIFICATION_PATH}")
    source_receipt = read_json(SOURCE_RESULTS_PATH)
    preflight = read_json(PREFLIGHT_PATH)
    receipt = read_json(RESULTS_PATH)
    manifest = build_manifest(source_receipt)
    mismatches: list[dict[str, Any]] = []
    compare_tree(mismatches, "manifest", receipt.get("manifest"), manifest)
    compare_tree(mismatches, "preflight.manifest", preflight.get("manifest"), manifest)
    compare_tree(mismatches, "schema_version", receipt.get("schema_version"), 1)
    compare_tree(mismatches, "status", receipt.get("status"), "complete")
    compare_tree(mismatches, "coefficients", receipt.get("coefficients"), COEFFICIENTS)
    compare_tree(mismatches, "grids", receipt.get("grids"), {name: list(value) for name, value in GRIDS.items()})
    compare_tree(mismatches, "basins", receipt.get("basins"), list(BASINS))
    compare_tree(mismatches, "structural_basins", receipt.get("structural_basins"), list(STRUCTURAL))
    compare_tree(mismatches, "continuation", receipt.get("continuation"), CONTINUATION)
    compare_tree(mismatches, "preflight.pass", preflight.get("pass"), True)
    primary_preflight = receipt.get("preflight")
    if not isinstance(primary_preflight, dict):
        mismatch(mismatches, "receipt.preflight", "object", primary_preflight, "schema")
        primary_preflight_pass = False
    else:
        primary_preflight_pass = primary_preflight.get("pass") is True
        compare_tree(mismatches, "receipt.preflight.pass", primary_preflight.get("pass"), True)
        compare_tree(mismatches, "receipt.preflight.failures", primary_preflight.get("failures"), [])
        expected_source_keys = {f"{family}:{basin}" for family in ("P", "D") for basin in BASINS}
        if not isinstance(primary_preflight.get("arms"), dict) or set(primary_preflight.get("arms", {})) != expected_source_keys:
            mismatch(mismatches, "receipt.preflight.arms", sorted(expected_source_keys), primary_preflight.get("arms"), "schema")
        else:
            for key, row in primary_preflight["arms"].items():
                if not isinstance(row, dict) or row.get("pass") is not True or row.get("failures") != []:
                    mismatch(mismatches, f"receipt.preflight.arms.{key}", "passing arm", row, "preflight")
    rows = receipt.get("arms")
    if not isinstance(rows, dict):
        mismatch(mismatches, "arms", "object", rows, "schema")
        rows = {}
    verified: dict[str, dict[str, Any]] = {}
    for family in ("P", "D"):
        for basin in BASINS:
            key = f"{family}:{basin}"
            arm = verify_arm(key, rows.get(key), source_receipt, mismatches)
            if arm is not None:
                verified[key] = arm
    selection = select_background(verified)
    selected = selection["basin"]
    if selected is not None:
        h_key = f"H:{selected}"
        h_arm = verify_arm(h_key, rows.get(h_key), source_receipt, mismatches)
        if h_arm is not None:
            verified[h_key] = h_arm
    expected_keys = {f"{family}:{basin}" for family in ("P", "D") for basin in BASINS}
    if selected is not None:
        expected_keys.add(f"H:{selected}")
    if set(rows) != expected_keys:
        mismatch(mismatches, "arms.keys", sorted(expected_keys), sorted(rows), "exact")
    compare_tree(mismatches, "h_selection", receipt.get("h_selection"), selection)
    expected_order = [f"P:{basin}" for basin in BASINS]
    if selected is not None:
        expected_order.append(f"H:{selected}")
    expected_order.extend(f"D:{basin}" for basin in BASINS)
    compare_tree(mismatches, "run_order", receipt.get("run_order"), expected_order)
    r1 = not manifest["required_mismatches"]
    r2 = preflight.get("pass") is True and primary_preflight_pass
    r3 = (
        receipt.get("run_order") == expected_order and set(verified) == expected_keys
        and all(arm["completed"] and arm["diagnostics"] is not None and arm["schedule_ok"] for arm in verified.values())
    )
    r5 = selected is not None
    quality = evaluate_quality(verified, selected)
    r6 = bool(quality["quality_all"])
    compare_tree(mismatches, "source_quality_gates", receipt.get("source_quality_gates"), quality)
    expected_primary_gates = {"R1": r1, "R2": r2, "R3": r3, "R4": None, "R5": r5, "R6": r6}
    compare_tree(mismatches, "recovery_gates", receipt.get("recovery_gates"), expected_primary_gates)
    expected_primary_verdict = preliminary_verdict(r1, r2, r3, r5, r6)
    compare_tree(mismatches, "primary_verdict", receipt.get("primary_verdict"), expected_primary_verdict)
    r4 = not mismatches
    verdict = expected_primary_verdict if r4 else "INCONCLUSIVE—EXECUTION OR VERIFICATION"
    report = {
        "schema_version": 1,
        "pass": r4,
        "verdict": verdict,
        "primary_verdict": receipt.get("primary_verdict"),
        "manifest": manifest,
        "recovery_gates": {"R1": r1, "R2": r2, "R3": r3, "R4": r4, "R5": r5, "R6": r6},
        "selection": selection,
        "quality_gates": quality,
        "mismatches": mismatches,
        "verified_arms": verified,
    }
    write_json(VERIFICATION_PATH, report)
    print(json.dumps({"pass": report["pass"], "verdict": verdict, "receipt": str(VERIFICATION_PATH)}, sort_keys=True))
    return 0 if report["pass"] else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", action="store_true", help="validate all twelve frozen source endpoints before optimization")
    arguments = parser.parse_args(argv)
    return run_preflight() if arguments.preflight else run_final_verification()


if __name__ == "__main__":
    raise SystemExit(main())
