# Incoming-Momentum Formation Probe at Fixed Total Charge 256

## Status: Preregistered conditional calculation—September 2026

## Abstract

This calculation tests whether a fixed-charge Q=256 two-packet preparation can leave a persistent localized remnant when the incoming carrier momentum is varied over a declared low-to-moderate ladder. The total signed charge, packet width, centre separation, coupling, domain, final time, grid schedule, conservation tolerances, and formation predicates are fixed before execution. The momentum ladder is $k\in\{0.25,0.5,1.0\}$ at packet centres $\zeta=\pm12$. The calculation measures only the declared axisymmetric scalar model. It does not establish three-dimensional stability, gravitational capture, physical size, quantum particle identity, spin, statistics, or a whole-bubble production mechanism.

## 1. Scope and lineage

The execution class is `q256_packet_momentum_probe`. This is a fresh Q=256 incoming-preparation calculation, not a continuation of the Q16 momentum campaign and not a reinterpretation of the completed Q256 wave-capture or spatial-convergence receipts. The preserved Q256 wave-capture result has SHA-256 `a202793ea2e6f91e8412461e723625ecaaf049819a85e0bf406ed1bfa52c92c4`; its independent verification has SHA-256 `e9afe82b8a5417905a7b03148deb6aad51599bc8a1d11870ba4c739c9b7f527e`. The preserved Q256 spatial-repair result has SHA-256 `89818a0950688db4da88aafbb38fa83638e7e86084404021d0d38f13c846e6b7`; its independent verification has SHA-256 `a420bac7d62fff8aa9071ec4e31737927f55a16c365616e5209a991c9ae6de46`.

The scientific output path is `runs/20260912_matter_formation_q256_momentum`. The primary runner creates it exclusively, snapshots this protocol, the declarative preparation specification, both runner/verifier sources, and every declared action source. The verifier writes `verification.json` and a sibling independent-state archive. A failed or partial execution remains preserved.

A positive result would establish only a conditional Q=256 remnant for one declared incoming momentum and preparation. It would not establish a global charge minimum, an optimal momentum, a minimum packet count, physical size, or gravitational capture.

## 2. Fixed action and preparation

Write $z=x+iy$ and evolve deviations $(f-1,x,y)$ with exterior Dirichlet deviations zero. The dimensionless energy and signed charge are

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

The exterior carrier frequency and characteristic speed are

$$
\Omega_\infty=\sqrt{B/a},\qquad v_* = \sqrt{k_{Cx}/(2a)}=\sqrt8.
$$

Every preparation has $f=1$ and $\dot f=0$. The `single256` control is a Gaussian of width $w=4$ centred at the origin with carrier frequency $\Omega_\infty$. Each pair is the sum of equal Gaussian envelopes of width $w=4$ centred at $\zeta=\pm12$, with inward phase gradients of magnitude $k$ and

$$
\omega(k)=\sqrt{\Omega_\infty^2+8k^2}.
$$

The `antiphase_k05` arm multiplies the left packet by $-1$. The `uncoupled_k05` control uses the $k=0.5$ pair with $h_C=0$ throughout. Every preparation is normalized once from the full single or superposed field to total signed charge $Q=256$. The nominal separated-packet charge is $Q/2=128$.

The group-speed estimate is $v_g(k)=8k/\omega(k)$; the three declared pair arms reach the origin before $t=32$ in the continuum estimate. This is a timing check, not an acceptance predicate. A pair is preparation-eligible only when its normalized envelope overlap is at most $0.01$, its origin-centred initial core charge fraction is at most $0.10$, and its initial energy satisfies $E\ge\Omega_\infty|Q|$. Eligibility is computed from the actual discretized preparation on each grid.

## 3. Frozen machine-readable schedule

The following JSON is the sole scientific schedule and decision contract.

```json
{
  "schema": "matter-formation-q256-packet-momentum-protocol-v1",
  "execution_class": "q256_packet_momentum_probe",
  "output": "runs/20260912_matter_formation_q256_momentum",
  "preparation": {
    "total_charge": 256.0,
    "nominal_packet_charge": 128.0,
    "width": 4.0,
    "center_separation": 12.0,
    "wave_numbers": [0.25, 0.5, 1.0],
    "omega_offset_squared": 8.0,
    "initial_overlap_max": 0.01,
    "initial_core_fraction_max": 0.10
  },
  "evolution": {
    "t_final": 48.0,
    "late_start": 32.0,
    "sample_dt": 0.5,
    "snapshot_times": [0.0, 32.0, 40.0, 48.0],
    "primary_method": "fourth-order Yoshida-composed velocity Verlet",
    "primary_grids": {
      "S1": [192, 0.25, 0.0078125],
      "S2": [192, 0.125, 0.00390625],
      "T1": [192, 0.25, 0.00390625]
    },
    "independent_method": "classical RK4 with separately assembled finite-volume operator",
    "independent_grid": [192, 0.25, 0.00390625]
  },
  "arms": {
    "all": ["single256", "pair_k025", "pair_k05", "pair_k10", "antiphase_k05", "uncoupled_k05"],
    "coupled_candidates": ["pair_k025", "pair_k05", "pair_k10", "antiphase_k05"],
    "comparison": ["single256", "pair_k025", "pair_k05", "pair_k10", "antiphase_k05", "uncoupled_k05"],
    "independent": ["single256", "pair_k025", "pair_k05", "pair_k10", "antiphase_k05", "uncoupled_k05"]
  },
  "comparison_observables": ["energy", "charge", "core_fraction", "core_rms", "core_energy", "shell_energy_fraction"],
  "binding_observable": "binding_ratio remains a formation predicate and is excluded from cross-resolution equivalence comparisons",
  "geometry": {
    "core_radius": 8.0,
    "cut_inner_radius": 8.0,
    "cut_outer_radius": 12.0,
    "shell_inner_radius": 8.0,
    "shell_outer_radius": 12.0,
    "outer_boundary_shell_width": 16.0
  },
  "tolerances": {
    "energy_drift": 0.0002,
    "charge_drift": 0.00002,
    "boundary_energy_fraction": 0.000001,
    "local_balance": 1e-8,
    "primary_reconstruction": 1e-8,
    "method_comparison": 0.05,
    "retained_signed_charge_fraction": 0.25,
    "binding_ratio_max": 0.99,
    "core_rms_max": 6.0,
    "late_core_variation_fraction": 0.10,
    "shell_energy_fraction": 0.05
  },
  "archive": {
    "primary_raw_states_per_row": 4,
    "independent_raw_states_per_arm": 4,
    "required_arrays": ["fields", "velocities", "r", "axial", "volume", "time"],
    "dtype": "float64",
    "sha256_required": true,
    "allow_pickle": false
  }
}
```

## 4. Observables and qualification

The primary runner evolves the axisymmetric cylindrical finite-volume system with cell volume $2\pi r\,dr\,d\zeta$. The independent verifier assembles the same action and boundary terms separately and evolves every declared arm with classical RK4.

Every primary sample records total energy, signed and absolute charge, charge centroid, origin-centred core signed and absolute charge, core RMS, mediator depletion, core energy, compact-cut energy and signed charge, cut axial momentum, binding radicand and ratio, interface-shell energy, outer-boundary energy, and signed local energy and charge derivatives and face fluxes.

The core is fixed at $r^2+\zeta^2<8^2$. The cubic smooth cut equals one through radius $8$ and zero from radius $12$ outward. The interface shell is exactly $8\le\sqrt{r^2+\zeta^2}<12$. The cut acts on deviations and velocities before its energy and momentum are reconstructed, so cutoff-generated gradient energy is included.

The compact binding ratio is

$$
\mathcal B=\frac{\sqrt{E_{\mathrm{cut}}^2-v_*^2P_{\mathrm{cut}}^2}}
{\Omega_\infty|Q_{\mathrm{cut}}|}.
$$

A zero cut charge, negative radicand, missing value, or nonfinite value fails qualification. A row is numerically qualified only when every sample is finite, total energy drift is below $2\times10^{-4}$, total signed-charge drift is below $2\times10^{-5}$, maximum outer-boundary energy fraction is below $10^{-6}$, and both instantaneous discrete local-balance residuals are at most $10^{-8}$.

A persistent late remnant requires every sample on $32\le t\le48$ to retain at least $0.25$ of the initial signed charge inside the fixed core, have $\mathcal B<0.99$, have core RMS at most $6$, and have interface-shell energy below $0.05$ of initial total energy. The late signed-core-charge range divided by the magnitude of initial signed charge must be at most $0.10$.

A Q256 momentum-arm formation candidate must be a coupled pair, pass preparation eligibility, pass numerical qualification, pass every persistence condition on S1, S2, and T1, and pass both spatial (S1→S2) and time-step (S1→T1) comparisons over the stable observable set. The single and uncoupled arms are controls. The binding ratio remains part of formation qualification even though it is excluded from cross-resolution equivalence comparisons because its denominator becomes ill-conditioned when the retained core charge is small.

## 5. Independent evidence and rejection controls

Each primary row archives raw fields and velocities at $t=0,32,40,48$. The verifier reopens every archive with pickle disabled and checks SHA-256, exact array names, float64 dtype, shape, embedded time, radial coordinates, axial coordinates, and cell volumes before reconstructing observables.

Each independent arm archives the same arrays and times in a distinct sibling directory. `raw_state_archive_complete` becomes true only after every independent file has been reopened and passed the same hash, dtype, shape, time, and geometry checks.

The independent T1 reconstruction is compared to the matching primary T1 row at each archived time over the stable observable set. Every comparison requires finite values for all declared observables, including the binding ratio. The maximum symmetric relative error over the stable set must remain below $0.05$.

The verifier must reject a changed state hash and must demonstrate that a changed field alters an independently reconstructed observable. Missing sources, changed live sources, malformed JSON constants, incomplete archive coverage, missing observables, and nonfinite observables fail closed.

The preparation specification is declarative only. The primary runner and independent verifier each assemble the normalized field, velocities, phase, coupling, and eligibility metadata in separate code paths. The independent verifier does not import the primary preparation assembler or primary evolution operator.

## 6. Decision tree and stopping rule

Implementation smoke checks must pass before the scientific output directory is created. The scientific schedule then executes once with the exact §3 values.

1. Any missing source identity, protocol mismatch, malformed receipt, incomplete state archive, failed reconstruction, nonfinite value, failed global conservation check, failed local-balance check, failed boundary check, failed required comparison, or failed independent comparison gives **INCONCLUSIVE**.
2. With all numerical and evidence checks passing, at least one fully compared coupled momentum arm plus a numerically qualified uncoupled control that fails formation gives **EMERGES—conditional Q=256 bound remnant in the declared incoming-momentum basin**.
3. With all numerical and evidence checks passing and no fully compared coupled momentum arm, the result gives **DOES NOT EMERGE in the specified Q=256 packet-momentum calculation**.

The execution ends at $t=48$. It does not extend time, change separation, change the charge, change packet width, select another momentum, alter a grid, relax a tolerance, or omit a failed arm. A negative or inconclusive result completes this preregistered calculation.

Every receipt keeps `complete_physical_matter_formation=false`, `gravitational_capture_established=false`, `physical_size_map_established=false`, and `packet_count_minimum_established=false`.

## References

- `computations/matter_formation_momentum_basin_prereg.md`—Q16 incoming-momentum protocol and comparison contract.
- `computations/matter_formation_wave_capture.py`—action, finite-volume observables, and Yoshida-composed evolution.
- `computations/verify_matter_formation_wave_capture.py`—separate finite-volume action assembly, RK4 evolution, and archive checks.
- `computations/matter_formation_neutral_packets.py`—axisymmetric finite-volume geometry and primary operator.
- `computations/matter_formation_radial_cloud.py`—supplied action coefficients and exterior frequency.
