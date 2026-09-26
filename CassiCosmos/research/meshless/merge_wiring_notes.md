# Merge → Sim Wiring — integration findings (`particle_merge` in cassi_sim.gd)

**Status:** SIM-INTEGRATION WAVE (item 1 = particle merge), landed in `cassi_sim.gd`
behind the init-time `@export var particle_merge: bool = false` + the `_render_frame`
merge hook. Verified by `res://scenes/verify_merge_sim.tscn` (G52–G54, 5/5 PASS).
**Repo:** `godot/space-sim`. This doc records the two Godot-on-global-RD traps a future
wiring wave (BH accretion, or anyone re-homing the merge into the decoupled engine)
MUST NOT re-run into.
**Date:** 2026-08-14

---

## 1. Trap 1 — `PackedByteArray.encode_float` on a *member* byte-array silently no-ops

**Symptom.** The merge dispatched with an all-zero push constant: `N=0, phi=0, Rm=0,
gridN=0` — so every thread hit `if (int(i) >= int(pc.N)) return;` and the kernel
"ran" but touched nothing (alive stayed 0, hash count 0, best 0). The PC buffer
`_merge_pc_bytes` was the correct 64-byte size, and the *source values* were correct
(`srcN=8 srcPhi=1.618` verified), but after `_merge_pc_bytes.encode_float(0, 8.0)`
the decode still read `0.0`.

**Root cause.** `PackedByteArray.encode_float(offset, value)` (and by strong
habituation the whole `encode_float`/`decode_float` family once the array is live as a
class *member*) did not write — a silent no-op. It is not a wrong-size or wrong-offset
issue (size was 64, offset 0, float32 little-endian matched `to_float32_array`).

**Fix (verified).** Do NOT rely on in-place `encode_float` for a re-used member PC
buffer. Rebuild the PC from a fresh `PackedFloat32Array` and assign it:
```
func _merge_bind_dispatch(cl: int, pass_mode: float) -> void:
    var f := _merge_pc_values()     # 16 floats, pass_mode@15 filled below
    f[15] = pass_mode
    _merge_pc_bytes = f.to_byte_array()   # assignment, NOT encode_float
    ...
```
`_merge_pc_values()` returns the 16-float array (`N, phi, φ⁻², Q_th, R_m, ext.xyz,
grid_N, hash_nxyz, cell_w.xyz`) built by direct `f[i] = …`. This is the ONLY
reliable form on the sim's global RD.

**General rule going forward:** in `cassi_sim.gd`, when a push constant is stored in a
member byte-array and mutated per-dispatch, build it via `PackedFloat32Array →
to_byte_array()` and assign, never `member.encode_float(...)`. (The existing nbody /
poisson / md PC bytes use `encode_float` and work — but those pre-existed; the merge's
fresh member hit the no-op. If a re-home wave touches those, prefer the array-build
form to be safe.)

## 2. Trap 2 — global-RD compute lists + `buffer_get_data` only execute from the renderer's frame

**Symptom.** The merge pass opened its own `compute_list_begin()/end()` sequences and
did `buffer_get_data` readbacks (the host prefix-sum between the spatial-hash count→fill
passes needs a CPU readback). Called from `_ready` or from a verify scene's `_process`,
the compute lists never executed (alive stayed 0, cc stayed 0). Called from the sim's
`_render_frame`, they executed correctly.

**Why.** The sim's global RenderingDevice (main instance) **cannot `submit()`/`sync()`**
("Only local devices can submit and sync." — verified at runtime). Compute lists are
deferred and submitted by the renderer's frame machinery (the `_render_frame` /
RenderingServer frame submission). `buffer_get_data` on the global RD "self-stalls" and
executes pending work **only when it is invoked from the frame-submission context** —
the same reason `_sample_occupancy`'s GPU path lives at the end of `_render_frame`.

**Fix (verified).** The merge hook lives in `_render_frame` (right before the
throttled occupancy report), gated on `particle_merge && _step_count > 0 &&
! _decoupled_active`, and `_run_merge_pass()` self-stalls its per-cycle readbacks
there. The verify scene drives steps from its own `_process` and lets the sim's
`_render_frame` run the merge, then reads results next frame.

**Implication for the BH-accretion wiring wave (and any re-home into the decoupled
engine):** the user's decoupled engine runs physics on a worker *thread* with a local
RD (which CAN `submit()/sync()`). If the merge is re-homed there, the local-RD
submit/sync makes per-cycle readbacks trivially correct — but the merge mutates the
mirrored global `_pos_buf`, which the engine does not own yet. Decide the ownership
before wiring: either the engine owns the merge (needs the merge buffers + the hash
scratch inside the engine's mirror set), or the host runs it on the global RD from
`_render_frame` (current verified placement). Do NOT call it from `_ready`/`_process`
on the global RD.

---

## Files landed (item 1)

- `scripts/cassi_sim.gd` — `@export var particle_merge`; merge state vars; PC bytes;
  buffer block in `_setup_buffers` (hash sized to `R_m`, `hash_nx = ⌊2·extent_i/R_m⌋`);
  pipeline in `_setup_shaders`; uniform set in `_cache_uniform_sets` (set 0, bindings
  0–14: pos/vel + alive/mass/mom/cen + EY/EI + best/sink/cc/cs/ch/cl/mc); frees in
  `_free_buffers`/`_free_uniform_sets`/`_free_shaders`; `_run_merge_pass()` +
  `_merge_pc_values()` + `_merge_bind_dispatch()`; `_render_frame` hook.
- `compute/cassi_particle_merge.glsl` — **unchanged** (the verified standalone kernel,
  pass-mode selector 0–6).
- `scripts/verify_merge_sim.gd` + `scenes/verify_merge_sim.tscn` — NEW in-sim battery
  (gitignored, needs `git add -f`). Planted 8 particles (3 high-q pairs + 1 low-q pair,
  piecewise EY/EI field), drives 1 physics step + frames, gates:
  - **G52** merged count monotonic across frames + Σm conserved (≤1e-3 rel)
  - **G53** dead marked `pos.w = 0`, survivors {0,2,4,6,7}; dead do NOT deposit
    (Σρ after a step == Σ live masses)
  - **G54** LOW-q pair (6,7) free-streams (the φ⁻² gate blocks)

Verified `RESULT: PASS` (5/5) on the RX 7900 XTX / Godot 4.7 console exe (windowed).

## Gate numbers (item-1 run)

```
merge G52: merged count monotonic (A=3 → B=3)          PASS
merge G52: total mass conserved (≤1e-3 rel) 46→46      PASS
merge G54: LOW-q pair (6,7) free-streams                PASS
merge G53: survivors {0,2,4,6,7}                        PASS
merge G53: dead do NOT deposit (Σρ==Σlive)             PASS
checks=5 failures=0  RESULT: PASS
```

## Hand-off to the BH-accretion wave (item 2 — NOT started)

- BH accretion (`bh_accretion`, default off) needs a pass that marks particles within a
  BH's accretion radius dead (`pos.w=0`) and `atomicAdd`s their mass into `bh[base].w`
  (base = 4 + slot·2, the BH record mass field). A small new shader
  (`compute/cassi_bh_accretion.glsl`, set 0 = pos + bh) bound in `_render_frame` after
  the BH-integrate block is the clean shape. BUT — do NOT start it while the user's
  decoupled-engine refactor is mid-flight: it depends on the same dispatch/render
  regions. Re-read the new `cassi_sim.gd` dispatch structure first.
