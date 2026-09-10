# Yang–Mills Residual Recovery and Score-Penalty Gramian Preregistration

## Status: Frozen protocol v4—September 2026

## 1. Question and scope

Which multiscale Gramian can supply the variance reconstruction still missing from the exact-vacuum Yang–Mills bounds?

The exact conditional theorems in `foundations/loop-to-bubble-projection-theorem.md` §§9.14, 9.20–9.21 contain two distinct operators:

1. conditional residual projections, whose lower coercivity is approximate tensorization;
2. transported-score operators, whose upper norm consumes physical gap margin.

These roles cannot be interchanged: the residual Gramian acts on the physical function Hilbert space, while the score Gramian acts on coarse tangent directions. A recovery-or-rigidity argument for variance must use residual projections. A lower bound on a score Gramian is not a gap mechanism. The result is an abstract finite-regulator theorem; it does not supply the exact-vacuum estimates, a thermodynamic limit, or a continuum Yang–Mills construction.

## 2. Frozen analytical obligations

### YMRG1. Residual Gramian and optimal tensorization

Let

\[
\mathcal H_{\rm phys}
=
\{f\in L^2(\mu):\mu(f)=0, f\text{ lies in the declared gauge-invariant sector}\}.
\]

Assume $\mathcal H_{\rm phys}$ is closed. Every conditional expectation below
preserves this sector and its common form domain. The block family is finite,
or its nonnegative weighted form sum is convergent on that domain.

For each conditional exterior sigma-algebra \(\mathcal F_B\), let

\[
P_Bf=\mathbb E_\mu(f\mid\mathcal F_B),
\qquad
R_B=I-P_B,
\]

On this invariant domain \(P_B\) is an orthogonal projection. For fixed weights \(w_B\ge0\), define

\[
\mathscr R
=
\sum_Bw_BR_B^*R_B
=
\sum_Bw_BR_B,
\]

and

\[
\gamma_{\rm rec}
=
\inf_{0\ne f\in\mathcal H_{\rm phys}}
\dfrac{\langle f,\mathscr Rf\rangle}{\|f\|_2^2}.
\]

The theorem must prove

\[
\sum_Bw_B\,
\mathbb E_\mu[\operatorname{Var}(f\mid\mathcal F_B)]
=
\langle f,\mathscr Rf\rangle,
\]

and therefore

\[
\boxed{A_{\rm AT}^{\rm opt}=\gamma_{\rm rec}^{-1}}
\]

when \(\gamma_{\rm rec}>0\). The zero-rate convention is
\(A_{\rm AT}^{\rm opt}=+\infty\).

The exact kernel is

\[
\ker\mathscr R
=
\bigcap_{B:w_B>0}\ker R_B
=
\bigcap_{B:w_B>0}\operatorname{Ran}P_B.
\]

A qualitative kernel identity does not imply a regulator-uniform positive \(\gamma_{\rm rec}\).

### YMRG2. Conditional rates imply a global rate only with recovery

All conditional and cover inequalities below hold on the same physical form
domain, with the displayed constants uniform over the declared block family.

Assume the conditional Poincaré estimates

\[
\|R_Bf\|_2^2
\le
\lambda_B^{-1}\mathcal E_B(f,f),
\qquad
\lambda_B\ge\lambda_{\rm loc}>0,
\]

and the cover estimate

\[
\sum_Bw_B\mathcal E_B(f,f)
\le
\rho\,\mathcal E(f,f).
\]

Then

\[
\boxed{
\lambda_{\rm gi}(\mu)
\ge
\dfrac{\gamma_{\rm rec}\lambda_{\rm loc}}{\rho}.
}
\]

This is (YM30) with \(A_{\rm AT}=1/\gamma_{\rm rec}\). The new statement identifies the precise recovery operator whose uniform lower spectrum is required.

For isometries \(T_{j\to n}:\mathcal H_n\to\mathcal H_j\) between declared scale Hilbert spaces, define the transported multiscale recovery Gramian

\[
\mathscr R_n
=
\sum_{j\le n}w_jT_{j\to n}^*R_jT_{j\to n}.
\]

Require
$R_jT_{j\to n}\Pi_{\mathcal N_n}=0$ for every positive-weight scale, so the
declared null subspace is contained in the Gramian kernel.

Let \(\mathcal N_n\) be a declared nonphysical null subspace. Before
centering it can contain constants; in an unreduced auxiliary
representation it can also encode gauge redundancies. The centered
gauge-invariant function space normally has these directions removed.
Quantitative recovery is

\[
\mathscr R_n
\succeq
\gamma_*\,(I-\Pi_{\mathcal N_n}),
\qquad
\gamma_*>0
\]

uniformly in regulator and scale. Rigidity is the additional statement
\(\ker\mathscr R_n=\mathcal N_n\); it does not follow from the displayed
null compatibility alone. Recovery additionally requires the uniform
positive spectral floor \(\gamma_*\).

### YMRG3. Score Gramian has the opposite sign role

Assume the conditional fibres are connected with the no-boundary or no-flux
form domain, the score components are centered in $H^{-1}$, and
$\mathcal L_V^{-1/2}$ acts on the orthogonal complement of constants.

Let

\[
\mathsf K_V:\xi\longmapsto
\mathcal L_V^{-1/2}s_{V,\xi}
\]

be the conditional transport-score operator of §9.21, so
\(\vartheta^2=\operatorname*{ess\,sup}_V\|\mathsf K_V\|_{\rm op}^2\).
For fixed \(\lambda_c,\lambda_{\rm fib}>0\), its one-step upper-bound matrix is

\[
M(\vartheta)
=
\begin{pmatrix}
(2\lambda_c)^{-1}&\vartheta/\lambda_c\\
\vartheta/\lambda_c&
2(\lambda_{\rm fib}^{-1}+\vartheta^2/\lambda_c)
\end{pmatrix}.
\]

The largest eigenvalue \(C_{-1}(\vartheta)\) is nondecreasing for
\(\vartheta\ge0\), because every entry of this nonnegative symmetric matrix is nondecreasing and its top eigenvector can be chosen nonnegative. Hence the certified rate \(C_{-1}^{-1}\) is nonincreasing.

A lower coercive bound on
\(\sum_jT_j^*\mathsf K_j^*\mathsf K_jT_j\) cannot replace the residual recovery bound. Score transport requires an upper estimate; residual recovery requires a lower estimate.

### YMRG4. Score-kernel counterexample

Use the centered product Gaussian

\[
d\mu(v,r)\propto e^{-v^2-2r^2}\,dv\,dr
\]

with standard Dirichlet energy \(|\partial_vf|^2+|\partial_rf|^2\). The conditional fibre law is independent of \(v\), so

\[
s_v=0,
\qquad
\mathsf K=0.
\]

The nonconstant coarse function \(f(v,r)=v\) selects the tangent direction
\(\xi=\partial_v\), and this direction lies in \(\ker\mathsf K\), while the
full Gaussian Poincaré rate is \(2\). Therefore a score near-kernel need not
be gauge or rigid; it can be a healthy coarse physical direction.

For the fibre-only conditional expectation
\(P_rf=\mathbb E(f\mid v)\), the residual \(R_r=I-P_r\) annihilates the
function \(v\). This shows that a block family which does not cover all
physical function directions has \(\gamma_{\rm rec}=0\), even when its
conditional rate is positive.

### YMRG5. Finite projection and quotient controls

Use three exact projection families.

1. Orthogonal recovery on \(\mathbb R^2\):
   \[
   R_1=e_1e_1^T,
   \qquad
   R_2=e_2e_2^T,
   \qquad
   \mathscr R=I,
   \qquad
   \gamma_{\rm rec}=1.
   \]
2. Near-parallel residuals on \(\mathbb R^2\):
   \[
   R_1=e_1e_1^T,
   \qquad
   R_2=r_\epsilon r_\epsilon^T,
   \qquad
   r_\epsilon=(\cos\epsilon,\sin\epsilon)^T.
   \]
   Their Gramian eigenvalues are
   \[
   1\pm|\cos\epsilon|.
   \]
   For the frozen range \(0<\epsilon<\pi/2\), the kernel is trivial and
   \(\gamma_{\rm rec}=1-\cos\epsilon\to0\) as \(\epsilon\downarrow0\).
   More generally the floor is \(1-|\cos\epsilon|\), and the kernel is
   trivial exactly when \(\epsilon\notin\pi\mathbb Z\). This is the frozen
   counterexample to qualitative rigidity implying uniform recovery.
3. Gauge-null control on \(\mathbb R^3\):
   \[
   \mathscr R=\operatorname{diag}(1,1,0),
   \qquad
   \mathcal N=\operatorname{span}\{e_3\}.
   \]
   The full-space minimum is zero and the quotient/physical minimum is one.

### YMRG6. Gaussian chain recovery

For the existing finite open Gaussian family

\[
D_N(m)=\operatorname{tridiag}(-1,2+m^2,-1),
\qquad
Q_N(m)=\sqrt{D_N(m)},
\qquad
d\mu_N\propto e^{-q^TQ_Nq}\,dq,
\]

let \(d_i=(Q_N)_{ii}\) and \(D=\operatorname{diag}(d_i)\). On first Gaussian chaos, the sum of one-coordinate conditional residual projections has Gram matrix


\[
G_N(m)=D^{-1/2}Q_N(m)D^{-1/2}.
\]

For the all-function statement, let $p_i$ be the first-chaos projection
associated with the conditional expectation $P_i$. On Gaussian chaos $k$,
$P_i=\Gamma(p_i)=p_i^{\otimes_s k}$, and

\[
I-p_i^{\otimes k}
\succeq
(I-p_i)\otimes I^{\otimes(k-1)}
\]

on the corresponding symmetrized range. The first-chaos lower bound
therefore holds on every higher chaos, while a linear function in the bottom
eigendirection saturates it.

The theorem must retain the exact identity

\[
\gamma_{\rm rec,N}(m)=\lambda_{\min}(G_N(m)),
\qquad
A_{\rm AT,N}^{\rm opt}=\gamma_{\rm rec,N}(m)^{-1}.
\]

At every finite \(N\), the common kernel is only the constants, but for \(m=0\)

\[
\dfrac{\lambda_{\min}(Q_N)}{\max_i d_i}
\le
\gamma_{\rm rec,N}(0)
\le
\dfrac{\lambda_{\min}(Q_N)}{\min_i d_i},
\qquad
\lambda_{\min}(Q_N)=2\sin\dfrac{\pi}{2(N+1)},
\]

so \(\gamma_{\rm rec,N}(0)\to0\). This is quantitative failure of uniform recovery despite exact finite rigidity. For \(m=1/2\), the fixed schedule records the positive massive control without transferring it to Yang–Mills.

## 3. Fixed verification schedule

Two implementations are required:

1. `computations/verify_yang_mills_recovery_gramian.py` is the primary NumPy verifier.
2. `computations/verify_yang_mills_recovery_gramian_independent.mjs` uses an explicit sine construction, independent Jacobi eigensolver, and direct projection algebra without importing the Python source.

The primary has exactly **58 checks**:

- 4 near-parallel rows at
  \(\epsilon\in\{1/2,1/4,1/8,1/16\}\), with 2 checks each for the exact eigenvalues and positive-but-decreasing recovery floor: 8;
- 2 orthogonal-recovery checks and 2 gauge-quotient checks: 4;
- 4 score rows at
  \(\vartheta\in\{0,1/10,1/2,1\}\), with 2 checks each for closed/direct eigenvalue agreement and monotone loss of the certified rate at
  \((\lambda_c,\lambda_{\rm fib})=(1,2)\): 8;
- 4 product-counterexample checks: zero score, nonconstant score-kernel witness, exact positive global rate, and zero recovery for the incomplete block family: 4;
- 10 Gaussian rows from
  \((N,m)\in\{4,8,16,32,64\}\times\{0,1/2\}\), with 3 checks each for the sine/eigen square root, residual-Gramian/tensorization identity, and finite-kernel plus Rayleigh bounds: 30;
- 4 transported quotient-Gramian checks for a fixed three-scale orthogonal fixture: construction, gauge null, physical floor, and transported quadratic identity: 4.

The independent verifier has exactly **30 checks**:

- 8 protocol/source/tolerance/count/summary integrity checks;
- one reconstruction for each of 4 near-parallel rows;
- one orthogonal and one gauge-quotient reconstruction;
- one reconstruction for each of 4 score rows;
- one product-counterexample reconstruction;
- one reconstruction for each of 10 Gaussian rows;
- one transported quotient-Gramian reconstruction.

The fixed transported fixture uses \(\mathbb R^3\), gauge null
\(\mathcal N=\operatorname{span}\{e_3\}\), residuals
\(R_0=e_1e_1^T\), \(R_1=e_2e_2^T\), \(R_2=e_1e_1^T\), weights
\((1/2,1,1/2)\), and transports
\(T_0=I\), \(T_1=\operatorname{diag}(-1,1,1)\),
\(T_2=\operatorname{diag}(1,-1,1)\). Its accumulated Gramian is
\(\operatorname{diag}(1,1,0)\). The quadratic identity uses exactly

\[
x_1=(1,2,3)^T,\quad
x_2=(-2,1/2,1)^T,\quad
x_3=(0,1,-4)^T,\quad
x_4=(\sqrt2,-\pi,1/4)^T.
\]

The matrix normalized error is operator norm divided by the larger of one and the reference operator norm. Scalar normalized error is absolute difference divided by the larger of one and the reference magnitude. Primary tolerance is \(10^{-11}\); independent comparison tolerance is \(10^{-9}\). The fixed rows, checks, weights, transports, vectors, and tolerances may not change after execution.

Primary receipt:

`runs/yang_mills_recovery_gramian/verification.json`.

Independent receipt:

`runs/yang_mills_recovery_gramian/verification-independent.json`.

Both bind the protocol and sources by SHA-256. The independent receipt also binds the primary receipt and rejects altered counts, tolerances, failed checks, duplicate check names, or row schedules.

## 4. Decision rule

- **PASS:** all 58 primary and 30 independent checks pass.
- **FAIL:** a frozen identity, spectrum, monotonicity, counterexample, count, tolerance, or source binding disagrees.
- **INCONCLUSIVE:** required execution or identity evidence is absent.

A PASS supports the implementation and finite projection/Gaussian controls. Analytical adoption additionally requires a direct proof and independent review. No finite result supplies uniform exact-vacuum recovery, a score upper bound, or a continuum Yang–Mills mass gap.

## 5. Stopping rule

Run the primary once after the protocol, both implementations and analytical review are complete. Run the independent verifier once against the primary receipt. Any protocol or source repair requires a new version or source-bound rerun with the complete schedule retained.

## 6. Sources fixed before execution

- `foundations/loop-to-bubble-projection-theorem.md` §§9.13–9.14, 9.20–9.21—exact vacuum, tensorization, score and transport recurrences.
- `computations/yang-mills-vacuum-block-prereg.md` §§1, 4—conditional rates and Gaussian tensorization controls.
- `turbulence/navier-stokes-replica-coherence.md`—source of the recovery-or-rigidity analogy; no Navier–Stokes field or estimate enters the Yang–Mills theorem.
- S. Janson, *Gaussian Hilbert Spaces*—conditional projections and Wiener-chaos reduction.
- J. von Neumann, *Functional Operators, Volume II*—orthogonal projections and Hilbert-space spectral theory.
