# Charged-Endpoint Spatial-Flux Preregistration

## Status: Preregistered—September 2026

## 1. Question

Can the spatial stiffness already present in the charged-endpoint action support a stationary local Yang/Yin conversion pattern, and what global constraint and gradient cost does that support impose?

This receipt tests six conditional claims:

1. the endpoint action fixes the relation among the Yang source, the rail-difference rate, and the relative-charge source;
2. the endpoint number obeys a gauge-covariant local continuity equation whose stationary source is the divergence of endpoint spatial current;
3. a prescribed zero-mean stationary source has an exact periodic constant-amplitude phase-current reconstruction;
4. the source and current are invariant under time-independent local relative-frame transformations;
5. periodic or no-flux endpoint data require zero integrated source, so a nonzero source mean cannot be supported by spatial endpoint flux alone;
6. every nonzero reconstructible source carries a positive endpoint gradient-energy cost with a closed Fourier representation.

The receipt isolates the endpoint equation with an imposed rail bilinear. It does not solve the coupled rail equations, select the endpoint potential or stiffness, establish a localized particle, or assign a physical conversion rate.

## 2. Source Boundary

The frozen authorities are:

- `foundations/endpoint-link-and-localization-boundary.md` §§2–3—the charge-$-g_Q$ endpoint field, action, coherent vertex source, and first-order endpoint equation;
- `foundations/interscale-current-soliton.md` §§4.4–4.5—the rail currents, Yang source $\Gamma$, and stationary circuit orientation;
- `computations/endpoint_action_response_prereg.md`—the rail-difference convention denoted by $\mathcal I_{\mathrm{link}}$ in the first-order response receipt.

All identities are local to one scale vertex $v$. Write

$$
P_v:=\left.\psi_Y^*\psi_I\right|_{\mathfrak s=v},
\qquad
n_v:=|\Upsilon_v|^2.
$$

The endpoint equation is

$$
i\hbar\partial_t\Upsilon_v
=-\frac{K_v}{2}D_i^{(-g_Q)}D_i^{(-g_Q)}\Upsilon_v
+U_v'(n_v)\Upsilon_v
-\kappa_vP_v.
$$

The Yang source coefficient at the vertex is frozen as

$$
\boxed{
\Gamma_v
:=-\frac{2\kappa_v}{\hbar}
\operatorname{Im}(\Upsilon_v^*P_v)
=\left.\partial_tE_Y\right|_v
=-\left.\partial_tE_I\right|_v.}
$$

The first-order response receipts use the rail-difference-rate convention

$$
\boxed{
\mathcal I_{\mathrm{link},v}
:=-2\Gamma_v
=\frac{4\kappa_v}{\hbar}
\operatorname{Im}(\Upsilon_v^*P_v)
=-\left.\partial_t(E_Y-E_I)\right|_v.}
$$

Neither quantity includes the relative charge. The gauge-weighted rail source is $g_Q\Gamma_v$, while the endpoint field has charge $-g_Q$.

## 3. Analytic Identities

Define the endpoint number current

$$
\boxed{
J_{\Upsilon,v}^i
:=\frac{K_v}{\hbar}
\operatorname{Im}\!\left[
\Upsilon_v^*D_i^{(-g_Q)}\Upsilon_v
\right].}
$$

The endpoint equation and its conjugate give

$$
\boxed{
\partial_tn_v+\partial_iJ_{\Upsilon,v}^i
=\Gamma_v
=-\frac12\mathcal I_{\mathrm{link},v}.}
$$

The rail relative-charge source and endpoint charge source cancel:

$$
\left.\partial_t\frac{g_Q}{2}(E_Y-E_I)\right|_v
=g_Q\Gamma_v,
\qquad
\partial_t(-g_Qn_v)+\partial_i(-g_QJ_{\Upsilon,v}^i)
=-g_Q\Gamma_v.
$$

For $\Upsilon_v=u_ve^{i\alpha_v}$,

$$
J_{\Upsilon,v}^i
=\frac{K_vu_v^2}{\hbar}
\left(\partial_i\alpha_v+g_QB_i(v)\right).
$$

A stationary-density branch therefore obeys

$$
\boxed{\partial_iJ_{\Upsilon,v}^i=\Gamma_v.}
$$

On a spatial region $\Omega$,

$$
\boxed{
\int_\Omega\Gamma_v\,d^3x
=\oint_{\partial\Omega}
\mathbf J_{\Upsilon,v}\cdot d\mathbf S.}
$$

Periodic data, no-flux boundary data, or a localized finite-energy current that decays sufficiently fast at infinity require $\int\Gamma_vd^3x=0$. Spatial endpoint flux can therefore support a stationary local source-and-sink pattern in a closed domain, while a nonzero integrated source requires boundary flux or additional endpoint transport.

## 4. Periodic Reconstruction and Cost

Freeze a periodic cube $\Omega=[0,L)^3$, constant $u_v>0$, and the trivial spatial gauge $B_i=0$. The stationary equation becomes

$$
\nabla^2\alpha_v
=\frac{\hbar}{K_vu_v^2}\Gamma_v.
$$

For the Fourier convention

$$
f(\mathbf x)=\sum_{\mathbf k}f_{\mathbf k}e^{i\mathbf k\cdot\mathbf x},
$$

a solution exists only when $\Gamma_{v,\mathbf0}=0$. Fixing the constant phase by $\alpha_{v,\mathbf0}=0$ gives

$$
\boxed{
\alpha_{v,\mathbf k}
=-\frac{\hbar}{K_vu_v^2}
\frac{\Gamma_{v,\mathbf k}}{|\mathbf k|^2},
\qquad
\mathbf k\ne\mathbf0.}
$$

The reconstructed current is

$$
\boxed{
\mathbf J_{\Upsilon,v,\mathbf k}
=-i\frac{\mathbf k}{|\mathbf k|^2}\Gamma_{v,\mathbf k},
\qquad
\mathbf k\ne\mathbf0.}
$$

Its endpoint gradient energy is

$$
\boxed{
H_{\nabla\Upsilon,v}
=\frac{K_vu_v^2}{2}\int_\Omega|\nabla\alpha_v|^2d^3x
=\frac{\hbar^2V}{2K_vu_v^2}
\sum_{\mathbf k\ne\mathbf0}
\frac{|\Gamma_{v,\mathbf k}|^2}{|\mathbf k|^2}
=\frac{\hbar^2V}{8K_vu_v^2}
\sum_{\mathbf k\ne\mathbf0}
\frac{|\mathcal I_{\mathrm{link},v,\mathbf k}|^2}{|\mathbf k|^2}.}
$$

This coefficient is positive for $K_v>0$, $u_v>0$, and any nonzero zero-mean source. It is an endpoint gradient-energy cost within the declared action. It does not supply the complete particle energy or establish stability.

For a real constant rotating-frame curvature $\mu_v:=W_v'(u_v^2)$, a reconstructed phase defines the imposed rail bilinear

$$
\boxed{
P_v
:=\frac{1}{\kappa_v}
\left[-\frac{K_v}{2}\nabla^2\Upsilon_v
+\mu_v\Upsilon_v\right].}
$$

This construction solves the stationary rotating-frame endpoint equation exactly. It establishes endpoint-equation compatibility with local source-and-sink conversion. The coupled rail equations and their boundary traces remain untested.

## 5. Frozen Numerical Point

Use deterministic normalized units

$$
\hbar=1.7,
\quad K_v=2.3,
\quad u_v=0.9,
\quad \kappa_v=0.6,
\quad g_Q=0.4,
\quad \mu_v=1.1.
$$

Use $L=2\pi$, $N=24$ points per axis, and the zero-mean source

$$
\Gamma_v(x,y,z)
=0.21\sin x
+0.13\cos(2y-z)
-0.08\sin(x+y+2z).
$$

The analytic phase is

$$
\alpha_v
=-\frac{\hbar}{K_vu_v^2}
\left[
0.21\sin x
+\frac{0.13}{5}\cos(2y-z)
-\frac{0.08}{6}\sin(x+y+2z)
\right].
$$

For the covariance check use

$$
\chi(x,y,z)
=0.17\cos(x-2z)+0.09\sin(y+z),
$$

with

$$
\alpha_v\mapsto\alpha_v-g_Q\chi,
\qquad
B_i\mapsto B_i+\partial_i\chi,
\qquad
\Upsilon_v\mapsto e^{-ig_Q\chi}\Upsilon_v,
\qquad
P_v\mapsto e^{-ig_Q\chi}P_v.
$$

For the incompatible-source check use $\Gamma_v^{\mathrm{bad}}:=\Gamma_v+0.07$.

## 6. Frozen Gates

All absolute and relative tolerances are $10^{-11}$ unless a gate states otherwise.

### SF1—Source normalization and relative-charge cancellation

Require pointwise

$$
\mathcal I_{\mathrm{link},v}=-2\Gamma_v
$$

and require the sum of the gauge-weighted rail and endpoint source terms to vanish.

### SF2—Stationary endpoint equation and local continuity

Construct $\Upsilon_v=u_ve^{i\alpha_v}$ and $P_v$ from §4. Require the stationary endpoint-equation residual, the error between the link-derived $\Gamma_v$ and the frozen source, and the error in $\nabla\cdot\mathbf J_{\Upsilon,v}=\Gamma_v$ to be below tolerance.

### SF3—Time-independent local gauge covariance

Apply the frozen $\chi$. Require invariance of $\partial_i\alpha_v+g_QB_i$, $\Gamma_v$, and $\mathbf J_{\Upsilon,v}$; require $D_i\Upsilon_v\mapsto e^{-ig_Q\chi}D_i\Upsilon_v$ and the transformed stationary endpoint residual to remain below tolerance.

### SF4—Periodic inverse-divergence reconstruction

Solve the frozen zero-mean source by discrete Fourier transform with the zero mode fixed to zero. Require agreement with the analytic phase and require the reconstructed current divergence to agree with $\Gamma_v$ below tolerance.

### SF5—Closed-domain zero-mode obstruction

Apply the same inverse-divergence construction to $\Gamma_v^{\mathrm{bad}}$. Require the reconstructed divergence to have zero spatial mean and its residual against $\Gamma_v^{\mathrm{bad}}$ to equal the uniform value $-0.07$ below tolerance. No alternate boundary condition may be introduced after execution.

### SF6—Positive gradient-cost identity

Evaluate $H_{\nabla\Upsilon,v}$ directly from the reconstructed phase gradient, from the $\Gamma_v$ Fourier sum, and from the $\mathcal I_{\mathrm{link},v}$ Fourier sum. Require all three values to agree within relative tolerance and require the common value to be strictly positive.

The overall verdict is `PASS` only if SF1–SF6 all pass. Any failed assertion fixes the first-execution verdict as `FAIL`; the script and raw output remain part of the record. No coefficient, grid, source, tolerance, or gate may be changed after the first execution.