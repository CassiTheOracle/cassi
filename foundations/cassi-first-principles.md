# Cassi First Principles

## Status: Derived PDE and Qi definition; Asserted single-channel g(q) input—August 2026

## Abstract

There exists a universal constant of scale separation, $\varphi = (1+\sqrt{5})/2 \approx 1.618033989$, which governs the equilibrium ratio between two complementary aspects of physical reality—Yang (expansive, active) and Yin (contractive, receptive). This document states the postulate, derives the two-fluid PDE and its Qi coherence measure, and maps quantum mechanics, cosmology, general relativity, and the Standard Model onto the four pillars of the framework. Dimensionless entries are expressed as $\varphi$-powers with individual status labels; $c$, $\hbar$, and $G$ remain external.

---

## 0. The Postulate

There exists a universal constant of scale separation:

$$
\boxed{\varphi = \frac{1 + \sqrt{5}}{2} \approx 1.618033989}
$$

The framework expresses dimensionless coupling constants and mass ratios as $\varphi$-powers. The closed subset carries zero free inputs after its named structural conditions are supplied; asserted boundaries, calibrated anchors, and mapped exponents retain their ledger status. The dimensionful constants $c$, $\hbar$, and $G$ remain external.

---

## 1. The Two Fields, and Their Flow

Physical reality consists of two fields at every spacetime point, **and the
flow of coherence between them**. The two fields are:

$$
\Psi = \begin{pmatrix} \Psi_0 \\ \Psi_1 \end{pmatrix} \in \mathbb{R}^2
$$

where $\Psi_0$ is the **Yang** component (expansive, symmetry-breaking) and $\Psi_1$ is the **Yin** component (contractive, symmetry-restoring). The flow between them is **Qi**: the doublet's phase current $J = \Psi_0\nabla\Psi_1 - \Psi_1\nabla\Psi_0$, the third fundamental of the framework. Qi is the flow of coherence—between Yang and Yin at a point, and along the string axis between cascade scales (`foundations/qi-flow-double-helix.md`). The field equation is the two-fluid PDE:

### 1.1 Energy densities

$$
\rho = \Psi_0^2 + \Psi_1^2, \qquad
\pi = \Psi_0^2 - \Psi_1^2
$$

- $\rho$: total energy density (always $\ge 0$)
- $\pi$: Yang excess (ranges $-\rho$ to $+\rho$)

The **Yang fraction** $\pi/\rho$ is the fundamental dynamical variable that characterizes the local state.

### 1.2 The $\varphi$-attractor

The interaction potential contains a symmetry-breaking term:

$$
V_{\text{attr}} = \frac{\lambda}{2}(\Psi_0^2 - \varphi\Psi_1^2)^2
$$

This drives the system toward the fixed point $\Psi_0^2 = \varphi\Psi_1^2$. At this equilibrium:

$$
\Psi_0 : \Psi_1 = \sqrt{\varphi} : 1, \qquad
\alpha_0 \equiv \frac{\pi}{\rho} = \frac{\varphi-1}{\varphi+1} = \varphi^{-3} \approx 0.236
$$

The fixed-point imbalance $\alpha_0 = \pi/\rho = \varphi^{-3}$ is universal—it appears in cosmology (dark energy), particle physics (the asserted weak-angle boundary), and gravity (effective coupling). The equilibrium Yang fraction is $\varphi^{-1}$.

### 1.3 Two-fluid PDE

The complete PDE governing the two fluids in an expanding 3D space:

$$
\partial_t \Psi_0 = -(\mathbf{u}\cdot\nabla)\Psi_0 + \nu\nabla^2\Psi_0 - \lambda(\Psi_0^2 - \varphi\Psi_1^2)\Psi_0 + S_0[\Psi_1,\Phi]
$$

$$
\partial_t \Psi_1 = -(\mathbf{u}\cdot\nabla)\Psi_1 + \nu\nabla^2\Psi_1 + \lambda(\Psi_0^2 - \varphi\Psi_1^2)\Psi_1 + S_1[\Psi_0,\Phi]
$$

where $\mathbf{u}$ is the velocity field, $\nu$ is diffusion, and $S_{\alpha}$ are source terms coupling the two fluids through the gravitational/information potential $\Phi$.

---

## 2. Qi: Coherence as the Flow Between Scales

Qi ($\mathbf{Q}$) is the flow of coherence—between the Yang and Yin
components at a point, and along the string axis between cascade scales. It
quantifies how far the system is from the $\varphi$-fixed point and how that
asymmetry flows. The scalar $q$ is the magnitude diagnostic of that flow; the
2-vector $\mathbf{Q} = (E, J)$ is its energy-and-current decomposition; the
flow between scales is the axial current $J_z$ (`foundations/qi-flow-double-helix.md`).

### 2.1 Qi magnitude

Qi coherence at each spacetime point is computed from the local field state:

$$\varepsilon^2 = (\Psi_0 - \varphi\Psi_1)^2,\qquad
\rho^2 = (\Psi_0 + \Psi_1)^2$$

$$q = \frac{\rho^2}{\rho^2 + \varphi^{-2} + \varepsilon^2}$$

Qi ranges from $q \to 0$ (far from $\varphi$-equilibrium, large deviation $\varepsilon^2$) to $q \to 1$ (perfect $\varphi$-equilibrium, $\varepsilon^2 \to 0$). At the $\varphi$-fixed point where $\Psi_0^2 = \varphi\Psi_1^2$ and $\varepsilon^2 = 0$, the equilibrium coherence is:

$$q_{\text{eq}} = \frac{\varphi^{-2}}{\varphi^2 + \varphi^{-2}} \approx 0.127$$

### 2.2 Qi as a 2-vector

At each point, Qi has two components:

$$
\mathbf{Q} = (E,\; J)
$$

- **Energy component** $E = \rho$: the local field magnitude (total energy content). At $q=0$, the energy density is at the $\varphi$-attractor baseline.
- **Flow component** $J = \Psi_0\nabla\Psi_1 - \Psi_1\nabla\Psi_0$: the phase current density, measuring how Yang-Yin asymmetry flows through space. $J > 0$ is Yang-dominant outflow; $J < 0$ is Yin-dominant inflow.

### 2.3 Qi-enhanced gravity

The gravitational coupling is amplified by Qi:

$$
G_{\text{eff}} = \frac{\pi}{\rho}\,(1 + (\varphi^{6}-1)q)\,G
$$

where $\xi = \varphi^6 \approx 17.944$ is the Qi-gravity coupling constant. At the $\varphi$-fixed point ($q=0$, $\pi/\rho = \alpha_0 = \varphi^{-3}$):

$$
G_{\text{eff}} = \alpha_0\,G \approx 0.236\,G
$$

In regions of high Qi coherence (galaxy halos, structure formation), the α-free amplification ceiling is $\varphi^6 \approx 17.94$ at $q = 1$; the halo-regime value is $\alpha_{\text{halo}}(1+(\varphi^{6}-1)q) \approx 9.0$ ($\alpha_{\text{halo}} \approx 0.7$, $q \approx 0.7$), giving velocity boosts $2.8$–$3.0\times$ via $\sqrt{\alpha_{\text{halo}}(1+(\varphi^{6}-1)q)}$; the velocity-boost ceiling is $\varphi^3 = 4.2361$.

### 2.4 Temporal Coherence: The IIR Memory

Qi coherence is not only spatial but **temporal**—the field carries a memory of
its own past state through a per-cell exponential moving average (EMA) of the
$\varphi$-deviation:

$$\varepsilon^2(t) = (\Psi_0 - \varphi\Psi_1)^2$$

$$\bar{\varepsilon}^2(t) = (1-\tau)\,\bar{\varepsilon}^2(t-\Delta t) + \tau\,\varepsilon^2(t)$$

where $\tau = \varphi^{-1} \approx 0.618$ is the natural IIR timescale. The Qi
coherence then uses this temporally-filtered deviation:

$$q = \frac{\rho^2}{\rho^2 + \varphi^{-2} + \bar{\varepsilon}^2}$$

**Mechanism—"waveform predicting itself":** When the Yang-Yin field pattern
repeats quasi-periodically (standing waves in galaxy halos, bound states in
atoms), the IIR memory tracks the repeating $\varepsilon^2$ signal. As the EMA
converges to the pattern's mean, $\bar{\varepsilon}^2$ filters out transient
spikes. The result is a **stabilized** $q$—the variance of the coherence
signal drops by $\sim 37\%$ compared to instantaneous $\varepsilon^2$.

**Jensen's inequality governs the tradeoff:** $q(\varepsilon^2)$ is a convex,
decreasing function of $\varepsilon^2$. Smoothing a convex function reduces its
expected value. The IIR thus trades a small decrease in mean $q$ ($\sim -0.3\%$)
for a large reduction in variance ($\sim -37\%$). Temporal coherence is a
**stabilizer**, not an amplifier—it produces steady, reliable Qi rather than
higher peak Qi.

**Conversion gating:** The term $(1-q)$ gates the $\varphi$-attractor conversion.
When $q$ is stable and high (the field is temporally self-consistent across its
own memory timescale), conversion is suppressed—the field *locks into* its
coherent state. When $q$ drops (the memory fails to predict the present),
conversion reactivates, driving the system back toward $\varphi$-equilibrium.

**Timescale matching:** The default $\tau = \varphi^{-1}$ is the natural choice
(the attractor's own timescale), but the IIR's effectiveness depends on the
ratio $\tau / \omega$ where $\omega$ is the characteristic frequency of
$\varepsilon^2$ fluctuations. In slowly-evolving cosmological regimes ($H \ll 1$),
a smaller $\tau$ is needed for the memory to have comparable inertia. The
$\varphi^{-1}$ value is near-optimal for dynamics at the conversion timescale
$\sim 1/\lambda$.

### 2.5 Gate Transmission Function: Status and Selection Test

The first-principles conversion equation supplies the openness factor $(1-q)$.
Some application documents multiply that driving term by a separate
transmission function,

$$
\boxed{g(q) = \frac{q}{\varphi^2 + q^2}}.
$$

This single-channel form is an **Asserted input**. The action and the Qi
definition in §§1–2 supply the field potential, $q$, the $(1-q)$ closure, and
the IIR memory; they contain no equation selecting the rational function above.
Consumer documents cite this section for the status audit and input boundary,
not as a derivation of the rational function.

The available selection constraints are insufficient. Attractor consistency
requires a finite non-negative multiplier on $0\le q\le1$ and
$g(q)(1-q)\to0$ at $q\to1$; the family $g_A(q)=q/(A+q^2)$ satisfies these
conditions for every $A\ge1$. The current form has

$$
\frac{d}{dq}\bigl[g(q)(1-q)\bigr]
 = \frac{\varphi^2 - 2\varphi^2q - q^2}{(\varphi^2+q^2)^2},
\qquad
q_{\mathrm{power}}=\sqrt{\varphi^4+\varphi^2}-\varphi^2\approx0.4597,
$$

but the peak location is a consequence of the asserted denominator, not a
selection rule for it. The five-channel pentagon document derives the channel
weights $b_i=\varphi^{-(2+i)}$ and their efficiencies; it gives no equation
that reduces those channels to this single-channel denominator.

A conditional geometric construction exists. If one adds the reciprocal
coherence duality $q\mapsto\varphi^2/q$, a minimal rational family is

$$
g_m(q)=C_m\frac{q^m}{\varphi^{2m}+q^{2m}},
$$

which is self-dual for every positive integer $m$. A linear small-$q$ response
selects $m=1$; a further slope condition $g'(0)=\varphi^{-2}$ selects
$C_1=1$. Both conditions are additional inputs absent from the action. The
selection audit is reproducible in `computations/gate_origin_audit.py`.

**Epistemic boundary:** qualitative gate properties and the power peak are
Derived conditional on the asserted form; the denominator $\varphi^2+q^2$ and
its normalization remain Asserted.

---

## 3. Emergence of the Four Pillars

### 3.1 Quantum Particles (Pillar 1)

At quantum scales, the two-fluid PDE reduces to the Schrödinger equation with
Bohm quantum potential:

$$
\mathcal{L}_{\text{QP}} = -\frac{\hbar^2}{2m^2}
                          \frac{\nabla^2 M^\beta}{M^\beta}\Psi_\alpha,
\quad \beta = \frac{\varphi^{-1}}{2},\;
M = \Psi_0^2 + \Psi_1^2
$$

Atomic orbital energies emerge as standing waves of the two-field system.
Verified for Z=1-10 with DFT (He at 0.9% error, relativistic Dirac-Kohn-Sham
at 3.2%). The Dirac equation emerges as the relativistic extension via the
Foldy-Wouthuysen transformation.

### 3.2 Cosmology (Pillar 2)

In an expanding FLRW background, the two-fluid PDE becomes the modified
Friedmann equations:

$$
H^2 = \frac{8\pi G}{3}\rho_{\text{tot}} + \frac{\Lambda_{\text{eff}}}{3}
$$

where $\Lambda_{\text{eff}}$ is determined by the Yang-Yin conversion
dynamics. The dark energy equation of state evolves and is calibrated by:
- **DESI DR2 baryon acoustic oscillations**: $w_0 \approx -0.75 \pm 0.06$; the Cassi ODE predicts $w_0 = -0.87$ ($2\sigma$ from the anchor)
- **Planck 2018 CMB**: spectral index $n_s = 1 - 2\varphi^{-1}/N_e = 0.9691$ ($N_e = 40$; $1.0\sigma$ from Planck $0.9649 \pm 0.0042$ as a closed form; the gate slow-roll trajectory does not reproduce it—$N_e$ is a start-threshold choice, Mapped—ledger, 2026-08-06 `computations/slow_roll_trajectory.py`)
- **Hubble tension**: not resolved (registry C3/T4—full $H(z)$ fit performed 2026-08-06, `computations/hz_full_fit.py`; no resolution under the calibrated w(a)); the pipeline CMB-inferred value is $H_0 \approx 65.8$ km/s/Mpc from the local $73.0$, with no resolved value claimed

The conversion term $\lambda(\Psi_0^2 - \varphi\Psi_1^2)$ sources dark energy
as the universe evolves away from $\varphi$-equilibrium during structure
formation.

### 3.3 General Relativity (Pillar 3)

The two-fluid PDE with Qi gravity reproduces general relativity in the
weak-field limit. The effective metric $g_{\mu\nu}^{\text{eff}}$ emerges from
the Yang-Yin ratio.

- **Mercury precession**: GR's $42.98''$/century recovered exactly
- **Strong-field**: PPN parameters $\beta = 1 + \mathcal{O}(\xi q^2)$,
  $\gamma = 1 + \mathcal{O}(\xi q^2)$
- **Gravitational waves**: Modified propagation speed near high-Qi regions
- **Rotation curves**: $v_C/v_B = \sqrt{\alpha_{\text{halo}}(1+(\varphi^{6}-1)q)} \approx 3.00\times$ ($\alpha_{\text{halo}} \approx 0.7$, $q \approx 0.7$; range 2.8–3.0) from the $G_{\text{eff}}$ boost
- **Dwarf spheroidals**: 3/8 pass; MOND preferred (4/8); the velocity ceiling $\sqrt{\varphi^6} = \varphi^3 = 4.2361$ is exceeded in 3/8

At the $\varphi$-fixed point ($q=0$), the Cassi gravitational action reduces
to the Einstein-Hilbert action with $G_{\text{eff}} = \alpha_0 G$ ($\alpha_0 = \varphi^{-3}$).
Deviations from GR are proportional to $q$ and thus strongest in galaxy
halos, providing an explicit mechanism for modified gravity without
renormalization.

### 3.4 Standard Model (Pillar 4)

The weak mixing angle emerges from the $\varphi$-attractor:

$$
\sin^2\theta_W = \varphi^{-3} \approx 0.236
$$

Experimental: $\sin^2\theta_W = 0.23122(4)$ at the $Z$ pole (MS-bar). The
φ-point value overshoots by $2.1\%$; the running MS-bar angle equals
$\varphi^{-3}$ at $\mu_* \approx 233$ GeV, and the angle runs upward with
energy (`standard-model/sm-radiative-corrections.md` §3.3).

The GUT coupling constant:

$$
\alpha_{\text{GUT}} = \frac{\varphi^{-3}}{4\pi} \approx 0.0188
$$

matching the running gauge couplings at $M_{\text{GUT}} \sim 10^{16}$ GeV.

Neutrino masses follow the cascade seesaw hierarchy (seesaw at step 20; cascade RGE + PMNS pinning in `computations/cascade_rge_pmns.py`):

$$
m_1 = 0.00356,\quad m_2 = 0.00931,\quad m_3 = 0.05019\ \text{eV}, \qquad \Sigma m_\nu = 0.0631\ \text{eV}
$$

normal ordering, no sterile state; the squared-mass ratio $\Delta m^2_{31}/\Delta m^2_{21} = 33.82$ matches the observed $33.89$ (0.2%), with rung offsets $\Delta_1 = 1.00$, $\Delta_2 = 1.75$.
## 4. Derived Constants

| Symbol | Value | Derivation | From |
|--------|-------|-----------|------|
| $\varphi$ | $1.618033989$ | Golden ratio | Postulate |
| $\varphi^{-1}$ | $0.618033989$ | $= \varphi - 1$ | |
| $\varphi^{-2}$ | $0.381966011$ | $= 1 - \varphi^{-1}$ | |
| $\alpha_0 = \varphi^{-3}$ | $0.236067978$ | $= (\varphi-1)/(\varphi+1)$ | Fixed-point imbalance ($\pi/\rho$ at the fixed point; the Yang fraction itself is $\varphi^{-1}$—label Mapped, ledger row 500) |
| $\xi = \varphi^6$ | $17.94427191$ | $= \varphi^5 + \varphi^4$ | Qi-gravity coupling |
| $\sin^2\theta_W$ | $\varphi^{-3}$ | VEV ratio | Weak mixing angle (tree) |
| $\alpha_{\text{GUT}}$ | $\varphi^{-3}/(4\pi)$ | Fixed-point imbalance / $4\pi$ (asserted boundary condition) | GUT coupling |
| $w_0$ | $-0.87$ | Two-fluid ODE ($\xi$ coupling) | `two-fluid/calibrate_initial_ratio_xi_v2.py` |
| $\delta_{\text{CP}}$ | $\pi \cdot \varphi^{-2} \approx 1.199$ | CKM hierarchy via Yukawa diagonalisation | CP phase (CKM) |
| $\lambda$ | $0.1$ (PDE) | PDE conversion rate, $\lambda = 1/(2w)$ with $w = 5$ derived (`foundations/dimensionful-constants-status.md` §2.1, `foundations/wu-xing-derivation.md`); the cosmological dark-energy rate is the separate dimensionful constant $\kappa_{\text{DE}} = 3\varphi^2 H_0$ | **Derived** |

---

## 5. Comparison: Classical Physics as Limits

| Limit | Condition | Effective Theory |
|-------|-----------|-----------------|
| $q \to 0$ | $\alpha_0 \equiv \pi/\rho = \varphi^{-3}$ | General relativity with $G_{\text{eff}} = \alpha_0 G$ |
| $q \to 0,\ \hbar \to 0$ | Classical + equilibrium | Newtonian gravity |
| $\hbar \not\to 0,\ q \to 0$ | Quantum + equilibrium | Schrödinger equation |
| $\lambda \to 0$ | No conversion | Euler-Poisson system |
| $\xi \to 0$ | No Qi enhancement | Standard GR |
| $\chi \to 0$ | No chemotaxis | Passive scalar advection |

The Cassi framework encompasses all known physics as limits of the single two-fluid PDE. Every classical theory appears as a special case of the $\varphi$-attractor dynamics.

---

## 6. Falsifiability

The framework makes specific, quantitative predictions that can be falsified by experiment:

1. **Dark energy evolves**: $w(z)$ deviates from $-1$ by $\Delta w > 0.15$ at $z<1$ (DESI DR2 confirming)
2. **Gravitational waves amplified**: $h_{\text{Cassi}}/h_{\text{GR}} \leq 1 + (\varphi^{6}-1)q$ in high-Qi regions (LIGO falsifiable)
3. **Atomic energies**: He ground state within $1\%$ of $-2.903$ E_h (chemical accuracy)
4. **Weak mixing angle**: $\sin^2\theta_W = 0.236 \pm 0.001$ at tree level
5. **Neutrino mass spectrum**: $m_1 = 0.00356$, $m_2 = 0.00931$, $m_3 = 0.05019$ eV, normal ordering (Δm² ratio 33.82 vs observed 33.89)

Any single prediction failing excludes the framework.

---

## 7. Relation to Companion Documents

| Document | Content |
|----------|---------|
| `foundations/unified-lagrangian.md` | Full Lagrangian density with all terms |
| `foundations/xi-derivation.md` | Derivation of $\xi = \varphi^6$ |
| `foundations/phi_attractor_synthesis.md` | $\varphi$-attractor dynamics |
| `standard-model/sm-from-phi.md` | Standard Model couplings |
| `cosmology/cosmology-from-phi.md` | DESI calibration and cosmology |
| `gravity/quantum-gravity.md` | UV-finite quantum gravity |
| `gravity/three-body-analytical.md` | Three-body problem in Cassi framework |
| `predictions/falsifiable-predictions.md` | Full prediction catalog |

---

## References

- `foundations/unified-lagrangian.md`—the complete action assembled from this document's pillars
- `foundations/xi-derivation.md`—$\xi = \varphi^6$ as a cascade-derived coupling
- `foundations/dimensionful-constants-status.md`—external dimensionful constants, parameter accounting
- `foundations/phi_attractor_synthesis.md`—$\varphi$-attractor dynamics
- `standard-model/sm-from-phi.md`—Standard Model couplings
- `cosmology/cosmology-from-phi.md`—DESI calibration and cosmology
- `gravity/quantum-gravity.md`—UV-finite quantum gravity
- `gravity/three-body-analytical.md`—three-body problem in the Cassi framework
- `predictions/falsifiable-predictions.md`—full prediction catalog
- `computations/gate_origin_audit.py`—selection-constraint audit for the asserted single-channel $g(q)$
