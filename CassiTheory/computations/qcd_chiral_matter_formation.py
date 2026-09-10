#!/usr/bin/env python3
"""Run the frozen QCD-anchored chiral matter-formation calculation.

Run from the CassiTheory root. The protocol is
computations/qcd-chiral-matter-formation-prereg.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import scipy
import torch
from scipy.integrate import solve_bvp
from scipy.signal import resample

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
PROTOCOL = ROOT / "computations" / "qcd-chiral-matter-formation-prereg.md"
SCHEMA = "cassi.qcd-chiral-matter-formation.v1"
PROTOCOL_START = "<!-- qcd-chiral-formation-protocol:start -->"
PROTOCOL_END = "<!-- qcd-chiral-formation-protocol:end -->"

F_PI_MEV = 93.0
M_PI_MEV = 138.0
SKYRME_E = 4.25
KAPPA_SQ = 20.0
HBARC_MEV_FM = 197.3269804
MU = M_PI_MEV / (SKYRME_E * F_PI_MEV)
LAMBDA = KAPPA_SQ / SKYRME_E**2
V_SQ = 1.0 - MU**2 / LAMBDA
C_VAC = LAMBDA * (1.0 - V_SQ) ** 2 / 4.0 - MU**2
M_SIGMA_MEV = math.sqrt(2.0 * KAPPA_SQ * F_PI_MEV**2 + M_PI_MEV**2)
L_PHYSICAL_FM = 5.0
DIMENSIONLESS_LENGTH = SKYRME_E * F_PI_MEV * L_PHYSICAL_FM / HBARC_MEV_FM
EPSILON = 1.0e-6
ATTEMPTED_DS = 2.0e-3
MAX_COMPONENT_CHANGE = 0.02
ENERGY_REL_TOL = 1.0e-9
MAX_HALVINGS = 24
MAX_ACCEPTED_STEPS = 100_000
EDGE_LIMIT = math.pi / 2.0
COEFFICIENT_TOL = 1.0e-10
DETERMINANT_TOL = 1.0e-13
AMBIGUITY_COEFFICIENT_TOL = 1.0e-9
AMBIGUITY_DETERMINANT_TOL = 1.0e-12
RETAINED_S = (0.0, 0.05, 0.10, 0.25, 0.50, 1.0, 2.0, 4.0, 8.0)
SEEDS = (104729, 104759, 104761, 104773, 104779, 104789)
T_C_MEV = (155.0, 158.0)
G_STAR = (17.25, 61.75)
PLANCK_MASS_GEV = 1.220890e19
GEV_INV_S = 6.582119569e-25
FM_OVER_C_S = 3.3356409519815204e-24

TETRAHEDRA = np.asarray(
    (
        ((0, 0, 0), (1, 0, 0), (1, 1, 0), (1, 1, 1)),
        ((0, 0, 0), (1, 1, 0), (0, 1, 0), (1, 1, 1)),
        ((0, 0, 0), (0, 1, 0), (0, 1, 1), (1, 1, 1)),
        ((0, 0, 0), (0, 1, 1), (0, 0, 1), (1, 1, 1)),
        ((0, 0, 0), (0, 0, 1), (1, 0, 1), (1, 1, 1)),
        ((0, 0, 0), (1, 0, 1), (1, 0, 0), (1, 1, 1)),
    ),
    dtype=np.int64,
)
ROOTS = np.sqrt(np.asarray((2.0, 3.0, 5.0, 7.0), dtype=np.float64))
PHASES = np.asarray((0.11, 0.23, 0.37, 0.53), dtype=np.float64)
TARGETS = np.asarray(
    [
        np.sin(m * ROOTS + PHASES) / np.linalg.norm(np.sin(m * ROOTS + PHASES))
        for m in range(1, 17)
    ],
    dtype=np.float64,
)


class NumericalFailure(RuntimeError):
    """A frozen numerical stop condition."""


class ProtocolFailure(RuntimeError):
    """The preregistered protocol cannot be identified exactly."""


def canonical_lf(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def root_relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def source_identity(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {"sha256": sha256_bytes(raw), "bytes": len(raw)}


def frozen_protocol_bytes() -> bytes:
    text = canonical_lf(PROTOCOL.read_bytes()).decode("utf-8")
    if text.count(PROTOCOL_START) != 1 or text.count(PROTOCOL_END) != 1:
        raise ProtocolFailure("Protocol markers are missing or non-unique")
    frozen = text.split(PROTOCOL_START, 1)[1].split(PROTOCOL_END, 1)[0]
    return frozen.encode("utf-8")


def protocol_identity() -> dict[str, Any]:
    frozen = frozen_protocol_bytes()
    return {
        "path": root_relative(PROTOCOL),
        "sha256": sha256_bytes(frozen),
        "bytes": len(frozen),
    }


def strict_json_write(path: Path, payload: Any) -> None:
    text = json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    temporary.replace(path)


def prepare_output(path: Path) -> Path:
    output = path.expanduser().resolve()
    if output.exists():
        if not output.is_dir() or any(output.iterdir()):
            raise ValueError(f"--output must be absent or empty: {output}")
    else:
        output.mkdir(parents=True)
    return output


def save_npz(output: Path, name: str, **arrays: Any) -> dict[str, Any]:
    path = output / name
    if path.exists():
        raise FileExistsError(f"Artifact already exists: {path}")
    with path.open("xb") as stream:
        np.savez(stream, **arrays)
    return {"file": name, "sha256": sha256_file(path), "bytes": path.stat().st_size}


def shell_mask(n: int) -> np.ndarray:
    mask = np.zeros((n, n, n), dtype=bool)
    mask[0, :, :] = True
    mask[-1, :, :] = True
    mask[:, 0, :] = True
    mask[:, -1, :] = True
    mask[:, :, 0] = True
    mask[:, :, -1] = True
    return mask


def impose_boundary_numpy(field: np.ndarray) -> np.ndarray:
    out = np.asarray(field).copy()
    mask = shell_mask(out.shape[-1])
    if out.ndim == 4:
        out[:, mask] = 0.0
        out[0, mask] = 1.0
    elif out.ndim == 5:
        out[:, :, mask] = 0.0
        out[:, 0, mask] = 1.0
    else:
        raise ValueError(f"Expected rank-4 or rank-5 field, received {out.shape}")
    return out


def numpy_energy_components(field: np.ndarray, h: float, include_u4: bool) -> dict[str, float]:
    phi = np.asarray(field, dtype=np.float64)
    if phi.ndim != 4 or phi.shape[0] != 4:
        raise ValueError(f"Expected (4,N,N,N), received {phi.shape}")
    forward = [(np.roll(phi, -1, axis=axis) - phi) / h for axis in (1, 2, 3)]
    e2_density = 0.5 * sum(np.sum(d * d, axis=0) for d in forward)
    e4_density = np.zeros_like(e2_density)
    if include_u4:
        norms = np.linalg.norm(phi, axis=0)
        hat = phi / np.maximum(norms, EPSILON)[None]
        dhat = [(np.roll(hat, -1, axis=axis) - hat) / h for axis in (1, 2, 3)]
        for a in range(3):
            for b in range(a + 1, 3):
                aa = np.sum(dhat[a] * dhat[a], axis=0)
                bb = np.sum(dhat[b] * dhat[b], axis=0)
                ab = np.sum(dhat[a] * dhat[b], axis=0)
                e4_density += 0.5 * (aa * bb - ab * ab)
    radius_sq = np.sum(phi * phi, axis=0)
    potential_density = LAMBDA * (radius_sq - V_SQ) ** 2 / 4.0 - MU**2 * phi[0] - C_VAC
    volume = h**3
    values = {
        "e2": volume * float(np.sum(e2_density, dtype=np.float64)),
        "e4": volume * float(np.sum(e4_density, dtype=np.float64)),
        "potential": volume * float(np.sum(potential_density, dtype=np.float64)),
    }
    values["total"] = values["e2"] + values["e4"] + values["potential"]
    return values


def torch_energy_densities(
    field: torch.Tensor, h: float, include_u4: bool
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    forward = [(torch.roll(field, -1, dims=axis) - field) / h for axis in (2, 3, 4)]
    e2 = 0.5 * sum(torch.sum(d * d, dim=1) for d in forward)
    e4 = torch.zeros_like(e2)
    if include_u4:
        norms = torch.linalg.vector_norm(field, dim=1, keepdim=True)
        hat = field / torch.clamp(norms, min=EPSILON)
        dhat = [(torch.roll(hat, -1, dims=axis) - hat) / h for axis in (2, 3, 4)]
        for a in range(3):
            for b in range(a + 1, 3):
                aa = torch.sum(dhat[a] * dhat[a], dim=1)
                bb = torch.sum(dhat[b] * dhat[b], dim=1)
                ab = torch.sum(dhat[a] * dhat[b], dim=1)
                e4 = e4 + 0.5 * (aa * bb - ab.square())
    radius_sq = torch.sum(field * field, dim=1)
    potential = LAMBDA * (radius_sq - V_SQ).square() / 4.0 - MU**2 * field[:, 0] - C_VAC
    return e2, e4, potential


def torch_component_values(parts: tuple[torch.Tensor, ...], h: float) -> tuple[np.ndarray, np.ndarray]:
    arrays = [
        (h**3 * part.sum(dim=(1, 2, 3), dtype=torch.float64)).detach().cpu().numpy()
        for part in parts
    ]
    components = np.stack(arrays, axis=1)
    return components, np.sum(components, axis=1)


def torch_gradient_and_energy(
    field: torch.Tensor, h: float, include_u4: bool, mask: torch.Tensor
) -> tuple[torch.Tensor, np.ndarray]:
    variable = field.detach().requires_grad_(True)
    parts = torch_energy_densities(variable, h, include_u4)
    loss = sum(part.sum() for part in parts)
    (gradient,) = torch.autograd.grad(loss, variable)
    gradient = gradient.masked_fill(mask[None, None], 0.0)
    _, total = torch_component_values(parts, h)
    return gradient.detach(), total


def torch_energy(field: torch.Tensor, h: float, include_u4: bool) -> np.ndarray:
    with torch.no_grad():
        _, total = torch_component_values(torch_energy_densities(field, h, include_u4), h)
    return total


def exact_unit(field: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    norms = np.linalg.norm(field, axis=0)
    if np.any(norms == 0.0):
        denominator = np.maximum(norms, np.finfo(np.float64).tiny)
    else:
        denominator = norms
    return field / denominator[None], norms


def max_edge_angle(field: np.ndarray) -> float:
    unit, norms = exact_unit(np.asarray(field, dtype=np.float64))
    if np.any(norms == 0.0):
        return math.pi
    maximum = 0.0
    for axis in (1, 2, 3):
        dot = np.sum(unit * np.roll(unit, -1, axis=axis), axis=0)
        maximum = max(maximum, float(np.max(np.arccos(np.clip(dot, -1.0, 1.0)))))
    return maximum


def baryon_density(field: np.ndarray, h: float) -> np.ndarray:
    unit, _ = exact_unit(np.asarray(field, dtype=np.float64))
    derivatives = [
        (np.roll(unit, -1, axis=axis) - np.roll(unit, 1, axis=axis)) / (2.0 * h)
        for axis in (1, 2, 3)
    ]
    columns = np.stack((unit, derivatives[0], derivatives[1], derivatives[2]), axis=-1)
    matrices = np.moveaxis(columns, 0, -2)
    return np.linalg.det(matrices) / (2.0 * math.pi**2)


def periodic_rms(weight: np.ndarray, physical_spacing: float) -> float | None:
    weights = np.asarray(weight, dtype=np.float64)
    total = float(np.sum(weights, dtype=np.float64))
    if total <= 1.0e-30:
        return None
    n = weights.shape[0]
    index = np.arange(n, dtype=np.float64)
    radius_sq = np.zeros_like(weights)
    for axis in range(3):
        shape = [1, 1, 1]
        shape[axis] = n
        coordinate = index.reshape(shape)
        phase = np.exp(2.0j * math.pi * coordinate / n)
        moment = np.sum(weights * phase)
        centre = (math.atan2(float(moment.imag), float(moment.real)) % (2.0 * math.pi)) * n / (2.0 * math.pi)
        delta = coordinate - centre
        delta -= n * np.round(delta / n)
        radius_sq += (physical_spacing * delta) ** 2
    return math.sqrt(float(np.sum(weights * radius_sq, dtype=np.float64)) / total)


def boundary_error(field: np.ndarray) -> float:
    phi = np.asarray(field, dtype=np.float64)
    mask = shell_mask(phi.shape[-1])
    expected = np.zeros((4, int(np.count_nonzero(mask))), dtype=np.float64)
    expected[0] = 1.0
    return float(np.max(np.abs(phi[:, mask] - expected)))


def regular_value_snapshot(field: np.ndarray, chunk_cubes: int = 16384) -> dict[str, Any]:
    phi = np.asarray(field, dtype=np.float64)
    if phi.ndim != 4 or phi.shape[0] != 4 or len(set(phi.shape[1:])) != 1:
        raise ValueError(f"Expected cubic (4,N,N,N) field, received {phi.shape}")
    if not np.all(np.isfinite(phi)):
        raise NumericalFailure("Nonfinite field in regular-value calculation")
    n = phi.shape[1]
    positive = np.zeros(len(TARGETS), dtype=np.int64)
    negative = np.zeros(len(TARGETS), dtype=np.int64)
    ambiguous = np.zeros(len(TARGETS), dtype=np.int64)
    total_cubes = n**3

    for start in range(0, total_cubes, chunk_cubes):
        flat = np.arange(start, min(total_cubes, start + chunk_cubes), dtype=np.int64)
        bases = np.stack((flat // (n * n), (flat // n) % n, flat % n), axis=1)
        for tetrahedron in TETRAHEDRA:
            columns = []
            for offset in tetrahedron:
                indices = (bases + offset[None]) % n
                columns.append(phi[:, indices[:, 0], indices[:, 1], indices[:, 2]].T)
            matrices = np.stack(columns, axis=2)
            determinants = np.linalg.det(matrices)
            usable = np.flatnonzero(np.abs(determinants) > DETERMINANT_TOL)
            if usable.size == 0:
                continue
            selected = matrices[usable]
            inverses = np.linalg.inv(selected)
            coefficients = np.einsum("nij,kj->nik", inverses, TARGETS, optimize=True)
            det_selected = determinants[usable]
            edges = np.stack(
                (
                    tetrahedron[1] - tetrahedron[0],
                    tetrahedron[2] - tetrahedron[0],
                    tetrahedron[3] - tetrahedron[0],
                ),
                axis=1,
            )
            domain_sign = int(np.sign(np.linalg.det(edges.astype(np.float64))))
            if domain_sign == 0:
                raise NumericalFailure("Degenerate frozen tetrahedron")
            for target_index in range(len(TARGETS)):
                c = coefficients[:, :, target_index]
                covered = np.all(c > COEFFICIENT_TOL, axis=1)
                near_simplex = np.all(c > -AMBIGUITY_COEFFICIENT_TOL, axis=1)
                near_face = near_simplex & np.any(np.abs(c) <= AMBIGUITY_COEFFICIENT_TOL, axis=1)
                near_determinant = covered & (np.abs(det_selected) < AMBIGUITY_DETERMINANT_TOL)
                ambiguous[target_index] += int(np.count_nonzero(near_face | near_determinant))
                signs = np.sign(det_selected[covered]).astype(np.int64) * domain_sign
                positive[target_index] += int(np.count_nonzero(signs > 0))
                negative[target_index] += int(np.count_nonzero(signs < 0))

    degrees = positive - negative
    common_degree = int(degrees[0]) if np.all(degrees == degrees[0]) else None
    rows = [
        {
            "index": index,
            "positive_hits": int(positive[index]),
            "negative_hits": int(negative[index]),
            "signed_degree": int(degrees[index]),
        }
        for index in range(len(TARGETS))
    ]
    ambiguity_count = int(np.sum(ambiguous))
    resolved = bool(
        max_edge_angle(phi) < EDGE_LIMIT
        and ambiguity_count == 0
        and np.all(positive >= 1)
        and np.all(negative >= 1)
        and common_degree is not None
    )
    return {
        "targets": rows,
        "ambiguity_count": ambiguity_count,
        "common_degree": common_degree,
        "resolved_positive_negative": resolved,
    }


def snapshot_metrics(field: np.ndarray, h: float, physical_spacing: float, include_u4: bool) -> dict[str, Any]:
    phi = np.asarray(field, dtype=np.float64)
    energies = numpy_energy_components(phi, h, include_u4)
    unit, norms = exact_unit(phi)
    del unit
    b = baryon_density(phi, h)
    positive = np.clip(b, 0.0, None)
    negative = np.clip(-b, 0.0, None)
    volume = h**3
    return {
        "total": energies["total"],
        "e2": energies["e2"],
        "e4": energies["e4"],
        "potential": energies["potential"],
        "mean_norm": float(np.mean(norms, dtype=np.float64)),
        "min_norm": float(np.min(norms)),
        "cutoff_hits": int(np.count_nonzero(norms <= EPSILON)),
        "max_edge_angle": max_edge_angle(phi),
        "B": volume * float(np.sum(b, dtype=np.float64)),
        "Bpos": volume * float(np.sum(positive, dtype=np.float64)),
        "Bneg": volume * float(np.sum(negative, dtype=np.float64)),
        "baryon_rms_fm": periodic_rms(np.abs(b), physical_spacing),
        "boundary_error": boundary_error(phi),
    }


def solve_radial_profile() -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    r = np.linspace(1.0e-5, 64.0, 1201)
    radius = 1.0 / math.sqrt(2.0)
    theta = 2.0 * np.arctan(r / radius)
    theta_prime = 2.0 * radius / (r * r + radius * radius)

    def rhs(x: np.ndarray, y: np.ndarray) -> np.ndarray:
        value, derivative = y
        sine = np.sin(value)
        second = (
            -2.0 * x * derivative
            - np.sin(2.0 * value) * (derivative * derivative - 1.0 - sine * sine / (x * x))
            - MU * MU * x * x * sine
        ) / (x * x + 2.0 * sine * sine)
        return np.vstack((derivative, second))

    def bc(left: np.ndarray, right: np.ndarray) -> np.ndarray:
        return np.asarray((left[0] - r[0] * left[1], right[0] - math.pi), dtype=np.float64)

    solution = solve_bvp(rhs, bc, r, np.vstack((theta, theta_prime)), tol=1.0e-8, max_nodes=100_000)
    if not solution.success:
        raise NumericalFailure(f"Massive radial profile failed: {solution.message}")
    sample = np.linspace(0.0, 64.0, 64_001)
    evaluated = solution.sol(np.maximum(sample, r[0]))
    f = math.pi - evaluated[0]
    f_prime = -evaluated[1]
    f[0] = math.pi
    f[-1] = 0.0
    diagnostics = {
        "success": bool(solution.success),
        "nodes": int(solution.x.size),
        "max_rms_residual": float(np.max(solution.rms_residuals)),
        "left_regular_residual": float(solution.y[0, 0] - r[0] * solution.y[1, 0]),
        "right_residual": float(solution.y[0, -1] - math.pi),
        "passes": bool(
            solution.success
            and float(np.max(solution.rms_residuals)) < 1.0e-6
            and abs(float(solution.y[0, 0] - r[0] * solution.y[1, 0])) < 1.0e-8
            and abs(float(solution.y[0, -1] - math.pi)) < 1.0e-8
        ),
    }
    return sample, f, f_prime, diagnostics


def coordinates(n: int, spacing: float) -> np.ndarray:
    index = np.arange(n, dtype=np.float64) - n / 2.0
    return np.stack(np.meshgrid(index * spacing, index * spacing, index * spacing, indexing="ij"))


def hedgehog(n: int, h: float, radial: tuple[np.ndarray, np.ndarray], reflected: bool) -> np.ndarray:
    xyz = coordinates(n, h)
    radius = np.linalg.norm(xyz, axis=0)
    knots, profile = radial
    f = np.interp(radius, knots, profile, left=profile[0], right=profile[-1])
    unit = xyz / np.maximum(radius, 1.0e-30)[None]
    field = np.concatenate((np.cos(f)[None], np.sin(f)[None] * unit), axis=0)
    field[1:, radius == 0.0] = 0.0
    if reflected:
        field[1] *= -1.0
    return impose_boundary_numpy(field)


def random_pair_fields() -> tuple[dict[int, list[np.ndarray]], list[dict[str, Any]]]:
    grids: dict[int, list[np.ndarray]] = {30: [], 40: []}
    metadata: list[dict[str, Any]] = []
    for seed in SEEDS:
        rng = np.random.Generator(np.random.PCG64(seed))
        primary = rng.standard_normal((4, 30, 30, 30), dtype=np.float64)
        for component in range(4):
            primary[component] -= float(np.mean(primary[component], dtype=np.float64))
            primary[component] *= 0.3 / float(np.std(primary[component], ddof=0, dtype=np.float64))
        refined = primary
        for axis in (1, 2, 3):
            refined = resample(refined, 40, axis=axis)
        refined = np.asarray(refined.real, dtype=np.float64)
        grids[30].append(impose_boundary_numpy(primary))
        grids[40].append(impose_boundary_numpy(refined))
        metadata.append({"id": f"random_{seed}", "kind": "random", "seed": seed})
    return grids, metadata


def control_suite(
    output: Path, device: torch.device, radial: tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]
) -> dict[str, Any]:
    controls: dict[str, Any] = {}

    n_vac = 16
    h_vac = DIMENSIONLESS_LENGTH / n_vac
    vacuum = np.zeros((1, 4, n_vac, n_vac, n_vac), dtype=np.float64)
    vacuum[:, 0] = 1.0
    vacuum_t = torch.as_tensor(vacuum, dtype=torch.float64, device="cpu").requires_grad_(True)
    loss_vac = sum(part.sum() for part in torch_energy_densities(vacuum_t, h_vac, True))
    (vacuum_gradient,) = torch.autograd.grad(loss_vac, vacuum_t)
    vacuum_residual = [float(torch.max(torch.abs(vacuum_gradient[:, c])).item()) for c in range(4)]
    controls["vacuum"] = {
        "N": n_vac,
        "component_residual_max": vacuum_residual,
        "residual_max": max(vacuum_residual),
        "passes": max(vacuum_residual) < 1.0e-7,
    }

    n_dir = 10
    h_dir = DIMENSIONLESS_LENGTH / n_dir
    u = np.arange(n_dir, dtype=np.float64) / (n_dir - 1.0)
    ux, uy, uz = np.meshgrid(u, u, u, indexing="ij")
    window = np.sin(math.pi * ux) ** 2 * np.sin(math.pi * uy) ** 2 * np.sin(math.pi * uz) ** 2
    field = np.empty((4, n_dir, n_dir, n_dir), dtype=np.float64)
    field[0] = 1.0 + 0.03 * window * np.cos(2.0 * math.pi * ux)
    field[1] = 0.08 * window * np.sin(2.0 * math.pi * ux)
    field[2] = 0.07 * window * np.cos(2.0 * math.pi * uy)
    field[3] = 0.06 * window * np.sin(2.0 * math.pi * uz)
    direction = np.stack(
        (
            window * np.sin(2.0 * math.pi * (uy + uz)),
            window * np.cos(2.0 * math.pi * (ux - uz)),
            window * np.sin(2.0 * math.pi * (ux + uy)),
            window * np.cos(2.0 * math.pi * (uy - uz)),
        )
    )
    direction /= np.linalg.norm(direction)
    eta = 1.0e-5
    field_t = torch.as_tensor(field[None], dtype=torch.float64, device="cpu").requires_grad_(True)
    parts = torch_energy_densities(field_t, h_dir, True)
    energy_t = h_dir**3 * sum(part.sum() for part in parts)
    (gradient_t,) = torch.autograd.grad(energy_t, field_t)
    automatic = float(torch.sum(gradient_t[0] * torch.as_tensor(direction, dtype=torch.float64)).item())
    plus = numpy_energy_components(field + eta * direction, h_dir, True)["total"]
    minus = numpy_energy_components(field - eta * direction, h_dir, True)["total"]
    finite_difference = (plus - minus) / (2.0 * eta)
    relative_error = abs(automatic - finite_difference) / max(1.0, abs(automatic), abs(finite_difference))
    directional_artifact = save_npz(
        output,
        "directional_control.npz",
        field=field,
        direction=direction,
        h=np.asarray(h_dir, dtype=np.float64),
        eta=np.asarray(eta, dtype=np.float64),
        include_u4=np.asarray(1, dtype=np.int8),
    )
    controls["directional_derivative"] = {
        "artifact": directional_artifact,
        "automatic": automatic,
        "finite_difference": finite_difference,
        "relative_error": relative_error,
        "passes": relative_error < 3.0e-4,
    }

    checker = np.zeros((4, n_vac, n_vac, n_vac), dtype=np.float64)
    checker[0] = 1.0
    ii, jj, kk = np.meshgrid(np.arange(n_vac), np.arange(n_vac), np.arange(n_vac), indexing="ij")
    checker[1] = 0.1 * np.where((ii + jj + kk) % 2 == 0, 1.0, -1.0)
    checker = impose_boundary_numpy(checker)
    checker_energy = numpy_energy_components(checker, h_vac, True)
    controls["checkerboard"] = {
        "N": n_vac,
        "energies": checker_energy,
        "passes": bool(checker_energy["total"] > 0.0 and checker_energy["e2"] > 0.0),
    }

    r, f, f_prime, radial_diagnostics = radial
    radial_artifact = save_npz(
        output,
        "radial_profile.npz",
        r=r,
        F=f,
        F_prime=f_prime,
        mu=np.asarray(MU, dtype=np.float64),
    )
    controls["radial_profile"] = {"artifact": radial_artifact, **radial_diagnostics}
    controls["device_probe"] = {
        "requested": str(device),
        "resolved": str(device),
        "passes": device.type in ("cpu", "cuda"),
    }
    return controls


def cosmology_control() -> dict[str, Any]:
    rows = []
    for temperature_mev in T_C_MEV:
        for g_star in G_STAR:
            temperature_gev = temperature_mev / 1000.0
            hubble_gev = 1.66 * math.sqrt(g_star) * temperature_gev**2 / PLANCK_MASS_GEV
            hubble_inverse_s = GEV_INV_S / hubble_gev
            rows.append(
                {
                    "temperature_mev": temperature_mev,
                    "g_star": g_star,
                    "H_GeV": hubble_gev,
                    "H_inverse_s": hubble_inverse_s,
                    "ratio_to_0p5_fm_over_c": hubble_inverse_s / (0.5 * FM_OVER_C_S),
                    "ratio_to_2_fm_over_c": hubble_inverse_s / (2.0 * FM_OVER_C_S),
                }
            )
    minimum_ratio = min(row["ratio_to_2_fm_over_c"] for row in rows)
    maximum_ratio = max(row["ratio_to_0p5_fm_over_c"] for row in rows)
    return {
        "classification": "crossover",
        "temperature_bracket_mev": list(T_C_MEV),
        "g_star_bracket": list(G_STAR),
        "rows": rows,
        "minimum_ratio_to_2_fm_over_c": minimum_ratio,
        "maximum_ratio_to_0p5_fm_over_c": maximum_ratio,
    }


def torch_boundary(field: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    vacuum = torch.zeros((1, 4, 1, 1, 1), dtype=field.dtype, device=field.device)
    vacuum[:, 0] = 1.0
    return torch.where(mask[None, None], vacuum, field)


def state_cutoff(field: torch.Tensor) -> tuple[np.ndarray, np.ndarray]:
    with torch.no_grad():
        norms = torch.linalg.vector_norm(field, dim=1)
        hits = torch.sum(norms <= EPSILON, dim=(1, 2, 3), dtype=torch.int64).cpu().numpy()
        minima = torch.amin(norms, dim=(1, 2, 3)).to(torch.float64).cpu().numpy()
    return hits, minima


def time_token(value: float) -> str:
    return format(value, ".12g").replace(".", "p")


def evolve_group(
    *,
    group_id: str,
    initial: np.ndarray,
    events: list[dict[str, Any]],
    n: int,
    include_u4: bool,
    device: torch.device,
    output: Path,
    receipt: dict[str, Any],
    receipt_path: Path,
) -> dict[str, Any]:
    h = DIMENSIONLESS_LENGTH / n
    physical_spacing = L_PHYSICAL_FM / n
    mask_np = shell_mask(n)
    mask = torch.as_tensor(mask_np, dtype=torch.bool, device=device)
    field = torch.as_tensor(initial, dtype=torch.float32, device=device)
    field = torch_boundary(field, mask)
    event_ids = [row["id"] for row in events]
    group: dict[str, Any] = {
        "id": group_id,
        "N": n,
        "physical_spacing_fm": physical_spacing,
        "dimensionless_spacing": h,
        "include_u4": include_u4,
        "events": events,
        "snapshots": [],
        "accepted_steps": 0,
        "halvings": 0,
        "completed": False,
    }
    receipt["groups"].append(group)
    strict_json_write(receipt_path, receipt)

    initial_energy = torch_energy(field, h, include_u4)
    initial_hits, initial_minima = state_cutoff(field)
    history_s = [0.0]
    history_ds = [0.0]
    history_energies = [initial_energy]
    history_halvings = [0]
    history_cutoff = [initial_hits]
    history_min_norm = [initial_minima]
    accepted_steps = 0
    current_s = 0.0

    def save_snapshot(retained: float) -> None:
        state = field.detach().to(torch.float64).cpu().numpy()
        metrics: dict[str, Any] = {}
        for event_index, event_id in enumerate(event_ids):
            row = snapshot_metrics(state[event_index], h, physical_spacing, include_u4)
            if retained in (4.0, 8.0):
                row["regular_value"] = regular_value_snapshot(state[event_index])
            metrics[event_id] = row
        artifact = save_npz(
            output,
            f"{group_id}_s_{time_token(retained)}.npz",
            field=state,
            event_ids=np.asarray(event_ids),
            s=np.asarray(retained, dtype=np.float64),
            N=np.asarray(n, dtype=np.int64),
            dimensionless_spacing=np.asarray(h, dtype=np.float64),
            physical_spacing_fm=np.asarray(physical_spacing, dtype=np.float64),
            include_u4=np.asarray(int(include_u4), dtype=np.int8),
        )
        group["snapshots"].append({"s": retained, "artifact": artifact, "events": metrics})
        strict_json_write(receipt_path, receipt)
        print(
            json.dumps(
                {
                    "group": group_id,
                    "s": retained,
                    "accepted_steps": accepted_steps,
                    "energy_range": [min(row["total"] for row in metrics.values()), max(row["total"] for row in metrics.values())],
                },
                allow_nan=False,
            ),
            flush=True,
        )

    try:
        save_snapshot(0.0)
        for retained in RETAINED_S[1:]:
            while current_s < retained - 1.0e-14:
                gradient, current_energy = torch_gradient_and_energy(field, h, include_u4, mask)
                if not np.all(np.isfinite(current_energy)) or not bool(torch.all(torch.isfinite(gradient)).item()):
                    raise NumericalFailure(f"{group_id}: nonfinite state or gradient at s={current_s}")
                max_gradient = float(torch.max(torch.abs(gradient)).item())
                bounds = [ATTEMPTED_DS, retained - current_s]
                if max_gradient > 0.0:
                    bounds.append(MAX_COMPONENT_CHANGE / max_gradient)
                ds = min(bounds)
                if not math.isfinite(ds) or ds <= 0.0:
                    raise NumericalFailure(f"{group_id}: invalid attempted step at s={current_s}")

                accepted = False
                used_halvings = 0
                candidate_energy: np.ndarray | None = None
                candidate: torch.Tensor | None = None
                for halving in range(MAX_HALVINGS + 1):
                    candidate = torch_boundary(field - ds * gradient, mask)
                    if not bool(torch.all(torch.isfinite(candidate)).item()):
                        raise NumericalFailure(f"{group_id}: nonfinite candidate at s={current_s}")
                    candidate_energy = torch_energy(candidate, h, include_u4)
                    if not np.all(np.isfinite(candidate_energy)):
                        raise NumericalFailure(f"{group_id}: nonfinite candidate energy at s={current_s}")
                    tolerance = ENERGY_REL_TOL * np.maximum(1.0, np.abs(current_energy))
                    if np.all(candidate_energy - current_energy <= tolerance):
                        accepted = True
                        used_halvings = halving
                        break
                    if halving == MAX_HALVINGS:
                        break
                    ds *= 0.5
                if not accepted or candidate is None or candidate_energy is None:
                    raise NumericalFailure(f"{group_id}: rejected candidate after 24 halvings at s={current_s}")

                field = candidate.detach()
                current_s += ds
                if abs(current_s - retained) <= 2.0e-13:
                    current_s = retained
                accepted_steps += 1
                if accepted_steps > MAX_ACCEPTED_STEPS:
                    raise NumericalFailure(f"{group_id}: exceeded 100000 accepted steps before s=8")
                hits, minima = state_cutoff(field)
                history_s.append(current_s)
                history_ds.append(ds)
                history_energies.append(candidate_energy)
                history_halvings.append(used_halvings)
                history_cutoff.append(hits)
                history_min_norm.append(minima)
            save_snapshot(retained)

        history_arrays = {
            "s": np.asarray(history_s, dtype=np.float64),
            "ds": np.asarray(history_ds, dtype=np.float64),
            "energies": np.asarray(history_energies, dtype=np.float64),
            "halvings": np.asarray(history_halvings, dtype=np.int64),
            "cutoff_hits": np.asarray(history_cutoff, dtype=np.int64),
            "min_norm": np.asarray(history_min_norm, dtype=np.float64),
        }
        history_artifact = save_npz(output, f"{group_id}_history.npz", **history_arrays)
        late = history_arrays["s"] >= 4.0 - 1.0e-12
        group["history"] = history_artifact
        group["history_shape"] = {
            "rows": int(history_arrays["s"].size),
            "events": len(event_ids),
            "event_ids": event_ids,
        }
        group["accepted_steps"] = accepted_steps
        group["halvings"] = int(np.sum(history_arrays["halvings"], dtype=np.int64))
        energy_differences = np.diff(history_arrays["energies"], axis=0)
        energy_tolerances = ENERGY_REL_TOL * np.maximum(
            1.0, np.abs(history_arrays["energies"][:-1])
        )
        group["max_accepted_energy_increase"] = float(np.max(energy_differences))
        group["max_energy_tolerance_excess"] = float(
            np.max(energy_differences - energy_tolerances)
        )
        group["history_energy_rule_passes"] = bool(
            np.all(energy_differences <= energy_tolerances)
        )
        group["late_cutoff_hits_max"] = {
            event_id: int(np.max(history_arrays["cutoff_hits"][late, event_index]))
            for event_index, event_id in enumerate(event_ids)
        }
        group["completed"] = True
        strict_json_write(receipt_path, receipt)
        return group
    except Exception:
        partial_name = f"{group_id}_history_partial.npz"
        if not (output / partial_name).exists():
            group["history_partial"] = save_npz(
                output,
                partial_name,
                s=np.asarray(history_s, dtype=np.float64),
                ds=np.asarray(history_ds, dtype=np.float64),
                energies=np.asarray(history_energies, dtype=np.float64),
                halvings=np.asarray(history_halvings, dtype=np.int64),
                cutoff_hits=np.asarray(history_cutoff, dtype=np.int64),
                min_norm=np.asarray(history_min_norm, dtype=np.float64),
            )
        group["accepted_steps"] = accepted_steps
        group["halvings"] = int(np.sum(np.asarray(history_halvings, dtype=np.int64)))
        strict_json_write(receipt_path, receipt)
        raise


def snapshot_at(group: dict[str, Any], retained: float) -> dict[str, Any]:
    matches = [row for row in group["snapshots"] if float(row["s"]) == retained]
    if len(matches) != 1:
        raise NumericalFailure(f"{group['id']}: missing unique s={retained} snapshot")
    return matches[0]


def classify(receipt: dict[str, Any]) -> None:
    groups = {row["id"]: row for row in receipt["groups"]}
    controls = receipt["controls"]
    histories_monotone = all(
        row["completed"] and row["history_energy_rule_passes"]
        for row in groups.values()
    )
    maximum_boundary_error = max(
        metric["boundary_error"]
        for group in groups.values()
        for snap in group["snapshots"]
        for metric in snap["events"].values()
    )
    qcf1 = bool(
        controls["vacuum"]["passes"]
        and controls["directional_derivative"]["passes"]
        and controls["checkerboard"]["passes"]
        and histories_monotone
        and maximum_boundary_error < 1.0e-7
        and all(group["completed"] for group in groups.values())
    )

    prepared_rows: list[dict[str, Any]] = []
    retained_signs = True
    radius_qualified = 0
    endpoint_absent = False
    for group_id in ("N30_complete", "N40_complete"):
        group = groups[group_id]
        for event_id, expected in (("prepared_positive", 1), ("prepared_negative", -1)):
            event_pass = True
            radius_pass = True
            endpoint_degree: int | None = None
            time_rows = []
            for retained in (4.0, 8.0):
                metric = snapshot_at(group, retained)["events"][event_id]
                regular = metric["regular_value"]
                degree = regular["common_degree"]
                if retained == 8.0:
                    endpoint_degree = degree
                topo_pass = bool(
                    degree == expected
                    and regular["ambiguity_count"] == 0
                    and metric["max_edge_angle"] < EDGE_LIMIT
                    and metric["cutoff_hits"] == 0
                    and abs(metric["B"]) >= 0.65
                )
                radius = metric["baryon_rms_fm"]
                radius_here = radius is not None and 0.20 <= radius <= 1.20
                event_pass = event_pass and topo_pass
                radius_pass = radius_pass and radius_here
                time_rows.append(
                    {
                        "s": retained,
                        "degree": degree,
                        "B": metric["B"],
                        "radius_fm": radius,
                        "topology_pass": topo_pass,
                        "radius_pass": radius_here,
                    }
                )
            retained_signs = retained_signs and event_pass
            radius_qualified += int(radius_pass)
            endpoint_absent = endpoint_absent or endpoint_degree != expected
            prepared_rows.append(
                {
                    "group": group_id,
                    "event": event_id,
                    "expected_degree": expected,
                    "times": time_rows,
                    "retains_sign": event_pass,
                    "radius_qualified": radius_pass,
                }
            )
    qcf2_supports = bool(qcf1 and retained_signs and radius_qualified >= 3)
    if not qcf1:
        qcf2_verdict = "INCONCLUSIVE"
    elif qcf2_supports:
        qcf2_verdict = "SUPPORTS"
    elif endpoint_absent:
        qcf2_verdict = "CONTRADICTS"
    else:
        qcf2_verdict = "INCONCLUSIVE"

    def resolved(group: dict[str, Any], event_id: str, retained: float) -> bool:
        metric = snapshot_at(group, retained)["events"][event_id]
        return bool(
            metric["regular_value"]["resolved_positive_negative"]
            and metric["cutoff_hits"] == 0
            and group["late_cutoff_hits_max"][event_id] == 0
        )

    random_ids = [f"random_{seed}" for seed in SEEDS]
    persistent_counts: dict[str, int] = {}
    endpoint_counts: dict[str, int] = {}
    for group_id in ("N30_complete", "N40_complete", "N30_no_u4"):
        group = groups[group_id]
        persistent_counts[group_id] = sum(
            resolved(group, event_id, 4.0) and resolved(group, event_id, 8.0)
            for event_id in random_ids
        )
        endpoint_counts[group_id] = sum(resolved(group, event_id, 8.0) for event_id in random_ids)
    qcf3_emerges = bool(
        qcf1
        and persistent_counts["N30_complete"] >= 4
        and persistent_counts["N40_complete"] >= 4
        and abs(persistent_counts["N30_complete"] - persistent_counts["N40_complete"]) <= 2
        and endpoint_counts["N30_complete"] - endpoint_counts["N30_no_u4"] >= 3
    )
    no_complete_endpoint = (
        endpoint_counts["N30_complete"] == 0 and endpoint_counts["N40_complete"] == 0
    )
    if not qcf1:
        qcf3_verdict = "INCONCLUSIVE"
    elif qcf3_emerges:
        qcf3_verdict = "EMERGES"
    elif no_complete_endpoint:
        qcf3_verdict = "DOES NOT EMERGE"
    else:
        qcf3_verdict = "INCONCLUSIVE"

    qcf4_candidates = []
    for group_id in ("N30_complete", "N40_complete"):
        group = groups[group_id]
        for event_id in random_ids:
            if not (resolved(group, event_id, 4.0) and resolved(group, event_id, 8.0)):
                continue
            degree4 = snapshot_at(group, 4.0)["events"][event_id]["regular_value"]["common_degree"]
            degree8 = snapshot_at(group, 8.0)["events"][event_id]["regular_value"]["common_degree"]
            prior_rows = [snap["events"][event_id] for snap in group["snapshots"] if float(snap["s"]) < 4.0]
            boundary_interval = any(
                row["min_norm"] <= 10.0 * EPSILON or row["max_edge_angle"] >= EDGE_LIMIT
                for row in prior_rows
            )
            qcf4_candidates.append(
                {
                    "group": group_id,
                    "event": event_id,
                    "degree_s4": degree4,
                    "degree_s8": degree8,
                    "boundary_interval": boundary_interval,
                }
            )
    qcf4_supports = bool(
        qcf1
        and any(
            row["degree_s4"] == 0 and row["degree_s8"] == 0 and row["boundary_interval"]
            for row in qcf4_candidates
        )
    )
    if not qcf1:
        qcf4_verdict = "INCONCLUSIVE"
    elif qcf4_supports:
        qcf4_verdict = "SUPPORTS"
    elif qcf4_candidates:
        qcf4_verdict = "CONTRADICTS"
    else:
        qcf4_verdict = "INCONCLUSIVE"

    cosmology = controls["cosmology"]
    qcf5_contradicts = bool(
        cosmology["classification"] == "crossover"
        and cosmology["minimum_ratio_to_2_fm_over_c"] > 1.0e12
    )
    qcf5_supports = bool(
        cosmology["classification"] == "first-order"
        and cosmology["maximum_ratio_to_0p5_fm_over_c"] < 1.0e3
    )
    qcf5_verdict = "CONTRADICTS" if qcf5_contradicts else "SUPPORTS" if qcf5_supports else "INCONCLUSIVE"

    completion_requirements = [
        {
            "requirement": "Cassi selection of microscopic QCD action and quantum state",
            "present": False,
            "evidence": "QCD is an empirical input and no Cassi-to-QCD selection rule is supplied.",
        },
        {
            "requirement": "quark baryon-current transport through chiral zeros",
            "present": False,
            "evidence": "The classical order-parameter calculation has no quark-current transport observable.",
        },
        {
            "requirement": "fermionic spin and statistics of late textures",
            "present": False,
            "evidence": "The classical fields are not collectively quantized with a Finkelstein-Rubinstein sector.",
        },
        {
            "requirement": "density-operator occupation numbers and production probabilities",
            "present": False,
            "evidence": "The dissipative ensemble is classical and carries no density operator.",
        },
        {
            "requirement": "unfitted cosmological initial state and cooling history",
            "present": False,
            "evidence": "The random hot field is stipulated and relaxation coordinate s has no cosmological-time map.",
        },
    ]
    qcf6 = all(row["present"] for row in completion_requirements)

    receipt["formation_summary"] = {
        "prepared": prepared_rows,
        "persistent_random_counts": persistent_counts,
        "endpoint_random_counts": endpoint_counts,
        "qcf4_candidates": qcf4_candidates,
    }
    receipt["gates"] = {
        "QCF1": {
            "passed": qcf1,
            "inputs": {
                "vacuum": controls["vacuum"]["passes"],
                "directional_derivative": controls["directional_derivative"]["passes"],
                "checkerboard": controls["checkerboard"]["passes"],
                "histories_monotone": histories_monotone,
                "maximum_boundary_error": maximum_boundary_error,
                "no_numerical_stop": all(group["completed"] for group in groups.values()),
            },
        },
        "QCF2": {
            "passed": qcf2_supports,
            "inputs": {
                "retained_signs": retained_signs,
                "radius_qualified_textures": radius_qualified,
                "endpoint_sign_absent": endpoint_absent,
            },
        },
        "QCF3": {
            "passed": qcf3_emerges,
            "inputs": {
                "persistent_counts": persistent_counts,
                "endpoint_counts": endpoint_counts,
            },
        },
        "QCF4": {
            "passed": qcf4_supports,
            "inputs": {"candidates": qcf4_candidates},
        },
        "QCF5": {
            "passed": qcf5_supports,
            "inputs": {
                "classification": cosmology["classification"],
                "minimum_ratio_to_2_fm_over_c": cosmology["minimum_ratio_to_2_fm_over_c"],
                "maximum_ratio_to_0p5_fm_over_c": cosmology["maximum_ratio_to_0p5_fm_over_c"],
            },
        },
        "QCF6": {
            "passed": qcf6,
            "inputs": {"requirements": completion_requirements},
        },
    }
    receipt["verdicts"] = {
        "QCF1": "PASS" if qcf1 else "FAIL",
        "QCF2": qcf2_verdict,
        "QCF3": qcf3_verdict,
        "QCF4": qcf4_verdict,
        "QCF5": qcf5_verdict,
        "QCF6": "PASS" if qcf6 else "FAIL",
    }
    receipt["complete_physical_matter_formation"] = bool(qcf6)


def make_receipt(device_arg: str, device: torch.device) -> dict[str, Any]:
    protocol = protocol_identity()
    constants = {
        "f_pi_mev": F_PI_MEV,
        "m_pi_mev": M_PI_MEV,
        "skyrme_e": SKYRME_E,
        "kappa_sq": KAPPA_SQ,
        "hbarc_mev_fm": HBARC_MEV_FM,
        "mu": MU,
        "lambda": LAMBDA,
        "v_sq": V_SQ,
        "c_vac": C_VAC,
        "m_sigma_mev": M_SIGMA_MEV,
        "physical_length_fm": L_PHYSICAL_FM,
        "dimensionless_length": DIMENSIONLESS_LENGTH,
        "epsilon": EPSILON,
        "attempted_ds": ATTEMPTED_DS,
        "max_component_change": MAX_COMPONENT_CHANGE,
        "energy_relative_tolerance": ENERGY_REL_TOL,
        "max_halvings": MAX_HALVINGS,
        "max_accepted_steps": MAX_ACCEPTED_STEPS,
        "edge_angle_limit": EDGE_LIMIT,
        "coefficient_tolerance": COEFFICIENT_TOL,
        "determinant_tolerance": DETERMINANT_TOL,
        "ambiguity_coefficient_tolerance": AMBIGUITY_COEFFICIENT_TOL,
        "ambiguity_determinant_tolerance": AMBIGUITY_DETERMINANT_TOL,
        "retained_s": list(RETAINED_S),
        "seeds": list(SEEDS),
        "targets": TARGETS.tolist(),
        "tetrahedra": TETRAHEDRA.tolist(),
    }
    return {
        "schema": SCHEMA,
        "completed": False,
        "scientific_execution_started": False,
        "protocol": protocol,
        "sources": {
            root_relative(SELF): source_identity(SELF),
            root_relative(PROTOCOL): source_identity(PROTOCOL),
        },
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "torch": torch.__version__,
            "torch_hip": torch.version.hip,
            "platform": platform.platform(),
            "requested_device": device_arg,
            "resolved_device": str(device),
            "torch_dtype": "float32",
            "pid": os.getpid(),
        },
        "constants": constants,
        "controls": {},
        "groups": [],
    }


def run(args: argparse.Namespace) -> int:
    output = prepare_output(args.output)
    receipt_path = output / "results.json"
    if args.device == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA/ROCm accelerator requested but torch.cuda.is_available() is false")
        device = torch.device("cuda")
    else:
        device = torch.device("cpu")
    torch.set_num_threads(4)
    start = time.perf_counter()
    receipt = make_receipt(args.device, device)
    strict_json_write(receipt_path, receipt)

    try:
        radial = solve_radial_profile()
        controls = control_suite(output, device, radial)
        controls["cosmology"] = cosmology_control()
        receipt["controls"] = controls
        strict_json_write(receipt_path, receipt)

        h30 = DIMENSIONLESS_LENGTH / 30.0
        base30 = hedgehog(30, h30, (radial[0], radial[1]), reflected=False)
        reflected30 = hedgehog(30, h30, (radial[0], radial[1]), reflected=True)
        base_topology = regular_value_snapshot(base30)
        reflected_topology = regular_value_snapshot(reflected30)
        base_degree = base_topology["common_degree"]
        reflected_degree = reflected_topology["common_degree"]
        if {base_degree, reflected_degree} != {-1, 1}:
            raise NumericalFailure(
                f"Prepared orientation control did not produce opposite unit degrees: {base_degree}, {reflected_degree}"
            )
        base_is_positive = base_degree == 1
        controls["prepared_orientation"] = {
            "base": base_topology,
            "reflected": reflected_topology,
            "base_is_positive": base_is_positive,
            "passes": True,
        }
        strict_json_write(receipt_path, receipt)

        random_grids, random_metadata = random_pair_fields()
        event_metadata = [
            {"id": "prepared_positive", "kind": "prepared", "seed": None},
            {"id": "prepared_negative", "kind": "prepared", "seed": None},
            *random_metadata,
        ]
        initial_by_n: dict[int, np.ndarray] = {}
        for n in (30, 40):
            h = DIMENSIONLESS_LENGTH / n
            ordinary = hedgehog(n, h, (radial[0], radial[1]), reflected=False)
            reflected = hedgehog(n, h, (radial[0], radial[1]), reflected=True)
            positive = ordinary if base_is_positive else reflected
            negative = reflected if base_is_positive else ordinary
            initial_by_n[n] = np.stack((positive, negative, *random_grids[n]), axis=0)

        receipt["scientific_execution_started"] = True
        strict_json_write(receipt_path, receipt)
        evolve_group(
            group_id="N30_complete",
            initial=initial_by_n[30],
            events=event_metadata,
            n=30,
            include_u4=True,
            device=device,
            output=output,
            receipt=receipt,
            receipt_path=receipt_path,
        )
        evolve_group(
            group_id="N40_complete",
            initial=initial_by_n[40],
            events=event_metadata,
            n=40,
            include_u4=True,
            device=device,
            output=output,
            receipt=receipt,
            receipt_path=receipt_path,
        )
        evolve_group(
            group_id="N30_no_u4",
            initial=initial_by_n[30],
            events=event_metadata,
            n=30,
            include_u4=False,
            device=device,
            output=output,
            receipt=receipt,
            receipt_path=receipt_path,
        )
        classify(receipt)
        receipt["wall_s"] = time.perf_counter() - start
        receipt["completed"] = True
        strict_json_write(receipt_path, receipt)
        print(
            json.dumps(
                {
                    "completed": True,
                    "output": str(output),
                    "wall_s": receipt["wall_s"],
                    "verdicts": receipt["verdicts"],
                    "complete_physical_matter_formation": receipt["complete_physical_matter_formation"],
                },
                allow_nan=False,
            ),
            flush=True,
        )
        return 0
    except Exception as exc:
        receipt["completed"] = False
        receipt["wall_s"] = time.perf_counter() - start
        receipt["failure"] = {"type": type(exc).__name__, "message": str(exc)}
        receipt["verdicts"] = {
            "QCF1": "FAIL",
            "QCF2": "INCONCLUSIVE",
            "QCF3": "INCONCLUSIVE",
            "QCF4": "INCONCLUSIVE",
            "QCF5": "INCONCLUSIVE",
            "QCF6": "FAIL",
        }
        receipt["complete_physical_matter_formation"] = False
        strict_json_write(receipt_path, receipt)
        print(json.dumps(receipt["failure"], allow_nan=False), file=sys.stderr, flush=True)
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
