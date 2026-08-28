# Soliton Self-Trapping (Wave-0) — PRE-REGISTRATION

**Probe:** `field-experience/soliton_self_trapping_probe.py` (NEW, to be written)
**Pre-registered:** written BEFORE any run. This file FREEZES the protocol.
**Date:** 2026-08-16. New files only; no existing file modified; no commits.
**Tier:** T2 theory-equation test of the within-scale balance search space
under the owner's "balance" reframe, extending the T3 projection/circulation
probe scope.
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
- seeded density-plane diagnostic `θ(r) = atan2(E_I, E_Y)` = a single
  winding around the bump center (`E_I/ E_Y = tan(θ)` with θ advancing over
  the lump). The winding number = 1 is a **Hypothesized seed input** and the
  charge/mass label of this pre-registered test;
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

**Motivation (owner hypothesis).** The phase-I pilot (frozen seed $m=1$, single
$Q=1$ winding spread over the whole box) displays a numerical `H-DISPERSES`
pattern: the loose twist has nearly flat `∇θ` in the core, so the Bohm-QP term
(gradient-driven) is too weak to oppose the `a∇²` dissipation. The owner
proposed that **trapping requires the Qi spiral to close its twist tightly—a
multi-scale effect** (the twist closes $m$ times within the lump,
`∇θ ~ m/r` steep, QP becomes localizing).

**Amendment.** The frozen seed axis is extended with winding number `m` (new
parameter; `m=1` preserves the frozen baseline exactly):
`θ = m·atan2(Y_c,X_c)` inside a fixed σ₀ lump. This adds a distinct regime to
the ablation; `m=1` remains the frozen baseline control.

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

**Stopping rule:** unchanged — early-term only on numerical blow-up;
the QP term stays regularized (field-relative floor + clipped inverse) so a
null is a physics claim about the tight-twist regime, not a NaN artifact.

## 11. Amendment 2 (2026-08-16): multi-scale axial probe — optional cross-rung-flow hypothesis

**Phase-scope boundary.** Amendment 1 tested the twist as a *spatial*
winding on a single-scale Gaussian. This amendment registers a **Hypothesized**
construction in (scale, doublet-plane) space
(`foundations/qi-flow-double-helix.md` §3.5), using seeded layer geometry and
seeded density-plane-angle values. The helix and any axial phase winding are
properties of that added construction. Here `J_z = R²∂_zθ` is the z component
of the local density-plane diagnostic $J_d$, with $R²=E_Y²+E_I²$ and units of
field²/length. It becomes transport or cross-rung flow only with a separate
constitutive map, projection, and test. A compact phase, amplitude current,
per-rung advance, or cascade-flow interpretation is an optional extension.
The single-scale probe had no cascade extent and no inflow, so it did not test
this seeded construction. The pre-registered rationale is: *"the trap needs
both the per-rung phase advance AND the axial multi-rung extent; the twist must
close tightly from the coherence flow of the lower scales."*
**Amendment.** The probe moves onto the shipped **lattice-stack machinery**
(`run_lattice_stack_probe.py`, read-only): M two-lobe coherence layers along z
(the string axis) with per-layer phase `θ_i = i·Δθ`. The layer positions,
angle increments, and fine-end excess are **Hypothesized inputs** to the
unrun test. Three changes test the optional multi-scale construction:

1. **φ-spaced shells** (cascade extent): layer positions `z_i` spaced by the
   cascade ladder `ℓ_n ∝ φ^n` around the lump, with the **fine (small-spacing)
   end = lower rungs** — replacing the base's uniform `s = N/M` spacing. The
   lump spans rungs, not a single scale.
2. **Per-rung phase advance**: `θ_i = i·Δθ` with `Δθ` at the seeded closure
   steps — pentagon `2π/5` (R = φ), decagon `π/5`, and the **P_∥ = 2 anti-phase
   `π`** (double-helix closure). These values are test inputs, not canonical
   density-plane-angle increments.
3. **Seeded coherence excess at the fine end**: the low-φ shells carry a
   stronger `ε` perturbation (`ε₀`). The optional mechanism asks whether this
   seeded contrast produces the relaxation winding `Δϑ(ε₀)` or an axial
   response in the measured diagnostics.
**Base = shipped solver** (`cassi_two_fluid_3d_gpu.py`, gate 'five') with its
native `(1−q)` gate and `dθ/dt = λ(1−q)·ρε/(E_Y²+E_I²)` density-plane-angle
rate — the real machinery, not the stripped ℒ_TF form. The rate and its
diagnostics are read under the optional construction boundary above.
**Frozen statistic/verdict (extend §5):** envelope persistence — `C_abs`
(two-hump contrast) and `A_peak` retention at t = 4 and t = 40; local axial
density-plane diagnostic `|J_z|` growth; `winding`; mass drift. **H-HOLDS** iff
the arm with
φ-spacing+phase+fine-excess keeps `C_abs(40) ≥ 0.5` and `A_peak(40)/A_peak(0)
≥ 0.5` while the A_uni_ne / m1 controls escape (C_abs → ~0), and mass/charge
drift ≤ 1e-6. **H-DISPERSES** iff all arms escape alike. **H-COLLAPSES** on
blow-up. Attribution: which element (φ-spacing, phase, fine-excess) is
necessary by pairwise contrast.

**Relation to Amendment 1 / Wave-0:** this uses the shipped winding solver so a
null here is a result for the tested seeded geometry, angle inputs, and local
diagnostics. It tests whether that optional multi-rung construction
self-locks; the result carries no canonical inter-rung transport claim and is
not an artifact of a stripped equation.


## 12. Amendment 3 (2026-08-16): meshless cascade-depth probes

### 12.1 Registered discriminator

The registered scalar-arm comparison asked whether a deeper $\varphi$-spaced
particle cluster retains radial shell spacing and interior coherence longer.
It specified:

- a local canonical coherence gate
  $q=\rho^2/(\rho^2+\varphi^{-2}+\varepsilon^2)$;
- local adaptive softening and a $q$-gated close-pair linking radius;
- depth arms matched in total mass and outer size;
- a joint hold time for shell-spacing retention within 20% of $\varphi$ and
  interior $q(r)\geq0.5q(r,0)$;
- mass drift no greater than $10^{-6}$ per arm.

The frozen positive branch requires

$$
T_{\mathrm{hold}}(4)>T_{\mathrm{hold}}(2)>T_{\mathrm{hold}}(1),
\qquad
T_{\mathrm{hold}}(4)\geq2T_{\mathrm{hold}}(1).
$$

The winding-arm comparison uses the same strict depth discriminator for the
inner-rung phase-order hold time.

### 12.2 Implementation audit

The shipped implementation does not instantiate the registered
counterfactual. `two-fluid/cassi_nbody.py` deposits physical mass density and
forms the occupied-cell proxy

$$
c=\frac{\rho}{\rho+\varphi^{-2}}.
$$

No reference-density normalization makes the two denominator terms
dimensionally comparable. The proxy therefore changes with particle mass,
particle count, and cell volume. A density-memory residual and $c$ are reduced
to global means and used to adjust one Gaussian softening length. The
registered local $q(E_Y,E_I)$ gate and close-pair linking path are absent.
`two-fluid/meshless_deep_probe.py` measures retention inside one radius rather
than shell-spacing retention and the registered interior $q(r)$ condition.

Depth changes several inputs at once:

| depth $D$ | particles | total mass | outer radius | exact initial inner fraction |
|---:|---:|---:|---:|---:|
| 1 | 800 | 800 | 1.200 | 1.000 |
| 2 | 1,600 | 1,600 | 1.942 | 0.816 |
| 4 | 3,200 | 3,200 | 5.083 | 0.591 |

The registration does not fix the particle count per shell, position seed,
phase-jitter seed, or velocity initialization. The scalar arm uses 800
particles per shell, position seed 42, velocity-direction seed 7, and an
isotropic heuristic speed field. The density-angle and signed-coordinate arms
use 1,200 particles per shell, position and phase seeds 1, a
$k\pi/2+0.05\,\mathcal N(0,1)$ angle seed, and velocities directed along the
inward gravitational acceleration. Neither speed construction establishes a
stationary virial state or verifies $2K/|PE|=1$.

Particle masses are immutable in all three executables. The registered mass
drift condition is therefore automatic and supplies no conservation test for
the density-angle or signed-component state. Neither observer executable runs
a matched observer-off trajectory. Particle count, total mass, extent,
initial inner fraction, velocity state, and observer construction all confound
the depth contrast. The registered discriminator is unscoreable.
The retained numerical patterns are legacy surrogate outputs. Because the
registered discriminator is unscoreable and protocol validity fails, they are
not a physical negative and do not support a `CONTRADICTS` verdict.

### 12.3 Scalar-arm receipt

`runs/20260817_013351_meshless_deep/results.json` contains the full $64^3$
sweep: 4,000 steps per arm, $\Delta t=0.001$, $L=20$, $G=1$, Gaussian width
$0.4$, and TSC deposition.

The aggregate receipt declares `N_shell: 1200`, while its arm counts and
per-arm files establish 800 particles per shell ($N=800D$). The arm records
govern the table; the aggregate metadata is internally inconsistent.

| arm | $D$ | stored hold | first stored fraction $\to$ last stored fraction | full-grid density proxy |
|---|---:|---:|---:|---:|
| depth_1 | 1 | 4.00 | $1.000\to0.965$ | 0.0032 |
| depth_2 | 2 | 4.00 | $0.816\to0.867$ | 0.0110 |
| depth_4 | 4 | 4.00 | $0.591\to0.692$ | 0.0362 |

The runner records positions after steps $1,101,\ldots,3901$, at times
$0.001,0.101,\ldots,3.901$. The stored implementation treats the first
post-step frame as $t=0$ and assigns $4.000$ to a run with no sampled
crossing, extending the reported hold by $0.099$ beyond the last observation.
Its custom acceleration interpolation also indexes the solver's
$[z,y,x]$ grids as $[x,y,z]$ when constructing the velocity magnitudes.

The executable retains the exact initial positions, uses the native particle
interpolator, records exact sample times, and right-censors a no-crossing arm
at its last tracked frame. No full scoreable sweep is available.
`runs/20260824_071225_meshless_deep/results.json` is a two-step smoke check and
is non-scoring.

**Registered discriminator: UNSCOREABLE. Scientific verdict: INCONCLUSIVE.
Protocol validity: FAIL.** Equal stored values provide no depth
discrimination, and the timing error prevents their interpretation as exact
horizon-censored hold times. The force heuristic, measured statistic, and
unmatched arms differ from the registered experiment.

### 12.4 Density-angle surrogate receipt

`two-fluid/meshless_winding_probe.py` adds one density-angle observer per
particle. It constructs surrogate coordinates from the physical-density proxy
and advances the angle with a whole-ensemble density-weighted aligner. The
coordinates do not satisfy the canonical density identities. A low-density
rule sets the proxy to $q=1$ below one percent of the instantaneous maximum,
which freezes the local winding term in those cells and can alter the
depth-order statistic.

`runs/meshless_winding_depth_angle-fix-L20.json` contains 4,000 steps per arm,
but it is not a scoreable implementation of the registered discriminator. Its
open-core phase mask cuts through the designed second shell, while
center-of-mass recentering spreads the discrete shell across that cut. Its
inner-fraction mask likewise intersects the recentered innermost shell,
producing stored initial fractions $0.500$, $0.309$, and $0.224$ instead of
the shell-label fractions $1.000$, $0.618$, and $0.447$. One-sided numerical
tolerances make comparison deterministic but do not restore shell membership;
no full scoreable receipt is available.

The parent solver wraps positions into the periodic box while the observer
uses raw origin-centered radii. Stored endpoint radii reach the box-corner
scale, so periodic wrapping contaminates radial membership. The three stored
hold times equal the run horizon. The observer does not feed back into the
gravitational trajectory, yet the executable records no matched
`wind=False` control. Its global aligner directly drives the measured phase
order, and the fixed N-body masses do not conserve or test an evolved phase
quantity.

`runs/meshless_winding_depth.json` uses a non-authoritative schema, incomplete
arm metadata, and an interrupted-sweep note. It does not supply a separate
registered receipt.

**Registered discriminator: UNSCOREABLE. Scientific verdict: INCONCLUSIVE.
Protocol validity: FAIL.** The surrogate receipt cannot support claims of
emergent winding, a canonical phase degree of freedom, cascade suppression,
or engine portability; its numerical pattern is not a physical negative.

### 12.5 Signed-component stress-test receipt

`two-fluid/meshless_doublet_probe.py` evolves signed Cartesian coordinates

$$
E_Y=A\cos\theta,\qquad E_I=A\sin\theta
$$

through the conversion algebra and a whole-ensemble vector-mean aligner. The
initial conditions occupy all four quadrants, outside the canonical domain
$E_Y\geq0$, $E_I\geq0$. Initial negative-coordinate fractions are
$(0,0.490)$ for depth 1, $(0.253,0.245)$ for depth 2, and $(0.506,0.492)$ for
depth 4.

`runs/meshless_doublet_depth.json` uses a non-authoritative field schema and a
terminal classifier that the present protocol cannot score.
`runs/meshless_doublet_smoke.json` is a single-arm smoke artifact with the same
status. The executable records an endpoint-retention Boolean rather than a
sampled hold time. Its raw-radius observer shares the shell-boundary and
periodic-wrap limitations in §12.4, and it records no matched observer-off
trajectory.

The observer has no feedback into the parent gravitational trajectory. The
global aligner directly affects phase order, while its rotation changes
$E_Y+E_I$. The signed-component sum is not a coupled-state invariant. Fixed
particle-mass conservation is independent of the evolving signed coordinates
and cannot satisfy the registered conservation requirement.

**Registered discriminator: UNSCOREABLE. Scientific verdict: INCONCLUSIVE.
Protocol validity: FAIL.** The signed-coordinate stress test cannot support
claims of canonical winding, phase stability, cascade suppression, or engine
portability; its numerical pattern is not a physical negative. A valid
particle probe requires matched depth arms, nonnegative canonical densities
plus an independent phase variable or a derived complex-amplitude model,
spatial coupling with declared neighbors, a sampled hold-time trajectory,
unwrapped or minimum-image radial tracking, and a conserved quantity belonging
to the coupled state.
