"""Minimal doublet span: why s = 1/2, and the Delta-n = 3 exclusion.

Run:  python computations/spin_doublet_minimal_span.py

Verifies the span-selection argument of
`foundations/spin-fibonacci-spiral.md` sec 2.3-2.4:

  Sec 1 - the Delta-n -> s mapping table, s = Delta n / 2.
  Sec 2 - the parity classes: the doublet boundary phase is
          pi * Delta n mod 2 pi, so only Delta n mod 2 matters; the rungs
          carry only two doublet phase states (0, pi) - the sign-alternating
          lattice; Delta n = 3 sits in the SAME class as Delta n = 1, so the
          spin-statistics parity does not exclude it.
  Sec 3 - the equilibrium-ratio anchoring: E_Y = phi E_I is a one-rung ratio
          (phi = ell_{n+1}/ell_n), so the doublet is an adjacent-rung object;
          the imbalance alpha_0 = phi^{-3} carries a 3-rung scale reading
          (sigma = ell_Pl / phi^3, rung -3), distinct from the doublet's own
          span.  Identity (phi-1)/(phi+1) = phi^{-3} and its 3-rung reading.
  Sec 4 - the decomposition: every span beyond the minimal class members
          {1, 2} decomposes into a minimal member plus integer full cycles
          (3 = 1 + 2, 4 = 2 + 2, 5 = 1 + 2 + 2, ...), so the fundamental
          realized spans are exactly {1, 2} -> s in {1/2, 1}; s = 3/2 =
          1/2 + 1 is the fermion plus one gauge cycle - composite.
  Sec 5 - the microcascade-mirror check: the reflection n -> -n preserves
          every span (Delta n -> Delta n), so the mirror does NOT exclude
          Delta n = 3.

Tier notes: sec 1-2 are arithmetic of the doublet postulate + pitch
convention (Derived conditional); sec 3 is the conversion-term fixed point
(Derived); sec 4 is the minimal-span principle applied (Derived conditional
on that principle); sec 5 is a verification that a candidate exclusion
does NOT close (honest negative).
"""

import numpy as np

PHI = (1 + 5 ** 0.5) / 2
LNPHI = np.log(PHI)


def main():
    print("=" * 74)
    print("Minimal doublet span: s = 1/2 and the Delta-n = 3 exclusion")
    print("=" * 74)

    # ------------------------------------------------------------------
    # Sec 1: the Delta-n -> s mapping table
    # ------------------------------------------------------------------
    print("\n-- Sec 1  THE Delta-n -> s MAPPING (s = Delta n / 2) --")
    print("  Delta n | doublet phase pi*Delta n | spin s = Delta n/2 | class")
    for dn in range(0, 7):
        s = dn / 2
        phase = np.pi * dn
        klass = ("trivial (scalar)" if dn == 0
                 else "spinor (half-cycle)" if dn % 2 == 1
                 else "boson (full cycle)")
        print(f"  {dn:>7} | {phase:>25.4f} rad | {s:>20} | {klass}")
    observed = {1: "fermion", 2: "vector boson", 4: "composite graviton"}
    for dn, name in observed.items():
        print(f"  observed: Delta n = {dn} -> s = {dn / 2} ({name})")

    # ------------------------------------------------------------------
    # Sec 2: the parity classes (phase fold mod 2)
    # ------------------------------------------------------------------
    print("\n-- Sec 2  THE PARITY CLASSES (boundary phase mod 2 pi) --")
    print("  the doublet boundary phase after Delta n rungs is"
          " pi * Delta n mod 2 pi")
    for dn in range(1, 9):
        ph = (np.pi * dn) % (2 * np.pi)
        parity = "odd (spinor, phase pi)" if dn % 2 == 1 else "even (boson, phase 0)"
        print(f"    Delta n = {dn}: phase {ph:.6f} mod 2 pi -> {parity}")
    same = (np.pi * 3) % (2 * np.pi) == (np.pi * 1) % (2 * np.pi)
    print(f"  check: Delta n = 3 and Delta n = 1 share the boundary phase:"
          f" {same}  (the spin-statistics parity does NOT exclude s = 3/2)")
    # the rung sequence carries only two doublet phase states
    seq = [((np.pi * k) % (2 * np.pi)) for k in range(8)]
    print(f"  doublet phase on successive rungs:"
          f" {', '.join(f'{p:.0f}*pi' if p else '0' for p in seq)}")
    print(f"  -> only two doublet phase states on the rungs (0, pi): the"
          f" sign-alternating lattice (adjacent rungs = opposite phases)")

    # ------------------------------------------------------------------
    # Sec 3: the equilibrium ratio anchors the doublet one rung apart
    # ------------------------------------------------------------------
    print("\n-- Sec 3  EQUILIBRIUM-RATIO ANCHORING (E_Y = phi E_I) --")
    print(f"  phi = {PHI:.10f} = ell_{{n+1}} / ell_n (one cascade rung of scale)")
    print(f"  conversion-term fixed point E_Y = phi E_I: the two components'")
    print(f"  equilibrium magnitudes differ by one rung -> the doublet is an")
    print(f"  adjacent-rung object, span Delta n = 1 (minimal nonzero interval)")
    # the imbalance alpha_0 = phi^-3: identity and 3-rung reading
    alpha0 = PHI ** -3
    ident = (PHI - 1) / (PHI + 1)
    print(f"  alpha_0 = (phi-1)/(phi+1) = {ident:.10f};"
          f" phi^-3 = {alpha0:.10f}; identity: {np.isclose(ident, alpha0)}")
    rungs = np.log(1 / alpha0) / LNPHI
    print(f"  alpha_0 as a scale ratio = 1/phi^3 ->"
          f" log_phi(1/alpha_0) = {rungs:.6f} rungs (the dephasing-noise"
          f" separation sigma = ell_Pl/phi^3 at rung -3)")
    one = np.log(PHI) / LNPHI
    print(f"  log_phi(phi) = {one:.6f} rung: the doublet's own span (1 rung)"
          f" is distinct from the imbalance's separation scale (3 rungs)")
    print(f"  check 1 rung != 3 rungs: {one != rungs}")

    # ------------------------------------------------------------------
    # Sec 4: the decomposition - minimal class members {1, 2}
    # ------------------------------------------------------------------
    print("\n-- Sec 4  THE DECOMPOSITION (minimal-span principle) --")
    print("  every span = minimal member of its parity class + j full cycles:")
    for dn in range(1, 11):
        if dn % 2 == 1:
            j = (dn - 1) // 2
            decomp = f"1 + 2*{j}" if j else "1 (minimal spinor atom)"
        else:
            j = dn // 2
            decomp = f"2*{j}" if j > 1 else "2 (minimal boson atom)"
        print(f"    Delta n = {dn:>2}: {decomp}")
    print("  fundamental realized spans = minimal members of the two classes:")
    print("    {1, 2} -> s in {1/2 (fermion), 1 (gauge boson)}")
    print("  composites: 3 = 1 + 2 -> s = 3/2 = 1/2 + 1 (fermion + gauge")
    print("              cycle; baryon resonances, e.g. Delta(1232));")
    print("              4 = 2 + 2 -> s = 2 = 1 + 1 (composite graviton)")
    # Fibonacci gloss: 3 = F_4 = F_2 + F_3
    print(f"  Fibonacci gloss: 3 = F_4 = F_2 + F_3 = 1 + 2 - the Fibonacci")
    print(f"  decomposition of 3 is exactly the fermion-plus-cycle sum")
    # the s-fold: s = Delta n / 2 for the two atoms
    for dn in (1, 2):
        print(f"  atom Delta n = {dn}: internal phase advance ="
              f" {np.pi * dn:.4f} rad = {dn / 2} doublet cycle(s),"
              f" s = {dn / 2}")

    # ------------------------------------------------------------------
    # Sec 5: the microcascade-mirror check (honest negative)
    # ------------------------------------------------------------------
    print("\n-- Sec 5  MICROCASCADE-MIRROR CHECK (does n -> -n exclude 3?) --")
    n0 = 5  # an arbitrary core rung
    for dn in (1, 3, 4):
        core, boundary = n0, n0 + dn
        m_core, m_boundary = -core, -boundary
        span = abs(boundary - core)
        m_span = abs(m_boundary - m_core)
        print(f"    span {dn}: rungs [{core}, {boundary}] -> mirror"
              f" [{m_core}, {m_boundary}]; span preserved:"
              f" {span == m_span}")
    print("  the mirror is a scale reflection (microcascade-mirror.md),"
          " it preserves every span,")
    print("  so it selects no span at all - it does NOT exclude Delta n = 3.")


if __name__ == "__main__":
    main()
