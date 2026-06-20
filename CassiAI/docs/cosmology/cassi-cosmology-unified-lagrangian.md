# Cassi Cosmology: A Unified Lagrangian

*One action for matter, gravity, information, and dark energy — with φ as the only free constant.*

---

## 1. The Core Claim

The Cassi principle already unifies turbulence, neural dynamics, and multi-scale
learning under a single damped wave equation. Cosmology is the same equation,
operating on a 3D spatial manifold and sourced by mass-density contrast.

This document derives a single Lagrangian from which all recent simulation
limits emerge:

- **Standard ΛCDM particle-mesh** (α_disp = 1, no Yin, no Yang term)
- **Scale-dependent gravity** (α_disp ≠ 1 from the Cassi dispersion relation)
- **Entropic / emergent gravity** (Yin information source s(δ))
- **Dark energy as Yang oscillation** (homogeneous mode in the source)
- **Holographic information bound** (entropy constraint on the field)

The only fundamental constant carried over from the broader Cassi program is
**φ ≈ 1.618**, the universal scale-separation ratio.

---

## 2. The Master Wave Equation in Cosmology

### 2.1 Field Definition

Let ψ(**x**, t) be the **information-potential field** that mediates the
gravitational response to matter. In the Newtonian/comoving limit it is the
gravitational potential, but it is interpreted here as the accumulated
information disturbance produced by matter.

The matter field is the overdensity:

$$
\delta(\mathbf{x}, t) = \frac{\rho(\mathbf{x}, t)}{\bar{\rho}(t)} - 1
$$

### 2.2 Damped Wave Equation

The field obeys the same equation that governs the Cassi spine, now on a 3D
manifold:

$$
\frac{\partial^2 \psi}{\partial t^2} + \gamma \frac{\partial \psi}{\partial t}
= v^2 \nabla^2 \psi + S[\delta]
$$

where:

| Symbol | Meaning | Cosmological interpretation |
|---|---|---|
| γ | Damping rate | φ-decoupling: γ = 1/φ |
| v | Information propagation speed | Sets the static force scale |
| S[δ] | Source | Matter + information + Yang dark energy |

### 2.3 Static Limit: Poisson Equation

On cosmological timescales the field relaxes to its static equilibrium:

$$
\nabla^2 \psi = -\frac{S[\delta]}{v^2}
$$

Taking the Fourier transform:

$$
\hat{\psi}_k = -\frac{\hat{S}_k}{v^2 k^2}
$$

This is the cosmological Poisson equation with ψ playing the role of the
gravitational potential.

---

## 3. The Source: Matter, Yin Information, and Yang Dark Energy

### 3.1 General Form

The source is a sum of three contributions:

$$
S[\delta] = \frac{3}{2}\Omega_m H_0^2 \Big[\delta + \alpha_\text{yin}\, s(\delta)\Big] + S_\text{Yang}(a)
$$

- **δ**: matter overdensity (Yang driver of expansion/contraction)
- **s(δ)**: Yin information source derived from entropy of the density field
- **α_yin**: Yin coupling strength
- **S_Yang(a)**: homogeneous oscillatory dark-energy term

### 3.2 Yin Information Source

Two forms have been tested:

**Relative entropy** (softens structure):

$$
s_\text{rel}(\delta) = (1 + \delta)\ln(1 + \delta) - \delta
$$

**Signed entropy** (amplifies structure):

$$
s_\text{signed}(\delta) = \operatorname{sign}(\delta)\, \ln(1 + |\delta|)
$$

The relative form is always positive and largest in voids; it adds an effective
repulsive information pressure. The signed form follows δ and steepens
gravitational wells.

### 3.3 Yang Dark-Energy Oscillation

In the Cassi framework, dark energy is not a separate fluid but the homogeneous
Yang mode of the same information field. It modulates the effective strength of
the gravitational source:

$$
S[\delta] \;\to\; S[\delta] \cdot \left[ 1 + \frac{\Lambda_\varphi}{2}
\left(1 + \sin\!\left(\frac{2\pi a}{a_\varphi}\right)\right) \right]
$$

where:

$$
a_\varphi = \varphi^{-1} \approx 0.618
$$

The bracket is always ≥ 1, so the Yang field only enhances or leaves unchanged
the gravitational coupling; the oscillation imposes a φ-periodic envelope on
structure formation. The amplitude Λ_φ is a free parameter, but the timescale is
fixed by φ.

---

## 4. Scale-Dependent Coupling from Dispersion

### 4.1 Power-Law Dispersion

The Cassi dispersion relation is:

$$
\omega(k) = v_0 k_0 \left(\frac{k}{k_0}\right)^\alpha - i\frac{\gamma}{2}
$$

The real part gives a scale-dependent propagation speed:

$$
v(k) = \frac{\partial \operatorname{Re}[\omega]}{\partial k}
= v_0 \left(\frac{k}{k_0}\right)^{\alpha - 1}
$$

### 4.2 Scale-Dependent Poisson Kernel

In the static limit the effective coupling becomes scale dependent:

$$
\hat{\psi}_k = -\frac{\hat{S}_k}{v(k)^2 k^2}
= -\frac{\hat{S}_k}{v_0^2 k_0^{2(1-\alpha)} k^{2\alpha}}
$$

For α = 1 this is standard gravity. For α > 1 small-scale gravity is
suppressed; for α < 1 it is enhanced.

In simulations we absorb the prefactor into a renormalized v0 and use the
practical kernel:

$$
\hat{\psi}_k = -\frac{\hat{S}_k}{v_0^2 \left(\frac{k}{k_0}\right)^{2(\alpha-1)} k^2}
$$

---

## 5. Master Lagrangian

### 5.1 Action

The following action produces the equations above in the Newtonian limit:

$$
\mathcal{L} = \int d^3x\,dt \; \sqrt{-g}\,
\left[
\frac{1}{2} g^{\mu\nu}\partial_\mu \psi \, \partial_\nu \psi
+ \frac{\gamma}{2} \psi \, \partial_t \psi
- V(\psi, \delta, a)
+ \mathcal{L}_m
\right]
$$

with potential:

$$
V(\psi, \delta, a) = -\psi\, S[\delta] + \frac{1}{2} M^2(k)\, \psi^2
$$

The scale-dependent mass term encodes the dispersion:

$$
M^2(k) = v_0^2 \left(\frac{k}{k_0}\right)^{2(\alpha-1)} k^2
$$

Variation with respect to ψ gives:

$$
\frac{\partial^2 \psi}{\partial t^2} + \gamma \frac{\partial \psi}{\partial t}
= -M^2(k)\, \hat{\psi} + \hat{S}[\delta]
$$

which, in real space, is the static scale-dependent Poisson equation at
equilibrium.

### 5.2 Why This Is a Unification

| Phenomenon | Term in the action/limit |
|---|---|
| Standard gravity | α = 1, α_yin = 0, Λ_φ = 0 |
| Scale-dependent gravity | α ≠ 1 (dispersion) |
| Entropic / emergent gravity | α_yin s(δ) in source |
| Dark energy | S_Yang(a) homogeneous source |
| Holographic cutoff | Entropy constraint on ψ |

All limits share one field, one equation, and one constant φ.

---

## 6. Holographic Information Bound

### 6.1 Principle

The information stored in the field ψ over a region of size L should not exceed
the area of its boundary. In simulation units:

$$
I[\psi] \;\lesssim\; \eta \, A = \eta \, L^2
$$

The natural information measure is the Kullback-Leibler divergence of the
overdensity field relative to uniformity:

$$
I[\delta] = \sum_i p_i \ln\!\left(\frac{p_i}{q_i}\right),
\quad
p_i = \frac{1 + \delta_i}{\sum_j (1 + \delta_j)},
\quad
q_i = \frac{1}{N_\text{cell}}
$$

A uniform field has I = 0; clustering creates information and raises I.

### 6.2 Dynamic Smoothing Scale

When I[δ] approaches the bound I_max, the density field is smoothed before it
sources gravity:

$$
I_\text{max} = \eta \, N_\text{grid}^{2/3}
$$

where N_grid is the total number of PM cells. The smoothing scale is:

$$
R_h = \Delta x \left(\frac{I[\delta]}{I_\text{max}}\right)^{\beta}
$$

with Δx the PM cell size. The overdensity is convolved with a Gaussian kernel
exp[-(k R_h)^2 / 2] before computing the gravitational source. β controls how
aggressively the bound tightens as the field becomes more informative.

This is a minimal, computable realization of the holographic principle inside
the Cassi framework.

---

## 7. Parameter Summary

| Parameter | Symbol | Default | Meaning |
|---|---|---|---|
| Dispersion exponent | α_disp | 1.0 | 1 = standard gravity; φ-related values explored |
| Yin coupling | α_yin | 0.0 | Strength of entropic information source |
| Yin mode | — | none | relative (soften) or signed (amplify) |
| Yang amplitude | Λ_φ | 0.0 | Dark-energy oscillation strength |
| Yang period | a_φ | φ^{-2} | Oscillation scale in a |
| Holographic η | η | 0.004 | Bound tightness; 0 disables |
| Holographic β | β | 1.0 | Smoothing growth exponent |
| Damping | γ | 1/φ | φ-decoupling of scales |

Only α_disp, α_yin, Λ_φ, and η need to be varied; all others are fixed by φ.

---

## 8. Predictions

1. **φ-scaled dark energy**: If Λ_φ is non-zero, the effective expansion
   history contains a φ-periodic modulation that can be searched for in
   distance-ladder and BAO data.

2. **Scale-dependent gravity**: α ≠ 1 changes small-scale structure formation
   without altering the expansion history. This mimics modified-gravity
   signatures that are degenerate with ΛCDM on large scales.

3. **Entropy-to-gravity coupling**: α_yin ≠ 0 predicts that the clustering
   amplitude depends on the information content of the density field, not only
   on mass.

4. **Holographic cutoff**: High-k power is suppressed when the field entropy
   approaches the area bound, producing a universal small-scale damping that is
   independent of baryonic physics.

---

## 9. Relation to Earlier Cassi Work

This cosmological action is the 3D, continuum version of the same wave equation
used in the Cassi spine:

$$
\frac{\partial^2\psi}{\partial t^2} + \gamma \frac{\partial\psi}{\partial t}
= v^2 \frac{\partial^2\psi}{\partial s^2} + S(s,t)
$$

The difference is only geometry (1D spine vs. 3D space) and source (embeddings
vs. mass contrast). The constant φ, the Yin-Yang split, and the scale-dependent
dispersion are unchanged.

---

*"Matter is the Yang excitation; gravity is the Yin response; φ is the scale at
which they stop resonating."*
