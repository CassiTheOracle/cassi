#!/usr/bin/env python3
"""
Numerical identities for a prescribed golden loxodrome in R^3
=============================================================

This script supports `foundations/why-three-dimensions.md` by checking the
curvature, torsion, and frame identities of one explicitly chosen
three-dimensional curve. The logarithmic spiral and its cone lift are
geometric postulates for this calculation. A generalized Frenet frame in
R^d can contain up to d vectors, so these checks cannot determine the ambient
dimension and must not be cited as a proof that d = 3.

The canonical two-fluid conversion is not integrated here. Its state consists
of two real density fields; conversion conserves total density and relaxes the
derived density-plane angle toward equilibrium rather than generating a
periodic 2*pi phase clock. The retained LAM value is the asserted solver
normalization/timescale convention and is unused by the geometric checks.
The rung-clock and five-route calculations below are conditional algebraic and
model relations evaluated with an assumed d=3 continuity geometry and an
optional spiral coordinate. They are consistency checks for that construction,
not an inference of the ambient dimension.

Usage: python computations/why_three_dimensions_frenet.py
"""

import numpy as np


PHI = (1.0 + 5.0 ** 0.5) / 2.0
B = np.log(PHI) / (2.0 * np.pi)  # prescribed golden-spiral pitch
TWO_PI = 2.0 * np.pi
LAM = 0.1  # asserted solver normalization; not a geometric or dimensional input


def planar_curvature(th):
    """Planar log spiral R = exp(B*theta): return (R, kappa)."""
    R = np.exp(B * th)
    dR = B * R
    d2R = B * B * R
    x = R * np.cos(th)
    y = R * np.sin(th)
    vx = dR * np.cos(th) - R * np.sin(th)
    vy = dR * np.sin(th) + R * np.cos(th)
    ax = d2R * np.cos(th) - 2 * dR * np.sin(th) - R * np.cos(th)
    ay = d2R * np.sin(th) + 2 * dR * np.cos(th) - R * np.sin(th)
    speed = np.hypot(vx, vy)
    kappa = np.abs(vx * ay - vy * ax) / speed ** 3
    return R, kappa


def cone_loxodrome(sa, ca, th, R0=1.0):
    """Return Frenet data for the prescribed R^3 cone loxodrome.

    The curve is

        (R sin(alpha) cos(theta), R sin(alpha) sin(theta),
         R cos(alpha)),  R = R0 exp(B theta).

    The returned normal is the true Frenet normal obtained from the first two
    derivatives, not an assumed radial direction.
    """
    R = R0 * np.exp(B * th)
    dR = B * R
    d2R = B * B * R
    d3R = B ** 3 * R
    v = np.stack(
        [
            dR * sa * np.cos(th) - R * sa * np.sin(th),
            dR * sa * np.sin(th) + R * sa * np.cos(th),
            dR * ca,
        ],
        axis=-1,
    )
    a = np.stack(
        [
            d2R * sa * np.cos(th)
            - 2 * dR * sa * np.sin(th)
            - R * sa * np.cos(th),
            d2R * sa * np.sin(th)
            + 2 * dR * sa * np.cos(th)
            - R * sa * np.sin(th),
            d2R * ca,
        ],
        axis=-1,
    )
    j = np.stack(
        [
            d3R * sa * np.cos(th)
            - 3 * d2R * sa * np.sin(th)
            - 3 * dR * sa * np.cos(th)
            + R * sa * np.sin(th),
            d3R * sa * np.sin(th)
            + 3 * d2R * sa * np.cos(th)
            - 3 * dR * sa * np.sin(th)
            - R * sa * np.cos(th),
            d3R * ca,
        ],
        axis=-1,
    )
    cross = np.cross(v, a)
    speed = np.linalg.norm(v, axis=-1)
    kappa = np.linalg.norm(cross, axis=-1) / speed ** 3
    tau = np.einsum("ij,ij->i", cross, j) / np.linalg.norm(cross, axis=-1) ** 2
    T = v / speed[:, None]
    N = a - np.einsum("ij,ij->i", a, T)[:, None] * T
    N = N / np.linalg.norm(N, axis=-1, keepdims=True)
    return T, N, kappa, tau


def check_close(label, actual, expected, atol=2.0e-11):
    """Print and assert a numerical identity."""
    actual = np.asarray(actual)
    expected = np.asarray(expected)
    error = np.max(np.abs(actual - expected))
    print(f"  {label}: max abs error = {error:.2e}")
    if not np.allclose(actual, expected, rtol=2.0e-11, atol=atol):
        raise AssertionError(f"{label} failed: max abs error {error:.3e}")


def main():
    print("=" * 78)
    print("  PRESCRIBED GOLDEN LOXODROME: R^3 FRENET IDENTITIES")
    print("  (geometric consistency checks; no ambient-dimension inference)")
    print("=" * 78)

    print("\n-- A. Planar golden spiral: R = R0 exp(B theta) --")
    print(f"  phi            = {PHI:.12f}")
    print(f"  B              = {B:.12f}")
    print(f"  pitch angle    = atan(B) = {np.degrees(np.arctan(B)):.6f} deg")
    print(f"  expansion/turn = exp(2*pi*B) = {np.exp(TWO_PI * B):.12f}")

    print("\n  Curvature at exact turn crossings (theta = 2*pi*n):")
    print("      n | R            kappa         rho_c=1/kappa   R*sqrt(1+B^2)")
    for n in range(4):
        thn = np.array([TWO_PI * n])
        Rn, kn = planar_curvature(thn)
        print(
            f"      {n} | {Rn[0]:.6f}  {kn[0]:.6f}  {1 / kn[0]:.6f}"
            f"      {Rn[0] * np.sqrt(1 + B ** 2):.6f}"
        )

    th = np.linspace(0.0, 8.0 * np.pi, 16001)
    R, kappa = planar_curvature(th)
    planar_invariant = kappa * R * np.sqrt(1.0 + B ** 2)
    check_close(
        "planar kappa*R*sqrt(1+B^2) = 1",
        planar_invariant,
        np.ones_like(planar_invariant),
    )
    print("  rho_c = R*sqrt(1+B^2) = 1/kappa is the self-similar curvature radius.")
    print("  The planar torsion is zero; kappa^2 is not constant along the spiral.")

    print("\n-- B. R^3 cone loxodrome: R and z scale by phi per turn --")
    print("  kappa*R = sin(alpha)*sqrt(1+B^2)/(B^2+sin(alpha)^2)")
    print("  tau*R   = B*cos(alpha)/(B^2+sin(alpha)^2)")
    print("  tau/kappa = B*cot(alpha)/sqrt(1+B^2)")

    for alpha_deg in (30.0, 45.0, 60.0):
        alpha = np.radians(alpha_deg)
        sa, ca = np.sin(alpha), np.cos(alpha)
        th = np.linspace(0.5, 8.0 * np.pi, 8000)
        Rcurve = np.exp(B * th)
        T, N, kappa, tau = cone_loxodrome(sa, ca, th)

        expected_kappa_R = sa * np.sqrt(1.0 + B ** 2) / (B ** 2 + sa ** 2)
        expected_tau_R = B * ca / (B ** 2 + sa ** 2)
        expected_ratio = B * ca / (sa * np.sqrt(1.0 + B ** 2))
        check_close(
            f"alpha={alpha_deg:.0f} deg: kappa*R",
            kappa * Rcurve,
            expected_kappa_R,
        )
        check_close(
            f"alpha={alpha_deg:.0f} deg: tau*R",
            tau * Rcurve,
            expected_tau_R,
        )
        check_close(
            f"alpha={alpha_deg:.0f} deg: tau/kappa",
            tau / kappa,
            expected_ratio,
        )

        frame_binormal = np.cross(T, N)
        frame_error = max(
            np.max(np.abs(np.linalg.norm(T, axis=-1) - 1.0)),
            np.max(np.abs(np.linalg.norm(N, axis=-1) - 1.0)),
            np.max(np.abs(np.linalg.norm(frame_binormal, axis=-1) - 1.0)),
            np.max(np.abs(np.einsum("ij,ij->i", T, N))),
        )
        print(f"  alpha={alpha_deg:.0f} deg: Frenet-frame orthonormality error = {frame_error:.2e}")
        if frame_error > 2.0e-10:
            raise AssertionError("Frenet frame is not orthonormal")

        inward = -np.stack(
            [np.cos(th), np.sin(th), np.zeros_like(th)],
            axis=-1,
        )
        expected_tangent_z = B * ca / np.sqrt(B ** 2 + sa ** 2)
        check_close(
            f"alpha={alpha_deg:.0f} deg: tangent z component",
            T[:, 2],
            expected_tangent_z,
        )
        inward_alignment = np.einsum("ij,ij->i", N, inward)
        print(
            f"  alpha={alpha_deg:.0f} deg: <T_z> = {T[:, 2].mean():.6f}; "
            f"<N . (-r_hat)> = {inward_alignment.mean():.6f}"
        )

    print("\n-- C. Conditional rung-clock map and d=3 consistency --")
    q_gate = PHI ** -2 / 3.0  # golden gate (1 - q_0), conditional normalization
    H_empty_d3 = LAM * PHI ** -2 / 3.0
    dnS_dt = LAM / TWO_PI * q_gate
    lucas = PHI ** 2 + PHI ** -2
    fixed_excess = (PHI - 1.0) / (PHI + 1.0)
    d_map = PHI ** -2 / q_gate
    check_close("conditional Lucas identity", lucas, 3.0)
    check_close("conditional fixed-point exponent", fixed_excess, PHI ** -3)
    check_close("conditional d map", d_map, 3.0)
    print(f"  Lucas identity:    phi^2 + phi^-2 = {lucas:.15f}  (= 3 exact)")
    print(
        f"  fixed-point excess: (phi-1)/(phi+1) = {fixed_excess:.15f}  "
        f"(= phi^-3 = {PHI**-3:.15f})"
    )
    print(f"  golden gate:       (1-q_0) = phi^-2/3 = {q_gate:.12f}")
    print(
        f"                    = phi^-2/(phi^2+phi^-2) = "
        f"{PHI**-2/(PHI**2+PHI**-2):.12f} (Lucas-normalized)"
    )
    print(
        f"  H_empty (d=3)     = lambda phi^-2/3 = lambda*(1-q_0) = "
        f"{H_empty_d3:.12f}"
    )
    print(
        f"  rung-clock ratio  dn_H/dn_S = 2pi/ln(phi) = "
        f"{TWO_PI/np.log(PHI):.9f}  (13.06)"
    )
    print(
        f"  (H_empty/ln phi)/(dn_S/dt) at the golden point = "
        f"{(H_empty_d3/np.log(PHI))/dnS_dt:.9f}  [identity holds]"
    )
    print("\n  d-dimensional continuity reading (conditional on the assumed geometry):")
    print("      H_empty(d) = lambda*phi^-2/d   (two-rung suppression split over d axes)")
    print("      consistency at the golden point:  H_empty(d) = H_empty(3)")
    print(
        f"      ==>  d = phi^-2/(1-q_0) = {d_map:.15f}  "
        f"= phi^2 + phi^-2 = 3  [conditional map]"
    )
    print("  The clock-ratio form (doc sec. 7):  R(d) = (phi^2+phi^-2)/d * 2pi/ln(phi)")
    for d in (1, 2, 3, 4, 5):
        Rval = (PHI ** 2 + PHI ** -2) / d * TWO_PI / np.log(PHI)
        mark = "  <-- = 2pi/ln(phi): assumed d = 3" if d == 3 else ""
        print(f"      d={d}: R({d}) = {Rval:9.5f}{mark}")
    print(
        "  -> The clock and pitch factors cancel within the assumed d=3 map; "
        "the solver does not select ambient dimension."
    )

    print("\n-- D. Pitch-convention covariance (optional coordinate convention) --")
    print(
        "  Convention chi = 2pi*k*n (k turns per rung): both sides of the "
        "clock identity rescale identically under the selected map:"
    )
    for kk in (0.5, 1.0, 2.0):
        dns = LAM / (TWO_PI * kk) * q_gate
        target = (H_empty_d3 / np.log(PHI)) / dns
        R3 = (PHI ** 2 + PHI ** -2) / 3.0 * target
        check_close(f"k={kk:g}: pitch-covariant target=R(3)", target, R3)
        print(
            f"      k={kk:g}: target = {target:.6f}, R(3) = {R3:.6f}, "
            f"match = {abs(target - R3) < 1e-9}  -> assumed d = 3 invariant"
        )

    print("\n-- E. Five-route comparison (conditional consistency map) --")
    print(f"  (a) Lucas:          phi^2 + phi^-2 = {lucas:.12f}")
    print(f"  (b) attractor:      (phi-1)/(phi+1) = phi^-3 = {PHI**-3:.12f}")
    print(
        "  (c) noise-signal:   phi^-delta = phi^-3 -> delta = 3 "
        "(quantum-gravity sec. 2.1)"
    )
    print(f"  (d) rung-clock:     d = phi^-2/(1-q_0) = {d_map:.12f}")
    print("  (e) Frenet-Serret:  3 frame vectors of the non-degenerate R^3 curve")
    print(
        "  Routes (a)-(e) are mathematical/model relations evaluated under "
        "shared framework postulates."
    )
    print(
        "  The shared integer's identification with ambient d=3 is "
        "Hypothesized and conditional; no route independently determines space."
    )

    print("\n" + "=" * 78)
    print("  SUMMARY")
    print("  * The planar self-similar curvature-radius identity is verified.")
    print("  * The prescribed R^3 loxodrome obeys the kappa*R, tau*R, and")
    print("    tau/kappa Frenet identities for every tested cone angle.")
    print("  * The reported frame alignment belongs to the chosen R^3 embedding.")
    print("  * No quantity in this program infers or proves the ambient dimension.")
    print("  * The rung-clock and pitch-covariance values are conditional on")
    print("    the assumed d=3 continuity geometry and optional coordinate.")
    print("  * The five-route comparison is a Hypothesized consistency map,")
    print("    not an independent determination of the ambient dimension.")
    print("=" * 78)


if __name__ == "__main__":
    main()
