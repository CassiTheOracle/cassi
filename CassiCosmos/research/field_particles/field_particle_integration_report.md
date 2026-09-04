# Field-Particle Production Integration Result

## Status: PASS—September 2, 2026

## 1. Registered run

`res://scenes/verify_field_particle_integration.tscn` instantiated the real
`CassiSim` renderer on the RX 7900 XTX with the field-authoritative toggle on.
The shared global RenderingDevice bootstrap completed, the PA12 engine loaded
its pinned state, and the scene reached 32 accepted field steps before the
registered checks ran.

The complete scene exited 0 in 15.3 seconds. Setup reached the field engine in
2.905 seconds. The visible surface showed one centered red particle quad on the
Cassi night background; this is the existing instancer consuming the derived
proxy, not a second particle state.

## 2. Runtime measurements

- simulator step count: 32;
- canonical field step count: 32;
- publish-boundary proxy refreshes: 3;
- derived object count: 1;
- proxy capacity: 64;
- active proxy weight: exactly `1.0`;
- all 63 unused proxy weights: exactly `0.0`;
- canonical state snapshot: 1,756,008 bytes;
- canonical velocity snapshot: 1,560,896 bytes;
- gravity status: `unmapped`;
- legacy field-engine dispatch counts: deposit 0, KDK 0, accretion 0, merge 0;
- central merge cycles: 0;
- central tree full builds and hierarchical refits: 0.

Proxy slot zero matched the catalog center within the registered `2e-5`
tolerance. Clean scene shutdown emitted no field-engine resource error.

## 3. Verdict

**PASS—FIELD-PARTICLE PRODUCTION INTEGRATION.**

The default-off production mode records the coupled PA12 RK4 chain as its sole
authoritative dynamics path and publishes only observational objects into the
existing renderer. No carrier charge, PA12 energy, catalog radius, or render
weight is promoted to gravitational mass. Gravity remains explicitly unmapped
until PA42/PA43 supplies a physical cross-sector identification.
