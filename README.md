# Cassi — the unified workspace

The Cassi projects are unified around one object: a two-fluid Yang/Yin field with Qi coherence and a φ-scaled gate vocabulary. The unification proposal lives in [UNIFICATION.md](./UNIFICATION.md).

## Projects

| Directory | Project | One line |
|---|---|---|
| `CassiAI/` | Cassi AI | A standalone PyTorch project training neural field models (QiField, FluidCord) that predict next states of physics fields and byte streams. |
| `CassiCore/` | CassiCore | A TypeScript npm-workspaces monorepo of 33 packages under `@cassicore/*`: the agent-orchestration platform whose memory layer is a "MnemicField" of attractors and engrams. |
| `CassiTheory/` | Cassi Theory | The laws: a two-fluid Yang/Yin field governed by a single PDE with φ the only parameter, a φ-cascade ladder of scales, and the gate vocabulary — plus the spectral two-fluid solver and the computation pipelines. |
| `CassiCosmos/` | Cassi Cosmos | The Godot 4.7 GPU space-sim (extracted from the physics repo with full git history): runs the field itself on the GPU as a live physics engine with a TCP loopback bridge. |

## Structure

```
Cassi/                                  ← the unified Cassi monorepo
├── UNIFICATION.md                       ← the unification proposal (field-as-AI)
├── README.md
├── CassiAI/                             Python/PyTorch archive
├── CassiCore/                           TypeScript orchestration and memory
├── CassiTheory/                         laws, papers, and solvers
├── CassiCosmos/                         Godot GPU space-sim
├── CassiCraft/                          playable Cassi world
└── CassiQwen/                           field-intelligence experiments
```

The physics parent **stays** at `C:/Users/Carina/workspaces/physics` (the two-fluid Python solvers' sibling work, `research/neural_closure/`, `data/fields/*.pt`, `archive/`). It is referenced from UNIFICATION.md but is not part of this workspace.
