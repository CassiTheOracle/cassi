# Fixed-Charge Packet Relative-Phase Probe

## Status: Preregistered conditional calculation—September 2026

## Abstract

This calculation tests whether the relative complex phase between two inward-moving charged packets changes their ability to leave a persistent localized remnant. Total signed charge, packet separation, width, carrier magnitude, phase-gradient direction, action, domain, grid ladder, final time, and persistence predicates are fixed. The relative phase ladder is $\delta\in\{0,\pi/2,\pi\}$, applied to the left packet after its inward carrier phase has been assigned. A separate outward arm controls the near-zero-core binding-ratio gate. The calculation measures only the declared axisymmetric scalar model. General three-dimensional stability, gravitational capture, physical size, quantum particle identity, spin, statistics, and a whole-bubble production mechanism remain outside the calculation.

## 1. Scope and lineage

The execution class is `packet_relative_phase_probe`. It is a fresh intervention at fixed total signed charge $Q=16$, packet centres $\zeta=\pm12$, width $w=4$, carrier magnitude $|k|=1$, and inward phase-gradient sign. The phase ladder changes only the relative complex multiplier of one packet. The fixed-charge separation, momentum magnitude, orientation, and width receipts provide preparation lineage; no earlier receipt is modified or used as evidence for this calculation.

The scientific output path is `runs/20260912_matter_formation_packet_phase`. The primary runner creates it exclusively, snapshots this protocol, the declarative preparation specification, both runner/verifier sources, and every declared action source. The verifier writes `verification.json` and a sibling independent-state archive. A failed or partial execution remains preserved.

A positive result would establish only a conditional remnant for one declared relative phase and fixed preparation. It would not establish a global phase-selection rule, an optimal phase, a global charge minimum, physical size, or a whole-bubble production mechanism.

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

Every preparation has $f=1$ and $\dot f=0$. The `single16_w4` control is a Gaussian of width $w=4$ centred at the origin with carrier frequency $\Omega_\infty$. The coupled phase arms are equal Gaussian envelopes centred at $\zeta=\pm12$, with inward phase-gradient sign $+1$, carrier magnitude $|k|=1$, and width $w=4$. Their carrier frequency is

$$
\omega=\sqrt{\Omega_\infty^2+8k^2}.
$$

After the inward carrier phases are assigned, the left packet is multiplied by $e^{i\delta}$ relative to the right packet. The three declared relative phases are

$$
\delta=0,\qquad \delta=\frac\pi2,\qquad \delta=\pi.
$$

Thus `pair_phase0` is in phase, `pair_phase90` is in quadrature, and `pair_phase180` is antiphase. The `uncoupled_phase0` arm uses the in-phase inward pair with $h_C=0$ throughout. The `outward_phase0` arm reverses both carrier phase gradients and exists only as the near-zero-core binding-gate control. Every preparation is normalized once from the complete superposed field to total signed charge $Q=16$.

The inward sign is fixed by $z\propto e^{i(k\zeta-\omega t)}$ and $\dot z=-i\omega z$: the packet at $\zeta=-12$ has phase gradient $+1$ and moves toward increasing $\zeta$, while the packet at $\zeta=+12$ has phase gradient $-1$ and moves toward decreasing $\zeta$. The relative phase is an internal multiplier and does not change either carrier gradient.

A pair is preparation-eligible only when its normalized envelope overlap is at most $0.01$, its origin-centred initial core charge fraction is at most $0.10$, and its initial energy satisfies $E\ge\Omega_\infty|Q|$. Eligibility is computed from the actual discretized preparation on each grid.

## 3. Frozen machine-readable schedule

The following JSON is the sole scientific schedule and decision contract.

```json
{
  "schema": "matter-formation-packet-relative-phase-protocol-v1",
  "execution_class": "packet_relative_phase_probe",
  "output": "runs/20260912_matter_formation_packet_phase",
  "preparation": {
    "total_charge": 16.0,
    "nominal_packet_charge": 8.0,
    "center_separation": 12.0,
    "width": 4.0,
    "wave_number_magnitude": 1.0,
    "inward_phase_sign": 1.0,
    "outward_phase_sign": -1.0,
    "relative_phases": [0.0, 1.5707963267948966, 3.141592653589793],
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
    "all": ["single16_w4", "pair_phase0", "pair_phase90", "pair_phase180", "uncoupled_phase0", "outward_phase0"],
    "coupled_candidates": ["pair_phase0", "pair_phase90", "pair_phase180"],
    "rule_control": "outward_phase0",
    "uncoupled_control": "uncoupled_phase0",
    "comparison": ["single16_w4", "pair_phase0", "pair_phase90", "pair_phase180", "uncoupled_phase0", "outward_phase0"],
    "independent": ["single16_w4", "pair_phase0", "pair_phase90", "pair_phase180", "uncoupled_phase0", "outward_phase0"]
  },
  "comparison_observables": ["energy", "charge", "core_fraction", "core_rms", "core_energy", "shell_energy_fraction"],
  "binding_gate": {
    "retained_core_fraction": 0.25,
    "binding_ratio_max": 0.99,
    "equivalence_rule": "binding_ratio is excluded from equivalence comparisons for every arm",
    "formation_rule": "if late minimum core fraction is at least 0.25, require binding_ratio below 0.99; otherwise the row is nonpersistent"
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

## 4. Qualification and explicit binding gate

The primary runner evolves the axisymmetric cylindrical finite-volume system with cell volume $2\pi r\,dr\,d\zeta$. The independent verifier assembles the same action and boundary terms separately and evolves every declared arm with classical RK4.

Every primary sample records total energy, signed and absolute charge, charge centroid, origin-centred core signed and absolute charge, core RMS, mediator depletion, core energy, compact-cut energy and signed charge, cut axial momentum, binding radicand and ratio, interface-shell energy, outer-boundary energy, and signed local energy and charge derivatives and face fluxes.

The core is fixed at $r^2+\zeta^2<8^2$. The cubic smooth cut equals one through radius $8$ and zero from radius $12$ outward. The interface shell is exactly $8\le\sqrt{r^2+\zeta^2}<12$.

The binding rule is explicit and unconditional with respect to equivalence: binding ratio is never a cross-resolution or time-step equivalence observable. Let $f_{\mathrm{core,min}}$ be the minimum signed core fraction over $32\le t\le48$.

1. If $f_{\mathrm{core,min}}\ge0.25$, binding evaluation is active and the row must satisfy $\max\mathcal B<0.99$ for persistence.
2. If $f_{\mathrm{core,min}}<0.25$, the row is automatically nonpersistent and the binding ratio is excluded from the equivalence decision.
3. The `outward_phase0` arm is a rule-control witness. The receipt must show $f_{\mathrm{core,min}}<0.25$ and a legacy binding-ratio comparison error above the $0.05$ method threshold while the stable comparison set passes. This demonstrates that the rule detects the ill-conditioned observable.

Cross-resolution and time-step comparisons use the stable observable set

$$
\{E,Q,f_{\mathrm{core}},R_{\mathrm{core}},E_{\mathrm{core}},f_{\mathrm{shell}}\}.
$$

The single and uncoupled arms are controls. The outward arm is the explicit binding-gate control and is not a formation candidate.

## 5. Independent evidence and rejection controls

Each primary row archives raw fields and velocities at $t=0,32,40,48$. The verifier reopens every archive with pickle disabled and checks SHA-256, exact array names, float64 dtype, shape, embedded time, radial coordinates, axial coordinates, and cell volumes before reconstructing observables.

Each independent arm archives the same arrays and times in a distinct sibling directory. `raw_state_archive_complete` becomes true only after every independent file has been reopened and passed the same hash, dtype, shape, time, and geometry checks.

The independent T1 reconstruction is compared to the matching primary T1 row at each archived time over the stable observable set. Every comparison also requires finite values for all declared observables, including binding ratio. The maximum symmetric relative error over the stable set must remain below $0.05$.

The verifier independently recomputes the rule-control witness from the archived primary rows: the retained-core minimum, the legacy binding-ratio error for `outward_phase0` across $G0\to G1$ and $G0\to T1$, and the stable-comparison pass. A receipt cannot claim the gate witness by copying a primary boolean.

The verifier must reject a changed state hash and must demonstrate that a changed field alters an independently reconstructed observable. Missing sources, changed live sources, malformed JSON constants, incomplete archive coverage, missing observables, and nonfinite observables fail closed.

The preparation specification is declarative only. The primary runner and independent verifier each assemble the normalized field, width, carrier phase gradients, relative phase, coupling, and eligibility metadata from that specification in separate code paths. The independent verifier does not import the primary preparation assembler or primary evolution operator.

## 6. Decision tree and stopping rule

Implementation smoke checks must pass before the scientific output directory is created. The scientific schedule then executes once with the exact §3 values.

1. Any missing source identity, protocol mismatch, malformed receipt, incomplete state archive, failed reconstruction, nonfinite value, failed global conservation check, failed local-balance check, failed boundary check, failed required comparison, failed independent comparison, or failed binding-gate witness gives **INCONCLUSIVE**.
2. With all numerical, evidence, and binding-gate checks passing, at least one fully compared coupled phase arm plus a numerically qualified uncoupled control that fails formation gives **EMERGES—conditional bound remnant in the declared relative-phase basin**.
3. With all numerical, evidence, and binding-gate checks passing and no fully compared coupled phase arm, the result gives **DOES NOT EMERGE in the specified relative-phase calculation**.

The execution ends at $t=48$. It does not extend time, change separation, width, carrier magnitude or gradient sign, change the phase ladder, alter a grid, relax a tolerance, or omit a failed arm. A negative or inconclusive result completes this preregistered calculation.

Every receipt keeps `complete_physical_matter_formation=false`, `gravitational_capture_established=false`, `physical_size_map_established=false`, and `packet_count_minimum_established=false`.

## References

- `computations/matter_formation_packet_separation_prereg.md`—fixed-charge separation ladder and basin boundary.
- `computations/matter_formation_momentum_orientation_prereg.md`—fixed-charge phase-gradient direction intervention and stable comparison set.
- `computations/matter_formation_packet_width_prereg.md`—fixed-charge width intervention and explicit binding gate.
- `computations/matter_formation_wave_capture.py`—action, finite-volume observables, and Yoshida-composed evolution.
- `computations/verify_matter_formation_wave_capture.py`—separate finite-volume action assembly, RK4 evolution, and archive checks.
- `computations/matter_formation_neutral_packets.py`—axisymmetric finite-volume geometry and primary operator.
- `computations/matter_formation_radial_cloud.py`—supplied action coefficients and exterior frequency.
