# Interscale Port-Matching Algebra Preregistration

## Status: Preregistered—September 2026

## 1. Question

Can the time-completed quadratic scale action determine the golden two-port matrix, or does it determine only the conserved boundary-flux form and a family of admissible endpoint couplings?

This receipt tests four algebraic claims:

1. a Hermitian endpoint coupling gives a unitary two-lead scattering matrix in the canonical flux norm;
2. the golden matrix is obtained at one declared design wave number only after its endpoint coupling is selected by inverse matching;
3. a fixed local coupling makes that split wave-number dependent;
4. the existing two-rail endpoint gluing is a phase-only perfect-transfer limit rather than a partial splitter.

No physical port identification, golden-angle selection, return routing, or non-reentry law is inferred from these checks.

## 2. Source Boundary

The frozen authorities are:

- `foundations/particle-stationary-action-closure.md` §3.2—the second-order temporal action and positive scale-gradient term;
- `foundations/interscale-current-soliton.md` §§3.1–3.3—the continuum and discrete scale-current normalizations;
- `foundations/geometric-manifold-completion.md` §§2.4–2.5—the two-rail scale circle and phase-only flux-preserving endpoint gluing;
- `foundations/interscale-stress-attenuation-boundary.md` §4—the declared golden two-port branch;
- `computations/interscale_stress_attenuation_check.py`—the executable conservation receipt to be extended only with the frozen checks below.

## 3. Quadratic Boundary Form

For a frozen background, suppressing spatial labels and collecting all local quadratic terms into a Hermitian matrix $\mathsf H$, use

$$
S^{(2)}
=
\frac12\int dt\,d\mathfrak s
\left[
C_\Psi\dot\eta^\dagger\dot\eta
-K_{\mathfrak s}(D_{\mathfrak s}\eta)^\dagger D_{\mathfrak s}\eta
-\eta^\dagger\mathsf H\eta
\right].
$$

The scale operator has boundary Green form

$$
\mathfrak b_{\partial I}(\eta_1,\eta_2)
=
K_{\mathfrak s}
\left[
\eta_1^\dagger D_{\mathfrak s}\eta_2
-(D_{\mathfrak s}\eta_1)^\dagger\eta_2
\right]_{\partial I}.
$$

For one solution, the associated scale flux is

$$
J_{\mathfrak s}[\eta]
=
\frac{K_{\mathfrak s}}{2i\hbar}
\left[
\eta^\dagger D_{\mathfrak s}\eta
-(D_{\mathfrak s}\eta)^\dagger\eta
\right].
$$

The potential Hessian affects bulk propagation while the boundary form depends on the scale-gradient coefficient and boundary data.

## 4. Frozen Two-Lead Matching Problem

At a two-lead vertex, let $\Phi$ collect the boundary values and let $\Phi'$ collect outward covariant derivatives. Restrict the numerical receipt to equal lead coefficient $K_{\mathfrak s}$ and equal real wave number $k>0$. A Hermitian Robin coupling obeys

$$
K_{\mathfrak s}\Phi'=\Lambda\Phi,
\qquad
\Lambda^\dagger=\Lambda.
$$

With flux-normalized incoming and outgoing amplitudes,

$$
\Phi=a^{\rm in}+a^{\rm out},
\qquad
\Phi'=ik(a^{\rm out}-a^{\rm in}),
$$

so

$$
S_\Lambda(k)
=
(ikK_{\mathfrak s}I-\Lambda)^{-1}
(ikK_{\mathfrak s}I+\Lambda),
\qquad
a^{\rm out}=S_\Lambda(k)a^{\rm in}.
$$

Hermiticity of $\Lambda$ must imply $S_\Lambda^\dagger S_\Lambda=I$. This is a conservation result; it leaves the endpoint coupling free.

## 5. Declared Golden Target

The target matrix already registered in the stress-boundary paper is

$$
S_\varphi
=
\begin{pmatrix}
 t_\varphi&r_\varphi\\
-r_\varphi&t_\varphi
\end{pmatrix},
\qquad
 t_\varphi=\varphi^{-1/2},
\qquad
 r_\varphi=\varphi^{-1}.
$$

Define

$$
J=
\begin{pmatrix}0&1\\-1&0\end{pmatrix},
\qquad
\tau_\varphi
=
\frac{r_\varphi}{1+t_\varphi}.
$$

At one declared design wave number $k_\star$, inverse matching requires

$$
\Lambda_\varphi(k_\star)
=
iK_{\mathfrak s}k_\star\tau_\varphi J.
$$

This matrix is Hermitian. Its off-diagonal phase requires a gauge-covariant endpoint intertwiner or resolved endpoint field. The bulk action and self-adjointness condition do not select this coupling, $k_\star$, or the golden target.

Holding $\Lambda_\varphi(k_\star)$ fixed at another wave number gives

$$
\alpha(k)=\frac{k_\star}{k}\tau_\varphi,
$$

and

$$
S(k)
=
\frac{1}{1+\alpha^2}
\begin{pmatrix}
1-\alpha^2&2\alpha\\
-2\alpha&1-\alpha^2
\end{pmatrix}.
$$

The target split is therefore a single-wave-number matching condition for this local coupling.

## 6. Frozen Numerical Checks

The tolerance for ST11–ST14 is $5\times10^{-13}$.

### ST11—Hermitian Robin unitarity

Use

$$
K_{\mathfrak s}=1.4,
\qquad
k=0.9,
\qquad
\Lambda=
\begin{pmatrix}
0.37&0.12+0.21i\\
0.12-0.21i&-0.23
\end{pmatrix}.
$$

Require both $\|S_\Lambda^\dagger S_\Lambda-I\|_{\max}$ and the input/output flux-norm residual for the frozen input $(0.63-0.14i,-0.22+0.51i)$ to lie below tolerance.

### ST12—Golden target inverse matching

Use

$$
K_{\mathfrak s}=1.3,
\qquad
k_\star=0.8.
$$

Require $\Lambda_\varphi^\dagger=\Lambda_\varphi$ and
$\|S_{\Lambda_\varphi}(k_\star)-S_\varphi\|_{\max}$ below tolerance.

### ST13—Fixed-coupling wave-number dependence

Hold $\Lambda_\varphi(k_\star)$ fixed and use $k=1.7k_\star$. Require the Cayley matrix to agree with the analytic $S(k)$ above within tolerance and to differ from $S_\varphi$ by more than $10^{-3}$.

### ST14—Existing endpoint perfect-transfer limit

Use endpoint phases

$$
\delta_-=0.37,
\qquad
\delta_+=-0.82,
$$

and the off-diagonal phase matrix

$$
S_{\rm GM}
=
\begin{pmatrix}
0&e^{i\delta_-}\\
e^{i\delta_+}&0
\end{pmatrix}.
$$

Require $S_{\rm GM}$ to be unitary and either singly occupied input to produce one unit of output power in exactly one channel.

## 7. Decision and Stopping Rule

The matching receipt passes only if ST11–ST14 all pass on the first execution after implementation. Any failed identity returns the derivation to algebra review. No coefficient, phase, tolerance, target matrix, or alternate wave-number ratio may change after output is observed. Stop after that execution.

A passing receipt establishes conservation, inverse matching, wave-number dependence, and the perfect-transfer limit. It leaves the microscopic endpoint interaction, the golden selection, the physical forward/return identification, and non-reentry open.

## References

- `foundations/particle-stationary-action-closure.md`—time-completed charged-field action
- `foundations/interscale-current-soliton.md`—scale-current normalization
- `foundations/geometric-manifold-completion.md`—two-rail circuit and endpoint gluing
- `foundations/interscale-stress-attenuation-boundary.md`—conditional golden splitter and routed-flux boundary
- `computations/interscale_stress_attenuation_check.py`—frozen executable receipt
