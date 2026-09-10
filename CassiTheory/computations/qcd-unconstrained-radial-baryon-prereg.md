# Unconstrained Radial Chiral-Chromodielectric Baryon Protocol

## Status: Preregistered—September 2026

## Abstract

The interacting-baryon calculation supplies a compact, bound endpoint inside a four-parameter profile family, while its first joint field minimization fails stationarity and continuum controls. This protocol removes that profile restriction. It minimizes the radial quark–meson energy over independent finite-volume values of the chiral and chromodielectric fields, follows a fixed occupied quark state, measures the full radial Hessian, and tests deterministic relaxation from compact and diffuse seeds. The calculation can establish a stationary localized baryon and a formation basin inside the empirical chiral chromodielectric action. Its scope excludes derivation of that action from the canonical Cassi pair, baryon-number creation, quark canonical quantization, the filled Dirac sea, electroweak conversion, and real-time closed-system formation.

## 1. Question and endpoint

The binary question is:

> Does the fixed empirical two-flavour chiral chromodielectric action possess a regulator-qualified, unconstrained radial local minimum with three occupied valence colours, finite energy, localized fields, a positive radial Hessian, and a reproducible dissipative basin?

A positive answer closes the radial profile-family gap for the empirical comparison action. It does not identify the microscopic completion of the canonical Cassi pair.

The frozen endpoint labels are:

- **QURB1 `PASS`**: the independently implemented finite-volume energy and analytic gradient pass their algebraic controls.
- **QURB2 `PASS`**: an unconstrained stationary localized state exists at the primary discretization.
- **QURB3 `PASS`**: the state is a strict radial local minimum in the declared coordinate metric.
- **QURB4 `PASS`**: grid, box, and regulator sequences meet all continuum thresholds.
- **QURB5 `EMERGES`**: the same state is reached from the declared compact and diffuse relaxation seeds.
- **QURB6 `PASS`**: required negative controls separate localization from the vacuum and free-quark limits.
- **QURB7 `ADOPT`**: QURB1–QURB4 and QURB6 pass and QURB5 emerges.
- **QURB8 `FAIL`**: a complete Cassi matter-formation mechanism remains unavailable because the microscopic action, canonical fermionic state, baryogenesis, and closed-system formation dynamics are outside the supplied theory.

QURB8 is frozen independently of QURB1–QURB7. A regular empirical baryon cannot change it.

## 2. Frozen action and occupied sector

The action is the two-flavour chiral chromodielectric model

$$
\begin{aligned}
\mathcal L_{\rm QCDM}={}&
\bar q\,i\gamma^\mu\partial_\mu q
+\frac12\partial_\mu\sigma\,\partial^\mu\sigma
+\frac12\partial_\mu\boldsymbol\pi\!\cdot\!\partial^\mu\boldsymbol\pi
-W(\sigma,\boldsymbol\pi)\\
&+\frac12\partial_\mu\chi\,\partial^\mu\chi-U(\chi)
-\frac{g}{\chi_\delta}\bar q
\left(\sigma+i\gamma^5\boldsymbol\tau\!\cdot\!\boldsymbol\pi\right)q,
\qquad
\chi_\delta=\sqrt{\chi^2+\delta^2}.
\end{aligned}
$$

The vacuum-subtracted chiral potential is

$$
W-W_{\rm vac}
=\frac{m_\pi^2f_\pi^2}{2}\left[(s-1)^2+p^2\right]
+\frac{\lambda f_\pi^4}{4}(s^2+p^2-1)^2,
\qquad
\lambda=\frac{m_\sigma^2-m_\pi^2}{2f_\pi^2},
$$

and the chromodielectric potential is

$$
U(\chi)=\frac12M_\chi^2\chi^2
\left[
1+\left(\frac{8\eta^4}{\gamma^2}-2\right)\frac{\chi}{\gamma M_\chi}
+\left(1-\frac{6\eta^4}{\gamma^2}\right)
\frac{\chi^2}{(\gamma M_\chi)^2}
\right].
$$

The frozen numerical constants are

| Quantity | Value |
|---|---:|
| $\hbar c$ | $197.3269804\ \mathrm{MeV\,fm}$ |
| $N_c$ | $3$ |
| $f_\pi$ | $93\ \mathrm{MeV}$ |
| $m_\pi$ | $139.6\ \mathrm{MeV}$ |
| $m_\sigma$ | $1200\ \mathrm{MeV}$ |
| $g$ | $23\ \mathrm{MeV}$ |
| $M_\chi$ | $1700\ \mathrm{MeV}$ |
| $\gamma$ | $0.2$ |
| $\eta$ | $0.12$ |

The occupied sector contains three colours in one grand-spin-zero hedgehog orbital. The radial spinor convention is

$$
q(\mathbf r)=\frac1{\sqrt{4\pi}}
\begin{pmatrix}h(r)\\ i\boldsymbol\sigma\!\cdot\!\hat{\mathbf r}\,j(r)\end{pmatrix}|G=0\rangle,
\qquad
\int_0^\infty r^2\left(h^2+j^2\right)\,dr=1.
$$

The meson fields are $\sigma=f_\pi s(r)$, $\boldsymbol\pi=f_\pi\hat{\mathbf r}p(r)$, and $\chi=\chi(r)$. The regulated radial Dirac operator is

$$
H_\delta=
\begin{pmatrix}
m_s & \hbar c\left(\partial_r+2/r\right)+m_p\\
-\hbar c\,\partial_r+m_p & -m_s
\end{pmatrix},
\quad
m_s=\frac{g f_\pi s}{\sqrt{\chi^2+\delta^2}},
\quad
m_p=\frac{g f_\pi p}{\sqrt{\chi^2+\delta^2}}.
$$

The primary occupied state is the lowest positive, nodeless discrete eigenstate continuously connected by maximum absolute overlap to the state at the accepted interacting-baryon endpoint. The state is reselected from the twelve eigenpairs nearest zero at every objective evaluation. A sign change, disappearance of a positive nodeless candidate, or overlap below $0.70$ is a branch event and fails QURB2 for that trajectory. The model contains no vacuum-polarization energy or filled negative continuum.

The accepted upstream receipt is

`runs/20260910_qcd_interacting_baryon/primary/recovery3/results.json`

with SHA-256

`0067c5139c76e7e8ebf75ee2ced88c645ecd9c66738489b10af003f0ba974437`.

The endpoint and formation seeds are read directly from this receipt; a hash mismatch aborts execution.

## 3. Independent finite-volume representation

The primary grid has $R=10\ \mathrm{fm}$ and $N=192$ radial cells. Cell centres are $r_i=(i+1/2)\Delta r$, faces are $r_{i+1/2}=(i+1)\Delta r$, and radial volumes without the common $4\pi$ factor are

$$
V_i=\frac{r_{i+1/2}^3-r_{i-1/2}^3}{3}.
$$

The independent optimization coordinates are

$$
x=(s_0,\ldots,s_{N-1},p_0,\ldots,p_{N-1},c_0,\ldots,c_{N-1}),
\qquad c_i=\chi_i/(\gamma M_\chi).
$$

Bounds are $-1.5\le s_i,p_i\le1.5$ and $0\le c_i\le1.5$. Boundary values are $s(R)=1$, $p(0)=p(R)=0$, $\chi(R)=0$; regularity gives $s'(0)=\chi'(0)=0$. Dirichlet values enter through half-cell gradient terms rather than fixed edge cells.

For a scalar cell field $f_i$ with outer value $f_R$, the discrete radial-gradient integral is

$$
I_\nabla[f]=
\sum_{i=1}^{N-1}\frac{r_i^2}{\Delta r}(f_i-f_{i-1})^2
+\frac{2R^2}{\Delta r}(f_{N-1}-f_R)^2.
$$

For the hedgehog pion,

$$
I_\nabla[p]=
\frac{\Delta r}{6}p_0^2+
\sum_{i=1}^{N-1}\frac{r_i^2}{\Delta r}(p_i-p_{i-1})^2
+\frac{2R^2}{\Delta r}p_{N-1}^2
+2\Delta r\sum_i p_i^2.
$$

The finite-volume field energy is

$$
E_{\rm fld}=4\pi\left[
\frac{f_\pi^2}{2\hbar c}\left(I_\nabla[s]+I_\nabla[p]\right)
+\sum_i\frac{V_i W_i}{(\hbar c)^3}
+\frac{I_\nabla[\chi]}{2\hbar c}
+\sum_i\frac{V_i U_i}{(\hbar c)^3}
\right].
$$

The objective is

$$
E_{\rm tot}(x)=3\epsilon_0(x)+E_{\rm fld}(x).
$$

The Hellmann–Feynman derivative of $\epsilon_0$ and exact derivatives of the finite-volume terms supply the analytic gradient. Linear solves and eigenproblems use symmetric sparse matrices. No interpolation, smoothing, or penalty term enters the objective.

## 4. Frozen numerical procedure

### 4.1 Algebraic controls

The verifier must pass all of these before minimizing:

1. The assembled Dirac matrix is symmetric to maximum absolute error below $10^{-12}\ \mathrm{MeV}$.
2. Every reported eigenvector has residual $\|H\psi-\epsilon\psi\|_2/\max(1,|\epsilon|)<10^{-9}$.
3. The analytic total-energy gradient agrees with centred finite differences in 24 fixed random directions at $N=48$ to relative directional error below $3\times10^{-5}$, with absolute tolerance $3\times10^{-5}\ \mathrm{MeV}$ when the numerical directional derivative is below $1\ \mathrm{MeV}$.
4. At the accepted four-parameter endpoint, the finite-volume interior field energy with its imposed outer half-cell penalties removed differs from an independent Simpson-rule evaluation of the analytic profile by less than $0.5\%$ at $N=384$. The outer penalties are checked separately from their displayed quadratic formulas.
5. The vacuum fields $s=1,p=0,\chi=0$ have zero field energy to absolute tolerance $10^{-10}\ \mathrm{MeV}$.

Any failure gives QURB1=`FAIL` and stops the expensive sequence.

### 4.2 Multilevel minimization

The primary minimization uses L-BFGS-B with the stated bounds and analytic gradient. It proceeds through $N=48,96,192$ at $R=10\ \mathrm{fm}$, prolonging each converged cell-centred profile by monotone cubic interpolation. Each level permits at most 1200 iterations and 4000 objective evaluations. Termination requires both a projected-gradient infinity norm below $10^{-3}\ \mathrm{MeV}$ and relative energy change below $10^{-10}$ over the final five accepted steps. The line search is the SciPy strong-Wolfe bounded implementation with maximum 60 line-search steps. Failure at a coarse level is retained and does not get replaced by a tuned start.

QURB2=`PASS` requires at $N=192$:

- successful termination under the frozen criteria;
- no active coordinate bounds within $10^{-6}$ except asymptotic $c_i=0$ cells beyond $8\ \mathrm{fm}$;
- $0<\epsilon_0<500\ \mathrm{MeV}$;
- $E_{\rm tot}<3gf_\pi/\delta$ at the same regulator;
- baryon RMS radius below $1.5\ \mathrm{fm}$;
- $|s_{N-1}-1|<10^{-3}$, $|p_{N-1}|<10^{-3}$, and $\chi_{N-1}<0.5\ \mathrm{MeV}$;
- no branch event.

### 4.3 Radial Hessian

The Hessian is the centred finite difference of the analytic gradient in the normalized coordinate $x$. ARPACK/Lanczos computes the eight smallest algebraic eigenvalues to residual below $10^{-6}\max(1,|\lambda|)$. The differencing step is $10^{-5}\max(1,\|x\|_2/\sqrt{3N})$ and is repeated at half step. QURB3=`PASS` requires all eight eigenvalues to agree in sign between steps, the smallest to exceed $10^{-3}\ \mathrm{MeV}$, and random displacements of normalized norm $10^{-3}$ along 16 fixed directions to increase the energy. A negative eigenvalue fails QURB3. An unresolved eigenvalue gives QURB3=`INCONCLUSIVE`.

### 4.4 Continuum qualification

Starting from independently prolonged copies of the primary result, run:

- grid sequence: $(R,N)=(10,96),(10,144),(10,192),(10,288)$;
- box sequence at matched $\Delta r\approx0.05208\ \mathrm{fm}$: $(R,N)=(8,154),(10,192),(12,230)$;
- regulator sequence at $(R,N)=(10,192)$: $\delta=4,2,1\ \mathrm{MeV}$.

Every sequence member must meet the QURB2 stationarity, localization, and branch conditions. Between the two finest grid members and between the two largest boxes, require relative differences below $1\%$ in total energy and quark level, below $2\%$ in RMS radius, and component-wise weighted profile overlaps above $0.99$ after conservative interpolation. A quadratic fit in $\delta$ must have relative residual below $0.5\%$ for all three observables, and its $\delta\to0^+$ intercept must differ from the $\delta=1\ \mathrm{MeV}$ value by less than $3\%$. These conditions define QURB4.

### 4.5 Formation basin

A deterministic preconditioned gradient flow at $(R,N,\delta)=(10\ \mathrm{fm},96,2\ \mathrm{MeV})$ uses the exact objective and gradient. The diagonal preconditioner is the inverse diagonal of the positive field-gradient operator plus $1\ \mathrm{MeV}$, evaluated once at the starting profile. Backtracking begins at unit step, halves until energy decreases, and stops below $2^{-30}$. The flow stops at projected-gradient infinity norm $10^{-3}\ \mathrm{MeV}$ or 20,000 accepted steps.

The four frozen starts are:

1. the accepted compact four-parameter endpoint;
2. the low-$\chi$ formation seed recorded as `start_index=1` in the upstream receipt;
3. a diffuse dilation of start 1 by factor $1.6$ with field amplitudes unchanged;
4. start 1 plus a smooth fixed-seed perturbation generated by NumPy `PCG64(20260910)`, projected onto the first eight radial sine modes and normalized to RMS amplitudes $(0.03,0.03,0.02)$ in $(s,p,c)$.

A start belongs to the primary basin when it terminates without a branch event and differs from the primary $N=96$ state by less than $1\%$ in energy and level, less than $2\%$ in RMS radius, and has all three profile overlaps above $0.99$. QURB5=`EMERGES` requires at least three starts in the basin, including the diffuse start. Two or fewer gives `DOES NOT EMERGE`; numerical interruption gives `INCONCLUSIVE`.

This gradient flow is a basin diagnostic. It is not assigned physical time.

### 4.6 Negative controls

Two controls run at $(R,N,\delta)=(10\ \mathrm{fm},96,2\ \mathrm{MeV})$ from start 1:

- **No occupancy:** set $N_c=0$. The fields must converge to the vacuum with field energy below $10^{-5}\ \mathrm{MeV}$ and maximum deviations $|s-1|,|p|,c<10^{-4}$.
- **No quark–meson coupling:** set $g=0$. No localized positive bound orbital may be reported; the fields must meet the same vacuum thresholds.

Both controls must pass for QURB6=`PASS`.

## 5. Decision tree

1. Run QURB1. Stop on `FAIL`.
2. Run the primary multilevel minimization. A missing stationary endpoint gives QURB2=`FAIL`; preserve the lowest-energy trajectory and measure its branch or collapse mode.
3. Run QURB3 only after QURB2 passes.
4. Run QURB4 only after QURB2 and QURB3 pass.
5. Run QURB5 and QURB6 after QURB2 passes, independent of QURB3–QURB4.
6. Set QURB7=`ADOPT` exactly when QURB1–QURB4 and QURB6 are `PASS` and QURB5=`EMERGES`; otherwise set QURB7=`REJECT`.
7. Set QURB8=`FAIL` and list the explicit missing structures.

No failed threshold may be rerun with changed bounds, grid schedule, state selector, starts, smoothing, penalty terms, line-search settings, or regulator values. Implementation defects may be corrected only when the defect and correction are recorded in the result receipt.

## 6. Required artifacts

The primary writes under
`runs/20260910_qcd_unconstrained_radial_baryon/recovery4/`:

- `results.json`: constants, source hashes, every threshold input, optimizer histories, state overlaps, eigen-residuals, Hessian spectrum, continuum rows, basin rows, controls, decisions, and elapsed time;
- `profiles.npz`: every accepted field profile and occupied spinor;
- `trajectory.npz`: accepted basin-flow energy and residual traces;
- `report.md`: a readable table generated directly from `results.json`.

The primary source lives at
`computations/qcd_unconstrained_radial_baryon.py`. Independent verification
must recompute receipt consistency and the decisive endpoint observables
without importing that source. It writes
`runs/20260910_qcd_unconstrained_radial_baryon/verification/recovery4/verification.json`.

## 7. Execution amendment 1—boundary-consistent quadrature control

The first execution is preserved at
`runs/20260910_qcd_unconstrained_radial_baryon/results.json`. Its finite-volume
control included the imposed half-cell interpolation from the analytic
profile's nonzero value at the last cell centre to the exact boundary value,
while the Simpson comparison integrated the unmodified analytic profile.
Those are different functions. The discrepancy was $0.5040711\%$, with every
gradient, Hermiticity, eigensystem and vacuum control passing.

Recovery 1 compares the common interior profile by removing the three
explicit outer half-cell quadratic penalties from the finite-volume value for
this control only. Their coefficients and values remain recorded and are
checked directly against the formulas in §3. The objective, gradients,
thresholds, fields, state rule, grids, starts and decision tree are unchanged.
Every arm is rerun into
`runs/20260910_qcd_unconstrained_radial_baryon/recovery1/`.

## 8. Execution amendment 2—program role and skipped-gate semantics

The recovery-1 executable carried a `verify_` filename although it generated
the primary receipt. During the first $N=48$ minimization it raised an
undifferentiated missing-state exception. Before independent reconstruction,
the executable is named
`computations/qcd_unconstrained_radial_baryon.py`, and downstream gates that
the decision tree does not authorize are recorded as
`SKIPPED_PREREQUISITE` rather than `FAIL`. The action, state selector, bounds,
grid schedule, thresholds, starts and scientific decision are unchanged.
Recovery 2 reruns the primary into
`runs/20260910_qcd_unconstrained_radial_baryon/recovery2/`; the independent
implementation reconstructs the decisive finite-grid spectrum from the
source-bound receipt.

## 9. Execution amendment 3—captured occupied-state branch event

Independent dense diagonalization of the recovery-2 starting profile finds
the positive nodeless $390.681268419\ {\rm MeV}$ state selected by the frozen
rule. The exception arose at a later L-BFGS-B trial profile where that state
disappeared, but the primary treated the trial-point branch event as a failed
run and discarded the last valid trajectory point.

The primary now terminates that one trajectory at the first disappearance or
sub-$0.70$ reference overlap, retains its lowest-energy accepted valid point,
and records the offending trial profile and branch classification. This
implements the frozen §3.2 and §4.2 branch rule; it does not add a penalty,
change a bound, permit the optimizer to cross the branch boundary, or alter
any scientific input. Recovery 3 writes the corrected receipt and the
independent program reconstructs both the valid starting state and the
offending trial spectrum.

## 10. Execution amendment 4—trajectory-only branch enforcement

The recovery-3 launch stopped inside QURB1 because the independent algebraic
gradient probe deliberately perturbs the fields beyond the $0.70$ overlap
threshold. That probe is not an optimization trajectory and already has
separate finite-difference acceptance gates. Branch enforcement is therefore
restricted to L-BFGS-B and basin trajectories; the eigensystem remains
mandatory in the algebraic probe. No equation, perturbation, tolerance,
optimizer setting, state selector or decision threshold changes. Recovery 4
writes the source-bound primary and independent receipts.

## References

- `computations/qcd-interacting-baryon-prereg.md`—fixed-family interacting-baryon protocol and empirical action.
- `computations/matter-formation-continuum-report.md` §79—cross-model matter-formation verdict.
- `foundations/matter-completion-boundary.md` §§24, 26–27—physical completion requirements and radial obstruction.
- `foundations/unified-lagrangian.md` §2.7—empirical regular quark–meson comparison action.
