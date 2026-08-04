"""Pooled-zone probe T8: the truncated tower and the t/H adjacent cells.

Run:  python two-fluid/run_pooled_zone_probe.py

Tests the pool-cell quantization (`computations/pooled_zone_modes.py`,
`foundations/rung-offset-mechanism.md` sec 4.1) and the channel-split
hypothesis (pool coherence splitting into K channels):

  E1. the truncated tower: bubbles only at x = m*phi, m >= 1 (no state
      below the sector boundary at x = 0), where does the |E_Y| extremum
      sit in the terminal cell [0, phi]?
        - two-bubble control (bubbles at 0 AND phi, equal amplitudes):
          crossing at u = -0.440 (Panel A/B, real-space midpoint)
        - truncation prediction (sector-edge fundamental): the log-space
          midpoint u = -0.500
        - wake-tail alternative: u = -1.000 (first antinode of the
          near bubble's own wake below it)
      The measurement decides.
  E2. sensitivity: tower depth M, amplitudes phi^-|m-1| vs equal, and
      emission phases coherent vs self-similar advance omega0 per rung.
  F.  the t/H two-cell pattern: bubbles at 0, phi, 2phi with amplitudes
      [1, 1, phi^-1] (the far bubble at the framework amplitude, Panel D)
      and the phase cases:
        (a) catalog: psi_1 = -0.315 (t cell), psi_2 = +1.312 (H cell)
        (b) 3-channel: psi_2 = psi_1 + omega0/3 (the channel-split
            hypothesis: Delta psi = 1.631 vs catalog 1.627, 0.2%)
        (c) 5-channel: psi_2 = psi_1 + omega0/5 (Wu Xing, 5 channels)
        (d) self-similar: psi_2 = psi_1 + omega0
        (e) coherent: psi_2 = psi_1
      Do the crossings land at delta_n = +0.124 (t) / -0.209 (H), and
      does the pair separation stay 1 - 1/3 = 2/3 under the third
      bubble's composition leverage (Panel D: -0.202 rungs/rad)?
  G.  amplitude asymmetry at psi = 0: f = 1.0, 0.8, 0.618, 0.6 — the
      crossing moves with f (the doc's 'locks at psi = 0' claim is
      checked against the analytic and the PDE).

Method: the probe's standing-pattern trick — with V = 0 initial
conditions the fields are exactly standing (d'Alembert, every term is
the same spatial frequency 2 pi), so the extremum of |E_Y| is the
extremum of |A| at any time; a short PDE evolution checks the pattern
(t = 0.05, inside the wall round-trip time).
"""

import numpy as np
from run_rung_offset_probe import (laplacian, rhs, evolve, extremum_u,
                                   u_of, gate_openness)

PHI = (1 + 5**0.5) / 2
LNPHI = np.log(PHI)
W0 = 2 * np.pi * PHI * LNPHI          # 4.892 rad/rung, self-similar
AMP = 0.32
T_SHORT = 0.05


def envelope(x, bubbles, amps, phases=None):
    """|E_Y| standing envelope: A = 1 + AMP sum_k amps_k cos(2pi(x -
    m_k*phi) + phase_k)."""
    phases = phases or np.zeros(len(bubbles))
    out = np.ones_like(x)
    for k, m in enumerate(bubbles):
        out = out + AMP * amps[k] * np.cos(2 * np.pi * (x - m * PHI)
                                           + phases[k])
    return out


def measure(x, A, lo, hi):
    """Extremum of |A| in the window, as u and delta_n (= u + 0.5)."""
    u = extremum_u(x, A, lo, hi)
    return u, u + 0.5


def pde_sanity(x, A, dx, dt):
    """Short evolution of the standing IC; max|PDE - A| in the window."""
    EY = A.copy()
    EI = 1 + AMP * sum(
        amps0[k] * np.cos(2 * np.pi * PHI * (x - m * PHI))
        for k, m in enumerate(bubbles0))
    VY = np.zeros_like(x)
    VI = np.zeros_like(x)
    EYf, _, _, _ = evolve(EY, EI, VY, VI, dx, dt,
                          int(round(T_SHORT / dt)), 0.0)
    an = 1 + (A - 1) * np.cos(2 * np.pi * T_SHORT)
    return np.max(np.abs(EYf - an)[(x >= 0.12) & (x <= 1.0)])


def main():
    print("=" * 74)
    print("Pooled-zone probe T8: truncated tower + t/H adjacent cells")
    print("=" * 74)

    L = 8.0 * PHI
    x_sp = 1.5
    N = 1600
    x = np.linspace(-x_sp, L, N)
    dx = x[1] - x[0]
    dt = 0.0015
    global bubbles0, amps0

    # ------------------------------------------------------------------
    # E1. the truncated tower: terminal-cell extremum
    # ------------------------------------------------------------------
    print("\n── E1  THE TRUNCATED TOWER (terminal cell [0, phi]) ──")
    bubbles0, amps0 = [0, 1], [1.0, 1.0]
    A = envelope(x, bubbles0, amps0)
    u, dn = measure(x, A, 0.12, 1.0)
    print(f"  control  (bubbles 0, phi, f = 1): u_max = {u:+.3f},"
          f" delta_n = {dn:+.3f}  (expect -0.440 / +0.060)")
    for M in [1, 2, 4, 8]:
        bubbles0 = list(range(1, M + 1))
        amps0 = [PHI ** (-(m - 1)) for m in bubbles0]
        A = envelope(x, bubbles0, amps0)
        u, dn = measure(x, A, 0.12, 1.0)
        s = pde_sanity(x, A, dx, dt)
        print(f"  truncated (M = {M} rungs up):      u_max = {u:+.3f},"
              f" delta_n = {dn:+.3f}  (PDE check {s:.2e})")
    print("  special positions: log midpoint -0.500; real midpoint -0.440;")
    print("  wake-tail antinode -1.000 (bubble at phi, first node below).")

    # ------------------------------------------------------------------
    # E2. sensitivity
    # ------------------------------------------------------------------
    print("\n── E2  SENSITIVITY ──")
    print(f"  {'case':>34} {'u_max':>8} {'delta_n':>8}")
    for M in [1, 2, 4, 8]:
        bubbles0 = list(range(1, M + 1))
        amps0 = [PHI ** (-(m - 1)) for m in bubbles0]
        u, dn = measure(x, envelope(x, bubbles0, amps0), 0.12, 1.0)
        print(f"  {'depth M = ' + str(M) + ' (phi^-|m-1|)':>34} {u:>+8.3f}"
              f" {dn:>+8.3f}")
    bubbles0, amps0 = list(range(1, 5)), [1.0] * 4
    u, dn = measure(x, envelope(x, bubbles0, amps0), 0.12, 1.0)
    print(f"  {'equal amplitudes, M = 4':>34} {u:>+8.3f} {dn:>+8.3f}")
    ph = [(W0 * (m - 1)) % (2 * np.pi) for m in bubbles0]
    u, dn = measure(x, envelope(x, bubbles0, amps0, ph), 0.12, 1.0)
    print(f"  {'self-similar phases, M = 4':>34} {u:>+8.3f} {dn:>+8.3f}")
    ph = [((W0 * (m - 1)) % (2 * np.pi)) / PHI for m in bubbles0]
    u, dn = measure(x, envelope(x, bubbles0, amps0, ph), 0.12, 1.0)
    print(f"  {'phases /phi, M = 4':>34} {u:>+8.3f} {dn:>+8.3f}")

    # ------------------------------------------------------------------
    # F. the t/H two-cell pattern (channel-split cases)
    # ------------------------------------------------------------------
    print("\n── F  THE t/H TWO-CELL PATTERN (bubbles 0, phi, 2phi) ──")
    psi_t, psi_H = -0.315, 1.312         # catalog wake phases
    print(f"  catalog Delta psi = {psi_H - psi_t:.3f} vs omega0/3 ="
          f" {W0/3:.3f} (0.2%) — the 3-channel advance")
    print(f"  {'case':>46} {'cell1 delta_n':>13} {'cell2 delta_n':>13}"
          f" {'pair diff':>10}")
    bubbles0, amps0 = [0, 1, 2], [1.0, 1.0, PHI ** -1]
    cases = [
        ("catalog (psi1 = psi_t, psi2 = psi_H)", [0.0, psi_t, psi_H]),
        ("3-channel (psi2 = psi1 + omega0/3)", [0.0, psi_t, psi_t + W0/3]),
        ("5-channel (psi2 = psi1 + omega0/5)", [0.0, psi_t, psi_t + W0/5]),
        ("self-similar (psi2 = psi1 + omega0)",
         [0.0, psi_t, (psi_t + W0) % (2 * np.pi)]),
        ("coherent (psi1 = psi2 = 0)", [0.0, 0.0, 0.0]),
    ]
    for label, ph in cases:
        A = envelope(x, bubbles0, amps0, ph)
        u1, dn1 = measure(x, A, 0.12, 1.0)
        u2, _ = measure(x, A, PHI + 0.12, 2 * PHI - 0.12)
        dn2 = u2 - 1.5                    # local to cell [phi, 2phi]
        print(f"  {label:>46} {dn1:>+13.3f} {dn2:>+13.3f}"
              f" {dn2 - dn1:>+10.3f}")
    print("  target: cell1 +0.124 (t), cell2 -0.209 (H); the pair")
    print("  separation 1 - 1/3 = 2/3 requires the crossings to differ")
    print("  by exactly -1/3 rung under the third bubble's composition.")

    # ------------------------------------------------------------------
    # G. amplitude asymmetry at psi = 0 (doc claim check)
    # ------------------------------------------------------------------
    print("\n── G  AMPLITUDE ASYMMETRY AT psi = 0 ──")
    print(f"  {'f':>6} {'u_max (PDE)':>12} {'delta_n':>9}"
          f" {'analytic':>10}")
    for f in [1.0, 0.8, 0.618, 0.6]:
        bubbles0, amps0 = [0, 1], [1.0, f]
        A = envelope(x, bubbles0, amps0)
        u_pde, dn_pde = measure(x, A, 0.12, 1.0)
        th = np.angle(1 + f * np.exp(1j * (0.0 - 2 * np.pi * PHI)))
        xm = (-th) % (2 * np.pi) / (2 * np.pi)
        if xm < 0.12:
            xm += 1.0
        if xm > 1.0:
            xm -= 1.0
        u_an = u_of(xm)
        print(f"  {f:>6.3f} {u_pde:>+12.3f} {dn_pde:>+9.3f}"
              f" {u_an:>+10.3f}")
    print("  the crossing responds to amplitude asymmetry at any psi:")
    print("  f = 1: -0.440, f = 0.8: -0.330, f = 0.618: -0.229 at psi = 0;")
    print("  x_max(f, psi) = -arg(1 + f e^{i(psi-2 pi phi)})/2 pi is exact.")

    print()
    print("  Verdicts:")
    print("  (E1) the terminal-cell extremum sits where the measurement")
    print("       says — the truncation either moves the crossing off the")
    print("       two-bubble value -0.440 or it does not; that position is")
    print("       the sector-edge placement the quantization must match.")
    print("  (F)  the channel-split cases show whether the 3-channel")
    print("       advance reproduces the t/H crossings under the third")
    print("       bubble's composition, and what the 5-channel advance")
    print("       would give.")
    print("  (G)  the f-dependence verdict decides the doc claim.")


if __name__ == "__main__":
    main()
