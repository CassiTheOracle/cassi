# Can the field's own readout cells decode the model? — design note

Scope: design only, no implementation. Everything in section 1 is read off the
pinned source in `CassiQwen/native/llama.cpp`; everything in section 2 is measured
from captures already on disk; section 3 is inference from 1+2 and says so.

## 1. What a readout cell actually is

Once per token, before that token's write lands, the field step
(`ggml_compute_forward_cassi_qi_field_step_f32`, `ggml/src/ggml-cpu/ops.cpp:11109`)
reads one complex number per mode. For mode `m` the readout is

```
cell(m) = coupling * read_gate(m) * (1/n_available) * sum_s chi_s * d_s / sqrt(rho_s)
d_s     = EY_s - phi * EI_s                 (the differential, scale s)
rho_s   = clamp(EY_s^2 + EI_s^2, 0, 64)     (the cell's energy, clamped)
chi_s   = q_s / q_max_s                     (how coherent the cell is)
q_s     = rho^2 / (rho^2 + 1/phi^2 + eps2_ema)
read_gate = mean_s(chi_s) * cross_scale_phase_agreement   (both in [0,1])
```

with `coupling = 0.5`, `phi = 1.618…`, one 9-float slot per (sequence, scale, mode)
holding `EY, EI, their velocities, eps2_ema`, `mode_count = 6144`,
`wave_mode_count = 3072` by default, 4 scales at most, and `d/sqrt(rho)` replaced by
the raw `d` when `--read-absolute` is passed
(`ops.cpp:11194-11234`, `11204-11213`; config in `src/llama-context.cpp:209-236`).
The block of 6144 floats that a `--flux-dump` writes for one token *is* these 3072
complex cells.

Four properties of that formula decide whether a cell can be a feature, and all four
are deliberate engineering choices, not accidents:

1. **The first read of a mode is scale-free and magnitude-free.** On a fresh mode the
   write gate is 1 (`!available` ⇒ `write_gate = 1`, `ops.cpp:11248`), so after the
   write `d = dt * source` and `rho = (dt*|source|/2)^2 * (1 + 1/phi^2)`, hence
   `|d| / sqrt(rho) = 2 / sqrt(1 + 1/phi^2) ≈ 1.666` *independent of the source
   magnitude* — the comment at `ops.cpp:11207` states the intent: scaling the state
   by `k` gives the same cell. A cell's first reading therefore carries the phase of
   its source pair and nothing else. Magnitude only re-enters through the
   `read_gate` and through `chi` (which saturates at 1), or by passing
   `--read-absolute`.
2. **The readout is a token-mean, not a token-sum.** `1/n_available` averages over
   the scales that are available, so raising `scale_count` does not raise the cell
   value; it averages more views.
3. **The gate is a product and it can zero the whole row.** `read_gate` is the mean
   coherence times the cross-scale phase agreement; a row is written only if
   `read_gate >= read_floor` and at least one scale is available, otherwise all
   3072 cells for that token are exactly zero (`ops.cpp:11225-11233`).
4. **The write backs off exactly where the cell is already coherent.**
   `write_gate = structured_source * (1 - q)`, `write_gain = clamp(dt*write_gate, 0, 0.5)`
   (`ops.cpp:11247-11254`): a mode that already holds a strong, coherent pattern
   accepts almost nothing new, while an empty mode accepts everything. Energy
   therefore accumulates in the modes that are already loud, and the loudest cell is
   the one that stops listening first. This is a *novelty* / habituation rule, and it
   is the single most important structural obstacle to legibility (see 3c).

## 2. What the existing captures say about the readout as a read

Measured with `readout_preflight.py` on the capture families already on disk
(`readout-preflight.json`, `readout-cells.npz`):

| reading | value | n |
| --- | --- | --- |
| cells available per state (`rho > energy_floor`) | 45-54 % of (scale, mode) slots | 6 arms |
| `rho` saturating at the 64 clamp | 5 of 6 arms | 6 arms |
| top 1 % of cells, share of total `rho` | 8-11 % | 6 arms |
| top 10 % of cells, share of total `rho` | 73-97 % | 6 arms |
| median cell weight `q` | 0.00 in every arm | 6 arms |
| median `chi` (write coherence) | 0.00 in 2 arms, 3e-5 in a third, 0.003-0.019 in the rest | 6 arms |
| flux floats exactly zero | 20.5 % (720 tokens), 95.7 % (12-token `abs_*` arms) | 6+3 arms |
| flux: largest cell is the same cell every token | 4 of 6 arms: one cell for all 120 tokens (1 distinct); fifth 0.442 over 5 cells; sixth 0.083 over 70; pooled modal 0.574 over 76 cells | 6 arms |
| cell energy vs model confidence (Spearman) | -0.075 | 720 tokens |
| field's own generated-token score vs model probability | +0.04 … +0.19 | 6 runs |
| probe cells → model's next token | 0.215, balanced 0.200, vs majority 0.262, shuffled 0.231±0.081 | 720 tokens, 5 classes, coverage 0.206 |
| probe cells → leading-space binary | 0.567, balanced 0.500, vs majority 0.717, shuffled balanced 0.500±0.000 | 720 tokens |
| probe cells → newline binary | 0.814, balanced 0.500, vs majority 0.978 | 720 tokens |

Three of those rows are the whole answer. First, the readout is *sparse and
saturated*: half the slots are empty, and where they are not empty the energy is
pinned at the clamp in five of six arms, so a cell's weight is 0 or at the ceiling
(the median cell weight is 0.00). Second, the loudest cell is close to a *fixed
channel*: in four of the six arms the maximum-energy cell is the same index for all 120
tokens, a fifth concentrates on 5 cells, and the pooled modal top cell covers 57 % of
tokens — the top of the readout is a channel, not a name for the current content, exactly
what a linear readout with a self-reinforcing (novelty-gated) write is expected to look
like. Third, the
linear-probe accuracy of the cells for the model's own next token is 0.215 against a
0.262 majority and a 0.231 ± 0.081 shuffled-label mean: indistinguishable from both
controls. The two binary targets say the same thing more sharply — balanced accuracy
0.500 with a shuffled control of 0.500 ± 0.000, i.e. the probe reads nothing at all,
while the raw accuracy (0.567, 0.814) is just the majority rate wearing a costume.

A matched A/B on the magnitude axis is already captured
(`_diag/aim-profile-floor-flag-canonical/{abs_on,abs_off,lesion,off}`: same prompt,
same 12 generated tokens, one knob — `qi_read_absolute`; the `lesion` arm's readout
is 100 % zero and the `off` arm has no readout at all). At n=12 it settles nothing
about content, but it does show the two arms consume different vectors (floor-flag
family: mean |cell| 0.000 vs 0.023, top-cell agreement 0.000, vector cosine +0.553),
i.e. the knob is live and the readout is not a constant.

## 3. What would have to be true for a cell to be a legible feature

For "cell 812 is up ⇒ the model is about to say a word beginning with a space" to be
a property of this field, four things must hold. None of them is a tuning problem;
each is about the rule in section 1.

**(a) The cell must be addressed, not just loud.** A legible feature is a cell whose
index is a function of content. Today the write is `mode ← chirp(0,mode) · layer_input[mode]`
— mode index *is* channel index, so addressing is inherited from the projection and
is already the right shape — but the readout's dependence on content runs only
through `chi`, which saturates at 1, and through the sign/phase of `d`, which the
first-read algebra of (1) makes magnitude-free. The memory of one token is a
*bounded* phase pattern.

**(b) A legible feature must be persistent across the tokens that follow.** The
oscillator advances 4 steps per token with damping `|symbol| ∈ [0.01, 0.5]`
(`ops.cpp:11271-11289`), so a written mode keeps turning for a while; but the top
cell index changes from token to token in the arms measured. Without
`--read-absolute` the amplitude of a mode's contribution is bounded by the clamp
(`rho ≤ 64`) rather than by how much of that content has accumulated, so "more about
this" cannot show up as "larger".

**(c) A cell that is loud must still be writable.** `write_gate = structured_source·(1-q)`
means a coherent cell resists. If the property of interest is established *after* the
cell has been excited (a topic that continues, a stance that develops), the cell that
should encode it has already stopped accepting. This is the structural reason the
readout can be self-confidently inert: coherence is rewarded with deafness.

**(d) A cell must be comparable to its siblings.** `1/n_available` and the
`rho`/`chi` clamps make the readout an average over available scales, and the row is
zeroed wholesale below `read_floor`. Two different contents that differ only in how
many scales are active produce the same cell value.

Conclusion: with the current rule the readout is best described as **a bounded,
magnitude-free phase fingerprint of the layer input, novelty-gated and averaged over
scales, over a state half of whose slots are empty and whose loudest channel is
usually the same channel for every token.** That is a perfectly good *signal* for the
seam to consume, and the pre-flight confirms the seam does consume it (the arms with
different readout knobs and the lesion arm produce different state/output traces),
but it is not a decoder of the model's content at this layer, and the probe numbers
above are the direct measurement of that statement.

## 4. The smallest experiment that would settle it

The read-absolute A/B is already captured but only over 12 tokens, so it cannot
answer the legibility question. The smallest *decisive* run reuses the harness
exactly as it is — no rebuild — and needs four arms over the same prompt set, ~200
generated tokens each (the size the carry-forward family already uses), with the same
`--flux-dump` the campaign already produces:

| arm | knob | the question it answers |
| --- | --- | --- |
| `off` | field not enabled | control: what does the probe score without any readout? |
| `live` | as today | baseline legibility of the current rule |
| `live_abs` | `--read-absolute` | does keeping the magnitude axis restore (b) and (c)? |
| `lesion` | readout zeroed, state still written | is any legibility in `live` coming from the readout at all, or from the state's effect on the layer? |

Measured per arm, on the same instrument as section 2: probe accuracy of the 6144
floats for the model's own next token, its shuffled-label control, the top-cell
index share, and the per-token zero share. Pre-registered falsifier: if `live_abs`
does not lift the probe above its shuffled control, the readout is not carrying
content and the next sense organ to build is attention capture, not a readout tweak.
The `lesion` arm separates "the readout is legible" from "the field's effect on the
residual is legible", which the current arm set cannot distinguish.

## 5. The commitment window

Measured from the same 27B captures the lens report uses (`steps32-*` and the
`aim-profile-floor-flag-canonical` family; 64 layers, width 5120). "Commitment" is the
first layer at which the lens's top-1 equals the model's own next token and stays there
through layer 63.

| captured position | n | commit layer (median) | stable run | p(answer) before → at commit | sharpness | lens entropy L32 → L55 → L63 |
| --- | --- | --- | --- | --- | --- | --- |
| last prompt row | 42 | 62 (p25 62, p75 63) | 2 layers | 0.235 → 0.456 | 0.18 | 11.25 → 0.70 → 1.29 |
| decode row of token 1 | 123 | 61 (p25 = p75 = 61) | 3 layers | 0.0040 → 0.718 | 0.71 | 10.74 → 4.87 → 0.19 |
| decode row of the last recorded token | 133 | 63 (p25 = p75 = 63) | 1 layer | 0.102 → 0.9994 | 0.88 | 10.78 → 2.68 → 0.00 |
| 0.8B control, 12-layer tail | 49 | 22.5 | 1.5 layers | 0.0015 → 0.069 | 0.05 | 9.39 @ L12 → 7.70 @ L23 |

**What is open and for how long.** Through layers 32-52 the answer is not merely
uncertain, it is *absent from any linear read*: the lens's top-5 contains the model's own
next token in fewer than half the states for 20-26 of the 32 layers, and its entropy sits
at 10.2-11.2 nats against a 248320-token vocabulary — a distribution close enough to
uniform that no register is legible in it. The spread of alternatives then narrows over
about four layers (median entropy at L54 → L58: 5.26 → 1.01 for the decode-early rows,
6.20 → 0.96 for the last decode row), and the residual finishes on one token: commit
layers span 37-63 across states (decode-early min 37, max 62; last-decode min 50), and
entropy at the final layer is 0.00 nats. By then the state has stopped being a
distribution and become a decision. The prompt-position row is the exception that makes
the window a property of the content rather than the depth: its entropy is already 0.58
at L53, because the token it is about to produce is boilerplate.

**What that implies for steering an attention-free register property.** A guidance signal
has to arrive while the residual still carries a spread of alternatives — before the
L54-L58 narrowing above, i.e. before ~L55 for these rows — and it has to be *sustained*
across the collapse, because the commit layer is per-state (37-63 measured) rather than a
fixed place. A signal applied at the last layers can still move a probability, but the
token it would move has already been chosen: after L62 (median entropy 0.55 for the last
decode row, 0.00 at L63) there is nothing left to steer but a rounding error. Two honest
qualifications: the window's width is a property
of where a given stack finishes deciding rather than a fixed fraction of depth (the 0.8B
control's 12-layer tail never commits at all within its own captured range — median 22.5,
sharpness 0.05, p 0.069 at the last layer), and a register property that does not change
the next token (a tone, a stance, a topic that persists) is invisible to this curve, so the
window does not bound it. The curve measures the next-token readout only.

**The field does not move commitment.** In the controlled pairs the commit layer and its
run length are identical in both arms: decode-early commits at L61 with a 3-layer run in
both `steps32-on` and `steps32-off` (p at commit 0.7050 vs 0.7032); the named decode pair
commits at L56 with an 8-layer run in both (0.9766 vs 0.9764); the carry-forward p0 pair
commits at L57 with a 7-layer run (0.8427 vs 0.8489). The one pair whose late decode curve
differs (`on-p0` at 0.037 vs `off-p0` at 0.435 at L63) has already diverged in generated
text by that point, so it is not a controlled comparison and nothing about commitment is
claimed from it. Within what these pairs control, the field's presence leaves the shape of
the collapse alone.

## 6. Capturing attention heads (the natural next sense organ)

Not needed for the logit lens or the probes, since both read the public residual
stream. The graph point already exists in the pinned build, and more of it is
exposed than the harness uses: when `cparams.cassi_capture` is set, `qwen35.cpp`
registers, per layer, the attention input (`t_cassi_capture_attention_input[il] = inpL`,
`src/models/qwen35.cpp:296-301` — the layer-input residual the harness already dumps)
and the attention delta (`t_cassi_capture_attention_delta[il] = cur` right after
`build_layer_attn` returns, `qwen35.cpp:315-319` — what the attention block itself
added), plus a head input (`t_cassi_capture_head_input = cur`, `qwen35.cpp:558-561`)
and the same pair for the FFN; `src/llama-graph.cpp:1514-1527` already marks all of
them as graph outputs. The harness, however, only writes the layer-input residual
(`tests/test-cassi-qi-latent.cpp`) and hardcodes `head_input_captured: false`
(line 998). So the cheapest next sense organ is a *dump*, not a graph change: point
one extra write at `t_cassi_capture_attention_delta[il]` (same
`dequantize → f32 → file` shape the harness already uses, one file per layer per
captured row) and flip the receipt flag. Per-head state (Q/K/V and the attention
probabilities) is *not* currently exposed — those live inside the
`build_layer_attn` implementation — so a per-head capture would need a new hook
there; the per-layer attention delta is available today.

## 7. Boundaries

Measured here: the algebra of section 1's rule as written in the pinned source; the
readout statistics and probe scores of section 2 on the named captures; the 12-token
`abs_on/abs_off/lesion/off` comparison; the commitment table of section 5 on the same
residual captures. Inference: that (a)-(d) are *why* the cells
are not legible (the statistics are consistent with that reading, and the mechanism
in section 1 predicts it, but no arm in this repo toggles (a)-(d) independently);
that attention heads would carry more legible content than the readout — plausible
from the logit lens result that the model's own residual becomes perfectly readable
at layer 62-63, and untested here; and that a steering signal present before ~L55 is
a precondition for changing the *next token*, which follows from where the collapse
sits rather than from any arm that moves it.
