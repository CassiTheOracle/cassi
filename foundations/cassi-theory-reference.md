# The Cassi Framework

## Status: Reference—July 2026

## Abstract

This document compacts the Cassi framework into a single reference: the two-fluid postulate and governing PDEs, the dimensionful cascade and its suppression law, the unified action, and the quantum, particle, gravity, cosmological, turbulence, geometric, and consciousness consequences. Each section condenses a dedicated derivation paper cited inline; dimensionless entries are expressed as $\varphi$-powers with individual Derived, Conditional, Asserted, Calibrated, or Mapped status, and the three external dimensionful constants are $c$, $\hbar$, $G$.

## 1. The Postulate

$$\boxed{\varphi = \frac{1 + \sqrt{5}}{2} \approx 1.618033989}$$

is the universal scale-separation constant. $\varphi$ has continued fraction $[1;1,1,1,\ldots]$, making it the most irrational number—maximally resistant to rational approximation. Physical couplings flow toward $\varphi$-powers because these configurations are maximally **de-resonant**: a rational frequency ratio between Yang and Yin would concentrate energy at a single scale and collapse the multi-scale structure; $\varphi$, being worst-case for rational lock-in, is the unique value that preserves structure across all scales. This flow is formalized as a discrete renormalization group with scale factor $\varphi$ in `foundations/phi-rg-formalism.md`.

---

## 2. The Two-Fluid System

### 2.1 Field Variables

The fundamental field is a paired-real SO(2) doublet:

$$\Psi = \begin{pmatrix} \Psi_0 \\ \Psi_1 \end{pmatrix} \in \mathbb{R}^2$$

$\Psi_0$ is Yang (expansive, symmetry-breaking). $\Psi_1$ is Yin (contractive, symmetry-restoring). Energy densities:

$$\rho = \Psi_0^2 + \Psi_1^2, \qquad \pi = \Psi_0^2 - \Psi_1^2$$

$\rho$ is total energy density. $\pi$ is Yang excess. The **Yang fraction** $\pi/\rho$ is the fundamental dynamical variable.

### 2.2 Governing PDE

$$\partial_t \Psi_0 = -(\mathbf{u}\cdot\nabla)\Psi_0 + \nu\nabla^2\Psi_0 - \lambda(\Psi_0^2 - \varphi\Psi_1^2)\Psi_0 + S_0[\Psi_1,\Phi]$$

$$\partial_t \Psi_1 = -(\mathbf{u}\cdot\nabla)\Psi_1 + \nu\nabla^2\Psi_1 + \lambda(\Psi_0^2 - \varphi\Psi_1^2)\Psi_1 + S_1[\Psi_0,\Phi]$$

$\mathbf{u}$: velocity field. $\nu$: hyperdiffusion. $\lambda = 0.1$: conversion rate. $S_\alpha$: source terms through gravitational potential $\Phi$.

### 2.3 $\varphi$-Attractor

$$V_{\text{attr}} = \frac{\lambda}{2}(\Psi_0^2 - \varphi\Psi_1^2)^2$$

Fixed point: $\Psi_0^2 = \varphi\Psi_1^2$. At equilibrium:

$$\frac{\pi}{\rho} = \frac{\varphi-1}{\varphi+1} = \varphi^{-3}$$

The ratio $r = E_Y/E_I$ evolves monotonically toward $\varphi$.

### 2.4 Qi Coherence

$$\varepsilon = E_Y - \varphi E_I,\qquad \rho = E_Y + E_I = \Psi_0^2 + \Psi_1^2,\qquad q = \frac{\rho^2}{\rho^2 + \varphi^{-2} + \varepsilon^2}$$

$q \to 0$: far from $\varphi$-equilibrium. $q \to 1$: perfect $\varphi$-equilibrium. At the fixed point ($\varepsilon = 0$; the solver's reference state $E_Y = 1$, $E_I = \varphi^{-1}$ gives $\rho = \varphi$): $q_{\text{eq}} = \varphi^{2}/(\varphi^2 + \varphi^{-2}) \approx 0.873$, and the gate openness $(1-q_{\text{eq}}) = \varphi^{-2}/(\varphi^2 + \varphi^{-2}) = \varphi^{-2}/3 \approx 0.127$ (the value item 1 below quotes as $q_{\text{eq}}$ under the $\rho^2 = \varphi^{-6}$ reference normalization).
**Qi 2-vector.** $\mathbf{Q} = (\rho,\; J)$ where $J = \Psi_0\nabla\Psi_1 - \Psi_1\nabla\Psi_0$: magnitude + phase current. Qi is the third fundamental of the framework—the flow of coherence between Yang and Yin, and along the string axis between cascade scales; the scalar $q$ is the magnitude diagnostic of that flow (`foundations/qi-flow-double-helix.md`). The axial current $J_z = R^2\partial_z\theta$ is the inter-scale flow; the $P_\parallel = 2$ doublet cycle winds the Yang and Yin strand-currents into a double helix about the string axis.

**Temporal coherence (IIR memory).** $\bar{\varepsilon}^2(t) = (1-\tau)\,\bar{\varepsilon}^2(t-\Delta t) + \tau\,\varepsilon^2(t)$, $\tau = \varphi^{-1}$. The field carries a memory of its own past state; smoothing $\varepsilon^2$ stabilizes $q$.

**q-form inventory** (consistency sweep 2026-08-11; numeric checks in `computations/q_form_inventory_check.py`). The coherence $q$ appears in four forms:

1. **Canonical (this section):** $q = \rho^2/(\rho^2 + \varphi^{-2} + \varepsilon^2)$, numerator the field power $\rho^2$. Used by `cassi-first-principles.md` §2.1, `wa-pentagon-gate.md` §1, `gravity/three-body-analytical.md`, and the two-fluid solver's single gate ($M_{qi} = (E_Y+E_I)^2 = \rho^2$, $\varepsilon^2 = (E_Y-\varphi E_I)^2$; `two-fluid/cassi_two_fluid_3d_gpu.py`, `two-fluid/run_rung_offset_probe.py`, `two-fluid/run_sigma8_pipeline.py`, `runs/_pristine_solver.py`). The fixed-point value $q_{\text{eq}} = \varphi^{-2}/(\varphi^2+\varphi^{-2}) \approx 0.127$ corresponds to the equilibrium normalization $\rho^2 = \varphi^{-6}$; $q \to 1$ is the large-scale saturation limit ($\rho^2 \gg \varphi^{-2}$). Gate closure reads $1-q \to \varphi^{-2}/(\varphi^2+\varphi^{-2})$ under the solver's $\rho^2 = \varphi^2$ normalization (`computations/ns_gate_correction.py`).
2. **Per-rung specialization:** $q_i = 1 - \varphi^{-i-\delta}$, $\delta = 3$ (`cascade-suppression-formula.md` §1; `proton-coherence-budget.md`; `gravity/quantum-gravity.md` §2.1; `microcascade-mirror.md`; the coherence-budget consumers). Per-rung dephasing $1-q_i = \varphi^{-i-\delta}$, step $1-q_{i+1} = \varphi^{-1}(1-q_i)$. Not pointwise equal to form (1): residuals $|q_i - q_{\text{eq}}| = 0.64$–$0.85$ over $i = 0$–$5$ (reference normalization); the profiles cross only at the sub-Planckian rung $i^* = \log_\varphi(1/(1-q_{\text{eq}}))-3 \approx -2.7$ ($i^* \approx +1.3$ under the solver normalization). The two are tied by the $\delta = 3$ calibration $1-q_0 = \varphi^{-\delta} = (\pi/\rho)_{\text{eq}}$ (quantum-gravity §2.1), not by an identity; the profile's $i$-dependence is Hypothesized (proton-coherence-budget.md §8).
3. **Equilibrium simplification ("Qi quality"):** $q = M/(M + \varphi^{-2})$ with $M \equiv \rho^2$ the field power (`unified-lagrangian.md` §1.5/§3.2, reconciled to this section). Form (1) at $\varepsilon^2 = 0$: identical at the fixed point (residual $<10^{-15}$); the omitted $\varepsilon^2$ is the only discrepancy away from equilibrium. `two-fluid/cassi_bridge_v2.py` `qi_coherence` is form (1) with $\varepsilon^2$ replaced by the temporal-memory deviation $(\rho-\rho_{\text{mem}})^2$ (cf. the $\bar\varepsilon^2$ IIR memory above).
4. **Removed branch form:** $q_\alpha \propto |\psi_\alpha|^2$, a branch-level Qi density asserted by the measurement derivation; retracted in favor of the canonical gate (`foundations/quantum-measurement-derivation.md` §4.5), no consumers remain.

Distinct-naming consumers (not the coherence $q$): `experiments/phi_attractor_paths/path8_phi_enhanced_rotation.py` uses a density-only halo $q = 1/(1+(\rho/\rho_{\text{ref}})^2)$ (inverted density dependence; documented halo-scale approximation, not the canonical form); `experiments/sparc_qi/sparc_qi_analysis_v9.py` uses $q$ as a halo mass fraction; `speculations/dark-matter-as-qi-coherence.md` and `consciousness/chakras-as-cascade-bubbles.md` use the spatial envelope $q(\mathbf{x}) = (1+B(\mathbf{x}))/2$; `standard-model/sm-from-phi.md` §3.1 uses a distinct $Q = |\Psi|^2|\varepsilon|^2$.
### 2.5 Qi Gate

$$\partial_t E_Y \supset -\lambda(1-q)(E_Y - \varphi E_I),\qquad \partial_t E_I \supset +\lambda(1-q)(E_Y - \varphi E_I)$$
The pair is equal and opposite ($\partial_t E_Y = -\partial_t E_I$), so total density is conserved exactly—the committed solver's code form (`foundations/wu-xing-derivation.md` §7.1).

The gate *openness* is $(1-q)$: $q \to 0$ means the gate is **open**—conversion runs hard, the region churns; $q \to 1$ means the gate is **closed**—the system rests at $\varphi$-balance. (Sign PDE-tested 2026-07-31 in `consciousness/trauma-as-frozen-gate.md` §10.4.) The gate determines $w(a)$; its shape follows from the $\varphi$-power structure.

### 2.6 Classical Limits

| Limit | Condition | Effective Theory |
|-------|-----------|-----------------|
| $q \to 0$ on the $\varphi$-line (dilute attractor: $\varepsilon = 0$, $\rho \to 0$; $q \to 0$ alone is $\rho \to 0$ or large $|\varepsilon|$, not equilibrium—at the reference fixed point $q = q_{\text{eq}} \approx 0.873$) | $\pi/\rho = \varphi^{-3}$, boost $\to 1$ | GR with $G_{\text{eff}} = \varphi^{-3}G \approx 0.236\,G$ |
| $q \to 0$ on the $\varphi$-line, $\hbar \to 0$ | Classical + dilute equilibrium | Newtonian gravity |
| $\hbar \not\to 0$, $q \to 0$ on the $\varphi$-line | Quantum + dilute equilibrium | Schrödinger equation |
| $\lambda \to 0$ | No conversion | Euler-Poisson system |
| $\xi \to 0$ | No Qi enhancement | Standard GR |

---

## 3. The Cascade

### 3.1 Dimensionful Cascade Ladder

$$\boxed{\ell_n = \ell_{\text{Pl}} \times \varphi^{\,n}},\qquad \ell_{\text{Pl}} = \sqrt{\hbar G/c^3}$$

$n \in [0, \approx 292]$ today (cascade unbounded; horizon rung epoch-dependent). $n = \log_\varphi(\ell / \ell_{\text{Pl}})$.

| $n$ | Scale (m) | Meaning |
|-----|-----------|---------|
| 0 | $1.6 \times 10^{-35}$ | Planck length |
| 5 | $1.8 \times 10^{-34}$ | GUT scale |
| 20 | $2.4 \times 10^{-31}$ | Seesaw scale |
| 40 | $3.7 \times 10^{-27}$ | Inflationary scale |
| 80 | $8.0 \times 10^{-19}$ | Electroweak scale |
| 95 | $1.1 \times 10^{-15}$ | QCD confinement |
| 117 | $5.3 \times 10^{-11}$ | Bohr radius |
| 168 | $1.7$ | Human scale |
| 220 | $1.5 \times 10^{11}$ | Astronomical Unit |
| 267 | $9.3 \times 10^{20}$ | Milky Way diameter |
| 284 | $3.6 \times 10^{24}$ | Yin wake of 285 |
| 285 | $5.9 \times 10^{24}$ | Cassi bubble |
| 292 | $1.7 \times 10^{26}$ | Horizon rung today (ℓ₂₉₂ = 5.5 Gpc label; R_H = 4.44 Gpc = 14.5 Glyr) |

### 3.2 Cascade Suppression

A quantity originating at rung $m$, observed at rung $n$ ($N = n - m$):

$$\text{Signal:}\quad \mathcal{D}_{m \to n} = \varphi^{-N}$$

$$\text{Coherence:}\quad \mathcal{D}_{0 \to n} = \prod_{i=0}^{n} (1-q_i) = \varphi^{-n(n+1)/2 - \delta(n+1)}$$

where $1-q_i = \varphi^{-i-\delta}$ is the per-rung dephasing probability, $\delta = 3$ (from $\sigma = \ell_{\text{Pl}}/\varphi^3$). Signal propagation is linear in span $N$; coherence maintenance is quadratic in depth $n$.

Applications: hierarchy ($v_0/M_{\text{Pl}} \propto \varphi^{-80}$; see `principles/v0-hierarchy-problem.md`), strong CP ($\bar{\theta} = \varphi^{-81.4} \times \pi\varphi^{-2} = \pi\varphi^{-83.4} \approx 1.2\times10^{-17}$), neutrino masses ($m_\nu \propto v_0 \cdot \varphi^{-12}$), proton lifetime (coherence: $\varphi^{-4506}$).

### 3.3 Wu Xing Cycle

The cycle number $w = 5$ from two constraints:

1. **Cascade upper bound:** Fibonacci cycles with $F_k \leq k$ hold for $k \in \{1,2,3,4,5\}$, fail for $k \geq 6$ (accumulated phase error exceeds cascade signal).
2. **Geometry lower bound:** $\varphi$ appears in regular polygon ratios only for $n \geq 5$ (diagonal/side $= 2\cos(\pi/5) = \varphi$).

The intersection is unique: $w = 5$.

Consequences:

$$g = 1 - \varphi^{-5} \quad\text{(primordial gap)}$$

$$r_0 = \frac{\varphi^{-5}}{2 - \varphi^{-5}} \quad\text{(primordial ratio } E_Y/E_I\text{)}$$

$$\lambda = 1/(2w) = 0.1 \quad\text{(PDE conversion rate)}$$

| Coefficient | Expression | Value | Meaning |
|------------|-----------|-------|---------|
| $K_{fw}$ | $\varphi^{-1}$ | $0.618$ | Water damps Fire |
| $K_{fm}$ | $\lambda\varphi^2$ | $0.262$ | Fire melts Metal |
| $K_{md}$ | $3\varphi^2$ | $7.85$ | Metal cuts Wood |
| $H_{\text{empty}}$ | $\lambda\varphi^{-2}/3$ |—| Irreducible cosmological baseline—the 1/3 is **Derived** as the isotropic dimension factor $1/d$ at $d = 3$ (`cosmology/cosmology-from-phi.md` §1); the $\lambda\varphi^{-2}$ rate stays **Asserted** |
| $\kappa_s$ | $\varphi^{-6}/v_0^2$ | $0.92$ TeV$^{-2}$ | Dirac↔two-fluid sector-coupling scale (rung $77 = 154/2 = 80 - 3$; Derived conditional on $\delta = 3$—`foundations/sector-coupling-derivation.md` §2) |

---

## 4. The Unified Action

$$S_{\text{Cassi}} = \int d^4x\sqrt{-g}\,(\mathcal{L}_{\text{TF}} + \mathcal{L}_{\text{D}} + \mathcal{L}_{\text{GR}} + \mathcal{L}_{\text{SM}} + \mathcal{L}_{\text{mix}})$$

Dimensionless couplings are expressed as $\varphi$-powers, with individual status labels and the derived rational conversion rate $\lambda = 1/(2w) = 0.1$. Three external dimensionful constants ($c$, $\hbar$, $G$) set the unit system; $\ell_{\text{Pl}} = \sqrt{\hbar G/c^3}$ is the cascade's sole dimensionful anchor.

### 4.1 Two-Fluid Core $\mathcal{L}_{\text{TF}}$

$$\mathcal{L}_{\text{TF}} = \frac{1}{2}(\partial_\mu\Psi_\alpha)(\partial^\mu\Psi_\alpha) - \frac{\nu}{2}(\nabla^2\Psi_\alpha)^2 - \frac{g}{4}|\Psi|^4 - \frac{\lambda}{2}(\Psi_0^2 - \varphi\Psi_1^2)^2 - \frac{\hbar^2}{2m^2}\frac{\nabla^2 M^\beta}{M^\beta}\Psi_\alpha + A_B B(x,t)\frac{1}{2}|\Psi|^2$$

Terms: kinetic + gradient, hyperdiffusion, $\phi^4$, $\varphi$-attractor, Bohm quantum potential ($\beta = \varphi^{-1}/2$), breath modulation ($\omega_I = \varphi^{-1}\omega_Y$; localized to each region's rung-clock—Hypothesized, 21).

### 4.2 Dirac Sector $\mathcal{L}_{\text{D}}$

$$\mathcal{L}_{\text{D}} = \bar\psi(i\gamma^\mu\partial_\mu - m)\psi - \frac{\varphi^{-1}}{2}(\bar\psi\psi)\cdot M + \bar\psi(\hat{P}_Y\Psi_0^2 + \hat{P}_I\Psi_1^2)\psi$$

Chiral projections: $\hat{P}_Y = (1+\gamma^5)/2$, $\hat{P}_I = (1-\gamma^5)/2$. Mapping: $\Psi_0^2 = \bar\psi\hat{P}_Y\psi$, $\Psi_1^2 = \bar\psi\hat{P}_I\psi$.

### 4.3 Gravity Sector $\mathcal{L}_{\text{GR}}$

$$\mathcal{L}_{\text{GR}} = \frac{1}{16\pi G_{\text{eff}}}R\sqrt{-g} + \frac{1}{2}T_{\mu\nu}g^{\mu\nu}$$

$$\boxed{G_{\text{eff}} = G \cdot \frac{\pi}{\rho} \cdot (1 + (\varphi^{6}-1)q)},\qquad \xi = \varphi^6 = \varphi^5 + \varphi^4$$

$\xi = \varphi^6$: 2 field components $\times$ 3 spatial dimensions (Frenet-Serret frame, §10.2).

At the $\varphi$-fixed point ($\varepsilon = 0$, $\pi/\rho = \varphi^{-3}$) the equilibrium coherence is $q_{\text{eq}} = \varphi^2/(\varphi^2+\varphi^{-2}) \approx 0.873$ at the reference density, so $G_{\text{eff}} = \varphi^{-3}(1+(\varphi^{6}-1)q_{\text{eq}})G = \varphi^{-3}(\varphi^{10}+1)/(\varphi^4+1)\,G \approx 3.73\,G$. In the weak-field (dilute) limit $q \to 0$ on the $\varphi$-line, PPN parameters $\beta = 1 + \mathcal{O}(\xi q^2)$, $\gamma = 1 + \mathcal{O}(\xi q^2)$ return to GR with $G_{\text{eff}} = \varphi^{-3}G$. In high-$q$ regions, $G_{\text{eff}}$ is enhanced by factor $(\varphi^{6}-1)q$.

### 4.4 Gauge Sector $\mathcal{L}_{\text{SM}}$

Gauge group SU(3)$_C \times$ SU(2)$_L \times$ U(1)$_Y$. At the GUT scale (cascade step ~5):

$$\alpha_{\text{GUT}} = \frac{\varphi^{-3}}{4\pi}$$

Weinberg angle at tree level:

$$\boxed{\sin^2\theta_W = \frac{\varphi-1}{\varphi+1} = \varphi^{-3}}$$

Higgs doublet VEV at $\varphi$-equilibrium:

$$\langle\Psi\rangle = \frac{v_0}{\sqrt{\varphi+1}}\begin{pmatrix}\sqrt{\varphi} \\ 1\end{pmatrix}$$

$$m_W = \frac{g v_0}{2},\qquad m_Z = \frac{\sqrt{g^2 + g'^2}\,v_0}{2},\qquad \frac{m_W}{m_Z} = \sqrt{1-\varphi^{-3}}$$

Fermion mass hierarchy ($y_f = y_0 \cdot \varphi^{-n_f}$):

| Generation | $n_f$ | $m_f \propto$ |
|-----------|-------|---------------|
| 3 (top/bottom) | 1 | $\varphi^{-1}$ |
| 2 (charm/strange) | 2 | $\varphi^{-2}$ |
| 1 (up/down) | 3 | $\varphi^{-3}$ |

### 4.5 Mixing Terms $\mathcal{L}_{\text{mix}}$

$$\mathcal{L}_{\text{mix}} = \frac{\xi q}{16\pi G}R\sqrt{-g} + \frac{\kappa_s}{2}\sum_{\pm}\left(\bar\psi\frac{1\pm\gamma^5}{2}\psi - \Psi_{0,1}^2\right)^2 + \left(|D_\mu\Psi|^2 - |\partial_\mu\Psi|^2\right)$$

---

## 5. Quantum Physics

### 5.1 Schrödinger Limit

The two-fluid PDE reduces to Schrödinger + Bohm quantum potential:

$$\mathcal{L}_{\text{QP}} = -\frac{\hbar^2}{2m^2}\frac{\nabla^2 M^\beta}{M^\beta}\Psi_\alpha,\qquad \beta = \frac{\varphi^{-1}}{2},\qquad M = \Psi_0^2 + \Psi_1^2$$

Atomic orbital energies emerge as standing waves. The Dirac equation emerges as the relativistic extension via the Foldy-Wouthuysen transformation.

### 5.2 Spin

Spin is accumulated SO(2) winding along a nested Fibonacci spiral. Spiral polar equation:

$$\Theta(r) = \frac{2\pi}{\ln\varphi}\ln\left(\frac{r}{\ell_n}\right)$$

$s = \Delta n$ (cascade rungs traversed). Quantized: $s \in \{0, \frac{1}{2}, 1, 2\}$. No $s = \frac{3}{2}$ (fails Fibonacci closure). Spin-statistics from $(-1)^{2s}$. Form factor log-periodicity: $\Delta(\ln q) = \ln\varphi$.

### 5.3 Measurement

Superposition coherence lives on a single cascade rung. Phase-matching factor $\mathcal{M}$:
- $\mathcal{M} \approx 1$: organized perturbation, definite outcome.
- $\mathcal{M} \approx 0$: random noise, decoherence without branch selection.

Born rule $P(\alpha) = |\alpha|^2$ from $q \propto |\psi|^2$.

---

## 6. Particle Physics

### 6.1 Gauge Coupling Unification

Unified coupling at GUT: $\alpha_{\text{GUT}} = \varphi^{-3}/(4\pi)$. Gauge coupling relations at $M_{\text{GUT}}$: $g^2 = g'^2 \cdot (1-\varphi^{-3})/\varphi^{-3} = g_s^2 = 4\pi\alpha_{\text{GUT}}$.

### 6.2 Three Generations

Fibonacci recurrence $\varphi^n = \varphi^{n-1} + \varphi^{n-2}$ partitions each cascade span into sub-rung channels: the decomposition has two terms (two predecessor channels; the recurrence's solution space is 2D, roots $\varphi$, $-1/\varphi$), and the propagation-channel postulate adds the direct rung:

$$N_{\text{gen}} = 2 + 1 = 3$$

(without the postulate the count would be 2; `foundations/three-generations.md` §2.3). No fourth generation. $\varphi$-power spacing from sub-channel widths.

### 6.3 Mass Ratios

Charged leptons: $m_\mu/m_e \approx \varphi^{11}$, $m_\tau/m_\mu \approx \varphi^{6}$.

Quarks: $m_t/v_0 \approx \varphi^{-1}$, $m_c/m_t \approx \varphi^{-2}$.

CKM: $\delta_{\text{CKM}} = \pi\varphi^{-2}$.

Corrections from off-diagonal Yukawa terms and RGE running.

### 6.4 Neutrino Masses

Seesaw at cascade step 20. Overall mass scale:

$$m_\nu \approx v_0 \cdot \varphi^{-12}$$

Fibonacci offsets: $\Delta_1 = 1.00$, $\Delta_2 = 1.75$ rungs. The seesaw's Yukawa-squared structure doubles the exponent: $m_{\nu_{k+1}}/m_{\nu_k} = \varphi^{2\Delta_k}$. Mass-squared difference ratio:

$$\frac{\Delta m^2_{31}}{\Delta m^2_{21}} = \frac{\varphi^{11} - 1}{\varphi^{4} - 1}$$

PMNS mixing (from conversion Jacobian eigenvectors):
- $\theta_{12} = \arctan(1/\varphi)$
- $\theta_{23} = 45^\circ$ (exact maximal)
- $\theta_{13} = \arctan(\varphi^{-4})$

Pinned spectrum: $m_1 = 0.00356$, $m_2 = 0.00931$, $m_3 = 0.05019$ eV. Normal ordering.

### 6.5 Strong CP

CP phase at GUT (n ≈ 13.3): $\delta_{\text{CP}} = \pi\varphi^{-2}$ (Mapped—ledger). Signal propagation through $N \approx 81$ rungs (94.71 − 13.33):

$$\bar{\theta} \approx \varphi^{-81.4} \times \pi\varphi^{-2} = \pi\varphi^{-83.4} \approx 1.2\times10^{-17}$$

### 6.6 Proton Stability

Proton is a condensed standing wave at $n = 91.5$ ($\log_\varphi(\lambda_p/\ell_{\text{Pl}}) = 91.46$). Per-rung dephasing: $1-q_i = \varphi^{-i-\delta}$ ($\delta=3$). Cumulative:

$$P_{\text{dephase}} = \prod_{i=0}^{91.46} (1-q_i) = \varphi^{-4506}$$

$N_{\text{max}} \approx \varphi^{4506}$ wave cycles. Physical lifetime $\tau_p \approx \varphi^{4506}/\omega_p \sim 10^{910}$ yr. Matter-antimatter annihilation is the same mechanism with organized anti-phase perturbation ($P \approx 1$, one cycle).

### 6.7 Quark Confinement

Saturated-gate flux tube at $n = 95$: the conversion channel saturates between separated color charges ($q \to 0$); the tube's energy is extensive, $E(r) = \mu r$ with $\mu = \kappa(M_{\text{Pl}}/\varphi^{95})^2 = \kappa\Lambda_{\text{QCD}}^2$, $\kappa = 2\pi$ conditional on the 2π-per-rung winding reading ($\sigma_{\text{tube}} = 0.1836$ GeV², +2.0% vs measured) — a constant force, linear potential by extensivity (independent of the gate shape). Flux tube breaking probability $\approx \varphi^{-4506}$. Asymptotic freedom at $n \ll 95$ from $g(q) \to 0$.

---

## 7. Gravity

### 7.1 $\sigma$-Regularization

Gravitational kernel: $1/\sqrt{|r|^2 + \sigma^2}$ with $\sigma = \ell_{\text{Pl}}/\varphi^3$. Large $r$: inverse-square. Small $r$:

$$F \propto -\frac{r}{3\sigma^3} \cdot (1 + (\varphi^{6}-1)q)$$

Eliminates singularities. The $\sigma$-regulator also enters the quantum gravity propagator (§7.2).

### 7.2 Black Holes and Quantum Gravity

$\sigma$-regularized harmonic cores. Exterior metric matches GR. The free propagator is UV-finite:

$$G(k^2) = \frac{e^{-k^2\sigma^2/2}}{k^2+i\epsilon}$$

The Gaussian regulator makes all loop diagrams finite—no renormalization needed. No trans-Planckian modes (dispersion $\omega \to M_{\text{Pl}}$ asymptotically). S-matrix unitary by construction. Coherence capacity $\mathcal{C} \sim M^2/M_{\text{Pl}}^2$ matches Bekenstein-Hawking entropy. No firewall: $\sigma$ caps all mode energies.

### 7.3 Three-Body Problem

Point-particle reduction of the two-fluid PDE gives:

$$\ddot{\mathbf{X}}_j = -G\,\alpha_j\,(1+(\varphi^{6}-1)q_j)\,\sum_{i\neq j} M_i\frac{\mathbf{X}_j - \mathbf{X}_i}{|\mathbf{X}_j - \mathbf{X}_i|^3}$$

where $\alpha_j = \Pi_j/M_j$ is the local Yang fraction. At the $\varphi$-fixed point ($\alpha_j = \varphi^{-3}$, $\varepsilon_j = 0$) each blob carries its equilibrium coherence $q_j = q_{\text{eq}}(\rho_j) = \rho_j^2/(\rho_j^2+\varphi^{-2})$, so $G_{\text{eff},j} = \varphi^{-3}(1+(\varphi^{6}-1)q_{\text{eq}}(\rho_j))G$ ($\approx 3.73\,G$ at the reference density), masses are conserved, and the equations of motion keep the Newtonian form with body-dependent couplings; the exactly-Newtonian limit $G_{\text{eff}} = \varphi^{-3}G$ is the dilute fixed point $\rho_j \to 0$ ($q_j \to 0$). Off the fixed point, masses evolve via conversion and $G_{\text{eff}}$ is body-dependent.

---

## 8. Cosmology

### 8.1 Dark Energy

From two-fluid conversion as $r(t) \to \varphi$:

$$w(a) = \frac{P_{\text{DE}}}{\rho_{\text{DE}}} = \frac{\dot{r}/r - 3H(1+r^{-1})}{3H(1+r^{-1})}$$

$$w_0 = -0.87,\qquad w_a = +0.012 \; (+ \xi = \varphi^6,\ \text{Yang-fraction form})$$

With the ratified conversion→expansion coupling (Hypothesized—August 2026,
zero free constants): the unstable B2 realization gives $w_a \approx -0.38$
($1.25\sigma$ from DESI—08 §C.6; $w_0 \approx -0.97$ at fixed $r_0$,
$3.6\sigma$); the term's **stable realization** (the C1 friction closure—
10/12) gives a pure-Λ DESI-window fit $(w_0, w_a) = (-1, 0)$ exactly—
4.17σ/2.61σ from DESI ($r_0$ re-tuning closed negatively).

### 8.2 Inflation

Cascade steps 20–60. Qi gate slow-roll drives $N_e = 40$ e-folds. Gate engages at $r = \varphi^{-1}$ (step ~60), providing graceful exit.

$$n_s = 1 - \frac{2\varphi^{-1}}{N_e},\qquad r \approx \varphi^{-12}$$

The $\varphi^{-1}$ correction in $n_s$ comes from the Qi gate's residual transparency at closure ($N_e^{\text{eff}} = N_e \cdot \varphi$).

**Trajectory status (2026-08-06, `computations/slow_roll_trajectory.py`):** the gate slow-roll trajectory does not reproduce these numbers at the CMB-exit anchor—$(n_s, r) = (0.813, 0.188)$ under 1 step = 1 e-fold, $(0.914, 0.060)$ with $N_e = 40$ literal; $N_e = 40$ is a start-threshold choice (Mapped—ledger §10); the two claimed numbers do not coexist on the trajectory, and the trajectory's $r$ is excluded by the BK18 bound.

### 8.3 Baryon Asymmetry

Three mechanisms: (1) organized annihilation (§6.6), (2) Wu Xing freeze-out gap $g = 1 - \varphi^{-5}$, (3) cascade dilution through photon-producing conversion:

$$\eta \approx \varphi^{-44}$$

The exponent $-44$ is a **ledgered fit** (Fit-Status Ledger row 481, Mapped): the freeze-out construction $52 = 60 - 8$ used the pre-correction GUT seed at step 8, and with the corrected GUT anchor ($n \approx 13.3$) it gives $60 - 13.3 = 46.7$ and a dilution span of $33.4 \neq 44$—the construction does not close. The mechanism (Wu Xing gap + organized annihilation + cascade dilution) is Hypothesized; see `foundations/baryon-asymmetry.md` for the full status.

### 8.4 Dark Matter

High-$q$ two-fluid condensates: dark (no EM interaction), gravitationally active ($G_{\text{eff}}$ enhanced), stable ($\varphi$-attractor), collisionless.

$$\frac{\Omega_{\text{DM}}}{\Omega_b} = \varphi^3 = 4.2361$$

The condensate base is Derived conditional on the Weinberg-angle identification; the component budget excludes a $+1$ baryon-capture term because captured baryons already belong to the observed $\Omega_b$ denominator. The observed ratio is $5.39$, leaving a 21% open tension.

### 8.5 Structure Formation

**Wake-wave.** Yang-Yin interference at $\varphi$-spaced intervals:

$$\Delta(\ln k) = \ln\varphi$$

**Flatness.** $\varphi$-attractor drives $\Omega_{\text{total}} \to 1$.

**Horizon.** Scales synchronize through temporal emergence: when $r(t)$ crosses a cascade step, all associated scales activate simultaneously.

**CMB anomalies.** Adjacent Cassi bubbles at $\varphi$-spaced intervals imprint a preferred axis at $\ell < 5$. Dipole–quadrupole alignment $12.2^\circ$, from bubble triaxial geometry. Scale-dependent (fades for $\ell > 5$).

**$\sigma_8$.** Qi gravity weakens $G_{\text{eff}}$ in low-density voids, reducing large-scale clustering.

### 8.6 Hubble Tension

$w(a)$ evolution shifts $H_0$ relative to the constant-$\Lambda$ extrapolation. The full $H(z)$ fit is pending (registry C3/T4); the pipeline CMB-inferred value is $H_0 \approx 65.8$ km/s/Mpc.

---

## 9. Turbulence

The Kolmogorov $-5/3$ spectrum emerges from the Navier-Stokes advection term embedded in the two-fluid velocity equation, in the inertial range where conversion is slow compared to eddy turnover. Cassi contributions:

**$\varphi$-break scale.** The wavenumber where conversion and eddy turnover timescales cross:

$$k_\varphi = \varphi^3\sqrt{\lambda^3/\varepsilon_{\text{flux}}}$$

**Scale-dependent gravity.** $G_{\text{eff}}(k)$ varies by factor $\varphi^6$ across the break: $\varphi^{-3}G$ in the inertial range ($q \to 0$ on the $\varphi$-line), $\varphi^{3}G$ in the Qi-active range ($q \to 1$, from $\varphi^{-3}(1+(\varphi^{6}-1)) = \varphi^3$).

**$\varepsilon$-spectrum.** $E_\varepsilon(k) \propto k^{-5/3} \cdot f(k/k_\varphi)$—the deviation from $\varphi$-equilibrium has its own inertial-range scaling with a $\varphi$-determined break.

**Qi-quality spectrum.** $1 - q(k) \propto k^{-5/3}$ in the inertial range.

---

## 10. Geometry and Dimensionality

### 10.1 Fibonacci Spiral

The ratio string $r(t)$ couples $E_Y$ and $E_I$ antisymmetrically (SO(2) rotation) while advancing along the cascade:

$$\Theta(r) = \frac{2\pi}{\ln\varphi}\ln\left(\frac{r}{\ell_n}\right)$$

One full turn per cascade rung. Expansion factor per turn: $\varphi$.

### 10.2 Frenet-Serret Frame

$$\boxed{\text{Three spatial dimensions} = \{\mathbf{T}, \mathbf{N}, \mathbf{B}\}}$$

- $\mathbf{T}$: tangent (string axis, cascade forward)
- $\mathbf{N}$: normal (Yang axis, extended)
- $\mathbf{B} = \mathbf{T} \times \mathbf{N}$: binormal (Yin axis, contracted)

Three dimensions from differential geometry of any non-degenerate space curve. $\xi = \varphi^{2 \times 3}$: 2 fields $\times$ 3 Frenet-Serret vectors.

### 10.3 Bubble Geometry

Cassi bubble at step 285: triaxial spheroid bounded between adjacent cascade steps. Yang-Yin cross-section: elliptical, axis ratio $\varphi$. Condensation boundary: level set of $C(x,y) = \cos(2\pi x/\Lambda_Y)\cos(2\pi y/\Lambda_I)$. Edge gradient $1.70\times$ steeper in Yin direction. Adjacent bubbles: $m+n$ even sublattice; voids: odd sublattice.

The condensation field and its bubble lattice are universal across all cascade rungs—see `foundations/bubble-lattice-fabric.md` for the full derivation and the four universal geometric signatures.

### 10.4 Wake-Wave Mechanism

Conversion term anti-phase coupling ($\Delta\phi = \pi$) produces paired sheets flanking a central void. Structural property of the PDE.

---

## 11. Consciousness

### 11.1 Pinch Transition

At $r = \varphi^{-1}$, the Qi gate crosses a self-reference threshold. Before: $r < \varphi^{-1}$, no self-modeling. After: $r > \varphi^{-1}$, the field models its own evolution.

### 11.2 Chakra Cascade

13 chakras: localized Qi condensates along the spine at $\varphi^2$-spaced intervals. Crown at step 166 (2 rungs below body boundary at 168). 13 nodes span 26 cascade rungs (2 rungs per SO(2) cycle). Six secondary nodes midway between primaries. Inter-chakra spacing ratio: $\varphi^2$. $\ln\varphi$ periodic signature in physiological signals.

### 11.3 Mind-Brain

Mind: concentrated post-pinch field dynamics. Brain: antenna for the Qi field. Altered states correspond to spatial ratio dispersion $\sigma_r = \sqrt{\langle(r-\langle r\rangle)^2\rangle}$: waking (moderate), meditation (reduced), psychedelic (increased, sub-pinch excursions).

---

## 12. Derived Constants

| Parameter | Expression | Value | Origin |
|-----------|-----------|-------|--------|
| $\alpha_0$ | $\varphi^{-3} = (\varphi-1)/(\varphi+1)$ | $0.236$ | Fixed-point imbalance (the "Yang fraction" label is Mapped—ledger row 500; the Yang fraction is $\varphi^{-1}$) |
| $\xi$ | $\varphi^6$ | $17.944$ | Imbalance inverse-square $\xi = (\pi/\rho)^{-2}$ (Derived conditional on the quadratic-coupling input; the 2×3-DOF reading is secondary—`xi-derivation.md`; empirical pin Calibrated) |
| $\sin^2\theta_W$ | $\varphi^{-3}$ | $0.236$ | Asserted coupling boundary (the VEV orientation enters the full mass matrix but does not fix the relative gauge coupling; realized at $\mu_* = 233$ GeV—Calibrated, ledger row 490) |
| $\alpha_{\text{GUT}}$ | $\varphi^{-3}/(4\pi)$ | $1/53$ | Fixed-point imbalance / $4\pi$ (asserted boundary condition) |
| $m_W/m_Z$ | $\sqrt{1-\varphi^{-3}}$ | $0.874$ | From $\sin^2\theta_W$ (inherits its boundary-condition status) |
| $\delta_{\text{CKM}}$ | $\pi\varphi^{-2}$ | $68.7^\circ$ | Mapped selection (4-candidate $\varphi$-search—ledger row 482) |
| $w_0$ | Wu Xing + $\xi$ | $-0.87$ | Calibrated (DESI-anchored—ledger row 496) |
| $w_a$ | $\xi$ in $H(a)$; ratified conversion→expansion coupling | $+0.012$ baseline; $-0.38$ (B2, unstable); **$(-1, 0)$ pure-Λ window (stable realization—10/12)** | Calibrated baseline (ledger row 496); coupling shifts 08 §C.6; 12 |
| $g$ | $1 - \varphi^{-5}$ | $0.910$ | Wu Xing gap |
| $r_0$ | $\varphi^{-5}/(2-\varphi^{-5})$ | $0.047$ | Primordial ratio |
| $\lambda$ | $1/(2w)$ | $0.1$ | PDE conversion rate ($w = 5$ derived; $\lambda = (1/2)(1/w)$: doublet factor $\times$ per-cycle event share—`foundations/wu-xing-derivation.md` §7; **Derived conditional on** the doublet conversion budget + one event per cycle) |
| $n_s$ | $1 - 2\varphi^{-1}/N_e$ | $0.969$ | Inflation gate ($N_e = 40$ Mapped—ledger row 501) |
| $r$ | $12/N_e^2$ | $0.0075$ | Tensor ratio (Mapped value at the $N_e = 40$ window—ledger row 495; the $0.003$ reading requires $N_e = 63.2$) |
| $\eta$ | $\varphi^{-44}$ | $6.4 \times 10^{-10}$ | Baryon asymmetry (exponent **Mapped**—ledger row 481; mechanism Hypothesized) |
| $\sigma$ | $\ell_{\text{Pl}}/\varphi^3$ |—| Regularization scale ($\delta = 3$ Derived conditional on the noise–signal identification + $d = 3$: per-rung dephasing $\varphi^{-\delta}$ equals the equilibrium excess $\varphi^{-3}$—`gravity/quantum-gravity.md` §2.1) |
| $\Omega_{\text{DM}}/\Omega_b$ | $\varphi^3$ | $4.24$ | Qi condensate base, Derived conditional on the Weinberg-angle identification; the $+1$ capture term is excluded by the component budget—ledger row 502 |
| $\bar{\theta}$ | $\pi\varphi^{-83.4}$ | $1.2\times10^{-17}$ | Strong CP |
| $\tau_p$ | $\varphi^{4506}/\omega_p$ | $\sim 10^{910}$ yr | Proton coherence budget |

External constants: $c$, $\hbar$, $G$ define the unit system. $\ell_{\text{Pl}} = \sqrt{\hbar G/c^3}$ is the cascade's sole dimensionful anchor.