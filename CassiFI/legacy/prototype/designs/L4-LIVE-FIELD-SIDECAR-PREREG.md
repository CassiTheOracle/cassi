# CassiQwen L4 — Live Field Sidecar Receipt Pre-registration

## Status: FROZEN BEFORE RUN—2026-08-18

## Scope

This protocol starts the existing unmodified CassiCosmos scene `scenes/mind_engine_cache.tscn` in a windowed Godot process and observes it through the already-tested CassiQwen L3 adapter. The scene configures a 32³ two-fluid field, `auto_step=false`, and bridge port 7599.

No CassiCosmos source, shader, scene, or project file is modified. The protocol does not use `--headless`. It does not send any mutable field command and does not contact, alter, or benchmark the Qwen server.

## Question

Can the existing mind-engine sidecar start on this Windows/AMD machine and yield one finite, bounded projection via the L3 read-only adapter?

## Fixed launch

```text
<Godot 4.7.1 Mono console executable> --path CassiCosmos res://scenes/mind_engine_cache.tscn
```

The service must bind `127.0.0.1:7599`. The process is a managed, temporary local sidecar and is stopped after the one observation.

## Fixed observation

Exactly one call:

```js
observeCassiField({ enabled: true, host: '127.0.0.1', port: 7599, projectionK: 8 })
```

The adapter may emit only `ping`, `state`, and `project` requests. It must not write to the field.

## Measurements

Record:

- sidecar readiness and startup log evidence;
- observation availability and reason if unavailable;
- state `step`, `t`, `meanEy`, `meanEi`, and `maxEps2`;
- projection cell count;
- all-finite status; and
- first and last returned `q`.

## Decision tree

1. If the scene cannot reach a ready loopback service within 120 seconds, verdict is `FAIL`; no alternative scene or flags are tried.
2. If the sole read-only observation is unavailable or malformed, verdict is `FAIL`; no retry is made.
3. If the observation is available with 1–8 finite cells and all commands are read-only, verdict is `PASS`.
4. After a `PASS` or `FAIL`, stop the managed sidecar. Any launch adjustment requires a new protocol.

## Stopping rule

One scene launch, one observation, one graceful service stop. No deposit, clear, step, snapshot, Qwen request, or parameter change.

## Interpretation tiers

- **T1 measured:** sidecar startup and one bounded projection response.
- **T2 inferred:** L3 can observe an independently running local field engine.
- **T3 speculative:** any impact of this field observation on Qwen completion or retrieval quality.

## Terminal contract

The protocol closes at `PASS` or `FAIL`. It does not open a steering or retrieval experiment.
