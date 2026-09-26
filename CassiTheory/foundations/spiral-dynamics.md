# Spiral Dynamics: Hubble, Gravity, and $c$ as Separate Cascade Diagnostics

## Status: Hypothesized—August 2026

## Abstract

The canonical two-fluid solver evolves two real densities, $E_Y$ and $E_I$.
Its conversion contribution conserves $\rho=E_Y+E_I$ and relaxes
$\varepsilon=E_Y-\varphi E_I$. The derived density-plane angle
$\theta_d=\operatorname{atan2}(E_I,E_Y)$ follows a monotone state trajectory
toward $\operatorname{atan}(\varphi^{-1})$. This angle is not an independent
compact phase and does not supply a periodic turn count or a fixed pitch per
cascade rung.

This document records three separate pieces of present-state mathematics: the
PDE Hubble relation, the potential-gradient force, and the scale-invariant
cancellation in the proposed signal-speed estimate. A logarithmic spiral,
compact clock, conversion-to-expansion rotation, and radial/azimuthal pitch
can be overlaid as an additional model, but they are **Hypothesized** inputs.
The numerical winding, stability, gravity, and scale-cancellation diagnostics
are retained with the parameter and implementation conditions under which they
were obtained.

---

## 1. Canonical density dynamics and optional spiral coordinates

### 1.1 The density-plane angle

For the conversion contribution, define

$$
\rho=E_Y+E_I,\qquad
\varepsilon=E_Y-\varphi E_I,
$$

Here $q$ is the canonical coherence gate defined in
`foundations/cassi-first-principles.md` §2.1.

The conversion contribution is

$$
\left.\partial_tE_Y\right|_{\mathrm{conv}}
=-\lambda(1-q)\varepsilon,
\qquad
\left.\partial_tE_I\right|_{\mathrm{conv}}
=+\lambda(1-q)\varepsilon.
$$

Thus

$$
\left.\dot\rho\right|_{\mathrm{conv}}=0,
\qquad
\left.\dot\varepsilon\right|_{\mathrm{conv}}
=-\lambda(1+\varphi)(1-q)\varepsilon.
$$

The derived density-plane angle is

$$
\theta_d=\operatorname{atan2}(E_I,E_Y),
$$

and its conversion-only rate is

$$
\boxed{
\left.\frac{d\theta_d}{dt}\right|_{\mathrm{conv}}
=\lambda(1-q)\frac{\rho\,\varepsilon}{E_Y^2+E_I^2}}
$$

with equilibrium value $\theta_{d,\mathrm{eq}}=\operatorname{atan}(\varphi^{-1})$.
For a homogeneous arm, the sign of $\varepsilon$ is preserved and
$\theta_d$ moves monotonically toward that value. The full PDE adds advection,
diffusion, and potential sources; those terms require their own local balance
analysis.

The solver convention is $\lambda=0.1$ in inverse solver-time units. The
normalization $w=5$, equal-and-opposite conversion, potential coefficient
normalization, and a phrase such as “one event per cycle” do not derive a rate
or its physical units. The value $\lambda=0.1$ is retained as an asserted
solver normalization/timescale convention. A probe using a different value
must report that value explicitly.

### 1.2 Optional compact phase and pitch

A separate geometric model may introduce a compact coordinate $\chi$ along the
cascade. One possible coordinate postulate is

$$
\chi(\ell)=\chi_0+\frac{2\pi}{\ln\varphi}
\ln\!\left(\frac{\ell}{\ell_0}\right),
\qquad
\ell_n=\ell_{\mathrm{Pl}}\varphi^n,
$$

or, equivalently, $\chi(n)=\chi_0+2\pi n$ for the chosen $P=1$ convention.
Another construction uses $P_\parallel=2$ and
$\chi(n)=\chi_0+2\pi n/P_\parallel$. These are coordinate choices for an
additional compact field. They do not define $\theta_d$, and the canonical
conversion equations select neither $P=1$ nor $P_\parallel=2$.

The logarithmic curve in the $(\ell,\chi)$ coordinates is therefore a
Hypothesized geometric overlay. It is not a trajectory derived by replacing
the density-plane angle with a periodic phase. The same boundary applies to
statements such as “one turn per rung,” “$\pi$ per rung,” or “one full cycle
after two rungs”: they describe an optional convention only when $\chi$ and
its pitch are explicitly added.

### 1.3 Conversion-to-expansion diagnostic record

The proposed conversion-to-expansion coupling has been written as

$$
V_{\mathrm{new}}
=\lambda\,\widetilde h(E_Y,E_I)+\frac{\lambda\varphi^{-2}}{d}.
$$

The source-level record gives the generator ratio
$\varphi^{-2}=0.382$, an optional dynamical rate of
$\ln\varphi/(2\pi)\approx0.0766$ turns per Hubble rung, a dynamical pitch
angle near $11.34^\circ$, and an azimuthal discriminator
$|a_\theta/a_r|=0.19880$. The solver as written has no $\Omega$ term in its
exchange-only rotation ($\omega=0$). These values belong to the proposed
conversion-to-expansion extension; they are not rates of $\theta_d$.

The winding test (09, run 2026-08-04) reports a layered-$\Omega$ rotation of
$0.3868\pm0.0001$ turns per rung against a dressed value $0.38902$. The bare
$\varphi^{-2}=0.382$ is the generator ratio, and an asserted $1.0$ turn per
rung is rejected as a dynamical claim. The measured discriminator is
$|a_\theta/a_r|=0.213$ versus $0.19880$. The source half's field-level
realization is unstable: it has a saddle at $(1,\varphi^{-1})$, density
blow-up without Hubble friction, logarithmic-domain exit after $0.108$ turns,
and a Hessian that cancels the $\Omega$ rotation at the fixed point.

The C1 Hubble-friction closure gives the reported stable realization at
$r_*=0.9502528427\ldots$; the fixed-point equation is transcendental. The
record identifies $r=\varphi$ as a repeller with
$f'(\varphi)=+0.12723$ and a knife-edge: $r>\varphi$ escapes, while
$r<\varphi$ drains to $r_*$. The associated pure-$\Lambda$ DESI-window fit is
$(w_0,w_a)=(-1,0)$, quoted as $4.17\sigma/2.61\sigma$ from the DESI anchor.
The spatial test reports a rapid ratio-field collapse,
$\sigma_r\times0.15$ in $1.2\tau$, into a $\rho$-dependent band with
$dr_*/d\rho\approx-0.38$; density structure survives and amplifies. The full
ratified term with $\Omega$ exits the grid's log domain at $t=8.07$. These are
records of the tested extension and its closure, not evidence that the
canonical density-plane angle is a compact clock. The same C1 record
attributes $78\%$ of the expansion rate to its coherent component under the
friction closure. “Coherent phase” in that report names the added extension
variable; it is not the canonical $\theta_d$.

---

## 2. Hubble expansion from the PDE ratio

### 2.1 Cascade scale and Hubble parameter

The cascade table assigns

$$
\ell_n=\ell_{\mathrm{Pl}}\varphi^n,
\qquad
\frac{a_{n+1}}{a_n}=\varphi,
\qquad
H=\frac{\dot a}{a}=\frac{d\ln a}{dt}.
$$

For a spatially averaged ratio
$r=\langle E_Y\rangle/\langle E_I\rangle$, the PDE expression is

$$
\boxed{
H=\frac{\lambda}{3}\frac{(\varphi-r)(1+r)}{r}
 +\frac{\lambda\varphi^{-2}}{3}}.
$$

The factor $1/3$ is the isotropic dimension factor and is Derived conditional
on the assumed spatial dimension $d=3$ in the cited cosmology formulation. The
canonical two-fluid solver takes this dimension as an input; it does not select
spatial dimension. The relation is an equation for the PDE Hubble variable; it
does not require a periodic angle.

The numerical check reports $R^2=1.000$ with mean error $0.06\%$ (tested July
2026). At the current epoch, the source record uses $N\approx291.543$ and
$\lambda=0.1$. The attenuation factors are
$\varphi^{-291.543}\approx1.1779216350439545\times10^{-61}$ and
$\lambda\varphi^{-291.543}\approx1.1779216350\times10^{-62}$ in solver
inverse-time units. The Hubble radius is recorded as
$R_H=\ell_{\mathrm{Pl}}\varphi^{291.543}\approx1.37\times10^{26}\,\mathrm m$
($4.44$ Gpc, $14.5$ Glyr), with the product check described in §4.

### 2.2 Optional spiral clock and pitch

An optional compact-coordinate model can associate a Hubble rung rate with

$$
H_{\mathrm{spiral}}
\approx\frac{\lambda\ln\varphi}{2\pi}(1-q).
$$

This is a Hypothesized spiral clock, not an equilibrium limit of the PDE
formula. At the reference state, the PDE term gives
$H=\lambda\varphi^{-2}/3$, while the optional expression gives
$H=\lambda\ln\varphi(1-q_0)/(2\pi)$ with
$1-q_0=\varphi^{-2}/3$. Their ratio is $2\pi/\ln\varphi$ under the
chosen rung-time convention. The optional coordinate rate is
$\ln\varphi/(2\pi)=0.0766$ turns per Hubble rung; $\varphi^{-2}=0.382$ is a
generator ratio under the faster rung-time
$2\pi d/\lambda\approx4.987$ times the Hubble rung-time. Neither number is a
canonical $\theta_d$ increment.

At the optional attractor, the radial relaxation and azimuthal gate rates are
reported as

$$
\gamma=\lambda(1-q_0)(1+\varphi)=\frac{\lambda}{3},
\qquad
\Omega_S=\lambda(1-q_0)=\frac{\lambda\varphi^{-2}}{3},
$$

so their algebraic ratio is

$$
\boxed{\tan(\mathrm{pitch})=\frac{\gamma}{\Omega_S}
=1+\varphi=\varphi^2=2.618\quad(69.1^\circ).}
$$

This tangent is a relation among rates in the optional construction. The
canonical conversion-angle rate is proportional to $\varepsilon$ and vanishes
at the fixed ratio. The two descriptions are not the same clock.

### 2.3 Baseline term

The PDE expression retains the baseline
$H_{\mathrm{empty}}=\lambda\varphi^{-2}/3$ at $r=\varphi$. Calling this term
zero-point spiral unwinding is an optional interpretation. The equation itself
only supplies the baseline Hubble contribution shown above.

---

## 3. Gravity from the potential gradient

### 3.1 Force equation

The momentum equation uses the buoyancy force

$$
\mathbf F=\Pi\nabla\Phi,
\qquad
\Pi=E_Y-E_I,
\qquad
\nabla^2\Phi=E_Y+E_I=\rho.
$$

With the solver convention $\widehat\Phi=-\widehat\rho/k^2$, a point-mass
potential is $\Phi=-M/(4\pi r)$ and its far-field gradient points outward.
The local force follows the sign of $\Pi$ rather than being unconditionally
attractive. At the closure probe,
$\nabla\Phi(x^*)=-0.0143$ and $\Pi(x^*)=+0.2834$, giving
$F_0(x^*)=-4.04\times10^{-3}$ at $t=0$
(`hypotheses/gravity-from-flow.md` §1). A Yang excess is repelled in the
reported TS1 branch ($d:9.90\to15.73$); a Yin excess is attracted in the
exchanged branch ($d:9.90\to7.51$). The point-particle reduction has the
Newtonian attractive convention

$$
\ddot{\mathbf X}_j
=-\alpha_j\bigl(1+(\varphi^6-1)q_j\bigr)\nabla\Phi
$$

(`gravity/three-body-analytical.md` §2.3).

These results are potential-gradient dynamics. A spiral-gradient reading is an
optional interpretation and is not needed for the force equation.

The rung-offset probes retain a separate local-flow record: at the tested
closure rungs, the flow is at most $1.5\%$ of the wave speed, points inward
for $J/\psi$, and is approximately zero for the muon; the conversion term
alone transports outward at at most $0.1\%$
(`foundations/rung-offset-mechanism.md` §5, T11–T13). These percentages
characterize the tested potential and conversion terms. They do not measure
an inter-rung phase current.

### 3.2 Cascade coupling record

The source scaling gives

$$
|\mathbf F_n|\sim\varphi^{-n}|\nabla\Phi|,
\qquad
\alpha_G(n)\sim\varphi^{-2n}.
$$

The inverse-square distance law follows conditionally from the assumed $d=3$
Poisson geometry—a Hypothesized geometric input; the canonical two-fluid solver
does not select spatial dimension. The cascade supplies the stated coupling
scaling.
For a proton at $n\approx91.5$, the record quotes

$$
\varphi^{-183}\approx5.7\times10^{-39},
\qquad
\alpha_G=\frac{Gm_p^2}{\hbar c}\approx5.91\times10^{-39},
$$

and $\alpha_G/\alpha\approx8.1\times10^{-37}$ for $\alpha\approx1/137$.
The integer-rung value is about $3.5\%$ below the observed $5.91\times10^{-39}$. The more precise fractional rung $91.46$ is the logarithmic map of the
measured mass; the catalog marks the resulting comparison Mapped (Fit-Status
Ledger row 506), rather than a parameter-free hierarchy prediction.

---

## 4. Scale-invariant signal-speed product

### 4.1 Algebraic cancellation

The proposed coherence-length estimate uses

$$
\ell_n=\ell_{\mathrm{Pl}}\varphi^n,
\qquad
\lambda_{\mathrm{eff}}(n)=\lambda\varphi^{-n}.
$$

Their product is

$$
\boxed{
\lambda_{\mathrm{eff}}(n)\ell_n
=\lambda\ell_{\mathrm{Pl}}}
$$

for every $n$. This is an algebraic scale-cancellation check. It does not by
itself derive the physical value of $c$: $\lambda=0.1$ is a dimensionless
solver convention, $\ell_{\mathrm{Pl}}$ is an external dimensionful anchor,
and the PDE-to-seconds calibration remains open.

### 4.2 Numerical record

Using the current-epoch values

$$
N\approx291.543,
\qquad
\lambda_{\mathrm{eff}}=0.1\varphi^{-291.543},
\qquad
R_H=\ell_{\mathrm{Pl}}\varphi^{291.543}\approx1.37\times10^{26}\,\mathrm m,
$$

the source record checks cancellation of the enormous factors. The product
is expected to recover $c\approx3\times10^8\,\mathrm{m\,s^{-1}}$ only after
calibrating solver inverse-time units against physical seconds; that numerical
calibration is not pinned.

### 4.3 Photon interpretation

A localized conversion disturbance may be assigned a frequency and a
coherence length in an additional propagation model. The statement
$\lambda_\gamma=c/\nu$ with emission-rung coherence length is therefore a
Hypothesized test relation, not a consequence of a compact density-plane
phase.

---

## 5. Separate mechanisms, one comparison table

The three equations below can be compared without assigning them a common
spiral cause:

| Mechanism | PDE or scaling relation | Present reading |
|---|---|---|
| Hubble | `_update_hubble` gives $H=f(r)$ | Canonical ratio-dependent expansion variable |
| Gravity | $\mathbf F=\Pi\nabla\Phi$ | Canonical potential-gradient force |
| Signal-speed product | $\lambda_{\mathrm{eff}}\ell_n=\lambda\ell_{\mathrm{Pl}}$ | Scale-cancellation diagnostic |
| Optional geometry | $\chi(n)=\chi_0+2\pi n/P$ | Hypothesized compact coordinate |

The solver may contain conversion, Hubble, and gravity terms simultaneously.
That coexistence does not establish that they are projections of one
Fibonacci spiral, and the canonical conversion angle remains the monotone
$\theta_d$ of §1.1.

---

## 6. Testable consequences and retained diagnostics

### 6.1 Hubble relation

The PDE expression for $H$ matches the quoted record to $R^2=1.000$ with
mean error $0.06\%$. The optional clock expression has a strong reported
correlation with $(1-q)$ ($R^2>0.99$), but its proportionality and rung-time
conversion are properties of the Hypothesized extension. The generator ratio
$\varphi^{-2}=0.382$ and the optional rates $0.0766$ turns per Hubble rung,
$11.34^\circ$ dynamical pitch, and $0.19880$ discriminator remain conditioned
on that extension.

### 6.2 Gravitational coupling

The relation $\alpha_G=\varphi^{-2n}$ is the identity
$\alpha_G=(m_p/M_{\mathrm{Pl}})^2$ when
$n=\log_\varphi(M_{\mathrm{Pl}}/m_p)$ is read from the measured proton mass.
At $n\approx91.5$ the quoted value is
$\varphi^{-183}\approx5.7\times10^{-39}$ versus
$5.91\times10^{-39}$, about $3.5\%$ low; the $0.1\%$ statement applies only
to the fractional-rung mass map and is Mapped. This result does not depend on
an optional spiral phase.

### 6.3 Scale-cancellation relation

The identity $\varphi^{-n}\varphi^n=1$ verifies the scale-invariant product
analytically for every $n$. The physical value awaits unit calibration.

### 6.4 Photon wavelength

The proposed equality between photon wavelength and an emission-rung
coherence length can be tested across atomic, nuclear, and particle sources.
It remains Hypothesized until a propagation model and data analysis are
specified.

---

## 7. Epistemic boundaries

### Derived or measured canonical content

- Conversion-only conservation of $\rho$ and monotone relaxation of
  $\theta_d=\operatorname{atan2}(E_I,E_Y)$ toward
  $\operatorname{atan}(\varphi^{-1})$.
- $H=(\lambda/3)(\varphi-r)(1+r)/r+\lambda\varphi^{-2}/3$ as the PDE
  Hubble relation; the quoted numerical check has $R^2=1.000$ and mean error
  $0.06\%$.
- $\mathbf F=\Pi\nabla\Phi$ with the stated sign-dependent local behavior.
- The algebraic cancellation
  $\lambda_{\mathrm{eff}}\ell_n=\lambda\ell_{\mathrm{Pl}}$.
- The cascade coupling comparison $\varphi^{-2n}$ with its Mapped proton
  calibration.

### Hypothesized additional structure

- A compact coordinate $\chi$ with a chosen pitch, including $P=1$ and
  $P_\parallel=2$ conventions.
- The logarithmic spiral interpretation and the relation of the optional
  $H_{\mathrm{spiral}}$ clock to $(1-q)$.
- The conversion-to-expansion term $V_{\mathrm{new}}$, its generator ratio,
  pitch, and the numerical winding-test/stability records in §1.3.
- Spiral-gradient language for gravity and the photon coherence-length
  relation.

### Speculative

- Physical unit calibration of $\lambda\ell_{\mathrm{Pl}}$ to $c$.
- Zero-point unwinding as the interpretation of $H_{\mathrm{empty}}$.
- Reverse-spiral configurations and any associated repulsive sector.

No item in the Hypothesized list changes the canonical density equations or
turns $\theta_d$ into a periodic field.

---

## References

- `foundations/cassi-first-principles.md`—canonical two-fluid equations, gate, and density-plane angle rate
- `foundations/spin-fibonacci-spiral.md`—optional compact-phase, pitch, and spinor construction
- `foundations/qi-flow-double-helix.md`—spatial density-plane diagnostic and double-helix boundary
- `cosmology/cosmology-from-phi.md`—PDE Hubble relation from the Yang–Yin ratio
- `foundations/dimensionful-cascade.md`—cascade table and $\ell_n=\ell_{\mathrm{Pl}}\varphi^n$
- `foundations/cascade-suppression-formula.md`—per-rung attenuation rule
- `foundations/dimensionful-constants-status.md`—physical-unit status of $c$, $\hbar$, and $G$
- `foundations/unified-lagrangian.md`—PDE coupling conventions
- `foundations/rung-offset-mechanism.md`—descent-flow and conversion diagnostics T11–T13
- `gravity/three-body-analytical.md`—point-particle potential-gradient convention
- `hypotheses/gravity-from-flow.md`—closure-probe force record
- `hypotheses/two-strand-five-channel-matter-organization.md`—TS1–TS4 and exchanged-pair records
- `two-fluid/cassi_two_fluid_3d_gpu.py`—two-fluid solver
- `two-fluid/run_pde_bubble_spiral.py`—bubble PDE diagnostic
- `visual-explainers/spiral_string.py`—optional spiral visualization
- `cassi-toe-rewrite-briefs/spiral-gravity/`—external provenance for the numbered conversion-to-expansion records
