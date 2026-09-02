# Embodied World-Field Intelligence Actuator-Settling Pre-registration

## Status: Frozen—2026-08-31

The frozen action-trace diagnostic sampled learned replay every 12 steps. Across all six targets, every one of the 100 supported samples outside the 0.75 success radius selected the desired signed actuator. Selected support stayed between 0.8975 and 1.0000. The policy readout is therefore stable; the v5 miss is physical settling, not learning or spatial sampling.

The trace shows the probe crossing the success region with residual velocity. Inside the region the field command is zero, so the existing RealSim viscosity is the sole brake. At the v5 value $\nu=3$, three trajectories were outside the radius at the terminal sample despite correct learned commands.

## Changed hypothesis

Use the existing physical calibration knob rather than add a second controller or direct particle impulse. Raise `realsim_viscosity` from 3.0 to 4.0 in the focused verifier and interactive demo only. For the replay transduction $u\approx d$ (`actuation / organ_radius = 1`), the linearized approach is

$$
\ddot e+\nu\dot e+\nu e=0,
$$

whose critical-damping value is $\nu=4$. The world-field shader, plasticity, action readout, actuation, targets, horizons, success radius, controls, default simulation values, ABI, and all gates remain unchanged.

## Frozen rerun

Run `verify_field_intelligence` once without diagnostic readbacks:

- learned and restored replay must each succeed on at least 5/6 targets;
- cleared and $\eta=0$ replay must succeed on at most 1/6;
- shuffled reward must succeed on at most 2/6;
- learned median terminal distance must be at most half the cleared median;
- restored terminal distances must match learned replay within 0.20 per target;
- FI0–FI9 and resource ownership must all pass.

Any miss is `REJECT`. A full battery run is allowed only after this run passes.
