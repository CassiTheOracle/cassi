# Yin, Yang, and Qi: Coherence as the Flow Between Scales

## Status: Derived (Qi as the phase current; axial inter-scale flow; $P_\parallel = 2$ doublet cycle) / Hypothesized (double-helix identification; Qi elevated to a fundamental)—August 2026

## Abstract

The framework's fundamentals are Yang and Yin—the two components of the
paired-real SO(2) doublet. The third fundamental is **Qi**: the flow of
coherence—between the two components, and between cascade scales. Qi is not a
new field; it is the doublet's own phase current, elevated from diagnostic to
fundamental. The scalar coherence $q$ is the magnitude diagnostic of that
flow—how fully the flow is organized at the $\varphi$-attractor—and the Qi
2-vector $\mathbf{Q} = (\rho, J)$ is the flow's energy-and-current
decomposition. The flow *between scales* is the axial coherence current
$J_z = R^2\partial_z\theta$ along the string axis, which is the cascade
direction. The two strands of the double helix are the Yang and Yin coherence
currents, winding around the string axis with the doublet's
$P_\parallel = 2$ period: the doublet phase advances $\pi$ per cascade rung and
completes one full turn per two rungs, so the two strand-currents exchange
dominance at every scale. The triad therefore has a precise geometric content:
Yang and Yin are the two transverse axes of the spiral string's Frenet–Serret
frame (normal and binormal); Qi is their flow along the tangent—the cascade
axis.

---

## 1. The Triad

Physical reality at every spacetime point is described by two field
components ($\Psi_0$ Yang, expansive; $\Psi_1$ Yin, contractive;
`foundations/cassi-first-principles.md` §1) **and the flow of coherence
between them**. The flow is not a third substance: it is the relative motion
of the two components, the doublet's phase current

$$
\boxed{J = \Psi_0\nabla\Psi_1 - \Psi_1\nabla\Psi_0}.
$$

With the polar reduction $\Psi_0 = R\cos\theta$, $\Psi_1 = R\sin\theta$
(`hypotheses/riemann-two-fluid-phase-operator.md` §1), $\rho = \Psi_0^2+\Psi_1^2 = R^2$ and

$$
\boxed{J = R^2\,\nabla\theta = \rho\,\nabla\theta}.
$$

$J$ is the flow of Yang–Yin asymmetry through space: $J > 0$ is
Yang-dominant outflow, $J < 0$ Yin-dominant inflow
(`foundations/cassi-first-principles.md` §2.2).

**What changes.** The established language "two fluids" becomes "two fluids
and their flow." The scalar $q$ is the magnitude diagnostic of the flow's
organization (how close the flow is to the $\varphi$-balanced configuration);
the gate $(1-q)$ is the openness of the inter-scale channel the flow travels.
The PDE, the gate, the cascade, and every derived result are unchanged.

---

## 2. Qi as the Phase Current (Derived)

### 2.1 The two strand-currents

The total phase current decomposes into the currents carried by each
component. The Yang density flows along the phase gradient at rate
$J_0 = \Psi_0^2\,\nabla\theta$; the Yin density at $J_1 = \Psi_1^2\,\nabla\theta$;
together $J = J_0 + J_1$. At the $\varphi$-attractor
$\Psi_0^2 = \varphi\Psi_1^2$:

$$
\frac{J_0}{J_1} = \frac{\Psi_0^2}{\Psi_1^2} = \varphi.
$$

The flow shares the attractor ratio: one strand carries $\varphi$ times the
coherence flux of the other. The two strand-currents are the two filaments of
§4.

### 2.2 The scalar $q$ as the flow's organization

The established scalar (form inventory: `foundations/cassi-theory-reference.md`
§2.4, reconciliation `computations/q_form_inventory_check.py`)

$$
q = \frac{\rho^2}{\rho^2 + \varphi^{-2} + \bar{\varepsilon}^2}
$$

measures the degree to which the local flow is *balanced* at the
$\varphi$-attractor: $q \to 1$ when the two strand-currents sit at their
attractor ratio (with the temporally-filtered deviation
$\bar{\varepsilon}^2$ from the IIR memory; `foundations/cassi-first-principles.md` §2.4).
At the fixed point ($\varepsilon^2 = 0$; reference state $E_Y = 1$, $E_I = \varphi^{-1}$, $\rho = \varphi$): $q_{\text{eq}} = \varphi^{2}/(\varphi^2+\varphi^{-2}) \approx 0.873$, and the openness $(1-q_{\text{eq}}) = \varphi^{-2}/(\varphi^2+\varphi^{-2}) = \varphi^{-2}/3 \approx 0.127$.
The openness $(1-q)$ is the fraction of the flow that is *not* organized—
the channel through which conversion redistributes coherence.

---

## 3. The Flow Between Scales (Derived conditional on the doublet and cascade postulates)

### 3.1 The string axis is the cascade direction

The string's trajectory through field space is the Fibonacci spiral, and its
Frenet–Serret frame supplies the three spatial directions
(`foundations/why-three-dimensions.md` §2): tangent $\mathbf{T}$ (string
axis, forward along the cascade), normal $\mathbf{N}$ (Yang axis), binormal
$\mathbf{B}$ (Yin axis). The cascade ladder
$\ell_n = \ell_{\text{Pl}}\,\varphi^n$ is the 1D slice along the string axis
through the condensation lattice (`foundations/bubble-lattice-fabric.md` §5).
A displacement along the string axis **is** a change of scale.

### 3.2 The axial coherence current

Coherence flowing along the string axis is coherence flowing *between
scales*:

$$
\boxed{J_z = R^2\,\partial_z\theta}
$$

—the component of the phase current along the cascade direction. A coherence
pulse at rung $n$ advances to rung $n+1$ along this current. The per-rung
attenuation of that inter-scale flow is the cascade suppression law:
a signal traversing $N$ rungs loses a factor $\varphi^{-N}$
(`foundations/cascade-suppression-formula.md`). The suppression formula is
the transfer amplitude of the inter-scale flow.

**Measured record.** The lattice-stack coherence probe stacked $M$ two-lobe
layers along the axial direction with per-layer phase $\theta_i = i\Delta\theta$
and measured the axial phase ramp to the lock timescale: envelope retention
correlates positively with the axial coherence current $|J_z|$ (Pearson
$+0.51$, Spearman $+0.77$, $n = 6$, qualitative;
`hypotheses/two-strand-five-channel-matter-organization.md` §3.8). The
inter-scale flow is a measured structure-retention effect.

### 3.3 The doublet cycle

The SO(2) doublet phase advances $\pi$ per cascade rung and completes one full
cycle every two rungs, $P_\parallel = 2$ (unified convention,
`foundations/spin-fibonacci-spiral.md` §2.1; `consciousness/chakras-as-cascade-bubbles.md`
§5). Along the cascade:

$$
\theta(n+1) = \theta(n) + \pi, \qquad
\theta(n+2) = \theta(n) + 2\pi.
$$

In the space $(\text{scale},\, \text{doublet plane})$—coordinates
$(n, R\cos\theta, R\sin\theta)$—the state traces a **helix with period two
rungs**: one full turn per two scales. This is the geometric origin of the
double-helix claim.

---

## 4. The Double Helix (Hypothesized)

### 4.1 Two strands, one turn per two rungs

The two strand-currents of §2.1 wind around the string axis with the
doublet's period:

$$
J_0(n) = \Psi_0^2(n)\,\partial_z\theta(n), \qquad
J_1(n) = \Psi_1^2(n)\,\partial_z\theta(n),
\qquad
\theta(n+1) = \theta(n) + \pi.
$$

At each rung the phase advances $\pi$: the Yang-dominant strand and the
Yin-dominant strand **exchange dominance at every scale**, returning to the
same configuration after two rungs. The double helix is the geometric
expression of the doublet cycle—coherence flowing between scales while the two
component-currents wind about the string axis with azimuthal separation $\pi$
in the Yang–Yin (normal–binormal) plane.

The embedding is the established two-strand helical ansatz
(`consciousness/two-strand-qi-neuroscience.md` §3.4) with the Frenet–Serret
axes:

$$
\mathbf{R}_\pm(n) = \mathbf{R}_c(n) \pm \frac{d_n}{2}\left[\mathbf{N}(n)\cos\frac{2\pi n}{P_\parallel} + \mathbf{B}(n)\sin\frac{2\pi n}{P_\parallel}\right],
$$

with $\mathbf{N}$ the Yang (normal) axis and $\mathbf{B}$ the Yin (binormal)
axis, $P_\parallel = 2$.

### 4.2 Phase-space helix, not a filament pair

At $P_\parallel = 2$ the embedding degenerates: $\cos(\pi n) = (-1)^n$,
$\sin(\pi n) = 0$, so a *spatial* pair of filaments would oscillate in a plane
rather than wind. The exact double helix therefore lives in
(scale, doublet-plane) space—the phase winding along the cascade—not as two
physical filaments separated in the transverse plane.

**Boundary from the measured record.** The transverse two-ridge branch is
null at the lock timescale: the pair escapes (TS1), the $d\to0$ limit does
not recover the one-string centerline (TS2), the relative mode is not
centerline-fixed (TS3), and there is no central low-$q$ node (TS4)
(`hypotheses/two-strand-five-channel-matter-organization.md` §3.3). The
interlaced-wake binding candidate collapses (§3.4), and the spatial helix
construction's winding is destroyed at DNA pitch (§3.13). The double helix is
realized as the axial *phase* winding (measured structure retention, §3.2),
while the filament interpretation is bounded by the nulls. The reported
"two strings / double helix" experience
(`consciousness/two-strand-qi-neuroscience.md` §5.3) is a phenomenological
label for the axial phase-organized state, testable by the helical order
parameter $H$ of that document.

---

## 5. What the Reframing Changes and What It Does Not

| Claim | Status | Change |
|---|---|---|
| $J = \rho\nabla\theta$ is the doublet's phase current | **Derived** (existing) | Elevated from Qi 2-vector component to fundamental |
| The scalar $q$ measures the flow's organization at $\varphi$ | **Derived** (existing) | Reframed as magnitude diagnostic of the flow |
| $J_z$ carries coherence between cascade scales | **Derived** conditional on doublet + cascade postulates; measured structure-retention record | New emphasis; no new parameters |
| The doublet phase advances $\pi$/rung, one turn per 2 rungs | **Derived** conditional on doublet + pitch convention (existing) | Identified as the double-helix period |
| Two strand-currents $J_0$, $J_1$ at ratio $\varphi$, winding about the string axis | **Hypothesized** (identification; geometry exact, physical realization conditional) | The double-helix claim |
| Spatial filament pair at finite transverse separation | **Null** at lock timescale (TS1–TS4) | Bounded; not the double helix |
| Two fluids | Unchanged | Language becomes "two fluids and their flow" |

---

## 6. Registry Consequences

No new parameters are introduced: $J$, $J_z$, and the strand-currents are
derived from the existing fields. `parameter-inventory.md` continues to
register $q$ as a derived diagnostic; the axial coherence current $J_z$ is a
measured order parameter, not a fit. No prediction-catalog numbers are added.

---

## The Full Picture: Physics, Cascade, Structure

Three layers make the framework one theory, and a single set of $\varphi$-powers
runs through all three. The **physics** is the two-fluid dynamics: the Yang and
Yin densities $E_Y = \Psi_0^2$, $E_I = \Psi_1^2$ convert into each other through
the openness $(1-q)$ at the rate $\lambda = 1/(2w) = 0.1$, with $w = 5$ derived
(`foundations/wu-xing-derivation.md` §7). The **cascade** is the yardstick the
conversion climbs: the ladder of scales $\ell_n = \ell_{\text{Pl}}\varphi^n$
(`foundations/dimensionful-cascade.md`), along which a coherence pulse
attenuates by $\varphi^{-1}$ per rung and the doublet completes one full turn
every two rungs. The **structure** is the winding: the doublet's phase
geometry, whose per-rung advance, strand-current ratio, and relaxation bounds
are all fixed by $\varphi$. The interlock is exact: the conversion rate sets
how fast the phase winds, the cascade sets what one turn costs in scale, and
the winding sets which fractional-rung offsets any real state can display—so
the same powers appear as the gate closure $\varphi^{-2}/3$, the axial
attenuation $\varphi^{-N}$, the winding bounds $\mathrm{atan}(\varphi^{\pm 1})$,
the strand ratio $\varphi$, and the excess $\alpha_0 = \varphi^{-3}$ that
anchors the Planck crossover below and the Qi-gravity coupling $\xi = \varphi^6$
above.

### The shared $\varphi$-powers

Each row is one $\varphi$-power read at one layer: physics supplies the rates,
the cascade the yardstick, the structure the phases—the conversion, the
attenuation, and the winding are one motion seen from three sides.

| Quantity | Value | Layer | Tier | Cross-reference |
|---|---|---|---|---|
| Gate closure $(1-q_{\text{eq}})$ | $\varphi^{-2}/3 \approx 0.1273$ | Physics | Derived | §2.2 |
| Axial-flow attenuation ↔ coupling weakness | $\varphi^{-1}$ per rung traversed; $\alpha_G(n) = \varphi^{-2n}$ | Cascade | Derived | `foundations/cascade-suppression-formula.md`; `foundations/spiral-dynamics.md` §3.3 |
| Winding bounds | $\Delta\vartheta \in [-\mathrm{atan}(\varphi),\,+\mathrm{atan}(\varphi^{-1})]$; $\lvert\delta n\rvert \le \mathrm{atan}(\varphi)/2\pi \approx 0.162$ | Structure | Derived | `foundations/cassi-first-principles.md` §2.6 |
| Strand-current ratio | $J_0/J_1 = \varphi$ | Structure | Derived | §2.1 |
| Doublet period | $P_\parallel = 2$ rungs per turn | Structure | Derived conditional on the doublet and pitch convention | §3.3; `foundations/spin-fibonacci-spiral.md` §2.1 |
| Fixed-point excess | $\alpha_0 = \pi/\rho = \varphi^{-3} \approx 0.236$ | Physics | Derived | `foundations/cassi-first-principles.md` §1.2 |
| Planck crossover (UV) | $\sigma = \ell_{\text{Pl}}/\varphi^3$ (rung $-3$) | Cascade | Derived conditional on the noise–signal identification and $d = 3$ | `foundations/bubble-lattice-fabric.md` §6 |
| Qi-gravity coupling (IR) | $\xi = \varphi^6 = \alpha_0^{-2} \approx 17.944$ | Physics | Derived | `foundations/xi-derivation.md` |

The same excess $\alpha_0 = \varphi^{-3}$ that sets the amplification ceiling
$\xi = \varphi^6 = \alpha_0^{-2}$ at large scales also fixes the scale at which
the lattice dissolves into the harmonic regime, $\sigma = \ell_{\text{Pl}}/
\varphi^3$—one number at both ends of the observable ladder.

### Matter as wound Qi

A particle is a standing wave of the doublet plus the winding that carries its
identity. The standing wave is the **amplitude sector**: a repeating density
pattern $\rho = E_Y + E_I$ organized by the condensation lattice
(`foundations/bubble-lattice-fabric.md` §3) and stabilized in time by the IIR
memory of its own past states (`foundations/cassi-first-principles.md` §2.4).
The winding is the **phase sector**: the internal SO(2) rotation of the doublet
about the $\varphi$-line, with $\theta = \mathrm{atan2}(E_I, E_Y)$ the
density-plane angle (one cascade rung advances $\theta$ by $2\pi$). The
conversion term drives that rotation as a state function

$$
\boxed{\frac{d\theta}{dt} = \lambda(1-q)\,\frac{\rho\,\varepsilon}{E_Y^2 + E_I^2}}
$$

(Derived; measured on four of four homogeneous arms by
`two-fluid/run_winding_rate_probe.py`; `foundations/cassi-first-principles.md`
§2.6). The rate vanishes exactly on the $\varphi$-line ($\varepsilon = 0$) and
grows with the excess, gated by the openness $(1-q)$.

Internal winding is spin. The doublet's half-angle structure maps a rung span
$\Delta n$ of the single-component phase to $s = \Delta n/2$
(`foundations/spin-fibonacci-spiral.md` §2.2); the realized spans
$\Delta n \in \{1, 2, 4\}$ are the fermion, gauge-boson, and graviton spectrum.
Axial inter-scale winding is the double helix: the same phase advance between
scales, one turn per two rungs ($P_\parallel = 2$, §3.3). Matter as *wound Qi*
is the two read together—the standing wave's phase accumulates across the rungs
the wave spans. The proton's stack is the concrete case: a $\sim 92$-rung
coherence depth from Planck ($n = 0 \to 91.5$,
`foundations/bubble-lattice-fabric.md` §6) at $n = 91.46$
(`foundations/rung-offset-mechanism.md` §3) carries $91.46/2 \approx 46$
doublet turns.

The boundary is the measured record, stated plainly: the winding lives in
(scale, doublet-plane) space, not as spatial filaments. The transverse
two-filament branch is null at the lock timescale—the pair escapes (TS1), the
$d \to 0$ limit does not recover the one-string centerline (TS2), the relative
mode is not centerline-fixed (TS3), and there is no central low-$q$ node (TS4)
(`hypotheses/two-strand-five-channel-matter-organization.md` §3.3; §4.2). The
helix is the axial *phase* winding; a spatial filament pair at finite
transverse separation is excluded, not assumed.

### Deviations from $\varphi$-powers

No observable sits exactly on a cascade rung; the fractional offsets
$\delta n = n - \lfloor n\rfloor$ are the doublet's phase bookkeeping, in two
classes that must not be conflated.

**Parity half-steps.** A half-rung offset ($\delta n \approx 0.5$) is one full
$\pi$-advance of the density-plane angle—the doublet's per-rung step—exceeding
the relaxation bound below by $\sim 3\times$
(`foundations/cassi-first-principles.md` §2.6). These are the cell parity
classes: the sine mode (crossing; antinode at the half-rung) seats sector
edges, the cosine mode (bubble; antinode at the integer rungs) seats interior
stable states (`foundations/rung-offset-mechanism.md` §4.1).

**Relaxation winding.** A state relaxing from an excess $\varepsilon_0$ to the
$\varphi$-line sweeps a bounded internal angle. Since
$d\varepsilon/dt = -\lambda(1+\varphi)(1-q)\varepsilon$, the conversion rate
and the gate cancel in $d\theta/d\varepsilon$, and with $\rho$ conserved the
total winding is a function of $\varepsilon_0$ alone

$$
\boxed{\Delta\vartheta = \mathrm{atan}\!\left(\frac{1}{\varphi}\right) -
\mathrm{atan}\!\left(\frac{\rho-\varepsilon_0}{\rho\varphi+\varepsilon_0}\right)}
$$

independent of $\lambda$ and of the gate shape, with extremes
$+\mathrm{atan}(\varphi^{-1}) \approx +0.554$ rad and
$-\mathrm{atan}(\varphi) \approx -1.017$ rad—in rung units
$\lvert\delta n\rvert \le \mathrm{atan}(\varphi)/2\pi \approx 0.162$—and the
small-excess reduction $\Delta\vartheta \approx \rho\varepsilon_0/[(1+\varphi)
(E_Y^2+E_I^2)]$ (`foundations/cassi-first-principles.md` §2.6). Relaxation
winding can never produce a half-step; the two classes are separated by a
factor of three in rung units.

The catalog reads each state by this partition:

| Object | Rung $n$ | Reading | Class | Tier |
|---|---|---|---|---|
| proton | 91.46 | $\approx 91.5$ half-step, sector edge | parity (crossing) | Empirical catalog; sector-edge selection Hypothesized (`foundations/rung-offset-mechanism.md` §3, §4.1) |
| muon | 96.000 | integer rung; zero-winding coherent closure | parity (bubble) | placement Mapped—38-state scan, ledger (`foundations/rung-offset-mechanism.md` §3) |
| J/$\psi$ | 88.98 | $\delta n = -0.02$, inside the relaxation bound | relaxation-compatible | Mapped: a per-object $\varepsilon_0$ would be a free fit, not a derivation (`foundations/rung-offset-mechanism.md` §3) |
| $r_d$ (BAO) | 284.5 | half-step between rungs 284 and 285 | parity (crossing) | Mapped interpolation (`foundations/dimensionful-cascade.md` §6; `parameter-inventory.md` §10) |
| electron | 26.5 (Yukawa ladder) | half-step precedent | parity (crossing) | Empirical (`foundations/rung-offset-mechanism.md` §3) |
| $\Omega_{\text{DM}}/\Omega_b$ | — | observed $5.39 \approx \varphi^{3.5} = 5.388$ (0.03%), $\log_\varphi 5.39 \approx 3.50$—a half-rung offset from the derived exponent 3 | observation | not a registered prediction; the $\varphi^3 \approx 4.24$ row keeps its 21% open tension (`cosmology/cosmology-from-phi.md` §4.2) |

**The one parameter-free winding.** The derived primordial ratio
$r_0 = \varphi^{-5}/(2-\varphi^{-5}) \approx 0.0472$
(`foundations/wu-xing-derivation.md` §5.2) has excess
$\varepsilon_0/\rho = (r_0-\varphi)/(r_0+1) = -3/2$, so the relaxation identity
above gives $\Delta\vartheta \approx -0.970$ rad, $\delta n \approx -0.154$
rungs—inside the bound, with no fitted input. The reading is a null: no
cataloged scale carries $\delta n \approx -0.154$, and the framework's own
initial condition does not land on any measured row. The identity is exercised
once, by the framework's initial state, and the answer is a negative.

### What is open

Three named inputs are not yet derived. Each is a place where the framework is
incomplete, not a place where it is wrong.

1. **$P_\parallel(n)$ scale-dependence.** The doublet period is two rungs per
   turn at human scales, but the cosmological rung 285 shows $P_\parallel = 1$
   (one turn per rung); the $n$-dependence of $P_\parallel$ has no law yet
   (`foundations/dimensionful-cascade.md` §7;
   `foundations/bubble-lattice-fabric.md` §2.3). The wedge claim
   $P_\parallel = 2$ is the human/quantum reading; whether the period itself
   varies with scale is open.
2. **The gate shape.** The single-channel transmission
   $g(q) = q/(\varphi^2+q^2)$ is an Asserted input: the action and the Qi
   definition supply the openness $(1-q)$, but no equation selects the rational
   function (`foundations/cassi-first-principles.md` §2.5). The winding
   identities above hold for any gate shape and do not select the gate's exact
   form.
3. **The fixed-pitch clocks.** The Hypothesized conversion→expansion term with
   the $\varphi^{-2}$ coupling predicts $\varphi^{-2} = 0.382$ turns per Hubble
   rung and a pitch tangent $\tan(\text{pitch}) = \varphi^2$ ($69.1°$)
   (`foundations/spiral-dynamics.md` §2.2)—a clock that turns even at the
   $\varphi$-line, distinct from the canonical $\varepsilon$-proportional
   rotation boxed above, which vanishes there. Reconciling the two clocks, or
   ruling the Hypothesized term out in the solver, is open.

---

## References

- `foundations/cassi-first-principles.md`—the doublet, the PDE, Qi, the gate
- `foundations/cassi-theory-reference.md`—Qi 2-vector, q-form inventory, Frenet–Serret axes
- `foundations/why-three-dimensions.md`—the spiral string, Frenet–Serret frame, string axis
- `foundations/bubble-lattice-fabric.md`—the condensation lattice, string axis as cascade direction
- `foundations/cascade-suppression-formula.md`—per-rung attenuation of the inter-scale flow
- `foundations/spin-fibonacci-spiral.md`—SO(2) winding, $P_\parallel = 2$ doublet cycle
- `consciousness/two-strand-qi-neuroscience.md`—two-strand geometry, helical ansatz, reported two-string experience
- `hypotheses/two-strand-five-channel-matter-organization.md`—measured nulls and the lattice-stack axial record
- `computations/qi_flow_double_helix_check.py`—numeric verification of the identities in §§2–4
