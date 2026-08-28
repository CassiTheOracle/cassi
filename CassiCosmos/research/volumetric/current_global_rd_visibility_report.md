# Current global-RenderingDevice visibility report

**Status:** Present-state measured snapshot, 2026-08-19. Verification used the Godot 4.7.1 console runner on the RX 7900 XTX. Windowed scene arms were run one process at a time; the battery runner was the only headless invocation.

## Live render receipt

The normal `scenes/main.tscn` renderer was launched with 200,000 particles. Particles remained visible after startup, the HUD reported live values (`Mode: Particles`, advancing `Step`), and the renderer-owned MultiMesh stayed populated. The decoupled path latches visibility after its first populated render buffer and seeds the renderer buffer before GPU-direct writes.

The live site-direct query path rendered visibly at approximately 8 FPS on this rig. That rate includes the current CPU publication of the site/hash query and is a measured performance baseline, not a claim of a finished high-throughput renderer.

## Global-RD meshless policy

A controlled probe isolates a renderer-ownership boundary: executing the meshless rebuild dispatch chain on the renderer-owned global RenderingDevice blacks out raster rendering even when positions, transforms, alpha, camera projection, and MultiMesh visibility remain valid. A cell-mode-7-only probe reproduces the blackout; that mode writes meshless volume/centroid buffers and does not alias the MultiMesh buffer. The global owner therefore never records that rebuild chain.

The safe render-topology ownership path is now:

1. Before the global frame list opens, `publish_render_query()` stages the tile-local site positions, shortlist, site count, and CPU-built spatial hash into the global render-query buffers. Window translations shift and republish this query payload at the frame boundary.
2. `service_render_topology()` snapshots the current site field/gradient arrays and submits them to `scripts/cassi_meshless_topology_worker.gd`.
3. The worker creates its own local RenderingDevice on its worker thread and runs open-tile Voronoi/JFA labels, adjacency, CSR offsets/neighbors, and optical payload construction with local barriers and local submit/sync.
4. The global owner uploads one completed topology generation before the next global render list and latches `_topology_ready`, generation, site count, required-neighbor count, and overflow together.
5. The site-native volume renderer consumes those global topology buffers; it never executes the blackout-triggering rebuild chain on the global device.

The worker is deliberately a **render-topology** worker. The live two-fluid physics and particle chain still own their global physics/grid buffers; the worker does not rewind or replace that evolving state.

## Rendering attachment boundary

The live decoupled renderer no longer calls `_render_field_slice()`. In field mode it uses the site-native volume path once the worker publishes a valid topology generation; before that first generation it keeps the particle presentation rather than dispatching against empty topology buffers. The raster-grid field attachment remains only for explicit inline compatibility paths.

The grid buffers have therefore been removed from the live decoupled rendering dependency, not deleted from the physics engine. They remain required by the two-fluid physics chain, condensation/BH/river readers, telemetry, diagnostics, and explicit compatibility arms.

## Verification receipts

Focused receipts after the change:

- `verify_particle_vfx.tscn`: 8/8 checks passed, including decoupled initial visibility.
- `verify_meshless_stability.tscn`: PASS.
- Moving-window topology probe: PASS; render-query generation `1 → 2`, topology generation `1 → 2`, 8192 sites, query payload changed after a +30 x translation, topology remained ready.
- Site-volume worker probe: PASS; topology generation 1 was consumed by volume dispatch 1, sentinel `0xC4551A5E`, executed generation 1, valid render texture.
- Live main-scene smoke: visible 200,000-particle renderer with advancing HUD step and site-direct colors.

The complete runner executed all 33 registered arms serially:

```text
33/33 PASS (total 246 s)
```

Known AMD shader notices (`OpArrayLength` and `OpAtomicFAddEXT` unsupported-operation messages) remained informational and did not fail an arm.

## Boundary

The live decoupled render dependency is now site-query/topology driven rather than raster-field driven. The remaining grid users are physics, telemetry, diagnostics, and explicit inline compatibility arms. Removing the grid from the entire simulation is a separate physics migration: it requires a solver-side local topology/state-remap path and an independently verified replacement for every grid-backed physics consumer, not a renderer-only buffer deletion.
