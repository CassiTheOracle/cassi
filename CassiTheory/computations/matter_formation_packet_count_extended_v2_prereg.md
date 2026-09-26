# Axisymmetric Four-to-Six Packet Formation Extension — v2

## Status: Preregistered—September 12, 2026

## Purpose and scope

This is the successor packet intervention selected after the first-order
wave-capture spatial null. It tests whether four, five, or six initially
separated, equal-charge, inward-moving carrier packets can leave a persistent
localized remnant under the same scalar action. Each nonzero radial centre is a
toroidal ring in the axisymmetric representation. The result is scoped to this
ring family and does not establish unrestricted three-dimensional capture.

This v2 protocol exists because the archived lower packet-count primary receipt
named by the earlier report is absent. The earlier report-listed identities
were primary `697c770f64e074690d2dd8cc496745884037438197986047c1887471e7e39295`
and independent `b1786ec532b35fd45061063398ff5549f3edfc20c0db4ef80953a6558712d7ac`.
A fresh lower run under the unchanged one-to-three protocol was executed only to
restore diagnostic context. Its primary receipt is
`3233dbe3f332b875d7cd2af06cf4861274e9062a144f2d4102e81d9b12254bd2`; its
independent receipt is `b1786ec532b35fd45061063398ff5549f3edfc20c0db4ef80953a6558712d7ac`.
The primary/independent identity asymmetry means the historical lower lineage
is **not accepted** as an inherited minimum-count proof. The lower receipts are
retained as diagnostic context only. This extension can test a new formation
route, but it MUST leave `minimum_packet_count=null` and
`packet_count_minimum_established=false` regardless of its outcome.

No damping, absorber, trap, clamping, daughter insertion, phenomenological
radiation term, or post-processing energy removal is added. The only energy
transport is that of the fixed scalar action. Every receipt retains
`complete_physical_matter_formation=false` and
`gravitational_capture_established=false`.

## 1. Fixed action and packet preparation

Use exactly the coefficients, total signed charge, width, reference radius,
wave number, normalization, and phase convention in
`matter_formation_packet_count_prereg.md` §§2–4:

$$
a=1/16,\quad c_\Psi=1/8,\quad u_\rho=4,\quad u_C=k_{Cx}=1,
\quad h_C=2.9598260763447164,\quad B=4.75,
$$

with $Q=16$, $w=4$, $R_0=20$, $|k|=1$, zero relative phase, and
$\omega=\sqrt{\Omega_\infty^2+8k^2}$. Each packet receives equal isolated
$L^2$ charge share; the coherent sum is normalized exactly once to $Q=16$ on
the actual grid.

For $N\in\{4,5,6\}$, use the fixed semicircle-spaced centres

$$
\theta_j=-\frac\pi2+\frac{j\pi}{N-1},\qquad
c_j=(R_0|\cos\theta_j|,R_0\sin\theta_j),\qquad j=0,\ldots,N-1.
$$

The inward phase direction is $d_j=-c_j/R_0$; the outward control reverses
all directions. The radial coordinate is reflected at the axis, so the endpoints
$r=0$ are valid axisymmetric rings rather than negative-radius points.

The fixed arms are:

| Arm | Count | Coupling | Role |
|---|---:|---:|---|
| `n4_inward` | 4 | $h_C$ | candidate |
| `n5_inward` | 5 | $h_C$ | candidate |
| `n6_inward` | 6 | $h_C$ | candidate |
| `n4_uncoupled` | 4 | $0$ | coupling control |
| `n5_uncoupled` | 5 | $0$ | coupling control |
| `n6_uncoupled` | 6 | $0$ | coupling control |
| `n6_outward` | 6 | $h_C$ | direction control |

Preparation eligibility requires all pairwise normalized envelope overlaps at
most $0.01$, initial origin-core charge fraction at most $0.10$, finite equal
shares, and $E\ge\Omega_\infty|Q|$. Actual values are recorded and verified;
no arm is discarded because it is inconvenient.

## 2. Evolution and observables

Use the primary fourth-order Yoshida-composed velocity-Verlet evolution and the
independent classical RK4 evolution. The fixed grid/time schedule is:

| Grid | Radius | Spacing | Time step |
|---|---:|---:|---:|
| G0 | 192 | 0.5 | 1/64 |
| G1 | 192 | 0.25 | 1/64 |
| T1 | 192 | 0.5 | 1/128 |

Run every arm to $T=48$, sample diagnostics every $0.5$, and save complete
fields and velocities at $t=0,32,40,48$. Compare the late-window means for
$E,Q,f_{\rm core},R_{\rm core},E_{\rm core},f_{\rm shell}$.

A candidate is persistent only if, throughout the retained late diagnostics,
its minimum core charge fraction inside radius $8$ is at least $0.25, its
binding ratio is below $0.99 whenever the retained-core gate is active, its
core RMS is at most $6$, late core-fraction variation is at most $0.10$, and
its shell-energy fraction is at most $0.05$. A candidate with a dispersed tail
below the retained-core threshold is nonpersistent; binding comparisons are
excluded exactly as specified in the lower protocol. The predicate also requires
finite traces, charge/energy conservation, local balance, boundary control,
stable grid comparisons, and independent-method agreement.

## 3. Decision tree

The verifier must pass live/archive source identity, exact schedule metadata,
packet shares and geometry, raw state reconstruction, mutation rejection, hash
rejection, conservation, local balance, boundary, primary space/time
comparisons, and independent RK4 comparisons. Any failed prerequisite returns
`INCONCLUSIVE` for the extension.

If all prerequisites pass and at least one of `n4_inward`, `n5_inward`, or
`n6_inward` forms on all three primary grids and in the independent method, the
verdict is

`EMERGES—conditional N=<count> ring-family formation in the four-to-six extension`.

The smallest newly forming count is reported as `first_new_forming_count`, but
it is **not** a global or inherited packet-count minimum. If all three new
candidate counts are nonforming and every prerequisite passes, the verdict is
`DOES NOT EMERGE in the specified four-to-six ring-family extension`. If any
prerequisite fails, the verdict is `INCONCLUSIVE`. In every case,
`minimum_packet_count` is null because the historical lower primary lineage is
not accepted.

A positive extension result would demonstrate a conditional classical
localized-remnant route from supplied incoming packets. It would not establish
vacuum creation, quantum particle production, a daughter split from a parent
pool, a physical particle species, spin/statistics, gravitational capture, a
physical size map, or complete physical matter formation.

Stop after this schedule. Do not extend the count, alter $Q$, width, phase,
momentum, coupling, geometry, grid, final time, or thresholds.

## 4. Required source archive

The primary runner and verifier must archive and bind the live bytes of this
protocol, `matter_formation_packet_count_extended_spec.py`, both new executable
sources, the lower primary and independent packet dynamics sources, and the
shared neutral-packet, radial-cloud, and wave-capture sources. The verifier must
check both fresh lower receipts as diagnostic context and record the failed
historical-lineage inheritance check without treating it as a scientific gate.
