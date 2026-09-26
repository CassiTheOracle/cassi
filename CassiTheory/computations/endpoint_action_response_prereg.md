# Source-Action Charged-Endpoint Response Preregistration

## Status: Preregistered—September 2026

## 1. Question

What quadratic rail response follows from the registered charged-endpoint action when the endpoint is allowed to fluctuate, and which response properties survive the source-action sign convention?

This receipt tests six conditional claims:

1. a closed, homogeneous, conservative time-harmonic endpoint extremum carries zero coherent Yang/Yin conversion current;
2. the endpoint action has the declared rail–endpoint mixed Hessian and the static endpoint action block is the negative endpoint energy Hessian;
3. the endpoint-mediated correction vanishes at quadratic order around the symmetric zero background, begins at quartic rail order, and contributes positively when the endpoint mass is positive;
4. a positive endpoint energy Hessian has a closed analytic pole pair and a declared pole-free response domain;
5. source-action elimination gives a Nambu-space Schur complement with exact constant-frame covariance;
6. the closed response is Hermitian away from its poles, while a declared damped continuation is non-Hermitian and obeys the retarded/advanced adjoint relation.

The endpoint potential, background, damping law, trace normalization, and physical Yang/Yin port identification remain Hypothesized. The numerical point checks the algebra in normalized units and does not calibrate a particle channel.

`computations/endpoint_dynamical_response_report.md` records a `FAIL` for the frozen DR receipt because DR5 treats $+\frac12\Xi^\dagger\mathcal D_v^R\Xi$ as the endpoint source-action block, while the registered action requires $\mathcal K_v^R=-\mathcal D_v^R$. This preregistration freezes the action kernel and its consequences before the source-action checker is implemented or executed.

## 2. Source Boundary

The frozen authorities are:

- `foundations/endpoint-link-and-localization-boundary.md` §§2–3—the charge-$-g_Q$ endpoint action, coherent current, frozen-background rail Hessian, and current-capacity branch;
- `foundations/geometric-manifold-completion.md` §§2.4–2.5—the two-rail species frame and endpoint-intertwiner covariance;
- `foundations/particle-stationary-action-closure.md` §3.2—the second-order charged-field temporal convention;
- `foundations/interscale-stress-attenuation-boundary.md` §§4.2–4.4—the canonical Robin normalization and scattering map;
- `computations/endpoint_robin_link_prereg.md`—the frozen-link normalization and selected-point response boundary;
- `computations/endpoint_dynamical_response_prereg.md`, `computations/endpoint_dynamical_response_check.py`, and `computations/endpoint_dynamical_response_report.md`—the frozen failed response receipt.

The calculation uses the same local boundary-trace normalization for the direct link and the endpoint-mediated correction. Every kernel below is a boundary-density kernel at fixed spatial Fourier momentum. A physical trace normalization may rescale all endpoint coefficients together and remains open.

## 3. Background Equation and Current Boundary

Write the endpoint potential as $U_v(n)$ with $n=|\Upsilon|^2$. At one vertex, the endpoint equation from the registered action is

$$
i\hbar\partial_t\Upsilon
=
-\frac{K_v}{2}D_i^{(-)}D_i^{(-)}\Upsilon
+U_v'(|\Upsilon|^2)\Upsilon
-\kappa_v\psi_Y^*\psi_I.
$$

For a homogeneous time-harmonic background,

$$
\Upsilon(t)=\Upsilon_{v,0}e^{-i\Omega_{\mathrm{bg}}t},
\qquad
\Upsilon_{v,0}=u_ve^{i\alpha_v},
\qquad
B_{v,0}:=Y_0^*I_0,
$$

define the rotating-frame potential

$$
W_v(n):=U_v(n)-\hbar\Omega_{\mathrm{bg}}n.
$$

The background equation is

$$
\boxed{W_v'(u_v^2)\Upsilon_{v,0}=\kappa_vB_{v,0}.}
$$

Because $W_v'$ is real for a conservative real potential,

$$
\operatorname{Im}(\Upsilon_{v,0}^*B_{v,0})=0.
$$

With $Y_0=|Y_0|e^{i\theta_Y}$ and $I_0=|I_0|e^{i\theta_I}$, the registered link current is

$$
\mathcal I_{\mathrm{link}}
:=
\frac{4\kappa_vu_v}{\hbar}|Y_0||I_0|
\sin(\theta_I-\theta_Y-\alpha_v),
$$

so every closed homogeneous time-harmonic extremum satisfies

$$
\boxed{\mathcal I_{\mathrm{link}}=0.}
$$

A nonzero stationary conversion current therefore requires endpoint spatial flux, a drive or open channel, a non-harmonic background, or a larger coupled background problem.

## 4. Quadratic Source Action

Use the co-rotating fractional endpoint fluctuation

$$
\psi_Y=Y_0+\eta_Y,
\qquad
\psi_I=I_0+\eta_I,
\qquad
\Upsilon=e^{-i\Omega_{\mathrm{bg}}t}\Upsilon_{v,0}(1+\zeta).
$$

Define the rail and endpoint Nambu vectors

$$
\mathbb\Phi
:=
\begin{pmatrix}
\eta_Y\\\eta_I\\\eta_Y^*\\\eta_I^*
\end{pmatrix},
\qquad
\Xi
:=
\begin{pmatrix}\zeta\\\zeta^*\end{pmatrix}.
$$

The direct rail block is

$$
\Lambda_{\mathrm{link},v}
:=2\kappa_vu_v
\begin{pmatrix}
0&e^{-i\alpha_v}\\
e^{i\alpha_v}&0
\end{pmatrix},
\qquad
\mathbb\Lambda_{0,v}
:=
\frac12
\begin{pmatrix}
\Lambda_{\mathrm{link},v}&0\\
0&\Lambda_{\mathrm{link},v}^*
\end{pmatrix}.
$$

With the doubled ordering above,

$$
\frac12\mathbb\Phi^\dagger\mathbb\Lambda_{0,v}\mathbb\Phi
=
\frac12
\begin{pmatrix}\eta_Y^*&\eta_I^*\end{pmatrix}
\Lambda_{\mathrm{link},v}
\begin{pmatrix}\eta_Y\\\eta_I\end{pmatrix},
$$

so the internal factor of $1/2$ reproduces the undoubled direct link once.

The mixed Hessian is

$$
\boxed{
\mathcal C_v
:=
\kappa_vu_v
\begin{pmatrix}
0&e^{-i\alpha_v}Y_0^*&e^{-i\alpha_v}I_0&0\\
e^{i\alpha_v}I_0^*&0&0&e^{i\alpha_v}Y_0
\end{pmatrix}.}
$$

The fractional fluctuation $\delta\Upsilon=\Upsilon_{v,0}\zeta$ gives

$$
\mathcal L_{\mathrm{mix}}^{(2)}
=
\kappa_vu_v\left[
e^{-i\alpha_v}\zeta^*(Y_0^*\eta_I+I_0\eta_Y^*)
+e^{i\alpha_v}\zeta(I_0^*\eta_Y+Y_0\eta_I^*)
\right].
$$

Let

$$
\mathcal Z_v:=\hbar u_v^2,
$$

and define the endpoint energy curvature

$$
A_v(\mathbf q)
:=
u_v^2\left[
W_v'(u_v^2)+u_v^2U_v''(u_v^2)
+\frac{K_v}{2}|\mathbf q|^2
\right],
\qquad
B_v:=u_v^4U_v''(u_v^2),
$$

The endpoint energy Hessian is

$$
\mathcal H_v(\mathbf q)
:=
\begin{pmatrix}
A_v(\mathbf q)&B_v\\
B_v^*&A_v(\mathbf q)
\end{pmatrix}.
$$


The registered source action has canonical temporal term minus endpoint energy. With the Fourier convention frozen in this receipt, its retarded endpoint action kernel is

$$
\boxed{
\mathcal K_v^R(\omega,\mathbf q)
:=
\mathcal Z_v(\omega+i\gamma_v)\sigma_3
-\mathcal H_v(\mathbf q).}
$$

For comparison with the frozen DR notation, define

$$
\mathcal D_v^R
:=
\mathcal H_v-\mathcal Z_v(\omega+i\gamma_v)\sigma_3,
\qquad
\boxed{\mathcal K_v^R=-\mathcal D_v^R.}
$$

The advanced action kernel is

$$
\mathcal K_v^A(\omega,\mathbf q)
:=
\mathcal Z_v(\omega-i\gamma_v)\sigma_3
-\mathcal H_v(\mathbf q)
=\mathcal K_v^R(\omega,\mathbf q)^\dagger
$$

for real $\omega$. The complete quadratic source action is

$$
\boxed{
Q_v^{(2),R}
=
\frac12\mathbb\Phi^\dagger\mathbb\Lambda_{0,v}\mathbb\Phi
+\frac12\Xi^\dagger\mathcal K_v^R\Xi
+\frac12\left(
\Xi^\dagger\mathcal C_v\mathbb\Phi
+\mathbb\Phi^\dagger\mathcal C_v^\dagger\Xi
\right).}
$$

At zero frequency, the static endpoint action block is $-\mathcal H_v$. This sign is fixed by the registered source action.

## 5. Source-Action Elimination and Poles

The endpoint equation from the quadratic source action is

$$
\mathcal K_v^R\Xi+\mathcal C_v\mathbb\Phi=0.
$$

Thus

$$
\boxed{
\Xi=-\left(\mathcal K_v^R\right)^{-1}\mathcal C_v\mathbb\Phi
=\left(\mathcal D_v^R\right)^{-1}\mathcal C_v\mathbb\Phi.}
$$

Substitution gives the equivalent source-action forms

$$
\boxed{
\mathbb\Lambda_{\mathrm{eff},v}^R
=
\mathbb\Lambda_{0,v}
-\mathcal C_v^\dagger
\left(\mathcal K_v^R\right)^{-1}
\mathcal C_v
=
\mathbb\Lambda_{0,v}
+\mathcal C_v^\dagger
\left(\mathcal D_v^R\right)^{-1}
\mathcal C_v.}
$$

Generic nonzero $Y_0$ and $I_0$ produce particle–hole blocks in $\mathbb\Lambda_{\mathrm{eff}}$. The active response is therefore a $4\times4$ Nambu kernel. An ordinary $2\times2$ complex-linear Robin matrix exists only when the anomalous blocks cancel.

At $\gamma_v=0$, positive endpoint energy curvature requires

$$
A_v(\mathbf q)>|B_v|.
$$

The action kernel has the pole pair

$$
\boxed{
\omega=\pm\omega_{\mathrm{end}}(\mathbf q),
\qquad
\omega_{\mathrm{end}}(\mathbf q)
:=
\frac{\sqrt{A_v(\mathbf q)^2-|B_v|^2}}{\mathcal Z_v}.}
$$

For $\gamma_v>0$, the declared continuation moves the poles to

$$
\omega=\pm\omega_{\mathrm{end}}(\mathbf q)-i\gamma_v.
$$

The tested closed response domain is

$$
|\omega|\leq\frac12\omega_{\mathrm{end}}(0),
$$

which is separated from both poles.

## 6. Symmetric Zero-Background Boundary

At $Y_0=I_0=\Upsilon_{v,0}=0$, the direct frozen-link block and the mixed quadratic block vanish. Use the unnormalized endpoint fluctuation $\xi=\delta\Upsilon$ and assume the positive rotating-frame mass

$$
m_{v,0}:=W_v'(0)>0.
$$

The static action kernel and cubic rail source are

$$
\boxed{\mathcal K_{v,0}(0)=-m_{v,0}I_2,}
\qquad
j_{v,0}
:=
\kappa_v
\begin{pmatrix}
\eta_Y^*\eta_I\\
\eta_I^*\eta_Y
\end{pmatrix}.
$$

Source-action elimination contributes

$$
\boxed{
\Delta Q_{v,0}^{(4)}
=-\frac12j_{v,0}^\dagger
\mathcal K_{v,0}(0)^{-1}j_{v,0}>0,}
$$

which is fourth order in the rail fluctuations. The frequency-dependent quadratic rail correction is exactly zero at this background.

## 7. Constant-Frame Covariance

For the constant relative-frame angle $\chi:=g_Q\beta$, define

$$
G(\chi)
:=
\operatorname{diag}(e^{i\chi/2},e^{-i\chi/2}),
\qquad
\mathbb G(\chi)
:=
\operatorname{diag}(G,G^*).
$$

Both $\Upsilon$ and $\Upsilon_{v,0}$ carry charge $-g_Q$, so the fractional endpoint fluctuation $\zeta$ and its Nambu vector $\Xi$ are invariant. The constant-frame covariance laws are

$$
\mathcal C_v\mapsto
\mathcal C_v\mathbb G^\dagger,
\qquad
\mathcal K_v^{R/A}\mapsto\mathcal K_v^{R/A},
$$

and

$$
\boxed{
\mathbb\Lambda_{\mathrm{eff},v}^{R/A}
\mapsto
\mathbb G\mathbb\Lambda_{\mathrm{eff},v}^{R/A}\mathbb G^\dagger.}
$$

The registered endpoint action contains $\partial_t\Upsilon$. This receipt covers constant frame changes. Time-dependent frame covariance requires a temporal relative-gauge connection and remains open.

## 8. Frozen Numerical Point

Use normalized units and the homogeneous mode $\mathbf q=0$:

$$
\hbar=u_v=1,
\qquad
\kappa_v=0.45,
\qquad
|Y_0|=0.7,
\qquad
\theta_Y=0.2,
$$

$$
|I_0|=0.5,
\qquad
\theta_I=-0.3,
\qquad
\alpha_v=\theta_I-\theta_Y=-0.5,
$$

$$
W_v'(u_v^2)
=\frac{\kappa_v|Y_0||I_0|}{u_v}=0.1575,
\qquad
U_v''(u_v^2)=0.6.
$$

Use

$$
\omega=0.2,
\qquad
\gamma_v=0.12,
\qquad
\chi=0.37.
$$

For the exact trilinear and static-action expansions, use

$$
\eta_Y=0.23-0.17i,
\qquad
\eta_I=-0.11+0.29i,
\qquad
\zeta=0.19+0.07i,
\qquad
t=0.37.
$$

For the symmetric zero-background quartic scaling check, use $m_{v,0}=1.1$ and the same rail perturbations at $t_1=0.4$ and $t_2=0.8$.

The equality tolerance is

$$
\varepsilon_{\mathrm{AR}}=5\times10^{-13}.
$$

The generic anomalous-block norm and the damped-response non-Hermiticity norm must each exceed $10^{-3}$.

## 9. Frozen Checks

### AR1—Closed homogeneous current boundary

Require the rotating-frame background-equation residual, $\operatorname{Im}(\Upsilon_{v,0}^*B_{v,0})$, and $\mathcal I_{\mathrm{link}}$ to lie below tolerance. Require the endpoint energy Hessian point to satisfy $A_v(0)>|B_v|$.

### AR2—Exact trilinear and static action Hessians

Expand the coherent trilinear link exactly through cubic order in the frozen real parameter $t$. Require the direct-plus-mixed quadratic coefficient to agree with the Nambu representation, and require the full polynomial reconstruction through $t^3$ to agree with the unexpanded link within tolerance. Independently expand the rotating-frame static endpoint action about the stationary background and require its quadratic coefficient to agree with $-\frac12\Xi^\dagger\mathcal H_v\Xi$ within tolerance.

### AR3—Zero-background order and sign

Set $Y_0=I_0=\Upsilon_{v,0}=0$. Require $\mathcal C_v$, the direct frozen-link block, and the endpoint-mediated quadratic Schur correction to vanish within tolerance. Integrate out the static unnormalized endpoint source $j_{v,0}$ with $\mathcal K_{v,0}(0)=-m_{v,0}I_2$ at $t_1$ and $t_2$; require both contributions to be positive and their ratio to equal $(t_2/t_1)^4=16$ within tolerance.

### AR4—Endpoint stability and poles

Require both eigenvalues $A_v(0)\pm|B_v|$ to be positive. Require the determinant of the closed action kernel to vanish at $\omega=\pm\omega_{\mathrm{end}}(0)$ within tolerance. Require the frozen real frequency to satisfy $|\omega|\leq\omega_{\mathrm{end}}(0)/2$. Under the damped continuation, require both shifted pole residuals at $\pm\omega_{\mathrm{end}}(0)-i\gamma_v$ to lie below tolerance.

### AR5—Source-action elimination, covariance, and Nambu boundary

At the closed frozen frequency, solve $\mathcal K_v^R\Xi+\mathcal C_v\mathbb\Phi=0$ directly for one physical rail Nambu vector and substitute it into the full quadratic source action. Require agreement with the Schur-complement form within tolerance. Also require direct agreement between $\mathbb\Lambda_{0,v}-\mathcal C_v^\dagger(\mathcal K_v^R)^{-1}\mathcal C_v$ and $\mathbb\Lambda_{0,v}+\mathcal C_v^\dagger(\mathcal D_v^R)^{-1}\mathcal C_v$. Transform the backgrounds and all kernels by the constant angle $\chi$; require the direct construction and covariance law for $\mathbb\Lambda_{\mathrm{eff}}^R$ to agree within tolerance. Require the upper-right particle–hole block norm to exceed $10^{-3}$.

### AR6—Closed and open response classes

Require the closed pole-free response to be Hermitian within tolerance. For $\gamma_v=0.12$, require the retarded response to differ from its adjoint by more than $10^{-3}$. Require the advanced response to equal the retarded adjoint within tolerance.

## 10. Decision and Stopping Rule

The source-action endpoint receipt passes only if AR1–AR6 all pass on the first execution after implementation. Any failed identity returns the derivation to algebra review. No background, coefficient, frequency, damping rate, frame angle, tolerance, or threshold may change after output is observed. Stop after that execution.

A passing receipt establishes the conditional closed-current boundary, mixed Hessian, source-action sign, zero-background quadratic boundary and positive quartic term, endpoint pole law, Nambu Schur response, and constant-frame covariance. It does not select $U_v$, $K_v$, $u_v$, the endpoint background, damping mechanism, trace normalization, port assignment, golden matching frequency, particle quantum numbers, or observable lifetime.

## References

- `foundations/endpoint-link-and-localization-boundary.md`—charged endpoint action, coherent current, and frozen rail Hessian
- `foundations/geometric-manifold-completion.md`—two-rail species frame and endpoint covariance
- `foundations/particle-stationary-action-closure.md`—time-completed charged-field convention
- `foundations/interscale-stress-attenuation-boundary.md`—canonical Robin boundary response
- `computations/endpoint_robin_link_prereg.md`—frozen-link response normalization
- `computations/endpoint_dynamical_response_report.md`—failed endpoint energy-kernel receipt
