# Source-Action Charged-Endpoint Response Outcome

## Status: PASS—September 2026

## 1. Verdict

The frozen AR1–AR6 source-action receipt passes on its first execution. The first-order endpoint action (EL9) therefore has, conditionally on the declared background and coefficients, a $4\times4$ Nambu rail response covariant under the declared constant relative-frame transformation, with endpoint action kernel

$$
\boxed{
\mathcal K_v^R
=\mathcal Z_v(\omega+i\gamma_v)\sigma_3-\mathcal H_v
=-\mathcal D_v^R,}
$$

and the equivalent Schur forms

$$
\boxed{
\mathbb\Lambda_{\mathrm{eff},v}^R
=\mathbb\Lambda_{0,v}
-\mathcal C_v^\dagger(\mathcal K_v^R)^{-1}\mathcal C_v
=\mathbb\Lambda_{0,v}
+\mathcal C_v^\dagger(\mathcal D_v^R)^{-1}\mathcal C_v.}
$$

This is a conditional response identity. It does not select the endpoint potential, amplitude, background, damping mechanism, trace normalization, physical species-port map, or a particle lifetime.

AR1–AR6 are the Bogoliubov–de Gennes linearization of the first-order endpoint action (EL9). No coefficient from the separate second-order fixed-$Q_C$ particle action enters $\mathcal H_v$, $\mathcal K_v^{R/A}$, the pole law, or the Schur complement.

## 2. Frozen Execution

The first and only execution was

```text
python computations/endpoint_action_response_check.py
```

and returned

```text
Cassi source-action charged-endpoint response check
  AR1 background residual             = 0.000e+00
  AR1 closed link current             = 0.000e+00
  AR2 trilinear reconstruction error  = 0.000e+00
  AR2 mixed-Hessian error             = 6.202e-19
  AR2 static action-Hessian error     = 6.951e-18
  AR3 positive quartic contribution   = 3.708520494545e-05
  AR3 quartic scaling error           = 0.000e+00
  AR4 endpoint pole frequency         = 0.462391879254
  AR4 maximum pole residual           = 0.000e+00
  AR5 K/D sign-equivalence residual   = 0.000e+00
  AR5 elimination residual            = 1.511e-17
  AR5 covariance residual             = 2.220e-16
  AR5 anomalous-block norm            = 0.390450933151
  AR6 closed Hermiticity residual     = 3.103e-17
  AR6 damped non-Hermiticity norm     = 0.360569701415
  AR6 advanced-adjoint residual       = 6.206e-17
ALL CHECKS PASSED
```

The frozen equality tolerance is $5\times10^{-13}$. The anomalous-block and damped non-Hermiticity norms exceed their frozen $10^{-3}$ lower bounds.

## 3. Gate Accounting

| Gate | Outcome |
|---|---|
| AR1 closed homogeneous current boundary | **PASS**—the background equation and phase balance give zero closed link current |
| AR2 exact trilinear and static action Hessians | **PASS**—the trilinear polynomial, mixed block, and $-\mathcal H_v$ static action block agree |
| AR3 zero-background order and source-action sign | **PASS**—the quadratic correction vanishes; the leading eliminated-source-action term is quartic and has a positive coefficient for the registered $m_{v,0}=1.1>0$, the protocol notation for $\mu_{v,0}:=W_v'(0)$ |
| AR4 endpoint stability and poles | **PASS**—both endpoint-curvature eigenvalues are positive and the analytic pole pair is reproduced |
| AR5 source-action elimination, covariance, and Nambu boundary | **PASS**—the $\mathcal K$ and $\mathcal D$ forms agree, direct elimination closes, constant-frame response-kernel covariance holds, and the anomalous block is nonzero |
| AR6 conservative and damped response classes | **PASS**—for $\gamma_v=0$ the real pole-free response is Hermitian; the declared retarded continuation is non-Hermitian, has lower-half-plane poles, and has the advanced response as its adjoint |

The overall frozen verdict is **PASS** because AR1–AR6 all pass.

## 4. Derived Boundaries

### 4.1 Closed homogeneous current

The background equation

$$
W_v'(u_v^2)\Upsilon_{v,0}=\kappa_vY_0^*I_0
$$

forces

$$
\operatorname{Im}(\Upsilon_{v,0}^*Y_0^*I_0)=0,
\qquad
\boxed{\mathcal I_{\mathrm{link}}=0.}
$$

Here $\mathcal I_{\mathrm{link}}=-2\Gamma_v$ is the negative
rail-difference rate; $\Gamma_v$ is the Yang source coefficient and
$g_Q\Gamma_v$ is the gauge-weighted source. Stationary spatial endpoint flux
permits a local source only with compensating sinks or boundary flux because
$\int_\Omega\Gamma_vd^3x=\oint_{\partial\Omega}
\mathbf J_{\Upsilon,v}\cdot d\mathbf S$. Open or driven channels,
non-harmonic states, and larger coupled backgrounds provide separate branches.

### 4.2 Symmetric zero background

At $Y_0=I_0=\Upsilon_{v,0}=0$, the direct and mixed quadratic rail blocks vanish. Define the static zero-background source-action curvature

$$
\mu_{v,0}:=W_v'(0)>0.
$$

The frozen AR3 protocol denotes this same curvature by $m_{v,0}$ and evaluates it at $m_{v,0}=1.1$. The symbol is protocol notation for a static potential curvature, not an inertial or physical mass. For a nonzero unnormalized endpoint source $j_{v,0}$,

$$
\mathcal K_{v,0}(0)=-\mu_{v,0}I_2,
\qquad
\boxed{
\Delta Q_{v,0}^{(4)}
:=-\frac12j_{v,0}^\dagger\mathcal K_{v,0}^{-1}j_{v,0}
=\frac{j_{v,0}^\dagger j_{v,0}}{2\mu_{v,0}}>0,}
\qquad
\Delta Q_{v,0}^{(4)}=O(\eta^4).
$$

The symmetric-vacuum term therefore begins at quartic rail order and cannot supply a linear Robin response. Its positive coefficient belongs to the eliminated source action under the Hypothesized curvature condition $\mu_{v,0}>0$; it is not a physical energy, stress, or stability result.

### 4.3 Active background

At generic nonzero $Y_0$ and $I_0$, the mixed block $\mathcal C_v$ is nonzero and the effective response has particle–hole blocks. This is the Bogoliubov–de Gennes response of the first-order endpoint action (EL9); the separate second-order fixed-$Q_C$ particle action remains outside this response. The active boundary law is generically Nambu doubled. The ordinary $2\times2$ complex-linear Cayley response applies to a frozen endpoint or to an active branch where the anomalous blocks cancel.

### 4.4 Closed and damped domains

With fields proportional to $e^{-i\omega t}$ and $A_v>|B_v|$, the conservative $\gamma_v=0$ endpoint poles are

$$
\omega=\pm\omega_{\mathrm{end}},
\qquad
\omega_{\mathrm{end}}
:=\frac{\sqrt{A_v^2-|B_v|^2}}{\mathcal Z_v}.
$$

The nonnegative quantity $\gamma_v\ge0$ has angular-frequency units,
$[\gamma_v]=T^{-1}$. It is a phenomenological retarded continuation of the
first-order Schrödinger/Berry endpoint action,
$\mathcal K_v^R=\mathcal Z_v(\omega+i\gamma_v)\sigma_3-\mathcal H_v$; it
supplies no second-order inertial coefficient and selects no microscopic bath.
The retarded poles are
$\omega=\pm\omega_{\mathrm{end}}-i\gamma_v$ in the lower half-plane. Conjugate
continuation gives
$\mathcal K_v^A=\mathcal Z_v(\omega-i\gamma_v)\sigma_3-\mathcal H_v
=(\mathcal K_v^R)^\dagger$ for real $\omega$, with poles
$\omega=\pm\omega_{\mathrm{end}}+i\gamma_v$ in the upper half-plane and
$\mathbb\Lambda^A=(\mathbb\Lambda^R)^\dagger$. The limit $\gamma_v\to0$
recovers the separate conservative kernel and its real pole pair. A
microscopic damping channel remains unselected.

## 5. Research Boundary

The receipt establishes algebraic response identities for the Bogoliubov–de Gennes linearization of the first-order endpoint action around one declared normalized background, together with response-kernel covariance under constant relative-frame rotations. The separate second-order fixed-$Q_C$ particle action and full time-dependent gauge covariance remain outside AR1–AR6. A physical endpoint model still requires:

- a selected $U_v$, $K_v$, and $u_v$;
- a sign-changing stationary source with endpoint flux, a physical boundary or
  inter-vertex transport channel, a drive, or a larger coupled background;
- a microscopic damping mechanism;
- a temporal relative-gauge connection for time-dependent frame covariance;
- a physical trace normalization and Yang/Yin species-port map;
- the doubled port-flux law for the Nambu response;
- the full coupled rail–endpoint fluctuation spectrum;
- an independently selected matching frequency, dressed phase, and $k_\star$;
- particle quantum numbers and an observable lifetime.

## References

- `computations/endpoint_action_response_prereg.md`—frozen AR1–AR6 protocol
- `computations/endpoint_action_response_check.py`—first-execution analytic receipt
- `computations/endpoint_dynamical_response_report.md`—separate failed energy-kernel receipt
- `foundations/endpoint-link-and-localization-boundary.md`—registered charged-endpoint action and response boundary
- `computations/endpoint_spatial_flux_report.md`—stationary source,
  closed-domain zero-mode, and gradient-cost boundary
- `foundations/interscale-stress-attenuation-boundary.md`—boundary-stress and Robin-response interpretation
