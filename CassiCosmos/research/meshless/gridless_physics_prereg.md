# Gridless physics replacement — pre-registration

Date: 2026-08-19
Gate: `scenes/verify_gridless_physics.tscn`

## Question

Does the production site-native physics chain advance a finite field, particle, and condensation state without reading an `N³` field carrier?

## Frozen inputs

The gate uses the small fixed-seed scene configuration in `scripts/verify_gridless_physics.gd`: gridless physics enabled, decoupled engine enabled, 8,192 particles, 8,192 sites, site condensation enabled with threshold `0.0`, no particle merge, and three post-bootstrap steps. The condensation counter is set to `99` before the run so the first checked step exercises the three-pass site BH condensation path. The gate reads only site buffers, topology status, BH records, telemetry, snapshot state, and particle acceleration.

## Statistics

The gate records:

- topology status generation, overflow, and site count;
- finite/bounded site `q` values;
- positive finite site volumes;
- aggregate site mass sum and the fixed-point accumulator sum;
- whether any particle acceleration has nonzero finite magnitude;
- the maximum finite condensed BH slot mass;
- snapshot generation and volume-weighted telemetry q mean.

## Decision tree

`PASS` requires all of the following: topology status is ready with matching generation and no overflow; site count is positive; every checked site q is finite and in `[0, 1]`; all site volumes are finite and positive; aggregate site mass is positive; at least one particle acceleration is finite and nonzero; at least one condensed BH slot has positive finite mass; snapshot generation is positive; and telemetry q mean is finite.

Any failed condition is `FAIL`. A timeout before the completion marker is `FAIL`; no post-run threshold or parameter adjustment is permitted.

The full Godot battery is a separate regression check and does not replace this gate.
