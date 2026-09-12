# Spatial Convergence of Charged Wave Capture

## Status: Preregistered conditional calculation—September 2026

## Abstract

This calculation tests whether the pair and antiphase charged-wave channels have a converged spatial observable under the supplied real-mediator, complex-carrier action. It keeps the physical preparation, domain, late-time window, core, interface shell, and acceptance thresholds fixed while refining the cylindrical finite-volume spacing and reducing the time step with the spatial scale. The calculation diagnoses spatial convergence; it does not establish gravitational capture, a physical size map, quantum particle identity, or a whole-bubble production mechanism.

## 1. Scope and baseline binding

The baseline acceptance anchor is the complete receipt at `runs/20260911_matter_formation_wave_capture_v2/result.json`, SHA-256 `c380ecb40c9c3239534e8546389ebfbac312d60e0df4238e7ce38e3a1780a052`. Its protocol identity is `8c8cfb63e2e2ecb56a82864e7ff38468791d00318d5b7ef99317a8aa324747ba`. The spatial-convergence calculation compares its declared G0, G1, G2, and T1 observables with the new refinement ladder and preserves the baseline receipt without modification.

The target channels are `pair256` and `antiphase256`. The single-packet and uncoupled arms are retained as numerical and rejection controls. Every target and control row archives raw fields and velocities at $t=0,32,40,48$ in a new output directory. The scientific output path is `runs/20260911_matter_formation_wave_capture_spatial_convergence_20260911`; creation refuses an existing path.

## 2. Fixed action and preparation

Write $z=x+iy$ and evolve deviations $(f-1,x,y)$ with exterior Dirichlet deviations zero. The dimensionless energy, signed charge, potential, and coefficients are the values in the baseline protocol:

$$
E=\int\left[\frac{c_\Psi}{2}\dot f^2+a|\dot z|^2+\frac12|\nabla f|^2+\frac{k_{Cx}}2|\nabla z|^2+V(f,|z|)\right]d^3x,
\qquad
Q=-2a\int\operatorname{Im}(z^*\dot z)d^3x,
$$

$$
V=\frac{u_\rho}{4}(f^2-1)^2+(B-h_C+h_Cf^2)|z|^2+\frac{u_C}{2}|z|^4,
$$

$$
a=\frac1{16},\quad c_\Psi=\frac18,\quad u_\rho=4,\quad u_C=1,\quad k_{Cx}=1,
\quad h_C=2.9598260763447164,\quad B=4.75.
$$

Every preparation has $f=1$ and $\dot f=0$. The single packet is a Gaussian of width $w=4$ centred at the origin. Each pair is the equal superposition of Gaussian packets of width $w=4$ centred at $\zeta=\pm12$, with inward wave number $k=1$ and the declared charged-wave frequency. `antiphase256` multiplies the left packet by $-1$. `outgoing256` reverses both wave numbers. `uncoupled256` uses the pair preparation with $h_C=0$ throughout. Each arm is normalized once from the full superposed field to total signed charge $64$, $128$, or $256$ as declared by the arm.
At every spatial level, evaluate the same analytic packet field at that level's cell geometry, then normalize the discretized superposition exactly once to the declared total signed charge.

The physical domain is $R=192$ with the same radial and axial finite-volume geometry at every resolution. The core is $r^2+\zeta^2<8^2$. The smooth cut equals one through radius $8$ and zero from radius $12$ outward. The interface shell is exactly $8\le\sqrt{r^2+\zeta^2}<12$. The outer boundary shell has width $16$.

## 3. Frozen machine-readable schedule

The following JSON is the sole scientific schedule and decision contract.

```json
{
  "schema": "matter-formation-spatial-convergence-protocol-20260911",
  "baseline": {
    "primary_receipt": "runs/20260911_matter_formation_wave_capture_v2/result.json",
    "primary_receipt_sha256": "c380ecb40c9c3239534e8546389ebfbac312d60e0df4238e7ce38e3a1780a052",
    "protocol_sha256": "8c8cfb63e2e2ecb56a82864e7ff38468791d00318d5b7ef99317a8aa324747ba",
    "source_sha256": {
      "computations/matter_formation_wave_capture.py": "31ab56d40524c505d90431b65b0072b998c65635313955d057b4d6d4b8e35b83",
      "computations/matter_formation_wave_capture_v2_prereg.md": "8c8cfb63e2e2ecb56a82864e7ff38468791d00318d5b7ef99317a8aa324747ba",
      "computations/matter_formation_neutral_packets.py": "743e2e75e6b8bc5c5ffd6a75393a49b9da6e5481b9b0b4dee08b040b3f1b901f",
      "computations/matter_formation_radial_cloud.py": "7ed6029e878c6642ab22a6c2526b4a02b2107b1538b751a6c1ea66762f5f6cb4",
      "computations/verify_matter_formation_wave_capture.py": "a7bccd1c20904e43b05cc7559863747df2d8b61dca8ea61b216c29581545da8d"
    }
  },
  "output": "runs/20260911_matter_formation_wave_capture_spatial_convergence_20260911",
  "preparation": {
    "charges": [64.0, 128.0, 256.0],
    "width": 4.0,
    "center": 12.0,
    "wave_number": 1.0,
    "initial_overlap_max": 0.01,
    "initial_core_fraction_max": 0.10
  },
  "evolution": {
    "t_final": 48.0,
    "late_start": 32.0,
    "sample_dt": 0.5,
    "snapshot_times": [0.0, 32.0, 40.0, 48.0],
    "primary_method": "fourth-order Yoshida-composed velocity Verlet",
    "spatial_ladder": {
      "S0": [192, 0.5, 0.015625],
      "S1": [192, 0.25, 0.0078125],
      "S2": [192, 0.125, 0.00390625]
    },
    "domain_control": [256, 0.5, 0.015625],
    "independent_method": "classical RK4 with separately assembled finite-volume operator",
    "independent_grid": [192, 0.25, 0.00390625]
  },
  "arms": {
    "target": ["pair256", "antiphase256"],
    "controls": ["single256", "uncoupled256"],
    "domain": ["pair256", "antiphase256"],
    "independent": ["pair256", "antiphase256"]
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
    "spatial_comparison": 0.05,
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

## 4. Required observables

Every primary and independent sample must contain finite numeric values for energy, signed charge, absolute charge, charge centroid, core signed and absolute charge, core fraction, core RMS, mediator depletion, core energy, compact-cut energy and signed charge, cut axial momentum, binding radicand, binding ratio, interface-shell energy, interface-shell energy fraction, outer-boundary energy, outer-boundary energy fraction, and every local energy and charge balance residual and face flux.

The primary and independent readers reject missing keys, `null`, nonnumeric values, NaN, positive infinity, negative infinity, malformed JSON constants, malformed array metadata, wrong dtype, wrong shape, wrong coordinates, wrong volumes, wrong embedded times, duplicate snapshot times, missing snapshot times, and hash mismatches. Initial energy and initial signed charge are finite-number requirements before any normalization or drift calculation.

Each row is numerically qualified only when all samples are finite, total energy drift is below $2\times10^{-4}$, total signed-charge drift is below $2\times10^{-5}$, maximum outer-boundary energy fraction is below $10^{-6}$, and both instantaneous discrete local-balance residuals are at most $10^{-8}$.

## 5. Spatial convergence and controls

For each target arm, compare the late-window means at adjacent spatial levels `S0→S1` and `S1→S2` for energy, charge, core fraction, core RMS, binding ratio, and interface-shell energy fraction. The comparison error is normalized by the fixed scales used by the baseline protocol. A target is spatially converged only when the `S1→S2` maximum error is below $0.05$ and is no larger than the corresponding `S0→S1` maximum error.

The domain control compares `S0` with the larger-domain control at the same spacing. The independently assembled RK4 calculation compares the target `S1` rows at $t=0,32,40,48$ with its raw-state reconstruction. Every comparison requires all declared values to be finite numeric values.

The field-level diagnostic records the per-sample decomposition of total energy into mediator potential, carrier potential, radial-gradient, axial-gradient, kinetic, core, and interface-shell contributions. It also records signed core charge, compact-cut charge, binding radicand, local energy balance, local charge balance, and boundary energy. These fields identify the spatial term responsible for any remaining discrepancy.

The uncoupled control must remain numerically qualified and fail the formation persistence conditions. A control failure, archive failure, source mismatch, malformed value, or failed conservation gate produces **INCONCLUSIVE**.

## 6. Decision tree and stopping rule

The implementation smoke checks and all fail-closed parser and archive controls must pass before the scientific output directory is created. The schedule executes once with the exact §3 values. The output path and independent archive path refuse overwrite.

1. Any missing source identity, protocol mismatch, malformed receipt, incomplete raw-state archive, failed reconstruction, nonfinite value, failed global conservation check, failed local-balance check, failed boundary check, or failed required comparison gives **INCONCLUSIVE**.
2. If both target arms satisfy the spatial-convergence gate, the independent method gate, and the controls, report **SPATIAL CONVERGENCE ESTABLISHED for the declared wave-capture observables**.
3. If either target arm fails the spatial-convergence gate, report **SPATIAL CONVERGENCE DOES NOT EMERGE in the declared resolution ladder**.

This calculation stops at $t=48$. It does not relax tolerances, remove a failed arm, change the preparation, or convert a spatial diagnostic into a formation claim. A subsequent bound-remnant test requires a separate protocol after the spatial gate passes.

Every receipt keeps `complete_physical_matter_formation=false`, `gravitational_capture_established=false`, `physical_size_map_established=false`, and `packet_count_minimum_established=false`.

## References

- `computations/matter_formation_wave_capture_v2_prereg.md`—baseline action, preparation, observables, and acceptance contract.
- `computations/matter_formation_wave_capture_spatial_convergence.py`—spatial-ladder primary runner and raw-state producer.
- `computations/verify_matter_formation_wave_capture_spatial_convergence.py`—independent RK4 execution, reconstruction, archive validation, and rejection controls.
- `computations/matter_formation_wave_capture.py`—shared finite-volume operator and Yoshida-composed evolution.
- `computations/verify_matter_formation_wave_capture.py`—shared independent action assembly and archive primitives.
- `foundations/matter-completion-boundary.md` §§7–8, 16–18—binding scope and continuum stability boundary.
