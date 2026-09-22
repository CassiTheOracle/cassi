# The Enstrophy Budget of the Widening Channel

**Status:** frozen pre-registration, 2026-09-21.

Companion to `computations/navier-stokes-curvature-clock-prereg.md` and
`computations/navier-stokes-curvature-clock-saturation-prereg.md`. The clock
measured the margin $\kappa a_n$ at the field core; its decision rule D3 recorded
that the assembled right-hand side of (KC1) is a *material* rate while the field
core is an argmax that slides through the fluid. Both readings are therefore
stated here on one declared trajectory, and the widening channel is expressed in
the flow's own enstrophy budget.

## 1. The identities under test

Write the frame $(t,n,b)$ with $t=\xi=\omega/|\omega|$, $n$ the geometric normal,
$b=t\times n$, and $\ell=t\cdot(\nabla u)t$. Incompressibility gives the frame
closure

$$\ell+n\!\cdot\!Sn+b\!\cdot\!Sb=0 \tag{KF}$$

so the widened-normal channel is fixed by the axial and binormal strains:
$2n\!\cdot\!Sn=-2\ell-2b\!\cdot\!Sb$, and (KC1) becomes

$$\frac{D_\tau\log(\kappa a_n)}{}=\underbrace{\frac{n\!\cdot\!(\partial_s\nabla u)t}{\kappa}}_{\text{bend}}\;-\;4\ell\;-\;2\,b\!\cdot\!Sb \tag{KC2}$$

The local enstrophy identity $D_\tau e=\omega\!\cdot\!S\omega+\nu\,\omega\!\cdot\!\Delta\omega$
with $e=\tfrac12|\omega|^2$ and $\omega\!\cdot\!S\omega=|\omega|^2\ell$ writes the axial
stretching as the local enstrophy rate:

$$\frac{D_\tau\log(\kappa a_n)}=\frac{\text{bend}}{\kappa}-2\,D_\tau\log e+4\nu\frac{\omega\!\cdot\!\Delta\omega}{|\omega|^2}-2\,b\!\cdot\!Sb \tag{KC3}$$

At a point where $|\omega|$ is locally maximal, $\Delta|\omega|^2\le0$ gives
$\omega\!\cdot\!\Delta\omega\le-|\nabla\omega|^2$, and the identity
$\Delta|\omega|^2=2|\omega|\Delta|\omega|+2|\nabla|\omega||^2$ gives the computable cap

$$\frac{D_\tau\log(\kappa a_n)}\le\frac{\text{bend}}{\kappa}-2\,D_\tau\log e+4\nu\frac{\Delta|\omega|}{|\omega|}-2\,b\!\cdot\!Sb \tag{KC4}$$

Every term of (KC2), (KC3) and (KC4) is a local quantity of the velocity field, and
every one of them is obtained from the raw tensors the clock already stores. The
budget's reading: margin growth is funded by the bending channel, by enstrophy
decay, and by binormal compression, against viscous removal.

**Character of the two sides.** (KC2) is a *frozen-field* statement: it is the
part of $D_\tau\log(\kappa a_n)$ produced by moving along the flow direction with
the field held fixed, and the closed forms of the clock's Block K, being steady,
could not distinguish it from the full material rate. The margin's full material
rate carries the field's own evolution as well,

$$D_\tau\log(\kappa a_n)=\underbrace{\frac{\text{bend}}{\kappa}-4\ell-2\,b\!\cdot\!Sb}_{\text{(KC2)}}\;+\;\partial_t\log(\kappa a_n).$$

The enstrophy identity of (KC3) is a *material* statement: $D_\tau e=\omega\!\cdot\!S\omega+\nu\,\omega\!\cdot\!\Delta\omega$
follows from the vorticity equation, which carries $\partial_t\omega$. The
measurement therefore separates the two: the advective increment is compared with
(KC2), the unsteady increment $\partial_t\log(\kappa a_n)$ with the field's own
evolution, and their sum is the material increment.

## 2. Frozen protocol

- The three declared families (`helix_wide`, `helix_narrow`,
  `helix_tight_pitch`), the same initial states, box ($N=16$, grid $6N+1$,
  cutoff $16$), viscosity $\nu=1/10$, step $\Delta t=1/2/1024$ and horizon
  $T=2$ as the saturation window.
- One additional state: a Lagrangian tracer released at the field core of the
  initial condition and advanced by the same RK4 step as the field, with its
  velocity evaluated spectrally from the frozen state at every stage.
- The budget of §1 is evaluated at the tracer, at the tracer's carried position
  and at the field core on a lattice of every $4$-th step ($1025$ lattice points
  per family), and stored in full at the nine saturation checkpoints. Drafted at
  every $64$-th step, widened to $8$ and then to $4$ before invocation: the
  residual of H2 is a finite-difference floor that falls linearly with the
  lattice spacing (measured $1.76\times10^{-4},\ 8.8\times10^{-5},\
  4.4\times10^{-5},\ 2.2\times10^{-5}$ at spacings $8,4,2,1$), so the spacing is
  set where the declared $10^{-4}$ bound is met with margin, and H2b measures that
  fall inside the same run.
- The instrument is validated before the measurement on every family: the point
  evaluator must reproduce the grid values of the initial state at a
  stride-$8$ subsample of the grid points to $10^{-12}$ (check H0). The grid
  convention is `irfftn` of the half-spectrum, whose mirror sum is what a point
  readout has to reproduce; reading a point by shifting the half-spectrum and
  calling `irfftn` again is a different operation and does not reproduce the
  grid, so it is not used.
- Three readings per lattice point: the tracer's own frame, the tracer's
  *carried* position (its position at the previous lattice step) read in the same
  field, and the field core. The carried reading makes the interval decomposition
  exact:
  $\Delta_{\text{material}}=\Delta_{\text{unsteady}}+\Delta_{\text{advective}}$
  with $\Delta_{\text{unsteady}}=\log(\kappa a_n)(S_{i+1},x_i)-\log(\kappa a_n)(S_i,x_i)$
  and $\Delta_{\text{advective}}=\log(\kappa a_n)(S_{i+1},x_{i+1})-\log(\kappa a_n)(S_{i+1},x_i)$.
- Interval budget: the advective increment is compared with the trapezoid of the
  frozen-field right-hand side (KC2) and with the trapezoid of the cap (KC4); the
  residual of the first is the quadrature error of the identity, the deficit of
  the second is the cap's slack. The material increment of $\tfrac12\log|\omega|^2$
  is compared with the trapezoid of the enstrophy rate, and the advective and
  unsteady shares of the material margin increment are reported.
- Reported in addition: the tracer's $|\omega|$ against the field core's, the
  tracer's displacement, and the enstrophy tail of the field.
- Reported, not gated: the field core's measured margin increment against the
  trapezoid of the assembled rate evaluated at the core. The core is an argmax
  that slides, so its assembled rate is a material rate of a point the core
  leaves behind; this comparison quantifies decision rule D3 of
  `computations/navier-stokes-curvature-clock-prereg.md` rather than testing an
  identity.

## 3. Decision rules

0. **H0 instrument.** The point evaluator reproduces `box.grid` of the initial
   state at a stride-$8$ subsample of the grid points to $10^{-12}$ in every
   family. A failure invalidates the point readings.
1. **H1 frame closure.** $|\ell+n\!\cdot\!Sn+b\!\cdot\!Sb|\le10^{-10}$ at every
   evaluated point. A failure contradicts the stored velocity gradients.
2. **H2 identity on the trajectory.** At the tracer, the trapezoid of the
   frozen-field rate (KC2) reproduces the *advective* log-increment to within the
   declared bound $10^{-4}$ at every lattice interval of every family. The bound
   is the finite-difference floor of a chord against a streamline, not a
   quadrature estimate, and **H2b** measures its fall on a $64$-step window of the
   first family: the residual must be below $10^{-4}$ at spacing $4$ and must fall
   by at least $1.8\times$ at each halving of the spacing.
3. **H3 cap.** At the tracer, the trapezoid of (KC4) is not smaller than the
   advective log-increment by more than $10^{-6}$ at any lattice interval. A
   violation falsifies the cap.
4. **H4 enstrophy form.** (KC3) is assembled with the local
   $D_\tau\log e=2\ell+2\nu\,\omega\!\cdot\!\Delta\omega/|\omega|^2$, so its
   agreement with (KC2) to $10^{-9}$ relative at every evaluated point is the
   algebraic identity of §1. **H4b** then tests the same quantity as a
   measurement: the trapezoid of $D_\tau\log e$ reproduces the measured
   $\log|\omega|$ increment along the tracer to within $10^{-4}$ at every lattice
   interval. **H8** verifies the interval decomposition of §2 to $10^{-9}$, and
   **H9** reports the advective and unsteady shares of the material margin
   increment.
5. **H5 the two readings.** The tracer's margin and the field core's margin are
   reported at every checkpoint, together with the tracer's $|\omega|$ ratio.
   Neither reading is a gate; the comparison is the measurement.
6. **H6 resolution.** The field enstrophy tail above $|k|=8$ is reported at every
   checkpoint and the declared $5\times10^{-2}$ classification is applied.
7. **H7 receipt cross-check.** The field-core cell and $|\omega|$ at each
   saturation checkpoint reproduce the raw values of
   `runs/20260921_curvature_clock_saturation/` to $10^{-9}$ relative; both are
   exact readings of shell-limited quantities. The margin is reported against the
   receipt's margin as well. The two margins differ because the clock's width is
   built from the grid interpolant of the direction field, which is not
   shell-limited, while this protocol evaluates the same local algebra pointwise
   from the exact velocity derivatives.

## 4. Stopping rule

All three families are integrated once at the declared parameters. No rerun with
adjusted parameters, no further extension of the horizon, and no additional
family are admitted after the run. Negative, inconclusive and failed outcomes are
retained and reported. The verifier recomputes the frame closure, the assembled
rate, the cap integrals and the budget statistics from the stored values,
reproduces the content digest, and includes a mutation control that perturbs one
stored value and requires at least one check to fail.

### Amendment of 2026-09-22: the material channels

The first invocation (`runs/20260921_curvature_budget`, `status=PASS`, content
digest `334963c0a0ef52ef`) verified every rule above. Its receipt also fixes, from
the same stored values, the size of the piece the frozen-field budget does not
describe: the carried trajectory's own changes against the integrals of the terms
the identity assigns to them. The measured gaps are, on `helix_wide` /
`helix_narrow` / `helix_tight_pitch`: the margin's material increment $+0.44094$ /
$+0.95664$ / $+0.72186$ against the frozen-field integral $+0.00522$ / $+0.00920$ /
$+0.02418$; the curvature channel $-0.02590$ / $-0.03173$ / $-0.09867$ against
$-0.01375$ / $-0.01713$ / $-0.02760$; the width channel $+0.46684$ / $+0.98837$ /
$+0.82053$ against $+0.00941$ / $+0.01316$ / $+0.02589$. The enstrophy identity
alone is material and holds along the carried trajectory to $5.1\times10^{-8}$,
$6.5\times10^{-5}$ and $1.8\times10^{-4}$.

The protocol is therefore amended to report those channels as `material_gaps` in
every family's entry and to check the material enstrophy identity directly (**H10**,
bound $10^{-3}$), with **H11** recording the reported gaps. The identities, the
families, the parameters, the lattice and every existing decision rule are
unchanged; the amendment adds a diagnostic and its reading, and the first
invocation's receipt stands as the frozen-field measurement it is. The second
invocation writes `runs/20260922_curvature_budget`.
