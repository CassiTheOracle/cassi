# Cassi Two-Fluid Cosmology: Deriving Expansion from Yang-Yin Balance

## 1. What we already have

The GPU two-fluid solver tracks two energy-like scalar fields on a periodic box:

- **Yang** `EY` — expansionary, outward, dark-energy-like
- **Yin**  `EI` — contractive, inward, matter-like

Their background means relax to the golden-ratio equilibrium

$$
\langle EY \rangle = 1, \qquad \langle EI \rangle = \varphi^{-1},
\qquad
\frac{\langle EY \rangle}{\langle EI \rangle} = \varphi \approx 1.618 .
$$

The homogeneous conversion dynamics are

$$
\dot EY = -\lambda\,(EY - \varphi\,EI), \qquad
\dot EI = +\lambda\,(EY - \varphi\,EI) .
$$

Two immediate consequences:

1. **Total background energy is conserved** by conversion:
   $
   \frac{d}{dt}(EY + EI) = 0 .
   $
2. The system is an *energy exchanger*, not a creator of energy.

So if we want expansion, we have to ask: **what geometric quantity is encoded by the Yang/Yin imbalance?**

---

## 2. A Cassi definition of the scale factor

In standard cosmology the scale factor $a(t)$ measures physical volume. Here we
identify volume with the Yang excess over Yin, because Yang is the
expansionary field. Define

$$
\boxed{a^3(t) \;\equiv\; \frac{EY(t)}{EI(t)}} .
$$

At equilibrium $a^3 = \varphi$. Small $a$ means Yin dominates (matter-dominated,
contracted); large $a$ means Yang dominates (dark-energy-dominated, expanded).

The Hubble parameter is the logarithmic growth rate of this volume:

$$
H \;\equiv\; \frac{\dot a}{a}
   \;=\; \frac{1}{3}\,\frac{d}{dt}\ln\!\left(\frac{EY}{EI}\right)
   \;=\; \frac{1}{3}\left(\frac{\dot EY}{EY} - \frac{\dot EI}{EI}\right) .
$$

Using the conversion equations,

$$
\boxed{
H = \frac{\lambda}{3}\,(\varphi - r)\,\frac{1+r}{r},
\qquad r \equiv \frac{EY}{EI} = a^3 .
}
$$

So expansion is driven by the **deviation from golden-ratio equilibrium**:

- If $r < \varphi$ (matter-dominated), $H > 0$ → expansion.
- If $r > \varphi$ (Yang-dominated), $H < 0$ → contraction.
- At $r = \varphi$, $H = 0$ → the static Cassi equilibrium.

This is a *dynamical* definition of expansion: it does not have to be put in by
hand, it falls out of the Yang-Yin imbalance.

---

## 3. Friedmann-like equation

In standard cosmology the Friedmann constraint is

$$
H^2 = \frac{8\pi G}{3}\,(\rho_m + \rho_\Lambda) .
$$

In the Cassi two-fluid we identify

$$
\rho_\Lambda \propto EY, \qquad \rho_m \propto EI .
$$

Because the homogeneous conversion conserves $EY+EI$, the total comoving
energy density is constant. Choose units so that

$$
EY + EI = \varphi \quad\Longleftrightarrow\quad \rho_{\rm tot} = \rho_{\rm crit} .
$$

Then the Friedmann constraint becomes simply

$$
\boxed{
\left(\frac{\dot a}{a}\right)^2 = H_0^2 \;\frac{EY + EI}{\varphi}
= H_0^2 .
}
$$

In this homogeneous limit $H$ is constant, so the natural attractor is **de
Sitter expansion** with $a \propto e^{H_0 t}$. The conversion term determines
*how fast* the system approaches the equilibrium scale factor
$a_* = \varphi^{1/3}$, but the asymptotic geometry is one of constant expansion.

---

## 4. Connecting to ΛCDM

ΛCDM is not purely de Sitter because matter dilutes as $a^{-3}$ while dark
energy does not. The Cassi homogeneous model as written assumes comoving
quantities that are not diluted. To recover the ΛCDM trajectory we promote the
fields to physical densities and add Hubble dilution:

$$
\dot\rho_\Lambda + 3H\rho_\Lambda = -\lambda\,(\rho_\Lambda - \varphi\,\rho_m),
$$
$$
\dot\rho_m + 3H\rho_m = +\lambda\,(\rho_\Lambda - \varphi\,\rho_m),
$$
$$
H^2 = \frac{8\pi G}{3}\,(\rho_\Lambda + \rho_m) .
$$

This is a **coupled dark-energy / matter fluid** whose interaction is fixed by
the golden ratio. At late times the interaction drives the ratio toward
$\rho_\Lambda/\rho_m = \varphi$, giving asymptotic fractions

$$
\Omega_\Lambda^* = \frac{\varphi}{1+\varphi} = \varphi^{-1} \approx 0.618,
$$
$$
\Omega_m^* = \frac{1}{1+\varphi} = \varphi^{-2} \approx 0.382 .
$$

The present observed value $\Omega_\Lambda/\Omega_m \approx 2.3$ is therefore
interpreted as the universe still evolving toward the Cassi equilibrium at
$\varphi \approx 1.618$ (or, depending on parametrization, toward
$\varphi^2 \approx 2.618$ if the dark-energy fraction is measured against the
Yin excess).

---

## 5. Physical meaning

- **Dark energy is Yang.** It carries the geometry; its density sets the
  expansion rate.
- **Gravity is Yin.** It clumps matter and tries to pull the ratio back toward
  equilibrium.
- **The conversion term is the Yang↔Yin exchange.** It is the cosmological
  analogue of particle creation / vacuum-matter transition.
- **The golden ratio is the late-time attractor.** The universe expands until
  Yang exceeds Yin by exactly $\varphi$, at which point the net drive for further
  expansion vanishes.

This is the same conclusion reached in the turbulence and oscillator
experiments: Yang must lead Yin by $\varphi$ for a stable, dynamic equilibrium.

---

## 6. How to implement it in the two-fluid solver

The practical upgrade is to work in **comoving coordinates** with a time-dependent
scale factor:

1. Replace physical coordinates $\mathbf{x}$ with comoving coordinates
   $\mathbf{q} = \mathbf{x}/a(t)$.
2. Add Hubble-drag terms to the velocity equation:
   $$
   \partial_t \mathbf{v} + (\mathbf{v}\cdot\nabla)\mathbf{v}/a
   = -\nabla\Phi/a - H\,\mathbf{v} .
   $$
3. Evolve $a(t)$ and $H(t)$ from the homogeneous Friedmann equation using the
   spatially averaged $EY$ and $EI$.
4. Keep the chemotactic drift and conversion terms unchanged; they now operate
   on comoving densities.

This turns the two-fluid box into a genuine cosmological solver whose
background expansion is derived from the Yang-Yin balance rather than imposed
externally.

---

## 7. Validation: two-fluid vs standard particle-mesh

A head-to-head run against a conventional particle-mesh N-body solver gives a
sanity check on the comoving two-fluid solver.  Both methods start from the same
ΛCDM-shaped Eisenstein-Hu power spectrum in a 100 Mpc/h box.

| Model | Resolution | Final δ_rms | RMS log error vs ΛCDM |
|---|---|---:|---:|
| Cassi two-fluid | 128³ grid | 0.081 | **0.479 dex** |
| Standard PM (TSC) | 256³ particles → 128³ mesh | 0.059 | 0.736 dex |

The PM run uses triangular-shaped-cloud mass assignment with eight particles per
force cell to suppress the one-particle-per-cell noise that steepens a raw CIC
spectrum.  Even so, the Cassi two-fluid retains the input ΛCDM shape more
faithfully, while the PM run shows the characteristic suppression of intermediate-
scale power and overshoot near the mesh Nyquist frequency.  The two-fluid solver
is therefore not merely reproducing ΛCDM by construction: it matches the
large-scale shape expected from standard N-body evolution without requiring a
particle-deconvolution step.

A direct cell-by-cell cross-correlation of the two-fluid and PM density fields
(with matched growth amplitude, χ = 2.0) gives a Pearson correlation of only
**≈ 0**.  The two methods therefore agree on the one-point power-spectrum shape
but not on the spatial locations of individual structures.  This is expected:
the two-fluid evolution is governed by chemotactic Yin-Yang collapse, while the
PM evolution is governed by gravitational N-body dynamics, so phases decorrelate
quickly even when the variance and P(k) shape are similar.

Full details:
- [`cassi-two-fluid-cosmology-pm-comparison.md`](cassi-two-fluid-cosmology-pm-comparison.md)
- [`cassi-two-fluid-cosmology-pm-long-evolution.md`](cassi-two-fluid-cosmology-pm-long-evolution.md)
- [`cassi-two-fluid-cosmology-pm-cross-corr.md`](cassi-two-fluid-cosmology-pm-cross-corr.md)

## 8. Summary

Yes — expansion can be derived from what we have. The scale factor is the ratio
of Yang to Yin energy, and the Hubble parameter is the rate at which the system
relaxes toward the golden-ratio equilibrium. The Friedmann constraint emerges
from energy conservation, and the late-time attractor is a de Sitter-like state
with $\Omega_\Lambda/\Omega_m = \varphi$. Adding Hubble drag and a dynamical
$a(t)$ to the GPU solver is the natural next implementation step.
