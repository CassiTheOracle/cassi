"""N_pde bridge check: does the Dirac↔two-fluid sector-coupling chi bridge close?

Run:  python computations/n_pde_bridge_check.py

Gap P42 (`parameter-inventory.md` sec 3.3, `foundations/sector-coupling-derivation.md`
sec 4): the chemotactic mobility chi must land in [0.5, 1.0].  The as-written bridge

    chi = kappa_s * phi^-1 / [m_e (1+phi)]          kappa_s = phi^-6 / v0^2

gives chi ~ 4.25e-4, three orders below the calibrated band.  The documented repair
inserts the PDE normalization factor N_pde ~ 2.35e3, "the number of field samples",
from "solver conventions (grid L=40, N=48, dt=0.002, rho_crit=phi)".

This script recomputes N_pde from the solver code itself, rather than taking the
doc's number:

  - `two-fluid/cassi_two_fluid_3d_gpu.py`:
      * TwoFluid3DGPU.__init__  (line 44):  defaults N=64, L=2*pi; dx = L/N (line 49)
      * ExpandingTwoFluid3DGPU.__init__ (line 308): rho_crit = PHI by default
      * _poisson (lines 117-124): Phi_k = -rho_hat_k / (k^2 * v^2)  -- the v0^2
        normalization lives in the Poisson solve
      * rhs() chemotaxis (lines 189-195): d_t E_I  +=  +chi * div(E_I grad Phi)
      * run scripts use N=48, dt=0.001, L=2*pi (e.g. run_churning_gate.py);
        the documented L=40, dt=0.002 set appears in NO run script
        (universal_cassi_solver.py has L=20, dt=0.002)
  - `two-fluid/cassi_bridge_v2.py`:
      * CassiBridgeV2.__init__ (line 117):  defaults grid=64, L=20
      * potential (line 585):  denom = v2_k * k2_safe, v2_k = v0^2 * (...)^(...)
        (line 190) -- the same v0^2 Poisson normalization
      * initial_cosmos (line 991): "Normalize to total mass = box volume"

The literal number of field samples a snapshot holds is N^3 (3D cells); a 2D
section holds N^2.  The verdict below: N^3 overshoots the calibrated band by
~47x, N^2 = 2304 lands in band at chi = 0.980 (a -2.0% residual), and the exact
closure value 2350.7 = m_e * v0^2 * phi^9 [GeV^3] is a rearrangement of the
bridge constants -- not a grid count -- so the four named conventions do not
pin N_pde.
"""

import ast
from pathlib import Path

import numpy as np

PHI = (1.0 + np.sqrt(5.0)) / 2.0

# ─── Physical constants (foundations/sector-coupling-derivation.md) ───────
V0 = 246.0            # GeV, electroweak VEV
M_E = 5.1099895e-4    # GeV, electron mass
KAPPA_S = PHI ** -6 / V0 ** 2     # 9.209e-7 GeV^-2 = 0.92 TeV^-2

CHI_BAND = (0.5, 1.0)


def read_solver_defaults():
    """Extract the solver's grid conventions from the source, not the docs.

    Returns (L, N, rho_crit, v0) as written in the code defaults, with the
    source line numbers.
    """
    src = (Path(__file__).resolve().parents[1]
           / "two-fluid" / "cassi_two_fluid_3d_gpu.py").read_text(encoding="utf-8")
    tree = ast.parse(src)

    def init_defaults(cls_name):
        for node in ast.walk(tree):
            if not (isinstance(node, ast.ClassDef) and node.name == cls_name):
                continue
            for stmt in node.body:
                if (isinstance(stmt, ast.FunctionDef) and stmt.name == "__init__"):
                    return stmt.args.defaults, stmt.args.args, stmt.lineno
        raise KeyError(cls_name)

    dfl, args, ln = init_defaults("TwoFluid3DGPU")
    arg_names = [a.arg for a in args[-len(dfl):]]

    def const_eval(node):
        """Evaluate simple default expressions (2.0*np.pi etc.)."""
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -const_eval(node.operand)
        if isinstance(node, ast.BinOp):
            a, b = const_eval(node.left), const_eval(node.right)
            if isinstance(node.op, ast.Mult):
                return a * b
            if isinstance(node.op, ast.Div):
                return a / b
            if isinstance(node.op, ast.Add):
                return a + b
            if isinstance(node.op, ast.Sub):
                return a - b
        if isinstance(node, ast.Attribute) and node.attr == "pi":
            return np.pi
        raise ValueError(node)

    vals = {}
    for name, d in zip(arg_names, dfl):
        try:
            vals[name] = const_eval(d)
        except ValueError:
            pass
    N_code, L_code = vals["N"], vals["L"]

    dfl2, args2, ln2 = init_defaults("ExpandingTwoFluid3DGPU")
    arg_names2 = [a.arg for a in args2[-len(dfl2):]]
    rho_crit_code = PHI  # default expression is the module constant PHI (line 308)
    return (L_code, N_code, rho_crit_code, ln, ln2)


def chi_of(n_pde):
    """Repaired bridge: chi = N_pde * kappa_s * phi^-1 / [m_e (1+phi)]."""
    return n_pde * KAPPA_S * PHI ** -1 / (M_E * (1.0 + PHI))


def main():
    print("=" * 74)
    print("N_pde bridge check: kappa_s -> chi normalization (gap P42)")
    print("=" * 74)

    # ── Sec 1: the as-written bridge ─────────────────────────────────────
    print("\n── Sec 1  THE AS-WRITTEN BRIDGE (N_pde = 1) ──")
    chi_raw = chi_of(1.0)
    print(f"  kappa_s = phi^-6/v0^2        = {KAPPA_S:.6e} GeV^-2 "
          f"({KAPPA_S * 1e6:.4f} TeV^-2)")
    print(f"  m_e     = {M_E:.6e} GeV   v0 = {V0} GeV")
    print(f"  chi(N_pde=1) = {chi_raw:.6e}   "
          f"-> {chi_raw * 1e4:.4f} x 1e-4 (doc: 4.25e-4)")
    print(f"  calibrated band: {CHI_BAND[0]} .. {CHI_BAND[1]}   "
          f"shortfall factor {1.0 / chi_raw:.2e}")

    # ── Sec 2: the solver's real conventions ─────────────────────────────
    print("\n── Sec 2  SOLVER CONVENTIONS, READ FROM CODE ──")
    L_code, N_code, rho_crit_code, ln_2f, ln_exp = read_solver_defaults()
    # Documented convention set (parameter-inventory.md sec 3.3)
    L, N, DT, RHO_CRIT = 40.0, 48.0, 0.002, PHI
    print(f"  documented set (inventory sec 3.3): L={L:g}, N={N}, "
          f"dt={DT}, rho_crit={RHO_CRIT:.6f}")
    print(f"  code defaults (cassi_two_fluid_3d_gpu.py:"
          f"{ln_2f}, :{ln_exp}):       L={L_code:g}, N={N_code}, "
          f"rho_crit={rho_crit_code:.6f} (=PHI)")
    print(f"  run scripts: N=48, dt=0.001, L=2*pi (run_churning_gate.py); "
          f"L=40 / dt=0.002 appear in no run script")
    print(f"  Poisson normalization (v0^2 in the kernel): "
          f"cassi_two_fluid_3d_gpu.py:121-124, "
          f"cassi_bridge_v2.py:190,585-586")
    dx = L / N
    print(f"  dx = L/N = {dx:.6f}   dV = dx^3 = {dx**3:.6f}   "
          f"box volume L^3 = {L**3:.6g}")
    print(f"  field samples per snapshot: N^3 = {N**3:.6g} (3D cells), "
          f"N^2 = {N**2:.6g} (2D section)")

    # ── Sec 3: N_pde candidates and the recomputed chi ───────────────────
    print("\n── Sec 3  N_pde CANDIDATES AND CHI ──")
    n_pde_exact = 1.0 / chi_raw          # required for chi = 1.0000
    print(f"  N_pde required for chi = 1.0000 : {n_pde_exact:.2f}   "
          f"(doc: ~2.35e3)")
    print(f"  exact closure factor: m_e*v0^2*phi^9 = "
          f"{M_E * V0**2 * PHI**9:.2f} GeV^3 "
          f"(= 1/chi_raw, a constant rearrangement -- the bridge "
          f"then reduces to chi = kappa_s*v0^2*phi^6 = 1 by construction)")

    rows = [
        ("N^3 (3D field samples)", N ** 3),
        ("N^2 (2D section samples)", N ** 2),
        ("N(N+1)", N * (N + 1.0)),
        ("1/dt * phi^3 (rate x rho^3)", 1.0 / DT * PHI ** 3),
        ("doc value 2.35e3", 2.35e3),
        ("exact closure m_e v0^2 phi^9", M_E * V0 ** 2 * PHI ** 9),
    ]
    print(f"\n  {'candidate':<34s}{'N_pde':>12s}{'chi':>12s}{'band':>7s}"
          f"{'resid vs 1':>12s}")
    for name, n_pde in rows:
        ch = chi_of(n_pde)
        in_band = CHI_BAND[0] <= ch <= CHI_BAND[1]
        print(f"  {name:<34s}{n_pde:>12.4g}{ch:>12.6f}"
              f"{'  YES' if in_band else '  no '}"
              f"{100.0 * (ch - 1.0):>11.2f}%")

    # Code-default grid (N=64) for contrast: does the reading survive?
    ch_n2_64 = chi_of(N_code ** 2)
    print(f"\n  (contrast) code-default grid N={N_code}: "
          f"N^2 = {N_code**2} -> chi = {ch_n2_64:.4f} "
          f"({'in band' if CHI_BAND[0] <= ch_n2_64 <= CHI_BAND[1] else 'OUT of band'})")

    # Monomial scan over the four documented quantities
    print("\n  nearest monomials in {L, N, dt, rho_crit} to the exact "
          "closure value:")
    base = {"L": L, "N": N, "dt": DT, "rho": RHO_CRIT}
    hits = []
    for name, b in base.items():
        for e in range(-4, 5):
            v = b ** e
            hits.append((abs(np.log(v / n_pde_exact)), f"{name}^{e}"))
    for a1, b1 in base.items():
        for a2, b2 in base.items():
            for e1 in range(-3, 4):
                for e2 in range(-3, 4):
                    v = b1 ** e1 * b2 ** e2
                    hits.append((abs(np.log(v / n_pde_exact)),
                                 f"{a1}^{e1}*{a2}^{e2}"))
    for err, name in sorted(hits)[:3]:
        print(f"    {name:<14s}  log-err {err:.4f}")

    # ── Sec 4: verdict ───────────────────────────────────────────────────
    print("\n── Sec 4  VERDICT ──")
    chi_3d = chi_of(N ** 3)
    chi_2d = chi_of(N ** 2)
    print(f"  literal field-sample count N^3 = {N**3:.6g}: "
          f"chi = {chi_3d:.4f} -- OUT of band (47x above 1.0)")
    print(f"  2D section count N^2 = {N**2:.6g}: "
          f"chi = {chi_2d:.4f} -- IN band [0.5, 1.0], "
          f"residual {100.0 * (chi_2d - 1.0):+.2f}%")
    print(f"  exact closure needs N_pde = {n_pde_exact:.1f} = "
          f"m_e*v0^2*phi^9 GeV^3, which is a rearrangement of the bridge "
          f"constants,")
    print(f"  not a function of L, N, dt, rho_crit: no monomial in the four "
          f"documented conventions")
    print(f"  reproduces it (nearest: N^2, 2.0% low).  The v0^2 factor does "
          f"trace to a code")
    print(f"  convention -- the Poisson kernel "
          f"(cassi_two_fluid_3d_gpu.py:121-124, denom = k2 * v2; "
          f"cassi_bridge_v2.py:585-586) --")
    print(f"  but the grid parameters do not enter at all.")
    print()
    if CHI_BAND[0] <= chi_2d <= CHI_BAND[1]:
        print("  RESULT: with N_pde = N^2 = 2304 the bridge lands IN the "
              "calibrated band,")
        print("          chi = 0.980, with a -2.0% residual against chi = 1.0; "
              "the -2.0% is the")
        print("          leftover after the repair.  With the literal "
              "3D sample count N^3")
        print("          the bridge does NOT close (chi = 47).")
    print()


if __name__ == "__main__":
    main()
