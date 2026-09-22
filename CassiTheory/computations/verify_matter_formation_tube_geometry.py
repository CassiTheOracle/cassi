#!/usr/bin/env python3
"""Independent verification of the field-tube geometry receipt.

The verifier never imports the producer.  It reads the frozen receipt, rebuilds the
cross-section and its metric on its own grid, and re-derives every number with its own
quadrature, its own functional assembly and a finite-difference stationarity test.

    python computations/verify_matter_formation_tube_geometry.py --receipt <receipt.json>
    python computations/verify_matter_formation_tube_geometry.py --receipt <receipt.json> --mutation

Exit status is 0 only when every check passes.  --mutation perturbs one stored profile
sample and requires the stationarity check to fail, which shows the checks can fire.

Model (registered matter-formation functional):

    E = int [ (1/2)|grad f|^2 + (K_Cx/2)|grad c|^2 + (u_rho/4)(f^2-1)^2
              + (B - h + h f^2)|c|^2 + (u_C/2)|c|^4 ] d^3x,     K_Cx = 1,

with vacuum boundary values f -> 1 and c -> 0 on the last face.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np

SCHEMA = "matter-formation-tube-geometry-v2"
TORUS_AMAX = 6.0
TORUS_NPHI = 64


def radial_grid(M: int, rmax: float):
    dr = rmax / M
    r = (np.arange(M) + 0.5) * dr
    rf = (np.arange(M) + 1.0) * dr
    rfm = np.concatenate([[0.0], rf[:-1]])
    return dr, r, rf, rfm


def energy_radial(f, c, coef, M, rmax):
    """Verifier's own assembly of the radial functional (its own quadrature weights)."""
    dr, r, rf, _ = radial_grid(M, rmax)
    fe = np.concatenate([f, [1.0]])
    ce = np.concatenate([c, [0.0]])
    v = (coef["u_rho"] / 4.0 * (f * f - 1.0) ** 2
         + (coef["B"] - coef["h"] + coef["h"] * f * f) * c * c
         + coef["u_C"] / 2.0 * c ** 4)
    e = 2.0 * math.pi * float(np.sum(r * dr * v))
    e += 2.0 * math.pi * coef["grad_f"] * float(np.sum(rf * dr * ((fe[1:] - fe[:-1]) / dr) ** 2))
    e += 2.0 * math.pi * coef["grad_c"] * float(np.sum(rf * dr * ((ce[1:] - ce[:-1]) / dr) ** 2))
    return e


def energy_simpson(f, c, coef, M, rmax):
    """Same functional, different quadrature: composite Simpson on the cell centres."""
    dr, r, rf, _ = radial_grid(M, rmax)
    fe = np.concatenate([f, [1.0]])
    ce = np.concatenate([c, [0.0]])

    def simp(x, y):
        n = x.size
        if n % 2 == 0:
            x, y = x[:-1], y[:-1]
            n -= 1
        return float(dr / 3.0 * (y[0] + y[-1] + 4.0 * y[1:-1:2].sum() + 2.0 * y[2:-2:2].sum()))

    v = (coef["u_rho"] / 4.0 * (f * f - 1.0) ** 2
         + (coef["B"] - coef["h"] + coef["h"] * f * f) * c * c
         + coef["u_C"] / 2.0 * c ** 4)
    e = 2.0 * math.pi * simp(r, r * v)
    e += 2.0 * math.pi * coef["grad_f"] * simp(rf, rf * ((fe[1:] - fe[:-1]) / dr) ** 2)
    e += 2.0 * math.pi * coef["grad_c"] * simp(rf, rf * ((ce[1:] - ce[:-1]) / dr) ** 2)
    return e


def population(f_unused, c, M, rmax):
    dr, r, _, _ = radial_grid(M, rmax)
    return float(2.0 * math.pi * np.sum(r * dr * c * c))


def stationarity(f, c, coef, M, rmax):
    """Finite-difference energy gradient of the verifier's own functional.

    Reported in units of the profile's own scale, so the number is a genuine measure of
    how close the stored profile is to a stationary point of the continuum functional.
    """
    dr, r, _, _ = radial_grid(M, rmax)
    h = 1e-6
    e0 = energy_radial(f, c, coef, M, rmax)
    gf = np.zeros(M)
    gc = np.zeros(M)
    for i in range(M):
        fp = f.copy()
        fp[i] += h
        gf[i] = (energy_radial(fp, c, coef, M, rmax) - e0) / h
        cp = c.copy()
        cp[i] += h
        gc[i] = (energy_radial(f, cp, coef, M, rmax) - e0) / h
    # a stationary profile satisfies dE/dx = mu dN/dx for one common mu; report the residual
    # of that overdetermined system, scaled by the gradient magnitude.
    dN = 4.0 * math.pi * r * dr * c
    v = np.concatenate([gf, gc])
    w = np.concatenate([np.zeros(M), dN])
    mu = float(np.dot(v, w) / max(np.dot(w, w), 1e-300))
    resid = v - mu * w
    return float(np.max(np.abs(resid)) * dr / max(abs(e0), 1e-300)), mu


def torus_weights(Na, amax, Nphi, kappa):
    """Verifier's own metric assembly for the bent cross-section."""
    da = amax / Na
    dphi = 2.0 * math.pi / Nphi
    a = (np.arange(Na) + 0.5) * da
    phi = np.arange(Nphi) * dphi
    af = np.arange(1, Na + 1) * da
    A = a[:, None]
    P = phi[None, :]
    Pf = P + 0.5 * dphi
    g = np.maximum(1.0 + kappa * A * np.cos(P), 0.0)
    VC = A * g * da * dphi
    gf = np.maximum(1.0 + kappa * af[:, None] * np.cos(P), 0.0)
    Fa = np.zeros((Na + 1, Nphi))
    Fa[1:] = af[:, None] * gf * dphi / da
    Fp = np.maximum(1.0 + kappa * A * np.cos(Pf), 0.0) * da / (A * dphi)
    return a, phi, da, dphi, VC, Fa, Fp, g


def energy_torus(f, c, coef, kappa, w, R, Na, amax, Nphi):
    _, _, _, _, VC, Fa, Fp, g = torus_weights(Na, amax, Nphi, kappa)
    ip = np.empty_like(f)
    ip[:-1] = f[1:]
    ip[-1] = 1.0
    jp = np.roll(f, -1, axis=1)
    grad_f = float(np.sum(Fa[1:] * (ip - f) ** 2) + np.sum(Fp * (jp - f) ** 2))
    cip = np.empty_like(c)
    cip[:-1] = c[1:]
    cip[-1] = 0.0
    cjp = np.roll(c, -1, axis=1)
    grad_c = float(np.sum(Fa[1:] * (cip - c) ** 2) + np.sum(Fp * (cjp - c) ** 2))
    tw = (coef["grad_c"] * w * w / R ** 2) / np.maximum(g, 1e-12) ** 2
    dens = ((coef["u_rho"] / 4.0) * (f * f - 1.0) ** 2
            + (coef["B"] - coef["h"] + coef["h"] * f * f) * c * c
            + (coef["u_C"] / 2.0) * c ** 4 + tw * c * c)
    return float(np.sum(VC * dens) + coef["grad_f"] * grad_f + coef["grad_c"] * grad_c)


def axisymmetric_profile(r_src, f_src, c_src, a, phi, kappa, target_population, Na, amax, Nphi):
    """Rebuild the axisymmetric cross-section from the stored radial profile."""
    rp = np.sqrt(np.maximum(a[:, None] ** 2 - 2 * a[:, None] * 0.0 * np.cos(phi[None, :]), 0.0))
    f = np.interp(rp, r_src, f_src, left=f_src[0], right=1.0)
    c = np.maximum(np.interp(rp, r_src, c_src, left=c_src[0], right=0.0), 0.0)
    _, _, _, _, VC, _, _, _ = torus_weights(Na, amax, Nphi, kappa)
    pop = float(np.sum(VC * c * c))
    c = c * math.sqrt(target_population / max(pop, 1e-300))
    return f, c


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--receipt", required=True)
    ap.add_argument("--mutation", action="store_true",
                    help="perturb one stored profile sample and require a failure")
    args = ap.parse_args()

    path = Path(args.receipt)
    receipt = json.loads(path.read_text())
    checks: list[tuple[str, bool, str]] = []

    def record(name, ok, detail):
        checks.append((name, bool(ok), detail))
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: {detail}")

    print("=" * 78)
    print(f"Independent verification of {path.name}")
    print("=" * 78)

    # V0 schema and content digest
    record("V0.1 receipt schema", receipt.get("schema") == SCHEMA,
           f"schema {receipt.get('schema')!r}")
    body = {k: v for k, v in receipt.items() if k != "content_sha256"}
    digest = hashlib.sha256(json.dumps(body, indent=1, sort_keys=True).encode()).hexdigest()
    record("V0.2 content digest reproduces", digest == receipt.get("content_sha256"),
           f"recomputed {digest[:16]}... against {str(receipt.get('content_sha256'))[:16]}...")

    coef = receipt["coefficients"]
    flat = receipt["flat"]
    M = int(flat["M"])
    rmax = float(flat["r"][-1] + 0.5 * (flat["r"][1] - flat["r"][0]))
    r_src = np.asarray(flat["r"], dtype=float)
    f_src = np.asarray(flat["f_profile"], dtype=float)
    c_src = np.asarray(flat["c_profile"], dtype=float)
    if args.mutation:
        f_src = f_src.copy()
        f_src[M // 2] += 1e-3

    # V1 the stored profile is a stationary point of the continuum functional
    grad, mu = stationarity(f_src, c_src, coef, M, rmax)
    record("V1.1 the stored profile is stationary (finite-difference gradient)",
           grad < 2e-3, f"scaled gradient residual {grad:.2e} (dr = {rmax / M:.4f})")
    record("V1.2 the stationarity residual is charge-consistent",
           abs(mu - flat["stationary_multiplier"]) < 0.05 * abs(flat["stationary_multiplier"]) + 0.05,
           f"verifier multiplier {mu:.6f} against receipt {flat['stationary_multiplier']:.6f}")

    # V2 the reported energy and population reproduce
    e_trap = energy_radial(f_src, c_src, coef, M, rmax)
    e_simp = energy_simpson(f_src, c_src, coef, M, rmax)
    pop = population(None, c_src, M, rmax)
    record("V2.1 the energy reproduces in the verifier's quadrature",
           abs(e_trap - flat["energy"]) < 1e-6 * abs(flat["energy"]),
           f"{e_trap:.9f} against receipt {flat['energy']:.9f}")
    record("V2.2 a second quadrature agrees to discretization accuracy",
           abs(e_simp - e_trap) < 2e-3 * abs(e_trap),
           f"Simpson {e_simp:.9f} against trapezoid {e_trap:.9f} "
           f"({100 * abs(e_simp / e_trap - 1.0):.4f}%)")
    record("V2.3 the population reproduces",
           abs(pop - flat["linear_density"]) < 1e-6 * flat["linear_density"],
           f"{pop:.9f} against receipt {flat['linear_density']:.9f}")
    record("V2.4 the per-charge energy reproduces",
           abs(e_trap / pop - flat["E_per_population"]) < 1e-6 * flat["E_per_population"],
           f"{e_trap / pop:.9f} against receipt {flat['E_per_population']:.9f}")

    # V3 the bending identity on the verifier's own grid
    Na, amax, Nphi = 128, TORUS_AMAX, TORUS_NPHI
    ref_rows = {row["R"]: row["dE_cross"] for row in receipt["bending_identity"]}
    devs = []
    for R in sorted(ref_rows):
        kappa = 1.0 / R
        a, phi, *_ = torus_weights(Na, amax, Nphi, kappa)
        f_k, c_k = axisymmetric_profile(r_src, f_src, c_src, a, phi, kappa, pop, Na, amax, Nphi)
        a0, phi0, *_ = torus_weights(Na, amax, Nphi, 0.0)
        f_0, c_0 = axisymmetric_profile(r_src, f_src, c_src, a0, phi0, 0.0, pop, Na, amax, Nphi)
        e0 = energy_torus(f_0, c_0, coef, 0.0, 0.0, 1.0, Na, amax, Nphi)
        devs.append((R, energy_torus(f_k, c_k, coef, kappa, 0.0, R, Na, amax, Nphi) - e0))
    worst = max(abs(d) for _, d in devs)
    record("V3.1 the untwisted bent tube costs no energy (verifier's own grid)",
           worst < 1e-9, f"max |dE| = {worst:.2e} over R = {max(ref_rows):g} ... {min(ref_rows):g}")
    record("V3.2 the receipt reports the same identity",
           max(abs(v) for v in ref_rows.values()) < 1e-9,
           f"receipt max |dE_cross| = {max(abs(v) for v in ref_rows.values()):.2e}")

    # V4 the twist energy equals the metric-weighted phase-gradient integral
    twist_rows = {row["R"]: row for row in receipt["twist"]}
    ratios = []
    for R in sorted(twist_rows):
        kappa = 1.0 / R
        a, phi, _, _, VC, _, _, g = torus_weights(Na, amax, Nphi, kappa)
        f_k, c_k = axisymmetric_profile(r_src, f_src, c_src, a, phi, kappa, pop, Na, amax, Nphi)
        unwound = energy_torus(f_k, c_k, coef, kappa, 0.0, R, Na, amax, Nphi)
        wound = energy_torus(f_k, c_k, coef, kappa, 1.0, R, Na, amax, Nphi)
        quad = coef["grad_c"] / R ** 2 * float(np.sum(VC * c_k * c_k / np.maximum(g, 1e-12) ** 2))
        ratios.append((R, wound - unwound, quad))
    worst_tw = max(abs(m / q - 1.0) for _, m, q in ratios)
    record("V4.1 the winding raises the energy by the phase-gradient integral",
           worst_tw < 1e-9,
           "measured/quadrature: " + ", ".join(f"R={R:g}: {m / q:.12f}" for R, m, q in ratios))
    enh = {R: row["metric_enhancement"] for R, row in twist_rows.items()}
    by_R = sorted(enh)
    record("V4.2 the metric enhancement grows as the torus tightens",
           all(enh[R] > 1.0 for R in enh)
           and all(enh[by_R[i]] > enh[by_R[i + 1]] for i in range(len(by_R) - 1)),
           "enhancement: " + ", ".join(f"R={R:g}: {enh[R]:.6f}" for R in by_R))
    lead = {R: row["measured"] / row["leading"] for R, row in twist_rows.items()}
    record("V4.3 the leading law is approached as curvature vanishes",
           abs(lead[max(lead)] - 1.0) < 1e-2 and lead[min(lead)] > lead[max(lead)],
           "measured/leading: " + ", ".join(f"R={R:g}: {lead[R]:.6f}" for R in sorted(lead)))

    # V5 the strong-density rows carry the flat-top surface term
    strong = receipt["strong"]
    gaps = {}
    for key, row in strong.items():
        n = float(key)
        e = energy_radial(np.asarray(row["f_profile"], dtype=float),
                          np.asarray(row["c_profile"], dtype=float), coef, M, rmax)
        p = population(None, np.asarray(row["c_profile"], dtype=float), M, rmax)
        record(f"V5.0 n={n:g} energy reproduces",
               abs(e / p - row["E_per_charge"]) < 1e-6 * abs(row["E_per_charge"]),
               f"verifier {e / p:.6f} against receipt {row['E_per_charge']:.6f}")
        gaps[n] = e / p - ((coef["B"] - coef["h"]) + 0.5 * math.sqrt(2.0 * coef["u_C"] * coef["u_rho"]))
    scaled = {n: gaps[n] * math.sqrt(n) for n in gaps}
    spread = max(scaled.values()) / min(scaled.values())
    record("V5.1 the residual gap is the interface surface term (gap*sqrt(n) constant)",
           spread < 1.05,
           "gap*sqrt(n): " + ", ".join(f"n={n:g}: {scaled[n]:.4f}" for n in sorted(scaled)))

    # V6 the mode ladder
    modes = receipt["modes"]
    soft = abs(modes["1"]["relative_min"])
    others = min(modes[str(m)]["relative_min"] for m in (2, 3, 4))
    record("V6.1 the translation mode is soft against the others", soft < 0.2 * abs(others),
           f"m=1 {modes['1']['relative_min']:+.2e} versus {others:+.2e}")
    record("V6.2 the non-translation modes are positive",
           all(modes[str(m)]["min"] > 0.0 and modes[str(m)]["negative"] == 0 for m in (2, 3, 4)),
           "minima " + ", ".join(f"m={m}: {modes[str(m)]['min']:.4f}" for m in (2, 3, 4)))
    record("V6.3 the angular stiffness rises with m",
           modes["2"]["min"] < modes["3"]["min"] < modes["4"]["min"],
           f"m=2 {modes['2']['min']:.4f} < m=3 {modes['3']['min']:.4f} < m=4 {modes['4']['min']:.4f}")

    # V7 the critical window
    crit = receipt["critical"]
    lo, hi = receipt["critical_window"]
    below = [row for key, row in crit.items() if float(key) <= lo]
    above = [row for key, row in crit.items() if float(key) >= hi]
    per_charge = lambda row: row["E_per_population"]
    record("V7.1 the carrier is unbound at and below the lower edge",
           all(per_charge(row) >= coef["B"] for row in below),
           f"{len(below)} scanned densities at or below {lo:g} sit at or above B "
           f"(smallest margin {min(per_charge(r) for r in below) - coef['B']:+.2e})")
    record("V7.2 a bound tube exists at and above the upper edge",
           all(per_charge(row) < coef["B"] for row in above),
           f"{len(above)} scanned densities at or above {hi:g} sit below B "
           f"(smallest margin {coef['B'] - max(per_charge(r) for r in above):+.2e})")
    record("V7.3 the window is a genuine bracket", lo < hi and hi - lo < 0.1,
           f"critical linear density in ({lo:.4f}, {hi:.4f})")

    failed = [name for name, ok, _ in checks if not ok]
    print("\n" + "=" * 78)
    if args.mutation:
        fired = [name for name in failed if name.startswith("V1.1")]
        print(f"mutation control: {len(failed)} checks failed, stationarity fired: {bool(fired)}")
        if fired:
            print("MUTATION DETECTED AS REQUIRED")
            return 0
        print("MUTATION NOT DETECTED")
        return 1
    print(f"{len(checks) - len(failed)}/{len(checks)} checks passed")
    if failed:
        for name in failed:
            print(f"  FAILED: {name}")
        print("NOT ALL CHECKS PASSED")
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
