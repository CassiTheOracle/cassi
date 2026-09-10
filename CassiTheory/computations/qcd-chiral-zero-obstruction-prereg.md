# QCD Chiral-Zero Obstruction Protocol

## Status: Preregistered—September 2026

## Abstract

This calculation tests whether the normalized Skyrme stabilizer used in the QCD-anchored chiral formation experiment admits a continuum, finite-energy change of winding. The local model is a nondegenerate zero of the four-component chiral field. Its normalized field develops a quartic-gradient energy proportional to the inverse distance from the zero. Exact integration, two independent quadratures, anisotropic rank-three controls, and the regulator used by the formation code distinguish a continuum result from a lattice artifact.

The protocol can reject the selected low-energy action as a continuum formation dynamics. It cannot reject QCD, the existence of baryons, or regular ultraviolet completions containing additional quark or vector fields.

<!-- qcd-chiral-zero-obstruction-protocol:start -->

## 1. Question and action

The frozen chiral action in `computations/qcd-chiral-matter-formation-prereg.md` contains

$$
\mathcal U_4[\hat{\boldsymbol\phi}]
=\frac12\int d^3x\sum_{i<j}
\left[G_{ii}G_{jj}-G_{ij}^2\right],
\qquad
G_{ij}=\partial_i\hat{\boldsymbol\phi}\cdot
\partial_j\hat{\boldsymbol\phi},
$$

with

$$
\hat{\boldsymbol\phi}
=\frac{\boldsymbol\phi}{|\boldsymbol\phi|}.
$$

A continuous change of the spatial degree requires a zero of
$\boldsymbol\phi$. The local normal form of a nondegenerate spacetime zero,
after orientation-preserving linear coordinate changes, is represented by

$$
\boldsymbol\phi_\tau(\mathbf x)
=(\tau,x_1,x_2,x_3),
\qquad
r=|\mathbf x|,
\qquad
\rho^2=\tau^2+r^2.
$$

Its spacetime Jacobian has determinant one. The calculation concerns the
local energy near the zero; no far-field particle profile is assumed.

## 2. Frozen analytic predictions

For $\tau\ne0$,

$$
\hat{\boldsymbol\phi}_\tau
=\frac{(\tau,\mathbf x)}{\rho},
\qquad
G_{ij}=\frac{\delta_{ij}}{\rho^2}
-\frac{x_i x_j}{\rho^4}.
$$

The two tangential eigenvalues of $G$ are $\rho^{-2}$ and its radial
eigenvalue is $\tau^2\rho^{-4}$. Therefore

$$
\boxed{
u_4(\tau,r)
=\frac12\left[rac1{(r^2+\tau^2)^2}
+\frac{2\tau^2}{(r^2+\tau^2)^3}\right].}
$$

On the ball $B_R$,

$$
\boxed{
E_4(\tau,R)
=\frac{\pi}{2|\tau|}
\left[
3\arctan X-
\frac{X(X^2+3)}{(1+X^2)^2}
\right],
\qquad X=\frac{R}{|\tau|}.}
$$

Consequently,

$$
\boxed{
E_4(\tau,R)
=\frac{3\pi^2}{4|\tau|}
-\frac{2\pi}{R}+O\!\left(\frac{\tau^2}{R^3}\right).}
$$

At the zero time, remove a ball of radius $a$ before normalizing. Then

$$
\boxed{
E_4(0;a,R)=2\pi\left(\frac1a-\frac1R\right).}
$$

For the formation code's pointwise prescription

$$
\hat{\boldsymbol\phi}_\epsilon
=\frac{\boldsymbol\phi}
{\max(|\boldsymbol\phi|,\epsilon)},
$$

applied to $\boldsymbol\phi_0=(0,\mathbf x)$, the interior $r<\epsilon$
has $G_{ij}=\delta_{ij}/\epsilon^2$. Direct integration gives

$$
\boxed{
E_{4,\max}(0;\epsilon,R)
=\frac{4\pi}{\epsilon}-\frac{2\pi}{R}.}
$$

Both prescriptions diverge, and their leading coefficients differ. A fixed
$\epsilon$ therefore changes the action rather than defining a
regulator-independent continuum limit.

The two-derivative density of the unnormalized local field is $3/2$, so

$$
E_2(B_R)=2\pi R^3.
$$

Every polynomial potential that is finite at
$\boldsymbol\phi=0$ contributes $O(R^3)$ locally. Neither term cancels the
inverse-length divergence.

## 3. General rank-three zero

At a nondegenerate spacetime zero, the spatial derivative
$A=D_{\mathbf x}\boldsymbol\phi$ has rank three. At the zero time,

$$
\hat{\boldsymbol\phi}(r\mathbf u)
=\frac{A\mathbf u}{|A\mathbf u|},
\qquad \mathbf u\in S^2,
$$

and is independent of $r$. Let $J_A(\mathbf u)$ be the area Jacobian of this
map between the unit sphere and the unit sphere in ${\rm im}\,A$. Its
quartic energy has the form

$$
E_4(0;a,R;A)
=C(A)\left(\frac1a-\frac1R\right),
\qquad
C(A)=\frac12\int_{S^2}J_A^2\,d\Omega.
$$

The angular map has degree $\pm1$, hence

$$
\int_{S^2}|J_A|\,d\Omega=4\pi,
$$

and Cauchy–Schwarz gives

$$
\boxed{C(A)\ge2\pi.}
$$

Equality holds for equal singular values. Rank below three is a declared
degenerate control and cannot represent a nondegenerate spacetime zero.

## 4. Frozen numerical inputs

Use IEEE float64 and

$$
R=4,
$$

with

$$
|\tau|,a,\epsilon\in
\{0.4,0.2,0.1,0.05,0.025,0.0125,0.00625\}.
$$

The anisotropic rank-three maps are represented, up to orthogonal changes
of domain and target basis, by singular-value triples

$$
(1,1,1),\qquad(0.6,1.0,1.8),\qquad(0.3,1.2,2.4).
$$

The degenerate control is $(0,1,2)$.

The primary program uses `scipy.integrate.quad` for radial integrals and a
tensor Gauss–Legendre/trapezoidal sphere quadrature for $C(A)$. It uses the
analytic derivative of the normalized field only to evaluate the frozen
integrands. The independent program uses fixed Gauss–Legendre rules,
constructs derivatives from the projection formula, and does not import the
primary source.

At the three Cartesian points

$$
(0.4,-0.3,0.2),\qquad(-0.7,0.1,0.5),\qquad(0.2,0.6,-0.4),
$$

with $\tau=0.15$, a centered difference with step $10^{-6}$ checks every
entry of $G$ against the closed form.

## 5. Measurements

Both programs record:

1. every entry of the closed-form and independently reconstructed pullback
   metric at the three derivative-control points;
2. numerical and exact $E_4(\tau,R)$ for every nonzero $\tau$;
3. the log–log slope of the last four temporal energies and the last four
   puncture energies;
4. $|\tau|[E_4(\tau,R)+2\pi/R]$ and its difference from $3\pi^2/4$;
5. $a[E_4(0;a,R)+2\pi/R]$ and its difference from $2\pi$;
6. $\epsilon[E_{4,\max}(0;\epsilon,R)+2\pi/R]$ and its difference from
   $4\pi$;
7. $C(A)$, $C(A)/(2\pi)$, and numerical sphere area for every rank-three
   map;
8. the numerical rank and angular-Jacobian floor for the degenerate map;
9. the hashes of the frozen protocol and both sources;
10. the final verdicts and `complete_physical_matter_formation=false`.

The primary receipt is written to
`runs/20260910_qcd_chiral_zero_obstruction/primary/results.json`. The
independent receipt is written to
`runs/20260910_qcd_chiral_zero_obstruction/verification/verification.json`.
Raw quadrature rows are stored as strict JSON within the same directories.

## 6. Frozen decisions

### QZO1—local differential identity

`PASS` requires every reconstructed metric entry to agree with the closed
form to absolute error below $2\times10^{-9}$, positive finite density at
every control point, and the analytic radial density to agree with the
eigenvalue reconstruction to relative error below $2\times10^{-12}$.
Otherwise QZO1 is `FAIL`.

### QZO2—temporal approach to the zero

`PASS` requires radial quadrature to agree with the exact finite-$R$ formula
to relative error below $2\times10^{-10}$ in every row, the last-four
log–log slope to lie in $[-1.02,-0.98]$, and the smallest-$|\tau|$ corrected
coefficient to differ from $3\pi^2/4$ by less than $5\times10^{-5}$.
Otherwise QZO2 is `FAIL`.

### QZO3—punctured zero and rank-three generality

`PASS` requires every puncture row to reproduce $2\pi(1/a-1/R)$ to relative
error below $2\times10^{-10}$, the last-four slope to lie in
$[-1.02,-0.98]$, sphere area to agree with $4\pi$ within $2\times10^{-6}$,
all three rank-three coefficients to be at least $2\pi-2\times10^{-5}$,
and the isotropic coefficient to agree with $2\pi$ within
$2\times10^{-5}$. The degenerate control must have numerical rank two and
zero minimum area Jacobian. Otherwise QZO3 is `FAIL`.

### QZO4—cutoff dependence

`PASS` requires every max-cutoff row to reproduce
$4\pi/\epsilon-2\pi/R$ to relative error below $2\times10^{-10}$, its
last-four slope to lie in $[-1.02,-0.98]$, and the smallest-$\epsilon$
corrected coefficient to agree with $4\pi$ within $2\times10^{-10}$.
Otherwise QZO4 is `FAIL`.

### QZO5—continuum topology-changing use of the selected action

`CONTRADICTS` applies if QZO1–QZO4 all pass. A nondegenerate degree-changing
zero then lies at infinite normalized-Skyrme energy, while the code cutoff
has no regulator-independent limit. `INCONCLUSIVE` applies if any numerical
gate fails.

### QZO6—complete physical matter formation

QZO6 is `FAIL`. This local calculation supplies no Cassi-to-QCD selection,
quark density operator, baryon-current transport, spin/statistics,
production probability, or cosmological state. No outcome may set
`complete_physical_matter_formation=true`.

## 7. Stopping and evidence rules

The protocol is frozen before either program is written. Each program runs
once. A code defect may be repaired only by an amendment that identifies the
defect, preserves prior receipts, changes the protocol hash, and reruns both
programs. Thresholds, input sets, formulas, and verdict branches remain
fixed.

The independent verifier reads the primary receipt and raw rows, checks all
hashes and schema fields, reconstructs every numerical result without
importing the primary source, and compares the complete verdict tree. A
missing or malformed primary package exits nonzero and assigns QZO1–QZO5
`INCONCLUSIVE`, QZO6 `FAIL`, and
`complete_physical_matter_formation=false`.

<!-- qcd-chiral-zero-obstruction-protocol:end -->

## 8. Scope

A `CONTRADICTS` result for QZO5 establishes that the normalized-Skyrme action
used by the chiral quench cannot describe a finite-energy continuum winding
change through a generic zero. Prepared textures can remain valid stationary
or relaxation benchmarks because their modulus stays nonzero. Lattice
texture production remains dependent on the chosen cutoff and spacing.

A regular formation model must add microscopic fields that remain defined
when the condensate vanishes and must carry the conserved baryon current
through that interval. Selecting and calibrating such a model is a separate
physical calculation.

## References

- `computations/qcd-chiral-matter-formation-prereg.md` §§1–7—selected action, topology condition, frozen quench and numerical stopping rule.
- `computations/qcd_chiral_matter_formation.py`—implemented max-normalization prescription and retained failed execution.
- `runs/20260909_qcd_chiral_matter_formation/amendment-1/results.json`—100,001-step incomplete QCD-anchored execution.
- `foundations/matter-completion-boundary.md` §§9, 12–13—microscopic non-identifiability and physical completion requirements.
- G. Holzwarth and J. Klomfass, “The Chiral Phase Transition in Dissipative Dynamics,” arXiv:hep-ph/0206228—linear $O(4)$ field, normalized Skyrme term, random hot fields and dissipative evolution.
