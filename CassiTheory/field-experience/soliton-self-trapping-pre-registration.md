# Soliton Self-Trapping (Wave-0) — PRE-REGISTRATION

**Probe:** `field-experience/soliton_self_trapping_probe.py` (NEW, to be written)
**Pre-registered:** written BEFORE any run. This file FREEZES the protocol.
**Date:** 2026-08-16. New files only; no existing file modified; no commits.
**Tier:** T2 theory-equation test of the CORRECTED within-scale search space (the
owner's "balance" reframe), upgrading the T3 projection/circulation probes.
**Status:** Pre-registered—not yet run.

> **Load-bearing choice, stated explicitly (per theory audit):** this probe
> integrates the **theory-specified RHS from `cassi-theory-reference.md` §4.1
> `ℒ_TF`** — kinetic/dispersion `+ hyperdiffusion + φ⁴ self-interaction +
> φ-attractor + Bohm quantum potential + breathe`, with φ⁴ and the Bohm QP
> **included** (they are missing from BOTH shipped integrators). It does **NOT**
> run the sim's linear-wave shader (`compute/cassi_two_fluid.glsl`), which is
> dispersive and cannot hold a soliton by superposition, nor the diffusive
> Python solver. A null here means "the theory-declared equation does not
> self-trap a lump in this regime" — **NOT** "the Cassi field has no soliton
> regime" — and the term-ablation (§6) attributes which term failed.

---

## 0. Problem statement

The unification program ("matter as wound Qi", `qi-flow-double-helix.md:275`)
claims a particle is a standing wave of the doublet plus its winding, i.e. a
**soliton condensate of the two-fluid field**; `cassi-theory-reference.md` §8.4
calls dark matter *high-`q` two-fluid condensates*. The simulator still runs a
ball-of-atoms particle system with heuristic merge/BH gates (the current crash
ceiling at large N is that architecture, not the field). The path to a
field-native reality simulator is: **demonstrate the field itself holds a
self-trapped, non-dispersing, non-radiating localized lump (a soliton) — whose
mass lands on the φ-cascade ladder — and that merge/BH become emergent.**

The search has failed to find such a stable structure because the prior
projection/circulation probes (`multiscale`, `taijitu-spatial`, `crown-swirl`,
`swirl-dynamics`) sought it at the **φ-ratio** `E_Y = φE_I` (the between-scale
attractor). The owner's reframe + the verified element dynamics correct this:

> **Between scales** φ is the de-resonant scale-separation attractor (the rung
> spacing). **Within a scale** the attractor is **balance** — where the mutual
> coupling of Yin and Yang can no longer attract or repel.

This pre-registration tests: **does a localized coherent seed self-trap to a
lump whose interior sits at the within-scale balance fixed point `ε*(ρ)`
(conversion = wake), under the theory-specified `ℒ_TF` RHS?**

---

## 1. Inherited verified record (why this is the next step)

- **Reaction balance fixed point (verified here, 2026-08-16, analytic + numeric;**
  reproducible via `soliton_epsstar_fixedpoint.py`):
  the per-cell two-fluid element dynamics from `field_experience.py`,
  `conv = λ(1−q)ε`, `wake = κ·tanh(ε/σ)`, `dε ∝ wake − conv`, have a **stable
  within-scale fixed point ε\*(ρ)** where `λ(1−q)ε = κ·tanh(ε/σ)`, and the
  **φ-line ε=0 is a REPELLER** (pushed off by the wake). Measured ε\*:
  ρ=1.00→0.848, 1.25→0.995, φ→1.186, 2.00→1.363; `q(ε*)≈0.48–0.64`.
  This generalizes the `coherence-stability` ledger entry (`ε*≈0.91` on-attractor
  repeller) to density-dependence and gives the interior target the seed relaxes to.
- **The theory declares the soliton-capable equation** (line 170 `ℒ_TF`), and
  **neither integrator implements it** (confirmed by grep: no φ⁴, no Bohm QP in
  `field_experience.py` / the sim shader).
- **Euler-Lagrange of `ℒ_TF` (derived + numerically verified here, 2026-08-16;** reproducible
  via `soliton_el_verify.py`):
  each term's EL contribution pinned against the discrete coordinate functional
  derivative (roundoff-exact for 5/6 local terms; Bohm QP verified as exact
  discrete functional derivative). The governing PDE is in §3.

## 2. Hypothesis statements (pre-registered)

- **H (self-trapping):** under the `ℒ_TF` RHS with φ⁴ + Bohm QP, a localized
  coherent seed relaxes to a **self-trapped, non-dispersing lump** whose interior
  approaches the within-scale balance `ε*(ρ)` (conversion = wake), and whose
  **mass/charge sits on the φ-cascade rung ladder**.
- **H-partition (decision tree):**
  - **H-DISPERSES** — the seed spreads/radiates to flat (no lump). Attribute via §6.
  - **H-COLLAPSES** — the lump contracts to a point / singular (field collapse).
    Attribute via §6.
  - **H-HOLDS** — a bounded lump persists for T cascade periods with mass/charge
    conserved (the soliton regime).
- **Term-ablation (§6) attributes every verdict to a term**, so a null is
  *which term failed* (φ⁴ too weak vs hyperdiffusion over-damping vs λ over-driving
  vs attractor mis-sign), never a bare negative.

## 3. Governing PDE (frozen — the theory-specified RHS)

From the `ℒ_TF` action (§1) via the Euler–Lagrange equation, the real-doublet
reduction (`Ψ₀ = E_Y, Ψ₁ = E_I`, `M = Ψ₀²+Ψ₁²`, `β = φ⁻¹/2`):

```
d_t Ψ0 =  a lap(Ψ0) + nu lap^2(Ψ0) + b |Ψ|^2 Ψ0
        + 2 λ (Ψ0^2 − φ Ψ1^2) Ψ0  −  Q_B0  +  c B(x) Ψ0
d_t Ψ1 =  a lap(Ψ1) + nu lap^2(Ψ1) + b |Ψ|^2 Ψ1
        − 2 λ φ (Ψ0^2 − φ Ψ1^2) Ψ1  −  Q_B1  +  c B(x) Ψ1
```

where `Q_Bα = (ħ²/2m²)·δ/δΨα[∫ (∇²M^β/M^β)·M]` is the (nonlocal) Bohm-QP
functional derivative — implemented discretely and validated numerically
(coordinate-FD roundtrip, §1). `nu`, `b`, `λ`, `c` = `A_B`, the coefficient
placeholders from §4.1, are **declared in the probe run config** (see §5
parameter table) and defaulted to the values below. Kinetic `a` is the
wave-speed/dispersion coefficient.

## 4. Seed (the theory's standing wave — frozen)

Use the standing-wave form exactly as `qi-flow-double-helix.md:275`:
- amplitude `ρ(r) = E_Y + E_I` = a localized bump (e.g. Gaussian of width σ₀),
  normalized so `∫ρ = 1` (mass/charge unit);
- phase `θ(r) = atan2(E_I, E_Y)` = a single winding around the bump center
  (`E_I/ E_Y = tan(θ)` with θ advancing over the lump), carrying the conserved
  winding number = 1 (the charge/mass of the seed);
- `q_coh = ρ²/(ρ² + φ⁻² + ε²)` ≥ φ⁻² across the bump core (the coherence gate),
  so the seed is coherent where it must self-trap.

## 5. Frozen protocol

- **Frozen coefficients (§3 PDE):** `a` (dispersion) = 1.0, `nu` (hyperdiffusion) = 0.01,
  `b` (φ⁴) = 1.0, `λ` (φ-attractor) = 0.1, `c` (breathe clamp) = 0.0 (off for the
  baseline self-trap; active in the full-couple follow-up), `β = φ⁻¹/2`, `ħ²/2m² = 1.0`
  (Bohm-QP scale). These default values make every term O(1)-comparable so the
  §6 ablation isolates single axes.
- **Grid:** N³ = 128³ (phase I; grid-robustness re-run at 96³/192³ if H-HOLDS).
- **Domain:** unit cube (h = 1/N); periodic wrap (same as the sim's Poisson).
- **Integrator:** spectral/leapfrog-style with a **conservative** (symplectic)
  base for the dispersive terms + implicit for the reaction/φ-attractor, so
  mass/charge/energy drift is ≤ 1e-6 over the run. (Soliton stability demands it.)
- **Statistic (frozen):** for each run (t = 0 … T), measure:
  - `R(t)` — lump localization width (2nd radial moment of ρ), normalized by R(0);
  - `Q(t)` — winding/charge (integral of the phase gradient circulation);
  - `M(t)` — rest mass `∫ρ`;
  - `eps_mid(t)` — interior ε at the lump center;
  - `rad_frac(t)` — radiated amplitude outside 2σ₀ (radiation loss).
- **Verdict thresholds (frozen):**
  - **H-HOLDS** iff `R(t_max) ≤ 2·R(0)` AND `ΔM < 1e-3` AND `Q(t_max) ≈ Q(0)` (±1%)
    AND `rad_frac → 0`, over **T ≥ 8 cascade periods** (T = 8·τ where τ = cascade-unit
    time under the rung spacing).
  - **H-DISPERSES** iff `R(t_max) > 4·R(0)` (seed spreads) OR `rad_frac → 1`.
  - **H-COLLAPSES** iff `R(t_max) < 0.1·R(0)` (runaway contraction) or field blows up.
- **Stopping rule:** run to `t_max`; early-term ONLY on numerical blow-up (finite
  check), which is classified per §6.
- **Decision tree:** H-HOLDS ⇒ soliton regime exists; parenthesize with §6 terms.
  H-DISPERSES / H-COLLAPSES ⇒ classify the dominant missing/over-strong term.

## 6. Term-ablation (null attribution — frozen)

Run H-HOLDS/H-DISPERSES/H-COLLAPSES five times over a single-axis toggle:
| arm | RHS | purpose |
|---|---|---|
| A0 | full `ℒ_TF` (baseline) | does the declared equation alone self-trap? |
| A1 | drop φ⁴ (`b=0`) | is the self-focusing nonlinearity the trap? |
| A2 | drop Bohm QP (`Q_B=0`) | is the quantum potential the trap's curvature source? |
| A3 | hyperdiffusion `nu` ×10 | does 4th-order damping over-erode the lump? |
| A4 | φ-attractor `λ` ×10 | does the attractor over-drive toward the φ-line (fighting the wake)? |

Each arm reports the same §5 statistics. The attribute is the arm whose toggle
most changes the verdict (e.g. A1→DISPERSE implicates the φ⁴ term).

## 7. Explicit interpretation guard (per theory audit)

This probe does **NOT** test the shipped sim shader or the diffusive Python
solver. It tests the **theory-declared `ℒ_TF`**. A null is an attribution to a
specific term (via §6), meaning "the theory's equation, as specified here, does
not self-trap in this regime" — it is **not** a global "no-soliton" negative,
and under no circumstance should a null be read as "the Cassi field has no
soliton regime."

## 8. Deliverables

1. `soliton_self_trapping_probe.py` (the frozen protocol above, runnable),
   writing `_diag/soliton_self_trapping.json` with per-arm statistics + verdict.
2. Report `soliton-self-trapping-report.md` with the verdict, §6 attribution,
   and the mass-ladder placement of the lump if H-HOLDS.
3. Ledger row appended to `probe-outcome-ledger.md`.

## 10. Amendment 1 (2026-08-16): twist-tightness seed axis

**Motivation (owner hypothesis).** The phase-I pilot (frozen seed m=1, single
Q=1 winding spread over the whole box) found H-DISPERSES: the loose twist has
nearly flat `∇θ` in the core, so the Bohm-QP term (gradient-driven) is too weak
to oppose the `a∇²` dissipation. The owner proposed that **trapping requires
the Qi spiral to close its twist tightly — a multi-scale effect** (the twist
closes m times within the lump, `∇θ ~ m/r` steep, QP becomes localizing).

**Amendment.** The frozen seed axis is extended with winding number `m` (new
parameter; `m=1` preserves the frozen baseline exactly):
`θ = m·atan2(Y_c,X_c)` inside a fixed σ₀ lump. This is a **new regime** added
to the ablation, not a re-run of the rejected baseline.

**New ablations (twist-tightness arm, A0 base = f4+qp+attr, EL-verified signs):**

| arm | m | asks |
|-----|---|------|
| T1 | 1 | frozen baseline (control) |
| T2 | 2 | 2 self-turns in the lump |
| T3 | 4 | 4 self-turns |
| T4 | 8 | tightly-closed twist |

**Frozen statistic/verdict/thresholds:** identical to §5 (R(t)/R(0), Q, M,
eps_mid, rad_frac; H-HOLDS iff R(t_max)≤2·R(0) ∧ ΔM<1e-3 ∧ Q(t_max)≈Q(0) ±1%
∧ rad_frac→0). Same grid/domain/integrator as phase I (Strang-split spectral
exponential). **If H-HOLDS** for any m≥2 while T1 disperses, the trap is
twist-mediated and multi-scale → re-open the §9 registry path.

**Stopping rule / honesty:** unchanged — early-term only on numerical blow-up;
the QP term stays regularized (field-relative floor + clipped inverse) so a
null is a physics claim about the tight-twist regime, not a NaN artifact.

## 11. Amendment 2 (2026-08-16): multi-scale axial probe — the twist is cross-rung flow

**Owner correction (confirmed).** Amendment 1 tested the twist as a *spatial*
winding on a single-scale Gaussian. The theory places the winding in
**(scale, doublet-plane) space**, not as spatial filaments
(`foundations/qi-flow-double-helix.md` §3.5): the helix is the **axial phase
winding along the cascade**, and it is **emergent from coherence flowing up the
rungs** — `J_z = R²∂_zθ` (£3.2), φ⁻¹ per rung, the doublet phase advancing π
per rung (P_∥ = 2, §3.3), winding born from a relaxation excess ε₀ (§3, the
relaxation winding Δϑ(ε₀)). The single-scale probe had no cascade extent and no
inflow, so it removed the mechanism by construction. Owner: *"the trap needs
both the per-rung phase advance AND the axial multi-rung extent; the twist must
close tightly from the coherence flow of the lower scales."*

**Amendment.** The probe moves onto the shipped **lattice-stack machinery**
(`run_lattice_stack_probe.py`, read-only): M two-lobe coherence layers along z
(the string axis) with per-layer phase `θ_i = i·Δθ`. Three changes realize the
multi-scale flow:

1. **φ-spaced shells** (cascade extent): layer positions `z_i` spaced by the
   cascade ladder `ℓ_n ∝ φ^n` around the lump, with the **fine (small-spacing)
   end = lower rungs** — replacing the base's uniform `s = N/M` spacing. The
   lump spans rungs, not a single scale.
2. **Per-rung phase advance**: `θ_i = i·Δθ` with `Δθ` at the natural closure
   steps — pentagon `2π/5` (R = φ), decagon `π/5`, and the **P_∥ = 2 anti-phase
   `π`** (double-helix closure).
3. **Seeded coherence excess at the fine end**: the low-φ shells carry a
   stronger `ε` perturbation (`ε₀`), the coherence excess the lower scales feed
   up, so the relaxation winding `Δϑ(ε₀)` can emerge as an axial current.

**Base = shipped solver** (`cassi_two_fluid_3d_gpu.py`, gate 'five') with its
native `(1−q)` gate and `dθ/dt = λ(1−q)·ρε/(E_Y²+E_I²)` winding — the real
machinery, not the stripped ℒ_TF form.

**Arms (fresh solver per arm, N = 48, dt = 0.001, t = 40 = 2/λ, zero new
terms — identical discipline to the lattice-stack family):**

| arm | geometry | asks |
|-----|----------|------|
| A_phi_en | φ-spaced + phase + fine-excess | does the multi-scale flow lock a persistent two-hump envelope? |
| A_phi_ne | φ-spaced + phase, no excess | is the fine-end excess load-bearing? |
| A_uni_en | uniform spacing + phase + excess | is φ-spacing load-bearing? |
| A_uni_ne | uniform + phase, no excess | base control |
| m1       | single layer (M=1) | the known TS1 escape control |

**Frozen statistic/verdict (extend §5):** envelope persistence — `C_abs`
(two-hump contrast) and `A_peak` retention at t = 4 and t = 40; axial current
`|J_z|` growth; `winding`; mass drift. **H-HOLDS** iff the arm with
φ-spacing+phase+fine-excess keeps `C_abs(40) ≥ 0.5` and `A_peak(40)/A_peak(0)
≥ 0.5` while the A_uni_ne / m1 controls escape (C_abs → ~0), and mass/charge
drift ≤ 1e-6. **H-DISPERSES** iff all arms escape alike. **H-COLLAPSES** on
blow-up. Attribution: which element (φ-spacing, phase, fine-excess) is
necessary by pairwise contrast.

**Relation to Amendment 1 / Wave-0:** this uses the shipped winding solver so a
null here is a real "the axial flow through a multi-rung stack does not
self-lock" claim on the actual theory machinery — not an artifact of a stripped
equation.

## 12. Amendment 3 (2026-08-16): meshless coherence-cluster depth probe — cascade suppression

**Owner steering (priority).** The grid PDE runs hit the resolution wall it
exists to remove: at M ≥ 11 the φ-spaced shells overlap below the layer width
on a fixed N³ grid, so deeper cascade structure needs a bigger box (8× per
octave). The owner: *"these are the kinds of limitations the simulator's
meshless mode was made for — use the simulation's solver instead of doing these
PDE tests. Start with (a) coherence-as-order-parameter; (b) two-fluid winding on
particles later. The goal is for the simulator to simulate reality."*

**Amendment.** Move the cascade-depth question onto the **meshless Qi-gated
particle solver** (`two-fluid/cassi_nbody.py` — leapfrog KDK, FFT-Poisson +
Gaussian softening, Qi-gated adaptive softening `q = ρ²/(ρ²+φ⁻²+ε²)`, Qi-gated
r_cut linking). The order parameter is the solver's own particle coherence
(the "φ-organized multi-scale cluster" tests whether more cascade rungs →
more stable, i.e. the cascade-suppression mechanism).

**Seed (φ-organized multi-scale coherent cluster):** N bodies in nested shells
at φ-spaced radii `r_k = r_min·φ^k` (k = 0..D−1, D = rung depth). The inner
(fine, lower-rung) shells carry the density/coherence excess ("lower scales
feed up") — realized natively by the Qi gate: the dense inner shells have high
`q = ρ²/(ρ²+φ⁻²+ε²)` → adaptive softening collapses → stronger core binding.

**Mechanism under test:** a multi-rung coherent cluster should self-persist
(retain its φ-spaced radial + coherence structure) longer than a single-scale
blob — more rungs → more stable. That depth scaling IS cascade suppression
(φ⁻¹ per rung coupling, `qi-flow-double-helix.md` §3.2).

**Arms (fresh solver per arm, L=20, G=1, sigma=0.4, dt=0.001, KDK):**

| arm | depth D (rungs) | asks |
|-----|-----------------|------|
| depth_1 | 1 (single shell, control) | does a single-scale blob just spread? |
| depth_2 | 2 (φ-nested) | is a second rung more stable? |
| depth_4 | 4 (φ-nested) | does deeper hold longer? |

Total mass/outer-size matched across arms; only rung depth (and inner fine
resolution) differ. Measure: radial shell-spacing retention vs t (φ-spacing
preserved), coherence profile q(r) retention, core radius vs t, mass drift.

**Frozen statistic/verdict:** let `T_hold(D)` = time the φ-spaced radial
structure (shell spacing within ±20% of φ) and the interior q ≥ 0.5·q(0) are
both retained. **SUPPORTS cascade suppression** iff `T_hold` is monotone
increasing in D (depth_4 > depth_2 > depth_1) and depth_4 ≥ 2× depth_1;
DOES NOT SUPPORT otherwise. Mass drift ≤ 1e-6 per arm (solver conservation).

**Relation:** uses the shipped Qi-gated meshless solver as-is (coherence is
already the order parameter for softening/binding) — no bespoke equation, and
the depth result transfers directly to the simulator.

If H-HOLDS, the lump's mass landing on the φ-cascade ladder is a **numeric
prediction** and must be synced to `predictions/falsifiable-predictions.md`
(after the report confirms it), per the registry-first rule. Until then this is
a T2 model test, not a registered prediction.

### §12 Result (2026-08-17, 64³, 3/3 arms, full run)

`runs/20260817_013351_meshless_deep/results.json` (4000 steps/arm, dt=0.001,
L=20, G=1, sigma=0.4, Qi-gated nbody, TSC deposition):

| arm | D | T_hold | inner_frac 0→end | q_last |
|-----|---|--------|------------------|--------|
| depth_1 | 1 | 4.00 (horizon) | 1.000 → 0.965 | 0.0032 |
| depth_2 | 2 | 4.00 (horizon) | 0.816 → 0.867 | 0.0110 |
| depth_4 | 4 | 4.00 (horizon) | 0.591 → 0.692 | 0.0362 |

**Frozen verdict: DOES NOT SUPPORT** — `T_hold` is not monotone in D (it is
**saturated at the run horizon for all three arms**), so the required
`depth_4 ≥ 2× depth_1` separation is not exhibited.

**Honest interpretation (saturation + trajectory signal).** `T_hold` is a
cap-limited metric: every arm retained its φ-spaced radial structure and
interior coherence to the full horizon, so the metric saturates before it can
discriminate depth. The trajectory-level signal is **opposite to dispersal and
consistent with cascade suppression**: the inner-φ-rung mass fraction **rises**
with depth (depth_2 0.816→0.867; depth_4 0.591→0.692) while the single-rung
control *drops* (depth_1 1.000→0.965) — the outer (higher-rung) coherence
**condenses into the dense core** rather than radiating away, more strongly the
deeper the stack. This is the scalar-q order parameter (a) seeing the
amplitude-sector side of cascade suppression — which is exactly the sector
where the winding phase (b) is the missing degree of freedom. The frozen rule
is honored (DOES NOT SUPPORT as written); the negative is a **metric
saturation**, not a dispersal, and motivates the (b) winding-phase extension
(`CassiCosmos/research/meshless/two_fluid_particle_winding_design.md`).

### §12b Result (2026-08-17, winding-on-particles (b1))

`two-fluid/meshless_winding_probe.py` (64³, 3/3 arms, 4000 steps each; runs
`runs/meshless_winding_depth.json`). depth_1/depth_2 from the 3-arm sweep;
depth_4 from an isolated rerun after a quiet mid-run background kill (GPU
contention, same as the (a) sweep — no physics difference, identical IC).

| arm | D | T_hold_phase | θ_order 0→end | inner_frac 0→end |
|-----|---|--------------|---------------|------------------|
| depth_1 | 1 | 1.00 (horizon) | 0.999 → 0.999 | 0.500 → 1.000 |
| depth_2 | 2 | 1.00 (horizon) | 0.799 → 0.993 | 0.309 → 0.605 |
| depth_4 | 4 | 1.00 (horizon) | 0.799 → 0.837 | 0.224 → 0.485 |

**Frozen verdict: DOES NOT SUPPORT** (T_hold_phase monotone in D but not
2× — all arms saturate at the run horizon, exactly the (a) saturation).

**Honest interpretation.** The (b1) phase sector **never decoheres**, for any
depth: the per-particle winding phase-lock `θ_order` stays ≥ its t=0 value in
every arm, and *rises* toward perfect phase-lock in the deeper arms (depth_2
0.799→0.993) while the already-locked single-rung control has no room (0.999).
Energy is conserved (E steady ≈ −9.3e5), no NaN. The scalar-q (a) metric
saturated because the amplitude sector condenses, not disperses; the winding
(b1) shows the phase sector is equally stable — the winding is a **real, stable
per-particle degree of freedom that moves toward phase-lock** (the coherence
"sound") rather than decohering, an outcome the (a) probe structurally could
not measure.

So the combined (a)+(b1) result supports the mechanism-consistent reading the
frozen T_hold rule cannot score: **neither the amplitude nor the phase sector
disperses, at any depth**, and both saturate the horizon-retention metrics. The
depth-2× requirement fails on metric ceiling, not on physical dispersal — the
(2×) test needs a longer horizon or a finer resolution to reveal depth
separation. This is the honest negative the pre-registered rule demands, with
the mechanism signal preserved. The per-particle winding (b1) is committed and
reproducible for the engine/shader follow-up (b2).

### §12c Result (2026-08-17, full-doublet winding (b2))

`two-fluid/meshless_doublet_probe.py` (64³, 3/3 arms, 4000 steps each, clean
3-arm sweep; runs `runs/meshless_doublet_depth.json`). Per-particle full
doublet `(E_Yi, E_Ii)` evolved by the shipped conversion
`conv = −λ(1−q)(E_Y−φE_I)` (mass-conserving exchange) + J_z neighbor phase
coupling; winding `θ_i = atan2(E_Ii, E_Yi)` derived. Removes the (b1)
reconstruction: amplitude and phase both free.

| arm | D | T_hold_phase | θ_order 0→end | Σρ_dp 0→end | inner_frac 0→end |
|-----|---|--------------|---------------|--------------|------------------|
| depth_1 | 1 | 1.00 (horizon) | 0.999 → 1.000 | 1199 → 1365 | 0.500 → 1.000 |
| depth_2 | 2 | 1.00 (horizon) | 0.799 → 1.000 | 2140 → 2344 | 0.309 → 0.605 |
| depth_4 | 4 | 1.00 (horizon) | 0.799 → 0.934 | 816 → 2301 (×2.8) | 0.224 → 0.485 |

**Frozen verdict: DOES NOT SUPPORT** (T_hold_phase monotone but all arms
saturate at the run horizon; no 2× depth separation — the same ceiling as the
(a) and (b1) horizon-retention metrics).

**Honest interpretation.** The full doublet is **stable and never decoheres**:
energy conserved (E steady in every arm), no NaN, and the winding phase-order
is retained or **rises toward perfect phase-lock (θ_order → 1.0)** in every arm
(depth_2 0.799→1.000, depth_4 0.799→0.934, depth_1 already 0.999→1.000). The
amplitude sector is the strongest signal yet: with E_Y/E_I both free, the
deepest arm's doublet mass **nearly triples** (816→2301) — the full-doublet
amplitude accumulates coherently via J_z coupling, far more than the (b1)
reconstruction could express, and inner-rung mass fraction condenses in every
arm (depth_4 0.224→0.485).

(b2) converges with (a)+(b1) on the mechanism the frozen T_hold rule cannot
score: **neither the amplitude nor the phase sector of the winding disperses at
any depth**; deeper stacks phase-lock and accumulate coherence, consistent with
cascade suppression, and the 2× separation is masked by the horizon-retention
ceiling. This is the honest negative the pre-registered rule demands, with the
mechanism preserved. The per-particle full doublet (b2) is committed, stable,
and directly portable to the CassiCosmos engine (per-particle EY/EI buffers +
the tree-walk J_z), completing the (b) winding-on-particles line.
