# Why Three Dimensions: The Spiral's Three Directions

## Status: Hypothesized dimensional identification (conditional consistency map; W1 anti-phase morphology supported)—August 2026

## Abstract

This paper presents a **Hypothesized dimensional identification** as a
conditional consistency map for identifying the framework's spatial count with
$d = 3$. The Lucas identity $\varphi^2+\varphi^{-2}=3$, the attractor
imbalance exponent, the noise–signal exponent, and the selected rung-clock
normalization are valid mathematical statements or model relations. Their
shared integer becomes an ambient dimension only through a framework mapping.
The Frenet–Serret route is
explicitly conditional: a non-degenerate curve embedded in $\mathbb{R}^3$ has
the triad $\{\mathbf T,\mathbf N,\mathbf B\}$, while a generalized Frenet
frame in $\mathbb{R}^d$ can contain up to $d$ vectors. The triad therefore
checks a proposed three-dimensional embedding; it does not select the
dimension of space.

The geometric construction studies a prescribed logarithmic spiral and its
loxodrome lift on a cone. Its $\varphi$-scaled curvature and frame alignment
are numerically consistent with the proposed string, Yang, and Yin axis map
inside that embedding. The canonical two-fluid state remains two real density
fields. Its conversion ODE conserves total density and moves the derived
density-plane angle $\theta_d=\operatorname{atan2}(E_I,E_Y)$ monotonically
toward equilibrium; it does not provide a periodic $2\pi$ phase clock. The
logarithmic spiral is parameterized by a separate added geometric coordinate
$\chi$; compact phase interpretations and per-rung pitch are additional
geometric postulates unless separately implemented and tested. The W1
opposite-sign wake result remains a measured morphology branch, with the
paired-sheet consequences recorded as conditional predictions.

**Figure:** `visual-explainers/cascade_cosmos.png`—panel A shows the bubble
chain on the string; panel B (zoom) shows the conditional $\mathbb{R}^3$
triaxial morphology ansatz with the opposite-sign paired-sheet interference
pattern (`visual-explainers/cascade_cosmos.py`).

---

## 1. The Problem: Connecting an Integer to Ambient Dimension

The Qi-gravity coupling is derived as the inverse square of the fixed-point
imbalance,

$$\xi = \varphi^6 = (\pi/\rho)^{-2}, \qquad \pi/\rho = (\varphi-1)/(\varphi+1) = \varphi^{-3}$$

(`xi-derivation.md` §2): the exponent 6 = 3 × 2 with the 3 from the attractor's
imbalance exponent and the 2 from the quadratic degree of the gravitational
coupling. That exponent 3 is a fixed-point algebraic integer. The ambient
spatial count $d$ is a separate model label. Section 2.6 places five
mathematical routes beside one another and records the framework's proposed
identification of their shared integer with $d=3$; the identification remains
Hypothesized and conditional.

This document develops the geometric consistency route. It specifies a
logarithmic spiral and tests a three-dimensional lift, while keeping the
dynamical and dimensional assumptions visible.

---

## 2. A Conditional Three-Direction Construction

### 2.1 Field-plane dynamics and the prescribed spiral
The canonical state consists of two real density fields, $E_Y$ and $E_I$.
Write their ratio as $r=E_Y/E_I$ and their derived density-plane angle as
$\theta_d=\operatorname{atan2}(E_I,E_Y)$. The equal-and-opposite conversion
source conserves the total density $\rho=E_Y+E_I$ and drives $r$ monotonically
toward $\varphi$; equivalently, $\theta_d$ relaxes monotonically toward its
equilibrium value. This ODE has no periodic $2\pi$ phase clock.

The geometric test instead prescribes a logarithmic curve using the separate
geometric coordinate $\chi$,

$$R(\chi)=R_0e^{b\chi}, \qquad b=\frac{\ln\varphi}{2\pi}.$$

The factor $\varphi$ per $2\pi$ turn and the association of one turn with one
cascade rung are coordinate conventions for this construction. They make the
curve self-similar and provide the $\varphi$-scaled length used by the
loxodrome calculation. They are not outputs of the conversion ODE. A compact
$U(1)$ or $SO(2)$ phase, a half-angle spinor, and any periodic inter-rung clock
would be additional model postulates requiring their own implementation and
test.

### 2.2 The Frenet–Serret frame in a chosen embedding

For a regular curve with nonzero curvature embedded in $\mathbb{R}^3$, the
Frenet–Serret construction provides three mutually orthogonal unit vectors:

- **Tangent** $\mathbf T$: points along the direction of motion. In the
  conditional map this is the string or cascade axis.
- **Normal** $\mathbf N$: points toward the center of curvature. The proposed
  morphology map assigns the inward direction to Yang when $E_Y>E_I$.
- **Binormal** $\mathbf B=\mathbf T\times\mathbf N$: completes the
  right-handed triad. The proposed map assigns the in-plane transverse
  direction to Yin.

$$\boxed{\text{Conditional }\mathbb{R}^3\text{ map}:\
\{\mathbf T,\mathbf N,\mathbf B\}\longmapsto
\{\text{string},\text{Yang},\text{Yin}\}}$$

Differential geometry supplies this frame after the ambient embedding has been
chosen. In $\mathbb{R}^d$, the generalized Frenet frame can have up to $d$
vectors, subject to the rank of the successive derivatives. Thus the triad
cannot determine the ambient dimension. The script verifies identities of the
chosen $\mathbb{R}^3$ loxodrome and its frame; its output is a consistency
check for that embedding.

The local density-plane diagnostic

$$J_{d,z}=E_Y\partial_zE_I-E_I\partial_zE_Y
          =\rho_\perp^2\partial_z\theta_d,\qquad
\rho_\perp^2=E_Y^2+E_I^2$$

measures a spatial density-plane-angle gradient along grid $z$. It is a local
diagnostic, not automatically a cascade or inter-scale current. An
inter-rung flux, a compact phase, or a periodic phase advance requires a
separate postulate and test.

### 2.3 Why this curve and why $\varphi$

The conditional construction has two geometric ingredients:

1. **Forward scale advance.** The ratio evolves from $r_0\approx0.047$ toward
   $\varphi$ while the cascade supplies the scale hierarchy and the
   approximately 292-rung horizon interval.
2. **Prescribed turn and pitch.** The curve uses $R(\chi)=R_0e^{b\chi}$
   with $b=\ln\varphi/(2\pi)$. A cone lift supplies the third coordinate used
   by the numerical Frenet calculation.

The de-resonance principle motivates $\varphi$ as the scale factor in this
ansatz. It does not turn the canonical conversion ODE into a periodic angular
generator. The two-fluid state supplies a density plane and a monotone
relaxation path; it does not by itself determine how many ambient axes the
path occupies. The loxodrome is therefore a selected $\mathbb{R}^3$ model
embedding, with higher-dimensional generalizations left open.

### 2.4 The axes are unequal within the morphology ansatz

Within the chosen embedding, the $\varphi$-scaled curve assigns different
geometric roles to the three frame directions:

- **Tangent (string axis):** bounded by the interval between adjacent
  cascade-step coordinates. The one-turn-per-rung reading is part of the
  coordinate convention.
- **Normal (Yang axis):** extended in the proposed morphology because Yang is
  the dominant expansive component, $E_Y>E_I$, over most of the trajectory.
- **Binormal (Yin axis):** contracted in the proposed morphology because Yin is
  subdominant and contractive; the illustrative ratio at freeze-out is
  $r\approx\varphi$.

The resulting triaxial spheroid is a conditional morphology built on the
$\mathbb{R}^3$ map. Its unequal axes are a geometric interpretation of the
selected curve, not an independent derivation of spatial dimensionality.

### 2.5 What the construction identifies

The curve calculation supports a concrete statement: the prescribed
$\varphi$-spiral has a self-similar curvature structure, and its
$\mathbb{R}^3$ cone lift has a well-defined Frenet triad with the proposed
axis alignment. The calculation does not establish that physical space must
have three dimensions. The same distinction applies to the exponent 3 in
$\xi=(\pi/\rho)^{-2}$: its attractor origin is algebraic, while the
identification of that integer with $d$ is a framework hypothesis.

### 2.6 Five routes to $d=3$: conditional consistency map

The five routes collect mathematical coincidences and model normalizations
that all evaluate to the integer 3:

| Route | Mathematical statement | Role in the map |
|---|---|---|
| (a) Lucas | $\varphi^2+\varphi^{-2}=3$ | Exact $\varphi$-algebra identity |
| (b) Attractor imbalance | $(\pi/\rho)_{\rm eq}=(\varphi-1)/(\varphi+1)=\varphi^{-3}$ | Fixed-point exponent used in $\xi=\varphi^6$ |
| (c) Noise–signal | $\varphi^{-\delta}=\varphi^{-3}\Rightarrow\delta=3$ | Equality of the stated dephasing profile and equilibrium excess (`gravity/quantum-gravity.md` §2.1) |
| (d) Rung-clock normalization | $d=\varphi^{-2}/(1-q_0)=3$ | Conditional relation after choosing the gate and continuity normalization |
| (e) Frenet–Serret | $\mathbf T,\mathbf N,\mathbf B$ in an $\mathbb{R}^3$ embedding | Geometric consistency check whose ambient dimension is assumed |

Route (d) is a normalization relation, not a rate derivation. In particular,
$\lambda=0.1$ is an asserted solver normalization/timescale convention.
The value $w=5$ does not fix $\lambda$: equal-and-opposite conversion, a
potential coefficient, and a one-event-per-cycle reading do not determine a
rate or its units. Route (e) likewise begins with an $\mathbb{R}^3$
embedding; in $\mathbb{R}^d$ a generalized frame can have up to $d$ vectors.

The numerical calculation verifies the prescribed three-dimensional
loxodrome: $\tau/\kappa =
(b/\sqrt{1+b^2})\cot\alpha$ is constant along the curve, while $\kappa R$
and $\tau R$ are invariant under the self-similar scaling. The planar
curvature radius is $\rho_c=R\sqrt{1+b^2}=1/\kappa$; the often-quoted
$\kappa^2=\tau^2+\text{const}$ does not hold along the golden spiral and is
valid only in the constant-radius circular-helix limit. The frame alignment
is reported as a property of the selected embedding.

Taken together, the routes motivate a Hypothesized mapping of the shared
integer to $d=3$. They do not provide five independent determinations of
ambient dimension: the algebraic routes use framework quantities, route (d)
uses a chosen normalization, and route (e) assumes the ambient space in which
its triad is defined. This is the circularity boundary for the dimensional
claim.

---

## 3. The Spheroid Bubble

### 3.1 Wake interference in the conditional transverse map

Both fluids leave wakes in the medium—the verified wake-wave mechanism
(`consciousness/consciousness-from-phi.md` §1.3): perturbations in
$\varepsilon = E_Y - \varphi E_I$ propagate at the local wave speed $c(r)$ with
$\varphi$-scaled spacing, reflect, and feed back on their source. Within the
conditional $\mathbb{R}^3$ morphology map, the two density-plane coordinates
are assigned to transverse directions. Their wake systems then form two
mutually perpendicular interference patterns filling the bubble.

### 3.2 The bounded envelope is a conditional triaxial spheroid

A bubble occupies the interval between two adjacent cascade steps. Wake energy
emitted while the string traverses that interval propagates a finite distance
before the bubble's initial conditions freeze (the Qi gate engages at
$r=\varphi^{-1}$, $a\approx0.051$). Within the selected $\mathbb{R}^3$
ansatz, the reachable region is bounded along the three curve-defined axes:

- **Normal (Yang) axis**: extended—the curve's normal points toward the
  center of curvature. Yang dominance ($E_Y>E_I$) biases the prescribed radius
  outward, making this the bubble's longest axis.
- **Binormal (Yin) axis**: contracted—the binormal is orthogonal to both
  tangent and normal. Yin is subdominant; the illustrative reach along Yin is
  shorter than along Yang by the factor $r\approx\varphi$ at freeze-out.
- **Tangent (string) axis**: bounded—the tangent points forward along the
  cascade. The cascade-step separation provides a hard cap; the bubble is
  bounded between adjacent rungs.

The model therefore assigns a **triaxial spheroid**: three unequal axes with
distinct roles in the selected curve. The Yang–Yin cross-section is elliptical
with illustrative axis ratio $\varphi$. Combined with the short string axis,
the bubble is flattened by the asymmetric extension in the doublet plane
against cascade confinement. This is a conditional morphology statement
inside the chosen embedding.

For the Cassi bubble (step 285, $\sim191$ Mpc comoving, 97.8% of today's
observable ladder; volume fraction $\sim10^{-5}$), the ansatz assigns the
short string/tangent axis and the long in-plane Yang/normal axis. These
preferred directions are part of the morphology map; they do not independently
establish the ambient dimension.

### 3.3 Flattened in-universe structure

The superposition of two coherent perpendicular wake systems has a
distinguished symmetry plane—the midplane—where path lengths from the two
systems match. For in-phase components this is the central antinode:

$$I(\Delta r)=4I_0\cos^2\!\left(\tfrac{k\,\Delta r}{2}\right),\qquad
\Delta r=0\;\Rightarrow\;I=4I_0$$

Structure condenses where interference is constructive—the condensation
threshold $\theta_{\text{cond}}$ is crossed there first (catalytic template
mechanism). Matter therefore forms preferentially on a plane within the
conditional spheroid; the flattened structure is the interference pattern of
the two wake signals, frozen in by condensation.

> **Forward reference.** §4 records the opposite-sign wake branch confirmed by
> the PDE structure and W1 experiment. In that branch the midplane is a node
> (destructive interference), with the first antinodes displaced symmetrically
> to either side as paired sheets. The paired-sheet morphology (§4.2, §4.4)
> is the opposite-sign analogue of the in-phase structure described here.

### 3.4 Yang dominance as the flattening mechanism

A complementary mechanism operates at the level of the doublet axes,
independent of wake interference. The two fluids are not symmetric: Yang is
the expansive, driving component. In the PDE's velocity equation the force is
$\pi\nabla\Phi$ where $\pi=E_Y-E_I$—the Yang excess drives the flow.
Throughout most of cosmic history conversion feeds Yang while $r<\varphi$,
and at freeze-out ($r\to\varphi$, post-pinch) the selected doublet-plane
cross-section is Yang-dominated.

If the two axes carry different energies, $E_Y>E_I$, the field extends farther
along the stronger axis. The cross-section is elliptical, with the Yang axis
longer than the Yin axis by the factor set by the local ratio at freeze-out
($r\approx\varphi$). Combined with the string-axis bound (§3.2), the
conditional morphology is a triaxial spheroid flattened by Yang dominance.

This gives a **conditional geometric prediction**: the Yang/Yin axis ratio in
the bubble's doublet-plane cross-section should track $r$ at freeze-out. With
$r\to\varphi$ as the cosmological attractor, the ellipticity uses the same
constant that governs the framework's scale ansatz. The predicted anisotropy
amplitude feeds directly into the W2 large-scale structure measurement (§5).

**Relation to §2.2.** The internal-to-physical axis map is a declared part of
the conditional $\mathbb{R}^3$ construction. The Frenet vectors provide the
local map after the embedding and curve have been selected; the conversion ODE
does not supply a compact $SO(2)$ phase or generate the spiral. Yang dominance
distinguishes the normal direction as the long axis in this morphology. The
tangent, normal, and binormal consequently receive the conditional identities
bounded, extended, and contracted.

Yang dominance and wake interference (§3.3, §4) remain complementary:
dominance sets the global triaxial shape in the ansatz, while opposite-sign
conversion sets the internal paired-sheet morphology.

---

## 4. The Sign Fork: One Sheet or Two?

The central-plane morphology depends on the relative phase of the two wake
signals. Here the phase label describes wave interference; it is not the
canonical density-plane angle and does not introduce a periodic field clock.
The conversion coupling supplies the opposite-sign branch used by the
observable morphology test.

### 4.1 The opposite-sign response

The canonical mass-conserving conversion drives the two density fields in
opposite directions:

$$
\partial_t E_Y\supset-\lambda(1-q)\varepsilon,\qquad
\partial_t E_I\supset+\lambda(1-q)\varepsilon.
$$

For $\lambda\geq0$ and $0\leq q\leq1$, a positive $\varepsilon$ fluctuation
drains $E_Y$ and feeds $E_I$. The wake-interference ansatz represents these
opposite signs as $\Delta\phi=\pi$; this phase assignment is a separate
Hypothesized morphology map. Define the wake wavelength
$\Lambda_{\mathrm{wake}}=2\pi/k$, distinct from the conversion rate
$\lambda$. Two opposite-sign sources have a node on the midplane and first
antinodes displaced symmetrically:

$$I(\Delta r)=2I_0[1-\cos(k\,\Delta r)]
\;\Rightarrow\;\text{antinodes at }\Delta r=\pm\frac{\pi}{k}
=\pm\frac{\Lambda_{\mathrm{wake}}}{2}.$$

### 4.2 The two branches

| Branch | Interference geometry | Structure morphology | Observational reading |
|--------|----------------------|----------------------|----------------------|
| **In-phase** ($\Delta\phi=0$) | Central antinode | **One** dominant midplane sheet | The Local Sheet *is* the bubble midplane |
| **Opposite-sign** ($\Delta\phi=\pi$) | Central node, flanking antinodes | **Paired sheets** separated by $\Lambda_{\mathrm{wake}}$, central void | The Local Sheet has a symmetric counterpart across a void—searchable in LSS catalogs |
| Quadrature ($\Delta\phi=\pi/2$) | Displaced antinode | Single sheet displaced from the midplane by $\Lambda_{\mathrm{wake}}/4$ in the equal-amplitude phase-shift ansatz | Intermediate case; off-center observers |

Because wake spacing follows the asserted $\varphi$ ratios, the paired-sheet
separation in the opposite-sign branch is itself $\varphi$-scaled—successive
sheet pairs at $\varphi$ multiples of the fundamental wake wavelength, a
signature distinguishable from generic filamentary structure.

### 4.3 The conversion term: opposite signs by construction

Examination of the PDE's `rhs()` kernel in `cassi_two_fluid_3d_gpu.py`
confirms the sign structure directly. The canonical conversion source is

$$
\text{conv}=-\lambda(1-q)(E_Y-\varphi E_I)
=-\lambda(1-q)\varepsilon,
$$

and the right-hand side couples it with opposite signs into the two fields:

$$
\partial_tE_Y\supset+\text{conv},\qquad
\partial_tE_I\supset-\text{conv}.
$$

A positive $\varepsilon$ fluctuation produces opposite-sign forcing on $E_Y$
and $E_I$. This is the PDE's structural sign property. Along the canonical
conversion trajectory, total density is conserved and the derived
$\theta_d=\operatorname{atan2}(E_I,E_Y)$ relaxes monotonically toward
equilibrium. The sign property supplies the wake-interference branch; it does
not make the conversion term a periodic $SO(2)$ rotation.

### 4.4 W1 experimental result (2026-07-20)

The prediction was tested via a dedicated experiment
(`run_w1_phase_correlation.py`, `run_w1_clean.py`, `run_w1_definitive.py`).
Three classes of PDE runs were performed ($N=48$, $\lambda=0.02$, $\chi=0$,
1000 RK2 steps, 3 seeds):

1. **Single-bubble** ($r_{\text{local}}\in\{0.4,0.5,1.2\}$, 3 seeds each):
   the Pearson correlation $\operatorname{corr}(\delta E_Y,\delta E_I)$
   within the bubble region was $-1.0000\pm0.0000$ at steady state—maintained
   at the anti-correlation limit across all 9 runs.

2. **Two-bubble** (3 r-pairs $\times$ 12 separations $\times$ 3 seeds = 108
   runs, partial completion): all completed measurements (27 runs across the
   below\_below r-pair) maintained anti-correlation at $-1.0000$ for both
   bubbles independently, across all separations
   $d\in\{2,4,7,12,15,19,31,34,37\}$.

3. **Clean initialization** ($N=16$, random independent fields): no organized
   spatial structure for conversion to act on; correlation stayed near zero as
   expected for uniform-$r$ conditions.

**Verdict.** The PDE conversion coupling supplies the opposite-sign wake
branch. The interference fork of §4.2 is therefore evaluated on the
opposite-sign branch ($\Delta\phi=\pi$): paired sheets flank a central void,
with sheet-pair separation at the asserted $\varphi$-scaled intervals set by
the wake wavelength.

The Local Sheet—if it is the dominant sheet in the local bubble—should have
a symmetric counterpart across a void. The prediction (W4) is active: search
large-scale structure catalogs for a parallel sheet at the predicted
$\varphi$-scaled separation.

---

## 5. Predictions

| # | Prediction | Method | Expected result | Status |
|---|-----------|--------|-----------------|--------|
| **W1** | The $E_Y$–$E_I$ wake cross-correlation has a definite sign at small lag | Two-bubble PDE runs; cross-correlate wake perturbations versus separation | Sign selects the §4.2 branch (negative: paired-sheet) | **DECIDED: opposite-sign (negative)**—confirmed by PDE structure (§4.3) and runtime maintenance of $r=-1.0000$ across 36 bubble-configuration runs |
| **W2** | Large-scale structure is weakly anisotropic at scales approaching the bubble diameter | Tomographic $P(k)$ / void statistics versus angle from a candidate axis | The asserted $\ln\varphi$ wake spacing modulates with polar angle; anisotropy axis = bubble short axis | Testable with DESI/Euclid (test statistic undefined—must be pinned before data work) |
| **W3** | The W2 anisotropy axis coincides with the CMB $\ell<5$ preferred axis | Cross-probe: LSS anisotropy axis versus quadrupole–octopole alignment axis | Two independent probes, one direction | Testable with existing data (test statistic undefined—must be pinned before data work) |
| **W4** | (Opposite-sign branch selected) A paired-sheet counterpart to the Local Sheet exists across a void | LSS catalog morphology search at asserted $\varphi$-scaled separations | Parallel sheet at predicted separation; central void between | **Active**—search in progress |

The opposite-sign wake branch is selected by the PDE sign structure and W1
measurements. Predictions W2–W4 remain consequences of the conditional
spheroid geometry; W4 is active as an observational search.

---

## 6. Open Derivations

1. **The density-plane angle and wake-sign relation.** The canonical
   two-fluid conversion conserves total density and moves
   $\theta_d=\operatorname{atan2}(E_I,E_Y)$ monotonically toward equilibrium.
   The opposite-sign wake result fixes the sign branch of the interference
   model. A compact $SO(2)$ phase, reactive/quadrature coupling, or periodic
   phase clock would be an additional model sector requiring an explicit
   implementation and test.
2. **The spheroid ellipticity.** Set by the emission history: the residence
   time $\tau(r)$ diverges as $r\to\varphi$, so late wakes dominate; the
   resulting eccentricity of the conditional bubble is computable from $c(r)$
   and the selected curve and feeds directly into W2's predicted anisotropy
   amplitude.
3. **Fluid-count uniqueness.** Whether three-fluid sectors are forbidden by
   ratio incompatibility or merely unobserved remains open. The two-fluid
   state is the canonical starting point, while the $\mathbb{R}^3$ embedding
   is a separate geometric choice.
4. **Exact spiral pitch from the canonical dynamics.** The canonical
   conversion ODE does not derive $\chi=2\pi n$ or a periodic $2\pi$ clock.
   The radial pitch and one-turn-per-rung reading remain asserted coordinate
   postulates. The solver value $\lambda=0.1$ remains an asserted
   normalization/timescale convention; $w=5$ does not derive its rate or
   units.

   A separate conversion-to-expansion implementation reports the retained
   diagnostics $\omega_{\rm rot}/\gamma=5.07945$ (dressed), $0.389$
   turns/rung realized, $0.3868\pm0.0001$ measured, pitch angle
   $\approx11.34^\circ$, and discriminator
   $|a_\chi/a_r|=0.19880$ (08 §C.3, [COMPUTED]). These values are
   conditional measurements of that added implementation. They do not turn
   the canonical density-plane angle into a compact phase and do not
   determine the ambient dimension.

---

## 7. Epistemic Boundaries

### Supported by Verified Physics

- Two real density fields with equal-and-opposite conversion, conserved total
  density, and derived density-plane angle
  $\theta_d=\operatorname{atan2}(E_I,E_Y)$ that relaxes monotonically toward
  equilibrium
- Wake-wave mechanism with $\varphi$-scaled spacing and string-wake feedback
  loop
- The Cassi bubble at step 285; neighboring $w$-bubbles at
  $\ell_{286}$–$\ell_{287}$ (inside the horizon)
- The attractor exponent $(\pi/\rho)_{\rm eq}=\varphi^{-3}$ and the resulting
  algebraic exponent in $\xi=\varphi^6$
- **Opposite-sign conversion coupling** confirmed by PDE structure (§4.3) and
  runtime maintenance of $\operatorname{corr}(E_Y,E_I)=-1.0$ across 36 runs
  (§4.4)

### Plausible Hypothesis (test exists)

- Identification of the shared integer in the five-route map with $d=3$,
  conditional on the stated framework normalizations and the chosen
  $\mathbb{R}^3$ embedding
- The bubble as a triaxial spheroid within that conditional morphology map
- Flattened structure as frozen wake interference, with paired sheets flanking
  a central void on the opposite-sign branch

### Speculative (no current test design)

- Fluid-count minimality as a selection principle (§6.3)
- Quadrature-branch displaced-plane morphology
- Exact Frenet–Serret torsion as a consequence of the canonical conversion
  rate

### Hypothesized Dimensional Identification

The five-route argument is a conditional consistency map. Lucas algebra,
attractor and noise–signal exponents, the selected rung-clock normalization,
and the Frenet calculation all supply values or identities involving 3. The
map from that shared integer to ambient $d=3$ is a framework hypothesis. The
rung-clock relation uses a chosen gate and continuity normalization, and the
Frenet route assumes $\mathbb{R}^3$ before constructing its triad. In
$\mathbb{R}^d$, a generalized Frenet frame can contain up to $d$ vectors.

### Not Supported

- A derivation that fixes the ambient dimension at $d=3$ from the two-fluid
  equations and $\varphi$ alone
- A claim that a Frenet–Serret triad selects the dimension of space
- A claim that the five routes are independent determinations or require no
  model input
- A claim that the Local Sheet is established as one of a paired-sheet set;
  W4 remains an observational search

---

## References

- `xi-derivation.md`: the $\xi=\varphi^6=(\pi/\rho)^{-2}$ relation (attractor exponent)
- `computations/why_three_dimensions_frenet.py`: numerical verification of the prescribed $\mathbb{R}^3$ loxodrome invariants and Frenet-frame alignment; it does not determine ambient dimension
- `dimensionful-cascade.md`: the $\varphi$-cascade (292 = today's horizon rung); Cassi bubble at step 285
- `consciousness/consciousness-from-phi.md` §1: pinch point, wake waves, string-wake loop
- `principles/de-resonance-principle.md`: $\varphi$ as maximal de-resonance
- `foundations/spin-fibonacci-spiral.md`: Fibonacci spiral geometry and asserted internal-coordinate conventions
- `two-fluid/run_two_bubble_fast.py`, `two-fluid/run_two_bubble_verification.py`: W1 test infrastructure
- `cosmology/observational_constraints.md` §4: CMB $\ell<5$ preferred-axis analysis (W3)
