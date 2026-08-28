# Engine-toggle pre-registration — Hamiltonian φ-completion (U1)

**Date:** 2026-08-16 · This freezes the protocol for the possible one-line engine change **before**
any engine edit. No engine/shader file is edited by this document. The numpy evidence (`wave 13`,
commit 63c8a4c) is the **pre-registered expectation**, not the gate.

## 1. The change — the EI-row coupling gains ONE factor φ

The engine coupling is `∂²EY/∂t² = c²∇²EY − ω₀²(EY−φEI)`, `∂²EI/∂t² = c²∇²EI + ω₀²(EY−φEI)`
(`compute/cassi_two_fluid.glsl:10-11`). In `pass_a` the coupling is assembled as:

```
cassi_two_fluid.glsl:196    float omega2 = pc.omega2;  // ω₀² — resonance frequency (default 20.0)
cassi_two_fluid.glsl:197    float phi = pc.phi;
cassi_two_fluid.glsl:198    float ey_ei_diff = ey_old - phi * ei_old;
cassi_two_fluid.glsl:202    float acc_ey = lap_ey - omega2 * ey_ei_diff;
cassi_two_fluid.glsl:203    float acc_ei = lap_ei + omega2 * ey_ei_diff;   <-- the EI-row coupling
```

The Hamiltonian completion multiplies the **EI row** of the coupling by φ — the single difference
between the engine (M_eng = [[1,−φ],[−1,φ]], non-symplectic, ~10% energy oscillation) and the
completed form (M_ham = [[1,−φ],[−φ,φ²]], symplectic rank-1 projector, same kernel). The **only**
line that changes is line 203; line 202 is untouched (the completion does not touch the EY row).

**Proposed conditional form (default OFF, bit-identical when OFF):**

```glsl
    // U1 Hamiltonian completion (default OFF): EI-row coupling gains one factor φ.
    float acc_ei = lap_ei + (pc.ham_completion > 0.5 ? phi * omega2 : omega2) * ey_ei_diff;
```

When `pc.ham_completion = 0.0`, the ternary selects `omega2` and the expression is
**bit-for-bit** `lap_ei + omega2 * ey_ei_diff` — today's shader. When `= 1.0`, it becomes
`lap_ei + phi * omega2 * ey_ei_diff`.

**Push-constant plumbing (owner decision, NOT done here):** the PC struct is the canonical 16-float
layout (`cassi_two_fluid.glsl:37-45`, `scripts/contracts/layout.gd §PC`). The flag needs one slot.
Two options, both leave the OFF path bit-identical: (a) repurpose the documented-unused
`gravity_mode` float (`cassi_two_fluid.glsl:41`, "unused here (nbody gravity selector)") as
`ham_completion`; (b) extend the struct to a 17th float and update `layout.gd §PC`. Option (a)
touches no layout contract; option (b) is semantically cleaner. Either is acceptable to the frozen
protocol as long as OFF is bit-identical.

## 2. Battery protocol

Executes **only** when the owner closes the Godot editor and greenlights (the arms run windowed,
never headless — `verify/README.md:73-76`).

**(i) Toggle OFF → bit-identity gate.** The full 30-arm battery (`verify/run_all.gd`) must stay
**30/30 green**. Any arm regression under OFF is a build bug, not a verdict — the toggle is not
load-bearing until OFF is bit-identical.

**(ii) Toggle ON → which arms respond, which must not.** The two-fluid coupling is exercised only by
the arms that evolve the coupled EY/EI fields through the ω₀² term:

- **Expected to respond (frequency/energy signature):** `verify_falsify` (w₀ estimator port —
  `verify/README.md:58`), the `verify_voronoi3d` family (`verify_voronoi3d`, `_moving`, `_aniso`,
  `_moving_aniso` — per-cell two-fluid wave vs numpy reference — `verify/README.md:49,55-57`), and
  `verify_mind_engine` (attractor-ratio deposit + off-ratio evolution — `verify/README.md:59`).
- **Must NOT change (particle / gravity / UI / stencil-only):** `verify_fft`, `verify_fmm`,
  `verify_gravity_modes`, `verify_merge`, `verify_meshless_sim`, `verify_meshless_stability`,
  `verify_particle_vfx`, `verify_phi_box`, `verify_ring`, `verify_river_law`, `validate_sim_ui`,
  `verify_survey`, `verify_synth`, `verify_volumetric`, `verify_meshless_gravity`,
  `verify_river_isotropy`, `verify_merge_sim`, `verify_meshless_reconstruct`,
  `verify_particle_vanish`, `verify_bh_accretion_engine`, `verify_merge_engine`,
  `verify_multigrid_engine`. These exercise the stencil, the gravity sector, the particle pipeline,
  or the UI — none of which the one-line coupling change touches.

**(iii) Frozen acceptance decision.** SUPPORTS iff, with the toggle ON:

1. **Frequency:** the in-engine anti-phase splay frequency shifts by the measured numpy ratio
   **1.1749** within the frozen band **[1.14, 1.21]** (±3%), measured by `verify_falsify`'s w₀
   estimator or a dedicated FFT of the EY−φEI component (the numpy expectation:
   `twofluid_hcompletion_report.md:11-12,50-57`).
2. **Energy:** the in-engine energy-drift signature matches the bounded shadow — the completed
   form's drift is bounded (~0.6%, saturating) versus the engine's ~10% non-conserved oscillation
   (`twofluid_hcompletion_report.md:45`).
3. **Null mode:** the φ-attractor null mode (EY = φEI) is unchanged — the attractor-ratio deposit
   stays at the fp32 floor in `verify_mind_engine` (`twofluid_hcompletion_report.md:50-55`).
4. **No regression:** every must-NOT-change arm (ii) stays green.

CONTRADICTS iff the null mode moves, the frequency does not shift per (1), or a must-NOT-change arm
regresses. INCONCLUSIVE on NaN/instability.

## 3. Rollback

The toggle reverts with a one-line flip (`ham_completion` → 0.0). No schema, data, or layout change
is entailed by option (a); option (b) reverts the one added PC float. There is no persisted state to
migrate.

## 4. Verdict vocabulary

PASS / FAIL / NULL per the house battery contract (`verify/README.md:20-28`). The numpy U1 evidence
is the **pre-registered expectation** — it is what the in-engine arms are checked against — and is
**not** itself the gate; the gate is the in-engine battery measurement under the frozen decision
tree above.

## Amendment (2026-08-16) — PC-slot decision settled: variant B

The PC-slot choice is settled by evidence. **Variant B** — the 17th PC float
(`_diag/ham_completion_variantB.patch`) — is the selected form: `ham_completion` is its own field and
never aliases the nbody gravity selector.

**Variant A is disqualified.** The host writes the live nbody gravity-mode value into the
`gravity_mode` slot at `cassi_physics_engine.gd:2215` (`encode_float(40, float(gravity_mode))`), so
repurposing that slot carries the gravity selector (0–5) into `ham_completion`. Under gravity modes
1–5 the value reads `> 0.5` and the completion enables silently — violating the OFF bit-identity
contract. The slot is unused by the two-fluid shader body but is not host-zero.

Variant B's change therefore includes the host plumbing, recorded as part of the frozen change: the
two host resize lines `cassi_physics_engine.gd:1186` and `cassi_sim.gd:2303` (`16 * 4` → `17 * 4`),
plus the ON/OFF encodes at offset 64 (`encode_float(64, 1.0)` for ON; `encode_float(64, 0.0)` for
OFF — `resize` zero-fills, so OFF is safe without an explicit write).

No threshold, verdict, or pin changes. The conditional form, the §2 battery protocol, and the §3
rollback stand as frozen.
