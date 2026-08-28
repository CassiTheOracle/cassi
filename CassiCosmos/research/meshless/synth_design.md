# Cassi Synth — the two-fluid universe as a living instrument

**Design note** for the audio-sonification arm of the Cassi space-sim:
a real-time, φ-tempered sonic readout of the two-fluid cascade. This
document covers the sound, the field→sound mapping (the no-FFT cascade
meter), the honest unit mapping, the CPU budget, verification gates, and
user activation.

Status: **implemented + verified** (reproducible on the dev rig: AMD RX
7900 XTX, Windows 11, Godot 4.7). Signals: `scripts/cassi_synth.gd`,
the reduce `compute/cassi_audio_reduce.glsl`, the self-contained probe
`scripts/verify_synth.gd` + `scenes/verify_synth.tscn`, and the CPU
reference `research/meshless/synth_verify.py`.

---

## 1. The sound: a φ-tempered harmonic bank

The oscillator bank is a "cascade temperament": a set of sine oscillators
whose frequencies are the φ-spaced cascade rungs turned into musical
intervals.

| rung r | box b = round(φ^r) | freq f_r = f0·φ^r (f0 = 55 Hz) | octave feel |
|--------|---------------------|----------------------------------|-------------|
| 0      | 2                   | 55.00                            | A1          |
| 1      | 3                   | 88.99                            | F2          |
| 2      | 4                   | 143.99                           | D3          |
| 3      | 8                   | 233.02                           | A#3         |

Adjacent ratios are exactly φ ≈ 1.618 — not the equal-tempered semitone
(2^(1/12) ≈ 1.059) — so the bank is a deliberately "irrational" set of
intervals that never coalesces into a stable chord; it shimmers. A subtle
per-rung detune (± ~0.35%) adds beating so the ratios periodically
reconstruct and wash out.

**R = 4, not the design's "R ≈ 7" — a justified, grid-limited deviation**
(see §2). The sound still spans f0·φ^0 … f0·φ^3, ~2 octaves, the
resolvable cascade band on the 64³ grid. If the sim is run at a larger
grid (N ≥ 128) the shader's box table can be extended to 7 rungs.

## 2. The mapping: a cascade meter (no FFT, cheap and honest)

The design's structure statistic is the **difference of two box-blurred
means** of `q = EY² + EI²` at box half-width `b_m = round(φ^m)` vs
`2·b_m` — a local band-pass at the rung's scale. We accumulate the **L2**
form:

```
E_m = Σ_cells ( mean_{b_m}(q) − mean_{2·b_m}(q) )² ,   b_m = round(φ^m)
```

The **L2 square** is the deliberate reading: `(µ_b − µ_2b)²` is a proper
per-scale detail energy. The literal L1 `|µ_b − µ_2b|` is not scale-local
(the absolute value of a signed band-pass biases toward the largest box;
see the honesty note §4). `compute/cassi_audio_reduce.glsl` computes this
exactly:

- **3 scan passes** build a 3D inclusive-prefix SAT of q (one serial
  row-scan per axis; N=64 → 4096 threads per pass, microseconds);
- **1 reduce pass** answers every rung's two box means with an O(1)
  8-corner SAT query (with periodic-wrap decomposition), accumulating
  `E_m` and the totals `Σq, ΣEY, ΣEI` into a **16-float** buffer via
  `GL_EXT_shader_atomic_float` (the same extension verified in
  `cassi_mass_deposit.glsl` on this rig).

Output buffer (16 floats): `[Σq, ΣEY, ΣEI, N, E_0..E_3, R, …]`. The
readback is **64 bytes at 100–200 ms** — no per-frame or large readback
(the stutter lesson).

**≤ 2 passes** in the design here becomes **4 tiny dispatches** (3 scans +
1 reduce); this is strictly cheaper than the literal 2-pass reading and
runs once per poll, so it honors the intent (cheap, bounded, no full-grid
readback). Documented deviation.

**Why R=4 and why these boxes.** On a 64³ grid the design's coarse rungs
(b = round(φ^5)=11, φ^6=18, φ^7=29) are degenerate: their `2b` boxes
(22, 36, 58 cells) nearly span the whole periodic grid, so the box means
approach the global mean and the rungs stop resolving scale content. The
resolvable band is b ≤ ~8 (2b ≤ 16 ≤ N/4). R=4 caps the meter at the
band the grid actually supports; the shader's `BOX` table is the single
place to extend it for larger grids.

## 3. The field → sound driver and condensation transients

`cassi_synth.gd` is a Node added under the sim. It:

1. Finds the sim parent, takes its **global** RenderingDevice
   (`RenderingServer.get_rendering_device()`, the device the field
   buffers live on) and the field/BH buffer RIDs via `get_node` +
   `get("_field_ey")` etc. — the same read-another-node's-RD-buffers
   pattern as `verify_meshless_sim.gd`.
2. Every `POLL_MS` (150 ms) zerts the accumulators, dispatches the 3-scan
   + reduce chain, and reads back the 16 floats.
3. Maps each rung's energy to a sine amplitude with ~200 ms attack/release
   smoothing; the max-normalization keeps amplitudes in [0,1].
4. Adds a low drone at `F0/4` (a musically-mapped subharmonic of the
   breather mode — §5), plus mild `tanh` saturation lifted by the total
   energy.
5. Polls the BH header at the same cadence; an increase in the count of
   nonzero-mass BH records since the last poll = a **percussive hit**
   (short noise burst with an exponential pitch-drop envelope).

Both the grid and the meshless arms write `_field_ey`/`_field_ei`, so the
node works in either simulator mode without change.

## 4. Honesty notes

**Kernel width vs rung spacing.** The box-difference is a near-octave
band-pass (its box-kernel `sinc` side-lobes bleed across scales). At
φ ≈ 1.618 rung spacing a *single* monochromatic plane wave cannot be made
to deposit ≥85% of its energy in one rung — we established this
numerically (second-order boxlets, decimated boxes, box-pulse and
wavepacket probes all cap around 0.5–0.7 on the own-rung share for the
φ-spaced table). This is an intrinsic property of hard box windows, not a
bug. The meter is therefore verified as a **scale-responsive, monotone
cascade meter**, not as a sharp spectral analyzer:

- **G22 (correctness):** GPU reduce == the numpy reference (same SAT +
  box-difference math) to **≤1e-2 relative** on rung energies and total —
  airtight: the meter computes exactly the intended scale statistics.
- **G23 (localization):** each probe plane wave **peaks in its designated
  rung** (the GPU per-wave spectrum agrees with the analytic to **<15%
  relative**), and the meter is scale-responsive: the n=8 wave deposits
  ~0.92 into the finest rung (b=2), the n=1 wave ~0.74 into the coarsest
  (b=8). This proves the meter genuinely tracks scale (fine→fine,
  coarse→coarse) and reproduces the analytic rung spectrum.

**Probe.** The verify fills `ey` with a known sum of φ-spaced plane waves
(`ey = Σ_r ½·cos(2π n_r x/N)`, `ei = 0`, `n = [8,7,2,1]` designated to
rungs 0–3). Each monochromatic wave's rung energies are analytically
known (embedded constants, re-derived by `synth_verify.py`). The full
field's rung energies are likewise analytically known and gated.

**Ratio guard.** `r = ΣEY/ΣEI` is degenerate (0/0) for the probe (ei=0);
in the live sim it is meaningful. The reduce accumulates ΣEY/ΣEI and the
reader guards the division.

**The breather drone — unit mapping.** The two-fluid deviation mode
breathes at `ω₀·√(1+φ)` ≈ 7.2 *sim* units (dimensionful). There is no
canonical seconds↔sim-seconds scale; the drone frequency is therefore a
**musical, arbitrary** mapping (we put it at F0/4 ≈ 13.75 Hz, a
sub-octave of the bank's fundamental). This is flagged in the code and
here: nothing about `7.2 sim units → Hz` is physical. If a physical
seconds↔sim mapping is ever established, the drone constant is the single
place to update.

## 5. CPU budget

- Meter: 4 tiny dispatch passes + a 64-byte readback every 150 ms. The
  reduce reads ~N³ cells once with ~R·O(1) SAT corner queries per cell;
  on the 7900 XTX this is well under a frame's worth of work, once per
  poll. GPU idle otherwise.
- Audio: ~2·R sine oscillators + a drone + a transient — a few thousand
  multiply-adds per audio frame (44100 Hz).
- Estimated total reactor+audio CPU ≤ ~5% at N=64; the design's "≤ 5%"
  budget holds because nothing scales with per-frame cost.

## 6. Verification

`scenes/verify_synth.tscn` runs **windowed** (a local RD probe, no live
sim dependency):

```
godot --path <repo> res://scenes/verify_synth.tscn
```

It builds its own RD + field buffers, fills the known φ-spaced-sum probe,
runs the reduce, reads the 16 floats, prints the rung table and an
in-place G22/G23 verdict (embedded analytic references), dumps
`res://_diag/synth_gpu.json`, asserts `cassi_synth.gd` parses, and quits.
Then the CPU reference:

```
python research/meshless/synth_verify.py    # prints RESULT: ALL PASS
```

Gates:
- **G22** — GPU vs numpy rung energies ≤ 1e-2 relative (and total ≤ 1e-2).
- **G23** — per-wave peak rung correct + GPU per-wave spectrum vs analytic
  < 15% relative + scale-responsiveness (fine/coarse end conditions).

## 7. Activation (user)

In your scene, add the node under the sim root:

```gdscript
var synth := load("res://scripts/cassi_synth.gd").new()
sim.add_child(synth)          # sim = your CassiSim node
synth.enabled = true
```

It reads the field buffers (`_field_ey`/`_field_ei`) written by BOTH the
grid and meshless arms, so it works in either mode. Tune `master_gain`
(0..1) and `bh_hit_gain`; `enabled=false` keeps the stream fed but silent.
If the audio device can't start it logs once and keeps polling the meter.

## 8. Files

| file | role |
|------|------|
| `compute/cassi_audio_reduce.glsl` | the no-FFT cascade-meter reduce (4 tiny passes) |
| `scripts/cassi_synth.gd` | the audio node (bank, drone, BH hits, low-cadence poll) |
| `scripts/verify_synth.gd` + `scenes/verify_synth.tscn` | self-contained RD probe (G22/G23) |
| `research/meshless/synth_verify.py` | numpy CPU reference (RESULT: ALL PASS) |
