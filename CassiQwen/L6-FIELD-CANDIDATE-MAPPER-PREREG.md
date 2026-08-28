# CassiQwen L6 — Field Candidate Mapper Pre-registration

## Status: FROZEN BEFORE IMPLEMENTATION—2026-08-18

## Scope

This protocol creates a pure offline mapping module in `CassiQwen/`. It consumes a caller-provided ordered candidate list and, only when explicitly enabled and supplied a valid L3-style projection, derives a deterministic candidate permutation.

It does not open a socket, start a field engine, call Qwen, modify prompts, touch llama.cpp, interpret field values as factuality, or select an answer. It is not wired into any completion path.

## Fixed mapping

Let candidates have immutable stable string IDs and let the projection contain up to eight ordered finite cells with non-negative $q$.

1. Sort candidates by ID in ascending Unicode code-unit order to create a canonical candidate domain.
2. For each projection rank $r$, compute the cell fingerprint:

\[
h_r = \mathrm{fnv1a32}(\texttt{gx|gy|gz|r}),
\]

where $(g_x,g_y,g_z)$ are reconstructed from the L5d inverse vertex map at $N=32$.
3. Add the $r$th cell’s finite $q$ to exactly one canonical candidate’s score, at index $h_r \bmod C$, where $C$ is candidate count.
4. Return candidates sorted by descending accumulated score; ties preserve their original caller order.

The projection’s geometric ranks only resolve a candidate-ordering permutation. They carry no claim about candidate truth, relevance, safety, quality, or preferred final answer.

## Disabled and invalid behavior

- `enabled=false` returns the original candidate sequence in the original order, with `applied=false`, without reading projection values.
- Any invalid candidate ID, duplicate ID, empty candidate list, malformed cell, non-finite coordinate, or negative/non-finite $q$ returns the original candidate sequence with `applied=false` and a reason.
- Invalid input never throws from the ordinary mapping call.

## Verification board

1. Disabled mode returns a candidate order exactly equal to the caller order even if projection is malformed.
2. Valid enabled mapping returns a permutation with every input candidate exactly once.
3. Identical candidates and projection produce identical output ordering and score records.
4. Candidate order ties preserve caller order.
5. Projection cell ordering changes the result under a constructed collision fixture.
6. Invalid projection and duplicate candidate IDs fail closed to the original order.
7. The L5d recorded eight-cell fixture yields a valid mapped result without any Qwen or socket call.

## Decision tree

- Any contract test failure: `FAIL`.
- All contract tests pass: `PASS`.

No field engine or Qwen server is launched. No LLM quality claim follows from this gate.
