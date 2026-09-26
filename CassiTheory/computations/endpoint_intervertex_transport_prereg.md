# Gauge-Covariant Inter-Vertex Endpoint Transport Preregistration

## Status: Preregistered—September 2026

## 1. Question

Can one separately declared conservative coupling between the two charged endpoint sections remove the closed-domain zero-mode obstruction while preserving the relative $U(1)_Q$ gauge law, endpoint number conservation, and the registered stationary circuit orientation?

This receipt tests six conditional claims:

1. a Wilson-dressed endpoint bilinear is invariant under independent endpoint values of one time-independent local relative-frame transformation;
2. the coupled endpoint equations produce equal-and-opposite transport and close the two stationary endpoint balances when $I_{-\to+}=\mathcal J_Q$;
3. variation of the Wilson link gives the charge current carried by this added scale-edge interaction and completes the local relative-charge ledger;
4. fixed endpoint amplitudes give the finite capacity $I_c=2t_\Upsilon u_-u_+/\hbar$;
5. every subcritical target has one positive-curvature branch and one negative-curvature companion at fixed amplitudes;
6. the bare endpoint bilinear fails independent endpoint gauge covariance, and $t_\Upsilon=0$ restores the nonzero-source obstruction.

The Wilson coupling below is a new Hypothesized action term. It is absent from the registered endpoint action (EL9), which contains no $D_{\mathfrak s}\Upsilon_v$ term and defines no $\Upsilon_v$-carried interscale current. The receipt tests the added link's algebra at fixed coefficients. It does not derive the coupling, extend $\Upsilon$ into a scale-bulk field, solve the Yang/Yin rail equations, establish particle localization, or assign a physical transport rate.

## 2. Source Boundary

The frozen authorities are:

- `foundations/endpoint-link-and-localization-boundary.md` §§2–3—the charge-$-g_Q$ endpoint fields, coherent Yang/Yin sources, first-order endpoint equations, and closed-domain zero-mode obstruction;
- `foundations/interscale-current-soliton.md` §§2.3 and 4.4–4.5—the relative connection, rail current, and stationary circuit orientation;
- `foundations/geometric-manifold-completion.md` §§2.5 and 5—the compact scale interval, gauge-covariant endpoint intertwiners, and circuit holonomy.

Let $v_-<v_+$ denote the endpoint vertices. The existing endpoint sections transform as

$$
\Upsilon_\pm\longmapsto e^{-ig_Q\chi_\pm}\Upsilon_\pm,
\qquad
\chi_\pm:=\chi(v_\pm),
$$

under

$$
B_{\mathfrak s}\longmapsto
B_{\mathfrak s}+\partial_{\mathfrak s}\chi.
$$

The existing local Yang source coefficients are

$$
\Gamma_v
:=-\frac{2\kappa_v}{\hbar}
\operatorname{Im}(\Upsilon_v^*P_v),
\qquad
P_v:=\left.\psi_Y^*\psi_I\right|_{\mathfrak s=v},
$$

with stationary circuit signs

$$
\Gamma_-:=+\mathcal J_Q,
\qquad
\Gamma_+:=-\mathcal J_Q.
$$

## 3. Added Wilson-Link Action

Define the oriented connection integral and charge-$-g_Q$ parallel transporter

$$
\mathcal B
:=\int_{v_-}^{v_+}B_{\mathfrak s}\,d\mathfrak s,
\qquad
\boxed{
\mathcal W_{+\leftarrow-}
:=e^{-ig_Q\mathcal B}.}
$$

Its transformation law is

$$
\boxed{
\mathcal W_{+\leftarrow-}
\longmapsto
 e^{-ig_Q\chi_+}
 \mathcal W_{+\leftarrow-}
 e^{+ig_Q\chi_-}.}
$$

Consequently

$$
Z_\Upsilon
:=\Upsilon_+^*\mathcal W_{+\leftarrow-}\Upsilon_-
$$

is gauge invariant. Introduce the separately declared conservative extension

$$
\boxed{
S_{\mathrm{tr}}
:=\int dt\,d^3x\,
 t_\Upsilon\left(Z_\Upsilon+Z_\Upsilon^*\right),
\qquad t_\Upsilon>0,}
$$

or equivalently

$$
\boxed{
\mathcal H_{\mathrm{tr}}
:=-t_\Upsilon\left(Z_\Upsilon+Z_\Upsilon^*\right).}
$$

This coupling is local in $(t,\mathbf x)$ and spans the finite scale interval through $\mathcal W_{+\leftarrow-}$. Its coefficient and microscopic origin remain free.

With

$$
\Upsilon_\pm=u_\pm e^{i\alpha_\pm},
\qquad
\Delta_\mathcal W
:=\alpha_+-\alpha_-+g_Q\mathcal B,
$$

one has

$$
Z_\Upsilon=u_-u_+e^{-i\Delta_\mathcal W},
\qquad
\boxed{
\mathcal H_{\mathrm{tr}}
=-2t_\Upsilon u_-u_+\cos\Delta_\mathcal W.}
$$

## 4. Endpoint Equations and Transport Current

Let $\mathcal F_v$ denote the complete right-hand side of the existing endpoint equation before adding inter-vertex transport. Variation of $S_{\mathrm{end}}+S_{\mathrm{tr}}$ gives

$$
\boxed{
\begin{aligned}
i\hbar\partial_t\Upsilon_-
&=\mathcal F_-
-t_\Upsilon\mathcal W_{+\leftarrow-}^*\Upsilon_+,\\
i\hbar\partial_t\Upsilon_+
&=\mathcal F_+
-t_\Upsilon\mathcal W_{+\leftarrow-}\Upsilon_-.
\end{aligned}}
$$

Direct norm differentiation fixes the orientation:

$$
\boxed{
\left.\partial_tn_-\right|_{\mathrm{tr}}
=\frac{2t_\Upsilon}{\hbar}\operatorname{Im}Z_\Upsilon
=-I_{-\to+},
\qquad
\left.\partial_tn_+\right|_{\mathrm{tr}}
=-\frac{2t_\Upsilon}{\hbar}\operatorname{Im}Z_\Upsilon
=+I_{-\to+}.}
$$

Define positive endpoint number transport from $v_-$ to $v_+$ by

$$
\boxed{
I_{-\to+}
:=-\frac{2t_\Upsilon}{\hbar}
\operatorname{Im}Z_\Upsilon
=\frac{2t_\Upsilon u_-u_+}{\hbar}
\sin\Delta_\mathcal W.}
$$

The two endpoint balances become

$$
\boxed{
\begin{aligned}
\partial_tn_-+\nabla\cdot\mathbf J_{\Upsilon,-}
&=\Gamma_- - I_{-\to+},\\
\partial_tn_++\nabla\cdot\mathbf J_{\Upsilon,+}
&=\Gamma_+ + I_{-\to+},
\end{aligned}}
\qquad
n_\pm:=|\Upsilon_\pm|^2.
$$

Transport cancels from the summed endpoint-number balance. On a homogeneous stationary closed endpoint domain, the registered circuit sources close precisely when

$$
\boxed{
I_{-\to+}=\mathcal J_Q,
\qquad
\Gamma_-=+\mathcal J_Q,
\qquad
\Gamma_+=-\mathcal J_Q.}
$$

The Wilson interaction also has a scale-edge gauge current. Along the oriented path,

$$
\boxed{
-\frac{1}{\hbar}
\frac{\delta H_{\mathrm{tr}}}
{\delta B_{\mathfrak s}(\mathfrak s)}
=-g_QI_{-\to+}
\mathbf 1_{(v_-,v_+)}(\mathfrak s).}
$$

This is the charge current of the added Wilson link. It is distinct from the spatial current $\mathbf J_{\Upsilon,v}$ in EL9 and from the Yang/Yin rail current $J_Q$. The oriented indicator has

$$
\partial_{\mathfrak s}\mathbf 1_{(v_-,v_+)}
=\delta(\mathfrak s-v_-)-\delta(\mathfrak s-v_+),
$$

so the link-current divergence cancels the endpoint charge transferred between vertices. The remaining endpoint charge source $-g_Q\Gamma_v$ cancels the rail source $+g_Q\Gamma_v$ at each vertex.

## 5. Capacity and Fixed-Amplitude Curvature

At fixed $u_\pm>0$,

$$
\boxed{
I_c:=\frac{2t_\Upsilon u_-u_+}{\hbar},
\qquad
|I_{-\to+}|\leq I_c.}
$$

A target $\mathcal J_Q$ has a stationary transport phase exactly when

$$
|\mathcal J_Q|\leq I_c.
$$

For $|\mathcal J_Q|<I_c$, let $r:=\mathcal J_Q/I_c$. The two branches may be represented by

$$
\Delta_{\mathrm s}:=\arcsin r,
\qquad
\Delta_{\mathrm u}:=\pi-\arcsin r
\pmod{2\pi}.
$$

Their fixed-amplitude phase curvature is

$$
\boxed{
\frac{\partial^2\mathcal H_{\mathrm{tr}}}
{\partial\Delta_\mathcal W^2}
=2t_\Upsilon u_-u_+\cos\Delta_\mathcal W.}
$$

For $t_\Upsilon>0$ and $u_\pm>0$, the principal branch has positive curvature, the companion has negative curvature, and the capacity boundary is marginal. This is a one-coordinate phase statement. Amplitude stability and the coupled rail-endpoint spectrum remain outside the receipt.

## 6. Frozen Numerical Point

Use deterministic normalized units

$$
\hbar=1.7,
\quad
t_\Upsilon=0.8,
\quad
u_-=0.9,
\quad
u_+=1.1,
\quad
g_Q=0.4,
$$

where $u_-=0.9$ and $u_+=1.1$ are the endpoint amplitudes, and

$$
\kappa_-=0.6,
\quad
\kappa_+=0.7,
\quad
\mu_-=1.2,
\quad
\mu_+=0.95.
$$

Freeze

$$
\mathcal B=0.37,
\qquad
\alpha_-=0.23,
\qquad
r=0.4,
\qquad
\Delta_{\mathrm s}=\arcsin r,
$$

and choose

$$
\alpha_+
:=\alpha_- - g_Q\mathcal B+\Delta_{\mathrm s}.
$$

The stationary target is

$$
\mathcal J_Q:=0.4I_c.
$$

For the gauge-covariance check use

$$
\chi_-=0.29,
\qquad
\chi_+=-0.41,
\qquad
\mathcal B\longmapsto
\mathcal B+\chi_+-\chi_-.
$$

For the stationary endpoint equations define the imposed rail bilinears by

$$
\boxed{
\begin{aligned}
P_-&:=\frac{\mu_-\Upsilon_-
-t_\Upsilon\mathcal W_{+\leftarrow-}^*\Upsilon_+}{\kappa_-},\\
P_+&:=\frac{\mu_+\Upsilon_+
-t_\Upsilon\mathcal W_{+\leftarrow-}\Upsilon_-}{\kappa_+}.
\end{aligned}}
$$

These definitions fix the local source signs without an additional
orientation choice:

$$
\kappa_-\operatorname{Im}(\Upsilon_-^*P_-)
=t_\Upsilon\operatorname{Im}Z_\Upsilon,
\qquad
\kappa_+\operatorname{Im}(\Upsilon_+^*P_+)
=-t_\Upsilon\operatorname{Im}Z_\Upsilon,
$$

and therefore

$$
\Gamma_-=I_{-\to+},
\qquad
\Gamma_+=-I_{-\to+}.
$$

The supercritical control uses $\mathcal J_Q^{\mathrm{sup}}:=1.05I_c$. The zero-coupling control sets $t_\Upsilon=0$ while retaining the frozen nonzero target $\mathcal J_Q$.

## 7. Frozen Gates

All absolute and relative tolerances are $10^{-11}$ except the centered finite-difference Wilson-current check, whose tolerance is $10^{-9}$.

### IT1—Wilson gauge covariance

Require the transformed connection integral to reproduce the endpoint-dressed transformation law for $\mathcal W_{+\leftarrow-}$. Require $Z_\Upsilon$, $\mathcal H_{\mathrm{tr}}$, $I_{-\to+}$, and both transformed stationary endpoint equations to remain invariant or covariant below tolerance.

### IT2—Stationary endpoint closure

Require both imposed-bilinear endpoint-equation residuals to vanish. Require the source identities

$$
\Gamma_-=I_{-\to+},
\qquad
\Gamma_+=-I_{-\to+},
$$

and the two stationary endpoint balances to hold below tolerance. Require the summed endpoint source to vanish.

### IT3—Scale-edge charge-current ledger

Differentiate the Wilson Hamiltonian with respect to $\mathcal B$ by a centered finite difference. Require

$$
-\hbar^{-1}\partial_{\mathcal B}\mathcal H_{\mathrm{tr}}
=-g_QI_{-\to+}
$$

within the stated finite-difference tolerance. Evaluate the two-vertex incidence ledger and require the rail sources, endpoint charge rates, and Wilson-link current divergence to sum to zero at each vertex.

### IT4—Finite transport capacity

Require the stable and companion phase branches to reproduce the same subcritical target, the critical phase $\pi/2$ to reproduce $I_c$, and the frozen target to satisfy $|\mathcal J_Q|<I_c$. Require the supercritical control to exceed the analytic sine bound by exactly $0.05I_c$ within tolerance.

### IT5—Fixed-amplitude phase curvature

Require positive curvature on $\Delta_{\mathrm s}$, negative curvature on $\Delta_{\mathrm u}$, equal curvature magnitudes within tolerance, and zero curvature at the marginal phase $\pi/2$ within tolerance.

### IT6—Necessary controls

Remove the Wilson factor while retaining independent endpoint gauge angles. Require the bare bilinear to change by more than $10^{-3}$. Set $t_\Upsilon=0$ while retaining $\mathcal J_Q\ne0$ and require the homogeneous stationary closure residual to equal $|\mathcal J_Q|$ within tolerance.

The overall verdict is `PASS` only if IT1–IT6 all pass. Any failed assertion fixes the first-execution verdict as `FAIL`; the script and raw output remain part of the record. No coefficient, phase, tolerance, control, or gate may be changed after the first execution.
