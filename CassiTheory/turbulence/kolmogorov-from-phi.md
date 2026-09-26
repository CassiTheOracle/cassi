# The Kolmogorov −5/3 Spectrum in Cassi: Derivation and Conditional Tests

## Status: Derived/Hypothesized—August 2026

---

## Abstract

The Kolmogorov $-5/3$ law is not derived from $\varphi$. Under the usual
incompressible Navier–Stokes assumptions, a kinetic-energy spectrum
$E_u(k)$ may be inherited by a solver whose velocity field has the required
advection, forcing, and dissipation. A density spectrum is a separate
observable and does not equal $E_u(k)$ without an additional closure.

The $\varphi$-break scale $k_\varphi$, a deviation spectrum
$E_\varepsilon(k)$, a scale-dependent gravity factor, and a quality spectrum
are optional turbulence closures and diagnostics. Their proposed forms require
additional assumptions about the gate, flux, shell averaging, and gravity
coupling. The break, slopes, and amplitudes are Hypothesized closure forms or
conditional test targets rather than established predictions. The real-space
ring construction in §6 is likewise a conditional reading of the spectral
cascade.

---

## 1. The Two-Fluid Spectral Energy Budget

### 1.1 Governing Equations

The canonical state uses two nonnegative real densities $E_Y,E_I$, their
advection-diffusion equations, and the velocity equation with force
$\pi\nabla\Phi$, where $\rho=E_Y+E_I$ and $\pi=E_Y-E_I$. The default solver
does not apply a $q$ gate. The equations below are an **optional
q-gated turbulence closure**, not the canonical/default PDE; they are shown
to make the assumptions behind the proposed spectral tests explicit. No
independent Metal multiplier is part of the canonical equations.

$$\partial_t E_Y = -\nabla\cdot(\mathbf{u}E_Y) + D\nabla^2 E_Y - \lambda(1-q)(E_Y - \varphi E_I) - \chi_Y\nabla\cdot(E_Y\nabla\Phi)$$

$$\partial_t E_I = -\nabla\cdot(\mathbf{u}E_I) + D\nabla^2 E_I + \lambda(1-q)(E_Y - \varphi E_I) + \chi\nabla\cdot(E_I\nabla\Phi)$$

$$\partial_t\mathbf{u} = -(\mathbf{u}\cdot\nabla)\mathbf{u} + \pi(1+(\varphi^{6}-1)q)\nabla\Phi + \nu\nabla^2\mathbf{u}$$

where:
- $\rho = E_Y + E_I$ (total density)
- $\pi = E_Y - E_I$ (Yang excess)
- $\varepsilon = E_Y - \varphi E_I$ (deviation from $\varphi$-equilibrium)
- $q = \frac{\rho^2}{\rho^2 + \varphi^{-2} + \varepsilon^2}$ (Qi quality diagnostic when the optional gate is enabled). Here $E_Y,E_I$ are dimensionless solver densities, or densities divided by a declared reference density $\rho_\star$; the displayed form is not a physical-units expression until that normalization is fixed.
- $\xi = \varphi^6 \approx 17.944$ (a proposed Qi-gravity coupling; its use here is conditional)
- $\chi_Y,\chi$ are optional chemotactic mobilities
### 1.2 Evolution of the Deviation

Within the selected optional q-gated closure, adding the two scalar equations
with weights $(1,-\varphi)$ gives the conservative equation

$$\partial_t\varepsilon+\nabla\cdot(\mathbf{u}\varepsilon)
=-\lambda(1+\varphi)(1-q)\varepsilon+D\nabla^2\varepsilon
+\text{(chemotaxis terms)}.$$

If $\nabla\cdot\mathbf{u}=0$, this is equivalent to the advective form
$\partial_t\varepsilon+\mathbf{u}\cdot\nabla\varepsilon$. The corresponding
local damping rate is

$$\gamma_\varepsilon=\lambda(1+\varphi)(1-q).$$

This rate belongs to the selected closure: it reaches
$\lambda(1+\varphi)$ only when the gate is open with $q=0$. The default
ungated solver uses its separate conversion equation. Turbulent advection can
regenerate $\varepsilon$.

### 1.3 Spectral Decomposition

Define the isotropic spectra separately:
- $E_\rho(k)$: spectrum of total density $\rho$
- $E_\pi(k)$: spectrum of Yang excess $\pi$
- $E_\varepsilon(k)$: spectrum of deviation $\varepsilon$
- $E_u(k)$: kinetic-energy spectrum of the velocity field $\mathbf{u}$

The scalar spectral budget at scale $k$ is

$$\frac{\partial E_\varepsilon(k)}{\partial t}
= T_\varepsilon(k) - \gamma_\varepsilon^{\text{eff}}(k)E_\varepsilon(k)
- 2Dk^2E_\varepsilon(k).$$

Here $T_\varepsilon(k)$ is nonlinear transfer from advection and
$\gamma_\varepsilon^{\text{eff}}(k)$ is the scale-dependent effective damping.
The canonical PDE does not identify $E_\rho$ with the kinetic spectrum
$E_u$; doing so would require a separately specified density–velocity
closure.

---

## 2. The Two Timescales

### 2.1 Eddy Turnover Time (Kolmogorov 1941)

At scale $k$, the characteristic velocity is
$u_k\sim(kE_u(k))^{1/2}$ under the conventional one-dimensional kinetic
energy-spectrum normalization. If the velocity sector satisfies the standard
Kolmogorov assumptions,

$$E_u(k)=C_K\varepsilon_{\text{flux}}^{2/3}k^{-5/3},\qquad
u_k\sim\varepsilon_{\text{flux}}^{1/3}k^{-1/3}.$$

The eddy turnover time is then

$$\tau_{\text{eddy}}(k)=\frac{1}{ku_k}
=\varepsilon_{\text{flux}}^{-1/3}k^{-2/3}.$$

### 2.2 Conversion Time

For the selected closure at an open gate ($q=0$), conversion damps
$\varepsilon$ at rate $\lambda(1+\varphi)$. The characteristic time is

$$\tau_{\text{conv}}=\frac{1}{\lambda(1+\varphi)}
\approx\frac{1}{\lambda\cdot2.618}.$$

For $\lambda=0.1$, $\tau_{\text{conv}}\approx3.82$ in simulation time units.

### 2.3 The $\varphi$-Break Scale

The **crossover wavenumber** $k_\varphi$ where the two timescales are equal is
defined within this optional closure by

$$\tau_{\text{eddy}}(k_\varphi) = \tau_{\text{conv}}$$

$$\varepsilon_{\text{flux}}^{-1/3} k_\varphi^{-2/3} = \frac{1}{\lambda(1+\varphi)}$$

$$\boxed{k_\varphi = \sqrt{\frac{\lambda^3(1+\varphi)^3}{\varepsilon_{\text{flux}}}}}$$

For the illustrative values $\lambda=0.1$ and
$\varepsilon_{\text{flux}}=1$ this gives
$k_\varphi\approx\sqrt{0.01794}\approx0.134$. If $L=2\pi$, the fundamental
mode is $k_{\min}=1$; this illustrative choice therefore places the proposed
break outside the resolved box. It is an algebraic scale estimate, not a
recorded spectrum receipt.

### 2.4 Conditional Regimes

The following table states assumptions used by the selected closure. The
$q$ and $G_{\text{eff}}$ columns are not outputs of the canonical solver:

| Regime | Condition | $\tau_{\text{eddy}}$ vs $\tau_{\text{conv}}$ | $E_\varepsilon$ behavior | assumed $q$ | conditional $G_{\text{eff}}$ |
|--------|-----------|---------------------------------------------|--------------------------|------------|-------------------------------|
| **Qi-active** | $k \ll k_\varphi$ | $\tau_{\text{eddy}} \gg \tau_{\text{conv}}$ | $E_\varepsilon$ strongly damped | $q$ near 0 | closure-dependent |
| **Inertial** | $k \gg k_\varphi$ | $\tau_{\text{eddy}} \ll \tau_{\text{conv}}$ | $E_\varepsilon$ weakly damped by conversion | not fixed by $k$ alone | closure-dependent |

The regime labels are conditional timescale interpretations. A high-$q$
state suppresses the $(1-q)$ conversion channel and cannot simultaneously be
described as strongly conversion-damped. No retained spectrum receipt
establishes a resolved break or the associated $q$ values. The proposed
$\varphi$-break may be compared with the condensation-vs-diffusion balance in
`foundations/bubble-edge-geometry.md` §1.2, but that analogy does not derive a
spatial ring structure.

---
## 3. The $E_\varepsilon$ Spectrum: An Optional Passive-Scalar Closure

### 3.1 Inertial Range ($k \gg k_\varphi$)

If the optional closure makes $\varepsilon$ a passive scalar and if the
Obukhov–Corrsin assumptions hold, then

$$E_\varepsilon(k) = C_{\text{OC}} \cdot \chi_\varepsilon \cdot \varepsilon_{\text{flux}}^{-1/3} \cdot k^{-5/3}$$

where $\chi_\varepsilon$ is a scalar-variance production rate. This is a
conditional application of standard passive-scalar theory, not a consequence
of the Cassi PDE. A proportionality $E_\varepsilon(k)\propto E_u(k)$ is a
candidate diagnostic whose normalization, density–velocity closure, and
forcing protocol must be fixed before testing.

### 3.2 Qi-Active Range ($k \ll k_\varphi$)

Within the same optional closure, a stationary shell budget could be written

$$0 \approx -\gamma_\varepsilon^{\text{eff}}(k) \cdot E_\varepsilon(k) + T_\varepsilon(k)$$

If a shell-average substitution is additionally made, one obtains the
illustrative form

$$\gamma_\varepsilon^{\text{eff}}(k) = \lambda(1+\varphi) \cdot \frac{\varphi^{-2} + E_\varepsilon(k)}{\bar{\rho}^2 + \varphi^{-2} + E_\varepsilon(k)}$$

where $\bar{\rho}^2$ is a chosen mean-square density. This substitution is not
derived from the local nonlinear $q$ field and has unresolved normalization
and window dependence. A steeper form
$E_\varepsilon(k)\propto k^{-5/3-\delta}$ with $\delta>0$ is therefore an
unregistered conditional test target; its sign and value require a closure
model and a retained spectrum receipt.

---

## 4. Optional Scale-Dependent Gravity Closure

### 4.1 Effective Gravitational Constant

The canonical velocity equation uses the force $\pi\nabla\Phi$. An optional
q-gated closure inserts a multiplicative factor:

$$\mathbf{F}_{\mathrm{opt}} = \pi(1 + (\varphi^{6}-1)q)\nabla\Phi.$$

If a scale-dependent coarse-grained $q_{\mathrm{proxy}}(k)$ and the ratio
$r_\pi(k)=\pi(k)/\rho(k)$ are supplied, the corresponding diagnostic can be
written

$$G_{\mathrm{eff,opt}}(k) = r_\pi(k)\left[1+(\varphi^{6}-1)q_{\mathrm{proxy}}(k)\right]G.$$

Neither $r_\pi(k)=\varphi^{-3}$ nor a scale law for
$q_{\mathrm{proxy}}(k)$ follows from the canonical equations. A constitutive
map, coarse-graining window, and calibration are required.

### 4.2 Conditional Endpoint Illustration

For illustration only, imposing $r_\pi=\varphi^{-3}$ and endpoint values
$q_{\mathrm{proxy}}=0,1$ gives $\varphi^{-3}G\approx0.236G$ and
$\varphi^3G\approx4.236G$, with ratio $\varphi^6\approx17.94$. These values
are a conditional ansatz, not a derived gravitational limit or an observed
scale dependence. Halo contrasts likewise require a separately specified
matter map and calibration.

### 4.3 Impact on the Energy Spectrum

An injection relation such as

$$P(k) \propto G_{\mathrm{eff,opt}}(k)\cdot
\langle\pi\nabla\Phi\cdot\mathbf{u}\rangle_k$$

requires a forcing and transfer closure. The inertial-range
$E_u(k)=C_K\varepsilon_{\text{flux}}^{2/3}k^{-5/3}$ is the standard kinetic
Kolmogorov form under its usual assumptions. It must not be relabeled as the
total-density spectrum $E_\rho(k)$. The proposed enhanced-flux
relation

$$\widetilde{\varepsilon}=\varphi^6\varepsilon_{\text{flux}}$$

and its resulting $\varphi^4$ amplitude factor are unproved choices, not
consequences of the force equation. The low-$k$ slope and any amplitude jump
remain unresolved until a closure and a retained spectrum receipt are
specified; no registered prediction is asserted here.

---

## 5. A Scale-Resolved $q$ Diagnostic Requires a Closure

The canonical $q$ is a local nonlinear diagnostic,

$$q(\mathbf{x}) = \frac{\rho(\mathbf{x})^2}{\rho(\mathbf{x})^2 + \varphi^{-2} + \varepsilon(\mathbf{x})^2}.$$

A Fourier-shell spectrum $E_\varepsilon(k)$ does not define a unique
scale-resolved $q(k)$ because the ratio must be coarse-grained before the
nonlinear operation. One possible mean-field proxy is

$$q_{\mathrm{proxy}}(k) = \frac{\bar{\rho}^2}{\bar{\rho}^2 + \varphi^{-2} + E_\varepsilon(k)},$$

with a declared window and normalization. For
$\bar{\rho}^2\gg\varphi^{-2}$ this becomes
$q_{\mathrm{proxy}}\approx[1+E_\varepsilon/\bar{\rho}^2]^{-1}$.

If $E_\varepsilon\propto k^{-5/3}$, this proxy increases with $k$ in the
inertial range and approaches $\bar{\rho}^2/(\bar{\rho}^2+\varphi^{-2})$ at
large $k$; it does not establish the opposite endpoint ordering assumed in
§2.4. The $q$ limits and any relation such as
$1-q_{\mathrm{proxy}}\propto k^{-5/3}$ therefore remain closure-dependent.
A preregistered coarse-graining rule, normalization, null model, and retained
spectrum receipt are required before this becomes a test.

---

## 6. The Real-Space Geometry of the $\varphi$-Cascade

The spectral budget in §§2–5 combines the canonical two-fluid variables with
a selected optional q-gated closure and inherited Navier–Stokes assumptions.
Its density, velocity, and proxy spectra therefore have mixed conditional
status. A separate optional Hypothesized coordinate construction supplies a
spatial reading through an individual bubble shell as a nested ladder of matter
and void rings; its use is conditional on the pitch, internal-advance, parity,
and radial-reading inputs stated in §6.3.

### 6.1 Optional Hypothesized coordinate: the ring ladder as a radial cascade reading

The optional Hypothesized coordinate construction uses
`foundations/bubble-edge-geometry.md` §3 to specify the interior structure of a
rung-$n$ bubble from the doublet phase $\alpha = \pi u$,
$u = \log_\varphi(r/\ell_n)$—a radial coordinate reading of the
$\pi$-per-rung internal advance. Under this coordinate, matter is assigned to
integer-rung radii and voids to half-rungs:

$$\boxed{r_k^{\text{matter}} = R\,\varphi^{-k}, \qquad r_k^{\text{void}} = R\,\varphi^{-(k+\frac12)}, \qquad k = 0,1,2,\ldots}$$

for a bubble shell of outer radius $R = \ell_n$. Within this coordinate
construction, the successive matter-ring ratio is fixed:

$$\frac{r_{k+1}^{\text{matter}}}{r_k^{\text{matter}}} = \varphi^{-1} \approx 0.6180$$

—so **eddies nest within eddies at a spacing factor $\varphi \approx 1.618$** under
this optional Hypothesized radial reading. It supplies a spatial reading
alongside the spectral cascade's split at $k_\varphi$. Classical
Richardson-style cascade sketches often use an order-two scale ratio, but the
exact factor depends on the chosen cascade convention; this coordinate uses
the golden ratio. No universal factor-two law is asserted here. The bubble
shell is the coordinate object on which this optional ladder is imprinted.

### 6.2 Rings as nested condensates; the ~10-rung floor

Within the same conditional coordinate, because $\ell_{n-k} = \ell_n\,\varphi^{-k}$,
matter ring $k$ is assigned to a rung-$(n-k)$ condensate—the radial picture of
bubbles-within-bubbles (`foundations/bubble-edge-geometry.md` §3.3). The cascade
suppression floor of ~1% (`foundations/bubble-lattice-fabric.md` §3.3) bounds the
coordinate's physically meaningful inward descent to $\Delta n \approx 10$ rungs;
the refined count is:

$$N = \frac{\ln 100}{\ln\varphi} = 9.570$$

Under this conditional radial reading, a bubble shell carries **~10 matter
rings** (interleaved with 9 void troughs) at the 1% coherence floor. Let
$r_{\mathrm{out}}=\ell_n$ and let $f\in(0,1]$ be a dimensionless radial
fraction. The span $[f\ell_n,\ell_n]$ contains

$$N(f)=-\log_\varphi f$$

successive rung intervals, independent of the dimensional outer scale
$\ell_n$. Thus the scale-covariance statement concerns the fraction $f$, not a
dimensioned radius inserted into a logarithm.

### 6.3 Tier: mixed conditional spectral budget and optional ring law

The spectral budget in §§2–5 is conditional on the selected closure,
coarse-graining choices, and inherited kinetic-spectrum assumptions. The ring
law is **Derived conditional** per `foundations/bubble-edge-geometry.md` §3.1,
subject to (i) the asserted pitch convention $\Theta=2\pi n$ per rung
(`foundations/spiral-dynamics.md` §1.2), (ii) the doublet's $\pi$-per-rung
internal advance (`foundations/spin-fibonacci-spiral.md` §2.1), (iii) the
pool-cell parities (`foundations/rung-offset-mechanism.md` §4.1), and (iv) the
radial-reading inference. Identifying interior rings with nested condensates
is an inference from `foundations/bubble-lattice-fabric.md` §3.2, not an
established identity.

### 6.4 Scope caveat: the canonical solver does not dynamically realize the ladder

The pre-registered dynamic probe `two-fluid/run_bubble_ring_dynamic_probe.py`
specifies four spatial-coupling arms—A baseline (conversion-only, $D =
\mathbf{u} = \chi = c_s^2 = 0$), B diffusion ($D = 0.0002$), C
gravity-buoyancy ($\nu = 0.0005$, $\chi = 0$), and W wave-verify
($c_s^2 = 0.5$)—but this document retains no JSON receipt or hash label for a
run. Its dynamic ring verdict is therefore **unverified** here; no four-arm
null result is claimed. The solver implementation is first-order in time (no
$d^2E/dt^2$ wave operator; $c_s^2$ enters only as a velocity pressure force),
so the full second-order ring-ladder wave form
($d^2E = c^2\nabla^2 E - \omega_0^2(E_Y - \varphi E_I)$) is not present in this
solver—it belongs to the space-sim GLSL PDE. Whether real-space realization
requires that second-order wave form remains an open question for a retained
probe receipt.

---

## 7. Conditional Inputs and Unresolved Results

The following rows are conditional algebra or model inputs, not results derived
by the canonical PDE:

| Quantity | Conditional basis | Status |
|---|---|---|
| $k_\varphi$ | Timescale equality in the selected closure | Hypothesized scale estimate |
| $G_{\mathrm{eff,opt}}$ relation and any endpoint ratio | q-gated force ansatz plus supplied $r_\pi$ and $q_{\mathrm{proxy}}$ maps | Hypothesized |
| $q_{\mathrm{proxy}}(k)$ | Chosen coarse-graining and shell normalization | Hypothesized diagnostic |
| $E_\varepsilon$ slope or amplitude change | Passive-scalar and transfer closure | Hypothesized test target |
| $\varphi^6$ flux and $\varphi^4$ amplitude factors | Explicit enhanced-flux ansatz | Hypothesized |

The standard kinetic $-5/3$ slope and $C_K$ remain inherited empirical
Navier–Stokes inputs. Exact low-$k$ slopes, intermittency, and any resolved
break require a closure and retained spectrum receipt.


## 8. Conclusion

The Kolmogorov $-5/3$ law remains an inherited kinetic-spectrum result under
the usual Navier–Stokes assumptions. The selected Cassi closure supplies
conditional diagnostics for $k_\varphi$, $E_\varepsilon$, and a chosen
$q_{\mathrm{proxy}}$; it does not establish a density spectrum, gravity
amplitude jump, or low-$k$ slope. No retained spectrum receipt in this
document establishes a measured turbulence exponent or resolved break.

### Candidate test design

Run a turbulence simulation with parameters that place the conditional
$k_\varphi$ estimate in the resolved kinetic inertial range. Using
$k_\varphi=\varphi^3\sqrt{\lambda^3/\varepsilon_{\text{flux}}}$:

| $N$ | $\lambda$ | $\varepsilon_{\text{flux}}$ | $k_\varphi$ | $k_{\max}$ | $k_\varphi/k_{\min}$ | $k_{\max}/k_\varphi$ | Integer modes below / above break |
|---|-----|--------|------|--------|----------------------|----------------------|-----------------------------------|
| 64 | 0.17 | 0.01 | 2.97 | 21.4 | 2.97 | 7.22 | 2 / 7 |
| 64 | 0.37 | 0.10 | 3.01 | 21.4 | 3.01 | 7.11 | 3 / 7 |
| 128 | 0.20 | 0.01 | 3.79 | 42.9 | 3.79 | 11.32 | 3 / 11 |
| 128 | 0.30 | 0.01 | 6.96 | 42.9 | 6.96 | 6.16 | 6 / 6 |

Candidate observables are the kinetic spectrum $E_u(k)$, the deviation
spectrum $E_\varepsilon(k)$, and a preregistered coarse-grained
$q_{\mathrm{proxy}}(k)$. A low-$k$ amplitude factor $\varphi^4$ or slope
change is a conditional hypothesis to be tested, not a current result.

---
## Appendix: Algebraic Break-Scale and Mode-Count Check

```python
# phi-break scale as a function of lambda and eps
import numpy as np
phi = (1 + np.sqrt(5))/2

# For N=64: lambda=0.17, eps=0.01 puts k_phi ~ 3 in the inertial range
lam, eps = 0.17, 0.01
k_phi = phi**3 * np.sqrt(lam**3 / eps)
k_min = 2*np.pi / (2*np.pi)  # = 1.0 for L=2pi
N, dealias = 64, 0.67
k_max = N/2 * dealias * k_min

print(f"lambda={lam}, eps={eps}")
print(f"k_phi = {k_phi:.3f}  ({k_phi/k_min:.1f}x k_min)")
print(f"Resolved range: [{k_min:.1f}, {k_max:.1f}]")
print(f"Integer modes below break: {int(k_phi/k_min)}")
print(f"Integer modes above break: {int(k_max/k_phi)}")
# Output:
# k_phi = 2.969  (3.0x k_min)
# Integer modes below break: 2; above break: 7

# For N=128: lambda=0.2, eps=0.01 gives deeper inertial range
N2 = 128
k_max2 = N2/2 * 0.67
lam2, eps2 = 0.20, 0.01
k_phi2 = phi**3 * np.sqrt(lam2**3 / eps2)
print(f"\nN=128: lambda={lam2}, eps={eps2}")
print(f"k_phi = {k_phi2:.3f}  ({k_phi2/k_min:.1f}x k_min)")
print(f"Resolved range: [{k_min:.1f}, {k_max2:.1f}]")
print(f"Integer modes below break: {int(k_phi2/k_min)}")
print(f"Integer modes above break: {int(k_max2/k_phi2)}")
# Output:
# k_phi = 3.788  (3.8x k_min)
# Integer modes below break: 3; above break: 11
```

For N=64 with $\lambda=0.17$, $\varepsilon=0.01$: $k_\varphi \approx 3.0$, with ~2 wavenumbers below the break and ~7 above. For N=128 with $\lambda=0.2$, $\varepsilon=0.01$: $k_\varphi \approx 3.8$, with ~3 below and ~11 above—a clean inertial range on both sides of the break.

---

## References

- `cassi-physics.md`—two-fluid PDE, Qi gate, and $G_{\text{eff}} = (\pi/\rho)(1+(\varphi^{6}-1)q)G$
- `foundations/xi-derivation.md`—derivation of the Qi-gravity coupling $\xi = \varphi^6$
- `foundations/bubble-edge-geometry.md` §§1.2, 3—conditional condensation threshold and radial ring construction
- `foundations/bubble-lattice-fabric.md` §§3.2–3.3—nested-condensate inference and the 1% suppression floor
- `foundations/spiral-dynamics.md` §1.2—conditional pitch convention used by the radial coordinate
- `foundations/spin-fibonacci-spiral.md` §2.1—doublet's $\pi$-per-rung internal advance
- `foundations/rung-offset-mechanism.md` §4.1—pool-cell parity assumptions
- `two-fluid/run_bubble_ring_dynamic_probe.py`—four-arm dynamic ring protocol; this document retains no JSON receipt or hash label for a run
