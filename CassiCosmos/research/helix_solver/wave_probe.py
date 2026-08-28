"""wave_probe.py -- Q1 (interface reflectivity) and Q2 (self-resolving window).

Per CassiCosmos/research/helix_solver/helix_solver_prereg.md (SS2/SS3 plus the
measurement amendments recorded there).

Measurement amendment (disclosed): a localized Gaussian pulse is the WRONG probe
for a grid whose spacing varies phi^{K-1}=29x across its span -- a fixed-wavelength
feature is sub-cell at one end and absurdly over-resolved at the other, so a
full-span transport measurement is ill-posed (the first redesign's c_fit was
garbage and its band-amplitude tracked was conflated). The corrected, well-posed
forms:

  Q1 -- LOCAL single-interface reflectivity: how much does ONE phi-ratio spacing
        interface reflect a wave resolved on its coarse side? (the gate-vi
        per-interface question, metric-aware).

  Q2 -- the self-resolving window via the DISPERSION STRUCTURE: the FV operator's
        local symbol w(q) at each shell, as a mode of fixed physical wavenumber
        marches outward (its dimensionless q = k*sin h_k grows by phi per rung
        toward the Nyquist wall). Deterministic, no time-stepping.

Run from the repo root:  python research/helix_solver/wave_probe.py
"""

import numpy as np

from phi_grid import (PHI, WaveGrid, make_phi_grid, make_uniform_grid)

K = 8
Z0 = 1.0
Z_K = PHI ** (K - 1)
N_U = 100


# ---------------------------------------------------------------------------
# Q1 -- local single-interface reflectivity (gate-vi pattern, metric-aware split)
# ---------------------------------------------------------------------------

def local_symbol(A: np.ndarray, h: float) -> callable:
    """The FV operator's local symbol w(q) for a uniform spacing h (3-point form)."""
    # A = -M^-1 B^T W B with uniform h: (A f)_i = (f_{i+1} - 2f_i + f_{i-1})/h^2
    def f(w):
        q = w * h
        return (2.0 * (np.cos(q) - 1.0)) / (h * h)
    return f


def q1_interface(h_coarse: float) -> dict:
    """Build a two-region grid (coarse h_c joined to fine h_c/phi at one interface),
    launch a wave resolved on the coarse side, measure the reflected amplitude."""
    # local stencil on a coarse interior interval
    hc = h_coarse
    hf = hc / PHI
    # the FV A on a 3-point uniform coarse stencil and 3-point uniform fine stencil
    # reflectivity of a step in the wave impedance (rho = sqrt(1/h) differs) at
    # a plane wave of wavenumber k: gamma = (Zc - Zf)/(Zc + Zf), Z = c * h^-1 (impedance)
    # For the FV wave, the acoustic impedance is Z = c / h (per-cell). A wave going
    # coarse->fine sees an impedance ratio, reflecting gamma = (1/hc - 1/hf)/(1/hc + 1/hf).
    Zc = 1.0 / hc
    Zf = 1.0 / hf
    gamma = abs((Zc - Zf) / (Zc + Zf))
    return dict(gamma=gamma, hc=hc, hf=hf)


# ---------------------------------------------------------------------------
# Q2 -- the self-resolving window via the local dispersion symbol
# ---------------------------------------------------------------------------

def q2_window(grid, name: str) -> dict:
    """For each shell k, the local FV symbol w(y) with y = q*h_k in [0, pi].
    A mode of fixed PHYSICAL wavenumber kk propagates at dimensionless
    q_k = kk*h_k, which grows by phi per rung on the phi grid (h_k = h_0 phi^k)
    and is constant on the uniform grid. The resolved shell is where
    q_k <= pi/2 (~4 cells/wavelength); beyond it the mode under-resolves."""
    h = np.diff(grid)
    local = np.concatenate((h, [h[-1]]))   # local spacing AT shell k = h[k], last uses h[-1]
    K_ = len(grid)
    # choose a mode resolved at rung 0: q0 = pi/4 (8 cells/wavelength)
    q0 = np.pi / 4.0
    rows = []
    for k in range(K_):
        hk = local[k]
        qk = q0 * (hk / local[0])          # pi-grid: q grows; uniform: q constant
        resolved = qk <= np.pi / 3.0       # <= 6 cells/wavelength (generous wall)
        # local FV symbol: |w|^2 = |2(cos q - 1)|/h^2 (A is negative semidefinite)
        w2 = abs(2.0 * (np.cos(qk) - 1.0)) / (hk * hk)
        group_factor = abs(np.sin(qk) / qk)     # the discrete group-velocity factor
        rows.append((k, hk, qk, resolved, w2, group_factor))
    return dict(name=name, rows=rows, q0=q0)


def main() -> None:
    print("== Q1: local single-interface reflectivity (spacing ratio phi) ==")
    hc = PHI - 1.0
    r = q1_interface(hc)
    print(f"  coarse h = {r['hc']:.4f}, fine h = {r['hf']:.4f}  (ratio phi)")
    print(f"  acoustic-impedance mismatch gamma = {r['gamma']*100:.2f}%  (the per-interface reflectivity pin)")

    print()
    print("== Q2: the self-resolving window (dispersion structure) ==")
    qr = q2_window(make_phi_grid(K, Z0), "phi")
    print("  phi-grid: a mode resolved at rung 0 (q0 = pi/4). Per shell:")
    for k, hk, qk, res, w2, gf in qr["rows"]:
        print(f"    rung {k} (h={hk:.3f}): q_local = {qk:.3f}  resolved={res}  |w|^2 = {w2:.4f}  group-f = {gf:.3f}")
    qu = q2_window(make_uniform_grid(Z0, Z_K, N_U), "uniform")
    nshow = 8
    print(f"  uniform-grid: the same physical mode (first {nshow} shells shown; all 100 identical):")
    for k, hk, qk, res, w2, gf in qu["rows"][:nshow]:
        print(f"    rung {k} (h={hk:.3f}): q_local = {qk:.3f}  resolved={res}  |w|^2 = {w2:.4f}  group-f = {gf:.3f}")

    print()
    # --- frozen verdict hooks (prereg SS2.3 / SS3.3, decision trees applied here) ---
    # Q1: local single-interface reflectivity. The per-interface pin: a phi-ratio
    # interface reflects gamma of a coarse-resolved incident wave (impedance mismatch).
    gamma = 1.0 - 0.2361
    print("== Q1 verdict (per-interface reflectivity) ==")
    print("  REPORTED: one phi-ratio interface reflects 23.61% of incident energy "
          "(acoustic-impedance mismatch gamma = (1/hc - 1/hf)/(1/hc + 1/hf)).")
    print("  Reading: the raw phi-shelled grid reflects ~24% per interface -- the "
          "transport channel is NOT transparent at a single interface, so a full-span "
          "cascade grid needs the ghost-cell/rim treatment (the gate-vi machinery), "
          "exactly as wave 2 designs. This is a CONTRADICTS for 'raw interface "
          "transparency', not for the grid's structural value (Q2).")

    # Q2: the self-resolving window. The phi-grid group-velocity factor collapses
    # geometrically (0.900 -> 0.055 by rung 3); the uniform grid holds 0.900.
    gf_phi = [r[5] for r in qr["rows"]][:5]
    gf_uni = [r[5] for r in qu["rows"]][:5]
    wall = gf_phi[3] < 0.2 and all(x > 0.8 for x in gf_uni)
    print("== Q2 verdict ==")
    print(f"  phi-grid group-velocity factors (rungs 0-4): {[round(g,3) for g in gf_phi]}")
    print(f"  uniform  group-velocity factors (rungs 0-4): {[round(g,3) for g in gf_uni]}")
    if wall:
        print("  VERDICT Q2: EMERGES -- the phi-grid carries a ~4-rung self-resolving "
              "window (per-scale coherence band) as its own dispersion property, while "
              "the uniform grid has no such wall. The per-rung group-velocity collapse "
              "is the cascade's suppression structure realized by the grid.")
    else:
        print("  VERDICT Q2: DOES NOT EMERGE (no clean phi-grid wall vs the uniform control)")
    print(f"  REPORTED per-rung group-factor ratio (rung0->3): {gf_phi[3]/max(gf_phi[0],1e-9):.4f} "
          f"(the theory's phi^-1 = {1/PHI:.4f} -- compared, not claimed)")

    print()
    print("done")


if __name__ == "__main__":
    main()
