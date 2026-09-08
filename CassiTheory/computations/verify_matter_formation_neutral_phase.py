"""Independent common-phase projection and finite-k spectrum verifier.

Run from the repository root.  This file is deliberately source-bound: it
reconstructs the component quadratic from T^a=sigma^a/2 and the adjoint
cross-product derivative, and does not import the primary calculation.
"""
from __future__ import annotations

import json
import math
import sys
from typing import Any

import numpy as np
import sympy as sp


PHI = (1.0 + math.sqrt(5.0)) / 2.0
RHO = 1.2
KX = 0.83
MUX = 0.8
VQ = 0.9
CPSI = 1.3
CPHI = 0.7
EPSX = 0.6
GQ = 0.71
COS_BETA = PHI ** -3
K_SCHEDULE = (0.0, 0.01, 0.02, 0.04, 0.08)

# Source convention: D_M Psi=(partial_M-i g A_M^a T^a)Psi and
# (D_M Phi)^a=partial_M Phi^a+g (A_M cross Phi)^a (PA8).


def _json_number(x: Any) -> Any:
    if isinstance(x, (np.floating, np.integer)):
        return float(x)
    if isinstance(x, np.ndarray):
        return [_json_number(v) for v in x.tolist()]
    if isinstance(x, dict):
        return {str(k): _json_number(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_json_number(v) for v in x]
    return x


def _bool(checks: dict[str, bool], name: str, value: bool) -> None:
    checks[name] = bool(value)


def _relative(a: float, b: float) -> float:
    return abs(float(a) - float(b)) / max(1.0, abs(float(b)))


def _component_symbolics() -> dict[str, Any]:
    """Build all component derivatives and exact projection identities."""
    u, aa, dd, rr, vv, gg = sp.symbols("u a d rho v g", positive=True, real=True)
    c, s = sp.symbols("c s", real=True)
    A1, A2, A3 = sp.symbols("A1 A2 A3", real=True)
    Avec = sp.Matrix([A1, A2, A3])
    # Build the source component derivative literally from T^a=sigma^a/2.
    I2 = sp.I
    sigma_local = [
        sp.Matrix([[0, 1], [1, 0]]),
        sp.Matrix([[0, -I2], [I2, 0]]),
        sp.Matrix([[1, 0], [0, -1]]),
    ]
    T = [sig / 2 for sig in sigma_local]
    cb, sb = sp.symbols("cos_half_beta sin_half_beta", real=True)
    psi_real = sp.sqrt(rr) * sp.Matrix([cb, sb])
    gauge_matrix = sum((Avec[j] * T[j] for j in range(3)), sp.zeros(2))
    Dpsi = I2 * (u * sp.eye(2) - gg * gauge_matrix) * psi_real
    fundamental_raw = sp.expand((Dpsi.conjugate().T * Dpsi)[0])
    # Unit spinor and relative-sphere substitutions, applied only after the
    # matrix multiplication: cb^2+sb^2=1, 2 cb sb=s, cb^2-sb^2=c.
    fundamental = sp.expand(
        fundamental_raw.subs(cb**2, (1 + c) / 2)
        .subs(sb**2, (1 - c) / 2)
        .subs(cb * sb, s / 2)
    )
    adjoint_vector = gg * Avec.cross(sp.Matrix([0, 0, vv]))
    adjoint = sp.expand(adjoint_vector.dot(adjoint_vector))
    component = sp.expand(aa * fundamental / 2 + dd * adjoint / 2)
    H = sp.simplify(sp.hessian(component, (A1, A2, A3)))
    b = sp.simplify(sp.Matrix([sp.diff(component, A1), sp.diff(component, A2), sp.diff(component, A3)]).subs({A1: 0, A2: 0, A3: 0}))
    grad0 = sp.simplify(sp.Matrix([sp.diff(component, z) for z in (A1, A2, A3)]))
    H0 = sp.simplify(H.subs({A1: 0, A2: 0, A3: 0}))
    Astar = sp.simplify(-H0.inv() * b)
    projected = sp.simplify(component.subs({A1: Astar[0], A2: Astar[1], A3: Astar[2]}))
    J = sp.simplify(2 * projected / u**2)

    # Exact observable algebra, using independent symbols for conjugates.
    x, y, xb, yb = sp.symbols("x y xb yb")
    p1, p2, p3 = sp.symbols("p1 p2 p3", real=True)
    psi = sp.Matrix([x, y])
    psib = sp.Matrix([xb, yb])
    I2 = sp.I
    sigma = [sp.Matrix([[0, 1], [1, 0]]), sp.Matrix([[0, -I2], [I2, 0]]), sp.Matrix([[1, 0], [0, -1]])]
    eps = I2 * sigma[1]
    M = p1 * sigma[0] + p2 * sigma[1] + p3 * sigma[2]
    O = sp.expand((psi.T * eps * M * psi)[0])
    Ob = sp.expand((psib.T * eps * M.conjugate() * psib)[0])
    rho_expr = sp.expand((psib.T * psi)[0])
    S_expr = [sp.expand((psib.T * sig * psi)[0]) for sig in sigma]
    identity = sp.expand(Ob * O - rho_expr**2 * (p1**2 + p2**2 + p3**2) + (p1 * S_expr[0] + p2 * S_expr[1] + p3 * S_expr[2])**2)

    # Gauge-invariance infinitesimal check for each generator.  Adjoint action
    # is the one induced by U sigma(Phi) U^{-1}; delta Phi=-e_a cross Phi.
    theta = sp.symbols("theta", real=True)
    gauge_residuals = []
    for index, T in enumerate([sig / 2 for sig in sigma]):
        dpsi = I2 * T * psi
        e = sp.zeros(3, 1)
        e[index] = 1
        dphi = -e.cross(sp.Matrix([p1, p2, p3]))
        dM = sum((dphi[j] * sigma[j] for j in range(3)), sp.zeros(2))
        variation = sp.expand((dpsi.T * eps * M * psi)[0] + (psi.T * eps * dM * psi)[0] + (psi.T * eps * M * dpsi)[0])
        gauge_residuals.append(sp.simplify(variation))

    # The exact displacement cost is the Hessian quadratic at the stationary
    # point; retaining it makes positivity an algebraic, not fitted, check.
    d1, d2, d3 = sp.symbols("d1 d2 d3", real=True)
    delta = sp.Matrix([d1, d2, d3])
    displacement_cost = sp.simplify(
        component.subs({A1: Astar[0] + d1, A2: Astar[1] + d2, A3: Astar[2] + d3})
        - component.subs({A1: Astar[0], A2: Astar[1], A3: Astar[2]})
    )
    displacement_identity = sp.simplify(displacement_cost - (delta.T * H0 * delta)[0] / 2)

    return {
        "symbols": (u, aa, dd, rr, vv, gg, c, s, A1, A2, A3),
        "component": component,
        "H": H0,
        "b": b,
        "grad": grad0,
        "Astar": Astar,
        "projected": projected,
        "J": J,
        "displacement_cost": displacement_cost,
        "displacement_identity": displacement_identity,
        "observable": O,
        "observable_identity": sp.simplify(identity),
        "gauge_residuals": gauge_residuals,
    }


SYMS = _component_symbolics()
_U, _A, _D, _R, _V, _G, _C, _S, *_ = SYMS["symbols"]
_A1S, _A2S, _A3S = SYMS["symbols"][8:]
_H_FUNC = sp.lambdify((_A, _D, _R, _V, _G, _C, _S), SYMS["H"], "numpy")
_B_FUNC = sp.lambdify((_A, _D, _R, _V, _G, _C, _S, _U), SYMS["b"], "numpy")
_COMP_FUNC = sp.lambdify(
    (_U, _A, _D, _R, _V, _G, _C, _S, _A1S, _A2S, _A3S),
    SYMS["component"],
    "numpy",
)

def _gauss_symbolics() -> dict[str, Any]:
    """Differentiate the finite-k temporal Lagrangian before numerical Schur elimination."""
    p, u1, u3, v1, v3, kval, ex = sp.symbols("qdot u1 u3 adot1 adot3 k epsilon", real=True)
    expr = SYMS["component"].subs({_U: p, _A1S: u1, _A2S: 0, _A3S: u3})
    expr += ex * ((v1 + kval * u1) ** 2 + (v3 + kval * u3) ** 2) / 2
    equations = [sp.factor(sp.diff(expr, z)) for z in (u1, u3)]
    Hfull = sp.hessian(expr, (p, u1, u3, v1, v3))
    zidx, uidx = [0, 3, 4], [1, 2]
    Heff = sp.simplify(
        Hfull.extract(zidx, zidx)
        - Hfull.extract(zidx, uidx) * Hfull.extract(uidx, uidx).inv() * Hfull.extract(uidx, zidx)
    )
    stationary = sp.solve(equations, (u1, u3), dict=True)[0]
    residuals = [sp.factor(eq.subs(stationary)) for eq in equations]
    z = sp.Matrix([p, v1, v3])
    reduced_identity = sp.factor(expr.subs(stationary) - (z.T * Heff * z)[0] / 2)
    return {
        "equations": equations, "effective_hessian": Heff,
        "stationary_residuals": residuals, "reduced_identity": reduced_identity,
    }




def _component_numeric(a: float, d: float, cval: float, uval: float, Aval: np.ndarray) -> float:
    sval = math.sqrt(max(0.0, 1.0 - cval * cval))
    A = np.asarray(Aval, dtype=np.float64)
    return float(_COMP_FUNC(uval, a, d, RHO, VQ, GQ, cval, sval, A[0], A[1], A[2]))


def _component_gradient_numeric(a: float, d: float, cval: float, uval: float, Aval: np.ndarray) -> np.ndarray:
    sval = math.sqrt(max(0.0, 1.0 - cval * cval))
    H = np.asarray(_H_FUNC(a, d, RHO, VQ, GQ, cval, sval), dtype=np.float64)
    b = np.asarray(_B_FUNC(a, d, RHO, VQ, GQ, cval, sval, uval), dtype=np.float64).reshape(3)
    return H @ np.asarray(Aval, dtype=np.float64) + b


def _projection(a: float, d: float, cval: float) -> tuple[np.ndarray, float, np.ndarray]:
    sval = math.sqrt(max(0.0, 1.0 - cval * cval))
    H = np.asarray(_H_FUNC(a, d, RHO, VQ, GQ, cval, sval), dtype=np.float64)
    b = np.asarray(_B_FUNC(a, d, RHO, VQ, GQ, cval, sval, 1.0), dtype=np.float64).reshape(3)
    Astar = np.linalg.solve(H, -b)
    J = a * RHO - float(b @ np.linalg.solve(H, b))
    return H, float(J), Astar


def _temporal_matrices(k: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (K_eff, H_uu, full temporal Hessian) after Gauss elimination."""
    # w=(qdot,u1,u3,a1dot,a3dot), and electric field is adot+k*u.
    cval = COS_BETA
    sval = math.sqrt(1.0 - cval * cval)
    Hm = np.asarray(_H_FUNC(CPSI, CPHI, RHO, VQ, GQ, cval, sval), dtype=np.float64)
    bm = np.asarray(_B_FUNC(CPSI, CPHI, RHO, VQ, GQ, cval, sval, 1.0), dtype=np.float64).reshape(3)
    # Matter term: 1/2*Cpsi*rho*p^2 + bm*p.u + 1/2*u.Hm.u.
    full = np.zeros((5, 5), dtype=np.float64)
    full[0, 0] = CPSI * RHO
    full[0, 1:3] = bm[[0, 2]]
    full[1:3, 0] = bm[[0, 2]]
    full[1:3, 1:3] = Hm[np.ix_([0, 2], [0, 2])]
    # epsilon/2 sum_i (adot_i+k*u_i)^2
    for j in range(2):
        ui = 1 + j
        vi = 3 + j
        full[ui, ui] += EPSX * k * k
        full[vi, vi] += EPSX
        full[ui, vi] += EPSX * k
        full[vi, ui] += EPSX * k
    z = [0, 3, 4]
    uu = [1, 2]
    Hzz = full[np.ix_(z, z)]
    Hzu = full[np.ix_(z, uu)]
    Huu = full[np.ix_(uu, uu)]
    K = Hzz - Hzu @ np.linalg.solve(Huu, Hzu.T)
    return K, Huu, full


def _spatial_stiffness(k: float) -> np.ndarray:
    """Hessian of the component spatial quadratic in (q,a1,a3)."""
    cval = COS_BETA
    sval = math.sqrt(1.0 - cval * cval)
    Hm = np.asarray(_H_FUNC(KX, 1.0 / MUX, RHO, VQ, GQ, cval, sval), dtype=np.float64)
    bm = np.asarray(_B_FUNC(KX, 1.0 / MUX, RHO, VQ, GQ, cval, sval, 1.0), dtype=np.float64).reshape(3)
    B = np.zeros((3, 3), dtype=np.float64)
    # spatial phase derivative is -k*q; Ax amplitudes are a1,a3.
    B[0, 0] = KX * RHO * k * k
    B[0, 1:] = -k * bm[[0, 2]]
    B[1:, 0] = -k * bm[[0, 2]]
    B[1:, 1:] = Hm[np.ix_([0, 2], [0, 2])]
    return B




def _spectrum(k: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    K, _, _ = _temporal_matrices(k)
    V = _spatial_stiffness(k)
    L = np.linalg.cholesky(K)
    Linv = np.linalg.inv(L)
    reduced = Linv @ V @ Linv.T
    vals, vecs_y = np.linalg.eigh((reduced + reduced.T) / 2.0)
    vecs = np.linalg.solve(L.T, vecs_y)
    residuals = []
    for j in range(3):
        residuals.append(float(np.linalg.norm(V @ vecs[:, j] - vals[j] * (K @ vecs[:, j])) / max(1.0, np.linalg.norm(V @ vecs[:, j]))))
    return vals, vecs, np.asarray(residuals)


def _trajectory() -> list[dict[str, Any]]:
    k = 0.08
    K, _, _ = _temporal_matrices(k)
    V = _spatial_stiffness(k)
    L = np.linalg.cholesky(K)
    Linv = np.linalg.inv(L)
    red = Linv @ V @ Linv.T
    vals, vy = np.linalg.eigh((red + red.T) / 2.0)
    modes = np.linalg.solve(L.T, vy)
    x0 = np.array([1.0e-3, 0.0, 0.0], dtype=np.float64)
    coeff = modes.T @ K @ x0
    if not np.all(np.isfinite(vals)) or not np.all(vals > 0.0):
        raise ValueError("The declared finite-k normal-mode wave requires a positive spectrum")
    w = np.sqrt(vals)
    E0 = 0.5 * float(x0 @ V @ x0)
    rows: list[dict[str, Any]] = []
    for ti in range(33):
        t = float(ti)
        cs = np.cos(w * t)
        sn = np.sin(w * t)
        x = modes @ (coeff * cs)
        xd = modes @ (-coeff * w * sn)
        energy = 0.5 * float(xd @ K @ xd + x @ V @ x)
        rows.append({
            "time": ti,
            "coordinates": x,
            "velocities": xd,
            "relative_energy_error": abs(energy - E0) / max(abs(E0), np.finfo(float).tiny),
        })
    return rows


def main() -> int:
    checks: dict[str, bool] = {}
    diagnostics: dict[str, Any] = {}
    exact = {
        "observable": str(SYMS["observable"]),
        "observable_identity_residual": str(SYMS["observable_identity"]),
        "gauge_generator_residuals": [str(v) for v in SYMS["gauge_residuals"]],
    }
    _bool(checks, "observable_gauge_invariant", all(v == 0 for v in SYMS["gauge_residuals"]))
    _bool(checks, "observable_norm_identity", SYMS["observable_identity"] == 0)

    beta = math.acos(COS_BETA)
    psi = np.array([math.cos(beta / 2.0), math.sin(beta / 2.0)], dtype=np.complex128) * math.sqrt(RHO)
    epsmat = 1j * np.array([[0, -1j], [1j, 0]], dtype=np.complex128)
    sig3 = np.array([[1, 0], [0, -1]], dtype=np.complex128)
    O0 = psi.T @ epsmat @ (VQ * sig3) @ psi
    expected_abs = RHO * VQ * math.sin(beta)
    _bool(checks, "vacuum_observable", abs(abs(O0) - expected_abs) < 1e-13 and abs(O0.real + expected_abs) < 1e-13)
    exact["vacuum_observable"] = "O_N=-rho*v_Q*sin(beta)*exp(2 i Theta)"
    exact["relative_sphere"] = "S/rho=(sin(beta),0,cos(beta)); cos(beta)=phi^(-3)"
    exact["centre_identification"] = "Theta modulo pi; vartheta=arg(O_N) modulo 2 pi"

    u, aa, dd, rr, vv, gg, c, s, *_ = SYMS["symbols"]
    J = SYMS["J"]
    expected_J = sp.simplify(aa * rr * s**2 * (dd * vv**2) / (aa * rr / 4 + dd * vv**2))
    schur_residual = sp.factor((J - expected_J).subs(s**2, 1 - c**2))
    displacement_residual = SYMS["displacement_identity"]
    _bool(checks, "schur_complement_exact", schur_residual == 0)
    _bool(checks, "positive_displacement_cost_exact", displacement_residual == 0)
    aligned = sp.simplify(expected_J.subs(s, 0))
    rigid = sp.simplify(sp.limit(expected_J, dd, sp.oo))
    _bool(checks, "aligned_limit_exact", aligned == 0)
    _bool(checks, "rigid_adjoint_limit_exact", sp.simplify(rigid - aa * rr * s**2) == 0)
    exact["projected_temporal_or_spatial_coefficient"] = str(expected_J)
    exact["schur_residual"] = str(schur_residual)
    exact["displacement_cost"] = str(SYMS["displacement_cost"])
    exact["displacement_residual"] = str(displacement_residual)
    exact["aligned_limit"] = str(aligned)
    exact["rigid_adjoint_limit"] = str(rigid)

    gauss = _gauss_symbolics()
    _bool(checks, "gauss_stationarity_exact", all(
        residual == 0 for residual in gauss["stationary_residuals"]))
    _bool(checks, "gauss_elimination_exact", gauss["reduced_identity"] == 0)
    exact["gauss_equations"] = [str(eq) for eq in gauss["equations"]]
    exact["gauss_effective_hessian"] = str(gauss["effective_hessian"])
    exact["gauss_stationary_residuals"] = [str(v) for v in gauss["stationary_residuals"]]
    exact["gauss_reduced_identity"] = str(gauss["reduced_identity"])

    projection_rows = []
    projection_ok = True
    for cval in (COS_BETA, -0.7, 0.0, 0.8, -1.0, 1.0):
        for a, d, label in ((CPSI, CPHI, "time"), (KX, 1.0 / MUX, "space")):
            H, Jnum, Astar = _projection(a, d, cval)
            grad = _component_gradient_numeric(a, d, cval, 1.0, Astar)
            row: dict[str, Any] = {
                "cos_beta": cval,
                "sector": label,
                "J": Jnum,
                "stationarity_residual": np.linalg.norm(grad),
                "displacements": {},
            }
            projection_ok &= np.linalg.norm(grad) < 1e-12 and np.min(np.linalg.eigvalsh(H)) > 0.0
            for axis in range(3):
                for sign in (-1.0, 1.0):
                    disp = np.zeros(3)
                    disp[axis] = sign * 0.1
                    cost = _component_numeric(a, d, cval, 1.0, Astar + disp) - _component_numeric(a, d, cval, 1.0, Astar)
                    row["displacements"][f"axis{axis + 1}_{sign:+.0f}"] = cost
                    projection_ok &= cost > -1e-13
            projection_rows.append(row)
    _bool(checks, "component_projection_controls", projection_ok)
    diagnostics["component_projection"] = projection_rows

    spectra = []
    spectrum_ok = True
    residual_max = 0.0
    for kval in K_SCHEDULE:
        vals, vecs, residuals = _spectrum(kval)
        residual_max = max(residual_max, float(np.max(residuals)))
        spectrum_ok &= np.all(np.isfinite(vals)) and np.all(vals >= -1e-12) and float(np.max(residuals)) < 1e-10
        spectra.append({"k": kval, "omega_squared": vals})
    _bool(checks, "finite_k_spectra", spectrum_ok)
    _bool(checks, "generalized_eigenvector_residuals", residual_max < 1e-10)
    _bool(checks, "zero_frequency_at_k0", abs(float(spectra[0]["omega_squared"][0])) < 1e-12)
    _bool(checks, "positive_finite_k_spectrum", all(np.all(np.asarray(row["omega_squared"]) > 0.0) for row in spectra[1:]))
    diagnostics["max_generalized_residual"] = residual_max

    _, Jt, _ = _projection(CPSI, CPHI, COS_BETA)
    _, Jx, _ = _projection(KX, 1.0 / MUX, COS_BETA)
    sound = Jx / Jt
    ratio = float(spectra[1]["omega_squared"][0]) / K_SCHEDULE[1] ** 2
    _bool(checks, "sound_speed_limit", abs(ratio - sound) / abs(sound) < 1e-3)
    diagnostics["phase_coefficients"] = {
        "J_t": Jt,
        "J_x": Jx,
        "sound_speed_squared": sound,
        "vartheta_time": Jt / 4.0,
        "vartheta_space": Jx / 4.0,
    }
    diagnostics["finite_k_ratio_at_0.01"] = ratio

    wave = _trajectory()
    max_wave_error = max(float(row["relative_energy_error"]) for row in wave)
    _bool(checks, "normal_mode_wave_energy", max_wave_error < 1e-9)
    diagnostics["wave_max_relative_energy_error"] = max_wave_error

    verdict = "PASS" if all(checks.values()) else "FAIL"
    result = {
        "verdict": verdict,
        "checks": checks,
        "complete_physical_matter_formation": False,
        "source_conventions": "PA8 uses D_M Phi=partial_M Phi+g_Q A_M cross Phi and D_M Psi=partial_M Psi-i g_Q A_M^a T^a Psi.",
        "derivation": exact,
        "phase_coefficients": diagnostics["phase_coefficients"],
        "spectra": spectra,
        "wave": wave,
        "diagnostics": diagnostics,
    }
    print(json.dumps(_json_number(result), sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # scientific prerequisite failure is nonzero
        print(json.dumps({"verdict": "FAIL", "checks": {"execution": False}, "complete_physical_matter_formation": False, "error": f"{type(exc).__name__}: {exc}"}, separators=(",", ":")))
        raise
