"""Independent algebra receipt for the neutral common-phase observable.

Run from the repository root.  This file deliberately does not import the
neutral-phase primary program or any of its output.  It verifies only the
local composite observable and its interpretation for the declared
fundamental-plus-adjoint fields.  The receipt is JSON on stdout and exits
nonzero if an exact algebraic check fails.
"""

from __future__ import annotations

import json
import math
import sys
from itertools import product
from typing import Any

import sympy as sp



def _json_value(value: Any) -> Any:
    """Convert SymPy/numeric values to strict JSON-compatible values."""
    if isinstance(value, (bool, int, str)) or value is None:
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, complex):
        return {"real": float(value.real), "imag": float(value.imag)}
    if isinstance(value, (sp.Integer, sp.Rational)):
        return str(value)
    if isinstance(value, sp.Float):
        return float(value)
    if isinstance(value, sp.Expr):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(v) for v in value]
    raise TypeError(f"cannot encode {type(value)!r}")



def _complex_pair(value: complex) -> dict[str, float]:
    return {"real": float(value.real), "imag": float(value.imag)}



def _component_algebra() -> tuple[dict[str, bool], dict[str, str]]:
    """Perform exact component checks without conjugation assumptions in SymPy."""
    I = sp.I
    x, y, xb, yb = sp.symbols("x y xbar ybar")
    p1, p2, p3 = sp.symbols("Phi1 Phi2 Phi3", real=True)
    sigma = [
        sp.Matrix([[0, 1], [1, 0]]),
        sp.Matrix([[0, -I], [I, 0]]),
        sp.Matrix([[1, 0], [0, -1]]),
    ]
    generators = [s / 2 for s in sigma]
    E = I * sigma[1]
    psi = sp.Matrix([x, y])
    M = p1 * sigma[0] + p2 * sigma[1] + p3 * sigma[2]
    observable = (psi.T * E * M * psi)[0]

    # The formal barred expression is the complex conjugate with p_a real.
    psib = sp.Matrix([xb, yb])
    Mbar = p1 * sigma[0] - p2 * sigma[1] + p3 * sigma[2]
    observable_bar = (psib.T * E * Mbar * psib)[0]

    rho = xb * x + yb * y
    spin = [
        (psib.T * s * psi)[0]
        for s in sigma
    ]
    phi_sq = p1**2 + p2**2 + p3**2
    phi_dot_spin = p1 * spin[0] + p2 * spin[1] + p3 * spin[2]

    checks: dict[str, bool] = {}
    details: dict[str, str] = {}

    for index, generator in enumerate(generators, start=1):
        delta_psi = I * generator * psi
        delta_m = I * generator * M - M * I * generator
        delta_observable = (
            (delta_psi.T * E * M * psi)[0]
            + (psi.T * E * delta_m * psi)[0]
            + (psi.T * E * M * delta_psi)[0]
        )
        reduced = sp.factor(sp.expand(delta_observable))
        key = f"su2_generator_{index}_variation_zero"
        checks[key] = reduced == 0
        details[key] = str(reduced)

    u = sp.symbols("u", nonzero=True)
    u1_difference = sp.factor(
        sp.expand(
            ((u * psi).T * E * M * (u * psi))[0] - u**2 * observable
        )
    )
    checks["common_u1_charge_two"] = u1_difference == 0
    details["common_u1_charge_two_difference"] = str(u1_difference)

    norm_difference = sp.factor(
        sp.expand(observable * observable_bar - (rho**2 * phi_sq - phi_dot_spin**2))
    )
    checks["modulus_identity"] = norm_difference == 0
    details["modulus_identity_difference"] = str(norm_difference)

    return checks, details



def _relative_sphere_algebra() -> tuple[dict[str, bool], dict[str, str]]:
    """Check the sign/conjugation convention linking O to G(z)^dagger(n.sigma)G(z)."""
    I = sp.I
    z1, z2, z1b, z2b = sp.symbols("z1 z2 z1bar z2bar")
    n1, n2, n3 = sp.symbols("n1 n2 n3", real=True)
    sigma = [
        sp.Matrix([[0, 1], [1, 0]]),
        sp.Matrix([[0, -I], [I, 0]]),
        sp.Matrix([[1, 0], [0, -1]]),
    ]
    E = I * sigma[1]
    z = sp.Matrix([z1, z2])
    zb = sp.Matrix([z1b, z2b])
    G = sp.Matrix([[z1, -z2b], [z2, z1b]])
    Gdagger = sp.Matrix([[z1b, z2b], [-z2, z1]])
    n_sigma = n1 * sigma[0] + n2 * sigma[1] + n3 * sigma[2]
    relative = sp.expand(Gdagger * n_sigma * G)
    normalized_observable = sp.expand((z.T * E * n_sigma * z)[0])
    normalized_observable_bar = sp.expand(
        (zb.T * E * (n1 * sigma[0] - n2 * sigma[1] + n3 * sigma[2]) * zb)[0]
    )

    checks = {
        "relative_matrix_lower_left_equals_normalized_observable": sp.simplify(
            relative[1, 0] - normalized_observable
        ) == 0,
        "relative_matrix_upper_right_is_conjugate": sp.simplify(
            relative[0, 1] - normalized_observable_bar
        )
        == 0,
    }
    details = {
        "normalized_observable": str(normalized_observable),
        "relative_lower_left": str(relative[1, 0]),
        "relative_upper_right": str(relative[0, 1]),
    }
    return checks, details



def _vacuum_witnesses() -> tuple[dict[str, bool], list[dict[str, Any]], dict[str, str]]:
    """Check the real unitary-gauge formula and provide non-singular witnesses."""
    rho, v, phase, c, s = sp.symbols("rho v phase c s", real=True)
    R = sp.symbols("R", positive=True, real=True)
    sigma2_i = sp.Matrix([[0, 1], [-1, 0]])
    sigma3 = sp.Matrix([[1, 0], [0, -1]])
    psi = sp.Matrix([R * phase * c, R * phase * s])
    observable = sp.expand((psi.T * sigma2_i * (v * sigma3) * psi)[0])
    expected = -R**2 * v * (2 * c * s) * phase**2
    checks = {
        "unitary_gauge_formula": sp.factor(observable - expected) == 0,
        "aligned_beta_zero_vanishes": observable.subs({s: 0, R: 1, v: 1, phase: 1}) == 0,
        "aligned_beta_pi_vanishes": observable.subs({c: 0, R: 1, v: 1, phase: 1}) == 0,
    }
    details = {
        "unitary_gauge_observable": str(observable),
        "unitary_gauge_expected": str(expected),
        "phase_definition": "vartheta = arg(O_N) = 2 Theta + pi on the displayed real branch when sin(beta)>0",
    }

    phi = (1.0 + math.sqrt(5.0)) / 2.0
    composition_cosine = phi ** -3
    composition_sine = math.sqrt(1.0 - composition_cosine**2)
    witnesses = [
        {
            "name": "declared_composition_vacuum",
            "rho": 1.2,
            "v_Q": 0.9,
            "cos_beta": composition_cosine,
            "sin_beta": composition_sine,
            "Theta": 0.0,
            "O_N": _complex_pair(complex(-1.2 * 0.9 * composition_sine, 0.0)),
            "O_over_rho_v": _complex_pair(complex(-composition_sine, 0.0)),
        },
        {
            "name": "quadrature_common_phase",
            "rho": 1.2,
            "v_Q": 0.9,
            "cos_beta": 0.0,
            "sin_beta": 1.0,
            "Theta": math.pi / 4.0,
            "O_N": _complex_pair(complex(0.0, -1.2 * 0.9)),
            "O_over_rho_v": _complex_pair(complex(0.0, -1.0)),
        },
        {
            "name": "aligned_yang",
            "rho": 1.2,
            "v_Q": 0.9,
            "cos_beta": 1.0,
            "sin_beta": 0.0,
            "Theta": 0.37,
            "O_N": _complex_pair(0.0j),
            "phase_defined": False,
        },
        {
            "name": "aligned_yin",
            "rho": 1.2,
            "v_Q": 0.9,
            "cos_beta": -1.0,
            "sin_beta": 0.0,
            "Theta": -0.19,
            "O_N": _complex_pair(0.0j),
            "phase_defined": False,
        },
    ]
    return checks, witnesses, details



def _centre_parity() -> tuple[dict[str, bool], list[dict[str, Any]]]:
    """Impose vertex centre Gauss laws on a closed three-link graph."""
    # Link signs are (-1)^(2j) for electric representations, not holonomies.
    # Site signs are (-1)^N for fundamental matter; adjoints contribute +1.
    # Each internal link enters two vertex laws, irrespective of orientation.
    rows: list[dict[str, Any]] = []
    for edge_signs in product((-1, 1), repeat=3):
        for site_signs in product((-1, 1), repeat=3):
            local_gauss = (
                site_signs[0] * edge_signs[0] * edge_signs[2],
                site_signs[1] * edge_signs[0] * edge_signs[1],
                site_signs[2] * edge_signs[1] * edge_signs[2],
            )
            rows.append(
                {
                    "edges": dict(zip(("01", "12", "20"), edge_signs)),
                    "sites": site_signs,
                    "vertex_gauss_signs": local_gauss,
                    "matter_parity": math.prod(site_signs),
                    "centre_gauss_allowed": all(sign == 1 for sign in local_gauss),
                }
            )
    accepted = [row for row in rows if row["centre_gauss_allowed"]]
    checks = {
        "vertex_gauss_product_equals_matter_parity": all(
            math.prod(row["vertex_gauss_signs"]) == row["matter_parity"]
            for row in rows
        ),
        "closed_graph_allowed_matter_parity_even": all(
            row["matter_parity"] == 1 for row in accepted
        ),
        "even_site_patterns_have_two_link_assignments_odd_have_none": all(
            sum(row["sites"] == sites for row in accepted)
            == (2 if math.prod(sites) == 1 else 0)
            for sites in product((-1, 1), repeat=3)
        ),
        "pure_gauge_fundamental_wilson_loop_allowed": any(
            row["sites"] == (1, 1, 1)
            and all(sign == -1 for sign in row["edges"].values())
            for row in accepted
        ),
    }
    return checks, rows



def main() -> int:
    algebra_checks, algebra_details = _component_algebra()
    sphere_checks, sphere_details = _relative_sphere_algebra()
    vacuum_checks, witnesses, vacuum_details = _vacuum_witnesses()
    centre_checks, centre_rows = _centre_parity()

    checks: dict[str, bool] = {}
    checks.update(algebra_checks)
    checks.update(sphere_checks)
    checks.update(vacuum_checks)
    checks.update(centre_checks)

    receipt = {
        "verdict": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "conventions": {
            "pauli_generators": "T^a = sigma^a/2; SU(2) variation uses delta Psi = i epsilon^a T^a Psi and delta(Phi.sigma) = [i epsilon^a T^a, Phi.sigma]",
            "adjoint_component_convention": "For h=exp(i epsilon^a T^a), delta Phi = Phi cross epsilon",
            "common_number_action": "Psi -> exp(i alpha) Psi, Phi -> Phi",
            "vacuum_parameterization": "Psi = exp(i Theta) sqrt(rho) (cos(beta/2), sin(beta/2))^T and Phi = v_Q e_3",
            "relative_doublet": "z = Psi/sqrt(rho), G(z)=[[z1,-z2*],[z2,z1*]], n=Phi/|Phi|",
        },
        "exact_algebra": {
            "observable": "O_N = Psi^T (i sigma^2) (Phi^a sigma^a) Psi",
            "component_details": algebra_details,
            "relative_sphere_details": sphere_details,
            "vacuum_details": vacuum_details,
        },
        "vacuum_witnesses": witnesses,
        "relative_sphere": {
            "definition": "N^a sigma^a = G(z)^dagger (n^a sigma^a) G(z)",
            "identity": "O_N/(rho |Phi|) = N_21, the lower-left entry",
            "conjugation_convention": "N_12 = (N_21)^*; no extra minus sign is inserted beyond i sigma^2",
            "azimuth_scope": "The existing relative S^2 azimuth already carries this phase. It is undefined at N_1=N_2=0, exactly where O_N=0.",
        },
        "centre_and_interpretation": {
            "centre_action": "(-I in SU(2)_Q, -1 in U(1)_N) acts trivially on the pair (Psi,Phi), so Theta is identified modulo pi and vartheta=arg(O_N) has period 2 pi.",
            "stabilizer": "With both fundamental components nonzero, H_full={1}; this centre identification is not a residual unbroken local Z2.",
            "triangle_scope": "At each vertex, (-1)^N times the incident electric-representation signs (-1)^(2j) must equal +1. Each internal link enters twice, so allowed states have even total fundamental-matter parity. The pure fundamental Wilson loop has three negative link signs and satisfies every vertex constraint. External boundary charges are excluded. Centre parity alone does not replace the full SU(2) Gauss projection or determine spin/statistics.",
            "classical_scope": "O_N is a local gauge-invariant charge-two classical composite observable. Its phase can have local gradients and time dependence after gauge projection.",
            "quantum_scope": "A charge-two operator is not an established paired quantum condensate. In an exact eigenstate of total common-number charge its one-point function is U(1)_N selection-rule forbidden, while charge-neutral correlators and local phase dynamics can remain nontrivial. No quantum vacuum, particle, fermion, boson, or statistics claim follows.",
            "boundary_and_number": "Selecting an asymptotic common phase removes at most a global boundary/zero-mode freedom; it does not set local derivatives to zero. Fixing total common-number charge constrains an integral momentum, not the pointwise phase, so zero-integral local phase fluctuations and their neutral collective dynamics remain allowed.",
        },
        "centre_parity_enumeration": centre_rows,
        "limitations": [
            "The phase is undefined where rho=0, |Phi|=0, or O_N=0 (including aligned compositions).",
            "The centre check is necessary bookkeeping only and is not a Gauss-law projection.",
            "The result is classical field algebra and does not establish a quantum condensate, physical particle, fermionic statistics, or nonlinear persistence.",
        ],
        "complete_physical_matter_formation": False,
    }
    print(json.dumps(_json_value(receipt), sort_keys=True, separators=(",", ":")))
    return 0 if receipt["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
