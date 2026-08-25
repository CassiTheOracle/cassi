r"""Verify the exact canonical reduction in the physical-becoming hierarchy.

Run from the CassiTheory repository root:

    python computations/verify_physical_becoming_reduction.py

The script checks symbolic identities only. It does not test the proposed
embodiment, shadow, attention, action, learning, or consciousness closures.

Two tiers of check:

* **Generic structure** -- the rank-one conversion matrix, its eigenvalues
  $0$ and $-(1+\varphi)\gamma_{\mathrm{conv}}$, the positive-semidefinite
  mobility, and the exact gradient-flow embedding hold for any nonnegative
  conversion rate $\gamma_{\mathrm{conv}}$.
* **Exact reference-state prediction** (Derived conditional) -- at the
  uniform reference state $(E_Y,E_I)=(1,\varphi^{-1})$ the $q$-gated rate
  collapses to $\Gamma_0=\lambda/3$, giving the imbalance decay
  $\varepsilon(t)=\varepsilon_0\,e^{-\lambda t/3}$, the $q$-deficit decay
  $e^{-2\lambda t/3}$ (twice the imbalance rate), and the frozen-unit-temperature
  FDT SDE $d\varepsilon=-(\lambda/3)\varepsilon\,dt-\sqrt{2\lambda/3}\,dW_t$.
  The nonlinear instantaneous log-decay rate
  $\Gamma(\varepsilon)=\varphi^2\lambda(\varphi^{-2}+\varepsilon^2)/(3+\varepsilon^2)$
  is monotone increasing in $\varepsilon^2$. At fixed $\rho=\varphi$ the
  positivity wedge is $-\varphi^2\le\varepsilon\le\varphi$, so the formal
  $\varepsilon^2\to\infty$ rate asymptote is not physically reachable; the
  normalized $R_Q$ boundary values are approximately $5.767427$ and
  $4.194048$ at $E_Y\to0$ and $E_I\to0$, respectively.
"""

from __future__ import annotations
import sympy as sp


phi = (sp.Integer(1) + sp.sqrt(5)) / 2
rho, eps, gamma_conv = sp.symbols("rho eps gamma_conv", real=True)
lam = sp.symbols("lam", positive=True, real=True)
E_y, E_i = sp.symbols("E_y E_i", nonnegative=True, real=True)


def require_zero(name: str, expression: sp.Expr) -> None:
    value = sp.simplify(expression)
    print(f"{name}: {value}")
    if value != 0:
        raise AssertionError(f"{name} failed: {value}")


def require_true(name: str, condition: bool) -> None:
    print(f"{name}: {condition}")
    if not condition:
        raise AssertionError(f"{name} failed")


def main() -> None:
    print("Physical-becoming canonical reduction verification")
    print(f"phi = {sp.N(phi, 16)}")

    # ------------------------------------------------------------------
    # Generic structure (gamma_conv >= 0 left symbolic).
    # ------------------------------------------------------------------
    # Coordinate change and positivity wedge.
    E_y_inverse = (phi * rho + eps) / (1 + phi)
    E_i_inverse = (rho - eps) / (1 + phi)
    require_zero("inverse rho", E_y_inverse + E_i_inverse - rho)
    require_zero("inverse epsilon", E_y_inverse - phi * E_i_inverse - eps)
    require_zero("phi squared identity", phi**2 - (1 + phi))

    lower_boundary = sp.simplify(E_y_inverse.subs(eps, -phi * rho))
    upper_boundary = sp.simplify(E_i_inverse.subs(eps, rho))
    require_zero("positivity lower boundary E_Y", lower_boundary)
    require_zero("positivity upper boundary E_I", upper_boundary)

    # Rank-one canonical conversion (dimensionless direction matrix).
    conversion_matrix = sp.Matrix([[-1, phi], [1, -phi]])
    require_true("conversion rank one", conversion_matrix.rank() == 1)
    characteristic = sp.factor(conversion_matrix.charpoly().as_expr())
    expected_characteristic = sp.factor(
        sp.Symbol("lambda") * (sp.Symbol("lambda") + 1 + phi)
    )
    require_zero(
        "conversion characteristic polynomial",
        characteristic - expected_characteristic,
    )
    require_zero(
        "total-density left null",
        (sp.Matrix([[1, 1]]) * conversion_matrix)[0, 0],
    )
    require_zero(
        "total-density left null second component",
        (sp.Matrix([[1, 1]]) * conversion_matrix)[0, 1],
    )
    require_true(
        "equilibrium right null",
        conversion_matrix * sp.Matrix([phi, 1]) == sp.zeros(2, 1),
    )

    drift = sp.Matrix(
        [-gamma_conv * (E_y - phi * E_i), gamma_conv * (E_y - phi * E_i)]
    )
    rho_dot = sp.simplify(drift[0] + drift[1])
    eps_dot = sp.simplify(drift[0] - phi * drift[1])
    require_zero("rho dot", rho_dot)
    require_zero(
        "epsilon contraction",
        eps_dot + gamma_conv * (1 + phi) * (E_y - phi * E_i),
    )

    # Positive-semidefinite mobility and exact gradient flow.
    imbalance = E_y - phi * E_i
    free_energy = imbalance**2 / 2
    gradient = sp.Matrix(
        [sp.diff(free_energy, E_y), sp.diff(free_energy, E_i)]
    )
    mobility = gamma_conv / (1 + phi) * sp.Matrix([[1, -1], [-1, 1]])
    gradient_drift = sp.simplify(-mobility * gradient)
    require_zero("gradient drift E_Y", gradient_drift[0] - drift[0])
    require_zero("gradient drift E_I", gradient_drift[1] - drift[1])

    density_mode = sp.Matrix([1, 1])
    imbalance_mode = sp.Matrix([1, -1])
    mobility_density = mobility * density_mode
    mobility_imbalance = (
        mobility * imbalance_mode
        - 2 * gamma_conv / (1 + phi) * imbalance_mode
    )
    require_zero("mobility density mode E_Y", mobility_density[0])
    require_zero("mobility density mode E_I", mobility_density[1])
    require_zero("mobility positive mode E_Y", mobility_imbalance[0])
    require_zero("mobility positive mode E_I", mobility_imbalance[1])

    dissipation = sp.simplify(gradient.dot(drift))
    require_zero(
        "free-energy dissipation identity",
        dissipation + gamma_conv * (1 + phi) * imbalance**2,
    )
    print(
        "free-energy derivative for gamma_conv >= 0: "
        f"{sp.factor(dissipation)} <= 0"
    )

    # Equal-and-opposite Markov noise preserves total density.
    noise_covariance = sp.simplify(2 * mobility)
    require_true(
        "noise covariance total-density null",
        noise_covariance * sp.Matrix([1, 1]) == sp.zeros(2, 1),
    )

    # Linearized retarded response in (rho, epsilon) coordinates.
    coordinate_map = sp.Matrix([[1, 1], [1, -phi]])
    response_generator = sp.simplify(
        coordinate_map * (gamma_conv * conversion_matrix) * coordinate_map.inv()
    )
    require_zero("rho response relaxation", response_generator[0, 0])
    require_zero(
        "epsilon response relaxation",
        response_generator[1, 1] + (1 + phi) * gamma_conv,
    )
    require_zero("response mode mixing rho-epsilon", response_generator[0, 1])
    require_zero("response mode mixing epsilon-rho", response_generator[1, 0])

    # ------------------------------------------------------------------
    # Reference state (E_Y, E_I) = (1, phi**-1) => rho = phi, eps = 0.
    q = rho**2 / (rho**2 + phi**-2 + eps**2)
    q_eq = sp.simplify(q.subs([(rho, phi), (eps, 0)]))
    require_zero("reference q exact", q_eq - phi**2 / 3)
    require_zero("reference gate exact", 1 - q_eq - phi**-2 / 3)
    print(f"q_eq(E_Y=1,E_I=phi^-1) = {sp.N(q_eq, 12)}")
    print(f"1-q_eq = {sp.N(1 - q_eq, 12)}")
    # At fixed rho=phi, positivity of both inverse densities restricts eps
    # to the closed wedge [-phi**2, phi].
    epsilon_lower = -phi**2
    epsilon_upper = phi
    E_y_ref = sp.simplify(E_y_inverse.subs(rho, phi))
    E_i_ref = sp.simplify(E_i_inverse.subs(rho, phi))
    require_zero(
        "fixed-rho lower positivity boundary E_Y",
        E_y_ref.subs(eps, epsilon_lower),
    )
    require_zero(
        "fixed-rho upper positivity boundary E_I",
        E_i_ref.subs(eps, epsilon_upper),
    )
    require_true(
        "fixed-rho positivity wedge ordered",
        bool(sp.simplify(epsilon_upper - epsilon_lower) > 0),
    )

    # R_Q is checked at analytic boundaries and at interior points only;
    # reflecting-boundary dynamics are not inferred from these identities.
    R_Q = 3 * (1 + phi**2 * eps**2) / (3 + eps**2)
    R_Q_lower = sp.simplify(R_Q.subs(eps, epsilon_lower))
    R_Q_upper = sp.simplify(R_Q.subs(eps, epsilon_upper))
    require_zero(
        "R_Q E_Y=0 boundary",
        R_Q_lower - (sp.Integer(105) + 33 * sp.sqrt(5)) / 31,
    )
    require_zero(
        "R_Q E_I=0 boundary",
        R_Q_upper - (sp.Integer(99) + 27 * sp.sqrt(5)) / 38,
    )
    print(f"R_Q boundary E_Y=0: {sp.N(R_Q_lower, 12)}")
    print(f"R_Q boundary E_I=0: {sp.N(R_Q_upper, 12)}")
    for interior_eps in (sp.Rational(-1, 2), sp.Integer(0), sp.Rational(1, 2)):
        require_true(
            f"R_Q interior point eps={interior_eps}",
            bool(
                sp.simplify(epsilon_lower < interior_eps)
                and sp.simplify(interior_eps < epsilon_upper)
            ),
        )
        print(
            f"R_Q interior eps={interior_eps}: "
            f"{sp.N(R_Q.subs(eps, interior_eps), 12)}"
        )

    # Gated conversion rate at the reference state.
    gamma_eq = sp.simplify(lam * (1 - q_eq))
    # (1 + phi) * gamma_eq = lambda/3 exactly.
    Gamma_0 = sp.simplify((1 + phi) * gamma_eq)
    require_zero(
        "reference imbalance rate Gamma_0 = lambda/3",
        Gamma_0 - lam / 3,
    )
    print(f"Gamma_0 = (1+phi)*lambda*(1-q_eq) = {sp.simplify(Gamma_0)}")

    # Small-imbalance decay: eps(t) = eps_0 * exp(-lambda t/3).
    # With diffusion the pole is -i*omega + D*k**2 + lambda/3.
    q_at_phi = sp.simplify(q.subs(rho, phi))
    q_series = sp.series(q_at_phi, eps, 0, n=3).removeO()
    q_deficit_curvature = sp.simplify(q_series.coeff(eps, 2))
    # q_deficit = q_eq - q ~ (phi**2/9) * eps**2  ==>  relaxes as exp(-2 lambda t/3).
    require_zero(
        "q deficit curvature phi**2/9",
        q_deficit_curvature + phi**2 / 9,
    )
    print("q expansion at reference state: q = phi**2/3 - (phi**2/9) eps**2 + ...")
    print("  => imbalance decays as exp(-lambda t/3); q-deficit as exp(-2 lambda t/3)")

    # Frozen unit-temperature FDT at k=0 and at the reference state. The
    # quadratic conversion availability is measured in k_B*T_bath units, so
    # the dimensionless thermal factor is one:
    # d eps = -(lambda/3) eps dt - sqrt(2 lambda/3) dW_t.
    # This stochastic check is conditional on that normalization and on a
    # Gaussian Markov conversion bath; the deterministic drift curve below
    # needs no bath.
    a_fdt = lam / 3
    b_fdt = sp.sqrt(2 * lam / 3)
    require_zero("FDT drift coefficient equals Gamma_0", a_fdt - Gamma_0)
    require_zero(
        "frozen-unit-temperature FDT normalization (b**2 = 2 a)",
        b_fdt**2 - 2 * a_fdt,
    )
    print(
        "frozen-unit-temperature FDT: "
        "d eps = -(lambda/3) eps dt - sqrt(2 lambda/3) dW_t"
    )
    # OS3 conversion noise alone has power 2*Gamma_0 at finite k. Its
    # equal-time variance is Gamma_0/(D*k**2 + Gamma_0), not 1. Full
    # equilibrium at finite k requires an additional diffusion-noise power
    # 2*D*k**2; D by itself does not determine that kernel.
    D, k, omega = sp.symbols("D k omega", nonnegative=True, real=True)
    a_k = D * k**2 + Gamma_0
    S_conversion = 2 * Gamma_0 / (omega**2 + a_k**2)
    require_zero(
        "conversion-bath Lorentzian at k=0",
        S_conversion.subs(k, 0) - 2 * Gamma_0 / (omega**2 + Gamma_0**2),
    )
    conversion_variance = sp.simplify(Gamma_0 / a_k)
    require_zero(
        "conversion-bath variance at k=0",
        conversion_variance.subs(k, 0) - 1,
    )
    print(
        "full finite-k equilibrium noise power: UNCLOSED "
        "(requires an independently specified diffusion-noise kernel)"
    )
    print(
        "finite-k conversion-only spectrum: "
        "S_eps=2*Gamma_0/(omega**2+(D*k**2+Gamma_0)**2), "
        "variance=Gamma_0/(D*k**2+Gamma_0)"
    )

    # Deterministic nonlinear instantaneous log-decay rate at fixed rho=phi.
    # It is monotone in eps**2; the physical wedge was checked above, and
    # its formal eps**2 -> infinity limit is not an allowed state.

    eps2 = sp.Symbol("eps2", positive=True)
    Gamma_nl = phi**2 * lam * (phi**-2 + eps2) / (3 + eps2)
    dGamma = sp.simplify(sp.diff(Gamma_nl, eps2))
    # dGamma/d(eps**2) = phi**2 * lambda * (3 - phi**-2) / (3 + eps**2)**2.
    # 3 - phi**-2 = 1 + phi = phi**2 > 0, so the derivative is strictly positive.
    require_zero(
        "3 - phi**-2 = phi**2 (positivity lemma)",
        sp.simplify(3 - phi**-2 - phi**2),
    )
    require_zero(
        "nonlinear Gamma derivative residue",
        sp.simplify(dGamma * (3 + eps2)**2 - phi**4 * lam),
    )
    require_true(
        "nonlinear Gamma derivative positive for lambda > 0",
        sp.simplify(dGamma).is_positive is True,
    )
    require_zero(
        "nonlinear Gamma(0) = lambda/3",
        sp.simplify(Gamma_nl.subs(eps2, 0) - lam / 3),
    )
    gamma_lower = sp.simplify(Gamma_nl.subs(eps2, phi**4) / lam)
    gamma_upper = sp.simplify(Gamma_nl.subs(eps2, phi**2) / lam)
    print(
        "nonlinear log-decay rate monotone on the physical wedge: "
        f"Gamma(0)=lambda/3, Gamma(-phi**2)/lambda={gamma_lower}, "
        f"Gamma(phi)/lambda={gamma_upper}"
    )

    # Distinguish gated from ungated: ungated Gamma = (1+phi) lambda = phi**2 lambda.
    Gamma_ungated = sp.simplify((1 + phi) * lam)
    require_zero(
        "ungated rate = phi**2 lambda",
        Gamma_ungated - phi**2 * lam,
    )
    print(f"gated Gamma_0 = lambda/3 vs ungated Gamma = phi**2 lambda")

    print("VERDICT: exact canonical reduction PASS")
    print("ALL CHECKS PASSED")


if __name__ == "__main__":
    main()
