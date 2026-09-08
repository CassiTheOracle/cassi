"""Independent finite-interval electric-support and Gauss-operator verifier.

This reconstruction is source-bound to PA8, PA11, PA14 and PA15 and to the
frozen schedule in §41.1 of ``matter-formation-continuum-report.md``.  It does
not import the primary calculation or any other project computation.  The
reported finite-interval spectrum is an operator/boundary identity witness,
not a three-dimensional particle solution or a matter-formation result.
"""
from __future__ import annotations

import json
import math
import sys
from typing import Any

import numpy as np
import sympy as sp
from scipy.spatial.transform import Rotation


# Frozen inputs from subsection 41.1.
PHI = (1.0 + math.sqrt(5.0)) / 2.0
RHO = 1.2
VQ = 0.9
GQ = 0.71
CPSI = 1.3
CPHI = 0.75
EPSX = 0.26
COS_BETA = PHI ** -3
SINSQ_BETA = 1.0 - COS_BETA * COS_BETA
AXIS = np.array([1.0, 2.0, -1.0], dtype=np.float64) / math.sqrt(6.0)
GRIDS = (15, 31, 63)
BOUNDARY_A0 = np.array([0.2, -0.1, 0.3], dtype=np.float64)
BOUNDARY_AR = np.zeros(3, dtype=np.float64)


# PA8 convention, retained literally in the derivation ledger:
# D_M Psi=(partial_M-i g_Q A_M^a T^a)Psi,
# (D_M Phi)^a=partial_M Phi^a+g_Q(A_M cross Phi)^a.


def _json_number(value: Any) -> Any:
    """Convert NumPy/SymPy containers to strict JSON-compatible primitives."""
    if isinstance(value, (np.floating, np.integer)):
        return float(value)
    if isinstance(value, np.ndarray):
        return [_json_number(item) for item in value.tolist()]
    if isinstance(value, dict):
        return {str(key): _json_number(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_number(item) for item in value]
    if isinstance(value, (sp.Integer, sp.Float, sp.Rational)):
        return float(value)
    return value


def _relative(a: float, b: float) -> float:
    return abs(float(a) - float(b)) / max(1.0, abs(float(b)))


def _finite_arrays(rows: list[dict[str, Any]], negative: list[dict[str, Any]]) -> bool:
    """Check every retained numerical array before strict JSON serialization."""
    keys = (
        "node_coordinates",
        "edge_rotations",
        "edge_angles",
        "profile_scale",
        "local_density",
        "local_adjoint_vectors",
        "local_mass_blocks",
        "physical_operator",
        "eigenspectrum",
        "stationarity_residual",
    )
    for row in rows:
        if any(not np.all(np.isfinite(np.asarray(row[key], dtype=np.float64))) for key in keys):
            return False
        control = row["boundary_control"]
        if any(
            not np.all(np.isfinite(np.asarray(control[key], dtype=np.float64)))
            for key in (
                "left_value",
                "right_value",
                "interior_solution",
                "full_node_solution",
                "stationarity_residual",
                "boundary_force",
            )
        ):
            return False
        if not all(
            np.isfinite(float(control[key]))
            for key in ("boundary_energy", "boundary_work", "boundary_identity_residual")
        ):
            return False
    for row in negative:
        if not np.all(np.isfinite(np.asarray(row["eigenspectrum"], dtype=np.float64))):
            return False
    return True


def _record(checks: dict[str, bool], name: str, value: bool) -> None:
    checks[name] = bool(value)


def _exact_text(value: Any) -> str:
    return str(sp.factor(sp.simplify(value)))


def _symbolic_derivation() -> dict[str, Any]:
    """Derive M, b, J_t and the complete-square identity independently.

    The spinor is sqrt(rho)*(cos(beta/2), sin(beta/2)) and the adjoint
    vacuum is v_Q e_3.  Thus its Pauli-vector expectation is
    rho*(sin(beta),0,cos(beta)).
    """
    rho, vq, g, cps, cpf, omega = sp.symbols(
        "rho v_Q g_Q C_Psi C_Phi omega", positive=True, real=True
    )
    cb, sb = sp.symbols("c_beta_half s_beta_half", real=True)
    c, s = sp.symbols("cos_beta sin_beta", real=True)
    a1, a2, a3 = sp.symbols("A_1 A_2 A_3", real=True)
    Avec = sp.Matrix([a1, a2, a3])
    I = sp.I
    sigma = [
        sp.Matrix([[0, 1], [1, 0]]),
        sp.Matrix([[0, -I], [I, 0]]),
        sp.Matrix([[1, 0], [0, -1]]),
    ]
    generators = [matrix / 2 for matrix in sigma]
    psi = sp.sqrt(rho) * sp.Matrix([cb, sb])
    phi = sp.Matrix([0, 0, vq])
    gauge_fundamental = sum(
        (Avec[index] * generators[index] for index in range(3)), sp.zeros(2)
    )
    # Relative equilibrium: D_t Psi=i(omega I-g A^a T^a)Psi;
    # D_t Phi=g A cross Phi.  The minus sign in PA15 is kept in q_Phi,
    # independently of the positive temporal energy used to form M.
    dpsi = I * (omega * sp.eye(2) - g * gauge_fundamental) * psi
    dphi = g * Avec.cross(phi)
    temporal_energy = sp.expand(
        cps * (sp.conjugate(dpsi).T * dpsi)[0] / 2
        + cpf * dphi.dot(dphi) / 2
    )
    # The symbols are real, so replace conjugates before simplification.
    temporal_energy = temporal_energy.xreplace(
        {sp.conjugate(z): z for z in (rho, vq, g, cps, cpf, omega, cb, sb, a1, a2, a3)}
    )
    temporal_energy = sp.expand(temporal_energy)
    substitutions = {cb**2: (1 + c) / 2, sb**2: (1 - c) / 2, cb * sb: s / 2}
    temporal_energy = sp.expand(temporal_energy.subs(substitutions))
    # Reapply the elementary trigonometric identities after expansion, since
    # products can occur in either order.
    temporal_energy = sp.expand(
        temporal_energy.subs({sb * cb: s / 2, cb * sb: s / 2})
    )
    matrix_m = sp.simplify(
        sp.hessian(temporal_energy, (a1, a2, a3)).subs(omega, 0)
    )
    gradient_at_zero = sp.Matrix(
        [sp.diff(temporal_energy, component).subs({a1: 0, a2: 0, a3: 0}) for component in (a1, a2, a3)]
    )
    b_vector = sp.simplify(-gradient_at_zero.subs(omega, 1))
    # Eliminate A at its stationary value and compare with the displayed J_t.
    astar = sp.simplify(matrix_m.inv() * b_vector * omega)
    reduced = sp.simplify(temporal_energy.subs({a1: astar[0], a2: astar[1], a3: astar[2]}))
    j_t = sp.simplify(2 * reduced / omega**2)
    displacement = sp.Matrix([a1, a2, a3]) - astar
    complete_square = sp.simplify(
        temporal_energy - reduced - (displacement.T * matrix_m * displacement)[0] / 2
    )
    displayed_j = 4 * cps * rho * cpf * vq**2 * s**2 / (cps * rho + 4 * cpf * vq**2)
    # The source expression follows PA15 directly for the adjoint component.
    qphi = sp.simplify(-cpf * g * phi.cross(dphi))
    return {
        "conventions": {
            "fundamental": "D_t Psi=partial_t Psi-i*g_Q*A_0^a*T^a*Psi",
            "adjoint": "D_t Phi=partial_t Phi+g_Q*A_0 cross Phi",
            "adjoint_source": "q_Phi=-C_Phi*g_Q*(Phi cross D_t Phi)",
            "electric_static_field": "F_ti=-D_i A_0 for static A_i and A_0",
        },
        "temporal_mass_matrix": _exact_text(matrix_m),
        "temporal_mass_matrix_expected": "g_Q**2*(C_Psi*rho/4*I + C_Phi*(|Phi|^2*I-Phi*Phi^T))",
        "common_rotation_source": _exact_text(b_vector),
        "common_rotation_source_expected": "g_Q*C_Psi*S/2",
        "adjoint_source_at_relative_equilibrium": _exact_text(qphi),
        "minimized_inertia": _exact_text(j_t),
        "minimized_inertia_expected": _exact_text(displayed_j),
        "inertia_residual": _exact_text(sp.expand(j_t - displayed_j).subs(c**2, 1-s**2)),
        "complete_square_residual": _exact_text(complete_square),
        "complete_square_remainder": "(A_0-M^{-1}b*omega)^T M (A_0-M^{-1}b*omega)/2",
        "symbolic_constraints": "c_beta_half^2+s_beta_half^2=1, 2*c_beta_half*s_beta_half=sin_beta, c_beta_half^2-s_beta_half^2=cos_beta",
        "elliptic_operator": "L_0=epsilon_x*D_i^dagger D_i+epsilon_s*D_s^dagger D_s+M = -epsilon_x*D_i D_i-epsilon_s*D_s D_s+M",
        "integration_by_parts_identity": "int[epsilon_x|D_i A_0|^2+epsilon_s|D_s A_0|^2+A_0^T M A_0]=0",
        "equality_case": (
            "Each term is nonnegative. With zero boundary work, equality gives covariantly "
            "constant A_0 and M A_0=0. The Dirichlet boundary condition fixes that covariant "
            "constant to zero. If both charged fields vanish in a bounded core, M may vanish "
            "there, but the positive edge form and the nonzero exterior mass region still force "
            "A_0=0 throughout; the core does not create a source-free electric mode."
        ),
    }


def _smoothstep_profile(x: np.ndarray) -> np.ndarray:
    s = np.clip((np.abs(x) - 0.25) / 0.25, 0.0, 1.0)
    return s**3 * (10.0 - 15.0 * s + 6.0 * s**2)


def _edge_rotations(x: np.ndarray) -> np.ndarray:
    """Use scipy Rotation.from_rotvec, not literal Rodrigues blocks."""
    midpoints = 0.5 * (x[:-1] + x[1:])
    angles = 0.11 * np.cos(np.pi * midpoints)
    return np.asarray(
        [Rotation.from_rotvec(AXIS * angle).as_matrix() for angle in angles],
        dtype=np.float64,
    )


def _incidence_matrix(rotations: np.ndarray) -> np.ndarray:
    """Explicit block edge incidence: (B a)_i=a_{i+1}-R_i a_i."""
    edge_count = rotations.shape[0]
    node_count = edge_count + 1
    incidence = np.zeros((3 * edge_count, 3 * node_count), dtype=np.float64)
    identity = np.eye(3, dtype=np.float64)
    for edge, rotation in enumerate(rotations):
        rows = slice(3 * edge, 3 * edge + 3)
        incidence[rows, 3 * edge : 3 * edge + 3] = -rotation
        incidence[rows, 3 * (edge + 1) : 3 * (edge + 1) + 3] = identity
    return incidence


def _local_mass_blocks(
    x_interior: np.ndarray, profile: str
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if profile == "uniform":
        scale = np.ones_like(x_interior)
    elif profile == "empty_core":
        scale = _smoothstep_profile(x_interior)
    else:
        raise ValueError(f"unknown profile {profile!r}")
    directions = np.column_stack(
        (
            np.sin(0.2 * np.sin(np.pi * x_interior)),
            np.zeros_like(x_interior),
            np.cos(0.2 * np.sin(np.pi * x_interior)),
        )
    )
    rho = RHO * scale
    phi = VQ * scale[:, None] * directions
    blocks = np.empty((x_interior.size, 3, 3), dtype=np.float64)
    for index in range(x_interior.size):
        p = phi[index]
        blocks[index] = GQ**2 * (
            (CPSI * rho[index] / 4.0 + CPHI * float(p @ p)) * np.eye(3)
            - CPHI * np.outer(p, p)
        )
    return scale, phi, blocks


def _mass_matrix(blocks: np.ndarray) -> np.ndarray:
    result = np.zeros((3 * blocks.shape[0], 3 * blocks.shape[0]), dtype=np.float64)
    for index, block in enumerate(blocks):
        result[3 * index : 3 * index + 3, 3 * index : 3 * index + 3] = block
    return result


def _energy_from_edges(
    full_state: np.ndarray,
    incidence: np.ndarray,
    mass_blocks: np.ndarray,
    h: float,
    epsilon: float,
) -> float:
    edge_difference = incidence @ full_state
    interior = full_state.reshape(-1, 3)[1:-1]
    mass_term = sum(float(vector @ block @ vector) for vector, block in zip(interior, mass_blocks))
    return float(epsilon * edge_difference.dot(edge_difference) / (2.0 * h) + h * mass_term / 2.0)


def _one_spectrum(n: int, profile: str) -> dict[str, Any]:
    h = 2.0 / (n + 1)
    coordinates = np.linspace(-1.0, 1.0, n + 2, dtype=np.float64)
    rotations = _edge_rotations(coordinates)
    incidence = _incidence_matrix(rotations)
    scale, phi, blocks = _local_mass_blocks(coordinates[1:-1], profile)
    mass = _mass_matrix(blocks)
    edge_stiffness = EPSX / h * (incidence.T @ incidence)
    full_stiffness = edge_stiffness.copy()
    interior_indices = np.arange(3, 3 * (n + 1), dtype=np.int64)
    full_stiffness[np.ix_(interior_indices, interior_indices)] += h * mass
    # This is h^{-1} nabla^2 E_h in the interior, with the local PA14 mass
    # blocks added to the Dirichlet edge operator.
    operator = full_stiffness[np.ix_(interior_indices, interior_indices)] / h
    eigenvalues = np.linalg.eigvalsh(operator)
    lower_bound = 4.0 * EPSX * h**-2 * math.sin(math.pi / (2.0 * (n + 1))) ** 2

    boundary_full = np.zeros(3 * (n + 2), dtype=np.float64)
    boundary_full[:3] = BOUNDARY_A0
    boundary_full[-3:] = BOUNDARY_AR
    kii = full_stiffness[np.ix_(interior_indices, interior_indices)]
    rhs = -full_stiffness[np.ix_(interior_indices, np.arange(3))] @ BOUNDARY_A0
    interior_solution = np.linalg.solve(kii, rhs)
    boundary_full[interior_indices] = interior_solution
    gradient = full_stiffness @ boundary_full
    boundary_force = gradient[:3]
    energy = _energy_from_edges(boundary_full, incidence, blocks, h, EPSX)
    boundary_work = float(BOUNDARY_A0 @ boundary_force)
    stationarity_residual = gradient[interior_indices]
    identity_residual = 2.0 * energy - boundary_work

    checks: dict[str, bool] = {}
    _record(checks, "operator_symmetric", np.allclose(operator, operator.T, rtol=0.0, atol=2e-13))
    _record(checks, "mass_blocks_positive_semidefinite", bool(np.min([np.min(np.linalg.eigvalsh(block)) for block in blocks]) >= -2e-13))
    _record(checks, "physical_spectrum_above_dirichlet_bound", bool(eigenvalues[0] >= lower_bound - 1e-10 * max(1.0, abs(lower_bound))))
    _record(checks, "dirichlet_lower_bound_positive", lower_bound > 0.0)
    _record(checks, "boundary_stationarity", _relative(float(np.linalg.norm(stationarity_residual)), 0.0) <= 1e-10)
    _record(checks, "boundary_work_positive", boundary_work > 0.0)
    _record(checks, "boundary_identity", _relative(2.0 * energy, boundary_work) <= 1e-10)
    _record(checks, "energy_positive", energy > 0.0)
    if profile == "empty_core":
        core = scale == 0.0
        _record(checks, "bounded_core_has_both_fields_zero", bool(np.any(core) and np.allclose(phi[core], 0.0)))
        _record(checks, "empty_core_still_has_positive_gap", eigenvalues[0] > 0.0)

    return {
        "N": n,
        "profile": profile,
        "h": h,
        "node_coordinates": coordinates,
        "edge_rotations": rotations,
        "incidence_matrix": incidence,
        "edge_angles": 0.11 * np.cos(np.pi * 0.5 * (coordinates[:-1] + coordinates[1:])),
        "profile_scale": scale,
        "local_density": RHO * scale,
        "local_adjoint_vectors": phi,
        "local_mass_blocks": blocks,
        "physical_operator": operator,
        "eigenspectrum": eigenvalues,
        "lowest_eigenvalue": float(eigenvalues[0]),
        "dirichlet_lower_bound": lower_bound,
        "boundary_control": {
            "left_value": BOUNDARY_A0,
            "right_value": BOUNDARY_AR,
            "interior_solution": interior_solution.reshape(n, 3),
            "full_node_solution": boundary_full.reshape(n + 2, 3),
            "stationarity_residual": stationarity_residual,
            "boundary_force": boundary_force,
            "boundary_energy": energy,
            "boundary_work": boundary_work,
            "boundary_identity_residual": identity_residual,
        },
        "boundary_energy": energy,
        "boundary_work": boundary_work,
        "stationarity_residual": stationarity_residual,
        "boundary_identity_residual": identity_residual,
        "checks": checks,
    }


def _negative_controls() -> list[dict[str, Any]]:
    controls: list[dict[str, Any]] = []
    for n in GRIDS:
        h = 2.0 / (n + 1)
        coordinates = np.linspace(-1.0, 1.0, n + 2, dtype=np.float64)
        rotations = _edge_rotations(coordinates)
        incidence = _incidence_matrix(rotations)
        _, _, blocks = _local_mass_blocks(coordinates[1:-1], "uniform")
        mass = _mass_matrix(blocks)
        epsilon = -EPSX
        stiffness = epsilon / h * (incidence.T @ incidence)
        interior = np.arange(3, 3 * (n + 1), dtype=np.int64)
        stiffness[np.ix_(interior, interior)] += h * mass
        operator = stiffness[np.ix_(interior, interior)] / h
        spectrum = np.linalg.eigvalsh(operator)
        checks = {"negative_lowest_eigenvalue": bool(spectrum[0] < 0.0)}
        controls.append(
            {
                "N": n,
                "profile": "uniform",
                "epsilon_x": epsilon,
                "eigenspectrum": spectrum,
                "lowest_eigenvalue": float(spectrum[0]),
                "checks": checks,
            }
        )
    return controls




def build_receipt() -> dict[str, Any]:
    derivation = _symbolic_derivation()
    physical = [_one_spectrum(n, profile) for n in GRIDS for profile in ("uniform", "empty_core")]
    negative = _negative_controls()
    comparison_rows = [
        {
            "N": row["N"],
            "profile": row["profile"],
            "lowest_eigenvalue": row["lowest_eigenvalue"],
            "dirichlet_lower_bound": row["dirichlet_lower_bound"],
            "boundary_energy": row["boundary_energy"],
            "boundary_work": row["boundary_work"],
            "stationarity_residual": float(np.linalg.norm(row["stationarity_residual"])),
            "boundary_identity_residual": row["boundary_identity_residual"],
        }
        for row in physical
    ]
    checks: dict[str, bool] = {}
    _record(checks, "symbolic_complete_square", derivation["complete_square_residual"] == "0")
    _record(checks, "symbolic_projected_inertia", derivation["inertia_residual"] == "0")
    _record(checks, "all_six_physical_rows", len(comparison_rows) == 6)
    _record(checks, "all_physical_checks", all(all(item["checks"].values()) for item in physical))
    _record(checks, "all_three_negative_controls", len(negative) == 3)
    _record(checks, "negative_controls_have_negative_modes", all(item["checks"]["negative_lowest_eigenvalue"] for item in negative))
    _record(checks, "finite_numeric_receipt", _finite_arrays(physical, negative))
    verdict = "PASS" if all(checks.values()) else "FAIL"
    return {
        "verdict": verdict,
        "checks": checks,
        "complete_physical_matter_formation": False,
        "scope": "conditional source-free stationary electric sector and finite-interval operator witness",
        "sources": {
            "action": "foundations/particle-stationary-action-closure.md PA8, PA11, PA14, PA15",
            "frozen_protocol": "computations/matter-formation-continuum-report.md §41.1",
        },
        "derivation": derivation,
        "comparison_rows": comparison_rows,
        "spectra": physical,
        "negative_electric_controls": negative,
        "excluded_cases": [
            "external charges",
            "imposed boundary voltage (the nonzero-voltage array is a deliberate witness outside isolated boundary conditions)",
            "thermal or finite-density reservoirs",
            "general time-dependent electric fields",
            "multifrequency solutions",
            "quantum bound states",
            "full three-dimensional particle solutions",
            "nonlinear formation or dispersal trajectories",
            "the separate common-number Gaussian calculation",
        ],
        "qualification": (
            "A PASS qualifies only the conditional temporal-support obstruction and the stated "
            "finite-interval operator/boundary identities; it is not a claim of completed matter formation."
        ),
    }


def main() -> int:
    try:
        receipt = _json_number(build_receipt())
        text = json.dumps(receipt, allow_nan=False, sort_keys=True, separators=(",", ":"))
        print(text)
        return 0 if receipt["verdict"] == "PASS" else 1
    except Exception as error:  # scientific failure is a nonzero executable result
        failure = {
            "verdict": "FAIL",
            "checks": {"execution_completed": False},
            "complete_physical_matter_formation": False,
            "error": f"{type(error).__name__}: {error}",
        }
        print(json.dumps(failure, allow_nan=False, sort_keys=True, separators=(",", ":")))
        return 1


if __name__ == "__main__":
    sys.exit(main())
