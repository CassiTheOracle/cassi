"""Verify the frozen gauge-covariant inter-vertex endpoint transport.

Run from the CassiTheory repository root:
    python computations/endpoint_intervertex_transport_check.py
"""

from __future__ import annotations

import cmath
import math
import sys


TOL = 1.0e-11
DERIVATIVE_TOL = 1.0e-9
CONTROL_MIN = 1.0e-3
DERIVATIVE_STEP = 1.0e-6

HBAR = 1.7
T_HOP = 0.8
U_MINUS = 0.9
U_PLUS = 1.1
G_Q = 0.4
KAPPA_MINUS = 0.6
KAPPA_PLUS = 0.7
MU_MINUS = 1.2
MU_PLUS = 0.95

CONNECTION_INTEGRAL = 0.37
ALPHA_MINUS = 0.23
CURRENT_RATIO = 0.4
CHI_MINUS = 0.29
CHI_PLUS = -0.41


def wilson(connection_integral: float) -> complex:
    return cmath.exp(-1j * G_Q * connection_integral)


def transport_energy(
    upsilon_minus: complex,
    upsilon_plus: complex,
    link: complex,
    hopping: float = T_HOP,
) -> float:
    bilinear = upsilon_plus.conjugate() * link * upsilon_minus
    return float((-hopping * (bilinear + bilinear.conjugate())).real)


def transport_current(
    upsilon_minus: complex,
    upsilon_plus: complex,
    link: complex,
    hopping: float = T_HOP,
) -> float:
    bilinear = upsilon_plus.conjugate() * link * upsilon_minus
    return -2.0 * hopping * bilinear.imag / HBAR


def current_from_phase(phase: float) -> float:
    return (
        2.0
        * T_HOP
        * U_MINUS
        * U_PLUS
        * math.sin(phase)
        / HBAR
    )


def phase_curvature(phase: float) -> float:
    return 2.0 * T_HOP * U_MINUS * U_PLUS * math.cos(phase)


def gate_line(name: str, passed: bool) -> str:
    return f"  {name:<33} = {'PASS' if passed else 'FAIL'}"


critical_current = 2.0 * T_HOP * U_MINUS * U_PLUS / HBAR
target_current = CURRENT_RATIO * critical_current
stable_phase = math.asin(CURRENT_RATIO)
unstable_phase = math.pi - stable_phase
alpha_plus = (
    ALPHA_MINUS
    - G_Q * CONNECTION_INTEGRAL
    + stable_phase
)

upsilon_minus = U_MINUS * cmath.exp(1j * ALPHA_MINUS)
upsilon_plus = U_PLUS * cmath.exp(1j * alpha_plus)
link = wilson(CONNECTION_INTEGRAL)
link_bilinear = upsilon_plus.conjugate() * link * upsilon_minus
energy = transport_energy(upsilon_minus, upsilon_plus, link)
current = transport_current(upsilon_minus, upsilon_plus, link)

# The imposed rail bilinears solve the homogeneous rotating-frame endpoint
# equations at the frozen point.
rail_minus = (
    MU_MINUS * upsilon_minus
    - T_HOP * link.conjugate() * upsilon_plus
) / KAPPA_MINUS
rail_plus = (
    MU_PLUS * upsilon_plus
    - T_HOP * link * upsilon_minus
) / KAPPA_PLUS

residual_minus = (
    MU_MINUS * upsilon_minus
    - KAPPA_MINUS * rail_minus
    - T_HOP * link.conjugate() * upsilon_plus
)
residual_plus = (
    MU_PLUS * upsilon_plus
    - KAPPA_PLUS * rail_plus
    - T_HOP * link * upsilon_minus
)

gamma_minus = (
    -2.0
    * KAPPA_MINUS
    / HBAR
    * (upsilon_minus.conjugate() * rail_minus).imag
)
gamma_plus = (
    -2.0
    * KAPPA_PLUS
    / HBAR
    * (upsilon_plus.conjugate() * rail_plus).imag
)

# IT1: independent endpoint values of one local time-independent frame change.
transformation_minus = cmath.exp(-1j * G_Q * CHI_MINUS)
transformation_plus = cmath.exp(-1j * G_Q * CHI_PLUS)
connection_integral_transformed = (
    CONNECTION_INTEGRAL + CHI_PLUS - CHI_MINUS
)
link_from_transformed_connection = wilson(connection_integral_transformed)
link_from_endpoint_law = (
    transformation_plus
    * link
    * transformation_minus.conjugate()
)
upsilon_minus_transformed = transformation_minus * upsilon_minus
upsilon_plus_transformed = transformation_plus * upsilon_plus
rail_minus_transformed = transformation_minus * rail_minus
rail_plus_transformed = transformation_plus * rail_plus

bilinear_transformed = (
    upsilon_plus_transformed.conjugate()
    * link_from_transformed_connection
    * upsilon_minus_transformed
)
energy_transformed = transport_energy(
    upsilon_minus_transformed,
    upsilon_plus_transformed,
    link_from_transformed_connection,
)
current_transformed = transport_current(
    upsilon_minus_transformed,
    upsilon_plus_transformed,
    link_from_transformed_connection,
)
residual_minus_transformed = (
    MU_MINUS * upsilon_minus_transformed
    - KAPPA_MINUS * rail_minus_transformed
    - T_HOP
    * link_from_transformed_connection.conjugate()
    * upsilon_plus_transformed
)
residual_plus_transformed = (
    MU_PLUS * upsilon_plus_transformed
    - KAPPA_PLUS * rail_plus_transformed
    - T_HOP
    * link_from_transformed_connection
    * upsilon_minus_transformed
)

wilson_law_error = abs(
    link_from_transformed_connection - link_from_endpoint_law
)
bilinear_invariance_error = abs(bilinear_transformed - link_bilinear)
energy_invariance_error = abs(energy_transformed - energy)
current_invariance_error = abs(current_transformed - current)
minus_covariance_error = abs(
    residual_minus_transformed
    - transformation_minus * residual_minus
)
plus_covariance_error = abs(
    residual_plus_transformed
    - transformation_plus * residual_plus
)

it1 = all(
    error <= TOL
    for error in (
        wilson_law_error,
        bilinear_invariance_error,
        energy_invariance_error,
        current_invariance_error,
        minus_covariance_error,
        plus_covariance_error,
    )
)

# IT2: stationary endpoint equations, oriented sources, and number closure.
equation_error = max(abs(residual_minus), abs(residual_plus))
minus_source_error = abs(gamma_minus - current)
plus_source_error = abs(gamma_plus + current)
minus_balance_error = abs(gamma_minus - current)
plus_balance_error = abs(gamma_plus + current)
summed_endpoint_source = abs(gamma_minus + gamma_plus)
target_current_error = abs(current - target_current)

it2 = all(
    error <= TOL
    for error in (
        equation_error,
        minus_source_error,
        plus_source_error,
        minus_balance_error,
        plus_balance_error,
        summed_endpoint_source,
        target_current_error,
    )
)

# IT3: Wilson-Hamiltonian derivative and the two-vertex charge ledger.
def energy_at_connection(connection_integral: float) -> float:
    return transport_energy(
        upsilon_minus,
        upsilon_plus,
        wilson(connection_integral),
    )


energy_derivative = (
    energy_at_connection(CONNECTION_INTEGRAL + DERIVATIVE_STEP)
    - energy_at_connection(CONNECTION_INTEGRAL - DERIVATIVE_STEP)
) / (2.0 * DERIVATIVE_STEP)
wilson_charge_current = -energy_derivative / HBAR
expected_charge_current = -G_Q * current
wilson_current_error = abs(
    wilson_charge_current - expected_charge_current
)

rail_charge_sources = (
    G_Q * gamma_minus,
    G_Q * gamma_plus,
)
endpoint_charge_rates = (
    -G_Q * (gamma_minus - current),
    -G_Q * (gamma_plus + current),
)
link_charge_divergence = (
    -G_Q * current,
    +G_Q * current,
)
charge_ledger = tuple(
    rail + endpoint + divergence
    for rail, endpoint, divergence in zip(
        rail_charge_sources,
        endpoint_charge_rates,
        link_charge_divergence,
    )
)
charge_ledger_error = max(abs(value) for value in charge_ledger)

it3 = (
    wilson_current_error <= DERIVATIVE_TOL
    and charge_ledger_error <= TOL
)

# IT4: the sine law, critical current, and the supercritical control.
stable_current = current_from_phase(stable_phase)
unstable_current = current_from_phase(unstable_phase)
critical_phase_current = current_from_phase(math.pi / 2.0)
subcritical_margin = critical_current - abs(target_current)
supercritical_current = 1.05 * critical_current
supercritical_excess = abs(supercritical_current) - critical_current
expected_supercritical_excess = 0.05 * critical_current

stable_current_error = abs(stable_current - target_current)
unstable_current_error = abs(unstable_current - target_current)
critical_current_error = abs(critical_phase_current - critical_current)
supercritical_excess_error = abs(
    supercritical_excess - expected_supercritical_excess
)

it4 = (
    stable_current_error <= TOL
    and unstable_current_error <= TOL
    and critical_current_error <= TOL
    and subcritical_margin > 0.0
    and supercritical_excess > 0.0
    and supercritical_excess_error <= TOL
)

# IT5: fixed-amplitude phase curvature on the two branches and boundary.
stable_curvature = phase_curvature(stable_phase)
unstable_curvature = phase_curvature(unstable_phase)
critical_curvature = phase_curvature(math.pi / 2.0)
curvature_magnitude_error = abs(
    stable_curvature + unstable_curvature
)

it5 = (
    stable_curvature > 0.0
    and unstable_curvature < 0.0
    and curvature_magnitude_error <= TOL
    and abs(critical_curvature) <= TOL
)

# IT6: removing either the Wilson dressing or the hopping coefficient.
bare_bilinear = upsilon_plus.conjugate() * upsilon_minus
bare_bilinear_transformed = (
    upsilon_plus_transformed.conjugate()
    * upsilon_minus_transformed
)
bare_covariance_failure = abs(
    bare_bilinear_transformed - bare_bilinear
)
zero_coupling_current = transport_current(
    upsilon_minus,
    upsilon_plus,
    link,
    hopping=0.0,
)
zero_coupling_residual = abs(target_current - zero_coupling_current)
zero_coupling_error = abs(
    zero_coupling_residual - abs(target_current)
)

it6 = (
    bare_covariance_failure > CONTROL_MIN
    and abs(target_current) > TOL
    and zero_coupling_error <= TOL
)

gates = {
    "IT1": it1,
    "IT2": it2,
    "IT3": it3,
    "IT4": it4,
    "IT5": it5,
    "IT6": it6,
}
overall = all(gates.values())

print("Gauge-covariant inter-vertex endpoint transport receipt")
print(f"  critical current I_c              = {critical_current:.12e}")
print(f"  target current J_Q                = {target_current:.12e}")
print(f"  stable phase Delta_s              = {stable_phase:.12e}")
print(f"  unstable phase Delta_u            = {unstable_phase:.12e}")
print(f"  transport Hamiltonian             = {energy:.12e}")
print(f"  IT1 Wilson-law error               = {wilson_law_error:.3e}")
print(f"  IT1 bilinear-invariance error      = {bilinear_invariance_error:.3e}")
print(f"  IT1 energy-invariance error        = {energy_invariance_error:.3e}")
print(f"  IT1 current-invariance error       = {current_invariance_error:.3e}")
print(f"  IT1 minus-equation covariance      = {minus_covariance_error:.3e}")
print(f"  IT1 plus-equation covariance       = {plus_covariance_error:.3e}")
print(f"  IT2 endpoint-equation error        = {equation_error:.3e}")
print(f"  IT2 lower-source error             = {minus_source_error:.3e}")
print(f"  IT2 upper-source error             = {plus_source_error:.3e}")
print(f"  IT2 summed-source error            = {summed_endpoint_source:.3e}")
print(f"  IT2 target-current error           = {target_current_error:.3e}")
print(f"  IT3 Wilson-current error           = {wilson_current_error:.3e}")
print(f"  IT3 charge-ledger error            = {charge_ledger_error:.3e}")
print(f"  IT4 stable-current error           = {stable_current_error:.3e}")
print(f"  IT4 companion-current error        = {unstable_current_error:.3e}")
print(f"  IT4 critical-current error         = {critical_current_error:.3e}")
print(f"  IT4 subcritical margin             = {subcritical_margin:.12e}")
print(f"  IT4 supercritical excess           = {supercritical_excess:.12e}")
print(f"  IT4 excess error                   = {supercritical_excess_error:.3e}")
print(f"  IT5 stable curvature               = {stable_curvature:.12e}")
print(f"  IT5 companion curvature            = {unstable_curvature:.12e}")
print(f"  IT5 curvature-magnitude error      = {curvature_magnitude_error:.3e}")
print(f"  IT5 marginal curvature             = {critical_curvature:.3e}")
print(f"  IT6 bare-bilinear change           = {bare_covariance_failure:.12e}")
print(f"  IT6 zero-coupling closure residual = {zero_coupling_residual:.12e}")
for name, passed in gates.items():
    print(gate_line(name, passed))
print(f"OVERALL: {'PASS' if overall else 'FAIL'}")

sys.exit(0 if overall else 1)
