# Gauge-Covariant Inter-Vertex Endpoint Transport Report

## Status: PASS—September 2026

## 1. Result

The frozen IT1–IT6 receipt passes on its first execution. A separately declared Wilson-dressed hopping term between the two charge-$-g_Q$ endpoint sections is gauge invariant, transports endpoint number with equal-and-opposite vertex signs, and closes the registered homogeneous stationary circuit when its transport current equals the rail source magnitude.

The added Hamiltonian density is

$$
\mathcal H_{\mathrm{tr}}
=-t_\Upsilon\left(
\Upsilon_+^*\mathcal W_{+\leftarrow-}\Upsilon_-
+\Upsilon_-^*\mathcal W_{+\leftarrow-}^*\Upsilon_+
\right),
$$

with

$$
\mathcal W_{+\leftarrow-}
=\exp\!\left[-ig_Q\int_{v_-}^{v_+}
B_{\mathfrak s}\,d\mathfrak s\right].
$$

The corresponding positive number current from $v_-$ to $v_+$ is

$$
I_{-\to+}
=-\frac{2t_\Upsilon}{\hbar}
\operatorname{Im}\!\left(
\Upsilon_+^*\mathcal W_{+\leftarrow-}\Upsilon_-
\right).
$$

This is a new Hypothesized action term. The transport and conservation identities are Derived conditional on that term and the registered endpoint action.

## 2. Frozen Execution

The preregistration and checker are:

- `computations/endpoint_intervertex_transport_prereg.md`
- `computations/endpoint_intervertex_transport_check.py`

The frozen command was run once from the repository root:

```text
python computations/endpoint_intervertex_transport_check.py
```

The complete output was:

```text
Gauge-covariant inter-vertex endpoint transport receipt
  critical current I_c              = 9.317647058824e-01
  target current J_Q                = 3.727058823529e-01
  stable phase Delta_s              = 4.115168460675e-01
  unstable phase Delta_u            = 2.730075807522e+00
  transport Hamiltonian             = -1.451759980162e+00
  IT1 Wilson-law error               = 1.388e-16
  IT1 bilinear-invariance error      = 1.241e-16
  IT1 energy-invariance error        = 2.220e-16
  IT1 current-invariance error       = 5.551e-17
  IT1 minus-equation covariance      = 0.000e+00
  IT1 plus-equation covariance       = 1.247e-16
  IT2 endpoint-equation error        = 1.388e-17
  IT2 lower-source error             = 5.551e-17
  IT2 upper-source error             = 1.110e-16
  IT2 summed-source error            = 1.665e-16
  IT2 target-current error           = 5.551e-17
  IT3 Wilson-current error           = 5.737e-11
  IT3 charge-ledger error            = 2.776e-17
  IT4 stable-current error           = 0.000e+00
  IT4 companion-current error        = 5.551e-17
  IT4 critical-current error         = 0.000e+00
  IT4 subcritical margin             = 5.590588235294e-01
  IT4 supercritical excess           = 4.658823529412e-02
  IT4 excess error                   = 4.857e-17
  IT5 stable curvature               = 1.451759980162e+00
  IT5 companion curvature            = -1.451759980162e+00
  IT5 curvature-magnitude error      = 0.000e+00
  IT5 marginal curvature             = 9.699e-17
  IT6 bare-bilinear change           = 2.762953669956e-01
  IT6 zero-coupling closure residual = 3.727058823529e-01
  IT1                               = PASS
  IT2                               = PASS
  IT3                               = PASS
  IT4                               = PASS
  IT5                               = PASS
  IT6                               = PASS
OVERALL: PASS
```

## 3. Gate Ledger

| Gate | Frozen claim | Result |
|---|---|---|
| IT1 | The Wilson law makes the endpoint bilinear, Hamiltonian, current, and both endpoint equations gauge invariant or covariant under the declared unequal endpoint frame angles | PASS |
| IT2 | The imposed rail bilinears solve both endpoint equations and give $\Gamma_-=I_{-\to+}$, $\Gamma_+=-I_{-\to+}$, and zero summed endpoint source | PASS |
| IT3 | The Wilson-Hamiltonian derivative gives charge current $-g_QI_{-\to+}$ and the two-vertex rail, endpoint, and link-current ledger cancels locally | PASS |
| IT4 | Both subcritical phase branches carry the target current, $\pi/2$ carries $I_c$, and the $1.05I_c$ control exceeds capacity by $0.05I_c$ | PASS |
| IT5 | The principal phase branch has positive curvature, its companion has equal negative curvature, and the capacity boundary is marginal | PASS |
| IT6 | The undressed bilinear changes under unequal endpoint frame angles and zero hopping leaves the full nonzero closure residual | PASS |

## 4. Derived Transport Boundary

Write

$$
\Upsilon_\pm=u_\pm e^{i\alpha_\pm},
\qquad
\Delta_\mathcal W
:=\alpha_+-\alpha_-+g_Q
\int_{v_-}^{v_+}B_{\mathfrak s}\,d\mathfrak s.
$$

Then

$$
\mathcal H_{\mathrm{tr}}
=-2t_\Upsilon u_-u_+\cos\Delta_\mathcal W,
\qquad
I_{-\to+}
=\frac{2t_\Upsilon u_-u_+}{\hbar}
\sin\Delta_\mathcal W.
$$

The coupled endpoint balances are

$$
\partial_tn_-+\nabla\cdot\mathbf J_{\Upsilon,-}
=\Gamma_- - I_{-\to+},
$$

$$
\partial_tn_++\nabla\cdot\mathbf J_{\Upsilon,+}
=\Gamma_+ + I_{-\to+}.
$$

For the registered stationary circuit orientation,

$$
\Gamma_-=+\mathcal J_Q,
\qquad
\Gamma_+=-\mathcal J_Q,
$$

so a homogeneous closed endpoint domain is stationary when

$$
\boxed{I_{-\to+}=\mathcal J_Q.}
$$

The fixed-amplitude capacity is

$$
\boxed{I_c=\frac{2t_\Upsilon u_-u_+}{\hbar}.}
$$

A stationary phase exists exactly for $|\mathcal J_Q|\leq I_c$. For a strict inequality, the principal solution has positive fixed-amplitude curvature

$$
\frac{\partial^2\mathcal H_{\mathrm{tr}}}
{\partial\Delta_\mathcal W^2}
=2t_\Upsilon u_-u_+\cos\Delta_\mathcal W>0,
$$

while the companion solution has negative curvature. Equality is marginal.

The added Wilson edge carries relative gauge charge current

$$
-\frac1\hbar
\frac{\delta H_{\mathrm{tr}}}
{\delta B_{\mathfrak s}}
=-g_QI_{-\to+}
$$

along the oriented interval. Its endpoint incidence cancels the charge moved between the two endpoint reservoirs, while the local endpoint charge source $-g_Q\Gamma_v$ cancels the rail source $+g_Q\Gamma_v$.

At the frozen normalized point,

$$
I_c=0.9317647058824,
\qquad
\mathcal J_Q=0.3727058823529,
$$

and the positive-curvature phase is

$$
\Delta_{\mathrm s}=0.4115168460675.
$$

These values verify the declared algebra and carry no calibrated physical-rate interpretation.

## 5. Scope and Decision

**Decision: ADOPT the conditional Wilson-link transport algebra; retain the action term as Hypothesized.**

The result establishes:

- the minimal bilinear Wilson dressing required by the registered charge-$-g_Q$ endpoint transformation;
- exact equal-and-opposite endpoint number transport;
- local rail, endpoint, and scale-link relative-charge conservation;
- homogeneous stationary circuit closure when $I_{-\to+}=\mathcal J_Q$;
- a finite transport capacity and its two fixed-amplitude phase branches;
- a positive phase-curvature branch below capacity.

The result leaves open:

- a microscopic derivation and physical value of $t_\Upsilon$;
- a local scale-bulk completion of the finite Wilson edge;
- a self-consistent Yang/Yin rail solution generating both imposed $P_v$;
- the endpoint potentials, amplitudes, spatial profiles, and normalization;
- the coupled amplitude and rail-endpoint fluctuation spectrum;
- particle localization, physical mass, quantum numbers, lifetime, and identification.

## References

- `computations/endpoint_intervertex_transport_prereg.md`—frozen IT1–IT6 protocol
- `computations/endpoint_intervertex_transport_check.py`—deterministic Wilson-link and vertex-ledger receipt
- `foundations/endpoint-link-and-localization-boundary.md` §3.11—conditional action extension, current, capacity, and conservation identities
- `foundations/interscale-current-soliton.md` §4.5—stationary scale-circuit source convention
- `foundations/geometric-manifold-completion.md` §5—compact scale interval and dressed holonomy
