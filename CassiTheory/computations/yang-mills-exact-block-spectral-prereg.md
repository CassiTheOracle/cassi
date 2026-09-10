# Cutoff SU(2) Finite-Lattice Conditional Block Spectral Study

## Status: Pre-registered—September 2026

## Abstract

This study computes a cutoff-projected Ritz ground state of a small
gauge-invariant regulated SU(2) Hamiltonian in a truncated spin-network basis,
then extracts conditional block densities from that cutoff state. The target is
finite-lattice evidence about the conditional Poincare rate and the
conditional transport score that enter (YM29), (YM151) and (YM170). Character
cutoffs, the graph, coupling schedule, boundary fixtures, convergence
thresholds and stopping rules are fixed here before implementation. A
converged boundary row can supply a witness for the declared cutoff model;
surviving rows supply cutoff-qualified evidence only. A uniform all-boundary
estimate, cutoff removal, the thermodynamic limit and the continuum mass gap
remain separate analytical obligations.

## 1. Question and scope

For the cutoff-projected measure
\(d\mu_J^{\mathrm{Ritz}}=|\Omega_J|^2dU\), does a full-holonomy block retain
a positive conditional Poincare rate and a finite conditional \(H^{-1}\)
transport score when the boundary holonomy is varied through the compact SU(2)
domain?

Use the seven-link two-plaquette graph
\[
(0,1),(1,2),(3,2),(0,3),(1,5),(4,5),(0,4),
\]
with plaquette words
\[
(0,1)(1,1)(2,-1)(3,-1),
\qquad
(0,1)(4,1)(5,-1)(6,-1).
\]
The regulated dimensionless Hamiltonian is
\[
h_x=K+2xN_p-xS,
\qquad
K=-\sum_{e,A}(X_e^A)^2,
\qquad
S=\sum_p\operatorname{Tr}U_p,
\qquad x=2/g^4.
\]

Retain the full link Haar measure and the Gauss-invariant spin-network
subspace. Do not gauge-fix the Hamiltonian. The conditional block is
\(B=\{0,1,2,3\}\); the exterior links are \(B^c=\{4,5,6\}\). Boundary
values are conditioned before the block covariance and Dirichlet matrices are
formed. Boundary gauge redundancy is removed only through the declared
spin-network intertwiners and the compact boundary orbit; no Cartesian
Lie-algebra chart is used for the boundary variable.

The finite study has two outputs:

1. the conditional rate \(\lambda_{B,J}^{\mathrm{Ritz}}(\eta)\) on the
   retained block test space;
2. the Galerkin conditional transport diagnostic
   \(\vartheta_{B,J,J_s}^{2,\mathrm{Gal}}(\eta)\) for the scheduled boundary
   tangent and declared score cutoff \(J_s\).

The retained test-space rate is an upper estimate of the unrestricted
conditional spectral gap of the cutoff measure. A small converged value is
therefore a finite witness against a proposed lower bound for that cutoff
model; a large value does not prove the unrestricted inequality or its
cutoff-removed counterpart.

## 2. Fixed truncation and cutoff/Ritz construction

Use the Peter–Weyl irreducible spins
\[
j\in\{0,\tfrac12,1,\ldots,J\},
\qquad
J\in\{\tfrac12,1,\tfrac32,2,\tfrac52\}.
\]
Project every multiplication and electric-Casimir operation back into the
same Gauss-invariant spin-network space. The projected Hamiltonian is
diagonalized as a real symmetric matrix after fixing the positive phase of its
Ritz ground vector. The matrix is assembled from exact SU(2) representation
contractions; no Monte Carlo quadrature or Cartesian group grid is accepted as
the primary result.

Use nested cutoff spaces. The projected ground energy is a Ritz upper bound
for the finite graph's untruncated ground energy, but the cutoff study does
not supply a cutoff-error theorem. Every measure, conditional rate, score and
observable is therefore labeled by \(J\) and remains cutoff-qualified.
Residual control and cutoff-to-cutoff stability are recorded as numerical
qualification, not as a proof of convergence to the untruncated vacuum.

For each retained cutoff, record:

- the lowest Ritz eigenvalue;
  the projected eigensolver residual
  \(r_J^{\mathrm{proj}}=\|P_J(h_x-E_0)P_J\Omega_J\|_2\);
  and the full-space Ritz residual
  \(r_J^{\mathrm{full}}=\|(h_x-E_0)\Omega_J\|_2\);
- the first excited Ritz eigenvalue in the gauge-invariant sector;
- the full source and operation manifests bound by SHA-256;
- all conditional covariance, Dirichlet and score matrices used below.

The projected Ritz residual \(r_J^{\mathrm{proj}}\) must be at most
\(10^{-10}\). The full-space residual \(r_J^{\mathrm{full}}\) includes the
omitted \((I-P_J)h_xP_J\) component; it must be finite, must be recorded
separately, and must be at most \(10^{-2}\) for a row to qualify for
`SUPPORTS_FINITE_BLOCK`. For \(J<\tfrac52\), a cutoff row is internally
stable only when the ground energy, conditional rate and score norm change by
at most \(10^{-6}\) relative to the next scheduled cutoff, with absolute
scale \(10^{-10}\) used when the reference value is below one. The endpoint
\(J=\tfrac52\) is accepted as internally stable only when the same observable
bound holds against \(J=2\), the projected residual bound passes, the full
residual is at most \(10^{-2}\) and is no larger than its \(J=2\) value, and
the nested Ritz energies are nonincreasing. The endpoint rate and score remain
cutoff-qualified observables. This endpoint rule is fixed before execution
and does not certify the untruncated finite-lattice limit.

## 3. Coupling and boundary schedule

Use the fixed weak-field-directed schedule
\[
x\in\{\tfrac14,1,4,16\}.
\]
For the primary compact boundary slice, set the exterior data to the
one-parameter conjugacy representatives
\[
\eta(\theta):
\quad
U_4=\exp(i\theta\sigma_3/2),
\qquad
U_5=U_6=I,
\qquad
\theta\in
\{0,\tfrac\pi8,\tfrac\pi4,\tfrac{3\pi}8,
\tfrac\pi2,\tfrac{5\pi}8,\tfrac{3\pi}4,\tfrac{7\pi}8,\pi\}.
\]
The tangent schedule is the unit conjugacy-angle tangent at the interior
points \(\theta\in\{\pi/4,\pi/2,3\pi/4\}\), with endpoint rows retained
only as boundary controls. The tangent normalization is the Haar metric
induced by \(X^A\), not the Euclidean norm of a Lie-algebra coordinate.

These boundary rows probe a compact symmetry-reduced slice. They do not
quantify all exterior holonomies. No `PASS` for (YM29) or (YM151) may be
issued from this schedule alone. A future all-boundary study must add a
compact-domain enclosure or an analytic symmetry reduction covering the full
boundary orbit.

## 4. Conditional rate and transport score

For each converged Ritz state and boundary value, form
\[
\rho_{B,J}^{\mathrm{Ritz},\eta}(U_B)
:=\frac{|\Omega_J(U_B,\eta)|^2}
{\int|\Omega_J(U_B,\eta)|^2dU_B}.
\]
Let \(\mathcal T_{B,J}^{\eta}\) be the image, after restriction to the
declared boundary value, of the globally gauge-invariant truncated
spin-network functions on the full graph. Quotient only linear dependencies
in this image and remove its constant direction. This is the retained fibre
sector; arbitrary block functions are not silently substituted for the
restrictions of globally gauge-invariant functions.

On \(\mathcal T_{B,J}^{\eta}\) compute the generalized eigenproblem
\[
D_{B,J}^{\eta}v
:=\lambda\,C_{B,J}^{\eta}v,
\]
where \(C\) is the conditional covariance matrix and \(D\) is the sum of
left-generator Dirichlet matrices over \(e\in B\). Record
\[
\lambda_{B,J}^{\mathrm{Ritz}}(\eta)
:=\min_{v\ne0,\ C v\ne0}
\frac{v^*D_{B,J}^{\eta}v}{v^*C_{B,J}^{\eta}v}.
\]
The restriction map, its rank and the removed constant direction are part of
the receipt.

Before forming a logarithmic score, certify on the compact block domain that
\(\rho_{B,J}^{\mathrm{Ritz},\eta}\) has no zero on the scheduled conditional
slice. The certificate must use an interval or analytic representation bound;
a sampled minimum or a floating-point floor is insufficient. If the
certificate fails, the rate row may still be recorded, but the score row is
`INCONCLUSIVE`.

For a certified positive slice and the interior tangent \(\xi_\theta\), define
the centered conditional score
\[
s_{B,J,\theta}^{\mathrm{Ritz},\eta}
:=\partial_\theta\log\rho_{B,J}^{\mathrm{Ritz},\eta}
-\mathbb E_{\rho_{B,J}^{\mathrm{Ritz},\eta}}
 [\partial_\theta\log\rho_{B,J}^{\mathrm{Ritz},\eta}].
\]
The Poisson calculation uses its weak pairing rather than assuming that this
logarithmic function lies in the retained block basis. Use the full
block-compatible score spaces \(\mathcal S_{B,J_s}\) with
\(J_s\in\{J+\tfrac12,J+1\}\), remove their constant direction, and write
\(\{\phi_a\}\) for the resulting basis. Assemble
\[
b_a
:=\int \partial_\theta
\rho_{B,J}^{\mathrm{Ritz},\eta}(U_B)\,\phi_a(U_B)\,dU_B
=\langle s_{B,J,\theta}^{\mathrm{Ritz},\eta},\phi_a\rangle_
{\rho_{B,J}^{\mathrm{Ritz},\eta}},
\qquad
(D_s)_{ab}
:=\sum_{e\in B,A}\langle X_e^A\phi_a,X_e^A\phi_b\rangle_
{\rho_{B,J}^{\mathrm{Ritz},\eta}}.
\]
Solve the Galerkin weak Poisson problem
\[
D_s u=b
\]
and record the restricted transport value
\[
\vartheta_{B,J,J_s}^{2,\mathrm{Gal}}(\eta)
:=b^*D_s^{+}b.
\]
This is the \(H^{-1}\) supremum restricted to \(\mathcal S_{B,J_s}\), hence
it is a lower bound on the full conditional \(H^{-1}\) norm. Record the score
basis, the projection/Poisson residual \(\|D_su-b\|\), and the difference
between the two scheduled score cutoffs. A Galerkin value below the (YM151)
margin does not certify that margin; a converged Galerkin value above it is a
finite cutoff witness. If positivity is absent, no pointwise log-score is
substituted by a finite-difference quotient; the row remains `INCONCLUSIVE`
unless a separate weak density-derivative construction is supplied and
preregistered. Every matrix entry, eigenvalue, score component, Poisson
residual and quadratic-form value must be finite. The centered score residual
must be at most \(10^{-9}\), and the Galerkin Poisson residual must be at most
\(10^{-8}\).

## 5. Fixed go/no-go rules

For every schedule row classify the finite calculation as follows:

- `WITNESS_CONDITIONAL_COLLAPSE` if a converged rate is below the declared
  target \(\lambda_{\mathrm{target}}=10^{-3}\), or if the rate decreases by
  more than a factor of four between the two highest converged cutoffs;
- `WITNESS_SCORE_MARGIN_FAILURE` if a converged Galerkin lower diagnostic
  \(\vartheta_{B,J,J_s}^{2,\mathrm{Gal}}\) already exceeds the frozen
  transport margin (YM151) after inserting the independently computed coarse
  and vertical rates for this finite graph. A lower diagnostic above the
  margin is a valid witness because the full \(H^{-1}\) norm is no smaller;
  a lower diagnostic below the margin does not certify it;
- `SUPPORTS_FINITE_BLOCK` if every rate row converges, no conditional-collapse
  witness or score lower-bound witness is found, all required positivity and
  finite residual checks pass, and the result is labeled cutoff-qualified;
- `INCONCLUSIVE` if any scheduled row fails cutoff convergence, matrix
  positivity, residual control or score centering.

`SUPPORTS_FINITE_BLOCK` is a finite spectral result for the declared cutoff
model, graph and boundary slice. It does not establish the essential boundary
infimum required by (YM29), cutoff removal, a volume-uniform recovery floor,
or a continuum gap. A converged witness is retained as a counterexample to the
tested cutoff target and does not exclude other cutoffs or block families.

## 6. Evidence and implementation boundary

The implementation must be a new source and receipt pair. It must not append
rows to the Gaussian/full-holonomy control receipts in
`computations/yang-mills-vacuum-block-prereg.md` or to the local-chart receipt
in `computations/yang-mills-su2-transport-expansion-prereg.md`.

The receipt must bind this protocol, the source, the representation tables,
the graph, the cutoff schedule and every generated matrix by SHA-256. It must
refuse overwriting an existing receipt. An independent implementation must
reconstruct the representation contractions and the generalized eigenproblem
without importing the primary source or reading its intermediate matrices.

The first implementation target is the cutoff/Ritz ground-state and
conditional-rate calculation. The multiscale recovery floor
\(\mathscr R_n\succeq\gamma_*(I-\Pi_{\mathcal N_n})\), the all-boundary
transport estimate, the approximate-tensorization constant, cutoff removal
and the continuum construction remain later proof obligations.

## References

- `foundations/loop-to-bubble-projection-theorem.md` §§9.14, 9.21–9.22—conditional block rate, transport score, recovery Gramian and continuum obligations.
- `computations/yang-mills-vacuum-block-prereg.md`—regulated Hamiltonian normalization and finite full-holonomy controls.
- `computations/yang-mills-su2-transport-expansion-prereg.md`—local-chart score calculation and compact-boundary scaling diagnostic.
- `computations/yang-mills-recovery-gramian-prereg.md`—residual recovery and score-penalty separation.
