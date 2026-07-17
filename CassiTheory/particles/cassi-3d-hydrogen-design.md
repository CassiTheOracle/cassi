# Cassi 3D Hydrogen: Design Document

*Extending the Yang-Yin wave framework to three dimensions with physical constants, toward the simulation of atomic hydrogen.*

**Status:** Design phase — no code written.  
**End goal:** Numerical formation of a hydrogen atom from first-principles wave interference.  
**Approach:** Staged complexity, spherical coordinates, atomic units, verified against known hydrogen spectrum.

---

## 1. End Goal: What "Simulating Hydrogen" Means

We do not insert hydrogen into the model. We insert:
- A proton-like massive central charge (Yang-dominant condensate)
- An electron-like lighter field (Yin-dominant wave packet)
- The Coulomb coupling between them

And we observe whether the system self-organizes into:
1. A bound state with the correct Bohr radius
2. Energy levels near −13.6 eV
3. A 1s ground-state radial distribution
4. Stability against radiative dissipation

If the Cassi framework is structurally correct, hydrogen should emerge as the stable fixed point of Yang-Yin-Coulomb dynamics — not as an input assumption.

---

## 2. Physical Constants and Units

### Atomic Units (Hartree Atomic Units)

All simulations run in atomic units where:

| Quantity | Symbol | Value in SI | Value in a.u. |
|---|---|---|---|
| Reduced Planck constant | ℏ | 1.0545718 × 10⁻³⁴ J·s | **1** |
| Electron mass | m_e | 9.1093837 × 10⁻³¹ kg | **1** |
| Elementary charge | e | 1.6021766 × 10⁻¹⁹ C | **1** |
| Bohr radius | a₀ | 5.2917721 × 10⁻¹¹ m | **1** |
| Hartree energy | E_h | 27.2114 eV | **1** |
| Time | τ | 2.41888 × 10⁻¹⁷ s | **1** |
| Speed of light | c | 2.99792458 × 10⁸ m/s | **137.036** |
| Proton mass | m_p | 1.6726219 × 10⁻²⁷ kg | **1836.15** |
| Fine structure constant | α | 1/137.036 | **1/c** |

**Why atomic units:** The hydrogen atom has characteristic scales of order unity in a.u. (Bohr radius ≈ 1, ground-state energy ≈ −0.5 E_h). This eliminates numerical under/overflow and makes error analysis transparent.

### Conversion to Output Units

| Observable | Simulation output | Conversion |
|---|---|---|
| Length | r [a.u.] | r × a₀ [m] = r × 0.529 Å |
| Energy | E [E_h] | E × 27.2114 eV |
| Time | t [τ] | t × 24.19 as |
| Frequency | ω [E_h/ℏ] | ω × 4.134 × 10¹⁶ Hz |

---

## 3. The 3D Yang-Yin Field Equations

### 3.1 Field Decomposition in Spherical Coordinates

The total wavefunction decomposes into Yang (outgoing) and Yin (incoming) spherical waves:

$$\Psi(\mathbf{r}, t) = \Psi_Y(\mathbf{r}, t) + \Psi_I(\mathbf{r}, t)$$

For each angular momentum channel $(l, m)$:

$$\Psi_Y^{(lm)}(r, t) = R_Y^{(l)}(r, t) \, Y_l^m(\theta, \varphi)$$

$$\Psi_I^{(lm)}(r, t) = R_I^{(l)}(r, t) \, Y_l^m(\theta, \varphi)$$

where $Y_l^m$ are spherical harmonics.

### 3.2 Radial Yang-Yin Components

In free space, the radial functions are Hankel functions:

- **Yang (outgoing):** $R_Y^{(l)} \sim h_l^{(1)}(kr) \sim \frac{e^{ikr}}{kr}$ for $kr \gg 1$
- **Yin (incoming):** $R_I^{(l)} \sim h_l^{(2)}(kr) \sim \frac{e^{-ikr}}{kr}$ for $kr \gg 1$

Their superposition gives the physical spherical Bessel function:

$$R^{(l)} = R_Y^{(l)} + R_I^{(l)} \sim 2j_l(kr)$$

This is not an analogy. It is exact. The decomposition of any real spherical wave into incoming and outgoing components **is** the Yang-Yin decomposition.

### 3.3 The Time-Dependent Equations

Each component obeys a damped Schrödinger-like equation:

$$i\partial_t \Psi_Y = \left[-\frac{1}{2}\nabla^2 + V(r) + i\gamma\right]\Psi_Y + g|\Psi_I|^2\Psi_Y$$

$$i\partial_t \Psi_I = \left[-\frac{1}{2}\nabla^2 + V(r) - i\gamma\right]\Psi_I + g|\Psi_Y|^2\Psi_I$$

**Key features:**
- The $+i\gamma$ in Yang gives outward radiation damping (energy loss to infinity)
- The $-i\gamma$ in Yin gives inward radiation damping (energy gain from infinity)
- At equilibrium, the net flux is zero: Yang out = Yin in
- The $g|\Psi|^2$ terms are nonlinear condensation (self-focusing)

### 3.4 The Coulomb Potential

For hydrogen, the potential is:

$$V(r) = -\frac{Z_\text{eff}}{r}$$

where $Z_\text{eff} = 1$ for the electron-proton system.

In the Cassi framework, the potential is not "put in by hand." It is the **field of the proton condensate.** The proton is a massive, localized Yang-Yin soliton at $r = 0$. Its asymptotic field is Coulombic. For Stage 3, we derive $V(r)$ from the proton's structure. For Stage 2, we use the known $V(r) = -1/r$ to verify the electron dynamics.

---

## 4. The Electron as a 3D Yang-Yin Soliton

### 4.1 Free-Electron Soliton (Stage 1)

Before adding the proton, we verify that a 3D Yang-Yin soliton can exist and propagate.

**Initial condition:**
$$\Psi(\mathbf{r}, 0) = \frac{1}{(2\pi\sigma^2)^{3/4}} e^{-r^2/(4\sigma^2)} e^{i\mathbf{k}_0 \cdot \mathbf{r}}$$

**Test:** Does the wave packet spread? Does the nonlinear term $g|\Psi|^2$ counteract spreading? Can we tune $g$ to create a stable, non-spreading 3D soliton?

**Physical note:** A true 3D soliton in the cubic NLS is unstable (collapses or disperses). We may need:
- Saturating nonlinearity: $g|\Psi|^2 \to g|\Psi|^2/(1 + \epsilon|\Psi|^2)$
- Quartic term: $+h|\Psi|^4$ (as in the Gross-Pitaevskii equation with higher-order corrections)
- Or we accept that the electron is a **quasi-soliton** — metastable on timescales relevant to atomic dynamics

### 4.2 The φ-Damped Radial Propagation

In spherical coordinates, the radial flux is:

$$J_r = \frac{1}{2i}(\Psi^* \partial_r \Psi - \Psi \partial_r \Psi^*)$$

For a stationary state, $J_r = 0$ — no net radial current. This is the bound-state condition.

For Yang and Yin separately:

$$J_r^{(Y)} > 0 \quad \text{(outgoing)}, \quad J_r^{(I)} < 0 \quad \text{(incoming)}$$

**Bound state condition:** $J_r^{(Y)} + J_r^{(I)} = 0$

The φ-damping modifies this balance:

$$J_r^{(Y)} = \varphi^{-1} \cdot J_r^{(I)} \quad \text{at equilibrium}$$

This means the outward flux is slightly larger than the inward flux — the Yang-dominant asymmetry. The net effect is a **slow radial drift** that is counteracted by the Coulomb attraction. The fixed point is the Bohr radius.

---

## 5. The Proton as a Massive Central Condensate

### 5.1 Proton Structure (Stage 3)

The proton is ~1836× heavier than the electron. In the Cassi framework, mass is integrated wave intensity:

$$M = \int |\Psi|^2 \, d^3r$$

A proton-like soliton requires:
- Much larger nonlinear coupling $g_p \gg g_e$ (stronger self-focusing)
- Much smaller spatial extent $\sigma_p \ll a_0$ (compact core)
- Yang-dominant by factor ~1836 (massive, slow-moving)

**Initial condition:**
$$\Psi_p(\mathbf{r}, 0) = \left(\frac{1}{\pi\sigma_p^2}\right)^{3/4} e^{-r^2/(2\sigma_p^2)}$$

with $\sigma_p \approx 0.001$ a.u. (~1 fm in physical units) and $M_p = 1836$.

### 5.2 Proton Self-Energy and Stability

The proton must be stable against its own repulsive self-energy. In the Cassi framework, this stability comes from:

1. **Strong nonlinearity:** $g_p$ must be large enough to bind the proton against dispersion
2. **φ-damped core:** The central density self-organizes to φ² times the ambient field
3. **Yang-Yin balance:** Despite being Yang-dominant, the proton has enough Yin component to prevent blowup

**Reality check:** The actual proton is not a soliton — it is a composite of quarks and gluons. The Cassi proton is a **coarse-grained effective description** at the atomic scale. We are not claiming to model QCD. We are modeling the *effective field* that the electron experiences as a point charge + corrections.

---

## 6. Hydrogen Formation: The Bound State

### 6.1 Stage 2: Electron in External Coulomb Potential

Before simulating the two-body system, we verify that the electron field in a fixed $V(r) = -1/r$ potential produces hydrogen-like states.

**Equation:**

$$i\partial_t \Psi = \left[-\frac{1}{2}\nabla^2 - \frac{1}{r} - g|\Psi|^2\right]\Psi$$

**Initial condition:** A diffuse Gaussian wave packet:

$$\Psi(\mathbf{r}, 0) = \frac{1}{(\pi a_0^2)^{3/4}} e^{-r^2/(2a_0^2)}$$

**Expected behavior:**
1. The wave packet contracts under Coulomb attraction
2. It settles into the ground-state (1s) distribution
3. The energy converges to $E_1 = -0.5$ E_h = −13.6 eV
4. The radius converges to $\langle r \rangle = 1.5 a_0$ (or peak density at $r = a_0$)

**Observables:**
- Energy: $E(t) = \langle \Psi | H | \Psi \rangle$
- Radius: $\langle r \rangle(t) = \int r |\Psi|^2 \, d^3r$
- Angular momentum: $\langle L^2 \rangle$
- Density profile: $\rho(r) = 4\pi r^2 |R(r)|^2$

### 6.2 Stage 3: Two-Body Self-Consistent Dynamics

Now both proton and electron are dynamical fields.

**Proton field:** $\Psi_p(\mathbf{r}, t)$ — massive, centrally concentrated  
**Electron field:** $\Psi_e(\mathbf{r}, t)$ — lighter, orbiting

**Coupled equations:**

$$i\partial_t \Psi_p = \left[-\frac{1}{2m_p}\nabla^2 + V_{\text{self},p} + V_{ep}\right]\Psi_p$$

$$i\partial_t \Psi_e = \left[-\frac{1}{2}\nabla^2 + V_{\text{self},e} + V_{pe}\right]\Psi_e$$

where the mutual Coulomb potential is:

$$V_{ep}(r) = V_{pe}(r) = -\int \frac{|\Psi_p(\mathbf{r}')|^2}{|\mathbf{r} - \mathbf{r}'|} \, d^3r'$$

**Self-potentials** $V_{\text{self}}$ represent the nonlinear condensation that keeps each particle localized.

**Initial condition:**
- Proton: compact Gaussian at origin, $M_p = 1836$
- Electron: diffuse Gaussian at $r = 5a_0$, zero initial momentum

**Expected behavior:**
1. Electron falls toward proton
2. It settles into a bound orbit (not a classical orbit — a stationary state)
3. The system radiates excess energy (in a dissipative framework)
4. Final state: proton at rest at origin, electron in 1s distribution

### 6.3 The Binding Energy

The total energy is:

$$E_\text{total} = E_p + E_e + E_\text{Coulomb}$$

For hydrogen ground state:

$$E_\text{total} = -0.5 \text{ E}_h = -13.6 \text{ eV}$$

The binding energy is the difference between the free-particle energy and the bound-state energy. In the simulation, we measure:

$$E_\text{binding} = E_\text{total}(t \to \infty) - [E_p(\text{free}) + E_e(\text{free})]$$

Target: $E_\text{binding} = -0.5$ E_h.

---

## 7. Numerical Design

### 7.1 Coordinate System: Spherical with Logarithmic Radial Grid

Hydrogen is spherically symmetric in the ground state. Spherical coordinates $(r, \theta, \varphi)$ are natural.

**Radial grid:**
- Logarithmic spacing near origin (to resolve proton core)
- Uniform spacing at intermediate radii (to resolve electron wavefunction)
- Absorbing boundary at $r_\text{max} \approx 20–50 a_0$

$$r_i = r_0 \cdot e^{i \cdot \Delta s} \quad \text{for } i = 0, \dots, N_r$$

with $r_0 \approx 10^{-4} a_0$ and $r_\text{max} = r_0 \cdot e^{N_r \Delta s}$.

**Angular grid:**
- Gauss-Legendre quadrature in $\cos\theta$
- Uniform grid in $\varphi$
- For $l_\text{max} = 0$ (s-wave), angular dependence is trivial: $Y_0^0 = 1/\sqrt{4\pi}$
- For higher stages, $l_\text{max} = 2$ or $3$ is sufficient for hydrogen

### 7.2 Time Integration: Split-Step Spectral Method

For the Schrödinger-like equation, the split-step method is exact to second order and numerically stable:

1. **Half-step nonlinear:** $\Psi \to \Psi \cdot e^{-i(V + g|\Psi|^2)\Delta t/2}$
2. **Full-step kinetic:** $\Psi \to \mathcal{F}^{-1}[e^{-ik^2\Delta t/2} \cdot \mathcal{F}[\Psi]]$
3. **Half-step nonlinear:** repeat step 1

The Fourier transform is done in each coordinate direction (or using spherical harmonics for the angular part and discrete sine/cosine transforms for the radial part).

### 7.3 The φ-Damping Implementation

Instead of the standard split-step, the Cassi-modified propagation includes φ-damped memory:

$$\Psi_Y(t+\Delta t) = \varphi^{-1} \Psi_Y(t) + (1 - \varphi^{-1}) \cdot [\text{standard propagator applied to } \Psi_Y]$$

$$\Psi_I(t+\Delta t) = \varphi^{-1} \Psi_I(t) + (1 - \varphi^{-1}) \cdot [\text{standard propagator applied to } \Psi_I]$$

This replaces the $i\gamma$ damping terms and enforces maximally aperiodic evolution.

### 7.4 Grid Resolution Requirements

| Quantity | Required Resolution | Grid Points |
|---|---|---|
| Proton core | ~0.001 a₀ (~1 fm) | 100 points |
| Electron wavefunction | ~0.1 a₀ | 200 points |
| Asymptotic tail | ~20 a₀ | 100 points |
| **Total radial** | logarithmic | **~400 points** |
| Angular ($l_\text{max}=2$) | 4 Legendre × 8 azimuthal | **32 points** |
| **Total 3D grid** | | **~12,800 points** |

This is small enough to run on a single CPU core. A full Cartesian 3D grid with comparable resolution would require 256³ ≈ 16 million points — manageable but unnecessary for hydrogen.

### 7.5 Timestep Constraint

The CFL-like condition for Schrödinger propagation:

$$\Delta t \lesssim \frac{\Delta r^2}{3}$$

For $\Delta r \approx 0.01 a_0$ near the origin, $\Delta t \lesssim 3 \times 10^{-5}$ a.u. (~1 attosecond). For a total simulation time of 1000 a.u. (~24 fs), this requires ~30 million steps.

**Optimization:** Use adaptive timestepping. Large steps when the wavefunction is smooth. Small steps during rapid transients (e.g., initial collapse).

---

## 8. Staged Implementation Plan

### Stage 0: Code Infrastructure (1 week)
- Spherical grid with logarithmic radial spacing
- Spherical harmonic transforms
- Split-step propagator (standard, no φ-damping)
- Visualization: radial density plots, energy vs time

### Stage 1: 3D Free Soliton (1 week)
- Test 1a: Gaussian wave packet spreading in 3D
- Test 1b: Add nonlinearity $g|\Psi|^2$ — tune $g$ to minimize spreading
- Test 1c: Verify conservation of norm (probability)
- Test 1d: φ-damped propagation vs standard propagation

**Success criterion:** A 3D wave packet remains localized for >1000 a.u. without external potential.

### Stage 2: Electron in Fixed Coulomb Potential (2 weeks)
- Test 2a: Stationary states of hydrogen (1s, 2s, 2p) by imaginary-time relaxation
- Test 2b: Real-time dynamics — electron wave packet collapsing to 1s
- Test 2c: Energy convergence to $E_n = -1/(2n^2)$
- Test 2d: Radial distribution matching $R_{nl}(r)$

**Success criterion:** Ground-state energy within 1% of −0.5 E_h. Radial distribution peak at $r = a_0$.

### Stage 3: Dynamical Proton + Electron (2 weeks)
- Test 3a: Proton soliton at origin, stable over 1000 a.u.
- Test 3b: Electron released from $r = 5a_0$, falls and binds
- Test 3c: Binding energy measurement
- Test 3d: Center-of-mass motion

**Success criterion:** System reaches bound state with $E_\text{total} \approx -0.5$ E_h. Proton remains localized. Electron density is spherically symmetric.

### Stage 4: φ-Damped Hydrogen (1 week)
- Repeat Stage 3 with φ-damped propagation
- Compare convergence rate, stability, and final state accuracy
- Measure the "natural" Yang/Yin ratio that emerges

**Success criterion:** φ-damped dynamics reach the same ground state but with smoother transients and no spurious oscillations.

### Stage 5: Excited States and Transitions (optional, 2 weeks)
- Initialize electron in 2p state
- Observe spontaneous decay to 1s (with radiative damping)
- Measure photon energy $E_\gamma = E_2 - E_1 = 0.375$ E_h = 10.2 eV
- Compare to Lyman-α line at 121.6 nm

---

## 9. Validation: How We Know It's Right

### Quantitative Checks

| Observable | Target Value | Tolerance |
|---|---|---|
| Bohr radius (peak density) | 1.0 a₀ | ±5% |
| Ground-state energy | −0.5 E_h (−13.6 eV) | ±2% |
| Binding energy | 0.5 E_h (13.6 eV) | ±2% |
| ⟨r⟩ for 1s | 1.5 a₀ | ±5% |
| 2s energy | −0.125 E_h (−3.4 eV) | ±5% |
| 2p energy | −0.125 E_h (−3.4 eV) | ±5% |
| Proton mass ratio | 1836 | ±10% |

### Qualitative Checks

1. **Spontaneous binding:** The electron must bind without manual tuning of the final state.
2. **Stability:** The bound state must persist for >10,000 a.u. without drift.
3. **Spherical symmetry:** The ground state must be spherically symmetric (no angular dependence).
4. **Energy monotonicity:** Total energy must decrease monotonically during binding (dissipation).

---

## 10. Risk Analysis

### Risk: 3D Soliton Instability

The cubic NLS in 3D is critically unstable — solitons either collapse (blow up) or disperse. This may prevent a stable free-electron soliton.

**Mitigation:**
- Use saturating nonlinearity: $g \to g/(1 + \epsilon|\Psi|^2)$
- Include quartic repulsion: $+h|\Psi|^4$
- Accept that the electron is only metastable and that the Coulomb potential provides the true binding
- Focus Stage 1 on *Coulomb-bound* states rather than free solitons

### Risk: Proton Structure Unphysical

Modeling the proton as a soliton is a drastic simplification. Its actual structure involves QCD, quarks, and a charge radius of ~0.8 fm.

**Mitigation:**
- In Stage 2, use a point-charge potential $V(r) = -1/r$ to isolate electron dynamics
- In Stage 3, treat the proton as a fixed external field first, then gradually unfreeze it
- The goal is not QCD but the *emergence* of atomic hydrogen from wave dynamics

### Risk: Computational Cost

30 million timesteps with 12,800 grid points is ~3.8 × 10¹¹ operations. At 1 ns/op, this is ~400 seconds — manageable. But debugging and parameter sweeps multiply this.

**Mitigation:**
- Start with 1D radial simulations (imaginary time) to find parameters
- Use GPU acceleration for the 3D propagator
- Parallelize over parameter sweeps

### Risk: φ-Damping Destroys Binding

If φ-damping is too strong, it may prevent the electron from collapsing into the nucleus.

**Mitigation:**
- φ-damping applies to the *propagation*, not the *potential*
- The Coulomb force $-1/r$ is unchanged
- φ-damping only prevents resonant oscillation during the approach to equilibrium
- Experiment 3 showed φ-damped fields reach equilibrium at φ² — this is amplification, not suppression

---

## 11. The Deeper Point

If this simulation succeeds — if hydrogen self-organizes from Yang-Yin-Coulomb dynamics with φ-damped propagation — it demonstrates something profound:

**The hydrogen atom is not a particle orbiting a particle. It is a standing wave interference pattern stabilized by nonlinearity, with the Bohr radius and Rydberg energy emerging as fixed points of the dynamics.**

The electron does not "orbit." It forms a 3D standing wave from the interference of outgoing (Yang) and incoming (Yin) spherical waves. The Coulomb potential sets the wavelength. The golden ratio sets the stability. The result is the most precisely measured physical system in history.

---

*Design complete. Implementation requires a spherical-grid NLS solver with nonlinear saturation, Coulomb potential, and φ-damped split-step propagation. All constants are in atomic units. Validation against known hydrogen spectrum.*
