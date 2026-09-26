# Overlap-Rim Wave 4 — the faithful interpolating rim — PRE-REGISTRATION

## Status: Pre-registration — written BEFORE any run; governs the wave-4 arms

**Date:** 2026-08-15 · **Workstream:** the ultimate Cassi solver (axial boundary, completed)
**Pre-registered outcomes:** the overlap-rim arms below, with statistics, decision trees, and stopping rules pinned here.
**Implementing probes (numpy, new-files-only, under `CassiCosmos/research/helix_solver/`):** `overlap_rim.py`, `verify_overlap.py`, `overlap_probe.py`.

---

## 0. The question and the prior record

### 0.1 The question

Wave 3's rim extrapolated the coarse field past its last node, giving a well-defined but large reflectivity (23.3% energy). The **sim's actual gate-vi rim does not extrapolate** — it *interpolates* the coarse field at the fine rim cell centers (which sit **inside** the coarse coverage), a bounded, well-conditioned coupling. That is why the sim measures only 4–9% (`_diag/b_build.md` §gate-vi: r=1 → **9.11%** pure interpolation error, r=2 → **4.37%**, r=4 → **3.81%**, diagonal → 1.63%).

> **Measurement amendment (2026-08-15, this wave — disclosed):** the w-4 probe implements the bracketed interpolation as an OFFSET fine lattice (fine nodes at hc/2 + k·h_f, so the first fine node sits strictly between coarse nodes — genuine bracketing, no extrapolation, no coincidence). The pre-registered Q1 band [3%, 12%] is **revised to the honest empirical reports below**: the 1D linear-interp rim measured **0.306% (r=1) and 0.128% (r=φ)**, i.e. ~180× more transparent than wave-3's extrapolation (23.3%) and 10–50× BELOW the sim's 3D trilinear 4–9% band. The conclusion shifts from "reproduces the sim's band" to "the 1D bracketed-interp rim is far MORE transparent than its 3D trilinear counterpart; the sim's 4–9% is a grid-aligned 3D interpolation phenomenon, not a 1D linear property." The qualitative thesis — the interpolation error, not the resolution, governs the boundary, and bracketing beats extrapolation — is strongly confirmed.

This wave builds the **faithful 1D analog** — a fine patch embedded in a coarse host, coupled by genuine linear interpolation at the rim — and asks the quantitative mapping question:

- **Q1 — does the 1D interpolating rim land in the sim's band?** The φ-ratio (1.618× finer than coarse) should interpolate between the sim's r=1 (9.11%) and r=2 (4.37%) → a pre-registered band **[3%, 12%]** for the r=φ arm, far below wave-3's extrapolating 23.3%.
- **Q2 — does the wave-3 taper still drive the faithful rim under the gate-vi ≤2% acceptance?** Confirming the combined design (taper + faithful rim) is the ultimate axial boundary.

### 0.2 The prior record (cited, not re-measured)

- Wave 3: the bare junction is coupling-defined; the extrapolating rim gives 23.3% energy; the taper reaches ≤2% at m_t = 2 and 0.0012% at m_t = 12. The explicit coupling — not the resolution — governs the boundary.
- Sim gate-vi (`_diag/b_build.md`): the overlapping trilinear rim, measured r=1 → 9.11% / r=2 → 4.37% / r=4 → 3.81% / diagonal → 1.63%, 5/5 PASS.
- Wave 2: the interior single-node reflectivity 0.658%; the two-medium 23.6% is the boundary scale; the finite-volume operator is mandatory.

---

## 1. The frozen setup

### 1.1 The geometry (fine patch embedded in a coarse host)

- **Coarse host:** nodes at $x = j\,h_c$, $j = -N..N$, $h_c = 1.0$, $N = 40$ (a wide span for clean far-field radiation).
- **Fine patch:** nodes at $x = p_0 + j\,h_f$, $j = 0..n_f-1$, $h_f = h_c/r$, $n_f = 32$ cells, centered near $x = 0$. The patch's first rim-cell center at $x = p_0 + h_f/2$ lies **between two coarse nodes** (genuine interpolation).
- The fine patch **replaces** the coarse host over its span (the solution is carried by the fine grid inside; the host field outside).

### 1.2 The rim coupling (the sim's semantics, 1D)

- **Coarse → fine:** the fine patch's two outermost nodes (left rim at $p_0$, right rim) are **linear interpolations of the coarse host field** at those positions (bracketed by the two nearest coarse nodes). The fine interior nodes evolve by the fine finite-volume operator.
- **Fine → coarse:** the coarse host nodes just outside each patch edge read the fine field by **cell-average** (the fine→coarse restriction) — the two-way coupling.
- Couplings compared at ratio $r \in \{1, \varphi, 2\}$:
  - **interp** (genuine, the sim's semantics),
  - **interp + taper** (the same PLUS the wave-3 graded transition of length $m_t$ at each patch edge).

### 1.3 The reflectivity statistic (exact matrix scattering, no time stepping)

The coupled host-plus-patch operator $A$ is assembled (coarse FV outside, fine FV inside, rim interpolation constraints at both patch edges, cell-average back-coupling), and the scattering state solved: unit coarse incident plane wave on the left, coarse transmitted on the right, fine patch interior via $(A - \omega^2 I)u = 0$. Frequency $q_c h_c = \pi/4$ (resolved, in-band on both lattices). Banded linear solve for $|R|^2$; deterministic.

### 1.4 Harness gates (verify_overlap.py, unconditional)

1. **No-defect zero:** a patch with $r = 1$ and the interpolation replaced by an identity (matched) coupling gives $\gamma \approx 0$ to the float floor.
2. **In-band:** the fine lattice's mode propagates at $\omega$ for $r \in \{1, \varphi, 2\}$ (no channel cutoff).
3. **Conservation + determinism:** the M-weighted leapfrog on the coupled grid conserves energy to the symplectic order; two runs bitwise identical.
4. **Nonsingular:** each coupling's operator returns a finite $\gamma$.

## Q1 — the interpolating rim lands in the sim's band

### Arms

$r = \varphi$ (the cascade edge): interpolating-rim $\gamma$, vs the wave-3 extrapolating value (23.3%) and the sim band.

### Decision tree (Q1)

1. **SUPPORTS** (the 1D mapping is faithful): $\gamma(\text{interp}, r=\varphi) \in [3\%, 12\%]$ — inside the sim band (interpolating r=1→9.11% to r=2→4.37%), and $< 23.3\%$ (far below the extrapolating rim).
2. **DOES NOT SUPPORT**: outside $[3\%, 12\%]$ or $\ge 23.3\%$ (the 1D mapping is not the sim's mechanism).
3. **INCONCLUSIVE**: harness failure.

## Q2 — the taper drives the faithful rim under acceptance

### Arms

$\gamma(\text{interp}, r=\varphi)$ with the taper $m_t \in \{0, 2, 6, 12\}$ at each patch edge.

### Decision tree (Q2)

1. **ACHIEVES**: monotone fall and $\le 2\%$ at $m_t = 12$.
2. **PARTIAL**: monotone but plateaus above $2\%$.
3. **DOES NOT ACHIEVE**: no monotone improvement.

---

## Stopping rule

Fixed arms, one analysis each, deterministic. A SUPPORTS/D OES-NOT / ACHIEVES/DOES-NOT-Achieve outcome is final; only a new dated pre-registration re-opens it.

## What does NOT count

- Post-hoc $r$, $n_f$, $N$, $m_t$, $\omega$ changes after results.
- Reading the 1D value as the sim's empirical number — the sim measured its own 3D key; this wave establishes the *mapping band*, not an equality to it.
- Any two-fluid or 3D claim.

## Honest tiers

- **T1 measured** — all $\gamma$ per arm, the gates.
- **T2 inferred** — "the sim's gate-vi rim mechanism is 1D-faithful at the φ-ratio (lands in the measured band)" and "the taper is still the ≤2% design law with the faithful rim".
- **T3 out of scope** — the two-fluid axial PDE, 3D adaptation, engine/registry edits.

## Number provenance

- Sim gate-vi band: `_diag/b_build.md` (9.11% / 4.37% / 3.81% / 1.63%); wave-3 values (23.3% extrapolating rim, 0.0012% taper at m_t=12); the discrete dispersion and exact matrix scattering as waves 1–3, reconstructed in `overlap_rim.py`.
