# Sound as Waves of Coherence — the two-fluid phase speed identity

**Status:** Draft, 2026-08-15, CassiCosmos (research note).
**Scope:** derived from the shipped solver `compute/cassi_two_fluid.glsl` and the merge
shader `compute/cassi_particle_merge.glsl`; no other files touched.
**Tier key:** TIER-1 = directly derivable from shipped code; TIER-2 = framework
interpretation, consistent but not uniquely implied; TIER-3 = speculative extension.

---

## §1 The question and the short answer

> *"Might the sound speed be related to the speed that coherence flows through Qi,
> and sound be waves of coherence?"*

**Yes. In this sim the two-fluid phase speed and the merge's sound speed are the same
thing by construction.** The field combination ρ = EY+EI (the coherence/density sum)
obeys a *gapless* wave equation, so it carries a propagating front at speed c; with
c² = 1 in code cell-index units that is exactly one lattice cell per leapfrog step, i.e.
c_s = h₀/dt — **the very quantity the merge shader documents as "the two-fluid phase
speed" and enforces as its subsonic-inflow threshold.** Sound here is waves of ρ, the
coherence carrier.

---

## §2 Derivation from the shipped solver

The solver integrates (header, `cassi_two_fluid.glsl:9-10`; acc in `pass_a`
lines 200-201, `omega2 = 20.0 = ω₀²` at line 194):

$$\partial_t^2 EY = c^2\nabla^2 EY - \omega_0^2(EY-\varphi EI),\qquad
\partial_t^2 EI = c^2\nabla^2 EI + \omega_0^2(EY-\varphi EI).$$

The Laplacian is the 19-point anisotropic stencil (`lap_ey_at`/`lap_ei_at`, lines 84-144)
whose weights reduce to (1/3 axis, 1/6 face-diagonal) at unit aspect and whose symbol is
$-h_0^2\,k^2_{\mathrm{phys}}$ — i.e. it reads $h_0^2\nabla^2_{\mathrm{phys}}$, so its raw
(cell-index) coefficient is exactly **c² = 1** in code units.

### ρ — the gapless ("acoustic") mode
Define ρ = EY+EI. Adding the two PDEs, the coupling cancels exactly:

$$\partial_t^2 \rho = c^2\nabla^2\rho.$$

The ω₀² term drops out entirely. **ρ propagates freely at the wave speed c** with no rest
gap — this is the coherence/density carrier.

### ε — the gapped ("optical") mode
Define ε = EY−φ·EI (the code's `ey_ei_diff`, line 196, squared into `eps2` in
`pass_b:237-238`, and the incoherence denominator of the merge gate `qcoh_at`,
`cassi_particle_merge.glsl:161-163`). Since ε ≠ a plain sum (φ picks a different weight):

$$\partial_t^2 \varepsilon = c^2\nabla^2\varepsilon - \omega_0^2(1+\varphi)\,\varepsilon,$$

with a **mass gap**

$$\omega_{\mathrm{gap}}^2 = \omega_0^2(1+\varphi) = 20\,(1+1.618\ldots) \approx 52.36,\qquad
\omega_{\mathrm{gap}}\approx 7.24\ \mathrm{rad/step}.$$

A uniform (k = 0) ε perturbation therefore oscillates in place at ω_gap; long-wavelength
modes ($k^2 < \omega_{\mathrm{gap}}^2/c^2$) are evanescent/non-propagating. Only
sufficiently short-wavelength ε structure propagates. **The incoherence impurity is pinned
at the pair-mismatch frequency and cannot carry a long-range front.** [TIER-1]

### The wave-speed identity
With c² = 1 in cell-index units (the `lap_ey` raw value used directly in `acc_ey`,
line 200), the ρ front advances one lattice cell per leapfrog step. Converting to physical
units (1 cell = h₀, one step = dt):

$$c_s = \frac{h_0}{dt} \quad (\text{$h_0$ = min-extent reference cell, `cassi_two_fluid.glsl:93`}).$$

This is **exactly** the merge's documented threshold — `cassi_particle_merge.glsl:19`
("c_s = h₀/dt (the two-fluid phase speed)"), push-constant comments lines 104-105, and the
enforced gate `pass_best:351`:

```glsl
if (length(vt) >= pc.h0 / max(pc.dt, 1e-9)) continue;   // reject |v_t| >= c_s
```

The identity is genuine, not an accident: the merge's "sound speed" *is* the coherence
(ρ) wave speed of the same field. [TIER-1]

---

## §3 The merge connection (subsonic gate = coherence speed)

The subsonic-inflow criterion (§3b of `coherence_merge_rnd.md`, hypothesis tier there)
rejects a pair whose transverse relative velocity |v_t| meets or exceeds c_s = h₀/dt. From
§2, c_s is the speed a ρ/coherence front travels. Thus the gate is literally:
**merge only pairs whose cross-track inflow is subsonic relative to the coherence wave —
a supersonic transverse pair is a coherence-disconnected fly-by, not an accreting
condensate.** [TIER-1 that the gate threshold = wave speed; TIER-2 that this is the right
condition for condensate formation — the "structure forms where the flow is subsonic"
claim in `coherence_merge_rnd.md:260-266` is doctrine-adjacent hypothesis].

---

## §4 Real-world mapping (phonons: acoustic vs optical) — TIER-2

Sound in a material is a longitudinal wave of density/order — phonons are quantized waves
of lattice order, with sound speed $c_s^2 = $ stiffness/density. The framework mirrors this
structure exactly:

| continuum | Qi two-fluid | |
|---|---|---|
| stiffness | Laplacian coefficient c² (= 1 in code) | TIER-1 |
| carrier field | ρ = EY+EI (coherence sum) | TIER-1 |
| acoustic branch | gapless ρ mode, speed cₛ = h₀/dt | TIER-1 |
| optical branch | gapped ε mode, ω_gap² = ω₀²(1+φ) | TIER-1 |
| "sound = waves of coherence" | the propagating ρ field carries the coherence density; ε (mismatch) suppresses it | TIER-2 |

The ε mode is the optical-phonon analog: it costs a gap frequency to excite and does not
transmit order. And q_coh = ρ²/(ρ²+φ⁻²+ε²) (`cassi_particle_merge.glsl:153-164`; the
framework's bounded coherence) makes this quantitative: **a passing ρ wave raises q_coh →
1 (it carries coherence); a nonzero ε drives q_coh → 0 (it destroys coherence).** So
wave-mediated coherence is carried by the gapless ρ mode and killed by the ε impurity —
exactly the "acoustic carries order, optical defect scatters it" picture. [TIER-2: the
phonon analogy, and the physical claim that ρ is "coherence", are consistent but not
uniquely implied by the code.]

---

## §5 Falsifiable sim predictions

Each is testable with the existing engine/probe machinery (verify_fft / two-fluid,
Gaussian `source_ey`/`source_ei`, the merge's `f_subsonic` flag).

1. **ρ front speed = h₀/dt.** A φ-locked compact ρ pulse (σ in `source_ey/source_ei`,
   lines 147-170) propagates at one cell per step; measure the outgoing front radius vs
   step in physical units and confirm slope = h₀. [TIER-1]

   Measurement refinement (verified by the verify_rho_front/verify_omega_invariant
   scenes, 2026-08-15): the PHASE speed is exactly one cell/step (the k→0 limit). A
   COMPACT broad-band pulse travels at the 19-point stencil's group speed ≈ 0.88–0.92·c
   (measured 0.884 cells/unit-time; matches the v_c ≈ 0.92 reading of §7.1), so the
   scene gates the lattice-dispersion window [0.85, 1.05] rather than the analytic
   c = 1. The ω₀²-invariance of this speed is verified bit-identically (0.8842 at
   ω₀² = 20 and 200).
2. **ε is gapped.** Launch a *pure-ε* perturbation (ρ = 0, i.e. EY = −EI): it stays put,
   oscillating in place at ω_gap ≈ 7.24 rad/step rather than radiating a front.
   *Correction to the common phrasing:* EY = φ·EI is ε = 0 — the *perfectly-coherent lock*,
   which propagates freely; the genuinely non-propagating input is the ρ-null, ε-nonzero
   state. [TIER-1]
3. **Sharp subsonic threshold.** With `f_subsonic` on, a pair at |v_t| slightly *below*
   h₀/dt passes the gate; slightly *above* always fails (the `>=` at line 351 is an exact
   step). Confirms the merge sound speed equals the coherence speed. [TIER-1]
4. **ω₀² independence of c_s, faster ε suppression.** Raise `omega2 = 20.0`
   (`cassi_two_fluid.glsl:194`): the ρ front speed is unchanged (ρ decouples from ω₀²),
   but the ε gap √(1+φ)·√ω₀² widens, so ε-mediated incoherence oscillates faster and
   q_coh's ε² suppression acts sooner. [TIER-1 for the invariance; TIER-2 that "faster"
   is a physically meaningful suppression rate]

---

## §6 Tier summary

| Claim | Tier | Where it lives |
|---|---|---|
| ∂²ρ/∂t² = c²∇²ρ (ρ gapless, coupling cancels) | 1 | derived from `cassi_two_fluid.glsl:9-10,200-201` |
| ∂²ε/∂t² = c²∇²ε − ω₀²(1+φ)ε, ω_gap² ≈ 52.36 | 1 | derived from same + `omega2 = 20.0` (line 194) |
| c_s = h₀/dt is the ρ/c phase speed (coherence speed) | 1 | `cassi_particle_merge.glsl:19,104-105,351` + stencil c²=1 |
| merge subsonic gate = sharp threshold at the coherence speed | 1 | `pass_best:347-352` |
| ρ decouples from ω₀² (c_s invariant to coupling) | 1 | mode-decomposition algebra |
| "sound = waves of coherence"; phonon acoustic/optical analogy | 2 | §4 mapping |
| ρ carries coherence / ε (eps²) suppresses it in q_coh | 2 | §4;
| `qcoh_at:161-163` gives the quantities, the "carries/propagates order" reading is interpretive |
| accretion realism: subsonic-inflow = condensate formation condition | 2 | §3; hypothesis tier in `coherence_merge_rnd.md:262-266` |
| the ρ wave is "coherence" in the physical sense of ordering spacetime | 3 | not implied by the bare wave equation alone |

**Bottom line (TIER-1):** the merge's sound speed c_s = h₀/dt is, exactly, the phase speed
of the gapless coherence field ρ = EY+EI — so "sound is waves of coherence" holds in this
sim *by construction*. The gapped ε mode is the optical-branch counterpart: it oscillates at
ω_gap ≈ 7.24 rad/step and cannot transmit long-range order. The interpretation of ρ as
physical "coherence" (rather than just its mathematical carrier) is TIER-2/3.

---

## §7 Implications for the Cassi project

**Scope:** cross-project implications of the §2 decomposition, classified
against the corpus. Every "already claimed" item is quoted with
`doc`/`file:section`. Tiering follows the note's key and the parent repo's
own epistemic discipline. §1–§6 are untouched.

### 7.0 The one-line answer

The decomposition (§2) is **new structure and vocabulary** — no document in
the corpus names a "gapless/acoustic ρ mode" or a "gapped/optical ε mode,"
a "mass gap," or a "coherence carrier" for the two-fluid field. **Every
number it produces was already derived, measured, and verified elsewhere.**
The note's value is therefore **provenance and unification**, not new
constants.

### 7.1 All the key numbers already existed

| §2 result | prior home (the number is known & verified) |
|---|---|
| ω_gap² = ω₀²(1+φ) = 20φ² ≈ 52.36, ω_gap = 7.2361 | the **breather** Ω = √(ω₀²(1+φ)) = 7.2361, derived and verified: `CassiCosmos/MESHLESS_PLAN.md` §(Stage 0) + §1 (measured 7.3144, G0–G4/1); `physics/…/neural_closure` G33 matches to 0.08% |
| ε = EY−φ·EI is the gapped deviation; ε = 0 ⇒ free propagation | the **photon condition** EY = φ·EI: `predictions/cassi_definitions.md` §"Electromagnetism" — under EY=φ·EI the ω₀² terms vanish → ∂²E/∂t² = c²∇²E (Maxwell); "Photon: traveling EY/EI wave at φ-resonance" |
| c_s = h₀/dt = ρ phase speed (coherence carrier) | coherence speed **measured**: `foundations/qi-as-spatial-spacing-signal.md` §1/§3.5 (`v_c ≈ 0.92 cells/unit-t ≈ the wave speed c`), `audit.md:165` ✅ |
| subsonic merge gate = derived condensation criterion | hypothesis-tier in `research/coherence_merge_rnd.md` §3b ("`|v_t| < c_s`, c_s = h₀/dt the grid wave speed"; "structure forms where the flow becomes subsonic") |
| sound = waves of coherence | a *built audio manifestation* already exists: `research/meshless/synth_design.md` sonifies the breather ω₀√(1+φ)≈7.2 as a 13.75 Hz drone |

**What §2 genuinely adds:** (i) ρ = EY+EI is the *eigenmode* that decouples
exactly (∂²ρ = c²∇²ρ) — the mode-decomposition *origin* of the gapless
carrier, not asserted; (ii) the breather *is* the ε mode at its gap — the
known 7.2361 is given a spectral home (the optical branch); (iii) the photon
condition ε = 0 is *derived* as "zeroing the gapped mode removes the mass
term," re-deriving `cassi_definitions.md`'s condition from the mode structure;
(iv) v_c ≈ 0.92 is *explained* as the ρ front speed of the same wave system.
[TIER-1: §2 algebra + the cited prior numbers.]

### 7.2 Cascade-rung numerology (honest: no rung hit)

| qty | value | log_φ | near-integer? |
|---|---|---|---|
| 1+φ (gap factor) | 2.618034 **= φ²** | 2.000 | **exact — a clean 2-rung ratio** |
| ω₀² | 20.0 | 6.225 | +0.225 — **NO** |
| ω_gap² = ω₀²φ² | 52.361 | 8.225 | +0.225 — **NO** |
| ω_gap = φ·ω₀ | 7.2361 | 4.113 | +0.113 — **NO** |

The single exact structural fact is the **ratio** ω_gap = φ·ω₀ (one clean
frequency-rung step, because 1+φ = φ²). The **anchor** ω₀² = 20 is **not** a
rung. **Do not claim a rung hit.** This connects to a known open problem:
`MESHLESS_PLAN.md` §9 R1 — *"ω₀² = 20.0 provenance: NO derivation exists in
the theory docs; ω₀ is a sim-numerical scale-setting constant."* §2 inherits
that gap; the honest open item is whether ω₀² has any φ-anchor (log_φ 6.225
says: not obviously). [TIER-1 numerology; the ladder is
`cascade_ladder.py`/`foundations/dimensionful-cascade.md` §3.]

**Conflation guard:** the cascade machine's `omega0 = 2π/lnφ ≈ 13.06`
(`cascade_ladder.py:385,494,538`) is the P(k) log-periodicity period and is
**unrelated** to the two-fluid ω₀² = 20. Do not connect them.

### 7.3 Three distinct sound speeds in the corpus — do not conflate

- **(A) sim lattice speed** c_s = h₀/dt (`cassi_particle_merge.glsl:19,
  104-105`), scale-free, code units, §2-derived. This is THE subject of the
  note.
- **(B) theory BHM sound speed** — `parameter-inventory.md` §3.2:
  `c_s² ~ (ħ²/m²a₀²)·(φ⁻²/(1+φ)) ≈ 0.146`, with **`φ⁻²/(1+φ) = φ⁻⁴` exactly**
  (clean φ-power; a tidy restatement worth keeping). A different genesis
  (Bohm quantum potential), not the lattice step.
- **(C) SPARC hydrostatic condensate** c_s ≈ 14 km/s, universal ratio
  `c_s/v_DM,flat = 1/√(2φ⁶) ≈ 0.167` (`foundations/phi_attractor_synthesis.md`
  §14.2; `experiments/sparc_qi/…_v3-9.py`), from ξ = φ⁶. Same *class*
  (coherence-medium sound speed), different scale and genesis.

The Tier-3 bridge that would unify them: if the cascade base rung sets
h₀ → ℓ_Pl and dt → t_Pl, then h₀/dt → c, turning the scale-free lattice speed
(A) into the physical light speed — only then do (A),(B),(C) and the
`cassi_definitions.md` photon condition meet. **No document currently claims
"light = coherence wave of the vacuum"** (searched speculations/ +
consciousness/ + predictions/); `qi-as-time-clock.md` §4/P3 already treats
t_n = ℓ_n/c via one shared speed as *trivial*, so this bridge is constructive
framework-consistent language, not a new numbered claim. **TIER-3.**

### 7.4 Other parts of the project

- **(a) Cascade machine (M2):** ladder `cascade_ladder.py` runs the same
  field; its CFL homothety (`dt·min(1,L/10)`, `m2_design.md` §1.5) is the
  per-level statement of "c_s = h₀/dt." Tier-2 connection, no new physics.
- **(b) Gravity-from-flow / river law:** the Poisson source reads
  `ρ = E_Y+E_I` (`hypotheses/gravity-from-flow.md` §1.1) — the exact gapless
  mode; the river object `C = −∇·J` (§2) is built on the same fields §2 makes
  wave-meaningful (ρ is an acoustic-density carrier, not an advected patch).
  Tier-2 interpretation; no prior doc says this.
- **(c) Multigrid:** the coarse level solves the **same** `∇²Φ = ρ` operator
  (`cascade_multigrid/multigrid_design.md` §(c)) as the ρ-wave's Laplacian —
  operator-sharing, **not** CFL/speed inheritance (a static solve, no
  time-step). Tier-2.
- **(d) Mind engine / consciousness:** the mind engine runs
  `cassi_two_fluid.glsl` verbatim (UNIFICATION.md §1.4), so the ρ/ε split
  applies to the 7599-bridge field. Standing-coherence claims
  (`consciousness/trauma-as-frozen-gate.md`, `time-memory-and-wake-locks.md`)
  are gapped (non-propagating ε) phenomena in this vocabulary; "coherence
  waves as carrier" is Tier-3, consistent but not implied.
- **(e) Falsifier machinery:** the four §5 predictions build directly as new
  verify scenes (§7.5). Note §5-pred-1 corrects the "stand-still" phrasing:
  the non-propagating input is the ρ-null, ε-nonzero state (EY = −EI), not
  EY = φ·EI (which is ε = 0 and propagates).

### 7.5 Recommended next steps (ranked)

1. **Falsifier scenes for §5.1–5.4** (ρ-front speed = h₀/dt; pure-ε gap; sharp
   subsonic threshold; ω₀²-independence of c_s) — instantiate on the existing
   `verify_q_growth.gd`/`verify_merge*.tscn` battery pattern.
2. **Header comment in `cassi_two_fluid.glsl`** documenting the ρ/ε split and
   the `ω_gap² = 20φ²` identity (implicit today).
3. **Patent the vocabulary in the merge shader** comment block (lines 18–19,
   104–105): "c_s = h₀/dt — the ρ-wave (coherence) phase speed."
4. **Ladder registry:** record only the exact `ω_gap = φ·ω₀` ratio; decline an
   absolute rung; append the ω₀² = 20 provenance question to `MESHLESS_PLAN`
   §9 R1 as still open.
5. **Optional:** a compact-pulse ρ probe contrasting the exact front speed
   with the prior standing-wave v_c ≈ 0.92 (`audit.md:165`).

---

## §7.6 The second-order form is the fundamental evolution equation

Owner decision (2026-08-15): Qi is the flow between the two fluids and is always
present, so the coupling term ω₀²(EY − φ·EI) never vanishes — the SECOND-ORDER wave
form (this note's subject) is the fundamental evolution equation. The first-order
gated form (`CassiTheory/foundations/cassi-first-principles.md` §1.2–1.3) is the
quasi-static/relaxation limit of the same dynamics, not a separate equation.

Consequences, in this vocabulary:
- The acoustic (ρ) and optical (ε) branches are always live; there is no regime
  where the ε mode is absent.
- The photon condition ε = 0 (`predictions/cassi_definitions.md`, EY = φ·EI) is an
  ideal limit — exact only where the flow is perfectly coherent; generically the
  gapped mode is weakly excited.
- c_s = h₀/dt (the coherence/sound speed) is a property of the fundamental
  second-order form, independent of ω₀² — set by the medium's stiffness (the
  Laplacian), not the coupling.
- The §7.5 falsifier scenes are the empirical anchor for this commitment.

[TIER-2: framework commitment, consistent with the TIER-1 §2 algebra; anchored by
the §5 predictions.]
