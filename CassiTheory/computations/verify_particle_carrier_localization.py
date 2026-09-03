#!/usr/bin/env python3
"""Independently verify the particle carrier localization campaign."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import torch

import verify_particle_stationary_q2_recovery_v2 as independent  # pyright: ignore[reportMissingImports]


ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / "runs" / "20260902_particle_carrier_localization"
PREFLIGHT_PATH = RUN_DIR / "preflight_verification.json"
RESULTS_PATH = RUN_DIR / "results.json"
VERIFICATION_PATH = RUN_DIR / "verification.json"
MANIFEST_PATH = ROOT / "computations" / "particle_carrier_localization_manifest.json"
SOURCE_ARTIFACT = ROOT / "runs" / "20260902_particle_stationary_precision_v5" / "fields_block01.npz"
SOURCE_RESULTS = ROOT / "runs" / "20260902_particle_stationary_precision_v5" / "results.json"
SOURCE_VERIFICATION = ROOT / "runs" / "20260902_particle_stationary_precision_v5" / "verification.json"
SOURCE_HASHES = {
    "artifact": "ac4c54fa0e5ed61f73cb86b5e83d0061806fc2e5d1725894bad9e8e89457a61e",
    "results": "9decc9a751d7c833f92754eb3e5187da9056bc5ddda0c9bd125e188f4e90cfa5",
    "verification": "7667c9617c3e4bd237e77e84226c78805d224002a18a192f25cce24cd2ce4b32",
}
PHI = (1.0 + math.sqrt(5.0)) / 2.0
FIXED_COEFFICIENTS = {
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
    "u_C": 1.0,
    "q_C": 4.0,
    "L_s": 1.0,
    "xi_gf": 1.0,
}
SOURCE_H_C = 1.5
OMEGA_LIMIT = 0.73
PRECISION_GRADIENT_LIMIT = 1.20e-4
PRIMARY_MAX_BLOCKS = 4
COMPARISON_MAX_BLOCKS = 6
CANDIDATES = (
    {"label": "half_reference", "multiplier": 0.50, "h_C": 2.9598260763447164},
    {"label": "three_quarters_reference", "multiplier": 0.75, "h_C": 4.439739114517074},
    {"label": "reference", "multiplier": 1.00, "h_C": 5.919652152689433},
    {"label": "five_quarters_reference", "multiplier": 1.25, "h_C": 7.399565190861791},
    {"label": "three_halves_reference", "multiplier": 1.50, "h_C": 8.879478229034149},
)
ABS_TOL = 1.0e-8
REL_TOL = 1.0e-6


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root is not an object: {path}")
    return value


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def coefficient_vector(h_c: float) -> dict[str, float]:
    return {**FIXED_COEFFICIENTS, "h_C": float(h_c)}


def expected_source_manifest() -> dict[str, Any]:
    return {
        "artifact": str(SOURCE_ARTIFACT.relative_to(ROOT)).replace("\\", "/"),
        "artifact_sha256": SOURCE_HASHES["artifact"],
        "results": str(SOURCE_RESULTS.relative_to(ROOT)).replace("\\", "/"),
        "results_sha256": SOURCE_HASHES["results"],
        "verification": str(SOURCE_VERIFICATION.relative_to(ROOT)).replace("\\", "/"),
        "verification_sha256": SOURCE_HASHES["verification"],
        "selected_block": 1,
        "source_h_C": SOURCE_H_C,
    }


def expected_schedule() -> dict[str, Any]:
    return {
        "precision_gradient_limit": PRECISION_GRADIENT_LIMIT,
        "omega_limit": OMEGA_LIMIT,
        "primary_max_blocks": PRIMARY_MAX_BLOCKS,
        "comparison_max_blocks": COMPARISON_MAX_BLOCKS,
        "primary_families": ["P"],
        "comparison_families": ["D", "H"],
        "comparison_basin": "separated_core",
        "continuation": independent.CONTINUATION,
    }


def verify_manifest(out: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str | None]:
    try:
        manifest = read_json(MANIFEST_PATH)
    except Exception as error:
        independent.mismatch(out, "manifest", "readable JSON object", repr(error), "read")
        return None, None
    independent.compare_tree(
        out,
        "manifest.schema",
        manifest.get("schema"),
        "cassi.particle-carrier-localization.manifest.v1",
    )
    independent.compare_tree(out, "manifest.source", manifest.get("source"), expected_source_manifest())
    independent.compare_tree(
        out,
        "manifest.fixed_coefficients",
        manifest.get("fixed_coefficients"),
        FIXED_COEFFICIENTS,
    )
    independent.compare_tree(out, "manifest.candidates", manifest.get("candidates"), list(CANDIDATES))
    independent.compare_tree(out, "manifest.schedule", manifest.get("schedule"), expected_schedule())
    hashes = manifest.get("sha256")
    if not isinstance(hashes, dict) or not hashes:
        independent.mismatch(out, "manifest.sha256", "nonempty object", hashes, "schema")
    else:
        for relative, expected in hashes.items():
            path = ROOT / relative
            actual = sha256_file(path) if path.is_file() else "MISSING"
            if actual != expected:
                independent.mismatch(
                    out, f"manifest.sha256.{relative}", expected, actual, "hash"
                )
    return manifest, sha256_file(MANIFEST_PATH)


def numpy_energy_variable(
    psi: np.ndarray,
    h: np.ndarray,
    a: np.ndarray,
    c: np.ndarray,
    x: np.ndarray,
    h_c: float,
) -> tuple[dict[str, float], float, dict[str, np.ndarray]]:
    dx = float(x[1] - x[0])
    dv = dx**3
    dpsi = np.stack(independent.gradient(psi, dx), axis=-2)
    gauge_psi = np.einsum(
        "...ia,abc,...c->...ib",
        a.astype(np.complex128),
        independent.SIGMA / 2.0,
        psi,
    )
    covariant_psi = dpsi - 1.0j * gauge_psi
    rho = np.sum(np.abs(psi) ** 2, axis=-1)
    spin = np.einsum(
        "...b,abc,...c->...a", psi.conj(), independent.SIGMA, psi
    ).real
    delta_phi = 0.5 * (
        (1.0 - PHI) * rho + (1.0 + PHI) * np.sum(h * spin, axis=-1)
    )
    da = independent.gradient(a, dx)
    curvature = np.stack(
        tuple(
            np.stack(
                tuple(
                    da[i][..., j, :]
                    - da[j][..., i, :]
                    + np.cross(a[..., i, :], a[..., j, :])
                    for j in range(3)
                ),
                axis=-2,
            )
            for i in range(3)
        ),
        axis=-3,
    )
    dh = np.stack(independent.gradient(h, dx), axis=-2)
    covariant_h = dh + np.cross(a, np.broadcast_to(h[..., None, :], a.shape))
    dc = np.stack(independent.gradient(c, dx), axis=-1)
    divergence = np.stack(tuple(da[i][..., i, :] for i in range(3)), axis=0).sum(axis=0)
    components = {
        "psi_gradient": FIXED_COEFFICIENTS["alpha_s"]
        * 0.5
        * float(np.sum(np.abs(covariant_psi) ** 2) * dv),
        "rho_potential": FIXED_COEFFICIENTS["u_rho"]
        / 4.0
        * float(np.sum((rho - 1.0) ** 2) * dv),
        "composition_potential": FIXED_COEFFICIENTS["u_phi"]
        / 2.0
        * float(np.sum(delta_phi**2) * dv),
        "curvature": FIXED_COEFFICIENTS["gamma_x"]
        / 4.0
        * float(np.sum(curvature**2) * dv),
        "h_gradient": FIXED_COEFFICIENTS["gamma_x"]
        / 2.0
        * float(np.sum(covariant_h**2) * dv),
        "h_potential": FIXED_COEFFICIENTS["u_H"]
        / 4.0
        * float(np.sum((np.sum(h**2, axis=-1) - 1.0) ** 2) * dv),
        "carrier_gradient": FIXED_COEFFICIENTS["k_Cx"]
        / 2.0
        * float(np.sum(dc**2) * dv),
        "carrier_quadratic": float(
            np.sum((FIXED_COEFFICIENTS["e_C"] - h_c * (1.0 - rho)) * c**2)
            * dv
        ),
        "carrier_quartic": FIXED_COEFFICIENTS["u_C"]
        / 2.0
        * float(np.sum(c**4) * dv),
    }
    gauge_fixing = (
        FIXED_COEFFICIENTS["xi_gf"]
        / 2.0
        * float(np.sum(divergence**2) * dv)
    )
    return components, gauge_fixing, {
        "rho": rho,
        "curvature": curvature,
        "divergence": divergence,
    }


def torch_physical_energy_variable(
    psi_real: torch.Tensor,
    psi_imag: torch.Tensor,
    h: torch.Tensor,
    a: torch.Tensor,
    c: torch.Tensor,
    dx: float,
    h_c: float,
) -> torch.Tensor:
    psi = torch.complex(psi_real, psi_imag)
    sigma = torch.tensor(independent.SIGMA, dtype=torch.complex128)
    dpsi = torch.stack(
        torch.gradient(
            psi, spacing=(dx, dx, dx), dim=(0, 1, 2), edge_order=2
        ),
        dim=-2,
    )
    gauge_psi = torch.einsum(
        "...ia,abc,...c->...ib", a.to(torch.complex128), sigma / 2.0, psi
    )
    covariant_psi = dpsi - 1.0j * gauge_psi
    rho = torch.sum(torch.abs(psi) ** 2, dim=-1)
    spin = torch.einsum("...b,abc,...c->...a", psi.conj(), sigma, psi).real
    delta_phi = 0.5 * (
        (1.0 - PHI) * rho + (1.0 + PHI) * torch.sum(h * spin, dim=-1)
    )
    da = torch.gradient(
        a, spacing=(dx, dx, dx), dim=(0, 1, 2), edge_order=2
    )
    curvature = torch.stack(
        tuple(
            torch.stack(
                tuple(
                    da[i][..., j, :]
                    - da[j][..., i, :]
                    + torch.cross(a[..., i, :], a[..., j, :], dim=-1)
                    for j in range(3)
                ),
                dim=-2,
            )
            for i in range(3)
        ),
        dim=-3,
    )
    dh = torch.stack(
        torch.gradient(
            h, spacing=(dx, dx, dx), dim=(0, 1, 2), edge_order=2
        ),
        dim=-2,
    )
    covariant_h = dh + torch.cross(a, h[..., None, :].expand_as(a), dim=-1)
    dc = torch.stack(
        torch.gradient(
            c, spacing=(dx, dx, dx), dim=(0, 1, 2), edge_order=2
        ),
        dim=-1,
    )
    dv = dx**3
    terms = (
        FIXED_COEFFICIENTS["alpha_s"]
        * 0.5
        * torch.sum(torch.abs(covariant_psi) ** 2)
        * dv,
        FIXED_COEFFICIENTS["u_rho"]
        / 4.0
        * torch.sum((rho - 1.0) ** 2)
        * dv,
        FIXED_COEFFICIENTS["u_phi"]
        / 2.0
        * torch.sum(delta_phi**2)
        * dv,
        FIXED_COEFFICIENTS["gamma_x"]
        / 4.0
        * torch.sum(curvature**2)
        * dv,
        FIXED_COEFFICIENTS["gamma_x"]
        / 2.0
        * torch.sum(covariant_h**2)
        * dv,
        FIXED_COEFFICIENTS["u_H"]
        / 4.0
        * torch.sum((torch.sum(h**2, dim=-1) - 1.0) ** 2)
        * dv,
        FIXED_COEFFICIENTS["k_Cx"]
        / 2.0
        * torch.sum(dc**2)
        * dv,
        torch.sum(
            (FIXED_COEFFICIENTS["e_C"] - h_c * (1.0 - rho)) * c**2
        )
        * dv,
        FIXED_COEFFICIENTS["u_C"] / 2.0 * torch.sum(c**4) * dv,
    )
    return torch.stack(terms).sum()


def recompute_diagnostics(
    fields: Mapping[str, np.ndarray], h_c: float
) -> dict[str, Any]:
    original_numpy_energy = independent.numpy_energy
    original_torch_energy = independent.torch_physical_energy

    def numpy_bound(
        psi: np.ndarray,
        h: np.ndarray,
        a: np.ndarray,
        c: np.ndarray,
        x: np.ndarray,
    ) -> tuple[dict[str, float], float, dict[str, np.ndarray]]:
        return numpy_energy_variable(psi, h, a, c, x, h_c)

    def torch_bound(
        psi_real: torch.Tensor,
        psi_imag: torch.Tensor,
        h: torch.Tensor,
        a: torch.Tensor,
        c: torch.Tensor,
        dx: float,
    ) -> torch.Tensor:
        return torch_physical_energy_variable(
            psi_real, psi_imag, h, a, c, dx, h_c
        )

    independent.numpy_energy = numpy_bound
    independent.torch_physical_energy = torch_bound
    try:
        return independent.recompute_diagnostics(fields)
    finally:
        independent.numpy_energy = original_numpy_energy
        independent.torch_physical_energy = original_torch_energy


def physical_diagnostics_only(diagnostics: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in diagnostics.items()
        if key not in {"objective_raw_gradient_rms", "objective_raw_gradient_max"}
    }


def source_balance(diagnostics: Mapping[str, Any]) -> dict[str, float]:
    components = diagnostics["energy_components"]
    charge = float(diagnostics["charge"])
    depletion_overlap = (
        FIXED_COEFFICIENTS["e_C"] * charge
        - float(components["carrier_quadratic"])
    ) / SOURCE_H_C
    quartic_integral = (
        2.0 * float(components["carrier_quartic"]) / FIXED_COEFFICIENTS["u_C"]
    )
    positive_cost = float(components["carrier_gradient"]) + (
        FIXED_COEFFICIENTS["u_C"] * quartic_integral
    )
    return {
        "depletion_overlap": depletion_overlap,
        "quartic_integral": quartic_integral,
        "positive_cost": positive_cost,
        "source_retention_margin": float(diagnostics["omega_c"])
        - FIXED_COEFFICIENTS["e_C"],
        "zero_margin_h_C": positive_cost / depletion_overlap,
        "reference_h_C": (
            positive_cost
            + charge * (FIXED_COEFFICIENTS["e_C"] - OMEGA_LIMIT)
        )
        / depletion_overlap,
    }


def quality_checks(diagnostics: Mapping[str, Any] | None) -> dict[str, bool]:
    if diagnostics is None:
        return {
            "charge_and_boundary": False,
            "physical_stationarity": False,
            "gauge_control": False,
            "outer_flux_control": False,
        }
    return {
        "charge_and_boundary": (
            float(diagnostics["charge_relative_error"]) <= 5.0e-12
            and float(diagnostics["boundary_residual"]) <= 1.0e-12
        ),
        "physical_stationarity": (
            float(diagnostics["physical_gradient_rms"]) <= PRECISION_GRADIENT_LIMIT
            and float(diagnostics["cutoff_virial"]) <= 0.08
        ),
        "gauge_control": (
            float(diagnostics["gauge_divergence_rms"]) <= 0.02
            and float(diagnostics["gauge_fixing_fraction"]) <= 0.01
        ),
        "outer_flux_control": (
            float(diagnostics["outer_flux_rms"]) <= 0.05
            and abs(float(diagnostics["outer_magnetic_number"])) <= 1.0e-10
        ),
    }


def localization_checks(
    diagnostics: Mapping[str, Any] | None, radius_limit: float
) -> dict[str, bool]:
    if diagnostics is None:
        return {
            "outer_carrier_fraction": False,
            "carrier_radius": False,
            "retention_margin": False,
            "density_depletion": False,
        }
    return {
        "outer_carrier_fraction": float(diagnostics["outer_carrier_fraction"])
        <= 1.0e-3,
        "carrier_radius": float(diagnostics["carrier_radius"]) < radius_limit,
        "retention_margin": float(diagnostics["omega_c"]) < OMEGA_LIMIT,
        "density_depletion": float(diagnostics["max_density_depletion"]) >= 0.10,
    }


def compare_metrics(primary: Mapping[str, Any], other: Mapping[str, Any]) -> dict[str, Any]:
    p = primary["diagnostics"]
    o = other["diagnostics"]

    def relative_difference(left: float, right: float) -> float:
        return abs(left - right) / max(abs(left), abs(right), 1.0e-12)

    result = {
        "energy_relative_difference": relative_difference(
            float(p["physical_energy"]), float(o["physical_energy"])
        ),
        "core_length_absolute_difference": abs(
            float(p["core_length"]) - float(o["core_length"])
        ),
        "omega_absolute_difference": abs(float(p["omega_c"]) - float(o["omega_c"])),
        "radius_relative_difference": relative_difference(
            float(p["carrier_radius"]), float(o["carrier_radius"])
        ),
    }
    result["pass"] = (
        result["energy_relative_difference"] <= 0.05
        and result["core_length_absolute_difference"] <= 0.75
        and result["omega_absolute_difference"] <= 0.10
        and result["radius_relative_difference"] <= 0.10
    )
    return result


def selected_source_row(out: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    for name, path, expected_hash in (
        ("source.artifact", SOURCE_ARTIFACT, SOURCE_HASHES["artifact"]),
        ("source.results", SOURCE_RESULTS, SOURCE_HASHES["results"]),
        ("source.verification", SOURCE_VERIFICATION, SOURCE_HASHES["verification"]),
    ):
        actual_hash = sha256_file(path) if path.is_file() else "MISSING"
        if actual_hash != expected_hash:
            independent.mismatch(out, name, expected_hash, actual_hash, "hash")
    try:
        results = read_json(SOURCE_RESULTS)
        verification = read_json(SOURCE_VERIFICATION)
    except Exception as error:
        independent.mismatch(out, "source.receipts", "readable JSON", repr(error), "read")
        return None, None
    independent.compare_tree(
        out,
        "source.results.primary_verdict",
        results.get("primary_verdict"),
        "PASS—HIGHER-PRECISION BACKGROUND",
    )
    independent.compare_tree(out, "source.results.selected_block", results.get("selected_block"), 1)
    independent.compare_tree(
        out,
        "source.results.selected_artifact_sha256",
        results.get("selected_artifact_sha256"),
        SOURCE_HASHES["artifact"],
    )
    independent.compare_tree(out, "source.verification.pass", verification.get("pass"), True)
    independent.compare_tree(out, "source.verification.mismatches", verification.get("mismatches"), [])
    independent.compare_tree(
        out,
        "source.verification.selected_artifact_sha256",
        verification.get("selected_artifact_sha256"),
        SOURCE_HASHES["artifact"],
    )
    selected = next(
        (row for row in results.get("blocks", []) if row.get("block") == 1), None
    )
    if not isinstance(selected, dict):
        independent.mismatch(out, "source.selected", "selected block object", selected, "schema")
        return None, verification
    return selected, verification


def verify_source(out: list[dict[str, Any]]) -> dict[str, Any] | None:
    selected, _ = selected_source_row(out)
    fields = independent.load_fields(SOURCE_ARTIFACT, "P", out, "source.artifact")
    if selected is None or fields is None:
        return None
    fresh = recompute_diagnostics(fields, SOURCE_H_C)
    reported = selected.get("diagnostics")
    if not isinstance(reported, dict):
        independent.mismatch(out, "source.diagnostics", "object", reported, "schema")
        return None
    independent.compare_tree(
        out,
        "source.diagnostics",
        fresh,
        physical_diagnostics_only(reported),
    )
    balance = source_balance(fresh)
    reference = balance["reference_h_C"]
    for index, candidate in enumerate(CANDIDATES):
        independent.compare_tree(
            out,
            f"candidate_formula[{index}]",
            candidate["h_C"],
            candidate["multiplier"] * reference,
        )
    return {
        "diagnostics": fresh,
        "retention_balance": balance,
        "quality_checks": quality_checks(fresh),
        "localization_checks": localization_checks(fresh, 2.0),
    }


def run_preflight() -> int:
    mismatches: list[dict[str, Any]] = []
    if RUN_DIR.exists():
        existing = sorted(path.name for path in RUN_DIR.iterdir())
        if existing:
            independent.mismatch(
                mismatches, "output_freshness", [], existing, "immutable_output"
            )
    manifest, manifest_sha256 = verify_manifest(mismatches)
    source = verify_source(mismatches)
    if source is not None:
        independent.compare_tree(
            mismatches,
            "source.quality_checks",
            source["quality_checks"],
            {
                "charge_and_boundary": True,
                "physical_stationarity": True,
                "gauge_control": True,
                "outer_flux_control": True,
            },
        )
        expected_localization = {
            "outer_carrier_fraction": False,
            "carrier_radius": False,
            "retention_margin": False,
            "density_depletion": True,
        }
        independent.compare_tree(
            mismatches,
            "source.localization_checks",
            source["localization_checks"],
            expected_localization,
        )
    report = {
        "schema": "cassi.particle-carrier-localization.preflight.v1",
        "pass": not mismatches and manifest is not None and source is not None,
        "manifest_sha256": manifest_sha256,
        "mismatches": mismatches,
        "source": source,
    }
    write_json(PREFLIGHT_PATH, report)
    print(json.dumps({"pass": report["pass"], "mismatches": len(mismatches)}, sort_keys=True))
    return 0 if report["pass"] else 1


def validate_block(
    out: list[dict[str, Any]],
    path: str,
    block: Any,
    family: str,
    h_c: float,
    expected_index: int,
    allowed_artifacts: set[str],
) -> dict[str, Any] | None:
    if not isinstance(block, dict):
        independent.mismatch(out, path, "block object", block, "schema")
        return None
    independent.compare_tree(out, f"{path}.block", block.get("block"), expected_index)
    independent.validate_continuation(block.get("optimizer"), f"{path}.optimizer", out)
    if not independent.finite_nonnegative(block.get("wall_seconds_total")):
        independent.mismatch(
            out,
            f"{path}.wall_seconds_total",
            "finite nonnegative number",
            block.get("wall_seconds_total"),
            "schema",
        )
    artifact = block.get("artifact")
    if not isinstance(artifact, str) or Path(artifact).name != artifact:
        independent.mismatch(out, f"{path}.artifact", "local NPZ filename", artifact, "path")
        return None
    allowed_artifacts.add(artifact)
    artifact_path = RUN_DIR / artifact
    actual_hash = sha256_file(artifact_path) if artifact_path.is_file() else "MISSING"
    independent.compare_tree(
        out, f"{path}.artifact_sha256", block.get("artifact_sha256"), actual_hash
    )
    fields = independent.load_fields(artifact_path, family, out, f"{path}.artifact")
    if fields is None:
        return None
    fresh = recompute_diagnostics(fields, h_c)
    reported = block.get("diagnostics")
    if not isinstance(reported, dict):
        independent.mismatch(out, f"{path}.diagnostics", "object", reported, "schema")
        return None
    independent.compare_tree(
        out,
        f"{path}.diagnostics",
        fresh,
        physical_diagnostics_only(reported),
    )
    quality = quality_checks(fresh)
    localization = localization_checks(
        fresh, (4.0 if family in ("P", "H") else 5.0) / 2.0
    )
    qualified = all(quality.values())
    localized = qualified and all(localization.values())
    independent.compare_tree(out, f"{path}.quality_checks", block.get("quality_checks"), quality)
    independent.compare_tree(
        out, f"{path}.localization_checks", block.get("localization_checks"), localization
    )
    independent.compare_tree(
        out, f"{path}.numerically_qualified", block.get("numerically_qualified"), qualified
    )
    independent.compare_tree(
        out, f"{path}.localized_and_retained", block.get("localized_and_retained"), localized
    )
    return {
        "artifact": artifact,
        "artifact_sha256": actual_hash,
        "diagnostics": fresh,
        "quality_checks": quality,
        "localization_checks": localization,
        "numerically_qualified": qualified,
        "localized_and_retained": localized,
    }


def validate_arm(
    out: list[dict[str, Any]],
    path: str,
    arm: Any,
    family: str,
    h_c: float,
    max_blocks: int,
    allowed_artifacts: set[str],
    require_initial_optimizer: bool,
) -> dict[str, Any] | None:
    if not isinstance(arm, dict):
        independent.mismatch(out, path, "arm object", arm, "schema")
        return None
    r_box, n = independent.GRIDS[family]
    exact = {
        "family": family,
        "basin": "separated_core",
        "R": r_box,
        "N": n,
        "dx": 2.0 * r_box / (n - 1),
        "h_C": h_c,
        "coefficient_vector": coefficient_vector(h_c),
        "max_blocks": max_blocks,
    }
    for name, expected in exact.items():
        independent.compare_tree(out, f"{path}.{name}", arm.get(name), expected)
    if require_initial_optimizer:
        independent.validate_initial_optimizer(
            arm.get("initial_optimizer"), f"{path}.initial_optimizer", out
        )
    else:
        independent.compare_tree(
            out, f"{path}.initial_optimizer", arm.get("initial_optimizer"), None
        )
    blocks = arm.get("blocks")
    if not isinstance(blocks, list) or not (1 <= len(blocks) <= max_blocks):
        independent.mismatch(
            out, f"{path}.blocks", f"list length in [1, {max_blocks}]", blocks, "bound"
        )
        return None
    verified_blocks: list[dict[str, Any]] = []
    for index, block in enumerate(blocks, start=1):
        verified = validate_block(
            out,
            f"{path}.blocks[{index - 1}]",
            block,
            family,
            h_c,
            index,
            allowed_artifacts,
        )
        if verified is not None:
            verified_blocks.append(verified)
    for block in verified_blocks[:-1]:
        if block["numerically_qualified"]:
            independent.mismatch(
                out,
                f"{path}.stopping_rule",
                "stop at first numerically qualified block",
                "later block present",
                "selection",
            )
    if not verified_blocks:
        return None
    terminal = verified_blocks[-1]
    independent.compare_tree(out, f"{path}.terminal_block", arm.get("terminal_block"), len(blocks))
    independent.compare_tree(
        out, f"{path}.terminal_artifact", arm.get("terminal_artifact"), terminal["artifact"]
    )
    independent.compare_tree(
        out,
        f"{path}.terminal_artifact_sha256",
        arm.get("terminal_artifact_sha256"),
        terminal["artifact_sha256"],
    )
    independent.compare_tree(
        out,
        f"{path}.diagnostics",
        physical_diagnostics_only(arm.get("diagnostics", {})),
        terminal["diagnostics"],
    )
    independent.compare_tree(out, f"{path}.quality_checks", arm.get("quality_checks"), terminal["quality_checks"])
    independent.compare_tree(
        out,
        f"{path}.localization_checks",
        arm.get("localization_checks"),
        terminal["localization_checks"],
    )
    independent.compare_tree(
        out,
        f"{path}.numerically_qualified",
        arm.get("numerically_qualified"),
        terminal["numerically_qualified"],
    )
    independent.compare_tree(
        out,
        f"{path}.localized_and_retained",
        arm.get("localized_and_retained"),
        terminal["localized_and_retained"],
    )
    independent.compare_tree(out, f"{path}.completed", arm.get("completed"), True)
    independent.compare_tree(out, f"{path}.error", arm.get("error"), None)
    return {
        **terminal,
        "family": family,
        "R": r_box,
        "N": n,
        "h_C": h_c,
        "block_count": len(blocks),
    }


def run_final_verification() -> int:
    mismatches: list[dict[str, Any]] = []
    manifest, manifest_sha256 = verify_manifest(mismatches)
    if not PREFLIGHT_PATH.is_file():
        independent.mismatch(mismatches, "preflight", "existing receipt", "MISSING", "read")
        preflight = None
    else:
        preflight = read_json(PREFLIGHT_PATH)
        independent.compare_tree(mismatches, "preflight.pass", preflight.get("pass"), True)
        independent.compare_tree(
            mismatches,
            "preflight.manifest_sha256",
            preflight.get("manifest_sha256"),
            manifest_sha256,
        )
    source_fresh = verify_source(mismatches)
    try:
        results = read_json(RESULTS_PATH)
    except Exception as error:
        independent.mismatch(mismatches, "results", "readable JSON", repr(error), "read")
        results = {}
    independent.compare_tree(
        mismatches,
        "results.schema",
        results.get("schema"),
        "cassi.particle-carrier-localization.results.v1",
    )
    independent.compare_tree(mismatches, "results.status", results.get("status"), "complete")
    independent.compare_tree(
        mismatches, "results.manifest_sha256", results.get("manifest_sha256"), manifest_sha256
    )
    if manifest is not None:
        independent.compare_tree(mismatches, "results.manifest", results.get("manifest"), manifest)

    if source_fresh is not None:
        reported_source = results.get("source")
        if not isinstance(reported_source, dict):
            independent.mismatch(mismatches, "results.source", "object", reported_source, "schema")
        else:
            independent.compare_tree(
                mismatches,
                "results.source.coefficient_vector",
                reported_source.get("coefficient_vector"),
                coefficient_vector(SOURCE_H_C),
            )
            independent.compare_tree(
                mismatches,
                "results.source.diagnostics",
                physical_diagnostics_only(reported_source.get("diagnostics", {})),
                source_fresh["diagnostics"],
            )
            independent.compare_tree(
                mismatches,
                "results.source.retention_balance",
                reported_source.get("retention_balance"),
                source_fresh["retention_balance"],
            )
            independent.compare_tree(
                mismatches,
                "results.source.quality_checks",
                reported_source.get("quality_checks"),
                source_fresh["quality_checks"],
            )
            independent.compare_tree(
                mismatches,
                "results.source.localization_checks",
                reported_source.get("localization_checks"),
                source_fresh["localization_checks"],
            )

    independent.compare_tree(
        mismatches,
        "results.candidate_order",
        results.get("candidate_order"),
        [row["label"] for row in CANDIDATES],
    )
    allowed_artifacts: set[str] = set()
    scan = results.get("primary_scan")
    verified_scan: list[dict[str, Any]] = []
    if not isinstance(scan, list) or not (1 <= len(scan) <= len(CANDIDATES)):
        independent.mismatch(
            mismatches,
            "results.primary_scan",
            f"list length in [1, {len(CANDIDATES)}]",
            scan,
            "bound",
        )
        scan = []
    for index, arm in enumerate(scan):
        candidate = CANDIDATES[index]
        independent.compare_tree(
            mismatches,
            f"results.primary_scan[{index}].label",
            arm.get("label") if isinstance(arm, dict) else None,
            f"primary_{candidate['label']}",
        )
        verified = validate_arm(
            mismatches,
            f"results.primary_scan[{index}]",
            arm,
            "P",
            float(candidate["h_C"]),
            PRIMARY_MAX_BLOCKS,
            allowed_artifacts,
            False,
        )
        if verified is not None:
            verified_scan.append(verified)

    localized_indices = [
        index for index, arm in enumerate(verified_scan) if arm["localized_and_retained"]
    ]
    selected_expected: dict[str, Any] | None = None
    if localized_indices:
        selected_index = localized_indices[0]
        if len(scan) != selected_index + 1:
            independent.mismatch(
                mismatches,
                "results.primary_scan.stopping_rule",
                selected_index + 1,
                len(scan),
                "selection",
            )
        candidate = CANDIDATES[selected_index]
        arm = verified_scan[selected_index]
        selected_expected = {
            "label": candidate["label"],
            "h_C": candidate["h_C"],
            "scan_index": selected_index,
            "artifact": arm["artifact"],
            "artifact_sha256": arm["artifact_sha256"],
        }
    elif len(scan) != len(CANDIDATES):
        independent.mismatch(
            mismatches,
            "results.primary_scan.stopping_rule",
            len(CANDIDATES),
            len(scan),
            "selection",
        )
    independent.compare_tree(
        mismatches, "results.selected_primary", results.get("selected_primary"), selected_expected
    )

    comparisons_verified: dict[str, dict[str, Any]] = {}
    if selected_expected is None:
        independent.compare_tree(mismatches, "results.comparison_order", results.get("comparison_order"), [])
        independent.compare_tree(mismatches, "results.comparison_arms", results.get("comparison_arms"), {})
        independent.compare_tree(mismatches, "results.comparisons", results.get("comparisons"), {})
    else:
        independent.compare_tree(
            mismatches, "results.comparison_order", results.get("comparison_order"), ["D", "H"]
        )
        comparison_arms = results.get("comparison_arms")
        if not isinstance(comparison_arms, dict):
            independent.mismatch(
                mismatches, "results.comparison_arms", "object", comparison_arms, "schema"
            )
            comparison_arms = {}
        for family in ("D", "H"):
            arm = comparison_arms.get(family)
            independent.compare_tree(
                mismatches,
                f"results.comparison_arms.{family}.label",
                arm.get("label") if isinstance(arm, dict) else None,
                f"comparison_{family}",
            )
            verified = validate_arm(
                mismatches,
                f"results.comparison_arms.{family}",
                arm,
                family,
                float(selected_expected["h_C"]),
                COMPARISON_MAX_BLOCKS,
                allowed_artifacts,
                True,
            )
            if verified is not None:
                comparisons_verified[family] = verified

    all_comparisons_qualified = (
        selected_expected is not None
        and set(comparisons_verified) == {"D", "H"}
        and all(row["numerically_qualified"] for row in comparisons_verified.values())
    )
    fresh_comparisons: dict[str, Any] = {}
    domain_match: bool | None = None
    comparisons_localized: bool | None = None
    if all_comparisons_qualified and selected_expected is not None:
        primary = verified_scan[int(selected_expected["scan_index"])]
        fresh_comparisons = {
            family: compare_metrics(primary, comparisons_verified[family])
            for family in ("D", "H")
        }
        independent.compare_tree(
            mismatches, "results.comparisons", results.get("comparisons"), fresh_comparisons
        )
        comparisons_localized = all(
            row["localized_and_retained"] for row in comparisons_verified.values()
        )
        domain_match = comparisons_localized and all(
            row["pass"] for row in fresh_comparisons.values()
        )

    any_primary_unqualified = any(
        not row["numerically_qualified"] for row in verified_scan
    ) or len(verified_scan) != len(scan)
    if selected_expected is None:
        expected_verdict = (
            "INCONCLUSIVE—NUMERICAL EXECUTION OR VERIFICATION"
            if any_primary_unqualified
            else "DOES NOT EMERGE—NO LOCALIZED RETAINED PRIMARY IN FROZEN BRACKET"
        )
    elif not all_comparisons_qualified:
        expected_verdict = "INCONCLUSIVE—NUMERICAL EXECUTION OR VERIFICATION"
    else:
        expected_verdict = (
            "EMERGES—DOMAIN-AND-RESOLUTION-MATCHED LOCALIZED RETAINED BRANCH"
            if domain_match
            else "EMERGES—FINITE-GRID LOCALIZED RETAINED BRANCH ONLY"
        )
    independent.compare_tree(
        mismatches, "results.primary_verdict", results.get("primary_verdict"), expected_verdict
    )

    expected_checks = {
        "source_control_reproduced": True,
        "planned_primary_scan_completed": selected_expected is not None
        or len(scan) == len(CANDIDATES),
        "localized_primary_found": selected_expected is not None,
        "comparison_grids_numerically_qualified": (
            all_comparisons_qualified if selected_expected is not None else None
        ),
        "comparison_grids_localized_and_retained": (
            comparisons_localized if all_comparisons_qualified else None
        ),
        "domain_and_resolution_match": domain_match,
    }
    independent.compare_tree(
        mismatches,
        "results.campaign_checks",
        results.get("campaign_checks"),
        expected_checks,
    )

    expected_files = {"preflight_verification.json", "results.json", *allowed_artifacts}
    actual_files = {
        path.name
        for path in RUN_DIR.iterdir()
        if path.is_file() and path != VERIFICATION_PATH
    } if RUN_DIR.is_dir() else set()
    if actual_files != expected_files:
        independent.mismatch(
            mismatches,
            "output_files",
            sorted(expected_files),
            sorted(actual_files),
            "immutable_output",
        )

    report = {
        "schema": "cassi.particle-carrier-localization.verification.v1",
        "pass": not mismatches,
        "manifest_sha256": manifest_sha256,
        "mismatches": mismatches,
        "independent_source": source_fresh,
        "verified_primary_scan": verified_scan,
        "verified_comparison_arms": comparisons_verified,
        "verified_comparisons": fresh_comparisons,
        "selected_primary": selected_expected,
        "scientific_verdict": (
            expected_verdict
            if not mismatches
            else "INCONCLUSIVE—NUMERICAL EXECUTION OR VERIFICATION"
        ),
    }
    write_json(VERIFICATION_PATH, report)
    print(
        json.dumps(
            {
                "pass": report["pass"],
                "mismatches": len(mismatches),
                "verdict": report["scientific_verdict"],
            },
            sort_keys=True,
        )
    )
    return 0 if report["pass"] else 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preflight", action="store_true")
    arguments = parser.parse_args(argv)
    return run_preflight() if arguments.preflight else run_final_verification()


if __name__ == "__main__":
    raise SystemExit(main())
