# Helix-solver program — consolidated report

**Date:** 2026-08-16 · This is the program's answer document. Every load-bearing number is
cited to the file:line of the wave report or provenance doc that produced it; the waves themselves
are reproducible from `CassiCosmos/` with the `verify_*` gates and `*_probe.py` scripts listed in
each report's traceability section.

## 1. The question and the answer

**Question:** is the helix-solver's candidate engine mechanism — the anisotropic two-fluid
operator, its φ-shelled grid, and its coherence-modulated gravity — a viable engine upgrade *yet*?

**Answer: not yet, and it is no longer an open shape question.** The headline that motivated the
program — the "oblate bubble" record σ_x/σ_y = 1.422, σ_x/σ_z = 2.510 — is **closed as
unverified/artifactual**, established by three independent legs (provenance audit → claim-map →
cascade-repro) plus four mechanism nulls (waves 8–12). It was never an engine observable, it is not
real even in its own source, no engine sector produces it, and no document in the workspace claims
the engine does. The **one validated candidate** for a real engine change is the **Hamiltonian
φ-completion toggle (U1)** — a one-line, default-off, bit-identical-off toggle that restores the
two-fluid coupling's symplectic structure: it preserves the φ-attractor null mode to machine
precision, shifts the anti-phase splay frequency by the predicted ratio 1.1749 (vs 1.1756), and
replaces the engine's ~10% non-conserved energy oscillation with a bounded ~0.6% integrator shadow
(`twofluid_hcompletion_report.md:7,11-12,45`). That toggle is the program's genuine deliverable; it
is frozen for the engine in `twofluid_hcompletion_engine_prereg.md`, not yet implemented.

## 2. Verdict table — every wave

| Wave | Question | Verdict | Key number | Commit |
|---|---|---|---|---|
| w1 | Single φ-ratio interface reflectivity (two-medium impedance) | CONTRADICTS raw transparency | γ = 23.61% | 70e12ce |
| w2 | Axial design law — taper reflectivity across a φ-rung | SUPPORTS (interior solved; design law m\*=0) | 0.658% (m=0) → 0.0018% (m=12) | d30ca07 |
| w3 | Two-medium coarse-fine boundary — explicit rim | SUPPORTS (rim well-defined; taper ACHIEVES) | 23.32% energy / 0.0012% at m_t=12 | b715702 |
| w4 | Bracketed-interpolation rim (the faithful sim rim, 1D) | CONFIRMS mechanism, REJECTS magnitude | 0.128% at r=φ (180× < extrapolation) | 8a763d9 |
| w5a | φ-ellipsoid 2D anisotropy imprint | EMERGES (later superseded as seed-inherited) | σ_x/σ_y 1.000 → 1.212 | fa8bb91 |
| w5a-followup | Bias-free edge-gradient proxy | proxy validated; dynamical edge DOES NOT EMERGE | proxy 1.0000–1.0025 (Gaussian) | a16c4ec |
| w5 close-out | Two-fluid fidelity gates reworked to honest findings | engine coupling not a gradient of a potential → no conserved quadratic | drift = reported finding, never a gate | f377c17 |
| w6 | Full-3D oblate triaxial spheroid probe | direction confirmed, magnitude OVER-SHOOTS | σ_x/y = 2.227, σ_x/z = 3.251 | 6549dc4 |
| w7 | 3D σ-relaxation time trace | transverse → φ, axial over-drives | σ_x/y → 1.871, σ_x/z → 4.442 | 48eb3ce |
| w8 | Sim-operator correction — waves 6–7 oblate claims superseded | operator yields PROLATE, not oblate | σ_x/z = 0.329 | b62778d |
| w9 | Source-feed + Poisson-gravity (g=1) mechanisms | all three DO NOT EMERGE (still prolate) | σ_x/z 0.329 / 0.528 / 0.304 | cbe1b97 |
| w10 | Particle-nbody gravity (g=1) on the (φ,1,φ²) box | CONTRADICTS — cloud stays round | particle σ_x/z = 1.001 | 50ae5b5 |
| w11 | Cascade-repro — the record against its own source | CONTRADICTS — energy is round at every step | energy σ_x/z = 1.000 (coh 2.497) | 7c522dc |
| U2 | Lap-weight degeneracy crossing, family h=(φ,1,s) | CONTRADICTS — marginal point outside band | s\* = 2.268189 ∉ [2.356, 2.880] | efc8cec |
| U3 | Full φ⁶-modulated gravity g = 1+(φ⁶−1)·q | CONTRADICTS — φ⁶ active but isotropic | particle σ_x/z = 1.003 (7× faster collapse) | cb4a5cd |
| U1 | Hamiltonian φ-completion of the two-fluid coupling | null-mode + frequency SUPPORTED; frozen energy criterion NOT met | freq ratio 1.1749 vs 1.1756 | 63c8a4c |

Provenance documents (not waves): audit `27ad20f`, claim-map `15db3c8`, dated annotations
`0ff22d7`.

## 3. The oblate-record closure — four legs

**(a) Never an engine observable.** The engine ships **no σ / RMS-extent / ellipsoid-ratio
readout** — grepping `cassi_physics_engine.gd`, `cassi_sim.gd`, and the shaders for `sigma_x`/`σ_x`/
ellipsoid-as-readout returns nothing (`oblate_provenance_audit.md:153`). The "record" is a σ of a
field distribution, a quantity the running Godot sim does not measure.

**(b) Not real in its own source.** The numbers trace to one Python PDE,
`CassiTheory/visual-explainers/string_bubble_cascade.py`, where σ_x/σ_y = φ is **seeded into the
IC envelope** (`sigma_x = φ·sigma_y`, `oblate_provenance_audit.md:36,41`) and the axial 2.510 is a
single unseeded run with no ensemble. The cascade-repro wave ported the source faithfully and found
the oblate shape is a **transient** (peaks ~step 1800) that the code's own `idx_bubble` (3500) never
selects, and — decisively — the **energy** distribution is **round** (σ_x/σ_z = 1.000) at the very
step where the coherence σ reads 2.497 (`cascade_repro_report.md:8,12-14,47`). The 1.422 and 2.510
are not co-realizable at any single snapshot (`cascade_repro_report.md:51,61,68`).

**(c) No engine mechanism produces it.** The four candidate sectors all came back null: the
operator alone gives **prolate** (σ_x/σ_z = 0.329, `triaxial3d_simop_corr_report.md:10`); the source
feed / field-gain / Poisson-gravity g=1 arms stay prolate (0.329–0.528,
`triaxial3d_feed_report.md:12-14`); particle self-gravity g=1 leaves the cloud round (σ_x/σ_z =
1.001, `triaxial3d_particle_report.md:12`); and the full φ⁶-modulated gravity — though it genuinely
accelerates collapse 7× (peak/p₀ 11.096 vs 1.616) — is **isotropic**, leaving the cloud round
(σ_x/σ_z = 1.003, `triaxial3d_phigravity_report.md:13,18-20`).

**(d) Zero engine-claim sites.** The claim-map classified every workspace occurrence of the oblate
shape into theory-prediction / illustrative / unverified-quote, and found **no document asserts the
running engine or sim produces the oblate bubble** (`oblate_claim_map.md:78`). The one site needing
a dated provenance note is `CassiTheory/foundations/bubble-edge-geometry.md:11`
(`oblate_claim_map.md:20`).

## 4. The genuine positive

The transverse ratio **σ_x/σ_y = 1.580 ≈ φ** (the field bubble's true-frame extent ratio at t=2400,
`triaxial3d_particle_report.md:14,47`) is real and already in the engine: it is the (φ,1,φ²) box's
in-plane φ aspect, read back by construction — the Yang field genuinely extends φ× further along x
than y. It is the only anisotropy the field sector actually produces, it survives every mechanism
null, and it needs no change.

## 5. The unification record

**U1 — Hamiltonian φ-completion (the validated candidate).** Symmetrizing the engine coupling
M_eng = [[1,−φ],[−1,φ]] into M_ham = [[1,−φ],[−φ,φ²]] (same kernel) preserves the φ-attractor null
mode EY=φEI to machine precision (max|d| = 6.7e-17 engine, 6.3e-17 completed) and shifts the
anti-phase splay frequency by the predicted ratio √(1+φ²)/√(1+φ) = 1.1756 (measured 1.1749, 0.06%).
Conservation is restored in the physics sense — the completed form's energy drift is a **bounded**
leapfrog shadow saturating at ~0.6%, versus the engine's ~10% non-conserved oscillation — but the
frozen 1200-step `drift_B < 0.1×drift_A` criterion is **not** met (0.167; the 1200 window is the
worst case), while at all windows ≥ 2400 it is (0.048–0.066) (`twofluid_hcompletion_report.md:7,11-12,45`).

**U2 — lap-weight crossing (CONTRADICTS).** The operator family h=(φ,1,s) has exactly one marginal
point where the z-axis coasts, at s\* = 2.268189 — outside the frozen success band [2.356, 2.880];
the engine default (φ,1,φ²) runs **anti-diffusive on z**, not at the marginal point
(`lapweight_crossing_report.md:8,14,75-78`).

**U3 — φ⁶-modulated gravity (CONTRADICTS).** The chord factor g = 1+(φ⁶−1)·q is real and active
(7× faster collapse) but does **not** imprint the field's transverse anisotropy on the collapsing
cloud: particle σ_x/σ_z = 1.003, field σ_x/z = 1.160 unchanged from baseline
(`triaxial3d_phigravity_report.md:7,13,18-20`).

## 6. Open items

1. **Engine-toggle pre-registration** — `twofluid_hcompletion_engine_prereg.md` freezes the U1
   one-line change (EI-row coupling ×φ), the 30-arm battery protocol, and the rollback, before any
   engine edit. Pending the owner's greenlight.
2. **The 30-arm battery** — the U1 toggle's bit-identity and response arms execute only when the
   owner closes the Godot editor (the battery arms run windowed, never headless — `verify/README.md`).
3. **Provenance correction** — `CassiTheory/foundations/bubble-edge-geometry.md:11` still quotes
   "σ_x/σ_z=2.510 … φ-ellipsoid bubble confirmed" as a confirmed record; it needs a dated
   provenance note (the audit's highest-risk site, `oblate_claim_map.md:20`). Held for the owner's
   review — it is a CassiTheory doc outside this repo's path-limited commit scope.
