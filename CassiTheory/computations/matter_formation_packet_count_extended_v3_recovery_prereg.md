# R0=32 Four-to-Six Packet Extension — Provenance Recovery

## Status: Preregistered recovery amendment—September 12, 2026

The v3 primary campaign used the admissible $R_0=32$, width-four, semicircle
ring schedule and passed its numerical gates, but its source archive omitted the
v2 independent-verifier source even though the v3 verifier required that source
as a codebase component. The v3 verifier therefore correctly returned
`INCONCLUSIVE` with `v2_source_archive_checks=[true,false]`. This recovery does
not weaken that check and does not use the v3 receipt as scientific evidence.
It reruns the unchanged v3 numerical schedule with the complete source archive.

The fixed action is $a=1/16$, $c_\Psi=1/8$, $u_\rho=4$,
$u_C=k_{Cx}=1$, $h_C=2.9598260763447164$, $B=4.75$; $Q=16$, width $w=4$,
$R_0=32$, $|k|=1$, zero relative phase, and the same one-time coherent
normalization. For $N=4,5,6$ use

$$
\theta_j=-\frac\pi2+\frac{j\pi}{N-1},\qquad
c_j=(32|\cos\theta_j|,32\sin\theta_j),\qquad d_j=-c_j/32.
$$

Run the seven v3 arms (`n4_inward`, `n5_inward`, `n6_inward`, their three
uncoupled controls, and `n6_outward`) on exactly

```json
{"G0":[192,0.5,0.015625],"G1":[192,0.25,0.015625],"T1":[192,0.5,0.0078125]}
```

to $T=48$, with samples every $0.5$ and full states at $0,32,40,48$.
Eligibility, persistence, conservation, resolution, and independent RK4
thresholds are exactly those in `matter_formation_packet_count_extended_v3_prereg.md`.
No damping, absorber, trap, clamping, daughter insertion, phenomenological
radiation term, or post-processing energy removal is allowed.

Any source, preparation, state, conservation, comparison, or independent-method
failure returns `INCONCLUSIVE`. If all gates pass and a candidate forms on all
three primary grids and in RK4, return the conditional `EMERGES` result with
its smallest new count. If all candidates are nonforming, return the conditional
`DOES NOT EMERGE` result. The lower historical lineage remains diagnostic only;
`minimum_packet_count` is always null and no outcome establishes complete
physical matter formation, vacuum creation, particle identity, or gravitational
capture.

The primary must archive and bind these live sources: this recovery protocol,
`matter_formation_packet_count_extended_v3_spec.py`, both recovery runners,
`matter_formation_packet_count_extended_v3.py`,
`verify_matter_formation_packet_count_extended_v3.py`,
`matter_formation_packet_count_extended_v2.py`,
`verify_matter_formation_packet_count_extended_v2.py`, the lower packet-count
primary/spec/prereg/verifier, and the shared neutral-packet, radial-cloud,
wave-capture, and independent-wave sources. The verifier must require every
archived/live identity and must retain the v3 omission as the reason for the
separate failed receipt.
