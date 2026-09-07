#!/usr/bin/env python3
"""Independent NumPy verifier for the canonical density--velocity excitation receipt.

This module deliberately contains no import of the primary program or of the two-fluid
solver.  It rebuilds the source right hand side from the equations and validates the
primary's raw NPZ/JSON receipt before doing any scientific comparison.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
from scipy.linalg import expm

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NOTE = ROOT / "computations" / "matter-formation-continuum-report.md"
DEFAULT_SOLVER = ROOT / "two-fluid" / "cassi_two_fluid_3d_gpu.py"
SCHEMA = "matter-formation-canonical-excitation-verification-v1"
PRIMARY_SCHEMA = "matter-formation-canonical-excitation-v1"
FROZEN_PROTOCOL_SHA256 = "4c3d0eb3fd1739b8f01cdf0dabcddcc983755ebe41197d89300accc86aa6e98b"
SOLVER_CANONICAL_SHA256 = "258e8783294250b731d93e7b5869b8172558c8aa0742502330cf3dbb5e3c90cc"
HEADING = "### 21.3 Canonical excitation calculation: pre-execution criteria"
VERDICT = "SUPPORTS—homogeneous canonical excitation and regular-observable boundaries"
INCONCLUSIVE = "INCONCLUSIVE"
CASES = (
    ("base_matched", "base", 0.4, 0.4 / ((1.0 + math.sqrt(5.0)) / 2.0), 0.2, 0.03, 0.02, 0.0, 0.0, False),
    ("base_attraction", "base", 0.4, 0.0, 0.2, 0.03, 0.02, 0.0, 0.0, False),
    ("base_repulsion", "base", 0.4, 0.4, 0.2, 0.03, 0.02, 0.0, 0.0, False),
    ("base_guard", "base", 0.0, 0.4, 0.2, 0.03, 0.02, 0.0, 0.0, False),
    ("base_jordan", "base", 0.4, None, 0.2, 0.03, 0.02, 0.0, 0.0, False),
    ("expanding_gated", "expanding", 0.4, None, 0.2, 0.03, 0.02, 0.0004, 0.7, True),
    ("expanding_ungated", "expanding", 0.4, None, 0.2, 0.03, 0.02, 0.0, 0.7, False),
    ("expanding_transport", "expanding", 0.4, None, 0.0, 0.0, 0.0, 0.0, 0.7, True),
)
WAVEVECTORS = ((1, 0, 0), (1, 1, 0), (1, 1, 1), (0, 0, 0), (6, 0, 0))
AMPLITUDES = np.asarray((1.0e-3, 5.0e-4), dtype=np.float64)
N = 16
L = 2.0 * math.pi
RHO0 = 2.0
LAMBDA = 0.2
NU = 0.02
U = np.asarray((0.2, -0.1, 0.05), dtype=np.float64)
PHI = (1.0 + math.sqrt(5.0)) / 2.0
PHI_INV = 1.0 / PHI
PHI_INV2 = 0.382
ROW_TOL = 1.0e-9
TRAJ_TOL = 1.0e-9


def canonical_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def raw_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(path: Path) -> str:
    return hashlib.sha256(canonical_bytes(path)).hexdigest()


def protocol_section(path: Path) -> bytes:
    text = canonical_bytes(path).decode("utf-8")
    heading = HEADING + "\n"
    if text.count(heading) != 1:
        raise ValueError("frozen section heading is not unique")
    start = text.index(heading)
    tail = text[start + len(heading) :]
    boundary = re.search(r"\n(?=#{1,3} )", tail)
    end = start + len(heading) + (boundary.start() if boundary else len(tail))
    return (text[start:end].rstrip() + "\n").encode("utf-8")


def strict_json(path: Path) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in items:
            if key in out:
                raise ValueError(f"duplicate JSON key: {key}")
            out[key] = value
        return out

    def constant(value: str) -> Any:
        raise ValueError(f"non-finite JSON constant: {value}")

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs, parse_constant=constant)


def finite_array(value: Any) -> bool:
    arr = np.asarray(value)
    return np.all(np.isfinite(arr))


def finite_number(value: Any) -> bool:
    return isinstance(value, (int, float, np.number)) and not isinstance(value, bool) and math.isfinite(float(value))


def safe(value: Any) -> Any:
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): safe(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [safe(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def normalized_error(actual: Any, expected: Any) -> float:
    aa = np.asarray(actual)
    bb = np.asarray(expected)
    if aa.shape != bb.shape or not finite_array(aa) or not finite_array(bb):
        return math.inf
    scale = max(1.0, float(np.max(np.abs(bb)))) if bb.size else 1.0
    return float(np.max(np.abs(aa - bb)) / scale) if aa.size else 0.0


def trajectory_error(actual: Any, expected: Any) -> float:
    aa = np.asarray(actual)
    bb = np.asarray(expected)
    if aa.shape != bb.shape or not finite_array(aa) or not finite_array(bb):
        return math.inf
    return float(np.max(np.abs(aa - bb)) / 1.0e-4) if aa.size else 0.0


def close_scalar(actual: Any, expected: Any, tol: float = ROW_TOL) -> bool:
    return finite_number(actual) and finite_number(expected) and abs(float(actual) - float(expected)) <= tol * max(1.0, abs(float(actual)), abs(float(expected)))


def make_kgrid() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    # Match the source's float32 reciprocal-spacing multiplication order.
    labels = np.fft.fftfreq(N, d=1.0 / N).astype(np.float32)
    k1 = (2.0 * np.pi * (labels * np.float32(1.0 / L))).astype(np.float64)
    kz, ky, kx = np.meshgrid(k1, k1, k1, indexing="ij")
    k2 = kx * kx + ky * ky + kz * kz
    kmax = float(np.max(np.abs(k1)))
    mask = ((np.abs(kx) < (2.0 / 3.0) * kmax) & (np.abs(ky) < (2.0 / 3.0) * kmax) & (np.abs(kz) < (2.0 / 3.0) * kmax)).astype(np.float64)
    return kx, ky, kz, k2, mask


KX, KY, KZ, K2, DEALIAS = make_kgrid()
K2_SAFE = K2.copy()
K2_SAFE[0, 0, 0] = 1.0


def transverse_basis(k: tuple[int, int, int]) -> np.ndarray:
    vec = np.asarray(k, dtype=np.float64)
    khat = vec / np.linalg.norm(vec)
    axis = np.eye(3, dtype=np.float64)[int(np.argmin(np.abs(khat)))]
    first = np.cross(khat, axis)
    first /= np.linalg.norm(first)
    second = np.cross(khat, first)
    second /= np.linalg.norm(second)
    return np.column_stack((first, second))


def config_values(case: str) -> dict[str, Any]:
    for ident, cls, chi, chi_y, lam, d, nu, hyper, cs2, gated in CASES:
        if ident == case:
            if chi_y is None:
                if ident == "base_jordan":
                    chi_y = (chi + (1.0 + PHI) ** 2 * lam / RHO0) / PHI
                else:
                    chi_y = chi / PHI
            return {"id": ident, "class": cls, "chi": chi, "chi_yang": chi_y, "lambda": lam, "D": d, "nu": nu, "hyper_nu": hyper, "cs2": cs2, "gated": gated}
    raise ValueError(f"unknown case {case}")


def source_rhs(config: dict[str, Any], uhat: np.ndarray, eyhat: np.ndarray, eihat: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Reconstruct rhs exactly from spectral operations, without solver code."""
    u = np.asarray([np.fft.ifftn(uhat[d]).real for d in range(3)])
    ey = np.fft.ifftn(eyhat).real
    ei = np.fft.ifftn(eihat).real
    rho = ey + ei
    pi = ey - ei
    rhohat = np.fft.fftn(rho)
    rhohat = rhohat.copy()
    rhohat[0, 0, 0] = 0.0
    phihat = -rhohat / K2_SAFE

    def grad(fhat: np.ndarray) -> np.ndarray:
        return np.asarray([np.fft.ifftn(1j * q * fhat).real for q in (KX, KY, KZ)])

    grad_phi = grad(phihat)
    grad_rho = grad(rhohat)
    grad_u = np.asarray([[np.fft.ifftn(1j * q * uhat[d]).real for q in (KX, KY, KZ)] for d in range(3)])
    adv_u = np.asarray([sum(u[j] * grad_u[d, j] for j in range(3)) for d in range(3)])
    if config["class"] == "expanding":
        f2 = sum((pi * grad_phi[d]) ** 2 for d in range(3))
        sf = f2 / (f2 + 0.2 ** 2 + 1.0e-10)
        force = np.asarray([(sf * pi * grad_phi[d] - config["cs2"] * grad_rho[d]) for d in range(3)])
        a = 1.0
        hubble = 0.0
    else:
        force = np.asarray([pi * grad_phi[d] for d in range(3)])
        a = 1.0
        hubble = 0.0
    a2 = a * a
    k4 = K2 * K2
    rhs_u = np.asarray([(-np.fft.fftn(adv_u[d]) / a + np.fft.fftn(force[d]) - config["nu"] * K2 * uhat[d] / a2 - hubble * uhat[d] - config["hyper_nu"] * k4 * uhat[d] / (a2 * a2)) * DEALIAS for d in range(3)])
    div_rhs = KX * rhs_u[0] + KY * rhs_u[1] + KZ * rhs_u[2]
    rhs_u = np.asarray([rhs_u[d] - div_rhs * q / K2_SAFE for d, q in enumerate((KX, KY, KZ))])

    grad_ey = grad(eyhat)
    grad_ei = grad(eihat)
    adv_ey = sum(u[d] * grad_ey[d] for d in range(3))
    adv_ei = sum(u[d] * grad_ei[d] for d in range(3))
    lam = config["lambda"]
    imbalance = ey - PHI * ei
    conv = -lam * imbalance
    if config["class"] == "expanding" and config["gated"] and lam != 0.0:
        m_qi = (ey + ei) ** 2
        eps_sq = imbalance ** 2
        q = m_qi / (m_qi + PHI_INV2 + eps_sq + 1.0e-30)
        conv = -lam * (1.0 - q) * imbalance
    rhs_ey = (-np.fft.fftn(adv_ey) / a - config["D"] * K2 * eyhat / a2 - config["hyper_nu"] * k4 * eyhat / (a2 * a2) + np.fft.fftn(conv)) * DEALIAS
    rhs_ei = (-np.fft.fftn(adv_ei) / a - config["D"] * K2 * eihat / a2 - config["hyper_nu"] * k4 * eihat / (a2 * a2) - np.fft.fftn(conv)) * DEALIAS
    if config["class"] == "base" and config["chi"] != 0.0:
        chi_y = config["chi_yang"]
        flux_y = np.asarray([chi_y * ey * grad_phi[d] for d in range(3)])
        flux_i = np.asarray([-config["chi"] * ei * grad_phi[d] for d in range(3)])
        div_y = 1j * KX * np.fft.fftn(flux_y[0]) + 1j * KY * np.fft.fftn(flux_y[1]) + 1j * KZ * np.fft.fftn(flux_y[2])
        div_i = 1j * KX * np.fft.fftn(flux_i[0]) + 1j * KY * np.fft.fftn(flux_i[1]) + 1j * KZ * np.fft.fftn(flux_i[2])
        rhs_ey = (rhs_ey - div_y) * DEALIAS
        rhs_ei = (rhs_ei - div_i) * DEALIAS
    return rhs_u, rhs_ey, rhs_ei


def expected_matrix(config: dict[str, Any], kval: tuple[int, int, int], source_k: np.ndarray, mask: float) -> np.ndarray:
    n = 5 if kval == (0, 0, 0) else 4
    mat = np.zeros((n, n), dtype=np.complex128)
    if mask == 0.0:
        return mat
    k2 = float(np.dot(source_k, source_k))
    omega = float(np.dot(source_k, U))
    if config["class"] == "base":
        b = 1.0 if config["chi"] != 0.0 else 0.0
        s = b * RHO0 / (1.0 + PHI) * (config["chi"] - PHI * config["chi_yang"])
        B = b * PHI * RHO0 / (1.0 + PHI) * (config["chi"] + config["chi_yang"])
        gamma = (1.0 + PHI) * config["lambda"]
        block = np.diag((-config["D"] * k2 + s, -config["D"] * k2 - gamma, -config["nu"] * k2, -config["nu"] * k2)).astype(np.complex128)
        block[1, 0] = -B
    else:
        g0 = PHI_INV2 / (RHO0 * RHO0 + PHI_INV2) if config["gated"] else 1.0
        gamma = (1.0 + PHI) * config["lambda"] * g0
        h = config["hyper_nu"] * k2 * k2
        block = np.diag((-config["D"] * k2 - h, -config["D"] * k2 - h - gamma, -config["nu"] * k2 - h, -config["nu"] * k2 - h)).astype(np.complex128)
    block -= 1j * omega * np.eye(4)
    if n == 4:
        return block
    mat[:4, :4] = block
    mat[0, 0] = 0.0 if config["class"] == "base" else 0.0
    mat[1, 0] = 0.0
    mat[1, 1] = -((1.0 + PHI) * config["lambda"] * (PHI_INV2 / (RHO0 * RHO0 + PHI_INV2) if config["gated"] else 1.0) if config["class"] == "expanding" else (1.0 + PHI) * config["lambda"])
    mat[2:, :] = 0.0
    return mat


def reconstruct_responses(config: dict[str, Any], kval: tuple[int, int, int], amplitudes: np.ndarray, source_idx: tuple[int, int, int], basis: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    n = 5 if kval == (0, 0, 0) else 4
    responses = np.zeros((2, 2, n, n), dtype=np.complex128)
    ey0 = PHI * RHO0 / (1.0 + PHI)
    ei0 = RHO0 / (1.0 + PHI)
    iz, iy, ix = np.indices((N, N, N), dtype=np.float64)
    phase = 2.0 * math.pi * (kval[0] * ix + kval[1] * iy + kval[2] * iz) / N
    wave = np.cos(phase)
    for ai, amp in enumerate(amplitudes):
        for si, sign in enumerate((1.0, -1.0)):
            for col in range(n):
                drho = sign * amp * wave * (1.0 if col == 0 else 0.0)
                deps = sign * amp * wave * (1.0 if col == 1 else 0.0)
                dey = (PHI * drho + deps) / (1.0 + PHI)
                dei = (drho - deps) / (1.0 + PHI)
                ey = ey0 + dey
                ei = ei0 + dei
                u = np.broadcast_to(U[:, None, None, None], (3, N, N, N)).copy()
                if kval == (0, 0, 0):
                    if col >= 2:
                        u[col - 2] += sign * amp
                elif col >= 2:
                    u += sign * amp * basis[:, col - 2, None, None, None] * wave
                uhat = np.asarray([np.fft.fftn(u[d]) for d in range(3)])
                eyhat = np.fft.fftn(ey)
                eihat = np.fft.fftn(ei)
                ru, rey, rei = source_rhs(config, uhat, eyhat, eihat)
                coeff = np.asarray([rey[source_idx] + rei[source_idx], rey[source_idx] - PHI * rei[source_idx]], dtype=np.complex128)
                if kval == (0, 0, 0):
                    vel = np.asarray([ru[d][source_idx] for d in range(3)], dtype=np.complex128)
                else:
                    vel = basis.T @ np.asarray([ru[d][source_idx] for d in range(3)], dtype=np.complex128)
                value = np.concatenate((coeff, vel))
                if kval != (0, 0, 0):
                    value *= 2.0 / (N ** 3)
                else:
                    value /= N ** 3
                responses[ai, si, :, col] = value
    jacobians = np.asarray([(responses[i, 0] - responses[i, 1]) / (2.0 * amplitudes[i]) for i in range(2)])
    richardson = (4.0 * jacobians[1] - jacobians[0]) / 3.0
    return responses, jacobians, richardson


def trajectory_expected(dt: float) -> tuple[np.ndarray, np.ndarray]:
    # The source records the physical vector in (kx, ky, kz) order.
    k = np.asarray((1, 1, 0), dtype=np.float64)
    K = float(np.dot(k, k))
    omega = float(np.dot(k, U))
    gamma = (1.0 + PHI) * LAMBDA * (PHI_INV2 / (RHO0 * RHO0 + PHI_INV2))
    h = 0.0004 * K * K
    A = np.diag((-0.03 * K - h, -0.03 * K - h - gamma, -0.02 * K - h, -0.02 * K - h)).astype(np.complex128) - 1j * omega * np.eye(4)
    x0 = 1.0e-4 * np.asarray((1.0, 0.7, 0.3, -0.2), dtype=np.complex128)
    steps = int(round(10.0 / dt))
    discrete = np.linalg.matrix_power(np.eye(4, dtype=np.complex128) + dt * A + 0.5 * dt * dt * (A @ A), steps) @ x0
    continuous = expm(10.0 * A) @ x0
    return continuous, discrete


def algebra_certificates() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    def add(name: str, ok: bool, evidence: str) -> None:
        checks.append({"name": name, "passed": bool(ok), "evidence": evidence})
    transform = np.asarray([[PHI / (1 + PHI), 1 / (1 + PHI)], [1 / (1 + PHI), -1 / (1 + PHI)]])
    inverse = np.asarray([[1.0, 1.0], [1.0, -PHI]])
    add("population_transform", np.allclose(transform @ inverse, np.eye(2), atol=1e-13), "inverse population transformation")
    chi = 0.4
    cy = chi / PHI
    s = RHO0 / (1 + PHI) * (chi - PHI * cy)
    B = PHI * RHO0 / (1 + PHI) * (chi + cy)
    add("matched_mobility", abs(s) < 1e-13 and abs(B - RHO0 * chi) < 1e-13, "s=0 and B=rho0*chi")
    gamma = (1 + PHI) * LAMBDA
    scalar = np.asarray([[-0.03 * 2 + s, 0], [-B, -0.03 * 2 - gamma]])
    polynomial = np.asarray([1.0, -np.trace(scalar), np.linalg.det(scalar)])
    add("base_characteristic_polynomial", np.allclose(np.poly(scalar), polynomial, atol=1e-12), "scalar block polynomial")
    jordan = np.asarray([[-1.0, 0.0], [1.0, -1.0]])
    nilpotent = jordan + np.eye(2)
    add("jordan_nilpotent", np.linalg.norm(nilpotent @ nilpotent) < 1e-13 and np.linalg.norm(nilpotent) > 0, "nonzero square-zero nilpotent")
    A = np.asarray([[-0.7, 0.0, 0.0, 0.0], [-0.4, -1.1, 0.0, 0.0], [0, 0, -0.2, 0], [0, 0, 0, -0.2]], dtype=float)
    J = np.eye(4); J[0, 1] = 1.0
    transformed = J @ A @ np.linalg.inv(J)
    add("similarity", np.allclose(np.poly(transformed), np.poly(A), atol=1e-13), "J A J^-1 has identical characteristic polynomial")
    lift = np.vstack((np.eye(4), np.asarray((1.0, 2.0, 0.0, 0.0))))
    induced = lift @ A @ np.linalg.pinv(lift)
    add("injective_lift", np.linalg.matrix_rank(lift) == 4 and np.allclose(induced @ lift, lift @ A, atol=1e-13), "five-dimensional induced generator intertwines on image")
    add("density_closure", abs(A[0, 1]) < 1e-13, "density row has no imbalance input")
    add("imbalance_closure_failure", abs(A[1, 0]) > 0, "imbalance row is forced by density")
    k = np.asarray((1.0, 2.0, 3.0)); P = np.eye(3) - np.outer(k, k) / np.dot(k, k)
    add("projector_identity", np.linalg.norm(P @ k) < 1e-13 and np.allclose(P @ P, P, atol=1e-13), "transverse projector")
    expanding_diag = np.diag(np.asarray([-1.0, -2.0, -3.0, -3.0]))
    add("expanding_spectrum", np.allclose(np.sort(np.linalg.eigvals(expanding_diag)), np.asarray([-3.0, -3.0, -2.0, -1.0])), "diagonal spectrum")
    return checks


def required_array_keys() -> set[str]:
    return {"wavevector", "basis", "mask", "amplitudes", "responses", "jacobians", "richardson", "expected"}


def load_npz(path: Path, required: set[str]) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as archive:
        if set(archive.files) != required:
            raise ValueError(f"{path.name}: array key set mismatch")
        result = {key: np.asarray(archive[key]) for key in archive.files}
    for key, value in result.items():
        if not finite_array(value):
            raise ValueError(f"{path.name}: non-finite array {key}")
    return result


def verify_receipt(primary_dir: Path, note: Path, solver: Path) -> dict[str, Any]:
    if not note.is_file() or not solver.is_file():
        raise ValueError("missing note or canonical solver prerequisite")
    if hashlib.sha256(protocol_section(note)).hexdigest() != FROZEN_PROTOCOL_SHA256:
        raise ValueError("frozen protocol hash mismatch")
    solver_can = canonical_sha256(solver)
    if solver_can != SOLVER_CANONICAL_SHA256:
        raise ValueError("canonical solver hash mismatch")
    result_path = primary_dir / "results.json"
    if not result_path.is_file():
        raise ValueError("primary results.json is missing")
    receipt = strict_json(result_path)
    if not isinstance(receipt, dict) or receipt.get("schema") != PRIMARY_SCHEMA:
        raise ValueError("primary schema mismatch")
    provenance = receipt.get("provenance")
    files = receipt.get("files")
    rows = receipt.get("rows")
    trajectories = receipt.get("trajectories")
    algebra = receipt.get("algebra")
    if not isinstance(provenance, dict) or not isinstance(files, dict) or not isinstance(rows, list) or not isinstance(trajectories, list) or not isinstance(algebra, dict) or not isinstance(algebra.get("records"), list):
        raise ValueError("primary receipt missing required containers")
    if provenance.get("protocol_sha256") != FROZEN_PROTOCOL_SHA256 or provenance.get("solver_canonical_sha256") != SOLVER_CANONICAL_SHA256:
        raise ValueError("primary source identity mismatch")
    solver_digest = raw_sha256(solver)
    if provenance.get("solver_raw_sha256") != solver_digest:
        raise ValueError("primary solver raw hash mismatch")
    for snapshot in ("source_solver.py", "source_primary.py", "frozen_protocol.txt"):
        snapshot_path = primary_dir / snapshot
        if snapshot not in files or not snapshot_path.is_file() or raw_sha256(snapshot_path) != files[snapshot]:
            raise ValueError(f"missing or hash-mismatched source snapshot {snapshot}")
    if files.get("source_solver.py") != solver_digest:
        raise ValueError("source_solver.py snapshot hash mismatch")
    if files.get("frozen_protocol.txt") != hashlib.sha256(protocol_section(note)).hexdigest():
        raise ValueError("frozen_protocol.txt snapshot hash mismatch")
    if files.get("source_primary.py") != provenance.get("primary_raw_sha256"):
        raise ValueError("source_primary.py snapshot hash mismatch")
    if canonical_sha256(primary_dir / "source_primary.py") != provenance.get("primary_canonical_sha256"):
        raise ValueError("source_primary.py canonical hash mismatch")
    for key in ("primary_canonical_sha256", "primary_raw_sha256"):
        if not isinstance(provenance.get(key), str) or not re.fullmatch(r"[0-9a-f]{64}", provenance[key]):
            raise ValueError(f"invalid provenance hash {key}")
    for version_key in ("python", "numpy", "torch", "scipy"):
        if not isinstance(provenance.get(version_key), str) or not provenance[version_key]:
            raise ValueError(f"missing provenance version {version_key}")
    config = receipt.get("config")
    if not isinstance(config, dict):
        raise ValueError("primary configuration is missing")
    if config.get("N") != N or not close_scalar(config.get("L"), L) or config.get("rho0") != RHO0 or config.get("lambda") != LAMBDA or config.get("D") != 0.03 or config.get("nu") != NU or normalized_error(config.get("U"), U) > ROW_TOL or normalized_error(config.get("amplitudes"), AMPLITUDES) > ROW_TOL or config.get("wavevectors") != [list(k) for k in WAVEVECTORS]:
        raise ValueError("primary frozen scalar configuration mismatch")
    cases_config = config.get("cases")
    if not isinstance(cases_config, list) or len(cases_config) != len(CASES):
        raise ValueError("primary frozen case configuration mismatch")
    for expected_case, actual_case in zip(CASES, cases_config):
        expected = config_values(expected_case[0])
        if not isinstance(actual_case, dict) or actual_case.get("id") != expected_case[0] or actual_case.get("class") != expected_case[1].capitalize():
            raise ValueError("primary case identity mismatch")
        for key, value in (("chi", expected["chi"]), ("chi_yang", expected["chi_yang"]), ("lam", expected["lambda"]), ("D", expected["D"]), ("nu", expected["nu"])):
            if not close_scalar(actual_case.get(key), value, ROW_TOL):
                raise ValueError(f"primary case parameter mismatch: {expected_case[0]}:{key}")
        if expected_case[0].startswith("expanding_"):
            for key, value in (("hyper_nu", expected["hyper_nu"]), ("cs2", expected["cs2"])):
                if not close_scalar(actual_case.get(key), value, ROW_TOL):
                    raise ValueError(f"primary case parameter mismatch: {expected_case[0]}:{key}")
            if actual_case.get("qi_gate") is not expected["gated"]:
                raise ValueError(f"primary case parameter mismatch: {expected_case[0]}:qi_gate")
    expected_ids = {f"{case[0]}_k{k[0]}_{k[1]}_{k[2]}" for case in CASES for k in WAVEVECTORS}
    if len(rows) != len(expected_ids) or {row.get("id") for row in rows} != expected_ids:
        raise ValueError("primary Jacobian identifiers do not match frozen set")
    arrays: dict[str, dict[str, np.ndarray]] = {}
    for row in rows:
        filename = row.get("array")
        if not isinstance(filename, str) or Path(filename).name != filename or filename not in files:
            raise ValueError("missing or unsafe Jacobian array filename")
        array_path = primary_dir / filename
        if not array_path.is_file() or raw_sha256(array_path) != files[filename]:
            raise ValueError(f"missing or hash-mismatched array {filename}")
        arrays[filename] = load_npz(array_path, required_array_keys())
    for filename in ("trajectory_dt004.npz", "trajectory_dt002.npz", "trajectory_dt001.npz"):
        path = primary_dir / filename
        if filename not in files or not path.is_file() or raw_sha256(path) != files[filename]:
            raise ValueError(f"missing or hash-mismatched trajectory {filename}")
        with np.load(path, allow_pickle=False) as archive:
            required = {"dt", "times", "coordinates", "minima", "rho_mean", "scale_factor", "hubble", "expected_continuous", "expected_discrete"}
            if set(archive.files) != required:
                raise ValueError(f"{filename}: trajectory key set mismatch")
            arrays[filename] = {key: np.asarray(archive[key]) for key in archive.files}
            for key, value in arrays[filename].items():
                if not finite_array(value):
                    raise ValueError(f"{filename}: non-finite array {key}")
    return {"receipt": receipt, "provenance": provenance, "files": files,
            "rows": rows, "trajectories": trajectories, "arrays": arrays}


def check_scientific(data: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    rows_out: list[dict[str, Any]] = []
    failures: list[str] = []
    primary_algebra = data["receipt"]["algebra"]
    if primary_algebra.get("passed") is not True:
        failures.append("primary algebra aggregate marked failed")
    for record in primary_algebra.get("records", []):
        if isinstance(record, dict) and record.get("passed") is not True:
            failures.append(f"primary algebra:{record.get('name', 'unnamed')}")
    kx, ky, kz, k2, mask = KX, KY, KZ, K2, DEALIAS
    by_id = {row["id"]: row for row in data["rows"]}
    for ident, _cls, *_ in CASES:
        config = config_values(ident)
        for kval in WAVEVECTORS:
            rid = f"{ident}_k{kval[0]}_{kval[1]}_{kval[2]}"
            row = by_id[rid]
            filename = row["array"]
            arr = data["arrays"][filename]
            idx = (kval[2] % N, kval[1] % N, kval[0] % N)
            source_k = np.asarray((kx[idx], ky[idx], kz[idx]), dtype=np.float64)
            n = 5 if kval == (0, 0, 0) else 4
            basis = np.eye(3) if n == 5 else transverse_basis(source_k)
            expected = expected_matrix(config, kval, source_k, float(mask[idx]))
            responses, jac, rich = reconstruct_responses(config, kval, AMPLITUDES, idx, basis)
            reasons: list[str] = []
            if row.get("passed") is not True:
                reasons.append("primary row marked failed")
            if list(np.asarray(row.get("k", []), dtype=int)) != list(kval) or row.get("case") != ident:
                reasons.append("row metadata")
            if normalized_error(arr["wavevector"].reshape(-1), source_k) > 0.0:
                reasons.append("source wavevector")
            if arr["basis"].shape != basis.shape or normalized_error(arr["basis"], basis) > ROW_TOL:
                reasons.append("basis")
            if arr["mask"].size != 1 or not close_scalar(arr["mask"].item(), mask[idx], ROW_TOL):
                reasons.append("mask")
            if normalized_error(arr["amplitudes"], AMPLITUDES) > ROW_TOL:
                reasons.append("amplitudes")
            if normalized_error(arr["responses"], responses) > ROW_TOL:
                reasons.append("responses")
            if normalized_error(arr["jacobians"], jac) > ROW_TOL:
                reasons.append("jacobians")
            if normalized_error(arr["richardson"], rich) > ROW_TOL:
                reasons.append("richardson")
            if normalized_error(arr["expected"], expected) > ROW_TOL:
                reasons.append("expected matrix")
            fine_resid = normalized_error(arr["jacobians"][1], expected)
            rich_resid = normalized_error(arr["richardson"], expected)
            if not close_scalar(row.get("fine_residual"), fine_resid, ROW_TOL) or not close_scalar(row.get("richardson_residual"), rich_resid, ROW_TOL):
                reasons.append("reported residual")
            passed = not reasons and fine_resid <= 5.0e-6 and rich_resid <= 1.0e-8
            if not passed:
                failures.append(f"{rid}: " + ", ".join(reasons or ["matrix residual"]))
            rows_out.append({"id": rid, "case": ident, "k": list(kval), "array": filename, "fine_residual": fine_resid, "richardson_residual": rich_resid, "passed": passed, "reasons": reasons})

    traj_out: list[dict[str, Any]] = []
    trajectory_map = {row.get("array"): row for row in data["trajectories"]}
    if len(data["trajectories"]) != 3 or set(trajectory_map) != {"trajectory_dt004.npz", "trajectory_dt002.npz", "trajectory_dt001.npz"}:
        failures.append("trajectory identifiers do not match frozen set")
    continuous_errors: dict[str, float] = {}
    for filename, dt in (("trajectory_dt004.npz", 0.04), ("trajectory_dt002.npz", 0.02), ("trajectory_dt001.npz", 0.01)):
        arr = data["arrays"][filename]
        row = trajectory_map.get(filename, {})
        continuous, discrete = trajectory_expected(dt)
        reasons: list[str] = []
        if row.get("passed") is not True: reasons.append("primary trajectory marked failed")
        if arr["dt"].size != 1 or not close_scalar(arr["dt"].item(), dt): reasons.append("dt")
        times = arr["times"]
        steps = int(round(10.0 / dt))
        if times.shape != (steps + 1,) or normalized_error(times, np.linspace(0.0, 10.0, steps + 1)) > TRAJ_TOL: reasons.append("times")
        coords = arr["coordinates"]
        shape_ok = coords.shape == (2, steps + 1, 4)
        if not shape_ok: reasons.append("coordinates shape")
        else:
            x0 = 1.0e-4 * np.asarray((1.0, 0.7, 0.3, -0.2), dtype=np.complex128)
            if normalized_error(coords[:, 0, :], np.asarray((x0, -x0))) > TRAJ_TOL: reasons.append("initial coordinates")
        if normalized_error(arr["expected_continuous"], continuous) > TRAJ_TOL: reasons.append("continuous expected")
        if normalized_error(arr["expected_discrete"], discrete) > TRAJ_TOL: reasons.append("discrete expected")
        if arr["minima"].ndim != 3 or arr["minima"].shape != (2, steps + 1, 2): reasons.append("minima shape")
        if arr["rho_mean"].shape != (2, steps + 1) or arr["scale_factor"].shape != (2, steps + 1) or arr["hubble"].shape != (2, steps + 1): reasons.append("telemetry shape")
        if shape_ok:
            odd = (coords[0, -1] - coords[1, -1]) / 2.0
            err_c = trajectory_error(odd, continuous)
            err_d = trajectory_error(odd, discrete)
        else:
            err_c = math.inf
            err_d = math.inf
        continuous_errors[filename] = err_c
        minima = float(np.min(arr["minima"])) if arr["minima"].ndim == 3 else math.inf
        drift = float(np.max(np.abs(arr["rho_mean"] - RHO0) / RHO0))
        scale_err = float(np.max(np.abs(arr["scale_factor"] - 1.0)))
        max_hubble = float(np.max(np.abs(arr["hubble"])))
        if not (err_d <= 2.0e-4 and minima > 0.1 and drift <= 1.0e-10 and scale_err <= 1.0e-12 and max_hubble <= 1.0e-12): reasons.append("trajectory threshold")
        for key, actual in (("endpoint_continuous_error", err_c), ("endpoint_discrete_error", err_d), ("maximum_mean_relative_drift", drift), ("maximum_scale_error", scale_err), ("maximum_hubble", max_hubble)):
            if not close_scalar(row.get(key), actual, TRAJ_TOL): reasons.append(key)
        if not close_scalar(row.get("minima"), minima, TRAJ_TOL): reasons.append("reported minima")
        passed = not reasons
        traj_out.append({"dt": dt, "array": filename, "endpoint_continuous_error": err_c, "endpoint_discrete_error": err_d, "minima": minima, "maximum_mean_relative_drift": drift, "maximum_scale_error": scale_err, "maximum_hubble": max_hubble, "passed": passed, "reasons": reasons})
        if not passed: failures.append(f"{filename}: " + ", ".join(dict.fromkeys(reasons)))
    e0, e1, e2 = (continuous_errors["trajectory_dt004.npz"], continuous_errors["trajectory_dt002.npz"], continuous_errors["trajectory_dt001.npz"])
    ratio_values = [e0 / e1 if finite_number(e0) and finite_number(e1) and e1 != 0.0 else math.inf, e1 / e2 if finite_number(e1) and finite_number(e2) and e2 != 0.0 else math.inf]
    ratio_ok = all(3.5 <= ratio <= 4.5 for ratio in ratio_values)
    ratio_record = {"name": "trajectory_continuous_ratios", "ratios": ratio_values, "passed": ratio_ok, "evidence": "continuous endpoint error ratios under dt halving"}
    if not ratio_ok:
        failures.append("trajectory_continuous_ratios")
        for item in traj_out:
            item["passed"] = False
            item["reasons"].append("continuous-error ratio")
    algebra = algebra_certificates()
    algebra.append(ratio_record)
    failures.extend([f"algebra:{item['name']}" for item in algebra if not item["passed"]])
    return rows_out, traj_out, algebra, failures


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(safe(payload), ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Independently verify canonical excitation receipt")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--primary-dir", required=True)
    parser.add_argument("--note", default=str(DEFAULT_NOTE))
    parser.add_argument("--solver", default=str(DEFAULT_SOLVER))
    args = parser.parse_args(argv)
    output_dir = Path(args.output_dir).resolve()
    primary_dir = Path(args.primary_dir).resolve()
    base = {"schema": SCHEMA, "verdict": INCONCLUSIVE, "passed": False, "provenance": {}, "rows": [], "trajectories": [], "algebra": [], "files": {}}
    if output_dir.exists():
        print("output directory must be absent before invocation", file=sys.stderr)
        return 1
    try:
        data = verify_receipt(primary_dir, Path(args.note).resolve(), Path(args.solver).resolve())
        rows, trajectories, algebra, failures = check_scientific(data)
        provenance = {
            "protocol_sha256": FROZEN_PROTOCOL_SHA256,
            "solver_canonical_sha256": SOLVER_CANONICAL_SHA256,
            "solver_raw_sha256": data["provenance"].get("solver_raw_sha256"),
            "primary_canonical_sha256": data["provenance"].get("primary_canonical_sha256"),
            "primary_raw_sha256": data["provenance"].get("primary_raw_sha256"),
            "verifier_canonical_sha256": canonical_sha256(Path(__file__)),
            "verifier_raw_sha256": raw_sha256(Path(__file__)),
            "primary_receipt_raw_sha256": raw_sha256(primary_dir / "results.json"),
            "python": data["provenance"].get("python"),
            "numpy": data["provenance"].get("numpy"),
            "torch": data["provenance"].get("torch"),
            "scipy": data["provenance"].get("scipy"),
        }
        result = {**base, "provenance": provenance, "rows": rows, "trajectories": trajectories, "algebra": algebra, "files": {str(k): v for k, v in data["files"].items()}}
        result["passed"] = not failures
        result["verdict"] = VERDICT if result["passed"] else INCONCLUSIVE
        if failures: result["error"] = "; ".join(failures)
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "source_verifier.py").write_bytes(Path(__file__).read_bytes())
        write_json(output_dir / "results.json", result)
        return 0 if result["passed"] else 1
    except Exception as exc:
        base["error"] = str(exc)
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            write_json(output_dir / "results.json", base)
        except Exception as write_exc:
            print(f"{exc}; unable to write failure receipt: {write_exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
