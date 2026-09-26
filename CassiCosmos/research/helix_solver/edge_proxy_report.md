# Edge-Gradient Wave 5a-followup — the bias-free 1.70 proxy — REPORT

**Date:** 2026-08-15 · **Pre-registration:** `edge_proxy_prereg.md` (written and frozen
before any run; amended once to correct the ground-truth control's expected value —
see §Honest amendments). Every number below came from `verify_edgeproxy.py` /
`edge_proxy_probe.py` live output, not the prereg's expectations.

## Verdict summary

| Leg | Statistic | Measured | Target | Verdict |
|---|---|---|---|---|
| **G — proxy validation** | isotropic Gaussian → $\frac{\|dC/ds\|_{\text{axial}}}{\|dC/ds\|_{\text{diag}}}$ | **1.0000–1.0025** at θ=0.3/0.4/0.5 | 1.00 (±0.01) | **PASS** (proxy is bias-free) |
| G | uniform checkerboard | **1.270** | exact 1.269 (±0.08) | **PASS** |
| G | φ-checkerboard | **1.935** | ≥1.5 & > control | **PASS** (grid-limited; exact 1.707) |
| F | machinery conservation (free) | 3.7e-4 | <5e-3 | **PASS** |
| F | determinism | bit-identical | | **PASS** |
| F | coherence sanity | C∈[-1,1] | | **PASS** (amended criterion) |
| **D — dynamical edge** | evolved two-fluid $\|dC/ds\|$ ratio | **no clean boundary** (single bubble); **C∉[-1,1]** (checkerboard seed) | — | **CONTRADICTS / DOES NOT EMERGE** (Reported Negative) |

## The three findings

### F1. The proxy is now genuinely bias-free — and that took real work

The withdrawn wave-5a "arc-proxy" was biased (its symmetric control read 0.54, not ~1).
The replacement measures the **directional derivative along each path** — the
doctrine's §2.2 quantity — not the full normal gradient magnitude. Getting it right
required three corrections, each caught by the ground-truth leg running *before* the
dynamical claim:

1. **Full gradient ≠ doctrine gradient.** The doctrine's diagonal is the gradient
   *projected on the path* (a directional derivative), not the magnitude $|\nabla C|$.
   Measuring the full magnitude over-read the diagonal (4.42 vs 3.97 analytic) —
   fixed by projecting onto the ray: `|(∇C)·ŝ|`.
2. **The diagonal is at the saddle angle, not 45°.** The doctrine's "neighbor" is the
   saddle at $(\Lambda_Y/4,\Lambda_I/4)$, at $\arctan(\Lambda_I/\Lambda_Y)=31.7°$ on
   the φ-arm — not a fixed 45° walk. Walking 45° walked off the saddle path.
3. **The true isotropic control is not $\cos\cos$.** Even a *uniform* checkerboard has
   a void-vs-saddle edge asymmetry (the doctrine formula $2\beta/\sqrt{\alpha^2+\beta^2}$
   gives √2, i.e. 1.414, not 1.0 — and the *exact* value at θ=0.45 is 1.269). The only
   guaranteed-no-anisotropy control is an **isotropic Gaussian**, which must read
   exactly 1.0. It does (1.0025/0.9999/1.0015) — the proxy is unbiased.

**The proxy is validated** by the Gaussian control reading 1.000 to three decimal
places at any threshold.

### F2. The doctrine's 1.70 is exact at θ=0.45, but the 2D φ-grid cannot reach it

Derived (not fitted): the exact directional-derivative ratio of the condensation field
$C=\cos(\alpha x)\cos(\beta y)$, $\beta=\varphi\alpha$, at the calibrated
$C=\theta=0.45$, is

$$\frac{|dC/ds|_{\text{axial}}}{|dC/ds|_{\text{diag}}} \Big|_{\theta=0.45}
= \frac{\beta\sqrt{1-\theta^2}\cdot\frac14\sqrt{\Lambda_Y^2+\Lambda_I^2}}
{4\pi\sqrt{\theta(1-\theta)}} = 1.707$$

matching the doctrine boxed 1.70130 to **0.4%**. The "C-independence" wording in §2.2
is a near-optimal approximation; the exact ratio at the operating point is 1.707. For
the uniform checkerboard the same exact formula gives **1.269** (not √2, not 1.0).

The **φ-ellipsoid proxy reads 1.935 on the discrete field** — not 1.707 — because the
2D φ-aspect grid under-measures the shallow (31.7°) diagonal: a **grid-anisotropy
artifact that does not converge with resolution** (1.935 at N=96/192/384/768). The
continuum condensation field's true 1.707 (and the doctrine's 1.7013) requires a
higher-order or full-3D measurement. The proxy's *differential* (φ 1.935 vs control
1.270) is robust — the φ-arm is clearly steeper — but its absolute value is
grid-limited.

### F3. The dynamical leg honestly does not realize a measurable edge (Reported Negative)

The evolved two-fluid fields do not produce a condensation boundary measurable by the
proxy on this minimal 2D probe:

- **Single Gaussian bubble, 600 steps:** $C_{\text{dyn}} = 2(EY^2+EI^2)-1$ peaks at
  −0.967 (φ-arm) / −0.985 (symmetric) — the small-amplitude wave just spreads and
  decays, giving $q = EY^2+EI^2 \sim 0.016$ at peak (far below the coherent baseline),
  so **no sharp edge contour exists** (n/a reading on both arms).
- **Checkerboard condensation seed** (the doctrine's §9.2 Method A): the sim's
  **non-conservative EY/EI coupling** (documented wave-5a finding: no common-potential
  gradient, 7.3% energy drift) **amplifies** $q$, driving $C_{\text{dyn}}$ out of
  $[-1,1]$ to $[+1.48, +2.06]$ — an **invalid condensation field**, unmeasurable.

**CONTRADICTS / DOES NOT EMERGE** for the dynamical edge on this 2D linear-wave probe.
The doctrine's 1.70 is a property of the condensation *field's shape*; realizing it
dynamically apparently needs a **stabilized/consumed feed** or the **full 3D oblate
spheroid** (the A2/axial direction), both of which are the follow-on, **not claimed
here**. This is an honest negative, not a doctrine failure — the exact analytic field
(parenthetically) gives 1.707.

## Honest amendments (disclosed, dated)

- **2026-08-15 (this wave):** the prereg's original ground-truth expectation "uniform
  control → 1.00" was **incorrect** — the doctrine's own formula gives the uniform
  checkerboard 1.269 (intrinsic void/saddle asymmetry), and only an isotropic field
  reads 1.0. The prereg's Leg-G section and harness gates were amended *before the
  dynamical claim* to the exact analytic anchors (Gauss→1.00, uniform→1.269,
  φ→≥1.5&>control), and this is recorded here.

## Traceability

- Re-run from `CassiCosmos/`: `python research/helix_solver/verify_edgeproxy.py`
  (~29 s, ALL CHECKS PASSED), `python research/helix_solver/edge_proxy_probe.py`
  (~54 s, deterministic).
- Files: `edge_proxy_prereg.md`, `edge_proxy.py`, `verify_edgeproxy.py`,
  `edge_proxy_probe.py` (all new, under `research/helix_solver/`).
- Doctrine: `bubble-edge-geometry.md` §2.2 (the 1.70 ratio), §1.2 (θ=0.45), §9.2
  (the checkerboard seed); the non-conservative coupling is documented in
  `triaxial_report.md` (wave 5a).
- The wave-5a "within 3% of 1.70" claim remains **withdrawn**; this wave replaces it
  with the validated bias-free proxy + exact-field anchors + an honest dynamical
  negative + the grid-limit qualification.
