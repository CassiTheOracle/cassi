# Separated Moving Field Particles Recovery Preregistration

## Status: Frozen—September 3, 2026

## 1. Recovery target

The first moving-pair registration failed before GPU execution because two
copies of a radius-`1.6314313` profile could not be separated on the existing
29³ domain. This recovery keeps the pinned profile unchanged and enlarges the
field domain instead.

## 2. Frozen fixture

The recovery fixture uses a 57³ grid with the pinned spacing
$\Delta x=2/7$ and extent `16.0`. Two byte-identical copies of every pinned
field deviation are embedded with centers at $x=-4$ and $x=+4$. Their outer
vacuum planes meet at the center of the larger grid, so the copies neither
overlap nor require spatial or amplitude rescaling. The complete outer shell is
the registered vacuum.

The left copy receives velocity `+0.25 x` and the right copy receives velocity
`-0.25 x`. Carrier phase and every second-order field velocity use the same
boost construction already checked by the single-field verifier. The objects
therefore begin moving toward one another.

A generated state file, velocity file, and manifest are accepted only if an
independent builder check reports:

- the pinned source-state SHA-256 unchanged;
- two embedded carrier charges matching the serialized source charge within
  `2e-7` each;
- total carrier charge matching twice the source charge within `4e-7` before
  phase rotation and within `2e-6` after float32 serialization;
- an exact vacuum outer shell;
- finite state and velocity arrays with 18 and 16 scalars per cell;
- two connected carrier-density objects with centers within one cell of
  $x=\pm4$;
- frozen SHA-256 values for the generated state and velocity before Godot use.

The accepted fixture receipt, frozen before the Godot run, is:

- source SHA-256: `5d43794099f52f4343486a2f1b38787356301153bd48d033d0d42451160ab6d3`;
- manifest SHA-256: `c07dfad59a696c2c9f9e6d474db8fb498ab100b1f7c3f5595493ca6f70b60919`;
- state SHA-256: `17b45f77d5014374a27fe806a895af2f4c56352931f201794025a6b6e4061d07`;
- velocity SHA-256: `5e203d68d9ac3e1922846c4dee9cceeddefc0b46b1bb524bd74a94bee7f5558a`;
- serialized copy charges: `3.999999962481` and `3.999999962481`;
- serialized pair charge: `7.999999882947`;
- independently recovered core centers: `-4.000000000000007` and
  `3.9999999999999982`.

Failure of any fixture check rejects the fixture without a GPU run.

## 3. Public setting

The only user-facing setting is `field_particles`, shown as **Field Particles**.
Its complete description is:

> Particles are simulated as moving patterns in the field instead of point objects.

The existing pinned single-field initialization remains a hidden verification
control. The public setting selects the separated moving pair.

## 4. Runtime acceptance

A dedicated windowed scene starts paused, captures the initial shared-RD field
catalog, runs at least 32 steps with `dt = 0.01`, and requires:

- exactly two catalog objects before and after evolution;
- the left center moves toward increasing x and the right center moves toward
  decreasing x by at least `0.01` each;
- at least 98% of initial carrier charge remains;
- the first two render proxies match the catalog and every unused proxy has
  zero weight;
- parent and field step counts agree;
- no legacy deposit, KDK, accretion, merge, site, tree, rotation, or gravity
  dispatch occurs;
- canonical state and velocity byte counts match the 57³ manifest;
- clean setup and shutdown with no script, shader, device, or resource error.

The pinned single-field verifier, its production integration control, and the
configured default-off battery must remain green.

## 5. Decision rule

All fixture and runtime checks must pass for `PASS—SEPARATED MOVING FIELD
PARTICLES`. Any failure is recorded before changing the grid, placement, boost,
thresholds, or bounds.
