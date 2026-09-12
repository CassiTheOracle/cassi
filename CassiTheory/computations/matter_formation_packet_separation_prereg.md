# Packet-Separation Basin Probe at Fixed Total Charge 16

## Status: Preregistered conditional calculation—September 2026

## Abstract

This calculation tests whether the initial separation of two incoming charged packets changes their ability to leave a persistent localized remnant in the supplied real-mediator, complex-carrier action. Total charge, packet width, wave number, phase convention, coupling, domain, grid ladder, final time, and acceptance predicates are fixed. The separation ladder is $c\in\{10,12,14\}$ for packet centres $\zeta=\pm c$. The calculation measures only the declared axisymmetric scalar model. General three-dimensional stability, gravitational capture, physical size, quantum particle identity, spin, statistics, and a whole-bubble production mechanism remain outside the calculation.

## 1. Scope and lineage

The execution class is `packet_separation_basin_probe`. It is a preparation intervention at fixed total signed charge $Q=16$; it is not a charge-threshold scan and does not modify the completed Q16 probe or the frozen spatial-convergence campaign.

The scientific output path is `runs/20260911_matter_formation_packet_separation`. The primary runner creates it exclusively, snapshots this protocol, the declarative preparation specification, both runner/verifier sources, and every declared action source. The verifier writes `verification.json` and a sibling independent-state archive. A failed or partial execution remains preserved.

A positive result would establish only a conditional remnant for one declared separation and the fixed preparation. It would not establish a global charge minimum, an optimal separation, a minimum packet count, physical size, or gravitational capture.

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
\Omega_\infty=\sqrt{B/a},\qquad v_*=\sqrt{k_{Cx}/(2a)}=\sqrt8.
$$

Every preparation has $f=1$ and $\dot f=0$. The `single16` control is a Gaussian of width $w=4$ centred at the origin with carrier frequency $\Omega_\infty$. Each pair is the sum of equal Gaussian envelopes of width $w=4$ centred at $\zeta=\pm c$, with $k=1$ and

$$
\omega=\sqrt{\Omega_\infty^2+8k^2}.
$$

The phases point inward. The `antiphase_c12` arm multiplies the left packet by $-1$. The `uncoupled_c12` arm uses the $c=12$ pair with $h_C=0$ throughout. Every preparation is normalized once from the full single or superposed field to total signed charge $Q=16$. The nominal charge share of a separated pair is $Q/2=8$ before interaction.

A pair is preparation-eligible only when its normalized envelope overlap is at most $0.01$, its origin-centred initial core charge fraction is at most $0.10$, and its initial energy satisfies $E\ge\Omega_\infty|Q|$. Eligibility is computed from the actual discretized preparation on each grid.

## 3. Frozen machine-readable schedule

The following JSON is the sole scientific schedule and decision contract.

```json
{
  "schema": "matter-formation-packet-separation-protocol-v1",
  "execution_class": "packet_separation_basin_probe",
  "output": "runs/20260911_matter_formation_packet_separation",
  "preparation": {
    "total_charge": 16.0,
    "nominal_packet_charge": 8.0,
    "width": 4.0,
    "centers": [10.0, 12.0, 14.0],
    "wave_number": 1.0,
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
      "G0": [192, 0.5, 0.015625],
      "G1": [192, 0.25, 0.015625],
      "T1": [192, 0.5, 0.0078125]
    },
    "independent_method": "classical RK4 with separately assembled finite-volume operator",
    "independent_grid": [192, 0.5, 0.0078125]
  },
  "arms": {
    "all": ["single16", "pair_c10", "pair_c12", "pair_c14", "antiphase_c12", "uncoupled_c12"],
    "coupled_candidates": ["pair_c10", "pair_c12", "pair_c14", "antiphase_c12"],
    "comparison": ["single16", "pair_c10", "pair_c12", "pair_c14", "antiphase_c12", "uncoupled_c12"],
    "independent": ["single16", "pair_c10", "pair_c12", "pair_c14", "antiphase_c12", "uncoupled_c12"]
  },
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

A separation-arm formation candidate must be a coupled pair, pass preparation eligibility, pass numerical qualification, pass every persistence condition, and pass both spatial ($G0\to G1$) and time-step ($G0\to T1$) comparisons. The single and uncoupled arms are controls.

## 5. Independent evidence and rejection controls

Each primary row archives raw fields and velocities at $t=0,32,40,48$. The verifier reopens every archive with pickle disabled and checks SHA-256, exact array names, float64 dtype, shape, embedded time, radial coordinates, axial coordinates, and cell volumes before reconstructing observables.

Each independent arm archives the same arrays and times in a distinct sibling directory. `raw_state_archive_complete` becomes true only after every independent file has been reopened and passed the same hash, dtype, shape, time, and geometry checks.

The independent T1 reconstruction is compared to the matching primary T1 row at each archived time. Every comparison requires finite energy, signed charge, core fraction, core RMS, compact binding ratio, interface-shell energy fraction, core energy, and mediator depletion. The maximum symmetric relative error must remain below $0.05$.

The verifier must reject a changed state hash and must demonstrate that a changed field alters an independently reconstructed observable. Missing sources, changed live sources, malformed JSON constants, incomplete archive coverage, missing observables, and nonfinite observables fail closed.

The preparation specification is declarative only. The primary runner and independent verifier each assemble the normalized field, velocities, coupling, and eligibility metadata from that specification in separate code paths. The independent verifier does not import the primary preparation assembler or primary evolution operator.

## 6. Decision tree and stopping rule

Implementation smoke checks must pass before the scientific output directory is created. The scientific schedule then executes once with the exact §3 values.

1. Any missing source identity, protocol mismatch, malformed receipt, incomplete state archive, failed reconstruction, nonfinite value, failed global conservation check, failed local-balance check, failed boundary check, or failed required comparison gives **INCONCLUSIVE**.
2. With all numerical and evidence checks passing, at least one fully compared coupled separation arm plus a numerically qualified uncoupled control that fails formation gives **EMERGES—conditional bound remnant in the declared separation basin**.
3. With all numerical and evidence checks passing and no fully compared coupled separation arm, the result gives **DOES NOT EMERGE in the specified packet-separation calculation**.

The execution ends at $t=48$. It does not extend time, change phase, select another separation, change packet width or charge, alter a grid, relax a tolerance, or omit a failed arm. A negative or inconclusive result completes this preregistered calculation.

Every receipt keeps `complete_physical_matter_formation=false`, `gravitational_capture_established=false`, `physical_size_map_established=false`, and `packet_count_minimum_established=false`.

## References

- `computations/matter_formation_two_packet_q16_prereg.md`—fixed-total-charge Q16 two-packet threshold probe.
- `computations/matter_formation_wave_capture.py`—action, finite-volume observables, and Yoshida-composed evolution.
- `computations/verify_matter_formation_wave_capture.py`—separate finite-volume action assembly, RK4 evolution, and archive checks.
- `computations/matter_formation_neutral_packets.py`—axisymmetric finite-volume geometry and primary operator.
- `computations/matter_formation_radial_cloud.py`—supplied action coefficients and exterior frequency.
