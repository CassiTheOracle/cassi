# CassiQwen L5 — Seeded Projection Scene Report

## Status: FAIL—2026-08-18

## Protocol result

`L5-SEEDED-PROJECTION-SCENE-PREREG.md` required one windowed scene launch and one live read-only observation. The launch did not reach readiness, so no observation was issued.

## Failure record

The initial CassiQwen-owned launcher attempted to load the engine through a relative resource path from a separate Godot project. Godot rejected the cross-project `res://` reference. A subsequent standalone-script attempt exposed a launcher lifecycle parse error: `SceneTree` does not provide `get_tree()`.

Neither failure reached the engine, bound port 7599, sent a bridge command, or contacted Qwen. No field state was modified.

## Terminal verdict

**FAIL.** The L5 protocol explicitly treats scene parse or startup failure as terminal. It is retained as the record and will not be retried.

## Successor boundary

The correct replacement is a fresh protocol that changes only the launcher packaging: run the CassiQwen-owned `SceneTree` script through the CassiCosmos project, where its engine resource is canonically available at `res://scripts/cassi_mind_engine.gd`. The fixed seed, grid, single step, bridge commands, acceptance criteria, and stop rule remain unchanged.
