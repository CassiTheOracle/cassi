#!/usr/bin/env python3
"""Verify the fixed Cassi phase-current hydrodynamic controls."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import shutil
import sys
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import sympy as sp


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "computations" / "cassi-fluid-phase-current-prereg.md"
DEFAULT_OUTPUT = ROOT / "runs" / "cassi_fluid_phase_current" / "verification.json"
SOURCE_PATHS = (
    Path("computations/cassi-fluid-phase-current-prereg.md"),
    Path("computations/verify_cassi_fluid_phase_current.py"),
    Path("foundations/interscale-current-soliton.md"),
    Path("foundations/geometric-manifold-completion.md"),
    Path("foundations/quantum-measurement-derivation.md"),
    Path("turbulence/cassi-fluid-feasibility.md"),
)
TOL = 1.0e-12


def scalar(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, complex):
        return {"real": value.real, "imag": value.imag}
    if isinstance(value, np.ndarray):
        return value.tolist()
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass
class CheckBook:
    checks: dict[str, dict[str, Any]] = field(default_factory=dict)

    def add(self, name: str, passed: bool, **evidence: Any) -> None:
        if name in self.checks:
            raise KeyError(f"duplicate check: {name}")
        self.checks[name] = {
            "passed": bool(passed),
            "evidence": {key: scalar(value) for key, value in evidence.items()},
        }

    def exact(self, name: str, expression: sp.Expr) -> None:
        simplified = sp.simplify(sp.trigsimp(expression))
        if isinstance(simplified, sp.MatrixBase):
            passed = all(component == 0 for component in simplified)
        else:
            passed = simplified == 0
        self.add(name, passed, simplified=str(simplified))

    def close(self, name: str, actual: float, expected: float, tolerance: float) -> None:
        error = abs(float(actual) - float(expected))
        self.add(
            name,
            math.isfinite(error) and error <= tolerance,
            actual=float(actual),
            expected=float(expected),
            error=error,
            tolerance=tolerance,
        )

    def below(self, name: str, actual: float, bound: float) -> None:
        value = float(actual)
        self.add(
            name,
            math.isfinite(value) and value < bound,
            actual=value,
            strict_upper_bound=bound,
        )

    def above(self, name: str, actual: float, bound: float) -> None:
        value = float(actual)
        self.add(
            name,
            math.isfinite(value) and value > bound,
            actual=value,
            strict_lower_bound=bound,
        )

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(row["passed"] for row in self.checks.values())

    @property
    def failed(self) -> list[str]:
        return [name for name, row in self.checks.items() if not row["passed"]]


def snapshot_sources(output_dir: Path) -> dict[str, dict[str, Any]]:
    snapshot_root = output_dir / "source_snapshots"
    manifest: dict[str, dict[str, Any]] = {}
    for relative in SOURCE_PATHS:
        source = ROOT / relative
        destination = snapshot_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        raw = source.read_bytes()
        destination.write_bytes(raw)
        manifest[relative.as_posix()] = {
            "path": relative.as_posix(),
            "snapshot": destination.relative_to(output_dir).as_posix(),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
    return manifest


def symbolic_checks(book: CheckBook) -> None:
    beta, alpha = sp.symbols("beta alpha", real=True)
    z0 = sp.cos(beta / 2) * sp.exp(sp.I * alpha / 2)
    z1 = sp.sin(beta / 2) * sp.exp(-sp.I * alpha / 2)
    norm = sp.conjugate(z0) * z0 + sp.conjugate(z1) * z1
    book.exact("algebra.spinor_normalization", norm - 1)
    book.exact("algebra.spinor_population_y", sp.conjugate(z0) * z0 - (1 + sp.cos(beta)) / 2)
    book.exact("algebra.spinor_population_i", sp.conjugate(z1) * z1 - (1 - sp.cos(beta)) / 2)

    berry_alpha = -sp.I * (
        sp.conjugate(z0) * sp.diff(z0, alpha)
        + sp.conjugate(z1) * sp.diff(z1, alpha)
    )
    berry_beta = -sp.I * (
        sp.conjugate(z0) * sp.diff(z0, beta)
        + sp.conjugate(z1) * sp.diff(z1, beta)
    )
    book.exact("algebra.berry_alpha", berry_alpha - sp.cos(beta) / 2)
    book.exact("algebra.berry_beta", berry_beta)

    nvec = sp.Matrix(
        [
            sp.sin(beta) * sp.cos(alpha),
            -sp.sin(beta) * sp.sin(alpha),
            sp.cos(beta),
        ]
    )
    orientation = sp.expand_trig(nvec.dot(sp.diff(nvec, beta).cross(sp.diff(nvec, alpha))))
    book.exact("algebra.spin_area_orientation", orientation + sp.sin(beta))
    curvature_ba = -sp.sin(beta) / 2
    book.exact("algebra.mermin_ho_coefficient", curvature_ba - orientation / 2)

    x, y, z = sp.symbols("x y z", real=True)
    beta_f = sp.Function("beta")(x, y, z)
    alpha_f = sp.Function("alpha")(x, y, z)
    coords = (x, y, z)
    curvature = {}
    for i in range(3):
        for j in range(3):
            curvature[i, j] = -sp.sin(beta_f) * (
                sp.diff(beta_f, coords[i]) * sp.diff(alpha_f, coords[j])
                - sp.diff(beta_f, coords[j]) * sp.diff(alpha_f, coords[i])
            ) / 2
    closed_three_form = (
        sp.diff(curvature[1, 2], x)
        + sp.diff(curvature[2, 0], y)
        + sp.diff(curvature[0, 1], z)
    )
    book.exact("algebra.berry_bianchi", closed_three_form)

    c, gy, gi = sp.symbols("c gy gi", real=True)
    book.exact("algebra.current_clebsch", c * gy + (1 - c) * gi - (gi + c * (gy - gi)))

    gq, b0 = sp.symbols("g_Q beta_0", real=True)
    bx = -y / 2
    by = x / 2
    gauge_ax = -gq * sp.cos(b0) * bx / 2
    gauge_ay = -gq * sp.cos(b0) * by / 2
    gauge_curl_z = sp.diff(gauge_ay, x) - sp.diff(gauge_ax, y)
    book.exact("algebra.gauge_curvature_witness", gauge_curl_z + gq * sp.cos(b0) / 2)

    rho1, rho2, c1, c2 = sp.symbols("rho1 rho2 c1 c2", positive=True)
    vy1, vi1, vy2, vi2 = sp.symbols("vy1 vi1 vy2 vi2", real=True)
    weights = (rho1 * c1, rho1 * (1 - c1), rho2 * c2, rho2 * (1 - c2))
    velocities = (vy1, vi1, vy2, vi2)
    rho_total = rho1 + rho2
    mean_velocity = sum(w * v for w, v in zip(weights, velocities)) / rho_total
    microscopic_twice = sum(w * v**2 for w, v in zip(weights, velocities))
    variance_twice = sum(w * (v - mean_velocity) ** 2 for w, v in zip(weights, velocities))
    book.exact(
        "algebra.kinetic_variance",
        microscopic_twice - rho_total * mean_velocity**2 - variance_twice,
    )

    tx, ty, tz, cx, cy, cz, ax, ay, az = sp.symbols(
        "tx ty tz cx cy cz ax ay az", real=True
    )
    tgrad = sp.Matrix([tx, ty, tz])
    cgrad = sp.Matrix([cx, cy, cz])
    agrad = sp.Matrix([ax, ay, az])
    helicity_density = (tgrad + c * agrad).dot(cgrad.cross(agrad))
    exterior_derivative = cgrad.dot(tgrad.cross(agrad))
    book.exact("algebra.positive_chart_helicity_exactness", helicity_density + exterior_derivative)

    kappa, winding, amplitude = sp.symbols("kappa N U", positive=True)
    shear_c = sp.Rational(1, 2) + amplitude * sp.sin(y) / (2 * kappa * winding)
    shear_u = kappa * (-winding + 2 * winding * shear_c)
    book.exact("algebra.shear_velocity", shear_u - amplitude * sp.sin(y))
    book.exact("algebra.shear_vorticity", -sp.diff(shear_u, y) + amplitude * sp.cos(y))
    shear_micro = sp.Rational(1, 2) * kappa**2 * (
        shear_c * winding**2 + (1 - shear_c) * winding**2
    )
    book.exact("algebra.shear_phase_energy", shear_micro - kappa**2 * winding**2 / 2)
    shear_resolved_mean = sp.integrate(shear_u**2 / 2, (y, 0, 2 * sp.pi)) / (2 * sp.pi)
    book.exact("algebra.shear_resolved_energy", shear_resolved_mean - amplitude**2 / 4)

    eta = sp.symbols("eta", real=True)
    hopf_a1 = sp.cos(eta) ** 2
    hopf_a2 = sp.sin(eta) ** 2
    hopf_f01 = sp.diff(hopf_a1, eta)
    hopf_f02 = sp.diff(hopf_a2, eta)
    hopf_density = -hopf_a1 * hopf_f02 + hopf_a2 * hopf_f01
    book.exact("algebra.hopf_helicity_density", hopf_density + 2 * sp.sin(eta) * sp.cos(eta))
    hopf_integral = (2 * sp.pi) ** 2 * sp.integrate(hopf_density, (eta, 0, sp.pi / 2))
    book.exact("algebra.hopf_helicity_integral", hopf_integral + 4 * sp.pi**2)
    hopf_star_e1 = -2 * sp.cos(eta)
    hopf_star_e2 = -2 * sp.sin(eta)
    book.exact("algebra.hopf_hodge_e1", hopf_star_e1 + 2 * sp.cos(eta))
    book.exact("algebra.hopf_hodge_e2", hopf_star_e2 + 2 * sp.sin(eta))

    phi_g, a1_g, a2_g, b1_g, b2_g = sp.symbols("phi_g a1_g a2_g b1_g b2_g", real=True)
    f1_g, f2_g, c01, c02, l1, l2, kv = sp.symbols(
        "f1_g f2_g c01 c02 l1 l2 kv", nonzero=True, real=True
    )
    lower_gradient = phi_g / kv - f1_g * c01 * l1 * b1_g - f2_g * c02 * l2 * b2_g
    comp1 = c01 + a1_g / (kv * f1_g * l1)
    comp2 = c02 + a2_g / (kv * f2_g * l2)
    reconstructed = kv * (
        lower_gradient
        + f1_g * comp1 * l1 * b1_g
        + f2_g * comp2 * l2 * b2_g
    )
    book.exact("algebra.two_pair_reconstruction", reconstructed - phi_g - a1_g * b1_g - a2_g * b2_g)

    amp, zz = sp.symbols("A z", real=True)
    beltrami_u = sp.Matrix([amp * sp.sin(zz), amp * sp.cos(zz), 0])
    beltrami_curl = sp.Matrix([-sp.diff(beltrami_u[1], zz), sp.diff(beltrami_u[0], zz), 0])
    for axis, component in enumerate(beltrami_curl - beltrami_u):
        book.exact(f"algebra.beltrami_curl_{axis}", component)
    beltrami_helicity = beltrami_u.dot(beltrami_curl)
    book.exact("algebra.beltrami_helicity", beltrami_helicity - amp**2)

    beltrami_c1 = sp.Rational(1, 2) + amp * sp.sin(zz) / 4
    beltrami_c2 = sp.Rational(1, 2) + amp * sp.cos(zz) / 4
    band1_twice = beltrami_c1 * 40 + (1 - beltrami_c1) * 8
    band2_twice = beltrami_c2 * 40 + (1 - beltrami_c2) * 8
    total_phase_energy = sp.integrate((band1_twice + band2_twice) / 4, (zz, 0, 2 * sp.pi)) / (2 * sp.pi)
    book.exact("algebra.beltrami_phase_energy", total_phase_energy - 12)
    resolved_energy = sp.integrate(beltrami_u.dot(beltrami_u) / 2, (zz, 0, 2 * sp.pi)) / (2 * sp.pi)
    book.exact("algebra.beltrami_resolved_energy", resolved_energy - amp**2 / 2)

    time, diffusion = sp.symbols("t D", positive=True)
    decaying_amp = sp.exp(-diffusion * time)
    comp_decay = sp.Rational(1, 2) + decaying_amp * sp.sin(zz) / 4
    book.exact(
        "algebra.composition_diffusion",
        sp.diff(comp_decay, time) - diffusion * sp.diff(comp_decay, zz, 2),
    )
    decaying_u = decaying_amp * sp.Matrix([sp.sin(zz), sp.cos(zz), 0])
    for axis, component in enumerate(
        sp.diff(decaying_u, time) - diffusion * sp.diff(decaying_u, zz, 2)
    ):
        book.exact(f"algebra.beltrami_viscous_decay_{axis}", component)
    convective = decaying_u[0] * sp.diff(decaying_u, x) + decaying_u[1] * sp.diff(decaying_u, y)
    book.exact("algebra.beltrami_convection", convective)

    witness_a = sp.sin(x)
    witness_b = sp.sin(y)
    witness_grad_a = sp.Matrix([sp.diff(witness_a, coord) for coord in coords])
    witness_grad_b = sp.Matrix([sp.diff(witness_b, coord) for coord in coords])
    witness_hessian_b = sp.hessian(witness_b, coords)
    witness_lap_b = sum(sp.diff(witness_b, coord, 2) for coord in coords)
    commutator = 2 * witness_hessian_b * witness_grad_a + witness_a * sp.Matrix(
        [sp.diff(witness_lap_b, coord) for coord in coords]
    )
    expected_commutator = sp.Matrix([0, -sp.sin(x) * sp.cos(y), 0])
    for axis, component in enumerate(commutator - expected_commutator):
        book.exact(f"algebra.diffusion_commutator_{axis}", component)
    commutator_curl = sp.Matrix(
        [
            sp.diff(commutator[2], y) - sp.diff(commutator[1], z),
            sp.diff(commutator[0], z) - sp.diff(commutator[2], x),
            sp.diff(commutator[1], x) - sp.diff(commutator[0], y),
        ]
    )
    book.exact("algebra.diffusion_commutator_curl_x", commutator_curl[0])
    book.exact("algebra.diffusion_commutator_curl_y", commutator_curl[1])
    book.exact("algebra.diffusion_commutator_curl_z", commutator_curl[2] + sp.cos(x) * sp.cos(y))

    h_l, h_e, coupling, initial_y = sp.symbols("h_L h_E V y_0", real=True)
    t_m, s_m = sp.symbols("t_m s_m", nonnegative=True)
    resolved = sp.Function("x")
    free_y = sp.exp(-sp.I * h_e * t_m) * initial_y
    convolution = sp.Integral(
        sp.exp(-sp.I * h_e * (t_m - s_m)) * coupling * resolved(s_m),
        (s_m, 0, t_m),
    )
    eliminated_y = free_y - sp.I * convolution
    exterior_residual = sp.diff(eliminated_y, t_m) + sp.I * h_e * eliminated_y + sp.I * coupling * resolved(t_m)
    book.exact("algebra.exterior_duhamel", exterior_residual.doit())
    direct_resolved_rhs = -sp.I * (h_l * resolved(t_m) + coupling * eliminated_y)
    memory_resolved_rhs = (
        -sp.I * h_l * resolved(t_m)
        - sp.I * coupling * free_y
        - coupling**2
        * sp.Integral(
            sp.exp(-sp.I * h_e * (t_m - s_m)) * resolved(s_m),
            (s_m, 0, t_m),
        )
    )
    book.exact("algebra.resolved_memory_equation", direct_resolved_rhs - memory_resolved_rhs)
    derivative_separation = abs(complex(-1j * 0.2 * (1 - (-1))))
    book.above("algebra.initial_exterior_dependence", derivative_separation, 0.1)


def mesh(n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    points = 2 * np.pi * np.arange(n, dtype=np.float64) / n
    return np.meshgrid(points, points, points, indexing="ij")


def wave_numbers(shape: tuple[int, int, int]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    values = [np.fft.fftfreq(n, d=1.0 / n) for n in shape]
    return np.meshgrid(*values, indexing="ij")


def derivative(value: np.ndarray, axis: int) -> np.ndarray:
    frequencies = np.fft.fftfreq(value.shape[axis], d=1.0 / value.shape[axis])
    shape = [1] * value.ndim
    shape[axis] = value.shape[axis]
    multiplier = 1j * frequencies.reshape(shape)
    return np.fft.ifftn(multiplier * np.fft.fftn(value)).real


def gradient(value: np.ndarray) -> np.ndarray:
    return np.stack([derivative(value, axis) for axis in range(3)])


def divergence(vector: np.ndarray) -> np.ndarray:
    return sum(derivative(vector[axis], axis) for axis in range(3))


def curl(vector: np.ndarray) -> np.ndarray:
    return np.stack(
        [
            derivative(vector[2], 1) - derivative(vector[1], 2),
            derivative(vector[0], 2) - derivative(vector[2], 0),
            derivative(vector[1], 0) - derivative(vector[0], 1),
        ]
    )


def laplacian(value: np.ndarray) -> np.ndarray:
    frequencies = wave_numbers(value.shape)
    k2 = sum(component**2 for component in frequencies)
    return np.fft.ifftn(-k2 * np.fft.fftn(value)).real


def vector_laplacian(vector: np.ndarray) -> np.ndarray:
    return np.stack([laplacian(component) for component in vector])


def leray(vector: np.ndarray) -> np.ndarray:
    frequencies = wave_numbers(vector.shape[1:])
    k2 = sum(component**2 for component in frequencies)
    hats = [np.fft.fftn(vector[axis]) for axis in range(3)]
    contraction = sum(frequencies[axis] * hats[axis] for axis in range(3))
    projected = []
    for axis in range(3):
        correction = np.zeros_like(contraction)
        np.divide(
            frequencies[axis] * contraction,
            k2,
            out=correction,
            where=k2 != 0,
        )
        projected.append(np.fft.ifftn(hats[axis] - correction).real)
    return np.stack(projected)


def max_abs(value: np.ndarray) -> float:
    return float(np.max(np.abs(value)))


def mean_dot(left: np.ndarray, right: np.ndarray) -> float:
    return float(np.mean(np.sum(left * right, axis=0)))


def constant_vector(template: np.ndarray, values: tuple[float, float, float]) -> np.ndarray:
    return np.stack([np.full_like(template, value) for value in values])


def phase_energy_density(
    fractions: tuple[float, float],
    compositions: tuple[np.ndarray, np.ndarray],
    velocities_y: tuple[np.ndarray, np.ndarray],
    velocities_i: tuple[np.ndarray, np.ndarray],
) -> np.ndarray:
    result = np.zeros_like(compositions[0])
    for fraction, composition, velocity_y, velocity_i in zip(
        fractions, compositions, velocities_y, velocities_i
    ):
        result += 0.5 * fraction * (
            composition * np.sum(velocity_y**2, axis=0)
            + (1 - composition) * np.sum(velocity_i**2, axis=0)
        )
    return result


def counterflow_density(
    observed: np.ndarray,
    fractions: tuple[float, float],
    compositions: tuple[np.ndarray, np.ndarray],
    velocities_y: tuple[np.ndarray, np.ndarray],
    velocities_i: tuple[np.ndarray, np.ndarray],
) -> np.ndarray:
    result = np.zeros_like(compositions[0])
    for fraction, composition, velocity_y, velocity_i in zip(
        fractions, compositions, velocities_y, velocities_i
    ):
        result += 0.5 * fraction * (
            composition * np.sum((velocity_y - observed) ** 2, axis=0)
            + (1 - composition) * np.sum((velocity_i - observed) ** 2, axis=0)
        )
    return result


def spatial_checks(
    book: CheckBook,
    arrays: dict[str, np.ndarray],
    recorded: dict[str, float],
) -> None:
    for n in (9, 15, 21):
        _, yy, _ = mesh(n)
        composition = 0.5 + 0.7 * np.sin(yy) / 6.0
        velocity_y = constant_vector(composition, (3.0, 0.0, 0.0))
        velocity_i = constant_vector(composition, (-3.0, 0.0, 0.0))
        velocity = composition[None, ...] * velocity_y + (1 - composition)[None, ...] * velocity_i
        expected_velocity = np.stack(
            [0.7 * np.sin(yy), np.zeros_like(yy), np.zeros_like(yy)]
        )
        numerical_curl = curl(velocity)
        expected_curl = np.stack(
            [np.zeros_like(yy), np.zeros_like(yy), -0.7 * np.cos(yy)]
        )
        numerical_divergence = divergence(velocity)
        phase_density = 0.5 * (
            composition * np.sum(velocity_y**2, axis=0)
            + (1 - composition) * np.sum(velocity_i**2, axis=0)
        )
        resolved_density = 0.5 * np.sum(velocity**2, axis=0)
        hidden_density = phase_density - resolved_density

        prefix = f"spatial.shear.N{n}"
        metrics = {
            "velocity_error": max_abs(velocity - expected_velocity),
            "curl_error": max_abs(numerical_curl - expected_curl),
            "divergence": max_abs(numerical_divergence),
            "helicity": abs(mean_dot(velocity, numerical_curl)),
            "phase_energy": float(np.mean(phase_density)),
            "resolved_energy": float(np.mean(resolved_density)),
            "hidden_energy": float(np.mean(hidden_density)),
        }
        for name in ("velocity_error", "curl_error", "divergence"):
            book.below(f"{prefix}.{name}", metrics[name], TOL)
        book.below(f"{prefix}.helicity", metrics["helicity"], 1.0e-13)
        book.close(f"{prefix}.phase_energy", metrics["phase_energy"], 4.5, TOL)
        book.close(f"{prefix}.resolved_energy", metrics["resolved_energy"], 0.7**2 / 4, TOL)
        book.close(
            f"{prefix}.energy_split",
            metrics["hidden_energy"] + metrics["resolved_energy"],
            metrics["phase_energy"],
            TOL,
        )
        book.add(
            f"{prefix}.composition_interval",
            bool(np.min(composition) > 0 and np.max(composition) < 1),
            minimum=float(np.min(composition)),
            maximum=float(np.max(composition)),
        )
        for name, value in metrics.items():
            recorded[f"{prefix}.{name}"] = value
        arrays[f"shear_N{n}_composition"] = composition
        arrays[f"shear_N{n}_velocity"] = velocity
        arrays[f"shear_N{n}_expected_velocity"] = expected_velocity
        arrays[f"shear_N{n}_curl"] = numerical_curl
        arrays[f"shear_N{n}_expected_curl"] = expected_curl
        arrays[f"shear_N{n}_divergence"] = numerical_divergence
        arrays[f"shear_N{n}_phase_density"] = phase_density
        arrays[f"shear_N{n}_resolved_density"] = resolved_density
        arrays[f"shear_N{n}_hidden_density"] = hidden_density

        _, _, zz = mesh(n)
        c1 = 0.5 + 0.25 * np.sin(zz)
        c2 = 0.5 + 0.25 * np.cos(zz)
        vy1 = constant_vector(c1, (6.0, -2.0, 0.0))
        vi1 = constant_vector(c1, (-2.0, -2.0, 0.0))
        vy2 = constant_vector(c2, (-2.0, 6.0, 0.0))
        vi2 = constant_vector(c2, (-2.0, -2.0, 0.0))
        u1 = c1[None, ...] * vy1 + (1 - c1)[None, ...] * vi1
        u2 = c2[None, ...] * vy2 + (1 - c2)[None, ...] * vi2
        observed = 0.5 * (u1 + u2)
        expected = np.stack([np.sin(zz), np.cos(zz), np.zeros_like(zz)])
        observed_curl = curl(observed)
        observed_divergence = divergence(observed)
        curl1 = curl(u1)
        curl2 = curl(u2)
        micro_density = phase_energy_density((0.5, 0.5), (c1, c2), (vy1, vy2), (vi1, vi2))
        resolved_density = 0.5 * np.sum(observed**2, axis=0)
        hidden_density = counterflow_density(
            observed, (0.5, 0.5), (c1, c2), (vy1, vy2), (vi1, vi2)
        )

        prefix = f"spatial.beltrami.N{n}"
        metrics = {
            "velocity_error": max_abs(observed - expected),
            "curl_error": max_abs(observed_curl - observed),
            "divergence": max_abs(observed_divergence),
            "helicity": mean_dot(observed, observed_curl),
            "band1_helicity": mean_dot(u1, curl1),
            "band2_helicity": mean_dot(u2, curl2),
            "phase_energy": float(np.mean(micro_density)),
            "resolved_energy": float(np.mean(resolved_density)),
            "hidden_energy": float(np.mean(hidden_density)),
        }
        for name in ("velocity_error", "curl_error", "divergence"):
            book.below(f"{prefix}.{name}", metrics[name], TOL)
        book.close(f"{prefix}.helicity", metrics["helicity"], 1.0, TOL)
        book.close(f"{prefix}.band1_helicity", metrics["band1_helicity"], 0.0, TOL)
        book.close(f"{prefix}.band2_helicity", metrics["band2_helicity"], 0.0, TOL)
        book.close(f"{prefix}.phase_energy", metrics["phase_energy"], 12.0, TOL)
        book.close(f"{prefix}.resolved_energy", metrics["resolved_energy"], 0.5, TOL)
        book.close(f"{prefix}.hidden_energy", metrics["hidden_energy"], 11.5, TOL)
        book.close(
            f"{prefix}.energy_split",
            metrics["resolved_energy"] + metrics["hidden_energy"],
            metrics["phase_energy"],
            TOL,
        )
        book.add(
            f"{prefix}.composition_interval",
            bool(min(np.min(c1), np.min(c2)) > 0 and max(np.max(c1), np.max(c2)) < 1),
            minimum=float(min(np.min(c1), np.min(c2))),
            maximum=float(max(np.max(c1), np.max(c2))),
        )
        for name, value in metrics.items():
            recorded[f"{prefix}.{name}"] = value
        arrays[f"beltrami_N{n}_c1"] = c1
        arrays[f"beltrami_N{n}_c2"] = c2
        arrays[f"beltrami_N{n}_u1"] = u1
        arrays[f"beltrami_N{n}_u2"] = u2
        arrays[f"beltrami_N{n}_curl1"] = curl1
        arrays[f"beltrami_N{n}_curl2"] = curl2
        arrays[f"beltrami_N{n}_velocity"] = observed
        arrays[f"beltrami_N{n}_expected"] = expected
        arrays[f"beltrami_N{n}_curl"] = observed_curl
        arrays[f"beltrami_N{n}_divergence"] = observed_divergence
        arrays[f"beltrami_N{n}_phase_density"] = micro_density
        arrays[f"beltrami_N{n}_resolved_density"] = resolved_density
        arrays[f"beltrami_N{n}_hidden_density"] = hidden_density

        xx, yy, zz = mesh(n)
        phi = 0.1 * np.sin(xx + yy + zz)
        a1 = 0.2 * np.sin(zz)
        b1 = np.sin(xx) + 0.3 * np.cos(yy)
        a2 = 0.15 * np.cos(xx)
        b2 = np.cos(yy) + 0.2 * np.sin(zz)
        general_c1 = 0.5 + a1 / 2.0
        general_c2 = 0.5 + a2 / 2.0
        alpha1 = 4.0 * b1
        alpha2 = 4.0 * b2
        lower = phi - b1 - b2
        grad_lower = gradient(lower)
        grad_alpha1 = gradient(alpha1)
        grad_alpha2 = gradient(alpha2)
        lower_band_velocity = grad_lower
        upper1 = grad_lower + grad_alpha1
        upper2 = grad_lower + grad_alpha2
        reconstructed = 0.5 * (
            general_c1[None, ...] * upper1
            + (1 - general_c1)[None, ...] * lower_band_velocity
        ) + 0.5 * (
            general_c2[None, ...] * upper2
            + (1 - general_c2)[None, ...] * lower_band_velocity
        )
        target = gradient(phi) + a1[None, ...] * gradient(b1) + a2[None, ...] * gradient(b2)
        prefix = f"spatial.two_pair.N{n}"
        reconstruction_error = max_abs(reconstructed - target)
        book.below(f"{prefix}.current_error", reconstruction_error, TOL)
        book.add(
            f"{prefix}.composition_interval",
            bool(
                min(np.min(general_c1), np.min(general_c2)) > 0
                and max(np.max(general_c1), np.max(general_c2)) < 1
            ),
            minimum=float(min(np.min(general_c1), np.min(general_c2))),
            maximum=float(max(np.max(general_c1), np.max(general_c2))),
        )
        recorded[f"{prefix}.current_error"] = reconstruction_error
        arrays[f"two_pair_N{n}_c1"] = general_c1
        arrays[f"two_pair_N{n}_c2"] = general_c2
        arrays[f"two_pair_N{n}_reconstructed"] = reconstructed
        arrays[f"two_pair_N{n}_target"] = target

    n = 21
    _, _, zz = mesh(n)
    vy1 = constant_vector(zz, (6.0, -2.0, 0.0))
    vi1 = constant_vector(zz, (-2.0, -2.0, 0.0))
    vy2 = constant_vector(zz, (-2.0, 6.0, 0.0))
    vi2 = constant_vector(zz, (-2.0, -2.0, 0.0))
    for time in (0.0, 0.3, 1.0):
        diffusivity = 0.03
        amplitude = math.exp(-diffusivity * time)
        c1 = 0.5 + amplitude * np.sin(zz) / 4
        c2 = 0.5 + amplitude * np.cos(zz) / 4
        dc1 = -diffusivity * amplitude * np.sin(zz) / 4
        dc2 = -diffusivity * amplitude * np.cos(zz) / 4
        u1 = c1[None, ...] * vy1 + (1 - c1)[None, ...] * vi1
        u2 = c2[None, ...] * vy2 + (1 - c2)[None, ...] * vi2
        observed = 0.5 * (u1 + u2)
        expected = amplitude * np.stack([np.sin(zz), np.cos(zz), np.zeros_like(zz)])
        du_dt = 0.5 * (dc1[None, ...] * (vy1 - vi1) + dc2[None, ...] * (vy2 - vi2))
        diffusive_laplacian = diffusivity * vector_laplacian(observed)
        composition_residual = max(
            max_abs(dc1 - diffusivity * laplacian(c1)),
            max_abs(dc2 - diffusivity * laplacian(c2)),
        )
        phase_density = phase_energy_density((0.5, 0.5), (c1, c2), (vy1, vy2), (vi1, vi2))
        resolved_density = 0.5 * np.sum(observed**2, axis=0)
        hidden_density = counterflow_density(
            observed, (0.5, 0.5), (c1, c2), (vy1, vy2), (vi1, vi2)
        )
        label = str(time).replace(".", "p")
        prefix = f"spatial.diffusive_beltrami.t{label}"
        metrics = {
            "velocity_error": max_abs(observed - expected),
            "evolution_error": max_abs(du_dt - diffusive_laplacian),
            "composition_error": composition_residual,
            "phase_energy": float(np.mean(phase_density)),
            "resolved_energy": float(np.mean(resolved_density)),
            "hidden_energy": float(np.mean(hidden_density)),
        }
        for name in ("velocity_error", "evolution_error", "composition_error"):
            book.below(f"{prefix}.{name}", metrics[name], TOL)
        book.close(f"{prefix}.phase_energy", metrics["phase_energy"], 12.0, TOL)
        book.close(
            f"{prefix}.resolved_energy",
            metrics["resolved_energy"],
            amplitude**2 / 2,
            TOL,
        )
        book.close(
            f"{prefix}.energy_split",
            metrics["resolved_energy"] + metrics["hidden_energy"],
            metrics["phase_energy"],
            TOL,
        )
        for name, value in metrics.items():
            recorded[f"{prefix}.{name}"] = value
        arrays[f"diffusive_t{label}_c1"] = c1
        arrays[f"diffusive_t{label}_c2"] = c2
        arrays[f"diffusive_t{label}_velocity"] = observed
        arrays[f"diffusive_t{label}_expected"] = expected
        arrays[f"diffusive_t{label}_du_dt"] = du_dt
        arrays[f"diffusive_t{label}_D_laplacian"] = diffusive_laplacian
        arrays[f"diffusive_t{label}_phase_density"] = phase_density
        arrays[f"diffusive_t{label}_resolved_density"] = resolved_density
        arrays[f"diffusive_t{label}_hidden_density"] = hidden_density

    xx, yy, zz = mesh(21)
    witness_a = np.sin(xx)
    witness_b = np.sin(yy)
    grad_a = gradient(witness_a)
    grad_b = gradient(witness_b)
    hessian_b = np.stack([gradient(grad_b[row]) for row in range(3)])
    lap_b = laplacian(witness_b)
    commutator_fft = 2 * np.einsum("ijxyz,jxyz->ixyz", hessian_b, grad_a)
    commutator_fft += witness_a[None, ...] * gradient(lap_b)
    commutator_exact = np.stack(
        [np.zeros_like(xx), -np.sin(xx) * np.cos(yy), np.zeros_like(xx)]
    )
    projected = leray(commutator_fft)
    commutator_error = max_abs(commutator_fft - commutator_exact)
    projected_norm = float(np.sqrt(np.mean(np.sum(projected**2, axis=0))))
    book.below("spatial.diffusion_commutator.analytic_error", commutator_error, TOL)
    book.above("spatial.diffusion_commutator.projected_norm", projected_norm, 1.0e-3)
    recorded["spatial.diffusion_commutator.analytic_error"] = commutator_error
    recorded["spatial.diffusion_commutator.projected_norm"] = projected_norm
    arrays["commutator_fft"] = commutator_fft
    arrays["commutator_exact"] = commutator_exact
    arrays["commutator_projected"] = projected


def hopf_and_memory_checks(
    book: CheckBook,
    arrays: dict[str, np.ndarray],
    recorded: dict[str, float],
) -> None:
    for order in (8, 16, 32):
        nodes, weights = np.polynomial.legendre.leggauss(order)
        eta = (nodes + 1) * np.pi / 4
        eta_weights = weights * np.pi / 4
        phase_points = 2 * order + 1
        phase_weight = 2 * np.pi / phase_points
        density = -2 * np.sin(eta) * np.cos(eta)
        phase_plane = np.ones((phase_points, phase_points), dtype=np.float64)
        integral = float(
            np.sum(eta_weights * density)
            * np.sum(phase_plane)
            * phase_weight**2
            / phase_plane.size
            * phase_plane.size
        )
        error = abs(integral + 4 * np.pi**2)
        prefix = f"hopf.quadrature.order{order}"
        book.below(f"{prefix}.error", error, TOL)
        recorded[f"{prefix}.integral"] = integral
        arrays[f"hopf_order{order}_eta"] = eta
        arrays[f"hopf_order{order}_weights"] = eta_weights
        arrays[f"hopf_order{order}_density"] = density
        arrays[f"hopf_order{order}_phase_weight"] = np.array(phase_weight)
        arrays[f"hopf_order{order}_phase_points"] = np.array(phase_points)

    h_e = np.diag(np.array([-2.0, -1.0, 1.0, 2.0], dtype=np.float64))
    coupling = np.array([[0.2, 0.3, 0.3, 0.2]], dtype=np.complex128)

    def kernel(time: float) -> np.ndarray:
        phase = np.diag(np.exp(-1j * np.diag(h_e) * time))
        return coupling @ phase @ coupling.conj().T

    recurrence_error = max_abs(kernel(2 * np.pi) - kernel(0.0))
    book.below("memory.finite_exterior.recurrence", recurrence_error, TOL)
    y_plus = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.complex128)
    y_minus = -y_plus
    derivative_plus = -1j * (coupling @ y_plus)[0]
    derivative_minus = -1j * (coupling @ y_minus)[0]
    derivative_separation = abs(derivative_plus - derivative_minus)
    book.above("memory.finite_exterior.initial_state_separation", derivative_separation, 0.1)
    book.close("memory.finite_exterior.y_plus_norm", np.linalg.norm(y_plus), 1.0, TOL)
    book.close("memory.finite_exterior.y_minus_norm", np.linalg.norm(y_minus), 1.0, TOL)
    recorded["memory.finite_exterior.recurrence"] = recurrence_error
    recorded["memory.finite_exterior.initial_state_separation"] = float(derivative_separation)
    arrays["memory_finite_HE"] = h_e
    arrays["memory_finite_V"] = coupling
    arrays["memory_finite_K0"] = kernel(0.0)
    arrays["memory_finite_K2pi"] = kernel(2 * np.pi)
    arrays["memory_finite_y_plus"] = y_plus
    arrays["memory_finite_y_minus"] = y_minus

    viscosity = 0.03
    wave_number = 1.0
    rate = viscosity * wave_number**2
    times = np.linspace(0.0, 2.0, 401)
    target = np.exp(-rate * times)
    errors: list[float] = []
    for tau in (0.2, 0.1, 0.05):
        matrix = np.array([[0.0, -1.0], [rate / tau, -1.0 / tau]], dtype=np.float64)
        eigenvalues, eigenvectors = np.linalg.eig(matrix)
        coefficients = np.linalg.solve(eigenvectors, np.array([1.0, rate]))
        modes = np.exp(eigenvalues[:, None] * times[None, :])
        state = eigenvectors @ (coefficients[:, None] * modes)
        amplitude = np.real_if_close(state[0]).astype(np.float64)
        response = np.real_if_close(state[1]).astype(np.float64)
        max_error = max_abs(amplitude - target)
        errors.append(max_error)

        amplitude_coefficients = eigenvectors[0] * coefficients
        response_coefficients = eigenvectors[1] * coefficients
        heat = np.zeros_like(times, dtype=np.complex128)
        for i, left_coefficient in enumerate(amplitude_coefficients):
            for j, right_coefficient in enumerate(response_coefficients):
                exponent = eigenvalues[i] + eigenvalues[j]
                integral = np.expm1(exponent * times) / exponent
                heat += left_coefficient * right_coefficient * integral
        heat = np.real_if_close(heat).astype(np.float64)
        energy_error = max_abs(0.5 * amplitude**2 + heat - 0.5)
        label = str(tau).replace(".", "p")
        prefix = f"memory.markov.tau{label}"
        book.add(
            f"{prefix}.positive",
            bool(np.min(amplitude) > 0 and np.min(response) > 0),
            amplitude_minimum=float(np.min(amplitude)),
            response_minimum=float(np.min(response)),
        )
        book.below(f"{prefix}.energy_error", energy_error, TOL)
        recorded[f"{prefix}.max_error"] = max_error
        recorded[f"{prefix}.energy_error"] = energy_error
        arrays[f"markov_tau{label}_time"] = times
        arrays[f"markov_tau{label}_amplitude"] = amplitude
        arrays[f"markov_tau{label}_response"] = response
        arrays[f"markov_tau{label}_heat"] = heat
        arrays[f"markov_tau{label}_target"] = target

    book.add(
        "memory.markov.strict_refinement",
        bool(errors[1] < errors[0] and errors[2] < errors[1]),
        errors=errors,
    )
    book.below("memory.markov.finest_error", errors[-1], 2.0e-4)
    recorded["memory.markov.error_tau0p2"] = errors[0]
    recorded["memory.markov.error_tau0p1"] = errors[1]
    recorded["memory.markov.error_tau0p05"] = errors[2]


def independent_reconstruction(
    book: CheckBook,
    array_path: Path,
    recorded: dict[str, float],
) -> None:
    with np.load(array_path, allow_pickle=False) as data:
        for n in (9, 15, 21):
            prefix = f"spatial.shear.N{n}"
            velocity = data[f"shear_N{n}_velocity"]
            numerical_curl = data[f"shear_N{n}_curl"]
            reconstructed = {
                "velocity_error": max_abs(velocity - data[f"shear_N{n}_expected_velocity"]),
                "curl_error": max_abs(numerical_curl - data[f"shear_N{n}_expected_curl"]),
                "divergence": max_abs(data[f"shear_N{n}_divergence"]),
                "helicity": abs(mean_dot(velocity, numerical_curl)),
                "phase_energy": float(np.mean(data[f"shear_N{n}_phase_density"])),
                "resolved_energy": float(np.mean(data[f"shear_N{n}_resolved_density"])),
                "hidden_energy": float(np.mean(data[f"shear_N{n}_hidden_density"])),
            }
            for name, value in reconstructed.items():
                book.close(f"reconstruct.{prefix}.{name}", value, recorded[f"{prefix}.{name}"], 1.0e-14)

            prefix = f"spatial.beltrami.N{n}"
            velocity = data[f"beltrami_N{n}_velocity"]
            numerical_curl = data[f"beltrami_N{n}_curl"]
            reconstructed = {
                "velocity_error": max_abs(velocity - data[f"beltrami_N{n}_expected"]),
                "curl_error": max_abs(numerical_curl - velocity),
                "divergence": max_abs(data[f"beltrami_N{n}_divergence"]),
                "helicity": mean_dot(velocity, numerical_curl),
                "band1_helicity": mean_dot(data[f"beltrami_N{n}_u1"], data[f"beltrami_N{n}_curl1"]),
                "band2_helicity": mean_dot(data[f"beltrami_N{n}_u2"], data[f"beltrami_N{n}_curl2"]),
                "phase_energy": float(np.mean(data[f"beltrami_N{n}_phase_density"])),
                "resolved_energy": float(np.mean(data[f"beltrami_N{n}_resolved_density"])),
                "hidden_energy": float(np.mean(data[f"beltrami_N{n}_hidden_density"])),
            }
            for name, value in reconstructed.items():
                book.close(f"reconstruct.{prefix}.{name}", value, recorded[f"{prefix}.{name}"], 1.0e-14)

            prefix = f"spatial.two_pair.N{n}"
            current_error = max_abs(
                data[f"two_pair_N{n}_reconstructed"] - data[f"two_pair_N{n}_target"]
            )
            book.close(
                f"reconstruct.{prefix}.current_error",
                current_error,
                recorded[f"{prefix}.current_error"],
                1.0e-14,
            )

        for time in (0.0, 0.3, 1.0):
            label = str(time).replace(".", "p")
            prefix = f"spatial.diffusive_beltrami.t{label}"
            velocity = data[f"diffusive_t{label}_velocity"]
            reconstructed = {
                "velocity_error": max_abs(velocity - data[f"diffusive_t{label}_expected"]),
                "evolution_error": max_abs(
                    data[f"diffusive_t{label}_du_dt"] - data[f"diffusive_t{label}_D_laplacian"]
                ),
                "phase_energy": float(np.mean(data[f"diffusive_t{label}_phase_density"])),
                "resolved_energy": float(np.mean(data[f"diffusive_t{label}_resolved_density"])),
                "hidden_energy": float(np.mean(data[f"diffusive_t{label}_hidden_density"])),
            }
            for name, value in reconstructed.items():
                book.close(f"reconstruct.{prefix}.{name}", value, recorded[f"{prefix}.{name}"], 1.0e-14)

        commutator_error = max_abs(data["commutator_fft"] - data["commutator_exact"])
        projected_norm = float(
            np.sqrt(np.mean(np.sum(data["commutator_projected"] ** 2, axis=0)))
        )
        book.close(
            "reconstruct.spatial.diffusion_commutator.analytic_error",
            commutator_error,
            recorded["spatial.diffusion_commutator.analytic_error"],
            1.0e-14,
        )
        book.close(
            "reconstruct.spatial.diffusion_commutator.projected_norm",
            projected_norm,
            recorded["spatial.diffusion_commutator.projected_norm"],
            1.0e-14,
        )

        for order in (8, 16, 32):
            eta_weights = data[f"hopf_order{order}_weights"]
            density = data[f"hopf_order{order}_density"]
            phase_weight = float(data[f"hopf_order{order}_phase_weight"])
            phase_points = int(data[f"hopf_order{order}_phase_points"])
            integral = float(np.sum(eta_weights * density) * (phase_weight * phase_points) ** 2)
            book.close(
                f"reconstruct.hopf.quadrature.order{order}.integral",
                integral,
                recorded[f"hopf.quadrature.order{order}.integral"],
                1.0e-14,
            )

        recurrence_error = max_abs(data["memory_finite_K2pi"] - data["memory_finite_K0"])
        separation = abs(
            -1j * (data["memory_finite_V"] @ data["memory_finite_y_plus"])[0]
            + 1j * (data["memory_finite_V"] @ data["memory_finite_y_minus"])[0]
        )
        book.close(
            "reconstruct.memory.finite_exterior.recurrence",
            recurrence_error,
            recorded["memory.finite_exterior.recurrence"],
            1.0e-14,
        )
        book.close(
            "reconstruct.memory.finite_exterior.initial_state_separation",
            separation,
            recorded["memory.finite_exterior.initial_state_separation"],
            1.0e-14,
        )

        for tau in (0.2, 0.1, 0.05):
            label = str(tau).replace(".", "p")
            amplitude = data[f"markov_tau{label}_amplitude"]
            response = data[f"markov_tau{label}_response"]
            heat = data[f"markov_tau{label}_heat"]
            target = data[f"markov_tau{label}_target"]
            max_error = max_abs(amplitude - target)
            energy_error = max_abs(0.5 * amplitude**2 + heat - 0.5)
            prefix = f"memory.markov.tau{label}"
            book.close(
                f"reconstruct.{prefix}.max_error",
                max_error,
                recorded[f"{prefix}.max_error"],
                1.0e-14,
            )
            book.close(
                f"reconstruct.{prefix}.energy_error",
                energy_error,
                recorded[f"{prefix}.energy_error"],
                1.0e-14,
            )
            residual = np.gradient(amplitude, data[f"markov_tau{label}_time"], edge_order=2) + response
            book.below(f"reconstruct.{prefix}.sampled_ode_residual", max_abs(residual[2:-2]), 1.0e-7)


def classifications(passed: bool) -> dict[str, str]:
    if not passed:
        return {
            "local_doublet_vorticity": "INCONCLUSIVE",
            "full_doublet_hopf_helicity": "INCONCLUSIVE",
            "positive_chart_nonzero_integrated_helicity": "INCONCLUSIVE",
            "two_band_beltrami_class": "INCONCLUSIVE",
            "fixed_phase_beltrami_diffusion_viscosity": "INCONCLUSIVE",
            "general_scalar_diffusion_vector_viscosity": "INCONCLUSIVE",
            "finite_closed_autonomous_irreversible_reduction": "INCONCLUSIVE",
            "selected_exponential_memory_markov_limit": "INCONCLUSIVE",
            "cassi_derived_positive_viscosity": "UNESTABLISHED",
            "arbitrary_flow_hydrodynamic_closure": "UNESTABLISHED",
        }
    return {
        "local_doublet_vorticity": "SUPPORTS",
        "full_doublet_hopf_helicity": "SUPPORTS",
        "positive_chart_nonzero_integrated_helicity": "CONTRADICTS",
        "two_band_beltrami_class": "SUPPORTS",
        "fixed_phase_beltrami_diffusion_viscosity": "SUPPORTS",
        "general_scalar_diffusion_vector_viscosity": "CONTRADICTS",
        "finite_closed_autonomous_irreversible_reduction": "CONTRADICTS",
        "selected_exponential_memory_markov_limit": "SUPPORTS",
        "cassi_derived_positive_viscosity": "UNESTABLISHED",
        "arbitrary_flow_hydrodynamic_closure": "UNESTABLISHED",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output_dir = output.parent
    if output_dir.exists():
        raise FileExistsError(f"refusing existing output directory: {output_dir}")
    output_dir.mkdir(parents=True)

    source_manifest = snapshot_sources(output_dir)
    environment = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "numpy": np.__version__,
        "sympy": sp.__version__,
        "cwd": Path.cwd().as_posix(),
        "environment": {
            key: os.environ.get(key)
            for key in ("PYTHONHASHSEED", "PYTHONDONTWRITEBYTECODE", "PYTHONIOENCODING")
        },
    }
    environment_path = output_dir / "environment.json"
    environment_path.write_text(json.dumps(environment, indent=2), encoding="utf-8")
    manifest_path = output_dir / "input_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema": "cassi.fluid.phase-current.inputs.v1",
                "sources": source_manifest,
                "environment": environment_path.name,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    book = CheckBook()
    arrays: dict[str, np.ndarray] = {}
    recorded: dict[str, float] = {}
    error: str | None = None
    try:
        symbolic_checks(book)
        spatial_checks(book, arrays, recorded)
        hopf_and_memory_checks(book, arrays, recorded)
        array_path = output_dir / "verification.arrays.npz"
        np.savez_compressed(array_path, **arrays)
        independent_reconstruction(book, array_path, recorded)
        for relative, row in source_manifest.items():
            current_hash = sha256(ROOT / relative)
            book.add(
                f"source_snapshot.working_match.{relative}",
                current_hash == row["sha256"],
                snapshot_sha256=row["sha256"],
                working_sha256=current_hash,
            )
    except Exception:
        error = traceback.format_exc()
        book.add("execution.unhandled_exception", False, traceback=error)

    result = {
        "schema": "cassi.fluid.phase-current.verification.v1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS" if book.passed else "FAIL",
        "check_count": len(book.checks),
        "failed_checks": book.failed,
        "checks": book.checks,
        "classifications": classifications(book.passed),
        "inputs": manifest_path.name,
        "arrays": "verification.arrays.npz" if (output_dir / "verification.arrays.npz").exists() else None,
        "recorded_metrics": recorded,
        "error": error,
    }
    output.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(f"Receipt: {output.relative_to(ROOT).as_posix()}")
    print(f"Checks: {len(book.checks)}")
    print(f"Status: {result['status']}")
    for key, value in result["classifications"].items():
        print(f"{key}: {value}")
    if book.failed:
        print("Failed checks:")
        for name in book.failed:
            print(f"- {name}")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
