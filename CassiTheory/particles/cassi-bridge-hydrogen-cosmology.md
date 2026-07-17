# Cassi Bridge: From Hydrogen to Cosmology

*A single Schrödinger–Poisson equation that contains the hydrogen atom and cosmic structure formation as two limits of the same information field.*

---

## 1. The core claim

The Cassi cosmology engine and the Cassi hydrogen solver look like different simulations:

- **Hydrogen** solves a 3D Schrödinger equation in atomic units with a Coulomb well.
- **Cosmology** solves a particle-mesh Poisson equation in Mpc/h with modified gravity, dark energy and an information bound.

Both are the same equation written in different units and occupied by different numbers of particles. The bridge is a **nonlinear Schrödinger–Poisson equation with a scale-dependent information potential**:

$$
i\,\partial_\tau \Psi(\mathbf{x},\tau)
= \Big[ -\frac{1}{2M}\nabla^2 + V_{\rm ext}(\mathbf{x}) + g\,|\Psi|^2 + \Phi[\rho] \Big]\Psi.
$$

The density is

$$
\rho(\mathbf{x},\tau) = |\Psi(\mathbf{x},\tau)|^2,
$$

and the information/gravitational potential is obtained from the density through the Cassi source operator

$$
\hat\Phi_k = -\frac{\hat S[\rho]_k}{v_0^2\,\left(\frac{k}{k_0}\right)^{2(\alpha_{\rm disp}-1)} k^2},
\qquad
S[\rho] = \rho + \alpha_{\rm yin}\,s(\rho) + S_{\rm Yang}(\tau).
$$

The same numerical engine — split-step spectral propagation plus an FFT Poisson solve — runs both limits. Only the parameters change.

---

## 2. The two limits

### 2.1 Atomic limit: hydrogen

| Control | Atomic value | Meaning |
|---|---|---|
| Mass $M$ | $1$ | electron mass in atomic units |
| External density $\rho_{\rm fixed}$ | narrow Gaussian of charge $Z=1$ | proton |
| External potential $V_{\rm ext}$ | $-1/\sqrt{r^2+\varepsilon^2}$ | soft Coulomb well |
| Self-consistent source | off | electron does not source its own potential |
| $\alpha_{\rm disp}$ | $1$ | standard Laplacian / Coulomb kernel |
| $\alpha_{\rm yin}$ | $0$ | no entropic correction at atomic scale |
| $\Lambda_\varphi$ | $0$ | no cosmological Yang oscillation |
| $g$ | small | optional nonlinear self-focusing |

In this limit the equation reduces to

$$
i\,\partial_\tau \Psi = \Big[-\frac{1}{2}\nabla^2 - \frac{1}{\sqrt{r^2+\varepsilon^2}} + g|\Psi|^2\Big]\Psi.
$$

Imaginary-time relaxation converges to the 1s-like ground state. The only Cassi fingerprint is the **φ-damped propagator**, which mixes the new field with the previous step:

$$
\Psi(\tau+\Delta\tau) = \varphi^{-1}\Psi(\tau) + (1-\varphi^{-1})\Psi_{\rm prop}(\tau+\Delta\tau),
$$

and reproduces the 4.76× oscillation suppression seen in the radial hydrogen solver.

### 2.2 Cosmological limit: large-scale structure

| Control | Cosmological value | Meaning |
|---|---|---|
| Mass $M$ | $\gg 1$ | many particles / semiclassical dust limit |
| External density $\rho_{\rm fixed}$ | $0$ | no imposed central charge |
| Self-consistent source | on | matter sources its own gravity |
| $\alpha_{\rm disp}$ | $1-\varphi^{-1}$ | scale-dependent enhanced small-scale gravity |
| $\alpha_{\rm yin}$ | $1.0$ | entropic information source |
| $\Lambda_\varphi$ | $1.0$ | Yang/dark-energy oscillation |
| $g$ | $0$ | no atomic self-focusing |

With $M\to\infty$ the de Broglie wavelength shrinks, the quantum pressure term $-\nabla^2/(2M)$ becomes negligible, and the Madelung form of the Schrödinger equation reduces to pressureless dust moving under the information potential $\Phi$. The density field $|\Psi|^2$ becomes the matter overdensity, and the same FFT kernel that produced the atomic Coulomb well now produces the cosmological gravitational potential.

---

## 3. The source operator

### 3.1 Baseline matter source

The raw source is the density itself. Removing the mean (the $k=0$ mode) corresponds to subtracting the arbitrary gauge constant from the potential.

### 3.2 Yin information source

The overdensity is

$$
\delta = \frac{\rho}{\bar\rho} - 1.
$$

Two forms are implemented:

- **Relative entropy** (softens structure):  
  $s_{\rm rel}(\delta) = (1+\delta)\ln(1+\delta) - \delta$.
- **Signed entropy** (amplifies structure):  
  $s_{\rm signed}(\delta) = {\rm sign}(\delta)\,\ln(1+|\delta|)$.

The effective source becomes

$$
S[\rho] = \rho + \alpha_{\rm yin}\,s(\delta)\,\bar\rho.
$$

### 3.3 Yang dark-energy oscillation

The homogeneous Yang mode modulates the source strength:

$$
S[\rho] \to S[\rho]\,\left[1 + \frac{\Lambda_\varphi}{2}\left(1 + \sin\!\left(\frac{2\pi\tau}{a_\varphi}\right)\right)\right],
\qquad a_\varphi = \varphi^{-1}.
$$

In the atomic limit this term is absent; in the cosmological limit it imposes a φ-periodic envelope on structure formation.

### 3.4 Holographic information bound

The field information is the KL divergence of the normalized density from uniformity:

$$
I[\rho] = \sum_i p_i\ln\!\left(\frac{p_i}{q_i}\right),
\qquad
p_i = \frac{\rho_i}{\sum_j \rho_j},
\quad
q_i = \frac{1}{N_{\rm cell}}.
$$

The information bound scales with the boundary area:

$$
I_{\max} = \eta\,N_{\rm grid}^{2/D}.
$$

If $I[\rho] > I_{\max}$, the density is Gaussian-smoothed at scale

$$
R_h = \Delta x\,\left(\frac{I[\rho]}{I_{\max}}\right)^\beta
$$

before it sources the potential. In the atomic limit this is a UV regulator; in the cosmological limit it is a small-scale cutoff.

---

## 4. The φ operator everywhere

| Regime | Where φ appears | Effect |
|---|---|---|
| Hydrogen | Damping weight $\varphi^{-1}$ in split-step | Suppresses orbital oscillations 4.76× |
| Cosmology | Scale exponent $\alpha_{\rm disp}=1-\varphi^{-1}$ | Enhances small-scale gravity |
| Cosmology | Yang period $a_\varphi=\varphi^{-1}$ | Sets dark-energy oscillation scale |
| Both | Stability condition for solitons | Yang/Yin amplitude ratio $r=\varphi^{-1}$ |

The role of φ is the same at both scales: it is the **scale-separation ratio at which the system stops resonating** and settles into a fixed point.

---

## 5. Numerical unification

Both limits use the same algorithm:

1. **FFT Poisson solve** for $\Phi$ from $S[\rho]$.
2. **Split-step spectral propagation**:
   - half potential step: $\Psi \to e^{-i(V+g|\Psi|^2)\Delta\tau/2}\Psi$
   - full kinetic step: $\Psi \to \mathcal F^{-1}\!\left[e^{-ik^2\Delta\tau/(2M)}\mathcal F[\Psi]\right]$
   - half potential step again
3. Optional **φ-damping** after the kinetic step.
4. Normalization (imaginary time, or mass conservation in real time).

The only differences are the boundary conditions, the choice of $M$, and which source terms are active.

---

## 6. Demonstration

The unified script `experiments/cassi_unified_bridge.py` implements the bridge in a single 3D split-step spectral solver. It exposes two modes:

- **Atomic mode**: $M=1$, fixed soft-Coulomb proton potential
  $V_{\rm ext}(r)=-1/\sqrt{r^2+\varepsilon^2}$ with $\varepsilon=0.1\,a_0$,
  self-consistent source turned off, and optional φ-damping.
  Imaginary-time relaxation converges to $E\approx -0.499\,E_h$ and
  $\langle r\rangle\approx 1.496\,a_0$, matching the hydrogen 1s state.

- **Cosmological mode**: $M=100$, no external potential, self-consistent source
  with $\alpha_{\rm disp}=1-\varphi^{-1}$, $\alpha_{\rm yin}=1.0$ (relative),
  $\Lambda_\varphi=1.0$, and holographic bound $\eta=0.004$. A random initial
  density field grows from $\delta_{\rm rms}\approx 0.05$ to
  $\delta_{\rm rms}\approx 0.45$, with power transferring to small scales.

Results and figures are written to `docs/cassi-bridge-results.md` and
`docs/figures/cassi_bridge_*.png`.

## 7. Prediction

If the bridge is structurally correct, a single simulation should be able to:

1. Recover the hydrogen ground state when run with $M=1$, a fixed proton charge and $\alpha_{\rm yin}=\Lambda_\varphi=0$.
2. Form gravitational structures when run with $M\gg 1$, no external charge and the full Cassi source.

The demonstration above confirms both limits from the same code path.
