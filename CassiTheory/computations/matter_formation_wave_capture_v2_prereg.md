# Repaired Scalar Wave-Capture Execution

## Status: Preregistered conditional calculation—September 2026

## Abstract

This calculation asks whether two initially separated, inward-moving charged carrier packets in the supplied real-mediator, complex-carrier action leave a localized bound remnant after interface radiation separates. The execution is fixed before the scientific runner starts. It measures a dimensionless, axisymmetric scalar model. General three-dimensional stability, gravitational capture, physical size, quantum particle identity, spin, statistics and a whole-bubble production mechanism remain outside the calculation.

## 1. Scope and immutable lineage

The execution class is `implementation_repair`. Its numerical inputs and decision thresholds are frozen in §3. The preserved baseline artifacts remain immutable and serve only as provenance and a negative replay control:

- `runs/20260911_matter_formation_wave_capture/result.json`, SHA-256 `5bfba3f472e4b95ccb10c491bdc3f4de04c227cd7f64c5008958d85152fe7291`;
- `runs/20260911_matter_formation_wave_capture/verification.json`, SHA-256 `610858fefb812999e14615aa195f2a9eb441ef5bef783d1bf43d5fa35b5ddb9f`;
- `computations/matter_formation_minimum_droplet_prereg.md`, SHA-256 `b8b6ee4f950e2b22dbe0a9afbacc5d56685b3e084912dec1d32421a111a22b10`.

The scientific output path is `runs/20260911_matter_formation_wave_capture_v2`. The runner creates it exclusively, snapshots this protocol and every declared local source, and refuses to overwrite an existing path. The verifier writes `verification-v2.json` plus a sibling independent-state archive inside that run. A failed or partial execution remains preserved.

## 2. Action and preparations

Write $z=x+iy$ and evolve deviations $(f-1,x,y)$ with exterior Dirichlet deviations zero. The supplied dimensionless energy and signed charge are

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
a=\frac1{16},\quad c_\Psi=\frac18,\quad u_\rho=4,\quad u_C=1,\quad k_{Cx}=1,
\quad h_C=2.9598260763447164,\quad B=4.75.
$$

The exterior carrier frequency and characteristic propagation speed are

$$
\Omega_\infty=\sqrt{B/a},\qquad v_*=\sqrt{k_{Cx}/(2a)}=\sqrt8.
$$

Every preparation has $f=1$ and $\dot f=0$. A single packet is

$$
z=A\exp[-(r^2+\zeta^2)/(2w^2)],\qquad \dot z=-i\Omega_\infty z.
$$

A pair is the sum of equal Gaussian envelopes centred at $\zeta=\pm12$, with width $w=4$, inward phases $\exp[\mp ik(\zeta\mp12)]$, $k=1$, and $\dot z=-i\omega z$, where

$$
\omega=\sqrt{\Omega_\infty^2+8k^2}.
$$

Antiphase multiplies the left packet by $-1$. Outgoing reverses both wave numbers. The uncoupled arm uses the pair256 preparation with $h_C=0$ throughout. Each arm is normalized once, from the full superposed field, to its declared total signed charge.

A pair is preparation-eligible only when its normalized envelope overlap is at most $0.01$, its initial origin-centred core charge fraction is at most $0.10$, and its initial energy satisfies $E\ge\Omega_\infty|Q|$.

## 3. Frozen machine-readable schedule

The following JSON is the sole scientific schedule and decision contract.

```json
{
  "schema": "matter-formation-wave-capture-protocol-v2",
  "execution_class": "implementation_repair",
  "output": "runs/20260911_matter_formation_wave_capture_v2",
  "lineage": {
    "baseline_primary": {
      "path": "runs/20260911_matter_formation_wave_capture/result.json",
      "sha256": "5bfba3f472e4b95ccb10c491bdc3f4de04c227cd7f64c5008958d85152fe7291"
    },
    "baseline_verification": {
      "path": "runs/20260911_matter_formation_wave_capture/verification.json",
      "sha256": "610858fefb812999e14615aa195f2a9eb441ef5bef783d1bf43d5fa35b5ddb9f"
    }
  },
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
    "primary_grids": {
      "G0": [192, 0.5, 0.015625],
      "G1": [192, 0.25, 0.015625],
      "G2": [256, 0.5, 0.015625],
      "T1": [192, 0.5, 0.0078125]
    },
    "independent_method": "classical RK4 with separately assembled finite-volume operator",
    "independent_grid": [192, 0.5, 0.0078125]
  },
  "arms": {
    "base": [
      "single64",
      "single128",
      "single256",
      "pair64",
      "pair128",
      "pair256",
      "antiphase256",
      "outgoing256",
      "uncoupled256"
    ],
    "comparison": ["single256", "pair256", "antiphase256", "uncoupled256"],
    "independent": ["single256", "pair256", "antiphase256", "uncoupled256"]
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

The primary runner evolves the axisymmetric cylindrical finite-volume system with cell volume $2\pi r\,dr\,d\zeta$. The independent verifier assembles the same action and boundary terms separately and evolves its four declared arms with classical RK4.

Every primary sample records total energy, signed and absolute charge, charge centroid, origin-centred core signed and absolute charge, core RMS, mediator depletion, core energy, compact-cut energy and signed charge, cut axial momentum, binding radicand and ratio, interface-shell energy, outer-boundary energy, and signed local energy and charge derivatives and face fluxes.

The core is fixed at $r^2+\zeta^2<8^2$. The cubic smooth cut equals one through radius $8$ and zero from radius $12$ outward. The interface shell is exactly $8\le\sqrt{r^2+\zeta^2}<12$. The cut acts on deviations and velocities before its energy and momentum are reconstructed, so the cutoff-generated gradient energy is included.

The compact binding ratio is

$$
\mathcal B=\frac{\sqrt{E_{\mathrm{cut}}^2-v_*^2P_{\mathrm{cut}}^2}}
{\Omega_\infty|Q_{\mathrm{cut}}|}.
$$

A zero cut charge, negative radicand, missing value or nonfinite value fails qualification.

A row is numerically qualified only when every sample is finite, total energy drift is below $2\times10^{-4}$, total signed-charge drift is below $2\times10^{-5}$, maximum outer-boundary energy fraction is below $10^{-6}$, and both instantaneous discrete local-balance residuals are at most $10^{-8}$.

A persistent late remnant requires every sample on $32\le t\le48$ to retain at least $0.25$ of the initial signed charge inside the fixed core, have $\mathcal B<0.99$, have core RMS at most $6$, and have interface-shell energy below $0.05$ of initial total energy. The late signed-core-charge range divided by the magnitude of initial signed charge must be at most $0.10$.

A formation candidate must be a coupled pair, pass preparation eligibility, pass numerical qualification and pass every persistence condition. `pair64` and `pair128` remain fixed screening samples without a converged formation claim because the frozen comparison ladder covers only the four comparison arms.

## 5. Independent evidence and rejection controls

Each primary row archives raw fields and velocities at $t=0,32,40,48$. The verifier reopens every archive with pickle disabled and checks SHA-256, exact array names, float64 dtype, shape, embedded time, radial coordinates, axial coordinates and cell volumes before reconstructing the observables.

Each independent arm archives the same arrays and times in a distinct sibling directory. `raw_state_archive_complete` becomes true only after every independent file has been reopened and passed the same hash, dtype, shape, time and geometry checks.

The independent T1 reconstruction is compared to the matching primary T1 row at each archived time. Every comparison requires finite energy, signed charge, core fraction, core RMS, compact binding ratio, interface-shell energy fraction, core energy and mediator depletion. The maximum symmetric relative error must remain below $0.05$.

Controls operate on copies or in-memory tensors. The verifier must reject a changed state hash and must demonstrate that a changed field alters an independently reconstructed observable. Missing sources, changed live sources, malformed JSON constants, incomplete archive coverage, missing observables and nonfinite observables fail closed.

## 6. Decision tree and stopping rule

The implementation smoke checks must pass before the scientific output directory is created. The scientific schedule then executes once with the exact §3 values.

1. Any missing source identity, protocol mismatch, malformed receipt, incomplete state archive, failed reconstruction, nonfinite value, failed global conservation check, failed local-balance check, failed boundary check, or failed required comparison gives **INCONCLUSIVE**.
2. With all numerical and evidence checks passing, at least one fully compared coupled candidate plus a numerically qualified uncoupled control that fails formation gives **EMERGES—conditional post-collision bound remnant**.
3. With all numerical and evidence checks passing and no fully compared coupled candidate, the result is **DOES NOT EMERGE in the specified wave-capture calculation**.

The execution ends at $t=48$. It does not extend time, change phase, select another packet width, change a charge, alter a grid, relax a tolerance or omit a failed arm. A negative or inconclusive result completes this preregistered calculation.

Every receipt keeps `complete_physical_matter_formation=false`, `gravitational_capture_established=false`, `physical_size_map_established=false` and `packet_count_minimum_established=false`.

## References

- `computations/matter_formation_minimum_droplet_prereg.md`—supplied scalar action, stationary branch and baseline capture schedule.
- `computations/matter_formation_wave_capture.py`—primary finite-volume runner and Yoshida-composed evolution.
- `computations/verify_matter_formation_wave_capture.py`—independent action assembly, RK4 evolution and archive verifier.
- `computations/matter_formation_neutral_packets.py`—axisymmetric finite-volume operator used by the primary runner.
- `computations/matter_formation_radial_cloud.py`—supplied action coefficients and exterior frequency.
- `foundations/matter-completion-boundary.md` §§7–8, 16–18—binding scope and continuum stability boundary.
