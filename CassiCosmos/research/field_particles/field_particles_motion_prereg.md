# Moving Field Particles Preregistration

## Status: Frozen—September 3, 2026

## 1. Question

Can the visible Field Particles mode start with two separate field objects and
show their field-derived centers moving, while retaining one canonical field
and keeping every legacy point-particle dynamics path disabled?

## 2. Registered change

The public setting is renamed from `field_particle_authority` to
`field_particles`. Its complete user-facing description is:

> Particles are simulated as moving patterns in the field instead of point objects.

When `field_particles` is enabled, the production initial condition is a pair
made from two translated copies of the pinned localized field. Each copy is
formed by translating every field's deviation from the registered vacuum; the
fixed outer shell remains the exact vacuum. The copies begin five cells to
either side of the origin and receive equal outward boosts of speed `0.25`.
Their positions and velocities remain catalog readouts from the canonical field.
No point-particle force, merge, deposit, or gravity path is added.

The existing pinned single-field verification remains available as an internal
single-seed control. It is not a second user-facing mode.

## 3. Acceptance checks

A new windowed production scene starts paused, captures the initial field
catalog, runs at least 32 shared-RenderingDevice steps with `dt = 0.01`, and
then requires:

- exactly two field objects before and after evolution;
- the left object's center moves toward decreasing x and the right object's
  center moves toward increasing x by at least `0.01` each;
- at least 98% of the pair's initial carrier charge remains;
- both leading render proxies match the two catalog centers and have visible
  weight, while every unused proxy has zero weight;
- simulator and field step counts agree;
- legacy deposit, KDK, accretion, merge, site, tree, rotation, and gravity
  paths remain unused;
- canonical state and velocity retain their exact registered byte sizes;
- the scene exits 0 with no script, shader, device, or shutdown error.

The existing single-seed focused scene and integration scene must still pass.
The configured default-off battery must remain green.

## 4. Decision rule

All checks above, both earlier field-particle scenes, and the default-off battery
must pass for `PASS—MOVING FIELD PARTICLES`. Any failure is recorded before
changing the pair construction, boost, thresholds, or acceptance bounds.
