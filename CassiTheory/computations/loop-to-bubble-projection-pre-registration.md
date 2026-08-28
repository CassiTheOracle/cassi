# Loop-to-Bubble Projection Verification Pre-Registration

## Status: Pre-registration—August 2026

## Purpose

This computation checks the finite identities used by
`foundations/loop-to-bubble-projection-theorem.md`. It tests the exact
projection of a phase-bearing, counteroriented loop population to the canonical
Yang/Yin densities, the associated coherence-matrix bubble map, the frozen
internal-mode spectrum, and the fivefold and alternating-phase corollaries.
It does not test whether the microscopic channels, their phases, or their
rates are physically realized. It does not derive quantum mechanics or a
universal spatial scale ratio.

## Frozen construction

At each bubble-scale point $x$, the microscopic support is one shared loop
$\chi\in[0,2\pi)$ with direction label $s\in\{+1,-1\}$ and carrier label
$a\in\{Y,I\}$. The nonnegative populations are
$f_{a,s}=|\psi_{a,s}|^2$. Their projection is

$$
E_a(x,t)=\sum_s\frac{1}{2\pi}\int_0^{2\pi}f_{a,s}(x,\chi,t)\,d\chi.
$$

The microscopic population equation uses one common exterior velocity $u$,
one common exterior diffusivity $D_x$, loop angular rate $\Omega=v/R$, loop
diffusion rate $d=D_\ell/R^2$, direction-exchange rate $r\geq0$, and the
projected canonical gate

$$
\kappa(x,t)=\lambda[1-q(E_Y,E_I)].
$$

Its four equations are

$$
\begin{aligned}
\partial_t f_{Y,s}
={}&-u\partial_xf_{Y,s}+D_x\partial_x^2f_{Y,s}
-s\Omega\partial_\chi f_{Y,s}+d\partial_\chi^2f_{Y,s}
+r(f_{Y,-s}-f_{Y,s})
-\kappa f_{Y,s}+\varphi\kappa f_{I,s},\\
\partial_t f_{I,s}
={}&-u\partial_xf_{I,s}+D_x\partial_x^2f_{I,s}
-s\Omega\partial_\chi f_{I,s}+d\partial_\chi^2f_{I,s}
+r(f_{I,-s}-f_{I,s})
+\kappa f_{Y,s}-\varphi\kappa f_{I,s}.
\end{aligned}
$$

The phase fields are kinematic data for the projection check; no phase
evolution law is frozen.

For the bubble map, define

$$
c=\sum_s\frac{1}{2\pi}\int_0^{2\pi}
\psi_{Y,s}^{*}\psi_{I,s}\,d\chi,
\qquad
\mathbf n=\frac{1}{\rho}
\bigl(2\operatorname{Re}c,2\operatorname{Im}c,E_Y-E_I\bigr),
\qquad \rho=E_Y+E_I.
$$

The affine bubble point is $\mathbf X=D\mathbf n$ with
$D=\operatorname{diag}(3,2,5/4)$.

## Frozen numerical inputs

- Golden ratio: $\varphi=(1+\sqrt5)/2$.
- Projection grid: periodic $N_x=7$, $N_\chi=12$ deterministic positive
  populations.
- Projection rates: $u=0.31$, $D_x=0.17$, $R=1.7$, $v=0.8$,
  $D_\ell=0.13$, $r=0.6$, $\lambda=0.04$.
- Canonical bounded coherence:
  $q=\rho^2/(\rho^2+\varphi^{-2}+\varepsilon^2)$ with
  $\varepsilon=E_Y-\varphi E_I$.
- Spectrum checks: $E_Y=1.1$, $E_I=0.7$ for the frozen $\kappa$ and
  $m=-6,\ldots,6$, plus one case with $|\Omega|>r$ and the pure-ballistic
  boundary $d=r=0$.
- Alternating layers: common composition, equal weights, initial phase
  $\delta=0.37$, and layer counts $K=2,\ldots,9$.
- Fivefold check: the canonical attractor composition
  $E_Y/E_I=\varphi$ and phases $\delta_j=2\pi j/5$.
- Double-precision absolute tolerance: $10^{-11}$.
- Python with NumPy; no optimizer, fit, random input, or external data.

## Frozen gates

### LB1—Exact zero-mode closure

A periodic finite-difference evaluation of the four microscopic right-hand
sides must project to

$$
\begin{aligned}
\partial_tE_Y&=-u\partial_xE_Y+D_x\partial_x^2E_Y
-\kappa(E_Y-\varphi E_I),\\
\partial_tE_I&=-u\partial_xE_I+D_x\partial_x^2E_I
+\kappa(E_Y-\varphi E_I)
\end{aligned}
$$

at every exterior grid point. The maximum component residual must be at most
$10^{-11}$.

### LB2—Conservation, positivity, and fixed composition

For frozen $\kappa,r\geq0$, the local reaction/exchange generator must have
nonnegative off-diagonal entries and zero column sums. Its uniform,
direction-balanced fixed vector must have $E_Y/E_I=\varphi$. The largest
algebraic residual must be at most $10^{-11}$.

### LB3—Coherence matrix and affine bubble

For deterministic phase-bearing loop amplitudes, the Hermitian matrix

$$
\Gamma=\begin{pmatrix}E_Y&c^*\\c&E_I\end{pmatrix}
$$

must be positive semidefinite, $|c|^2\leq E_YE_I$, and
$\mathbf X^TD^{-2}\mathbf X\leq1$. A proportional carrier pair must saturate
all three bounds and lie on the shell. A nonproportional pair must lie in the
interior. The maximum equality residual must be at most $10^{-11}$ and every
inequality slack must have the required sign within tolerance.

### LB4—Alternating-phase cancellation

For equal layer weights and phases $\delta_j=\delta+j\pi$, the normalized
coherence factor

$$
\zeta_K=K^{-1}\sum_{j=0}^{K-1}e^{i\delta_j}
$$

must vanish for even $K$ and satisfy $|\zeta_K|=1/K$ for odd $K$. The maximum
residual must be at most $10^{-11}$.

### LB5—Internal-mode spectrum and gap

With exterior derivatives suppressed and $\kappa$ frozen, the four population
generator eigenvalues for loop Fourier integer $m$ must equal

$$
\Lambda_{m,c,\pm}
=-dm^2+c-r\pm\sqrt{r^2-m^2\Omega^2},
\qquad
c\in\{0,-\kappa(1+\varphi)\}.
$$

The numerical and closed-form eigenvalue multisets must agree to
$10^{-11}$. At $m=0$ the spectrum must be

$$
\{0,-2r,-\kappa(1+\varphi),-2r-\kappa(1+\varphi)\}.
$$

The frozen positive-gap case must agree with

$$
g_{\rm int}=\min\left\{
\kappa(1+\varphi),\;2r,\;
 d+r-\operatorname{Re}\sqrt{r^2-\Omega^2}
\right\}.
$$

The pure-ballistic boundary $d=r=0$ must have zero real spectral gap.

### LB6—Projection non-injectivity

Two phase assignments with identical four populations must have identical
$(E_Y,E_I)$ while producing different $c$ and different affine bubble points.
The density residual must be at most $10^{-11}$ and the coherence/bubble
separation must exceed $10^{-3}$.

### LB7—Fivefold visibility corollary

At fixed composition, multiplying the coherence by
$\eta\in\{1,3/4,1/4\}$ must multiply every transverse fivefold orbit radius
and chord by $\eta$. For every $\eta>0$, the normalized pentagram-to-pentagon
chord ratio must remain $\varphi$. At $\eta=0$, all five transverse points
must coincide. The maximum residual must be at most $10^{-11}$.

## Decision and stopping rule

- **PASS:** LB1–LB7 all pass on the first completed execution.
- **FAIL:** any equality exceeds tolerance, any inequality has the wrong sign,
  or any required separation is absent.
- Execution stops after the first completed gate ledger. A source-code defect
  that prevents the frozen computation from running may be corrected without
  changing the construction, inputs, equations, tolerances, or decision
  rules; the correction must be reported with the result.
