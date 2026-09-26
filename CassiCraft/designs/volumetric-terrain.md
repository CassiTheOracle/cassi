# Volumetric, Multi-Scale Terrain

**Question under design:** replace the standard 1m³ block with a volumetric /
continuous terrain system that fills blocks with structure at *multiple scales
within a single 1m block*, editable with precision tools at sub-block scale.

## The core insight: the field already is the terrain

Minecraft's 1m block is a discrete state (block-id). The Cassi world is a
continuum (ρ = EY+EI, q = coherence, ε² = decoherence, all sampled anywhere).
Replacing "block" with "volume" is therefore not a bolted-on rendering trick —
it is the *natural representation* of the physics we already want:

- **Blocks are iso-surfaces of the field** — matter where ρ exceeds a
  condensation threshold, carved where ε² dominates.
- **Mining is a perturbation** — remove matter, lower local ρ, and the field
  reorganizes around the scar (terrain heals toward its attractor).
- **Ore is a scalar channel in the continuum**, not a block-id with a worldgen
  height range. It precipitates where coherence accumulates.

The domain already has no inherent 1m grid. The grid is imposed by the
rendering surface, not the physics.

## Cascade rungs = the multiple scales

The theory's cascade is *itself* a multi-scale / multi-rung structure (φ-rungs,
coarse+fine Poisson levels). That maps 1:1 onto "multiple scales of block
within a 1m block":

- A "block" is a local condensation at rung *n*.
- Inspecting or editing it opens the next finer crystallization at rung *n−1*
  (a φ-scaled refinement), and so on down.
- **Precision tools are coherence-manipulators at a chosen rung.** Tool
  resolution ⇔ rung: coarse pick ⇔ coarse rung, sculpting chisel ⇔ fine rung.
  One physics, one tool language, arbitrarily deep.

So the multi-scale demand is not a rendering hierarchy we bolt on — it is the
field's actual rung structure, surfaced as editable scales.

## Architecture: the dual world

Full field-governed geometry breaks collision, block-states, redstone, and the
entire inventory/mod block ecology — the long tail. The pragmatic spine is two
cooperating representations of the *same* field:

| Layer | Role | Substrate |
|---|---|---|
| **Geometry / render** | what you *see* and *sculpt* | field iso-surfaces (Marching Cubes / Dual Contouring), sub-block detail where needed |
| **Gameplay grid** | collision, mechanics, inventory, redstone | coarse 1m "Cassi block" grid *derived from* the field — each block carries its field value and re-quantizes as the field evolves |

The coarse grid is the compatibility layer that keeps Minecraft playable while
the volumetric layer is the living surface. The two are projections of one
continuum, so they never drift — the coarse block's value is just the field
integrated over its meter.

## Rendering / cost approach

- **Data:** never store sub-block detail densely world-wide. The field is
  sparse + sampled-on-demand: high resolution only near surfaces / where
  edited·adaptive, sparse elsewhere (an SVO is the natural fit if/when needed).
  Sub-block data *costs nothing to compute* — it is just re-sampling the field.
  It only costs to store where instanced near the player.
- **Meshing:** a dirty-chunk meshing scheduler; crack-free LOD transitions via
  Transvoxel where coarse meets fine; far LOD reuses the vanilla mesher.
- **Chunk-activity:** the meshless-site lattice doubles as the region tick map
  (see README) — mesh/regenerate where the field is active, idle elsewhere.

## Precision tools

- A brush applied to the *local* field: carve a cavity / sculpt a shape by
  editing the density scalar; hardness = threshold; ore = distinct scalar
  channel swept by the tool's rung.
- Sub-block and block-scale editing are the same operation at different rungs —
  no separate tool systems.
- The field heals around edits, so precision work is a *conversation* with the
  medium, not a mutation of a static grid.

## Honest hard problems

1. **Gameplay substrate (the long tail).** Collision, block-state machine,
   redstone, and the mod ecosystem all assume 1m discrete blocks. The dual-world
   grid is the mitigation; fully replumbing redstone/inventory to field terms is
   a large, separate design.
2. **Memory.** Dense sub-block storage world-wide is impossible. Adaptive +
   sparse + sample-on-demand is mandatory, not optional.
3. **Dynamic meshing cost at scale.** Re-meshing sculpted regions must be
   scheduled and budgeted per tick; LOD distance culling is load-bearing.

## Feasibility verdict

- Rendering/geometry as field-driven volume with sub-block detail and precision
  sculpting: **very feasible**, and it is the *right* design for a Cassi world
  (the terrain is epiphenomenal to the field anyway).
- Replacing the gameplay substrate with it: **the hard, long tail** — mitigated
  by keeping a coarse gameplay grid derived from the same continuum.
