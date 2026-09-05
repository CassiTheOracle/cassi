# CassiQwen L24 learned correction

## Status: FROZEN BEFORE POLICY ACCEPTANCE — 2026-08-22

## Purpose

Exercise an explicit experimental provider mode in which a compact field-conditioned shadow student may replace the teacher's selected token for a bounded number of positions. The native Qwen output path remains available and remains the default. This is a control-path and persistence experiment, not a language-quality or safety claim.

## Frozen contract

- The teacher trace schema is the L22 SQLite journal; each record carries a 128-value float32 field sketch, selected token, and compact top-k receipts.
- The L23 student is a cosine-prototype learner over observed teacher labels. It cannot invent an unobserved token ID.
- `cassi_student_mode=corrective` is opt-in and defaults to one correction per request.
- The correction budget is explicit and bounded by `max_tokens`; confidence is reported, not used as a language-quality gate. The default threshold is `0.0`.
- `shadow` records predictions without changing committed tokens. `corrective` may commit the observed student label. Ordinary provider mode is unchanged when the option is absent.

## Measurements

Record `student_prediction`, confidence, source label count, `student_applied`, committed token ID, field step, field hash, and teacher-call status for every event. Verify the checkpoint and trace journal remain writable after correction.

## Decision tree

- `FAIL`: malformed student checkpoint, non-finite sketch, missing prediction receipt, or an unbounded correction.
- `PASS`: shadow mode leaves the committed path untouched and corrective mode applies exactly the requested bounded budget when a student prediction is available.

This decision is mechanical. It does not gate use of the opt-in experimental provider and does not claim output improvement.
