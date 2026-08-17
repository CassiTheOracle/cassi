# Soliton self-trapping: Wave-0 probe report

## Status: NULL (probe verdict INCONCLUSIVE→H-DISPERSES) — 2026-08-16

## Verdict

**H-DISPERSES.** The theory-declared `ℒ_TF` RHS, integrated on a real doublet
`(E_Y,E_I)` with a localized winding seed (σ₀ = 0.1, Q = 1), **does not
self-trap in the frozen O(1) regime.** Across every completed arm (A0–A2):

| arm | verdict | R/R(0) | ΔQ | rad_frac | q_mid(t_max) |
|-----|---------|--------|-----|----------|--------------|
| A0 full (φ⁴+QP+attr) | H-DISPERSES | 1.19 | 0.9998 | 0.966 | 0.00046 |
| A1 no-φ⁴ | H-DISPERSES | 1.19 | 0.9998 | 0.966 | 0.00046 |
| A2 no-QP | H-DISPERSES | 0.85 | 0.9999995 | 0.966 | 0.00012 |

The winding charge Q is destroyed to ~0 and ~97% of the rest-mass radiates out
of the 2σ₀ core in every arm, over T ≈ 0.3 cascade periods (the pilot horizon).
No arm retains a localized, phase-coherent lump.

## Section 1 — The frozen protocol's operator signs are off from the verified EL

This probe's primary scientific yield is an **audit finding**: the frozen
pre-registration §3 PDE and the `soliton_el_verify.py` summary line carry
operator signs that **disagree with the Euler–Lagrange equation actually
verified numerically** in the same repo. `soliton_el_verify.py` checks (all
`OK`, coordinate-functional variation) and this probe's independent
verification (§2) give:

| operator | §3 pre-reg / el_verify summary | verified EL | this probe |
|----------|-------------------------------|-------------|------------|
| hyperdiffusion | `+ ν ∇⁴` | **`− ν ∇⁴`** (check #2) | `− ν` |
| φ⁴ | `+ b\|Ψ\|²Ψ` | **`− b\|Ψ\|²Ψ`** (check #3) | `− b` |
| attractor P0 | `+ 2λ(Ψ₀²−φΨ₁²)Ψ₀` | **`− 2λ(…)Ψ₀`** (check #4) | `− 2λ` |
| attractor P1 | `− 2λφ(…)Ψ₁` | **`+ 2λφ(…)Ψ₁`** (check #4) | `+ 2λφ` |

The governing equation, transcribed with the **verified** signs, is a purely
dissipative real reaction–diffusion:

```
∂t Ψ0 = a·∇²Ψ0 − ν·∇⁴Ψ0 − b|Ψ|²Ψ0 − 2λ(Ψ₀²−φΨ₁²)Ψ0 − Q_B0
∂t Ψ1 = a·∇²Ψ1 − ν·∇⁴Ψ1 − b|Ψ|²Ψ1 + 2λφ(Ψ₀²−φΨ₁²)Ψ1 − Q_B1
```

There is **no conservative (symplectic / non-dissipative) term** in this
frozen real-doublet reduction: the kinetic is real-diffusive (`a∇²`),
hyperdiffusion damps, and the φ⁴ is defocusing. A phase-coherent soliton
requires a dispersive (Schrödinger-type `i∂t`, or a two-fluid sign-symmetric KE)
base to balance. That base is **absent** from the frozen equation, so dispersal
is the structurally expected outcome. The null is attributable to the missing
dispersive/conservative mechanism — **not** to a global "the Cassi field has no
soliton" claim (§7 guard).

## Section 2 — Probe implements the verified EL

The probe's nonlinear closures were independently re-verified here against the
coordinate-FD functional derivative of the theory action

```
L_nl = −(g/4)|Ψ|⁴ − (λ/2)(Ψ₀²−φΨ₁²)²
```

giving relative error **≤ 6e-10** on both components. The linear/hyperdiffusion
operators are spectral and exact. The numerical scheme is a **Strang-split
exponential integrator**: the stiff linear part (symbol `a(−k²) − νk⁴`, real and
≤ 0) is exponentiated exactly in Fourier space; the O(1) nonlinear terms are
RK4'd in real space between the two linear half-steps. This removes the
biharmonic stiffness that made the earlier explicit-RK4 formulation blow up.

## Section 3 — Numerical robustness findings (grid-robustness, per §5)

The pilot's grid-robustness sweep is **not fully converged**, and the cause is
identified:

- **N=32 / N=40**: lump amplitude absorbed (amax 0.5 → ~6e-3), rad_frac ≈ 0.97.
- **N=48**: lump **disperses** (R/R0 ≈ 11 at N=48 earlier; 1.19 with the corrected
  signs+QP-floor on the smaller box), rad_frac ≈ 0.966.
- **N=64**: the **Bohm-QP term NaNs** (ablations isolate `qpOnly` as the only
  blowing arm; `lin`/`f4only`/`attrOnly` are finite and mutually identical).

The N=64 blowup is a **numerical fragility of the nonlocal QP functional** at
fields approaching zero: `M^(β−1)` (β = φ⁻¹/2 ≈ 0.31, exponent −0.69) diverges
as M→0. A floor of 1e-4 + clipped inverse restores finiteness at N=64, but the
QP nonlocality makes the R-metric resolution-sensitive (whether drained mass
reads as "spread R" vs "localized-but-empty" depends on grid). The **stable
discriminators — ΔQ → 1 and rad_frac → 0.97 — agree across 48/64**: the lump
dissolves. The QP term needs a properly-regularized implementation (e.g. a
GADGET-style field-relative floor or a clipped `M^β` ratio) before any 128³
claim.

## Section 4 — Ablation attribution (§6)

- **A1 (drop φ⁴) ≡ A0**: identical to ~1e-3 — at the seed amplitude the defocusing
  φ⁴ is negligible against `a∇²` (coefficient ratio ~500). φ⁴ is not the trap.
- **A2 (drop QP) ≡ A1 in verdict** (ΔQ even larger): QP does not create trapping;
  it only changes the absorption details.
- The dominant driver of dispersal is the **real-diffusive `a∇²`** kinetic
  (present in every arm), which irreversibly dissolves the lump and destroys Q.

## Section 5 — Loss-incident note

`probe-outcome-ledger.md` (referenced by the recovered taijitu doc) was an
untracked file lost in the earlier `rm -rf` deletion; it is **not** on the
remote and **not** restored. This report supersedes its role for the Wave-0
soliton question.

## Section 6 — Amendment 1 (2026-08-16): twist-tightness seed axis — H-DISPERSES

Per the pre-reg §10 amendment, the seed was re-run with winding number `m`
(self-turns inside the lump; `θ = m·atan2(Y_c,X_c)`, A0 base, EL-verified signs,
N=48, T≈0.3). Tests the owner hypothesis that trapping requires the Qi spiral
to close its twist tightly (a multi-scale effect).

| m | seed Q | R/R(0) | ΔQ | rad_frac | q_mid(t_max) | verdict |
|---|--------|--------|-----|----------|--------------|---------|
| 1 | 0.77 | 1.19 | 1.0000 | 0.966 | 0.0005 | H-DISPERSES |
| 2 | 1.29 | 1.13 | 1.0000 | 0.966 | 0.0004 | H-DISPERSES |
| 4 | 2.41 | 1.15 | 1.0000 | 0.966 | 0.0004 | H-DISPERSES |
| 8 | 4.02 | 1.13 | 1.0000 | 0.966 | 0.0004 | H-DISPERSES |

**Attribution.** Closing the twist (seed Q 0.77→4.02) does **not** trap the
dispersion: ΔQ→1, rad_frac→0.966 in every case. The steepened phase gradient
strengthens the Bohm-QP term in the seed, but the frozen equation has **no
conservative/dispersive mechanism to convert that phase energy into a stable
barrier** — the real `a∇²` + `−ν∇⁴` + defocusing φ⁴ is purely dissipative, so
the twist energy radiates regardless of m. The trap needs **both** the
multi-scale twist (the owner's localizing structure) **and** a dispersive
(Schrödinger `i∂t` / two-fluid sign-symmetric KE) base to carry it — the base
is what §3 omits. This converts the next step from a seed tweak into the
amendment that adds the dispersive term (§ next steps).

## Next steps

1. **Add a dispersive/conservative base** (the theory's Schrödinger+QP reduction
   — `i∂t`, or the two-fluid sign-symmetric KE) and re-probe. The §6 twist test
   confirms this is the load-bearing amendment: neither the loose (m=1) nor the
   tightly-closed twist (m=4,8) traps, because the frozen real-dissipative
   equation has no conservative term to carry twist (phase) energy. The next
   probe adds the dispersive base AND the multi-scale twist together, per the
   owner's hypothesis, rather than tuning the seed alone.
2. **Regularize the QP nonlocal term** before any 128³ run (field-relative
   floor / clipped ratio) — §3.
3. Grid-robust re-run at 96³/192³ **only** once (1)+(2) land; the current
   equation is not resolution-stable as posed.
