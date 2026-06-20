# Cassi Two-Fluid Bridge: Incompressible Yang and Yin

*A simpler, fluid-dynamic picture of the Cassi bridge: two incompressible energy
fields that convert into each other and generate structure through their
opposite buoyancy in a shared information potential.*

---

## 1. The simplification

The Schrödinger–Poisson bridge is exact and single-field, but it carries a lot
of phase information. A coarser, more tractable description is to split the
energy density directly into two interacting fluids:

| Fluid | Symbol | Role |
|---|---|---|
| Yang | $E_Y(\mathbf{x},t)$ | expansive, entropy-producing, outward-pushing |
| Yin | $E_I(\mathbf{x},t)$ | contractive, structure-forming, inward-pulling |

Instead of a complex wavefunction we now have two real scalar densities. Their
coupling is carried by the same information potential that appears in the
bridge Lagrangian.

---

## 2. Field definitions

Total density and Yang-Yin pressure:

$$
\rho = E_Y + E_I,
\qquad
\Pi = E_Y - E_I.
$$

The information potential is the Poisson response to the total density:

$$
\nabla^2 \Phi = \rho - \bar\rho.
$$

Overdensities ($\rho > \bar\rho$) produce $\Phi < 0$ — a potential well.

---

## 3. Incompressible fluid equations

A single incompressible velocity field $\mathbf{u}$ advects both fluids:

$$
\nabla\cdot\mathbf{u} = 0.
$$

The momentum equation is driven by the Yang-Yin pressure gradient in the
information potential:

$$
\partial_t \mathbf{u} + (\mathbf{u}\cdot\nabla)\mathbf{u}
= -\nabla p + \nu\nabla^2\mathbf{u} + \Pi\,\nabla\Phi .
$$

The force term $\Pi\,\nabla\Phi$ is non-conservative in general: where Yang
($\Pi>0$) sits on a slope of $\Phi$, it is pushed toward lower density; where
Yin ($\Pi<0$) sits on the same slope, it is pulled toward higher density. This
creates vorticity and mixing.

In 2D the natural form is vorticity–streamfunction:

$$
\omega = \hat z\cdot(\nabla\times\mathbf{u}),
\qquad
\nabla^2\psi = -\omega,
\qquad
\mathbf{u}=(-\partial_y\psi,\;\partial_x\psi),
$$

and the vorticity equation becomes

$$
\partial_t \omega + (\mathbf{u}\cdot\nabla)\omega
= \nu\nabla^2\omega + J(\Pi,\Phi),
$$

where

$$
J(\Pi,\Phi)=\partial_x\Pi\,\partial_y\Phi-\partial_y\Pi\,\partial_x\Phi
$$

is the Jacobian of the Yang-Yin pressure against the information potential.

---

## 4. Yang–Yin conversion

The two fluids convert into each other, conserving total energy:

$$
\partial_t E_Y + \mathbf{u}\cdot\nabla E_Y
= D\nabla^2 E_Y - \lambda\,(E_Y - \varphi E_I),
$$

$$
\partial_t E_I + \mathbf{u}\cdot\nabla E_I
= D\nabla^2 E_I + \lambda\,(E_Y - \varphi E_I).
$$

The source term drives the local ratio toward the golden-ratio equilibrium:

$$
\frac{E_I}{E_Y} \to \varphi^{-1} \approx 0.618.
$$

This is the same stability condition that selected the optimal soliton in the
Yang-Yin particle framework.

---

## 5. Relation to the Schrödinger–Poisson bridge

| Schrödinger–Poisson | Two-fluid limit |
|---|---|
| $|\Psi|^2$ | $\rho = E_Y+E_I$ |
| phase of $\Psi$ | incompressible velocity $\mathbf{u}$ |
| quantum pressure $-\nabla^2/(2M)$ | viscous diffusion $\nu\nabla^2\mathbf{u}$ |
| Coulomb/gravitational potential | information potential $\Phi$ |
| Yin source $s(\rho)$ | conversion term $\lambda(E_Y-\varphi E_I)$ |
| Yang oscillation | time-dependent modulation of $\lambda$ or $\nu$ |

The two-fluid model is the **hydrodynamic limit** of the bridge: it keeps the
energy and momentum dynamics but discards the fine quantum phase.

---

## 6. What it predicts

1. **Spontaneous circulation**: $J(\Pi,\Phi)$ creates vorticity wherever Yang
   and Yin gradients are misaligned with the information field.
2. **Golden-ratio mixing**: conversion relaxes patches to
   $E_I/E_Y\approx\varphi^{-1}$, producing the same contrast ratio seen in the
   soliton analysis.
3. **Structure from two fluids**: knots of Yin collapse while Yang fills voids,
   analogous to cosmic web formation or electron-proton binding viewed as a
   fluid separation instability.

---

## 7. Implementation

`experiments/cassi_two_fluid.py` solves the 2D vorticity–streamfunction system
with a Fourier pseudospectral RK4 method. Default parameters:

| Parameter | Value |
|---|---|
| Grid | 128² |
| Domain | $[0, 2\pi]^2$ |
| Viscosity $\nu$ | 0.0002 |
| Diffusivity $D$ | 0.0002 |
| Conversion rate $\lambda$ | 0.02 |

The demo initializes $E_Y$ with an $x$-dependent sine wave and $E_I$ with a
$y$-dependent sine wave, so that $\nabla\Pi$ and $\nabla\Phi$ are misaligned.
The resulting $J(\Pi,\Phi)$ generates vorticity, and the conversion term keeps
the mean ratio locked to $\langle E_I\rangle/\langle E_Y\rangle\approx\varphi^{-1}$.

Outputs:

- `docs/figures/cassi_two_fluid_fields.png`
- `docs/figures/cassi_two_fluid_timeseries.png`
- `docs/cassi-two-fluid-results.md`

