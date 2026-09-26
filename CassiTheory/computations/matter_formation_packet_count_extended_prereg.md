# Axisymmetric Four-to-Six Packet Collision Extension

## Status: Preregistered conditional calculation—September 2026

## Abstract

This successor calculation extends the completed one-to-three packet probe to
packet counts $N=4,5,6$ in one explicitly axisymmetric meridional preparation
family. It asks whether adding more initially separated incoming carrier packets
can leave a persistent localized remnant at the same total signed charge and
under the same scalar action. It is an incoming-packet calculation, not a
parent-pool daughter test and not a vacuum-production calculation.

The axisymmetric representation treats each nonzero radial centre as a toroidal
ring. The new geometries are therefore semicircle-spaced ring preparations, not
unrestricted three-dimensional point-packet configurations. A positive result
would establish a conditional first forming count only in the declared ring
family and only after the inherited lower-count evidence and the new rows pass
all source, archive, conservation, resolution, and independent-method checks.

No damping, absorber, trap, clamping, daughter insertion, phenomenological
radiation term, or post-processing energy removal is added. The only energy
transport is that of the fixed scalar action. Every receipt retains
`complete_physical_matter_formation=false` and
`gravitational_capture_established=false`.

## 1. Scope and lower-count lineage

The execution class is `packet_count_extension`. The primary runner creates
`runs/20260912_matter_formation_packet_count_extended` exclusively and archives
this protocol, its specification, both executable sources, and all imported
numerical sources. The independent verifier creates a fresh RK4 state archive.

The completed lower-count receipt is bound, not recomputed or silently retuned:

- primary: `runs/20260912_matter_formation_packet_count/result.json`,
  SHA-256 `697c770f64e074690d2dd8cc496745884037438197986047c1887471e7e39295`;
- independent: `runs/20260912_matter_formation_packet_count/verification.json`,
  SHA-256 `b1786ec532b35fd45061063398ff5549f3edfc20c0db4ef80953a6558712d7ac`.

The bound receipt has `numeric_pass=true`, with the $N=2$ and $N=3$ coupled
candidate rows nonpersistent and `minimum_packet_count=null`. The extension
can establish $N=4$, $5$, or $6$ only if the inherited lower rows remain bound
to these exact receipts and the first newly forming count passes every gate.
If all new counts fail, the extension leaves the minimum unestablished.

## 2. Fixed action and preparation

Use exactly the action and coefficients in
`matter_formation_packet_count_prereg.md` §§2–4:

$$
a=1/16,
\quad c_\Psi=1/8,
\quad u_\rho=4,
\quad u_C=k_{Cx}=1,
\quad h_C=2.9598260763447164,
\quad B=4.75.
$$

The total signed charge is $Q=16$, Gaussian width $w=4$, reference radius
$R_0=20$, carrier magnitude $|k|=1$, zero relative phase, and
$\omega=\sqrt{\Omega_\infty^2+8k^2}$ for every moving arm. Each isolated
packet receives equal pre-superposition $L^2$ charge share, and the complete
field is normalized exactly once on the actual grid to $Q=16$.

For count $N\in\{4,5,6\}$, set

$$
\theta_j=-\frac\pi2+\frac{j\pi}{N-1},
\qquad
c_j=(R_0|\cos\theta_j|,R_0\sin\theta_j),
\qquad j=0,\ldots,N-1.
$$

These are distinct centres in the meridional half-plane $r\ge0$ and are
semicircle-spaced. The inward direction is $d_j=-c_j/R_0$; the outward
control reverses all directions. The packet phase is the linear phase
$k[d_{j,r}(r-c_{j,r})+d_{j,\zeta}(\zeta-c_{j,\zeta})]$.

Arms are:

| Arm | Count | Coupling | Role |
|---|---:|---:|---|
| `n4_inward` | 4 | $h_C$ | candidate |
| `n5_inward` | 5 | $h_C$ | candidate |
| `n6_inward` | 6 | $h_C$ | candidate |
| `n4_uncoupled` | 4 | $0$ | coupling control |
| `n5_uncoupled` | 5 | $0$ | coupling control |
| `n6_uncoupled` | 6 | $0$ | coupling control |
| `n6_outward` | 6 | $h_C$ | direction control |

A row is preparation-eligible only when all pairwise normalized envelope
overlaps are at most $0.01$, the initial origin-core charge fraction is at most
$0.10$, and $E\ge\Omega_\infty|Q|$. The actual discretized values are
recorded and checked on every grid.

## 3. Evolution and observables

Use the primary fourth-order Yoshida-composed velocity-Verlet evolution and an
independently assembled classical RK4 evolution. Use exactly

```json
{
  "G0": [192, 0.5, 0.015625],
  "G1": [192, 0.25, 0.015625],
  "T1": [192, 0.5, 0.0078125]
}
```

Run to $T=48$, sample every $0.5$, and archive fields and velocities at
$t=0,32,40,48$. Stable resolution comparisons use

$$
\{E,Q,f_{\rm core},R_{\rm core},E_{\rm core},f_{\rm shell}\}.
$$

Binding remains a formation predicate. Let $f_{\rm core,min}$ be the minimum
signed charge fraction inside the fixed radius $8$ over $32\le t\le48$.
Persistence requires $f_{\rm core,min}\ge0.25$, maximum binding ratio below
$0.99$, maximum core RMS at most $6$, late core-fraction variation at most
$0.10$, and maximum interface-shell energy fraction at most $0.05$. If the
retained-core gate is inactive, the row is nonpersistent and binding-ratio
comparison is excluded from stable equivalence comparisons.

## 4. Decision tree and stopping rule

Both implementations must pass source identity, preparation metadata, charge
normalization, raw archive reconstruction, mutation and hash rejection controls,
conservation, local balance, boundary, stable-observable comparisons, and
independent-method comparisons. Any failed prerequisite gives `INCONCLUSIVE`.

The inherited $N=2$ and $N=3$ candidate rows are accepted only through the
source-bound lower-count receipt identities in §1. The first count in ascending
order among $4,5,6$ whose coupled inward arm forms on all three primary grids,
passes both methods, and has all lower candidate counts nonforming establishes
that conditional count. If none forms, return
`DOES NOT EMERGE in the specified four-to-six packet extension` and retain
`minimum_packet_count=null`. If any prerequisite fails, return `INCONCLUSIVE`
and do not infer a count.

Stop after this schedule. Do not extend the count, alter $Q$, width, geometry,
phase, momentum, coupling, grid, final time, or persistence thresholds. No
outcome establishes unrestricted three-dimensional capture, gravitational
capture, a physical length map, quantum creation, particle identity, or
complete physical matter formation.

## 5. Required source lineage

The runners must snapshot and bind the live bytes of:

- this protocol and `matter_formation_packet_count_extended_spec.py`;
- `matter_formation_packet_count_extended.py` and
  `verify_matter_formation_packet_count_extended.py`;
- `matter_formation_packet_count.py` and
  `verify_matter_formation_packet_count.py`;
- `matter_formation_wave_capture.py`,
  `verify_matter_formation_wave_capture.py`,
  `matter_formation_neutral_packets.py`, and
  `matter_formation_radial_cloud.py`.

The archived source bytes, live source bytes, and inherited lower-count receipt
hashes are part of the verifier's acceptance contract.
