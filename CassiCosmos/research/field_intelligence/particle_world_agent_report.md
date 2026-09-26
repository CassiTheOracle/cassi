# Unified Particle World Agent Report

## Status: ADOPT — 2026-09-01

Pre-registration: `research/field_intelligence/particle_world_agent_prereg.md`

## Verdict

**ADOPT.** The unified Workbench, decoupled authoritative executor, provider round trip, player-facing controls, exact Undo, focused verifier, and complete regression battery all satisfy the frozen correctness gates. PWA11 records a bounded shipped-count Apply latency as a measured limitation; neither measured run produced device loss, TDR, or an operation near the existing 240-second per-arm timeout.

## Gate outcomes

| Gate | Outcome | Evidence |
|---|---|---|
| PWA0 | **PASS** | Manual controls and provider-staged chat programs both normalize and execute through `FieldWorkbench`; neither the UI nor provider has a second particle mutation path. |
| PWA1 | **PASS** | Focused Python and GDScript coverage verifies exact selected counts, deterministic generators and point-cloud resampling, strict finite/schema/limit validation, and rejection before writes. |
| PWA2 | **PASS** | With no staged command, the normal simulation and complete battery retain their established execution path; the particle-program dispatch is invoked only by explicit Workbench Apply. |
| PWA3 | **PASS** | The focused decoupled fixture and live 2,500,000-particle receipt both report `backend: authoritative_gpu`; engine-owned buffers, rather than simulation mirrors, are the mutation authority. |
| PWA4 | **PASS** | Apply preserves particle count and mass, produces finite target state, matches the deterministic ring assignment, and leaves non-particle/grid-compatibility buffers unchanged for the particle-only command. |
| PWA5 | **PASS** | Position changes invalidate cached acceleration/gravity state, refresh render snapshots, and remain finite through one explicit post-Apply step. |
| PWA6 | **PASS** | Preview returns the canonical digest, affected count, bounds, bounded target sample, RMS error, and maximum displacement while all seven supported authoritative buffers remain byte-identical. |
| PWA7 | **PASS** | Automatic Undo restores position/mass, velocity, acceleration, field, grid velocity, cached acceleration, clock, and pre-Apply digest byte-for-byte. |
| PWA8 | **PASS** | The real checkpoint-backed provider stages the adoption request as a canonical ring program and returns a field response without mutating the world before local Apply. |
| PWA9 | **PASS** | The matching Apply receipt is observed by the same provider session exactly once; identical retries are idempotent and conflicting request/result digests reject. |
| PWA10 | **PASS** | The ordinary `scenes/main.tscn` Workbench exposes and exercises Send, Preview, Apply, Undo, Pause/Resume, staged digest, provider status, and visible result status. |
| PWA11 | **PASS—MEASURED LIMITATION** | At 2,500,000 particles the baseline measured normalization `0.199 ms`, readback `97.158 ms`, authoritative GPU write `42.532 ms`, Preview `5639.700 ms`, Apply `11300.346 ms`, and one step `3442.876 ms`. The allowed repair precomputed reusable curve bases and reused resolved targets; the rerun measured normalization `0.192 ms`, readback `35.923 ms`, write `42.528 ms`, Preview `4572.929 ms`, Apply `7702.721 ms`, and one step `3005.682 ms`. Apply is a bounded paused edit; neither run produced device loss, timeout, or TDR. |
| PWA12 | **PASS** | Final focused verifier exits 0. Focused Python run: `40 passed in 8.34s`. Final Cosmos battery: `38/38 PASS`, exit 0, `252 s`; `verify_particle_world_agent` is arm 38 and passes in `2 s`. |

## Live workbench receipt

The ordinary `scenes/main.tscn` workbench was paused at step 0 and sent:

> Arrange the selected particles into a ring around the orange cursor, radius 5

The provider staged digest `17de759ffb205eeae7a116ec07916292468ce2def41b72a5b57ddf2705745d3b`, Preview accepted all 2,500,000 particles with maximum displacement `449.4941`, Apply returned `backend: authoritative_gpu`, and `/v1/world/result` stored `status: applied` with no error for request `world-1788320316-721`. The UI displayed `Provider observed the applied world result exactly once`.

## Stopping-rule disposition

The one allowed implementation repair and rerun are consumed. The repaired Apply is materially faster but remains a visible `7.703 s` paused operation at the shipped 2,500,000-particle count, so that latency is retained as the PWA11 measured limitation. All hard gates PWA0 through PWA10 and PWA12 pass, and PWA11 has no device loss, TDR, or timeout; the frozen verdict is therefore `ADOPT`.
