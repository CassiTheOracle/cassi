# Minimum Scalar Droplet and Incoming-Wave Capture

## Status: Preregistered conditional calculation—September 2026

## Abstract

This calculation asks whether the supplied three-dimensional real-mediator, complex-carrier action has a positive binding-charge boundary and whether initially unbound waves leave a localized bound remnant. Every charge, length and time below is dimensionless. The field representation, coefficients and charge are supplied inputs. Physical particle identification, a two-dimensional vacuum surface, a physical lattice spacing and gravitational backreaction remain outside this action.

## 1. Action and analytic bounds

Write $z=x+iy$, $n=|z|^2$ and $B=e_C+1/(4a)=4.75$. The energy and signed charge are

$$
E=\int\left[\frac{c_\Psi}{2}\dot f^2+a|\dot z|^2+\frac12|\nabla f|^2+\frac12|\nabla z|^2+V(f,|z|)\right]d^3x,
\quad Q=-2a\int\operatorname{Im}(z^*\dot z)d^3x,
$$

$$
V=\frac{u_\rho}{4}(f^2-1)^2+(B-h_C+h_Cf^2)n+\frac{u_C}{2}n^2.
$$

The inherited values are $a=1/16$, $c_\Psi=1/8$, $u_\rho=4$, $u_C=1$, $h_C=2.9598260763447164$, and both gradient coefficients are one. The exterior frequency is $\Omega_\infty=\sqrt{B/a}$ and propagation speed is $v_*=\sqrt8$. Vacuum subtraction is $f=1,z=0$. The fixed-charge functional is

$$
I(Q)=\inf\left[\frac12\int(|\nabla f|^2+|\nabla c|^2)+\int V(f,c)+\frac{Q^2}{4a\int c^2}\right].
$$

The tempting Sobolev decomposition with $W(n)=Bn-\min_fV(f,\sqrt n)$ is rejected as a global bound: near $n=0$, the minimizing mediator has $f^2\to1$ and $W(n)=h_Cn+O(n^2)$, so $W(n)/n^{5/3}\to\infty$. The runner records this failure and does not infer a global $K$, $N_0$ or $Q_0$. The existing sufficient certificate $Q>149.36022508149227$ supplies an upper bound on the infimum of binding charges. Numerical branch endpoints provide conditional tighter evidence; no failed solve establishes universal nonexistence.

The action's lower-density and large-density terms therefore need a different coercive decomposition before an analytic no-binding interval can be claimed. That unresolved inequality is not used in the scientific decision tree.

## 2. Frozen machine-readable schedule

The following JSON is the sole numerical schedule. Implementation and numerical repair may change source code before execution. Scientific criteria and initial conditions are fixed once this document is first used by a scientific runner. Each run snapshots this file and all transitive local numerical sources into an exclusively created directory. Preserved failed executions must never be overwritten.

```json
{
  "schema": "matter-minimum-droplet-protocol-v1",
  "stationary": {
    "charges": [1, 2, 4, 8, 16, 32, 64, 128, 256],
    "grids": {"S0": [32.0, 0.125], "S1": [32.0, 0.0625], "S2": [64.0, 0.125]},
    "seed_scales": [0.8, 1.2],
    "bisection_steps": 6,
    "residual_tolerance": 0.00002,
    "outer_fraction_tolerance": 0.000001,
    "binding_margin_fraction": 0.0001,
    "seed_tolerance": 0.00002,
    "space_tolerance": 0.005,
    "domain_tolerance": 0.001,
    "maxiter": 50000,
    "maxfun": 200000,
    "ftol": 1e-15,
    "gtol": 1e-9,
    "maxcor": 50
  },
  "capture": {
    "charges": [64.0, 128.0, 256.0],
    "width": 4.0,
    "center": 12.0,
    "wave_number": 1.0,
    "t_final": 48.0,
    "late_start": 32.0,
    "sample_dt": 0.5,
    "snapshot_times": [0.0, 32.0, 40.0, 48.0],
    "grids": {"G0": [192, 0.5, 0.015625], "G1": [192, 0.25, 0.015625], "G2": [256, 0.5, 0.015625], "T1": [192, 0.5, 0.0078125]},
    "base_arms": ["single64", "single128", "single256", "pair64", "pair128", "pair256", "antiphase256", "outgoing256", "uncoupled256"],
    "comparison_arms": ["single256", "pair256", "antiphase256", "uncoupled256"],
    "independent_arms": ["single256", "pair256", "antiphase256", "uncoupled256"],
    "core_radius": 8.0,
    "cut_radius": 12.0,
    "shell_radius": 16.0,
    "outer_shell_width": 16.0,
    "energy_drift_tolerance": 0.0002,
    "charge_drift_tolerance": 0.00002,
    "boundary_energy_fraction_tolerance": 0.000001,
    "comparison_tolerance": 0.05,
    "snapshot_tolerance": 0.02,
    "retained_charge_fraction": 0.25,
    "binding_ratio_max": 0.99,
    "core_rms_max": 6.0,
    "late_core_variation_fraction": 0.10,
    "separation_shell_energy_fraction": 0.05,
    "initial_overlap_max": 0.01,
    "initial_core_fraction_max": 0.10,
    "reconstruction_tolerance": 1e-9,
    "flux_balance_tolerance": 1e-8
  }
}
```

## 3. Stationary execution and decision tree

On each grid, descend through the listed charges using both compact seed scales. At the first charge each seed is the inherited populated-ball shape; subsequent seeds use the preceding endpoint with the carrier scaled by $\sqrt{Q_{new}/Q_{old}}$. Record every endpoint regardless of localization. On S0 also ascend through the listed charges using a diffuse Gaussian of width $R/4$ at the first charge and continuation thereafter. This prevents a single compact history from being the only searched basin.

Save $r,V,f,c,Q,\Omega,E,R,\Delta r$ for every endpoint. Independently reconstruct population, energy, stationary residuals, charge, RMS localization length $\xi$, exterior exponential length $[2a(\Omega_\infty^2-\Omega^2)]^{-1/2}$ where real, and outer-half charge fraction. Never substitute the analytic tail length for the RMS length.

A numerically stationary endpoint passes the residual criterion independently of localization. A binding witness additionally has outer fraction below tolerance, $E/(\Omega_\infty Q)<1-10^{-4}$ and $\Omega/\Omega_\infty<1-10^{-4}$. Compare both descending seeds and all three grids at every charge where a binding witness is asserted. Compare energy and RMS length with denominators $\max(1,|value|)$; boundary-clearance quantities are excluded from domain equality tests.

Find the lowest adjacent listed S0 charges whose descending searched endpoints change from no qualified binding witness to a qualified binding witness. If such a pair exists, perform exactly six arithmetic-midpoint subdivisions, solving each midpoint on all three grids with both compact seed scales. A midpoint advances the binding upper endpoint only when all required comparisons qualify; a numerically stationary diffuse/unbound result advances the searched lower endpoint. A solver/resolution ambiguity halts subdivision and returns INCONCLUSIVE for the bracket. The lower endpoint is a searched-family statement. The analytic $Q_0$, if proved, is the global sufficient no-binding bound. Missing bracketing or a failed solver cannot be described as universal nonexistence.

For listed charges with sampled constituent charges summing to the parent, report every available split-energy difference. These finite comparisons are scoped to the sampled states. The inherited continuum strict-subadditivity theorem remains a separate result for the full infimum.

Stationary verdict: SUPPORTS for independently reconstructed and converged binding witnesses; INCONCLUSIVE for unresolved numerical qualification. The receipt separately records analytic-bound acceptance, searched onset bracket, smallest qualified sampled RMS length and whether global minimum charge/radius has been established (false).

## 4. Wave preparations and evolution

Use the existing axisymmetric cylindrical finite-volume operator with volume $2\pi r\,dr\,dzeta$ and exterior Dirichlet deviations zero. Evolve deviations $(f-1,\Re z,\Im z)$ with fourth-order Yoshida-composed velocity Verlet. The independent evolution uses separately assembled finite-volume fluxes and classical RK4. No field clipping, damping, changing norm or absorbing potential is allowed.

All preparations have $f=1,\dot f=0$. A single carrier is $z=A\exp[-(r^2+zeta^2)/(2w^2)]$, $\dot z=-i\Omega_\infty z$. A pair is the sum of equal Gaussian envelopes centred at $zeta=\pm12$, multiplied by phases $\exp[\mp ik(zeta\mp12)]$ directed inward, with common initial frequency $\omega=\sqrt{\Omega_\infty^2+8k^2}$ and $\dot z=-i\omega z$. Antiphase multiplies the left packet by $-1$; outgoing reverses both wave numbers. Normalize once to the arm's total signed charge using the full superposed field. Uncoupled uses the pair256 preparation with $h_C=0$ throughout. Pair overlap is the normalized absolute envelope inner product and must be below 0.01. All claimed initially unbound arms must have $E\ge\Omega_\infty Q$; pair arms also require initial central core charge fraction below 0.10. Record initial eligibility separately from final formation.

Run every base arm on G0. Run all comparison arms on G1, G2 and T1. The independent verifier evolves all independent arms on G0 and reconstructs all primary archived states. Charge64/128 formation claims remain baseline-only unless they have the same predeclared comparison coverage; no unplanned continuation is permitted. Their role is a fixed screening sample.

Every sample records total energy, signed and absolute charge, central retained signed charge and energy, charge-weighted core RMS, mediator depletion, compact-cut charge/energy/axial momentum, binding ratio, interface-shell energy fraction, outer-boundary energy fraction, core energy/charge derivatives and outward discrete fluxes. The core is $r^2+zeta^2<8^2$. Use a cubic smooth cutoff equal to one inside radius8 and zero outside radius12 on deviations and velocities; its energy includes the cutoff-generated interface. Binding uses $\sqrt{E_{cut}^2-8P_{cut}^2}/(\Omega_\infty|Q_{cut}|)$; a negative radicand fails qualification. Core fluxes must be independently assembled from face currents and satisfy instantaneous discrete balances at every stored full state. Energy gradients are allocated half to each adjacent cell, with boundary-face energy allocated to its adjacent cell. The shell is radius12 to16; boundary energy lies within16 of any outer cylindrical boundary. The measurement domain is conservative; its exterior stores outgoing radiation. No reflection may return during the declared interval, checked through the boundary-energy criterion and the larger domain.

A late-time candidate must pass numerical qualification, preparation eligibility and every sampled time at $32\le t\le48$: retained charge fraction at least0.25, compact binding ratio below0.99, core RMS at most6, shell energy at most0.05 of initial total energy. The late range of core charge divided by initial total charge must be at most0.10. The16-unit late window is approximately5.66 core-radius crossing times at $v_*=\sqrt8$. Each reported formed candidate must also pass its prescribed resolution, domain, timestep and independent-method comparisons. A compact transient that fails the late conditions does not qualify. Baseline-only results are described without a converged formation claim.

EMERGES requires at least one fully compared coupled candidate, with its matched uncoupled control failing formation and passing numerical qualification. DOES NOT EMERGE applies when all required numerical comparisons qualify and no fully compared coupled candidate qualifies. Any required numerical failure yields INCONCLUSIVE. This is finite-time survival relative to free dispersion; general nonaxisymmetric stability, quantum creation, particle identity and a universal minimum packet count remain unestablished.

## 5. Verification, stopping and physical interpretation

Each runner and verifier has a --smoke mode for deterministic implementation controls, stored outside scientific run directories. Smokes cover energy-gradient consistency, zero-vacuum preservation, charge sign, free propagation, source identity and a known stationary reference. No smoke may scan scientific parameters or choose successful arms. The primary and independent verifier compare raw fields and observables; they must reject changed energy, changed charge, corrupt archives, missing source identity and transient-only formation claims. Rejection controls operate on copies and never alter accepted evidence.

Run the scientific schedule once. Preserve failed executions. Implementation repairs require their own output directory, the unchanged protocol hash and an explicit repair record; scientific retuning requires a distinct future preregistration. There is no automatic extension of final time, change of phase, selection of a more favourable width, or removal of a failed comparison.

No empirical normalization is selected. With dimensionless energy $\widehat E$ and size $\widehat\xi$, a physical map would require $E=E_0\widehat E$, $\xi=L_0\widehat\xi$, and $\mathcal C=[2GE_0/(c^4L_0)]\widehat E/\widehat\xi$. The action supplies neither $E_0$ nor $L_0$ nor a relation $L_0/\ell_n$. Every receipt retains complete_physical_matter_formation=false and gravitational_capture_established=false.

## References

- `computations/matter-formation-continuum-report.md` §§25, 35–36, 74–76—selected action, continuum bound and prior numerical implementations.
- `computations/matter_formation_radial.py`—spherical finite-volume energy and gradient.
- `computations/matter_formation_pool_profiles.py`—fixed-signed-charge mass-weighted objective.
- `computations/matter_formation_neutral_packets.py`—three-dimensional axisymmetric operator and time integrator.
- `computations/verify_matter_formation_pool_dispersal.py`—independent spherical and cylindrical flux operators.
- `foundations/matter-completion-boundary.md` §§7–8, 16–18—stress normalization, binding scope and stability boundary.
