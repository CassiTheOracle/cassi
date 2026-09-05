# L40 Rolling Ordered Relational Recall — Frozen Preregistration

## Status: FROZEN — 2026-08-30

L40 is frozen after preserving the complete L39 `ADOPT` and before any L40 runner, verifier, smoke, or canonical execution. L30–L39 source and canonical evidence remain immutable.

## Question

L39 established one ordered pair: the current symbol ranks first and its predecessor ranks second. Does the unchanged field roll that ordered relation forward through several distinct transitions, so that the second slot follows the immediate predecessor rather than a stale earlier symbol?

This is a capability probe of the adopted L39 operator. It introduces no field law, readout, constant, adaptive state, learned decoder, history table, or fitted parameter.

## Identity and files

Unchanged field identities:

- layout: `cassi.qi-cyclic-chromatic-coordinate-native.v1`;
- operator: `cassi.qi-ordered-relational-chromatic-recall.v1`;
- projection: `cassi.qi-cyclic-chromatic-projection.v1`.

New evidence identities:

- board: `cassi.l40.rolling-ordered-relational-board.v1`;
- traces: `cassi.l40.rolling-ordered-relational-traces.v1`;
- verification: `cassi.l40.rolling-ordered-relational-verification.v1`.

New files:

- `verification/run_l40_rolling_ordered_relational_recall.py`;
- `verification/verify_l40_rolling_ordered_relational_recall.py`.

No new field module is permitted. The runner imports the immutable L39 controller directly.

## Frozen canonical schedule

Canonical execution uses the existing RX 7900 XTX PyTorch/ROCm device, float32, seven channels, `mode_count=2048`, `alphabet_size=260`, batch size eight, trust `1`, and eight evolution steps per tick.

For the inherited L30 target vector

`S0 = (0, 37, 74, 111, 148, 185, 222, 259)`,

define

- `S1[b] = (S0[b] + 97) mod 260`;
- `S2[b] = (S0[b] + 181) mod 260`;
- `S3 = S1`.

All three symbols are distinct within every row. The fixed rolling schedule is:

1. heartbeat once;
2. deposit `S0` for one eight-step tick;
3. evolve sixteen blank eight-step ticks;
4. deposit `S1` for one eight-step tick;
5. evolve sixteen blank eight-step ticks;
6. deposit `S2` for one eight-step tick;
7. evolve sixteen blank eight-step ticks;
8. deposit `S3` for one eight-step tick;
9. evolve sixteen blank eight-step ticks.

Record a checkpoint immediately after each deposit and after its sixteen-tick blank horizon. There are eight checkpoints in this order:

- `s0-deposit`, `s0-horizon`;
- `s1-deposit`, `s1-horizon`;
- `s2-deposit`, `s2-horizon`;
- `s3-reversal-deposit`, `s3-reversal-horizon`.

Expected categorical slots are:

- stage `S0`: current `S0`, no available predecessor;
- stage `S1`: current `S1`, predecessor `S0`;
- stage `S2`: current `S2`, predecessor `S1`;
- stage `S3`: current `S1`, predecessor `S2`.

The final stage is an explicit reversal. Success therefore requires direction-sensitive order, not mere membership in the recently seen set.

## Frozen traces

The raw NPZ contains, without pickle:

- all eight checkpoint fields as float32;
- the shared phase codebook as float32 real/imaginary pairs;
- expected current symbols for every checkpoint and row;
- expected predecessor symbols, using `-1` where unavailable;
- controller current symbols, relational symbols, relational availability, ordered scores, clamp counts, maximum input-energy drift, and maximum absolute field value.

The board binds every source hash and the trace hash. JSON is canonical and finite; writes use atomic sibling replacement.

## Mechanical gates

The independent NumPy verifier must establish:

1. source, preregistration, board, and trace identities and hashes match;
2. device is a real AMD ROCm GPU and dtype is float32;
3. every required array has its frozen shape and dtype and contains finite values;
4. direct NumPy reconstruction of the L31 current scores and L38 relational scores from each stored field equals the runner tensors within float32 tolerance;
5. direct categorical reconstruction of L39 ordered scores, current symbols, relational symbols, and availability equals the runner tensors;
6. readout never changes stored field state;
7. all tick clamp counts are zero, maximum input-energy drift is at most `2e-6`, and maximum absolute field value does not exceed the immutable L39 bound.

## Functional gates

For every row at both checkpoints of every stage:

1. emitted and diagnostic current symbols equal the frozen current vector;
2. stage `S0` reports no relational availability and contains exactly one categorical slot, score `3`, at the current symbol;
3. stages `S1`–`S3` report relational availability and the relational symbol equals the frozen immediate predecessor;
4. stages `S1`–`S3` rank exactly `[current, predecessor]` as top two with categorical scores `[3, 2]`;
5. no other symbol has score at least `2`;
6. at `S2` and `S3`, the older nonadjacent `S0` symbol is not the predecessor slot unless it is also the current symbol, which the frozen vectors exclude.

All rows and all checkpoints must pass. No averaging may hide a failed row.

## Decision rule and stopping rule

Return:

- `ADOPT` only if every mechanical and functional gate passes;
- `REJECT` when mechanics pass but any rolling-order functional gate fails;
- `FAIL` for malformed, non-independent, non-finite, hash-invalid, or mechanically inconsistent evidence;
- `INCOMPLETE` only when canonical evidence is unavailable or interrupted.

Run existing L39 CPU contracts and Python syntax checks first. Then run one canonical RX 7900 XTX board and one independent verifier. Preserve the first complete verdict. Any change to the schedule, symbols, checkpoints, gates, L39 field source, readout, or constants requires a new preregistration.