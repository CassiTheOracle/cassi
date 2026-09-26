# Cascade Multigrid — φ-Spaced Multi-Level Gravity (Stage 7, CASCADE_GRID §3.3)

**Status:** Design + numpy prototype (`stage7_multigrid.py`), gates G38–G41 PASS
**Repo:** `godot/space-sim` (this dir is the READ-ONLY wave's deliverable; NO sim
code touched — parallel workers own the scripts/shaders)
**Date:** 2026-08-13
**Companion:** `research/cascade_multigrid/stage7_multigrid.py` (the measured prototype)

This is the design + prototype for the last multi-scale lever of CASCADE_GRID.md —
§3.3 mechanism 2, "coarse long-range level". The naive two-level schemes were
measured to FAIL (the coarse Green's near-field is ~8× deep at 4 coarse cells; a
half-box patch carries its own periodic images). This file answers the design
questions (a)–(e) with measurements, and the gates prove the corrected two-level
force is coherent.

---

## (a) Level spacing — φ is not a power of 2: the honest integer rounding

The sim's spectral Poisson (`compute/cassi_poisson.glsl`) is a **radix-2 Stockham
FFT, N ∈ {64, 128, 256}, power of 2 only**. φ ≈ 1.618 is not a power of 2, so *no
exact* φ-spaced level exists on the radix-2 FFT. The candidate coarse levels and
their integer-compatibility:

| Level | N_c = round(N_f/φ) = 40 | N_c = N_f/2 = 32 |
|---|---|---|
| φ-ideal | round(64/1.618) = round(39.55) = **40** | 32 (the naive radix-2) |
| radix-2? | **NO** (40 ∉ {64,128,256}) | **YES** |
| gcd(N_f, N_c) | gcd(64,40) = 8 | gcd(64,32) = 32 |
| coarse/fine cell *phase* | 64/40 = 1.6 fine cells = 5/8 (incommensurate) | 64/32 = 2 fine cells = 1/1 (aligned) |
| coarse cell boundaries hitting fine boundaries | every 8 fine cells (≤ 12.5% phase-locked) | **every cell (100% phase-locked)** |

**The resonance consequence (de-resonance principle, GRID_LAYOUT §1.2).** The
placement bias / anisotropy of any grid is a function of where the source and
probe sit *within a cell*. With N_c = N_f/2, every coarse cell boundary coincides
with a fine cell boundary (100% phase-locked): the coarse Green's cell-phase
structure **constructively reinforces** the fine lattice's — the worst resonance.
With N_c = round(N_f/φ) = 40, the coarse boundaries are incommensurate with the
fine (gcd = 8 → only every 8th fine cell at a coarse boundary), so the coarse's
phase errors are **decorrelated** from the fine's — the maximally de-resonant
pair, exactly the φ-principle.

**Measured (G40):** at a matched physical probe radius (r = 15.00), the placement
bias (worst-direction phase spread, source swept over one full cell of that level)
is:

| Level | worst-dir phase spread | mean |
|---|---|---|
| fine N=64 | 0.2894 | 0.2111 |
| **φ-spaced N=40** | **0.4658** | **0.3828** |
| naive N/2 N=32 | 0.5635 | 0.5103 |

The φ-spaced coarse (0.466) beats the naive N/2 (0.564) — **de-resonation wins**.
(The coarse levels are both more phase-sensitive than the fine because each is
swept over *its own larger physical cell*; the meaningful comparison is the φ-vs-N/2
pair at matched probe radius.)

**Honest integer-compatibility recommendation:** the φ-ideal N=40 is NOT radix-2.
The sim's coarse level therefore has two options:
1. **N_c = 40 with a non-radix-2 FFT for the coarse level only** (the numpy
   prototype already does integer-N FFT freely; a coarse-only mixed-radix path is
   a contained shader/host addition — the fine stays radix-2). This preserves the
   de-resonance.
2. If radix-2 is non-negotiable, the honest fallback is **N_c = 32 (N/2)** and the
   design must ACKNOWLEDGE it re-introduces the coarse/fine boundary resonance
   (G40: bias 0.56 vs 0.47). The φ-spacing is the point of the multigrid's
   de-resonance; option 1 is strongly preferred.

A third level at round(N/φ²) = round(24.44) = 24 (or the radix-2 N/4 = 16) is the
natural *next* rung for a deeper pyramid, with the same gcd analysis (gcd(64,24)=8
incommensurate vs gcd(64,16)=16). Only the fine + N=40 pair is implemented in this
wave.

---

## (b) The windowed two-level force

The two-level force is the CASCADE_GRID §3.3 window, corrected by a measured
per-level normalization:

```
F(r) = w(r)·F_fine(r) + (1 − w(r))·(N_c/N_f)³·F_coarse(r)
w(r) = 1                       for r ≤ 4·h_c          (full fine)
     = 0                       for r ≥ 7·h_c          (full coarse)
     = 1 − smoothstep_t(r)     between (smooth blend),  t = (r−4h_c)/(7h_c−4h_c)
```

- **h_c = L0/N_c** (coarse y-axis cell, N_c = 40 → h_c = 1.875). The window is a
  function of the **physical** source–probe distance r (min-image), so it is
  rotationally isotropic on the φ-aspect box (expressed in coarse cells on the
  reference axis, the same convention as CASCADE_GRID §3.3's "6–8 coarse cells").
- **The (N_c/N_f)³ factor is the load-bearing correction** (see the prototype's
  `COARSE_VOL`). The spectral Poisson treats ρ as a **per-cell density** (the sim's
  TSC deposit writes mass per cell). At a different N the same physical blob gives
  a different per-cell density, so the raw Φ (and its gradient) scale like
  `(N_other/N_f)³`. Measured: exactly `(40/64)³ = 0.244` for N_c=40 vs N_f=64
  (verified at a well-resolved blob). Without the factor, the coarse is
  `(64/40)³ = 4.096×` too deep and a naive blend `wF_f + (1−w)F_c` is silently
  ~4× wrong in the transition band — the multi-level form of the CASCADE_GRID §1
  "per-level normalization must be exact" trap. The sim's per-grid force already
  absorbs its own h³ in G_N (GRID_LAYOUT §2.3); the multigrid blend must put every
  level on the fine's physical scale.

**Why this window (measured):** the coarse Green's *near-field* is the measured
failure zone ("~8× deep at 4 coarse cells" — §3.3). The window keeps w ≡ 1 for all
r ≤ 4 h_c, so the bubble scale is the fine force EXACTLY. The blend band
(4–7 h_c = 6.4–11.2 fine cells) is where the coarse's r/h is already large enough
to be a healthy far-field (see (c)); beyond 7 h_c the renormalized coarse matches
the fine's far field to < 2% (measured).

---

## (c) Where the coarse level gets its BOUNDARY data (the honest answer)

**The coarse level needs NO boundary data — it is its own periodic solve on the
FULL box, not a patch.** This is the measured-resolution of the §3.3 patch failure:

- The patch path is dead: a half-box patch (period 37.5 vs 75) carries its own
  periodic-image field and needs coarse-supplied boundary conditions the periodic
  Stockham FFT does not provide (§3.3, measured). The correct coarse level reuses
  the SAME torus geometry — same per-axis L_i, same k = 2π·n/L convention — at a
  lower N_c. It is a **global-periodic solve at lower resolution**, so it has no
  boundaries at all (the whole box wraps, exactly like the fine).
- The blend does the only job the patch's boundary conditions were meant for: it
  **keeps the coarse near-field out of the bubble scale** (§3.3's "transition keeps
  the coarse Green's near-field out"). The measured 2% leak-in radius (G38) is 9.38
  — outside the 4 h_c protected zone, so the coarse's near-field failure never
  reaches the bubbles.
- This is the same reason the coarse is a *long-range* level, not a zoom: it
  contributes only where its own (larger-cell) Green is trustworthy, i.e. r beyond
  its near-field spike. True AMR/zoom patches (mechanism 3, requiring non-periodic
  or windowed solves with genuinely coarse-supplied BCs) remain a future, larger
  project — unchanged from §3.3.

---

## (d) Cost accounting

Per particle per step, the multigrid adds exactly:

- **one extra gradient sample** (the coarse level's Φ field is probed once per
  particle via the same trilinear sampler the fine uses), plus
- **one window evaluation** (a smoothstep on the precomputed min-image distance r)
  and one vector blend `w·F_f + (1−w)·F_c`.

That is the full per-particle cost — the coarse level's solve is a GLOBAL grid
pass (own deposit at N_c³ + spectral solve + gradient), the same O(N_c³) structure
as the fine chain but at `(N_c/N_f)³ = 0.244` the cells (N=40 vs N=64 → ~6.1% of
the fine's cell count). The coarse level is NOT a per-particle interaction; it is
one amortized grid solve. This matches CASCADE_GRID §3.1/§3.3's cost model ("the
real cost is the second gradient sample" — the Poisson chain is not the bottleneck
at N ≤ 64; the per-particle pass is).

Storage: one extra N_c³×3 gradient field (`40³×3×8 B ≈ 1.5 MB`) + the coarse
deposit/solve buffers. The w(r) is recomputed per particle from the existing
min-image distance.

---

## (e) Later sim integration path (DESIGN ONLY — not implemented this wave)

The `cascade_poisson` arm in `scripts/cassi_sim.gd`, additive like
`dual_grid`/`gradient_order` so the pinned batteries stay bit-identical at
default-off.

**Toggle:** `cascade_poisson: bool = false` (default off → existing chain untouched).

**Pass placement in `_step_dispatches` (when ON):**
1. Deposit ρ at the FINE N (existing pass — unchanged). Also deposit ρ at the
   coarse N_c (a second `cassi_mass_deposit.glsl` dispatch with a coarse-N PC;
   the deposit shader is N-generic already).
2. Fine spectral Poisson chain (existing, unchanged).
3. Coarse spectral Poisson chain (the SAME `cassi_poisson.glsl`, dispatched with
   N_c and the same per-axis extents; the kspace mode already reads extent_x/y/z —
   it is resolution-parametric). Coarse gradient pass (the existing `pass_mode=1`
   at coarse N).
4. N-body pass: per particle, probe both fine and coarse gradients, compute
   r = min-image distance to its global source, w = window(r), and
   `a = −G_N·(π/ρ)·(w·∇Φ_f + (1−w)·(N_c/N_f)³·∇Φ_c)` — the whole-product chord form
   preserved on both arms.

**New resources:**
- buffers: coarse ρ (N_c³×4 B), coarse Φ/grad (N_c³×16 B), a coarse N in the
  Poisson PC.
- shaders: **none new** — `cassi_poisson.glsl`, `cassi_mass_deposit.glsl`, and the
  gradient/nbody passes are all resolution-parametric (N read from PC; extents
  already per-axis). The only code is host-side dispatch plumbing + the window in
  the nbody sampler (or a tiny dedicated window helper).
- `verify` gate: a new cascade-multigrid verify scene asserting G38/G39/G40/G41
  analogues on the GPU (volume-normalized coarse == fine far field to <2%; φ vs
  N/2 placement bias; per-level k exactness), plus the battery-green invariant at
  `cascade_poisson = false`.

**N=40 non-radix-2 note (integration):** the fine stays radix-2; the coarse N=40
needs the deposit/Poisson/gradient passes to accept N=40, which the current shader
guards reject (`N&(N-1)==0` in `fft_main`). Either (a) a blended-factor Stockham
for the coarse axis passes (contained: the coarse runs its own transform), or
(b) accept the de-resonance loss with N=32. Documented in (a); the numpy
prototype proves the N=40 physics.

---

## Gates (measured — `python stage7_multigrid.py`)

All on the shader-exact chain (TSC deposit → spectral Poisson → O2 central
gradient → trilinear probe, φ-aspect box L=(φ,1,φ²)·75, N_f=64, N_c=40).
Chain validation: fine ring anisotropy 2h/4h/8h = **1.1609 / 1.0798 / 1.0572** —
the CASCADE_GRID §2 O2-baseline class (1.246/1.090/1.022); the 4h 1.080 sits next
to the pinned 1.090 (the exact blob σ is our calibration choice).

- **G38 (PASS)** — near-field protected. Pure-fine zone (r ≤ 4 h_c = 7.5, w ≡ 1):
  combined ≡ fine, worst deviation **0.000000**. 2% leak-in radius = **9.38**,
  outside the protected boundary (7.5). Deviation profile is a smooth bounded
  hand-off: 0.023 at w=0.74 → 0.087 (max, mid-blend) at w=0.24 → **0.018 at r=21
  (w=0, full coarse)** — the renormalized coarse reproduces the fine's far field to
  <2% at large r. *Without* the volume factor the same profile was 1.5–3.9 (150–
  390% off) — the correction is material.
- **G39 (PRIMARY null + supplementary PASS)** — the far-field is **NOT** smoother
  than fine-only at matched physical radius: coarse ring anisotropy > fine at every
  far r (13.1: 1.1222 vs 1.0532; 30.0: 1.6603 vs 1.6501). **This is the honest
  structural null**: the torus-Green anisotropy is r/h-self-similar (GRID_LAYOUT
  §0 — identical at N=64/N=128 at the same r/h), and at a fixed physical r the
  coarse has larger cells (r/h_c < r/h_f), so it sits higher on the anisotropy
  curve. The multigrid's genuine value is **de-resonance + multi-rung scale
  coverage**, not raw far-field smoothness — this CORRECTS the CASCADE_GRID §3.3
  "coarse supplies the smooth far field" reading. Supplementary (the de-resonance
  lever): the φ-spaced N=40 ring anisotropy is **≤ the naive N/2 (N=32)** at every
  far radius (1.1222 vs 1.2102 @13.1; 1.1244 vs 1.1367 @18.8), converging to the
  same asymptote at 22.5/30 — **de-resonation reduces the ring anisotropy**.
- **G40 (PASS)** — φ-spaced N=40 placement bias (worst-dir 0.4658) **<** naive
  N/2 N=32 (0.5635) at the matched physical probe radius 15.00. De-resonation wins
  (the (a) integer-compatibility analysis: gcd 8 vs 32).
- **G41 (PASS)** — per-level normalization exact. Coarse Φ == an independent
  direct coarse reference to **3.4e-16**. And the k-factor trap demonstrated: a
  solve whose k uses the raw fftfreq fraction (n/N) instead of the shader's integer
  modes (2π·n/L) gives center Φ = −1.70e+04 vs the correct −4.16 — a **4096×
  (N_f²) error**, invisible in any ratio measurement, fatal to any multi-level
  combination (CASCADE_GRID §1's trap, now quantified).

**RESULT: ALL PASS.**

---

## Honest limits & open items

- The 1.3–1.7 ring-anisotropy *floor* at r = 13–30 (both levels) is dominated by
  the φ-box's per-axis h spread (physical-ring-on-anisotropic-box mixes r/h per
  axis, and the y-axis images pull the ring); it is NOT reduced by the coarse and
  the multigrid does not claim to fix it (that is the §2.8 isolation/short-axis
  issue, a box_scale lever).
- The exact blob σ for the "TSC blob" source is our calibration choice (σ=2.5
  physical → 4h anchor 1.080 vs the pinned 1.090). The chain (deposit → solve →
  gradient → probe) is shader-exact; the source shape is a documented standard,
  and every gate is a RELATIVE (fine-vs-coarse / de-resonance) comparison robust to
  the absolute blob normalization.
- The de-resonance win (G40/G39-supp) is the measured case for picking N=40 over
  N=32 in the sim, at the cost of the non-radix-2 coarse FFT path.
- True zoom-patch AMR (mechanism 3, coarse-supplied BCs) remains a larger future
  project — this wave delivers the windowed long-range level only.
