# Whole-Bubble Handedness Selector Protocol

## Status: Preregistered—September 2026

## Abstract

This protocol tests whether the existing Hypothesized phase-bearing interscale
Cassi action can select the sign of a spatially handed collective state. It
separates three claims: the existence of a physical CP-odd helicity observable,
the existence of a linear instability that creates handedness around the
homogeneous state, and the representation of externally prepared helical
states. The calculation uses only the registered positive-coefficient action,
its derived London operator, and the published one- and two-band current
fixtures. An explicit CP-odd helicity term appears only as a signed control and
is absent from the tested Cassi action.

## 1. Question and scope

The tested action is the first-order complex Yang/Yin interscale action in
`foundations/interscale-current-soliton.md` §2.4. Its spatial phase-current and
helicity identities are those of
`turbulence/cassi-fluid-phase-current-hydrodynamics.md` §§2–4.

The binary question is:

> Does this action distinguish the two signs of whole-field spatial helicity or
> contain a negative linear mode that selects a handed state from its
> homogeneous vacuum?

A positive result would require an energy splitting or a negative chiral
Hessian eigenvalue in the registered action. Merely constructing a helical
configuration does not qualify as selection. The calculation does not identify
helicity with baryon number and does not test nonlinear far-from-equilibrium
domain formation.

## 2. Frozen transformations

Charge conjugation is represented by complex conjugation of the doublet and
sign reversal of the relative connection:

$$
C:\quad \Psi\mapsto\Psi^*,\qquad B_A\mapsto-B_A.
$$

For the spatial number-current velocity $u$ and
$\omega=\nabla\times u$, the frozen transformation table is

| Operation | $u(t,\mathbf x)$ | $\omega(t,\mathbf x)$ | $h=u\cdot\omega$ |
|---|---|---|---|
| $C$ | $-u(t,\mathbf x)$ | $-\omega(t,\mathbf x)$ | $+h(t,\mathbf x)$ |
| $P$ | $-u(t,-\mathbf x)$ | $+\omega(t,-\mathbf x)$ | $-h(t,-\mathbf x)$ |
| $CP$ | $+u(t,-\mathbf x)$ | $-\omega(t,-\mathbf x)$ | $-h(t,-\mathbf x)$ |

On a parity-symmetric closed domain,

$$
H=\int u\cdot\omega\,d^3x
$$

is therefore $C$-even, $P$-odd and $CP$-odd. Every term in the tested action is
quadratic in a covariant derivative, curvature, density displacement, or
composition displacement and is invariant under these transformations.

## 3. Frozen static criterion

The homogeneous state has

$$
\rho=\rho_0,\qquad E_Y=\varphi E_I,\qquad
D_i\Psi=D_{\mathfrak s}\Psi=0,\qquad G_{AB}=0.
$$

With all displayed stiffnesses positive, its static energy is zero and the
energy density is a sum of nonnegative terms. A negative static mode would
therefore contradict the declared coefficient domain.

The density Hessian at Fourier symbol
$\sigma=K_x|\mathbf k|^2+K_{\mathfrak s}p^2$ is

$$
W_\sigma=
\frac{\lambda_\rho}{2}aa^T+\lambda_\varphi bb^T
+\frac{\sigma}{4}D^{-1},
$$

where $a=(1,1)^T$, $b=(1,-\varphi)^T$ and
$D=\operatorname{diag}(E_{Y0},E_{I0})$. The allowed longitudinal connection
variation leaves the physical phase branch

$$
\omega_{\rm long}^2=
\frac{\sigma\,\frac{E_{Y0}E_{I0}}{\rho_0}
\left[2\lambda_\rho+\lambda_\varphi(1-\varphi)^2\right]
+\sigma^2/4}{\hbar^2}.
$$

The transverse London operator for a spatial curl eigenmode is

$$
L_T(k,p)=\frac{k^2}{\mu_x}+\frac{p^2}{\mu_m}+M_i^2,
\qquad
M_i^2=\frac{g_Q^2K_x\rho_0}{4}.
$$

The two helical polarizations obey
$\nabla\times B_\pm=\pm kB_\pm$ and must have the same $L_T$ in the registered
action.

## 4. Frozen fixtures

### 4.1 Positive-chart control

One everywhere-positive normalized doublet on a closed domain must reproduce

$$
\int A\wedge dA=0.
$$

This control distinguishes local vorticity from nonzero integrated helicity.

### 4.2 Opposite Beltrami pair

On the $2\pi$ periodic cube, use

$$
u_+(z)=A(\sin z,\cos z,0),\qquad
u_-(z)=A(\sin z,-\cos z,0),
$$

with $A=0.6$. They obey

$$
\nabla\times u_+=u_+,
\qquad
\nabla\times u_-=-u_-,
$$

and have equal mean kinetic energy and opposite mean helicity. Spectral
reconstructions use $N=9,15,21$.

### 4.3 Explicit-selector control

The registered action has $\kappa_H=0$. A diagnostic extension

$$
E_{\kappa}=E_0-\kappa_H H,
\qquad \kappa_H=0.137,
$$

must split the opposite-helicity fixtures by

$$
E_{\kappa,+}-E_{\kappa,-}=-2\kappa_H A^2.
$$

This term is a control demonstrating what an actual CP-odd selector would do;
it is not adopted into the Cassi action.

## 5. Numerical witnesses

The primary calculation evaluates:

1. the transformation-sign table;
2. the positive-chart zero-helicity identity;
3. the opposite Beltrami pair at $N=9,15,21$;
4. the density Hessian at
   $\sigma\in\{0,0.1,1,10\}$ with
   $(\lambda_\rho,\lambda_\varphi,E_{Y0},E_{I0},\hbar)
   =(0.7,1.1,\varphi/(1+\varphi),1/(1+\varphi),1)$;
5. the transverse operator on the Cartesian product
   $\mu_x\in\{0.4,1,2.5\}$,
   $\mu_m\in\{0.5,1.5\}$,
   $M_i^2\in\{0.1,1,3\}$,
   $k\in\{1,2,4\}$ and
   $p\in\{0,1,3\}$;
6. the explicit-selector control.

The independent calculation reconstructs every statistic from the equations
above without importing the primary implementation.

## 6. Frozen gates

| Gate | Pass condition |
|---|---|
| WHS1 | Every $C$, $P$ and $CP$ sign in §2 is reproduced exactly |
| WHS2 | Action-term parity is even and the integrated positive-chart helicity is zero to $10^{-12}$ |
| WHS3 | Maximum Beltrami curl and divergence error is at most $10^{-12}$ on all grids |
| WHS4 | Opposite-helicity mean kinetic energies agree to $10^{-12}$ and their helicities sum to at most $10^{-12}$ |
| WHS5 | Every density-Hessian eigenvalue is at least $-10^{-12}$ and every $\omega_{\rm long}^2$ is at least $-10^{-12}$ |
| WHS6 | Every transverse $L_T$ is positive and the two helical polarizations agree to $10^{-14}$ |
| WHS7 | The registered $\kappa_H=0$ energy splitting is at most $10^{-12}$ |
| WHS8 | The explicit-selector splitting agrees with $-2\kappa_HA^2$ to $10^{-12}$ |

Source, schema, finite-value and raw-array reconstruction checks are mandatory
prerequisites. Any prerequisite failure gives `INCONCLUSIVE`.

## 7. Verdict tree

- WHS1–WHS4 passing returns `SUPPORTS` for a CP-odd whole-field helicity
  observable in the phase-bearing extension.
- WHS5–WHS7 passing returns `DOES NOT EMERGE` for handedness selection from the
  homogeneous state in the registered positive-coefficient action.
- A reproducible negative eigenvalue or nonzero default energy splitting would
  return `EMERGES`, provided WHS1–WHS4 and every prerequisite pass.
- WHS8 must pass as a sensitivity control. Its success does not alter the
  registered-action verdict.
- No outcome changes the complete-matter verdict without a microscopic coupling
  from the selected collective variable to particle production and an
  independently qualified formation trajectory.

## 8. Outputs and stopping rule

The primary output is
`runs/20260910_whole_bubble_handedness_selector/primary/`; the independent
output is
`runs/20260910_whole_bubble_handedness_selector/verification/`.
Both retain JSON, NPZ arrays, manifests and exact source snapshots.

Run one primary calculation and one independent calculation. Do not alter the
fixtures, coefficients, grids, tolerances or verdict tree after observing the
result. An implementation defect may be repaired only in a separately named
recovery directory while retaining the failed attempt.

## References

- `foundations/interscale-current-soliton.md`—phase-bearing interscale action, London operator and exterior-state boundary.
- `turbulence/cassi-fluid-phase-current-hydrodynamics.md`—current, vorticity, helicity and Beltrami identities.
- `computations/matter-formation-continuum-report.md` §§37, 84–85—surrounding-cascade response and matter-completion boundary.
