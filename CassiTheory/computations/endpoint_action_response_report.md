# Source-Action Charged-Endpoint Response Outcome

## Status: PASS—September 2026

## 1. Verdict

The frozen AR1–AR6 source-action receipt passes on its first execution. The registered endpoint action therefore has, conditionally on the declared background and coefficients, a gauge-covariant $4\times4$ Nambu rail response with the endpoint action kernel

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
| AR3 zero-background order and sign | **PASS**—the quadratic correction vanishes, the leading term is quartic, and its action contribution is positive |
| AR4 endpoint stability and poles | **PASS**—both curvature eigenvalues are positive and the analytic pole pair is reproduced |
| AR5 source-action elimination, covariance, and Nambu boundary | **PASS**—the $\mathcal K$ and $\mathcal D$ forms agree, direct elimination closes, constant-frame covariance holds, and the anomalous block is nonzero |
| AR6 closed and open response classes | **PASS**—the closed response is Hermitian; the damped retarded response is non-Hermitian and its advanced partner is the adjoint |

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

A nonzero stationary conversion current requires endpoint spatial flux, an open or driven channel, a non-harmonic state, or a larger coupled background.

### 4.2 Symmetric zero background

At $Y_0=I_0=\Upsilon_{v,0}=0$, the direct and mixed quadratic rail blocks vanish. With $m_{v,0}>0$,

$$
\mathcal K_{v,0}(0)=-m_{v,0}I_2,
\qquad
\boxed{
\Delta Q_{v,0}^{(4)}
=-\frac12j_{v,0}^\dagger\mathcal K_{v,0}^{-1}j_{v,0}>0.}
$$

The endpoint-mediated rail term therefore begins at quartic order and cannot supply a linear Robin response about the symmetric vacuum.

### 4.3 Active background

At generic nonzero $Y_0$ and $I_0$, the mixed block $\mathcal C_v$ is nonzero and the effective response has particle–hole blocks. The active boundary law is generically Nambu doubled. The ordinary $2\times2$ complex-linear Cayley response applies to a frozen endpoint or to an active branch where the anomalous blocks cancel.

### 4.4 Closed and damped domains

For $A_v>|B_v|$, the endpoint pole pair is

$$
\omega=\pm\frac{\sqrt{A_v^2-|B_v|^2}}{\mathcal Z_v}.
$$

The closed pole-free response is Hermitian. The declared damping continuation shifts the poles by $-i\gamma_v$, gives a non-Hermitian retarded response, and obeys $\mathbb\Lambda^A=(\mathbb\Lambda^R)^\dagger$. A microscopic damping channel remains unselected.

## 5. Research Boundary

The receipt establishes algebraic response identities around one declared normalized background. A physical endpoint model still requires:

- a selected $U_v$, $K_v$, and $u_v$;
- a background with the spatial flux, drive, or larger coupling needed for nonzero stationary conversion current;
- a microscopic damping mechanism;
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
- `foundations/interscale-stress-attenuation-boundary.md`—boundary-stress and Robin-response interpretation
