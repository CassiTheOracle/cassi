# Field-Particle Production Integration Preregistration

## Status: Frozen—September 2, 2026

## 1. Question

Can the accepted PA12 field runtime become a default-off authoritative dynamics
mode in `CassiSim` without dispatching the legacy particle deposit, KDK,
accretion, merge, site, tree, or rotation chains and without assigning an
unselected physical mass to a PA42 carrier?

## 2. Frozen production seam

`field_particle_authority = false` remains the shipped default. When enabled:

- `CassiSim` requires the decoupled/shared-RenderingDevice engine path and uses
  a fixed observational proxy capacity of 64 slots;
- `CassiPhysicsEngine` owns one `CassiFieldParticleEngine` on the same
  RenderingDevice and records its complete coupled RK4 update as the sole
  dynamics chain;
- the legacy mass-deposit, gravity, two-fluid, condensation, black-hole,
  particle KDK, merge, site/tree, and rotation dispatches do not run;
- a publish-boundary readback derives the object catalog and writes positions
  and velocities into the existing render buffers; unused proxy slots have
  `w = 0`;
- live proxy slots use a fixed render-only `w = 1`. This value controls
  instancing visibility only and is not deposited, interpreted as mass, or fed
  back into the canonical field;
- snapshots expose canonical field state, canonical field velocity, manifest,
  observables, catalog, and explicit gravity status `unmapped`;
- PA42/PA43 gravity coupling remains absent because no physical particle mass
  or cross-sector parameter mapping is selected.

The mode forcibly disables incompatible legacy runtime toggles rather than
silently running two authoritative systems. Default-off execution takes no new
branch beyond the false mode check.

## 3. Registered focused scenario

A windowed scene instantiates the real `CassiSim` renderer with
`field_particle_authority = true`, `dt = 0.01`, and presentation extras off.
After at least 32 accepted field steps it must demonstrate:

- decoupled/shared-RD production startup succeeds;
- exactly one canonical field engine is active;
- all four legacy dispatch counters remain zero and merge cycles remain zero;
- the field step count and simulator step count advance together;
- the derived catalog contains one object;
- proxy slot zero matches that object's center and fixed render weight;
- all unused proxy slots have zero weight;
- a snapshot contains exact-size canonical state and velocity byte arrays;
- snapshot gravity status is `unmapped`;
- the window renders a visible particle proxy;
- clean shutdown emits no resource-lifecycle error.

The scene must exit 0 within 240 seconds. The prior standalone arm is rerun
after integration, followed by the unchanged full battery.

## 4. Frozen decision rule

`PASS—FIELD-PARTICLE PRODUCTION INTEGRATION` requires every focused condition,
the standalone field arm, and the full legacy battery to pass. Any failure is
recorded before changing equations, thresholds, or architecture.
