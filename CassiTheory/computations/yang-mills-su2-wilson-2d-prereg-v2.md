# Normalization-Corrected SU(2) Wilson Schwinger Bridge in Two Dimensions

## Status: Pre-registered analytic verification—September 2026

## Abstract

This protocol fixes the normalized-Haar character coefficient and the gluing eigenvalue of the two-dimensional SU(2) Wilson model before either corrected verifier is executed. The coefficient multiplying an irreducible character is derived by Haar orthogonality; one factor of the representation dimension is then removed, exactly once, by character convolution. The primary uses adaptive Haar quadrature and modified Bessel functions. The independent implementation uses midpoint Haar quadrature and a positive Bessel series.

The result is a finite two-dimensional benchmark. It does not construct a four-dimensional Gibbs state, a continuum limit or a physical Yang–Mills mass gap.

## 1. Haar coefficient and gluing normalization

Write an SU(2) conjugacy class as

$$
U\sim\operatorname{diag}(e^{i\theta},e^{-i\theta}),
\qquad 0\leq\theta\leq\pi,
$$

and index irreducible characters by their dimension

$$
n=2j+1=1,2,3,\ldots,
\qquad
\chi_n(\theta)=\frac{\sin(n\theta)}{\sin\theta}.
$$

Normalized Haar integration of a class function is

$$
\int_{SU(2)}f(U)\,dU
=
\frac2\pi\int_0^\pi f(\theta)\sin^2\theta\,d\theta,
\qquad
\int\chi_n\chi_m\,dU=\delta_{nm}.
\tag{YMW2-1}
$$

For the Wilson plaquette weight

$$
w_\beta(U)
:=
\exp\!\left(\frac\beta2\operatorname{Tr}U\right)
=
e^{\beta\cos\theta},
\qquad \beta>0,
$$

the coefficient multiplying $\chi_n$ is therefore

$$
\begin{aligned}
C_n(\beta)
&:=\int_{SU(2)}w_\beta(U)\chi_n(U)\,dU\\
&=\frac2\pi\int_0^\pi e^{\beta\cos\theta}
\sin\theta\sin(n\theta)\,d\theta\\
&=I_{n-1}(\beta)-I_{n+1}(\beta)
=\frac{2n}{\beta}I_n(\beta)>0.
\end{aligned}
\tag{YMW2-2}
$$

Thus

$$
\boxed{
w_\beta(U)=\sum_{n=1}^{\infty}C_n(\beta)\chi_n(U)
=\sum_{n=1}^{\infty}n\,r_n(\beta)\chi_n(U),
\qquad
r_n(\beta):=\frac{C_n(\beta)}n=\frac{2I_n(\beta)}\beta.
}
\tag{YMW2-3}
$$

The quotient in (YMW2-3) is fixed by the normalized-Haar convolution identity

$$
\int_{SU(2)}
\chi_n(AU)\chi_m(U^{-1}B)\,dU
=
\frac{\delta_{nm}}n\chi_n(AB).
\tag{YMW2-4}
$$

Each internal-link gluing removes the representation dimension already present in $C_n$. There is no second division by $n$.

## 2. Torus partition function and transfer-vacuum correlator

On a periodic rectangular two-dimensional lattice with spatial length $L_s$, temporal length $L_t$ and area $A=L_sL_t$, character gluing gives

$$
Z_{L_s,L_t}(\beta)
=
\sum_{n\geq1}r_n(\beta)^A,
\qquad
Z_{N,L_s,L_t}(\beta)
=
\sum_{n=1}^{N}r_n(\beta)^A.
\tag{YMW2-5}
$$

The zero-temperature transfer-vacuum correlator of the fundamental character is

$$
C_{L_s,\beta}(t)
:=
\left(\frac{r_2(\beta)}{r_1(\beta)}\right)^{L_st},
\qquad t\in\mathbb N_0,
\tag{YMW2-6}
$$

because $\chi_2\chi_1=\chi_2$. Its one-step effective mass is

$$
m_{\mathrm{eff}}(L_s,\beta)
:=
-\log\frac{C(t+1)}{C(t)}
=
L_s\log\frac{r_1(\beta)}{r_2(\beta)}.
\tag{YMW2-7}
$$

Equation (YMW2-6) is a transfer-vacuum matrix element. It is not the finite-$L_t$ thermal torus correlator; $L_t$ enters the partition and tail checks in (YMW2-5).

## 3. Corrected character tail

The positive Bessel series gives

$$
I_n(\beta)
\leq
\frac{(\beta/2)^n}{n!}e^{\beta^2/4}.
$$

Consequently

$$
r_n(\beta)
\leq
q_n(\beta)
:=
\frac{2e^{\beta^2/4}}\beta
\frac{(\beta/2)^n}{n!},
\qquad
\frac{q_{n+1}}{q_n}=\frac\beta{2(n+1)}.
\tag{YMW2-8}
$$

For $n\geq N+1$ and the frozen schedule below,

$$
\rho_{N,\beta}:=\frac\beta{2(N+2)}<1,
$$

so the omitted torus weight satisfies

$$
0\leq R_{N,A}(\beta)
:=\sum_{n>N}r_n(\beta)^A
\leq
\frac{q_{N+1}(\beta)^A}{1-\rho_{N,\beta}^{A}}.
\tag{YMW2-9}
$$

The receipt records both ordinary and logarithmic forms of this bound.

## 4. Frozen schedules and checks

Use

$$
\beta\in\{1,2,4\},
\quad
L_s,L_t\in\{1,2,4\},
\quad
N\in\{8,16,24,32\},
\quad
t\in\{0,1,2,4\}.
\tag{YMW2-10}
$$

The independent Haar schedule is $n\in\{1,2,\ldots,8\}$ at every declared $\beta$. There are 108 parameter rows. Each row has exactly ten checks:

1. all retained $C_n$ and $r_n$ values are finite and positive;
2. numerical Haar quadrature agrees with $C_n=2nI_n/\beta$ on the eight-order Haar schedule;
3. $C_n/n=r_n$ for every retained representation;
4. the rejected double division $r_n/n$ differs from $r_n$ by at least one half in relative magnitude at $n=2$;
5. $r_n$ is strictly decreasing over the retained schedule;
6. all four transfer-vacuum correlators satisfy (YMW2-6);
7. every one-step effective mass satisfies (YMW2-7);
8. the corrected positive tail bound (YMW2-9) is finite in logarithmic form and has $0<\rho_{N,\beta}<1$;
9. the 64-term omitted-tail probe lies below (YMW2-9) and the retained partition is positive;
10. $A=L_sL_t$.

The primary has 1,080 row checks and twelve top-level source, schema, schedule and count checks, for exactly 1,092 checks. The independent receipt has twelve top-level checks and one complete independent reconstruction for each of the 108 rows, for exactly 120 checks.

## 5. Implementations and receipts

The primary implementation is

`computations/verify_yang_mills_su2_wilson_2d.py`.

The independent implementation is

`computations/verify_yang_mills_su2_wilson_2d_independent.mjs`.

The corrected receipts are

- `runs/yang_mills_su2_wilson_2d/verification-v2.json`;
- `runs/yang_mills_su2_wilson_2d/verification-independent-v2.json`.

Both implementations refuse to overwrite an existing receipt without an explicit replacement flag. The primary evaluates Bessel functions with the installed numerical library and Haar coefficients by adaptive quadrature. The independent source evaluates Bessel functions from their positive series and Haar coefficients by deterministic midpoint quadrature. It imports neither the primary source nor primary arrays. The primary scalar tolerance is $10^{-11}$, its Haar relative tolerance is $10^{-9}$, and the independent comparison tolerance is $10^{-9}$.

## 6. Decision contract

`PASS` requires all 1,092 primary checks and all 120 independent checks to pass with current protocol and source hashes. It also requires the double-division control to fire in every row.

`FAIL` records any Haar-normalization, convolution quotient, firing-control, transfer, correlator, effective-mass, tail, source-identity or count failure.

`INCONCLUSIVE` records missing execution or missing finite-value evidence.

A `PASS` establishes the normalization-corrected finite two-dimensional Wilson benchmark and its declared tail bound. It supplies no four-dimensional thermodynamic state, OS reconstruction, lattice-spacing limit or regulator-independent mass gap.

The unversioned protocol and its unversioned receipts use the rejected double-division normalization and carry no active evidence claim.

## References

- K. Osterwalder and E. Seiler, “Gauge field theories on a lattice,” *Annals of Physics* **110**, 440–471 (1978), [doi:10.1016/0003-4916(78)90039-8](https://doi.org/10.1016/0003-4916(78)90039-8).
- M. Lüscher, “Construction of a selfadjoint, strictly positive transfer matrix for euclidean lattice gauge theories,” *Communications in Mathematical Physics* **54**, 283–292 (1977), [doi:10.1007/BF01614090](https://doi.org/10.1007/BF01614090).
- `computations/yang-mills-su2-wilson-2d-prereg.md`—invalidated normalization retained as defect provenance.
- `foundations/loop-to-bubble-projection-theorem.md`—regulated Yang–Mills results and the continuum boundary.
- Clay Mathematics Institute, *Yang–Mills and Mass Gap*—continuum target.
