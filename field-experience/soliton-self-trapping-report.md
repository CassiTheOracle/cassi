# Soliton self-trapping: Wave-0 probe report

## Status: Scientific verdict INCONCLUSIVE; protocol validity FAIL (pilot `H-DISPERSES` pattern) — 2026-08-16

## Verdict

**Scientific verdict: INCONCLUSIVE.** The available pilot exhibits a numerical
`H-DISPERSES` pattern, but it does not satisfy the frozen protocol's $N=128$
and $T\geq8$ cascade-period requirements. The theory-declared `ℒ_TF` RHS,
integrated on a real doublet `(E_Y,E_I)` with a localized winding seed
($\sigma_0=0.1$, $Q=1$), gives the following pilot observations across every
completed arm (A0–A2):

| arm | pilot pattern | R/R(0) | ΔQ | rad_frac | q_mid(t_max) |
|-----|---------|--------|-----|----------|--------------|
| A0 full (φ⁴+QP+attr) | H-DISPERSES | 1.19 | 0.9998 | 0.966 | 0.00046 |
| A1 no-φ⁴ | H-DISPERSES | 1.19 | 0.9998 | 0.966 | 0.00046 |
| A2 no-QP | H-DISPERSES | 0.85 | 0.9999995 | 0.966 | 0.00012 |

The winding charge $Q$ is destroyed to $\sim0$ and $\sim97\%$ of the
rest-mass radiates out of the $2\sigma_0$ core over $T\approx0.3$ cascade
periods (the pilot horizon). These traces are a short-horizon numerical
pattern, not a scoreable frozen `H-DISPERSES` branch or a physical negative
about the Cassi field.

## Section 1 — Frozen protocol and verified EL signs differ

The frozen pre-registration §3 PDE and the `soliton_el_verify.py` summary line
use operator signs that differ from the Euler–Lagrange equation returned by the
verified coordinate-functional calculation. The coordinate-functional checks
pass, and this probe uses:

| operator | §3 pre-reg / el_verify summary | verified EL | this probe |
|----------|-------------------------------|-------------|------------|
| hyperdiffusion | `+ ν ∇⁴` | **`− ν ∇⁴`** (check #2) | `− ν` |
| φ⁴ | `+ b\|Ψ\|²Ψ` | **`− b\|Ψ\|²Ψ`** (check #3) | `− b` |
| attractor P0 | `+ 2λ(Ψ₀²−φΨ₁²)Ψ₀` | **`− 2λ(…)Ψ₀`** (check #4) | `− 2λ` |
| attractor P1 | `− 2λφ(…)Ψ₁` | **`+ 2λφ(…)Ψ₁`** (check #4) | `+ 2λφ` |

The sign mismatch, short horizon, and pilot grid mean these observations do
not score the frozen protocol; they retain the scientific classification
**INCONCLUSIVE**.

The governing equation, transcribed with the **verified** signs, is a real,
non-conservative reaction–diffusion system:

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

The probe's nonlinear closures agree with the coordinate-FD functional
derivative of the theory action

```
L_nl = −(g/4)|Ψ|⁴ − (λ/2)(Ψ₀²−φΨ₁²)²
```

giving relative error **≤ 6e-10** on both components. The linear/hyperdiffusion
operators are spectral and exact. The numerical scheme is a **Strang-split
exponential integrator**: the stiff linear part (symbol `a(−k²) − νk⁴`, real and
≤ 0) is exponentiated exactly in Fourier space; the O(1) nonlinear terms are
RK4'd in real space between the two linear half-steps. The stiff biharmonic
operator is handled by the exponential linear step rather than an explicit
RK4 update.

## Section 3 — Numerical robustness findings (grid-robustness, per §5)

The available grid-robustness measurements are not fully converged; the
high-resolution fragility is in the nonlocal QP evaluation:

- **N=32 / N=40**: lump amplitude absorbed (amax 0.5 → ~6e-3), rad_frac ≈ 0.97.
- **N=48**: the lump **disperses** (R/R0 $\approx11$ in a separate setup;
  R/R0 $=1.19$ with verified signs and a QP floor on the smaller box; these
  setups are not pooled), rad_frac $\approx0.966$.
- **N=64**: the **Bohm-QP term NaNs** (ablations isolate `qpOnly` as the only
  blowing arm; `lin`/`f4only`/`attrOnly` are finite and mutually identical).

The N=64 blowup is a **numerical fragility of the nonlocal QP functional** at
fields approaching zero: `M^(β−1)` (β = φ⁻¹/2 ≈ 0.31, exponent −0.69) diverges
as M→0. A floor of 1e-4 + clipped inverse restores finiteness at N=64, but the
QP nonlocality makes the R-metric resolution-sensitive (whether drained mass reads as "spread R" vs "localized-but-empty" depends on grid).
Within the available 48/64 pilot runs, the stable discriminators — $\Delta Q
\to1$ and rad_frac $\to0.97$ — agree: the lump dissolves in these runs. This
pilot pattern does not score the frozen long-horizon `H-DISPERSES` branch. The
QP term needs a properly-regularized implementation (e.g. a GADGET-style
field-relative floor or a clipped $M^\beta$ ratio) before any $128^3$ claim.

## Section 4 — Ablation attribution (§6)

- **A1 (drop φ⁴) ≡ A0**: identical to ~1e-3 — at the seed amplitude the defocusing
  φ⁴ is negligible against `a∇²` (coefficient ratio ~500). φ⁴ is not the trap.
- **A2 (drop QP) ≡ A1 in verdict** (ΔQ even larger): QP does not create trapping;
  it only changes the absorption details.
- The dominant driver of the observed dispersal is the real-diffusive
  `a∇²` kinetic (present in every arm), which drives the measured loss of
  localization and winding charge.

## Section 5 — Loss-incident note

`field-experience/probe-outcome-ledger.md` is the compact index for the six
completed counterflow/source-only field experiments; it does not subsume this
Wave-0 report. This report is the source record for the Wave-0 soliton
question.

## Section 6 — Amendment 1 (2026-08-16): twist-tightness seed axis — pilot `H-DISPERSES` pattern

The amendment's seed-axis sweep uses winding number `m` (self-turns inside the
lump; $\theta=m\operatorname{atan2}(Y_c,X_c)$, A0 base, EL-verified signs,
$N=48$, $T\approx0.3$). It tests the owner hypothesis that trapping requires
the Qi spiral to close its twist tightly (a multi-scale effect). Because this
horizon is shorter than the frozen $T\geq8$ cascade-period requirement, these
values do not receive a frozen `H-DISPERSES` verdict.

| m | seed Q | R/R(0) | ΔQ | rad_frac | q_mid(t_max) | pilot pattern |
|---|--------|--------|-----|----------|--------------|---------|
| 1 | 0.77 | 1.19 | 1.0000 | 0.966 | 0.0005 | H-DISPERSES |
| 2 | 1.29 | 1.13 | 1.0000 | 0.966 | 0.0004 | H-DISPERSES |
| 4 | 2.41 | 1.15 | 1.0000 | 0.966 | 0.0004 | H-DISPERSES |
| 8 | 4.02 | 1.13 | 1.0000 | 0.966 | 0.0004 | H-DISPERSES |

**Pilot pattern.** Closing the twist (seed $Q$ $0.77\to4.02$) does **not**
produce a bounded lump in these short-horizon runs: $\Delta Q\to1$ and
rad_frac $\to0.966$ in every case. The steepened phase gradient strengthens
the Bohm-QP term in the seed, but the full real-doublet evolution (including
QP) has no explicitly conservative/dispersive mechanism to convert that phase
energy into a stable barrier.
These observations indicate that the next registered test needs both the
multi-scale twist and a dispersive
(Schrödinger $i\partial_t$ / two-fluid sign-symmetric KE) base; they do not
establish a physical negative or confirm a soliton-free field.

## Next steps

1. **Add a dispersive/conservative base** (the theory's Schrödinger+QP reduction
   — $i\partial_t$, or the two-fluid sign-symmetric KE) and re-probe. The
   Amendment 1 pilot suggests that neither the loose ($m=1$) nor the
   tightly-closed twist ($m=4,8$) traps under the frozen real-dissipative
   equation, because no conservative term carries the twist (phase) energy.
   The next probe adds the dispersive base and the multi-scale twist together,
   rather than tuning the seed alone.
2. **Regularize the QP nonlocal term** before any 128³ run (field-relative
   floor / clipped ratio) — §3.
3. Grid-robust re-run at 96³/192³ **only** once (1)+(2) land; the current
   equation is not resolution-stable as posed.
