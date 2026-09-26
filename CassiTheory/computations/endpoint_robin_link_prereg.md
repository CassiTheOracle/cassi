# Charged Endpoint–Robin Matching Preregistration

## Status: Preregistered—September 2026

## 1. Question

Does the registered charge-$-g_Q$ endpoint section provide the gauge-covariant Hermitian Robin coupling required by the two-port boundary problem, and what constraints follow when the same endpoint must carry the stationary scale current?

This receipt tests five conditional algebraic claims:

1. the frozen coherent link is a Hermitian, gauge-covariant Robin vertex in the Yang/Yin species-port basis;
2. its Cayley scattering matrix has an exact closed form and preserves the canonical flux norm;
3. a quarter-turn dressed endpoint phase and one selected coupling ratio realize the declared golden matrix at one $k_\star$;
4. simultaneous stationary-current capacity gives a lower bound on $k_\star$ and fixes the current fraction of the endpoint capacity;
5. a fixed frozen link remains wave-number dependent away from its matching point.

The Yang/Yin species-port identification, endpoint normalization, dressed phase, $k_\star$, and physical golden selection remain Hypothesized. No observable particle channel, lifetime, or broadband splitter is inferred.

## 2. Source Boundary

The frozen authorities are:

- `foundations/endpoint-link-and-localization-boundary.md` §§2–3—the relative charge convention, coherent link action, endpoint phase, current capacity, and stable phase branch;
- `foundations/geometric-manifold-completion.md` §§2.4–2.5—the two-rail species frame, flux-normalized traces, and endpoint-intertwiner covariance;
- `foundations/particle-stationary-action-closure.md` §3.2—the second-order charged-field temporal action and positive scale-gradient term;
- `foundations/interscale-stress-attenuation-boundary.md` §§4.2–4.4—the canonical flux norm, Hermitian Robin family, and declared golden target;
- `computations/endpoint_link_localization_check.py`—the executable endpoint receipt to be extended only with the frozen checks below.

The calculation uses the same boundary-trace normalization for the coherent link and the Robin problem. A different physical normalization rescales $\kappa_v|\Upsilon_v|$ and must be matched separately.

## 3. Frozen Coherent-Link Reduction

At one two-rail vertex, conditionally identify the boundary vector with the Yang/Yin species traces,

$$
\Phi_v
:=
\begin{pmatrix}\psi_Y(v)\\\psi_I(v)\end{pmatrix},
\qquad
\Upsilon_v=u_v e^{i\alpha_v},
\qquad
\nu_v:=2\kappa_vu_v>0.
$$

Define

$$
M(\alpha_v)
:=
\begin{pmatrix}
0&e^{-i\alpha_v}\\
e^{i\alpha_v}&0
\end{pmatrix}
=
\cos\alpha_v\,\sigma_x
+\sin\alpha_v\,\sigma_y.
$$

The coherent interaction in the endpoint action is

$$
\kappa_v
\left(
\Upsilon_v^*\psi_Y^*\psi_I
+\Upsilon_v\psi_I^*\psi_Y
\right)
=
\frac12\Phi_v^\dagger
\Lambda_{\mathrm{link},v}\Phi_v,
$$

with

$$
\boxed{
\Lambda_{\mathrm{link},v}
=
\nu_v M(\alpha_v)
=
2\kappa_vu_v
\begin{pmatrix}
0&e^{-i\alpha_v}\\
e^{i\alpha_v}&0
\end{pmatrix}.}
$$

The frozen identities are

$$
M^\dagger=M,
\qquad
M^2=I,
\qquad
\operatorname{tr}M=0,
\qquad
\det M=-1.
$$

Thus $\Lambda_{\mathrm{link},v}$ is Hermitian and has eigenvalues $\pm\nu_v$.

For a local relative-frame change

$$
G(\beta)
:=
\begin{pmatrix}
e^{ig_Q\beta/2}&0\\0&e^{-ig_Q\beta/2}
\end{pmatrix},
\qquad
\Upsilon_v\mapsto e^{-ig_Q\beta}\Upsilon_v,
$$

require

$$
\boxed{
\Lambda_{\mathrm{link},v}
\mapsto
G(\beta)\Lambda_{\mathrm{link},v}G(\beta)^\dagger.}
$$

This makes $K_{\mathfrak s}\Phi_v'=\Lambda_{\mathrm{link},v}\Phi_v$ covariant when the boundary value and outward derivative transform in the same local frame.

## 4. Frozen Scattering and Golden Matching

Set

$$
x:=K_{\mathfrak s}k,
\qquad
a(k):=\frac{\nu_v}{x}.
$$

Using $M^2=I$, the Robin Cayley matrix must reduce to

$$
\boxed{
S_{\mathrm{link}}(k)
=
\frac{x^2-\nu_v^2}{x^2+\nu_v^2}I
-i\frac{2x\nu_v}{x^2+\nu_v^2}M(\alpha_v).}
$$

For real positive $x$ and $\nu_v$, require

$$
S_{\mathrm{link}}(k)^\dagger S_{\mathrm{link}}(k)=I.
$$

Let the oriented golden target be

$$
S_{\varphi,\epsilon}
:=t_\varphi I+\epsilon r_\varphi J,
\qquad
J:=\begin{pmatrix}0&1\\-1&0\end{pmatrix},
\qquad
\epsilon\in\{+1,-1\},
$$

where

$$
t_\varphi=\varphi^{-1/2},
\qquad
r_\varphi=\varphi^{-1},
\qquad
\tau_\varphi:=\frac{r_\varphi}{1+t_\varphi}.
$$

The selected-point matching conditions are

$$
\boxed{
\alpha_v=-\epsilon\frac{\pi}{2}\pmod{2\pi},
\qquad
\frac{2\kappa_vu_v}{K_{\mathfrak s}k_\star}
=\tau_\varphi.}
$$

They imply

$$
\Lambda_{\mathrm{link},v}
=i\epsilon K_{\mathfrak s}k_\star\tau_\varphi J,
\qquad
S_{\mathrm{link}}(k_\star)=S_{\varphi,\epsilon}.
$$

The phase is a fixed-frame representative. Its physical statement is the corresponding dressed endpoint-intertwiner phase.

Holding the same frozen link at another wave number gives

$$
a(k)=\frac{k_\star}{k}\tau_\varphi,
$$

so the golden split occurs only at the selected matching point.

## 5. Frozen Current-Capacity Compatibility

At uniform $\varphi$ composition,

$$
\sqrt{E_YE_I}=\frac{\rho}{\varphi^{3/2}},
$$

and the coherent link has critical current

$$
\mathcal J_{c,v}
=
\frac{\nu_v\rho}{\hbar\varphi^{3/2}}.
$$

The stationary circuit current is

$$
|\mathcal J_{Q,m}|
=
\frac{K_{\mathfrak s}\rho|\Delta_m|}
{\hbar\varphi^3\mathfrak s_p}.
$$

After selected-point matching,

$$
\boxed{
\frac{|\mathcal J_{Q,m}|}{\mathcal J_{c,v}}
=
\frac{|\Delta_m|}
{\varphi^{3/2}\mathfrak s_p\tau_\varphi k_\star}
=
\frac{k_{\min,m}}{k_\star}.}
$$

The locally stable branch requires $|\mathcal J_{Q,m}|<\mathcal J_{c,v}$, hence

$$
\boxed{
k_\star>k_{\min,m}
:=
\frac{|\Delta_m|}
{\varphi^{3/2}\mathfrak s_p\tau_\varphi}.}
$$

At equality the endpoint phase stiffness vanishes. For the unbiased $m=1$ branch with $\Delta_1=2\pi$ and $\mathfrak s_p=91.461618346$, the frozen numerical value is

$$
\boxed{k_{\min,1}=0.096464036203895.}
$$

This is a conditional lower bound using the Mapped proton endpoint and the declared matching branch. It does not select $k_\star$.

## 6. Frozen Numerical Checks

The tolerance for ER1–ER5 is $5\times10^{-13}$.

### ER1—Hermitian link and gauge covariance

Use

$$
\kappa_v=0.41,
\qquad
u_v=0.73,
\qquad
\nu_v=2\kappa_vu_v,
\qquad
\alpha_v=-0.37,
\qquad
g_Q\beta=0.44.
$$

Require the Hermiticity residual, $\|M^2-I\|_{\max}$, and the covariance residual between the transformed endpoint field and $G\Lambda G^\dagger$ to lie below tolerance. Require the two eigenvalue invariants $\operatorname{tr}\Lambda=0$ and $\det\Lambda=-\nu_v^2$ within tolerance.

### ER2—Closed-form link scattering

Use the ER1 link with

$$
K_{\mathfrak s}=1.4,
\qquad
k=0.9.
$$

Require the Cayley matrix to agree with the closed form in §4, require $\|S^\dagger S-I\|_{\max}$ below tolerance, and require one frozen complex input vector to preserve its flux norm within tolerance.

### ER3—Selected golden match

Use

$$
K_{\mathfrak s}=1.3,
\qquad
k_\star=0.8,
\qquad
\nu_v=K_{\mathfrak s}k_\star\tau_\varphi,
\qquad
\alpha_v=-\frac{\pi}{2},
\qquad
\epsilon=+1.
$$

Require $\Lambda_{\mathrm{link},v}=iK_{\mathfrak s}k_\star\tau_\varphi J$ and $S_{\mathrm{link}}(k_\star)=S_{\varphi,+}$ within tolerance.

### ER4—Current-capacity compatibility

Use

$$
\Delta_1=2\pi,
\qquad
\mathfrak s_p=91.461618346,
\qquad
k_\star=0.8.
$$

Require

$$
\frac{\kappa_vu_v}{K_{\mathfrak s}}
=\frac{k_\star\tau_\varphi}{2},
\qquad
k_{\min,1}=0.096464036203895,
\qquad
\frac{|\mathcal J_{Q,1}|}{\mathcal J_{c,v}}
=\frac{k_{\min,1}}{k_\star},
$$

within tolerance. Require the matched link to lie strictly on the stable side of the capacity bound. At $k_\star=k_{\min,1}$, require the computed phase-stiffness factor $\sqrt{1-(k_{\min,1}/k_\star)^2}$ to vanish within tolerance.

### ER5—Frozen-link bandwidth boundary

Hold the ER3 link fixed and set $k=1.7k_\star$. Require the Cayley matrix to agree with the fixed-link analytic form within tolerance and to differ from $S_{\varphi,+}$ by more than $10^{-3}$.

## 7. Decision and Stopping Rule

The endpoint–Robin receipt passes only if ER1–ER5 all pass on the first execution after implementation. Any failed identity returns the derivation to algebra review. No coefficient, phase, tolerance, target matrix, wave-number ratio, or numerical bound may change after output is observed. Stop after that execution.

A passing receipt establishes the conditional frozen-link Robin reduction, covariance, unitary scattering law, selected-point golden realization, stable-current lower bound, and fixed-link bandwidth boundary. It leaves the physical port assignment, endpoint normalization and potential, dressed-phase selection, $k_\star$, golden origin, and active endpoint fluctuation response open.

## References

- `foundations/endpoint-link-and-localization-boundary.md`—charged coherent endpoint action, current capacity, and stable phase branch
- `foundations/geometric-manifold-completion.md`—two-rail species frame and endpoint covariance
- `foundations/particle-stationary-action-closure.md`—time-completed charged-field action
- `foundations/interscale-stress-attenuation-boundary.md`—canonical Robin scattering and declared golden target
- `computations/endpoint_link_localization_check.py`—frozen executable endpoint receipt
