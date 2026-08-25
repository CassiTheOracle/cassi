# The De-Resonance Principle in Cassi

## Status: Derived number-theory identity / Hypothesized physical de-resonance mapping—August 2026

## Abstract

The continued fraction $\varphi=[1;1,1,\ldots]$ and its sharp Hurwitz/Lagrange approximation constant are established number-theory facts. In the standard integer fractional-linear equivalence class, $\varphi$ is the conventional positive representative of the worst-approximable class. Cassi uses that arithmetic property to motivate a physical proposal. Its canonical density-conversion target

$$\boxed{r_\star \equiv \frac{E_Y}{E_I}=\varphi}$$

is a declared model postulate and solver input. A physical attractor, suppression of phase locking, a coupling flow, or survival of multi-scale structure requires specified dynamics and observables; arithmetic extremality alone does not establish those outcomes. The correction table records the $\varphi$-power baselines used in the proposal, their measured offsets, and candidate mechanisms. The de-resonance mapping remains a concrete, testable Cassi hypothesis.

## 0. Scope: arithmetic datum and physical proposal

The arithmetic statement and the physical interpretation have separate epistemic status.

| Layer | Statement | Status in this paper |
|-------|-----------|----------------------|
| Number theory | $\varphi=(1+\sqrt{5})/2=[1;1,1,\ldots]$ and the sharp Hurwitz/Lagrange approximation result | **Derived number-theory identity / standard theorem** |
| Cassi target | The canonical density-conversion target is $r_\star=E_Y/E_I=\varphi$ | **Hypothesized model postulate / solver input** |
| Physical mapping | The two-fluid dynamics may select $r_\star$, reduce phase locking, and organize scales near $\varphi$-powers | **Hypothesized** |
| Correction catalogue | Measured anchors and calculated comparisons, with quantity provenance and mechanism tiers stated below | Mixed; see the row-level labels |

The target $r_\star$ is therefore an input against which the equations can be tested. It is not a number-theory consequence. A candidate attractor claim has a definite form: for a declared parameter region and an open set of initial conditions, the computed ratio $r(t)$ approaches $r_\star$ and remains there within a stated tolerance. The same experiment must measure phase locking and spectral energy transfer, so that resonance behavior and scale retention are outcomes of the equations rather than assumptions.

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

### 1.3 The physical claim that remains to be tested

The Cassi proposal is that the two-fluid equations, with the declared target $r_\star=\varphi$, may possess a robust de-resonant regime. The hypothesis can be tested by varying $r(0)$ around $r_\star$, scanning damping and coupling parameters, and comparing the basin and long-time behavior with rational and other irrational controls. Evidence for the proposed mapping would include reproducible convergence to $r_\star$, a measured reduction in phase-locking intervals under predeclared conditions, and a quantified spectrum that retains energy across the selected scales. Each result needs a constitutive and observation map from field variables to the measured ratio, phase, and spectrum.

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

The Cassi proposal has a clear division between an arithmetic input and a physical hypothesis.

1. The arithmetic input is the extremal rational-approximation property of the golden-ratio equivalence class.
2. The model postulate is the canonical target $r_\star=E_Y/E_I=\varphi$ used in the density conversion and solver.
3. The physical hypothesis is that specified two-fluid dynamics can make this target a robust regime, with measurable effects on phase locking, coupling offsets, and scale transfer.

Within that posture, selected dimensionless couplings may be organized near $\varphi$-power baselines, while RGE running, thresholds, flavor mixing, and particle content supply corrections. The empirical table supplies a starting catalogue for those tests. It does not establish that every quantity has a $\varphi$-power baseline, that deviations are monotonic in scale, or that the same mechanism controls every sector.

The framework's predictive content therefore lies in declaring the target, the selected observable set, the tolerance, and the dynamics before a comparison. A successful de-resonance result would show convergence and spectral behavior in the equations under controls; a successful coupling result would reproduce the listed offsets with a specified mechanism; a failed comparison would delimit the proposal's domain.

## 7. Conclusion

The mathematical content of this paper is the continued-fraction identity for $\varphi$, its Fibonacci convergents, and the standard sharp rational-approximation result under an explicit equivalence convention. The Cassi physical content is a Hypothesized mapping that uses $\varphi$ as the declared density-conversion target and asks whether two-fluid dynamics select a de-resonant regime.
The proposal remains concrete: vary the initial ratio around $r_\star$, measure locking and spectral transfer, and compare with rational and irrational controls. Use $\delta n=\ln(1+\delta)/\ln\varphi$ as a scalar logarithmic rung offset. A phase interpretation requires its own observation/constitutive map. These tests determine whether the proposed attractor and correction mechanisms describe the dynamics; the arithmetic extremality alone sets their motivation.

## References

- `foundations/phi-rg-formalism.md`—Hypothesized discrete-$\varphi$ renormalization-group construction and proposed physical flow.
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
