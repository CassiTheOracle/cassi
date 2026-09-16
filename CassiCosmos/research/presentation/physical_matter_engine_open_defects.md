# Physical matter engine — qualification status (measured 2026-09-10)

Verifier: `scripts/verify_physical_matter_engine.gd` (arm scene
`scenes/verify_physical_matter_engine.tscn`, receipt
`_diag/physical_matter/engine_verification.json`).

## Focused engine arm

The focused GPU qualification is green: **32/32 checks pass**. The receipt
covers the hash-bound conditional hydrogen-plasma model, conservative
initialization, hydro, atomic kinetics and emissivity, radiation transport,
moving-frame rejection, lifecycle/checkpoint behavior, and the physical
observer. PM-G4 now records a post-step rate-solve oracle and explicit
heating/exchange controls. The exchange oracle compares the global material
ledger delta with the global radiation-energy delta; cell-local deltas remain
diagnostic fields and are not silently substituted for the conservation
oracle.

The earlier Beer/slab, observer, and lifecycle findings were verifier-fixture
and accounting defects, not an accepted engine failure. They are closed by
the current focused receipt:

- Beer and slab transfer fixtures are source-controlled and use the shader's
  total-extinction convention.
- The slab uses a direct ionized snapshot so the visible CIE groups have a
  measured source.

- The PM-G5 source-function oracle follows the mode-6 update exactly:
  `source = emission / (4π c κ_abs)` and
  `T = source · (1 − exp(−c κ_abs Δt))`. With zero initial radiation, every
  ordinate receives the same absorptive target `T`; because the Lebedev weights
  sum to `4π`, `mean_after_absorption = 4πT` and
  `mean_after_absorption / 4π = T`. The scattering blend therefore adds no
  multiplier. The verifier includes the derived `emission_scale` in `T`,
  proves the full exchange remains above the thermal floor (`lambda = 1`),
  and records the scale/lambda diagnostics in the receipt.
- PM-G7 includes escaped material energy, gravity work, and the second
  momentum-boundary ledger.
- PM-G8 requires finite, nonblack live observer output.

## Production qualification remains failed

The production arm is registered at
`scenes/verify_physical_matter_production.tscn` and selects the preregistered
heating alternative for the “compression or heating” observation event. Two
clean windowed launches on the RX 7900 XTX reached the second 2,500,000-particle
decoupled setup, then lost the Vulkan device before the first qualifying
physical publication. Both processes exited with code 29 and reported a
Vulkan device loss/TDR with the last breadcrumb in the renderer
`BLIT_PASS`/`UI_PASS` path. No unchanged retry is admissible.

Under the frozen PM-G9/PM-G10 criteria, a device loss before accepted physical
steps is a production **FAIL**, not a green acceptance receipt. The focused
engine result does not promote the production arm. A future run requires a
real GPU-ownership or production-performance fix and a fresh bounded receipt.

## Scope boundary

The generated model and its SHA-bound reference identity are unchanged by the
verifier repairs. The live heating control is an explicit queued GPU event:
the engine records it into the shared compute list, commits it at the
publication fence, and exposes accepted-event counters in the publication.
Compression remains the alternative allowed by PM-G9; it is not implemented
or claimed as part of this qualification.
