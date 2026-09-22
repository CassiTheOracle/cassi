# Wound Carrier Loop as a Yang–Mills Gap Mechanism: Fixed Reduced Calculation

## Status: Pre-registered—September 2026

## 1. Question and scope

This calculation applies the corrected transverse-tube functional in
`computations/matter_formation_tube_geometry.py` to the closed-loop mechanism
needed by the Yang–Mills mass-gap program. It asks four fixed questions:

1. When does the registered carrier tube bind relative to the dilute charged
   continuum?
2. Do nonzero temporal charge and nonzero spatial phase winding together
   generate a finite loop length?
3. Does the preferred loop lie inside the geometric domain in which the
   straight-tube profile can be transported around a circle?
4. Are the non-symmetry transverse modes of that tube locally gapped?

The result is a calculation in the registered real-mediator/complex-carrier
scalar sector. The carrier is neutral under the conditional $SU(2)_Q$ gauge
field, its global $U(1)$ charge has no selected physical quantum, and no map
identifies its phase winding with a Wilson-loop representation. The calculation
therefore cannot establish a Yang–Mills vacuum, a continuum gauge theory, a
regulator-independent mass, or the Clay mass-gap statement. Its applicable
outcome is a candidate scale-generation mechanism and a precise boundary on
what remains to connect it to pure Yang–Mills.

The completed tube-geometry run in
`runs/20260921_matter_formation_tube_geometry/` fixed the coefficient correction,
radial-grid feasibility and geometric support convention before this protocol.
It contains no minimization of the wound charged-loop mass defined below.

## 2. Frozen functional and exact reduction

Use

$$
\begin{aligned}
E_\perp(n)=\inf_{\int_{\mathbb R^2}c^2=n}\int_{\mathbb R^2}\Big[
&\frac12|\nabla f|^2+\frac{k_{Cx}}2|\nabla c|^2
+\frac{u_\rho}{4}(f^2-1)^2\\
&+(B-h_C+h_Cf^2)c^2+\frac{u_C}{2}c^4\Big]d^2x_\perp,
\end{aligned}
$$

with

$$
a=\frac1{16},\quad c_\Psi=\frac18,\quad
k_{Cx}=u_C=1,\quad u_\rho=4,\quad B=\frac{19}{4},\quad
h_C=2.9598260763447164.
$$

Write $e(n)=E_\perp(n)/n$ and
$\Omega_\infty=\sqrt{B/a}$. The weak-field reduction gives

$$
\beta=\frac{2h_C^2}{u_\rho}-u_C,
\qquad
n_T=\frac{k_{Cx}N_T}{2\beta},
\qquad N_T=11.700896,
$$

as the infinite-plane Townes onset. A charged straight tube exists exactly
when $e(n)<B$.

Bend a profile into a circular loop of length $L=2\pi R$. Let
$N=Ln$ be its integrated carrier norm, $Q$ its signed temporal Noether charge,
and $w\in\mathbb Z$ its longitudinal phase winding. The thin-loop reduced mass
is

$$
\boxed{
M_{Q,w}(L,n)=L E_\perp(n)
+\frac{2\pi^2k_{Cx}w^2n}{L}
+\frac{Q^2}{4aLn}.}
$$

Equivalently,

$$
M_{Q,w}(N,n)=Ne(n)
+\frac{2\pi^2k_{Cx}w^2n^2+Q^2/(4a)}{N}.
$$

At fixed $n$ the exact minimizing norm, length and mass are

$$
\begin{aligned}
A_{Q,w}(n)&=\frac{Q^2}{4a}+2\pi^2k_{Cx}w^2n^2,\\
N_*(n)&=\sqrt{\frac{A_{Q,w}(n)}{e(n)}},\qquad
L_*(n)=\frac{N_*(n)}n,\\
M_*(n)&=2\sqrt{e(n)A_{Q,w}(n)}.
\end{aligned}
$$

For $w\ne0$, put $q=|Q/w|$. A wound loop lies below the dilute charged
threshold $\Omega_\infty|Q|$ at density $n$ exactly when

$$
q^2>
\frac{8\pi^2a k_{Cx}e(n)n^2}{B-e(n)}.
$$

The schedule-resolved binding onset is therefore the minimum of the right-hand
square root over rows with $e(n)<B$. A finite stationary density satisfies

$$
e'(n)A_{Q,w}(n)+4\pi^2k_{Cx}w^2ne(n)=0.
$$

Both nonzero quantities matter. With $Q=0$, the mass tends to zero as the
carrier dilutes. With $w=0$, temporal charge can bind the carrier but supplies
no finite loop radius; the reduced family collapses toward increasing density.

## 3. Fixed numerical schedule

### 3.1 Straight profiles

Use the cell-centred finite-volume equations of
`computations/matter_formation_tube_geometry.py`, with exact discrete
variation of the displayed functional, $f(R_{\max})=1$, $c(R_{\max})=0$,
$0\le f\le1$ and $c\ge0$.

The primary sweep is

$$
(M,R_{\max})=(200,8),
$$

at the fixed densities

$$
\begin{gathered}
1.75,\ 1.875,\ 2.0,\ 2.25,\ 2.5,\ 2.75,\ 3.0,\ \pi,\
3.25,\ 3.5,\ 3.75,\ 4.0,\\
4.5,\ 5.0,\ 6.0,\ 8.0,\ 12.0,\ 24.0,\ 48.0.
\end{gathered}
$$

Continue from the nearest converged row. A failed row receives one fresh-seed
retry with eight block sweeps. Require maximum stationarity residual below
$10^{-7}$.

At $n=2,4,8$, repeat on $(M,R_{\max})=(400,8)$ for a spacing comparison and
on $(M,R_{\max})=(400,16)$ for a same-spacing domain comparison. Require the
relative $e(n)$ discrepancy below $5\times10^{-4}$ in both comparisons.

Use shape-preserving cubic interpolation of the converged primary $e(n)$ rows.
Minimize separately on every adjacent interval and select the least finite
value; no extrapolation beyond the registered density schedule is allowed.
The fixed charge schedule is

$$
Q\in\{16,64,128,256\},\qquad w=1.
$$

Record the schedule-resolved $q_{\rm bind}$, each leading minimum, its
neighboring density bracket, $N_*$, $L_*$, $R_*=L_*/(2\pi)$, binding margin
$\Omega_\infty Q-M_*$, and whether the minimum touches a density endpoint.

### 3.2 Circular-geometry qualification

The validated transported-profile convention uses cross-section support
$a_\perp\le6$ and physical loop radii $R\ge8$. For each candidate record the
carrier fraction outside $a_\perp=6$. Geometry qualification requires

$$
R_*\ge8,
\qquad
\frac{\int_{a_\perp>6}c^2d^2x_\perp}{n}<10^{-4}.
$$

For $R\ge8$, independently of the leading $1/R^2$ approximation, use the exact
metric factor

$$
\eta(n,R)=
\frac{\int_0^6 2\pi r c_n(r)^2
[1-(r/R)^2]^{-1/2}dr}
{\int_0^6 2\pi r c_n(r)^2dr}.
$$

The corresponding transported-profile mass is

$$
M^{\rm tor}_{Q,w}(n,R)=2\pi R E_\perp(n)
+\frac{\pi k_{Cx}w^2n}{R}\eta(n,R)
+\frac{Q^2}{8\pi aRn}.
$$

At $Q=256,w=1$, minimize this mass over the fixed density interpolation at
$R=8$. Re-solve the profile once at the interpolated density and recompute the
mass without interpolating its profile. Record its binding margin and the
one-sided radial derivative. A positive derivative means that energy falls
toward radii below the validated transported-tube domain and therefore does
not establish a stationary thin loop.

### 3.3 Transverse spectrum

At the recomputed $Q=256,w=1,R=8$ trial density, assemble the exact discrete
Hessian of $E_\perp-\mu n$. For angular cross-section modes
$m=0,1,2,3,4$, use the registered kinetic mass density

$$
W=\operatorname{diag}(c_\Psi,2a)
$$

with the radial area measure and solve $Hv=\omega^2Wv$. Project the $m=0$
amplitude block onto the fixed-$n$ tangent space. The carrier global phase is
an exact unrepresented zero mode. The $m=1$ translation eigenvalue must be
soft relative to the first positive $m=2,3,4$ eigenvalue; every
non-symmetry mode used in a gap statement must have $\omega^2>0$.

This spectrum tests local transverse shape stability only. It does not replace
the missing loop-radius mode when the radial derivative is nonzero.

## 4. Controls and independent reconstruction

The primary receipt must include all source identities, every profile array,
energies, populations, multipliers, residuals, interpolation brackets,
loop rows, metric factors, spectral eigenvalues, checks and classifications.
It contains no wall-clock value. Its `content_sha256` is SHA-256 of the sorted
JSON body before that field is added.

The independent program must not import the primary program or the tube module.
From the stored arrays and declared grid it independently reconstructs:

1. population, energy, multiplier residual and tail fraction for every profile;
2. the Townes onset, $q_{\rm bind}$ rows, loop masses and binding margins;
3. the exact torus metric factor and fixed-$R$ trial mass;
4. the generalized transverse Hessian spectrum;
5. the complete row inventories, source/snapshot bindings and content digest.

Array-derived scalar comparisons use normalized error
$|x-y|/\max(1,|x|,|y|)<5\times10^{-9}$. Eigenvalues use $10^{-7}$ because
the symmetry mode is conditioned by a finite outer boundary. The verifier must
also show that changing one stored energy by $10^{-3}$ trips the mass
comparison and that changing one positive spectral eigenvalue's sign trips the
stability classifier.

## 5. Decision tree and stopping rule

- A missing row, nonfinite value, source mismatch, profile residual failure,
  resolution/domain failure or independent reconstruction failure gives
  **INCONCLUSIVE**.
- If no scheduled $Q$ has $M_*<\Omega_\infty Q$, record
  `NO_BOUND_WOUND_LOOP_IN_SCHEDULE`.
- If a leading bound minimum exists but violates the circular-geometry gate,
  record `BOUND_REDUCED_LOOP_OUTSIDE_THIN_DOMAIN` for that minimum.
- If the $R=8$ transported trial is bound but its radial derivative points to
  $R<8$, record `BOUND_THIN_TRIAL_NO_THIN_STATIONARY_RADIUS`.
- Only a bound interior minimum satisfying the geometry gate, with positive
  non-symmetry transverse modes and positive loop-radius curvature, may receive
  `SUPPORTS_CONDITIONAL_WOUND_LOOP_GAP_MECHANISM`.
- Every branch retains `yang_mills_identification=UNRESOLVED`,
  `continuum_gauge_construction=UNRESOLVED`,
  `charge_quantization=UNRESOLVED` and `clay_verdict=null`.

Execute this schedule once after both programs are complete. A programming
defect may be repaired only with a new output directory that preserves the
failed receipts and records the repair. Do not add densities, charges, starts,
or acceptance thresholds after opening the scientific receipt.

## 6. Evidence commands

Run from `CassiTheory`:

```text
python computations/matter_formation_wound_loop_gap.py --output runs/20260921_matter_formation_wound_loop_gap/primary.json
python computations/verify_matter_formation_wound_loop_gap.py --input runs/20260921_matter_formation_wound_loop_gap/primary.json --output runs/20260921_matter_formation_wound_loop_gap/independent.json
```

Use fresh paths. The primary freezes this protocol, the corrected tube module,
and both executable programs into an adjacent source directory before solving.
The independent receipt binds the consumed primary bytes and the same frozen
source set.
