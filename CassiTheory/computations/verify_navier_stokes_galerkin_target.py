#!/usr/bin/env python3
"""Verify frozen finite-mode controls for the Navier–Stokes Galerkin target.

Run from the CassiTheory repository root:
    python computations/verify_navier_stokes_galerkin_target.py

The executable checks the finite-mode endpoint controls scheduled in
computations/navier-stokes-galerkin-target-prereg.md. It evaluates the initial
critical remainder with a spectral Leray projection and midpoint quadrature,
then emits a source-bound receipt. It does not integrate a Galerkin trajectory.
"""
from __future__ import annotations

import argparse
import re
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import sympy as sp


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
PROTOCOL = ROOT / "computations" / "navier-stokes-galerkin-target-prereg.md"
PAPER = ROOT / "turbulence" / "navier-stokes-replica-coherence.md"
NEAR_RANK_NOTE = ROOT / "turbulence" / "navier-stokes-near-rank-recovery-obstruction.md"
DEFAULT_OUTPUT = (
    ROOT
    / "runs"
    / "navier_stokes_galerkin_endpoint_controls_publication_20260913"
    / "verification.json"
)
EXPECTED_CHECKS = 8
EXPECTED_CHECK_NAMES = (
    "G1 finite-mode controls survive Leray projection",
    "G2 rank-deficient heat target vanishes",
    "G3 ABC Beltrami target vanishes",
    "G4 rank-two datum has positive endpoint remainder",
    "G5 near-rank production remains fixed and positive",
    "G6 near-rank source is sampled full rank with uniform H3 bound",
    "G7 Euclidean endpoint scaling has critical exponent",
    "G8 Galerkin enstrophy absorption identity",
)
GRID_SIZE = 64
TORUS_LENGTH = 2.0 * np.pi
NU = 0.1
EPSILONS = (1.0e-1, 1.0e-2, 1.0e-3, 1.0e-4)
EPSILON_MAX = max(EPSILONS)
SCALE = 3.0
RECONSTRUCTION_TOL = 1.0e-10
PRODUCTION_TOL = 1.0e-10
SCALING_TOL = 2.0e-10
RANK_FRACTION_MIN = 0.5
SCHEMA = "cassi.navier-stokes.galerkin-endpoint-controls.verification.v1"


class CheckBook:
    def __init__(self) -> None:
        self.checks: list[dict[str, Any]] = []
        self.failures: list[str] = []

    def record(
        self,
        name: str,
        passed: bool,
        observed: Any,
        expected: Any,
        tolerance: Any = None,
    ) -> None:
        row = {
            "name": name,
            "passed": bool(passed),
            "observed": stringify(observed),
            "expected": stringify(expected),
        }
        if tolerance is not None:
            row["tolerance"] = stringify(tolerance)
        self.checks.append(row)
        if not passed:
            self.failures.append(name)


def stringify(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, sp.MatrixBase):
        return [[stringify(item) for item in row] for row in value.tolist()]
    if isinstance(value, sp.Basic):
        return str(value)
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, complex):
        return {"real": value.real, "imag": value.imag}
    if isinstance(value, dict):
        return {str(key): stringify(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [stringify(item) for item in value]
    return value


def finite(value: Any) -> bool:
    if isinstance(value, (float, int, np.floating, np.integer)):
        return math.isfinite(float(value))
    return all(finite(item) for item in value)


def midpoint_grid(domain: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    coordinate = np.arange(GRID_SIZE, dtype=np.float64) * domain / GRID_SIZE
    return np.meshgrid(coordinate, coordinate, coordinate, indexing="ij")


def wave_numbers(domain: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    frequency = 2.0 * np.pi * np.fft.fftfreq(
        GRID_SIZE,
        d=domain / GRID_SIZE,
    )
    return np.meshgrid(frequency, frequency, frequency, indexing="ij")


def leray_project(
    velocity: np.ndarray,
    cutoff: float,
    domain: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    velocity_hat = np.fft.fftn(velocity, axes=(1, 2, 3), norm="ortho")
    kx, ky, kz = wave_numbers(domain)
    wave_vector = np.stack((kx, ky, kz), axis=0)
    k_squared = kx * kx + ky * ky + kz * kz
    mask = (k_squared > 0.0) & (k_squared <= cutoff * cutoff + 1.0e-10)
    k_dot_velocity = np.sum(wave_vector * velocity_hat, axis=0)
    projected_hat = velocity_hat - np.divide(
        wave_vector * k_dot_velocity[None, ...],
        k_squared[None, ...],
        out=np.zeros_like(velocity_hat),
        where=k_squared[None, ...] > 0.0,
    )
    projected_hat *= mask[None, ...]
    projected = np.fft.ifftn(
        projected_hat,
        axes=(1, 2, 3),
        norm="ortho",
    ).real
    return projected, projected_hat, k_squared, mask


def determinant_3(matrix: np.ndarray) -> np.ndarray:
    return (
        matrix[0, 0] * (matrix[1, 1] * matrix[2, 2] - matrix[1, 2] * matrix[2, 1])
        - matrix[0, 1] * (matrix[1, 0] * matrix[2, 2] - matrix[1, 2] * matrix[2, 0])
        + matrix[0, 2] * (matrix[1, 0] * matrix[2, 1] - matrix[1, 1] * matrix[2, 0])
    )


def spectral_observables(
    velocity: np.ndarray,
    cutoff: float,
    domain: float = TORUS_LENGTH,
) -> dict[str, Any]:
    projected, projected_hat, k_squared, mask = leray_project(
        velocity,
        cutoff,
        domain,
    )
    kx, ky, kz = wave_numbers(domain)
    wave_vector = (kx, ky, kz)
    gradient = np.empty(
        (3, 3, GRID_SIZE, GRID_SIZE, GRID_SIZE),
        dtype=np.float64,
    )
    for component in range(3):
        for coordinate in range(3):
            gradient[component, coordinate] = np.fft.ifftn(
                1j * wave_vector[coordinate] * projected_hat[component],
                axes=(0, 1, 2),
                norm="ortho",
            ).real
    strain = 0.5 * (gradient + np.swapaxes(gradient, 0, 1))
    vorticity = np.stack(
        (
            gradient[2, 1] - gradient[1, 2],
            gradient[0, 2] - gradient[2, 0],
            gradient[1, 0] - gradient[0, 1],
        ),
        axis=0,
    )
    vorticity_hat = np.fft.fftn(vorticity, axes=(1, 2, 3), norm="ortho")
    vorticity_gradient = np.empty_like(gradient)
    for component in range(3):
        for coordinate in range(3):
            vorticity_gradient[component, coordinate] = np.fft.ifftn(
                1j * wave_vector[coordinate] * vorticity_hat[component],
                axes=(0, 1, 2),
                norm="ortho",
            ).real
    cell_volume = (domain / GRID_SIZE) ** 3
    production_density = np.einsum(
        "i...,ij...,j...->...",
        vorticity,
        strain,
        vorticity,
    )
    vorticity_norm_squared = np.sum(vorticity * vorticity, axis=0)
    palinstrophy_density = np.sum(vorticity_gradient * vorticity_gradient, axis=(0, 1))
    divergence_hat = sum(
        wave_vector[coordinate] * projected_hat[coordinate]
        for coordinate in range(3)
    )
    divergence = np.fft.ifftn(
        1j * divergence_hat,
        axes=(0, 1, 2),
        norm="ortho",
    ).real
    production = float(np.sum(production_density) * cell_volume)
    enstrophy = float(np.sum(vorticity_norm_squared) * cell_volume)
    palinstrophy = float(np.sum(palinstrophy_density) * cell_volume)
    target = production - 0.5 * NU * palinstrophy
    h3 = float(
        np.sqrt(
            np.sum((1.0 + k_squared) ** 3 * np.abs(projected_hat) ** 2)
            * cell_volume
        )
    )
    determinant = determinant_3(vorticity_gradient)
    scale = max(1.0, float(np.max(np.abs(velocity))))
    projection_error = float(np.max(np.abs(projected - velocity)) / scale)
    divergence_error = float(np.max(np.abs(divergence)))
    return {
        "P": production,
        "W": enstrophy,
        "D": palinstrophy,
        "target": target,
        "target_positive": max(target, 0.0),
        "H3": h3,
        "determinant": determinant,
        "projection_error": projection_error,
        "divergence_error": divergence_error,
        "retained_mode_count": int(np.count_nonzero(mask)),
    }


def shear_field(n: int = 2, domain: float = TORUS_LENGTH) -> np.ndarray:
    _, y, _ = midpoint_grid(domain)
    velocity = np.zeros((3, GRID_SIZE, GRID_SIZE, GRID_SIZE), dtype=np.float64)
    velocity[0] = np.sin(2.0 * np.pi * n * y / TORUS_LENGTH)
    return velocity


def abc_field(domain: float = TORUS_LENGTH) -> np.ndarray:
    x, y, z = midpoint_grid(domain)
    scale = TORUS_LENGTH / domain
    x, y, z = scale * x, scale * y, scale * z
    velocity = np.empty((3, GRID_SIZE, GRID_SIZE, GRID_SIZE), dtype=np.float64)
    velocity[0] = np.sin(z) + np.cos(y)
    velocity[1] = np.sin(x) + np.cos(z)
    velocity[2] = np.sin(y) + np.cos(x)
    return velocity


def rank_two_base(domain: float = TORUS_LENGTH) -> np.ndarray:
    x, y, _ = midpoint_grid(domain)
    x, y = 2.0 * np.pi * x / domain, 2.0 * np.pi * y / domain
    velocity = np.zeros((3, GRID_SIZE, GRID_SIZE, GRID_SIZE), dtype=np.float64)
    velocity[0] = -np.sin(y)
    velocity[2] = np.sin(x) + np.cos(x) * np.sin(y)
    return velocity


def near_rank_field(epsilon: float, domain: float = TORUS_LENGTH) -> np.ndarray:
    perturbation = abc_field(domain)
    return rank_two_base(domain) + epsilon * perturbation


def symbolic_controls() -> dict[str, Any]:
    x, y, z, t = sp.symbols("x y z t", real=True)
    coordinates = (x, y, z)
    nu = sp.symbols("nu", positive=True, real=True)
    shear = sp.Matrix([sp.exp(-4 * nu * t) * sp.sin(2 * y), 0, 0])
    shear_laplacian = sum(
        (sp.diff(shear, coordinate, 2) for coordinate in coordinates),
        sp.zeros(3, 1),
    )
    shear_heat_residual = sp.simplify(
        sp.diff(shear, t) - nu * shear_laplacian
    )
    shear_divergence = sum(
        sp.diff(shear[index], coordinates[index]) for index in range(3)
    )
    shear_vorticity = sp.Matrix(
        [
            sp.diff(shear[2], y) - sp.diff(shear[1], z),
            sp.diff(shear[0], z) - sp.diff(shear[2], x),
            sp.diff(shear[1], x) - sp.diff(shear[0], y),
        ]
    )
    abc = sp.Matrix(
        [
            sp.sin(z) + sp.cos(y),
            sp.sin(x) + sp.cos(z),
            sp.sin(y) + sp.cos(x),
        ]
    )
    abc_divergence = sum(
        sp.diff(abc[index], coordinates[index]) for index in range(3)
    )
    abc_curl = sp.Matrix(
        [
            sp.diff(abc[2], y) - sp.diff(abc[1], z),
            sp.diff(abc[0], z) - sp.diff(abc[2], x),
            sp.diff(abc[1], x) - sp.diff(abc[0], y),
        ]
    )
    abc_laplacian = sum(
        (sp.diff(abc, coordinate, 2) for coordinate in coordinates),
        sp.zeros(3, 1),
    )
    abc_convection = abc.jacobian(coordinates) * abc
    abc_bernoulli = sp.Matrix(
        [
            sp.diff((abc.T * abc)[0] / 2, coordinate)
            for coordinate in coordinates
        ]
    )
    base = sp.Matrix(
        [
            -sp.sin(y),
            0,
            sp.sin(x) + sp.cos(x) * sp.sin(y),
        ]
    )
    base_divergence = sum(
        sp.diff(base[index], coordinates[index]) for index in range(3)
    )
    base_vorticity = sp.Matrix(
        [
            sp.diff(base[2], y) - sp.diff(base[1], z),
            sp.diff(base[0], z) - sp.diff(base[2], x),
            sp.diff(base[1], x) - sp.diff(base[0], y),
        ]
    )
    base_gradient = base_vorticity.jacobian(coordinates)
    base_strain = sp.Rational(1, 2) * (
        base.jacobian(coordinates) + base.jacobian(coordinates).T
    )
    base_production = sp.expand(
        (base_vorticity.T * base_strain * base_vorticity)[0]
    )
    base_average = sp.integrate(
        sp.integrate(
            sp.integrate(base_production, (x, 0, 2 * sp.pi)),
            (y, 0, 2 * sp.pi),
        ),
        (z, 0, 2 * sp.pi),
    ) / (2 * sp.pi) ** 3
    return {
        "nu": nu,
        "shear_divergence": sp.simplify(shear_divergence),
        "shear_heat_residual": shear_heat_residual,
        "shear_vorticity": shear_vorticity,
        "shear_gram_rank": (
            shear_vorticity.jacobian(coordinates)
            * shear_vorticity.jacobian(coordinates).T
        ).rank(),
        "abc_divergence": sp.simplify(abc_divergence),
        "abc_curl_residual": abc_curl - abc,
        "abc_heat_residual": abc_laplacian + abc,
        "abc_bernoulli_residual": (
            abc_convection - abc_bernoulli
        ).applyfunc(lambda item: sp.trigsimp(item)),
        "base_divergence": sp.simplify(base_divergence),
        "base_source_determinant": sp.factor((base_gradient * base_gradient.T).det()),
        "base_production_average": sp.simplify(base_average),
    }


def verify_controls(book: CheckBook, values: dict[str, Any]) -> None:
    symbolic = symbolic_controls()
    shear = spectral_observables(shear_field(), cutoff=2.0)
    abc = spectral_observables(abc_field(), cutoff=1.0)
    base = spectral_observables(rank_two_base(), cutoff=2.0)
    near_rank = {
        f"{epsilon:g}": spectral_observables(
            near_rank_field(epsilon),
            cutoff=2.0,
        )
        for epsilon in EPSILONS
    }
    controls = {"shear": shear, "abc": abc, "base": base, "near_rank": near_rank}
    values["controls"] = {
        "shear": {key: value for key, value in shear.items() if key != "determinant"},
        "abc": {key: value for key, value in abc.items() if key != "determinant"},
        "base": {key: value for key, value in base.items() if key != "determinant"},
        "near_rank": {
            key: {inner: value for inner, value in item.items() if inner != "determinant"}
            for key, item in near_rank.items()
        },
    }
    values["symbolic"] = {
        key: stringify(value)
        for key, value in symbolic.items()
        if key != "nu"
    }

    control_residuals = {
        name: {
            "projection_error": item["projection_error"],
            "divergence_error": item["divergence_error"],
            "retained_mode_count": item["retained_mode_count"],
        }
        for name, item in ([("shear", shear), ("abc", abc), ("base", base)]
        + [(f"near_rank_{epsilon:g}", item) for epsilon, item in zip(EPSILONS, near_rank.values())])
    }
    projection_pass = all(
        item["projection_error"] <= RECONSTRUCTION_TOL
        and item["divergence_error"] <= RECONSTRUCTION_TOL
        for item in control_residuals.values()
    )
    book.record(
        EXPECTED_CHECK_NAMES[0],
        projection_pass,
        control_residuals,
        "all normalized projection and divergence residuals <= 1e-10",
        RECONSTRUCTION_TOL,
    )

    shear_pass = (
        symbolic["shear_divergence"] == 0
        and symbolic["shear_heat_residual"] == sp.zeros(3, 1)
        and symbolic["shear_gram_rank"] == 1
        and abs(shear["P"]) <= PRODUCTION_TOL
        and shear["D"] > 0.0
        and shear["target_positive"] == 0.0
    )
    book.record(
        EXPECTED_CHECK_NAMES[1],
        shear_pass,
        {
            "symbolic_divergence": symbolic["shear_divergence"],
            "symbolic_heat_residual": symbolic["shear_heat_residual"],
            "source_rank": symbolic["shear_gram_rank"],
            "P": shear["P"],
            "D": shear["D"],
            "target_positive": shear["target_positive"],
        },
        "divergence=0, heat residual=0, rank=1, P=0, D>0, target_positive=0",
        PRODUCTION_TOL,
    )

    abc_pass = (
        symbolic["abc_divergence"] == 0
        and symbolic["abc_curl_residual"] == sp.zeros(3, 1)
        and symbolic["abc_heat_residual"] == sp.zeros(3, 1)
        and symbolic["abc_bernoulli_residual"] == sp.zeros(3, 1)
        and abs(abc["P"]) <= PRODUCTION_TOL
        and abs(abc["D"] - abc["W"]) <= PRODUCTION_TOL
        and abc["target_positive"] == 0.0
    )
    book.record(
        EXPECTED_CHECK_NAMES[2],
        abc_pass,
        {
            "symbolic_divergence": symbolic["abc_divergence"],
            "symbolic_curl_residual": symbolic["abc_curl_residual"],
            "symbolic_heat_residual": symbolic["abc_heat_residual"],
            "symbolic_bernoulli_residual": symbolic["abc_bernoulli_residual"],
            "P": abc["P"],
            "D": abc["D"],
            "W": abc["W"],
            "target_positive": abc["target_positive"],
        },
        "ABC identities, P=0, D=W, target_positive=0",
        PRODUCTION_TOL,
    )

    volume = TORUS_LENGTH**3
    base_pass = (
        symbolic["base_divergence"] == 0
        and symbolic["base_source_determinant"] == 0
        and symbolic["base_production_average"] == sp.Rational(1, 4)
        and abs(base["P"] / volume - 0.25) <= PRODUCTION_TOL
        and base["target_positive"] > 1.0
    )
    book.record(
        EXPECTED_CHECK_NAMES[3],
        base_pass,
        {
            "symbolic_divergence": symbolic["base_divergence"],
            "symbolic_source_determinant": symbolic["base_source_determinant"],
            "symbolic_production_average": symbolic["base_production_average"],
            "numerical_production_average": base["P"] / volume,
            "P": base["P"],
            "D": base["D"],
            "target": base["target"],
            "target_positive": base["target_positive"],
        },
        "source determinant=0, production average=1/4, target_positive>1",
        PRODUCTION_TOL,
    )

    near_production = {
        epsilon: item["P"] / volume for epsilon, item in zip(EPSILONS, near_rank.values())
    }
    near_targets = {epsilon: item["target_positive"] for epsilon, item in zip(EPSILONS, near_rank.values())}
    near_production_pass = all(
        abs(production - 0.25) <= PRODUCTION_TOL
        for production in near_production.values()
    ) and all(target > 1.0 for target in near_targets.values())
    book.record(
        EXPECTED_CHECK_NAMES[4],
        near_production_pass,
        {
            "production_averages": near_production,
            "target_positive": near_targets,
        },
        "every production average=1/4 and every target_positive>1",
        PRODUCTION_TOL,
    )

    base_h3 = base["H3"]
    perturbation_h3 = spectral_observables(abc_field(), cutoff=1.0)["H3"]
    h3_bound = base_h3 + EPSILON_MAX * perturbation_h3
    rank_fractions: dict[float, float] = {}
    for epsilon, item in zip(EPSILONS, near_rank.values()):
        determinant = item["determinant"]
        threshold = max(1.0e-13, 1.0e-8 * float(np.max(np.abs(determinant))))
        rank_fractions[epsilon] = float(np.mean(np.abs(determinant) > threshold))
    h3_values = {epsilon: item["H3"] for epsilon, item in zip(EPSILONS, near_rank.values())}
    rank_pass = (
        all(fraction > RANK_FRACTION_MIN for fraction in rank_fractions.values())
        and all(value <= h3_bound * (1.0 + 1.0e-10) for value in h3_values.values())
        and finite(rank_fractions)
        and finite(h3_values)
    )
    book.record(
        EXPECTED_CHECK_NAMES[5],
        rank_pass,
        {
            "sampled_nonzero_determinant_fraction": rank_fractions,
            "H3_values": h3_values,
            "base_H3": base_h3,
            "perturbation_H3": perturbation_h3,
            "H3_triangle_bound": h3_bound,
        },
        "every sampled determinant fraction>0.5 and H3<=triangle bound",
        {"rank_fraction_min": RANK_FRACTION_MIN, "relative_H3": 1.0e-10},
    )

    scaled_base = spectral_observables(
        SCALE * rank_two_base(TORUS_LENGTH / SCALE),
        cutoff=2.0 * SCALE,
        domain=TORUS_LENGTH / SCALE,
    )
    ratios = {
        "P": scaled_base["P"] / base["P"],
        "D": scaled_base["D"] / base["D"],
        "target": scaled_base["target"] / base["target"],
    }
    scaling_pass = all(
        abs(ratio - SCALE**3) / SCALE**3 <= SCALING_TOL
        for ratio in ratios.values()
    )
    book.record(
        EXPECTED_CHECK_NAMES[6],
        scaling_pass,
        {
            "lambda": SCALE,
            "ratios": ratios,
            "expected_initial_ratio": SCALE**3,
            "expected_time_integrated_ratio": SCALE,
        },
        "P, D, and target ratios=lambda^3; time-integrated ratio=lambda",
        SCALING_TOL,
    )


def verify_absorption_identity(book: CheckBook, values: dict[str, Any]) -> None:
    p, d, nu = sp.symbols("P_N D_N nu", real=True)
    residual = sp.expand((2 * p - 2 * nu * d) + nu * d - 2 * (p - nu * d / 2))
    book.record(
        EXPECTED_CHECK_NAMES[7],
        residual == 0,
        {"residual": residual, "identity": "W_N' + nu D_N = 2(P_N^str - nu D_N/2)"},
        "residual=0",
    )
    values["absorption_identity_residual"] = residual


def protocol_integrity() -> dict[str, Any]:
    text = PROTOCOL.read_text(encoding="utf-8")
    tags = re.findall(r"\\tag\{(GTC\d+)\}", text)
    expected_tags = [f"GTC{index}" for index in range(1, 13)]
    declared_names = tuple(
        re.findall(r"^\d+\. `([^`]+)`", text, flags=re.MULTILINE)
    )
    return {
        "tag_count": len(tags),
        "unique_tag_count": len(set(tags)),
        "expected_tags": expected_tags,
        "observed_tags": tags,
        "tags_match": tags == expected_tags,
        "declared_check_count": len(declared_names),
        "declared_check_names": list(declared_names),
        "inventory_names_match": declared_names == EXPECTED_CHECK_NAMES,
        "inventory_declaration_present": "exactly these eight checks" in text,
        "selected_receipt_present": (
            "runs/navier_stokes_galerkin_endpoint_controls_publication_20260913/verification.json"
            in text
        ),
        "paper_binding_present": "turbulence/navier-stokes-replica-coherence.md" in text,
        "near_rank_binding_present": (
            "turbulence/navier-stokes-near-rank-recovery-obstruction.md" in text
        ),
        "verifier_binding_present": (
            "computations/verify_navier_stokes_galerkin_target.py" in text
        ),
        "target_binding_present": (
            "sup_{N\\ge1}\\sup_{\\|u_{0,N}\\|_{H^3}\\le R_0}" in text
        ),
    }


def compute() -> tuple[dict[str, Any], bool]:
    book = CheckBook()
    values: dict[str, Any] = {}
    verify_controls(book, values)
    verify_absorption_identity(book, values)
    observed_names = tuple(row["name"] for row in book.checks)
    inventory_match = observed_names == EXPECTED_CHECK_NAMES
    if not inventory_match:
        book.failures.append("fixed check inventory")
    integrity = protocol_integrity()
    integrity_pass = bool(
        integrity["tags_match"]
        and integrity["inventory_names_match"]
        and integrity["inventory_declaration_present"]
        and integrity["selected_receipt_present"]
        and integrity["paper_binding_present"]
        and integrity["near_rank_binding_present"]
        and integrity["verifier_binding_present"]
        and integrity["target_binding_present"]
    )
    if not integrity_pass:
        book.failures.append("protocol integrity")
    success = (
        not book.failures
        and inventory_match
        and integrity_pass
        and len(book.checks) == EXPECTED_CHECKS
    )
    result = {
        "schema": SCHEMA,
        "status": "PASS" if success else "FAIL",
        "expected_check_count": EXPECTED_CHECKS,
        "expected_check_names": list(EXPECTED_CHECK_NAMES),
        "check_count": len(book.checks),
        "inventory_match": inventory_match,
        "protocol_integrity": integrity,
        "checks": book.checks,
        "failures": book.failures,
        "values": stringify(values),
        "classifications": {
            "finite_mode_endpoint_controls": "SUPPORTS" if success else "INCONCLUSIVE",
            "cutoff_uniform_galerkin_time_integral": "UNRESOLVED" if success else "INCONCLUSIVE",
            "production_relative_covariance_compensation": "UNRESOLVED" if success else "INCONCLUSIVE",
            "arbitrary_data_navier_stokes_regularity": "UNRESOLVED" if success else "INCONCLUSIVE",
        },
        "scope": {
            "trajectory_integration": "NOT_RUN",
            "stochastic_flow_simulation": "NOT_RUN",
            "continuum_compactness_passage": "NOT_RUN",
            "endpoint_integrand": "INITIAL_TIME_FINITE_MODE_CONTROLS",
            "near_rank_full_rank": "SAMPLED_GRID_CONTROL_PLUS_ANALYTIC_SOURCE_NOTE",
            "galerkin_target": "UNRESOLVED_TIME_INTEGRATED_BOUND",
        },
    }
    return result, success


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    manifest_path = output.with_suffix(".inputs.json")
    snapshot_dir = output.with_suffix(".sources")
    if any(path.exists() for path in (output, manifest_path, snapshot_dir)):
        raise FileExistsError(f"Use a fresh output path: {output}")

    sources = {
        "protocol": PROTOCOL,
        "paper": PAPER,
        "near_rank_note": NEAR_RANK_NOTE,
        "verifier": Path(__file__).resolve(),
    }
    payloads = {key: path.read_bytes() for key, path in sources.items()}
    identities = {
        key: {
            "path": path.relative_to(WORKSPACE).as_posix(),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        for (key, path), payload in zip(sources.items(), payloads.values())
    }
    created = datetime.now(timezone.utc).isoformat()
    manifest = {
        "created_utc": created,
        "identities": identities,
        "numpy_version": np.__version__,
        "sympy_version": sp.__version__,
        "grid_size": GRID_SIZE,
        "viscosity": NU,
    }
    result, success = compute()
    result["created_utc"] = created
    result["identities"] = identities
    result["numpy_version"] = np.__version__
    result["sympy_version"] = sp.__version__
    output.parent.mkdir(parents=True, exist_ok=True)
    snapshot_dir.mkdir(parents=True, exist_ok=False)
    for key, payload in payloads.items():
        (snapshot_dir / f"{key}{sources[key].suffix}").write_bytes(payload)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    passed_count = sum(row["passed"] for row in result["checks"])
    print(f"{passed_count} / {EXPECTED_CHECKS} checks passed")
    print(f"inventory_match: {result['inventory_match']}")
    print(f"protocol_tags_match: {result['protocol_integrity']['tags_match']}")
    print(f"status: {result['status']}")
    for name, classification in result["classifications"].items():
        print(f"{name}: {classification}")
    if success:
        print("ALL CHECKS PASSED")
        return 0
    for failure in result["failures"]:
        print(f"FAIL: {failure}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
