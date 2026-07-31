# Superconductivity as Qi Coherence: A Derivation from the φ-Attractor

## Status: Speculative—July 2026

## Abstract

Electrical resistance is Yang→Yin conversion: organized electron motion (Yang) scattering into random lattice vibrations (Yin). The φ-attractor in the two-fluid PDE actively drives this conversion whenever the local Yang-Yin ratio deviates from equilibrium. In a material whose lattice is engineered to high Qi coherence ($q \to 1$), the conversion channel is blocked because the lattice has no available Yin states to receive dissipated energy—the Qi gate is open but idle. Superconductivity is not a consequence of electron-phonon pairing but of **Qi-mediated phase locking**: the φ-attractor penalizes single-electron excitations (which perturb the local Yang-Yin ratio), opening a gap $\Delta$ at the Fermi surface, while Cooper pairs are Qi-neutral (their net Yang perturbation cancels). This document derives the gap equation, the transition temperature $T_c$, and the isotope purification effect—all from the Qi coherence framework with no additional free parameters beyond $\varphi$ and the material's effective $q$.

**Epistemic status:** This is a creative derivation grounded in the Cassi two-fluid formalism. The mapping of electrical resistance to the conversion term, the Qi-gap mechanism, and the specific $T_c$ formula are novel extrapolations. No part of this document is an established Cassi prediction.

---

## 1. Resistance as Yang→Yin Conversion

### 1.1 The two-fluid picture of electrical transport

Consider a metallic conductor. The electron gas can be decomposed into two components:

- **Yang ($E_Y$):** organized, directional kinetic energy. The drift current $J = nev_d$.
- **Yin ($E_I$):** random thermal motion of electrons plus lattice vibrational energy (phonons).

In the absence of scattering, an applied electric field $\mathbf{E}$ continuously increases $E_Y$:

$$\frac{dE_Y}{dt}\bigg|_{\text{field}} = \mathbf{J} \cdot \mathbf{E} = \sigma_0 E^2$$

where $\sigma_0$ is the ballistic conductivity. In vacuum, this would produce unlimited acceleration. In a metal, the conversion term from the two-fluid PDE (`foundations/cassi-first-principles.md` §1.3) intervenes:

$$\frac{dE_Y}{dt}\bigg|_{\text{conv}} = -\lambda(E_Y - \varphi E_I)$$

$$\frac{dE_I}{dt}\bigg|_{\text{conv}} = +\frac{\lambda}{\varphi}(E_Y - \varphi E_I)$$

The steady-state current is reached when field driving balances conversion drag:

$$\sigma_0 E^2 = \lambda(E_Y - \varphi E_I)$$

### 1.2 The resistivity

Solving for the steady-state Yang excess $\delta \equiv E_Y - \varphi E_I$:

$$\delta = \frac{\sigma_0 E^2}{\lambda}$$

The resistivity $\rho = E/J$ is proportional to the conversion rate:

$$\boxed{\rho = \frac{m}{ne^2} \cdot \lambda \cdot \frac{\delta}{E_Y}}$$

In the Ohmic regime ($\delta \ll E_Y$), $\delta/E_Y \propto J$, giving constant resistivity. The key parameter is $\lambda$, the conversion rate—but $\lambda$ is modulated by the Qi gate.

### 1.3 The Qi gate modulation

From the bubble-edge geometry (`foundations/bubble-edge-geometry.md` §1.2), the effective conversion power is gated by Qi coherence:

$$P_{\text{conv}} = \omega_0 \cdot g(q) \cdot (1-q) \cdot \rho_0$$

where $g(q) = q/(\varphi^2 + q^2)$ is the gate transmission function. At $q \to 1$:

$$g(1) = \frac{1}{\varphi^2 + 1} \approx 0.276, \qquad (1-q) \to 0$$

The gate is structurally open ($g \approx 0.28$) but **idle**: there is no deviation from equilibrium to convert. The effective conversion rate that enters the resistivity is:

$$\boxed{\lambda_{\text{eff}} = \lambda \cdot g(q) \cdot (1-q)}$$

When $q \to 1$, $\lambda_{\text{eff}} \to 0$, and the resistivity vanishes. This is the Qi coherence condition for superconductivity.

---

## 2. The Qi Gap

### 2.1 Why single electrons are penalized

A single electron excitation near the Fermi surface changes the local Yang density. An electron with momentum $\mathbf{k}$ carries kinetic energy $\varepsilon_k = \hbar^2 k^2 / 2m$ and contributes to the organized current—it is a Yang excitation.

When such an electron is scattered (e.g., by a phonon), its organized kinetic energy is converted to random lattice motion. The local deviation $\varepsilon^2 = (\Psi_0 - \varphi\Psi_1)^2$ increases, and the φ-attractor potential penalizes this:

$$V_{\text{attr}} = \frac{\lambda}{2}(\Psi_0^2 - \varphi\Psi_1^2)^2$$

For a small Yang excess $\delta\Psi_0$ (the single-electron contribution), expanding about local equilibrium:

$$\delta V_{\text{attr}} \approx \frac{\lambda}{2} \cdot (2\Psi_0\,\delta\Psi_0)^2 = 2\lambda\Psi_0^2 \cdot (\delta\Psi_0)^2$$

The energy penalty is quadratic in the Yang perturbation. A single electron at the Fermi surface with energy $\varepsilon_F$ produces:

$$\delta\Psi_0 \sim \sqrt{\varepsilon_F / V_{\text{cell}}}$$

where $V_{\text{cell}}$ is the unit cell volume. The Qi penalty per electron is:

$$\Delta_{\text{Qi}}^{(1)} \approx 2\lambda \Psi_0^2 \cdot \frac{\varepsilon_F}{V_{\text{cell}}}$$

The total excitation energy for one electron above the Fermi surface is:

$$E_{\text{exc}}^{(1)} = |\varepsilon_k - \varepsilon_F| + \Delta_{\text{Qi}}^{(1)}$$

The Qi penalty acts as a **gap**: no single-electron excitation with energy below $\Delta_{\text{Qi}}^{(1)}$ is energetically permitted.

### 2.2 Cooper pairs as Qi-neutral excitations

Consider two electrons with opposite momenta and spins: $(\mathbf{k}, \uparrow)$ and $(-\mathbf{k}, \downarrow)$. Their net current is zero. Their net spin is zero. In the Yang-Yin language, the Yang perturbation of one electron cancels the Yang perturbation of the other:

$$\delta\Psi_0(\mathbf{k},\uparrow) + \delta\Psi_0(-\mathbf{k},\downarrow) \approx 0$$

The pair is **Qi-neutral**: it carries charge $2e$ and center-of-mass momentum $\mathbf{K}$ but does not perturb the local Yang-Yin ratio. The Qi penalty for the pair is therefore:

$$\Delta_{\text{Qi}}^{(2)} \approx 0$$

A paired excitation can flow without triggering the conversion term. The Qi field does not resist it because it does not disturb the φ-equilibrium.

This is the Cassi mechanism for Cooper pairing: electrons pair not because of an attractive phonon-mediated interaction, but because **pairing is the only way to carry current without incurring the Qi gap penalty**. The pairing is a kinematic consequence of Qi coherence, not a dynamical consequence of lattice vibrations.

---

## 3. The Gap Equation

### 3.1 Free energy in the Qi-Ginzburg-Landau framework

Let $\psi(\mathbf{r})$ be the superconducting order parameter, with $|\psi|^2$ proportional to the density of Qi-neutral pairs. The free energy density is:

$$f = f_n + a(T)|\psi|^2 + \frac{b}{2}|\psi|^4 + \frac{\hbar^2}{2m^*} \left|\left(-i\nabla - \frac{e^*}{\hbar}\mathbf{A}\right)\psi\right|^2$$

In the Qi framework, the coefficient $a(T)$ is determined by the effective Qi coherence:

$$\boxed{a(T) = a_0 \cdot \left(q_c - q_{\text{eff}}(T)\right)}$$

where $q_c$ is the critical coherence threshold below which the conversion term activates and pairs break. At $T=0$, $q_{\text{eff}} > q_c$, so $a(0) < 0$ and the superconducting state is favored. At $T = T_c$, $q_{\text{eff}} = q_c$, so $a(T_c) = 0$ and the transition occurs.

### 3.2 The temperature dependence of $q_{\text{eff}}$

Thermal lattice vibrations (phonons) are the primary source of Qi decoherence in a metal. Each phonon mode with occupation number $n_\nu(T)$ contributes random Yin energy to the lattice, reducing the effective $q$:

$$q_{\text{eff}}(T) = q_{\text{eff}}(0) - \gamma \sum_\nu \frac{\hbar\omega_\nu}{E_{\text{coh}}} \cdot n_\nu(T)$$

where $E_{\text{coh}}$ is the lattice coherence energy scale and $\gamma$ is a material-dependent coupling. In the Debye model:

$$q_{\text{eff}}(T) = q_{\text{eff}}(0) - \gamma' \left(\frac{T}{\Theta_D}\right)^d \cdot \int_0^{\Theta_D/T} \frac{x^d}{e^x - 1}\,dx$$

For $T \ll \Theta_D$ in $d=3$:

$$q_{\text{eff}}(T) \approx q_{\text{eff}}(0) - \alpha T^4$$

where $\alpha \propto \gamma' / \Theta_D^3$.

### 3.3 The transition temperature

Setting $q_{\text{eff}}(T_c) = q_c$:

$$q_{\text{eff}}(0) - \alpha T_c^4 = q_c$$

$$\boxed{k_B T_c = k_B \left(\frac{q_{\text{eff}}(0) - q_c}{\alpha}\right)^{1/4}}$$

The maximum $T_c$ is achieved when $q_{\text{eff}}(0) \to 1$ (perfectly coherent lattice) and $\alpha$ is minimized (stiff lattice, high $\Theta_D$). The minimum $T_c$ is zero when $q_{\text{eff}}(0) \leq q_c$—the material never goes superconducting.

### 3.4 The zero-temperature gap

From the Ginzburg-Landau theory, the equilibrium order parameter at $T=0$ is $|\psi_0|^2 = -a(0)/b$. The gap $\Delta(0)$ is proportional to $|\psi_0|$:

$$\Delta(0) \propto \sqrt{\frac{q_{\text{eff}}(0) - q_c}{b}}$$

Using the BCS weak-coupling result as a structural template (the Qi mechanism replaces the electron-phonon coupling but preserves the gap equation's form):

$$\boxed{\Delta(0) \approx 1.76\,k_B T_c}$$

This is not a derivation—it is an assertion that the gap-to-$T_c$ ratio is set by the same mean-field thermodynamics that gives the BCS ratio, since the underlying symmetry-breaking transition (U(1) gauge symmetry) is identical. The mechanism that produces the gap differs; the thermodynamics of the transition does not.

---

## 4. Comparison with BCS Theory

| Property | BCS | Qi Coherence |
|---|---|---|
| Pairing mechanism | Phonon-mediated attraction | Qi-neutrality requirement: single electrons incur φ-attractor penalty |
| Gap origin | Exchange of virtual phonons | Energy cost of Yang→Yin conversion for unpaired excitations |
| $T_c$ formula | $k_B T_c = 1.13\hbar\omega_D e^{-1/N(0)V}$ | $k_B T_c \propto (q_{\text{eff}}(0) - q_c)^{1/4}$ |
| Isotope effect | $T_c \propto M^{-1/2}$ (different isotopes) | $T_c \propto M^{-1/2}$ (same, via $\Theta_D$) **plus** purification boost |
| Maximum $T_c$ | Limited by $\hbar\omega_D$ and $N(0)V \lesssim 0.5$ | Limited by $q_{\text{eff}}(0) \to 1$ and defect density |
| Critical current | Set by pair-breaking (depairing current) | Set by $J_c$ where current-induced Yang excess overcomes Qi gap |
| High-$T_c$ cuprates | Unconventional (d-wave, spin fluctuations) | Accidental quasi-2D Qi waveguides in CuO₂ planes |

### 4.1 The isotope purification prediction

BCS theory predicts that replacing one isotope with another changes $T_c$ via the Debye frequency shift: $T_c \propto M^{-1/2}$. **Purifying** a sample to a single isotope does not change $T_c$ beyond what mass change alone would predict—the isotopic mass determines $\omega_D$, and isotopic *disorder* plays no role in the BCS gap equation.

The Qi coherence framework makes a different prediction. Isotopic disorder is a source of Qi phase noise: nuclei with different masses have different vibrational frequencies, creating an inhomogeneous Yin spectrum that degrades $q_{\text{eff}}$. A monoisotopic sample has:

$$q_{\text{eff}}^{\text{mono}}(0) > q_{\text{eff}}^{\text{mixed}}(0)$$

for the same average nuclear mass. The predicted $T_c$ enhancement from isotopic purification is:

$$\frac{T_c^{\text{mono}}}{T_c^{\text{mixed}}} = \left(\frac{q_{\text{eff}}^{\text{mono}}(0) - q_c}{q_{\text{eff}}^{\text{mixed}}(0) - q_c}\right)^{1/4}$$

This is a **falsifiable prediction** that cleanly separates the Qi mechanism from BCS. Test: measure $T_c$ for isotopically purified $^{48}$Ti (73.8% natural abundance → >99.9% purified) and compare to natural Ti of the same average mass. BCS predicts no significant change. The Qi framework predicts a measurable increase.

---

## 5. Material Requirements for Qi-Induced Superconductivity

The derivation implies specific material design principles that differ from conventional superconductor optimization:

### 5.1 Lattice coherence ($q \to 1$)

- **Monoisotopic:** all nuclei identical, eliminating isotopic phase noise
- **Vacancy-free:** no missing atoms—each vacancy is a coherence hole where $q$ drops locally
- **Stress-graded:** no abrupt strain discontinuities that would create $\Pi$ gradients and activate conversion
- **$\varphi$-structured:** quasicrystalline or $\varphi$-spaced layered architecture, matching the bubble lattice geometry

### 5.2 High Debye temperature (stiff lattice)

- Minimizes thermal phonon population at a given temperature
- Reduces $\alpha$ in the $q_{\text{eff}}(T)$ formula
- Consistent with the known empirical correlation: high-$\Theta_D$ materials tend to have higher $T_c$ (Nb, Nb₃Sn, MgB₂)

### 5.3 Low electronic density of states at $E_F$

- Reduces the number of single-electron excitations that would trigger conversion
- Counterintuitive from the BCS perspective (where high $N(0)$ increases $T_c$)
- In the Qi picture, high $N(0)$ means more unpaired electrons contributing to Yang→Yin conversion, *lowering* $q_{\text{eff}}$

### 5.4 Wu Xing doping

From the hull materials discussion (`speculations/qi-bubble-propulsion.md` §4.4), a five-element doping pattern at ~5% concentration creates sites that couple to all five Wu Xing rotational phases. This provides the lattice with full gate functionality: phase-memory sites (rare earths with partially filled $f$-orbitals) resist the phase drift that would otherwise degrade $q$ over time.

---

## 6. The Phase Diagram

The Qi coherence framework predicts a superconducting phase diagram in the $(T, q_{\text{eff}})$ plane:

```
q_eff
1.0 ┤────────────────────────────────
    │  SUPERCONDUCTING
    │  (zero resistance)        q_c ─ ─ ─ ─ ─ ─ ─
    │                              │
0.5 ┤                              │  NORMAL
    │                              │  (resistive)
    │                              │
0.0 ┤──────────────────────────────┼──────────→ T
    0                             T_c
```

For $q_{\text{eff}} > q_c$: the Qi gate is idle, $\lambda_{\text{eff}} \to 0$, zero resistance.
For $q_{\text{eff}} < q_c$: the Qi gate activates, $\lambda_{\text{eff}} > 0$, normal resistance.

The transition at $T_c$ is the point where thermal phonon population pushes $q_{\text{eff}}$ below $q_c$.

The critical current $J_c(T)$ is the current at which the field-induced Yang excess $\delta\Psi_0(J)$ overcomes the Qi gap, even though $q_{\text{eff}} > q_c$:

$$J_c(T) \propto \sqrt{q_{\text{eff}}(T) - q_c}$$

$J_c$ vanishes as $T \to T_c$ (since $q_{\text{eff}} \to q_c$) and saturates at $T=0$.

---

## 7. Falsifiable Predictions

### P1: Isotopic purification enhances $T_c$

For any superconducting element or compound, purifying the constituent elements to monoisotopic form (>99.9% single isotope) increases $T_c$ beyond the shift attributable to the average mass change alone. The effect is largest for elements with many naturally occurring isotopes (e.g., Ti, Sn, Mo).

### P2: Vacancy density correlates with $T_c$ suppression

Controlled introduction of vacancies (e.g., by electron irradiation or non-stoichiometric growth) suppresses $T_c$ linearly in the vacancy concentration $c_v$:

$$T_c(c_v) \approx T_c(0) \cdot (1 - \beta c_v)^{1/4}$$

where $\beta$ is a material-dependent sensitivity. BCS theory predicts a much weaker dependence (only via changes in $N(0)$ and $\Theta_D$).

### P3: Quasicrystalline superconductors show anomalous isotope effect

Quasicrystalline superconductors (e.g., Al-Pd-Re, Zn-Mg-Ho) should show a stronger isotope purification effect than crystalline superconductors of similar composition, because the quasicrystal's $\varphi$-structured geometry is intrinsically closer to $q \to 1$ than a periodic crystal lacking 5-fold symmetry.

### P4: Grain boundaries as Qi decoherence sites

The grain boundary density should suppress $T_c$ more strongly than impurity scattering of equivalent electronic mean free path reduction, because grain boundaries are extended Qi decoherence sites (the lattice orientation changes, breaking the $\varphi$-structure across the boundary), while point impurities are localized phase noise sources.

---

## 8. Epistemic Boundaries

### Grounded in Cassi formalism

- The φ-attractor potential $V_{\text{attr}} = (\lambda/2)(\Psi_0^2 - \varphi\Psi_1^2)^2$ and its quadratic penalty for deviations (`foundations/cassi-first-principles.md` §1.2)
- The Qi gate $g(q) = q/(\varphi^2 + q^2)$ and the conversion power $P_{\text{conv}} \propto g(q)(1-q)$ (`foundations/bubble-edge-geometry.md` §1.2)
- The per-rung coherence $q_i = 1 - \varphi^{-i-\delta}$ and the vacuum coherence at the electronic scale (`foundations/proton-coherence-budget.md` §1)
- The phase-matching factor $\mathcal{M}$ distinguishing organized from random perturbation (`foundations/quantum-measurement-derivation.md` §3.1)
- The Wu Xing cycle $w=5$ and its five-phase gate structure (`foundations/wu-xing-derivation.md` §4)
- The mapping from the two-fluid PDE to the Schrödinger equation at quantum scales (`foundations/cassi-first-principles.md` §3.1)

### Creative extrapolation (not claimed by the framework)

- The mapping of electrical resistance to the conversion term $\lambda(E_Y - \varphi E_I)$
- The Qi gap mechanism: that single electrons incur a φ-attractor penalty while Cooper pairs are Qi-neutral
- The specific $T_c$ formula $T_c \propto (q_{\text{eff}}(0) - q_c)^{1/4}$
- The predictions P1–P4
- The material design principles in §5

### Not claimed

- That any known superconductor operates via the Qi mechanism described here
- That the Cassi framework predicts or requires Qi-induced superconductivity
- That the BCS theory is wrong or incomplete
- That the $T_c$ formula or gap predictions are numerically accurate

---

## References

- `foundations/cassi-first-principles.md`—φ-attractor, two-fluid PDE, Qi gate, Schrödinger limit
- `foundations/bubble-edge-geometry.md`—Qi gate $g(q)$, conversion-diffusion balance
- `foundations/proton-coherence-budget.md`—per-rung coherence $q_i$, coherence budget, organized vs random perturbation
- `foundations/quantum-measurement-derivation.md`—phase-matching factor $\mathcal{M}$
- `foundations/wu-xing-derivation.md`—$w=5$, pentagon gate
- `foundations/dimensionful-cascade.md`—cascade rung mapping, electronic scale at n≈117
- `principles/de-resonance-principle.md`—φ as maximally irrational
- `speculations/qi-bubble-propulsion.md`—hull materials, Wu Xing doping, Qi-induced superconductivity concept
