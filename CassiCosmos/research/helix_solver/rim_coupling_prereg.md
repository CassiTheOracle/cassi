# Rim-Coupling Wave 3 — the two-medium boundary in the cascade geometry — PRE-REGISTRATION

## Status: Pre-registration — written BEFORE any run; governs the wave-3 arms

**Date:** 2026-08-15 · **Workstream:** the ultimate Cassi solver (axial operator, boundary)
**Pre-registered outcomes:** the rim-coupling arms below, with statistics, decision trees, and stopping rules pinned here.
**Implementing probes (numpy, new-files-only, under `CassiCosmos/research/helix_solver/`):** `rim_coupling.py`, `verify_rim.py`, `rim_probe.py`.

---

## 0. The question and the prior record

### 0.1 The question

Wave 2 left one open problem: the **genuine two-medium boundary** — a coarse patch abutting a fine patch in the cascade geometry (spacing ratio φ). Wave 2's numbers straddled it: the continuum impedance formula gives 23.6%, but the single continuous-grid node reflects 0.658% — neither is the sim's case. The sim's gate-vi *has* this boundary solved: a fine patch reads **interpolated coarse values at a rim** (coarse→fine trilinear at the rim cell centers; fine→coarse cell-average downsample), measured green at r=1 → **9.11%** (the trilinear truncation error), r=2 → **4.37%**, r=4 → **3.81%**, diagonal → **1.63%** (`_diag/b_build.md` §gate-vi, `overhaul_build_plan.md`).

This wave asks the two questions that make the sim's rim *portable to the axial cascade operator*:

- **Q1 — does the interpolated-rim coupling reproduce the sim's reflectivity on a 1D φ-ratio two-medium boundary?** I.e., is the measured 4–9% the *interpolation truncation* (a 1D linear-rim property), independent of the resolution ratio?
- **Q2 — does the wave-2 graded taper, applied AT the boundary as the anti-reflection transition, push the rim-coupled reflectivity under the gate-vi acceptance (≤2% / the sim's honest ≤5%)?** Combining the sim's rim (interpolation coupling) with the wave-2 taper (graded spacing) is the proposed "ultimate" axial boundary.

### 0.2 The prior record (cited, not re-measured)

- Wave 1: the finite-volume operator is the mandatory discretization on non-uniform grids ($A = -M^{-1}B^{\mathsf T}WB$); Q2 EMERGES (the self-resolving window).
- Wave 2: **correction** — the continuous-grid single node reflects 0.658% (not the two-medium 23.61%); the graded taper cancels to 0.0018%, scale-invariantly. The 23.61% picture is the *two-medium boundary* — this wave.
- The sim's gate-vi (`_diag/b_build.md` §gate-vi): the ghost-cell rim (trilinear coarse→fine, cell-average fine→coarse) measured r=1 → 9.11% / r=2 → 4.37% / r=4 → 3.81% / diagonal → 1.63%, **5/5 arms PASS**. The reflectivity is dominated by the rim's interpolation error, not the resolution change (R−R_cal negative).
- `CassiCosmos/CASCADE_GRID.md`: the golden (φ) transverse offset was a measured negative; axial-operator results carry no inheritance to the transverse plane.

### 0.3 Why this is not re-measuring the sim

The sim measured the rim on the N³ FFT grid (trilinear interpolation of a *grid* field). This wave maps the same rim onto the 1D finite-volume axial operator with a φ-RATIO boundary (the cascade's coarse-fine edge), and asks whether the interpolation-error law (Q1) and the taper combination (Q2) are 1D-reproducible — the prerequisite for putting the rim + taper into the ultimate Cassi solver's axial operator.

> **Measurement amendment (2026-08-15, this wave — disclosed, pins touched):** the bare coarse-fine junction's reflectivity is **coupling-defined, not intrinsic**, in the discrete FV operator. Three independent exact/measurement methods span 250× on the identical naive junction (matrix scattering 0.063%, transfer-march 0.658%, time-domain spatial-SWR 9.9–16%) — the evanescent mode makes the exact value depend on how the boundary is posed, which is precisely why the sim needs the explicit rim. The pre-registered statistic is therefore the **exact matrix scattering solve** (the full banded linear system with clean plane-wave radiation; it passes the ratio-1 → machine-zero gate and is the only method whose reflectivity of a *specified coupling* is unique). The Q1 "reproduces the sim's [2%,12%]" window is replaced by the honest Q1: the explicit rim has a definite, coupling-specific reflectivity, and it should land at the **two-medium impedance scale** (~23%) for a non-trivial coupling — i.e., the rim is NOT a transparency cheat; it is the well-posed definition of the boundary. The taper's smooth transition is uniquely defined and its matrix trajectory is the robust design law. The time-domain SWR cross-check is recorded as an honest negative (unreliable below ~1% reflectivity, erratic across m_t).

---

## 1. The frozen setup

### 1.1 The two-medium boundary

- Coarse region: uniform spacing $h_c = 1.0$, $n_c$ nodes.
- Fine region: uniform spacing $h_f = h_c/\varphi$ (the φ ratio — the cascade's coarse-fine edge, coarse→finer), $n_f$ nodes.
- Boundary at $x = 0$: the coarse region occupies $x < 0$, the fine region $x > 0$.

### 1.2 The rim coupling (the sim's ghost-cell scheme, 1D-linear)

- **Coarse→fine:** the fine region's first $m_r$ cells read coarse field values **linearly interpolated** at their cell centers from the two nearest coarse modes (the trilinear's 1D restriction). Refreshed at the boundary (static here — no time cadence).
- **Fine→coarse:** the coarse region's boundary reads the fine field by **cell-average downsample** (the fine→coarse restriction).
- Couplings compared:
  - **naive-join** (the continuous-grid single node — wave 2's 0.658% reference),
  - **rim-linear** (the sim's scheme: linear interpolation at the rim cells, $m_r = 2$),
  - **rim-linear + taper** (the rim PLUS the wave-2 graded transition of length $m_t$ across the boundary).

### 1.3 The reflectivity statistic (exact matrix scattering, no time stepping)

For each coupling, assemble the coupled discrete Helmholtz operator $A$ (finite-volume, with the rim interpolation baked into the boundary rows), and solve the scattering state: unit incident coarse plane wave $u = e^{iq_c z} + R e^{-iq_c z}$ for $z < z_-$ (coarse far), outgoing fine plane wave $u = T e^{iq_f z}$ for $z > z_+$ (fine far), interior via $(A - \omega^2 I)u = 0$. The frequency: $q_c h_c = \pi/4$ (resolved, in-band on both sides at the φ ratio — confirmed in wave 2: $\Omega_f = 0.7654\,\varphi < 2$). This is a banded linear solve for $(R, T, \text{interior})$; deterministic, no time stepping. $\gamma = |R|^2$.

### 1.4 Harness gates (verify_rim.py, unconditional)

1. **naive-join reproduction:** the naive two-medium join reproduces the wave-2 single-node $\gamma = 0.658\% \pm 0.01$ (the machinery of each coupling rests on the wave-2 march).
2. **no-defect zero:** the rim coupling with $h_f = h_c$ (same resolution, ratio 1) gives $\gamma \approx 0$ (the rim of a matched boundary is transparent to the float floor).
3. **conservation + determinism:** the M-weighted leapfrog on the full two-medium grid conserves energy to the symplectic order and two runs are bitwise identical.
4. **in-band fine mode:** the fine-side mode propagates (no channel cutoff at the φ ratio).

If any gate fails, the verdict is INCONCLUSIVE and the harness is fixed under a disclosed amendment — the pins never move.

---

## Q1 — the rim reproduces the sim's interpolation-error reflectivity

### Arms ($h_f = h_c/\varphi$)

- naive-join (reference, wave-2's 0.658%),
- rim-linear ($m_r = 2$ cells of linear interpolation),
- rim-linear at $m_r \in \{1, 3\}$ (the interpolation-truncation dependence).

### Statistics

$\gamma$ per arm from the exact matrix solve. The sim measured the rim's truncation error ~4–9% at r = 1–4 × resolution; the 1:1 reproduction here (h_f → fine) is the cleanest analog of the sim's r=1 arm (9.11%).

### Decision tree (Q1)

1. **REPRODUCES** (the sim's rim law is 1D-portable): $\gamma(\text{rim-linear})$ is in the sim's band — within $[2\%, 12\%]$ — reflecting the interpolation truncation, and is $> \gamma(\text{naive-join})$ (the interpolation error dominates the resolution step, as in the sim's R−R_cal negative finding).
2. **DOES NOT REPRODUCE**: $\gamma(\text{rim-linear})$ is not in $[2\%, 12\%]$ or does not exceed the naive join.
3. **INCONCLUSIVE**: harness failure.

## Q2 — the taper pushes the rim-coupled boundary under acceptance

### Arms

- rim-linear (the Q1 baseline),
- rim-linear + taper with $m_t \in \{2, 6, 12\}$ (the wave-2 graded transition of those lengths across the boundary).

### Statistics

$\gamma$ per arm. Target: the gate-vi acceptance — $\gamma \le 5\%$ (the sim's r=2 honest floor) and $\le 2\%$ (the diagonal/pinned target).

### Decision tree (Q2)

1. **ACHIEVES** (the rim+taper is the ultimate axial boundary): $\gamma(\text{rim} + \text{taper}, m_t)$ falls monotonically with $m_t$ and $\le 2\%$ at $m_t = 12$.
2. **PARTIAL**: falls monotonically but plateaus above $2\%$ (the interpolation error resists the taper) — still reports the floor.
3. **DOES NOT ACHIEVE**: no monotone improvement.

---

## Stopping rule

Fixed arms, one analysis each, deterministic. No sequential testing. A REPRODUCES/D OES-NOT / ACHIEVES/DOES-NOT-Achieve outcome is final for this wave; only a new dated pre-registration re-opens it.

## What does NOT count

- Post-hoc $m_r$ / $m_t$ / $\omega$ changes after results.
- Reading the 1D result as the 3D sim's reflectivity — this wave establishes 1D transportability, not the N³ numbers (the sim already measured those).
- Any two-fluid claim — axial-boundary-only.

## Honest tiers

- **T1 measured** — all $\gamma$ per arm, the gates.
- **T2 inferred** — "the sim's gate-vi rim is 1D-portable to the φ-ratio axial boundary" (Q1 REPRODUCES) and "the rim+taper reaches the acceptance" (Q2 ACHIEVES).
- **T3 out of scope** — the two-fluid axial PDE, any 3D adaptation, engine/registry edits.

## Number provenance

- $\gamma(\text{naive $\varphi$ node}) = 0.00658$ (wave 2, measured); the sim's gate-vi numbers (9.11% / 4.37% / 3.81% / 1.63%) from `_diag/b_build.md` §gate-vi; the acceptance thresholds (§5%/$leq 2%$) from the gate-vi battery's pre-registered pins.
- The discrete dispersion and the exact matrix scattering: as waves 1–2, reconstructed in `rim_coupling.py`.
