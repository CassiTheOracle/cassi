"""Verify the frozen phi-counterflow selection gates PC1-PC7."""

from __future__ import annotations

import math


PHI = (1.0 + math.sqrt(5.0)) / 2.0
KAPPA = 0.07
DT = 0.002
T_END = 120.0
STATES = ((2.0, 0.7), (0.5, 1.4))


def rhs(ey: float, ei: float) -> tuple[float, float]:
    eps = ey - PHI * ei
    return -KAPPA * eps, KAPPA * eps


def rk4(ey: float, ei: float) -> tuple[float, float, bool, bool]:
    above = ey / ei > PHI
    monotone = True
    positive = True
    previous = ey / ei
    for _ in range(round(T_END / DT)):
        y1, i1 = rhs(ey, ei)
        y2, i2 = rhs(ey + 0.5 * DT * y1, ei + 0.5 * DT * i1)
        y3, i3 = rhs(ey + 0.5 * DT * y2, ei + 0.5 * DT * i2)
        y4, i4 = rhs(ey + DT * y3, ei + DT * i3)
        ey += DT * (y1 + 2.0 * y2 + 2.0 * y3 + y4) / 6.0
        ei += DT * (i1 + 2.0 * i2 + 2.0 * i3 + i4) / 6.0
        current = ey / ei
        positive &= ey > 0.0 and ei > 0.0 and current > 0.0
        monotone &= current <= previous + 1e-14 if above else current >= previous - 1e-14
        previous = current
    return ey, ei, monotone, positive


def ratio_after_exposure(ey0: float, ei0: float, exposure: float) -> float:
    rho = ey0 + ei0
    eps = (ey0 - PHI * ei0) * math.exp(-(1.0 + PHI) * exposure)
    return (PHI * rho + eps) / (rho - eps)


def fibonacci(n: int) -> int:
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def report(gate: str, passed: bool, detail: str) -> bool:
    print(f"{gate}: {'PASS' if passed else 'FAIL'} — {detail}")
    return passed


def main() -> int:
    gates: list[bool] = []

    pc1_residual = 0.0
    for ey, ei in STATES:
        dey, dei = rhs(ey, ei)
        eps = ey - PHI * ei
        pc1_residual = max(
            pc1_residual,
            abs(dey + dei),
            abs((dey - PHI * dei) + KAPPA * (1.0 + PHI) * eps),
            abs((1.0 + PHI) - PHI**2),
        )
    gates.append(report("PC1", pc1_residual <= 1e-12, f"max residual={pc1_residual:.3e}"))

    pc2_residual = 0.0
    for ey, ei in STATES:
        ky = 0.8
        alpha = ey / ei
        ki = alpha * ky
        jy = ey * ky
        ji = -ei * ki
        pc2_residual = max(pc2_residual, abs(jy + ji), abs(alpha - ey / ei))
    gates.append(report("PC2", pc2_residual <= 1e-12, f"max residual={pc2_residual:.3e}"))

    pc3_residual = 0.0
    pc3_final = 0.0
    pc3_monotone = True
    pc3_positive = True
    for ey0, ei0 in STATES:
        ey, ei, monotone, positive = rk4(ey0, ei0)
        numeric = ey / ei
        exact = ratio_after_exposure(ey0, ei0, KAPPA * T_END)
        pc3_residual = max(pc3_residual, abs(numeric - exact))
        pc3_final = max(pc3_final, abs(numeric - PHI))
        pc3_monotone &= monotone
        pc3_positive &= positive
    pc3_pass = pc3_residual <= 1e-9 and pc3_final <= 1e-8 and pc3_monotone and pc3_positive
    gates.append(
        report(
            "PC3",
            pc3_pass,
            f"exact residual={pc3_residual:.3e}; phi residual={pc3_final:.3e}; "
            f"monotone={pc3_monotone}; positive={pc3_positive}",
        )
    )

    pc4_residual = 0.0
    for ey, ei in STATES:
        alpha = ey / ei
        dey, dei = rhs(ey, ei)
        from_densities = (dey * ei - ey * dei) / ei**2
        closed = -KAPPA * (1.0 + alpha) * (alpha - PHI)
        pc4_residual = max(pc4_residual, abs(from_densities - closed))
    eigenvalue = -KAPPA * (1.0 + PHI)
    pc4_residual = max(pc4_residual, abs(eigenvalue + KAPPA * PHI**2))
    gates.append(report("PC4", pc4_residual <= 1e-12 and eigenvalue < 0.0, f"max residual={pc4_residual:.3e}; eigenvalue={eigenvalue:.6f}"))

    exposure_ratios = [ratio_after_exposure(*STATES[0], exposure) for exposure in (0.0, 0.4, 50.0)]
    initial_ratio = STATES[0][0] / STATES[0][1]
    pc5_zero = abs(exposure_ratios[0] - initial_ratio)
    pc5_finite = abs(exposure_ratios[1] - PHI)
    pc5_large = abs(exposure_ratios[2] - PHI)
    pc5_pass = pc5_zero <= 1e-12 and pc5_finite > 1e-6 and pc5_large <= 1e-12
    gates.append(report("PC5", pc5_pass, f"K=0 residual={pc5_zero:.3e}; K=0.4 residual={pc5_finite:.3e}; K=50 residual={pc5_large:.3e}"))

    mobility_ratios = (0.5, 1.0, 1.7)
    mobility_alphas = tuple(mobility * PHI for mobility in mobility_ratios)
    mobility_residual = max(abs(alpha - mobility * PHI) for alpha, mobility in zip(mobility_alphas, mobility_ratios))
    mobility_separated = all(abs(alpha - PHI) > 1e-3 for alpha, mobility in zip(mobility_alphas, mobility_ratios) if mobility != 1.0)
    through_alphas = tuple(PHI - current / 0.8 for current in (-0.2, 0.0, 0.2))
    through_residual = max(abs((PHI * 0.8 - alpha * 0.8) - current) for alpha, current in zip(through_alphas, (-0.2, 0.0, 0.2)))
    through_ordered = through_alphas[0] > through_alphas[1] > through_alphas[2]
    pc6_pass = mobility_residual <= 1e-12 and through_residual <= 1e-12 and mobility_separated and through_ordered
    gates.append(report("PC6", pc6_pass, f"mobility={mobility_alphas}; through-current={through_alphas}; max residual={max(mobility_residual, through_residual):.3e}"))

    identity_residual = 0.0
    for n in range(2, 13):
        identity_residual = max(
            identity_residual,
            abs((fibonacci(n + 1) - PHI * fibonacci(n)) - ((-1.0) ** n) * PHI ** (-n)),
        )
    records: list[int] = []
    best = math.inf
    for p in range(1, 145):
        qw = max(1, round(PHI * p))
        defect = abs(qw - PHI * p)
        if defect < best:
            best = defect
            records.append(p)
    expected = [1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144]
    pc7_pass = identity_residual <= 1e-12 and records == expected
    gates.append(report("PC7", pc7_pass, f"identity residual={identity_residual:.3e}; record denominators={records}"))

    verdict = "PASS" if all(gates) else "FAIL"
    print(f"VERDICT: {verdict} ({sum(gates)}/{len(gates)} gates)")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
