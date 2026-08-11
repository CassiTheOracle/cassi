# Quantum Measurement as Organized Cascade Perturbation

## Status: Derived (coherent-field statistics), outcome basis open—August 2026

## Abstract

The same coherence-budget mechanism that gives the proton its $10^{910}$-year
lifetime (`foundations/proton-coherence-budget.md`) resolves the quantum
measurement problem. A superposition is a multi-branch condensed pattern in the
Qi field; its inter-branch coherence lives at a **single cascade rung**—the
rung of the quantum number being superposed—not across all 92 supporting
rungs. Measurement is organized perturbation phase-matched to that rung; its
collapse probability per interaction is $\mathcal{O}(1)$, not cascade-suppressed.
Environmental decoherence is random perturbation at the **same single rung**
with $\mathcal{M} \approx 0$—it causes off-diagonal decay (standard
Zurek decoherence) but **no single-outcome selection**. Only organized
($\mathcal{M} \approx 1$) perturbation can select a branch. The Born rule then
follows from **coherent-field detection statistics** (§4): the field at the
detector is a coherent excitation of the linear quantum sector with amplitude
$A(x) \propto \psi(x)$; absorbed quanta are Poisson with mean
$|A(x)|^2 \propto |\psi(x)|^2$; the outcome probability is the relative rate
$|\psi(x)|^2/\sum|\psi(x')|^2$—with no additional postulate. Which observable
the gate measures (the outcome basis) remains an input (§4.6).

---

## 1. The problem restated

In standard quantum mechanics, measurement collapses the wavefunction into an
eigenstate with probability $|\langle\phi|\psi\rangle|^2$ (the Born rule), but
the theory provides no mechanism—collapse is a *postulate*, not a derivation.
Environmental decoherence can diagonalize the density matrix in a preferred
basis but cannot select a single outcome, leaving the "measurement problem"
intact.

In Cassi, the two-fluid field provides a medium in which collapse is a
**physical process**—the same process that stabilizes protons and annihilates
antimatter, applied to the inter-branch coherence of a superposition.

---

## 2. The superposition as a multi-branch Qi pattern

A quantum superposition $|\psi\rangle = \alpha|0\rangle + \beta|1\rangle$
corresponds to the Qi field hosting **two competing templates** $\phi_0(s)$ and
$\phi_1(s)$—spatially overlapping but phase-incompatible standing-wave
configurations. Both are condensed patterns, each stable in isolation (each has
its own full cascade depth and the associated $10^{910}$-year stability). The
superposition persists because the **inter-branch coupling** is weak—the two
templates are nearly orthogonal in Qi phase space, and their interaction is a
surface term at the rung where they differ.

The crucial structural fact: the two branches share the **same cascade rungs
$i = 0$ through $n-1$** (mass, charge, color—all quantum numbers held in
common). They differ **only at rung $n$**—the rung of the superposed
observable (spin, polarization, path, energy level). The inter-branch coherence
is therefore a **single-rung** phenomenon, not a full-cascade phenomenon.

| Structure | Cascade depth of coherence | Decoherence pathway | $P_{\text{per cycle}}$ |
|-----------|---------------------------|---------------------|------------------------|
| Proton (single condensate) | $n = 91.5$ rungs | Random dephasing at all 92 rungs | $\varphi^{-4506} \approx 10^{-942}$ |
| Superposition (two-branch) | **1 rung** ($n$) | Random perturbation at rung $n$ | $\varphi^{-n-3} \approx 10^{-20}$ |
| Superposition + measurement | 1 rung ($n$) | **Organized** perturbation at rung $n$ | $\mathcal{O}(1)$ |
| Matter-antimatter pair | $n = 91.5$ rungs | **Organized** anti-phase at all 92 rungs | $\mathcal{O}(1)$ |

---

## 3. Organized vs. random perturbation

### 3.1 The phase-matching factor $\mathcal{M}$

An environmental perturbation couples to the field at rung $i$ with an
effective interaction strength proportional to the **phase alignment**
between the perturbation and the target pattern:

$$P_{\text{decohere},i} = (1-q_i) \times \mathcal{M}_i$$

where $\mathcal{M}_i \in [0,1]$ measures the phase-matching between the
perturbation and the pattern at rung $i$:

- $\mathcal{M}_i \approx 1$: the perturbation is **organized**—it matches
  the phase structure of the target. The per-cycle decoherence probability
  is $1-q_i$, independent of cascade depth.

- $\mathcal{M}_i \approx 0$: the perturbation is **random**—its phase is
  uncorrelated with the specific quantum number's phase structure. Each
  random interaction provides zero net phase-matching to the inter-branch
  coherence; the superposition's off-diagonal elements decay slowly via
  accumulated random phase drift, not via organized attack.

### 3.2 Measurement: $\mathcal{M} \approx 1$

A measurement apparatus is designed to couple to a specific observable. It
produces a perturbation **phase-matched** to the corresponding cascade rung.
For a spin measurement (Stern-Gerlach), the magnetic field gradient is
organized to couple to spin—$\mathcal{M}_{\text{spin}} \approx 1$. For a
position measurement (double-slit with detector), the photon absorption is
organized to couple to path—$\mathcal{M}_{\text{path}} \approx 1$.

The organized perturbation attacks the inter-branch coherence at the target
rung with $\mathcal{O}(1)$ probability per interaction. The superposition
collapses as rapidly as the measurement coupling strength allows:
strong coupling → single-interaction collapse; weak coupling → gradual
which-path information accumulation.

### 3.3 Environmental decoherence: random, unphase-matched

Thermal photons, stray magnetic fields, cosmic rays—these couple to the
superposition at the **same single rung** as measurement (the rung of the
superposed quantum number). But their coupling is **random**—they carry no
phase information about the specific inter-branch phase difference.
$\mathcal{M}_{\text{env}} \approx 0$ for the branch-selection channel.

The result is **density-matrix diagonalization without single-outcome
selection**. Random interactions accumulate random phase errors between the
branches, causing the off-diagonal elements $\rho_{01}$ to decay—this is
standard environmental decoherence, described fully by Zurek et al. But
because $\mathcal{M}_{\text{env}} \approx 0$, there is no organized attack on
either branch's Qi density. The diagonal elements $\rho_{00}$ and $\rho_{11}$
are preserved. No branch is selected; no single outcome emerges.

Standard decoherence correctly explains why macroscopic superpositions don't
persist (many environmental degrees of freedom → rapid off-diagonal decay)
and why microscopic superpositions do (few coupling channels → slow decay).
What it cannot explain—and what the Qi mechanism supplies—is why
measurement produces a **single definite outcome** with **Born-rule
probabilities** rather than just a diagonal density matrix.

Measurement: $\mathcal{M} \approx 1$, attacks one rung → single outcome with
$|\alpha|^2$ probability (§4). Environment: $\mathcal{M} \approx 0$, same
rung → off-diagonal decay only, no branch selection. The distinction is
**phase-matching alone**—not cascade depth.

---

## 4. The Born rule from coherent-field statistics

### 4.1 Detection is gate-mediated absorption from a linear field

The quantum sector of the two-fluid field is **linear**—the Schrödinger limit
of the PDE (`foundations/cassi-theory-reference.md` §5.1) with a quadratic
kinetic term (`foundations/unified-lagrangian.md` §1.1). A superposition
$\sum_i c_i |i\rangle$ is therefore a linear sum of field configurations: the
field amplitude at the detector is

$$\psi(x) = \sum_i c_i\,\phi_i(x)$$

with the cross terms present from the start. Amplitudes superpose and interfere
automatically; no interference postulate is needed.

A detector is a region where the **Qi gate** (`foundations/cassi-theory-reference.md`
§2.5) opens along the measured field direction at the target rung: an organized
($\mathcal{M} \approx 1$, §3.2) single-rung conversion that absorbs one quantum
of field excitation. Each absorption removes one quantum from the field mode at
$x$ and registers an outcome.

### 4.2 The absorbed-quanta count is Poisson

*Input.* The field mode at the detector sits in a **coherent state** $|A(x)\rangle$
with amplitude $A(x) = g\,\psi(x)$, where $g$ is the detector's absorption
coupling (efficiency). Coherent states are the natural states of a free linear
field (Glauber 1963); the two-fluid quantum sector is free to the extent the
$\varphi$-attractor condensate is a slowly varying background.

For a coherent state, the number of quanta absorbed in a fixed exposure is
**Poisson** (standard quantum-optics result; Glauber 1963, Mandel & Wolf 1995):

$$P(n) = \frac{e^{-\lambda(x)}\,\lambda(x)^n}{n!}, \qquad
\lambda(x) = |A(x)|^2 = g^2\,|\psi(x)|^2$$

Verified numerically: sampled counts reproduce the Poisson mean–variance
identity and $P(0) = e^{-\lambda}$ (`computations/coherent_field_born_rule.py` §1).

### 4.3 The outcome probability is the relative rate

A measurement reports the **first absorption**. Each detector channel $x$ is an
independent Poisson process with rate $\lambda(x)$; the first event across the
array lands at $x$ with probability equal to its relative rate
(competing-exponential law):

$$\boxed{P(x) = \frac{\lambda(x)}{\sum_{x'} \lambda(x')}
= \frac{|\psi(x)|^2}{\sum_{x'} |\psi(x')|^2}}$$

Three properties follow without further assumption:

- **Exact at any coupling.** The detector efficiency $g$ cancels; the law holds
  for strong and weak absorption alike. The weak-coupling limit
  $1 - e^{-\lambda(x)} \approx \lambda(x)$ governs the single-channel *firing*
  probability in a short exposure, but the relative rate is the normalized
  outcome law—numerically confirmed: for $\lambda = (0.5,\,0.3)$ the Born
  probability is $0.625$, while the unnormalized firing probability
  $1 - e^{-0.5} = 0.3935$ is not the outcome probability
  (`computations/coherent_field_born_rule.py` §4).
- **Normalization automatic.** $\sum_x P(x) = 1$ identically.
- **Frequencies converge to it.** Conditional on $N$ total absorptions the
  channel counts are multinomial with probabilities $\lambda/\sum\lambda$
  (Poisson splitting), so long-run detection frequencies converge to
  $|\psi(x)|^2$ (verified numerically, §3 of the script).

For a two-branch superposition with detectors that resolve the branches
($\phi_0$, $\phi_1$ with disjoint support or observable-tagged channels), the
boxed law reduces to the familiar form

$$\boxed{P(\alpha) = \frac{|\alpha|^2}{|\alpha|^2 + |\beta|^2}}$$

With overlapping support the same law yields the interference pattern
$|\psi(x)|^2$—complementarity is automatic.

### 4.4 Interference and normalization are automatic

Both derive from the linearity of the quantum sector:

- **Interference:** $|\psi_1 + \psi_2|^2 = |\psi_1|^2 + |\psi_2|^2 +
  2\operatorname{Re}(\psi_1^*\psi_2)$—the cross term is present by
  construction (verified numerically, §5 of the script).
- **Normalization:** a normalized state $\sum_x |\psi(x)|^2 = 1$ gives
  $\sum_x P(x) = 1$ identically through the relative-rate form.

### 4.5 The survival rule as a secondary reading

The earlier form of this section asserted a selection rule: the lower-$q$
branch decoheres first, and branch survival is proportional to a branch Qi
density $q_\alpha \propto |\psi_\alpha|^2$. That rule rested on a branch-level
$q$ distinct from the canonical gate
$q = \rho^2/(\rho^2 + \varphi^{-2} + \varepsilon^2)$
(`foundations/cassi-theory-reference.md` §2.4), and the survival dynamics were
asserted, not derived. The coherent-field statistics of §4.1–4.3 replace it:
the quadratic law follows from counting, with no survival postulate.

The rule survives only as a consistency reading. The canonical gate $q$ is
monotonically increasing in field intensity $\rho^2$ at fixed self-prediction
error $\varepsilon^2$, so the branch with larger $|\alpha|^2$ is the more
coherent branch—a stability bias toward higher $q$ is directionally consistent
with the $|\alpha|^2$ law. It is not its source: $q$ saturates toward 1 and is
not proportional to $|\psi|^2$ (verified numerically, §6 of the script), so it
cannot supply the exact quadratic statistics.

### 4.6 Open: the outcome basis

The derivation fixes the outcome *probabilities* for the gate's outcomes; it
does not derive which observable the gate measures. In the framework's current
form the gate opens **along the measured field direction**—the direction the
apparatus is constructed to couple to—so the outcome basis is the **gate's
eigenbasis** (the eigenbasis of the measured observable; a Stern-Gerlach
gradient defines the spin quantization axis, a which-path detector the path
basis). Which observable a given apparatus realizes is set by its construction,
not by the field equations. **The outcome-basis selection is an input, not
derived.**

> **Inputs.** The Born rule of §4.3 is derived from: (i) the quantum sector is
> linear (Schrödinger limit, `foundations/cassi-theory-reference.md` §5.1);
> (ii) the field mode at the detector is a coherent state with amplitude
> $A(x) = g\psi(x)$ (§4.2); (iii) detection is gate-mediated absorption of a
> quantum—organized single-rung conversion, $\mathcal{M} \approx 1$ (§3.2,
> theory-reference §2.5); (iv) the outcome basis is the gate's eigenbasis,
> set by apparatus construction (§4.6).

---

## 5. Strong and weak measurement as limits of the same process

### 5.1 Strong measurement (single-interaction collapse)

When the measurement coupling is strong (one interaction provides
$\mathcal{M} \approx 1$ at the target rung), the superposition collapses in
that single interaction. The outcome is branch $\alpha$ with probability
$|\alpha|^2$ (§4.3).

Example: a photon absorbed by a detector. The absorption is a single organized
interaction at the path rung. Collapse is instantaneous. The photon's which-path
superposition dissolves; the detector registers the first absorption, which
lands on path $x$ with probability $|\psi(x)|^2$ (§4.3).

### 5.2 Weak measurement (gradual which-path acquisition)

When the measurement coupling is weak (many interactions needed to accumulate
$\mathcal{M} \to 1$ at the target rung), collapse is gradual. Each weak
interaction provides partial phase-matching: $\mathcal{M}_k \ll 1$ per
interaction, and $\sum_k \mathcal{M}_k \to 1$ over many interactions.

During the gradual collapse, the accumulated counts $\lambda(x)$—the
which-path information—update the outcome posterior: the channel that has
absorbed quanta carries a higher effective rate, and the surviving field
amplitude reweights accordingly. This is observable as "weak values" and
trajectories in weak measurement experiments (Aharonov, Albert, and Vaidman 1988).

The framework predicts: weak trajectories should trace a path determined by the
field-intensity gradient $\nabla|\psi(x)|^2$, converging to the $|\psi(x)|^2$
outcome distribution as $\sum \mathcal{M}_k \to 1$.

---

## 6. Relation to proton stability and annihilation

This completes a **trifecta** of coherence-budget phenomena:

| Phenomenon | Structure | Perturbation | Rungs attacked | $P_{\text{per cycle}}$ |
|-----------|-----------|-------------|----------------|------------------------|
| Proton decay | Single condensate | Random | All $n$ rungs | $\varphi^{-(n(n+1)/2 + \delta(n+1))} \approx 10^{-942}$ |
| Annihilation | Particle-antiparticle pair | Organized (anti-phase) | All $n$ rungs | $\mathcal{O}(1)$ |
| **Measurement collapse** | Superposition | **Organized (phase-matched)** | **1 rung** | $\mathcal{O}(1-q_n) \approx 10^{-20}$ |

Measurement is the *single-rung* analogue of annihilation—organized attack,
but targeting only the rung where the branches differ, not the full cascade
structure. This is why measurement collapses superpositions with $|\alpha|^2$
statistics but leaves the particle itself intact (no mass-to-energy conversion).
Annihilation attacks all rungs—total dissolution. Measurement attacks one
rung—branch selection, particle survives. Proton decay attacks all rungs but
randomly—nothing happens on laboratory timescales.

---

## 7. Testable predictions

| # | Prediction | Observable | Status |
|---|-----------|-----------|--------|
| M1 | Environmental decoherence cannot produce single-outcome selection with Born-rule statistics—only organized ($\mathcal{M} \approx 1$) perturbation can | Run long-duration superposition experiments under controlled random noise; observe off-diagonal decay (standard decoherence) but no biased branch selection; check that outcome distributions remain uniform (no Born-rule signature) until organized measurement is applied | Consistent with standard decoherence results; the null is that random noise never produces biased outcomes |
| M2 | Weak measurement trajectories follow the field-intensity gradient | Reconstruct weak trajectories; compare to $\nabla|\psi(x)|^2$ predicted path | Testable with existing weak-measurement apparatus |
| M3 | Measurement collapse time scales inversely with phase-matching $\mathcal{M}$ | Vary detector coupling strength; measure collapse onset vs coupling | Testable with tunable-detector experiments |
| M4 | Single-photon which-path detection produces $|\psi(x)|^2$ statistics with no deviation beyond Poisson | Extended quantum optics statistics; no "collapse noise" beyond shot noise | The defining content of §4.2–4.3: counts are Poisson with mean $\propto |\psi(x)|^2$; testable with high-statistics quantum optics |
| M5 | Collapse is NOT a spontaneous process—it requires organized perturbation; zero environmental-collapse events in ultra-high-vacuum, ultra-low-temperature, shielded superpositions | Run superposition lifetime tests under maximally isolated conditions; no decay to classical state | Testable with matter-wave interferometry in space (MAQRO) |

---

## 8. Epistemic boundaries

### Derived (from the Schrödinger limit, with the §4 inputs)

- Single-rung vs full-cascade coherence architectures (§2): superposition decoherence costs one rung; proton decay costs all 92 (0 → 91.5)
- Born rule from coherent-field statistics: $P(x) = |\psi(x)|^2/\sum|\psi(x')|^2$ (§4), conditional on the inputs listed in §4.6; verified numerically (`computations/coherent_field_born_rule.py`)

### Hypothesized (mechanism specified, testable)

- Phase-matching factor $\mathcal{M}$ as the bridge between organized and random regimes (§3.1)
- Strong/weak measurement limits as $\sum\mathcal{M}_k$ accumulation (§5)
- Weak trajectory = field-intensity gradient path (§5.2, M2)

### Open (inputs, not derived)

- Coherent-state structure of the field at the detector (§4.2)
- Outcome-basis selection: the measured observable is set by apparatus construction; the gate's eigenbasis is the outcome basis (§4.6)
- Exact functional form of $\mathcal{M}_i$ at multi-rung interfaces

---

## 9. References

- `foundations/proton-coherence-budget.md`—proton lifetime, annihilation mechanism, $N_{\text{max}}$ formula
- `../../quantum-measurement-qi-appendix.md`—qualitative Qi collapse framework, 5 predictions
- Glauber, R. J., "Coherent and Incoherent States of the Radiation Field," *Phys. Rev.* 131, 2766 (1963)—coherent states; Poisson photon-counting statistics
- Mandel, L. & Wolf, E., *Optical Coherence and Quantum Optics* (Cambridge University Press, 1995)—coherent-state counting statistics
- `computations/coherent_field_born_rule.py`—numeric verification of §4.2–4.6 (Poisson step, relative-rate law, multinomial splitting, weak-coupling limit, automatic interference, canonical-$q$ monotonicity)
- `(external—see papers/consciousness-framework.md in physics repo)` §9—catalytic template and Qi-to-matter coupling
- `open-questions-cassi-answers.md`—Q7 (measurement problem), Q9 (proton lifetime)
