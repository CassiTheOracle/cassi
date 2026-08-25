# Spin and Fibonacci Spirals: An Optional Compact-Phase Extension

## Status: Hypothesized—August 2026

## Abstract

The canonical Cassi state is the real density pair $(E_Y,E_I)$. Its derived
angle $\theta_d=\operatorname{atan2}(E_I,E_Y)$ changes monotonically under the
equal-and-opposite conversion ODE and approaches
$\operatorname{atan}(\varphi^{-1})$. The ODE conserves
$\rho=E_Y+E_I$; it does not provide an independent compact phase, a fixed
angular advance per cascade rung, a complex amplitude, a half-angle spinor, or
spin quantization.

This document specifies a separate, **Hypothesized** construction in which an
added compact coordinate $\chi$ is assigned a logarithmic Fibonacci pitch. An
optional complex amplitude and half-angle lift then provide a proposed map
$s=\Delta n/2$, proposed $4\pi$ spinor periodicity, and proposed particle
assignments. Those structures are model postulates and are not consequences of
the canonical conversion. The two-pole PDE nulls, exact sign-flip arithmetic
of the optional ansatz, minimal-span bookkeeping, and form-factor prediction
are retained with their present numerical and epistemic boundaries.

---

## 1. Canonical densities and the optional spiral coordinate

### 1.1 What the solver evolves

The conversion contribution is

$$
\rho=E_Y+E_I,
\qquad
\varepsilon=E_Y-\varphi E_I,
$$

Here $q$ is the canonical coherence gate defined in
`foundations/cassi-first-principles.md` §2.1.

$$
\left.\partial_tE_Y\right|_{\mathrm{conv}}
=-\lambda(1-q)\varepsilon,
\qquad
\left.\partial_tE_I\right|_{\mathrm{conv}}
=+\lambda(1-q)\varepsilon.
$$

Therefore

$$
\left.\dot\rho\right|_{\mathrm{conv}}=0,
\qquad
\left.\dot\varepsilon\right|_{\mathrm{conv}}
=-\lambda(1+\varphi)(1-q)\varepsilon.
$$

The density-plane angle is

$$
\theta_d=\operatorname{atan2}(E_I,E_Y),
$$

with conversion-only rate

$$
\boxed{
\left.\frac{d\theta_d}{dt}\right|_{\mathrm{conv}}
=\lambda(1-q)\frac{\rho\,\varepsilon}{E_Y^2+E_I^2}}.
$$

It moves monotonically toward
$\theta_{d,\mathrm{eq}}=\operatorname{atan}(\varphi^{-1})$ on a homogeneous
conversion arm and stops at the fixed ratio. A branch choice for
$\operatorname{atan2}$ is a coordinate representation of two real numbers;
it is not a compact dynamical field.

The solver convention is $\lambda=0.1$ in inverse solver-time units. The
choice $w=5$ does not derive this rate or its units: equal-and-opposite
conversion, potential-coefficient normalization, and a “one event per cycle”
interpretation leave $\lambda=0.1$ as an asserted normalization/timescale
convention. Numerical diagnostics below retain the value used by each named
probe.

The committed winding-rate probe tests this state function rather than a
periodic phase. At its setting $\lambda=0.05$, $t=4$, four of four homogeneous
arms agree with the formula to relative error at most $2.2\times10^{-3}$ and
with 100% sign agreement (`two-fluid/run_winding_rate_probe.py`).

### 1.2 Coordinate postulate for a Fibonacci spiral

An additional model may introduce a compact coordinate $\chi$ on the scale
ladder

$$
\ell_n=\ell_{\mathrm{Pl}}\varphi^n,
\qquad
\chi(\ell)=\chi_0+\frac{2\pi}{\ln\varphi}
\ln\!\left(\frac{\ell}{\ell_n}\right).
$$

For this convention the coordinate pitch is
$2\pi/\ln\varphi\approx13.06$ radians per e-fold in scale. The numerical
value belongs to the chosen coordinate map.

Equivalently, one may choose

$$
\chi(n)=\chi_0+2\pi n
$$

for a one-turn-per-rung coordinate convention, or
$\chi(n)=\chi_0+2\pi n/P_\parallel$ for a chosen pitch
$P_\parallel$. This is an explicit coordinate postulate. It is not the
canonical angle $\theta_d$, and the conversion ODE supplies no value of
$P_\parallel$.

With a conceptual scale coordinate $r_c$ rather than a physical spatial
radius, the optional logarithmic curve is

$$
\chi(r_c)=\chi_0+\frac{2\pi}{\ln\varphi}
\ln\!\left(\frac{r_c}{\ell_n}\right).
$$

The variable $r_c$ labels scale; it is not a radial coordinate in physical
three-dimensional space. The construction can be used to describe a
geometric overlay only after $\chi$, its pitch, and its embedding are supplied
as additional model data.

The separate conversion-to-expansion test assigns the optional generator ratio
$\varphi^{-2}=0.382$, $0.0766$ turns per Hubble rung, an $11.34^\circ$
dynamical pitch, and $|a_\theta/a_r|=0.19880$. The winding record is
$0.3868\pm0.0001$ turns per rung versus the dressed $0.38902$; these values
belong to the tested extension and have no status as canonical
$\theta_d$ increments (`foundations/spiral-dynamics.md` §1.3).

### 1.3 Spatial PDE boundary

The two-pole bubble PDE test (July 2026,
`two-fluid/run_pde_bubble_spiral.py`) found angular power dominated by
$m=2$ (ellipsoid cross-section), with no detectable $m=5$ Fibonacci mode. Its
angular phase tracking measured $d\phi/dt\sim1.5\times10^{-4}$ rad/step,
against an expected $\lambda=0.02$ rad/step for that tested extension. There
was no detectable spiral rotation in the physical density pattern.

The five-arm pattern in `visual-explainers/fibonacci_bubble_spiral.py` is a
geometric property of geodesics on the triaxial $\varphi$-ellipsoid, following
the golden-angle phyllotaxis $2\pi/\varphi^2$. It is an optional surface
geometry and does not show that the canonical PDE generates a Fibonacci phase.

---

## 2. Optional compact phase, half-angle, and spin map

### 2.1 Half-angle lift as an added representation

Choose the one-turn coordinate convention for illustration,
$\Delta\chi=2\pi\Delta n$, and define an additional half-angle variable

$$
\vartheta=\frac{\chi}{2},
\qquad
\Delta\vartheta=\pi\Delta n.
$$

An optional complex-amplitude ansatz is

$$
(\Psi_Y,\Psi_I)
:=\bigl(\sqrt{E_Y}\,e^{i\chi/2},\ \sqrt{E_I}\,e^{i\chi/2}\bigr),
\qquad r=\frac{E_Y}{E_I},
\qquad \frac{|\Psi_Y|^2}{|\Psi_I|^2}=r.
$$

The complex exponentials and the half-angle are new structure. The canonical
state supplies the real ratio $r$ but does not supply $e^{i\chi/2}$, its
single-valuedness condition, or a spinor representation.

If the added representation is accepted, its proposed spin label is

$$
\boxed{
 s=\frac{\Delta\vartheta}{2\pi}
 =\frac{\Delta\chi}{4\pi}
 =\frac{\Delta n}{2}.}
$$

The arithmetic of the ansatz gives

$$
\Psi(\chi+2\pi)=-\Psi(\chi),
\qquad
\Psi(\chi+4\pi)=+\Psi(\chi).
$$

`computations/spin_doublet_half_angle.py` reports the exact ratios
$\Psi(\chi+2\pi)/\Psi(\chi)=-1$ and
$\Psi(\chi+4\pi)/\Psi(\chi)=+1$. The script also evaluates the separately
defined full-angle scalar $e^{i\chi}$, which returns to itself under
$\chi\mapsto\chi+2\pi$. These are exact checks of the proposed ansatz, not
measurements of the canonical two-fluid solver.

### 2.2 Proposed spectrum table

The following table records the optional mapping when $\Delta n$ is selected
as a model input. It is not a derivation from $E_Y$ and $E_I$.

| Proposed spin $s$ | Selected span $\Delta n$ | Added angle $\Delta\vartheta$ | Added periodicity | Proposed class | Example |
|:---:|:---:|---|---|---|---|
| $0$ | $0$ | None | $2\pi$ | Scalar boson | Higgs |
| $\frac12$ | $1$ | $\pi$ | $4\pi$ | Fermion | Electron, quark |
| $1$ | $2$ | $2\pi$ | $2\pi$ | Vector boson | Photon, W/Z, gluon |
| $2$ | $4$ | $4\pi$ | $2\pi$ for an integer representation | Tensor proposal | Composite graviton |

The entries labelled periodicity belong to the added representation. The
canonical density-plane angle has no corresponding $4\pi$ physical-periodicity
statement.

### 2.3 Minimal-span selection

The conversion fixed point is

$$
E_Y=\varphi E_I,
$$

and the cascade scale ratio is $\ell_{n+1}/\ell_n=\varphi$. An optional
adjacent-rung interpretation identifies this ratio with a selected span
$\Delta n=1$, giving $s=1/2$ under the added map. The selection is a
minimal-span principle, not a consequence of the density ratio alone:

$$
\boxed{\Delta n=1\quad\Longrightarrow\quad s=\frac12
\quad\text{(optional minimal-span rule).}}
$$

The fixed-point excess

$$
\alpha_0=\frac{\pi}{\rho}=\varphi^{-3}
$$

is a density ratio with scale reading three rungs,
$\varphi^{-3}=\ell_{n-3}/\ell_n$, and the associated crossover is
$\sigma=\ell_{\mathrm{Pl}}/\varphi^3$ at rung $-3$. It is distinct from the
optional one-rung span. `computations/spin_doublet_minimal_span.py` reports
$\log_\varphi(\varphi)=1$ rung and
$\log_\varphi(\varphi^3)=3$ rungs. Those logarithms are scale bookkeeping;
they do not create an angular clock.

The minimal-span rule also proposes that a $2$-rung closing cycle is a gauge
content and that a $4$-rung state is composite. Specific particle assignments
remain Hypothesized.

### 2.4 Spin-$3/2$ boundary

The optional half-angle representation admits $\Delta n=3$ and
$\Delta\vartheta=3\pi$. Its parity agrees with the $\Delta n=1$ class because
$3\equiv1\pmod2$; the microcascade mirror preserves every span. Under the
additional minimal-span rule,

$$
\Delta n=3=1+2
$$

is read as an optional fermion span plus one optional gauge cycle, so it is
classified as composite. The observed absence of a fundamental spin-$3/2$
state remains an empirical statement. A fundamental spin-$3/2$ observation
would test the minimal-span postulate rather than the canonical conversion
ODE.

---

## 3. Optional Fibonacci self-similarity

### 3.1 Nested scale construction

An added spiral can be repeated at each supporting rung:

$$
\chi_i(r_c)=\chi_0+\frac{2\pi}{\ln\varphi}
\ln\!\left(\frac{r_c}{\ell_i}\right),
\qquad i=0,1,\ldots,n.
$$

The statement that each rung's endpoint joins the next rung's start and that
zooming by $\varphi$ reproduces the local curve is a self-similarity postulate
for the added geometry. It does not follow from the measured density-plane
relaxation.

With one copy per $\varphi$ scaling, the associated curve count gives the
formal value

$$
D=\frac{\ln\varphi}{\ln\varphi}=1.
$$

This is the dimension of the idealized curve in the added doublet plane; an
effective dimension for an embedding in physical space plus an internal
coordinate requires a separate embedding definition.

The figure record in `visual-explainers/fractal_zoom.png` describes three
panels: $\varphi$-spaced cascade rings with
$I(\rho)=2[1-\cos(2\pi\rho)]$, a Qi-bubble deep zoom with elliptical
$\varphi:1$ cross-section and two five-arm spiral poles, and a pole zoom with
golden-angle arms. These are visualization and geometry records, not PDE
proof of compact phase.

### 3.2 Sampling and Fibonacci ratios

For the optional logarithmic curve,

$$
 r(\chi)=\ell_n\exp\!\left[
 \frac{\ln\varphi}{2\pi}(\chi-\chi_n)\right].
$$

Sampling at $\Delta\chi=2\pi$ gives
$r_{k+1}/r_k=\varphi\approx1.618$; quarter-turn sampling gives
$r_{k+1}/r_k=\varphi^{1/4}\approx1.128$ and
$r_{k+4}/r_k=\varphi\approx1.618$. The resulting geometric sequence has
Fibonacci-ratio asymptotics through the usual Binet relation. This is a
property of the chosen scale-coordinate construction.

The proposed biological reading associates macroscopic phyllotaxis with
$\varphi$-spaced condensation scales near $n\approx142$–$168$. That mapping
is Hypothesized and does not claim that biology or the canonical PDE selects
an internal phase.

---

## 4. Optional exchange and Pauli interpretations

### 4.1 Exchange phase

If the added variable is coupled to a quantum exchange representation, one may
postulate

$$
\psi\longmapsto e^{is2\pi}\psi=(-1)^{2s}\psi.
$$

Integer and half-integer assignments then give the usual symmetric and
antisymmetric exchange factors. This is a proposed quantum representation;
the real density conversion equations do not prove the spin-statistics
theorem.

### 4.2 Pauli boundary condition

A further model may impose antisymmetry on two identical added spinor states.
The resulting opposite-spin condition and Pauli exclusion are boundary
conditions of that quantum extension. They cannot be inferred from two real
positive densities occupying one spatial grid point, and they require an
explicit many-body state space.

---

## 5. Testable form-factor consequence

If the optional spiral fractal is part of a particle's charge distribution,
its proposed form factor is

$$
\boxed{
F(q^2)=F_0(q^2)\left[
1+A\cos\!\left(2\pi
\frac{\ln(q/\Lambda_{\mathrm{QCD}})}{\ln\varphi}+\delta\right)+\cdots\right]}.
$$

Here $A$ and $\delta$ are additional fit quantities. The predicted period is
$\Delta(\ln q)=\ln\varphi\approx0.4812$.

| Observable | Optional prediction | Status |
|---|---|---|
| Proton $F_1(q^2)$ | Log-periodic oscillations with $\Delta(\ln q)=\ln\varphi$ | Testable with JLab/ELC $ep$ data |
| Proton $F_2(q^2)$ | Same period with a different phase | Joint fit |
| Neutron $F_1(q^2)$ | Same period with a different amplitude | Deuteron/quasi-elastic test |
| Pion $F_\pi(q^2)$ | Period break near $q\sim\Lambda_{\mathrm{QCD}}$ | JLab 12 GeV test |
| $\Delta(1232)$ transition form factor | Enhanced amplitude from proposed orbital winding | CLAS/MAID analysis |

This is a falsifiable extension, not a prediction forced by
$\theta_d=\operatorname{atan2}(E_I,E_Y)$.

---

## 6. Relation to the coherence-budget comparison

| | Proton decay | Annihilation | Measurement | Optional spin construction |
|---|---|---|---|---|
| What is sampled | All 92 rungs, random | All 92 rungs, anti-phase | One rung, phase-matched | Added winding across selected rungs |
| Timescale input | Cascade product | Single-cycle | Single-cycle | Added pitch $2\pi/\ln\varphi$ |
| Optional quantized quantity | N/A | N/A | Born rule $|\alpha|^2$ | $s=\Delta\vartheta/(2\pi)=\Delta n/2$ |
| What persists | Proton itself | Nothing | Post-collapse branch | Added spiral geometry if postulated |

The proton record quotes a coherence lifetime of $10^{910}$ years and a
coherence depth of approximately 92 rungs. Reading a $\pi$ increment across
that depth, or assigning spin-$1/2$ to a quark, requires the optional compact
coordinate and minimal-span rules. The lifetime and rung count themselves do
not supply those rules.

---

## 7. Epistemic boundaries

### Canonical and measured

- The solver state is two real densities $(E_Y,E_I)$.
- Conversion conserves $\rho$ in its equal-and-opposite contribution and
  moves $\theta_d=\operatorname{atan2}(E_I,E_Y)$ monotonically toward
  $\operatorname{atan}(\varphi^{-1})$.
- The two-pole PDE test has $m=2$ angular dominance, no detectable $m=5$
  dynamic mode, and $d\phi/dt\sim1.5\times10^{-4}$ rad/step versus the
  tested $\lambda=0.02$ expectation.
- The golden-angle five-arm ellipsoid pattern is a geometric visualization
  record.
- The exact sign-flip ratios in §2.1 are arithmetic checks of the added
  complex ansatz.

### Hypothesized additional structure

- Compact $\chi$, a logarithmic Fibonacci pitch, and any chosen
  $P_\parallel$.
- A complex amplitude, half-angle lift, $4\pi$ periodicity, and the proposed
  map $s=\Delta n/2$.
- The adjacent-rung minimal-span rule, particle assignments, and the
  composite interpretation of higher spans.
- Spin-statistics and Pauli interpretations coupled to a many-body quantum
  state space.
- The form-factor log-periodicity with period $\ln\varphi$.

### Speculative

- Biological phyllotaxis as a direct expression of the added compact geometry.
- Numerical values for the form-factor amplitude $A$ and phase $\delta$.

The optional constructions are useful only with their extra variables and
selection rules named. None changes the canonical conversion numerics or
turns the density-plane angle into an independent phase clock.

---

## References

- `foundations/cassi-first-principles.md`—canonical two-fluid state, gate, and density-plane angle rate
- `foundations/qi-flow-double-helix.md`—spatial density-plane diagnostic and optional double-helix embedding
- `foundations/spiral-dynamics.md`—optional scale-coordinate clock and separate Hubble/gravity diagnostics
- `foundations/proton-coherence-budget.md`—proton stability and cascade coherence
- `foundations/quantum-measurement-derivation.md`—measurement and Born-rule context
- `foundations/why-three-dimensions.md`—Frenet–Serret and triaxial geometry
- `foundations/dimensionful-cascade.md`—cascade table and rung spacings
- `predictions/falsifiable-predictions.md`—cosmological $\ln\varphi$-periodic prediction catalog
- `open-questions-cassi-answers.md`—Q7, Q9, and Q10 status entries
- `visual-explainers/fibonacci_bubble_spiral.py`—golden-angle ellipsoid geometry
- `visual-explainers/fractal_zoom.py`—optional fractal visualization
- `computations/spin_doublet_half_angle.py`—arithmetic check of the added half-angle ansatz
- `computations/spin_doublet_minimal_span.py`—optional span bookkeeping and parity checks
- `foundations/rung-offset-mechanism.md`—fractional-rung catalog
- `foundations/microcascade-mirror.md`—scale-reflection diagnostic
- `two-fluid/run_pde_bubble_spiral.py`—two-pole PDE test
