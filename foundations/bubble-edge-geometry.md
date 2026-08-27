# Bubble Edge Geometry: Physical Profile of the Condensation Boundary

## Status: Derived transverse geometry; Hypothesized axial/radial coordinate assignments; Tested radial-ladder realization REJECT; Derived conditional threshold relation; Asserted single-channel gate form—August 2026

## Abstract

The chord lattice (`visual-explainers/chord_lattice.py`) derives the geometric skeleton of the megacascade: a staggered checkerboard of bubble and void sites from the supplied condensation field $C(x,y) = \cos(2\pi x/\Lambda_Y)\cos(2\pi y/\Lambda_I)$. This document derives the geometric level-set profile of the condensation boundary—its radial and 3D edge shape—and records conditional/Hypothesized proxy readings for $r$, $q_{\mathrm{proxy}}$, $\rho$, and $G_{\text{eff}}$ once separate constitutive maps are supplied. Supplied adjacent-rung wakes provide an exact phase-staggered additive layer template. They do not generate the multiplicative interior ring ladder, select their own drive frequency, or convert phase nodes into physical gaps. The geometric proxy alone does not derive those physical profiles or their observable consequences.

All bubbles carry the same Wu Xing number $w = 5$ (Derived conditional under the selected construction in `foundations/wu-xing-derivation.md`; the physical organizing cycle and five-channel application remain Hypothesized). The lattice is homogeneous—every bubble is structurally identical. The "neighboring bubble" in the chord lattice is the same $w$, spatially separated by $\varphi$-scaled interference.

**Figure:** `visual-explainers/string_bubble_cascade.png`—6-panel 3D damped-wave two-fluid PDE with sharper c² trap (α=0.15): pentagon at pinch (m=5 24.6%) → a transient φ-ellipsoid coherence-shell reading (σ_x/σ_z=2.510, σ_x/σ_y=1.422 at step 1100; the energy distribution is round, σ_x/σ_z=1.000, and the transverse σ_x/σ_y is set by the φ-scaled IC envelope) → cascade r-field shown via E_Y/E_I ratio. The bubble forms transiently as a coherent φ-shaped structure at early times (`visual-explainers/string_bubble_cascade.py`).

---

## 1. The Condensation Field as a Physical Proxy

### 1.1 From Interference to Coherence

The chord lattice field is:

$$\boxed{C(x,y) = \cos\!\left(\frac{2\pi x}{\Lambda_Y}\right) \cos\!\left(\frac{2\pi y}{\Lambda_I}\right), \qquad \Lambda_Y = \varphi\,\Lambda_I}$$

This is the product of the two perpendicular wake systems—Yang wake along the extended axis, Yin wake along the contracted axis. The W1 experiment confirmed anti-phase coupling, so the $m+n$ even sublattice (where $C = +1$ at extrema) is assigned the condensate sites and the $m+n$ odd sublattice (where $C = -1$) is assigned the voids. For supplied adjacent-rung carriers, the wake beat envelope of `foundations/wake-geometry.md` §2 has antinodes at $m\,\ell_{n+1}$, nodes at the half-rungs, and alternating demodulated sign across neighboring antinodes. This supplies a conditional interferometric placement template; a separate constitutive law must turn the template into physical condensation and suppressed transfer.

The raw intensity coordinate $q_{\mathrm{proxy}}$ is high where $C \approx 1$ and vanishes where $C \approx -1$, but it is not the bounded canonical Qi variable. Define a separately supplied constitutive map $q_{\mathrm{solver}}=\mathcal{M}(q_{\mathrm{proxy}})$ with $\mathcal{M}:[0,2]\to[0,1]$. Canonical conversion uses the measured solver variable $q_{\mathrm{solver}}$; relating it to the geometric proxy requires this separate map. The conditional gate reading below therefore uses $g(q_{\mathrm{solver}})(1-q_{\mathrm{solver}})$.

The physical interpretation is:

Within this paper's condensation-proxy ansatz, define

$$q_{\mathrm{proxy}}(\mathbf{x}) = \frac{(1 + C(\mathbf{x}))^2}{2}.$$

At the bubble center ($C = 1$), $q_{\mathrm{proxy}} \to 2$, the maximum of the raw geometric intensity coordinate. At the void center ($C = -1$), $q_{\mathrm{proxy}} \to 0$. The bounded canonical reading is $q_{\mathrm{solver}}=\mathcal{M}(q_{\mathrm{proxy}})$ and is not fixed by this geometric assignment.

### 1.2 Derivation of the Condensation Threshold

The condensation threshold $\theta_{\text{cond}}$ is fixed conditionally by the conversion–diffusion balance once the asserted gate, the bounded proxy-to-solver map $\mathcal{M}$, and the balance parameter $R$ are supplied. Determining these inputs from the PDE remains open.

**Conditional conversion power.** The single-channel Qi transmission function is the asserted input $g(q_{\mathrm{solver}}) = q_{\mathrm{solver}}/(\varphi^2 + q_{\mathrm{solver}}^2)$ (`foundations/cassi-first-principles.md` §2.5; selection audit in `computations/gate_origin_audit.py`). The bounded solver variable supplies the thermodynamic distance from equilibrium through $(1-q_{\mathrm{solver}})$. The canonical relaxation itself uses the measured solver $q_{\mathrm{solver}}$; the proxy substitution $q_{\mathrm{solver}}=\mathcal{M}(q_{\mathrm{proxy}})$ is conditional on the separate constitutive map. The corresponding conditional conversion energy injection per unit time is:

$$P_{\text{conv}} = \omega_0 \cdot g(q_{\mathrm{solver}}) \cdot (1-q_{\mathrm{solver}}) \cdot \rho_0, \qquad g(q_{\mathrm{solver}}) = \frac{q_{\mathrm{solver}}}{\varphi^2 + q_{\mathrm{solver}}^2}$$

The gate enters at two levels in this conditional model: $g(q_{\mathrm{solver}})$ is the asserted transmission input, while the bounded solver openness $(1-q_{\mathrm{solver}})$ decreases as $q_{\mathrm{solver}}$ rises. Their product sets the conditional gated-conversion power used below.

**Effective diffusion power.** The condensation field's natural tendency to smooth gradients dissipates structure:

$$P_{\text{diff}} = D_{\text{eff}} \cdot \frac{\langle|\nabla C|^2\rangle}{C^2} \cdot \rho_0$$

where $D_{\text{eff}}$ is the **effective diffusion coefficient of the condensation field**—not the microscopic scalar diffusion $D$ from the PDE, but the coarse-grained damping rate of the $C(x,y)$ interference pattern at the bubble scale. $D_{\text{eff}}$ includes contributions from the PDE's microscopic $D$, advective mixing by the velocity field, and any conversion-mediated smoothing (§9.2 explains how to measure it).

At the edge ($C = \theta_{\text{cond}}$), the azimuthally-averaged normalized gradient from the condensation field is:

$$\left.\frac{\langle|\nabla C|^2\rangle}{C^2}\right|_{\text{edge}} \approx \frac{\alpha^2 + \beta^2}{2} \cdot \frac{1-\theta_{\text{cond}}}{\theta_{\text{cond}}^2}$$

**Fixed point.** Setting $P_{\text{conv}} = P_{\text{diff}}$ at $C = \theta_{\text{cond}}$ and defining

$$q_{\mathrm{proxy,edge}} = \frac{(1+\theta_{\text{cond}})^2}{2}, \qquad q_{\mathrm{edge}} = \mathcal{M}(q_{\mathrm{proxy,edge}}) \in [0,1]$$

gives

$$\omega_0 \cdot \frac{q_{\mathrm{edge}}}{\varphi^2 + q_{\mathrm{edge}}^2} \cdot (1-q_{\mathrm{edge}}) = D_{\text{eff}} \cdot \frac{\alpha^2 + \beta^2}{2} \cdot \frac{1-\theta_{\text{cond}}}{\theta_{\text{cond}}^2}.$$

Writing $R \equiv 2D_{\text{eff}}(\alpha^2+\beta^2)/\omega_0$ gives the implicit threshold relation

$$\boxed{4\theta_{\text{cond}}^2 q_{\mathrm{edge}}(1-q_{\mathrm{edge}}) = R(1-\theta_{\text{cond}})(\varphi^2 + q_{\mathrm{edge}}^2), \qquad q_{\mathrm{edge}} = \mathcal{M}\!\left(\frac{(1+\theta_{\text{cond}})^2}{2}\right)}$$

No cubic closure or numerical $\theta_{\text{cond}}$ follows until the constitutive map $\mathcal{M}$ and $D_{\text{eff}}/\omega_0$ are supplied. The balance combines the condensation field's effective diffusion coefficient, the conversion rate $\omega_0 = \lambda = 0.1$ by convention, and the condensation field wavenumbers $\alpha = 2\pi/\Lambda_Y$, $\beta = 2\pi/\Lambda_I$.

**Selected constitutive comparison map.** If the separate map is chosen as $\mathcal{M}(s)=\sqrt{s/2}$ for $s\in[0,2]$, then $q_{\mathrm{edge}}=(1+\theta_{\mathrm{cond}})/2$, and the general balance reduces on the interior branch to

$$\boxed{\theta_{\mathrm{cond}}^2(1+\theta_{\mathrm{cond}})=R\left(\varphi^2+\frac{(1+\theta_{\mathrm{cond}})^2}{4}\right)}$$

The monotonic branch runs from $\theta_{\mathrm{cond}}=0$ at $R=0$ to $\theta_{\mathrm{cond}}=1$ at $R=2/(\varphi^2+1)\approx0.552$; the phenomenological selection $\theta_{\mathrm{cond}}=0.45$ corresponds to $R\approx0.093$. This is a map-specific benchmark, not a canonical/PDE prediction. A general $\mathcal{M}$ has no such numerical closure or universal percolation conclusion.

**The wavenumbers.** The condensation field wavelengths are set by the bubble scale: $\Lambda_Y = \ell_{285} \approx 191$ Mpc (the Cassi bubble diameter from `foundations/dimensionful-cascade.md`), $\Lambda_I = \Lambda_Y/\varphi \approx 118$ Mpc. This gives $\alpha = 2\pi/\Lambda_Y \approx 1.07 \times 10^{-24}$ m$^{-1}$, $\beta = \varphi\alpha \approx 1.73 \times 10^{-24}$ m$^{-1}$, and $\alpha^2 + \beta^2 = \alpha^2(1+\varphi^2) \approx 4.12 \times 10^{-48}$ m$^{-2}$.

**Status.** The implicit relation between $\theta_{\text{cond}}$, $R$, and $q_{\mathrm{edge}}=\mathcal{M}((1+\theta_{\text{cond}})^2/2)$ is **Derived conditional on the asserted gate form, the bounded constitutive map, and the canonical solver normalization** from the balance of gated conversion and diffusion. The geometric benchmark $\theta_{\text{cond}} = 0.45$ may be used as a phenomenological selection, but it does not determine $R$ without $\mathcal{M}$. Section 9 specifies the PDE computation to determine the map and balance inputs.

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

Evaluating the gradient anisotropy ratio requires retaining the level-set value. Along the axial direction toward a void (e.g. the Yin axis, $x=0$): $C = \cos(\beta y)$, so $|dC/dy| = \beta|\sin(\beta y)| \approx \beta\sqrt{1-C^2}$. Along the diagonal direction toward a neighboring bubble (path to the saddle at $(\Lambda_Y/4, \Lambda_I/4)$), the directional path derivative is $|dC/ds| \approx \frac{2\alpha\beta}{\sqrt{\alpha^2+\beta^2}}\sqrt{C(1-C)}$.

The ratio of edge steepnesses at the same $C = \theta_{\text{cond}}$ is:

$$\boxed{\frac{|\nabla C|_{\text{axial}}}{|\nabla C|_{\text{diag}}} = \frac{\sqrt{\alpha^2+\beta^2}}{2\alpha}\sqrt{\frac{1+C}{C}} = \frac{\sqrt{1+\varphi^2}}{2}\sqrt{\frac{1+\theta_{\text{cond}}}{\theta_{\text{cond}}}}}$$

This ratio is conditional on the selected boundary level, not a zero-parameter constant. At the phenomenological selection $\theta_{\text{cond}}=0.45$, it is $1.7072$; the void-ward (axial) edge is then $1.7072\times$ steeper than the neighbor-ward (diagonal) edge. The ratio varies with $C$ and is distinct from the bubble's $\varphi$ shape anisotropy. The fixed-step PDE diagnostic does not dynamically select or retain a $C=0.45$ edge, so this numerical evaluation is a conditional geometric-proxy value rather than a solver output.

**Physical interpretation (conditional).** At the selected boundary level $\theta_{\text{cond}}=0.45$, crossing the bubble boundary along the contracted Yin axis (toward a void) produces a $1.7072\times$ steeper drop in the constructed proxy $q_{\mathrm{proxy}}$ than crossing toward a neighboring bubble. Any corresponding $\rho$ or $G_{\text{eff}}$ gradient requires a separately supplied constitutive map; it is not determined by the geometric proxy alone. The edge is "softer" along Yang and toward neighbors; "sharper" along Yin and toward voids at this selected level.

### 2.3 The 3D Edge Shape

The geometric 3D extension assigns the bubble a bounded extent along the string axis (the cascade direction), with the chosen extent tied to the cascade-step separation. The full 3D condensation field is:

$$B_n(x, y, z) = \cos(\alpha x)\cos(\beta y) \cdot \cos(\gamma_n z), \qquad \gamma_n = \frac{2\pi}{P_\parallel^{(n)}} = \frac{2\pi}{p_\parallel(n)\ell_n}$$

where $P_\parallel^{(n)} = p_\parallel(n)\ell_n$ is the physical along-string bubble period at rung $n$, with dimensionless rung-spacing assignment $p_\parallel(n)$. The bubble edge in 3D is:

$$\{B_n(x,y,z) = \theta_{\text{cond}}\}$$

an oblate triaxial spheroid—extended in Yang, contracted in Yin, bounded along the string—with a waisted cross-section in the Yin-string plane (the anti-phase node produces the paired-sheet morphology; see `foundations/why-three-dimensions.md` §4). The axial factor and the dimensionless assignment $p_\parallel(n)$, hence the physical period $P_\parallel^{(n)}$, are Hypothesized geometric coordinate assignments; canonical density-plane conversion does not fix them.

---

## 3. Radial Interior Structure: the Ring Ladder

A rung-$n$ bubble's interior is modeled with a Hypothesized geometric doublet coordinate
$\alpha_{\mathrm{geom}} = \theta_\Psi = \pi\,u$, with
$u = \log_\varphi(r/\ell_n)$ the log-rung radial coordinate. This coordinate
is used to label a nested ladder of matter and void rings. It is distinct
from the density-plane angle $\theta_d = \operatorname{atan2}(E_I,E_Y)$;
the canonical conversion relaxes that density plane and does not supply
this radial $\theta_\Psi$ assignment. Moving radially inward from the
bubble edge, matter is assigned to the integer-coordinate radii and voids
to the half-rungs between them.

### 3.1 The boxed ring law

The radial phase of the doublet is

$$\boxed{\alpha_{\mathrm{geom}}(r) = \theta_\Psi(r) = \pi\,u, \qquad u = \log_\varphi\!\left(\frac{r}{\ell_n}\right)}$$

By construction, $\alpha_{\mathrm{geom}}$ changes by $\pi$ when $u$ changes by one. Under this separate geometric assignment, the Stokes double angle $\Theta_S = 2\theta_\Psi \pmod{2\pi}$ changes by $2\pi$ per rung; a compact spiral coordinate may be denoted $\chi$ when a named radial/spiral coordinate is needed. These fixed phase increments are Hypothesized coordinate conventions, not consequences of the canonical density-plane relaxation. The pool-cell parities (`foundations/rung-offset-mechanism.md` §4.1) assign the standing pattern's antinodes to matter and its nodes to voids: the cosine mode $\cos\bigl(\pi(u-n)\bigr)$ has antinodes at the integer rungs and zeros at the half-rungs.

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

**Tier: Hypothesized geometric coordinate assignment, conditional.** The ring law is a coordinate/lattice construction conditional on (i) the asserted geometric pitch convention $\chi(n)=\chi_0+2\pi n$ for the chosen $P=1$ convention in `foundations/spiral-dynamics.md` §1.2; (ii) the local coordinate postulate $\alpha_{\mathrm{geom}} = \theta_\Psi = \pi u$ introduced in §3.1; (iii) the pool-cell parities (`foundations/rung-offset-mechanism.md` §4.1); (iv) the
~10-rung nesting depth (below); and (v) the radial-reading inference—the
reading of the geometric doublet coordinate radially is an **inference**
resting on the nested-sub-lattice structure of `foundations/bubble-lattice-fabric.md`
§3.2, not an established identity of the canonical PDE. Item (v) is flagged
throughout.
### 3.2 Named radial spatial projection

The geometric coordinate defines a named radial spatial projection, not an
inter-rung current. Using $\rho$ as the radial weight in this phenomenological
reading:

$$J_{\Psi,r} \equiv J_r = \rho\,\partial_r\alpha_{\mathrm{geom}} = \frac{\rho\,\pi}{r\ln\varphi}, \qquad
\int_{\ell_{n-1}}^{\ell_n} J_{\Psi,r}\,dr = \rho\pi$$

per rung shell. This integral records geometric phase-coordinate accumulation
within a shell. It does not establish transport between cascade scales. A
separate constitutive map would be required to relate $J_{\Psi,r}$, or a
density-plane spatial projection $J_{d,r}$ built from $\theta_d$, to an
inter-rung flux. The canonical conversion supplies no such map; its rank-one
relaxation remains local in the density plane.

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
$n$-independent under this geometric radial assignment: $N(R) = -\log_\varphi R$ over a radial
span $[R\ell_n, \ell_n]$ depends only on the fraction $R$, not on $\ell_n$.

**Verdict: Hypothesized geometric reduction / REDUCES.** The cascade connection—each ring
is a rung-$(n-k)$ condensate, the ladder realizes the nested sub-lattice
radially—is a reduction claim, and it inherits the radial-reading flag (the
identification of interior rings with nested condensates rests on the
inference of §3.1); it does not close the physics of shell interiors on its
own, and it is not derived by canonical conversion.

### 3.4 The φ-ellipse of each ring

Under the geometric scale assignment described in `foundations/bubble-lattice-fabric.md` §2, each rung-$(n-k)$ condensate is assigned the same functional condensation proxy after the required parameter/unit re-normalization, with wavelengths scaled to $\ell_{n-k}$; its Yang-Yin cross-section is
therefore a φ-ellipse with the same axis ratio

$$\frac{a_X}{a_Y} = \varphi$$

as the parent (§2.1). **Flag as inference:** the φ-ellipticity of each ring
inherits the radial-reading inference of §3.1—it is the geometric scale assignment
applied to the nested rings, not an independent derived shape.

### 3.5 Negative control: the naive wake-sum is not the ladder

The naive one-dimensional wake-sum that a beat picture would propose for the
intra-shell ridges,

$$f(r) = \cos\!\left(\frac{2\pi r}{\ell_n}\right) +
\cos\!\left(\frac{2\pi\varphi r}{\ell_n}\right),$$

has zeros at $r \approx \{0.191,\,0.573,\,0.809,\,0.955\}\,\ell_n$ (bisection;
verified by `two-fluid/run_bubble_ring_probe.py` Leg B). These are **not** the
matter-ring positions $\{\ell_n, \ell_n\varphi^{-1}, \ell_n\varphi^{-2},
\ell_n\varphi^{-3}\} = \{1,\,0.618,\,0.382,\,0.236\}\,\ell_n$: $0.382$ and
$0.809$ are **not** zeros of the wake-sum, and none of the four zeros lands on
a $\varphi$-ladder position. The intra-shell ladder is imposed by the
Hypothesized geometric phase coordinate (§3.1). Ordinary wake beating produces additive spacing in $r$; the multiplicative $\varphi$ ratios require the supplied log-radius coordinate.

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
  ($d^2E = c^2\nabla^2 E - \omega_{0,\mathrm{wave}}^2(E_Y-\varphi E_I)$) is not present in
  this solver—it belongs to the space-sim GLSL PDE. The recorded first-order null
  does not test that form. The tested undriven second-order readback in the
  owner's space sim (Godot, $N = 128$, $\omega_0^2 = 20$, featureless
  filled-ball seed, no source drive) also shows no persistent ladder—a
  transient shell with one interior ridge at ratio 0.545 (marginal
  $\varphi^{-1}$) at $t = 24$, dissipated by $t = 40$, detector self-test
  PASS (probe `diag_bubble_rings.gd` in the owner's space-sim repo). The
  registered ~10-ring dynamical realization is therefore `REJECT` on the
  tested first-order solver and undriven space-sim wave form. The geometric coordinate law remains Hypothesized and requires a new preregistration before another mechanism can change that verdict.

**Rejected emergence test:** a simulated bubble was required to show ~10
matter ridges at $r_k = \ell_n\,\varphi^{-k}$ (successive matter-ring ratio
$\varphi^{-1}=0.6180$, distinct from the interleaved-ridge ratio
$\varphi^{-1/2}=0.7862$), interleaved with 9 void troughs at
$\ell_n\,\varphi^{-(k+\frac12)}$, with strict matter/void alternation and an
$n$-independent count. The tested canonical and undriven second-order arms do
not meet this contract. Cataloged as Prediction 51
(`predictions/falsifiable-predictions.md`).

### 3.7 Driven second-order phase layers do not supply the ring ladder

The default CassiCosmos second-order wave branch separates into a massless
density channel and an imbalance channel with propagation threshold

$$
\Omega_g=\varphi\omega_{0,\mathrm{wave}}.
$$

A supplied harmonic drive at

$$
\Omega_*=\varphi^{3/2}\omega_{0,\mathrm{wave}}
$$

makes the two propagating wavenumbers satisfy
$k_\rho/k_\epsilon=\varphi$. The frozen propagating fits produce
phase-staggered layers with additive spacing
$2\pi/|k_\rho-k_\epsilon|$; the generic-frequency control gives ratio
$1.311855471$. The independent lock-in closure verifies sub-gap attenuation
$3.067\times10^{-6}$ and tuned ratio $1.618096626$. The current live source
path has no harmonic selector for $\Omega_*$.

These driven layers do not have radii
$r_k=\ell_n\varphi^{-k}$. Their additive spacing therefore leaves Prediction
51 `REJECT`. Uniform phase staggering also leaves the declared nearest-neighbor
chain gapless. A separate coupling-magnitude modulation opens the tested unit
gap and suppresses 12-cell transmission to $4.738\times10^{-6}$, establishing
only a conditional node-to-link mechanism. The PDE does not derive that map.
See `field-experience/phase-staggered-scale-gap-report.md`.

---

## 4. Influence of Neighbors and Voids

### 4.1 Diagonal Neighbors: Saddle Deformation

The nearest neighbor to a bubble is a diagonal neighbor at distance $d_{\text{diag}} = \sqrt{\Lambda_Y^2 + \Lambda_I^2}/2$. The saddle between them sits at $(\Lambda_Y/4, \Lambda_I/4)$ where $C = 0$.

The neighbor's presence deforms the edge through the global structure of $C$—not through a dynamical interaction, but because the bubble boundary IS the level set of $C$, and $C$ already includes the neighbor's contribution.

The deformation is: the boundary contour is **flattened** toward the diagonal neighbor compared to the isolated elliptical approximation. The flattening is small when $\theta_{\text{cond}} \gg 0$ (bubbles are deep within their own potential wells) and large as $\theta_{\text{cond}} \to 0$.

The saddle barrier height from bubble center to saddle is $1$ in $C$-units. In the constructed proxy reading: $q_{\mathrm{proxy,center}} = 2$, $q_{\mathrm{proxy,saddle}} = 0.5$, and $q_{\mathrm{proxy,edge}} = (1+\theta_{\text{cond}})^2/2 = 1.05125$ for the phenomenological selection $\theta_{\text{cond}} = 0.45$. The raw proxy barrier from edge to saddle is $\Delta q_{\mathrm{proxy}} = 1.05125 - 0.5 = 0.55125$; a canonical Qi barrier requires the separate bounded map $\mathcal{M}$.

### 4.2 Axial Voids: Full Barrier

Between a bubble and its axial neighbor (along Yang at $(\Lambda_Y, 0)$ or along Yin at $(0, \Lambda_I)$), there is a void at the midpoint where $C = -1$ and $q_{\mathrm{proxy}} = 0$. These axial neighbors **never merge** in the geometric proxy—the path between them goes through $C = -1$ (a minimum), not through a saddle. The void is an absolute barrier to geometric connectivity; whether a physical $J_{\Psi}$ or $J_d$ crosses it requires a separate constitutive transport map.

Each bubble is geometrically connected only to its 4 diagonal neighbors, not its 4 axial neighbors. The lattice degree is 8 geometric but 4 connectable—a structural prediction of the chord geometry.

### 4.3 Void Influence on Edge Steepness

The void at $C = -1$ sits in the axial direction. Moving from the bubble center toward an axial void, $C$ drops from $1$ to $-1$—a steeper gradient than toward a diagonal saddle (which only drops to $0$). This means:

- **Axial edge** (facing a void): sharper transition and steeper $q_{\mathrm{proxy}}$ gradient; any more abrupt drop in $\rho$ or $G_{\text{eff}}$ is conditional on a constitutive map
- **Diagonal edge** (facing a neighbor): gentler transition and shallower $q_{\mathrm{proxy}}$ gradient; any gradual $\rho$ or $G_{\text{eff}}$ change is likewise conditional

The quantitative ratio at the selected boundary level is $\frac{\sqrt{1+\varphi^2}}{2}\sqrt{\frac{1+\theta_{\text{cond}}}{\theta_{\text{cond}}}} \approx 1.7072$ for $\theta_{\text{cond}}=0.45$ (§2.2).

---

## 5. Conditional Physical Readings at the Edge

### 5.1 Condensation Proxy $q_{\mathrm{proxy}}(C)$

$$q_{\mathrm{proxy}}(C) = \frac{(1 + C)^2}{2}$$

This is the constructed geometric intensity proxy, not an identity for the canonical or measured solver Qi field. At the phenomenological selection $\theta_{\text{cond}} = 0.45$, $q_{\mathrm{proxy,edge}} = 1.05125$; at the saddle ($C = 0$), $q_{\mathrm{proxy,saddle}} = 0.5$; and in the void ($C = -1$), $q_{\mathrm{proxy,void}} = 0$. The bounded canonical reading is

$$q_{\mathrm{solver}}(C) = \mathcal{M}\!\left(q_{\mathrm{proxy}}(C)\right), \qquad \mathcal{M}:[0,2]\to[0,1],$$

and its values require a separately supplied constitutive map.

### 5.2 Conditional Effective Gravitational Constant

If separate constitutive maps supply $\rho(C)$ and $\mathcal{M}$, the application-level Qi-gravity ansatz reads

$$G_{\text{eff}}(C) = \frac{\pi}{\rho(C)} \bigl(1 + (\varphi^{6}-1)q_{\mathrm{solver}}(C)\bigr), \qquad q_{\mathrm{solver}}(C)=\mathcal{M}\!\left(\frac{(1+C)^2}{2}\right), \qquad \xi = \varphi^6 \approx 17.944.$$

At the bubble center, edge, and void, the canonical Qi inputs are respectively $\mathcal{M}(2)$, $\mathcal{M}(1.05125)$, and $\mathcal{M}(0)$ for the phenomenological selection $\theta_{\text{cond}}=0.45$. The corresponding $G_{\text{eff}}$ coefficients therefore remain conditional on the supplied map and density profile; the geometric proxy alone supplies no numerical amplified-to-unamplified gravity profile. Directional steepness depends on the geometric $C$ gradient and on the separately supplied constitutive maps.

### 5.3 Conditional Density Profile

A separate constitutive density map may be parameterized phenomenologically as

$$\rho(C) \approx \rho_0 \cdot \max\!\left(0,\; \frac{C - \theta_{\text{cond}}}{1 - \theta_{\text{cond}}}\right)^{n_{\text{cond}}}$$

with $n_{\text{cond}} \approx 1$ (linear condensation) to $n_{\text{cond}} \approx 2$ (quadratic, from the catalytic template mechanism in `foundations/why-three-dimensions.md` §3.3). The exact exponent is a target for PDE computation. This profile is not derived by the geometric proxy; Section 9.4 specifies the measurement protocol that can test the constitutive ansatz.

---

## 6. Observable Signatures

### 6.1 CMB Boundary Imprint

The bubble edge at $z \approx 19$ (Qi gate engagement, the "pinch") supplies a geometric $q_{\mathrm{proxy}}$ gradient with $\varphi$-asymmetric steepness. A CMB imprint or a physical $G_{\text{eff}}$ gradient requires a separately supplied constitutive map from this proxy to the solver's Qi, density, and gravity variables; the geometric proxy alone does not derive either consequence. Conditional on that map, the gradient produces:

- A scale-dependent preferred axis at $\ell < 5$ that fades at smaller scales (super-horizon boundary)
- The $12.2^\circ$ alignment angle between the CMB dipole (Yang axis) and the quadrupole-octopole axis (bubble boundary normal)—measured, calibrated from the data vectors; the bubble-boundary mechanism is a candidate whose orientation is fitted to the measured axis (Hypothesized; `foundations/refined-numeric-predictions.md` §2.3)

### 6.2 Void Ellipticity Prediction

Conditional on the constitutive map and catalog selection, the geometric gradient reading manifests as:

- Voids are more elongated along Yang (the softer proxy edge allows structure to extend further before dropping below threshold)
- Voids are more sharply truncated along Yin (the steeper proxy edge cuts off abruptly)
- The $\varphi$-shape reading (ratio of Yang-extent to Yin-extent at the density threshold tracking $\varphi$) is a separate observable from the conditional $1.7072$ gradient ratio at $\theta_{\text{cond}}=0.45$—a shape measurement cannot by itself test the gradient ratio

**Measured 2026-08-07** (VAST/ZOBOV SDSS DR7 + NSA volume-limited tracers, 130 voids, $R_{\text{eff}} \ge 15\,h^{-1}$Mpc): the conditional $1.7072$ gradient ratio at $\theta_{\text{cond}}=0.45$ does not appear in the data—$\hat\mu = 1.005 \pm 0.221$ (99% CI [0.584, 1.753], $p_{\text{pred}} = 0.008$), NULL per the pre-registered decision tree; the T3 control fails (RSD quadrupole), so the primary is systematics-limited, and the RSD-free 2D transverse control is also NULL. The measured void shape $\varepsilon = 1 - c/a = 0.225 \pm 0.066$ (99% CI [0.210, 0.240]) excludes both the $\varphi$-shape reading 0.382 and the literal 1.70-as-shape reading 0.412. Catalog record: `predictions/falsifiable-predictions.md` §3.

The gradient anisotropy ratio and the shape ratio are two distinct predictions from the same condensation field: the bubble is $\varphi$-elliptical in shape, while the edge ratio is conditional on $C=\theta_{\text{cond}}$ and equals $1.7072$ only at $\theta_{\text{cond}}=0.45$. On the DR7 sample the conditional gradient ratio is null and the $\varphi$-shape reading is excluded by the measured shape ellipticity.

### 6.3 Absolute Lattice Scales

The condensation field wavelengths are set by the cascade. From `foundations/dimensionful-cascade.md`, the Cassi bubble at step 285 gives:

$$\Lambda_Y = \ell_{285} \approx 191\ \text{Mpc}, \qquad \Lambda_I = \frac{\Lambda_Y}{\varphi} \approx 118\ \text{Mpc}$$

These are the fundamental spatial periods of the chord lattice: $\Lambda_Y$ is the bubble-to-bubble spacing along Yang, $\Lambda_I/2$ is the string-to-string spacing along Yin, and the stagger is $\Lambda_Y/2$. The along-string period at rung $n$ is $P_\parallel^{(n)} = p_\parallel(n)\ell_n$, a Hypothesized geometric coordinate assignment tied to the chosen cascade-step spacing; its dimensionless value remains open as summarized in `foundations/bubble-lattice-fabric.md` §2.3. The transverse periods are fixed by the cascade table, while canonical density-plane conversion does not determine the axial period.

### 6.4 Galaxy Distribution at the Edge

Galaxies trace the condensation field. The edge region—where $C$ drops from $\theta_{\text{cond}}$ to $0$—should show:

- A conditional application-level transition from spiral-dominated (high-$q_{\mathrm{proxy}}$, organized rotation) to diffuse/dwarf-dominated (low-$q_{\mathrm{proxy}}$, weak gravity); the rotation and gravity readings require separate constitutive maps
- The transition distance is $\sim \Lambda_I \cdot \sqrt{1-\theta_{\text{cond}}}$ along Yin and $\sim \Lambda_Y \cdot \sqrt{1-\theta_{\text{cond}}}$ along Yang—an anisotropic "coastal shelf"

---

## 7. Open Derivations

1. **$D_{\text{eff}}/\omega_0$ and the proxy-to-solver map from the PDE.** The dimensionless parameter $R = 2 D_{\text{eff}}(\alpha^2+\beta^2)/\omega_0$ enters the implicit threshold relation through $q_{\mathrm{edge}}=\mathcal{M}((1+\theta_{\text{cond}})^2/2)$. $\omega_0 = \lambda = 0.1$ and $\alpha^2+\beta^2$ are known (§1.2). $D_{\text{eff}}$ is the effective diffusion coefficient of the coarse-grained condensation field $C(x,y)$ at the bubble scale—distinct from a microscopic PDE input parameter. It must be **measured** from the PDE by seeding the $C$ pattern and observing its decay rate (§9.2). The bounded constitutive map $\mathcal{M}$ must be measured alongside the solver response (§9.3). A phenomenological $\theta_{\text{cond}}=0.45$ can be compared with the resulting implicit balance only after both inputs are available.

2. **Condensation exponent $n_{\text{cond}}$ (§5.3).** The power-law exponent in the conditional constitutive map governing how rapidly $\rho$ drops at the edge. It is observable in void density profiles and testable with the PDE as described in §9.4.

3. **Neighbor coupling strength.** The raw proxy barrier from edge to saddle is $\Delta q_{\mathrm{proxy}} = 0.55125$ for the phenomenological selection $\theta_{\text{cond}}=0.45$. Whether a corresponding bounded canonical Qi barrier is surmountable for physical Qi transport (coherence tunneling through the saddle) is a separate question from geometric connectivity—the chord connectivity docs correctly label it as Speculative.

---

## 8. Epistemic Boundaries

### Derived geometric quantities; conditional application relations

- Bubble shape: triaxial spheroid with axis ratio $\varphi$ in the Yang-Yin plane
- Lattice geometry: staggered checkerboard, $m+n$ even = bubble, odd = void
- Anisotropic edge steepness ratio: $\frac{\sqrt{1+\varphi^2}}{2}\sqrt{\frac{1+\theta_{\text{cond}}}{\theta_{\text{cond}}}}$, which is $1.7072$ only at the selected $\theta_{\text{cond}}=0.45$ (conditional geometric proxy prediction)
- Connectable degree: 4 (diagonal only—axial paths blocked by $C=-1$ voids)
- Functional form for $\theta_{\text{cond}}$: $4\theta_{\text{cond}}^2 q_{\mathrm{edge}}(1-q_{\mathrm{edge}}) = R(1-\theta_{\text{cond}})(\varphi^2 + q_{\mathrm{edge}}^2)$ with $q_{\mathrm{edge}}=\mathcal{M}((1+\theta_{\text{cond}})^2/2)$, from the conditional conversion-diffusion balance
- Constructed condensation proxy: $q_{\mathrm{proxy}}(C) = (1+C)^2/2$ with bounded canonical reading $q_{\mathrm{solver}}=\mathcal{M}(q_{\mathrm{proxy}})$
- Absolute scales: $\Lambda_Y = \ell_{285}$, $\Lambda_I = \Lambda_Y/\varphi$ from the cascade table
- Conditional $G_{\text{eff}}(C)$ profile from $\xi = \varphi^6$, requiring separately supplied constitutive maps for $\mathcal{M}$ and $\rho(C)$

### Hypothesized coordinate assignments and constitutive maps

- The axial factor $\cos(\gamma_n z)$, the dimensionless assignment $p_\parallel(n)$ (and hence $P_\parallel^{(n)}$), and the full 3D product $B_n(x,y,z)$
- The radial ring ladder and its $\alpha_{\mathrm{geom}} = \theta_\Psi = \pi u$ coordinate reading
- Numerical value of $\theta_{\text{cond}}$ (requires $D_{\text{eff}}$ from PDE; the functional form is conditional on the asserted gate)
- The condensation exponent $n_{\text{cond}}$ and the resulting edge density profile, pending constitutive-map measurement

### Speculative (constitutive coherence transport)

- Qi tunneling through inter-bubble saddles, or any identification of $J_{\Psi}$ or $J_d$ with inter-rung transport without a separate constitutive map

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

   **Measurement boundary:** the seeded run can measure the decay or growth rate of the constructed $C_{\mathrm{proxy}}$ pattern. Interpreting that rate as $D_{\text{eff}}$ requires separating advection, conversion, and the supplied proxy-to-solver map; the canonical local relaxation does not by itself provide a diffusion law for $C_{\mathrm{proxy}}$.

2. **Run parameters**:

   | Parameter | Value | Rationale |
   |---|---|---|
   | Grid | $64 \times 64 \times 4$ | 2D slice + thin z (minimal, only for 3D operator) |
   | `D` | 0.0 | Canonical default (conservation-exact, 44); D>0 = diffusion-bound |
   | `lam` | 0.1 | Canonical solver normalization/timescale convention; the relation $\lambda = 1/(2w)$ with $w=5$ is Hypothesized and requires independent cycle-time/dynamical closure |
   | `qi_gate` | True | Qi gate active (defines measured solver $q_{\mathrm{solver}}$ from fields; it is not the constructed $q_{\mathrm{proxy}}(C)$) |
   | `chi` | 0.0 | No chemotaxis (isolate pure reaction-diffusion) |
   | `hubble_mode` | 'conversion' | Standard expansion |
   | `a0` | 0.2 | Start near bubble epoch |
   | `max_H` | 0.5 | Safety cap |
   | `dt` | 0.001 | Standard CFL-limited timestep |
   | Steps | 10,000 | Sufficient for several e-folds of evolution |

3. **Monitor** measured $q_{\mathrm{solver,center}}(t)$ and independently constructed $C_{\mathrm{proxy,center}}(t)$ at the bubble center $(x,y) = (0,0)$. The constructed $C_{\mathrm{proxy}}$ pattern amplitude evolves as:

   $$C_{\text{center}}(t) \approx C_0 \cdot \exp\left(-\Gamma_{\text{eff}} \, t\right)$$

   where $\Gamma_{\text{eff}} = D_{\text{eff}}(\alpha^2+\beta^2)$ is the effective damping rate of the condensation field. Extract $\Gamma_{\text{eff}}$ by fitting an exponential to $C_{\text{center}}(t)$ over the linear regime.

4. **Compute $D_{\text{eff}}$**:

   $$D_{\text{eff}} = \frac{\Gamma_{\text{eff}}}{\alpha^2 + \beta^2}$$

   where $\alpha, \beta$ are in code units (radians per grid length).

5. **Compute $R$**:

   $$R = \frac{2 D_{\text{eff}}(\alpha^2+\beta^2)}{\omega_0} = \frac{2 \Gamma_{\text{eff}}}{\omega_0}$$

   where $\omega_0 = \text{lam}$ in code units. **Crucially**, $R$ is independent of the unit mapping—it falls directly out of the measured damping rate.

6. **Apply the implicit threshold relation only after measuring $\mathcal{M}$.** Use

   $$4\theta_{\text{cond}}^2 q_{\mathrm{edge}}(1-q_{\mathrm{edge}}) = R(1-\theta_{\text{cond}})(\varphi^2 + q_{\mathrm{edge}}^2), \qquad q_{\mathrm{edge}}=\mathcal{M}\!\left(\frac{(1+\theta_{\text{cond}})^2}{2}\right).$$

   This is not a cubic in $\theta_{\text{cond}}$ until a specific constitutive map $\mathcal{M}$ is supplied. With that map fixed, solve the implicit relation numerically and compare the result with the phenomenological selection $\theta_{\text{cond}}=0.45$.

#### Method B: Emergent pattern (cross-check)

As a cross-check, run from random initial conditions (`initial_amplitude=0.2`) on a $128^2 \times 64$ grid with the same parameters above (but `chi=5.0` to allow gravitational assembly). The `chi=5.0` gravity channel drives the wake-wave pattern out of the random initial conditions—assembly is the driver, not spontaneous emergence (`two-fluid/run_bubble_ring_dynamic_probe.py`: the canonical first-order solver forms no radial structure from no-drive seeds). After the system reaches quasi-steady structure ($\sim$5,000 steps), extract:

- The dominant condensation wavelength $\Lambda_Y^{(m)}$ from the Fourier power spectrum $P(k_x, k_y)$ of measured solver $q_{\mathrm{solver}}(x,y)$.
- The measured $\theta_{\text{cond}}^{(m)}$ from the $q_{\mathrm{solver}}(C_{\mathrm{proxy}})$ scatter plot (§9.3).
- Compare the measured map and threshold with Method A's implicit balance, if the constitutive map and the measured $D_{\text{eff}}$ support that comparison.

### 9.3 Direct Extraction of $\theta_{\text{cond}}$ from $q_{\mathrm{solver}}(C_{\mathrm{proxy}})$

Independently of Method A, $\theta_{\text{cond}}$ can be measured directly from a fully-developed bubble simulation:

1. Run the expanding PDE as in Method B above, $128 \times 128 \times 64$ grid, with `qi_gate=True`, standard parameters.
2. At each diagnostic step (every 200 steps), extract the measured 2D $q_{\mathrm{solver}}(x,y)$ field from the Qi gate diagnostic and construct $C_{\mathrm{proxy}}(x,y)$ independently from the analytic condensation field and known coordinates. Do not compute $C_{\mathrm{proxy}} = 2q_{\mathrm{solver}} - 1$: that equality is the paper's proxy ansatz, not a canonical solver identity.
3. Construct the **$q_{\mathrm{solver}}(C_{\mathrm{proxy}})$ scatter plot**: for each grid cell in the Yang-Yin midplane ($z \approx 0$), add a point $(C_{\mathrm{proxy},i}, q_{\mathrm{solver},i})$.
4. Conditional on the supplied constitutive map and on an observed monotone transition, the scatter can locate the geometric threshold by relating $C_{\mathrm{proxy}}$ to the measured bounded $q_{\mathrm{solver}}$; the canonical relaxation does not require a sigmoid or a universal S-curve.
5. If the measured relation has a resolved midpoint, fit the threshold as the $C_{\mathrm{proxy}}$-value where $q_{\mathrm{solver}}$ crosses a declared midpoint. A sigmoid fit is an optional empirical parameterization:

   $$q_{\mathrm{solver}}(C_{\mathrm{proxy}}) = \frac{1}{1 + \exp(-(C_{\mathrm{proxy}} - \theta_{\text{cond}})/\sigma)}$$

   and $\theta_{\text{cond}}$ is then the fitted midpoint.

**Consistency check:** Compare any direct threshold fit with the implicit balance from Method A only after the same constitutive map $\mathcal{M}$ and solver normalization have been supplied. A discrepancy then identifies additional dynamics or map mismatch; no universal percentage criterion follows from the canonical conversion alone.


### 9.4 Measurement of the Condensation Exponent $n_{\text{cond}}$

The density profile exponent $n_{\text{cond}}$ parameterizes a conditional constitutive map for how $\rho$ drops from $\rho_0$ inside the bubble to $\rho \to 0$ outside:

$$\rho(C_{\mathrm{proxy}}) \approx \rho_0 \cdot \max\!\left(0,\; \frac{C_{\mathrm{proxy}} - \theta_{\text{cond}}}{1 - \theta_{\text{cond}}}\right)^{n_{\text{cond}}}$$

**Measurement protocol:**

1. From the same simulation as §9.3, extract radial profiles of measured $\rho(r)$ along both axial directions ($x=0$ toward void, $y=0$ toward void). Use a wedge average of $\pm 10^\circ$ around each direction to reduce noise.
2. Construct $C_{\mathrm{proxy}}(r)$ from the analytic condensation field: $C_{\mathrm{proxy}}(r) = \cos(\alpha r)$ along the Yang axis or $C_{\mathrm{proxy}}(r) = \cos(\beta r)$ along the Yin axis.
3. For grid cells with $C_{\mathrm{proxy}} > \theta_{\text{cond}}$, fit:

   $$\log \rho = \log \rho_0 + n_{\text{cond}} \cdot \log\!\left(\frac{C_{\mathrm{proxy}} - \theta_{\text{cond}}}{1 - \theta_{\text{cond}}}\right)$$

   using $\theta_{\text{cond}}$ from §9.2/§9.3. The slope is the conditional-map exponent $n_{\text{cond}}$.
4. Report $n_{\text{cond}}$ with bootstrap uncertainty from the fit residuals.

**Anisotropy check:** The fit should be performed separately for the Yang and Yin axial directions. If $n_{\text{cond}}$ differs measurably between the two, the geometric proxy alone does not determine the density profile—additional direction-dependent physics (e.g., velocity shear anisotropy) is active. A difference > 0.2 warrants investigation.

### 9.5 Parameter Summary and Cross-Checks

| Parameter | Method | Output | Status after computation |
|---|---|---|---|
| $D_{\text{eff}}$ | Pattern decay (§9.2 Method A) | Effective diffusion coefficient | Derived from measured solver decay |
| $\theta_{\text{cond}}$ | Solved from the implicit relation in §9.2 step 6 after supplying $\mathcal{M}$ | Conditional geometric threshold | Derived conditional on the asserted gate, constitutive map, and solver normalization |
| $\theta_{\text{cond}}$ | Direct fit from measured $q_{\mathrm{solver}}(C_{\mathrm{proxy}})$ relation (§9.3) | Cross-check threshold | Empirical conditional on the observed map |
| $n_{\text{cond}}$ | Log-log fit of $\rho(C_{\mathrm{proxy}})$ (§9.4) | Conditional density exponent | Hypothesized; fit required |
| $R$ | From $2\Gamma_{\text{eff}}/\omega_0$ | Dimensionless balance ratio, conditional on the supplied solver normalization | Derived conditional |

**Scaling test:** Repeat Method A at 2-3 grid resolutions ($N=48, 64, 96$) with the same physical box size to verify that $D_{\text{eff}}$ converges. Advection-induced eddy diffusivity should be resolution-independent in the resolved range; microscopic $D$ dominates at low resolution. The converged value is the physical $D_{\text{eff}}$.

### 9.6 Analytical Bounds

Even before the PDE computation, tight bounds can be placed on both parameters from existing theory.

#### Bounds on $\theta_{\text{cond}}$

The phenomenologically selected $\theta_{\text{cond}} = 0.45$ remains a geometric benchmark. It does not determine $R$ without the bounded map $\mathcal{M}$, and the canonical conversion supplies no independent lower or upper bound on $\theta_{\text{cond}}$ or $R$.

The geometric connectivity and density readings can still be used as conditional application checks:

- A lower-threshold selection near the saddle would alter the constructed geometric edge placement and must be checked against the diagonal-connectivity reading.
- A high-threshold selection would alter the conditional density contrast through the supplied $\rho(C)$ map and must be checked against the observed cosmic-web contrast.
- Neither check is a canonical transport theorem, and neither yields a numerical bound on $R$ before $\mathcal{M}$ and $D_{\text{eff}}$ are measured.

The canonical default $\lambda = 0.1$ remains a solver normalization/timescale convention; the relation $\lambda = 1/(2w)$ with $w=5$ remains Hypothesized. The D=0 default remains the conservation-exact setting, while D>0 is a diffusion-bound reading. A bare $D=0.001$ estimate can be reported as an input-scale diagnostic, but it does not predict $\theta_{\text{cond}}$ without the constitutive map and a measured effective damping.

**Testable comparison:** the PDE measurement will report the measured map $\mathcal{M}$, $D_{\text{eff}}$, and any compatible $\theta_{\text{cond}}$ rather than selecting one of three canonical $R$ regimes. The ranges $0.1$–$0.3$, $0.3$–$0.6$, and $0.6$–$0.7$ remain phenomenological labels for thin-skinned, mid-range, and nearly-filling geometric readings only; they carry no inferred $R$ intervals.

#### Bounds on $n_{\text{cond}}$

**Phenomenological working range:** $n_{\text{cond}} \in [1.0, 2.0]$, with best guess $n_{\text{cond}} \approx 1.5$. These labels parameterize the conditional density-map family and remain to be fitted; the squared proxy assignment and canonical local relaxation do not derive the range.

The PDE measurement will determine whether the selected constitutive profile is compatible with the measured density field.



### 9.7 Supplementary Physical Interpretations

Once $\theta_{\text{cond}}$ and $n_{\text{cond}}$ are determined and the required constitutive maps are supplied, several conditional proxy/application readings follow:

| Conditional proxy/application quantity | Formula | Example ($\theta_{\text{cond}}=0.45$, $n_{\text{cond}}=1.5$) |
|:---|:---|:---|
| Edge $q_{\mathrm{proxy}}$ | $q_{\mathrm{proxy,edge}} = (1+\theta_{\text{cond}})^2/2$ | $1.05125$ |
| Edge canonical input | $q_{\mathrm{solver,edge}}$ | $\mathcal{M}(1.05125)$; no numerical value before the map is supplied |
| Midpoint density ($C_{\mathrm{proxy}}=0$, saddle) | $\rho_{\text{saddle}}/\rho_0$ | $0$ under the displayed conditional density-map ansatz |
| Density at $C_{\mathrm{proxy}} = \theta_{\text{cond}}/2$ | $\rho/\rho_0 = \max\!\left(0,\; \frac{\theta_{\text{cond}}/2 - \theta_{\text{cond}}}{1-\theta_{\text{cond}}}\right)^{n_{\mathrm{cond}}}$ | $0$ under the displayed conditional density-map ansatz |
| Advective enhancement | $D_{\text{eff}}/D$ | To be measured; no value follows from the phenomenological $\theta_{\text{cond}}$ |
| Edge width (Yin) | $\Delta r_{\text{Yin}} = \Lambda_I \cdot \sqrt{1-\theta_{\text{cond}}}$ | $118 \times \sqrt{0.55} \approx 87$ Mpc |
| Edge width (Yang) | $\Delta r_{\text{Yang}} = \Lambda_Y \cdot \sqrt{1-\theta_{\text{cond}}}$ | $191 \times \sqrt{0.55} \approx 142$ Mpc |
| $G_{\text{eff}}$ ratio (center/edge) | $\dfrac{\rho_{\text{edge}}}{\rho_0}\dfrac{1+(\varphi^6-1)\mathcal{M}(1.05125)}{1+(\varphi^6-1)\mathcal{M}(2)}$ | Conditional on $\mathcal{M}$ and $\rho(C)$; no numerical ratio before both maps are supplied |
| $G_{\text{eff}}$ ratio (edge/void) | $\dfrac{\rho_{\text{void}}}{\rho_{\text{edge}}}\dfrac{1+(\varphi^6-1)\mathcal{M}(0)}{1+(\varphi^6-1)\mathcal{M}(1.05125)}$ | Conditional on $\mathcal{M}$ and $\rho(C)$; no numerical ratio before both maps are supplied |

---

## 10. The Lattice at Other Scales

The rung-indexed condensation field $B_n(x,y,z)$ and its checkerboard lattice are not specific to the cosmological scale of step 285. The same functional form may be assigned at other rungs with the conditional wavelength and parameter/unit re-normalization described in `foundations/bubble-lattice-fabric.md` §2. This geometric assignment does not establish an identical physical field at every rung or a current transported between rungs.

---

## References
- `visual-explainers/chord_lattice.py`—condensation field, staggered lattice, bubble shape derivation
- `visual-explainers/chord_connectivity.py`—percolation analysis, saddle barriers
- `visual-explainers/chord_side_on.py`—3D bubble shape, waisted lobe-pairs, string threading
- `foundations/why-three-dimensions.md`—three dimensions from the spiral's Frenet-Serret frame, triaxial spheroid, anti-phase selection
- `foundations/wake-geometry.md`—wake beat envelope, staggered checkerboard placement, closure ladder
- `foundations/wu-xing-derivation.md`—$w = 5$ derived conditional under the selected construction; the physical organizing cycle and five-channel application remain Hypothesized (all bubbles identical)
- `foundations/dimensionful-cascade.md`—Cassi bubble at step 285, 191 Mpc
- `foundations/spiral-dynamics.md`—the geometric spiral coordinate, $c(r)$ profile, and wave-speed application; $H \propto (1-q)$
- `foundations/cassi-first-principles.md`—Qi gate $g(q) = q/(\varphi^2+q^2)$, conversion dynamics
- `foundations/string-bubble-projective-map.md`—affine $\mathbb{CP}^1$ realization of the selected quadratic shell, its pullback metric, and the induced phase and conversion flows
- `consciousness/consciousness-from-phi.md` §3—two-bubble correlation test
- `visual-explainers/string_bubble_cascade.py`—3D damped-wave two-fluid PDE: string → pinch → spheroid → cascade
- `two-fluid/cassi_two_fluid_3d_gpu.py`—PDE solver, $D$, $\lambda$, Qi gate implementation
- `foundations/bubble-lattice-fabric.md`—universal condensation geometry, with axial/radial coordinate assignments treated as Hypothesized
- `foundations/spin-fibonacci-spiral.md`—the geometric doublet phase convention used in the radial ring assignment
- `foundations/rung-offset-mechanism.md`—pool-cell parities: cosine antinodes at integer rungs, sine antinodes at half-rungs
- `two-fluid/run_bubble_ring_probe.py`—ring-ladder probe (Prediction 51): analytic ring law, recorded negative result, radial envelope
- `two-fluid/run_bubble_ring_dynamic_probe.py`—ring-ladder dynamic-realization probe (Prediction 51): four spatial-coupling arms A/B/C/W, NO RINGS on all arms to $t=40$
- `predictions/falsifiable-predictions.md`—Prediction 51 (bubble-shell ring ladder)
- `field-experience/phase-staggered-scale-gap-report.md`—additive driven layers, imbalance threshold, source-selection null, phase-only gap null, and conditional link-modulated gap
