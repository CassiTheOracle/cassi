# Charged-Endpoint Spatial-Flux Report

## Status: PASS—September 2026

## 1. Result

The frozen SF1–SF6 receipt passes on its first execution. The charged-endpoint action has an exact local continuity law, and its spatial stiffness can support stationary local Yang/Yin source-and-sink conversion through endpoint current divergence. A closed periodic or no-flux endpoint domain still has zero integrated conversion source at each scale vertex.

The derived source normalization is

$$
\Gamma_v
=-\frac{2\kappa_v}{\hbar}
\operatorname{Im}(\Upsilon_v^*P_v),
\qquad
\mathcal I_{\mathrm{link},v}=-2\Gamma_v.
$$

Thus $\Gamma_v$ is the Yang source coefficient, $\mathcal I_{\mathrm{link},v}$ is the negative rail-difference rate, and $g_Q\Gamma_v$ is the gauge-weighted source.

## 2. Frozen Execution

The preregistration and checker are:

- `computations/endpoint_spatial_flux_prereg.md`
- `computations/endpoint_spatial_flux_check.py`

The frozen command was run once from the repository root:

```text
python computations/endpoint_spatial_flux_check.py
```

The complete output was:

```text
Charged-endpoint spatial-flux receipt
  grid                              = 24^3
  direct gradient energy            = 4.670076740822e+00
  gamma spectral energy             = 4.670076740822e+00
  link spectral energy              = 4.670076740822e+00
  SF1 source-normalization error     = 0.000e+00
  SF1 charge-cancellation error      = 0.000e+00
  SF2 endpoint-equation error        = 1.570e-16
  SF2 link-source error              = 3.886e-16
  SF2 continuity error               = 1.193e-15
  SF3 invariant-gradient error       = 2.776e-17
  SF3 covariant-derivative error     = 5.594e-17
  SF3 covariant-laplacian error      = 1.144e-16
  SF3 current-invariance error       = 1.388e-16
  SF3 source-invariance error        = 1.665e-16
  SF3 transformed-equation error     = 4.518e-16
  SF4 analytic-phase error           = 1.804e-16
  SF4 periodic-source mean           = 8.224e-18
  SF5 bad-source mean error          = 0.000e+00
  SF5 reconstructed-divergence mean  = 8.224e-18
  SF5 zero-mode residual error       = 1.027e-15
  SF6 gamma-energy relative error    = 1.902e-16
  SF6 link-energy relative error     = 1.902e-16
  SF1                              = PASS
  SF2                              = PASS
  SF3                              = PASS
  SF4                              = PASS
  SF5                              = PASS
  SF6                              = PASS
OVERALL: PASS
```

## 3. Gate Ledger

| Gate | Frozen claim | Result |
|---|---|---|
| SF1 | $\mathcal I_{\mathrm{link},v}=-2\Gamma_v$ and the gauge-weighted rail and endpoint sources cancel | PASS |
| SF2 | The imposed-bilinear endpoint equation is exact and $\nabla\cdot\mathbf J_{\Upsilon,v}=\Gamma_v$ | PASS |
| SF3 | The current, source, covariant derivative, covariant Laplacian, and endpoint equation are covariant under the declared nonconstant time-independent frame change | PASS |
| SF4 | The periodic Fourier inverse reproduces the analytic phase and source divergence | PASS |
| SF5 | Adding source mean $0.07$ leaves a uniform residual $-0.07$ because periodic divergence has no zero mode | PASS |
| SF6 | At the frozen $K_v=2.3$ and $u_v=0.9$, direct, $\Gamma_v$-spectral, and $\mathcal I_{\mathrm{link},v}$-spectral gradient energies agree and are positive | PASS |

## 4. Derived Boundary

The exact endpoint current is

$$
J_{\Upsilon,v}^i
:=\frac{K_v}{\hbar}
\operatorname{Im}\!\left[
\Upsilon_v^*D_i^{(-g_Q)}\Upsilon_v
\right],
$$

and the endpoint number balance is

$$
\partial_t|\Upsilon_v|^2
+\partial_iJ_{\Upsilon,v}^i
=\Gamma_v.
$$

For stationary density,

$$
\int_\Omega\Gamma_v\,d^3x
=\oint_{\partial\Omega}
\mathbf J_{\Upsilon,v}\cdot d\mathbf S.
$$

This identity sharpens the spatial-flux escape from the homogeneous closed-current boundary. Local conversion is compatible with a stationary endpoint when the source has compensating sinks or when endpoint current crosses the boundary. A spatially uniform nonzero circuit source cannot be stationary in a closed endpoint domain under the registered action.

For constant amplitude on a periodic cube, every zero-mean source has the phase reconstruction

$$
\alpha_{v,\mathbf k}
=-\frac{\hbar}{K_vu_v^2}
\frac{\Gamma_{v,\mathbf k}}{|\mathbf k|^2},
\qquad \mathbf k\ne\mathbf0,
$$

and, when $K_v>0$ and $u_v>0$, has the positive gradient cost

$$
H_{\nabla\Upsilon,v}
=\frac{\hbar^2V}{2K_vu_v^2}
\sum_{\mathbf k\ne\mathbf0}
\frac{|\Gamma_{v,\mathbf k}|^2}{|\mathbf k|^2}.
$$

The frozen normalized source gives

$$
H_{\nabla\Upsilon,v}=4.670076740822.
$$

This normalized value verifies the declared algebra and carries no calibrated
particle-energy interpretation.

## 5. Scope and Decision

**Decision: ADOPT the conditional spatial-flux identities and closed-domain obstruction.**

The result establishes:

- exact endpoint, rail-difference, and charge-source normalization;
- local stationary source support by endpoint current divergence;
- a zero-mode obstruction for every closed periodic or no-flux endpoint domain;
- a positive nonlocal gradient cost for every reconstructible source when $K_v>0$ and $u_v>0$;
- covariance under the declared time-independent local relative-frame transformations.

The result leaves open:

- the coupled rail solution that generates the imposed bilinear $P_v$;
- a physical endpoint potential $U_v$, stiffness $K_v$, amplitude $u_v$, and source profile;
- inter-vertex endpoint transport or a physical boundary-flux channel;
- the complete particle energy, spectrum, localization, stability, and particle identification.

## References

- `computations/endpoint_spatial_flux_prereg.md`—frozen SF1–SF6 protocol
- `computations/endpoint_spatial_flux_check.py`—deterministic analytic and Fourier receipt
- `foundations/endpoint-link-and-localization-boundary.md` §3.10—derived continuity, zero-mode, and gradient-cost identities
- `foundations/interscale-current-soliton.md` §4.5—stationary scale-circuit source convention
