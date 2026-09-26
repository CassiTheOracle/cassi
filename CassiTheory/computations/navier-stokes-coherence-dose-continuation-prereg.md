# Coherence-Dose Continuation Criterion: Fixed Verification Schedule

## Status: Pre-registered—September 2026

## Abstract

This schedule checks a conditional continuation criterion extracted from the positive-minus-positive replica identity. The criterion bounds enstrophy when the accumulated positive active seeded rate has a uniform data-ball bound, or when the retarded covariance spread cancels the seeded occupation up to a uniform remainder. Exact symbolic algebra checks the implications and the strain-operator bound. Closed-form periodic shear, rank-two Beltrami, ABC, and homogeneous extensional controls test the stated scope. The schedule makes no generic Navier–Stokes trajectory claim and leaves the all-data dose, retarded-compensation, and global-regularity questions unresolved.

## 1. Scope and equations

The schedule concerns a smooth mean-zero divergence-free solution on a compact interval before a possible singular time. The source note is `turbulence/navier-stokes-coherence-dose-criterion.md`; the parent replica identities are in `turbulence/navier-stokes-replica-coherence.md`.

For $W(0)>0$, define

$$
G(t)=\int_0^t\Gamma_M(s)\,ds,
\qquad
G_+(t)=\int_0^t(\Gamma_M(s))_+\,ds,
\qquad
A_M(t)=W(0)e^{2G(t)}.
\tag{RCD1}
$$

The retarded covariance spread is nonnegative and the exact identity is

$$
\mathcal V(t)=2\nu\int_0^tD(s)\mathbb E_{\eta_s,B}
\exp\left(2\int_s^t\sigma_r^{s,a,k}\,dr\right)ds\ge0,
\qquad
W(t)=A_M(t)-\mathcal V(t).
\tag{RCD2}
$$

Therefore a positive-dose bound gives

$$
W(t)\le W(0)e^{2G_+(t)}.
\tag{RCD3}
$$

On the normalized torus, an initial $H^3$ bound gives $W(0)\le\|u_0\|_{H^3}^2$. A retarded-spread compensation bound has the form

$$
\mathcal V(t)\ge A_M(t)-C_{\mathrm{ret}}.
\tag{RCD4}
$$

Finally, for $M\succeq0$ and symmetric $S$,

$$
\Gamma_M(t)=\frac{\int S:M\,dx}{\mathcal E_M(t)}
\le\|S(t)\|_{L^\infty(\operatorname{op})}.
\tag{RCD5}
$$

## 2. Fixed check inventory

The verifier must execute exactly 16 checks with these ordered names:

1. `C1 positive-minus-positive identity`
2. `C2 retarded-spread upper bound`
3. `C3 positive-dose domination`
4. `C4 data-ball continuation envelope`
5. `C5 retarded compensation implication`
6. `C6 strain-rate operator-norm bound`
7. `X1 periodic shear occupation identity`
8. `X2 periodic shear active dose`
9. `X3 rank-two Beltrami Navier-Stokes identities`
10. `X4 rank-two singular source control`
11. `X5 ABC Navier-Stokes identities`
12. `X6 ABC enstrophy production cancellation`
13. `X7 ABC finite strain dose`
14. `X8 homogeneous extensional dose`
15. `I1 protocol tags and inventory`
16. `I2 note anchors and unresolved scope`

## 3. Decision tree

1. If a symbolic implication or exact-control check fails, classify the run `FAIL` and propagate no result.
2. If all checks pass, classify the active-dose implication, the retarded-spread implication, the operator-norm rate bound, and the four control calculations as `SUPPORTS` at their stated conditional scope.
3. Keep a uniform initial-data-ball bound on $G_+$, a uniform retarded-spread estimate, and arbitrary-data three-dimensional Navier–Stokes regularity `UNRESOLVED`.
4. The shear control must retain $J=0$ and $\Gamma_M=0$; the rank-two Beltrami control must retain $J=0$ while allowing accumulated covariance recovery; the ABC control must retain $J(0)>0$; the affine control must remain outside the periodic Navier–Stokes class.
5. No generic trajectory integration, stochastic-flow Monte Carlo, fitted constant, Cassi constitutive term, or claim of a global-regularity proof is within scope.

## 4. Evidence boundary

The schedule verifies finite symbolic consequences of the exact occupation identity and exact closed-form control formulas. The periodic Prodi–Serrin bridge is used analytically as a conditional implication. The schedule does not produce the uniform positive-dose estimate or the retarded-spread lower bound required for arbitrary-data regularity. The strain-operator estimate is a continuation-level bound and is not classified as a data-uniform closure.

The receipt must bind raw SHA-256 identities for this protocol, the source note, and `computations/verify_navier_stokes_coherence_dose.py`. Generated evidence remains local and untracked.

## 5. Sources

- `turbulence/navier-stokes-coherence-dose-criterion.md`—conditional active-dose and retarded-spread continuation criterion
- `turbulence/navier-stokes-replica-coherence.md`—replica occupation identity and periodic continuation bridge
- `computations/verify_navier_stokes_coherence_dose.py`—fixed symbolic and exact-control verifier
- P. Constantin and G. Iyer, [A stochastic Lagrangian representation of the three-dimensional incompressible Navier–Stokes equations](https://arxiv.org/abs/math/0511067)—stochastic Cauchy representation
- J. Serrin, [On the interior regularity of weak solutions of Navier–Stokes equations](https://link.springer.com/article/10.1007/BF00253344)—velocity Prodi–Serrin continuation criterion
