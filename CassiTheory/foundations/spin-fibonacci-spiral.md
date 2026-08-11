# Spin as Fibonacci Spiral Winding: The SO(2) Doublet Fractal

## Status: Derived (conditional on the doublet postulate + pitch convention + the minimal-span principle)—August 2026

## Abstract

Spin is the accumulated SO(2) winding of the $(E_Y, E_I)$ doublet along a
radial Fibonacci spiral—the geometric structure that a condensed standing
wave assumes between coherence-budget collapse events. Moving radially
outward from a particle's center to its boundary, the conversion term
continuously rotates the Yang-Yin arrow in the internal doublet plane, tracing
a logarithmic spiral with $\varphi$-scaled pitch. The total accumulated
rotation divided by $2\pi$ is the spin. The physical state is the Yang/Yin
doublet, which carries the half-angle of the spiral
phase: its internal winding is quantized to integer or half-integer values,
spin-$1/2$ being the doublet's fundamental representation (one $\pi$-advance
of the pair per rung, $4\pi$ physical periodicity): the doublet's two
components are anchored one rung apart by the equilibrium ratio
$E_Y = \varphi E_I$, so the fundamental fermion is the **minimal doublet**,
spanning the minimal nonzero rung interval $\Delta n = 1$ (§2.3). Spin-$1$
is a full doublet cycle (two rungs, gauge boson), spin-$2$ two doublet
cycles (composite SO(2) excitation—no fundamental graviton); the
half-integer tower beyond $1/2$ folds onto the fermion span plus integer
gauge cycles and is excluded as fundamental by decomposition (§2.4). The nested spirals
across all supporting cascade rungs form a self-similar Fibonacci fractal.
Spin-statistics emerge from the parity of the winding number. The prediction:
particle form factors $F(q^2)$ carry the same $\ln\varphi$-periodic imprint as
the cosmological $P(k)$—testable in scattering data.

---

## 1. What a particle looks like between collapses

The proton coherence budget (`proton-coherence-budget.md`) established *how
long* a condensed standing wave survives. The quantum measurement derivation
(`quantum-measurement-derivation.md`) established *how superpositions decohere
into single outcomes*. Neither addressed the question: **what geometric
structure does the field adopt while it persists?**

The condensate is not a featureless blob. The conversion term

$$\text{conv} = -\lambda(E_Y - \varphi E_I)$$

continuously rotates the $(E_Y, E_I)$ doublet vector in its internal SO(2)
plane. At each spatial point, the field has a direction—an angle $\Theta$
in the doublet plane—and moving radially outward from the condensate's
center, $\Theta$ accumulates rotation. The trajectory is a **logarithmic
spiral**:

$$\boxed{\Theta(r) = \Theta_0 + \frac{2\pi}{\ln\varphi} \cdot \ln\!\left(\frac{r}{\ell_n}\right)}$$

where $\ell_n$ is the particle's cascade scale and the pitch $2\pi/\ln\varphi$
is set by the same de-resonance constant that structures every other scale in
the framework: one full rotation ($2\pi$) per cascade rung ($\Delta\ln r =
\ln\varphi$). This rung-to-angle mapping is the **coordinate postulate**
(Asserted pitch convention $\Theta = 2\pi n$,
`foundations/spiral-dynamics.md` §1.1)—the geometry on which the spin
quantization of §2 rests. The angle $\Theta$ is the phase of a single doublet
component; the physical state, the two-component doublet, carries the
half-angle $\Theta/2$ and therefore advances $\pi$ per rung, completing its
full SO(2) cycle every two rungs (§2.1). "One rung $= 2\pi$" and "two rungs
$=$ one full doublet cycle" are the same convention in the single-component
vs doublet viewpoint (boxed unified convention, §2.1). The *dynamical*
rotation rate is a separate,
derived quantity: with the ratified conversion→expansion coupling the doublet
turns $\varphi^{-2} = 0.382$ turns per Hubble rung (pitch angle $\approx
11.34°$; azimuthal discriminator $|a_\theta/a_r| = 0.19880$)—08 §C.3,
[COMPUTED].

The logarithmic spiral is the **Fibonacci spiral**: each full turn multiplies
the radius by $\varphi$, and the spiral's growth follows the Fibonacci sequence
$r_{k+1}/r_k \to \varphi$ as $k \to \infty$.

**Crucial distinction—internal vs spatial spiral.** The spiral $\Theta(r)$
traces the doublet arrow's rotation in the **internal** $(E_Y, E_I)$ plane—
the abstract 2D space of field amplitudes, not physical 3D space. The doublet
angle $\Theta = \text{atan2}(E_I, E_Y)$ is defined at each spatial point
independently; the spiral parameter $r$ is the radial coordinate *in a
conceptual space* (cascade rung index mapped to length scale), not a spatial
radial coordinate. In the spiral formula of §1 the phase $\Theta$ is the
polar angle of a single component; the physical doublet state carries the
half-angle $\Theta/2$ (§2.1). This means:

- **In the internal space:** the doublet traces a perfect Fibonacci spiral
  (derived, §1).
- **In physical 3D space:** the spiral does NOT manifest as a visible spiral
  pattern in $E_Y$ or $E_I$ individually. The two-pole bubble PDE test (July
  2026, `two-fluid/run_pde_bubble_spiral.py`) confirmed this: the spatial angular power
  spectrum at the bubble poles shows $m=2$ (ellipsoid cross-section) dominance
  with no $m=5$ Fibonacci mode emergence, and angular phase tracking showed no
  detectable spiral rotation ($d\phi/dt \sim 1.5\times 10^{-4}$ rad/step vs
  $\lambda = 0.02$ rad/step expected).
- **The Fibonacci spiral on the $\varphi$-ellipsoid** (5-arm emergence at poles,
  `visual-explainers/fibonacci_bubble_spiral.py`) is a **geometric** property
  of geodesics on the triaxial surface—it follows from the golden angle
  phyllotaxis $2\pi/\varphi^2$ on the $\varphi$-ellipsoid and does not require
  PDE dynamics to "produce" it. The PDE's role is to maintain the ellipsoid
  geometry; the pentagon follows from the geometry, not the dynamics.

---

## 2. Quantization from the doublet structure

### 2.1 The doublet winding is spin

The total accumulated rotation from the condensate's core ($r \approx
\ell_{n-\Delta n}$) to its boundary ($r \approx \ell_n$) is

$$\Delta\Theta = \frac{2\pi}{\ln\varphi} \cdot \ln\!\left(\frac{\ell_n}{\ell_{n-\Delta n}}\right) = 2\pi \cdot \Delta n$$

where $\Delta n$ is the number of cascade rungs the pattern's spiral spans
internally and $\Theta$ is the phase of a single doublet component (pitch
convention, §1: $2\pi$ per rung). The spin is not this single-component
winding, however—it is the winding of the physical state, the Yang/Yin
doublet.

**The doublet carries the half-angle.** The physical field is the
two-component doublet

$$\boxed{(\Psi_Y, \Psi_I) = \bigl(r^{1/2}\, e^{i\Theta/2},\; r^{-1/2}\, e^{i\Theta/2}\bigr)}$$

Each component carries the half-angle $\Theta/2$, with amplitudes the
square-root weights of the ratio field $r = E_Y/E_I$. The doublet is the
square root of the single-component phase evolution, in the same sense that a
spinor is the square root of a rotation. Its internal phase

$$\vartheta = \frac{\Theta}{2} \qquad\Longrightarrow\qquad \Delta\vartheta = \pi\,\Delta n$$

advances $\pi$ per rung—the **half-angle**—and the spin is the doublet's
internal winding measured in its own full cycles:

$$\boxed{s = \frac{\Delta\vartheta}{2\pi} = \frac{\Delta\Theta}{4\pi} = \frac{\Delta n}{2}}$$

**Why half-integers exist: the spinor property.** A single component is
single-valued: $\Theta \to \Theta + 2\pi$ (one rung) returns it to itself, so
single-valuedness alone quantizes winding to integers only. The doublet is
the physical state, and a single-component $2\pi$ flips its overall sign:

$$\Psi(\Theta + 2\pi) = -\Psi(\Theta), \qquad \Psi(\Theta + 4\pi) = +\Psi(\Theta)$$

[COMPUTED—`computations/spin_doublet_half_angle.py`: $\Psi(\Theta+2\pi)/
\Psi(\Theta) = -1$ exactly; $\Psi(\Theta+4\pi)/\Psi(\Theta) = +1$ exactly; the
single component returns $+1$ under $\Theta \to \Theta+2\pi$.]

The doublet is anti-periodic under a single-component $2\pi$ (one rung) and
returns to itself only after $4\pi$ (two rungs). This is exactly the spinor
transformation property $\psi(\mathbf{r}) \to -\psi(\mathbf{r})$ under a
$2\pi$ rotation: the half-rung subdivision of the cascade is the pair's
$\pi$-rotation per rung, not a winding-number postulate. The doublet winding
therefore admits

$$s \in \{0, \tfrac{1}{2}, 1, \tfrac{3}{2}, 2, \ldots\}$$

with the half-integers the doublet's fundamental windings and spin-$\tfrac12$
the doublet's fundamental (two-component, angle-halving) representation:
fermions are two-fluid doublets.

**Unified convention.** "One rung $= 2\pi$ of phase" and "$P_\parallel = 2$
rungs per full SO(2) cycle" (`consciousness/chakras-as-cascade-bubbles.md`
§5) are the same statement in two viewpoints: a single component advances
$2\pi$ per rung, while the doublet—the physical state—advances $\pi$ per rung
and completes its full SO(2) cycle every two rungs:

$$\boxed{\text{1 rung} = 2\pi\ \text{(single-component phase)} = \pi\ \text{(doublet internal phase)};\qquad \text{2 rungs} = \text{one full doublet SO(2) cycle}}$$

$$\boxed{\text{Inputs: (1) the pitch convention—a single component's phase advances } 2\pi \text{ per cascade rung (asserted coordinate postulate, } \text{foundations/spiral-dynamics.md §1.1}\text{); (2) the doublet postulate—the physical state is the } (\Psi_Y, \Psi_I) \text{ doublet carrying the half-angle, the spinor (square-root) representation of the single-component rotation; (3) the conversion term's continuous rotation of the doublet (unified Lagrangian). Conditional on these, the half-integer quantization and } s = \Delta n/2 \text{ follow; the mapping of spin values to specific particles remains Hypothesized (§2.2, §7).}}$$

### 2.2 The four observed values from doublet winding

The spin values follow from the doublet's half-angle structure (§2.1):
$s = \Delta n/2$ with $\Delta n$ the rung span of the single-component
phase, equivalently $s = \Delta\vartheta/2\pi$ with $\Delta\vartheta$ the
doublet's internal phase advance. The cascade's natural spans are the
half-cycle and full-cycle steps of the doublet—$1$ rung (one $\pi$-advance)
and $2$ rungs (one full cycle).

| Spin $s$ | Span (rungs, $\Delta n$) | Doublet internal winding $\Delta\vartheta$ | Physical periodicity | Particle class | Example |
|:---:|:---:|---|---|---|---|
| $0$ | $0$ | None—scalar | $2\pi$ | Scalar boson | Higgs |
| $\frac{1}{2}$ | $1$ | $\pi$ (half the doublet cycle) | **$4\pi$** (spinor) | Fermion | Electron, quark |
| $1$ | $2$ | $2\pi$ (full doublet cycle) | $2\pi$ | Vector boson | Photon, W/Z, gluon |
| $2$ | $4$ | $4\pi$ (two doublet cycles) | $2\pi$ | Tensor boson | Composite graviton (SO(2) excitation) |

The half-integer spin of fermions arises from the doublet's half-angle: each
rung advances the pair's internal phase by $\pi$—half its full cycle—so the
minimal non-trivial doublet state carries $s = 1/2$. The "half-rung
subdivision" of the cascade is this $\pi$-rotation per rung; it is a
consequence of the doublet representation, not a postulate about winding
numbers. Restoring the fermion's original field configuration requires a
**double** physical rotation ($4\pi$, two rungs), the geometric origin of the
spinor transformation property
$\psi(\mathbf{r}) \to -\psi(\mathbf{r})$ under $2\pi$ rotation—and of the
Pauli exclusion principle, which follows from the resulting exchange phase
(§4).

### 2.3 The minimal doublet: why $s = \frac{1}{2}$

The half-angle structure of §2.1 fixes *how* winding maps to spin
($s = \Delta n/2$) but not *which* spans the cascade realizes. The observed
fundamental spectrum—$s = \tfrac{1}{2}$ fermions, $s = 1$ gauge bosons, and
the composite $s = 2$ graviton—is the claim that the realized spans are
$\Delta n \in \{1, 2, 4\}$. The minimality of the fermion's span closes part
of that claim.

**The doublet is an adjacent-rung object.** The conversion term's fixed
point is the equilibrium ratio

$$E_Y = \varphi E_I$$

and the cascade step is the same ratio of scales, $\ell_{n+1}/\ell_n =
\varphi$: one rung. The two components' equilibrium magnitudes are therefore
separated by exactly one cascade step, so the doublet's defining structure is
the **adjacent-rung pair**—the Yang component anchored one rung above the
Yin component (one Yang-dominant rung and one Yin-dominant rung, the
self-contained Qi condensate of `consciousness/chakras-as-cascade-bubbles.md`
§5.1). The fundamental doublet state spans its own defining interval: the
minimal nonzero rung interval,

$$\boxed{\Delta n = 1 \qquad\Longrightarrow\qquad s = \frac{\Delta n}{2} = \frac{1}{2}}$$

with $\Delta\vartheta = \pi$ (one half-cycle of the doublet, §2.1). The
fixed-point imbalance $\alpha_0 = \pi/\rho = \varphi^{-3}$ is a *different*
object: a dimensionless ratio of the two fluids' energy densities. Its scale
reading is three rungs—$\varphi^{-3} = \ell_{n-3}/\ell_n$, the dephasing-noise
separation $\sigma = \ell_{\mathrm{Pl}}/\varphi^3$ at rung $-3$
(`foundations/bubble-lattice-fabric.md` §2)—but that is the separation of the
two fluids' background coherence profiles, not the doublet's own span
[COMPUTED—`computations/spin_doublet_minimal_span.py` §3:
$\log_\varphi(\varphi) = 1$ rung vs $\log_\varphi(\varphi^3) = 3$ rungs].

Spin-$\tfrac{1}{2}$ is the minimal half-integer: the minimal nonzero span of
the discrete cascade produces the minimal nonzero spin of the doublet
representation. The fundamental fermion is the **minimal doublet**.

**The minimal-span principle.** The doublet's internal phase is
$2\pi$-periodic, so a full cycle of winding (2 rungs) is the gauge-boson
content—a *separate* excitation, not an attribute of a fundamental fermion.
The load-bearing selection rule is: **a fundamental state realizes the
minimal member of its winding class—it carries no redundant full-cycle
winding**; equivalently, a fundamental state does not decompose into the
fermion span plus integer gauge cycles. This is the same minimality that
excludes a fundamental graviton ($\Delta n = 4 = 2 + 2$, §2.4), stated once
as an input rather than per-particle.

**Tier.** Conditional on the doublet postulate + pitch convention (§2.1),
the equilibrium ratio $E_Y = \varphi E_I$ (conversion-term fixed point,
`foundations/unified-lagrangian.md`), and the minimal-span principle, the
fundamental fermion spin $s = \tfrac{1}{2}$ is **Derived**. The
identification of the electron/quark doublet with this minimal state remains
part of the Hypothesized particle mapping (§2.2).

### 2.4 Why no fundamental spin-$\frac{3}{2}$?

The spinor structure of §2.1 admits every half-integer: an internal winding
$\Delta\vartheta = 3\pi$ (a spin-$\frac{3}{2}$ doublet over a $3$-rung span)
is a consistent doublet state, exactly as $\Delta\vartheta = \pi$ is. Two
candidate exclusions were tested; one does not close, one does.

**The parity structure does not exclude $\Delta n = 3$.** The doublet
boundary phase after $\Delta n$ rungs is $\pi\,\Delta n \bmod 2\pi$—a
function of $\Delta n \bmod 2$ alone. The rungs carry only two doublet phase
states, $0$ and $\pi$: the sign-alternating lattice of adjacent-rung
opposite phases (`consciousness/chakras-as-cascade-bubbles.md` §12.1). This
folds the half-integer tower into two parity classes: odd $\Delta n$
(spinor, boundary phase $\pi$) and even $\Delta n$ (boson, boundary phase
$0$). $\Delta n = 3$ sits in the **same** class as $\Delta n = 1$—both odd,
both fermionic under the exchange parity $(-1)^{2s}$ (§4.1)—so
spin-statistics parity does not exclude it. Nor does the microcascade mirror
(`foundations/microcascade-mirror.md`): its scale reflection $n \to -n$
preserves every span ($\Delta n \to \Delta n$), so it selects no span at all
[COMPUTED—`computations/spin_doublet_minimal_span.py` §2, §5: $\pi\cdot 3
\equiv \pi \pmod{2\pi}$; rung phase sequence $0, \pi, 0, \pi, \ldots$; spans
reflection-invariant].

**What does exclude it: decomposition (minimal-span principle).**
$\Delta n = 3$ decomposes into the two fundamental atoms of §2.3,

$$\Delta n = 3 = 1 + 2:$$

the minimal fermion span (one half-cycle) plus one full doublet cycle (the
gauge span). The winding content of a $3$-rung state is exactly a fermion
followed by a gauge cycle—a composite, not a new fundamental. The same
decomposition removes every span beyond the minimal members of the two
parity classes:

$$\boxed{\Delta n \in \{1, 2\}: \quad s = \tfrac{1}{2}\ \text{(fermion—minimal nonzero span)},\qquad s = 1\ \text{(gauge boson—minimal closing span)}}$$

with $s = 0$ the trivial span ($\Delta n = 0$) and all higher spins
composite: $s = \tfrac{3}{2} = \tfrac{1}{2} + 1$ (fermion plus one gauge
cycle; baryon resonances like $\Delta(1232)$, orbital angular momentum added
to constituent quark spins), $s = 2 = 1 + 1$ (the composite graviton,
§2.2). The earlier "no Fibonacci closure" phrasing is sharpened: the
Fibonacci decomposition of $3$ is exactly the fermion-plus-cycle sum
($3 = F_4 = F_2 + F_3 = 1 + 2$)—there is no Fibonacci way to write $3$ as a
single atom [COMPUTED—`computations/spin_doublet_minimal_span.py` §4].

**Tier.** The exclusion of a *fundamental* spin-$\tfrac{3}{2}$ is **Derived
conditional** on the minimal-span principle of §2.3. The empirical claim—all
observed spin-$\tfrac{3}{2}$ states are composites—stands as observation.
What would stress the argument: a fundamental spin-$\tfrac{3}{2}$ state
(e.g., a gravitino) would require either a failure of the minimal-span
principle or a mechanism making a $3$-rung winding irreducible.

---

## 3. The Fibonacci spiral fractal

### 3.1 Self-similarity across the cascade

The radial spiral at the particle's own rung ($n$) does not exist in
isolation. It is the **visible surface** of a nested structure: the same
spiral pattern, with the same pitch, repeats at every supporting cascade rung
from Planck ($n=0$) to the particle's boundary ($n$):

$$\Theta_i(r) = \Theta_0 + \frac{2\pi}{\ln\varphi} \cdot \ln\!\left(\frac{r}{\ell_i}\right), \qquad i = 0, 1, \ldots, n$$

At each rung $i$, the spiral begins where the previous rung's spiral ended—
the core at $i$ connects continuously to the boundary at $i-1$. The cumulative
structure is a **self-similar fractal**: zooming in by $\varphi$ reveals one
fewer rung of accumulated winding, but the local spiral geometry is identical.

The Hausdorff dimension of this fractal follows from the Fibonacci scaling:
$D = \ln(N)/\ln(1/r)$ where $N$ is the number of self-similar copies per
scale factor $r$. With one full spiral turn per $\varphi$-scaling, $D =
\ln(\varphi)/\ln(\varphi) = 1$—the spiral is a **curve** in the doublet
plane, but its embedding in physical 3D space + internal SO(2) gives the
composite structure a higher effective dimension.

**Figure:** `visual-explainers/fractal_zoom.png`—three-panel fractal zoom: (A) cascade overview with φ-spaced rings, identical I(ρ)=2[1−cos(2πρ)] per ring, Fibonacci spiral overlay; (B) single Qi bubble deep zoom—elliptical φ:1 cross-section, Qi coherence texture, two five-arm spiral poles; (C) pole ultra-zoom—five Fibonacci spiral arms via golden-angle phyllotaxis (2π/φ²), nested sub-bubble. Demonstrates infinite self-similarity: zoom by φ → identical structure (`visual-explainers/fractal_zoom.py`).

### 3.2 The Fibonacci sequence in the spiral arms

The spiral's radial coordinate at angle $\theta$:

$$r(\theta) = \ell_n \cdot \exp\!\left(\frac{\ln\varphi}{2\pi} \cdot (\theta - \Theta_n)\right)$$

Sampling at full turns ($\Delta\theta = 2\pi$—one cascade rung per turn) gives
$r_{k+1}/r_k = \varphi \approx 1.618$; sampling at quarter-turns
($\Delta\theta = \pi/2$) gives $r_{k+1}/r_k = \varphi^{1/4} \approx 1.128$:

$$r_{k+1} / r_k = \varphi^{1/4} \approx 1.128, \quad r_{k+4} / r_k = \varphi \approx 1.618$$

The radial sequence $r_k = \ell_n \varphi^k$ from full-turn sampling follows
the Fibonacci sequence (scaled by $\ell_n$) in the limit $k \to \infty$,
because $\varphi^k = F_k \cdot \varphi + F_{k-1}$ (exact, by Binet) and the
full-turn samples land on cascade rungs.

The observed Fibonacci spirals in phyllotaxis (sunflowers, pinecones) are
the **macroscopic signature** of the same fundamental spiral structure: the
Qi field's ordered condensation at biological cascade rungs ($n \approx
142$–$168$, cellular to organism) inherits the same SO(2) winding geometry
from the fundamental cascade. Biology doesn't "choose" Fibonacci spirals—
the field geometry that condenses into living structure already has them.

---

## 4. Spin-statistics from winding parity

### 4.1 Exchange as a physical $2\pi$ rotation

To exchange two identical particles, one particle is rotated around the other by $\pi$
in physical space (half a full circuit). This corresponds to a $2\pi$ rotation
of the coordinate system of one particle relative to the other—the full
relative angular displacement for an exchange. Under this $2\pi$ relative
rotation, the internal SO(2) doublet of the exchanged particle accumulates a
phase:

$$\psi \to e^{i \cdot s \cdot 2\pi} \cdot \psi = (-1)^{2s} \cdot \psi$$

For the doublet, a single-component $2\pi$ is exactly the sign flip of §2.1,
so this exchange phase is the spinor phase of the doublet's half-angle
structure.

For integer $s$: $(-1)^{2s} = +1$ → symmetric wavefunction → Bose-Einstein.
For half-integer $s$: $(-1)^{2s} = -1$ → antisymmetric → Fermi-Dirac.

The spin-statistics theorem is not an additional postulate; it is the **parity
of the internal SO(2) winding** evaluated at the exchange rotation. Half-turn
winding ($s = 1/2$, $2s = 1$) gives an odd exchange phase; full-turn winding
($s = 1$, $2s = 2$) gives an even exchange phase.

### 4.2 The Pauli exclusion principle geometrically

Two identical spin-$1/2$ particles cannot occupy the same quantum state because
their internal doublet arrows, each requiring a $4\pi$ physical rotation to
close, are incommensurate when placed at the same spatial point. The
antisymmetry of the wavefunction is the **boundary condition** that results
from forcing two $4\pi$-periodic structures into the same cascade rung: they
can only coexist if their internal phases are opposite, which requires
opposite spin projection ($m_s = +1/2$ and $-1/2$). Same spin projection →
phase conflict → Pauli exclusion. The exclusion principle is the no-go
theorem for co-located in-phase Fibonacci spirals.

---

## 5. Testable prediction: form factor log-periodicity

If the particle's internal structure is a Fibonacci spiral fractal, its
electromagnetic form factor—the Fourier transform of the charge distribution—
must carry the spiral's periodicity:

$$\boxed{F(q^2) = F_0(q^2) \cdot \Big[1 + A \cdot \cos\!\big(2\pi \cdot \tfrac{\ln(q/\Lambda_{\text{QCD}})}{\ln\varphi} + \delta\big) + \cdots\Big]}$$

where $A$ is the spiral modulation amplitude, $\delta$ is a phase offset, and
higher harmonics ($2\ln\varphi$, $3\ln\varphi$, $\ldots$) correspond to
contributions from deeper cascade rungs.

| Observable | Prediction | Status |
|---|---|---|
| Proton $F_1(q^2)$ (Dirac FF) | Log-periodic oscillations at $\Delta(\ln q) = \ln\varphi \approx 0.4812$ | Testable with JLab/ELC $ep$ scattering data |
| Proton $F_2(q^2)$ (Pauli FF) | Same period, different phase (different spiral arm sampled) | Joint fit of $F_1$ and $F_2$ |
| Neutron $F_1(q^2)$ | Amplitude differs (neutral charge reduces spiral contrast) but same period | Testable with deuteron/quasi-elastic data |
| Pion form factor $F_\pi(q^2)$ | Period breaks at $q \sim \Lambda_{\text{QCD}}$ (pion's cascade depth is shallower) | JLab 12 GeV data |
| $\Delta(1232)$ transition FF | Amplitude enhanced—spin-3/2 resonance has additional orbital winding | CLAS/MAID analysis |

The prediction mirrors the cosmological $P(k)$ prediction (`predictions/falsifiable-predictions.md`
§5)—same period, same $\varphi$, same underlying mechanism, different probe.
If detected, it is a unique Cassi signature orthogonal to perturbative QCD.

---

## 6. Relation to the trifecta

| | Proton decay | Annihilation | Measurement | **Spin** |
|---|---|---|---|---|
| **What's attacked** | All 92 rungs, random | All 92 rungs, anti-phase | 1 rung, phase-matched | **Winding across rungs, continuous** |
| **What sets timescale** | Cascade product | Single-cycle | Single-cycle | **Cascade pitch $2\pi/\ln\varphi$** |
| **What's quantized** | N/A (erosion) | N/A (binary) | Born rule $|\alpha|^2$ | **SO(2) doublet winding $s = \Delta\vartheta/2\pi = \Delta n/2$** |
| **What persists** | Proton itself | Nothing | Post-collapse branch | **Spiral geometry of the surviving branch** |

Spin is what the field does **between** the events—the geometric structure of
the condensate that the coherence budget protects. The proton lives $10^{910}$
years because no random perturbation finds all 92 rungs simultaneously; while
it lives, its quarks carry spin-$1/2$ because the internal SO(2) doublet winds
by $\pi$ from the QCD core to the proton boundary. Same cascade, same $\varphi$,
three different aspects of one field.

## 7. Epistemic boundaries

### Derived (from $\varphi$ + PDE + cascade)

- Logarithmic spiral trajectory of $(E_Y, E_I)$ in **internal** SO(2) doublet
  space: follows from the conversion term's continuous rotation and the
  $\varphi$-scaling of the cascade
- Spin-statistics from exchange-phase parity: $(-1)^{2s}$
- The spiral is in internal doublet space, not a spatial pattern in $E_Y$
  alone (confirmed by two-pole bubble PDE test, July 2026)

### Derived conditional (on the doublet postulate + pitch convention)

- Spin quantization to integer and half-integer values from the doublet's
  half-angle structure: a single component is single-valued (integer winding
  only); the doublet carries the half-angle and is anti-periodic under a
  single-component $2\pi$, which yields the half-integer windings.
  Spin-$\frac{1}{2}$ is the doublet's fundamental (two-component,
  angle-halving) representation; fermions are two-fluid doublets. Inputs:
  the asserted pitch convention $\Theta = 2\pi n$ per rung
  (`foundations/spiral-dynamics.md` §1.1) and the doublet postulate (§2.1).
- The unified rung/phase convention: 1 rung = $2\pi$ single-component phase
  = $\pi$ doublet internal phase; 2 rungs = one full doublet SO(2) cycle
  ($P_\parallel = 2$ of `consciousness/chakras-as-cascade-bubbles.md` §5)—
  the same statement in the single-component vs doublet viewpoint.

### Derived conditional (also on the minimal-span principle)

- $s = \frac{1}{2}$ as the fundamental fermion spin: the doublet is an
  adjacent-rung object (equilibrium ratio $E_Y = \varphi E_I$, one cascade
  rung of separation), so the minimal doublet spans the minimal nonzero rung
  interval $\Delta n = 1$; the minimal half-integer is the fundamental
  fermion's spin (§2.3). Inputs: §2.1 + the equilibrium ratio (conversion-term
  fixed point) + the minimal-span principle.
- No fundamental spin-$3/2$: the spinor structure admits $\Delta n = 3$, and
  neither the spin-statistics parity ($\Delta n = 3 \equiv \Delta n = 1
  \bmod 2$) nor the microcascade mirror (which preserves every span) excludes
  it—but $\Delta n = 3 = 1 + 2$ decomposes into the fermion span plus one
  gauge cycle, so under the minimal-span principle a fundamental $s = 3/2$ is
  composite, not fundamental (§2.4). The empirical absence of fundamental
  $s = 3/2$ states stands as observation.

### Hypothesized (mechanism specified, testable)

- Specific mapping of spin values to observed fundamental particles ($0$,
  $1/2$, $1$, $2$) from the doublet winding and the rung spans the cascade
  realizes (the spans $\{1, 2\}$ and their composites are Derived conditional
  on the minimal-span principle; the identification of specific particle
  species with them is Hypothesized)
- Form factor log-periodicity at $\Delta(\ln q) = \ln\varphi$
- Fibonacci spiral arm emergence at $\varphi$-ellipsoid poles (5 arms):
  **geometric**—follows from golden angle phyllotaxis on the triaxial
  surface, not from PDE dynamics (see `visual-explainers/fibonacci_bubble_spiral.py`)

### Speculative (consistent, no test design yet)

- Fibonacci spiral phyllotaxis as biological-cascade expression of the same
  SO(2) winding geometry
- Exact form factor modulation amplitude $A$ and phase $\delta$ from the
  spiral's core-boundary radial profile

---

## 8. References

- `foundations/proton-coherence-budget.md`—proton stability, cascade coherence
- `foundations/quantum-measurement-derivation.md`—measurement, Born rule, single-rung
- `foundations/why-three-dimensions.md`—spiral's Frenet-Serret frame, triaxial spheroid
- `foundations/dimensionful-cascade.md`—cascade table, $\Delta n$ spacings
- `predictions/falsifiable-predictions.md` §5—$\ln\varphi$-periodic $P(k)$
- `open-questions-cassi-answers.md`—Q7 (measurement), Q9 (proton), Q10 (spin)
- `visual-explainers/fibonacci_bubble_spiral.py`—Fibonacci spiral on $\varphi$-ellipsoid
- `visual-explainers/fractal_zoom.py`—fractal zoom: cascade self-similarity, φ-spaced rings, identical I(ρ)
- `computations/spin_doublet_half_angle.py`—doublet half-angle verification: sign flip per rung, full cycle per 2 rungs
- `computations/spin_doublet_minimal_span.py`—minimal doublet span: $\Delta n \to s$ mapping, parity classes, equilibrium-ratio anchoring ($E_Y = \varphi E_I$ vs $\alpha_0 = \varphi^{-3}$), decomposition $\{1, 2\}$ atoms, microcascade-mirror check
- `foundations/rung-offset-mechanism.md`—half-rung offsets, cell parities, sector-edge crossings
- `foundations/microcascade-mirror.md`—sub-Planckian cascade extension, scale reflection (spans preserved)
- `two-fluid/run_pde_bubble_spiral.py`—two-pole bubble PDE test (July 2026)
