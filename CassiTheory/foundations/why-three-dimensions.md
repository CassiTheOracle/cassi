# Why Three Dimensions: The Spheroid Bubble and the 2+1 Derivation

## Status: Hypothesis with Derivation-Shaped Mechanism and Falsifiable Forks

## Abstract

The Cassi framework derives every structural integer from the two-fluid PDE and
$\varphi$ — with one exception: the **3** in $\xi = \varphi^{2 \times 3}$, which
`xi-derivation.md` imports from observation ("the three directions in which
curvature propagates"). This document proposes a derivation: space is the
two-axis plane of the SO(2) fluid doublet ($E_Y \perp E_I$) plus the cascade
axis along which bubble-steps stack — $3 = 2 + 1$. The same mechanism gives the
universe-bubble a **shape** (an oblate spheroid, bounded between adjacent
megacascade steps) and its **internal morphology** (flattened structure
condensed onto the interference plane of the two perpendicular wake systems).
A sign analysis of the conversion term forks the prediction into two
observationally distinguishable branches — single central sheet vs. paired
sheets flanking a central void — making the idea testable both numerically
(existing two-bubble PDE scripts) and observationally (large-scale structure
morphology, CMB axis alignment).

---

## 1. The Problem: The Last Imported Integer

The Qi-gravity coupling is derived as

$$\xi = \varphi^6, \qquad 6 = \underbrace{2}_{\text{field components}} \times \underbrace{3}_{\text{spatial dimensions}}$$

(`xi-derivation.md` §2). Of the two factors, the 2 is internal — EY and EI are
the two components of the fluid doublet. The 3 is not derived anywhere in the
framework; it is restated observation. The claim of "zero free parameters
beyond $\varphi$" therefore carries a silent asterisk: one bare integer,
taken from the world rather than from the theory.

This document removes the asterisk.

---

## 2. The 2+1 Counting

### 2.1 Two fluids = two perpendicular axes

In the dual-real (SO(2)) formulation of the two-fluid field, $E_Y$ and $E_I$
are not two independent scalars — they are the **two orthogonal components of a
single doublet**, the paired-real decomposition of what would otherwise be a
complex field. The Yang and Yin directions are perpendicular in the framework's
own mathematics: two axes of an internal plane, related by SO(2) rotation, with
the conversion term mediating the rotation (gated by $1-q$).

### 2.2 The string is the third axis

The ratio $r = E_Y/E_I$ evolves along a one-dimensional trajectory — the
"string" — from $r_0 \approx 0.047$ to the $\varphi$-attractor. Along this same
axis the megacascade stacks its bubbles: the Wu Xing bubble at step 285 sits
between BAO (step 284) and the supercluster rung (step 288), separated by
$\varphi$-scaled voids from neighboring $w$-bubbles. The cascade direction is
not a spatial direction *within* our universe — it is the direction **along
which universes are spaced**. The proposal: the third spatial dimension of a
bubble's interior geometry *is* the cascade axis, internalized — the direction
along which the bubble is bounded between its two adjacent steps.

$$\boxed{3 = \underbrace{2}_{\text{SO(2) doublet axes}} + \underbrace{1}_{\text{cascade/string axis}}}$$

### 2.3 Why two fluids (and not more)

The counting $N_{\text{dim}} = N_{\text{fluids}} + 1$ would give 4 dimensions
for three fluids, so the fluid count must itself be grounded. The de-resonance
principle supplies the ground: multi-scale structure requires an irrational
ratio to avoid resonance collapse. **One field has no ratio at all; two fields
have exactly one** — which can be maximally irrational ($\varphi$). Two fluids
is the *minimal* structure supporting a de-resonant attractor. Whether larger
doublet counts are forbidden or merely unrealized in our sector is an open
question (§6); the minimal reading is that nature occupies the smallest
de-resonant possibility, and the smallest possibility gives $2 + 1 = 3$.

### 2.4 Consequence: $\xi$ becomes fully internal

With $3 = 2 + 1$ derived,

$$\xi = \varphi^{\,2 \times (2+1)}$$

every integer in the exponent traces to the two-fluid structure itself. The
$\xi$ derivation no longer imports anything from observation; the TOE's
parameter inventory loses its last dimensional input. The empirical content
(flat rotation curves, $\xi \approx 17.944$ vs. calibrated $\approx 18$) is
unchanged — what changes is that the 3 stops being a premise and becomes a
theorem-candidate.

---

## 3. The Spheroid Bubble

### 3.1 Wake interference of perpendicular fields

Both fluids leave wakes in the medium — the verified wake-wave mechanism
(`consciousness-from-phi.md` §1.3): perturbations in
$\varepsilon = E_Y - \varphi E_I$ propagate at the local wave speed $c(r)$ with
$\varphi$-scaled spacing, reflect, and feed back on their source. Because the
two fluids are perpendicular axes of the doublet, their wake systems form **two
mutually perpendicular interference patterns** filling the bubble.

### 3.2 The bounded envelope is an oblate spheroid

A bubble occupies the interval between two adjacent cascade steps. Wake energy
emitted while the string traverses that interval propagates a finite distance
before the bubble's initial conditions freeze (the Qi gate engages at
$r = \varphi^{-1}$, $a \approx 0.051$). The reachable region — extended along
the doublet plane, bounded above and below along the string by the step
separation — is an **oblate spheroid**: flattened along the cascade axis,
extended across the two fluid axes. The universe is not a sphere on the string;
it is a lens.

The Wu Xing bubble (step 285, $\sim 191$ Mpc comoving, 98% of the observable
volume) thereby acquires a *shape* for the first time, and with it a
**preferred geometric axis**: the short axis is the string direction.

### 3.3 Flattened in-universe structure

The superposition of two coherent perpendicular wake systems has a
distinguished symmetry plane — the midplane — where path lengths from the two
systems match. For in-phase components this is the central antinode:

$$I(\Delta r) = 4 I_0 \cos^2\!\left(\tfrac{k\,\Delta r}{2}\right), \qquad \Delta r = 0 \;\Rightarrow\; I = 4 I_0$$

Structure condenses where interference is constructive — the condensation
threshold $\theta_{\text{cond}}$ is crossed there first (catalytic template
mechanism). Matter therefore forms preferentially on a **plane**, not
uniformly through the spheroid: flattened in-universe structure is the
interference pattern of the two fluids, frozen in by condensation.

---

## 4. The Phase Fork: One Sheet or Two?

The character of the central plane depends on the **relative phase of the two
wake systems**, which is set by the conversion coupling. This is the idea's
first derivation problem — and it forks the prediction.

### 4.1 The naive sign: anti-phase

Mass-conserving conversion drives the two fields in opposite directions:

$$\partial_t E_Y \supset +\,\omega_0\, g(q)\,\varepsilon, \qquad \partial_t E_I \supset -\,\omega_0\, g(q)\,\varepsilon/\varphi$$

A positive $\varepsilon$ fluctuation feeds $E_Y$ and drains $E_I$: the two
wakes are emitted **anti-phase** ($\Delta\phi = \pi$). Two anti-phase sources
have a **node on the midplane** and first antinodes displaced symmetrically:

$$I(\Delta r) = 2 I_0 \left[1 - \cos(k\,\Delta r)\right] \;\Rightarrow\; \text{antinodes at } \Delta r = \pm \lambda/2$$

### 4.2 The two branches

| Branch | Interference geometry | Structure morphology | Observational reading |
|--------|----------------------|----------------------|----------------------|
| **In-phase** ($\Delta\phi = 0$) | Central antinode | **One** dominant midplane sheet | The Local Sheet *is* the bubble midplane |
| **Anti-phase** ($\Delta\phi = \pi$) | Central node, flanking antinodes | **Paired sheets** separated by $\lambda/2$, central void | The Local Sheet has a symmetric counterpart across a void — searchable in LSS catalogs |
| Quadrature ($\Delta\phi = \pi/2$) | Displaced antinode | Single sheet displaced from midplane by $\lambda/8$ | Intermediate case; off-center observers |

Because wake spacing follows $\varphi$-ratios, the paired-sheet separation in
the anti-phase branch is itself $\varphi$-scaled — successive sheet pairs at
$\varphi$ multiples of the fundamental wake wavelength, a signature
distinguishable from generic filamentary structure.

### 4.3 Deciding the branch

The phase relation is a property of the SO(2) conversion structure and can be
measured **numerically, today, with existing code**: initialize a two-bubble
configuration (`run_two_bubble_fast.py`), and measure the wake
cross-correlation $\langle \delta E_Y \, \delta E_I \rangle$ as a function of
separation. Its sign at small lag is the relative phase: negative $\Rightarrow$
anti-phase branch (paired sheets), positive $\Rightarrow$ in-phase branch
(single sheet). This is prediction W1 (§5) — a day-one experiment requiring no
new code paths.

---

## 5. Falsifiable Predictions

| # | Prediction | Method | Expected result | Status |
|---|-----------|--------|-----------------|--------|
| **W1** | The $E_Y$–$E_I$ wake cross-correlation has definite sign at small lag | Two-bubble PDE runs; cross-correlate wake perturbations vs. separation | Sign selects the §4.2 branch (negative: paired-sheet) | **Testable now** — existing scripts |
| **W2** | Large-scale structure is weakly anisotropic at scales approaching the bubble diameter | Tomographic $P(k)$ / void statistics vs. angle from a candidate axis | The $\ln\varphi$ wake period modulates with polar angle; anisotropy axis = bubble short axis | Testable with DESI/Euclid |
| **W3** | The W2 anisotropy axis coincides with the CMB $\ell < 5$ preferred axis | Cross-probe: LSS anisotropy axis vs. quadrupole–octopole alignment axis | Two independent probes, one direction | Testable with existing data |
| **W4** | (Anti-phase branch only) A paired-sheet counterpart to the Local Sheet exists across a void | LSS catalog morphology search at $\varphi$-scaled separations | Parallel sheet at predicted separation; central void between | Conditional on W1 |

Predictions W2–W4 are consequences of the spheroid geometry; W1 is the gate —
it selects which version of the mechanism nature uses and costs nothing but
compute.

---

## 6. Open Derivations

1. **The internal→physical axis map.** The perpendicularity of $E_Y$/$E_I$ is
   exact in field space (the SO(2) doublet). Mapping those internal axes onto
   two *physical* spatial axes — presumably through wake propagation along the
   fluids' segregated gradients during bubble formation — is the derivation
   that converts the 2+1 counting from accounting into geometry.
2. **The two-fluid phase relation.** §4 derives the fork from the sign
   structure of the conversion term, but the full SO(2) coupling (including
   reactive/quadrature components) must be computed from the dual-real PDE to
   fix $\Delta\phi$ from first principles rather than by fork.
3. **The spheroid ellipticity.** Set by the emission history: the residence
   time $\tau(r)$ diverges as $r \to \varphi$, so late wakes dominate; the
   resulting eccentricity of the bubble is computable from $c(r)$ and the
   string trajectory and feeds directly into W2's predicted anisotropy
   amplitude.
4. **Fluid-count uniqueness.** §2.3 grounds two fluids as the minimal
   de-resonant structure; whether three-fluid sectors are forbidden (ratio
   incompatibility) or merely unobserved remains open.

---

## 7. Epistemic Boundaries

### Supported by Verified Physics

- SO(2) doublet structure of the two fluids; perpendicularity of the field
  axes (dual-real formulation)
- Wake-wave mechanism with $\varphi$-scaled spacing; string-wake feedback loop
- The Wu Xing bubble at step 285; neighboring $w$-bubbles beyond the horizon
- The imported status of the 3 in $\xi = \varphi^6$ (this is a gap in the
  existing text, not new physics)

### Plausible Hypothesis (test exists)

- $3 = 2 + 1$ dimension counting; $\xi = \varphi^{2\times(2+1)}$ fully internal
- The bubble as oblate spheroid bounded between cascade steps
- Flattened structure as frozen wake-interference plane
- The phase fork (single vs. paired sheets), decidable by W1

### Speculative (no current test design)

- The internal→physical axis identification (§6.1)
- Fluid-count minimality as a selection principle (§6.4)
- Quadrature-branch displaced-plane morphology

### Not Supported

- Any claim that dimensionality has been *derived* to date — this document is
  the candidate derivation, pending §6 and the W1 measurement
- Any claim that the Local Sheet is established as the bubble midplane (or one
  of a pair) — it is the natural observational reading, not a confirmed one

---

## References

- `xi-derivation.md`: the $\xi = \varphi^6$ derivation and its imported 3
- `dimensionful-cascade.md`: the 292-step cascade; Wu Xing bubble at step 285
- `consciousness-from-phi.md` §1: pinch point, wake waves, string-wake loop
- `de-resonance-principle.md`: $\varphi$ as maximal de-resonance
- `run_two_bubble_fast.py`, `run_two_bubble_verification.py`: W1 test infrastructure
- `observational_constraints.md` §4: CMB $\ell < 5$ preferred-axis analysis (W3)
