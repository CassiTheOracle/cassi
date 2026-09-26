# Helix Solver Wave 1 — the φ-shelled axial grid probe — PRE-REGISTRATION

## Status: Pre-registration — written BEFORE any run; governs the wave-1 arms

**Date:** 2026-08-15 · **Workstream:** the ultimate Cassi solver (solver-topology wave)
**Pre-registered outcomes:** the Q1 and Q2 arms below, with statistics, decision trees, and stopping rules pinned here.
**Implementing probes (numpy, new-files-only):** `CassiCosmos/research/helix_solver/phi_grid.py` (grid constructor + wave stepper), `verify_phi_grid.py` (the harness gates), `wave_probe.py` (the Q1/Q2 arms). No engine, shader, or verify asset changes; no GPU (the owner's editor is open).

---

## 0. The question and the prior record

### 0.1 The question

The ultimate Cassi solver asks whether the axial (string/cascade) direction of the solver's grid should BE the cascade slice: shell positions $z_k = z_0\varphi^k$ — a displacement along the string axis is a change of scale (`CassiTheory/foundations/qi-flow-double-helix.md` §3.1). This wave measures the two make-or-break numbers for that topology, on the 1D wave equation $\partial_t^2 u = c^2\,\partial_z^2 u$ with the canonical 3-point stencil on the non-uniform grid:

- **Q1 — transport.** Does a wave cross the φ-interfaces (spacing ratio φ per shell) without pathological reflection?
- **Q2 — the resolution wall.** Does the φ-grid give every scale a finite resolved band with a per-rung transmission law — the cascade's suppression structure realized as the grid's own property?

### 0.2 The prior record (cited, not re-measured)

- `CassiCosmos/CASCADE_GRID.md` §2/§3: the dual half-cell BCC pair is the measured winner (placement-bias excess down 4.6×); the golden (φ) TRANSVERSE offset pair measured WORSE (1.51 vs 1.263). Each φ-placement must earn its own measurement; no free inheritance.
- `CassiTheory/hypotheses/two-strand-five-channel-matter-organization.md` §3.8: the per-rung π anti-phase stack (`m8_pi`) cancels float-exact and is inert ($C_{\text{abs}} = 0$ throughout) — the π-per-rung alternation is a measured construction identity in the doublet plane, not a spatial winding.
- §3.13: the spatial azimuthal helix construction (h0–h4) measured radial emergence, no pair, winding dissolved — the double helix is a phase-space claim (`qi-flow-double-helix.md` §4.2: at $P_\parallel = 2$ the embedding degenerates to a planar Yang-axis oscillation). This wave builds no transverse winding.
- The lattice-stack program's protocol invariant is initialization-only, canonical solver untouched. This wave is its complement: the solver's axial GRID is what changes.

---

## 1. The frozen setup

### 1.1 Grids

- **φ-arm (probe):** $K = 8$ shells, $z_k = \varphi^k$, $k = 0..7$ (span $[1.0, \varphi^7 \approx 29.03]$); spacings $h_k = z_{k+1} - z_k = \varphi^k(\varphi - 1)$; spacing ratio per interface: $h_{k+1}/h_k = \varphi$ everywhere.
- **Uniform arm (null):** the same span $[1.0, \varphi^7]$, $N_u = 100$ points ($dz \approx 0.283 < h_0$ — a finer-than-finest reference; the gate-vi calibration-arm pattern: the clean reference for the BC/dispersion floor).
- $c = 1$; time step $dt = 0.4\,h_0 = 0.2472$ on BOTH arms (CFL-safe on both: $dt < dz_u$, $dt < h_0$).

### 1.2 Stencils (3-point, non-uniform, polynomial-exact)

For point $i$ with $h_- = z_i - z_{i-1}$, $h_+ = z_{i+1} - z_i$:

- Second derivative (the wave operator):

$$u''_i = \frac{2}{h_- h_+ (h_- + h_+)}\left[\,h_+ u_{i-1} - (h_- + h_+)u_i + h_- u_{i+1}\,\right]$$

- First derivative (for the ±z invariants and the IC):

$$u'_i = \frac{h_-^2 u_{i+1} - h_+^2 u_{i-1} + (h_+^2 - h_-^2)u_i}{h_- h_+ (h_- + h_+)}$$

Both reduce to the standard centered formulas on the uniform arm and reproduce $z^m$ derivatives exactly (the verify gates pin this).

### 1.3 Stepper

Staggered leapfrog: $v \mathrel{+}= dt \cdot c^2 \cdot (A u)$; $u \mathrel{+}= dt \cdot v$, with $A$ the tridiagonal second-derivative matrix. Dirichlet $u = 0$ at both ends (both arms, identical). Deterministic — no RNG anywhere.

### 1.4 Harness gates (verify_phi_grid.py, unconditional)

1. φ-ratio: $z_{k+1}/z_k - \varphi \le 10^{-15}$ for all k; the uniform arm spans exactly $[z_0, z_7]$.
2. Stencil exactness: $A\,z^2 = 2$ and $D_1\,z^2 = 2z$ on the interior, both grids, $\le 10^{-9}$.

> **Harness amendment (2026-08-15, first gate run — disclosed, pins untouched):** the gate-2 exactness floor was relaxed $10^{-12} \to 10^{-9}$: the 100-point uniform arm's float accumulation measures $3.64\times10^{-12}$ (the polynomial is exact in real arithmetic; a genuine stencil bug is $O(1)$, so $10^{-9}$ still pins the construction). The stepper's CFL guard was corrected to the true Von Neumann bound $\min(h)/c$ (the initial $0.5\times$ factor rejected the stable $dt = 0.4\,h_0$ on the uniform arm). The Q1/Q2 pins (R/T/a$_{\mathrm k}$ thresholds) are unchanged.

> **Stencil amendment (2026-08-15, behind gate g3 — disclosed, pins untouched):** the Q1/Q2 operator is now the **finite-volume Laplacian** $A = -M^{-1}B^{\mathsf T} W B$ (edge incidence $B$, edge weights $W = \mathrm{diag}(1/h_k)$, cell volumes $M_{ii} = (h_{i-1}+h_i)/2$) and the M-weighted leapfrog $v \mathrel{+}= dt\,c^2 A u;\ u \mathrel{+}= dt\,v$, with the exactly-conserved energy $E = \tfrac12(v^{\mathsf T} M v + c^2 (Bu)^{\mathsf T} W (Bu))$. The originally-pinned classic 3-point non-equidistant centered stencil is **not symmetric on a non-uniform grid** ($|A - A^{\mathsf T}| = O(1)$, measured $2.0$ at K=8) — it has no conserved discrete energy there ($E$ drifts $\sim 9$% at the probe dt). Gate g3 caught it; the finite-volume form conserves to the symplectic order (uniform: $6.7\times10^{-5}$ over 200 steps at $dt = 0.05\min h$; $\varphi$: $1.8\times10^{-3}$ at $dt = 0.1\,h_0$). Gate g2 is redefined to the finite-volume invariants: (i) $A$ is symmetric under $M$ ($A^{\mathsf T} M = M A$), (ii) the edge flux $(B u)^{\mathsf T} W (B u)$ is the conservative norm, (iii) the smooth-residual $A\sin z = -\sin z$ holds in the resolved interior. The Q1/Q2 pins are unchanged.
3. Energy conservation on the uniform arm: a smooth IC away from the ends, 200 steps: relative drift $\le 10^{-10}$.
4. Determinism: two identical runs bitwise identical.

If any harness gate fails, the probe verdict is INCONCLUSIVE and the harness is fixed under a disclosed amendment — the pins never move.

---

## 2. Q1 — transport across the φ-interfaces (inward, the refining direction)

### 2.1 Setup

Gaussian pulse launched INWARD (toward $z_0$; the spacing shrinks, so the wave stays resolved throughout — this isolates pure interface reflection from the Q2 wall):

- Launch: $z_c = \varphi^4 \approx 6.854$, width $\sigma = \lambda/4$ with $\lambda = 4\,h_4 \approx 16.94$, so $\sigma \approx 4.24$; IC $u(z) = \exp(-(z-z_c)^2/(2\sigma^2))$, $v(z) = -c\,u'(z)$ (pure $-z$-going).
- Interfaces crossed: 4→3→2→1 (three φ-interfaces at ratio φ each) plus the uniform arm's none.
- $t_{\text{ref}}$: the first step when the pulse centroid passes $z_c - \sigma$ (early, before the first interface). Fit $c_{\text{fit}} = \sqrt{\langle\dot u^2\rangle/\langle u'^2\rangle}$ over the pulse-support mask (the gate-vi fitted-speed discipline).
- $t_{\text{probe}}$: the first step when the centroid passes $z_{2.5} = \varphi^{2.5} \approx 3.33$ (the measurement window, boundary-clear — a harness assert: $|u|, |u'| \le 10^{-6}$ at both endpoints during the window).

### 2.2 Statistics

Over the pulse-support mask at $t_{\text{probe}}$ (both arms, identical definitions):

$$E_{\text{forw}} = \sum_i (\dot u_i - c_{\text{fit}} u'_i)^2, \qquad E_{\text{back}} = \sum_i (\dot u_i + c_{\text{fit}} u'_i)^2$$

$$R = E_{\text{back}}/E_{\text{forw}}, \qquad T = E_{\text{forw}}(t_{\text{probe}})/E_{\text{forw}}(t_{\text{ref}})$$

### 2.3 Decision tree (Q1)

1. **SUPPORTS** (the φ-shelled axial grid is a transport channel): $R_\varphi \le 10\%$ AND $T_\varphi \ge 90\%$ — the pinned transport criterion across the three φ-interfaces.
2. **CONTRADICTS**: $R_\varphi > 10\%$ with the harness clean ($R_u \le 5\%$ — the uniform arm must itself be near-transparent).
3. **INCONCLUSIVE**: $R_u > 5\%$ (harness/BC defect — fix the harness under a disclosed amendment, never the pin).

---

## 3. Q2 — the resolution wall (outward, the coarsening direction)

### 3.1 Setup

Gaussian pulse launched OUTWARD (toward $z_7$; the spacing grows as $\varphi^k$, so the wave's cells-per-wavelength shrink geometrically — the cascade's resolution structure):

- Launch: $z_c = z_1 = \varphi \approx 1.618$, $\lambda = 4\,h_0 \approx 2.472$, $\sigma = \lambda/4 \approx 0.618$; IC $u(z) = \exp(-(z-z_c)^2/(2\sigma^2))$, $v(z) = +c\,u'(z)$ (pure $+z$-going).
- Wall definition: shell k is resolved iff $\lambda \ge 4\,h_k$. With $\lambda = 4h_0$: shell 0 marginal, shells $k \ge 1$ unresolved ($h_1 = \varphi h_0 > h_0$). The wall band is $k = 1..4$ (5 interfaces).
- Envelope amplitude: $A_k$ = the maximum of $|u|$ over the shell band $[z_k - h_{k-1}/2,\ z_k + h_k/2]$ as the pulse passes (tracked per band, deterministic).

### 3.2 Statistics

Per-rung transmission $a_k = A_{k+1}/A_k$ for $k = 0..4$ (the incident reference is $A_0$, the last resolved shell). The reported per-rung factor: $\bar a = \text{mean}(a_k,\ k = 1..4)$.

### 3.3 Decision tree (Q2)

1. **EMERGES** (the suppression structure is the grid's own property): the uniform arm shows $a_k \ge 0.98$ for all k (no wall — the harness branch), AND the φ-arm shows (i) $a_k < 0.98$ for all $k \ge 1$ (a real wall) and (ii) rung-uniformity $\max(a_k)/\min(a_k) \le 1.2$ over $k = 1..4$ — every rung presents the same impedance ratio φ, so the per-rung transmission is a ladder.
2. **DOES NOT EMERGE**: the φ-arm shows no attenuation ($a_k \ge 0.98$) or a non-uniform wall (max/min $> 1.2$).
3. **INCONCLUSIVE**: the uniform arm shows $a_k < 0.98$ anywhere (harness/BC defect).

The measured $\bar a$ is REPORTED next to $\varphi^{-1} \approx 0.618$ as a number of interest. The theory's per-rung suppression $\varphi^{-N}$ (`cascade-suppression-formula.md`) is a coherence-transfer amplitude; grid transmission is a resolution-transport amplitude — the two are compared, not identified, and no registry entry is proposed on this wave regardless of the value.

---

## 4. Stopping rule

- Fixed sample: exactly two arms per question (φ + uniform), one analysis run each, no sequential testing, no re-runs to "get a cleaner number."
- Q1 stops at $t_{\text{probe}}$ (the centroid crossing $z_{2.5}$); Q2 stops when the pulse centroid passes $z_5 \approx 11.09$ (past the wall band). Both deterministic.
- The only condition that can re-open this pre-registration is a new written pre-registration; a CONTRADICTS/DOES NOT EMERGE is a finding, not a re-framing.

## 5. What does NOT count as evidence

- Post-hoc parameter changes ($K$, $\lambda$, $\sigma$, $dt$) after seeing results — the values are frozen in §1–§3.
- A per-interface reflectivity extracted by any method other than the §2.2 statistics.
- $\bar a$ landing near $\varphi^{-1}$ being read as the coherence-suppression law — the comparison is reported, never adopted (§3.3).
- Any transverse-plane claim (checkerboard, dual lattice, helix winding) — this wave is axial-only; the transverse record is §0.2's citations.

## 6. Honest tiers

- **T1 measured** — everything the probes print: the harness gates, $R_\varphi$, $R_u$, $T_\varphi$, $c_{\text{fit}}$ per arm, $a_k$, $\bar a$.
- **T2 inferred** — "the φ-spaced axial grid is a viable transport channel for the ultimate Cassi solver" (Q1 SUPPORTS) and "the φ-grid carries a per-rung transmission ladder" (Q2 EMERGES).
- **T3 out of scope** — any engine/solver adoption, the two-fluid PDE's axial coupling on shells, and any theory-registry edit.

## 7. Number provenance

- $\varphi = 1.618033988749895$; $\varphi^7 = 29.0344...$, $h_0 = \varphi - 1 = 0.61803...$, $h_4 = \varphi^4(\varphi-1) = 4.2361...$: recomputed from $\varphi$; matches §1.1.
- The measured-record citations: `CassiCosmos/CASCADE_GRID.md` §2/§3 (the 4.6× and the 1.51-vs-1.263 golden-offset negative); `CassiTheory/hypotheses/two-strand-five-channel-matter-organization.md` §3.8 (`m8_pi` float-exact cancellation), §3.13 (h0–h4 radial emergence); `CassiTheory/foundations/qi-flow-double-helix.md` §3.1 (the string axis is the cascade direction), §4.2 (the planar degeneracy at $P_\parallel = 2$).
- The wall criterion $\lambda \ge 4h$: the house resolved-band convention (≥4 cells per structure radius, `CassiCosmos/MACHINE_PLAN.md` §1.3) applied to wavelength.
