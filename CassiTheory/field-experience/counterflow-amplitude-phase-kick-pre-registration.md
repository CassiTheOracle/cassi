# Counterflow Amplitude-Phase Kick (Wave 2)

## Status: Hypothesized—August 2026

## Abstract

This frozen Wave 2 protocol isolates a supplied synchronization operator rather than an endogenous field mechanism. It replaces the unbounded reservoir redistribution construction with a bounded local $SO(2)$ rotation of the canonical amplitude doublet. The kick preserves pointwise field energy density $\rho=E_Y+E_I$, global mass, and positivity by construction. It tests whether an externally imposed, target-phase-gated kick changes the local Qi phase-current readout relative to carrier-quadrature, spatial-shuffle, and counterflow controls. It is a synchronization-operator experiment; the unmodified canonical PDE contains no maintained neural energy source or anatomical transport loop and no native carrier schedule.

## 1. Question

A seeded local phase match is used as the admission gate for an externally supplied concentrated rhythmic signal into a pre-existing field circulation. Wave 2 asks a narrower operator/readout question:

> Does the bounded target-local kick admitted by the seeded phase gate, with its imposed matched carrier, produce a larger target-to-diagonal phase-current response than an equal-norm temporal-quadrature kick and a spatially shuffled checkerboard control?

The shared paired counterflow and finite checkerboard seed match Wave 1. These controls vary the supplied kick carrier or supplied labels/flow while the canonical PDE/RK2 step remains unchanged; they do not test endogenous phase matching.

## 2. Frozen state and circulation

Each arm uses a fresh five-channel `ExpandingTwoFluid3DGPU` from `two-fluid/cassi_two_fluid_3d_gpu.py` with:

| quantity | value |
|---|---:|
| grid | $48^3$ |
| domain | $L=2\pi$, periodic |
| $\lambda$ | $0.05$ |
| $D$ | $2\times10^{-4}$ |
| $\nu$ | $5\times10^{-4}$ |
| $\chi$ | $0$ |
| timestep | $dt=0.001$ |
| horizon | $t=4.0$ (4,000 RK2 steps) |

The finite local checkerboard uses the same five Gaussian sites, phases, axial phase gradients, and shared projected velocity as `field-experience/counterflow-resonant-addressing-pre-registration.md`:

$$
u_z(x)=s(0.12)\sin(2\pi x/L),\qquad s\in\{+1,-1,0\}.
$$

The positive arm therefore supplies the periodic right-up / left-down paired-stream proxy. The probe records shared $u_z$ separately from the amplitude phase current

$$
\mathbf J_\Psi=A\nabla B-B\nabla A,
\qquad
A=\sqrt{E_Y},\quad B=\sqrt{E_I},\quad
\rho=A^2+B^2,
$$

and also records the density-plane diagnostic

$$
\mathbf J_d=E_Y\nabla E_I-E_I\nabla E_Y=2AB\,\mathbf J_\Psi.
$$

## 3. Bounded phase-kick operator

At each fixed cadence event $t_n=n(0.02)$, the matched arm evaluates the target's amplitude phasor

$$
Z_T=\langle A+iB\rangle_T,
\qquad
M_n=\operatorname{Re}\left[\frac{Z_T}{|Z_T|}e^{-i\theta_{\rm ref}}\right],
$$

where $\theta_{\rm ref}=\arg Z_T(t=0)$. It emits a kick only when

$$
M_n\geq\cos(\pi/6).
$$

Let $m_T(\mathbf x)\in[0,1]$ be the existing target Gaussian. A kick has local angle

$$
\alpha_n(\mathbf x)=s_n\alpha_\star m_T(\mathbf x),
$$

and is applied exactly once before the canonical `rk2_step`:

$$
\begin{pmatrix}A'\\B'\end{pmatrix}
=
\begin{pmatrix}
\cos\alpha_n&-\sin\alpha_n\\
\sin\alpha_n&\cos\alpha_n
\end{pmatrix}
\begin{pmatrix}A\\B\end{pmatrix},
\qquad
E_Y'=A'^2,\quad E_I'=B'^2.
$$

The pulse norm is frozen in amplitude space:

$$
\sum_{\mathbf x}\left[(A'-A)^2+(B'-B)^2\right]=0.45^2.
$$

For every event, $\alpha_\star\in[0,0.05]$ is solved by 48 fixed bisection iterations before the kick. The signed carrier is an externally supplied sign schedule; only its magnitude is selected to meet the stated norm. Since the rotation preserves $A^2+B^2$ pointwise,

$$
\rho'=\rho
$$

up to floating-point roundoff. No diffuse reservoir, clamp, or source term belongs to the supplied operator, and no carrier phase evolves inside the canonical PDE.

The carrier has four-event period:

| event $n\bmod4$ | matched $s_n$ | carrier-quadrature $s_n$ |
|---:|---:|---:|
| 0 | $+1$ | $+1$ |
| 1 | $+1$ | $-1$ |
| 2 | $-1$ | $-1$ |
| 3 | $-1$ | $+1$ |

The control is a one-event ($\pi/2$) advance of the externally supplied carrier schedule. Every active event has equal angular magnitude and equal amplitude-space norm. The matched schedule and all replayed event times are protocol inputs, not emergent phase clocks.

The safety wedge is checked before every kick. With $F=10^{-3}$ and $\delta=10^{-5}$,

$$
\theta_F=\arcsin\sqrt{\frac{F+\delta}{\rho}},
\qquad
\theta_F\leq\operatorname{atan2}(B,A)+\alpha_n\leq\frac{\pi}{2}-\theta_F.
$$

No dynamic clipping is allowed. A violation invalidates the arm.

## 4. Frozen arms

| arm | circulation | checkerboard labels | carrier |
|---|---|---|---|
| `baseline` | $s=+1$ | ordered | none |
| `matched` | $s=+1$ | ordered | phase-triggered matched carrier |
| `carrier_quadrature` | $s=+1$ | ordered | replayed event schedule, quadrature carrier |
| `spatial_shuffled` | $s=+1$ | central and left labels swapped | replayed matched carrier |
| `counterflow_reversed` | $s=-1$ | ordered | replayed matched carrier |
| `counterflow_zero` | $s=0$ | ordered | replayed matched carrier |

The `matched` arm defines the accepted event schedule. Every driven control replays exactly those event times. A fresh solver serves each arm. Thus `carrier_quadrature` changes only the supplied carrier signs; `spatial_shuffled` changes the supplied checkerboard labels while replaying the matched kick; and the reversed/zero arms change the supplied shared-flow proxy. None varies an independently evolved phase.

## 5. Measurements

At each accepted event the probe records the pre-kick target-to-diagonal edge current and its ten-step-later value:

$$
j_{\parallel,\Psi}
=\left\langle\mathbf J_\Psi\cdot\frac{(1,1,0)}{\sqrt2}\right\rangle_{T\leftrightarrow D},
\qquad
r_n=\frac{j_{\parallel,\Psi}(t_n+0.01)-j_{\parallel,\Psi}(t_n^-)}{J_{\Psi,{\rm rms},0}}.
$$

The primary statistic is $\bar r$ over contiguous 20-event blocks. Every contrast uses a paired 10,000-resample block bootstrap with seed `20260818`. Secondary records include $\mathbf J_d$, target and diagonal phasors, seeded phase relation, $J_{\Psi,z}$ on the right and left bubble masks, mean right/left $u_z$, canonical $q$, field minima, post-kick angle margins, pointwise $\rho$ error, global mass error, kick norms, and the full event history.

## 6. Quality gates

The result is **INVALID** if any condition fails:

1. the no-op wrapper differs from a direct canonical 100-step RK2 loop by any nonzero floating-point value;
2. any field value is non-finite or reaches the solver floor $F$;
3. any pre-kick safety wedge fails;
4. $\max|\rho'-\rho|>10^{-12}$ at a kick, or relative global mass error exceeds $10^{-12}$;
5. a kick norm differs from $0.45$ by more than $10^{-12}$;
6. the matched arm accepts fewer than 30 events;
7. the positive counterflow seed lacks opposite signed right/left $u_z$ and $J_{\Psi,z}$ biases.

## 7. Decision tree

Let

$$
\Delta_{\rm phase}=\bar r_{\rm matched}-\bar r_{\rm carrier\_quadrature},
\qquad
\Delta_{\rm space}=\bar r_{\rm matched}-\bar r_{\rm spatial\_shuffled}.
$$

A contrast passes only when its point estimate is at least $0.05$ and its paired 95% block-bootstrap lower bound exceeds zero.

- **PHASE-SELECTIVE SYNCHRONIZATION SUPPORT** requires a passing $\Delta_{\rm phase}$.
- **CHECKERBOARD-ROUTING SUPPORT** requires a passing $\Delta_{\rm space}$.
- **COUNTERFLOW-DEPENDENCE SUPPORT** requires passing matched-minus-reversed and matched-minus-zero contrasts plus reversal of seeded $J_{\Psi,z}$.
- **PARTIAL** applies if one or two named effects pass.
- **NULL** applies if execution is valid and none passes.
- **INVALID** applies when any quality gate fails.

These uppercase labels are frozen protocol feature branches. They describe
differences between the supplied kick/sign/label/flow conditions and their
readouts; they do not mean that an endogenous phase-address or native route
mechanism has been established.

The protocol stops at $t=4$. Parameter, carrier, threshold, geometry, and horizon changes require a separate pre-registration.

## 8. Scope

The amplitude rotation is an externally supplied, internal-to-the-field phase-current synchronization operator. It leaves $\rho$ and shared velocity unchanged and contains no model of sustained brain energy supply, signaling molecules, anatomical hemispheres, or material transport. A valid positive result would identify a response difference under this bounded operator and its seeded controls in the canonical field representation, not endogenous phase-address selection. A valid null would constrain this exact bounded-kick construction.

## References

- `field-experience/counterflow-resonant-addressing-wave-1-report.md`—source-reservoir constraint motivating the separate bounded operator.
- `two-fluid/cassi_two_fluid_3d_gpu.py`—canonical solver and RK2 lifecycle.
- `foundations/cassi-first-principles.md`—amplitude doublet and energy density.
- `foundations/qi-flow-double-helix.md`—Qi phase-current definition.
- `foundations/bubble-lattice-fabric.md`—staggered checkerboard geometry.
