# Smooth-Cascade Wave 2 — the axial design law — PRE-REGISTRATION

## Status: Pre-registration — written BEFORE any run; governs the wave-2 arms

**Date:** 2026-08-15 · **Workstream:** the ultimate Cassi solver (axial operator)
**Pre-registered outcomes:** the design-law arms below, with statistics, decision trees, and stopping rules pinned here.
**Implementing probes (numpy, new-files-only, under `CassiCosmos/research/helix_solver/`):** `smooth_cascade.py`, `verify_smooth.py`, `smooth_probe.py`.

---

## 0. The question and the prior record

### 0.1 The question

Wave 1 (`helix_solver_report.md`, commit `70e12ce`) pinned that a bare φ-ratio spacing interface reflects 23.61% of a resolved incident wave (the acoustic-impedance mismatch). This wave asks the quantitative design law: **how smooth must the cascade slice be — how many sub-cells per rung — for interface transport to reach the gate-vi ≤2% acceptance, while preserving the rung lattice $z_k = z_0\varphi^k$ exactly?**

$$ \gamma(r) = \left|\frac{r-1}{r+1}\right|,\qquad r = \frac{h_{k+1}}{h_k} $$

gives $\gamma(\varphi) = 23.61\%$, and $\gamma(r) \le 2\% \iff r \le 1.0408 \approx \varphi^{1/12}$ — i.e. ~12 cells per rung. The probe verifies this at the **operator level** (exact discrete scattering through a real taper grid, not just the formula) and tests the graded-index cancellation that makes an exponential taper reflect far less than $m$ uncorrelated steps.

### 0.2 The prior record (cited, not re-measured)

- Wave 1 (this directory): $\gamma(\varphi) = 23.61\%$; the centered stencil is non-symmetric on non-uniform grids ($|A-A^{\mathsf T}| = O(1)$) — the wave operator must be the finite-volume Laplacian $A = -M^{-1}B^{\mathsf T}WB$ with the M-weighted leapfrog and conserved energy $\tfrac12(v^{\mathsf T}Mv + c^2(Bu)^{\mathsf T}Wu)$.

> **Wave-1 Q1 correction (2026-08-15, this wave — disclosed):** wave-1's 23.61% was the **two-semi-infinite-medium** acoustic-impedance mismatch $\gamma = |(r-1)/(r+1)|$ — the correct reflectivity of a genuine coarse-fine *patch boundary*. The exact single-node scattering (this wave) shows the FV operator's **interior φ-ratio single node** reflects only **0.658%** at a resolved mode ($q_c h_c = \pi/4$) — a localized point-scatterer, reflecting $O(\Delta h^2)$ at long wavelength. So the raw φ-grid's *interior* is near-transparent (far better than wave-1 feared); the 23.61% picture applies only at a true two-medium boundary, where the gate-vi rim is the coupling. Both are recorded; the taper design law below is measured at the operator level.

- `CassiCosmos/CASCADE_GRID.md` §2/§3: the golden (φ) TRANSVERSE offset pair measured worse than half-cell (1.51 vs 1.263); the dual BCC pair is the winner. Each φ-placement earns its own measurement. **Caveat carried forward:** the transverse-plane φ-ratio was a measured negative; this wave measures the *axial* taper reflectivity, a different quantity — no inheritance.
- `CassiTheory/hypotheses/two-strand-five-channel-matter-organization.md` §3.8/§3.13: the π-anti-phase and helix records — cited, not touched (axial-only here).

---

## 1. The frozen setup

### 1.1 Bases and grids

- $\varphi = 1.618033988749895$; rung lattice $z_k = z_0\varphi^k$, $z_0 = 1.0$, $K = 8$.
- **Smooth-cascade grid:** between consecutive rungs $z_k$ and $z_{k+1}$ place $m$ sub-intervals with per-cell spacing ratio $r = \varphi^{1/m}$ (a geometric/exponential taper). The full grid is geometric throughout with per-cell ratio $r$. Rung endpoints are the size-$(K-1)m + 1$ grid's exact nodes at $z_k = \varphi^k$.
- **Scattering grid (for the reflectivity measurement):** a coarse uniform region (spacing $h_c$) → the $m$-cell exponential taper (spacing $h_c r^j$, $j=0..m$, ending at $h_f = h_c \varphi$) → a fine uniform region (spacing $h_f$). $h_c = 1.0$; the total ratio across the taper is $\varphi$.

### 1.2 The operator

The finite-volume Laplacian $A = -M^{-1}B^{\mathsf T}WB$ (edge $B$, weights $W = \mathrm{diag}(1/h_k)$, cell volumes $M_{ii} = (h_{i-1}+h_i)/2$), with the conserved energy $E = \tfrac12(v^{\mathsf T}Mv + c^2(Bu)^{\mathsf T}Wu)$. $c = 1$.

### 1.3 The reflectivity statistic (exact discrete scattering, no time stepping)

For the scattering grid, inject a unit plane-wave from the coarse end at frequency $\omega$ (long-wavelength, resolved: $\omega$ chosen so the coarse mode has $q_c h_c = \pi/4$ everywhere it is resolved). The two uniform regions each carry the discrete dispersion $\omega = c\,\frac{2}{h}\sin\frac{q h}{2}$. The scattering state is $u = e^{iq_c z} + R\,e^{-iq_c z}$ on the coarse region and $u = T\,e^{iq_f z}$ on the fine region, matched through the taper interior by the FV operator at every node. The reflectivity $\gamma = |R|^2$ is solved exactly by a banded linear system (the transfer/scattering problem of the discrete Helmholtz operator). Deterministic; no RNG, no time stepping.

### 1.4 Harness gates (verify_smooth.py, unconditional)

1. **Rung-lattice preservation:** the smooth-cascade grid's node at sub-index $k m$ equals $\varphi^k$ to $\le 10^{-13}$ (the taper subdivides, never moves, the rung lattice).
2. **Taper ratio:** the per-cell spacing ratio is $r = \varphi^{1/m}$ to $\le 10^{-12}$ throughout.
3. **Bare-interface reproduction:** the exact scattering through a single $\varphi$-step (no taper, $m=0$) reproduces $\gamma = 23.6\% \pm 0.1$ (the wave-1 number at the operator level).
4. **Conservation + determinism:** the M-weighted leapfrog conserves the finite-volume energy to the symplectic order on the smooth grid (uniform tier as wave 1, $\le 5\times10^{-2}$ over 200 steps at $dt = 0.1\min h$), and two runs are bitwise identical.

If any harness gate fails, the verdict is INCONCLUSIVE and the harness is fixed under a disclosed amendment — the pins never move.

---

## 2. Q1 — the design law: reflectivity vs taper length

### 2.1 Arms

For $m \in \{0, 1, 2, 3, 6, 12, 24\}$ (0 = bare φ-step), compute $\gamma(m) = $ the exact scattering reflectivity of the $m$-cell exponential taper across total ratio $\varphi$. Same $\omega$, same $h_c$, same operator.

### 2.2 Statistics

$\gamma(m)$ for each $m$, from the exact scattering solve. The graded-index prediction: for a smooth taper the step reflections cancel to leading order, so $\gamma(m)$ should fall far faster than $m$ copies of the per-cell $\gamma(r)$.

### 2.3 Decision tree (Q1)

1. **SUPPORTS** (the smooth-cascade design law): $\gamma(m)$ falls monotonically with $m$, AND $\gamma(12) \le 2\%$ (the gate-vi acceptance), AND the measured $\gamma(12)$ is within $2\times$ of the graded-index cancellation expectation (i.e., much better than $12$ independent $\gamma(\varphi^{1/12}) \approx 2\%$ steps would imply — the interference is the point).
2. **DOES NOT SUPPORT**: $\gamma(m)$ does not fall monotonically, or $\gamma(12) > 2\%$ (the graded taper does not reach acceptance).
3. **INCONCLUSIVE**: harness gate fails (fix the harness first, never the pin).

The measured $m^* = \min\{m : \gamma(m) \le 2\%\}$ is the REPORTED design law (the cells-per-rung for the axial grid).

---

## 3. Q2 — the cascade structure under subdivision (preservation gate)

### 3.1 Statistic

On the smooth-cascade grid (m = 12), verify the wave-1 Q2 self-resolving window persists: a mode resolved at rung 0 (q₀ = π/4) still shows the geometric per-rung group-velocity collapse $|\sin q/q|$ across rungs, now with $q$ growing by $\varphi^{1/12}$ per *sub-cell* and the full rung window resolving ~12 cells. Report the group-velocity factor at the 4th rung under subdivision vs the wave-1 unsmoothed number (0.055).

### 3.2 Decision tree (Q2)

1. **EMERGES**: the subdivided grid still shows the per-rung collapse (group factor $< 0.2$ at the 4th rung), so the self-resolving window is scale-invariant under subdivision.
2. **DOES NOT EMERGE**: subdivision destroys or weakens the window beyond the unsmoothed value.
3. **INCONCLUSIVE**: harness failure.

The point of Q2: the subdivision that fixes transport (Q1) must NOT kill the cascade's coherence structure (Q2) — both must hold for the smooth-cascade grid to be the right axial operator.

---

## 4. Stopping rule

- Fixed arms: the $m$-set above, one analysis each. No sequential testing, no re-runs to "get a cleaner number."
- The exact scattering solve is deterministic — a single pass.
- A CONTRADICTS/DOES NOT EMERGE is a finding, not a re-framing. Only a new, later-dated pre-registration can re-open this.

## 5. What does NOT count as evidence

- Post-hoc $m$, $\omega$, or operator changes after seeing results.
- The time-domain standing-wave measurement (the wave-1 lesson: finite/time-stepping probes on steep ratios are fragile); the exact scattering solve is the pre-registered statistic.
- $\gamma(m)$ being read as the sim's own interface reflectivity — the sim's coarse-fine coupling is the interpolated rim (`CASSI_GRID.md` gate-vi), which wave 3 measures; this wave establishes the graded-taper baseline.
- Any transverse-plane or two-fluid claim — axial-only here.

## 6. Honest tiers

- **T1 measured** — $\gamma(m)$ per arm, $m^*$, the harness gates, the Q2 group-velocity factors.
- **T2 inferred** — "the axial cascade slice needs ~12 smoothly-tapered cells per rung for ≤2% interface transport, and this subdivision preserves the cascade structure."
- **T3 out of scope** — the two-fluid axial operator on shells, 2D/3D coupling, any engine/registry edit.

## 7. Number provenance

- $\gamma(\varphi) = |(\varphi-1)/(\varphi+1)| = 0.61803/2.61803 = 0.23607$ (wave-1's 23.61%).
- $r_{2\%}$: $\gamma(r) \le 0.02 \iff r \le (1.02/0.98) = 1.04082$; $\varphi^{1/12} = 1.0407$; so $m^* \approx 12$.
- The discrete dispersion $\omega = c(2/h)\sin(qh/2)$, transfer/scattering of the tridiagonal FV Helmholtz — standard, reconstructed in `smooth_cascade.py`.
- Wave-1 citations as in §0.2.
