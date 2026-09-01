# Cassi Physics: The Bubble Lattice at Every Scale

## Status: Synthesis—August 2026

## Abstract

Cassi is a proposed field framework organized around the declared scale-separation target $\varphi\approx1.618$. The canonical state uses two nonnegative density components conventionally labeled Yang ($E_Y$) and Yin ($E_I$); the canonical equations treat them as neutral components and use the **Asserted** C-class/framework convention $\lambda=0.1$ in named calculations. The implementation class default is $\lambda=0.02$ unless a caller passes a different value. The positive-root lift $\Psi^{(+)}=(\sqrt{E_Y},\sqrt{E_I})$ supplies coordinate diagnostics. A distinct optional regulated quantum sector quantizes the finite CassiFI complex-field configuration as a linear wavefunctional. **Hypothesized** geometric and phenomenological mappings organize selected coherence patterns.

---

# Part I—The Substrate

## 1. The Fractal Lattice

Zoom into a bubble and you find the same lattice again. A bubble is not a solid object—it is one scale of a repeating structure. Inside every bubble, more bubbles: smaller lattices, the same pattern, another turn of the spiral.

Zoom out, and the lattice you are inside is itself a bubble of a larger lattice. The pattern repeats at every scale, in both directions—it never bottoms out and never tops out. The framework's **Hypothesized** geometric construction treats this as a **nested lattice of bubbles**, each scale a zoom of every other; this is not a consequence of the canonical density PDE.

Within that **Hypothesized** geometry, each modeled bubble carries a proposed **five-arm Fibonacci spiral** at its poles, organized by the golden angle $2\pi/\varphi^2 \approx 137.5^\circ$. Count the arms and you find consecutive Fibonacci numbers—34 one way, 55 the other—because the golden angle is the one turn that never repeats exactly, so the spiral never locks into a smaller symmetry. Sunflowers, pinecones, and nautilus shells display the same phyllotaxis at their own scale; that analogy does not establish the proposed pole geometry. A sunflower is an observed instance of phyllotaxis, not evidence for the model's source.

The pattern is described by two nonnegative density components and their coherence structure. The framework conventionally labels them **Yang** ($E_Y$) and **Yin** ($E_I$). A **Hypothesized** phenomenological mapping may call Yang expansive or outward and Yin contractive or inward; the canonical PDE treats $E_Y$ and $E_I$ as neutral density components. For $\rho>0$, the optional positive-root coordinate lift $\Psi^{(+)}=(\Psi_0^{(+)},\Psi_1^{(+)})=(\sqrt{E_Y},\sqrt{E_I})$ supplies the amplitude-plane diagnostic $\theta_\Psi=\operatorname{atan2}(\Psi_1^{(+)},\Psi_0^{(+)})$ and the foundational spatial phase-current diagnostic $\mathbf{J}_\Psi=\Psi_0^{(+)}\nabla\Psi_1^{(+)}-\Psi_1^{(+)}\nabla\Psi_0^{(+)}=\rho\nabla\theta_\Psi$. The density-plane angle $\theta_d=\operatorname{atan2}(E_I,E_Y)$ and Stokes double angle $\Theta_S=\operatorname{atan2}(2\Psi_0^{(+)}\Psi_1^{(+)},E_Y-E_I)=2\theta_\Psi\pmod{2\pi}$ are distinct coordinates. The density-lattice diagnostic $\mathbf{J}_d=E_Y\nabla E_I-E_I\nabla E_Y=(E_Y^2+E_I^2)\nabla\theta_d=2\sqrt{E_YE_I}\,\mathbf{J}_\Psi$ has different units. A named spatial projection records a chosen direction; physical-current and inter-rung transport interpretations require a separate constitutive map and remain **Hypothesized**.

The canonical conversion relaxes the local ratio $r=E_Y/E_I$ toward $\varphi$. Spatial responses in the deviation $\varepsilon=E_Y-\varphi E_I$ can form patterns in simulations. Supplied adjacent-rung carriers have an exact phase-staggered beat envelope, while interpreting its antinodes and nodes as physical bubbles and voids remains a **Hypothesized** phenomenological mapping. The distinct default CassiCosmos second-order wave branch separates into a massless density mode and an imbalance mode with threshold $\Omega_g=\varphi\omega_{0,\mathrm{wave}}$; a supplied drive at $\Omega_*=\varphi^{3/2}\omega_{0,\mathrm{wave}}$ gives $k_\rho/k_\epsilon=\varphi$ and additively spaced layers. The current source path selects no such drive, and phase staggering alone opens no transfer gap. The independently defined Qi gate closes as $q$ increases and opens as $q$ decreases; associating high-$q$ pockets with bubbles and low-$q$ regions with voids requires the same separate physical mapping.

Coherence gates conversion: at high $q$ the gate closes and at low $q$ the gate opens. Reading these gate states as a bubble holding or a void churning belongs to the **Hypothesized** phenomenological mapping above. Where a spatial solution develops a coherent filament, a **Hypothesized** geometric mapping may call it a **condensed fluid string**—the proposed spine around which bubbles condense (source: `foundations/bubble-lattice-fabric.md`).

The recorded geometric bubble model has a definite shape: an **oblate triaxial spheroid** bounded along the named string, with axis ratio $\varphi$ in its Yang–Yin cross-section. Interpreting the long and short axes as Yang/outward and Yin/inward is a **Hypothesized** geometric mapping, not a canonical transport law. The named cross-section is a supplied staggered checkerboard of bubble and void sites, each bubble joined to its diagonal neighbors through saddles and separated from its axial neighbors by void barriers. Reusing this condensation field at every scale defines the nested geometric construction. The registered canonical and undriven second-order probes do not dynamically generate its multiplicative radial ring ladder.

The canonical fixed-point ratio is $r=E_Y/E_I=\varphi$. In the neutral density variables this is the balance condition of the rank-one relaxation. Interpreting the ratio as relative push and pull strength, or as the unique mechanism that preserves a nested pattern, is a **Hypothesized** phenomenological mapping.

The rest of this document unpacks that image into physics: the equations that govern the two fluids, the coherence gate that controls conversion, the geometric spiral used to organize the proposed scale sequence, the conditional dimensionful cascade that parameterizes scales from an external Planck anchor to an epoch-dependent horizon coordinate, and the specific phenomena to which the framework applies these constructions. Every claim carries a label: **Derived** (follows mathematically from the framework), **Calibrated** (anchored to an observation), **Mapped** (fitted or selected with ledgered provenance), **Hypothesized** (consistent and testable), or **Speculative** (framework-consistent with no test yet designed). **Creative** marks exploratory applications outside this evidence ladder.

---

## 2. Two Fluids and the Governing Equation

The canonical state comprises continuous nonnegative density components with values at every point of space, analogous to two coupled scalar density fields. The components are conventionally labeled Yang ($E_Y$) and Yin ($E_I$); those names carry no intrinsic transport direction. Their local ratio is $r=E_Y/E_I$. A **Hypothesized** phenomenological or geometric mapping may describe the components as expansive/outward and contractive/inward when interpreting a particular solution.

For a separate **Hypothesized** amplitude/action extension, the optional
positive-root coordinate lift $\Psi_0^{(+)}=\sqrt{E_Y}$ and
$\Psi_1^{(+)}=\sqrt{E_I}$ may be used. The attractor potential in that
extension is

$$
V_{\mathrm{attr}}=\frac{\lambda}{2}
\left((\Psi_0^{(+)})^2-\varphi(\Psi_1^{(+)})^2\right)^2.
$$

Here $\lambda=0.1$ is the **Asserted** C-class/framework convention used in
named attractor calculations; the implementation class default is
$\lambda=0.02$ unless a caller passes the named convention. This potential
alone specifies no amplitude evolution: an amplitude equation requires a
separately selected action or dissipative prescription. The optional action
construction in `foundations/unified-lagrangian.md` §1.1 uses a distinct
**Hypothesized** fourth-order coefficient $\kappa_4$; the canonical solver
reserves $\nu$ for velocity viscosity and $D$ for scalar-density diffusion.
Those coefficients are distinct from the canonical density conversion below.

In the density form used by the solvers, the canonical conversion term is

$$\boxed{\partial_t E_Y \supset -\lambda(1-q)(E_Y - \varphi E_I), \qquad \partial_t E_I \supset +\lambda(1-q)(E_Y - \varphi E_I)}$$

with $q$ the Qi coherence of section 3. The gated density pair conserves
$\rho=E_Y+E_I$ exactly and drives the local imbalance toward
$E_Y=\varphi E_I$; the separate **Hypothesized** amplitude-level
action/attractor representation supplies an optional field construction.

Writing $\kappa=\lambda(1-q)$, the canonical density conversion is

$$
\partial_t
\begin{pmatrix}E_Y\\E_I\end{pmatrix}_{\!\mathrm{conv}}
=\kappa
\begin{pmatrix}-1&\varphi\\1&-\varphi\end{pmatrix}
\begin{pmatrix}E_Y\\E_I\end{pmatrix}.
$$

This rank-one relaxation has eigenvalues $0$ and $-\kappa(1+\varphi)=-\lambda(1-q)(1+\varphi)$. It conserves $\rho=E_Y+E_I$ while generally changing $E_Y^2+E_I^2$; the canonical conversion is a density-plane relaxation rather than a norm-preserving $SO(2)$ generator.

### Why $\varphi$?

$\varphi$ is, in a precise arithmetic sense, the **most irrational number**: its continued fraction has all unit entries, and its best rational approximants converge unusually slowly. Rational frequency ratios can support resonant locking in suitable dynamical systems, but irrationality alone leaves the physical frequency ratios and dynamics unspecified and gives no guarantee of multiscale survival.

The **Hypothesized** de-resonance interpretation (`principles/de-resonance-principle.md`) motivates selecting $\varphi$ as the scale-separation constant. The canonical gated density equations declare the $\varphi$-line as their conversion target; convergence toward that target follows from the stated rank-one solver term and its assumptions. The discrete renormalization or physical flow interpretation remains **Hypothesized**.

**Epistemic status:** the canonical gated density equations are **Derived**
from the framework's postulate and declared solver structure. The separate
**Hypothesized** ungated amplitude action/attractor representation supplies
the corresponding $\varphi$-fixed-point structure. The de-resonance argument
for a physical attractor is **Hypothesized**.

---

## 3. Coherence and the Qi Gate

The push and pull are not balanced everywhere at every moment. Some regions are close to $\varphi$-balance; others are far from it. **Coherence** (written $q$, called **Qi** in the framework) is a bounded local diagnostic with $0\le q\le1$ under the stated normalization:

- At fixed density, $\varepsilon\to0$ approaches $q_{\mathrm{eq}}(\rho)=\rho^2/(\rho^2+\varphi^{-2})<1$; $q\to1$ requires both alignment with the golden-ratio line and $\rho\gg\varphi^{-1}$. Treating high $q$ as orderly structure, or mapping it to bubbles, atoms, cells, or thoughts, is a **Hypothesized** phenomenological interpretation.
- $q\to0$ is the low-density limit under the canonical diagnostic. The gate openness $(1-q)$ then approaches one, so the canonical conversion acts more strongly on the imbalance. Calling low-$q$ regions chaotic or voids, or saying that they cannot hold lasting structure, is a **Hypothesized** mapping, not a consequence of $q$ alone.

In the canonical equations, $q$ is a dimensionless local gate diagnostic defined by a **C / Asserted** constitutive choice under the reference normalization; the rational form and bare $\varphi^{-2}$ floor are not derived from $\varphi$ and the PDE. With the default instantaneous diagnostic, set $\rho=E_Y+E_I$, $\pi=E_Y-E_I$, and $s=\pi/\rho$. Then $\varepsilon/\rho=(\varphi^2s-\varphi^{-1})/2$ and
$$q(\rho,s)=\left[1+\left(\frac{\varphi^2s-\varphi^{-1}}{2}\right)^2+\frac{\varphi^{-2}}{\rho^2}\right]^{-1}.$$
Thus $q$ depends on density and composition; $q$ is not an independent gate dial at fixed $s$. The optional `qi_memory` closure replaces $\varepsilon^2$ by a history-filtered value and is outside this instantaneous identity. The canonical solver fields are dimensionless/reference-normalized. If $E_Y,E_I$ denote physical energy densities, use an external reference density $\rho_*$ (equivalently $e_Y=E_Y/\rho_*$ and $e_I=E_I/\rho_*$) so that the dimensionless diagnostic is evaluated consistently; no $\rho_*$ scale is derived. The bounds and reference-state arithmetic are **Derived conditional** on that definition and normalization. The broader language of coherence as an organizing strength belongs to the named phenomenological mapping.

### The gate: sign and consequences

Coherence does more than measure balance: it **gates** the conversion. In the governing equation, the gate appears as the factor $(1-q)$ multiplying the imbalance:

$$\text{conv} = -\lambda(1-q)\,\varepsilon, \qquad \varepsilon = E_Y - \varphi E_I$$

The gate's *openness* is $(1-q)$. When $q$ is low, the gate is **open** and conversion runs hard—the region churns, converting aggressively, unable to settle. When $q$ is high, the gate is **closed** and the system rests in balance.

The sign is established by the PDE tests of 2026-07-31 (`consciousness/trauma-as-frozen-gate.md` §10.4): when $q$ is low the gate is open and conversion runs hard; when $q$ is high the gate is closed. A low-coherence region is not frozen—it is unsettled.

Optional extensions assign the gate roles in cosmic expansion, modified
gravity, and human-scale phenomenology. The canonical PDE establishes the gate
sign and openness; conversion-to-expansion dynamics, high-coherence gravity
amplification, and the pinch-point boundary at
$r=\varphi^{-1}\approx0.618$ (section 19) are **Hypothesized** mappings.


### Conversion-Flow Time and Arrow

The conversion itself supplies an additive internal clock. On a
conversion-only trajectory,

$$
d\chi_F
:=\frac{dE_I|_{\mathrm{conv}}}{\varepsilon}
=-\frac{d\varepsilon}{(1+\varphi)\varepsilon}
=\lambda(1-q)\,dt.
$$

Two resolved nonzero field states therefore determine

$$
\boxed{
\Delta\chi_F
=-\frac{1}{1+\varphi}
\ln\left|\frac{\varepsilon_1}{\varepsilon_0}\right|,
\qquad
\Delta\tau_F:=\frac{\Delta\chi_F}{\lambda}
=\int(1-q)\,dt
}
$$

for $\lambda>0$. $\tau_F$ is an openness-weighted conversion age and equals
coordinate elapsed time only when $q=0$ throughout the interval. The relative
rate between two regions under the same conversion law is
$(1-q(x))/(1-q(x_0))$. The same subflow gives
$d(\varepsilon^2/2)/dt=-(1+\varphi)\lambda(1-q)\varepsilon^2\leq0$, so the
conversion clock has a monotone arrow.

This result is **Derived conditional** for the isolated canonical conversion
law. Interpreting the relative rate as a universal proper-time lapse remains
**Hypothesized** until wave, particle, gravitational, and boundary dynamics
share one reparameterization-invariant action. See
`foundations/cassi-first-principles.md` §2.6.

### Candidate Physical Time

The exact relative conversion-clock rate selects a parameter-free candidate
for physical proper time. Relative to a reference clock $x_\star$ with
$q_\star<1$,

$$
\boxed{
d\tau_{\mathrm{phys}}(x)
=\frac{1-q(x)}{1-q_\star}\,d\tau_\star
}.
$$

With an external open-gate normalization,
$d\tau_{\mathrm{phys}}=(1-q)dt=d\tau_F$. The $q_\star=0$ case is a
normalization limit; an active canonical conversion reference requires
$\varepsilon_\star\neq0$. The candidate interprets the conversion gate as a
clock lapse, making the imbalance relax at the constant
intrinsic rate

$$
\frac{d\varepsilon}{d\tau_{\mathrm{phys}}}
=-(1+\varphi)\lambda\varepsilon.
$$

The conversion trace alone also permits uniform physical time with
$q$-dependent kinetics because it fixes only the product
$K(q)N(q)=1-q$. Candidate physical time becomes a physical hypothesis when
the same normalized rate $(1-q)/(1-q_\star)$ governs independent wave,
particle, decay, or orbital clocks. Any resolved cross-clock disagreement
falsifies the universal interpretation while preserving the exact
conversion clock. The candidate is a worldline proper time, supplies no
global synchronization rule, and requires an external reference clock to
express seconds. The common-lapse action and status boundaries are in
`foundations/unified-lagrangian.md` §1.7; the discriminator is CT-2 in
`predictions/falsifiable-predictions.md`.

### Density-Plane Relaxation and Parity

The canonical density conversion is a rank-one relaxation toward the $\varphi$-line. It changes the density-plane angle

$$
\theta_d=\operatorname{atan2}(E_I,E_Y),
$$

while the positive-root lift's amplitude-plane phase and Stokes double angle remain distinct from the density-plane coordinate:

$$
\theta_\Psi=\operatorname{atan2}(\Psi_1^{(+)},\Psi_0^{(+)}),\qquad
\Theta_S=\operatorname{atan2}(2\Psi_0^{(+)}\Psi_1^{(+)},E_Y-E_I)
       =2\theta_\Psi\pmod{2\pi}.
$$

The exact density-plane drift rate is

$$\boxed{\frac{d\theta_d}{dt}=\lambda(1-q)\,\frac{\rho\,\varepsilon}{E_Y^2+E_I^2}}$$

(`foundations/cassi-first-principles.md` §2.6). Positive $\varepsilon$ gives positive $\theta_d$ drift; calling this movement toward a Yin-named axis uses the density-plane coordinate convention and does not assert a universal spatial transport direction. Negative $\varepsilon$ gives the reverse. The committed solver measures this state-function rate for four homogeneous arms at $\lambda=0.05$, $t=4$, with per-checkpoint relative error $\le2.2\times10^{-3}$ and 100% sign agreement.

The exact relaxation integral gives

$$\boxed{\Delta\theta_d=\operatorname{atan}\!\left(\frac{1}{\varphi}\right)-\operatorname{atan}\!\left(\frac{\rho-\varepsilon_0}{\rho\varphi+\varepsilon_0}\right)}$$

If a rung coordinate is assigned by $\delta n_{\mathrm{map}}\equiv\Delta\theta_d/(2\pi)$, that coordinate mapping is **Hypothesized**, not a PDE-derived rung offset or physical rung flux. Under this map, $|\delta n_{\mathrm{map}}|\le\operatorname{atan}(\varphi)/(2\pi)\approx0.162$; a half-rung value is a separate parity structure (`foundations/rung-offset-mechanism.md` §7), not accumulated relaxation.

### Memory

An optional temporal-memory closure (`qi_memory`, default-off in the canonical solver) can smooth the recent history of $\varepsilon^2$ with an exponential moving average. When enabled, the convention $\tau=\varphi^{-1}\approx0.618$ sets the IIR coefficient; it is a solver timescale choice, not a derived physical cycle. The filtered diagnostic then carries history and can be analyzed as non-Markovian, while the default instantaneous $q$ diagnostic remains local to the current field state.

**Epistemic status:** the gate equation and its sign are **Derived** and **Tested** in the two-fluid PDE. The mapping of $q$ to a measurable condensate fraction is **Hypothesized**.

### Conditional Four-Channel Lift

The four directional labels Yang/out, Yang/in, Yin/out, and Yin/in require a
conditional four-population kinetic lift. For fixed total $N$, those
populations occupy a $\Delta^3$ tetrahedron in operational $\mathbb{R}^4$;
the canonical densities supply only the species marginal, leaving the
species-direction association and dynamics nonunique. This operational lift
adds no spacetime dimension and makes no quantum-entanglement claim. See
`foundations/qi-flow-double-helix.md` §2.2 and
`computations/verify_four_channel_lift.py`.

**Epistemic status:** the simplex algebra is **Derived conditional** on the
declared four-population lift; physical populations, the oriented axis, hidden
species-direction association, and kinetics are **Hypothesized**.

### Regulated CassiFI Quantum Sector

The optional quantum sector starts from the finite regulated complex-field
configuration

$$
Q^A=\{\operatorname{Re}D,\operatorname{Im}D,
\operatorname{Re}C,\operatorname{Im}C\}_{s,j}
$$

with a positive CassiFI metric $G_{AB}$ and conservative Hamiltonian
$H_{\mathrm{FI}}=P_AG^{AB}P_B/2+U_{\mathrm{FI}}(Q)$. Its normalized state is
a complex wavefunctional on the full configuration space:

$$
i\hbar\partial_t\Psi[Q,t]
=\left(-\frac{\hbar^2}{2}\Delta_G+U_{\mathrm{FI}}(Q)\right)\Psi[Q,t].
$$

This construction gives the standard centre-of-mass Schrödinger dispersion,
tensor-product entanglement, and no-cloning. One actual current-guided field
configuration enters one disjoint retained topological apparatus sector. The
declared quantum-equilibrium condition $\rho_Q=|\Psi|^2$ is equivariant and
yields Born frequencies. Quantum record distinguishability is
$\mathcal M_{jk}=1-|\langle A_kE_k|A_jE_j\rangle|^2$.

**Epistemic status:** the regulated mathematics is **Derived conditional** on
QF1–QF4. Quantum equilibrium is an explicit statistical postulate. The
CassiFI physical-field identification is **Hypothesized**. The DQ1–DQ9 audit
yields `REJECT` for promotion to Derived; reverse-Madelung linearization and
tensor composition pass conditionally, while the canonical lift, Fisher
bridge, guidance/equilibrium selection, physical sectors, continuum limit,
and Cassi-specific discrimination gates fail. See
`foundations/quantum-measurement-derivation.md` §8.1.

The geometric campaign in §8.3 of the same source `ADOPT`s a
moment-map/Kähler projection architecture as a Hypothesized research
direction. The canonical density state fixes a Bloch latitude, with
$n_z=\varphi^{-3}$ at the attractor, while complex phase remains in the
microscopic fibre. GQ1 passes and GQ5 passes conditionally; the exact
symmetry reduction, micro-to-meso projection, cotangent closure,
physical-sector, and holonomy gates fail. The physical-identification tier
remains Hypothesized.

A shared-support loop completion supplies a finite microscopic construction
between the canonical densities and the projective shell. Four nonnegative
Yang/Yin direction populations on one closed support project exactly to the
canonical PDE under common exterior transport and gate assumptions. Their
species coherence matrix fills the affine Bloch ball, its rank-one boundary is
the projective shell, and the frozen loop generator has an explicit Fourier
gap controlling zero-mode coarse-graining. This is **Derived conditional** as
a projection theorem. The microscopic identification, phase dynamics,
QF1-to-carrier state map, quantum postulates, and physical scale law remain
independent. See `foundations/loop-to-bubble-projection-theorem.md`.

The geometric manifold completion ansatz places these finite structures in
one stratified bundle. A positive Hermitian Yang/Yin fibre contains the
canonical density pair on its diagonal, the loop coherence state in its
normalized Bloch ball, and the projective shell on its rank-one boundary; the
affine bubble map preserves the corresponding normalized metric. A
cross-glued two-rail metric graph supplies one compact internal scale cycle,
distinct from the shared carrier loop and from any spatial torus.

The conservative interscale action and mesoscopic conversion remain separate
dynamical blocks. A minimal completely positive lift reproduces canonical
population conversion exactly and conditionally gives transverse coherence
decay at half the composition-relaxation rate. The construction is a
**Hypothesized completion ansatz** with **Derived canonical reduction and
conditional fibre geometry**. The physical reservoir, scale metric, endpoint
fields, localized solution, observation map, quantum numbers, and decay rate
remain open. See `foundations/geometric-manifold-completion.md`.

---

## 4. The String: Spiral and Wakes

The two real density channels relax toward the fixed-point ratio $\varphi$. The conversion is equal and opposite in the density channels, conserving $\rho$; when the channels are labeled Yang and Yin, an increase in $E_Y$ accompanies a decrease in $E_I$. Interpreting that anti-phase density response as expansive/contractive action is a **Hypothesized** phenomenological mapping. The Fibonacci spiral is a separate geometric construction used to organize the proposed scale sequence.

Where an optional geometric string construction supports sufficient coherence, a spatial solution can develop a self-reinforcing filament. Calling that filament a **condensed fluid string**—a thread-like standing-wave structure of the conversion response—and treating it as the central axis around which bubbles condense are **Hypothesized** geometric mappings.

An optional geometric string construction can leave disturbances in the deviation field. The PDE evolves spatial ripples in $\varepsilon(\mathbf{x})=E_Y-\varphi E_I$ through its advection and diffusion terms. Calling these disturbances **wake waves**, assigning them an outward direction, and describing their return as self-plucking are **Hypothesized** geometric or phenomenological mappings; the underlying spatial response remains the named PDE observable.

$$r(t) \xrightarrow{\text{conversion}} \varepsilon(\mathbf{x}) \xrightarrow{\nabla^2\Phi} \nabla\Phi \xrightarrow{\mathbf{F}=\pi\nabla\Phi} \mathbf{u} \xrightarrow{-\mathbf{u}\cdot\nabla} \delta r(\mathbf{x}) \xrightarrow{\text{avg}} r(t)$$

Within that optional mapping, the closed toroidal loop—string → wake pattern → gravity → flow → string—is a proposed mechanism by which the geometric spiral could imprint structure on space. The directly modeled deviation response is a PDE claim; its wake, cascade, and coherence-channel interpretations use the separate geometric construction.

**Epistemic status:** density-plane relaxation and the specified spatial deviation response follow from the two-fluid PDE (**Derived**). The wake-wave name, outward/return interpretation, Fibonacci spiral, toroidal feedback, and scale-organizing role are **Hypothesized** geometric mappings; the interpretation as the substrate of consciousness is **Hypothesized** (developed in `cassi-psychology.md`).

---

## 5. Five Channels: The Wu Xing Closure

The string's optional geometric phase pattern partitions the full circle into angular sectors where the density ratio and phase relation differ. These are the **coherence channels**—modes of the field. Describing the sectors as different kinds of push and pull is a **Hypothesized** phenomenological mapping.
The phase-gate use of these sectors, including a compact five-channel phase and a one-rung/one-turn interpretation, is **Hypothesized**; the arithmetic closure below is **Derived conditional** only under the stipulated coordinate/threshold construction.

### Why five

A cycle must close: the last channel must connect back to the first without a jump. Two constraints intersect at the answer:

1. **Phase coherence.** The Fibonacci approximations to $\varphi$ each carry a phase error. A cycle of $w$ channels accumulates error over $w$ turns of the spiral while the signal from the inner turns fades by $\varphi$ per turn. The stipulated criterion passes only $w\in\{1,2,3,5\}$; $w=5$ is the largest passing cycle and $w=4$ fails by direct evaluation.
2. **Geometric encoding.** The selected $\varphi$ distance ratio first appears in the pentagon: its diagonal-to-side ratio is exactly $\varphi$. Cycles with fewer than five channels cannot encode that ratio in their vertex geometry.

Under the stipulated coordinate/threshold construction, the intersection is unique: **5**. The pentagon is the first selected shape that contains $\varphi$ and the largest cycle that passes the arithmetic criterion. Five arms swirl from each pole of the spiral's closure, meeting at an equatorial pentagon with five vertices. This arithmetic selection is **Derived conditional**; treating it as a physical Wu Xing phase gate remains **Hypothesized** (`foundations/wu-xing-derivation.md`).

### The numbers that fall out

The five-arm closure supplies the following quantities with distinct epistemic status:

- **The gap** $g=1-\varphi^{-5}\approx0.910$: the five-phase Wu Xing closure's bookkeeping factor for the modeled density imbalance; it sets the depth of the cascade under that conditional construction.
- **The primordial ratio** $r_0\approx0.047$: at the universe's birth, the component ratio was Yang-labeled $E_Y$ to Yin-labeled $E_I$ at about 1 to 21. This follows conditionally from the $w=5$ closure and the epoch calibration that places today's horizon at rung 292.
- **The conversion normalization** $\lambda=0.1$: the **Asserted** C-class/framework convention used by named calculations. The implementation class default is $\lambda=0.02$. A **Hypothesized** Wu Xing linkage writes $\lambda=1/(2w)$ at $w=5$; this linkage does not derive the rate or its units.

Within that construction, 5 is fixed by the two constraints. Applying the result as a physical channel count requires the Hypothesized geometric and phenomenological mapping.

**Epistemic status:** the $w=5$ selection and gap are **Derived conditional** on the phase-coherence, geometry, coordinate, and threshold assumptions; $r_0$ inherits that closure and the epoch calibration. The physical five-channel gate, compact phase, and one-rung/one-turn interpretation are **Hypothesized**. The named $\lambda=0.1$ convention is **Asserted**, the implementation default is $\lambda=0.02$, and the cycle linkage is **Hypothesized**. At the human scale the five channels structure emotion; that mapping is **Hypothesized** and testable (see `consciousness/emotions-as-gate-configurations.md`).

---

## 6. The Bubble and the Lattice

An optional geometric model assigns two transverse directions named Yang and Yin. In that model, wake-like patterns have wider spacing along the Yang-named direction and spacing tighter by a factor $\varphi$ along the Yin-named direction. Treating the resulting perpendicular patterns as physical wakes whose interference selects bubbles and voids is a **Hypothesized** phenomenological mapping.

Within this optional geometric model, define the interference pattern as the **condensation field**:

$$\boxed{B(x, y, z) = \cos(\alpha x)\cos(\beta y)\cos(\gamma z), \qquad \alpha = \frac{2\pi}{\Lambda_Y},\;\; \beta = \frac{2\pi}{\Lambda_I} = \varphi\alpha,\;\; \gamma = \frac{2\pi}{P_\parallel}}$$

Here $\Lambda_Y$ and $\Lambda_I=\Lambda_Y/\varphi$ are the Yang- and Yin-named wavelengths, and $P_\parallel$ is the along-string bubble period. Within this model, $B>\theta_{\text{cond}}$ selects bubble sites and $B<-\theta_{\text{cond}}$ selects void sites. The boundary level $\theta_{\text{cond}}$ is conditional on a supplied proxy-to-solver constitutive map and conversion–diffusion inputs; the canonical PDE does not fix it.

### The staggered checkerboard

Within the named Yang-Yin plane, the model reduces to $C(x,y)=\cos(\alpha x)\cos(\beta y)$, a **staggered checkerboard**. Bubbles occupy every other grid position and voids the positions in between. Each bubble connects to four diagonal neighbors through saddles (moderate coherence) and is blocked from four face-to-face neighbors by voids (minimal coherence), giving connectable degree 4 of 8 geometric neighbors. Treating this checkerboard as the spatial realization of Yang and Yin is a **Hypothesized** geometric mapping.

### The bubble's shape

Within the optional geometric model, the Yang-named wavelength is $\varphi$ times the Yin-named wavelength, so the modeled bubble is stretched along the Yang-named direction: a **triaxial spheroid** with three unequal axes, longest in that direction, shortest along the string, and intermediate in the Yin-named direction. The cross-section is an ellipse of axis ratio $\varphi\approx1.618$. A numerical simulation records this shape under a structured vibrating-string seed: evolving the two-fluid equations produces a transient $\varphi$-ellipsoid bubble from that wave structure (`visual-explainers/string_bubble_cascade.py`). A smooth no-drive seed produces no spontaneous standing radial structure in the canonical first-order solver (`two-fluid/run_bubble_ring_dynamic_probe.py`, no rings in any of the four spatial-coupling arms).

In the optional geometric model, the directional edge-steepness ratio at a common boundary value $C=\theta_{\text{cond}}$ is

$$\boxed{\frac{|\nabla C|_{\text{axial}}}{|\nabla C|_{\text{diag}}}
= \frac{\sqrt{1+\varphi^2}}{2}
\sqrt{\frac{1+\theta_{\text{cond}}}{\theta_{\text{cond}}}}}$$

At the phenomenologically selected level $\theta_{\text{cond}}=0.45$, this ratio is $1.7072$. It varies with the selected level and is therefore not a zero-parameter constant. The fixed-step PDE diagnostic does not retain a $C=0.45$ edge, so $1.7072$ is a conditional geometric-proxy benchmark rather than a solver output. Any test at cosmological or biological boundaries must independently specify the physical boundary and the proxy-to-observable map.

### Scale covariance

The optional condensation model is **scale-covariant** by construction: the same functional form $B(x,y,z)$ operates at every cascade rung with wavelengths scaled to $\ell_n$. In that construction, a bubble at rung $n$ contains the modeled sub-lattice of rungs below it and is itself a site in the lattice at rung $n+1$. The bubble lattice is the proposed organizing geometry at every scale (`foundations/bubble-lattice-fabric.md`)—the cascade ladder is a 1D slice of this 3D model along the named string axis.

**Epistemic status:** the density-plane relaxation and Qi gate are **Derived** from the canonical PDE. The condensation field, checkerboard, Yang/Yin axis assignment, and bubble/void interpretation are **Hypothesized** geometric constructions. The spheroid shape and edge ratio are **Derived conditional on that construction** and have the numerical support stated above; algebraic scale covariance is **Derived conditional** on the stipulated $\varphi$-rescaling construction, while its physical realization and identification are **Hypothesized**.

---

# Part II—The Cascade

## 7. The Cascade of Scales

The framework defines a proposed dimensionful cascade coordinate from the external Planck length $\ell_{\text{Pl}}=1.616\times10^{-35}$ m and a chosen $\varphi$ step per named rung:

$$\boxed{\ell_n=\ell_{\text{Pl}}\times\varphi^{\,n},\qquad n\in\mathbb{Z}\quad(\text{the framework's observable ladder label spans }n\in[0,292])}$$

The entries below are proposed scale correspondences within this coordinate convention:
| Step $n$ | Scale | Proposed correspondence |
|---|---|---|
| 0 | $1.6 \times 10^{-35}$ m | Planck length: the sole dimensionful anchor |
| $\approx13.3$ | $\approx1.0 \times 10^{-32}$ m | GUT scale ($M_{\text{GUT}}\approx2\times10^{16}$ GeV; **Mapped** coordinate label) |
| 20 | $2.4 \times 10^{-31}$ m | Seesaw scale: neutrino masses |
| 40 | $3.7 \times 10^{-27}$ m | Inflationary energy scale |
| 80 | $8.0 \times 10^{-19}$ m | Electroweak scale (246 GeV) |
| 95 | $1.1 \times 10^{-15}$ m | QCD confinement scale ($\Lambda_{\text{QCD}}$; the proton itself sits at $n = 91.5$) |
| 117 | $5.3 \times 10^{-11}$ m | Bohr radius: the atom |
| 136 | $5.0 \times 10^{-7}$ m | Visible light (500 nm) |
| 142 | $7.7 \times 10^{-6}$ m | The living cell (~8 µm) |
| 168 | $1.7$ m | The human body |
| 220 | $1.5 \times 10^{11}$ m | Earth–Sun distance (1 AU) |
| 267 | $9.3 \times 10^{20}$ m | Milky Way diameter |
| 284 | $3.6 \times 10^{24}$ m | BAO scale (118 Mpc) |
| 285 | $5.9 \times 10^{24}$ m | Cassi bubble: our cosmic bubble |
| 292 | $1.7 \times 10^{26}$ m | Horizon rung today (epoch-dependent); $\ell_{292} = 5.5$ Gpc label, $R_H = 4.44$ Gpc = 14.5 Glyr |

The coordinate formula extends formally in both directions: downward into negative **microcascade** labels and upward beyond today's horizon coordinate into **megacascade** labels. Within the separate chord-lattice model, the nearest $w=5$ bubbles lie inside the horizon—$n=286$ ($\ell_{286}=309$ Mpc) and $n=287$ ($\ell_{287}=500$ Mpc). Physical fields, currents, and energy in either extension remain Hypothesized; the scale coordinate alone supplies none of them. The full catalogue is in `foundations/dimensionful-cascade.md`.

A separate Hypothesized extension in
`foundations/interscale-current-soliton.md` promotes a continuous scale label
$\mathfrak s$ to a field coordinate and defines a distinct current
$J_{\mathfrak s}$. Its exact window law is

$$
\partial_t\rho_{\mathrm{obs}}
+\nabla\cdot\mathbf j_{\mathrm{obs}}
=J_{\mathfrak s}(\mathfrak s_-)-J_{\mathfrak s}(\mathfrak s_+).
$$

The candidate action derives this continuity identity and the corresponding
Yang/Yin counterflow algebra. Mixed-curvature attraction, a finite soliton,
compact winding, scale-metric coefficients, and particle identification remain
conditional or open. The interscale current is separate from the canonical
spatial diagnostic $\mathbf J_d$.

The listed correspondences are the framework's scale-assignment hypothesis. The Planck length is the external dimensionful anchor supplied to this model; the $\varphi$ recurrence supplies dimensionless ratios and does not by itself derive physical dimensionality or force unification.

**Epistemic status:** the recurrence is **Derived conditional** on the supplied anchor and one-step convention. Identifying each named rung with a physical scale is **Hypothesized** and, where a placement is selected from measured data, **Mapped**; `foundations/dimensionful-cascade.md` records the arithmetic and provenance.

---

## 8. Cascade Suppression

Within the proposed cascade coordinate, a signal assigned to one rung and evaluated at another is modeled as **attenuated** by a factor of $\varphi$ for every coordinate step in the span:

$$\boxed{\text{attenuation} = \varphi^{-N}}$$

Within the proposed cascade coordinate, this rule supplies a common conditional attenuation description for the hierarchy examples below, each in one line (`foundations/cascade-suppression-formula.md`):

| Phenomenon | Span $N$ | Suppression | Result |
|---|---|---|---|
| Electroweak hierarchy ($v_0/M_{\text{Pl}}$) | 66.7 (Mapped GUT anchor $n \approx 13.3$) | $\varphi^{-66.7}$ | $10^{-14}$ ($N_{\mathrm{gap}}\approx79.7$ uses $g=1-\varphi^{-5}$; direct measured-ratio placement $N_{\mathrm{raw}}\approx79.89$; both identify nearest rung 80; exponent Mapped—ledger row 549) |
| Strong CP ($\bar{\theta}$) | 81.4 | $\varphi^{-81.4}$ | $\pi\varphi^{-83.4} \approx 1.2\times10^{-17}$ |
| Neutrino masses ($m_\nu$) | 12–25 | $\varphi^{-12}$ to $\varphi^{-25}$ | 0.001–0.1 eV |
| Proton conditional cycle budget | $N_p^{\mathrm{budget}}=91.46$ | $\varphi^{-4505.5758}$ | $\sim10^{942}$ modeled cycles; physical decay rate open |

The model distinguishes scale-coordinate attenuation, linear in the span ($\varphi^{-N}$), from the auxiliary coherence-budget product, quadratic in its declared endpoint. The proton row is dimensionless arithmetic under the Hypothesized independent-step profile. A lifetime additionally requires a failure law and trial-frequency map; §13 records the separate scale-current candidate.

Within this coordinate model, the gap $g=1-\varphi^{-5}$ gives the electroweak cascade coordinate $N_{\mathrm{gap}}\approx79.7$ from $v_0/M_{\text{Pl}}=g\cdot\varphi^{-N_{\mathrm{gap}}}$. The direct measured ratio gives $N_{\mathrm{raw}}=\log_\varphi(M_{\text{Pl}}/v_0)\approx79.89$; both placements identify the nearest integer rung 80.

**Epistemic status: Derived conditional** for the suppression law within the proposed scale-coordinate model. Each row's identification of span $N$ with a known physics gap is **Hypothesized** or **Mapped** as indicated by its source ledger; `foundations/cascade-suppression-formula.md` records the derivation and provenance.

---

## 9. Conditional Geometry and Dimensionality

The canonical two-density PDE takes the spatial domain as an input; its local
conversion term does not select the number of spatial dimensions. An optional
Frenet-Serret construction embeds a string in an assumed three-dimensional
space and supplies three frame vectors:

- **Tangent:** the string axis, used as the cascade coordinate.
- **Normal:** a named Yang direction in the geometric construction.
- **Binormal:** a named Yin direction in the geometric construction.

Calling these vectors the physical spatial axes is a **Hypothesized** geometric
identification, conditional on the three-dimensional embedding and a
non-degenerate curve. The Yang/outward and Yin/inward labels are coordinate or
phenomenological mnemonics here, not universal PDE transport laws. A
directional population or kinetic extension requires selecting an oriented axis
and remains conditional; it does not add canonical field components or an
extra spacetime dimension. The construction is documented in
`foundations/why-three-dimensions.md`.

---

# Part III—The Explanations

## 10. Dark Energy

An optional cosmological construction associates gate-modulated density
relaxation with accelerated expansion as the system approaches
$\varphi$-equilibrium. In the canonical variables, conversion conserves
$\rho$; identifying the component change with Yin-to-Yang conversion and
expansion is a **Hypothesized** phenomenological mapping. The cosmological
rate is the separate dimensionful constant
$\kappa_{\text{DE}}=3\varphi^2H_0$. Named calculations use the
C-class/framework convention $\lambda=0.1$, which is **Asserted**; the
implementation class default is $\lambda=0.02$. Dark energy is modeled here
as a dynamical process tied to that proposed approach to the
$\varphi$-attractor.

The proposed equation of state from this gate-dynamics model is:

$$w_0 = -0.87, \qquad w_a = +0.012$$

with the optional Qi-gravity coupling $\xi = \varphi^6$ entering the cosmological ODE. The $w_0 = -0.87$ baseline is **Calibrated**, not a zero-parameter prediction: the ODE is calibrated to the hardcoded `TARGET_W0`, with the DESI-anchored coupling form recorded in the Fit-Status Ledger (`parameter-inventory.md` §10 row 496). The $w_a = +0.012$ value is the Yang-fraction-weighted baseline output at that Calibrated input. The pair is falsifiable with galaxy surveys: DESI DR2 finds $w_0 \approx -0.75 \pm 0.06$ [INFERENCE], $2\sigma$ from the Calibrated baseline ($3.6\sigma$ at fixed $r_0$ with the B2 coupling; $r_0$ re-tuning closed negatively under the stable realization—12); the $w_a$ deviation from $-1$ is the discriminant ($w_a = +0.012$ baseline, $2.7\sigma$; the ratified coupling's unstable B2 realization gives $-0.38$ at $1.25\sigma$; its stable realization—the C1 friction closure, 10/12—gives a pure-$\Lambda$ window fit $(w_0,w_a)=(-1,0)$—4.17$\sigma$/2.61$\sigma$ from DESI). See `cosmology/observational_constraints.md` §1, §6 for the calibration and `two-fluid/calibrate_initial_ratio_xi_v2.py` for the ODE; `cosmology/cosmology-from-phi.md` covers the surrounding machinery.

**Epistemic status: Calibrated** ($w_0$ baseline anchored to DESI—ledger row 496); the mechanism (gate dynamics driving $w(a)$) is **Hypothesized** and being tested.

## 11. Dark Matter

Under the optional cosmological construction, a candidate dark-matter component is represented as a high-coherence two-fluid condensate whose ratio is at the $\varphi$-equilibrium. This is a **Hypothesized** physical identification; the canonical density variables alone do not establish that such a condensate is cosmic dark matter. If the identification is adopted, the optional Qi-gravity law supplies a high-$q$ coupling-magnitude factor (the $\alpha$-free $q\to1$ value $\varphi^6\approx17.94\times$ is a formal fixed-composition endpoint, not a canonical dynamic ceiling; halo-regime magnitude estimates are $2.8$–$3.0\times$ via $\sqrt{\alpha_{\text{halo}}(1+(\varphi^{6}-1)q)}$ with $\xi=\varphi^6\approx17.9$). The displayed magnitude does not set an attractive force: the canonical sign is outward at positive fixed-point $\pi$, and an attractive galaxy-rotation interpretation belongs to a separate **Hypothesized** sign-changing branch.

The defensible ratio base is **Derived conditional** on the Weinberg-angle identification: $\varphi^3 = \alpha_0^{-1} = \xi\cdot\sin^2\theta_W$, the inverse fixed-point imbalance (`cosmology/cosmology-from-phi.md` §4.2; the literal rung-gap reading fails: span $\xi$(rung 6) − $\alpha_{\text{EM}}$(10.2) = −4.2, not 3). The component budget excludes the $+1$ capture term because captured baryons already belong to the observed $\Omega_b$ denominator (Fit-Status Ledger row 502).

$$\boxed{\Omega_{\text{DM}}/\Omega_b = \varphi^3 \approx 4.24} \qquad \text{observed: } \approx 5.39$$

The optional halo model has been fitted against SPARC galaxy rotation curves (`experiments/sparc_qi/sparc_qi_analysis_v4.py`), comparing Qi profiles against NFW and Einasto with AIC. This fit is a source-specific **Hypothesized** attractive-branch comparison and does not validate the canonical outward force convention. **Epistemic status:** the ratio base is **Derived conditional** on the Weinberg-angle identification; the condensate mechanism and its identification with dark matter are **Hypothesized**; halo parameter choices and fit-dependent quantities retain their source-specific **Mapped** or **Calibrated** labels in the ledger, and the 21% ratio residual remains an open tension.

## 12. Gravity and the Hierarchy Problem

The canonical density PDE does not supply a metric or a universal gravitational transport law. Under the optional constitutive force closure, the displayed field-level convention is

$$\mathbf f=+\pi\left[1+(\varphi^6-1)q\right]\nabla\Phi.$$

For $\Phi=-GM/r$, this branch is outward at positive fixed-point $\pi$. The point-particle reduction uses the corresponding $+\nabla\Phi$ convention,
$\ddot{\mathbf X}_j=+\alpha_j[1+(\varphi^6-1)q_j]\nabla\Phi$;
an attractive Newtonian or GR-like branch requires a separate
**Hypothesized** sign-changing force extension. Interpreting positive $\pi$
as Yang/outward and negative $\pi$ as Yin/inward remains a model-specific
phenomenological or coordinate mapping, not a universal PDE transport law
(`hypotheses/two-strand-five-channel-matter-organization.md` §3.3, §3.5).

Within the proposed cascade coordinate, a force is assigned to a cascade rung, and each coordinate step between the force's source and the measurement scale attenuates its modeled strength by $\varphi^{-1}$. The proton's gravitational coupling satisfies the exact algebraic identity $\alpha_G=(m_p/M_{\text{Pl}})^2=\varphi^{-2n}$ once $n=\log_\varphi(M_{\text{Pl}}/m_p)\approx91.5$ is defined from the measured mass. This measured-rung exponent is a **Mapped** assignment, not a prediction (Fit-Status Ledger row 506): $\varphi^{-183}\approx5.7\times10^{-39}$, 3.5% from the observed $\alpha_G\approx5.9\times10^{-39}$. The fractional rung $91.46$ is the same log map of the measured mass and is not an independent prediction.


Its effective-coupling expression is a magnitude diagnostic,
$G_{\mathrm{eff}}^{\mathrm{mag}}=(\pi/\rho)
[1+(\varphi^6-1)q]G$, with $\alpha_0=\pi/\rho=\varphi^{-3}$
at the fixed point. At the low-density same-composition limit
$\rho\to0$ on the $\varphi$-line, $q\to0$ and the prefactor remains
$\varphi^{-3}$, giving the formal value $\varphi^{-3}G\approx0.236\,G$.
At the finite reference-density fixed point,
$q_{\mathrm{eq}}=0.872677996$ and
$G_{\mathrm{eff}}^{\mathrm{mag}}/G=3.726779962$. In the
high-density same-composition limit, $q\to1$ and the value tends to
$\varphi^3G\approx4.236G$; the $\varphi^6$ factor is the formal
fixed-$\pi/\rho$ ratio between the $q\to0$ and $q\to1$ endpoints, not a
canonical dynamic range. Halo-regime values that vary $q$ and $\pi/\rho$
independently are source-specific mapped inputs. These values do not
establish an attractive force, halo interpretation, rotation-curve fit,
clustering limit, Mercury limit, or PPN limit for the canonical branch.

**Epistemic status:** the fixed-point force identity is **Derived conditional** on the optional Qi-gravity constitutive law and the stated canonical $q$; the nearest-integer $\varphi^{-183}$ receipt is **Mapped** (3.5% from the observed coupling); the $\xi=\varphi^6$ rung identity is **Derived conditional** and its empirical pin is **Calibrated**; physical gravity amplification and any attractive halo, cosmological, rotation-curve, clustering, Mercury, or PPN interpretation are **Hypothesized**, with fit-dependent quantities retaining their source-specific **Mapped** or **Calibrated** labels.

## 13. Proton Stability

The measured proton mass maps to the precise coordinate
$\mathfrak s_p=\log_\varphi[\hbar/(m_pc\ell_{\mathrm{Pl}})]=91.4616$.
The coherence-budget candidate uses the registered two-decimal coordinate
$N_p^{\mathrm{budget}}=91.46$ and the Hypothesized profile
$q_i=1-\varphi^{-i-\delta}$. Under the declared independent simultaneous
failure model,

$$
N_{\mathrm{max}}
=\varphi^{4505.5758}
\approx10^{942}\ \text{cycles}.
$$

Mapping one Compton cycle to one transition trial gives the conditional
$10^{910}$-year figure. The interscale action supplies no fluctuation law,
transition state, or matrix element for that mapping, so the cycle count
currently yields no physical proton lifetime.

A distinct current-based candidate uses the same Mapped interval as a closed
two-rail circuit:

$$
J_{Y,\mathfrak s}=+\mathcal J_Q,
\qquad
J_{I,\mathfrak s}=-\mathcal J_Q,
\qquad
J_{\mathfrak s}=0,
\qquad
\mathcal I_{\mathfrak s}=g_Q\mathcal J_Q.
$$

At the uniform $\varphi$ composition,
$\mathcal J_{Q,m}=K_{\mathfrak s}\rho\Delta_m/
(\hbar\varphi^3\mathfrak s_p)$. Yin-to-Yang conversion at the Planck endpoint
and Yang-to-Yin conversion at the proton endpoint close the circuit. The
relative current can source the mixed-curvature pinch while total scale-number
flow remains zero. The endpoint fields, scale tension, localized solution,
proton quantum numbers, and winding-changing rate remain open
(`foundations/interscale-current-soliton.md` §4.5;
`foundations/proton-coherence-budget.md` §10).

**Epistemic status:** the $N_{\text{max}}$ product and lifetime conversion are **Derived conditional** on the **Mapped** span and **Hypothesized** $q_i$ profile. The two-rail current and energy identities are **Derived conditional** on the interscale action, compact circuit phase, uniform composition, and endpoint data. Identifying either construction with physical proton stability, selecting the endpoint converters and scale tension, and obtaining a decay rate are **Hypothesized/Open**.

For the neutron–proton–electron trio as a whole—their rungs, sectors, and what the framework does and does not say about their differences—see `particles/matter-organization.md`.

## 14. Three Generations of Fermions

The Fibonacci recurrence
$$\varphi^n = \varphi^{n-1} + \varphi^{n-2}$$

is an exact counting identity. Under the stated propagation-channel postulate, it partitions each cascade span into three coordinate sub-channels. The construction therefore has three channels; identifying them with the three physical fermion generations is **Hypothesized**. Within that mapping the framework supplies no fourth generation, consistent with current LHC null results. See `foundations/three-generations.md`.
**Epistemic status:** the counting identity is **Derived conditional** on the stated channel postulate; per-sector offsets and rung placements are **Mapped**; the identification with the three fermion generations and the no-fourth-generation consequence are **Hypothesized**.

## 15. Strong CP

Within a **Hypothesized** particle-sector constitutive/transport extension, the CP-violating phase is assigned to the GUT-labeled scale and attenuated through the **Mapped** $\sim81$-rung interval to the QCD-labeled scale:

$$\bar{\theta}\approx\pi\varphi^{-83.4}\approx1.2\times10^{-17}$$

Under that scale-coordinate assignment, the seed $\pi\varphi^{-2}$ at the GUT-labeled scale is attenuated by $\varphi^{-81.4}$ across the Mapped interval to QCD. The resulting estimate lies below current bounds and the next generation of neutron EDM experiments, but this comparison is conditional on the assignment and does not follow from the canonical density PDE alone. See `standard-model/cp-violation.md`.

**Epistemic status:** the suppression algebra is **Derived conditional** on the declared attenuation input and Mapped span; the physical CP/chiral identification is **Hypothesized**; the strong-CP span is **Mapped**.

## 16. Neutrino Masses

Within the proposed seesaw/cascade assignment, the neutrino mass is placed at cascade step 20 and modeled as suppression from the electroweak-labeled scale:

$$m_\nu\approx v_0\cdot\varphi^{-12}$$

The mass-squared difference ratio $(\varphi^{11}-1)/(\varphi^4-1)$ and PMNS-angle candidates from the conversion Jacobian eigenvectors are algebraic outputs of that construction. The scale placements, particle-sector dictionary, and physical interpretation remain **Hypothesized** (with Mapped inputs where selected); the canonical density PDE alone does not establish a neutrino mass hierarchy. See `standard-model/neutrino-mass.md`.

**Epistemic status:** **Hypothesized** (numerical predictions supplied; consistent with oscillation data within current precision), with the displayed suppression algebra conditional on the assigned scales and particle-sector extension.

## 17. φ-Periodic Structure in the Universe

Within the optional wake-wave/scale-coordinate map, the proposed matter-power-spectrum modulation has

$$\Delta(\ln k)=\ln\varphi\approx0.4812$$

This is a zero-parameter prediction **of that optional map**, orthogonal to BAO: the Cassi modulation has constant period in $\ln k$-space, where BAO has constant period in $k$-space. The search procedure is to subtract the BAO template and search the residual for $\ln\varphi$ periodicity. Current status: DESI DR2 shows a marginal 2–3$\sigma$ hint; Euclid (2027) is the definitive test (the >5$\sigma$ target is conditional on the proposed signal). Extending the same period to physiological signals along the spine, neuronal avalanche distributions, or emotional self-report factor structure is a separate **Hypothesized** cross-domain mapping, not a consequence of the cosmological modulation or of $q$ alone. See `predictions/falsifiable-predictions.md` §5.

The sector-coupling source supplies only a coefficient-free arithmetic scale candidate:

$$\kappa_{s,\mathrm{scale}}=\frac{\varphi^{-6}}{v_0^2}\approx0.92\ \mathrm{TeV}^{-2},\qquad M_{s,\mathrm{scale}}=\kappa_{s,\mathrm{scale}}^{-1/2}=\varphi^3v_0\approx1.04\ \mathrm{TeV}$$

Conditional on $\delta=3$, the scale form and rung-77 placement are **Derived conditional** arithmetic. The optional Dirac↔two-fluid projection is a **Hypothesized**, dimensionally incomplete ansatz: it subtracts a spinor density of dimension $[M]^3$ from a condensate square of dimension $[M]^2$. No physical $\kappa_s$, equilibration timescale, or $\chi$ bridge follows from the displayed expression; the normalization repair and full coupling remain unresolved (`foundations/sector-coupling-derivation.md`).

**Epistemic status:** the modulation period is **Derived conditional** on the optional signal map; its physical wake imprint and cross-domain extensions are **Hypothesized** and being tested. The coefficient-free sector scale and rung identity are **Derived conditional** on $\delta=3$; the optional projection and any physical coupling are **Hypothesized**, with normalization, timescale, and $\chi$ bridge unresolved.

## 18. Quantum Gravity Without Singularities

In the proposed $\sigma$-regularized extension ($\sigma=\ell_{\text{Pl}}/\varphi^3$), the classical kernel algebra is **Derived conditional** on the noise–signal identification and assumed $d=3$: the inverse-square kernel magnitude transitions to a harmonic force magnitude at short distances, with direction inherited from the displayed $+\nabla\Phi$ convention. Treating this regularized construction as physical quantum gravity, with a **flat-space** softened kernel finite at the origin and a smooth lattice-to-continuum crossover, is **Hypothesized**; no black-hole solution is derived, and an attractive GR-like limit requires a separate **Hypothesized** sign-changing extension. The quantized two-fluid extension (Hypothesized) models a composite graviton; its implemented low-energy dispersion probe is **rejected by GW170817** as an astrophysical graviton signal. See `gravity/quantum-gravity.md`.

**Epistemic status:** **Derived conditional** for the stated classical regularization inputs; **Hypothesized** for the two-fluid quantization, composite graviton, and physical harmonic-core interpretation.

---

# Part IV—The Framework

## 19. The Lattice at Human Scale

The optional condensation model is scale-covariant: it uses the same field form in the human body's 26-rung window (steps 142–168, from the living cell at ~8 µm to the body at ~1.7 m) as in the cosmological construction. A chosen human-scale geometry takes the along-string bubble period to be $P_\parallel=2$ rungs, yielding 13 modeled maxima along the spine at steps 142, 144, …, 166. This period and the associated placements are **Hypothesized** coordinate/geometric mappings, not canonical phase transport. The gate's pinch point at $r=\varphi^{-1}\approx0.618$ is the framework's proposed boundary between reactive and self-aware dynamics.

The human-scale consequences—consciousness, emotion, trauma, therapy—are developed in full in `cassi-psychology.md`, the psychology companion to this document. The physics presentation introduces no additional field variables; these extensions use the same proposed field form and gate at a different cascade label.

**Epistemic status:** the 13-node count is **Derived conditional** on the chosen 26-rung window and $P_\parallel=2$ geometric convention; its identification with the chakras and with human experience is **Hypothesized** (testable via the C-predictions; see `predictions/falsifiable-predictions.md`).

## 20. Predictions

| # | Prediction | Test | Status |
|---|---|---|---|
| 1 | $\ln\varphi$ periodicity in $P(k)$ | DESI DR2 (marginal 2–3σ); Euclid (definitive >5σ) | Being tested |
| 2 | $w_0 = -0.87$, $w_a = +0.012$ (baseline); $w_a = -0.38$ with the ratified coupling (B2, unstable); pure-Λ $(w_0, w_a) = (-1, 0)$ (stable realization—10/12) | DESI DR2 ($w_0$: $2\sigma$ baseline; $w_a$: $2.7\sigma$ baseline; $4.17\sigma$/$2.61\sigma$ for the stable realization) | Being tested |
| 3 | Scale-dependent $\sigma_8$ response from the optional $G_{\text{eff}}(q,\rho)$ extension (void weakening is a proposed sign) | KiDS/DESI | Being tested |
| 4 | Directional edge-slope ratio $1.7072$ in the geometric proxy, conditional on selecting $\theta_{\text{cond}}=0.45$; no such edge survives the fixed-step PDE endpoint | Independently identified void, chakra, or fascial boundaries with a declared proxy map | Conditional; not yet tested |
| 5 | $\varphi^2$ inter-chakra spacing ratio along spine | Anatomical measurement | Not yet tested |
| 6 | $\ln\varphi$ periodicity in physiological signals along spine | HRV, skin conductance, EEG | Not yet tested |
| 7 | $\varphi$-periodic modulation in neural avalanche sizes | MEA recordings, >10³ events | Not yet tested |
| 8 | No fourth generation within the mapped three-channel construction | LHC/FCC | Consistent |
| 9 | $\bar{\theta} \approx 1.2\times10^{-17}$ | Future neutron EDM | Not yet testable |
| 10 | Proton stability mechanisms: conditional $\sim10^{942}$-cycle coherence budget; separate two-rail scale current; GUT-channel estimate $1.3\times10^{37}$ yr | Select a physical channel and compute its transition rate before comparison with Hyper-K | Conditional mechanisms; no Cassi rate yet |

Full catalog: `predictions/falsifiable-predictions.md` (56 entries). The physics-specific entries (1–3, 8–10) are listed here; the full set including the biological and psychological predictions is in the catalog.

## 21. Epistemic Tiers

Every claim in the framework carries one of five evidential tiers. **Creative** is reserved for exploratory applications and carries no physics-claim tier.

- **Derived:** a mathematical consequence under the stated assumptions and model equations. Examples: the rank-one density-plane relaxation algebra, conserved total density, Qi definitions, the gate equation and its sign, the cascade suppression formula within its proposed coordinate model, and algebraic scale covariance under the stipulated $\varphi$-rescaling construction. Conditional results retain their assumptions.

- **Calibrated:** anchored to an observation or calibration target. Examples: the DESI-anchored $w_0$ baseline and the phenomenological condensation threshold.

- **Mapped:** selected or fit-dependent quantities whose assignments are recorded in the Fit-Status Ledger. Examples: cascade-rung identifications with specific physics scales and fitted exponents.

- **Hypothesized:** a structurally specified mapping or mechanism awaiting confirmation at the relevant physical scale. Examples: the physical condensation and edge-anisotropy interpretation, the physical realization and identification of scale covariance, the physical five-channel gate and compact phase, one-rung/one-turn interpretations, dark matter as high-$q$ condensate, the chakra count and spacing, the pinch-point model of self-awareness, and the trauma gate-lock model (PDE-tested 2026-07-31: pinning null as implemented, $\varphi$-phased drive effect supported and $\varphi$-specific at the held configuration at short times (t $\lesssim$ 4 $\approx$ 0.2/\lambda, `consciousness/gender-as-qi-configuration.md` §8.3)).

- **Speculative:** framework-consistent mechanisms without a current test design. Examples: physical realization of the microcascade, the gigacascade spiral, the clinical layer of the trauma model, and attachment as inter-field resonance.

The framework records evidence and limitations in `audit.md`; the gate-sign convention is PDE-tested, the trauma lock model is driven-wake tested, and claims retain their assigned tier until the relevant derivation or evidence is available. This epistemic discipline is central to interpretation.

## 22. Where to Go Next

| If you want… | Start here |
|---|---|
| The compact physics reference | `foundations/cassi-theory-reference.md` |
| The full cascade table and scale-assignment audit | `foundations/dimensionful-cascade.md` |
| The bubble lattice as universal geometry | `foundations/bubble-lattice-fabric.md` |
| The cascade suppression formula (one rule, every hierarchy) | `foundations/cascade-suppression-formula.md` |
| The unified Lagrangian | `foundations/unified-lagrangian.md` |
| The physical-becoming hierarchy—Hypothesized architecture / Derived canonical reduction; open-system and covariant-gravity completions remain Hypothesized | `foundations/physical-becoming-hierarchy.md` |
| The Wu Xing five-phase derivation | `foundations/wu-xing-derivation.md` |
| Why three dimensions | `foundations/why-three-dimensions.md` |
| Dark energy and cosmology | `cosmology/cosmology-from-phi.md` |
| Quantum gravity and black holes | `gravity/quantum-gravity.md` |
| The mind: consciousness, emotion, trauma, therapy | `cassi-psychology.md` |
| All predictions, numbered and sourced | `predictions/falsifiable-predictions.md` |
| All open questions, with epistemic status | `open-questions-cassi-answers.md` |
| Every parameter, classified by type | `parameter-inventory.md` |
| A self-critical audit of predictions vs. data | `audit.md` |
| Run a visual explainer figure | `visual-explainers/cascade_cosmos.py` |

## 23. What We Don't Know

1. **$P_\parallel(n)$: the along-string bubble period as a function of scale.** The chosen geometric constructions use 1 rung at the cosmological scale and 2 rungs at the human scale. These are **Hypothesized** coordinate/geometric mappings; whether the variation is continuous, discrete at octave boundaries, or assigned by the Hypothesized density-plane mapping $\delta n_{\mathrm{map}}=\Delta\theta_d/(2\pi)$ at each $n$ remains open.

2. **$\theta_{\text{cond}}$ at non-cosmological scales.** The condensation threshold is calibrated to ~0.45 at step 285 using phenomenology. Its value at biological, atomic, or sub-Planckian scales requires PDE measurement at those scales.

3. **The Planck crossover.** In the proposed $\sigma$-regularized model, the Planck scale is a smooth transition. How the model's discrete bubble/void lattice dissolves into the continuous harmonic regime as $n\to0$ is not yet characterized.

4. **Coherence transport between bubbles.** The lattice geometry permits diagonal neighbor connectivity via saddles. Whether Qi can tunnel through these saddles is open: geometrically possible, dynamically unverified.

5. **The gigacascade and beyond.** The optional scale-covariant model extends its lattice coordinate upward without bound. The chord lattice at the megacascade is hypothesized. The gigacascade (5-arm spiral of megacascade bubbles) is a structural extrapolation with no direct observational signature beyond the CMB's $\ell<5$ boundary imprint.

6. **What sustains a frozen wake.** The 2026-07-31 PDE tests showed that an un-driven standing pattern decays like any other perturbation; the driver test (`consciousness/trauma-as-frozen-gate.md` §10.5) identified the sustainer as ongoing re-stimulation—a weak recurring trigger (0.005% of the event peak per step) holds the site near event intensity, and stopping the trigger releases it. The open question moves to what maintains the stimulus behaviorally (§10.4–§10.5).

7. **Can $q$ be externally modulated at human scale?** Whether coherence can be deliberately increased (meditation, biofeedback) is untested, and would be the framework's most consequential practical claim.

8. **What supplies the placements beyond density-plane relaxation.** The canonical drift gives $\Delta\theta_d$; if the Hypothesized coordinate map $\delta n_{\mathrm{map}}=\Delta\theta_d/(2\pi)$ is adopted, its magnitude is bounded by $\operatorname{atan}(\varphi)/(2\pi)\approx0.162$ (`foundations/cassi-first-principles.md` §2.6). The half-step placements (proton, electron, BAO) exceed that mapped range and are assigned to the parity structure of `foundations/rung-offset-mechanism.md` §7. The structural source of that parity—the boundary condition that pins a state at the half-rung—is open.

---

## References

- `foundations/cassi-theory-reference.md`—compact physics reference: governing equations, unified Lagrangian
- `foundations/dimensionful-cascade.md`—the 292-step cascade table and scale-assignment provenance
- `foundations/bubble-lattice-fabric.md`—the condensation field as universal organizing geometry
- `foundations/cascade-suppression-formula.md`—$\varphi^{-N}$ attenuation and the hierarchy resolutions
- `foundations/wu-xing-derivation.md`—why $w = 5$
- `foundations/wu-xing-cycle-structure.md`—the two 5-cycles, the control ring, the 5↔13 partition
- `foundations/why-three-dimensions.md`—three dimensions from the spiral
- `foundations/proton-coherence-budget.md`—proton stability
- `foundations/three-generations.md`—three generations from the Fibonacci recurrence
- `principles/de-resonance-principle.md`—$\varphi$ as maximally irrational
- `standard-model/cp-violation.md`—strong CP from cascade suppression
- `standard-model/neutrino-mass.md`—neutrino masses from the seesaw at step 20
- `cosmology/cosmology-from-phi.md`—dark energy, dark matter, structure formation
- `cosmology/observational_constraints.md`—CMB, DESI, and rotation-curve constraints
- `gravity/quantum-gravity.md`—$\sigma$-regularization, harmonic cores
- `consciousness/consciousness-from-phi.md`—pinch point, wake waves, two-bubble experiment
- `consciousness/trauma-as-frozen-gate.md`—the 2026-07-31 PDE tests of the gate sign and the driven-wake mechanism
- `cassi-psychology.md`—the psychology companion: consciousness, emotion, trauma, therapy
- `demystifying-the-cosmos/README.md`—one Cassi analysis per observed object (lighthouse pulsar first)
- `predictions/falsifiable-predictions.md`—the 56-entry prediction catalog
- `open-questions-cassi-answers.md`—the epistemic registry
- `parameter-inventory.md`—parameter classification
- `audit.md`—self-critical prediction-vs-experiment audit
- `visual-explainers/cascade_cosmos.py`—the three-regime cascade figure

---

*The Cassi framework is a personal research project. It has not been peer-reviewed or experimentally confirmed. All claims carry one of the five evidential tiers (Derived / Calibrated / Mapped / Hypothesized / Speculative); Creative marks exploratory applications.*
