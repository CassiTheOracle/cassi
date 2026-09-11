# Initial geometry and pool interpretation

## Scope

This implementation note fixes the interpretation boundary for the production
three-layer view. It does not change the frozen arm definitions or verdicts in
`research/matter_formation/trajectory_general_attractor_prereg.md`, and it does
not promote a visual layer count into a matter-formation result.

## Production initial state

`scenes/main.tscn` currently selects:

- `initial_condition = 6` (`Nested shells`);
- `initial_motion = 1` (`At rest`);
- `num_clusters = 3`;
- `cluster_separation = 1500`.

The sampler in `scripts/cassi_particle_initial_conditions.gd` uses the selected
shape branch. For shape 6 it sets

```text
shell = index % shell_count
radius = shell_inner_radius + shell_spacing * shell
```

with the current default `shell_count = 3`, `shell_inner_radius = 0.34`, and
`shell_spacing = 0.33`. The three radial populations are therefore part of the
initial condition for each component. The production view cannot by itself
show that dynamics formed three pools or selected three stationary modes.

The production configuration also starts three separated components. That
macro geometry can generate later overlaps, turning points, and density waves,
but it does not remove the seeded-shell confound. A claim that the production
view is an emergent three-shell attractor is out of scope until a shell-free
three-component control is compared with it using the same time-resolved
measurement.

## Existing controls

The calibrated scene receipts already separate two relevant cases while
preserving the three-component layout:

| Receipt | Initial shape | Components | Separation | Late profile | Scope |
|---|---|---:|---:|---|---|
| `attractor_scene_calibrated/G3` | Spiral disc (IC 3) | 3 | 1500 | one ridge in all 63 late samples | shell-free shape control |
| `attractor_scene_calibrated/G6` | Nested shells (IC 6) | 3 | 1500 | late mean has one ridge; 57/63 samples have one and 6/63 have zero | seeded-shell reference |

Both receipts are bounded under the calibrated configuration. Both retain all
8,192 particles, have zero event records, and close total mass to the recorded
precision. The G3 arm is the relevant shell-free multi-component control; its
late one-ridge profile does not establish that the production visual is an
emergent three-shell state. The G6 arm retains the IC6 shell parameters for
comparison but also does not provide a persistent late three-ridge profile.

The separate energy scan is a stronger single-cloud control: it uses one
Gaussian component with no prescribed shell radii. All eight speed/seed arms
retain one late ridge, although transient multi-ridge epochs occur. That result
constrains an energy-only explanation for a persistent shell pattern in a
single cloud; it does not identify the production scene's seeded geometry as a
new dynamical state.

## Particle pool boundary

The current trajectory probes evolve separate particles. In the relevant arms,
`particle_merge = false`, the initial and final live counts are equal, and the
zero event ledger records no demonstrated coalescence or bound composite. The
observed radial layers are therefore kinematic density maxima: particles move
through one another's radial bands, producing transient expansion, collapse,
turning-point, and phase-mixing patterns. Their repeated breathing does not by
itself demonstrate a persistent localized matter pool.

A future pool claim needs separate observables, such as a bounded aggregate or
field-localized state whose identity, coherence, or conserved charge persists
through the cycle. A bound pool could have a collective breathing mode, so
radius oscillation alone is not the discriminator. The discriminator is whether
a localized composite state exists and remains identifiable, rather than a
population of independent particles repeatedly crossing a radius.

The pool-identity measurements should include:

- provenance-preserving component labels through overlap, with each component's
  centroid and internal RMS radius tracked separately;
- connectedness or cluster membership under a declared spatial/phase-space
  relation;
- internal coherence, including velocity or field-phase alignment where the
  corresponding state is available;
- virial balance or an equivalent boundness diagnostic over the breathing cycle;
- internal size relative to centroid motion, so a coherent pool's breathing is
  separated from three independent centroids passing through one another.

## Event-time measurement boundary

The next production-scale probe must be registered separately and must include:

1. a shell-free three-component initial condition, such as Gaussian or Uniform,
   with the production separation, mass, timestep, and calibration;
2. the IC6 three-component reference with `shell_count = 3` recorded explicitly;
3. provenance labels retained through overlap, component-local centroids, and
   internal RMS radii, not only radius from the global window centre;
4. the initial radial profile, the full time-resolved ridge series, and the
   turning-point times for each component;
5. a comparison of inherited initial radii against newly appearing ridges;
6. connectedness, coherence, virial balance, internal-vs-centroid size,
   particle live-count, event, mass, and phase-space-stream diagnostics.

Only a ridge that appears after initialization, persists beyond the transient
breathing interval, and survives the shell-free control can support a dynamical
three-layer claim. Until then, the production three-layer view is compatible
with seeded nested-shell geometry plus subsequent particle motion, and the
atomic-shell analogy remains a hypothesis about a future localized mode rather
than a result of the current particle trajectories.
