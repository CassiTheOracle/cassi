# The Bubble Lattice: Universal Organizing Geometry at Every Cascade Rung

## Status: Derived transverse geometry; Hypothesized axial/radial coordinate assignments—August 2026

## Abstract

The condensation field

$$\boxed{B(x, y, z) = \cos(\alpha x)\cos(\beta y)\cos(\gamma_n z), \qquad \alpha = \frac{2\pi}{\Lambda_Y},\;\; \beta = \frac{2\pi}{\Lambda_I} = \varphi\alpha,\;\; \gamma_n = \frac{2\pi}{P_\parallel^{(n)}} = \frac{2\pi}{p_\parallel(n)\ell_n}}$$

uses the displayed $B(x,y,z)$ as a geometric organizing ansatz. Its transverse factors and checkerboard interpretation are structural geometric results; the axial factor $\cos(\gamma_n z)$ with inverse-length wave number $\gamma_n$, the dimensionless rung count $p_\parallel(n)$, the physical along-string period $P_\parallel^{(n)} = p_\parallel(n)\ell_n$, and the extension of the pattern across rungs are Hypothesized coordinate assignments. With fixed dimensional parameters the canonical two-fluid PDE is not invariant under $\varphi$-coordinate rescaling; a scale-covariance statement requires corresponding parameter/unit re-normalization. That conditional reparameterization does not identify $B$ with a transported inter-rung field. The bubble lattice—a 3D staggered checkerboard of coherent condensates and empty voids, bounded along the string axis—is therefore the universal organizing geometry used to describe matter, coherence, and geometry from Planck to the megacascade. The cascade ladder of scales is a geometric 1D slice of this 3D lattice.

---

## 1. The Condensation Field

### 1.1 Origin

The two-fluid PDE's canonical conversion term couples Yang and Yin antisymmetrically:

$$\partial_t E_Y \supset -\lambda(1-q)(E_Y - \varphi E_I), \qquad \partial_t E_I \supset +\lambda(1-q)(E_Y - \varphi E_I)$$

Writing $a = \lambda(1-q)$, its density-plane action is

$$\left.\partial_t
\begin{pmatrix}E_Y\\E_I\end{pmatrix}\right|_{\mathrm{conv}}
=-a
\begin{pmatrix}1&-\varphi\\-1&\varphi\end{pmatrix}
\begin{pmatrix}E_Y\\E_I\end{pmatrix}.$$

This is a rank-one relaxation: it conserves $\rho = E_Y + E_I$ and has eigenvalues $0$ and $-\lambda(1-q)(1+\varphi)$. It is not an $SO(2)$ rotation and supplies no fixed phase advance. Keep the angles distinct: $\theta_d = \operatorname{atan2}(E_I,E_Y)$ is the density-plane angle, $\theta_\Psi = \operatorname{atan2}(\Psi_1,\Psi_0)$ is the doublet phase, and $\Theta_S = 2\theta_\Psi \pmod{2\pi}$ is the Stokes double angle. A compact geometric spiral coordinate, when that separate convention is introduced, is denoted $\chi$.

The conversion term relaxes the local density-plane deviation $\varepsilon(\mathbf{x}) = E_Y - \varphi E_I$. Spatial wake/interference patterns may be represented when the other PDE terms and a geometric ansatz are supplied, but canonical conversion alone does not generate a fixed phase clock. We use the following geometric condensation proxy (with its axial factor and cross-rung assignment remaining Hypothesized):

$$B(x, y, z) = \cos(\alpha x)\cos(\beta y) \cdot \cos(\gamma_n z)$$

- $x$: Yang axis (extended, normal direction)
- $y$: Yin axis (contracted, binormal direction)
- $z$: String axis (cascade direction, tangent)
- $\Lambda_Y$: Yang wake wavelength in the $x$-$y$ plane
- $\Lambda_I = \Lambda_Y/\varphi$: Yin wake wavelength
- $p_\parallel(n)$: dimensionless number of cascade-rung intervals between adjacent bubble maxima along the string axis
- $P_\parallel^{(n)} = p_\parallel(n)\ell_n$: physical along-string bubble period

The string axis is a spatial coordinate, not by itself a scale-transport channel. If a wavefunction/doublet phase and amplitude are supplied, the axial spatial projection is

$$J_{\Psi,z} = \rho\,\partial_z\theta_\Psi.$$

A corresponding density-plane projection $J_{d,z}$ may be defined from $\theta_d$ when that current is part of the model. $J_{\Psi,z}$ and $J_{d,z}$ are named spatial currents; identifying either with transport between cascade scales requires a separate constitutive map, which is not supplied here. The $p_\parallel(n)=2$ winding is a Hypothesized geometric coordinate assignment, not a consequence of canonical conversion (`foundations/qi-flow-double-helix.md`).

Under this geometric proxy assignment, bubbles are labeled where $B > \theta_{\text{cond}}$ and voids where $B < -\theta_{\text{cond}}$. The threshold $\theta_{\text{cond}}$ is determined conditionally by the conversion-diffusion balance (`foundations/bubble-edge-geometry.md` §1.2).

### 1.2 The 2D Cross-Section: Staggered Checkerboard

In the Yang-Yin plane ($z$ fixed at a bubble maximum), the field reduces to:

$$C(x, y) = \cos(\alpha x)\cos(\beta y)$$

This produces a **staggered checkerboard lattice**:

At the center grid, with $m,n\in\mathbb{Z}$,

$$x=m\frac{\Lambda_Y}{2},\qquad y=n\frac{\Lambda_I}{2},\qquad C(x,y)=(-1)^{m+n}.$$

Thus even $m+n$ gives $C=+1$ bubble centers and odd $m+n$ gives $C=-1$ void centers. The saddles are $C=0$ quarter-offset sites and lines where one cosine vanishes:

$$x=\left(m+\frac12\right)\frac{\Lambda_Y}{2}=\frac{(2m+1)\Lambda_Y}{4}\quad\text{or}\quad y=\left(n+\frac12\right)\frac{\Lambda_I}{2}=\frac{(2n+1)\Lambda_I}{4}.$$

They are not the odd-parity center sites. Bubbles occupy the even-parity sublattice and voids the odd-parity sublattice. Each bubble is connected to its 4 diagonal neighbors via these saddles and blocked from its 4 axial neighbors by $C=-1$ void barriers. The lattice degree is 8 geometric but 4 connectable.

The staggered placement is interferometric: the wake beat envelope of `foundations/wake-geometry.md` §2 places bubble maxima at $m\,\ell_{n+1}$ and void zeros at the half-rungs, reproducing this checkerboard from geometric phase structure alone, with no coupling strength entering.

### 1.3 The 3D Extension: Bounded Along the String

The full 3D field $B(x,y,z)$ multiplies the transverse checkerboard by $\cos(\gamma_n z)$. The along-string cosine bounds each bubble's extent in the cascade direction. The bubble edge in 3D is:

$$\{B(x,y,z) = \theta_{\text{cond}}\}$$

an oblate triaxial spheroid—extended in Yang, contracted in Yin, bounded along the string.

---

## 2. Conditional Scale Reparameterization

### 2.1 The PDE's $\varphi$-Rescaling Symmetry

The two-fluid PDE governing $E_Y, E_I$ is:

$$\partial_t E_Y = -(\mathbf{u}\cdot\nabla)E_Y + \nu\nabla^2 E_Y - \lambda(1-q)(E_Y - \varphi E_I) + \ldots$$
$$\partial_t E_I = -(\mathbf{u}\cdot\nabla)E_I + \nu\nabla^2 E_I + \lambda(1-q)(E_Y - \varphi E_I) + \ldots$$

Under the formal coordinate rescaling $\mathbf{x} \to \varphi\mathbf{x}$, $t \to \varphi t$, the spatial derivatives transform as $\nabla \to \varphi^{-1}\nabla$. With the canonical parameters $\lambda$ and $\nu$ held fixed, the conversion term carries no derivative rescaling, so the fixed-parameter PDE is not invariant under this coordinate change. A scale-covariance statement therefore requires corresponding rescaling of dimensional parameters or units; after that reparameterization, the diffusion and advection terms carry the expected $\varphi^{-2}$ and $\varphi^{-1}$ factors, while the conversion pair remains equal and opposite and conserves $\rho = E_Y + E_I$. This conditional reparameterization does not turn the rank-one relaxation into an $SO(2)$ rotation or a constitutive transport law.

The geometric proxy may be written with the same functional form at adjacent rungs only as a conditional coordinate assignment with the required parameter/unit re-normalization; the asserted Qi-gate transmission nonlinearity $g(q) = q/(\varphi^2 + q^2)$ supplies an application input, not an inter-rung map. Under this assignment, wavelengths are reduced by $\varphi$ for upward steps or expanded by $\varphi$ for downward steps. This is not a map carrying a current from rung $n$ to rung $n+1$.

### 2.2 The Condensation Field Under the Scale Assignment

The geometric proxy $B(x,y,z)$ is assigned a conditional wavelength rule after the required parameter/unit re-normalization. At cascade rung $n$:

$$\boxed{\Lambda_Y^{(n)} = \ell_n, \qquad \Lambda_I^{(n)} = \ell_n/\varphi, \qquad P_\parallel^{(n)} = p_\parallel(n)\ell_n, \qquad \gamma_n = \frac{2\pi}{P_\parallel^{(n)}} = \frac{2\pi}{p_\parallel(n)\ell_n}}$$

The wavelengths scale with the cascade rung $\ell_n = \ell_{\text{Pl}} \times \varphi^n$. The **functional form** $B(x,y,z) = \cos(\alpha x)\cos(\beta y)\cos(\gamma_n z)$ is assigned identically at every rung; only the wavelengths—and hence $\gamma_n$—change. Because $P_\parallel^{(n)}$ is a length and $p_\parallel(n)$ is dimensionless, $\gamma_n$ has inverse-length units and $\gamma_n z$ is dimensionless. This coordinate assignment does not by itself establish a physical inter-rung field or current.

### 2.3 $p_\parallel(n)$ and $P_\parallel^{(n)}$: The Along-String Period

$p_\parallel(n)$ is the dimensionless number of cascade-rung intervals between adjacent bubble maxima along the string axis; its associated physical period is $P_\parallel^{(n)} = p_\parallel(n)\ell_n$. Current evidence suggests $p_\parallel(n)$ may depend on $n$:

| Scale | $n$ (approx) | Dimensionless rung count $p_\parallel(n)$ | Physical period $P_\parallel^{(n)}$ | Source |
|---|---|---|---|---|
| Cosmological | ~285 | $p_\parallel(n)=1$ (one rung) | $P_\parallel^{(n)}=\ell_n$ | `foundations/bubble-edge-geometry.md` §2.3 |
| Human body | 142–168 | $p_\parallel(n)=2$ (two rungs) | $P_\parallel^{(n)}=2\ell_n$ | `consciousness/chakras-as-cascade-bubbles.md` §5 |

Whether $p_\parallel(n)$ varies continuously or discretely, and what determines its value at a given $n$, is an open question (§8). At the human scale, $p_\parallel(n)=2$ and $P_\parallel^{(n)}=2\ell_n$ are a Hypothesized geometric convention compatible with representing one full $\chi$ cycle over two rung increments; it is not derived from the canonical density-plane relaxation. At the cosmological scale, the wake-wave application reads $p_\parallel(n)=1$ and $P_\parallel^{(n)}=\ell_n$ as a Hypothesized geometric assignment. The coexistence of these values remains an application-level question, not evidence that the canonical conversion has an $n$-dependent $SO(2)$ clock.

---

## 3. The 3D Lattice Structure

### 3.1 Three Orthogonal Periodicities

The full bubble lattice has three spatial periods, one along each Frenet-Serret axis:

| Axis | Direction | Physical period | Spacing |
|---|---|---|---|
| $x$ (Yang, normal) | Extended | $\Lambda_Y = \ell_n$ | widest |
| $y$ (Yin, binormal) | Contracted | $\Lambda_I = \ell_n/\varphi$ | intermediate |
| $z$ (String, tangent) | Cascade | $P_\parallel^{(n)} = p_\parallel(n)\ell_n$ | along-string |

### 3.2 The Lattice as a Nested Hierarchy

Because the same condensation field is assigned at every $n$, the lattice is **self-similar across scales** as a geometric construction. A bubble at rung $n$ contains within it the full sub-lattice of rungs $n-1$, $n-2$, $\ldots$—the 2D checkerboard in its own Yang-Yin cross-section, plus the along-string periodicity of its own sub-cascade. A bubble at rung $n$ is itself a site in the lattice at rung $n+1$.

This nesting continues upward and downward without bound:

$$\underbrace{\cdots \subset \text{bubble}_{n-2} \subset \text{bubble}_{n-1} \subset \text{bubble}_n \subset \text{bubble}_{n+1} \subset \text{bubble}_{n+2} \subset \cdots}_{\text{infinite bidirectional nesting}}$$

The microcascade mirror (`foundations/microcascade-mirror.md`) establishes the downward extension to $n \to -\infty$. The megacascade (chord lattice beyond $n = 292$) is the upward extension. The lattice has **no intrinsic floor or ceiling**.

Read radially through a single bubble's shell, this nesting is represented by the Hypothesized geometric coordinate $\alpha_{\mathrm{geom}} = \theta_\Psi = \pi\,u$, $u = \log_\varphi(r/\ell_n)$. It quantizes the interior into matter rings at $r_k = \ell_n\,\varphi^{-k}$ (each a rung-$(n-k)$ condensate, since $\ell_n\,\varphi^{-k} = \ell_{n-k}$) with void rings at $\ell_n\,\varphi^{-(k+\frac12)}$, ~10 rings within the ~1% nesting floor, $n$-independent (`foundations/bubble-edge-geometry.md` §3). This radial projection is an inference resting on the nested-sub-lattice structure; it is not an independently-derived identity of the canonical density-plane relaxation.

### 3.3 Effective Nesting Depth

The cascade suppression formula (`foundations/cascade-suppression-formula.md`) bounds the physically meaningful nesting depth. A signal propagating downward through the lattice attenuates by $\varphi^{-1}$ per rung descended. Structure at rung $n$ is attenuated to $\varphi^{-\Delta n}$ when observed at rung $n - \Delta n$. For a coherence floor of ~1% ($\varphi^{-\Delta n} > 0.01$), the effective nesting depth is $\Delta n \approx 10$ rungs.

The formal lattice is infinite. The **observable** lattice at any given rung extends roughly 10 rungs downward before signal attenuation smears the pattern into noise.

---

## Geometric Signatures at a Selected Rung

At a selected rung, the assigned transverse condensation field supplies conditional geometric signatures. Their algebra follows from the stipulated proxy and coordinate assignment; it does not establish a universal cross-rung edge ratio or a biological/cosmological realization.

### 4.1 $\varphi$-Elliptical Bubble Shape

The bubble cross-section in the Yang-Yin plane is elliptical with axis ratio:

$$\frac{a_X}{a_Y} = \frac{\beta}{\alpha} = \varphi \approx 1.618$$

**Testable at:** cosmological voids (SDSS/DESI void ellipticity), chakra cross-sections (biophoton imaging), cellular structures (microscopy).

### 4.2 Level-Dependent Edge Steepness Anisotropy

At a common condensation boundary level $C=\theta_{\mathrm{cond}}$, the directional gradient ratio in the optional geometric proxy is

$$\boxed{R(\theta_{\mathrm{cond}})\equiv\frac{|\nabla C|_{\text{axial}}}{|\nabla C|_{\text{diag}}}=\frac{\sqrt{1+\varphi^2}}{2}\sqrt{\frac{1+\theta_{\mathrm{cond}}}{\theta_{\mathrm{cond}}}}}$$

At the phenomenologically selected $\theta_{\mathrm{cond}}=0.45$, $R=1.7072$. It varies with the selected level and is therefore a conditional geometric-proxy benchmark, not a zero-parameter constant or canonical PDE output. The fixed-step PDE diagnostic retains no $C=0.45$ edge. Any test at cosmological or biological boundaries must independently identify the physical boundary and the proxy-to-observable map.

**Testable at:** independently identified cosmological void, chakra, fascial, or cellular boundaries, with the relevant proxy-to-observable map declared.

### 4.3 Qi Density Profile

$$q_{\mathrm{proxy}}(\mathbf{x}) = \frac{(1 + B(\mathbf{x}))^2}{2}$$

At a bubble center ($B \to 1$), the raw geometric intensity proxy is $q_{\mathrm{proxy}} \to 2$; at a void center ($B \to -1$), it is $q_{\mathrm{proxy}} \to 0$. The canonical solver variable remains bounded, $q_{\mathrm{solver}}=\mathcal{M}(q_{\mathrm{proxy}})\in[0,1]$, and the constitutive map $\mathcal{M}:[0,2]\to[0,1]$ is separate from the geometric assignment. The proxy functional form is a Hypothesized geometric ansatz; its endpoint values and other algebraic consequences follow once the ansatz is stipulated. The numerical value of $\theta_{\text{cond}}$ depends on the conversion-diffusion balance and $\mathcal{M}$ at each scale and may vary with $n$.

### 4.4 Hypothesized Fibonacci Spiral Coordinate at Octave Boundaries

At the boundaries between cascade octaves—where the lattice's $\varphi$-spacing resolves into the next level of organization—a separate geometric construction assigns the 2D checkerboard a **5-arm Fibonacci spiral coordinate**. Its polar equation is:

$$\chi(r) = \frac{2\pi}{\ln\varphi}\ln\left(\frac{r}{\ell_n}\right)$$

Here $\chi(r)$ is a compact Hypothesized geometric coordinate associated with the doublet phase convention; it is not the Stokes double angle $\Theta_S = 2\theta_\Psi \pmod{2\pi}$ and not the density-plane angle $\theta_d$. By construction, a $\varphi$ change in the radial coordinate produces one $2\pi$ coordinate increment (one full coordinate turn per cascade-rung increment). This fixed phase assignment is a Hypothesized geometric convention, not a consequence of canonical conversion. The expansion factor per turn is $\varphi$. The 5-fold symmetry follows from the Wu Xing cycle ($w = 5$, `foundations/wu-xing-derivation.md`), which appears at octave boundaries where the lattice is assigned coherent coordinate phases.

**Observed at:** the cosmological Cassi bubble (step 285, 5 spiral arms in galaxy distribution), the human chakra system ($13 = F_7$ Fibonacci nodes along the spine), the neural hierarchy (8 levels within a $\varphi^5$ span), and potentially at galaxy-cluster scales, molecular scales, and gigacascade scales.

---

## 5. The Cascade Ladder as a 1D Slice

The dimensionful cascade $\ell_n = \ell_{\text{Pl}} \times \varphi^n$ (`foundations/dimensionful-cascade.md`) is traditionally presented as a 1D ladder of scales. This document uses a geometric identification:

**The cascade ladder can be represented as a 1D slice of the 3D bubble lattice, taken along the string axis ($z$) at a fixed transverse position.**

The cascade steps $n = 0, 1, 2, \ldots, 292$ (today's observable range) are the along-string bubble maxima in the cosmological application with $p_\parallel(n)=1$ (one rung, so $P_\parallel^{(n)}=\ell_n$). The voids between steps are the $B = -1$ minima. The "cascade suppression" factor for a signal span of $N$ rungs remains an attenuation law indexed by rung separation; identifying it with a current or physical transport along the $z$-axis requires a separate constitutive map, which is not supplied here.

The ladder metaphor is correct but incomplete—it captures the assigned along-string periodicity $p_\parallel(n)$ and its physical period $P_\parallel^{(n)}$ but omits the transverse lattice structure. Every "rung" of the ladder is a full 2D checkerboard of bubbles and voids in the Yang-Yin plane.

---

## 6. Manifestations Across the Cascade

| Cascade rung $n$ | Scale $\ell_n$ | Physical structure | Lattice manifestation |
|---|---|---|---|
| 0 | $1.6 \times 10^{-35}$ m | Planck length | $\sigma$-regularized crossover; lattice dissolves into harmonic regime at $\sigma = \ell_{\text{Pl}}/\varphi^3$ (rung $-3$; noise–signal crossover at the Planck core, `gravity/quantum-gravity.md` §2.1) |
| ~5 | $1.8 \times 10^{-34}$ m | GUT scale | Gauge symmetry breaking at a lattice node |
| ~95 | $1.0 \times 10^{-15}$ m | QCD confinement | Proton as a condensed standing wave; 92-rung coherence depth (0 → 91.5) |
| ~117 | $5.3 \times 10^{-11}$ m | Bohr radius | Atomic bubble lattice onset; orbital shells as nested bubble surfaces |
| ~136 | $5.0 \times 10^{-7}$ m | Visible light | One $\varphi$-step wide; 7 sub-rungs via Fibonacci partitioning |
| 142–168 | $7.7 \times 10^{-6}$ to $1.7$ m | Human body | 26-rung nested lattice; 13 chakra nodes at $p_\parallel(n)=2$ (so $P_\parallel^{(n)}=2\ell_n$) |
| ~144 | ~20 µm | Neuron soma | Neural hierarchy anchor; 8 $\varphi$-spaced levels |
| ~267 | $9.3 \times 10^{20}$ m | Milky Way | Galaxy as a bubble condensate in the cosmic lattice |
| 285 | $5.9 \times 10^{24}$ m | Cassi bubble | One full along-string period $P_\parallel^{(285)}=\ell_{285}$; 2D checkerboard observable in void catalogs |
| >292 | >$1.7 \times 10^{26}$ m | Megacascade | Chord lattice of $w=5$ bubbles at $\varphi$-spaced intervals; 5-arm spiral at gigacascade octave |

---

## 7. Epistemic Boundaries

### Derived conditional (from the transverse condensation field + selected-level geometric inputs)

- The transverse condensation proxy $C(x,y) = \cos(\alpha x)\cos(\beta y)$ and its 2D checkerboard lattice (`foundations/bubble-edge-geometry.md` §1.1, §4)
- The $\varphi$-elliptical bubble shape (axis ratio $\varphi$) (`foundations/bubble-edge-geometry.md` §2.1)
- The level-dependent directional edge-slope proxy $R(\theta_{\mathrm{cond}})=\frac{\sqrt{1+\varphi^2}}{2}\sqrt{\frac{1+\theta_{\mathrm{cond}}}{\theta_{\mathrm{cond}}}}$ (`foundations/bubble-edge-geometry.md` §2.2); at $\theta_{\mathrm{cond}}=0.45$, $R=1.7072$ as a conditional geometric-proxy benchmark, with no surviving $C=0.45$ edge at the fixed-step PDE endpoint
- The Qi density proxy $q_{\mathrm{proxy}} = (1+B)^2/2$ with the bounded canonical map $q_{\mathrm{solver}}=\mathcal{M}(q_{\mathrm{proxy}})$ when the geometric ansatz and constitutive map are supplied (`foundations/bubble-edge-geometry.md` §1.1)
- The displayed PDE's conditional scale reparameterization under $\varphi$-rescaling (`foundations/microcascade-mirror.md` §2)
- The Planck-crossover scale: $\sigma = \ell_{\text{Pl}}/\varphi^3$ (rung $n = -3$)—the scale at which the lattice's bubble/void phase structure dissolves into the harmonic regime (noise–signal crossover at the Planck core, `gravity/quantum-gravity.md` §2.1; **Derived conditional on the noise–signal identification and $d = 3$**)

### Hypothesized (geometric coordinate assignments, PDE-testable, predictions supplied)

- The full 3D product $B(x,y,z) = \cos(\alpha x)\cos(\beta y)\cos(\gamma_n z)$ and its operation at every cascade rung
- That the radial ring ladder is the $\alpha_{\mathrm{geom}} = \theta_\Psi = \pi u$ projection of the nested lattice (`foundations/bubble-edge-geometry.md` §3)
- That specific biological structures (chakras, neural hierarchy, muscle architecture) are lattice instantiations—the scale covariance says the geometric field can be assigned at these scales; that the structures we observe *are* the field's bubble lattice at those scales is a structural mapping requiring PDE verification
- That $p_\parallel(n)$ varies with $n$ ($p_\parallel(n)=1$ at cosmological scale, $p_\parallel(n)=2$ at human scale)—the physical periods $P_\parallel^{(n)}=\ell_n$ and $P_\parallel^{(n)}=2\ell_n$ are Hypothesized geometric conventions compatible with the $\Theta_S$ assignment; applying this rung-count rule across rungs is also Hypothesized, and neither the $n$-dependence nor the single-rung assignment at step 285 is yet derived
- That the 5-arm Fibonacci spiral appears at every octave boundary (observed at step 285; extension to other octaves is structurally consistent but unverified)

### Speculative

- The gigacascade, teracascade, and higher octaves—the lattice's upward infinity is logically consistent with scale covariance, but no direct observation is possible beyond the megacascade's CMB boundary imprint at $\ell < 5$
- The exact mapping of specific anatomical structures (individual vertebrae, named muscles, cortical areas, specific fascial planes) to specific cascade rungs

---

## 8. Open Questions

Items 1–2 and 4–5 are open; item 3 is the derived Planck-crossover scale (tier: Derived conditional on the noise–signal identification and $d = 3$).

1. **What sets $p_\parallel(n)$ and $P_\parallel^{(n)}$?** The dimensionless along-string rung count is $p_\parallel(n)=1$ at the cosmological scale and $p_\parallel(n)=2$ at the human scale; the corresponding physical periods are $P_\parallel^{(n)}=\ell_n$ and $P_\parallel^{(n)}=2\ell_n$. The allowed set is constrained first: $p_\parallel(n) \in \{1, 2\}$ exactly. The values $1$ and $2$, and applying this rung-count rule across scales, are Hypothesized geometric assignments.

At a transverse bubble center, writing the axial coordinate at a half-rung cell wall as $z=(m+\tfrac12)\ell_n$, the cell-wall axial factor is

$$
\cos(\gamma_n z)=\cos\!\left(\gamma_n(m+\tfrac12)\ell_n\right)=\cos\!\left(\frac{\pi(2m+1)}{p_\parallel(n)}\right).
$$

For $p_\parallel(n)=1$ this gives $-1$ (full voids), for $p_\parallel(n)=2$ it gives $0$ (saddles $\le \theta_{\text{cond}} \approx 0.45$, barriers), and for $p_\parallel(n)\ge 3$ it gives $+0.5$/$+0.707$/$+0.809$—some half-rung then sits above $\theta_{\text{cond}}$ inside a bubble, so the cell walls leak. Fractional $p_\parallel(n)$ is excluded by the de-resonance principle (`foundations/wake-geometry.md` §1a). Tier: **Hypothesized geometric coordinate assignment, conditional on the half-rung void structure and de-resonance.** The observed $n$-reading is then a choice between the two scale-covariant lattices, not a continuous law; what remains open is which lattice a given scale selects.

2. **Does $\theta_{\text{cond}}$ vary with $n$?** The conversion-diffusion balance depends on $D_{\text{eff}}/\omega_0$, and $D_{\text{eff}}$ (the effective diffusion of the condensation field) may vary with scale. The cosmological $\theta_{\text{cond}} \approx 0.45$ is calibrated phenomenologically; measuring it at other scales (e.g., biological) requires PDE simulation at those scales.

3. **The Planck crossover scale (derived).** The $\sigma$-regularization makes the Planck scale a smooth crossover: the lattice's discrete bubble/void structure dissolves into the continuous harmonic regime at $\sigma = \ell_{\text{Pl}}/\varphi^3$—cascade rung $n = -3$, three rungs below the Planck cell. The scale is derived by the noise–signal crossover at the Planck core (`gravity/quantum-gravity.md` §2.1): the per-rung dephasing noise of the two-fluid, $1 - q_i = \varphi^{-i-\delta}$, equals the equilibrium Yang excess $(\pi/\rho)_{\text{eq}} = (\varphi-1)/(\varphi+1) = \varphi^{-3}$ (the fixed-point imbalance $\alpha_0$ that also anchors $\xi = \alpha_0^{-2}$, `foundations/xi-derivation.md` §2.1) at the doublet's reference rung, giving $\varphi^{-\delta} = \varphi^{-3}$ and hence $\delta = 3$; because the profile steps by the de-resonance damping $\varphi^{-1}$ per rung, the dephasing reaches certainty ($1 - q \to 1$) precisely at rung $-3 = \sigma$, the floor of the physical profile (verified numerically: $\sigma = 3.815\times10^{-36}$ m; $\log_\varphi(\sigma/\ell_{\text{Pl}}) = -3.000$). The geometric reading $\delta = d = 3$—each of the three spatial axes contributing one rung of indistinguishability depth via the per-axis de-resonance damping $\varphi^{-1}$—is secondary. What remains open is the crossover *profile*—the transition shape of $B(x,y,z)$ into the harmonic regime as $n \to 0$, which requires PDE resolution at the Planck cell.

**Inputs.**

$$
\boxed{
\begin{aligned}
&\text{(a) noise} = \text{signal identification} && \text{the separation scale is where per-rung dephasing noise equals the equilibrium excess—physical postulate, same status as the Wu Xing coherence criterion (foundations/wu-xing-derivation.md §6)}\\
&\text{(b) fixed-point excess } (\pi/\rho)_{\text{eq}} = \varphi^{-3} && \text{Derived: phi-attractor fixed point (foundations/cassi-theory-reference.md §2.3)}\\
&\text{(c) per-rung dephasing family } 1 - q_i = \varphi^{-i-\delta} && \text{de-resonance; the family's } i\text{-dependence remains Hypothesized (foundations/proton-coherence-budget.md §8)}\\
&\text{(d) } d = 3 \text{ for the geometric reading } \delta = d && \text{conditional: Frenet–Serret frame, granted its three postulates (foundations/why-three-dimensions.md §7; G5, Hypothesized)}\\
&\text{(e) two-fluid phase structure of the Planck cell} && \text{context: this document §2–§5: condensation field, staggered checkerboard, string bound at rung 0}
\end{aligned}
}
$$

4. **Is the lattice structure identical in the microcascade ($n < 0$)?** The microcascade mirror (`foundations/microcascade-mirror.md`) establishes bidirectional extension but notes a regime change in the Qi coherence profile at $n < 0$. Whether the condensation field maintains the same $B(x,y,z)$ functional form or transitions to something else is not yet known.

5. **Can the lattice realize a quantum apparatus?** The regulated measurement construction uses a Hamiltonian interaction that correlates alternatives with disjoint retained topological sectors, plus one actual guided configuration and quantum equilibrium (`open-questions-cassi-answers.md` Q7). A bubble lattice could supply microscopic apparatus coordinates only if an explicit CassiFI Hamiltonian produces those sectors and the required record overlaps $\gamma_{jk}$. No such lattice-to-apparatus derivation is presently registered.

---

## References

- `foundations/bubble-edge-geometry.md`—condensation field derivation, checkerboard lattice, edge anisotropy, $\theta_{\text{cond}}$
- `foundations/dimensionful-cascade.md`—complete cascade table, $\ell_n = \ell_{\text{Pl}} \times \varphi^n$ (292 = today's horizon rung)
- `foundations/microcascade-mirror.md`—bidirectional cascade extension, conditional scale-reparameterization statement
- `foundations/cascade-suppression-formula.md`—signal attenuation per rung, effective nesting depth bound
- `foundations/why-three-dimensions.md`—Frenet-Serret frame, triaxial spheroid, string axis
- `foundations/wake-geometry.md`—wake beat envelope, checkerboard placement, closure ladder
- `foundations/spin-fibonacci-spiral.md`—Fibonacci spiral and the Hypothesized geometric SO(2) coordinate convention, $\chi(r)$ polar equation
- `foundations/wu-xing-derivation.md`—$w = 5$ derived conditional under the selected construction; the physical organizing cycle and five-fold symmetry application remain Hypothesized
- `foundations/three-generations.md`—Fibonacci recurrence, sub-channel partitioning
- `consciousness/chakras-as-cascade-bubbles.md`—human-scale lattice, $p_\parallel(n)=2$ and $P_\parallel^{(n)}=2\ell_n$, 13-node derivation
- `consciousness/consciousness-from-phi.md`—26-step human cascade, pinch transition
- `gravity/quantum-gravity.md`—$\sigma$-regularization, Planck-scale smooth crossover; §2.1 derives $\delta = 3$
- `computations/sigma_delta_derivation.py`—numerical verification of the Planck-crossover derivation (identities, saturation at rung $-3$, phase-slip structure)
- `hypotheses/neural-criticality.md`—8-level neural hierarchy as lattice at neural rungs
- `visual-explainers/chord_lattice.py`—condensation field, staggered lattice visualization
- `visual-explainers/string_bubble_cascade.py`—3D PDE bubble formation on string
- `visual-explainers/cascade_cosmos.py`—three-regime cascade diagram with microcascade spiral
