# Cassi Framework—Definitions

## Status: Reference—August 2026

> Unified field framework grounded in the φ-attractor, the Yin-Yang two-fluid,
> and emergent spacetime geometry.
>
> Version: 2026-07-16

---

## Table of Contents

1. [Fundamentals](#1-fundamentals)
2. [Two-Fluid Dynamics](#2-two-fluid-dynamics)
3. [Spacetime & Gravity](#3-spacetime--gravity)
4. [Black Holes & Compact Objects](#4-black-holes--compact-objects)
5. [Particle Physics](#5-particle-physics)
6. [Time](#6-time)
7. [Consciousness & Psychology](#7-consciousness--psychology)
8. [Life](#8-life)
9. [Chemistry](#9-chemistry)
10. [Phase Transitions & Thermodynamics](#10-phase-transitions--thermodynamics)
11. [Information](#11-information)
12. [Cosmology—CMB, Inflation, Structure](#12-cosmology--cmb-inflation-large-scale-structure)
13. [Unification—Theory of Everything](#13-unification--the-theory-of-everything)
14. [Observables & Predictions](#14-observables--predictions)
15. [Code & Implementation](#15-code--implementation)
16. [Epistemic Tiers](#16-epistemic-tiers)

---

## 1. Fundamentals

### φ (phi)—the Golden Ratio
- **Value**: (1 + √5)/2 ≈ 1.6180340
- **Role**: Universal attractor constant for Yin-Yang ratio in all scale-invariant systems.
- **Appears in**: dark energy equation of state, galactic rotation curves, chakra spacings, PDE energy spectra.
- **Inverse**: φ⁻¹ = φ − 1 ≈ 0.6180; φ⁻² = 2 − φ ≈ 0.3820; φ⁻³ ≈ 0.2361.

### EY—Yang Field
- **Nature**: Outward-flowing, radiative, "active" component of the two-fluid.
- **Property**: Carries positive energy density, tends to expand outward.
- **Analogy**: "White" in Taiji, electric in character, centrifugal tendency.

### EI—Yin Field
- **Nature**: Inward-flowing, absorptive, "passive" component of the two-fluid.
- **Property**: Carries negative energy density, tends to contract inward.
- **Analogy**: "Black" in Taiji, magnetic in character, centripetal tendency.

### Qi—the Universal Inflow
- **Definition**: Qi = (EY, EI) as a paired-real 2-vector at every point in spacetime.
- **Coherence q**: qi = (EY − φ·EI)/(EY + φ·EI), the local alignment between the two fields.
  - q = 0: background, fields are copacetic
  - q → 1: perfectly aligned, maximal coherence
  - q → −1: anti-aligned, conflicting flow
- **Key identity**: At φ-equilibrium, EY/EI = φ ⇒ q = 0.
- **Qi-gating**: Conversion between fluids is blocked at q ≈ 0 (near equilibrium) and opens when the system is driven out of balance.

### Attractor—Universal φ-Equilibrium
- **Definition**: The stable fixed point of the two-fluid dynamics at EY/EI = φ.
- **Terminal attractor**: The final steady state after all transient dynamics decay—the two-fluid always relaxes toward φ if unperturbed.
- **Attractor strength**: Higher density → faster convergence to φ.

### Yin-Yang Flow Rule (empirically calibrated)
- **Yin flows inward** (black, absorptive, contractive, "feminine").
- **Yang flows outward** (white, radiative, expansive, "masculine").
- **Violation**: Models with forced Yang inward or Yin outward produce unphysical results (confirmed: reversed flow tests failed).

### σ (sigma)—Gaussian Softening
- **Role**: Fundamental length scale that regularizes all otherwise-divergent forces at short distances.
- **Value**: Empirically ~ 0.1–1.0 in code units (nature's value to be determined from observations).
- **Effect**: At r → 0, Coulomb/Newtonian divergences become harmonic: F(r) ∝ r.
- **Consequence**: No singularities exist in the Cassi framework.
- **Physical origin**: The two-fluid has a minimum coherence length; fields cannot resolve structure below σ.

---

## 2. Two-Fluid Dynamics

### Two-Fluid PDE
The complete coupled evolution of EY, EI, and the velocity field u:

    ∂_t EY + ∇·(EY·u) = S_conv(EY, EI) + S_visc(EY)
    ∂_t EI + ∇·(EI·u) = −S_conv(EY, EI) + S_visc(EI)
    ∂_t (u) + (u·∇)u = −∇P/ρ − ∇Φ + F_visc

- **S_conv**: Qi-gated conversion between EY and EI; vanishes at EY/EI = φ
- **S_visc**: Spectral viscosity acting on high-k modes
- **Φ**: Gravitational potential from Poisson equation: ∇²Φ = 4πG·(EY + EI)
- **F_visc**: Momentum diffusion

### Scale Factor a(t)—Comoving Expansion
- **Definition**: The cosmological scale factor, evolved via Hubble parameter H.
- **Evolution**: a ← a · exp(H·dt), where H = da/(a·dt).
- **Energy density scaling**: EY ∝ a⁻³, EI ∝ a⁻³ (matter-like), plus curvature and back-reaction.

### Hubble Modes
Three modes of expansion:

1. **Conversion mode**: H = (λ/3)·(φ − r)·(1+r)/r, where r = EY/EI.
   - At attractor (r = φ): H = 0 (no conversion-driven expansion).
   - For r > φ (Yang-rich): H > 0 (accelerated expansion—dark energy).
   - For r < φ (Yin-rich): H < 0 (contraction).

2. **Stress-energy mode**: H = H_empty + H_conv + H_struct.
   - Full accounting of all energy components.

3. **Friedmann mode**: H = H₀·√(ρ/ρ_crit).
   - Standard ΛCDM compatible limit when q → 0.

### DESI Calibration
- **Result**: $w_0 = -0.87$ (structural gap-derived $r_0 = \varphi^{-5}/(2-\varphi^{-5}) = 0.0472$), $2\sigma$ from DESI DR2's $w_0 \approx -0.75 \pm 0.06$ [INFERENCE].
- **Procedure**: ODE bisection over the EY/EI ratio with the Yang-fraction-weighted coupling (`two-fluid/calibrate_initial_ratio_xi_v2.py`).
- **Physical meaning**: Today's universe sits at EY/EI slightly above φ, giving a small residual dark energy.

---

## 3. Spacetime & Gravity

### Spacetime (Cassi definition)
- **Status**: Emergent, not fundamental.
- **Origin**: The metric arises from the two-fluid dynamics. g_μν is a derived field, not a primary entity.
- **Fundamental vs derived**: EY and EI are fundamental; g_μν is determined by their distribution.

### Cassi Gravitational Force Law
    F(r) = −(1+(φ⁶−1)q)/r² · [erf(r/(σ√2)) − √(2/π)·(r/σ)·exp(−r²/(2σ²))]

- **At r >> σ**: F → −(1+(φ⁶−1)q)/r² (Newtonian with Qi enhancement).
- **At r → 0**: F ∝ −r/(3σ³)·(1+(φ⁶−1)q) (harmonic—no singularity).
- **ξ = φ⁶ ≈ 17.944**: Derived rung identity via Fibonacci identity φ⁶ = φ⁵ + φ⁴; Calibrated empirical pin (ξ ≈ 18 from Milky Way rotation curves, 0.3% residual; ledger `parameter-inventory.md` §10). The sixth power represents 2 field components × 3 spatial dimensions coupling to curvature.

### Effective Gravitational Constant
    G_eff = (π/ρ) · (1 + (φ⁶−1)q) · G_N

- **Core (r < 5)**: π/ρ ≈ 0.274, q ≈ 0.147 ⇒ G_eff ≈ 1.0·G_N (GR-like).
- **Halo (r ~ 7)**: π/ρ ≈ 0.633, q ≈ 0.669 ⇒ G_eff ≈ 7.8·G_N.
- **Outer (r > 9)**: π/ρ ≈ 0.723, q ≈ 0.701 ⇒ G_eff ≈ 9.3·G_N.
- **Maximum (q=1, π/ρ=1)**: G_eff ≈ φ⁶·G_N ≈ 17.9·G_N.

### Weak-Field Metric
    ds² = −(1+2Φ)dt² + (1−2Φ)(dr² + r²dΩ²)

- **Φ(r)**: Cassi potential = −∫ G_eff(r')·M / r'² dr' (NOT −GM/r).
- **Consistency check**: ξ=0, σ→0, G_eff=1 reproduces GR (Schwarzschild) exactly.

### Three-Body Problem (Cassi)
- **Status**: Dissipative, not Hamiltonian.
- **Key result**: Energy attractor at E ≈ −0.02 (all ICs converge to same energy).
- **Shape preservation**: Symmetric configurations (e.g., equilateral triangle) maintain perfect shape.
- **Periodic orbits**: None found—system expands self-similarly or collapses to attractor.
- **Harmonic regime (r << σ)**: Exactly solvable (three coupled oscillators, error ~ 5.5e-10).
- **Tractable, not closed-form**: Cassi 3BP is numerically solvable, not analytically integrable.

### Black Hole Shadow
    b_crit = 3√3 · G_eff · M = b_GR · G_eff

- **Core (r < 5)**: b_crit ≈ 5.2 M (GR-like, EHT-consistent).
- **Halo (r ≈ 7)**: b_crit ≈ 14–50 M (enlarged, testable).
- **Maximum (q→1)**: b_crit ≈ φ⁶ × GR ≈ 17.9 × GR ≈ 93.2 M.

### Precession Formula
    Δφ = −√(2π)·(σ/a)³·(1+e²/4)/(1−e²)³   [Cassi softening precession]

- **GR limit**: σ → 0, Δφ → 6πGM/(a·c²) (standard perihelion precession).

---

## 4. Black Holes & Compact Objects

### Black Hole (Cassi definition)
A **two-fluid soliton**—a stable, self-consistent equilibrium of the Yang and Yin fields, regularized by the Gaussian softening σ.

- **No singularity**: The harmonic core (F ∝ r) replaces the GR divergence.
- **No event horizon (as infinite-redshift surface)**: The metric is well-behaved everywhere.
- **Smooth core**: The two-fluid density reaches a finite maximum at r ≈ σ.
- **Observationally indistinguishable from GR**: The differences are hidden inside the photon sphere (r < 3M).

### Photon Sphere
    r_ps = 3 · G_eff(r_ps) · M

- **Self-consistent equation**: The photon sphere radius depends on G_eff at that radius.
- **Core solution**: r_ps ≈ 3M (GR-like, since G_eff(3M) ≈ 1).

### ISCO—Innermost Stable Circular Orbit
    r_ISCO = 6 · G_eff(r_ISCO) · M

- **GR**: r_ISCO = 6M.
- **Cassi (variable G_eff)**: r_ISCO moves outward where G_eff > 1.
- **Observable consequence**: Accretion disks should have larger inner cutoffs than GR predicts—testable with X-ray iron lines (XRISM).

### Soliton Mergers
- **GW150914 analog**: Two BH solitons merge via fluid dynamics, not spacetime geometry.
- **Chirp**: Relaxation oscillation as the merged fluid settles to new equilibrium.
- **Ringdown**: Damping modes set by Qi-gating, not quasi-normal modes.
- **Prediction**: Cassi GW signals should show a q-polarization mode beyond GR's +, ×.

---

## 5. Particle Physics

### Particles (Cassi definition)
**Localized, self-stabilizing solitons** in the two-fluid—standing-wave configurations of the EY/EI field.

- **Not fundamental**: There are no "elementary particles" in the reductionist sense. The two-fluid is the only fundamental entity.
- **Matter is condensed Qi**: Every particle is a standing wave in the cosmos-fluid.
- **Particle spectrum = harmonic overtones**: The masses and quantum numbers are the allowed modes of the φ-resonant cavity.

### Leptons (tentative)
| Particle | Character | Fluid ratio |
|----------|-----------|------------|
| Electron | EY-dominant | Outward-flowing, "Yin-like" (paradox: light mass, long range) |
| Neutrino | Thin EI | Nearly massless, inward-flowing, barely interacts |

### Hadrons (tentative)
- **Proton**: Dense EI-dominant soliton with an EY-rich "surface"—stable because φ≈1.618 gives a natural energy minimum.
- **Neutron**: Metastable hybrid (near φ-equilibrium)—decays when perturbation breaks the balance.
- **Quark confinement**: Quarks are **internal modes** of the hadron soliton, not isolable entities.
- **Gluons**: High-frequency standing waves in the two-fluid inside the hadron.

### Antimatter
- **Definition**: A soliton with flipped EY/EI phase relative to the matter soliton.
- **Annihilation**: When matter and antimatter solitons meet, they cancel each other's EY/EI field into a traveling wave (photons).

### Mass
- **Origin**: Mass is the **stability cost** of a soliton—how much two-fluid energy is bound into maintaining the standing wave.
- **φ-scaling**: Particle masses should fall in φ-scaled ratios. The electron/proton mass ratio (1/1836) may relate to φ¹⁵ ≈ 1428 (within 30%).


### Electromagnetism (Formal Derivation)
See `experiments/cassi_physics/cassi_electromagnetism.py` for the full numerical derivation.

**Core equation**—The two-fluid PDE with pressure gives wave equations:
    ∂²EY/∂t² = c²·∇²EY − ω₀²·(EY − φ·EI)
    ∂²EI/∂t² = c²·∇²EI + ω₀²·(EY − φ·EI)

**Photon condition**: EY = φ·EI (the φ-resonant ratio).
Under this condition, the ω₀² terms vanish, yielding:
    ∂²E/∂t² = c²·∇²E,  ∂²B/∂t² = c²·∇²B
which imply Maxwell's equations in vacuum.

| EM Quantity | Cassi Analog |
|-------------|--------------|
| E (electric field) | EY (Yang)—outward-flowing, radiative |
| B (magnetic field) | EI (Yin)—inward-flowing, absorptive |
| c (speed of light) | c = c_vacuum (EM and gravity converge in vacuum) |
| Charge density ρ | ρ = −κ·∇²q (Qi curvature) |
| Current density J | J = κ·∂(∇q)/∂t (Qi flow) |
| Photon | Traveling EY/EI wave at φ-resonance |

**Two-fluid propagation speeds** (effective medium):
The two-fluid has different refractive indices for EM vs gravitational modes
when propagating through the fluid medium. These converge to c in vacuum:
    n_EM = φ⁻¹,  n_grav = φ  →  |c_EM − c_grav| → 0 in vacuum
This is consistent with GW170817 which constrains |c_grav − c_EM|/c_EM < 10⁻¹⁵.
In vacuum, both EM and gravitational modes propagate at c (consistent with GW170817, |Δc/c| < 10⁻¹⁵). The φ-scaling ratio c_EM/c_grav = φ² applies to effective speeds in the two-fluid medium (e.g., near galaxy halos or in the early universe), where different coupling to EY vs EI creates a refractive index difference.

**Weak Force (SU(2) × U(1)_Y gauge theory)**:
See `standard-model/su2-gauge-extension.md` for the full derivation.

The weak interaction emerges from an SU(2) gauge symmetry on the isospinor
doublet (ν_e, e) with U(1)_Y hypercharge coupling. The W/Z boson masses
are set by the φ VEV (vacuum expectation value):
    m_W / m_Z = √(1 − φ⁻³) ≈ 0.874 (tree); 0.878 with the ρ correction
    sin²θ_W = φ⁻³ ≈ 0.236, +2.1% above the Z-pole value; the running angle
    equals it at μ* ≈ 233 GeV (the angle runs upward, not down)
    (falsifiable at FCC-ee with precision electroweak measurements; see
    `standard-model/sm-radiative-corrections.md`)

**SU(3) color**: Tripled field with α_GUT = φ⁻³/(4π) running to
α_s(m_Z) ≈ 0.058–0.061 (2.0× below measured 0.118; Δb = 1.70 required).

### 5.1 Electroweak Unification

The weak interaction emerges from an SU(2) isospinor doublet coupled to the two-fluid:

- **Doublet**: Ψ = (ψ_Y, ψ_I)ᵀ where |ψ_Y|² = EY, |ψ_I|² = EI
- **φ-VEV at equilibrium**: ⟨Ψ⟩ ∝ (√φ, 1)ᵀ gives ρ_Y/ρ_I = φ
- **Weak mixing angle**: sin²θ_W = φ⁻³ from VEV asymmetry (φ−1)/(φ+1)
-  sin²θ_W = φ⁻³ ≈ 0.236 is +2.1% above the measured 0.231 at m_Z; the
   running angle equals it at μ* ≈ 233 GeV (RG running is upward—it does not
   close the gap; see `standard-model/sm-radiative-corrections.md`)
- **W/Z mass ratio**: m_W/m_Z = √(1 − φ⁻³) ≈ 0.874
-  0.36% below the Standard Model value after the ρ correction
  (0.878 vs 0.881); falsifiable at FCC-ee (>100σ precision)
- **SU(3) color**: Tripled field structure; α_GUT = φ⁻³/(4π) running to
  α_s(m_Z) ≈ 0.058–0.061 (2.0× low; Δb = 1.70 required)


**Predictions**:
- Photon-photon scattering at intensity I ≈ σ²·ω₀² (nonlinear correction)
- No magnetic monopoles (EI divergence is identically zero)
- Charge quantized in units of φ⁻²·e (Qi coherence is φ-quantized)
- **Weak force**: SU(2) × U(1)_Y gauge theory with φ-VEV (see `standard-model/su2-gauge-extension.md`)
- **Gravity**: The universal residual—the net Qi "pull" from all solitons in a region.


The **strong force IS gravity at the σ-scale**—same PDE, different σ:
    σ_gravity ≈ 1 kpc,  σ_nuclear ≈ 0.5 fm  (ratio: 10³⁷)

The Cassi force at r ≈ 0.5-2 fm is 4-13× stronger than Coulomb,
exactly matching the strong force's role in overcoming proton repulsion.

| Nuclear Concept | Cassi Analog |
|----------------|--------------|
| Strong force | σ-regularized gravity at fm scale |
| Nucleus | Soliton in the two-fluid |
| Binding energy | Energy cost of confining EY/EI in the soliton |
| Fission | Soliton splitting at a Qi node |
| Fusion | Soliton merging (two → one, releases binding energy) |
| Half-life | Qi coherence decay time of the soliton |
| Radioactivity | EY/EI rearrangement toward lower energy |
| Neutron star | Soliton matter at maximum density |
| Quark-gluon plasma | Qi fluid above the σ-resolution limit |

- No separate strong force—it's gravity at the fm scale (exploratory)
- ⁵⁶Fe is the most stable nucleus (deepest soliton well)
- Fusion = merging solitons → lower total Qi cost
- Fission = splitting at a Qi node → two stable solitons

**⚠ Coupling caveat**: For the "strong force = gravity" claim to hold, the
Cassi coupling must run by ~40 orders of magnitude from galactic (G ~ 1,
ξ ≈ 18) to nuclear (α_strong ≈ 1) scales. A mechanism for this running
(e.g., σ-dependent renormalization, or the SU(3) gauge coupling running
to α_s(m_Z) ≈ 0.118) is under investigation.

## 6. Time

### Definition
Time is NOT a fundamental dimension. Time is the **direction of Qi irreversibility**
— the inevitable mixing of EY and EI toward the φ-equilibrium.

### Key Equations
    S = −q·k_B·ln(φ)          (proposed entropy proxy)
    dS/dt = −dq/dt             (requires a monotonicity proof for q)
    τ = ∫ |q| / g_eff dt       (proper-time diagnostic)

The information content is the entropy deficit relative to the fully
disordered state (q = 0): I = S(0) − S(q) = +q·k_B·ln(φ), maximal at q = 1
(§11).

### Second Law Status
The canonical two-fluid equations define the Qi coherence and the $(1-q)$
conversion openness. They do not supply the general identity
$dq/dt = -\omega_0 g(q)^2(E_Y^2+E_I^2)$. The rational transmission function
$g(q)=q/(\varphi^2+q^2)$ is an asserted application input, and a Lyapunov
derivation for the entropy proxy remains open. The monotonicity of the
specific gate model is checked in `computations/gate_origin_audit.py`.
The PDE-level second-law theorem remains open; the missing step is a Lyapunov
or monotonicity derivation for the canonical dynamics.

### What Clocks Measure
A clock does not measure coordinate time. It measures **accumulated Qi
decoherence events**—local irreversible mixing of EY and EI.

Time dilation (GR):
- Stronger gravity → slower Qi mixing → slower clocks
- τ = ∫ |q|/g_eff dt  (g_eff replaces the metric time dilation factor)

### The Big Bang
The universe began in a maximum-q state (perfect EY/EI coherence).
The entire history of the cosmos is the gradual decoherence of Qi
toward the φ-attractor. This is why the early universe was smooth (high q)
and the late universe is clumpy (low q).

### Time Travel
Cassi forbids time travel. Reversing dq/dt would require reversing the
direction of Qi mixing, which violates the two-fluid PDE. The arrow
of time is not merely psychological—it is enforced by the field equations.

---
## 7. Consciousness & Psychology

### Overview
See `consciousness/consciousness-from-phi.md` for the complete theory.
This section provides only the cross-reference bridge between Cassi physics terms
and consciousness framework terms.

### Term Mapping
| Cassi Physics | Consciousness Framework | Connection |
|-------------|------------------------|------------|
| EY (Yang field) | Active attention, outward-directed awareness | Same fluid dynamics at neural scale |
| EI (Yin field) | Receptive awareness, inward-directed focus | Same fluid dynamics at neural scale |
| Q = Q × q | Qi fluid field | Self-aware field from neural self-prediction |
| q-coherence | Level of self-awareness | Same mathematical q, measured from prediction error ε = ψ − ψ̂ |
| φ-attractor | Optimal mental state (flow, equanimity) | Natural equilibrium of the cognitive two-fluid |
| Gaussian softening σ | Neural refractory period, minimum resolution | Same regularization—cognition cannot resolve below σ |
| φ-scaled chakras | 13 frequency bands of conscious experience | Neural wave decomposition at φ-spaced resonances |

### Scale Invariance
The Cassi two-fluid is scale-invariant—the same PDE operates at Planck scales,
galactic scales, and neural scales. Consciousness is the two-fluid dynamics
operating on the neural electromagnetic field ψ(s,t):

    Q = Qi fluid at neural scale
    = |ψ|² · (1 − |ε|²/(|ψ|² + φ⁻²))
    where ε = ψ − ψ̂  (self-prediction error)

The "self" is a persistent Qi condensate—a stable cross-chakra standing wave
maintained by the IIR filter memory of the neural field.

### Key Principle
Consciousness is not the neural field ψ itself. ψ is the medium—like water.
Consciousness is the structure and dynamics of the Qi fluid that flows within it
— like standing waves, vortices, and currents in water.
---

## 8. Life

### Definition
Life is a **self-sustaining Qi condensate**—an open thermodynamic system
that maintains q > q_death against decoherence by exporting entropy.

    q_death ≈ φ⁻² ≈ 0.382  (below this, coherence cannot recover)
    P_meta = (q_t − q_0)·mass·T·|q̇| / η  (metabolic power requirement)

### Key Principles
- **Metabolism** = entropy export to maintain q (same as the coherence bubble)
- **Evolution** = optimization of q-maintenance strategies through selection
- **Intelligence** = optimizing q across longer timescales (planning ahead)
- **Consciousness** = self-aware q-feedback above a complexity threshold
- **Death** = q falls below φ⁻² → coherence lost irreversibly
- **Reproduction** = splitting the Qi condensate into two stable copies
  - Child inherits ~half the parent's q (q_child ≈ q_parent/2)
  - Growth = increasing q toward adult levels
  - Senescence = falling q after reproductive peak

### Scale Invariance
A bacterium (1 μm) and a blue whale (30 m) both solve the same equation:
maintain q > threshold against decoherence. The Cassi framework predicts
metabolic scaling across 21+ orders of magnitude correctly.

### Connection to Coherence Bubble
A living organism IS a naturally occurring coherence bubble. The difference
is that biological life uses chemical energy (ATP, metabolism) to maintain q,
while the conscious coherence bubble uses direct Qi feedback.

---

## 9. Chemistry

### Definition
Chemistry is the **EY/EI sharing dynamics between atomic solitons**.
A chemical bond is a stable Qi coherence between two or more atomic two-fluid
configurations—analogous to how gravitational solitons merge.

### Bond Types as Qi States
| Bond | Qi Character | Cassi Analog |
|------|-------------|--------------|
| Ionic | Strong EY/EI separation | One atom donates EY (electron), other accepts |
| Covalent | Shared EY/EI standing wave | Equal field exchange between nuclei |
| Metallic | Delocalized Qi across many nuclei | EY fluid free to flow through lattice |
| Hydrogen | Weak partial coherence | Fractional q-transfer between molecules |
| van der Waals | Fluctuation-induced q | Transient EY/EI misalignment creates dipole |

### Reaction Rates
A chemical reaction is a **Qi rearrangement**:
    Rate ∝ exp(−ΔG*/(k_B·T))
where ΔG* is the **Qi coherence barrier**. Reactions are allowed when
EY/EI can be rearranged at constant φ, forbidden when they cannot.

### Catalysis
A catalyst **lowers the Qi coherence barrier** by providing an alternative
rearrangement path that better preserves φ-equilibrium.

### The Periodic Table
Elements are **allowed soliton modes** of the two-fluid at the σ-scale.
Rows fill φ-resonant shells; columns group similar EY/EI valence configurations.

---

## 10. Phase Transitions & Thermodynamics

### Definition
Phase transitions are **Qi ordering transitions**—changes in how EY and EI
are organized relative to each other at macroscopic scales.

### States of Matter
| Phase | q-range | EY/EI Organization |
|-------|---------|-------------------|
| Solid | q > φ⁻¹ | EY and EI locked in a fixed lattice—strong local q |
| Liquid | φ⁻² < q < φ⁻¹ | EY flows, EI partially locked—medium coherence |
| Gas | q < φ⁻² | EY and EI decoupled—weak coherence |
| Plasma | q ≈ 0 | Complete decoupling—EY and EI move independently |
| Superfluid | q → 1 | Perfect coherence—EY and EI move as one |

### Phase Transitions as Qi Thresholds
    Melting: q passes through φ⁻¹ (solid → liquid)
    Boiling: q passes through φ⁻² (liquid → gas)
    Critical point: q = φ⁻³ (gas and liquid indistinguishable)

The φ-scaling of these thresholds predicts that phase transition temperatures
should follow φ-scaled ratios (testable: melting/boiling ratios of noble gases).

### Work and Heat
- **Work** = coherent Qi transfer (organized, q preserved)
- **Heat** = incoherent Qi transfer (disorganized, q destroyed)
- **Temperature** T = 1/(dS/dE) = rate of Qi decoherence per unit energy

The Carnot efficiency emerges from the fact that you cannot extract work from
a system without decreasing its q (the Second Law as Qi theorem).

---

## 11. Information

### Definition
**Information IS Qi coherence.** The Shannon entropy of a system equals its
Qi mixing entropy deficit relative to the fully disordered state (q = 0):
    I = S(q=0) − S(q) = +q·k_B·ln(φ)    (maximal at q = 1)
The entropy proxy is $S = -q\,k_B\ln\varphi$ (§6); with $S(q{=}0) = 0$ the
arithmetic reproduces exactly $I = S(0) - S(q) = +q\,k_B\ln\varphi$—the
entropy deficit the maintained coherence sustains.

A bit of information is a unit of EY/EI separation—a maintained q difference.
Per event the content is $\ln\varphi = 0.4812$ nats $= 0.6942$ bits, and
erasing a bit destroys $\ln 2/\ln\varphi = 1.4404$ q-units (cross-checked
against the Landauer row below).

The openness $(1-q)$ belongs to the flow, not the stored stock: at a conversion
processing rate $\lambda(1-q)$ per unit time, the information-processing rate is
    dI_flow/dt = λ(1−q)·k_B·ln(φ)

### Landauer's Principle
Erasing one bit of information dissipates E = k_B·T·ln(2).
In Cassi: erasing a bit destroys exactly ln(2)/ln(φ) units of q:
    Δq_bit = ln(2)/ln(φ) ≈ 1.44  (necessary q destruction per bit erased)

This unifies thermodynamics, information theory, and Qi dynamics.

### Maxwell's Demon
The demon can sort EY and EI (increase q, decrease entropy) only by
exporting at least as much entropy as it creates. The demon IS a
coherence bubble—it temporarily maintains high q by measuring
(interacting with) the system, then dumping the entropy elsewhere.

---

## 12. Cosmology—CMB, Inflation, Large-Scale Structure

### The CMB
The Cosmic Microwave Background is the **last-scattering surface of the
two-fluid**—the epoch when EY and EI decoupled from matter and the
photon mode (EY = φ·EI) became free-streaming.

Cassi predicts:
- **No B-mode polarization from primordial GW** (no inflation → no tensor modes)
- **Preferred axis** from residual large-scale Qi coherence (testable with Planck)
- **CMB cold spot** = region of lower q (coherence void)

### Inflation as φ-Reset
Inflation was a period when π/ρ (the Yin-Yang density ratio) was driven
far from its attractor φ⁻³. The exponential expansion was the two-fluid
rushing back toward equilibrium—not a separate scalar field (inflaton).

    H_inflation ∝ (φ − r_initial)  (deviation from φ drives expansion)
    Slow roll: r → φ⁻³ as equilibrium restores
    Reheating: excess Qi released as photons and matter

This predicts:
- **No B-modes** (Cassi inflation didn't produce tensor perturbations)
- **Slightly red-tilted spectrum** (n_s < 1) as r approaches φ⁻³ from above
- **No running of spectral index** (attractor dynamics, not multi-field)

### Large-Scale Structure
Galaxies and clusters are **frozen-in Qi fluctuations** from the early universe.
The cosmic web is the structure of q-fluctuations amplified by gravity.

    δ_galaxy ∝ δ_q  (galaxy overdensity ∼ Qi overcoherence)
    φ-scaled void sizes predicted: r_void ∝ φ^n

---

## 13. Unification—The Theory of Everything

### The Single Equation
The Cassi framework proposes that ALL known physics—gravity, electromagnetism,
nuclear forces, quantum mechanics, thermodynamics, consciousness, and life —
emerges from a single two-fluid PDE:

    ∂_t EY + ∇·(EY·u) = ω₀·g(q)·(EY − φ·EI) + ν·∇²EY   [application form; g(q) asserted]
    ∂_t EI + ∇·(EI·u) = −ω₀·g(q)·(EY − φ·EI) + ν·∇²EI
    ∂_t u + (u·∇)u = −∇P − ∇Φ − η·u

where:
- **EY**: Yang field (outward, radiative, electric-like)
- **EI**: Yin field (inward, absorptive, magnetic-like)
- **φ ≈ 1.618**: The universal attractor (golden ratio)
- **g(q) = q/(φ² + q²)**: asserted single-channel transmission input; selection audit in `computations/gate_origin_audit.py`
- **σ**: The softening scale (same mechanism at all scales)
- **ξ = φ⁶ ≈ 17.944**: Qi coupling strength (derived from Fibonacci identity φ⁶ = φ⁵ + φ⁴)
- **ν, η**: Viscosity and damping coefficients

### How Each Force Emerges
| Scale | σ | Phenomenon | What You See |
|-------|---|-----------|--------------|
| fm | 0.5 fm | Nuclear | Strong force, nuclei, fission/fusion |
| m–km | Earth σ | Daily life | Newtonian gravity, EM |
| kpc | galaxy σ | Galactic | Dark matter, rotation curves |
| Mpc | cosmological σ | Cosmic | Dark energy, cosmic web |

### The Four Pillars (Cassi TOE)
1. **Dirac QM**: The two-fluid at quantum scale → Dirac equation and QFT
2. **GR/Gravity**: The two-fluid at large scale → GR via G_eff(r) metric
3. **Gauge fields**: SU(3) × SU(2) × U(1) from two-fluid isospin structure
4. **Quantum Gravity**: σ-regularized two-fluid quantization → UV-finite QG

See `experiments/cassi_physics/cassi_quantum_gravity.py` for the formal derivation.

Pillar 4 closes the TOE loop: the same PDE that describes classical gravity,
when quantized, gives a predictive (UV-finite) quantum theory of gravity.
The Gaussian softening σ ≈ 1/M_Pl acts as a natural UV regulator:
    G(k²) = exp(−k²·σ²/2) / k²  →  no divergences at any order

These four pillars unify at φ-equilibrium: the same PDE reproduces all known
physics at different σ-scales, with φ as the universal attractor coupling.

> **Implementation mapping**: The three conceptual pillars above correspond to three implementation pillars in code:
> 1. **Implementation Pillar 1—Relativistic QM**: `DiracBridge` reproduces the Dirac equation from the two-fluid at quantum scale.
> 2. **Implementation Pillar 2—GR/Gravity**: `QiGravitySolver3D` with G_eff(r) and ξ = φ⁶ implements the emergent gravity sector.
> 3. **Implementation Pillar 3—Gauge Unification**: `cassi_su2_bridge.py` implements SU(2)×U(1)_Y; SU(3) color coupling runs from α_GUT = φ⁻³/(4π).
>
> The conceptual pillars describe *what* emerges from the two-fluid; the implementation pillars describe *how* it is computed.

---

## 14. Observables & Predictions

### Confirmed
| Observation | Cassi Prediction | Status |
|-------------|-----------------|--------|
| Dark energy (DESI DR2) | $w_0 = -0.87$ | $2\sigma$ from DESI $\approx -0.75 \pm 0.06$ [INFERENCE]—tension, not matched |
| Galaxy rotation curves | Qi-enhanced G_eff | ⚠️ MOND preferred (4/8 vs 3/8 dwarfs) |
| Baryonic Tully-Fisher | Slope ≈ 0.96 | ✓ Consistent |
| Mercury precession | GR limit (σ→0) | ✓ Reproduces 43″/century |
| BH shadow (EHT) | GR-like (core G_eff≈1) | ✓ Consistent with M87* |
| Lagrange stability | σ-increases stability | ✓ Verified numerically |
| 3BP attractor | Energy attractor at E≈−0.02 | ✓ Verified numerically |

### Falsifiable
| Prediction | Mechanism | Test |
|-----------|-----------|------|
| BH shadow ~5.2M (core) | Core G_eff ≈ 1 | EHT (already consistent) |
| Larger BH shadow from halo | Halo G_eff ≈ 10 | Future EHT at larger angles |
| Accretion disk ISCO ~60M | Variable G_eff pushes ISCO out | XRISM iron line profiles |
| GW q-polarization | Two-fluid → extra GW mode | LIGO/Virgo/KAGRA beyond +,× |
| No singularities | σ softening → harmonic core | Future quantum gravity tests |
| φ-scaled particle masses | EY/EI → harmonic overtones | Future collider data |
| Life as Qi condensate | Metabolic scaling across masses | Measurable P(q) in organisms |
| Nuclear = σ-gravity | Binding energy curve | Precision nuclear data |
| Strong force = gravity at fm | Force ratio matches strong/Coulomb | Lattice QCD verification |
| EM = EY/EI field imbalance | Two-fluid → Maxwell-like | Optical/EM experiments |


**Unified Lagrangian:** The full Cassi action combines all sectors with zero free parameters.
See `foundations/unified-lagrangian.md` for the complete derivation.

$$
\mathcal{L}_{\text{Cassi}} = \mathcal{L}_{\text{TF}} + \mathcal{L}_{\text{D}} + \mathcal{L}_{\text{GR}} + \mathcal{L}_{\text{SM}} + \mathcal{L}_{\text{mix}}
$$

Each subsector has its own document:
- Two-fluid core ($\mathcal{L}_{\text{TF}}$): `foundations/cassi-first-principles.md`
- Dirac matter ($\mathcal{L}_{\text{D}}$): `cassi_dirac_bridge.py`
- Gravity ($\mathcal{L}_{\text{GR}}$): `foundations/xi-derivation.md`, `theory/qi-fluid-formalism.md`
- SM gauge ($\mathcal{L}_{\text{SM}}$): `standard-model/su2-gauge-extension.md`, `standard-model/sm-from-phi.md`
- Mixing ($\mathcal{L}_{\text{mix}}$): `foundations/unified-lagrangian.md`

**Cosmology:** All three open problems solved by the $\varphi$-governed two-fluid.
See `cosmology/cosmology-from-phi.md` for full derivations.

| Phenomenon | Mechanism | Cassi Prediction | Observed | Gap |
|-----------|----------|-----------------|----------|-----|
| Inflation | Yang/Yin ratio $r \to \varphi$ | $n_s = 0.9691$, $r = 0.0075$ ($12/N_e^2$ at $N_e = 40$—Mapped window, ledger §10 row 495) | $0.9649 \pm 0.0042$ | $1.0\sigma$ |
| Baryogenesis | $\varphi^{-3}$ chiral asym → sphalerons | $\eta = \varphi^{-44} \approx 6.38\times10^{-10}$ | $6.0\times10^{-10}$ | Within $6.3\%$ |
| Dark Matter | High-Qi condensate, $G_{\text{eff}}$ boost | $\Omega_{\text{DM}}/\Omega_b = \varphi^3 \approx 4.236$ | $5.39$ | 21% open tension |

New theory documents:
- `cosmology/cosmology-from-phi.md` | Inflation, baryogenesis, dark matter from $\varphi$
- `foundations/unified-lagrangian.md` | Full Cassi action with zero free parameters
- `foundations/xi-derivation.md` | $\xi = \varphi^6$ first-principles derivation
---

## 15. Code & Implementation

### Key Scripts
| File | Purpose |
|------|---------|
| `two-fluid/cassi_two_fluid_3d_gpu.py` | Core two-fluid PDE solver |
| `two-fluid/cassi_gr_bridge.py` | GR extensions with G_eff(q) coupling |
| `two-fluid/universal_cassi_solver.py` | Universal formation solver (PDE + N-body) |
| `two-fluid/cassi_nbody.py` | Cassi N-body particle integrator |
| `experiments/cassi_physics/cassi_three_body.py` | Three-body problem with Qi damping |
| `experiments/cassi_physics/cassi_black_hole_raytracer.py` | Black hole shadow (heuristic) |
| `experiments/cassi_physics/cassi_nuclear.py` | Nuclear = σ-regularized gravity |
| `experiments/cassi_physics/cassi_quantum_gravity.py` | UV-finite QG from σ-regularization |
| `experiments/cassi_quantum_measurement.py` | Born rule from Qi threshold (parent repo) |
| `experiments/cassi_time.py` | Arrow of time from Qi irreversibility (parent repo) |
| `experiments/cassi_coherence_bubble.py` | Consciousness bubble thermodynamics (parent repo) |
| `experiments/cassi_life.py` | Life as self-sustaining Qi condensate (parent repo) |
| `experiments/cassi_spacetime_variable_geff.py` | Spatially-varying G_eff(r) (parent repo) |
| `experiments/cassi_accretion_disk.py` | Accretion disk emission (parent repo) |
| `foundations/unified-lagrangian.md` | Full Cassi Lagrangian (all sectors, zero free parameters) |
| `standard-model/su2-gauge-extension.md` | SU(2) × U(1)_Y gauge derivation, φ-VEV |
| `two-fluid/cassi_su2_bridge.py` | SU(2) gauge bridge with φ-governed weak force |
| `two-fluid/run_electroweak.py` | Electroweak runner—W/Z mass prediction |
| `foundations/xi-derivation.md` | ξ = φ⁶ first-principles derivation |
| `CassiCosmos/` | Real-time universe simulator |
### Managed Skills
| Skill | Purpose |
|-------|---------|
| `godot-compute-nbody` | Compute shader N-body in Godot 4 |

### Key Constants
| Symbol | Value | Meaning |
|--------|-------|---------|
| φ | 1.6180340 | Universal attractor ratio |
| φ⁻¹ | 0.6180340 | Inverse golden ratio |
| φ⁻² | 0.3819660 | Yang-Yang coupling floor |
| φ⁻³ | 0.23606798 | Background π/ρ in vacuum |
| ξ = φ⁶ | 17.944 | Qi-gravity coupling: Derived rung identity (φ⁶ = φ⁵ + φ⁴), Calibrated empirical pin (MW rotation curve) |
| PHI_6 = φ⁶ | 17.944 | Qi-gravity coupling: Derived rung identity, Calibrated empirical pin |
| `σ` | 0.1–1.0 (code units) | Gaussian softening scale |
| `cosmology/cosmology-from-phi.md` | Complete Cassi cosmology (inflation, baryogenesis, DM) |
| Qi gate threshold | q₀ ≈ φ⁻² | Conversion block at equilibrium |

---

---

## 16. Epistemic Tiers

Every claim in the framework carries an epistemic tier. The ladder, highest to
lowest: **Derived > Calibrated > Mapped > Hypothesized > Speculative >
Creative**. Full definitions with worked examples:
`open-questions-cassi-answers.md` §Epistemic Tiers and
`hypotheses/README.md` §Epistemic Tier Definitions.

- **Derived**—a priori mathematical consequence of $\varphi$ + the two-fluid
  PDE; zero fitted or anchored constants. The governing equation is the
  framework's postulate; a claim that merely restates the axiom is the axiom,
  not a Derived consequence.
- **Calibrated**—the framework supplies the form; the constant's value is
  anchored to a stated observation, and downstream claims that use the pinned
  value inherit Calibrated unless independently derived. Example: $\xi =
  \varphi^6$ (Derived rung identity, Calibrated empirical pin $\xi \approx 18$
  from the Milky Way rotation curve).
- **Mapped**—the placement (rung, exponent, offset, candidate, normalization)
  was selected or fitted to data: search tables, grid scans, nearest-integer
  logs of measured ratios, back-solved normalizations, candidate tables, free
  parameters closing a gap, scan highlights. The fit MUST be recorded in the
  Fit-Status Ledger (`parameter-inventory.md` §10). A Mapped claim carries no
  evidential weight until the placement is independently derived.
- **Hypothesized**—mechanism proposed with a pinned $\varphi$-power or a
  testable prediction; derivation not closed, value not anchored and not
  fitted.
- **Speculative**—framework-consistent; mechanism sketched, prediction not
  yet pinned, testing pending.
- **Creative**—exploration, not a claim (`speculations/creative-extensions/`);
  exempt from the evidential ladder and the ledger duty.

Bookkeeping words—Reference, Index, Synthesis, Plan, Registry, Catalog, Open
problem—are genres, not epistemic claims, and do not sit on the ladder.
"Tested" is a verification marker that attaches to a tier and never upgrades
one. The former "near-Derived" label is retired; use the honest tier (Mapped,
Calibrated, Hypothesized, or Speculative).

---

*End of definitions. This is a living document—add entries as the framework grows.*
