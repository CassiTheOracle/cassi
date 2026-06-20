# Cassi Cosmology: Deriving Entropic Gravity from the Master Wave Equation

*A first-principles connection between the Cassi spine-wave framework and the cosmological particle-mesh simulations.*

---

## 1. The Cassi Master Wave Equation

The Cassi mathematics document proposes that all multi-scale dynamics on the
one-dimensional **spine** are governed by a single damped wave equation:

$$
\frac{\partial^2 \psi}{\partial t^2}
+ \gamma \frac{\partial \psi}{\partial t}
= v^2 \frac{\partial^2 \psi}{\partial s^2}
+ \chi \frac{\partial \psi}{\partial s}
+ S(s,t)
$$

where:

- $\psi(s,t)$ is the complex wave amplitude of the information field,
- $\gamma$ is a universal damping coefficient,
- $v$ is the information propagation speed,
- $\chi$ is a chirality/twist term,
- $S(s,t)$ is the source.

The spine is not meant to be a physical spatial dimension in the ordinary
sense; it is an **information manifold** whose oscillations encode the state of
a multi-scale system. Different physical systems correspond to different
sources $S$ and different effective dimensions, but the equation itself is
universal.

---

## 2. From the Spine to Three-Dimensional Space

For cosmology we promote the spine to the three-dimensional comoving space of
the universe. The second-order spatial derivative becomes the Laplacian, and
the chirality term drops out for an isotropic cosmological field:

$$
\frac{\partial^2 \psi}{\partial t^2}
+ \gamma \frac{\partial \psi}{\partial t}
= v^2 \nabla^2 \psi
+ S(\mathbf{x},t)
$$

We now identify $\psi(\mathbf{x},t)$ with the **gravitational-information
potential**. In standard gravity this potential is usually denoted $\Phi$ and
satisfies the Poisson equation. The Cassi framework says that $\psi$ is not an
instantaneous constraint but a dynamical field that relaxes to equilibrium under
damping and wave propagation.

---

## 3. The Static Limit: Recovering a Poisson Equation

Cosmological structure formation is much slower than the relaxation time of the
information field. We are therefore interested in the **quasi-static limit**
where time derivatives are negligible:

$$
\frac{\partial \psi}{\partial t} \approx 0,
\qquad
\frac{\partial^2 \psi}{\partial t^2} \approx 0
$$

The master wave equation collapses to:

$$
0 = v^2 \nabla^2 \psi + S(\mathbf{x})
\quad \Longrightarrow \quad
\nabla^2 \psi = -\frac{S(\mathbf{x})}{v^2}
$$

This is a Poisson equation. The gravitational acceleration felt by matter is
the gradient of the potential:

$$
\mathbf{a} = -\nabla \psi
$$

So **gravity emerges as the static equilibrium of the Cassi information field**,
exactly in the spirit of Verlinde-style entropic gravity, but now derived from
a concrete dynamical equation rather than a thermodynamic argument.

---

## 4. The Source: Yang (Matter) and Yin (Information)

In the Cassi framework every system has two opposing forces:

| Force | Direction | Cosmological role |
|---|---|---|
| **Yang** | Expansion / outward | Tends to disperse structure; in gravity it appears as the inertial/expansion tendency of the background |
| **Yin** | Contraction / inward | Tends to pull matter together; here it is the information-density gradient that drives collapse |

For cosmology we split the source into a Yang part and a Yin part:

$$
S(\mathbf{x}) = S_\text{Yang}(\mathbf{x}) + S_\text{Yin}(\mathbf{x})
$$

The Yang source is simply the mass overdensity:

$$
S_\text{Yang}(\mathbf{x}) = \frac{3}{2}\Omega_m \, \delta(\mathbf{x})
$$

This is the standard source term in comoving particle-mesh cosmology.

The Yin source is an **information density** built from the overdensity field.
Two prescriptions have been explored:

**Relative entropy (Yin as smoothing):**

$$
s_\text{rel}(\delta) = (1+\delta)\log(1+\delta) - \delta
$$

This function is convex and positive everywhere. It measures how much the local
density distribution deviates from uniformity. When added to the source it acts
like an effective pressure that reduces contrast between voids and knots.

**Signed entropy (Yin as amplification):**

$$
s_\text{sgn}(\delta) = \operatorname{sign}(\delta) \, \log(1+|\delta|)
$$

This function preserves the sign of the overdensity. It reinforces both
overdensities and underdensities, sharpening structure rather than smoothing
it.

The full source is then:

$$
S(\mathbf{x}) = \frac{3}{2}\Omega_m \left[ \delta(\mathbf{x}) + \alpha \, s(\delta(\mathbf{x})) \right]
$$

where $\alpha$ is the **Yin coupling strength**. Setting $\alpha = 0$ recovers
standard gravity. The static field equation becomes:

$$
\nabla^2 \psi = -\frac{3}{2}\Omega_m \, \frac{\delta + \alpha \, s(\delta)}{v^2}
$$

In code units we choose $v^2 = 1$, so the equation reduces to the entropic
Poisson equation used in the simulations.

---

## 5. The Role of $\varphi$

The golden ratio appears in three distinct ways:

1. **Damping rate.** The universal damping coefficient is taken to be:

   $$
   \gamma = \varphi^{-1} \approx 0.618
   $$

   This guarantees maximally aperiodic relaxation: no rational frequency can
   resonate with the damping kernel.

2. **Scale separation.** The continuous $k$-space is sampled into
   $\varphi$-spaced shells. Power and information are tracked shell by shell,
   naturally separating linear, quasi-linear, and nonlinear regimes.

3. **Yang-Yin asymmetry.** The relative magnitude of Yang and Yin is tuned by
   $\alpha$. The Cassi principle suggests that equilibrium occurs when Yang
   exceeds Yin by a factor of order $\varphi$, not when they are exactly equal.

---

## 6. Numerical Realization: Damped-Wave Relaxation

Rather than solving the static equation directly, the simulation explicitly
relaxes the information field using the damped wave equation. In Fourier space
each mode obeys:

$$
\frac{\partial^2 \hat{\psi}_k}{\partial t^2}
+ \gamma \frac{\partial \hat{\psi}_k}{\partial t}
+ v^2 k^2 \hat{\psi}_k
= \hat{S}_k
$$

This is the equation of a driven, damped harmonic oscillator. Each mode has a
natural frequency $\omega_k = v k$ and decays at rate $\gamma$. The steady-state
solution is:

$$
\hat{\psi}_k^{(\text{eq})} = \frac{\hat{S}_k}{v^2 k^2}
$$

which is exactly the Fourier-space Poisson solve.

In the simulation the field is updated through a short relaxation interval at
every cosmological step. Because the density field evolves slowly compared with
the field relaxation time, the potential remains close to its instantaneous
equilibrium. Using the previous step's field as the initial condition makes the
relaxation cheap and physically meaningful: the information field has a
memory, but it is a $\varphi$-damped memory.

---

## 7. Summary

The entropic gravity simulations are not an ad hoc modification of Newtonian
cosmology. Within the Cassi framework they are the **static limit of a single
master wave equation** acting on a three-dimensional information manifold. The
source is split into a Yang (matter) part and a Yin (information) part. The
relative and signed entropy prescriptions correspond to two different Yin
characters: one that spreads information and softens structure, and one that
concentrates information and amplifies structure.

This gives a concrete, numerically testable answer to the question: *What would
gravity look like if it were an information-structuring process governed by
Yang-Yang dynamics with $\varphi$-scale separation?*
