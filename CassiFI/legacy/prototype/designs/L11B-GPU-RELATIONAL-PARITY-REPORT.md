# CassiQwen L11b — Typed GPU Relational Parity Report

## Status: INVALID—2026-08-18

## Protocol result

The typed declaration fixed the original parser issue and the native engine initialized. The run then failed before producing a receipt because the probe called a nonexistent method:

```text
Invalid call. Nonexistent function 'shutdown' in base 'Node (cassi_mind_engine.gd)'.
```

The aborted arm consequently returned no valid `finite` dictionary, and the parent script also reported invalid dictionary access. The old parser message visible at process startup belongs to the earlier L11 process output; the typed L11b execution reached the engine and exposed the lifecycle error above.

No Qwen request or bridge command occurred. The probe did not produce a valid field comparison.

## Terminal verdict

**INVALID.** The fixed L11b protocol cannot be retried. The current engine source has no `shutdown()` method; the successor must reuse one initialized engine and call its existing clear/reset path between arms, then free the single node after the receipt.
