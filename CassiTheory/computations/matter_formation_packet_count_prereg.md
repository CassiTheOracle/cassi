# Axisymmetric One-to-Three Packet Collision Probe

## Status: Preregistered conditional calculation—September 2026

## Abstract

This calculation tests the first three packet counts in one fixed
axisymmetric collision family. It asks whether a pair or a triple of
initially separated carrier packets can leave a persistent localized remnant
when the total signed charge, packet width, carrier magnitude, coupling,
domain, grid ladder, final time, and persistence rule are fixed. The
axisymmetric representation treats a nonzero radial centre as a toroidal ring;
the triple arm is therefore a three-ring meridional preparation, not a claim
about three point packets in unrestricted three-dimensional space.

The schedule does not assume that collision implies capture. A candidate forms
only when the late core retains charge, remains compact, satisfies the local
binding gate, has a bounded shell-energy fraction, and is stable under the
declared resolution and independent-method comparisons. A positive result
would identify a minimum packet count only within this preparation family. A
negative result leaves higher counts and other three-dimensional geometries
open.

## 1. Scope and lineage

The execution class is `packet_count_probe`. The scientific output path is
`runs/20260912_matter_formation_packet_count`. The primary runner creates it
exclusively and snapshots this protocol, its declarative specification, both
runner/verifier sources, and every imported numerical source used by the two
implementations. The verifier writes `verification.json` and a sibling
independent-state archive. Failed or partial execution remains preserved.

The intervention is packet count. The tested candidate counts are $N=2$ and
$N=3$. The $N=1$ arm is a noninteracting control. The schedule does not use
an earlier packet receipt as numerical evidence; the pair is rebuilt under
this protocol so the count comparison has one source-bound preparation
contract.

## 2. Fixed action

Write $z=x+iy$ and evolve $(f-1,x,y)$ with exterior Dirichlet deviations
zero. The dimensionless energy and signed charge are

$$
E=\int\left[\frac{c_\Psi}{2}\dot f^2+a|\dot z|^2+\frac12|\nabla f|^2+\frac{k_{Cx}}2|\nabla z|^2+V(f,|z|)\right]d^3x,
\qquad
Q=-2a\int\operatorname{Im}(z^*\dot z)d^3x,
$$

$$
V=\frac{u_\rho}{4}(f^2-1)^2+(B-h_C+h_Cf^2)|z|^2+\frac{u_C}{2}|z|^4.
$$

The fixed coefficients are

$$
a=\frac1{16},\quad c_\Psi=\frac18,\quad u_\rho=4,
\quad u_C=1,\quad k_{Cx}=1,
\quad h_C=2.9598260763447164,\quad B=4.75.
$$

The exterior frequency and characteristic speed are

$$
\Omega_\infty=\sqrt{B/a},\qquad v_* = \sqrt{k_{Cx}/(2a)}=\sqrt8.
$$

## 3. Frozen preparation contract

The total signed charge is $Q=16$, the Gaussian width is $w=4$, the
reference radius is $R_0=20$, the carrier magnitude is $|k|=1$, and all packet
relative phases are zero. The moving-packet frequency is

$$
\omega=\sqrt{\Omega_\infty^2+8k^2},
$$

while the centred one-packet control uses $\omega=\Omega_\infty$ and zero
spatial phase gradient. The packet centres use meridional coordinates
$(r,\zeta)$:

- $N=1$: $(0,0)$;
- $N=2$: $(0,-R_0)$ and $(0,+R_0)$;
- $N=3$: $(R_0,0)$,
  $(R_0/2,+\sqrt3R_0/2)$, and
  $(R_0/2,-\sqrt3R_0/2)$.

For a nonzero centre $c_j=(r_j,\zeta_j)$, the inward unit direction is
$d_j=-c_j/R_0$. The packet phase is

$$
\phi_j=k\left[d_{j,r}(r-r_j)+d_{j,\zeta}(\zeta-\zeta_j)\right]
$$

for inward arms. The outward control reverses every $d_j$. This makes all
three triple centres point toward the origin at the initial instant. The
radial centre is interpreted according to the axisymmetric volume element
$2\pi r\,dr\,d\zeta$: it represents a ring, so the triple is a declared
three-ring meridional collision.

Each Gaussian envelope is

$$
g_j(r,\zeta)=\exp\left[-\frac{(r-r_j)^2+(\zeta-\zeta_j)^2}{2w^2}\right].
$$

Before coherent superposition, its amplitude is weighted so that each packet
has the same isolated $L^2$ charge share. If
$I_j=\int g_j^2d^3x$, use the raw weight
$\sqrt{(1/N)/I_j}$. The complete complex superposition is then normalized
once so that its full signed charge, including overlap terms, is exactly
$Q=16$ on the actual grid. The receipt records isolated contributions,
reconstructed fractions, the full charge, all pairwise envelope overlaps, and
the initial origin-core fraction. Equal isolated shares must reconstruct to
$1/N$ within $10^{-12}$.

The arms are:

| Arm | Count | Coupling | Phase preparation | Role |
|---|---:|---:|---|---|
| `single_center` | 1 | $h_C$ | zero gradient | noninteracting control |
| `pair_inward` | 2 | $h_C$ | inward | candidate |
| `pair_uncoupled` | 2 | $0$ | inward | coupling control |
| `triple_inward` | 3 | $h_C$ | inward | candidate |
| `triple_uncoupled` | 3 | $0$ | inward | coupling control |
| `triple_outward` | 3 | $h_C$ | outward | direction control |

A candidate is preparation-eligible only if every pairwise normalized envelope
overlap is at most $0.01$, the initial origin-centred core charge fraction is
at most $0.10$, and the initial energy satisfies
$E\ge\Omega_\infty|Q|$. The actual discretized values are used on every
primary grid.

## 4. Evolution and observables

Use the fourth-order Yoshida-composed velocity-Verlet primary evolution and a
separately assembled classical RK4 independent evolution. The grids are

```json
{
  "G0": [192, 0.5, 0.015625],
  "G1": [192, 0.25, 0.015625],
  "T1": [192, 0.5, 0.0078125]
}
```

The run ends at $T=48$, samples every $0.5$, and archives fields and
velocities at $t=0,32,40,48$. The stable comparison observables are
$\{E,Q,f_{\mathrm{core}},R_{\mathrm{core}},E_{\mathrm{core}},f_{\mathrm{shell}}\}$.
Binding ratio is evaluated in the formation predicate but is not used as a
resolution-equivalence observable when the retained core gate is inactive.

Let $f_{\mathrm{core,min}}$ be the minimum signed origin-core fraction over
$32\le t\le48$. Persistence requires

1. $f_{\mathrm{core,min}}\ge0.25$;
2. maximum binding ratio below $0.99$;
3. maximum core RMS radius at most $6$;
4. late core-fraction variation at most $0.10$;
5. maximum interface-shell energy fraction at most $0.05$.

If the retained-core gate is inactive, the arm is nonpersistent and binding
ratio is excluded from equivalence comparisons. A candidate `formation` flag
also requires numerical qualification, preparation eligibility, and the
coupled inward role.

## 5. Decision tree and stopping rule

The primary and independent records must pass source identity, preparation
metadata, full charge normalization, archive reconstruction, conservation,
local balance, boundary, stable-observable comparisons, and the independent
method comparisons. Any missing, malformed, nonfinite, or failed prerequisite
returns `INCONCLUSIVE` and preserves all evidence.

The packet-count minimum is established only when all prerequisites pass and
one of these conditions holds:

- the pair arm forms across all three primary grids while the noninteracting
  control is nonpersistent, giving `minimum_packet_count=2`; or
- the pair arm is nonpersistent across all three primary grids, the triple arm
  forms across all three primary grids, and the noninteracting control is
  nonpersistent, giving `minimum_packet_count=3`.

If neither candidate forms, the verdict is
`DOES NOT EMERGE in the specified one-to-three packet schedule` and the packet
count minimum remains unestablished. The same applies when the prerequisites
pass but the tested geometry does not supply a formation arm. No result in
this schedule establishes a universal packet-count minimum, unrestricted
three-dimensional point-packet dynamics, gravitational capture, a physical
length calibration, quantum creation, or complete matter formation.

The run does not change the count ladder, geometry, width, charge, phase
schedule, coupling, grid, tolerance, or final time after execution begins.

## References

- `computations/matter_formation_wave_capture.py`—supplied charged-wave action, finite-volume operator, diagnostics, and primary evolution primitives.
- `computations/verify_matter_formation_wave_capture.py`—separately assembled finite-volume operator, RK4 evolution, archive validation, and reconstruction controls.
- `computations/matter_formation_neutral_packets.py`—axisymmetric cylindrical grid and Yoshida coefficients.
- `computations/matter_formation_radial_cloud.py`—supplied action coefficients and exterior frequency.
- `foundations/matter-completion-boundary.md`—conditional stationary and formation boundary.
- `foundations/dimensionful-cascade.md`—conditional scale-coordinate map; no physical packet length is assigned by this calculation.
