# WaveGradientFilter Code Review

**Date:** 2026-06-07
**Scope:** `cassi/wave_gradient_filter.py`, `train_multimodal.py`, `cassi/streaming_text_sampler.py`, `debug_wave_optimizer.py`
**Reviewer:** self

---

## Executive Summary

The WaveGradientFilter integrates three ideas (IIR filtering, chakra decomposition, Newton-Schulz orthogonalization) into a coherent optimizer design. The architecture is sound and the code is well-documented. However, there are **4 critical bugs** that will cause silent failures or broken resume behavior, plus **2 high-priority performance issues** that compound the already-known OOM problems.

| Severity | Count | Status |
|----------|-------|--------|
| Critical | 4 | To fix |
| High | 2 | To fix |
| Medium | 4 | To fix |
| Low | 3 | Documented |

---

## Critical Bugs

### 1. Neuro-modulation silently dropped when mixed precision is ON
**File:** `cassi/streaming_text_sampler.py` — `MixedPrecisionTrainer.step_optimizer()`

**Problem:** `optimizer_step()` accepts `neuro_modulation` and passes it to `step_optimizer()`, but `step_optimizer()` never forwards it to the actual optimizer step:

```python
def step_optimizer(self, clip_grad=1.0):          # ← doesn't accept neuro_mod
    ...
    self.scaler.step(self.optimizer)               # ← calls optimizer.step() with no args
```

`GradScaler.step()` cannot pass extra kwargs to `optimizer.step()`. Therefore **neuro_modulation is completely ignored in the mixed-precision path**, even though `train_epoch()` provides it. It only works when `--mixed-precision` is NOT passed.

**Impact:** IIR theta shifts, LR scaling, and momentum resets from the neuroplasticizer have no effect when AMP is enabled. The optimizer falls back to default behavior silently.

**Fix:** Bypass `scaler.step()` when `neuro_modulation` is provided, and call `optimizer.step(neuro_modulation=...)` directly after the already-performed `unscale()`. Accept the trade-off that inf/NaN gradient skipping is manual in this path (but `isfinite(loss)` in `train_epoch` already guards against NaN backward).

---

### 2. Neuro-modulation not passed to WaveGradientFilter at all
**File:** `train_multimodal.py` — `train_epoch()`, line ~191

**Problem:**
```python
neuro_mod = info.get('neuro_modulation') if args.optimizer == 'iir' else None
```

This only extracts neuro-modulation for `iir`, not `wave`. WaveGradientFilter's `step()` accepts the same `neuro_modulation` dict, but it is always `None` for wave.

**Impact:** Wave optimizer never receives neuroplasticizer modulation (LR scale, theta shift, reset).

**Fix:** Change condition to `args.optimizer in ('iir', 'wave')`.

---

### 3. Resume does NOT restore optimizer state
**File:** `train_multimodal.py` — resume block + `save_checkpoint()`

**Problem:** `save_checkpoint()` now saves `optimizer.state_dict()` and `scaler.state_dict()`, but the resume block only loads the model weights:

```python
ck = torch.load(args.save, ...)
state = ck['model']
model.load_state_dict(filtered, strict=False)
# Missing: opt.load_state_dict(ck['optimizer'])
# Missing: scaler.load_state_dict(ck['scaler'])
```

**Impact:** On resume, all IIR momentum buffers (`m_prev`, `m_prev2`) are reset to zeros. This breaks temporal continuity — the filter has "forgotten" its history. For a second-order resonant filter, this is equivalent to a hard pulse reset at every resume. Training quality degrades.

**Fix:** Load optimizer and scaler state after loading model state. Guard against mismatched param shapes (e.g., after `--unfreeze-spine` changes).

---

### 4. Non-D 2D matrices ignore `ns_skip_width`
**File:** `cassi/wave_gradient_filter.py` — `step()`, line ~285

**Problem:** For matrices where neither dimension equals `self._spine_D`, the code falls back to full-matrix Muon with a fixed `steps=ns_max`:

```python
else:
    # Non-D 2D matrix: full-matrix Muon
    update = _full_matrix_muon(m_filtered, steps=ns_max)
```

There is no `ns_skip_width` check here. If a model contains a large non-D matrix (e.g., a 4096×4096 projection), it will always run NS with `ns_max` steps, creating large m×m temporaries.

**Impact:** Potential OOM on any sufficiently large non-D matrix, regardless of `ns_skip_width` setting.

**Fix:** Add a shape-based skip: if `min(m, n) > ns_skip`, skip NS and use the IIR-filtered gradient directly (with aspect-ratio scaling applied).

---

## High-Priority Performance Issues

### 5. Yang weights moved to GPU every step, for every parameter
**File:** `cassi/wave_gradient_filter.py` — `_chakra_orthogonalize()`, line ~317

```python
weights = self._yang_weights.to(device, non_blocking=True)
```

This is called inside `_chakra_orthogonalize()`, which is called once per eligible parameter per step. For 19 chakra-eligible params, that's 19 device transfers per step of a 13-element tensor. Trivial individually, wasteful and unnecessary.

**Fix:** Move `_yang_weights` to the target device once in `bind_spine()` or `__init__`, or lazily cache the device tensor on first use.

---

### 6. `fused = torch.zeros_like(m_filtered)` allocated per parameter per step
**File:** `cassi/wave_gradient_filter.py` — `_chakra_orthogonalize()`, line ~315

```python
fused = torch.zeros_like(m_filtered)
```

For a 6272×32768 parameter, this allocates ~823MB (float32) every step. For 19 params, potentially 15GB of transient allocations per step. PyTorch's caching allocator handles this, but it fragments memory and increases peak pressure.

**Fix:** Re-use `m_filtered` as the accumulator in-place instead of allocating a separate `fused` tensor. Since `m_filtered` is the IIR output and is not needed after fusion, we can overwrite it:

```python
m_filtered.zero_()  # or start with first band
# ... accumulate bands into m_filtered directly ...
return m_filtered
```

Alternatively, accumulate into `fused` but re-use it across calls via a cache (complex due to varying shapes).

The simplest correct approach: initialize `fused` as a clone of the first band (after NS/view), then add subsequent bands. This avoids the `zeros_like` allocation.

---

## Medium-Priority Issues

### 7. Missing aspect-ratio scaling for skipped chakras
**File:** `cassi/wave_gradient_filter.py` — `_chakra_orthogonalize()`, lines 333-339

When a band is skipped (`width > ns_skip`), it is used directly without the `max(1, m/n)**0.5` compensation that Muon applies. This means skipped bands have a different effective update magnitude than NS-processed bands, creating an inconsistency in the optimizer's behavior across chakras.

**Fix:** Apply aspect-ratio scaling to skipped bands too:
```python
if width > ns_skip:
    ns_update = band
    m, n = ns_update.shape[-2], ns_update.shape[-1]
    ns_update = ns_update * max(1, m / n) ** 0.5
```

---

### 8. No CLI arguments for NS tuning parameters
**File:** `train_multimodal.py`

`ns_min_steps`, `ns_max_steps`, `ns_skip_width`, and `use_resonant_ns` are hardcoded in `WaveGradientFilter.__init__` with defaults (3, 6, 4096, True). Users cannot tune them from the command line. This makes experimentation difficult.

**Fix:** Add `--wave-ns-min`, `--wave-ns-max`, `--wave-ns-skip`, `--wave-no-resonant` CLI args and pass them through `wave_kwargs`.

---

### 9. `_compute_coeffs` called per-parameter instead of per-group
**File:** `cassi/wave_gradient_filter.py` — `step()`

```python
for p in group['params']:
    ...
    a1, a2, b0 = self._compute_coeffs({**group, 'theta': theta})
```

The coefficients are identical for every parameter in a group. Computing them inside the param loop is cheap but unnecessary.

**Fix:** Hoist `a1, a2, b0 = self._compute_coeffs(...)` before `for p in group['params']`.

---

### 10. `train_epoch` loss average uses expected sample count
**File:** `train_multimodal.py` — `train_epoch()`

```python
n = n_batches * args.bs
return epoch_loss / n, epoch_pred / n, ...
```

If some batches are skipped (non-finite loss) or the last batch is smaller than `bs`, `n` overcounts. The denominator should be the actual number of samples processed.

**Fix:** Accumulate a running `n_samples` count and divide by that.

---

## Low-Priority / Style Nits

### 11. `spectral_slope_loss` is expensive and unconditionally computed for all physics batches
The FFT-based spectral loss runs on every physics batch regardless of whether it's needed. Consider making it conditional on a flag or only in early epochs.

### 12. Debug script `debug_wave_optimizer.py` uses incorrect momentum buffer reference
Line 65: `m_filtered = state.get('m_prev2') if group['order'] == 2 else state['m_prev']` — this is a debug-only profiling script, but it accesses `group['order']` correctly and is not production-critical.

### 13. `torch.cuda.empty_cache()` removed from epoch loop
This was removed (presumably for speed), but without it, long training runs may see memory fragmentation. Monitor memory usage; re-add if OOMs occur mid-run.

---

## Reliability Assessment

| Component | Reliability | Notes |
|-----------|-------------|-------|
| IIR core | Good | Same logic as proven ResonantIIR, tensor-swap pattern is correct |
| Chakra split/fuse | Good | Indexing logic is correct for both split_dim=0 and split_dim=1 |
| NS convergence | Poor | `ortho_err` 0.19–0.76 after max steps. Coefficients may need tuning for tall matrices. |
| Memory safety | Poor | Even with ns_skip=4096, 12 chakras × 19 params create heavy transient pressure. |
| Resume | Broken | Optimizer state not loaded (critical bug #3) |
| Mixed-precision integration | Broken | Neuro-mod dropped (critical bug #1) |
| Neuro-mod for wave | Broken | Never extracted for wave (critical bug #2) |

---

## Recommendations

1. **Fix the 4 critical bugs first** — they are one-line or few-line fixes with outsized impact.
2. **Fix the 2 high-priority perf issues** — they reduce memory pressure without changing algorithm behavior.
3. **Consider making NS optional per-band based on width** — The 6272-wide chakra is already skipped. Evaluate whether skipping the 3875-wide chakra (12th) further improves stability.
4. **Profile ortho_err across chakra shapes** — The poor NS convergence suggests the KellerJordan coefficients may need adaptation for aspect ratios > 5:1.
5. **Add a small smoke test** — A test that constructs a tiny HoneybeeBrain, runs 2 steps, saves/loads checkpoint, and verifies state continuity would catch bugs #1, #2, #3 at commit time.
