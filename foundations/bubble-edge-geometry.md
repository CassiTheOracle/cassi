# Bubble Edge Geometry: Physical Profile of the Condensation Boundary

## Status: Derived geometry; Derived conditional threshold relation; Asserted single-channel gate form—August 2026

## Abstract

The chord lattice (`visual-explainers/chord_lattice.py`) derives the geometric skeleton of the megacascade: a staggered checkerboard of bubble and void sites from the condensation field $C(x,y) = \cos(2\pi x/\Lambda_Y)\cos(2\pi y/\Lambda_I)$. But the bubble *edge* is more than a level set. This document derives the physical profile across the condensation boundary—how $r$, $q$, $\rho$, and $G_{\text{eff}}$ transition from bubble interior to void, what the 3D edge shape is, and what observable signatures the edge imprints.

All bubbles carry the same Wu Xing number $w = 5$ (uniquely derived in `foundations/wu-xing-derivation.md`). The lattice is homogeneous—every bubble is structurally identical. The "neighboring bubble" in the chord lattice is the same $w$, spatially separated by $\varphi$-scaled interference.

**Figure:** `visual-explainers/string_bubble_cascade.png`—6-panel 3D damped-wave two-fluid PDE with sharper c² trap (α=0.15): pentagon at pinch (m=5 24.6%) → **φ-ellipsoid bubble confirmed** (σ_x/σ_z=2.510 vs φ²=2.618, σ_x/σ_y=1.422 vs φ=1.618 at step 1100) → cascade r-field shown via E_Y/E_I ratio. The bubble forms transiently as a coherent φ-shaped structure at early times (`visual-explainers/string_bubble_cascade.py`).

---

## 1. The Condensation Field as a Physical Proxy

### 1.1 From Interference to Coherence

The chord lattice field is:

$$\boxed{C(x,y) = \cos\!\left(\frac{2\pi x}{\Lambda_Y}\right) \cos\!\left(\frac{2\pi y}{\Lambda_I}\right), \qquad \Lambda_Y = \varphi\,\Lambda_I}$$

This is the product of the two perpendicular wake systems—Yang wake along the extended axis, Yin wake along the contracted axis. The W1 experiment confirmed anti-phase coupling, so the $m+n$ even sublattice (where $C = +1$ at extrema) are the condensate sites; the $m+n$ odd sublattice (where $C = -1$) are the voids. The staggered placement is interferometric: the wake beat envelope of `foundations/wake-geometry.md` §2 puts bubble centers at $m\,\ell_{n+1}$ and voids at the half-rungs, so the checkerboard follows from phase structure alone.

$C$ is not just a geometric label. It measures the **degree of constructive interference** between the two fluid wakes. Where $C \approx 1$, both wakes are in phase—the two fluids are tightly coupled, conversion is efficient, and Qi density $q$ is high. Where $C \approx -1$, the wakes are maximally out of phase—the fluids work against each other, conversion stalls, and $q \to 0$.

The physical interpretation is:

$$q(\mathbf{x}) = \frac{1 + C(\mathbf{x})}{2}$$

At the bubble center ($C = 1$): $q \to 1$, fully coherent.
At the void center ($C = -1$): $q \to 0$, fully disordered.

### 1.2 Derivation of the Condensation Threshold

The condensation threshold $\theta_{\text{cond}}$ is not a free parameter—it is the fixed point where the conversion rate (which builds coherence) balances the effective diffusion rate (which smooths it away).

**Conversion power.** The single-channel Qi transmission function is the asserted input $g(q) = q/(\varphi^2 + q^2)$ (`foundations/cassi-first-principles.md` §2.5; selection audit in `computations/gate_origin_audit.py`). The first-principles driving factor is $(1-q)$, which provides the thermodynamic distance from equilibrium. The conversion energy injection per unit time is:

$$P_{\text{conv}} = \omega_0 \cdot g(q) \cdot (1-q) \cdot \rho_0, \qquad g(q) = \frac{q}{\varphi^2 + q^2}$$

The gate couples at two levels: $g(q)$ controls *how efficiently* the two fluids convert (the Qi coherence enables conversion), while $(1-q)$ controls *how much* conversion is needed (the remaining deviation from equilibrium).

**Effective diffusion power.** The condensation field's natural tendency to smooth gradients dissipates structure:

$$P_{\text{diff}} = D_{\text{eff}} \cdot \frac{\langle|\nabla C|^2\rangle}{C^2} \cdot \rho_0$$

where $D_{\text{eff}}$ is the **effective diffusion coefficient of the condensation field**—not the microscopic scalar diffusion $D$ from the PDE, but the coarse-grained damping rate of the $C(x,y)$ interference pattern at the bubble scale. $D_{\text{eff}}$ includes contributions from the PDE's microscopic $D$, advective mixing by the velocity field, and any conversion-mediated smoothing (§9.2 explains how to measure it).

At the edge ($C = \theta_{\text{cond}}$), the azimuthally-averaged normalized gradient from the condensation field is:

$$\left.\frac{\langle|\nabla C|^2\rangle}{C^2}\right|_{\text{edge}} \approx \frac{\alpha^2 + \beta^2}{2} \cdot \frac{1-\theta_{\text{cond}}}{\theta_{\text{cond}}^2}$$

**Fixed point.** Setting $P_{\text{conv}} = P_{\text{diff}}$ at $C = \theta_{\text{cond}}$ and using $q = (1+\theta_{\text{cond}})/2$, $1-q = (1-\theta_{\text{cond}})/2$:

$$\omega_0 \cdot \frac{(1+\theta_{\text{cond}})/2}{\varphi^2 + ((1+\theta_{\text{cond}})/2)^2} \cdot \frac{1-\theta_{\text{cond}}}{2} = D_{\text{eff}} \cdot \frac{\alpha^2 + \beta^2}{2} \cdot \frac{1-\theta_{\text{cond}}}{\theta_{\text{cond}}^2}$$

Canceling the common factor $(1-\theta_{\text{cond}})$ (valid for $\theta_{\text{cond}} \neq 1$, non-degenerate bubbles):

$$\boxed{\theta_{\text{cond}}^2 (1 + \theta_{\text{cond}}) = R\left(\varphi^2 + \frac{(1+\theta_{\text{cond}})^2}{4}\right), \qquad R \equiv \frac{2 D_{\text{eff}}(\alpha^2 + \beta^2)}{\omega_0}}$$

This equation determines $\theta_{\text{cond}}$ from the single dimensionless parameter $R$, which combines the condensation field's effective diffusion coefficient $D_{\text{eff}}$, the conversion rate $\omega_0 = \lambda = 0.1$, and the condensation field wavenumbers $\alpha = 2\pi/\Lambda_Y$, $\beta = 2\pi/\Lambda_I$.

**The phase diagram.** Conditional on the asserted single-channel gate $g(q) = q/(\varphi^2 + q^2)$, the relation with the true gate is **monotonic**: larger $R$ produces larger $\theta_{\text{cond}}$ (thicker-edge bubbles). There is no catastrophic percolation threshold—bubbles never merge spontaneously. The mapping is smooth from $\theta_{\text{cond}} \to 0$ at $R \to 0$ (infinitesimal bubbles) to $\theta_{\text{cond}} \to 1$ at $R \to 2/(\varphi^2 + 1) \approx 0.552$ (bubbles filling the entire lattice). The calibration $R \approx 0.093$ gives the phenomenologically-inferred $\theta_{\text{cond}} = 0.45$.

**The wavenumbers.** The condensation field wavelengths are set by the bubble scale: $\Lambda_Y = \ell_{285} \approx 191$ Mpc (the Cassi bubble diameter from `foundations/dimensionful-cascade.md`), $\Lambda_I = \Lambda_Y/\varphi \approx 118$ Mpc. This gives $\alpha = 2\pi/\Lambda_Y \approx 1.07 \times 10^{-24}$ m$^{-1}$, $\beta = \varphi\alpha \approx 1.73 \times 10^{-24}$ m$^{-1}$, and $\alpha^2 + \beta^2 = \alpha^2(1+\varphi^2) \approx 4.12 \times 10^{-48}$ m$^{-2}$.

**Status.** The functional form relating $\theta_{\text{cond}}$ to $R$ is **Derived conditional on the asserted gate form** from the balance of gated conversion and diffusion. The numerical value depends on $D_{\text{eff}}/\omega_0$—the ratio of the condensation field's effective diffusion to the conversion rate, measurable from the PDE. The phenomenologically-calibrated $\theta_{\text{cond}} = 0.45$ corresponds to $R \approx 0.093$. Section 9 specifies the PDE computation to determine $R$ and $\theta_{\text{cond}}$ from first principles.

---

## 2. The Edge Profile: Radial Gradient

### 2.1 The 2D Cross-Section (Yang-Yin Plane)

Near a bubble center at the origin, the condensation field is approximately quadratic:

$$C(r) \approx 1 - \frac{1}{2}\left(\alpha^2 x^2 + \beta^2 y^2\right), \qquad \alpha = \frac{2\pi}{\Lambda_Y},\;\; \beta = \frac{2\pi}{\Lambda_I}$$

The bubble boundary $C = \theta_{\text{cond}}$ is the ellipse:

$$\frac{x^2}{a_X^2} + \frac{y^2}{a_Y^2} = 1, \qquad a_X = \frac{\sqrt{2(1-\theta_{\text{cond}})}}{\alpha},\;\; a_Y = \frac{\sqrt{2(1-\theta_{\text{cond}})}}{\beta},\;\; \frac{a_X}{a_Y} = \frac{\beta}{\alpha} = \varphi$$

The full field (not approximated) determines the exact boundary shape. Near the saddle toward a diagonal neighbor at $(\Lambda_Y/2, \Lambda_I/2)$, the contour flattens—the bubble is not a perfect ellipse.

### 2.2 Gradient at the Edge: Quantitative Anisotropy

The gradient of $C$ at the boundary determines how sharp the edge transition is:

$$|\nabla C| = \sqrt{(\alpha \sin(\alpha x)\cos(\beta y))^2 + (\beta \cos(\alpha x)\sin(\beta y))^2}$$

Evaluating the gradient anisotropy ratio. Along the axial direction toward a void (e.g. the Yin axis, $x=0$): $C = \cos(\beta y)$, so $|dC/dy| = \beta|\sin(\beta y)| \approx \beta\sqrt{1-C^2}$. Along the diagonal direction toward a neighboring bubble (path to saddle at $(\Lambda_Y/4, \Lambda_I/4)$): $C = \cos(\pi t/2)\cos(\pi t/2) = \cos^2(\pi t/2)$, so $|dC/ds| \approx \sqrt{(\alpha^2+\beta^2)(1-C^2)}/2$.

The ratio of edge steepnesses at the same $C = \theta_{\text{cond}}$ is:

$$\boxed{\frac{|\nabla C|_{\text{axial}}}{|\nabla C|_{\text{diag}}} = \frac{2\beta}{\sqrt{\alpha^2 + \beta^2}} = \sqrt{\frac{4\varphi^2}{1+\varphi^2}} \approx 1.70}$$

This is a **zero-parameter prediction**: the void-ward (axial) edge is $1.70\times$ steeper than the neighbor-ward (diagonal) edge. The ratio is close to $\varphi \approx 1.618$ but not identical—the edge steepness anisotropy is a distinct observable from the bubble's $\varphi$ shape anisotropy.

**Physical interpretation.** Crossing the bubble boundary along the contracted Yin axis (toward a void) produces a $1.70\times$ steeper drop in $q$, $\rho$, and $G_{\text{eff}}$ than crossing toward a neighboring bubble. The edge is "softer" along Yang and toward neighbors; "sharper" along Yin and toward voids.

### 2.3 The 3D Edge Shape

The bubble extends along the string axis (the cascade direction) with bounded extent set by the cascade-step separation. The full 3D condensation field is:

$$B(x, y, z) = \cos(\alpha x)\cos(\beta y) \cdot \cos(\gamma z), \qquad \gamma = \frac{2\pi}{P_\parallel}$$

where $P_\parallel$ is the along-string bubble period. The bubble edge in 3D is:

$$\{B(x,y,z) = \theta_{\text{cond}}\}$$

an oblate triaxial spheroid—extended in Yang, contracted in Yin, bounded along the string—with a waisted cross-section in the Yin-string plane (the anti-phase node produces the paired-sheet morphology; see `foundations/why-three-dimensions.md` §4).

---

## 3. Radial Interior Structure: the Ring Ladder

A rung-$n$ bubble's interior is not featureless: the doublet phase
$\alpha = \pi\,u$, with $u = \log_\varphi(r/\ell_n)$ the log-rung radial
coordinate, quantizes the interior into a nested ladder of matter and void
rings. Moving radially inward from the bubble edge, matter condenses at the
radii where the doublet has completed an integer number of $\pi$-advances,
and voids open at the half-rungs between them.

### 3.1 The boxed ring law

The radial phase of the doublet is

$$\boxed{\alpha(r) = \pi\,u, \qquad u = \log_\varphi\!\left(\frac{r}{\ell_n}\right)}$$

—the internal-phase advance of the $(\Psi_Y, \Psi_I)$ doublet as one descends
the cascade rungs (`foundations/spin-fibonacci-spiral.md` §2.1: the doublet
advances $\pi$ per rung, completing one full SO(2) cycle every two rungs). The
pool-cell parities (`foundations/rung-offset-mechanism.md` §4.1) assign the
standing pattern's antinodes to matter and its nodes to voids: the cosine
mode $\cos\bigl(\pi(u-n)\bigr)$ has antinodes at the integer rungs (matter),
and the sine mode $\sin\bigl(\pi(u-n)\bigr)$ has antinodes at the half-rungs
(voids). Combining the phase quantization with the parities gives the ladder:

$$\boxed{r_k^{\text{matter}} = \ell_n\,\varphi^{-k}, \qquad
r_k^{\text{void}} = \ell_n\,\varphi^{-(k+\frac12)}, \qquad k = 0,1,2,\ldots}$$

Matter ring $k$ sits at the radius where $u = -k$ (an integer), its adjacent
void one half-rung inward at $u = -(k+\tfrac12)$, i.e.
$r_k^{\text{void}} = r_k^{\text{matter}}\,\varphi^{-1/2}$. The radial
spacing ratios are fixed:

$$\frac{r_{k+1}^{\text{matter}}}{r_k^{\text{matter}}} = \varphi^{-1}
\approx 0.618, \qquad
\frac{r_k^{\text{void}}}{r_k^{\text{matter}}} = \varphi^{-1/2}
\approx 0.786$$

so adjacent matter rings are separated by a factor $\varphi^{-1} = 0.618$
and each matter ring is trailed inward by its void at a factor
$\varphi^{-1/2} = 0.786$—strict matter/void alternation, exactly the
checkerboard parity of §1.1 read radially instead of on the 2D lattice.

**Tier: Derived conditional.** The ring law is derived conditional on (i) the
asserted pitch convention $\Theta = 2\pi n$ per rung of
`foundations/spiral-dynamics.md` §1.1; (ii) the doublet's $\pi$-per-rung
internal advance (`foundations/spin-fibonacci-spiral.md` §2.1); (iii) the
pool-cell parities (`foundations/rung-offset-mechanism.md` §4.1); (iv) the
~10-rung nesting depth (below); and (v) the radial-reading inference—the
reading of the doublet phase radially, $\alpha = \pi\,u$, is an **inference**
resting on the nested-sub-lattice structure of `foundations/bubble-lattice-fabric.md`
§3.2, not an established identity. Item (v) is flagged throughout.

### 3.2 The radial phase current

The radial phase $\alpha = \pi u$ carries a radial phase current. The
doublet's phase advances $\pi$ per rung, and $u$ runs over one rung per
factor $\varphi$ of radius, so a radial leg spanning one rung accumulates one
$\pi$-advance:

$$J_r = \frac{\rho\,\pi}{r\ln\varphi}, \qquad
\int_{\ell_{n-1}}^{\ell_n} J_r\,dr = \rho\pi$$

per rung shell. This is the **radial reading** of the doublet phase
$\alpha = \pi u$—the intra-shell analogue of the axial phase current
$J_z = R^2\partial_z\theta$ that carries coherence between cascade scales
(`foundations/qi-flow-double-helix.md`; `foundations/bubble-lattice-fabric.md`
§1.1). It is attributed accurately as a new radial reading: the repo's
established identity is the axial $J_z$; there is no established "axial
phase current $= \rho\pi$" anchor, and the $J_r$ form here rests on the same
radial-reading inference as the ring law itself.

### 3.3 Nesting depth and the cascade connection

The nesting depth sets the number of resolvable rings. The cascade
suppression floor of ~1% (`foundations/bubble-lattice-fabric.md` §3.3) bounds
the physically meaningful inward descent to $\Delta n \approx 10$ rungs; the
refined count is

$$N = \frac{\ln 100}{\ln\varphi} = 9.570$$

so a simulated bubble shows **~10 matter rings** (interleaved with 9 void
rings) inside its shell.

Each matter ring is itself a nested condensate: because
$\ell_{n-k} = \ell_{\text{Pl}}\,\varphi^{n-k} = \ell_n\,\varphi^{-k}$, matter
ring $k$ is exactly a rung-$(n-k)$ bubble. The ladder is the **radial picture
of bubbles-within-bubbles**—the nesting chain of `foundations/bubble-lattice-fabric.md`
§3.2 read one-dimensionally through the shell. The ~10-ring count is
$n$-independent (scale-covariant): $N(R) = -\log_\varphi R$ over a radial
span $[R\ell_n, \ell_n]$ depends only on the fraction $R$, not on $\ell_n$.

**Verdict: Derived conditional / REDUCES.** The cascade connection—each ring
is a rung-$(n-k)$ condensate, the ladder realizes the nested sub-lattice
radially—is a reduction claim, and it inherits the radial-reading flag (the
identification of interior rings with nested condensates rests on the
inference of §3.1); it does not close the physics of shell interiors on its
own.

### 3.4 The φ-ellipse of each ring

By scale covariance (`foundations/bubble-lattice-fabric.md` §2), each
rung-$(n-k)$ condensate carries the same condensation field as the parent
bubble, with wavelengths scaled to $\ell_{n-k}$; its Yang-Yin cross-section is
therefore a φ-ellipse with the same axis ratio

$$\frac{a_X}{a_Y} = \varphi$$

as the parent (§2.1). **Flag as inference:** the φ-ellipticity of each ring
inherits the radial-reading inference of §3.1—it is scale covariance applied
to the nested rings, not an independent derived shape.

### 3.5 Honest negative: the naive wake-sum is not the ladder

The naive one-dimensional wake-sum that a beat picture would propose for the
intra-shell ridges,

$$f(r) = \cos\!\left(\frac{2\pi r}{\ell_n}\right) +
\cos\!\left(\frac{2\pi\varphi r}{\ell_n}\right),$$

has zeros at $r \approx \{0.191,\,0.573,\,0.809,\,0.955\}\,\ell_n$ (bisection;
verified by `two-fluid/run_bubble_ring_probe.py` Leg B). These are **not** the
matter-ring positions $\{\ell_n, \ell_n\varphi^{-1}, \ell_n\varphi^{-2},
\ell_n\varphi^{-3}\} = \{1,\,0.618,\,0.382,\,0.236\}\,\ell_n$: $0.382$ and
$0.809$ are **not** zeros of the wake-sum, and none of the four zeros lands on
a $\varphi$-ladder position. The intra-shell ladder is **phase-quantized**
(§3.1), not the wake beat.

### 3.6 Not established

Two aspects are explicitly not derived here, and the prediction is
Hypothesized (PDE-testable) pending them:

- **Ring amplitudes.** The condensation exponent $n_{\text{cond}}$ (§5.3) has
  not been applied to the interior rings; the relative ring strengths are
  open.
- **PDE realization.** Whether the two-fluid PDE realizes all ~10 interior
  rings from microphysics is not established. The analytic probe
  `two-fluid/run_bubble_ring_probe.py` (Leg C) demonstrates the radial
  envelope a simulated bubble must show; the pre-registered dynamic probe
  `two-fluid/run_bubble_ring_dynamic_probe.py` (spherical standing-condensate
  seed) runs four spatial-coupling arms—A baseline (conversion-only,
  $D=\mathbf{u}=\chi=c_s^2=0$), B diffusion ($D=0.0002$), C gravity-buoyancy
  ($\nu=0.0005$, $\chi=0$), W wave-verify ($c_s^2=0.5$)—and finds **NO RINGS
  on every arm at every epoch to $t=40$** (0 matter maxima outside the
  4-cell core; $u_{\text{rms}}\sim 10^{-4}$ even on C/W). None of the
  canonical coupling channels in this solver realizes the ladder. The
  wave-mode verification confirms `ExpandingTwoFluid3DGPU` is first-order in
  time (no $d^2E/dt^2$ wave operator; $c_s^2$ enters only as a velocity
  pressure force), so the full second-order ring-ladder wave form
  ($d^2E = c^2\nabla^2 E - \omega_0^2(E_Y-\varphi E_I)$) is not present in
  this solver—it belongs to the space-sim GLSL PDE. Whether realization
  requires that second-order form remains the open content; the honest
  four-arm null is recorded. The second-order wave-form readback in the
  owner's space sim (Godot, $N = 128$, $\omega_0^2 = 20$, featureless
  filled-ball seed, no source drive) also shows no persistent ladder—a
  transient shell with one interior ridge at ratio 0.545 (marginal
  $\varphi^{-1}$) at $t = 24$, dissipated by $t = 40$, detector self-test
  PASS (probe `diag_bubble_rings.gd` in the owner's space-sim repo). The
  ~10-ring ladder's dynamical realization therefore remains open in both
  the first-order solver and the sim's wave form.

**Test:** a simulated bubble should show ~10 matter ridges at
$r_k = \ell_n\,\varphi^{-k}$ (successive matter-ring ratio $\varphi^{-1} =
0.6180$, vs the null interleaved-ridge ratio $\varphi^{-1/2} = 0.7862$),
interleaved with 9 void troughs at $\ell_n\,\varphi^{-(k+\frac12)}$, with
strict matter/void alternation and an $n$-independent count. Cataloged as
Prediction 51 (`predictions/falsifiable-predictions.md`).

---

## 4. Influence of Neighbors and Voids

### 4.1 Diagonal Neighbors: Saddle Deformation

The nearest neighbor to a bubble is a diagonal neighbor at distance $d_{\text{diag}} = \sqrt{\Lambda_Y^2 + \Lambda_I^2}/2$. The saddle between them sits at $(\Lambda_Y/4, \Lambda_I/4)$ where $C = 0$.

The neighbor's presence deforms the edge through the global structure of $C$—not through a dynamical interaction, but because the bubble boundary IS the level set of $C$, and $C$ already includes the neighbor's contribution.

The deformation is: the boundary contour is **flattened** toward the diagonal neighbor compared to the isolated elliptical approximation. The flattening is small when $\theta_{\text{cond}} \gg 0$ (bubbles are deep within their own potential wells) and large as $\theta_{\text{cond}} \to 0$.

The saddle barrier height from bubble center to saddle is $1$ in $C$-units. In physical terms: $q_{\text{center}} \approx 1$, $q_{\text{saddle}} = 0.5$, $q_{\text{edge}} = (1+\theta_{\text{cond}})/2 \approx 0.725$ (for $\theta_{\text{cond}} = 0.45$). The Qi barrier from the edge to the saddle is $\Delta q = 0.725 - 0.5 = 0.225$.

### 4.2 Axial Voids: Full Barrier

Between a bubble and its axial neighbor (along Yang at $(\Lambda_Y, 0)$ or along Yin at $(0, \Lambda_I)$), there is a void at the midpoint where $C = -1$ and $q = 0$. These axial neighbors **never merge**—the path between them goes through $C = -1$ (a minimum), not through a saddle. The void is an absolute barrier to coherence transport.

Each bubble is connected only to its 4 diagonal neighbors, not its 4 axial neighbors. The lattice degree is 8 geometric but 4 connectable—a structural prediction of the chord geometry.

### 4.3 Void Influence on Edge Steepness

The void at $C = -1$ sits in the axial direction. Moving from the bubble center toward an axial void, $C$ drops from $1$ to $-1$—a steeper gradient than toward a diagonal saddle (which only drops to $0$). This means:

- **Axial edge** (facing a void): sharper transition, steeper $q$ gradient, more abrupt drop in $G_{\text{eff}}$
- **Diagonal edge** (facing a neighbor): gentler transition, shallower $q$ gradient, more gradual $G_{\text{eff}}$ change

The quantitative ratio is $\sqrt{4\varphi^2/(1+\varphi^2)} \approx 1.70$ (§2.2).

---

## 5. Physical Quantities at the Edge

### 5.1 Qi Density $q$

$$q(C) = \frac{1 + C}{2}$$

At $\theta_{\text{cond}} = 0.45$: $q_{\text{edge}} \approx 0.725$.
At the saddle ($C = 0$): $q_{\text{saddle}} = 0.5$.
In the void ($C = -1$): $q_{\text{void}} = 0$.

### 5.2 Effective Gravitational Constant

$$G_{\text{eff}}(C) = \frac{\pi}{\rho(C)} \bigl(1 + (\varphi^{6}-1)q(C)\bigr), \qquad \xi = \varphi^6 \approx 17.944$$

At the bubble center ($C = 1$, $q = 1$): $G_{\text{eff}} \approx (\pi/\rho_0)\varphi^6 \approx 17.94\,\pi/\rho_0$.
At the edge ($C = 0.45$, $q = 0.725$): $G_{\text{eff}} \approx (\pi/\rho_{\text{edge}})(1 + 0.725(\varphi^{6}-1)) \approx 13.3\,\pi/\rho_{\text{edge}}$.
In the void ($C = -1$, $q = 0$): $G_{\text{eff}} \to \pi/\rho_{\text{void}}$—unamplified gravity.

The transition from amplified to unamplified gravity occurs across the edge. The steepness of this transition depends on direction (axial vs. diagonal) as described in §4.3.

### 5.3 Density Profile

The matter density $\rho$ traces the condensation field because structure condenses where conversion is efficient:

$$\rho(C) \approx \rho_0 \cdot \max\!\left(0,\; \frac{C - \theta_{\text{cond}}}{1 - \theta_{\text{cond}}}\right)^{n_{\text{cond}}}$$

with $n_{\text{cond}} \approx 1$ (linear condensation) to $n_{\text{cond}} \approx 2$ (quadratic, from the catalytic template mechanism in `foundations/why-three-dimensions.md` §3.3). The exact exponent is a target for PDE computation. Section 9.4 specifies the measurement protocol.

---

## 6. Observable Signatures

### 6.1 CMB Boundary Imprint

The bubble edge at $z \approx 19$ (Qi gate engagement, the "pinch") imprints on the CMB as a preferred direction. The edge is not a sharp wall—it is a gradient in $q$ and $G_{\text{eff}}$ with $\varphi$-asymmetric steepness. This gradient produces:

- A scale-dependent preferred axis at $\ell < 5$ that fades at smaller scales (super-horizon boundary)
- The $12.2^\circ$ alignment angle between the CMB dipole (Yang axis) and the quadrupole-octopole axis (bubble boundary normal)—measured, calibrated from the data vectors; the bubble-boundary mechanism is a candidate whose orientation is fitted to the measured axis (Hypothesized; `foundations/refined-numeric-predictions.md` §2.3)

### 6.2 Void Ellipticity Prediction

The anisotropic edge steepness (§2.2) predicts that **void boundaries are sharper in the Yin direction and softer in the Yang direction**. The prediction is the boundary-**gradient** ratio $|\nabla C|_{\text{axial}}/|\nabla C|_{\text{diag}} = \sqrt{4\varphi^2/(1+\varphi^2)} = 1.70130$ (§2.2)—a steepness ratio at the same density threshold, distinct from the bubble's $\varphi$ **shape** anisotropy (axis ratio $\varphi \approx 1.618$, ellipticity $\varepsilon = 1 - \varphi^{-1} = 0.382$; §2.1). In void catalog data (SDSS/DESI), the gradient reading manifests as:

- Voids are more elongated along Yang (the softer edge allows structure to extend further before dropping below threshold)
- Voids are more sharply truncated along Yin (the steeper edge cuts off abruptly)
- The $\varphi$-shape reading (ratio of Yang-extent to Yin-extent at the density threshold tracking $\varphi$) is a separate observable from the 1.70 gradient ratio—a shape measurement cannot by itself test the 1.70

**Measured 2026-08-07** (VAST/ZOBOV SDSS DR7 + NSA volume-limited tracers, 130 voids, $R_{\text{eff}} \ge 15\,h^{-1}$Mpc): the 1.70 gradient ratio does not appear in the data—$\hat\mu = 1.005 \pm 0.221$ (99% CI [0.584, 1.753], $p_{\text{pred}} = 0.008$), NULL per the pre-registered decision tree; the T3 control fails (RSD quadrupole), so the primary is systematics-limited, and the RSD-free 2D transverse control is also NULL. The measured void shape $\varepsilon = 1 - c/a = 0.225 \pm 0.066$ (99% CI [0.210, 0.240]) excludes both the $\varphi$-shape reading 0.382 and the literal 1.70-as-shape reading 0.412. Catalog record: `predictions/falsifiable-predictions.md` §3.

The gradient anisotropy ratio and the shape ratio are two distinct predictions from the same condensation field: the bubble is $\varphi$-elliptical in shape AND the edge is $1.70\times$ steeper toward voids than toward neighbors. On the DR7 sample the 1.70 gradient ratio is null and the $\varphi$-shape reading is excluded by the measured shape ellipticity.

### 6.3 Absolute Lattice Scales

The condensation field wavelengths are set by the cascade. From `foundations/dimensionful-cascade.md`, the Cassi bubble at step 285 gives:

$$\Lambda_Y = \ell_{285} \approx 191\ \text{Mpc}, \qquad \Lambda_I = \frac{\Lambda_Y}{\varphi} \approx 118\ \text{Mpc}$$

These are the fundamental spatial periods of the chord lattice: $\Lambda_Y$ is the bubble-to-bubble spacing along Yang, $\Lambda_I/2$ is the string-to-string spacing along Yin, and the stagger is $\Lambda_Y/2$. The along-string period $P_\parallel$ is set by the cascade step spacing—the comoving distance between adjacent rungs at the bubble epoch. All three lattice dimensions are determined from the cascade table; no phenomenological inputs remain.

### 6.4 Galaxy Distribution at the Edge

Galaxies trace the condensation field. The edge region—where $C$ drops from $\theta_{\text{cond}}$ to $0$—should show:

- A transition from spiral-dominated (high-$q$, organized rotation) to diffuse/dwarf-dominated (low-$q$, weak gravity)
- The transition distance is $\sim \Lambda_I \cdot \sqrt{1-\theta_{\text{cond}}}$ along Yin and $\sim \Lambda_Y \cdot \sqrt{1-\theta_{\text{cond}}}$ along Yang—an anisotropic "coastal shelf"

---

## 7. Open Derivations

1. **$D_{\text{eff}}/\omega_0$ from the PDE.** The dimensionless parameter $R = 2 D_{\text{eff}}(\alpha^2+\beta^2)/\omega_0$ determines $\theta_{\text{cond}}$ numerically. $\omega_0 = \lambda = 0.1$ and $\alpha^2+\beta^2$ are known (§1.2). $D_{\text{eff}}$ is the effective diffusion coefficient of the coarse-grained condensation field $C(x,y)$ at the bubble scale—NOT a microscopic PDE input parameter. It must be **measured** from the PDE by seeding the $C$ pattern and observing its decay rate (§9.2). Once $D_{\text{eff}}$ is determined, $\theta_{\text{cond}}$ becomes a Derived number rather than a phenomenologically-calibrated one.

2. **Condensation exponent $n_{\text{cond}}$ (§5.3).** The power-law exponent governing how rapidly $\rho$ drops at the edge. Observable in void density profiles; testable with the PDE as described in §9.4.

3. **Neighbor coupling strength.** The Qi barrier from edge to saddle is $\Delta q = 0.225$. Whether this barrier is surmountable for Qi transport (coherence tunneling through the saddle) is a separate question from geometric connectivity—the chord connectivity docs correctly label it as Speculative.

---

## 8. Epistemic Boundaries

### Derived (from condensation field + Qi gate + cascade)

- Bubble shape: triaxial spheroid with axis ratio $\varphi$ in the Yang-Yin plane
- Lattice geometry: staggered checkerboard, $m+n$ even = bubble, odd = void
- Anisotropic edge steepness ratio: $\sqrt{4\varphi^2/(1+\varphi^2)} \approx 1.70$ (zero-parameter)
- Connectable degree: 4 (diagonal only—axial paths blocked by $C=-1$ voids)
- Functional form for $\theta_{\text{cond}}$: $\theta^2(1+\theta) = R(\varphi^2 + (1+\theta)^2/4)$ from conversion-diffusion balance
- $q(C) = (1+C)/2$: Qi density from the condensation field
- Absolute scales: $\Lambda_Y = \ell_{285}$, $\Lambda_I = \Lambda_Y/\varphi$ from the cascade table
- $G_{\text{eff}}(C)$ profile across the edge ($\xi = \varphi^6$)

### Hypothesized (PDE-testable)

- Numerical value of $\theta_{\text{cond}}$ (requires $D_{\text{eff}}$ from PDE; functional form is Derived)
- The condensation exponent $n_{\text{cond}}$ and the resulting edge density profile

### Speculative (coherence transport)

- Qi tunneling through inter-bubble saddles

---

## 9. Computational Plan: PDE Determination of $\theta_{\text{cond}}$ and $n_{\text{cond}}$

This section specifies the exact PDE computation needed to promote $\theta_{\text{cond}}$ and $n_{\text{cond}}$ from Hypothesized to Derived. The plan uses the two-fluid PDE solver (`two-fluid/cassi_two_fluid_3d_gpu.py`, `ExpandingTwoFluid3DGPU` class).

### 9.1 Corrected Parameter Mapping

The document uses "$\nu$" in two incompatible ways. We adopt the following conventions for this plan:

| Symbol in doc | Renamed to | Nature | Origin |
|:---:|:---:|---|---|
| $\nu$ (diffusion in $R = 2\nu(\alpha^2+\beta^2)/\omega_0$) | $D_{\text{eff}}$ | Effective diffusion of condensation field | **Measured** from PDE output (§9.2) |
| $\nu$ (exponent in $\rho \propto (C-\theta_{\text{cond}})^{n_{\text{cond}}}$) | $n_{\text{cond}}$ | Density profile power law | **Fitted** from PDE output (§9.4) |

The PDE code has three diffusion-like input parameters:

| Code param | Line | Default | Role in $\theta_{\text{cond}}$ |
|---|---|---|---|
| `D` | 295 | 0.0 | Momentum-space numerical viscosity (∇²), the conservation-exact canonical default (44). NOT $D_{\text{eff}}$; D>0 = the diffusion-bound readings. |
| `nu` | 295 | 0.001 | Velocity viscosity (∇²). Irrelevant for condensation. |
| `hyper_nu` | 299 | 0.0 | Hyperdiffusion (∇⁴). Disabled by default. Irrelevant. |

The $D_{\text{eff}}$ in the $\theta_{\text{cond}}$ equation is an **effective coarse-grained diffusion** of the $C(x,y)$ interference pattern at the bubble scale. It is not equal to any single PDE input: it encodes the combined effect of microscopic diffusion, advective mixing by the velocity field (which acts as an eddy diffusivity $D_{\text{turb}} \sim u_{\text{rms}} \times L_{\text{bubble}}$), and conversion-mediated smoothing. $D_{\text{eff}}$ must be determined from the PDE simulation, not read from the input parameters.

**The dimensionless ratio $R$ is scale-invariant.** In PDE code units:

$$R = \frac{2\,D_{\text{eff}}^{(\text{code})}\,(\alpha_{\text{code}}^2 + \beta_{\text{code}}^2)}{\omega_0^{(\text{code})}}$$

where $\alpha_{\text{code}} = 2\pi / \Lambda_Y^{(\text{code})}$, and $\Lambda_Y^{(\text{code})}$ is the bubble wavelength in grid units. The ratio $D_{\text{eff}}/\omega_0$ converts identically across any consistent unit system, so the code-unit measurement maps directly to the physical $R$.

### 9.2 Direct Measurement of $D_{\text{eff}}$

The most direct method: **seed the condensation field and measure its decay rate**.

#### Method A: Pattern decay

1. **Initialize** a 2D slice of the expanding PDE (64³ grid, $L = 2\pi$, or size sufficient for $\Lambda_Y \approx 32$ grid points):

   $$E_Y(\mathbf{x}) = 1.0 + A \cdot \cos(\alpha x) \cos(\beta y), \qquad E_I(\mathbf{x}) = \varphi^{-1}$$

   with $A = 0.1$ (small amplitude to stay in the linear regime), $\alpha = 2\pi/32$, $\beta = \varphi\alpha$, and no velocity perturbation ($\mathbf{u}=0$). This directly imprints the condensation field pattern as the initial condition.

   **Why this works:** The PDE's reaction-diffusion dynamics will either amplify (if $R$ is below the threshold for growth) or damp (if $R$ is above threshold) the seeded pattern. The growth/decay rate directly measures $D_{\text{eff}}$.

2. **Run parameters**:

   | Parameter | Value | Rationale |
   |---|---|---|
   | Grid | $64 \times 64 \times 4$ | 2D slice + thin z (minimal, only for 3D operator) |
   | `D` | 0.0 | Canonical default (conservation-exact, 44); D>0 = diffusion-bound |
   | `lam` | 0.1 | Derivation value $\lambda = 1/(2w)$ from `foundations/wu-xing-derivation.md` |
   | `qi_gate` | True | Qi gate active (defines $q$ from fields) |
   | `chi` | 0.0 | No chemotaxis (isolate pure reaction-diffusion) |
   | `hubble_mode` | 'conversion' | Standard expansion |
   | `a0` | 0.2 | Start near bubble epoch |
   | `max_H` | 0.5 | Safety cap |
   | `dt` | 0.001 | Standard CFL-limited timestep |
   | Steps | 10,000 | Sufficient for several e-folds of evolution |

3. **Monitor** $q_{\text{center}}(t)$ and $C_{\text{center}}(t)$ at the bubble center $(x,y) = (0,0)$. The $C$ pattern amplitude evolves as:

   $$C_{\text{center}}(t) \approx C_0 \cdot \exp\left(-\Gamma_{\text{eff}} \, t\right)$$

   where $\Gamma_{\text{eff}} = D_{\text{eff}}(\alpha^2+\beta^2)$ is the effective damping rate of the condensation field. Extract $\Gamma_{\text{eff}}$ by fitting an exponential to $C_{\text{center}}(t)$ over the linear regime.

4. **Compute $D_{\text{eff}}$**:

   $$D_{\text{eff}} = \frac{\Gamma_{\text{eff}}}{\alpha^2 + \beta^2}$$

   where $\alpha, \beta$ are in code units (radians per grid length).

5. **Compute $R$**:

   $$R = \frac{2 D_{\text{eff}}(\alpha^2+\beta^2)}{\omega_0} = \frac{2 \Gamma_{\text{eff}}}{\omega_0}$$

   where $\omega_0 = \text{lam}$ in code units. **Crucially**, $R$ is independent of the unit mapping—it falls directly out of the measured damping rate.

6. **Solve for $\theta_{\text{cond}}$**:

   $$\theta_{\text{cond}}^2 (1 + \theta_{\text{cond}}) = R\left(\varphi^2 + \frac{(1+\theta_{\text{cond}})^2}{4}\right)$$

   This is a cubic in $\theta_{\text{cond}}$. Solve numerically (e.g., `scipy.optimize.fsolve` or Newton's method with initial guess $\theta_{\text{cond}} = 0.45$).

#### Method B: Emergent pattern (cross-check)

As a cross-check, run from random initial conditions (`initial_amplitude=0.2`) on a $128^2 \times 64$ grid with the same parameters above (but `chi=5.0` to allow gravitational assembly). The `chi=5.0` gravity channel drives the wake-wave pattern out of the random initial conditions—assembly is the driver, not spontaneous emergence (`two-fluid/run_bubble_ring_dynamic_probe.py`: the canonical first-order solver forms no radial structure from no-drive seeds). After the system reaches quasi-steady structure ($\sim$5,000 steps), extract:

- The dominant condensation wavelength $\Lambda_Y^{(m)}$ from the Fourier power spectrum $P(k_x, k_y)$ of $q(x,y)$.
- The measured $\theta_{\text{cond}}^{(m)}$ from the $q(C)$ scatter plot (§9.3).
- Compare with Method A's prediction.

### 9.3 Direct Extraction of $\theta_{\text{cond}}$ from $q(C)$

Independently of Method A, $\theta_{\text{cond}}$ can be measured directly from a fully-developed bubble simulation:

1. Run the expanding PDE as in Method B above, $128 \times 128 \times 64$ grid, with `qi_gate=True`, standard parameters.
2. At each diagnostic step (every 200 steps), extract the 2D $q(x,y)$ field (from the Qi gate diagnostic) and $C(x,y)$ (computed as $(2q-1)$ from $q = (1+C)/2$).
3. Construct the **$q(C)$ scatter plot**: for each grid cell in the Yang-Yin midplane ($z \approx 0$), add a point $(C_i, q_i)$.
4. The scatter should show a characteristic S-curve: $q \approx 1$ for $C > \theta_{\text{cond}}$ (inside the bubble), dropping to $q \approx 0$ for $C < \theta_{\text{cond}}$ (outside).
5. Fit the threshold as the $C$-value where $q$ drops below $0.5$ (the midpoint of the transition). Alternatively, fit a sigmoid:

   $$q(C) = \frac{1}{1 + \exp(-(C - \theta_{\text{cond}})/\sigma)}$$

   and extract $\theta_{\text{cond}}$ as the sigmoid midpoint.

**Consistency check:** The $\theta_{\text{cond}}$ from this scatter fit must agree with the value predicted by Method A via $R$. Disagreement > 10% indicates the effective diffusion is not the only determinant of the edge—other processes (advection, chemotaxis, gravity) contribute.

### 9.4 Measurement of the Condensation Exponent $n_{\text{cond}}$

The density profile exponent $n_{\text{cond}}$ determines how rapidly $\rho$ drops from $\rho_0$ inside the bubble to $\rho \to 0$ outside:

$$\rho(C) \approx \rho_0 \cdot \max\!\left(0,\; \frac{C - \theta_{\text{cond}}}{1 - \theta_{\text{cond}}}\right)^{n_{\text{cond}}}$$

**Measurement protocol:**

1. From the same simulation as §9.3, extract radial profiles of $\rho(r)$ along both axial directions ($x=0$ toward void, $y=0$ toward void). Use a wedge average of $\pm 10^\circ$ around each direction to reduce noise.
2. Convert radial distance $r$ to $C(r)$ using the analytic condensation field: $C(r) = \cos(\alpha r)$ along the Yang axis or $C(r) = \cos(\beta r)$ along the Yin axis.
3. For grid cells with $C > \theta_{\text{cond}}$, fit:

   $$\log \rho = \log \rho_0 + n_{\text{cond}} \cdot \log\!\left(\frac{C - \theta_{\text{cond}}}{1 - \theta_{\text{cond}}}\right)$$

   using $\theta_{\text{cond}}$ from §9.2/§9.3. The slope is $n_{\text{cond}}$.
4. Report $n_{\text{cond}}$ with bootstrap uncertainty from the fit residuals.

**Anisotropy check:** The fit should be performed separately for the Yang and Yin axial directions. If $n_{\text{cond}}$ differs measurably between the two, the condensation field alone does not determine the density profile—additional direction-dependent physics (e.g., velocity shear anisotropy) is active. A difference > 0.2 warrants investigation.

### 9.5 Parameter Summary and Cross-Checks

| Parameter | Method | Output | Status after computation |
|---|---|---|---|
| $D_{\text{eff}}$ | Pattern decay (§9.2 Method A) | Effective diffusion coefficient | Derived |
| $\theta_{\text{cond}}$ | Computed from $R$ via cubic (§9.2 step 6) | Condensation threshold | Derived (from $D_{\text{eff}}$) |
| $\theta_{\text{cond}}$ | Direct fit from $q(C)$ scatter (§9.3) | Cross-check threshold | Derived (empirical) |
| $n_{\text{cond}}$ | Log-log fit of $\rho(C)$ (§9.4) | Density exponent | Derived |
| $R$ | From $2\Gamma_{\text{eff}}/\omega_0$ | Dimensionless balance ratio | Derived |

**Scaling test:** Repeat Method A at 2-3 grid resolutions ($N=48, 64, 96$) with the same physical box size to verify that $D_{\text{eff}}$ converges. Advection-induced eddy diffusivity should be resolution-independent in the resolved range; microscopic $D$ dominates at low resolution. The converged value is the physical $D_{\text{eff}}$.

### 9.6 Analytical Bounds

Even before the PDE computation, tight bounds can be placed on both parameters from existing theory.

#### Bounds on $\theta_{\text{cond}}$

The phenomenologically-calibrated $\theta_{\text{cond}} = 0.45$ corresponds to $R \approx 0.093$. We can bound $\theta_{\text{cond}}$ from two directions:

**Lower bound ($\theta_{\text{cond}} \geq 0.1$):** A bubble with $\theta_{\text{cond}} < 0.1$ would have its edge so close to the saddle ($C=0$) that neighbor connectivity becomes inevitable. The connectable degree would increase from 4 to 8, contradicting the structural prediction of `chord_connectivity.py`. Since the connectivity prediction is well-verified geometrically, we have $\theta_{\text{cond}} \geq 0.1$, giving $R \geq 1.9 \times 10^{-3}$.

**Upper bound ($\theta_{\text{cond}} \leq 0.7$):** A bubble with $\theta_{\text{cond}} > 0.7$ would have $q_{\text{edge}} > 0.85$, meaning the edge region is nearly as coherent as the bubble center. The void-bubble density contrast would be $\rho_{\text{center}}/\rho_{\text{edge}} \lesssim 1.3$, too low to produce the observed cosmic web (void-bubble density contrasts of 10-100 are required by galaxy surveys). This gives $\theta_{\text{cond}} \leq 0.7$, $R \leq 0.215$.

**Tightest bound (from $\lambda$):** The PDE conversion rate $\lambda = 0.1$ (derived, $w=5$). At the canonical default $D = 0$ (the conservation-exact setting — `parameter-inventory.md` §6; the D=0.001 diffusion was the entire Eulerian eroder, 44) the microscopic contribution to $D_{\text{eff}}$ vanishes, so the bare estimate rests entirely on advective mixing (measurable, §9.2). Under the old $D = 0.001$ default the bare estimate was $D_{\text{eff}} \approx D = 0.001$ (the diffusion-bound reading); at $\Lambda_Y = 32$ grid points ($\alpha_{\text{code}} = 2\pi/32 \approx 0.196$, $\beta_{\text{code}} = 0.318$, $\alpha^2+\beta^2 \approx 0.139$):

$$R_{\text{bare}} = \frac{2 \times 0.001 \times 0.139}{0.1} = 2.78 \times 10^{-3}$$

which gives $\theta_{\text{cond}} \approx 0.12$—at the lower bound. This suggests the phenomenologically-calibrated 0.45 requires $D_{\text{eff}}$ to be approximately $30\times$ larger than the old microscopic $D$, likely from advective enhancement.

**Testable prediction:** The PDE measurement will yield $\theta_{\text{cond}}$ in one of three regimes:

| Regime | $\theta_{\text{cond}}$ | $R$ | Implication |
|---|---|---|---|
| Near-surface | 0.1–0.3 | $< 0.04$ | Advection doesn't enhance diffusion; bubbles are thin-skinned |
| **Mid-range** | **0.3–0.6** | **0.04–0.15** | **Advection enhances diffusion ~10–50$\times$; bubbles match phenomenology** |
| Nearly-filling | 0.6–0.7 | 0.15–0.22 | Strong advective enhancement; bubbles fill most of the lattice |

If the result lands in the mid-range (best guess based on phenomenological success), the advective enhancement factor $D_{\text{eff}}/D$ serves as a **derived turbulent diffusivity ratio** at the bubble scale—a new structural number.

#### Bounds on $n_{\text{cond}}$

**Lower bound: $n_{\text{cond}} \geq 1$.** The density cannot respond more steeply than linearly to the condensation field because the driving mechanism (conversion rate $\propto q \propto (1+C)/2$) is linear in $C$ for small deviations from threshold. A sub-linear response ($n_{\text{cond}} < 1$) would require a suppression mechanism with no physical basis.

**Upper bound: $n_{\text{cond}} \leq 2$.** Quadratic response arises naturally from the catalytic template mechanism (`foundations/why-three-dimensions.md` §3.3): existing density enhances further condensation, giving a self-amplifying $n_{\text{cond}} = 2$ in the limit. Values above 2 would require a higher-order amplification mechanism not present in the two-fluid PDE.

**Conjecture: $n_{\text{cond}} \approx 3/2$.** The condensation front moves outward from the bubble center. Points further from the center crossed the threshold earlier and have accumulated density for longer. The accumulated density scales as $\rho \propto \delta^{3/2}$ for a diffusive front ($\dot{\delta} \propto 1/\sqrt{t}$), which translates to $n_{\text{cond}} \approx 1.5$ when template acceleration is active. The precise value depends on whether the growth phase is diffusion-limited ($n \approx 0.75$, excluded by the $n \geq 1$ bound) or template-accelerated ($n \approx 1.5$).

$$n_{\text{cond}} \in [1.0, 2.0], \quad \text{best guess: } n_{\text{cond}} \approx 1.5$$

The PDE measurement will definitively determine this.

### 9.7 Supplementary Physical Interpretations

Once $\theta_{\text{cond}}$ and $n_{\text{cond}}$ are determined, several derived quantities follow:

| Derived quantity | Formula | Example ($\theta_{\text{cond}}=0.45$, $n_{\text{cond}}=1.5$) |
|:---|---:|---:|
| Edge $q$ | $q_{\text{edge}} = (1+\theta_{\text{cond}})/2$ | 0.725 |
| Midpoint density ($C=0$, saddle) | $\rho_{\text{saddle}}/\rho_0$ | 0 (below threshold; $\rho$ formally zero) |
| Density at $C = \theta_{\text{cond}}/2$ | $\bigl((\theta_{\text{cond}}/2 - \theta_{\text{cond}})/(1-\theta_{\text{cond}})\bigr)^{n_{\text{cond}}} = (\theta_{\text{cond}}/(1-\theta_{\text{cond}}))^{n_{\text{cond}}}$ | $(0.45/0.55)^{1.5} \approx 0.74$ |
| Advective enhancement | $D_{\text{eff}}/D$ | $\approx 34$ for $R=0.093$ |
| Edge width (Yin) | $\Delta r_{\text{Yin}} = \Lambda_I \cdot \sqrt{1-\theta_{\text{cond}}}$ | $118 \times \sqrt{0.55} \approx 87$ Mpc |
| Edge width (Yang) | $\Delta r_{\text{Yang}} = \Lambda_Y \cdot \sqrt{1-\theta_{\text{cond}}}$ | $191 \times \sqrt{0.55} \approx 142$ Mpc |
| $G_{\text{eff}}$ ratio (center/edge) | $\varphi^6/(1+q_{\text{edge}}(\varphi^{6}-1)) \times (\rho_{\text{edge}}/\rho_0)$ | $17.94/13.28 \times 0.30 \approx 0.41$ |
| $G_{\text{eff}}$ ratio (edge/void) | $(1+q_{\text{edge}}(\varphi^{6}-1))/1 \times (\rho_{\text{void}}/\rho_{\text{edge}})$ | $13.3 \times \rho_{\text{void}}/\rho_{\text{edge}}$ |

---

## 10. The Lattice at Other Scales

The condensation field $B(x,y,z)$ and its checkerboard lattice are not specific to the cosmological scale of step 285. The two-fluid PDE is scale-covariant under φ-rescaling, so the identical field operates at every cascade rung. The full derivation and implications are in `foundations/bubble-lattice-fabric.md`.

---

## References

- `visual-explainers/chord_lattice.py`—condensation field, staggered lattice, bubble shape derivation
- `visual-explainers/chord_connectivity.py`—percolation analysis, saddle barriers
- `visual-explainers/chord_side_on.py`—3D bubble shape, waisted lobe-pairs, string threading
- `foundations/why-three-dimensions.md`—three dimensions from the spiral's Frenet-Serret frame, triaxial spheroid, anti-phase selection
- `foundations/wake-geometry.md`—wake beat envelope, staggered checkerboard placement, closure ladder
- `foundations/wu-xing-derivation.md`—$w = 5$ uniqueness (all bubbles identical)
- `foundations/dimensionful-cascade.md`—Cassi bubble at step 285, 191 Mpc
- `foundations/spiral-dynamics.md`—$c(r)$ profile, wave speed; $H \propto (1-q)$
- `foundations/cassi-first-principles.md`—Qi gate $g(q) = q/(\varphi^2+q^2)$, conversion dynamics
- `consciousness/consciousness-from-phi.md` §3—two-bubble correlation test
- `visual-explainers/string_bubble_cascade.py`—3D damped-wave two-fluid PDE: string → pinch → spheroid → cascade
- `two-fluid/cassi_two_fluid_3d_gpu.py`—PDE solver, $D$, $\lambda$, Qi gate implementation
- `foundations/bubble-lattice-fabric.md`—universal condensation field, checkerboard lattice, scale-covariance
- `foundations/spin-fibonacci-spiral.md`—doublet $\pi$-per-rung internal advance (radial ring phase)
- `foundations/rung-offset-mechanism.md`—pool-cell parities: cosine antinodes at integer rungs, sine antinodes at half-rungs
- `two-fluid/run_bubble_ring_probe.py`—ring-ladder probe (Prediction 51): analytic ring law, honest negative, radial envelope
- `two-fluid/run_bubble_ring_dynamic_probe.py`—ring-ladder dynamic-realization probe (Prediction 51): four spatial-coupling arms A/B/C/W, NO RINGS on all arms to $t=40$
- `predictions/falsifiable-predictions.md`—Prediction 51 (bubble-shell ring ladder)