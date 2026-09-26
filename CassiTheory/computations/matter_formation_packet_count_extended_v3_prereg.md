# Axisymmetric Four-to-Six Packet Formation Extension — v3

## Status: Preregistered—September 12, 2026

## Purpose

This successor tests the same four-to-six incoming-packet formation question as
v2, but repairs a declared preparation failure before execution. The v2 run
used $R_0=20$ with width $w=4$: its measured maximum pairwise overlaps were
$0.0455034889$ for $N=5$ and $0.1486767661$ for $N=6$, above the frozen
$0.01$ eligibility limit. The v2 verifier therefore returned `numeric_pass=false`
with `preparation_contract.overlap_metadata=false`. Those rows are
`INCONCLUSIVE`, not a null, and are not reused as evidence.

This v3 changes only the declared preparation radius to $R_0=32$ so the same
semicircle-spaced ring family is initially separated. It does not change the
action, charge, width, phase, momentum convention, coupling, grid, evolution,
persistence thresholds, or decision semantics. No v2 output is used as a
scientific result.

The absent historical lower primary receipt remains an explicit limitation.
The lower one-to-three receipts are diagnostic context only; this run MUST set
`minimum_packet_count=null` and `packet_count_minimum_established=false`.

No damping, absorber, trap, clamping, daughter insertion, phenomenological
radiation term, or post-processing energy removal is permitted. Every receipt
retains `complete_physical_matter_formation=false` and
`gravitational_capture_established=false`.

## 1. Fixed preparation

Use the one-to-three protocol's action and coefficients:

$$
a=1/16,\quad c_\Psi=1/8,\quad u_\rho=4,\quad u_C=k_{Cx}=1,
\quad h_C=2.9598260763447164,\quad B=4.75,
$$

with total signed charge $Q=16$, Gaussian width $w=4$, reference radius
$R_0=32$, carrier magnitude $|k|=1$, zero relative phase, and
$\omega=\sqrt{\Omega_\infty^2+8k^2}$. Normalize the coherent sum exactly once
on each grid to $Q=16$ and give each isolated packet equal charge share.

For $N=4,5,6$ use

$$
\theta_j=-\frac\pi2+\frac{j\pi}{N-1},\qquad
c_j=(R_0|\cos\theta_j|,R_0\sin\theta_j),\qquad
 d_j=-c_j/R_0.
$$

The inward phase uses $d_j$; the outward control reverses it. The seven arms
are `n4_inward`, `n5_inward`, `n6_inward`, `n4_uncoupled`, `n5_uncoupled`,
`n6_uncoupled`, and `n6_outward`, with coupling $h_C$ for coupled arms and
zero for uncoupled arms. Only the three inward coupled arms are candidates.

Every arm must satisfy measured pairwise overlap at most $0.01`, initial
origin-core fraction at most $0.10$, finite equal shares, and
$E\ge\Omega_\infty|Q|$. The verifier recomputes these conditions; no arm is
discarded or relabeled.

## 2. Fixed evolution

Use primary Yoshida-composed velocity Verlet and independently assembled
classical RK4, both using the existing finite-volume scalar action. The schedule
is:

| Grid | Radius | Spacing | Time step |
|---|---:|---:|---:|
| G0 | 192 | 0.5 | 1/64 |
| G1 | 192 | 0.25 | 1/64 |
| T1 | 192 | 0.5 | 1/128 |

Run every arm to $T=48$, sample every $0.5$, and retain fields and velocities at
$0,32,40,48$. Compare late means for $E,Q,f_{\rm core},R_{\rm core},
E_{\rm core},f_{\rm shell}$. Persistence requires retained core fraction at
least $0.25$, binding ratio below $0.99$ when active, core RMS at most $6$,
late core-fraction variation at most $0.10$, and shell-energy fraction at most
$0.05$, plus all conservation, balance, boundary, resolution, and independent
method gates.

## 3. Decision

Any failed source, preparation, raw-state, conservation, comparison, or
independent-method gate returns `INCONCLUSIVE`. If all gates pass and a
candidate forms on all three primary grids and in independent RK4, return
`EMERGES—conditional N=<count> ring-family formation in the R0=32 extension`,
using the smallest newly forming count. If all three candidates are nonforming,
return `DOES NOT EMERGE in the specified R0=32 four-to-six ring-family
extension`.

This result is a conditional classical localized-remnant test only. It does not
establish a global packet minimum, vacuum creation, quantum particle
production, a parent-to-daughter split, a physical particle species,
spin/statistics, gravitational capture, a physical size map, or complete
physical matter formation. Stop after this schedule.

## 4. Source and provenance contract

The primary archives this protocol, the v3 specification and both v3 runners,
the v2 runner used only as a codebase component, the lower packet-count
sources, and the shared dynamics sources. The independent verifier checks all
archived/live hashes, strict primary rows, mutation and hash rejection controls,
independent RK4 state archives, conservation, primary comparisons, and the v3
preparation contract. It records lower-lineage failure as diagnostic context,
never as a formation gate.
