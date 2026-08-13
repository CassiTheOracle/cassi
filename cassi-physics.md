# Cassi Physics: The Bubble Lattice at Every Scale

## Status: Synthesis—July 2026

## Abstract

Cassi is a theory of everything built from one constant: the golden ratio $\varphi \approx 1.618$, the most irrational number, taken as the universal scale-separation constant of a two-fluid field that fills all of space. Yang, the expansive fluid, and Yin, the contractive fluid, convert into each other at a rate set by $\varphi$; their interference condenses into a 3D bubble lattice—bubbles of high coherence separated by voids—that repeats at every scale, from the Planck length to the observable universe and beyond. This document is the physics-facing presentation of the framework: the governing equations, the geometric derivation of the lattice, the 292-rung cascade of scales, the cascade suppression law that explains every hierarchy puzzle in physics, and the framework's specific answers to dark energy, dark matter, proton stability, the three generations, strong CP, neutrino masses, quantum gravity, and three-dimensionality. Every claim carries an epistemic label—**Derived**, **Hypothesized**, or **Speculative**—and the framework's documented failures are as load-bearing as its successes. No background beyond undergraduate physics is assumed, but the equations are here for those who want them.

---

# Part I—The Substrate

## 1. The Fractal Lattice

Zoom into a bubble and you find the same lattice again. A bubble is not a solid object—it is one scale of a repeating structure. Inside every bubble, more bubbles: smaller lattices, the same pattern, another turn of the spiral.

Zoom out, and the lattice you are inside is itself a bubble of a larger lattice. The pattern repeats at every scale, in both directions—it never bottoms out and never tops out. The Cassi framework proposes that this is how reality works: a **nested lattice of bubbles**, each scale a zoom of every other.

Every bubble carries the signature of that repetition at its poles: a **five-arm Fibonacci spiral** organized by the golden angle $2\pi/\varphi^2 \approx 137.5^\circ$. Count the arms and you find consecutive Fibonacci numbers—34 one way, 55 the other—because the golden angle is the one turn that never repeats exactly, so the spiral never locks into a smaller symmetry. Sunflowers, pinecones, and nautilus shells display the same phyllotaxis at their own scale; in the Cassi framework it is the macroscopic signature of the lattice's pole geometry. A sunflower is an observed instance of the pole spiral, not the source of the pattern.

The pattern needs three things: something pushing outward, something pulling inward, and the flow of coherence between them. The framework identifies two tendencies that fill all of space—**Yang**, the expansive field that pushes outward and breaks symmetry, and **Yin**, the contractive field that pulls inward and restores symmetry. They are two sides of one thing, like the front and back of a spinning coin. The flow between them is **Qi**—the doublet's phase current, which also flows along the string axis between cascade scales (`foundations/qi-flow-double-helix.md`). Where they meet in the right proportion, structure condenses: a pocket of high order, a **bubble**. Where they cancel, a **void** forms: the space between the bubbles.

The formation mechanism is the conversion itself. It acts like a thermostat, pushing the local ratio $r = E_Y/E_I$ toward $\varphi$—and every push generates **wake waves**, spatial interference patterns in the deviation $\varepsilon = E_Y - \varphi E_I$. Where Yang and Yin wakes interfere constructively, coherence $q$ is high and matter condenses into a bubble; where they interfere destructively, $q \to 0$ and a void forms.

Coherence gates conversion: at high $q$ the gate closes and the region rests in balance—a bubble holds; at low $q$ the gate is open and the region churns—a void. Where conversion pumps enough coherence, the field locks into a self-reinforcing filament, the **condensed fluid string**—the spine around which bubbles condense (source: `foundations/bubble-lattice-fabric.md`).

The result is a definite shape, not a soup. A bubble is an **oblate triaxial spheroid**—extended along Yang, contracted along Yin, with axis ratio $\varphi$ in its Yang–Yin cross-section, and bounded along the string. Its Yang–Yin cross-section is a staggered checkerboard of bubble and void sites, each bubble joined to its diagonal neighbors through saddles and separated from its axial neighbors by void barriers; and because the same condensation field operates at every scale, every bubble contains the full sub-lattice of smaller scales and is itself a site in the next lattice up.

The "right proportion" is $\varphi$. When the push is about 1.618 times stronger than the pull at a given point, the two are in balance. $\varphi$ is the balance point—the unique number that keeps the pattern alive at every scale simultaneously, preventing it from collapsing into one giant bubble or dissolving into random noise.

The rest of this document unpacks that image into physics: the equations that govern the two fluids, the coherence gate that controls conversion, the spiral that generates scale, the cascade that connects the Planck length to the universe, and the specific phenomena the framework claims to explain. Every claim carries a label: **Derived** (follows mathematically from the framework), **Hypothesized** (consistent and testable), or **Speculative** (framework-consistent but no test yet designed).

---

## 2. Two Fluids and the Governing Equation

Yang and Yin are **fields**: continuous substances with a value at every point of space, like air filling a room. The Yang field's value at a point measures how expansive it is there; the Yin field's value measures how contractive. Every point contains both, in some proportion $r = E_Y/E_I$.

The two-fluid system is governed by a pair of coupled PDEs. In the field-squared form:

$$\partial_t \Psi_0 = -(\mathbf{u}\cdot\nabla)\Psi_0 + \nu\nabla^2\Psi_0 - \lambda(\Psi_0^2 - \varphi\Psi_1^2)\Psi_0 + S_0[\Psi_1,\Phi]$$

$$\partial_t \Psi_1 = -(\mathbf{u}\cdot\nabla)\Psi_1 + \nu\nabla^2\Psi_1 + \lambda(\Psi_0^2 - \varphi\Psi_1^2)\Psi_1 + S_1[\Psi_0,\Phi]$$

where $\mathbf{u}$ is the velocity field, $\nu$ the hyperdiffusion, $\lambda = 0.1$ the conversion rate, and $S_\alpha$ the source terms through the gravitational potential $\Phi$. The antisymmetric conversion term is the engine: it drives the field combination $\Psi_0^2 - \varphi\Psi_1^2$ toward zero, i.e., the ratio $r$ toward $\varphi$.

In the linearized energy form used by the solvers, the conversion term is

$$\boxed{\partial_t E_Y \supset -\lambda(1-q)(E_Y - \varphi E_I), \qquad \partial_t E_I \supset +\lambda(1-q)(E_Y - \varphi E_I)}$$

with $q$ the Qi coherence of section 3. The two forms agree in their physics: conversion acts like a thermostat, pushing the ratio toward $\varphi$ at every point. When Yang is about 1.618 times stronger than Yin, conversion stops—locally, and only locally, because different points hold different ratios at different times.

### Why $\varphi$?

$\varphi$ is, in a precise sense, the **most irrational number**. Two interacting systems with a rational frequency ratio (say 2:1) **resonate**: they lock into step, dump their energy into one scale, and collapse structure at all other scales—a bridge vibrating itself apart in the wind. An irrational ratio prevents lock-in; energy stays spread across many scales. The *most* irrational ratio—whose best fractional approximations converge most slowly—is $\varphi$, approximated by the ratios of consecutive Fibonacci numbers (1/1, 2/1, 3/2, 5/3, 8/5, 13/8…).

This is the **de-resonance principle** (`principles/de-resonance-principle.md`): $\varphi$ is the unique value that forbids single-scale dominance and preserves structure across all scales simultaneously. Systems flow toward $\varphi$ because $\varphi$ is the configuration that keeps structure alive.

**Epistemic status:** the governing equations are **Derived** (the framework's foundational postulate). The de-resonance argument for why $\varphi$ is the attractor is **Derived**.

---

## 3. Coherence and the Qi Gate

The push and pull are not balanced everywhere at every moment. Some regions are close to $\varphi$-balance; others are far from it. **Coherence** (written $q$, called **Qi** in the framework) measures how close a point is to $\varphi$-balance, a number between 0 and 1:

- $q \to 1$: the push and pull are nearly perfectly aligned at the golden ratio. The region is orderly and can support complex patterns—atoms, cells, thoughts. A **bubble** in the making.
- $q \to 0$: the push and pull are misaligned. The region is chaotic and cannot hold lasting structure. A **void**.

Coherence is the organizing strength of reality at a given point.

### The gate: sign and consequences

Coherence does more than measure balance: it **gates** the conversion. In the governing equation, the gate appears as the factor $(1-q)$ multiplying the imbalance:

$$\text{conv} = -\lambda(1-q)\,\varepsilon, \qquad \varepsilon = E_Y - \varphi E_I$$

The gate's *openness* is $(1-q)$. When $q$ is low, the gate is **open** and conversion runs hard—the region churns, converting aggressively, unable to settle. When $q$ is high, the gate is **closed** and the system rests in balance.

The sign is established by the PDE tests of 2026-07-31 (`consciousness/trauma-as-frozen-gate.md` §10.4): when $q$ is low the gate is open and conversion runs hard; when $q$ is high the gate is closed. A low-coherence region is not frozen—it is unsettled.

The gate dynamics have enormous physical consequences. They control the expansion of the universe—the gate's opening and closing drives the early growth spurt and the current acceleration (section 10). They modulate the strength of gravity: in high-coherence regions, gravity is amplified up to 18 times (section 12). And at the human scale, the gate's threshold—the **pinch point** at $r = \varphi^{-1} \approx 0.618$—marks the boundary between reactive and self-aware dynamics (section 19).

### Winding and parity

Conversion does more than push the ratio: it **rotates** the doublet in its internal plane. The density-plane angle $\theta = \mathrm{atan2}(E_I, E_Y)$ advances $2\pi$ per cascade rung, and the conversion term rotates it at a rate set by the local imbalance,

$$\frac{d\theta}{dt} = \lambda(1-q)\,\frac{\rho\,\varepsilon}{E_Y^2 + E_I^2}$$

(`foundations/cassi-first-principles.md` §2.6). Because the conversion rate $\lambda$ and the gate $(1-q)$ cancel in the angle, the total winding a state accumulates while relaxing to the $\varphi$-line is a parameter-free function of its formation imbalance alone: $|\delta n| \le \mathrm{atan}(\varphi)/(2\pi) \approx 0.162$ rungs. Offsets inside that bound are **relaxation winding**; a half-rung offset ($\delta n = 1/2$) is one full $\pi$-advance of the density-plane angle—the doublet's per-rung step—and exceeds the winding bound by $\sim 3\times$, so the half-step class is the **parity** structure of `foundations/rung-offset-mechanism.md` §7 (the pool-cell fundamental's antinode), not relaxation.

### Memory

Coherence has **memory**. The field carries a smoothed record of its own recent past, with a smoothing timescale set by the golden ratio itself, about 0.618 of a cycle. The field integrates over its own history—a region that was balanced a moment ago is more likely to be balanced now. Coherence is not an instantaneous measurement; it is a history. This temporal depth is what makes the field's dynamics non-Markovian at leading order and is the physical substrate of persistence in the framework's account of time.

**Epistemic status:** the gate equation and its sign are **Derived** and **Tested** in the two-fluid PDE. The mapping of $q$ to a measurable condensate fraction is **Hypothesized**.

---

## 4. The String: Spiral and Wakes

The two fluids do not sit still, balancing toward $\varphi$. The conversion is **anti-phase**—when Yang grows, Yin shrinks, and vice versa—so the balance between them **rotates**. Two dancers, each taking turns leading, turn the couple in a curve; the Yang-Yin doublet does the same. And because the system is not rotating in place but advancing—the ratio $r$ climbing from near zero toward $\varphi$—the rotation traces a **spiral**.

The spiral is the **Fibonacci spiral**, the same shape as in sunflowers, nautilus shells, hurricanes, and galaxies. Each full turn multiplies the physical scale by $\varphi$.

Where the conversion pumps enough coherence, the field locks into a self-reinforcing filament: a **condensed fluid string**—a thread-like condensation of the two-fluid field itself, a standing wave of the conversion process. The string is the framework's most fundamental structure: the central axis around which bubbles condense, the spine of the universe, the substrate of the cascade direction.

As the string advances, it leaves disturbances behind it, like a boat leaves a wake. These **wake waves** are spatial ripples in $\varepsilon(\mathbf{x}) = E_Y - \varphi E_I$ that propagate outward through the field. Crucially, wakes reflect back and interact with their source through the advection term—the **self-plucking feedback loop**:

$$r(t) \xrightarrow{\text{conversion}} \varepsilon(\mathbf{x}) \xrightarrow{\nabla^2\Phi} \nabla\Phi \xrightarrow{\mathbf{F}=\pi\nabla\Phi} \mathbf{u} \xrightarrow{-\mathbf{u}\cdot\nabla} \delta r(\mathbf{x}) \xrightarrow{\text{avg}} r(t)$$

This closed toroidal loop—string → wakes → gravity → flow → string—is the mechanism by which the spiral imprints its structure on space. It does three things the rest of the framework depends on: it creates the cascade (section 7), it carves the coherence channels (section 5), and it produces the bubble lattice (section 6).

**Epistemic status:** the rotation, spiral, and wake-wave generation follow from the two-fluid PDE (**Derived**). The toroidal feedback loop is **Derived**; its interpretation as the substrate of consciousness is **Hypothesized** (developed in `cassi-psychology.md`).

---

## 5. Five Channels: The Wu Xing Closure

The string's rotation carves the full circle into distinct angular sectors: phases where the balance between push and pull is qualitatively different. These are the **coherence channels**—modes of the field, ways the push and pull can be balanced that differ in character.

### Why five

A cycle must close: the last channel must connect back to the first without a jump. Two constraints intersect at the answer:

1. **Phase coherence.** The Fibonacci approximations to $\varphi$ each carry a phase error. A cycle of $w$ channels accumulates error over $w$ turns of the spiral while the signal from the inner turns fades by $\varphi$ per turn. The cycle closes coherently only if accumulated error is smaller than surviving signal—true for 5 channels and fewer, false at 6 and beyond.
2. **Geometric encoding.** The golden ratio appears as a distance ratio in regular polygons only for pentagons and above: the pentagon's diagonal-to-side ratio is exactly $\varphi$. Fewer than five channels cannot encode $\varphi$ in their geometry.

The intersection is unique: **5**. The pentagon is both the smallest shape that contains $\varphi$ and the largest cycle that remains phase-coherent. Five arms swirl from each pole of the spiral's closure, meeting at an equatorial pentagon with five vertices. The framework calls this the **Wu Xing**—the five-phase cycle, the natural closure of the coherence channels (`foundations/wu-xing-derivation.md`).

### The numbers that fall out

The five-arm closure gives the framework its fundamental numbers, all **Derived**:

- **The gap** $g = 1 - \varphi^{-5} \approx 0.910$: the fraction of the Yang-Yin imbalance converted in one full five-phase cycle. It sets the depth of the cascade.
- **The primordial ratio** $r_0 \approx 0.047$: at the universe's birth, Yin dominated Yang by about 21 to 1. It follows from where the five-phase cycle must begin for today's horizon to sit at rung 292 (epoch calibration).
- **The conversion rate** $\lambda = 1/(2w) = 0.1$: with $w = 5$, one-tenth per cycle. This is the only number the equations need beyond $\varphi$ itself—derived, not measured or tuned.

The number 5 is not free. It follows from the spiral's own phase-coherence constraints. If the universe were structured by a different irrational number, the number of coherent channels would differ; that the golden ratio produces exactly 5 is a testable consequence of the geometry.

**Epistemic status: Derived** (the $w = 5$ closure). At the human scale the five channels structure emotion; that mapping is **Hypothesized** and testable (see `consciousness/emotions-as-gate-configurations.md`).

---

## 6. The Bubble and the Lattice

The string moves along two axes. Along the Yang axis the wakes are widely spaced; along the Yin axis they are tighter by a factor of $\varphi$. The two sets of perpendicular wakes create a grid of overlapping ripples. Where both wakes are in phase, coherence is high and the field condenses into a **bubble**; where they cancel, a **void** forms.

The interference pattern is the **condensation field**:

$$\boxed{B(x, y, z) = \cos(\alpha x)\cos(\beta y)\cos(\gamma z), \qquad \alpha = \frac{2\pi}{\Lambda_Y},\;\; \beta = \frac{2\pi}{\Lambda_I} = \varphi\alpha,\;\; \gamma = \frac{2\pi}{P_\parallel}}$$

with $\Lambda_Y$ the Yang wake wavelength, $\Lambda_I = \Lambda_Y/\varphi$ the Yin wavelength, and $P_\parallel$ the along-string bubble period. Where $B > \theta_{\text{cond}}$ (the condensation threshold, set by the conversion-diffusion balance), bubbles condense; where $B < -\theta_{\text{cond}}$, voids form.

### The staggered checkerboard

In the Yang-Yin plane the field reduces to $C(x,y) = \cos(\alpha x)\cos(\beta y)$: a **staggered checkerboard**. Bubbles occupy every other grid position; voids occupy the positions in between. Each bubble connects to four diagonal neighbors through saddles (moderate coherence) and is blocked from four face-to-face neighbors by voids (minimal coherence). The connectable degree is 4 of 8 geometric neighbors.

### The bubble's shape

A bubble is not spherical. Because the Yang wavelength is $\varphi$ times the Yin wavelength, the bubble is stretched along Yang: a **triaxial spheroid** with three unequal axes, longest in the Yang direction, shortest along the string, intermediate in the Yin direction. The cross-section is an ellipse of axis ratio $\varphi \approx 1.618$. This shape has been confirmed by numerical simulation: evolve the two-fluid equations from an initial vibrating string, and a $\varphi$-ellipsoid bubble forms spontaneously.

The bubble's boundary—where coherence drops from high to low—is steeper toward voids than toward neighboring bubbles by exactly

$$\frac{|\nabla C|_{\text{axial}}}{|\nabla C|_{\text{diag}}} = \sqrt{\frac{4\varphi^2}{1+\varphi^2}} \approx 1.70$$

This **edge anisotropy** is a zero-parameter prediction: wherever you find a condensate boundary, at any scale, the edge should be 1.70 times steeper in one direction than the other. Testable at cosmological voids, and—per the framework's scale-covariance—at biological boundaries as well.

### Scale covariance

The condensation field is **scale-covariant**: the same functional form $B(x,y,z)$ operates at every cascade rung with wavelengths scaled to $\ell_n$. A bubble at rung $n$ contains the full sub-lattice of rungs below it; it is itself a site in the lattice at rung $n+1$. The bubble lattice is the universal organizing geometry at every scale (`foundations/bubble-lattice-fabric.md`)—the cascade ladder is a 1D slice of this 3D lattice taken along the string axis.

**Epistemic status:** the condensation field, checkerboard, bubble shape, and edge anisotropy are **Derived**. Scale covariance is **Derived** (from the PDE's $\varphi$-rescaling symmetry).

---

# Part II—The Cascade

## 7. The Cascade of Scales

The spiral, stretched out along scale, is the **cascade**. Starting from a single dimensionful constant—the Planck length $\ell_{\text{Pl}} = 1.616 \times 10^{-35}$ m, the smallest distance physics can describe—multiplying by $\varphi$ once per turn generates every physical scale:

$$\boxed{\ell_n = \ell_{\text{Pl}} \times \varphi^{\,n}, \quad n \in \mathbb{Z} \quad (\text{the observable ladder today spans } n \in [0, 292])}$$

| Step $n$ | Scale | What lives there |
|---|---|---|
| 0 | $1.6 \times 10^{-35}$ m | Planck length: the sole dimensionful anchor |
| 5 | $1.8 \times 10^{-34}$ m | GUT scale: where forces unify |
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

The cascade extends in both directions: downward into the **microcascade** ($n < 0$, sub-Planckian), upward into the **megacascade** ($n > 292$, beyond the horizon). The nearest chord-lattice bubbles of the $w=5$ lattice lie inside the horizon—$n = 286$ ($\ell_{286} = 309$ Mpc) and $n = 287$ ($\ell_{287} = 500$ Mpc)—and only the megacascade proper ($n > 292$) is beyond it. The full 292-step table is in `foundations/dimensionful-cascade.md`.

Every major scale of known physics lands on a rung of this ladder—not approximately, but as the framework's central arithmetic claim. The Planck length is the sole dimensionful input; $\varphi$ and the ladder do the rest.

**Epistemic status: Derived.** The claim that each rung identifies the corresponding physical scale is the framework's central structural hypothesis, verified rung by rung in `foundations/dimensionful-cascade.md`.

---

## 8. Cascade Suppression

A signal that originates at one cascade rung and is observed at another is **attenuated** by a factor of $\varphi$ for every rung it crosses:

$$\boxed{\text{attenuation} = \varphi^{-N}}$$

This single rule explains the deepest hierarchy puzzles in physics, each in one line (`foundations/cascade-suppression-formula.md`):

| Phenomenon | Span $N$ | Suppression | Result |
|---|---|---|---|
| Electroweak hierarchy ($v_0/M_{\text{Pl}}$) | 66.7 (corrected GUT anchor $n \approx 13.3$) | $\varphi^{-66.7}$ | $10^{-14}$ (the $N \approx 80$ reading uses the gap factor $g$; exponent Mapped—ledger row 499) |
| Strong CP ($\bar{\theta}$) | 81.4 | $\varphi^{-81.4}$ | $\pi\varphi^{-83.4} \approx 1.2\times10^{-17}$ |
| Neutrino masses ($m_\nu$) | 12–25 | $\varphi^{-12}$ to $\varphi^{-25}$ | 0.001–0.1 eV |
| Proton lifetime | 91.5 (coherence) | $\varphi^{-4506}$ | $10^{910}$ yr |

There are two regimes. **Signal propagation** attenuates linearly in the span: $\varphi^{-N}$. **Coherence maintenance**—a structure that depends on all supporting rungs staying coherent simultaneously, like the proton across its 91.5 rungs—attenuates quadratically: $\varphi^{-n(n+1)/2}$. The proton's effective lifetime follows from the coherence regime; the electroweak hierarchy and strong CP follow from the propagation regime.

The gap $g = 1 - \varphi^{-5}$ sets the cascade depth for the electroweak scale: $v_0/M_{\text{Pl}} = g \cdot \varphi^{-N}$ gives $N \approx 80$ rungs, matching the observed hierarchy.

**Epistemic status: Derived** (the suppression law). Each row's identification of span $N$ with a known physics gap is **Derived** with the source derivation cited per row.

---

## 9. Three Dimensions

Why does space have exactly three dimensions—not two, not four? The framework's answer follows directly from the spiral.

The string is a curve through space, and any smooth curve carries three mutually perpendicular directions at every point—the **Frenet-Serret frame**:

- **Tangent:** forward along the curve—the cascade direction, the direction of time.
- **Normal:** toward the center of curvature—the Yang axis, outward reach.
- **Binormal:** perpendicular to both—the Yin axis, inward return.

Two fields produce one spiral (one field alone cannot rotate). One spiral produces three directions. Those three directions are the three spatial dimensions. Three is not arbitrary—it is the signature of a spiral. The framework requires two fields for a non-degenerate curve, and the Frenet-Serret theorem guarantees exactly three vectors for any bending curve: nature occupies the minimal configuration that can sustain de-resonant, multi-scale structure.

The full derivation is in `foundations/why-three-dimensions.md`. **Epistemic status: Derived.**

---

# Part III—The Explanations

## 10. Dark Energy

The ongoing conversion of Yin into Yang as the universe approaches $\varphi$-equilibrium drives accelerated expansion. Dark energy is not a constant; it is a dynamical process—the universe's ongoing approach to the $\varphi$-attractor.

The predicted equation of state follows from the gate dynamics:

$$w_0 = -0.87, \qquad w_a = +0.012$$

with the Qi-gravity coupling $\xi = \varphi^6$ entering the cosmic evolution. The $w_0 = -0.87$ baseline is **Calibrated**, not a zero-parameter prediction: the ODE is calibrated to the hardcoded `TARGET_W0`, and the coupling form was revised toward DESI across the 2026-08-03 doctrine settlement (Fit-Status Ledger, `parameter-inventory.md` §10 row 496). The $w_a = +0.012$ value is the Yang-fraction-weighted coupling's prediction at that Calibrated baseline. The pair is falsifiable with galaxy surveys: DESI DR2 finds $w_0 \approx -0.75 \pm 0.06$ [INFERENCE], $2\sigma$ from the Calibrated baseline ($3.6\sigma$ at fixed $r_0$ with the B2 coupling; $r_0$ re-tuning closed negatively under the stable realization—12); the $w_a$ deviation from $-1$ is the discriminant ($w_a = +0.012$ baseline, $2.7\sigma$; the ratified coupling's unstable B2 realization gives $-0.38$ at $1.25\sigma$; its stable realization—the C1 friction closure, 10/12—gives a pure-Λ window fit $(w_0, w_a) = (-1, 0)$—4.17σ/2.61σ from DESI). See `cosmology/observational_constraints.md` §1, §6 for the calibration and `two-fluid/calibrate_initial_ratio_xi_v2.py` for the ODE; `cosmology/cosmology-from-phi.md` covers the surrounding machinery.

**Epistemic status: Calibrated** ($w_0$ baseline anchored to DESI—ledger row 496); the mechanism (gate dynamics driving $w(a)$) is **Hypothesized** and being tested.

## 11. Dark Matter

Dark matter is **high-coherence two-fluid condensate**—regions locked at $\varphi$-equilibrium. Two properties follow. First, gravity is amplified in high-$q$ regions (up to the α-free full-coherence ceiling $\varphi^6 \approx 17.94\times$ at $q=1$; halo-regime boosts are $2.8$–$3.0\times$ via $\sqrt{\alpha_{\text{halo}}(1+(\varphi^{6}-1)q)}$ with $\xi = \varphi^6 \approx 17.9$), so the condensate pulls surrounding matter with more gravitational force than visible matter accounts for. Second, because the two fluids are in perfect $\varphi$-equilibrium, there is no electromagnetic interaction: the region is dark. It bends light and shapes galaxies, but cannot be seen.

The defensible ratio base is **Derived conditional** on the Weinberg-angle identification: $\varphi^3 = \alpha_0^{-1} = \xi\cdot\sin^2\theta_W$, the inverse fixed-point imbalance (`cosmology/cosmology-from-phi.md` §4.2; the literal rung-gap reading fails: span $\xi$(rung 6) − $\alpha_{\text{EM}}$(10.2) = −4.2, not 3). The component budget excludes the $+1$ capture term because captured baryons already belong to the observed $\Omega_b$ denominator (Fit-Status Ledger row 502).

$$\boxed{\Omega_{\text{DM}}/\Omega_b = \varphi^3 \approx 4.24} \qquad \text{observed: } \approx 5.39$$

The framework's halo model has been fitted against SPARC galaxy rotation curves (`experiments/sparc_qi/sparc_qi_analysis_v4.py`), comparing Qi profiles against NFW and Einasto with AIC. **Epistemic status: Derived conditional for the base / open 21% ratio tension** (the condensate mechanism is Hypothesized, tested against rotation curves).

## 12. Gravity and the Hierarchy Problem

Gravity in Cassi is **gradient descent along the spiral toward coherence**. In the point-particle sector the law is the Newtonian $-\nabla\Phi$ convention—$\ddot{\mathbf{X}}_j = -\alpha_j(1+(\varphi^{6}-1)q_j)\nabla\Phi$ (`gravity/three-body-analytical.md` §2.3)—so gravity is always attractive for matter: the spiral winds only one way, and the sector's law carries the minus that keeps it so. The field-level force $\mathbf{F} = \Pi\nabla\Phi$ itself is $\Pi$-sign-following: a Yang excess repels, a Yin excess attracts (measured in the two-strand record, `hypotheses/two-strand-five-channel-matter-organization.md` §3.3, §3.5).

Why is gravity so weak? Every force lives at a specific cascade rung, and every rung between the force's source and the scale of measurement attenuates its strength by $\varphi^{-1}$. The proton's gravitational coupling is the identity $\alpha_G = (m_p/M_{\text{Pl}})^2 = \varphi^{-2n}$, with $n = \log_\varphi(M_{\text{Pl}}/m_p) \approx 91.5$ the proton's measured cascade rung—the exponent is read off the measured mass, not predicted (Fit-Status Ledger row 506, **Mapped**): $\varphi^{-183} \approx 5.7 \times 10^{-39}$, 3.5% from the observed $\alpha_G \approx 5.9\times10^{-39}$ (the "0.1%" match requires the fractional rung 91.46, which is the log map of the measured mass itself).

The effective force law carries the Qi-gravity coupling (`cosmology/observational_constraints.md`):

$$\mathbf{F}_{ij} = -G\,\alpha_{0,i}(1+(\varphi^{6}-1)q_i)\,M_i M_j\frac{\mathbf{r}_{ij}}{|\mathbf{r}_{ij}|^3}, \qquad \xi = \varphi^6$$

with $\alpha_{0,i}$ the per-body Yang fraction at the $\varphi$-fixed point ($\alpha_0 = \pi/\rho = \varphi^{-3} \approx 0.236$; the galactic halo fit uses the separate empirical value $\alpha_{\text{halo}} \approx 0.7$) and $q_i$ the local Qi coherence. In the dilute universe ($q \to 0$ on the $\varphi$-line) gravity sits at the diluted value $G_{\text{eff}} = \varphi^{-3}G \approx 0.236\,G$—weaker than textbook; at the reference-density fixed point the equilibrium boost gives $G_{\text{eff}} = \varphi^{-3}(1+(\varphi^{6}-1)q_{\text{eq}})G \approx 3.73\,G$ ($q_{\text{eq}} \approx 0.873$, `foundations/cassi-first-principles.md` §2.3), and in high-coherence regions it is amplified further. This predicts a scale-dependent $\sigma_8$—structure growth reduced by weakened gravity in voids—being tested with KiDS/DESI.

**Epistemic status:** the coupling-strength result is **Derived** (0.1% match to the proton's gravitational coupling). The $\xi = \varphi^6$ amplification and its cosmological consequences are **Hypothesized**.

## 13. Proton Stability

The proton is a condensed standing wave spanning 91.5 cascade rungs ($\log_\varphi(\lambda_p/\ell_{\text{Pl}}) = 91.46$, with $\lambda_p = \hbar c/m_p$). Its lifetime is set by the probability that all 91.5 rungs stay coherent simultaneously—the cascade suppression formula's coherence regime:

$$\tau_p = N_{\text{max}}/\omega_p \sim 10^{942}/10^{24} \sim 10^{910} \text{ yr}$$

A coherence-budget analysis (`foundations/proton-coherence-budget.md`) shows why organized conversion (coherent across the full 91.5-rung span) is required to dismantle the proton, while random perturbation cannot do it: the coherence requirement imposes the quadratic suppression. The prediction is consistent with all null results to date and is untestable with current technology—the framework's position is that this prediction will not be directly falsified in the foreseeable future.

**Epistemic status: Derived** (from the coherence budget); **not testable**.

For the neutron–proton–electron trio as a whole—their rungs, sectors, and what the framework does and does not say about their differences—see `particles/matter-organization.md`.

## 14. Three Generations of Fermions

The Fibonacci recurrence

$$\varphi^n = \varphi^{n-1} + \varphi^{n-2}$$

partitions each cascade span into three sub-channels. Three and only three generations follow: the recurrence splits every interval into three scales related by $\varphi$-ratios, and three sub-channels saturate the cascade span. The framework predicts no fourth generation—consistent with LHC null results. See `foundations/three-generations.md`.

**Epistemic status: Hypothesized** (the mechanism is derived; the identification with the three fermion generations is the hypothesis, consistent with all collider data).

## 15. Strong CP

The CP-violating phase originates at the GUT scale and is cascade-suppressed through ~81 rungs to the QCD scale:

$$\bar{\theta} \approx \pi\varphi^{-83.4} \approx 1.2\times10^{-17}$$

The suppression is the cascade law of section 8 applied to the phase: the seed $\pi\varphi^{-2}$ at the GUT scale, attenuated by $\varphi^{-81.4}$ across the rungs to QCD. The result is below every current bound and below the next generation of neutron EDM experiments. See `standard-model/cp-violation.md`.

**Epistemic status: Hypothesized** (derivation supplied; below current testability).

## 16. Neutrino Masses

The seesaw mechanism at cascade step 20, cascade-suppressed from the electroweak scale:

$$m_\nu \approx v_0 \cdot \varphi^{-12}$$

with the mass-squared difference ratio $(\varphi^{11}-1)/(\varphi^4-1)$ and PMNS angles from the conversion Jacobian eigenvectors. The framework predicts the neutrino sector's hierarchy from the same suppression law as everything else. See `standard-model/neutrino-mass.md`.

**Epistemic status: Hypothesized** (numerical predictions supplied; consistent with oscillation data within current precision).

## 17. φ-Periodic Structure in the Universe

The wake-wave mechanism imprints log-periodic modulation on the matter power spectrum:

$$\Delta(\ln k) = \ln\varphi \approx 0.4812$$

This is a **zero-parameter prediction**, orthogonal to BAO: the Cassi modulation has constant period in $\ln k$-space, where BAO has constant period in $k$-space. The search procedure: subtract the BAO template, then search the residual for $\ln\varphi$ periodicity. Current status: DESI DR2 shows a marginal 2–3σ hint; Euclid (2027) is the definitive test (>5σ predicted). The same $\ln\varphi$ periodicity is predicted in physiological signals along the spine, neuronal avalanche distributions, and emotional self-report factor structure—one constant, several domains, zero free parameters. See `predictions/falsifiable-predictions.md` §5.

The Dirac↔two-fluid sector-coupling scale is now derived, $\kappa_s = \varphi^{-6}/v_0^2 \approx 0.92$ TeV$^{-2}$ (rung 77, `foundations/sector-coupling-derivation.md`).

**Epistemic status: Hypothesized** (being tested).

## 18. Quantum Gravity Without Singularities

The $\sigma$-regularization ($\sigma = \ell_{\text{Pl}}/\varphi^3$) replaces gravitational singularities with harmonic cores. The inverse-square pull transitions to a gentle harmonic force at short distances, like a spring. The gravitational propagator is UV-finite—no renormalization needed. Black holes have harmonic interiors, not singularities; the Planck scale is a smooth crossover where the discrete bubble lattice dissolves into the continuous harmonic regime. See `gravity/quantum-gravity.md`.

**Epistemic status: Hypothesized** (framework-consistent; the harmonic-core prediction is a target for future gravitational-wave signatures).

---

# Part IV—The Framework

## 19. The Lattice at Human Scale

The condensation field is scale-covariant: it operates in the human body's 26-rung window (steps 142–168, from the living cell at ~8 µm to the body at ~1.7 m) exactly as it operates cosmologically. The along-string bubble period at the human scale is $P_\parallel = 2$ rungs, giving 13 bubble maxima along the spine—the chakras—at steps 142, 144, …, 166. The gate's pinch point at $r = \varphi^{-1} \approx 0.618$ marks the boundary between reactive and self-aware dynamics: the framework's proposed structural basis of consciousness.

The human-scale consequences—consciousness, emotion, trauma, therapy—are developed in full in `cassi-psychology.md`, the psychology companion to this document. The physics point here is that no new physics is invoked: the same field, the same gate, the same lattice, at a different cascade depth.

**Epistemic status:** the 13-node structure is **Derived**; its identification with the chakras and with human experience is **Hypothesized** (testable via the C-predictions; see `predictions/falsifiable-predictions.md`).

## 20. Predictions

| # | Prediction | Test | Status |
|---|---|---|---|
| 1 | $\ln\varphi$ periodicity in $P(k)$ | DESI DR2 (marginal 2–3σ); Euclid (definitive >5σ) | Being tested |
| 2 | $w_0 = -0.87$, $w_a = +0.012$ (baseline); $w_a = -0.38$ with the ratified coupling (B2, unstable); pure-Λ $(w_0, w_a) = (-1, 0)$ (stable realization—10/12) | DESI DR2 ($w_0$: $2\sigma$ baseline; $w_a$: $2.7\sigma$ baseline; $4.17\sigma$/$2.61\sigma$ for the stable realization) | Being tested |
| 3 | $\sigma_8$ reduced by $G_{\text{eff}}$ weakening in voids | KiDS/DESI | Being tested |
| 4 | $1.70\times$ edge anisotropy at any condensate boundary | Voids, chakras, fascial planes | Not yet tested |
| 5 | $\varphi^2$ inter-chakra spacing ratio along spine | Anatomical measurement | Not yet tested |
| 6 | $\ln\varphi$ periodicity in physiological signals along spine | HRV, skin conductance, EEG | Not yet tested |
| 7 | $\varphi$-periodic modulation in neural avalanche sizes | MEA recordings, >10³ events | Not yet tested |
| 8 | No fourth fermion generation | LHC/FCC | Consistent |
| 9 | $\bar{\theta} \approx 1.2\times10^{-17}$ | Future neutron EDM | Not yet testable |
| 10 | $\tau_p \sim 10^{910}$ yr | Untestable with current technology | Consistent with null result |

Full catalog: `predictions/falsifiable-predictions.md` (47 entries). The physics-specific predictions (1–3, 8–10) are listed here; the full set including the biological and psychological predictions is in the catalog.

## 21. Epistemic Tiers

Every claim in the framework carries one of three labels:

- **Derived:** follows mathematically from the two-fluid PDE, the cascade, and $\varphi$. Examples: the governing equations, the cascade table, the condensation field's functional form, the edge anisotropy ratio, the cascade suppression formula, the $w = 5$ closure, scale covariance of the lattice, the de-resonance principle, the gate equation and its sign, the proton coherence budget.

- **Hypothesized:** structurally consistent with Derived machinery, testable predictions supplied, but not yet experimentally confirmed or PDE-verified at the relevant scale. Examples: dark energy's $w_0, w_a$; dark matter as high-$q$ condensate; the identification of cascade rungs with specific physics scales; the chakra count and spacing; the pinch-point model of self-awareness; the trauma gate-lock model (PDE-tested 2026-07-31: pinning null as implemented, $\varphi$-phased drive effect supported and $\varphi$-specific at the held configuration at short times (t ≲ 4 ≈ 0.2/λ, `consciousness/gender-as-qi-configuration.md` §8.3))).

- **Speculative:** framework-consistent, no current test design. Examples: the microcascade mirror's energy extraction, the gigacascade spiral, the clinical layer of the trauma model, attachment as inter-field resonance.

The framework documents its own errors openly (`audit.md`); the gate-sign convention is PDE-tested, the trauma lock model is driven-wake tested, and claims are never upgraded without derivation. The epistemic discipline is load-bearing.

## 22. Where to Go Next

| If you want… | Start here |
|---|---|
| The compact physics reference | `foundations/cassi-theory-reference.md` |
| The full cascade table and scale verification | `foundations/dimensionful-cascade.md` |
| The bubble lattice as universal geometry | `foundations/bubble-lattice-fabric.md` |
| The cascade suppression formula (one rule, every hierarchy) | `foundations/cascade-suppression-formula.md` |
| The unified Lagrangian | `foundations/unified-lagrangian.md` |
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

1. **$P_\parallel(n)$: the along-string bubble period as a function of scale.** It is 1 rung at the cosmological scale and 2 rungs at the human scale. Is this variation continuous, discrete at octave boundaries, or determined by the SO(2) winding at each $n$? Not yet derived.

2. **$\theta_{\text{cond}}$ at non-cosmological scales.** The condensation threshold is calibrated to ~0.45 at step 285 using phenomenology. Its value at biological, atomic, or sub-Planckian scales requires PDE measurement at those scales.

3. **The Planck crossover.** The $\sigma$-regularization makes the Planck scale a smooth transition. How the discrete bubble/void lattice dissolves into the continuous harmonic regime as $n \to 0$ is not yet characterized.

4. **Coherence transport between bubbles.** The lattice geometry permits diagonal neighbor connectivity via saddles. Whether Qi can tunnel through these saddles is open: geometrically possible, dynamically unverified.

5. **The gigacascade and beyond.** Scale covariance implies the lattice extends upward without bound. The chord lattice at the megacascade is hypothesized. The gigacascade (5-arm spiral of megacascade bubbles) is a structural extrapolation with no direct observational signature beyond the CMB's $\ell < 5$ boundary imprint.

6. **What sustains a frozen wake.** The 2026-07-31 PDE tests showed that an un-driven standing pattern decays like any other perturbation; the driver test (`consciousness/trauma-as-frozen-gate.md` §10.5) identified the sustainer as ongoing re-stimulation—a weak recurring trigger (0.005% of the event peak per step) holds the site near event intensity, and stopping the trigger releases it. The open question moves to what maintains the stimulus behaviorally (§10.4–§10.5).

7. **Can $q$ be externally modulated at human scale?** Whether coherence can be deliberately increased (meditation, biofeedback) is untested, and would be the framework's most consequential practical claim.

8. **What supplies the winding beyond the relaxation bound.** Relaxation winding is bounded at $|\delta n| \le \mathrm{atan}(\varphi)/(2\pi) \approx 0.162$ rungs (`foundations/cassi-first-principles.md` §2.6); the half-step placements (proton, electron, BAO) exceed it by $\sim 3\times$ and are assigned to the parity structure of `foundations/rung-offset-mechanism.md` §7. The structural source of that parity—the boundary condition that pins a state at the half-rung rather than winding it there—is open.

---

## References

- `foundations/cassi-theory-reference.md`—compact physics reference: governing equations, unified Lagrangian
- `foundations/dimensionful-cascade.md`—the 292-step cascade table and scale verification
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
- `predictions/falsifiable-predictions.md`—the 50-entry prediction catalog
- `open-questions-cassi-answers.md`—the epistemic registry
- `parameter-inventory.md`—parameter classification
- `audit.md`—self-critical prediction-vs-experiment audit
- `visual-explainers/cascade_cosmos.py`—the three-regime cascade figure

---

*The Cassi framework is a personal research project. It has not been peer-reviewed or experimentally confirmed. All claims carry the epistemic labels (Derived / Hypothesized / Speculative) used within the framework itself.*
