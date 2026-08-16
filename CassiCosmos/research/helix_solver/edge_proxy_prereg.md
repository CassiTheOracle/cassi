# Edge-Gradient Wave 5a-followup — the bias-free 1.70 proxy — PRE-REGISTRATION

## Status: Pre-registration — written BEFORE any run; governs the edge-proxy arms

**Date:** 2026-08-15 (follow-up to the triaxial wave 5a corrected report) ·
**Workstream:** the ultimate Cassi solver (transverse geometry) ·
**Pre-registered outcomes:** whether the doctrine's 1.70 edge-steepness anisotropy is
actually measurable from the (coherent/symmetric) two-fluid edge by a **bias-free**
gradient method, and whether the φ-ellipsoid arm carries it.
**Implementing probes (numpy, new-files-only, under `CassiCosmos/research/helix_solver/`):**
`edge_proxy.py`, `verify_edgeproxy.py`, `edge_proxy_probe.py`.

---

## 0. Why this wave exists (the corrected gap)

The triaxial wave-5a report "within 3% of 1.70" was **withdrawn**: the 
edge-steepness arc-proxy (walk a fixed-angle ray and measure the *arc-length to the
crossing*) is biased. Its own symmetric control read 0.540, not ≈1.0, because the
diagonal ray does not pass through the contour along its steepest-ascent (normal)
direction — the arc-length along a fixed ray is not $|\nabla C|^{-1}$. The doctrine's
1.70 must therefore be re-measured with a **bias-free gradient statistic** before it
can be claimed either way.

## 0.1 The doctrine target (exact, zero-parameter)

From `bubble-edge-geometry.md` §2.2, with $C(x,y) = \cos(\alpha x)\cos(\beta y)$,
$\beta = \varphi\alpha$:

Along the axial (Yin) direction $x=0$: $C = \cos(\beta y)$, so
$|\nabla C|_{\text{axial}} = \beta\sqrt{1-C^2}$.
Along the diagonal toward the neighbor (path to the saddle $(\Lambda_Y/4,\Lambda_I/4)$):
$C = \cos^2(\pi t/2)$, so $|\nabla C|_{\text{diag}} = \frac12\sqrt{(\alpha^2+\beta^2)(1-C^2)}$.

The ratio at the SAME level $C$ (the $\sqrt{1-C^2}$ factors cancel — **holds at any
threshold**):

$$\boxed{\;\frac{|\nabla C|_{\text{axial}}}{|\nabla C|_{\text{diag}}}
= \frac{2\beta}{\sqrt{\alpha^2+\beta^2}}
= \sqrt{\frac{4\varphi^2}{1+\varphi^2}} \approx 1.70130\;}$$

This is the zero-parameter prediction. It is a property of the **condensation field's
gradient**, not of the Laplacian — but the Laplacian shapes the *evolved* field whose
edge we measure, so the two arms (φ-ellipsoid vs symmetric) must differ.

## 0.2 The bias-free statistic (replacing the arc proxy)

For a chosen scalar field $f$ (a condensation/coherence field defined below):

1. Find the field center (peak). Let $f_{\text{peak}}$ be its value.
2. Walk two rays from the center — axial (Yin, $+y$) and diagonal ($+45^\circ$) — at a
   fine physical step, bilinearly interpolated, and locate the first crossing of the
   level $f = \theta$, with $\theta = \theta_{\text{cond}} \cdot f_{\text{peak}}$
   (the condensation threshold fraction, **the same on both rays**).
3. At each crossing point, evaluate the **full gradient magnitude**
   $$|\nabla f| = \sqrt{\left(\tfrac{\partial f}{\partial x}\right)^2
   + \left(\tfrac{\partial f}{\partial y}\right)^2}$$
   by central differences on the grid (both partials — this is what removes the
   ray-arc bias: the diagonal crossing's gradient is the *normal* steepness, not the
   along-ray component).
4. Report $r_{\text{edge}} = |\nabla f|_{\text{axial}} / |\nabla f|_{\text{diag}}$.

Because the doctrine's ratio is $C$-independent, any common threshold reproduces it
to discretization error — this makes the proxy robust to the exact $\theta$ used.

## 1. The two legs

### 1.1 Leg G (ground-truth / machinery validation — must PASS or the proxy is broken)

**Fields (analytic, exact doctrine):**
$$C(x,y) = \cos\left(\tfrac{2\pi x}{\Lambda_Y}\right)
\cos\left(\tfrac{2\pi y}{\Lambda_I}\right), \qquad \Lambda_I = \Lambda_Y/\varphi$$
sampled on the same $N\times N$ grid as the dynamical arms. The proxy reads the
**directional derivative along each path** (the doctrine's §2.2 quantity), the full
gradient projected on the ray. The exact analytic values at the study threshold
$\theta = 0.45$ are (derived, not fitted):

| Field | Exact directional-derivative ratio at $\theta=0.45$ |
|---|---|
| φ-checkerboard ($\Lambda_I=\Lambda_Y/\varphi$) | $\approx 1.707$ (the doctrine boxed value 1.70130 is the same number to 0.4% — the "C-independence" line in §2.2 is a near-optimal approximation; the exact ratio at the calibrated $\theta=0.45$ is 1.707) |
| uniform checkerboard ($\Lambda_I=\Lambda_Y$) | $\approx 1.269$ (NOT √2 — the checkerboard's void-ward / saddle-ward asymmetry is intrinsic; call this the checkerboard control) |
| **isotropic Gaussian** (no void/saddle asymmetry) | **exactly 1.000** at any threshold — this is the true no-anisotropy control |

**Leg G gates:**
1. **G-gauss:** the isotropic Gaussian measures exactly $1.000 \pm 0.01$ at
   $\theta \in \{0.3, 0.4, 0.5\}$ (proves the proxy is unbiased — no ray-arc or
   direction artifact).
2. **G-control:** the uniform checkerboard measures $1.269 \pm 0.08$ (the doctrine's
   checkerboard value; brackets the analytic 1.269).
3. **G-phi:** the φ-checkerboard measures $\ge 1.5$ and **clearly above the control**
   (brackets the analytic 1.707 and the doctrine 1.70130; the residual grid-anisotropy
   along the shallow diagonal is a documented limit, so ≥1.5 with separation is the
   acceptable bar).

If G-gauss or G-control fails, the proxy is still biased → fix, don't proceed. G-phi's
exact magnitude is grid-limited (the φ-aspect 2D grid under-measures the shallow
diagonal; a non-grid-limited full-3D or higher-order measurement is the follow-on).

### 1.2 Leg D (the dynamical claim)

Evolve the two-fluid wave (the triaxial machinery, see below) from a symmetric Gaussian
bubble on both arms (φ-ellipsoid aspect $(\varphi,1)$ vs symmetric $(1,1)$). At the
final state, form the condensation/coherence field from the two-fluid fields. The
measured field is
$$C_{\text{dyn}} = 2\,(EY^2 + EI^2) - 1$$
on each arm, and the bias-free $r_{\text{edge}}$ is measured on it with the **same
diagonal direction used for the ground truth**, so the grid's diagonal bias affects both
arms identically and cancels in the **differential**.

**Decision (Q-followup):**

| Verdict | Condition |
|---|---|
| **SUPPORTS 1.70** | φ-ellipsoid arm's $r_{\text{edge}}$ is **clearly above** the symmetric arm's (differential $\Delta = r_{\phi} - r_{\text{sym}} \ge 0.15$) and the symmetric arm's $r_{\text{sym}}$ is near the checkerboard-control's 1.27 |
| **CONTRADICTS** | φ-arm ≈ symmetric arm (no differential), or both ≈ 1.0 |
| **INCONCLUSIVE** | harness failure (control not ~1, ground-truth leg fails, non-conservation instability, no clean crossing) |

A **Reported Negative (CONTRADICTS / DOES-NOT-EMERGE)** is a deliverable, not a
re-frame. The 1.70 target remains the doctrine's regardless; this probe measures the
**differential** (the φ-arm vs symmetric-arm edge anisotropy), not the absolute 1.70
(which is grid-limited here and flagged as a higher-order follow-on).

## 2. Frozen setup

- **Domain:** the 2D Yang-Yin plane, $N = 96$ per axis, periodic.
- **Operators:** `anisotropic_laplacian(N, aspect)` from `triaxial_laplacian.py`
  (the sim's anisotropic 19-point FV stencil reduced to 2D). φ-ellipsoid arm:
  aspect $(\varphi, 1)$; symmetric control: $(1, 1)$.
- **Evolver:** `TwoFluid2D` (the two-fluid leapfrog, staggered start),
  $\omega_0^2 = 20$, $c = 1$, $\mathrm{d}t = 0.02$. The machinery conserves the free
  case to ~4e-4; the coupling is non-conservative as written (documented in the 5a
  report) — that is a known PDE property, not a harness error.
- **Seed:** a single radially-symmetric Gaussian bubble centered at $N/2$ (EY, EI
  co-located — no diagonal offset, per the 5a correction).
- **Steps:** 600 (the same as the 5a probe; deterministic).
- **Threshold fraction:** $\theta_{\text{cond}} = 0.45$ (the doctrine's calibrated
  value), applied to each arm's own peak. Sensitivity: re-report $r_{\text{edge}}$ at
  $\theta \in \{0.35, 0.45, 0.55\}$ — the ratio must be roughly flat (it is
  $C$-independent analytically); a strong $\theta$-dependence exposes a remaining
  proxy artifact.

## 3. Harness gates (verify_edgeproxy.py, unconditional, must all PASS)

1. **G-gauss:** the analytic isotropic Gaussian control → $r_{\text{edge}} =
   1.00 \pm 0.01$ at $\theta \in \{0.3, 0.4, 0.5\}$ (proves the proxy is unbiased).
2. **G-control:** the analytic uniform checkerboard → $1.27 \pm 0.08$ (the doctrine's
   checkerboard value, brackets the exact 1.269).
3. **G-phi:** the analytic φ-checkerboard → $\ge 1.5$ AND clearly above G-control
   (brackets the exact 1.707 and the doctrine 1.70130; the grid-anisotropy limit is
   documented).
4. **Machinery conservation:** free ($\omega_0^2=0$) two-fluid energy drift
   $< 5\times10^{-3}$ over 600 steps.
5. **Determinism:** two identical runs bitwise identical.
6. **Peak/coherence sanity:** the peak of $EY^2+EI^2 > 0$ and $C_{\text{dyn}} \in
   [-1, 1]$ everywhere (a valid Qi density).

## Stopping rule

Fixed: one seed, 600 steps, two arms, thresholds $\{0.35,0.45,0.55\}$, one analysis
per arm, deterministic. A CONTRADICTS is a finding. Only a new dated pre-registration
re-opens.

## What does NOT count

- Post-hoc thresholds, steps, seed, or grid changes.
- Reading the ground-truth leg's 1.70 (a fit-field measurement) as the dynamical
  verdict — only Leg D's $C_{\text{dyn}}$ measures the sim's edge.
- The sim's 3D/axial anisotropy (A2) — that is the full-3D follow-on, not this 2D
  transverse probe.
