# Conservative scale completion — float32 replay preregistration

Status: PRE-REGISTERED before the successor replay — 2026-09-02

The single GPU acquisition registered by `rotation_scale_completion_prereg.md` completed without a harness failure and is frozen at `_diag/rotation_scale_completion_gpu.json` with SHA-256 `b8936cb5f047be11dc365bbd78920ba1f45c22d5f3fc440b046a6dc6c6bae015`.

The first independent verifier stopped before computing G92–G96 because it compared the Godot `Vector3` seed serialized from float32 (`0.400000005960464`, `-0.200000002980232`, `0.100000001490116`) to decimal design values with a double-precision `1e-12` configuration tolerance. That receipt is retained at `_diag/rotation_scale_completion_verify.json` with SHA-256 `dcf6c4acb2d5bba4679d796f5aab86f40581142e1e3e476536a57216040a077a` and verdict `INCONCLUSIVE—IMPLEMENTATION`.

This successor performs no GPU rerun and changes no state, equation, source binding, case, seed vector, coupling, threshold, statistic, gate, or decision. It changes only the expected serialized seed representation to the exact three IEEE-754 float32 values produced by the acquisition language. The raw preregistration path remains `rotation_scale_completion_prereg.md`; the successor binds both preregistrations and the exact frozen raw hash.

The corrected verifier writes `_diag/rotation_scale_completion_verify_replay.json` and applies G92–G96 and the decision tree verbatim from `rotation_scale_completion_prereg.md`. Run it once. Any further implementation failure is `INCONCLUSIVE—IMPLEMENTATION` and stops the campaign.
