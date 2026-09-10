# Interacting Chiral-Chromodielectric Baryon Protocol

## Status: Preregistered—September 2026

## Abstract

This protocol tests the next microscopic matter boundary left by the regular
quark–meson carrier and the finite-cutoff confining bridge. It combines their
essential roles in one supplied low-energy action: explicit two-flavour Dirac
quarks carry exact baryon number, chiral fields supply the regular spin-isospin
texture, and a chromodielectric field makes the asymptotic quark mass diverge
as its regulator is removed. The calculation asks whether three occupied
colours relax to a finite, localized, stationary and reduced-stability-qualified
baryon in this interacting action.

The action is empirical QCD content. Its field choice and parameters are not
derived from the canonical Cassi two-density law. A positive result therefore
establishes an existence and formation comparison inside the supplied action.
It cannot establish complete physical matter formation. That decision is
frozen as `ICB6=FAIL` and `complete_physical_matter_formation=false`.

## 1. Question and scope

### 1.1 Frozen question

Given one unit of baryon number in the supplied two-flavour
chiral-chromodielectric action, does a common three-colour valence level and its
interacting chiral and dielectric fields possess:

1. a regular finite-regulator Hamiltonian with exact conserved baryon current;
2. an isolated stationary localized endpoint;
3. stable regulator and radial-grid extrapolations;
4. positive dilation and volume-preserving affine shape curvatures; and
5. a reproducible basin of dissipative seeded formation?

The experiment does not begin from a zero-baryon vacuum. Baryon number is an
initial condition inherited from the measured cosmological asymmetry, exactly
as in `computations/qcd-quark-meson-carrier-prereg.md`. The formation claim is
therefore a fixed-$B=1$ collapse or relaxation claim.

### 1.2 What this can decide

A pass through ICB1–ICB5 supports a finite, interacting, colour-degenerate
baryon endpoint and a reduced dissipative route to it. It closes the artificial
separation between the regular quark–meson carrier and a confining field at the
level of this effective action.

### 1.3 What this cannot decide

The protocol contains no derivation of QCD, no Cassi selection rule for the
action, no renormalized Dirac determinant, no arbitrary-nonradial spectrum, no
unitary real-time thermal ensemble, no observable proton/neutron projection,
and no baryogenesis mechanism. It also uses a spherical hedgehog variational
family. These exclusions determine ICB6 before execution.

## 2. Frozen action and state

### 2.1 Fields and action

The supplied Minkowski action is

$$
\begin{aligned}
\mathcal L_{\rm ICB}={}&
\bar q\,i\gamma^\mu\partial_\mu q
+\frac12\partial_\mu\sigma\partial^\mu\sigma
+\frac12\partial_\mu\boldsymbol\pi\cdot\partial^\mu\boldsymbol\pi
-W(\sigma,\boldsymbol\pi)\\
&+\frac12\partial_\mu\chi\partial^\mu\chi-U(\chi)
-\frac{g}{\chi_\delta}\bar q
\left(\sigma+i\gamma^5\boldsymbol\tau\cdot\boldsymbol\pi\right)q,
\end{aligned}
$$

with

$$
\chi_\delta=\sqrt{\chi^2+\delta^2}.
$$

The positive regulator $\delta$ is removed through a frozen sequence. The
physical field is $\chi$; $\chi_\delta$ occurs only in the quark coupling.

The chiral potential is the vacuum-subtracted linear sigma model used by the
regular carrier:

$$
W-W_{\rm vac}
=\frac{m_\pi^2f_\pi^2}{2}\left[(s-1)^2+p^2\right]
+\frac{\lambda f_\pi^4}{4}(s^2+p^2-1)^2,
$$

where $s=\sigma/f_\pi$, $\boldsymbol\pi=f_\pi\hat{\mathbf r}p$ and

$$
\lambda=\frac{m_\sigma^2-m_\pi^2}{2f_\pi^2}.
$$

The chromodielectric potential follows the quartic CDM parameterization:

$$
U(\chi)=\frac12M_\chi^2\chi^2
\left[
1+\left(\frac{8\eta^4}{\gamma^2}-2\right)
\frac{\chi}{\gamma M_\chi}
+\left(1-\frac{6\eta^4}{\gamma^2}\right)
\frac{\chi^2}{(\gamma M_\chi)^2}
\right].
$$

It has the true vacuum at $\chi=0$ and a local stationary point at
$\chi=\gamma M_\chi$ with $U=(\eta M_\chi)^4$.

### 2.2 Frozen empirical parameters

| quantity | value | role |
|---|---:|---|
| $N_c$ | $3$ | occupied colour multiplicity |
| $f_\pi$ | $93.0\ {\rm MeV}$ | chiral vacuum scale |
| $m_\pi$ | $139.6\ {\rm MeV}$ | explicit chiral breaking |
| $m_\sigma$ | $1200\ {\rm MeV}$ | regular-carrier comparison value |
| $g$ | $23.0\ {\rm MeV}$ | CDM quark coupling |
| $M_\chi$ | $1700\ {\rm MeV}$ | chromodielectric mass |
| $\gamma$ | $0.2$ | local-minimum coordinate $\gamma M_\chi$ |
| $\eta$ | $0.12$ | bag-pressure scale $(\eta M_\chi)^4$ |
| $\hbar c$ | $197.3269804\ {\rm MeV\,fm}$ | unit conversion |

The values $g=0.023\ {\rm GeV}$, $M_\chi=1.7\ {\rm GeV}$,
$\gamma=0.2$ and $\eta=0.12$ are the published CDM comparison set. The
chiral constants preserve the already qualified regular-carrier comparison.
The combined list is an external empirical parameter choice.

### 2.3 Exact baryon current and occupied state

The global phase $q\mapsto e^{i\alpha}q$ gives

$$
J_B^\mu=\frac13\bar q\gamma^\mu q,
\qquad \partial_\mu J_B^\mu=0.
$$

Three colours occupy one normalized, nodeless, positive-energy grand-spin-zero
level. The colour wavefunction is antisymmetric, so the state has fermionic
$B=1$. Meson and chromodielectric fields are classical mean fields. The
normal-ordered empty constituent-quark state is the reference; the
renormalized negative-energy determinant is excluded.

### 2.4 Frozen hedgehog family

The chiral family is

$$
\begin{aligned}
\cos F(r)&=\frac{r^4-R_c^4}{r^4+R_c^4},\\
\sin F(r)&=\frac{2R_c^2r^2}{r^4+R_c^4},\\
s(r)&=1-a+a\cos F(r),\\
p(r)&=-a\sin F(r),
\end{aligned}
$$

and the chromodielectric field is

$$
\chi(r)=\chi_0\exp[-(r/R_\chi)^2].
$$

The four variational coordinates are

$$
\mathbf z=(a,R_c,\chi_0,R_\chi)
$$

with frozen bounds

$$
0\le a\le1,\quad
0.15\le R_c/{\rm fm}\le2.50,\quad
1\le\chi_0/{\rm MeV}\le510,\quad
0.15\le R_\chi/{\rm fm}\le2.50.
$$

The endpoints $a=0$ and $a=1$ are admissible chiral sectors. The other three
coordinates must finish at least two percent of their full bound width from a
bound for ICB2 to pass.

### 2.5 Radial Hamiltonian

On cell-centred radii $r_i=(i+1/2)\Delta r$, the weighted two-component radial
Hamiltonian is the same Hermitian Wilson-regularized operator qualified in
`computations/qcd-quark-meson-carrier-prereg.md`, with

$$
S_i=\frac{g f_\pi s_i}{\sqrt{\chi_i^2+\delta^2}},
\qquad
P_i=\frac{g f_\pi p_i}{\sqrt{\chi_i^2+\delta^2}}
$$

in place of $M_qs_i$ and $M_qp_i$. The derivative is centred in the interior,
uses the declared one-sided half-cell rows at the boundaries, and is similarity
transformed by $r_i\sqrt{\Delta r}$. A positive Wilson term

$$
H_W=\frac12\hbar c\,\Delta r\,D^TD
$$

lifts radial doublers. Twelve eigenpairs nearest zero are computed by symmetric
shift-invert iteration. The selected level is the lowest positive state whose
upper radial component has zero nodes over 99.9 percent of its probability.

### 2.6 Frozen energy

The endpoint energy is

$$
E(\mathbf z;\delta,N)=3\epsilon_0+E_{\sigma\pi}+E_\chi,
$$

where

$$
E_{\sigma\pi}=4\pi\int_0^{R_{\max}}r^2dr\left\{
\frac{f_\pi^2}{2\hbar c}
\left[(s')^2+(p')^2+\frac{2p^2}{r^2}\right]
+\frac{W-W_{\rm vac}}{(\hbar c)^3}\right\},
$$

and

$$
E_\chi=4\pi\int_0^{R_{\max}}r^2dr\left\{
\frac{(\chi')^2}{2\hbar c}+\frac{U(\chi)}{(\hbar c)^3}
\right\}.
$$

All integrals use composite Simpson quadrature on the cell-centred grid with
an explicitly reconstructed $r=0$ endpoint. The omitted tail is independently
bounded from the analytic Gaussian and algebraic chiral profiles.

## 3. Frozen numerical calculation

### 3.1 Primary solve

The primary box and regulator are

$$
R_{\max}=10\ {\rm fm},\qquad N=320,\qquad\delta=2\ {\rm MeV}.
$$

A deterministic differential-evolution search uses seed `260910`, population
multiplier 10, `maxiter=70`, mutation interval $(0.5,1.0)$, recombination
$0.7$, relative tolerance $10^{-7}$ and one worker. A bounded Powell polish
with `xtol=1e-6`, `ftol=1e-8` and `maxiter=240` starts at the best population
member. Failed spectra receive the frozen penalty

$$
10^7+10^3(a+R_c+\chi_0+R_\chi).
$$

No result-dependent restart, new bound or parameter change is permitted.

### 3.2 Stationarity and branch isolation

Finite differences are taken in normalized coordinates

$$
x_j=\frac{z_j-z_{j,\min}}{z_{j,\max}-z_{j,\min}}
$$

with step $h=0.002$. Central differences apply to free coordinates. At $a=0$
or $a=1$, the corresponding one-sided Karush–Kuhn–Tucker derivative is used.
The full central Hessian applies when $a$ is free; otherwise the projected
Hessian covers the three free coordinates and all feasible mixed directions
sampled below.

The branch is traced at every stencil point by maximal weighted eigenvector
overlap with the endpoint state. A stencil fails if its overlap is below
$0.98$ or if the selected state changes node count.

### 3.3 Grid, box and regulator sequences

The frozen radial sequence at $R_{\max}=10\ {\rm fm}$ and $\delta=2\ {\rm
MeV}$ is

$$
N\in\{240,320,480,640\}.
$$

Each nonprimary row receives a bounded Powell re-minimization from the primary
endpoint under the same coordinate bounds. The box sequence keeps
$\Delta r=0.03125\ {\rm fm}$:

$$
(R_{\max}/{\rm fm},N)\in\{(8,256),(10,320),(12,384)\}.
$$

The regulator sequence at $(R_{\max},N)=(10\ {\rm fm},320)$ is

$$
\delta/{\rm MeV}\in\{8,4,2,1,0.5\}.
$$

Every regulator row is independently polished from the primary endpoint. The
reported zero-regulator estimate is the least-squares intercept in $\delta^2$
of the final three rows. A linear-in-$\delta$ fit is recorded as a sensitivity
control and cannot replace the frozen decision fit.

### 3.4 Dilation identity

For a normalized endpoint state pulled back with
$r\mapsto r/\Lambda$, the exact trial-energy decomposition is

$$
E_{\rm trial}(\Lambda)=
\frac{K_q}{\Lambda}+M_q+\Lambda G+\Lambda^3V,
$$

where $K_q$ is the three-quark physical derivative expectation, $M_q$ is its
scalar-plus-pseudoscalar interaction expectation, $G$ is total field-gradient
energy and $V$ is total field-potential energy. The endpoint virial residual is

$$
\mathcal V=-K_q+G+3V.
$$

Direct re-diagonalized energies are also evaluated after multiplying both
$R_c$ and $R_\chi$ by

$$
\Lambda\in\{0.50,0.70,0.85,0.95,1.00,1.05,1.15,1.40,2.00\}.
$$

### 3.5 Volume-preserving affine shape mode

The frozen nonradial control pulls every field and the normalized quark state
back by

$$
A(d)=\operatorname{diag}(e^d,e^d,e^{-2d}),\qquad\det A=1.
$$

Rotational isotropy of the hedgehog stress gives the exact trial energy

$$
E_{\rm aff}(d)=
N_cK_1\frac{2e^d+e^{-2d}}{3}
+N_cM_1
+G\frac{2e^{2d}+e^{-4d}}{3}+V,
$$

where $K_1$ and $M_1$ are one-quark derivative and interaction expectations.
Thus

$$
E_{\rm aff}''(0)=2N_cK_1+8G.
$$

The script records this analytic curvature and the direct trial differences at
$d\in\{-0.20,-0.10,0,0.10,0.20\}$. This is a quadrupolar affine stability
statement. General nonradial modes remain outside the protocol.

### 3.6 Seeded dissipative formation basin

Twelve starts are fixed in normalized coordinates:

$$
\begin{array}{c|cccc}
 & a&R_c&\chi_0&R_\chi\\\hline
1&0.00&0.30&15&0.30\\
2&0.25&0.50&25&0.50\\
3&0.50&0.70&40&0.70\\
4&0.75&0.90&60&0.90\\
5&1.00&1.10&80&1.10\\
6&0.20&1.40&120&0.60\\
7&0.40&0.60&160&1.40\\
8&0.60&1.80&220&1.00\\
9&0.80&1.00&280&1.80\\
10&1.00&2.10&340&1.30\\
11&0.35&1.60&420&2.10\\
12&0.65&2.30&480&2.30
\end{array}
$$

Radii are in fm and $\chi_0$ is in MeV. Each start undergoes the same bounded
Powell dissipative relaxation on the primary grid. Its accepted callback
energies must be nonincreasing within $10^{-5}\ {\rm MeV}$. A start joins the
endpoint basin when its final energy differs by at most $2\ {\rm MeV}$, its
normalized coordinate distance is at most $0.05$, its selected-state overlap
with the primary endpoint is at least $0.98$, and its tail probability beyond
$8\ {\rm fm}$ is below $10^{-4}$.

## 4. Frozen controls

### 4.1 Algebra controls

The calculation must reproduce:

1. $\partial_\mu J_B^\mu=0$ symbolically from the global phase symmetry;
2. $U(0)=U'(0)=0$ and $U''(0)=M_\chi^2$;
3. $U'(\gamma M_\chi)=0$ and
   $U(\gamma M_\chi)=(\eta M_\chi)^4$;
4. a positive quartic coefficient and a negative cubic coefficient;
5. a Hamiltonian transpose-asymmetry below $10^{-10}\ {\rm MeV}$.

### 4.2 State controls

At the primary endpoint:

- $0<\epsilon_0<2500\ {\rm MeV}$;
- the upper component has zero nodes;
- the same-sign spectral gap exceeds $5\ {\rm MeV}$;
- probability beyond $8\ {\rm fm}$ is below $10^{-4}$;
- probability normalization error is below $10^{-10}$;
- the three colour copies agree to machine precision.

### 4.3 Tail controls

The analytic field-tail estimate beyond $R_{\max}$ must be below
$10^{-4}\ {\rm MeV}$. The $8$, $10$ and $12\ {\rm fm}$ box energies must agree
to the box criterion in §5.3. No hard truncation may be hidden by setting a
field to zero before the box boundary.

### 4.4 Negative controls

Three controls are mandatory:

1. **vacuum-field control:** $a=0$, $\chi_0=0$ at each $\delta$;
2. **no-confining-coupling control:** replace $g/\chi_\delta$ by the constant
   $M_q/f_\pi$ with $M_q=500\ {\rm MeV}$ while keeping the optimized fields;
3. **single-colour control:** replace the factor $N_c=3$ by $N_c=1$ without
   changing the field coordinates.

The vacuum-field control must delocalize as the box grows or rise with
$1/\delta$. The no-confining-coupling control must reproduce a finite
asymptotic continuum threshold and cannot be counted as confinement. The
single-colour control tests that the three-colour occupation materially
backreacts on the minimizing fields.

## 5. Frozen decisions

### 5.1 ICB1—action and exact-current qualification

`PASS` requires all algebra controls, finite action density at every positive
regulator, exact Hermiticity within tolerance, and an exactly conserved global
baryon current. Otherwise ICB1 is `FAIL`.

### 5.2 ICB2—stationary localized endpoint

`PASS` requires all state controls, all non-$a$ coordinates two percent inside
their bounds, primary optimizer success, normalized free-coordinate gradient
components below $1.0\ {\rm MeV}$, correct KKT sign if $a$ is active, and a
projected normalized-coordinate Hessian minimum eigenvalue above
$5.0\ {\rm MeV}$. Any failed branch-overlap stencil makes ICB2 `FAIL`.

### 5.3 ICB3—regulator, grid and box qualification

`PASS` requires:

1. the $N=480$ and $N=640$ energies to agree within $0.5\%$, levels within
   $0.5\%$, radii within $1.0\%$, and state overlap above $0.995$;
2. the $10$ and $12\ {\rm fm}$ energies to agree within $0.2\%$, levels within
   $0.2\%$, radii within $0.5\%$, and state overlap above $0.995$;
3. the $\delta=1$ and $0.5\ {\rm MeV}$ energies to agree within $1.0\%$,
   levels within $1.0\%$, radii within $1.0\%$, and state overlap above
   $0.995$;
4. a finite $\delta^2\to0$ intercept and a difference below $2.0\%$ between
   the linear and quadratic extrapolated energies.

Otherwise ICB3 is `FAIL`.

### 5.4 ICB4—reduced stability

`PASS` requires:

- $|\mathcal V|/(|K_q|+G+3|V|)<0.02$;
- direct dilation energies at $\Lambda=0.95$ and $1.05$ exceed the endpoint by
  at least $0.05\ {\rm MeV}$ and both endpoint-side extrema at $0.5$ and $2.0$
  exceed it by at least $10\ {\rm MeV}$;
- $K_1>0$, $G>0$ and $E_{\rm aff}''(0)>10\ {\rm MeV}$;
- all four nonzero affine trial points exceed $E_{\rm aff}(0)$.

This gate covers radial dilation and one exact volume-preserving affine mode.
It does not cover arbitrary nonradial perturbations. A failed condition makes
ICB4 `FAIL`.

### 5.5 ICB5—seeded reduced formation

`SUPPORTS` requires at least eight of twelve fixed starts to enter the endpoint
basin, including at least one start with $\chi_0\le25\ {\rm MeV}$ and one with
$\chi_0\ge340\ {\rm MeV}$. Every counted path must have nonincreasing accepted
energies. Otherwise ICB5 is `CONTRADICTS`. Solver failure before all twelve
terminal receipts makes ICB5 `INCONCLUSIVE`.

### 5.6 ICB6—physical completion

ICB6 is frozen to `FAIL`. Therefore

```text
complete_physical_matter_formation=false
```

for every outcome. The supplied empirical action, normal-ordered sea,
spherical variational family, dissipative parameter relaxation, inherited
baryon number, and missing observable projection do not meet the physical
completion standard.

### 5.7 Overall decision

- ICB1–ICB4 `PASS` and ICB5 `SUPPORTS`:
  `INTERACTING_REDUCED_FORMATION_SUPPORTS`.
- Any of ICB1–ICB4 `FAIL`, or ICB5 `CONTRADICTS`:
  `INTERACTING_REDUCED_FORMATION_CONTRADICTS`.
- Missing or nonfinite evidence:
  `INTERACTING_REDUCED_FORMATION_INCONCLUSIVE`.

The overall physical verdict remains `FAIL` under every branch.

## 6. Execution, evidence and amendments

The primary script is `computations/qcd_interacting_baryon.py`. It writes

```text
runs/20260910_qcd_interacting_baryon/primary/results.json
```

plus immutable source snapshots and numerical arrays. The independent verifier
is `computations/verify_qcd_interacting_baryon.py`; it reads the primary receipt,
reconstructs the potentials, Hamiltonian, energies, finite differences,
extrapolations and frozen decisions without importing the primary module, and
writes

```text
runs/20260910_qcd_interacting_baryon/verification/verification.json
```

The protocol SHA-256, both source hashes and every output hash are recorded.
The primary run executes once. An implementation defect may be repaired only
through a dated amendment in this file that identifies the defect, preserves
the failed output, changes the protocol hash and reruns all affected arms into
a new directory. Physical parameters, bounds, starts, tolerances and decision
branches remain fixed.

### 6.1 Execution amendment 1—sequence-serialization defect

The first execution completed the primary optimization and entered the
convergence sequences, then stopped before writing a scientific receipt. The
sequence serializer removed a private row before using it to calculate the
next adjacent-state overlap, producing a `KeyError`. The preserved failed
attempt is
`runs/20260910_qcd_interacting_baryon/primary/`. The serializer now computes
all overlaps before removing private row objects. The accepted rerun writes
`runs/20260910_qcd_interacting_baryon/primary/recovery1/results.json`, and its
independent verification writes beneath
`runs/20260910_qcd_interacting_baryon/verification/recovery1/`. No action,
parameter, grid, start, threshold or decision branch changes.

### 6.2 Execution amendment 2—tail-control adjudication

The recovery-1 execution evaluated and recorded the independently integrated
field energy beyond the primary box, but its decision function omitted the
mandatory §4.3 threshold from ICB3. The scientific receipt is preserved at
`runs/20260910_qcd_interacting_baryon/primary/recovery1/`. The repaired
adjudicator applies the already-frozen $10^{-4}\ {\rm MeV}$ threshold as part
of regulator, grid and box qualification and exposes its Boolean result. The
accepted rerun writes
`runs/20260910_qcd_interacting_baryon/primary/recovery2/results.json`, and its
independent verification writes beneath
`runs/20260910_qcd_interacting_baryon/verification/recovery2/`. No calculated
quantity, physical parameter, grid, start, tolerance or scientific threshold
changes.

### 6.3 Execution amendment 3—undeclared localization penalty

Independent reconstruction of recovery 2 found that the primary objective
added $10^5P(r\ge8\ {\rm fm})$ and replaced the physical energy by a penalty
whenever that probability exceeded $0.05$. The frozen objective in §3.1
permits the declared $10^7+10^3\sum_jz_j$ value only when no selected spectrum
exists; localization is adjudicated separately by ICB2. The undeclared term
could suppress a lower delocalized branch and therefore affect the scientific
outcome. The repaired objective uses the physical energy for every finite
selected spectrum and the exact frozen penalty only for a missing or nonfinite
spectrum. Recovery-2 receipts remain preserved. The accepted primary run
writes `runs/20260910_qcd_interacting_baryon/primary/recovery3/results.json`;
independent verification writes beneath
`runs/20260910_qcd_interacting_baryon/verification/recovery3/`. No action,
parameter, grid, start, tolerance, threshold or decision branch changes.

## References

- `computations/qcd-quark-meson-carrier-prereg.md`—regular Dirac carrier,
  chiral family, radial Hamiltonian and exact-current qualification.
- `computations/qcd-confining-carrier-prereg.md`—finite-cutoff confining action,
  colour-singlet state and confinement boundary.
- `computations/matter-formation-continuum-report.md` §79, §81—empirical carrier
  and confining-bridge results that motivate this interacting test.
- `foundations/matter-completion-boundary.md` §24, §26—current microscopic
  completion boundary.
- M. Malheiro et al., [“Small quark stars in the chromodielectric
  model”](https://arxiv.org/abs/hep-ph/0111148)—chiral chromodielectric action,
  quartic potential and published parameter set.
- M. C. Birse and M. K. Banerjee, [“Chiral model of the nucleon and
  delta”](https://doi.org/10.1103/PhysRevD.31.118)—self-consistent valence-quark
  hedgehog and physical parameter context.
