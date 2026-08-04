"""Mode quantization of the pooled two-fluid zone.

Run:  python computations/pooled_zone_modes.py

The energy pools of elementary particles are the constructive-overlap
cells of the rotating Yang/Yin wake pair (`foundations/wake-geometry.md`
sec 2): the two wakes cos(2 pi x/ell_n) and cos(2 pi phi x/ell_n) are
the two phases of one string motion, their product is the beat envelope
with zeros (voids) at x = (m+1/2) ell_{n+1}, and the two-bubble crossing
sits at x_max = phi/2 - psi/(4 pi) (`two-fluid/run_rung_offset_probe.py`
Panel B).  A particle is a standing mode of the pool cell; the mode
quantization is the closure of the wave on the cell.

  Sec 1 — the pool cell and its exact special positions (Derived).
  Sec 2 — the standing modes of the cell: the two parities (Derived).
  Sec 3 — the catalog reading: sector edges vs interior states
          (Empirical, selection Hypothesized).
  Sec 4 — the top/Higgs 2/3-rung as a phase-rung structure (open).
"""

import numpy as np

PHI = (1 + 5**0.5) / 2
LNPHI = np.log(PHI)
M_PL = 1.220890e19          # GeV
W0 = 2 * np.pi * PHI * LNPHI            # 4.8922 rad/rung, Yin wake
A0 = 0.5 + (1 - np.log(2) / LNPHI)      # = 1.5 - log_phi 2 = 0.05958
B0 = 1.0 / W0                           # = 0.20441


def n_of(m):
    return np.log(M_PL / m) / LNPHI


def main():
    print("=" * 74)
    print("Pooled-zone mode quantization: standing modes of the overlap cell")
    print("=" * 74)

    # ------------------------------------------------------------------
    # Sec 1: the pool cell and its special positions
    # ------------------------------------------------------------------
    print("\n── Sec 1  THE POOL CELL (Derived) ──")
    print("  The wake pair cos(2pi x/ell_n) + cos(2pi phi x/ell_n) has beat")
    print("  envelope zeros (voids) at x = (m+1/2) ell_{n+1}; the two-bubble")
    print("  pattern's amplitude peaks at the crossing between adjacent")
    print("  bubbles, x_max = phi/2 - psi/(4 pi).")
    u_cross = 1 - np.log(2) / LNPHI
    print(f"  coherent crossing: u(phi/2) = 1 - log_phi 2 = {u_cross:.4f}")
    print(f"  (0.06 rungs above the naive half-rung -0.5; the 3% near-miss")
    print(f"   scale of the mass catalog)")
    print(f"  intercept A0 = 0.5 - u(phi/2) = 1.5 - log_phi 2 = {A0:.5f}")
    print(f"  slope     B0 = 1/(2 pi phi ln phi) = {B0:.5f} = 1/omega0")
    print(f"  omega0 = 2 pi phi ln phi = {W0:.4f} rad/rung (self-similar")
    print("  Yin wake, wake-geometry.md sec 3b)")
    print("  the PDE-measured relation delta_n(psi) = A0 - B0 psi")
    print("  (probe Panel B, verified to 1e-3 rungs) is the exact")
    print("  linearization of u(x_max(psi)) - u(phi/2) + A0: A0 and B0")
    print("  are analytic, not fit coefficients.")
    # linearization check: du/dx at phi/2 times -psi/(4 pi)
    slope = 2 / (PHI * LNPHI) / (4 * np.pi)
    print(f"  check: du/dx|_(phi/2) * (-1/(4 pi)) = -{slope:.5f} = -B0")

    # ------------------------------------------------------------------
    # Sec 2: the standing modes of the cell
    # ------------------------------------------------------------------
    print("\n── Sec 2  THE STANDING MODES (Derived) ──")
    print("  The pool cell [n, n+1] in rung space: the boundaries are the")
    print("  voids (envelope zeros) — the overlap vanishes there, so the")
    print("  field closes with nodes at both cell ends.")
    print("  sine parity   psi_1(u) = sin(pi (u - n)):")
    print("    nodes at n and n+1, antinode at the midpoint n + 1/2 —")
    print("    the crossing/Yin phase; the sector-edge states (e, tau, b,")
    print("    pi, p/n, Lambda_QCD, d sit at the half-rung of their cell).")
    print("  cosine parity psi_2(u) = cos(pi (u - n)):")
    print("    antinodes at the integer rungs — the bubble/Yang phase;")
    print("    the interior stable states (mu, J/psi, D, Sigma, Z).")
    print("  The half-rung is not a free position: it is the antinode of")
    print("  the fundamental mode of the terminal cell — the only mode")
    print("  with a single antinode at the midpoint.  Higher modes")
    print("  sin(m pi (u-n)) put antinodes at n + k/m, not at the")
    print("  midpoint.")
    # antinode positions for the first modes
    for m in [1, 2, 3]:
        uu = np.linspace(0, 1, 4001)
        amp = np.abs(np.sin(m * np.pi * uu))
        an = [(2*k + 1) / (2*m) for k in range(m)]
        print(f"    sin({m} pi (u-n)): antinodes at {an}")

    # ------------------------------------------------------------------
    # Sec 3: the catalog reading
    # ------------------------------------------------------------------
    print("\n── Sec 3  THE CATALOG READING (Empirical) ──")
    print("  Sector edges (lightest state of each terminated tower), with")
    print("  the half-rung of their frame:")
    # (name, rung, half-rung, frame note)
    edges = [
        ("e",    np.log(174.104 / 0.00051099895) / LNPHI, 26.5, "Yukawa"),
        ("tau",  np.log(174.104 / 1.77686) / LNPHI, 9.5, "Yukawa"),
        ("b",    np.log(174.104 / 2.86) / LNPHI + np.log(0.991881) / LNPHI,
         8.5, "top-anchored"),
        ("pi",   n_of(0.13957039), 95.5, "Compton"),
        ("p,n",  n_of(0.9383), 91.5, "Compton"),
        ("d",    n_of(0.0047), 102.5, "Compton"),
        ("L_QCD", n_of(0.213), 94.5, "Compton"),
    ]
    print(f"  {'state':>7} {'rung':>8} {'half-rung':>10} {'resid':>8}"
          f" {'frame':>14}")
    resids = []
    for name, n, half, frame in edges:
        r = n - half
        resids.append(abs(r))
        print(f"  {name:>7} {n:>8.2f} {half:>10.1f} {r:>+8.3f} {frame:>14}")
    print(f"  mean |residual| = {np.mean(resids):.3f} rungs (uniform"
          f" baseline 0.25);")
    print("  every edge sits within 0.08 rungs of its half-rung; the")
    print("  lepton frame entries are the same half-rungs as the")
    print("  top-anchored ladder of sm-radiative-corrections.md sec 6.3")
    print("  (b: 8.5 +1.0%, tau: 9.5 +0.5%, e: 26.5 -2.1%).")
    print("  Interior stable states at integer rungs (bubble parity):")
    for name, m in [("mu", 0.1056583755), ("J/psi", 3.0969),
                    ("D", 1.86484), ("Sigma", 1.192642), ("Z", 91.1876)]:
        n = n_of(m)
        print(f"    {name:>6}: n = {n:.3f}  (integer {round(n)},"
              f" resid {n - round(n):+.3f})")
    print("  The muon is the dual-citizen: 96.000 (Compton, sharpest")
    print("  placement in the catalog) and 15.39 (Yukawa frame, the")
    print("  most-resistant half-rung of the ladder).  The frame choice")
    print("  is not settled by the quantization; the dual placement is")
    print("  a real tension to report, not to smooth over.")

    # ------------------------------------------------------------------
    # Sec 4: the top/Higgs 2/3-rung as a phase-rung structure
    # ------------------------------------------------------------------
    print("\n── Sec 4  THE TOP/HIGGS 2/3-RUNG (open structure) ──")
    n_t, n_H = n_of(172.69), n_of(125.25)
    dn_t, dn_H = (n_t % 1) - 0.5, (n_H % 1) - 0.5
    psi_t = (A0 - dn_t) / B0
    psi_H = (A0 - dn_H) / B0
    print(f"  n_t = {n_t:.3f} (delta_n = {dn_t:+.3f} from 80.5),"
          f" psi_t = {psi_t:+.3f} rad")
    print(f"  n_H = {n_H:.3f} (delta_n = {dn_H:+.3f} from 81.5),"
          f" psi_H = {psi_H:+.3f} rad")
    dpsi = psi_H - psi_t
    print(f"  Delta psi = {dpsi:.3f} rad  vs  omega0/3 = {W0/3:.3f} rad"
          f"  ({100*(dpsi/(W0/3)-1):+.2f}%)")
    print(f"  -> n_H - n_t = 1 - Delta psi/omega0 = 1 - 1/3 = 2/3:")
    print(f"     the 2/3-rung separation is one full cell minus exactly")
    print(f"     one third of a phase-rung.  The 1/3 has no mechanism")
    print(f"     yet — it is the open structure of the Higgs chain.")
    print(f"  observation (not a claim): psi_t + psi_H ="
          f" {psi_t + psi_H:.3f} ~ 1 rad.")
    print()
    print("  Verdict: the pool-cell quantization is derived (Sec 1-2);")
    print("  the identification of the catalog's sector edges with the")
    print("  fundamental sine modes is Hypothesized (the catalog")
    print("  statistics of rung-offset-mechanism.md sec 3 remain the")
    print("  honest baseline); the 1/3 phase-rung of the t/H pair is")
    print("  open.")

    # ------------------------------------------------------------------
    # Sec 5: the channel-split hypothesis (K = 3 and K = 5)
    # ------------------------------------------------------------------
    print("\n── Sec 5  THE CHANNEL-SPLIT HYPOTHESIS (K = 3, K = 5) ──")
    print()
    print("  K = 3 (the EW-scale pool splits into three coherence")
    print("  channels): the t/H wake phases differ by")
    print(f"      Delta psi = psi_H - psi_t = {psi_H - psi_t:.3f} rad")
    print(f"      vs omega0/3 = {W0/3:.3f} rad"
          f"  ({100*(1-(psi_H-psi_t)/(W0/3)):+.2f}%)")
    print("  the 2/3-rung separation is one cell minus one channel:")
    print("  n_H - n_t = 1 - Delta psi/omega0 = 1 - 1/3 = 2/3.")
    print("  The third channel is empty: psi_3 = psi_H + omega0/3 =")
    print(f"  {psi_H + W0/3:+.2f} rad implies frac"
          f" {(A0 - (psi_H + W0/3)/W0) % 1:.3f} — no EW state sits there")
    print("  (Z 0.951, W 0.213, t 0.624, H 0.291).")
    print()
    print("  K = 5 (Wu Xing — the pentagon; the top's Yukawa is the")
    print("  five-cycle gap 2g - g^2): five channels, phase advance")
    print(f"  omega0/5 = {W0/5:.4f} rad per channel; fifths grid in")
    print("  frac: {0.2, 0.4, 0.6, 0.8} plus the integers (0/5).")
    # the Compton-frame catalog (rung-offset-mechanism.md sec 3) + v0 + GUT
    catalog = [
        ("t", 172.69), ("H", 125.25), ("Z", 91.1876), ("W", 80.369),
        ("Ups", 9.46030), ("Bc", 6.27447), ("Lb", 5.6196),
        ("Bs", 5.36688), ("B", 5.27934), ("b", 4.18), ("psi2S", 3.68610),
        ("J/psi", 3.0969), ("Lc", 2.28646), ("Ds", 1.96835),
        ("D", 1.86484), ("tau", 1.77686), ("Om", 1.67245),
        ("Xi*", 1.5318), ("Sig*", 1.3837), ("Xi", 1.31486), ("c", 1.27),
        ("Del", 1.232), ("Sig", 1.192642), ("Lam", 1.115683),
        ("phi", 1.019461), ("eta'", 0.95778), ("n", 0.939565),
        ("p", 0.938272), ("om", 0.78265), ("rho", 0.77526),
        ("eta", 0.547862), ("K", 0.493677), ("pi", 0.13957039),
        ("mu", 0.1056583755), ("s", 0.093), ("d", 0.00467),
        ("u", 0.00216), ("e", 0.00051099895),
    ]
    ns = [("v0", n_of(246.0)), ("GUT", n_of(1.0e16))]
    for name, m in catalog:
        ns.append((name, n_of(m)))
    fifths = [0.2, 0.4, 0.6, 0.8, 0.0]
    hits = []
    print(f"  fifths scan over {len(ns)} states (catalog + v0 + GUT):")
    print(f"  {'state':>7} {'n':>9} {'frac':>7} {'5th':>5} {'resid':>7}")
    for name, n in ns:
        frac = n % 1.0
        best, br = None, 9.0
        for f in fifths:
            r = min(abs(frac - f), 1 - abs(frac - f))
            if r < br:
                best, br = f, r
        mark = " *" if br < 0.03 else ""
        if br < 0.03:
            hits.append((name, n, best, br))
        print(f"  {name:>7} {n:>9.3f} {frac:>7.3f} {best:>5.1f}"
              f" {br:>+7.3f}{mark}")
    print(f"  within 0.03 rungs of a fifth: {len(hits)} observed;"
          f" uniform expectation {0.3*len(ns):.1f} (each state has"
          f" 2*0.03/0.2 = 0.3 probability)")
    for lab, f, nm in [("0/5", 0.0, "mu"), ("1/5", 0.2, "W"),
                       ("2/5", 0.4, "pi"), ("3/5", 0.6, "t"),
                       ("4/5", 0.8, "GUT")]:
        m = [h for h in hits if abs(h[2] - f) < 1e-9]
        print(f"  {lab}: {', '.join(h[0] for h in m) if m else 'empty'}"
              + (f" (GUT at 0.0302 — just outside)" if lab == "4/5"
                 and not m else ""))
    print("  Look-elsewhere discipline: the named states were selected")
    print("  after the pattern emerged; the overall count shows no")
    print("  fifths clustering, and the energy ordering fails (pi, mu")
    print("  are low-energy). The K = 5 structure is a curiosity, not")
    print("  evidence; the K = 3 advance (0.2%) remains the only")
    print("  channel-split support.")
    print()
    print("  Transition-zone reading (the five-fold as the pole structure):")
    print("  the EW scale is interior to the universe bubble (rung ~80 of")
    print("  285); the half-rungs (K=2 checkerboard) and the K=3 EW pool")
    print("  are interior structures.  The five-fold belongs to the")
    print("  transitions: the top closure (the ladder starts at 5 — the")
    print("  pentagon; 285 = 5x57, the Cassi bubble on a five-arm closure")
    print("  boundary) and the bottom — the Planck transition, where a new")
    print("  bubble starts down the cascade.  Transition band (rungs 0-17):")
    for name, m in [("M_Pl", 1.220890e19),
                    ("reduced M_Pl", 1.220890e19 / np.sqrt(8 * np.pi)),
                    ("GUT 1e16", 1.0e16), ("GUT 3e15", 3.0e15),
                    ("GUT 3e16", 3.0e16)]:
        nn = n_of(m)
        frac = nn % 1.0
        br = min(min(abs(frac - f), 1 - abs(frac - f))
                 for f in [0.2, 0.4, 0.6, 0.8, 0.0])
        print(f"    {name:>12}: n = {nn:7.2f}, frac {frac:.3f},"
              f" nearest fifth resid {br:+.3f}")
    print("  the only fifth candidate in the band is the GUT scale at")
    print("  14.77 = 14 + 4/5 (resid 0.0302, 1.5% in scale — borderline;")
    print("  the GUT band 10^15.5-10^16.5 spans rungs 12.4-17.2, so the")
    print("  4/5 position lies inside the uncertainty band).")
    print()
    print("  Verdict: the channel-split hypothesis is Hypothesized —")
    print("  K = 3 matches the t/H phase difference to 0.2% but the")
    print("  coherent 3-bubble pattern does not reproduce the crossings")
    print("  (probe T8 panel F); K = 5 has no interior footprint (10 vs")
    print("  12 expected), which is the expected reading if the five-fold")
    print("  is a transition structure: the top transition already shows")
    print("  it (285 = 5x57), and the bottom-transition probe (the GUT at")
    print("  4/5) is borderline, not a hit.")
    print()


if __name__ == "__main__":
    main()
