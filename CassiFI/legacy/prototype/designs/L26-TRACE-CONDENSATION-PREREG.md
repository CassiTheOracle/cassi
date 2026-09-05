# CassiQwen L26 trace condensation and promotion

## Status: FROZEN BEFORE CONDENSATION — 2026-08-22

## Purpose

Turn durable L22 teacher traces into an atomic L23 student candidate and promote that candidate to an active checkpoint with provenance. The active checkpoint is a compact experimental artifact; it is not a replacement for the pinned native teacher.

## Frozen procedure

1. Read trace IDs in deterministic journal order.
2. Use every fifth record as a held-out diagnostic when at least two records exist; train the candidate on the remaining records.
3. Report held-out accuracy, coverage, mean confidence, source IDs, and byte/record counts.
4. Fit the final candidate on all records, write it atomically, then write an active copy atomically with the promotion report embedded.
5. Optional journal consolidation retains the latest N records per session only after the active checkpoint preserves the full source-ID list.

## Promotion rule

Promotion is structural, not quality-gated: a finite, schema-valid candidate with at least one trace record and matching model identity is promoted. Held-out metrics are diagnostics and are never used to block the experimental provider. A provider may still run in ordinary teacher mode when no active checkpoint is selected.

## Decision tree

- `FAIL`: trace replay/checksum failure, invalid field sketch, model identity mismatch, non-atomic checkpoint, or missing source provenance.
- `PROMOTE`: structural checks pass; candidate and active checkpoints are readable and carry the same source IDs.

The report must preserve the exact promotion policy and diagnostic metrics. This is a condensation/provenance result, not a claim of semantic quality or production readiness.
