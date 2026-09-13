# Fixed-Graph Interacting Feshbach Resolvent Test

## Status: Pre-registered—September 2026

## Abstract

This finite-regulator study measures the discarded-sector resolvent and
Feshbach self-energy for the smallest existing interacting two-plaquette
SU(2) Hamiltonian with a nested spin-network cutoff. It turns the first
analytic requirement in (YM262) into a finite matrix inequality. The result
is a fixed-graph diagnostic: it can establish the inequality for the declared
cutoff matrix and can expose failure of the Schur lower bound, but it supplies
no uniform weak-coupling, volume, cutoff-removal or continuum estimate.

## 1. Fixed graph and Hamiltonian

Use the seven-link two-plaquette graph and the exact representation
contractions implemented by
`computations/verify_yang_mills_exact_block_spectrum.py`. The source uses
doubled-spin cutoff arguments. Use retained source cutoff $c_P=1$ and full
source cutoff $c_Q=3$; these are the smallest nested source spaces in this
operator with 4 and 23 raw gauge-invariant states, respectively. The
corresponding maximum link spins are $1/2$ and $3/2$. The physical labels
$C_P$ and $C_Q$ below refer to these two retained/full levels, not to the
raw array dimensions. Use the dimensionless Hamiltonian

$$
\widehat H_x=S^{-1/2}H_xS^{-1/2},
\qquad x\in\left\{\tfrac14,1,4,16\right\},
$$

with $H_x$ and the diagonal generalized overlap $S$ supplied by
`SpectrumSpace`. The normalization converts the generalized spin-network
matrix to an ordinary Hermitian matrix.

For each scheduled $x$, let $E_0$ and $\Omega$ be the lowest eigenvalue and
normalized eigenvector of $\widehat H_x$. Work in the vacuum-orthogonal space
$\mathcal K=\Omega^\perp$, which has dimension $22$ for the full $23$-state
source space. Let $L$ be the coordinate subspace spanned by the nested
$c_P=1$ states. Its vacuum-orthogonal image has rank $4$. Define the retained
interacting fibre and its discarded complement

$$
\mathcal P=\operatorname{ran}\bigl((I-|\Omega\rangle\langle\Omega|)L\bigr),
\qquad
\mathcal Q=\mathcal K\ominus\mathcal P,
\qquad
\dim\mathcal P=4,\quad\dim\mathcal Q=18.
$$

The test uses orthonormal frames $V_P,V_Q$ for these two spaces and the exact
finite blocks of $\widehat H_x-E_0$:

$$
A=V_P^*(\widehat H_x-E_0)V_P,
\qquad
B=V_P^*(\widehat H_x-E_0)V_Q,
\qquad
D=V_Q^*(\widehat H_x-E_0)V_Q.
$$

## 2. Discarded-sector resolvent target

Set

$$
\alpha=\lambda_{\min}(A),
\qquad
\delta_Q=\lambda_{\min}(D),
\qquad
\beta=\|B\|_2.
$$

For every $0\le\lambda<\delta_Q$, the required finite discarded-sector
resolvent estimate is

$$
\left\|(D-\lambda I)^{-1}\right\|_2
\le \frac{1}{\delta_Q-\lambda}.
\tag{F1}
$$

The associated Feshbach self-energy is

$$
\Sigma(\lambda)=B(D-\lambda I)^{-1}B^*,
$$

and its norm must obey

$$
\|\Sigma(\lambda)\|_2
\le \frac{\beta^2}{\delta_Q-\lambda}.
\tag{F2}
$$

A sufficient finite-dimensional Schur lower bound is

$$
\Phi(\lambda):=
\alpha-\lambda-\frac{\beta^2}{\delta_Q-\lambda}>0.
\tag{F3}
$$

When $\Phi(0)>0$, record the positive root

$$
\gamma_{\mathrm{Fesh}}
:=\frac{\alpha+\delta_Q-
\sqrt{(\alpha-\delta_Q)^2+4\beta^2}}{2}.
\tag{F4}
$$

The measured finite-graph gap must satisfy
$\Delta_x\ge\gamma_{\mathrm{Fesh}}$ up to numerical tolerance whenever
(F3) supplies a positive root. This is the finite Schur-complement
conclusion used by the test; it is not a regulator-uniform version of
(YM262).

## 3. Schedule and controls

The primary schedule is exactly
$x\in\{1/4,1,4,16\}$. For each row, record the raw source dimensions,
the post-projection ranks of $\mathcal P$ and $\mathcal Q$, $E_0$, the finite
gap $\Delta_x$, $\alpha$, $\delta_Q$, $\beta$, the resolvent norm at
$\lambda_{\mathrm{test}}=\frac12\min(\Delta_x,\delta_Q)$, the bound in
(F1), the self-energy norm and (F2), $\Phi(0)$, the ratio
$\beta^2/(\alpha\delta_Q)$, and $\gamma_{\mathrm{Fesh}}$ when defined.

The executable checks are:

1. the raw nested/full source dimensions are $(4,23)$ and the post-projection
   ranks are $\dim\mathcal P=4$, $\dim\mathcal Q=18$;
2. the normalized Hamiltonian is Hermitian and its ground residual is below
   $10^{-11}$;
3. $\alpha>0$ and $\delta_Q>0$ on every scheduled row;
4. (F1) holds at $\lambda_{\mathrm{test}}$ to relative tolerance
   $10^{-10}$;
5. (F2) holds at $\lambda_{\mathrm{test}}$ to relative tolerance
   $10^{-10}$;
6. the direct Feshbach matrix is positive at $\lambda_{\mathrm{test}}$
   and its minimum eigenvalue is no smaller than $\Phi(\lambda_{\mathrm{test}})$
   within $10^{-10}$ absolute tolerance;
7. whenever $\Phi(0)>0$, the measured gap is no smaller than (F4) within
   $10^{-10}$ absolute tolerance;
8. the tail-floor control marks $\lambda=\delta_Q$ as an invalid resolvent
   point without evaluating an inverse there, demonstrating that (F1) has
   the declared domain.

The finite estimate is classified `SUPPORTS_FINITE_FESHBACH` only when every
scheduled row has a positive $\gamma_{\mathrm{Fesh}}$. Rows with valid
resolvent identities but $\Phi(0)\le0$ are retained as
`NO_POSITIVE_SCHUR_CERTIFICATE` and are not execution failures. A failure of
an identity or numerical control is `INCONCLUSIVE`.

## 4. Evidence boundary

The receipt is source-bound to this protocol and the exact block-spectrum
source. It is written once to
`runs/yang_mills_interacting_feshbach/verification.json` and refuses to
overwrite an existing receipt. All numbers are finite graph, finite cutoff
and dimensionless. They do not establish a constant independent of lattice
spacing, spatial volume or weak-coupling trajectory, and they do not establish
(YM262), (YM265), (YM266), a continuum Hamiltonian or a Yang–Mills mass gap.

## References

- `foundations/loop-to-bubble-projection-theorem.md` §§9.17, 9.19.2 and 9.34—interacting fibre, discarded-sector Feshbach operator and uniform lower-form criterion.
- `computations/verify_yang_mills_exact_block_spectrum.py`—exact finite SU(2) representation contractions and nested cutoff Hamiltonian.
- `computations/yang-mills-exact-block-spectral-prereg.md`—fixed seven-link graph and cutoff conventions.
