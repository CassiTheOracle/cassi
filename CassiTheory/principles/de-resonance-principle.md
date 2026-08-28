# The De-Resonance Principle in Cassi

## Status: Derived number-theory identity and conditional counterflow phase-selection theorem / Hypothesized physical realization—August 2026

## Abstract

The continued fraction $\varphi=[1;1,1,\ldots]$ and its sharp
Hurwitz/Lagrange approximation constant are established number-theory facts.
In the standard integer fractional-linear equivalence class, $\varphi$ is the
conventional positive representative of the worst-approximable class. The
canonical density-conversion target

$$
\boxed{r_\star\equiv\frac{E_Y}{E_I}=\varphi}
$$

is a declared model postulate and solver input. The selected conversion law
conditionally relaxes a homogeneous parcel toward that target. With the
additional compact-phase assumptions of counteroriented strand currents,
equal mobilities, zero net current, and adiabatic current adjustment, the same
relaxation also selects the phase-gradient magnitude ratio
$\alpha=\theta_I'/\theta_Y'\to\varphi$. Compact winding identifies Fibonacci
record near-closures to the irrational local target. Physical realization of
the phase-current closure and suppression of resonance remain testable
hypotheses.

## 0. Scope: arithmetic datum and physical proposal

The arithmetic statement and the physical interpretation have separate epistemic status.

| Layer | Statement | Status in this paper |
|-------|-----------|----------------------|
| Number theory | $\varphi=(1+\sqrt{5})/2=[1;1,1,\ldots]$ and the sharp Hurwitz/Lagrange approximation result | **Derived number-theory identity / standard theorem** |
| Cassi target | The canonical density-conversion target is $r_\star=E_Y/E_I=\varphi$ | **Hypothesized model postulate / solver input** |
| Density relaxation | The selected homogeneous conversion law approaches $r_\star$ under persistent positive gate exposure | **Derived conditional on the selected conversion law** |
| Counterflow bridge | Equal-mobility, zero-net-current counterflow gives $\alpha=E_Y/E_I\to\varphi$ | **Derived conditional on the compact-phase current closure** |
| Compact topology | A continuous nonzero scalar amplitude on $S^1$ conserves integer winding; changing sector requires a phase slip or altered boundary, topology, or bundle structure | **Derived topological identity** |
| Physical realization | Separate compact phases, equal strand mobilities, zero net current, adiabatic adjustment, and reduced phase locking occur in the physical field | **Hypothesized** |
| Correction catalogue | Measured anchors and calculated comparisons, with quantity provenance and mechanism tiers stated below | Mixed; see the row-level labels |

The target $r_\star$ enters through the selected conversion operator. The
conditional phase theorem introduces no second $\varphi$ input: it projects
the density ratio into a phase-gradient ratio through a stated current
closure. A physical attractor claim still requires a declared parameter
region, an open set of initial conditions, and observables for the currents,
phase locking, and spectral transfer.

## 1. The arithmetic statement and resonance scope

### 1.1 Continued fraction and extremal approximation—**Derived number theory**

The golden ratio is the positive solution of the fixed-point equation for the all-one continued fraction:

$$
x=1+\frac{1}{x}
\quad\Longrightarrow\quad
x^2-x-1=0
\quad\Longrightarrow\quad
x=\varphi=\frac{1+\sqrt{5}}{2}.
$$

With $F_0=0$, $F_1=1$, and $F_{k+1}=F_k+F_{k-1}$, the convergents of $[1;1,1,\ldots]$ follow the Fibonacci ratios (after the initial convention):

$$
\frac{1}{1},\ \frac{2}{1},\ \frac{3}{2},\ \frac{5}{3},\ \frac{8}{5},\ \frac{13}{8},\ldots
$$

For an irrational $x$, let $\|qx\|$ denote the distance from $qx$ to the nearest integer and define the approximation constant

$$
\mu(x)\equiv\liminf_{q\to\infty}q\|qx\|.
$$

The standard Hurwitz theorem and the sharp equality case give

$$
\mu(x)\leq\frac{1}{\sqrt{5}}
\quad\text{for every irrational }x,
\qquad
\mu(\varphi)=\frac{1}{\sqrt{5}}.
$$

Larger $\mu$ means poorer asymptotic rational approximation in this convention, so $\varphi$ is extremal or worst approximable in the standard Hurwitz/Lagrange sense. The extremal status belongs to an equivalence class: for

$$
T(x)=\frac{a x+b}{c x+d},
\qquad
a,b,c,d\in\mathbb{Z},
\qquad
ad-bc=\pm1,
$$

the integer fractional-linear equivalents of $\varphi$ have the same standard asymptotic class. This paper uses the positive $\varphi$ representative as a convention. A uniqueness statement requires that equivalence convention and a specified domain; the arithmetic result supplies no preferred physical coordinate by itself.

The phrase “maximally irrational” is used here only for this approximation metric. It carries an arithmetic meaning and no automatic dynamical meaning.

### 1.2 What the arithmetic result says about resonance

In a coupled-oscillator model, a rational frequency ratio supplies exact commensurability and can enable resonant terms. Energy concentration, phase locking, or transfer to a particular scale then depends on forcing, detuning, nonlinear couplings, damping, geometry, and initial conditions. A rational ratio alone does not determine collapse of a multi-scale state.

An irrational ratio removes exact commensurability for that scalar pair, while near-rational approximants can still produce long finite-time interactions. Nonlinear combination frequencies and parametric resonances require their own analysis. The extremal approximation property of $\varphi$ limits one arithmetic route to close rational approximation; it does not universally prevent resonance locking or guarantee persistent multi-scale structure.

### 1.3 Canonical density selection—**Derived conditional**

For a homogeneous conversion-only parcel, write

$$
\rho=E_Y+E_I,
\qquad
\varepsilon=E_Y-\varphi E_I,
\qquad
\kappa(t)=\lambda[1-q(t)]\geq0.
$$

The selected conversion contribution obeys

$$
\dot E_Y=-\kappa\varepsilon,
\qquad
\dot E_I=+\kappa\varepsilon,
$$

and therefore

$$
\dot\rho=0,
\qquad
\dot\varepsilon=-\kappa(1+\varphi)\varepsilon
=-\kappa\varphi^2\varepsilon.
$$

For accumulated exposure $K(t)=\int_0^t\kappa(u)\,du$,

$$
\varepsilon(t)=\varepsilon_0e^{-\varphi^2K(t)},
\qquad
\frac{E_Y}{E_I}
=\frac{\varphi\rho+\varepsilon(t)}{\rho-\varepsilon(t)}.
$$

Whenever $E_I>0$, the ratio $r=E_Y/E_I$ satisfies the projective flow

$$
\boxed{\dot r=-\kappa(1+r)(r-\varphi)}.
$$

The positive fixed point is asymptotically stable when
$K(t)\to\infty$. Finite exposure leaves a finite residual, and $\kappa=0$
freezes the current ratio. The result establishes selection by the declared
conversion operator; the occurrence of that operator in nature retains the
model-postulate status in §0.

### 1.4 Counterflow phase selection—**Derived conditional**

Use the compact phase coordinates of
`foundations/qi-loop-mass-cascade.md`. Let
$k_Y=\partial_s\theta_Y>0$ and $k_I=\partial_s\theta_I>0$ denote phase-gradient
magnitudes measured along each strand's own orientation. For opposite physical
strand orientations and positive mobilities $\mu_Y,\mu_I$, define the signed
currents

$$
J_Y=+\mu_YE_Yk_Y,
\qquad
J_I=-\mu_IE_Ik_I.
$$

If $J_0=J_Y+J_I$ is the imposed net current, then

$$
\alpha\equiv\frac{k_I}{k_Y}
=\frac{\mu_Y}{\mu_I}\frac{E_Y}{E_I}
-\frac{J_0}{\mu_IE_Ik_Y}.
$$

The equal-mobility, zero-net-current closure gives the exact identity

$$
\boxed{\alpha=r}.
$$

Adiabatic enforcement of that closure along the conversion trajectory gives

$$
\boxed{\dot\alpha=-\kappa(1+\alpha)(\alpha-\varphi)},
\qquad
\alpha(t)=
\frac{\varphi\rho+\varepsilon_0e^{-\varphi^2K(t)}}
{\rho-\varepsilon_0e^{-\varphi^2K(t)}}.
$$

Thus the canonical density target becomes a dynamically selected local
continuum phase-gradient target under the added closure. On a common ordinary
compact loop, uniform single-valued phases require

$$
\alpha=\frac{q_{\rm w}}{p},
\qquad p,q_{\rm w}\in\mathbb Z_{>0}.
$$

The irrational target has no exact finite-winding closure. Its record
near-closures are the Fibonacci pairs
$(p,q_{\rm w})=(F_n,F_{n+1})$, with

$$
F_{n+1}-\varphi F_n=(-1)^n\varphi^{-n}.
$$

Fixed integers $(p,q_{\rm w})$ make the uniform compact ratio discrete and
time independent. Continuous tracking of $\alpha(t)$ therefore applies to
local or noncompact gradients, or else requires phase slips that change the
winding sector. The arithmetic identifies the record candidates; a physical
energy, dissipation, or transition law must choose among them.

This supplies a direct conditional chain from density conversion to the
Fibonacci compact candidates. The compact phases, common loop geometry,
opposite strand orientation, current constitutive law, equal mobilities, zero
net current, adiabatic adjustment, and any required winding-sector dynamics
are the explicit physical assumptions.

#### Topological winding boundary—**Derived**

The need for a sector transition is exact under the ordinary scalar-loop
assumptions. Let
$\psi_a:S^1\times[t_0,t_1]\to\mathbb C\setminus\{0\}$ be jointly continuous
and piecewise smooth in $\chi$, with
$\psi_a=\sqrt{f_a}\,e^{i\theta_a}$. At each time,

$$
w_a(t)
:=
\frac{1}{2\pi i}
\oint_{S^1}\psi_a^{-1}\partial_\chi\psi_a\,d\chi
=
\deg\!\left(\frac{\psi_a}{|\psi_a|}\right)
\in\mathbb Z,
\qquad a\in\{Y,I\}.
$$

The joint nonvanishing evolution is a homotopy in
$\mathbb C\setminus\{0\}$, so $w_a$ is invariant. For a smooth evolution the
same result follows directly:

$$
\dot w_a
=
\frac{1}{2\pi i}
\oint_{S^1}
\partial_\chi\!\left(\psi_a^{-1}\partial_t\psi_a\right)d\chi
=0.
$$

Therefore a finite compact pair $(p,q_{\rm w})$ cannot continuously track the
changing continuum target. A sector change requires an amplitude zero—a phase
slip—or a change of boundary conditions, topology, or bundle structure. With
a gauge connection, a gauge-covariant circulation or holonomy replaces the
scalar winding above.

This proves the necessity of a transition event, not its rate, direction, or
energetic preference. The next physical frontier is a microscopic
complex-amplitude law that generates the counteroriented currents and their
effective mobilities, permits and selects phase slips, and still projects to
the canonical real-density equations. The present density and population
laws cannot supply that result because their projections discard phase and
winding.

### 1.5 Frozen verification and controls

`computations/phi-counterflow-selection-pre-registration.md` freezes seven
gates for the algebra, transient, stability, exposure boundary, constitutive
controls, and compact approximation sequence.
`computations/verify_phi_counterflow_selection.py` passes PC1–PC7 on the first
protocol-complete execution recorded in
`computations/phi-counterflow-selection-report.md`. The maximum transient
residual against the exact
solution is $4.441\times10^{-16}$; the projective-flow residual is
$1.110\times10^{-16}$; and the Fibonacci identity residual through
$p=144$ is $1.017\times10^{-14}$.

The controls delimit the theorem. A mobility ratio
$m=\mu_Y/\mu_I$ shifts the fixed phase ratio to $m\varphi$. A nonzero
through-current adds
$-J_0/(\mu_IE_Ik_Y)$. Finite accumulated exposure preserves a nonzero
initial-condition residual. The attracting density states form a line indexed
by the conserved $\rho$; ratio stability holds within each fixed-$\rho$
sector. Full PDE terms can alter the local density trajectory. Fixed compact
windings require phase slips or another sector-transition mechanism to follow
the continuum target. Measurements of the separate currents, phase locking,
spectral transfer, and winding transitions decide whether the conditional
closure describes the physical field.

## 2. Cassi framework posture

The $\varphi$-power expressions below are working baselines for selected quantities. They are model ansätze whose physical scope must be stated for each sector.

| Quantity or sector | Cassi working expression | Status |
|--------------------|-------------------------|--------|
| Canonical density-conversion target | $r_\star=E_Y/E_I=\varphi$ | **Hypothesized postulate / solver input** |
| Selected dimensionless quantities | near a $\varphi$-power, with deviations determined by dynamics | **Hypothesized ansatz** |
| $v_0$ | $M_{\rm Pl}\cdot\varphi^{-80}\cdot(1+\text{correction})$ | **Hypothesized baseline** |
| $m_e$ | $v_0\cdot\varphi^{-26}/\sqrt{2}\cdot(1+\text{correction})$ | **Hypothesized baseline** |
| $\sin^2\theta_W$ | $\varphi^{-3}\cdot(1+\text{correction})$ | **Hypothesized baseline; running calculation below** |

The phrase “near a $\varphi$-power” is a selection rule for the declared Cassi set, with a tolerance and a null model still required. It is not a universal assertion about every dimensionless observable.

## 3. Empirical pattern of corrections

The table is a catalogue of offsets from the chosen baselines. Let $B$ be the baseline and $M$ the measured value, and define

$$
\delta\equiv\frac{M-B}{B},
\qquad
M=B(1+\delta).
$$

| Quantity | Nearest $\varphi$-power baseline $B$ | Measured $M$ | Relative offset $\delta=(M-B)/B$ | Quantity provenance | Mechanism tier |
|----------|--------------------------------------|--------------|-----------------------------------|---------------------|----------------|
| $\sin^2\theta_W$ | $\varphi^{-3}=0.236$ | $0.23122$ | $-2.1\%$ (the baseline is $+2.1\%$ above measured) | Calibrated observation anchor; Mapped running comparison | Mapped conditional; physical interpretation Hypothesized |
| $v_0/M_{\rm Pl}$ | $\varphi^{-80}=1.91\times10^{-17}$ | $2.02\times10^{-17}$ | $+5.6\%$ from direct/raw anchors; catalog rounded comparison $+5.3\%$ | Calibrated observation anchor; Mapped baseline exponent | Hypothesized mechanism |
| $m_e$ | $v_0\varphi^{-26}/\sqrt{2}=0.64$ MeV | $0.511$ MeV | $-20\%$ | Calibrated observation anchor; Mapped baseline exponent | Speculative |
| $\alpha_s(M_Z)$ | $0.058$ (SM RGE) | $0.118$ | $+103\%$ (approximately $\times2.0$) | Calibrated observation anchor (`standard-model/sm-radiative-corrections.md` §2); Mapped $\Delta b=1.70$ input (ongoing) | Speculative |

The scalar logarithmic rung offset associated with a multiplicative correction is

$$
\boxed{\delta n\equiv\frac{\ln(1+\delta)}{\ln\varphi}
=\log_\varphi\!\left(\frac{M}{B}\right).}
$$

This $\delta n$ measures a scalar displacement in logarithmic $\varphi$-rung units. It has no phase units. An identification such as $\delta n=\Delta\theta/(2\pi)$, or any other two-fluid phase-lag interpretation, is **Hypothesized** and requires a separately defined observation/constitutive map connecting the scalar observable to local field phases. The rung-offset program (`foundations/rung-offset-mechanism.md`) proposes such a correspondence; the table itself uses only the logarithmic definition.

The quantity-provenance labels have the following scope:

- **External**—a source value or constant is taken from outside the Cassi
  derivation.
- **Calibrated**—an observation anchors the comparison.
- **Mapped**—a fitted or selected relation, exponent, or bookkeeping input is
  recorded; an ongoing mapping is marked explicitly.
- Mechanism tiers remain **Derived**, **Hypothesized**, or **Speculative** as
  stated in each row; provenance is not itself a mechanism tier.

The offsets in this sample range from about $2\%$ to about $20\%$, with the QCD comparison near a factor of two. This is a descriptive grouping of the listed rows. It does not establish a monotonic relation between offset size and attractor strength, scale, or de-resonance. Such a relation requires a declared observable set, tolerance, and null comparison.
## 4. Physical origin of each correction

### 4.1 $\sin^2\theta_W$ ($2.1\%$ baseline offset at $m_Z$)—**Mapped conditional running; Hypothesized Cassi interpretation**

The chosen baseline gives $\sin^2\theta_W=\varphi^{-3}=0.23607$. The measured
MS-bar value at $m_Z$ is $0.23122$, so the baseline is $+2.1\%$ above the
measurement. The quoted running calculation reaches $\varphi^{-3}$ at
$\mu_*\approx233$ GeV. The angle runs upward with energy ($0.43$ at
$2\times10^{16}$ GeV in the SM and $0.38$ in the MSSM variant), so this is an
IR matching statement rather than a GUT-scale boundary condition
(`standard-model/sm-radiative-corrections.md` §3.3). Interpreting the
matching value as a physical de-resonance target remains Hypothesized.

### 4.2 $v_0/M_{\rm Pl}$ ($5.3\%$ correction)—**Hypothesized; mechanism unidentified**

If the Cassi potential is evaluated at its declared $\varphi$ target, its
equilibrium relation is

$$
v_0^2=-\frac{\mu^2}{g}.
$$

Within that stationary-point algebra, $v_0$ is independent of $\lambda$.
The residual is convention-dependent. Using the displayed direct/raw anchors
$M_{\rm Pl}=1.22\times10^{19}\,\mathrm{GeV}$ and $v_0=246\,\mathrm{GeV}$
gives $N_{\rm raw}=\log_\varphi(M_{\rm Pl}/v_0)\approx79.89$ and a
nearest-integer comparison of approximately $5.6\%$ to $\varphi^{-80}$.
The table's displayed ratios are rounded; the catalog's rounded $5.3\%$
entry uses its declared rounded ratio. The gap-adjusted cascade convention
is a separate quantity,
$N_g=\log_\varphi(gM_{\rm Pl}/v_0)\approx79.7$ with
$g=1-\varphi^{-5}$ (`foundations/dimensionful-cascade.md` §2.1). Neither
convention supplies a computed physical correction.

Plausible candidate mechanisms remain:

- **Threshold corrections at the matching scale** from heavy-particle finite
  shifts.
- **RGE running of $v_0$** in the Cassi SU(2) framework, with the sign still
  requiring analysis.
- **The exact target value** versus the nearest integer power is a
  convention-dependent baseline comparison, not a correction mechanism.

See `principles/v0-hierarchy-problem.md` for the full analysis. None of these
candidates has a completed calculation in the Cassi framework, so the physical
correction remains Hypothesized.

### 4.3 $m_e$ (observed $-20\%$ baseline offset; candidate mixing scale $\sim25\%$)—**Speculative**

The $\varphi$-power expression is the no-mixing baseline. A flavor-mixing
interpretation assigns the measured offset to mixing among the three lepton
families. A specified CKM-like ansatz could produce a correction of order
$25\%$, while the actual magnitude and sign require a specified lepton mixing
matrix and calculation. The current row supports a test proposal rather than a
completed mechanism.


### 4.4 $\alpha_s(M_Z)$ (approximately $\times2.0$ correction)—**Speculative**

The one-loop $\alpha_s$ estimate from the chosen boundary

$$
\alpha_{\rm GUT}=\frac{\varphi^{-3}}{4\pi}
$$

depends on the particle content between $M_{\rm GUT}$ and $m_Z$. With the
Standard Model coefficient $b_0=7$ for $n_f=6$, the quoted running gives
$\alpha_s(M_Z)\approx0.058$, compared with the measured $0.118$.

Closing this numerical gap would require $\Delta b=1.70$, with candidate
spectra such as a vector-like colored fermion pair, two colored scalars, or
about three KK levels of a gluon. The $\alpha_s$ RGE depends on the full
particle spectrum; this candidate spectrum is a particle-content hypothesis
and receives no direct derivation from the irrationality of $\varphi$.

## 5. Testable consequences of the Hypothesized mapping

These are conditional proposals. Their tolerances are working specifications,
not consequences of the number-theory theorem.

### 5.1 Precision electroweak

Future precision electroweak measurements can compare the Z-pole value with
the $\varphi^{-3}$ baseline: the baseline is currently $+2.1\%$ above the
measured value, and the running angle reaches the baseline at
$\mu_*\approx233$ GeV. A specified RGE and threshold model can be confronted
with the residual shift. A discrepancy beyond the computed running would
challenge that model instance and motivate threshold tests.

### 5.2 New scalar discoveries (unregistered proposal)

For a newly discovered scalar with mass $M_X$ and coupling $y_X$ to the
Standard Model Higgs, a proposed ansatz is

$$
y_X\approx\varphi^{-n}(1+\delta),\qquad |\delta|<0.3,
$$

for an integer $n$ assigned from the field's declared role. The role-to-$n$
map, tolerance, and comparison set must be fixed before using a measurement.
No such role-to-$n$ map is registered here.

### 5.3 Future precision lepton-sector observables (unregistered proposal)

The flavor-mixing hypothesis becomes calculable once the full lepton mixing
matrix and the relevant renormalization prescription are specified. A residual
larger than $30\%$ could challenge flavor mixing as the dominant correction
under that stated model and tolerance. Other mechanisms remain separate
hypotheses.

### 5.4 GUT-scale $\alpha_s$ (unregistered proposal)

If a future GUT-scale determination of $\alpha_s$ lies within $10\%$ of
$\varphi^{-3}/(4\pi)$, it could support the particular boundary relation
together with the associated SUSY/KK running explanation. A significantly
different value would disfavor that boundary/spectrum combination and require
a new scale assignment.

## 6. Implications for the TOE

The Cassi proposal has four distinct layers.

1. The arithmetic input is the extremal rational-approximation property of
   the golden-ratio equivalence class.
2. The model postulate is the canonical target
   $r_\star=E_Y/E_I=\varphi$ used in the density conversion and solver.
3. The conditional theorem maps the selected density relaxation to
   $\alpha\to\varphi$ under equal-mobility, zero-net-current counterflow and
   identifies the Fibonacci record approximants imposed by compact closure.
4. The physical hypothesis assigns that closure and a winding-sector
   transition law to the Yang/Yin field and predicts measurable phase-locking
   and spectral-transfer behavior.

Selected dimensionless couplings may be organized near $\varphi$-power
baselines, while RGE running, thresholds, flavor mixing, and particle content
supply corrections. Each application retains its own declared observable,
tolerance, and mechanism.

## 7. Conclusion

The number-theory result fixes the arithmetic meaning of de-resonance. The
counterflow theorem supplies the missing conditional bridge from the
canonical density target to the compact phase-gradient target:

$$
E_Y/E_I\longrightarrow\varphi,
\qquad
J_Y+J_I=0,\ \mu_Y=\mu_I
\quad\Longrightarrow\quad
\theta_I'/\theta_Y'\longrightarrow\varphi.
$$

Finite compact closure has Fibonacci record near-windings. Physical selection
among those discrete sectors requires an energy, dissipation, or phase-slip
law. The remaining physics problem is sharply localized: determine whether
the two fluids carry the required counteroriented compact currents with equal
effective mobility, whether winding transitions occur, and whether their
measured dynamics reduce phase locking relative to predeclared rational and
irrational controls.

## References

- `foundations/phi-rg-formalism.md`—Hypothesized discrete-$\varphi$ renormalization-group construction and proposed physical flow.
- `computations/phi-counterflow-selection-pre-registration.md`—Frozen PC1–PC7 algebra, stability, exposure, control, and compact-closure gates.
- `computations/verify_phi_counterflow_selection.py`—Independent standard-library execution of the frozen gates.
- `computations/phi-counterflow-selection-report.md`—Protocol-complete PC1–PC7 ledger and epistemic boundary.
- `foundations/rung-offset-mechanism.md`—Hypothesized correspondence between fractional rung offsets and two-fluid phase variables.
- `principles/v0-hierarchy-problem.md`—Analysis of the $v_0$ hierarchy offset and candidate mechanisms.
- `standard-model/sm-radiative-corrections.md` §§2–3.2—PDG 2024 input $\alpha_s(m_Z)=0.1180(9)$ and the one-/two-loop $\varphi$-boundary running comparison; numerical provenance `computations/sm_radiative_corrections.py`.
- J. W. S. Cassels, *An Introduction to Diophantine Approximation*,
  Cambridge Tracts in Mathematics and Mathematical Physics 45, Cambridge
  University Press (1957), Chapter I, §§5–6 (Hurwitz theorem and the
  golden-ratio equality case); Cambridge excerpt:
  https://assets.cambridge.org/97805210/45872/excerpt/9780521045872_excerpt.pdf
- The equality $\mu(\varphi)=1/\sqrt{5}$ is used in the standard
  Hurwitz/Lagrange form stated by Cassels, Chapter I, §§5–6, under the
  explicit equivalence convention in §1.1; no Cassi dynamical consequence is
  inferred from the arithmetic identity.
