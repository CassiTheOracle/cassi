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
