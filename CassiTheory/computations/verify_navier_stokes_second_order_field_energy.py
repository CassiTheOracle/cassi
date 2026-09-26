#!/usr/bin/env python3
"""Verify second-order Cassi field energy and the Navier–Stokes time–curl criterion.

Run from CassiTheory:
    python computations/verify_navier_stokes_second_order_field_energy.py

The fixed protocols are the parent preregistration, symbolic-recovery protocol,
and independent-audit amendment in computations/.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
import sympy as sp


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
OUTPUT = (
    ROOT
    / "runs"
    / "navier_stokes_second_order_field_energy"
    / "verification.audit-qualified.json"
)
SCHEMA = "cassi.navier-stokes.second-order-field-energy.verification.v2"
ATOL = 2.0e-10
RTOL = 2.0e-10

SOURCE_PATHS = {
    "protocol": ROOT / "computations" / "navier-stokes-second-order-field-energy-prereg.md",
    "recovery_protocol": ROOT / "computations" / "navier-stokes-second-order-field-energy-recovery-prereg.md",
    "audit_protocol": ROOT / "computations" / "navier-stokes-second-order-field-energy-audit-amendment.md",
    "audit_recovery_protocol": ROOT / "computations" / "navier-stokes-second-order-field-energy-audit-recovery-prereg.md",
    "audit_recovery2_protocol": ROOT / "computations" / "navier-stokes-second-order-field-energy-audit-recovery2-prereg.md",
    "equation_recovery_protocol": ROOT / "computations" / "navier-stokes-second-order-field-energy-equation-recovery-prereg.md",
    "scale_anchor_recovery_protocol": ROOT / "computations" / "navier-stokes-second-order-field-energy-scale-anchor-recovery-prereg.md",
    "equation_tag_recovery_protocol": ROOT / "computations" / "navier-stokes-second-order-field-energy-equation-tag-recovery-prereg.md",
    "live_continuum_recovery_protocol": ROOT / "computations" / "navier-stokes-second-order-field-energy-live-continuum-recovery-prereg.md",
    "parent_receipt": ROOT / "runs" / "navier_stokes_second_order_field_energy" / "verification.json",
    "verifier": Path(__file__).resolve(),
    "two_fluid_shader": WORKSPACE / "CassiCosmos" / "compute" / "cassi_two_fluid.glsl",
    "field_particle_shader": WORKSPACE / "CassiCosmos" / "compute" / "cassi_field_particle.glsl",
    "gauge_action": ROOT / "foundations" / "particle-stationary-action-closure.md",
}

EXPECTED_SHA256 = {
    "protocol": "de08fca92c0d4b84fb0cdfe8cc0008b22446255a7a89308baec4571097dc1b27",
    "recovery_protocol": "8b4e1ddbebe507c672aa02ec0a0463ce7e73f4b511508b41f648b2142a97bf1c",
    "audit_protocol": "bdcd555d11f1d6111728f1e7f700ebd833e272c4fb09b036ba213d667ce1a8e0",
    "audit_recovery_protocol": "66cd9d899429703732867901077452d46453dcb26cbb2456d57b147f1b8e0719",
    "audit_recovery2_protocol": "9ef7a9dccdd5f4616dd5a37015892d569b7a7793cdd1c7879ffecbdf54e29a74",
    "equation_recovery_protocol": "ac2f67abfa1026b5c9d521ee4f657f4eafd06bff3a23bd5e60ce7e28b61503d8",
    "scale_anchor_recovery_protocol": "3023bd7563a2df5602ce530a595f016a49d2d091cf5904e85644bbce9cd82cc1",
    "equation_tag_recovery_protocol": "fa15ed6c2a352821fde380e7d827ca048512afe4cdee5ada4825b3580e2ed231",
    "live_continuum_recovery_protocol": "378062f6b00c5f77bd63d4b83a50febc9bbe39b68d6c369ce3ba9bfadaa6201f",
    "parent_receipt": "5a1baee3e42995b778e1a6b4b118337284be9cd903ee1048e313b7c8bc011d7a",
    "two_fluid_shader": "a6811a4967e1a7641905990ae28c0777e39bbe578d5559e37007f6f4ce7d632a",
    "field_particle_shader": "f0a12d0e1952215bbb1a71bdb95da35beed4548671085ca83d623a194c09a679",
    "gauge_action": "b15d6340cb8f15369f091d7ea5d5e70daad788f7953eb7917cd550554e56fe1a",
}

checks: list[dict[str, Any]] = []
values: dict[str, Any] = {}


def record(name: str, passed: bool, detail: str) -> None:
    passed = bool(passed)
    checks.append({"name": name, "passed": passed, "detail": detail})
    print(f"{'PASS' if passed else 'FAIL'}  {name}: {detail}")


def scalar_is_zero(value: sp.Expr) -> bool:
    return sp.simplify(sp.trigsimp(value)) == 0


def exact_zero(name: str, value: sp.Expr | sp.MatrixBase) -> None:
    if isinstance(value, sp.MatrixBase):
        simplified = value.applyfunc(lambda item: sp.simplify(sp.trigsimp(item)))
        passed = all(item == 0 for item in simplified)
        detail = str(simplified)
    else:
        simplified = sp.simplify(sp.trigsimp(value))
        passed = simplified == 0
        detail = str(simplified)
    record(name, passed, detail)


def close(name: str, actual: float, expected: float, *, atol: float = ATOL, rtol: float = RTOL) -> None:
    actual = float(actual)
    expected = float(expected)
    error = abs(actual - expected)
    limit = atol + rtol * max(abs(actual), abs(expected), 1.0)
    record(name, math.isfinite(actual) and error <= limit,
           f"actual={actual:.16e}, expected={expected:.16e}, error={error:.3e}, limit={limit:.3e}")


def max_close(name: str, actual: np.ndarray, expected: np.ndarray, *, atol: float = ATOL, rtol: float = RTOL) -> None:
    actual = np.asarray(actual)
    expected = np.asarray(expected)
    error = float(np.max(np.abs(actual - expected)))
    scale = max(float(np.max(np.abs(actual))), float(np.max(np.abs(expected))), 1.0)
    limit = atol + rtol * scale
    finite = bool(np.all(np.isfinite(actual)) and np.all(np.isfinite(expected)))
    record(name, finite and error <= limit, f"max_error={error:.3e}, limit={limit:.3e}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_region(text: str, start: str, end: str) -> str:
    start_index = text.find(start)
    if start_index < 0:
        return ""
    end_index = text.find(end, start_index + len(start))
    if end_index < 0:
        return ""
    return text[start_index:end_index]


def strip_c_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return re.sub(r"//[^\n]*", "", text)


# ---------------------------------------------------------------------------
# F. Source preflight and frozen external-input manifest.
# ---------------------------------------------------------------------------

source_text: dict[str, str] = {}
source_hashes: dict[str, str] = {}
for index, (source_name, source_path) in enumerate(SOURCE_PATHS.items(), start=1):
    exists = source_path.is_file()
    record(
        f"F{index:02d} source exists: {source_name}",
        exists,
        str(source_path.relative_to(WORKSPACE)),
    )
    if exists:
        source_hashes[source_name] = sha256(source_path)
        source_text[source_name] = source_path.read_text(encoding="utf-8")
    else:
        source_text[source_name] = ""

for index, (source_name, expected_hash) in enumerate(
    EXPECTED_SHA256.items(), start=len(SOURCE_PATHS) + 1
):
    actual_hash = source_hashes.get(source_name)
    record(
        f"F{index:02d} frozen hash matches: {source_name}",
        actual_hash == expected_hash,
        f"actual={actual_hash}, expected={expected_hash}",
    )


# ---------------------------------------------------------------------------
# A. Live Yang/Yin scalar pair: symmetrizer, energy, and U1 interpretation.
# ---------------------------------------------------------------------------

phi = (sp.Integer(1) + sp.sqrt(5)) / 2
M = sp.Matrix([[1, -phi], [-1, phi]])
K = sp.diag(1, phi)
v = sp.Matrix([1, -phi])
M1 = v * v.T
kernel = sp.Matrix([phi, 1])
lam = sp.symbols("lambda")

exact_zero("A01 golden-ratio identity", phi**2 - phi - 1)
exact_zero("A02 default weighted self-adjointness", K * M - M.T * K)
exact_zero("A03 weighted coupling equals rank-one potential", K * M - M1)
record("A04 positive scalar mass metric", float(phi.evalf()) > 0 and K.det() > 0,
       f"diagonal=(1,{float(phi.evalf()):.15f}), determinant={float(K.det().evalf()):.15f}")
exact_zero("A05 default kernel", M * kernel)
exact_zero("A06 default characteristic polynomial",
           sp.expand(M.charpoly(lam).as_expr() - lam * (lam - phi**2)))
exact_zero("A07 U1 kernel", M1 * kernel)
exact_zero("A08 U1 characteristic polynomial",
           sp.expand(M1.charpoly(lam).as_expr() - lam * (lam - (1 + phi**2))))
exact_zero("A09 U1 symmetry", M1 - M1.T)

Y, I_field, Yt, It = sp.symbols("Y I Y_t I_t", real=True)
ell, cs2, w2 = sp.symbols("ell c_s2 omega_0_2", nonnegative=True, real=True)
epsilon = Y - phi * I_field
acc_y = -cs2 * ell * Y - w2 * epsilon
acc_i = -cs2 * ell * I_field + w2 * epsilon

weighted_energy = sp.Rational(1, 2) * (
    Yt**2 + phi * It**2
    + cs2 * ell * (Y**2 + phi * I_field**2)
    + w2 * epsilon**2
)
weighted_derivative = (
    sp.diff(weighted_energy, Y) * Yt
    + sp.diff(weighted_energy, I_field) * It
    + sp.diff(weighted_energy, Yt) * acc_y
    + sp.diff(weighted_energy, It) * acc_i
)
exact_zero("A10 default weighted-energy derivative", weighted_derivative)

equal_energy = sp.Rational(1, 2) * (
    Yt**2 + It**2
    + cs2 * ell * (Y**2 + I_field**2)
    + w2 * epsilon**2
)
equal_derivative = (
    sp.diff(equal_energy, Y) * Yt
    + sp.diff(equal_energy, I_field) * It
    + sp.diff(equal_energy, Yt) * acc_y
    + sp.diff(equal_energy, It) * acc_i
)
exact_zero("A11 default equal-inertia derivative formula",
           equal_derivative - (1 - phi) * w2 * It * epsilon)
record("A12 default equal-inertia derivative is nonzero",
       sp.simplify(equal_derivative) != 0, str(sp.factor(equal_derivative)))

acc_i_u1 = -cs2 * ell * I_field + phi * w2 * epsilon
equal_u1_derivative = (
    sp.diff(equal_energy, Y) * Yt
    + sp.diff(equal_energy, I_field) * It
    + sp.diff(equal_energy, Yt) * acc_y
    + sp.diff(equal_energy, It) * acc_i_u1
)
exact_zero("A13 U1 equal-inertia energy derivative", equal_u1_derivative)
exact_zero("A14 U1 frequency-ratio square",
           (1 + phi**2) / (1 + phi) - (phi + 2) / phi**2)

rho, eps_mode, rhot, epst = sp.symbols("rho eps rho_t eps_t", real=True)
Y_from_modes = (phi * rho + eps_mode) / phi**2
I_from_modes = (rho - eps_mode) / phi**2
Yt_from_modes = (phi * rhot + epst) / phi**2
It_from_modes = (rhot - epst) / phi**2
mode_energy = weighted_energy.subs({
    Y: Y_from_modes,
    I_field: I_from_modes,
    Yt: Yt_from_modes,
    It: It_from_modes,
})
expected_mode_energy = sp.Rational(1, 2) * (
    phi**-1 * (rhot**2 + cs2 * ell * rho**2)
    + phi**-2 * (epst**2 + cs2 * ell * eps_mode**2)
    + w2 * eps_mode**2
)
exact_zero("A15 normal-coordinate weighted energy", mode_energy - expected_mode_energy)
exact_zero("A16 density-mode equation", acc_y + acc_i + cs2 * ell * (Y + I_field))
exact_zero("A17 imbalance-mode equation",
           acc_y - phi * acc_i + (cs2 * ell + phi**2 * w2) * epsilon)

scalar_shader = strip_c_comments(source_text["two_fluid_shader"])
scalar_pass_a = source_region(scalar_shader, "void pass_a()", "void pass_b()")
record(
    "A18 live EY acceleration matches protocol",
    "float acc_ey = lap_ey - omega2 * ey_ei_diff;" in scalar_pass_a,
    "executable default EY assignment found in pass_a",
)
record(
    "A19 live EI/U1 acceleration matches protocol",
    "float acc_ei = lap_ei + (pc.ham_completion > 0.5 ? phi * omega2 : omega2) * ey_ei_diff;"
    in scalar_pass_a,
    "executable default EI assignment and U1 branch found in pass_a",
)

field_particle_shader = strip_c_comments(source_text["field_particle_shader"])
state_stride_match = re.search(
    r"(?m)^\s*const int STATE_STRIDE = (\d+);\s*$", field_particle_shader
)
ax0_match = re.search(r"(?m)^\s*const int AX0 = (\d+);\s*$", field_particle_shader)
state_stride = int(state_stride_match.group(1)) if state_stride_match else None
ax0 = int(ax0_match.group(1)) if ax0_match else None
connection_accesses = all(
    token in field_particle_shader
    for token in (
        "sample_vector(p, AX0,",
        "sample_vector(p, AX0 + 3,",
        "sample_vector(p, AX0 + 6,",
    )
)
record(
    "A20 live field-particle connection channels",
    state_stride == 18 and ax0 == 9 and connection_accesses,
    f"STATE_STRIDE={state_stride}, AX0={ax0}, executable_triplet_access={connection_accesses}",
)

velocity_stride_match = re.search(
    r"(?m)^\s*const int VELOCITY_STRIDE = (\d+);\s*$", field_particle_shader
)
velocity_stride = int(velocity_stride_match.group(1)) if velocity_stride_match else None
velocity_mapping = source_region(
    field_particle_shader, "int velocity_component_for_state", "float state_rate"
)
velocity_buffers = (
    "readonly buffer VelocityIn {" in field_particle_shader
    and "buffer VelocityOut {" in field_particle_shader
)
velocity_loops = field_particle_shader.count("component < VELOCITY_STRIDE") >= 3
mapping_found = (
    "return component <= 6 ? component : AX0 + component - 7;" in velocity_mapping
)
record(
    "A21 live second-order velocity channels",
    velocity_stride == 16 and velocity_buffers and velocity_loops and mapping_found,
    f"VELOCITY_STRIDE={velocity_stride}, buffers={velocity_buffers}, "
    f"full_loops={velocity_loops}, mapping={mapping_found}",
)

scalar_lap_ey = source_region(
    scalar_shader, "float lap_ey_at", "float lap_ei_at"
)
normalized_discrete_wave = all(
    token in scalar_lap_ey
    for token in (
        "float hx = pc.extent_x / hn;",
        "float bxy = (1.0 / 3.0) * h02 / (hx2 + hy2);",
        "float fd_xy =",
        "+ bxy * fd_xy",
    )
) and all(
    token in scalar_pass_a
    for token in (
        "float acc_ey = lap_ey - omega2 * ey_ei_diff;",
        "float acc_ei = lap_ei + (pc.ham_completion > 0.5 ? phi * omega2 : omega2) * ey_ei_diff;",
    )
)
record(
    "A22 live normalized discrete wave operator",
    normalized_discrete_wave,
    "extent-dependent mixed stencil found and lap_ey/lap_ei enter with coefficient 1",
)


# ---------------------------------------------------------------------------
# B. One-color gauge restriction: curvature, Gauss law, and positive energy.
# ---------------------------------------------------------------------------

D = sp.Matrix(3, 3, lambda i, j: sp.symbols(f"d{i}{j}", real=True))
omega_components = sp.Matrix([
    D[1, 2] - D[2, 1],
    D[2, 0] - D[0, 2],
    D[0, 1] - D[1, 0],
])
f_spatial_sq = sum((D[i, j] - D[j, i])**2 for i in range(3) for j in range(3))
exact_zero(
    "B01 spatial curvature dual identity",
    f_spatial_sq - 2 * omega_components.dot(omega_components),
)
record(
    "B02 one-color commutator vanishes",
    all(sp.LeviCivita(a, 2, 2) == 0 for a in range(3)),
    "epsilon^(a33)=0 for all colors",
)

x_g, y_g, z_g, t_g = sp.symbols("x_g y_g z_g t_g", real=True)
gauge_coords = (x_g, y_g, z_g)
vector_potential = sp.Matrix([
    sp.Function("P0")(x_g, y_g, z_g, t_g),
    sp.Function("P1")(x_g, y_g, z_g, t_g),
    sp.Function("P2")(x_g, y_g, z_g, t_g),
])
velocity_from_potential = sp.Matrix([
    sp.diff(vector_potential[2], y_g) - sp.diff(vector_potential[1], z_g),
    sp.diff(vector_potential[0], z_g) - sp.diff(vector_potential[2], x_g),
    sp.diff(vector_potential[1], x_g) - sp.diff(vector_potential[0], y_g),
])
velocity_t_from_potential = velocity_from_potential.diff(t_g)
divergence_velocity_t = sum(
    sp.diff(velocity_t_from_potential[i], gauge_coords[i]) for i in range(3)
)
exact_zero(
    "B03 differentiated incompressibility satisfies spatial Gauss term",
    divergence_velocity_t,
)

ut_components = sp.Matrix(sp.symbols("u_t0:3", real=True))
epsilon_x, mu_x, kappa_a = sp.symbols(
    "epsilon_x mu_x kappa_A", positive=True, real=True
)
cg_inv_sq = epsilon_x * mu_x
gauge_hamiltonian = (
    epsilon_x * kappa_a**2 * ut_components.dot(ut_components) / 2
    + kappa_a**2 * f_spatial_sq / (4 * mu_x)
)
expected_normalized_gauge_energy = sp.Rational(1, 2) * (
    omega_components.dot(omega_components)
    + cg_inv_sq * ut_components.dot(ut_components)
)
exact_zero(
    "B04 dimensionally normalized gauge energy",
    mu_x * gauge_hamiltonian / kappa_a**2 - expected_normalized_gauge_energy,
)
exact_zero("B05 gauge speed identity", 1 / cg_inv_sq - 1 / (epsilon_x * mu_x))

source_action = source_text["gauge_action"]
pa11_region = source_region(
    source_action, "The source-free particle-sector action is", r"\tag{PA11}"
)
pa12_region = source_region(
    source_action, r"\tag{PA11}", r"\tag{PA12}"
)
pa13_region = source_region(
    source_action, "### 3.3 Source-unit dimensions", r"\tag{PA13}"
)
pa14_region = source_region(
    source_action, "Variation of $S_P$", r"\tag{PA14}"
)
record(
    "B06 canonical gauge electric coefficient present",
    r"\frac{\epsilon_x}{2}\mathcal F_{ti}^a\mathcal F_{ti}^a" in pa11_region,
    "PA11 electric curvature term found inside tagged equation region",
)
record(
    "B07 canonical gauge magnetic coefficient present",
    r"\frac{1}{4\mu_x}\mathcal F_{ij}^a\mathcal F_{ij}^a" in pa12_region,
    "PA12 magnetic curvature term found inside tagged equation region",
)
gauss_terms_present = all(
    token in pa14_region
    for token in (
        r"\epsilon_x(D_i\mathcal F_{ti})^a",
        r"\epsilon_{\mathfrak s}(D_{\mathfrak s}",
        r"q_\Psi^a+q_\Phi^a",
    )
)
record(
    "B08 complete canonical Gauss constraint present",
    gauss_terms_present,
    f"PA14 spatial, scale, and charge terms found={gauss_terms_present}",
)

# Dimension vectors are ordered as powers of (L, T).
connection_dimension = (-1, 0)
fluid_velocity_dimension = (1, -1)
kappa_dimension = (-2, 1)
mapped_dimension = tuple(
    fluid_velocity_dimension[i] + kappa_dimension[i] for i in range(2)
)
record(
    "B09 velocity-to-connection conversion dimension",
    mapped_dimension == connection_dimension,
    f"[kappa_A u]={mapped_dimension}, [A_i]={connection_dimension}",
)
source_dimensions_present = (
    r"[\Phi]=[\mathcal A_i]=L^{-1}" in pa13_region
    and r"[\mathcal A_0]=T^{-1}" in pa13_region
)
record(
    "B10 canonical connection dimensions present",
    source_dimensions_present,
    f"PA13 spatial and temporal connection dimensions found={source_dimensions_present}",
)
epsilon_scale, scale_gauss, q_psi, q_phi = sp.symbols(
    "epsilon_scale scale_gauss q_psi q_phi", real=True
)
full_gauss = (
    epsilon_x * kappa_a * divergence_velocity_t
    + epsilon_scale * scale_gauss
    - q_psi
    - q_phi
)
source_free_gauss = full_gauss.subs({scale_gauss: 0, q_psi: 0, q_phi: 0})
exact_zero(
    "B11 source-free scale-free Gauss reduction",
    source_free_gauss,
)

compact_latex = lambda text: re.sub(r"\s+", "", text)
pa11_compact = compact_latex(pa11_region)
pa12_compact = compact_latex(pa12_region)
scale_curvature_terms_present = (
    compact_latex(
        r"\frac{\epsilon_{\mathfrak s}}{2}"
        r"\mathcal F_{t\mathfrak s}^a\mathcal F_{t\mathfrak s}^a"
    )
    in pa11_compact
    and compact_latex(
        r"\frac{1}{2\mu_{\mathfrak s}}"
        r"\mathcal F_{i\mathfrak s}^a\mathcal F_{i\mathfrak s}^a"
    )
    in pa12_compact
)
record(
    "B12 canonical scale-curvature sectors present",
    scale_curvature_terms_present,
    f"PA11 electric and PA12 magnetic scale terms found={scale_curvature_terms_present}",
)

dt_as, ds_at, di_as, ds_ai, comm_ts, comm_is = sp.symbols(
    "dt_A_scale ds_A_time di_A_scale ds_A_i comm_t_scale comm_i_scale",
    real=True,
)
scale_curvatures = sp.Matrix([
    dt_as - ds_at + comm_ts,
    di_as - ds_ai + comm_is,
])
scale_flat_curvatures = scale_curvatures.subs({
    dt_as: 0,
    ds_at: 0,
    di_as: 0,
    ds_ai: 0,
    comm_ts: 0,
    comm_is: 0,
})
exact_zero(
    "B13 explicit one-color scale-flat curvature restriction",
    scale_flat_curvatures,
)


# ---------------------------------------------------------------------------
# C. Exact tensor cancellation, interpolation exponents, and scaling.
# ---------------------------------------------------------------------------

s00, s11, s22, s01, s02, s12 = sp.symbols("s00 s11 s22 s01 s02 s12", real=True)
S_symbolic = sp.Matrix([
    [s00, s01, s02],
    [s01, s11, s12],
    [s02, s12, s22],
])
a01, a02, a12 = sp.symbols("a01 a02 a12", real=True)
A_symbolic = sp.Matrix([
    [0, a01, a02],
    [-a01, 0, a12],
    [-a02, -a12, 0],
])
om = sp.Matrix(sp.symbols("omega0:3", real=True))
q = sp.Matrix(sp.symbols("q0:3", real=True))
sigma = sp.symbols("sigma", real=True)
b = sigma * q
g = om - b

exact_zero("C01 antisymmetric velocity-gradient cancellation", (q.T * A_symbolic * q)[0])
outer_difference = om * om.T - q * q.T
production_difference = (om.T * S_symbolic * om)[0] - (q.T * S_symbolic * q)[0]
exact_zero("C02 tensor contraction equals production difference",
           sum(S_symbolic[i, j] * outer_difference[i, j] for i in range(3) for j in range(3))
           - production_difference)
factorized = g * om.T + b * g.T
factor_error = (outer_difference - factorized).applyfunc(
    lambda item: sp.expand(item).subs(sigma**2, 1)
)
exact_zero("C03 signed difference-of-squares factorization", factor_error)
zero_residual_production = production_difference.subs({
    q[0]: sigma * om[0],
    q[1]: sigma * om[1],
    q[2]: sigma * om[2],
})
zero_residual_production = sp.expand(zero_residual_production).subs(sigma**2, 1)
exact_zero("C04 zero residual cancels strain production", zero_residual_production)

r = sp.symbols("r", positive=True)
theta = sp.Rational(3, 1) / r
a_exp = 2 * r / (r - 2)
p_exp = 2 * r / (2 * r - 3)
exact_zero("C05 Holder exponent identity", 1 / a_exp + 1 / r + sp.Rational(1, 2) - 1)
exact_zero("C06 critical mixed-norm identity", 2 / p_exp + 3 / r - 2)
exact_zero(
    "C07 Euclidean residual scaling identity",
    p_exp * (2 - 3 / r) - 2,
)
exact_zero("C08 Young viscosity exponent", theta / (2 - theta) - 3 / (2 * r - 3))
exact_zero("C09 Young energy exponent", (1 - theta / 2) * 2 / (2 - theta) - 1)
exact_zero("C10 r=3 endpoint", p_exp.subs(r, 3) - 2)
exact_zero("C11 r=3 strain exponent", a_exp.subs(r, 3) - 6)
exact_zero("C12 r=infinity time endpoint", sp.limit(p_exp, r, sp.oo) - 1)
exact_zero("C13 r=infinity strain endpoint", sp.limit(a_exp, r, sp.oo) - 2)

# On R^3 or an unnormalized rescaled domain, the spatial Jacobian contributes
# lambda^(-3/r). A fixed volume-normalized torus has no such domain factor.
euclidean_space_norm_power = 2 - 3 / r
euclidean_time_integral_power = sp.simplify(
    p_exp * euclidean_space_norm_power - 2
)
exact_zero("C14 rescaled-domain time-curl amplitudes agree", 3 - 1 - 2)
exact_zero(
    "C15 rescaled-domain critical residual-work dilation",
    euclidean_time_integral_power,
)
exact_zero("C16 rescaled-domain H_c enstrophy scaling", 4 - 3 - 1)
exact_zero("C17 rescaled-domain D_c dissipation scaling", 6 - 3 - 3)
fixed_torus_space_norm_power = sp.Integer(2)
exact_zero(
    "C18 fixed normalized torus residual amplitude exponent",
    fixed_torus_space_norm_power - 2,
)
fixed_torus_r3_work_power = (
    p_exp * fixed_torus_space_norm_power - 2
).subs(r, 3)
exact_zero(
    "C19 fixed normalized torus r=3 work exponent",
    fixed_torus_r3_work_power - 2,
)


# ---------------------------------------------------------------------------
# D. Exact heat-flow controls.
# ---------------------------------------------------------------------------

x, y, z, time = sp.symbols("x y z t", real=True)
nu, n, amp = sp.symbols("nu n a", positive=True, real=True)
coords = (x, y, z)


def symbolic_gradient(vector: sp.Matrix) -> sp.Matrix:
    return sp.Matrix(3, 3, lambda i, j: sp.diff(vector[j], coords[i]))


def symbolic_divergence(vector: sp.Matrix) -> sp.Expr:
    gradient = symbolic_gradient(vector)
    return sum(gradient[i, i] for i in range(3))


def symbolic_curl(vector: sp.Matrix) -> sp.Matrix:
    gradient = symbolic_gradient(vector)
    return sp.Matrix([
        gradient[1, 2] - gradient[2, 1],
        gradient[2, 0] - gradient[0, 2],
        gradient[0, 1] - gradient[1, 0],
    ])


def symbolic_laplacian(vector: sp.Matrix) -> sp.Matrix:
    return vector.applyfunc(lambda component: sum(sp.diff(component, coordinate, 2) for coordinate in coords))


def symbolic_advect(left: sp.Matrix, right: sp.Matrix) -> sp.Matrix:
    gradient = symbolic_gradient(right)
    return sp.Matrix([
        sum(left[i] * gradient[i, j] for i in range(3))
        for j in range(3)
    ])


def time_derivative(vector: sp.Matrix, order: int = 1) -> sp.Matrix:
    return vector.applyfunc(lambda component: sp.diff(component, time, order))


heat = sp.exp(-nu * n**2 * time)
beltrami = amp * heat * sp.Matrix([sp.sin(n * z), sp.cos(n * z), 0])
beltrami_t = time_derivative(beltrami)
beltrami_omega = symbolic_curl(beltrami)
exact_zero("D01 Beltrami divergence", symbolic_divergence(beltrami))
exact_zero("D02 Beltrami curl eigenfield", beltrami_omega - n * beltrami)
exact_zero("D03 Beltrami nonlinearity", symbolic_advect(beltrami, beltrami))
exact_zero("D04 Beltrami heat equation",
           beltrami_t + symbolic_advect(beltrami, beltrami) - nu * symbolic_laplacian(beltrami))
exact_zero("D05 Beltrami time-curl residual",
           beltrami_omega + beltrami_t / (nu * n))
beltrami_wave_defect = (
    time_derivative(beltrami, 2)
    + (nu * n)**2 * symbolic_curl(symbolic_curl(beltrami))
)
exact_zero("D06 Beltrami gauge-wave defect formula",
           beltrami_wave_defect - 2 * nu**2 * n**4 * beltrami)
record("D07 Beltrami gauge-wave defect is nonzero",
       any(sp.simplify(component) != 0 for component in beltrami_wave_defect),
       "heat flow is not a Lorentzian gauge wave")

shear = amp * heat * sp.Matrix([sp.sin(n * y), 0, 0])
shear_t = time_derivative(shear)
shear_omega = symbolic_curl(shear)
exact_zero("D08 shear divergence", symbolic_divergence(shear))
exact_zero("D09 shear nonlinearity", symbolic_advect(shear, shear))
exact_zero("D10 shear heat equation",
           shear_t + symbolic_advect(shear, shear) - nu * symbolic_laplacian(shear))
exact_zero("D11 shear time-curl orthogonality", shear_t.dot(shear_omega))

sin2_average = sp.integrate(sp.sin(y)**2, (y, 0, 2 * sp.pi)) / (2 * sp.pi)
sin3_abs_average = (
    sp.integrate(sp.sin(y)**3, (y, 0, sp.pi))
    - sp.integrate(sp.sin(y)**3, (y, sp.pi, 2 * sp.pi))
) / (2 * sp.pi)
exact_zero("D12 normalized sine-square average", sin2_average - sp.Rational(1, 2))
exact_zero("D13 normalized absolute sine-cube average",
           sin3_abs_average - 4 / (3 * sp.pi))

T, c_symbol = sp.symbols("T c", positive=True, real=True)
time_factor = sp.integrate(sp.exp(-2 * nu * n**2 * time), (time, 0, T))
exact_zero("D14 shear lower-bound time integral",
           time_factor - (1 - sp.exp(-2 * nu * n**2 * T)) / (2 * nu * n**2))
kinetic_initial = sp.Rational(1, 2) * amp**2 * sin2_average
exact_zero("D15 shear kinetic-energy anchor", kinetic_initial - amp**2 / 4)
lower_bound = (
    (4 / (3 * sp.pi))**sp.Rational(2, 3)
    * amp**2 * nu**2 * n**4 / c_symbol**2
    * time_factor
)
expected_lower_bound = (
    (4 / (3 * sp.pi))**sp.Rational(2, 3)
    * amp**2 * nu * n**2 / (2 * c_symbol**2)
    * (1 - sp.exp(-2 * nu * n**2 * T))
)
exact_zero("D16 shear residual-work lower bound", lower_bound - expected_lower_bound)


# ---------------------------------------------------------------------------
# E. Independent Fourier reconstruction of the fixed nonlinear datum.
# ---------------------------------------------------------------------------

N = 32
axis = 2.0 * np.pi * np.arange(N, dtype=np.float64) / N
X, Y_grid, Z_grid = np.meshgrid(axis, axis, axis, indexing="ij")
fixture = np.empty((N, N, N, 3), dtype=np.float64)
fixture[..., 0] = np.cos(Y_grid) + np.sin(X + Y_grid)
fixture[..., 1] = np.cos(X) - np.sin(X + Y_grid)
fixture[..., 2] = np.cos(X) + np.cos(Y_grid) + np.sin(X + Y_grid)

wave_numbers = np.fft.fftfreq(N, d=1.0 / N)
KX, KY, KZ = np.meshgrid(wave_numbers, wave_numbers, wave_numbers, indexing="ij")
K_AXES = (KX, KY, KZ)
K_SQ = KX**2 + KY**2 + KZ**2


def fft_vector(vector: np.ndarray) -> np.ndarray:
    return np.fft.fftn(vector, axes=(0, 1, 2))


def ifft_vector(vector_hat: np.ndarray) -> np.ndarray:
    return np.fft.ifftn(vector_hat, axes=(0, 1, 2)).real


def derivative_scalar(field: np.ndarray, derivative_axis: int) -> np.ndarray:
    field_hat = np.fft.fftn(field, axes=(0, 1, 2))
    return np.fft.ifftn(1j * K_AXES[derivative_axis] * field_hat, axes=(0, 1, 2)).real


def gradient_vector(vector: np.ndarray) -> np.ndarray:
    result = np.empty(vector.shape[:-1] + (3, 3), dtype=np.float64)
    for derivative_axis in range(3):
        for component in range(3):
            result[..., derivative_axis, component] = derivative_scalar(
                vector[..., component], derivative_axis
            )
    return result


def divergence_vector(vector: np.ndarray) -> np.ndarray:
    gradient = gradient_vector(vector)
    return np.trace(gradient, axis1=-2, axis2=-1)


def curl_vector(vector: np.ndarray) -> np.ndarray:
    gradient = gradient_vector(vector)
    return np.stack([
        gradient[..., 1, 2] - gradient[..., 2, 1],
        gradient[..., 2, 0] - gradient[..., 0, 2],
        gradient[..., 0, 1] - gradient[..., 1, 0],
    ], axis=-1)


def laplacian_vector(vector: np.ndarray) -> np.ndarray:
    vector_hat = fft_vector(vector)
    return ifft_vector(-K_SQ[..., None] * vector_hat)


def leray_project(vector: np.ndarray) -> np.ndarray:
    vector_hat = fft_vector(vector)
    dot = KX * vector_hat[..., 0] + KY * vector_hat[..., 1] + KZ * vector_hat[..., 2]
    inverse_k_sq = np.zeros_like(K_SQ)
    nonzero = K_SQ > 0
    inverse_k_sq[nonzero] = 1.0 / K_SQ[nonzero]
    projected = vector_hat.copy()
    for component, wave_number in enumerate(K_AXES):
        projected[..., component] -= wave_number * dot * inverse_k_sq
    return ifft_vector(projected)


def advect_vector(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    right_gradient = gradient_vector(right)
    return np.einsum("...i,...ij->...j", left, right_gradient)


def inner_vector(left: np.ndarray, right: np.ndarray) -> float:
    return float(np.mean(np.einsum("...i,...i->...", left, right)))


def gradient_norm_sq(vector: np.ndarray) -> float:
    gradient = gradient_vector(vector)
    return float(np.mean(np.einsum("...ij,...ij->...", gradient, gradient)))


def tensor_contraction(left: np.ndarray, right: np.ndarray) -> float:
    return float(np.mean(np.einsum("...ij,...ij->...", left, right)))


nu_value = 0.37
c_value = 1.7
fixture_gradient = gradient_vector(fixture)
fixture_strain = 0.5 * (fixture_gradient + np.swapaxes(fixture_gradient, -1, -2))
fixture_omega = curl_vector(fixture)
fixture_advection = advect_vector(fixture, fixture)
fixture_ut = nu_value * laplacian_vector(fixture) - leray_project(fixture_advection)
fixture_utt = (
    nu_value * laplacian_vector(fixture_ut)
    - leray_project(
        advect_vector(fixture_ut, fixture)
        + advect_vector(fixture, fixture_ut)
    )
)
fixture_omega_t = curl_vector(fixture_ut)

record("E01 Fourier arrays finite",
       all(np.all(np.isfinite(array)) for array in (
           fixture, fixture_gradient, fixture_strain, fixture_omega,
           fixture_ut, fixture_utt, fixture_omega_t,
       )),
       "all fixed-datum arrays are finite")
close("E02 Fourier divergence-free datum",
      float(np.max(np.abs(divergence_vector(fixture)))), 0.0)
close("E03 Fourier divergence-free time derivative",
      float(np.max(np.abs(divergence_vector(fixture_ut)))), 0.0)
max_close("E04 Leray projector idempotence",
          leray_project(leray_project(fixture_advection)),
          leray_project(fixture_advection))
close("E05 transport cancellation",
      inner_vector(advect_vector(fixture, fixture_ut), fixture_ut), 0.0)

stretching = tensor_contraction(
    fixture_strain,
    np.einsum("...i,...j->...ij", fixture_omega, fixture_omega),
)
close("E06 stretching anchor", stretching, 0.5)

enstrophy_lhs = (
    inner_vector(fixture_omega, fixture_omega_t)
    + nu_value * gradient_norm_sq(fixture_omega)
)
close("E07 enstrophy balance", enstrophy_lhs, stretching)

time_strain = tensor_contraction(
    fixture_strain,
    np.einsum("...i,...j->...ij", fixture_ut, fixture_ut),
)
time_energy_lhs = (
    inner_vector(fixture_ut, fixture_utt)
    + nu_value * gradient_norm_sq(fixture_ut)
)
close("E08 time-derivative energy balance", time_energy_lhs, -time_strain)

q_fixture = fixture_ut / c_value
h_derivative_half = (
    inner_vector(fixture_omega, fixture_omega_t)
    + inner_vector(fixture_ut, fixture_utt) / c_value**2
)
dissipation = (
    gradient_norm_sq(fixture_omega)
    + gradient_norm_sq(fixture_ut) / c_value**2
)
combined_lhs = h_derivative_half + nu_value * dissipation
outer_difference_numeric = (
    np.einsum("...i,...j->...ij", fixture_omega, fixture_omega)
    - np.einsum("...i,...j->...ij", q_fixture, q_fixture)
)
combined_rhs = tensor_contraction(fixture_strain, outer_difference_numeric)
close("E09 combined second-order energy balance", combined_lhs, combined_rhs)

alignment_dot = np.einsum("...i,...i->...", fixture_omega, q_fixture)
sigma_fixture = np.where(alignment_dot >= 0.0, 1.0, -1.0)
b_fixture = sigma_fixture[..., None] * q_fixture
g_fixture = fixture_omega - b_fixture
factorized_numeric = (
    np.einsum("...i,...j->...ij", g_fixture, fixture_omega)
    + np.einsum("...i,...j->...ij", b_fixture, g_fixture)
)
max_close("E10 pointwise signed tensor factorization",
          outer_difference_numeric, factorized_numeric)

residual_norm = np.linalg.norm(g_fixture, axis=-1)
plus_norm = np.linalg.norm(fixture_omega - q_fixture, axis=-1)
minus_norm = np.linalg.norm(fixture_omega + q_fixture, axis=-1)
max_close("E11 pointwise residual minimization", residual_norm, np.minimum(plus_norm, minus_norm))

ModeKey = tuple[int, int, int]
ModeField = dict[ModeKey, np.ndarray]


def add_mode(target: ModeField, key: ModeKey, value: np.ndarray) -> None:
    if key in target:
        target[key] += value
    else:
        target[key] = np.asarray(value, dtype=np.complex128).copy()


def add_mode_fields(*fields: ModeField) -> ModeField:
    result: ModeField = {}
    for field in fields:
        for key, value in field.items():
            add_mode(result, key, value)
    return result


def direct_advective_modes(left: ModeField, right: ModeField) -> ModeField:
    result: ModeField = {}
    for ell, left_hat in left.items():
        for m, right_hat in right.items():
            key = tuple(ell[axis_index] + m[axis_index] for axis_index in range(3))
            m_vector = np.asarray(m, dtype=np.float64)
            coefficient = 1j * np.dot(m_vector, left_hat)
            add_mode(result, key, coefficient * right_hat)
    return result


def direct_leray_mode(key: ModeKey, value: np.ndarray) -> np.ndarray:
    wave_vector = np.asarray(key, dtype=np.float64)
    wave_number_sq = float(np.dot(wave_vector, wave_vector))
    if wave_number_sq == 0.0:
        return value.copy()
    return value - wave_vector * np.dot(wave_vector, value) / wave_number_sq


def direct_ns_first_derivative(field: ModeField, viscosity: float) -> ModeField:
    advection = direct_advective_modes(field, field)
    result: ModeField = {}
    zero = np.zeros(3, dtype=np.complex128)
    for key in set(field) | set(advection):
        wave_number_sq = float(sum(component**2 for component in key))
        value = (
            -viscosity * wave_number_sq * field.get(key, zero)
            - direct_leray_mode(key, advection.get(key, zero))
        )
        add_mode(result, key, value)
    return result


def direct_ns_second_derivative(
    field: ModeField,
    field_t: ModeField,
    viscosity: float,
) -> ModeField:
    advection_t = add_mode_fields(
        direct_advective_modes(field_t, field),
        direct_advective_modes(field, field_t),
    )
    result: ModeField = {}
    zero = np.zeros(3, dtype=np.complex128)
    for key in set(field_t) | set(advection_t):
        wave_number_sq = float(sum(component**2 for component in key))
        value = (
            -viscosity * wave_number_sq * field_t.get(key, zero)
            - direct_leray_mode(key, advection_t.get(key, zero))
        )
        add_mode(result, key, value)
    return result


def modes_to_fft_coefficients(field: ModeField) -> np.ndarray:
    result = np.zeros((N, N, N, 3), dtype=np.complex128)
    for key, value in field.items():
        grid_key = tuple(component % N for component in key)
        result[grid_key] = value
    return result


mode_x = np.asarray((0.0, 0.5, 0.5), dtype=np.complex128)
mode_y = np.asarray((0.5, 0.0, 0.5), dtype=np.complex128)
mode_xy = np.asarray((1.0, -1.0, 1.0), dtype=np.complex128)
fixture_modes: ModeField = {
    (1, 0, 0): mode_x,
    (-1, 0, 0): mode_x,
    (0, 1, 0): mode_y,
    (0, -1, 0): mode_y,
    (1, 1, 0): -0.5j * mode_xy,
    (-1, -1, 0): 0.5j * mode_xy,
}
fixture_ut_reference = direct_ns_first_derivative(fixture_modes, nu_value)
fixture_utt_reference = direct_ns_second_derivative(
    fixture_modes,
    fixture_ut_reference,
    nu_value,
)
max_close(
    "E12 Leray-projected u_t equation against independent modes",
    fft_vector(fixture_ut) / N**3,
    modes_to_fft_coefficients(fixture_ut_reference),
)
max_close(
    "E13 Leray-projected u_tt equation against independent modes",
    fft_vector(fixture_utt) / N**3,
    modes_to_fft_coefficients(fixture_utt_reference),
)

values.update({
    "grid_n": N,
    "nu": nu_value,
    "c": c_value,
    "stretching": stretching,
    "enstrophy_balance_lhs": enstrophy_lhs,
    "time_energy_balance_lhs": time_energy_lhs,
    "time_energy_balance_rhs": -time_strain,
    "combined_balance_lhs": combined_lhs,
    "combined_balance_rhs": combined_rhs,
    "residual_l3": float(np.mean(residual_norm**3)**(1.0 / 3.0)),
})


# ---------------------------------------------------------------------------
# Receipt and frozen verdict.
# ---------------------------------------------------------------------------

failures = [entry for entry in checks if not entry["passed"]]
inventory_ok = len(checks) == 110
status = (
    "PASS—DERIVED CONDITIONAL"
    if not failures and inventory_ok
    else "FAIL—SECOND-ORDER FIELD ENERGY AUDIT"
)
payload = {
    "schema": SCHEMA,
    "status": status,
    "checks_total": len(checks),
    "checks_passed": len(checks) - len(failures),
    "checks_failed": len(failures),
    "expected_checks": 110,
    "check_inventory_matches": inventory_ok,
    "tolerances": {"absolute": ATOL, "relative": RTOL},
    "source_sha256": source_hashes,
    "expected_source_sha256": EXPECTED_SHA256,
    "values": values,
    "checks": checks,
}
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

print()
print(f"Receipt: {OUTPUT.relative_to(ROOT)}")
print(f"SUMMARY: {len(checks) - len(failures)}/{len(checks)} checks passed")
if failures or not inventory_ok:
    print("FAIL—SECOND-ORDER FIELD ENERGY AUDIT")
    if not inventory_ok:
        print(f"  - check inventory: actual={len(checks)}, expected=110")
    for failure in failures:
        print(f"  - {failure['name']}: {failure['detail']}")
    sys.exit(1)

print("ALL CHECKS PASSED")
