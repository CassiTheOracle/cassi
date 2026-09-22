# Thick Torus Relaxation of the Charged Wound Carrier Loop

## Status: Pre-registered—September 2026 | Frozen | One invocation | Revision 2 pre-invocation, not invoked

### Revision record

Revision 2 (2026-09-22, before any invocation) corrects two internal inconsistencies found while
implementing the protocol, records the solver actually used, and records that the single
invocation is retained:

1. the registered mass of §2 omitted the loop length: the transported reference of §2 is a total
   energy while the formula written there was per unit length, and the comparison against the
   dilute threshold is only meaningful in the total convention;
2. the validation comparisons of §3.2 divided by $2\pi R$ on one side only, so V1 and V2 compared a
   per-unit-length energy against a flat per-unit-length anchor after an extra $2\pi R$ division,
   and V3 compared a per-unit-length energy against a total reference;
3. the solver declaration of §3.1 now names the method that is actually used, and its iteration
   budget.

The invocation is retained because the implemented solver does not reach the registered
stationarity gate; `computations/matter-formation-thick-torus-gap-report.md` records the exact-metric
measurements taken before invocation, the mechanism they expose, and the remaining obstacle.

## 1. Question and scope

The registered tube geometry (`computations/matter_formation_tube_geometry.py`) established that a bent untwisted tube costs no energy, that a twisted tube is a spring with a preferred radius, and that the reduced charge problem binds a charged wound loop. The wound-loop calculation (`computations/matter_formation_wound_loop_gap.py`, report `computations/matter-formation-wound-loop-gap-report.md`, theorem `foundations/loop-to-bubble-projection-theorem.md` §9.45) then found that the resulting stationary radius lies inside the tube core: the transported trial at $R=8$ has a positive radial derivative, so the reduced family wants smaller $R$, and at those radii the transported cross-section is no longer the tube that was relaxed.

This protocol closes that gap with the geometry already registered. The cross-section is relaxed in the exact toroidal metric on a two-dimensional $(a,\phi)$ grid, at fixed cross-section population and fixed loop radius, so that the curvature-induced profile relaxation, the outward migration of the carrier into the wide side of the torus, and the winding term are all evaluated on the same functional. It asks one question:

> With the cross-section relaxed in the exact toroidal geometry, does the charged wound carrier loop have an interior stationary radius with positive radius curvature, a geometrically admissible cross-section, and a mass below the dilute charged threshold?

The scope is the conditional scalar sector. The carrier is neutral under $SU(2)_Q$, the global $U(1)$ charge and its phase winding are not mapped to a Wilson-loop representation, and no map identifies the carrier with a gauge field. The result is a statement about one functional, its schedule, and its grids.

## 2. Registered functional, charge reduction, and the exact torus energy

Coefficients are those of the registered matter-formation functional, unchanged:

$$a=\tfrac{1}{16},\quad c_\psi=\tfrac18,\quad u_\rho=4,\quad u_C=1,\quad K_{Cx}=1,\quad B=e_C+\tfrac{1}{4a}=\tfrac{19}{4},\quad h_C=2.9598260763447164 .$$

$$\Omega_\infty=\sqrt{B/a}=8.717797887081348 .$$

The three-dimensional measure in adapted coordinates around a circle of radius $R$ is $dV=R\,a\,(1+\kappa a\cos\phi)\,da\,d\phi\,ds$ with $\kappa=1/R$, so the cross-section metric factor is

$$g(a,\phi)=1+\frac{a}{R}\cos\phi .$$

The exact discrete torus functional is the registered one (`TorusSection` of the geometry module):

$$E_{\rm tor}=\sum_{\rm cells} V_C\Big[\tfrac{u_\rho}{4}(f^2-1)^2+(B-h_C+h_Cf^2)c^2+\tfrac{u_C}{2}c^4+\tfrac{K_{Cx}}{2}\frac{w^2}{R^2}\frac{c^2}{g^2}\Big]+\tfrac12\sum_{\rm faces}F_a(\Delta f)^2+\tfrac{K_{Cx}}{2}\sum_{\rm faces}F_a(\Delta c)^2+\tfrac12\sum_{\rm faces}F_\phi(\delta_\phi f)^2+\tfrac{K_{Cx}}{2}\sum_{\rm faces}F_\phi(\delta_\phi c)^2,$$

with $V_C=a\,g\,da\,d\phi$ the cross-section cell measure, $F_a$ the radial face area, $F_\phi$ the azimuthal face area, and the boundary values $f=1$, $c=0$ on the outer radial face.

The cross-section population is

$$n=\sum_{\rm cells}V_C\,c^2=\int a\,g\,da\,d\phi\;c^2 ,$$

so the total carrier norm is $N=2\pi R\,n$, and the temporal Noether charge $Q$ contributes the registered term $Q^2/(4aN)$. The reported mass is therefore

$$M(R,n;Q)=2\pi R\,E_{\rm tor}(R,n)+\frac{Q^2}{8\pi a R\,n}.$$

$E_{\rm tor}$ is the cross-section energy per unit length, which is what `TorusSection.energy`
returns, so $2\pi R\,E_{\rm tor}$ is the loop's total energy.

The dilute charged threshold is $\Omega_\infty|Q|$, and the binding margin is $\Omega_\infty|Q|-M$.

Two identities of the registered functional are used as consistency anchors rather than assumptions:

* for a $\phi$-independent profile, $\sum_\phi V_C$ reproduces the flat measure $2\pi a\,da$ exactly and $\sum_\phi F_a$ reproduces the flat radial face exactly, so the static and radial-gradient energy of such a profile equals $2\pi R$ times its flat energy at every $R$;
* the winding term is the only curvature-dependent term in the cross-section energy, and the reduced transported model

$$M^{\rm red}(R,n;Q)=2\pi R\,E_\perp(n)+\frac{\pi K_{Cx}w^2n\eta}{R}+\frac{Q^2}{8\pi aRn}$$

with $\eta$ the measure-weighted mean of $g^{-2}$ is the value of $E_{\rm tor}$ at the transported flat profile.

## 3. Procedure

### 3.1 Grids, solver, and convergence

Every relaxation minimizes $E_{\rm tor}$ over $(f,c)$ at fixed population $n$ and fixed $R$, with $w=1$ unless stated. The stationarity system is the exact discrete variational system of the geometry module: the gradient $(R_f,R_c,n-N)$ and its Jacobian, with the Lagrange multiplier $\lambda$ for the population constraint carried as the last unknown. The solver minimizes the energy over the constraint with projected L-BFGS-B, re-enforcing the population exactly at every evaluation, and then polishes the bordered stationarity system with damped Newton steps under a residual-norm merit and a sparse LU factorization of the Jacobian, escalating the Levenberg shift when a step is rejected. A solve is converged when $\max|{\rm residual}|\le 10^{-9}$ within 600 iterations.

The domain is the cross-section disk that lies inside the torus: $a_{\max}=0.9R$ for every scan radius, so $g\ge 0.1$ on the whole grid and no cell carries zero measure. The scan grid is $N_a=200$ radial cells and $N_\phi=32$ azimuthal cells. Radii are visited from the smallest curvature to the largest, each warm-started from the previous radius at the same density and each density from the previous density at the same radius. At every radius the carried profile competes with lifted copies of the registered flat profile placed at sampled polar positions $(a_0,\varphi_0)$ with $a_0\in\{0,0.2,0.35,0.5,0.65\}\,a_{\max}$ and $\varphi_0\in\{\pi,\pi/2,0\}$, and the lowest-energy candidate starts the relaxation, because the exact toroidal metric lets the carrier leave the axis.

At most 8 of the scheduled solves may fail to converge. No failed solve may be a per-radius argmin row, a refinement row, or a stored profile.

### 3.2 Validation stage

Three declared configurations tie the torus solver to the registered flat physics. They are not part of the gap scan.

* **V1 (flat limit, untwisted).** $R=64$, $w=0$, $n=\pi$, grid $(N_a,a_{\max},N_\phi)=(300,8.0,32)$. Requirement: $|E_{\rm tor}-E_\perp(\pi)|/E_\perp(\pi)\le 10^{-2}$, with $E_\perp(\pi)$ computed by the registered `Tube` class at its registered resolution $(M,r_{\max})=(200,8.0)$; both sides are per unit length.
* **V2 (flat limit, twisted).** $R=64$, $w=1$, $n=\pi$, same grid. Requirement: $|E_{\rm tor}-E_\perp(\pi)|/E_\perp(\pi)\le 10^{-2}$; the winding contribution per unit length at $R=64$ is reported.
* **V3 (transported feasibility).** The scan row $(R,n)=(8.0,5.0)$, $w=1$. Requirement: $2\pi R\,E_{\rm tor}\le M^{\rm red}(8,5;0)\,(1+2\times10^{-3})$ at $R=8$, with $E_\perp(5)=22.174477188390973$ and $\eta=1.0118788464248585$ taken from the frozen wound-loop receipt. The relative deficit against the transported value is reported.

### 3.3 Gap scan

Radii: $R\in\{5.0,5.5,6.0,6.5,7.0,7.5,8.0,9.0,10.0,12.0,16.0\}$.

Cross-section populations: $n\in\{2,3,4,5,6,8,10,12,16,20,24,32\}$.

Charges: $Q\in\{64,128,256\}$, winding $w=1$.

Every $(R,n)$ row records the energy, population, multiplier, residual, iteration count, the $99.9\%$ containment radius $a_{99}$, the minimum metric factor over the support, and the outermost-decile population fraction.

For each $R$, the mass is minimized over $n$ at each $Q$, giving $M^*(R;Q)$ and its argmin density. A radius is an interior argmin when $M^*$ is below both schedule neighbours.

### 3.4 Refinement and the radius curvature

For each $Q$, the coarse bracket is the pair of schedule neighbours of the coarse argmin. The refined radii are $R_{\rm argmin}+k\,\Delta R$ with $\Delta R=0.25$ and $k\in\{-4,\dots,4\}$, clipped to the bracket, evaluated on the same density schedule and grid. The refined argmin is the minimum of that set. The reported curvature is the parabola coefficient $c_2$ of the quadratic fit through the refined argmin and its two refined neighbours, $M(R)\approx M^*+\tfrac12c_2(R-R^*)^2$, together with the discrete second difference at the same three points.

### 3.5 Geometric admissibility

At the refined argmin the cross-section must satisfy $a_{99}\le0.85\,R^*$, and the outermost-decile population fraction must not exceed $10^{-3}$.

### 3.6 Constrained transverse spectrum

At the refined argmin $(R^*,n^*)$ of each $Q$, the exact Hessian of $E_{\rm tor}$ at the converged multiplier is restricted to the tangent space of the population constraint, with the registered kinetic measure ${\rm diag}(c_\psi V_C,\,2aV_C)$, and the lowest eight generalized eigenvalues are computed. The spectrum grid is $(N_a,N_\phi)=(100,16)$ with $a_{\max}=0.9R^*$, relaxed to the same convergence gate. Reported: the lowest eight eigenvalues, the minimum eigenvalue, and the dominant azimuthal harmonic of the three lowest modes.

The global phase mode is absent from the real-amplitude Hessian by construction. The radius direction is not contained in the spectrum; it is measured by the curvature of §3.4.

### 3.7 Winding-off control scan

The same radius and density schedules, the same grid, and $w=0$ are relaxed in full, and $M^*(R;256)$ is formed. The scan is reported as the control that isolates the winding's contribution to the radius selection; its stationary radius, if any, is compared with the $w=1$ value.

## 4. Controls, tolerances, and independent reconstruction

* **C1 grid resolution.** The row $(R,n)=(7.0,5.0)$ and the refined argmin row of each $Q$ are repeated at $(N_a,N_\phi)=(400,64)$. Requirement: relative energy difference $\le5\times10^{-4}$.
* **C2 spectrum resolution.** The spectrum at the refined argmin of $Q=256$ is repeated at $(N_a,N_\phi)=(150,24)$. Requirement: the minimum eigenvalue keeps its sign and $|\Delta\lambda|\le0.05\max(1,|\lambda|)$.
* **C3 mutation control.** The stored-profile reconstruction is required to fail when a stored energy is perturbed by $10^{-6}$ relative, and to pass unperturbed.
* **C4 winding sign flip.** The spectrum at the refined argmin of $Q=256$ is recomputed with the winding term's sign reversed. Requirement: the minimum eigenvalue decreases by more than $10^{-6}$ and becomes negative.
* **C5 winding-off difference.** Either the $w=0$ scan has no interior stationary radius, or its stationary radius differs from the $w=1$ value by more than $\Delta R=0.25$.
* **C6 schedule interiority.** The refined argmin radius is strictly interior to the refined set, and the argmin density at the refined argmin radius is strictly interior to the density schedule. Violations select the declared boundary branches of §5 rather than a failure.

The primary receipt contains all identities, energies, populations, multipliers, residuals, iteration counts, support radii, metric factors, spectral eigenvalues, checks, and classifications, together with the flattened $(f,c)$ arrays of every per-radius argmin row and of the refined argmin rows. It contains no wall-clock value. Its `content_sha256` is the SHA-256 of the sorted compact JSON body with that field removed.

The independent program `computations/verify_matter_formation_thick_torus_gap.py` must not import the primary program or the geometry module. From the primary receipt and the declared grid data it independently reconstructs, with its own quadrature: the energy, population, stationarity residual, containment radius, and metric factor of every stored profile, agreeing to $5\times10^{-9}$ relative or absolute, whichever is looser; the population constraint to $10^{-9}$; the mass curve, the refined stationary radius to $0.05$, and the curvature to $5\times10^{-2}$ relative; the threshold and margins from its own arithmetic; and the classification from its own numbers. It independently solves the constrained relaxation at $(R,n)\in\{(6.5,5.0),(8.0,5.0),(10.0,8.0)\}$ with its own implementation of the same discrete functional, requiring agreement with the primary energy to $2\times10^{-3}$ relative, its own stationarity residual $\le10^{-8}$, and its own constraint satisfied to $10^{-9}$. It also verifies the source identities against the frozen snapshot files, repeats the mutation control of C3, and states which checks it could not perform.

## 5. Decision rule

1. A missing row, a nonfinite value, a source mismatch, a profile residual above the gate, more than 8 failed solves, a stored profile that is not an argmin or refinement row, a resolution or validation failure, or an independent reconstruction failure yields **INCONCLUSIVE**.
2. If no $Q$ has an interior radius argmin: **NO_INTERIOR_STATIONARY_RADIUS_IN_SCHEDULE**.
3. If any $Q$'s coarse argmin is a schedule endpoint: **RADIUS_SCHEDULE_BOUNDARY_LIMITED**.
4. If any $Q$'s argmin density at the refined argmin radius is a density-schedule endpoint: **DENSITY_SCHEDULE_BOUNDARY_LIMITED**.
5. If $M^*(R^*;256)\ge\Omega_\infty\,256$: **THICK_TORUS_LOOP_UNBOUND_IN_SCHEDULE**.
6. If the geometric admissibility of §3.5 fails: **THICK_TORUS_STATIONARY_RADIUS_INSIDE_CORE_OVERLAP**.
7. If the radius curvature is non-positive or the minimum constrained eigenvalue is non-positive: **THICK_TORUS_MARGINALLY_UNSTABLE_STATIONARY_RADIUS**.
8. Otherwise: **SUPPORTS_CONDITIONAL_THICK_TORUS_GAP_MECHANISM**.

The branch records the charge that triggered it. Every branch retains `yang_mills_identification=UNRESOLVED`, `continuum_gauge_construction=UNRESOLVED`, `charge_quantization=UNRESOLVED`, and `clay_verdict=null`.

The claim carried by branch 8 is: for each scheduled charge, the cross-section relaxed in the exact toroidal metric has an interior stationary radius with positive radius curvature and a positive constrained spectrum, and the mass there is below the dilute charged threshold by the reported margin.

## 6. Evidence commands

Run from `CassiTheory`:

```
python computations/matter_formation_thick_torus_gap.py \
    --output runs/20260921_matter_formation_thick_torus_gap/primary.json
python computations/verify_matter_formation_thick_torus_gap.py \
    --input runs/20260921_matter_formation_thick_torus_gap/primary.json \
    --output runs/20260921_matter_formation_thick_torus_gap/independent.json
```

The primary freezes the protocol, the geometry module, the primary program, and the independent program into a `.inputs.json` manifest and a `.sources` snapshot directory beside the receipt, and refuses to overwrite an existing output.

## 7. Retained boundaries

The calculation is a finite-grid variational relaxation of one registered functional. It does not establish continuum existence, nonlinear stability in time, a gauge-field identification, or a physical value of the mass gap. It measures whether the scalar carrier sector, relaxed in its own curvature geometry, closes its loop scale on its own.
