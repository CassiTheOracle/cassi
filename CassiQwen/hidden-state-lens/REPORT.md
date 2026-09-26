# What is legible in the captured hidden states — logit lens, probes, and the field's own readout

Source: the 27B Q4_K_M captures already on disk (`CassiQwen/native/llama.cpp/_diag/…`),
the 0.8B captures that use the same layout, and the field readout dumps from the
carry-forward campaign. Nothing here ran the model, modified llama.cpp, or rebuilt
anything. Every number below is measured from those files; the row marked *inference* is
the only claim that is not a reading of a receipt.

Two questions, answered separately:

1. **Can the model's own state be read?** Yes, from layer 55 onward, and it collapses to a
   single token at the end of the stack. The lens never needs training, so this part is
   unaffected by sample size.
2. **Can a trained probe read it better?** Not on this capture set. The battery holds
   133-280 capture directories but only **4-8 independent trajectories**, and the
   next-token target is constant within a trajectory, so a probe evaluated across
   trajectories is answering a question the data cannot pose. The measured evidence for
   that is below, with the counts.

## 1. The lens: reading every layer with the model's own unembedding

For each captured row we take that layer's residual, apply the model's final RMS norm and
the unembedding it actually uses at the end (`output.weight`, 248320 tokens, read from the
GGUF), and read the resulting distribution. "The model's own next token" is the argmax of
the logits captured for that exact row — free labels, no trainer.

Instrument check first, because a lens that cannot reproduce a logit it *has* would make
everything else noise: on 256 decode rows at layer 63 the lens's top-1 equals the captured
argmax for **0.977** of them, median rank 1, p90 rank 1. The machinery is right.

### 27B, width 5120, layers 32-63 (the last half of the stack)

| captured position | n | majority token | lens top-1 (L63) vs that | median p(answer): L32 → at commit → L63 | commit layer | stable run | sharpness |
| --- | --- | --- | --- | --- | --- | --- | --- |
| last prompt row | 42 | `'\n\n'`-like, 0.881 | 0.357, never beats majority | 0.0009 → 0.4559 → 0.4436 | 62 (p25 62, p75 63) | 2 | 0.18 |
| decode row of token 1 | 123 | `' that'`, 0.732 | **1.000** | 0.0002 → **0.7178** → 0.9621 | **61 (p25 = p75 = 61)** | 3 | 0.71 |
| decode row of the last recorded token | 133 | `' a'`, 0.774 | **0.955** | 0.0017 → 0.9994 → 0.9994 | 63 (p25 = p75 = 63) | 1 | 0.88 |

Readable layers (the model's own next token lands in the lens's top-5 for at least half the
states) — and the *unreadable* ones, reported rather than forced:

| position | readable | unreadable |
| --- | --- | --- |
| prompt | 33-35, 55-63 (12 of 32) | 20 layers, including all of 36-54 |
| decode-early | 52-58, 60-63 (11 of 32) | 21 layers, including all of 32-51 |
| decode | 35, 44, 45, 55, 62, 63 (6 of 32) | 26 layers |

Entropy tells the same story more sharply, because it does not depend on picking a
threshold. Median lens entropy in nats, against a 248320-token vocabulary:

| position | L32 | L50 | L55 | L56 | L60 | L62 | L63 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| prompt | 11.25 | 10.81 | 0.70 | 0.44 | 1.37 | 2.18 | 1.29 |
| decode-early | 10.74 | 10.19 | 4.87 | 3.16 | 0.20 | 0.54 | 0.19 |
| decode | 10.78 | 9.98 | 2.68 | 1.15 | 0.82 | 0.55 | **0.00** |

Through layer ~50 the residual is, as far as a linear read goes, **empty of the answer**:
~10-11 nats on a 248320-token vocabulary is very nearly uniform, which is what a
near-orthogonal projection of a mid-stack residual looks like. This is the honest form of
"early layers are unreadable" — not a weak signal, but no signal.

### The commitment curve

Definition used throughout: the first layer at which the lens's top-1 equals the model's
own next token **and stays** through layer 63. Sharpness = p(answer) at commit − p(answer)
one layer before.

- **decode row of token 1 (n=123): commit L61**, p25 = p75 = 61 — every state commits at
  the same layer, 3 layers before the end. Median p(answer) 0.00397 at the layer before
  commit → **0.7178** at commit (sharpness 0.714), and top-1 correctness goes 0.195 (L60)
  → **0.935 (L61)** → 1.000 (L62, L63). This is the one clean, tight transition in the
  whole set: all 123 states commit, none drifts back off it for the remaining three layers.
- **decode row of the last recorded token (n=133): commit L63**, i.e. at the very last
  layer, one-layer run, sharpness 0.88: 0.150 top-1 (L62) → 0.955 (L63), median p 0.1016
  at the layer before commit → 0.9994, entropy 0.55 → 0.00. The model here decides and
  executes in the same layer.
- **last prompt row (n=42): commit L62 with a 2-layer run, sharpness 0.18** — the weakest
  and least trustworthy of the three: 28 of 42 states commit, 14 never put the model's own
  token top-1 at any layer, and the lens's top-1 (0.357 at L63) never beats the 0.881
  majority token. Reading a commitment layer out of a position where the read never beats
  "always guess the boilerplate token" is not a reading; it is reported for completeness.

**Where commitment forms: L61 for the mid-generation rows, L63 (the final layer) for the
last rows, L62 for the prompt rows.** The collapse is 1-3 layers wide, and its sharpness
varies by a factor of five between the tight case (0.88) and the prompt case (0.18).

### 0.8B control, width 1024, layers 12-23

Its last half-decade of layers is genuinely *not* committed. Only L23 is readable (top-5
0.98); top-1 there is 0.327 against a 0.837 majority, so it still loses to the baseline.
Median commit layer 22.5, median sharpness 0.05, p(answer) 0.0015 at the layer before that
commit → 0.069 at commit (the L23 median is 0.038), entropy 9.39 (L12) → 7.70 (L23) —
barely below uniform. Same instrument, same
method, a stack whose captured tail has not decided. This matters for reading the 27B
numbers: the 27B's L61-63 collapse is a small-model-independent property of *being at the
end of a deep stack*, not an artifact of the lens.

### On arm vs off arm

Two controlled pairs, both with the same prompt and the same capture layout:
`steps32-on` vs `steps32-off` (named twins) and `carry-forward/runs2/epoch-0/{on,off}-p0`.

| pair | position | off commit layer / run / p at commit | on commit layer / run / p at commit |
| --- | --- | --- | --- |
| steps32 | decode-early | 61 / 3 / 0.7032 | 61 / 3 / 0.7050 |
| steps32 | decode | 56 / 8 / 0.9764 | 56 / 8 / 0.9766 |
| carry-forward p0 | decode-early | 57 / 7 / 0.8489 | 57 / 7 / 0.8427 |
| carry-forward p0 | decode | 63 / 1 / 0.4353 | never (p at L63 0.0370) |

**The field does not move where commitment forms.** Same commit layer, same stable run,
p(answer) within 0.006 at the commit layer, in every pair where the two arms are genuinely
comparable. The steps32 twins are byte-identical in their prompt captures; the carry-forward
p0 decode row is the one exception and it is not a controlled comparison — the two arms have
diverged in generated text by that layer (that is why the agreement table restricts the
comparison to the prompt and early-decode rows).

One further measured fact that supports "the field does not perturb the model's path"
(`lens-results.json → residual_reuse`: 14 groups, 246 captures compared, grouped by prompt
and next token at the first captured layer, where both arms have seen the same text). In the
largest group — 100 captures of the same decode row, layer 32 — the residuals are **2
distinct byte strings**, with a pairwise max |Δ| of 0.00851 against a row rms of 1.248, a
**0.68 %** difference; no group exceeds 0.68 % of its row rms. The arms are re-runs of one
trajectory, and the field's footprint on the residual at that layer is below one percent of
its scale.

*Inference (not measured):* the prompt position's top-1 never matching the model's own
next token while p(answer) reaches 0.44 is consistent with the stored prompt-row logits and
the captured prompt-row residual being from slightly different positions, but no receipt
in the capture set states the position of each stored logits file, so the cause is not
established here. It is the single most informative thing to fix first (see §6).

## 2. Probes: what a trained linear read can and cannot show here

Instrument: ridge (dual form, λ chosen inside the training fold on group-aware inner
splits) on per-layer residuals, group-aware cross validation where a group is one
trajectory, standardized features, **balanced accuracy** reported beside raw accuracy
because the next-token classes are 90/12/12/9, plus exactly the two controls the design
calls for: the always-most-frequent-class baseline, and a shuffled-label control that must
land at chance.

Two measurement repairs were required before any number meant anything, and both were
found by the instrument disagreeing with itself:

- **A catch-all class is not a class.** The first version folded every rare token into one
  "other" class. Two states in it share no target, so the probe can never be right on it
  and accuracy is capped by how much of the sample is rare. The superseded run printed a
  pooled accuracy of ~0.296 *flat across all 32 layers* against a 0.392 majority, and that
  artifact was overwritten by the strict-mapper run receipted here; flatness at every layer
  is the tell, because it is not a finding, it is a broken target. The mapper now keeps only
  labels with at least 8 states and drops the rest with the coverage reported.
- **The captures hold far fewer trajectories than directories.** The census is now in the
  receipt (`probe-results.json → capture_census`), because it is the sample size that
  matters:

| width | kind | capture dirs | distinct prompts | largest repeat of one prompt | independent trajectories |
| --- | --- | --- | --- | --- | --- |
| 5120 | decode | 133 | 4 | **100** | 4 |
| 5120 | decode-early | 123 | 4 | **90** | 4 |
| 5120 | prompt | 24 | 8 | 10 | 8 |
| 1024 | prompt | 49 | 6 | 9 | 7 |

A held-out trajectory then holds a class the training fold never saw, and the probe fails
*by construction*. Measured per-fold, for the 5120 decode-early family:

| fold | held-out size | held-out class | present in training? |
| --- | --- | --- | --- |
| 1 | 90 | 2 | **no** |
| 2 | 12 | 3 | **no** |
| 3 | 12 | 1 | **no** |
| 4 | 9 | 0 | **no** |

Every fold holds out a class absent from training. That is why the measured accuracy is
0.000 — and, decisively, why **the shuffled-label control also reads 0.000 with zero
variance**: it is not landing at chance, it is failing to be a control. The gate added to
the instrument refuses to report a probe below 20 independent trajectories, and keeps the
measurement in the receipt only as that evidence.

Measured anyway, for the record, at 5 folds / 4 shuffles (all marked `not_supported` in
`probe-results.json`; none of these is a claim about the model):

| probe | trajectories | classes | best-layer accuracy | balanced | majority baseline | shuffled control | verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 5120 decode-early (L32) | 4 | 4 (90/12/12/9) | 0.000 | 0.000 | 0.694 | 0.000 ± 0.000 | not supported: degenerate by construction |
| 5120 pooled (L33) | 7 | 5 (103/90/31/12/9) | 0.431 | 0.400 | 0.466 | 0.166 ± 0.344 | not supported: below its own majority and 0.8 sd above its control |
| 5120 decode | 2 | 1 (103 of 133) | — | — | 0.774 | — | not supported: one class survives, nothing to predict |
| 5120 prompt | 4 | 1 (19 of 24) | — | — | 0.881 | — | not supported: one class survives |
| 1024 prompt (L16) | 7 | 2 (41/8) | 0.950 | 0.950 | 0.792 | 0.792 ± 0.331 | not supported: 0.5 sd above a control that is just predicting the majority, over 7 trajectories |

So, plainly: **the next-token probe is not supported by this capture set**, and the reason
is now measured rather than suspected — the battery varies field settings, not prompts.

The coarser target (hedge/qualifier vs direct claim) fails even earlier, for a reason that
has nothing to do with sample size: the continuations are overwhelmingly direct claims.

| width | continuations classifiable | direct claim | hedge/qualifier | trajectories |
| --- | --- | --- | --- | --- |
| 5120 | 250 of 280 | **250** | **0** | 6 |
| 1024 | 39 of 49 | **39** | **0** | 5 |

Not one hedge in 289 classifiable continuations. A one-class target is not a probe, so no
accuracy is reported — this is the count the design asked for instead of a noisy number.

## 3. The field's own readout as a decoder (design note)

`CassiQwen/hidden-state-lens/FIELD_READOUT_DESIGN.md`, written against the pinned source
rather than from memory: a readout cell is a bounded, magnitude-free phase fingerprint of
the layer input (the first-read algebra at that point is literally independent of the
source's scale), novelty-gated so that a coherent cell stops accepting writes, and averaged
over available scales with the row zeroed wholesale below `read_floor`. Measured on the
existing dumps (6 arms, 720 tokens, 6144 readout floats per token): 45-54% of slots
available, ρ pinned at the 64 clamp in 5 of 6 arms, median cell weight **0.00**, and the
loudest cell is a near-fixed channel — in 4 of the 6 arms the top cell is the *same index
for all 120 tokens* (share 1.000, 1 distinct cell), a fifth concentrates on 5 cells, and
the pooled modal top cell still holds 57% of tokens. A decoder's address cannot be constant
across contents. The probe of those
6144 readout floats for the model's own next token scores 0.215 against a 0.262 majority
and a 0.231 ± 0.081 shuffled control — indistinguishable from both; on two binary targets
the raw accuracies are 0.567 and 0.814 but the balanced accuracies are exactly 0.500 with a
control of 0.500 ± 0.000 (against majorities 0.717 and 0.978), i.e. the probe reads nothing
and the raw number is the majority rate. The readout is a
signal the seam can consume, but it is not a name for what the model is about to say. The
one live knob in that family, the magnitude axis (`qi_read_absolute`), does change the
vector — floor-flag `abs_on` vs `abs_off`: cell-vector cosine +0.553, norm ratio 0.002,
top-cell agreement 0.0, and the `lesion` arm reads exactly zero — so the readout is not a
constant, it is simply not content-addressed.

Both the readout pre-flight and the probe shared one instrument defect worth recording,
because the *symptom* is what led to it: both folded rare next-token labels into a
catch-all class. That is not a class, and it caps accuracy by construction. The readout
probe's own numbers moved when the mapper was fixed (0.158 → 0.215, its majority 0.775 →
0.262 as the merged bucket stopped dominating the sample), and the pooled residual probe
was flat at every layer for the same reason. The verdicts did not change — no probe here
beats both controls — but the numbers quoted above are from the strict mapper.

The note's smallest decisive experiment (four arms — `off` / `live` / `live_abs` /
`lesion` — over the ~200-token generation the campaign already uses, with the `--flux-dump`
already produced) and its attention-capture requirement are unchanged, and its new §5
states the commitment window: a steering signal has to arrive before the collapse at
~L55-L61, which is 2-6 layers wide and varies per state.

## 4. What is measured here, and what is not

**Measured (readings of receipts):** every table above — per-layer top-1/top-5/rank/p,
median entropy, readable and unreadable layer sets, commitment layers and runs, on/off
agreement, the trajectory census, the per-fold class-disjointness, the probe scores and
both controls, the continuation-stance counts, the readout statistics, and the ~1% residual
footprint of the field across re-run arms.

**Inference (flagged, not evidence):** the *cause* of the prompt position's low top-1 rate
(position mismatch between the stored logits and the captured residual — not verified);
the claim that the 27B's L61-63 collapse is a property of the end of a deep stack rather
than of this model (the 0.8B control is consistent with it and is one data point); the
reading that the residual is "empty" rather than "weakly informative" at L32-50 (uniform
entropy supports it, but a nonlinear read is not excluded); and the (a)-(d) mechanism in
the design note's §3.

**Explicitly not claimed:** that the field's presence alters where or how sharply the model
commits. The controlled pairs show identical commit layers and runs, and the one pair that
differs had already diverged in text.

## 5. The single most informative follow-up

**Capture a few hundred tokens from independent prompts** (rather than many field settings
of the same prompt), with the same harness and the same two dump points already wired.
That one change buys all three things this report had to refuse: a next-token probe whose
per-layer accuracy, majority baseline and shuffled control are all meaningful; a
stance/hedge probe with two populated classes, since more prompts means more continuations
and some of them will hedge; and a commitment curve whose per-arm medians are not 4 points
deep. It costs no rebuild — the dump path exists and the field arms can be run over a
prompt set instead of a setting set — and it is the only change that converts the
`not_supported` verdicts above into measurements.

Second in value, and much cheaper: make the receipt record *which position* each stored
logits file belongs to. The prompt-position mismatch inferred in §1 is the one open
question in the lens numbers, and one field in the harness's receipt settles it.

## 6. Files

| file | what it is |
| --- | --- |
| `logit_lens.py` | lens driver: applies the final norm + unembedding per layer, writes tables, commitment aggregates, arm pairs, figures |
| `lens_common.py` | shared capture indexing, GGUF tensor reading, f32 readers, token decoding |
| `probe_decode.py` | probe driver: strict per-kind classes, grouped CV, balanced accuracy, both controls, trajectory census, trajectory gate |
| `verify_report.py` | independent check: re-derives every number in this report and the design note from the receipts, and prints PASS or the mismatches |
| `readout_preflight.py`, `readout-cells.npz` | field readout pre-flight, including the `--absolute-ab` mode |
| `inventory_captures.py` | capture inventory (438 rows) |
| `lens-states.json`, `lens-results.json` | lens inputs and outputs (per-layer tables, commitments, arm pairs, twin digests) |
| `lens-curves-w5120.npz`, `lens-curves-w1024.npz` | cached per-layer lens statistics the tables and figures are drawn from |
| `probe-results.json` | probe receipt: census, gated verdicts, and the retained measurements |
| `commitment-curve-w5120.png`, `commitment-curve-w1024.png` | per-kind commitment curves |
| `commitment-curve-arms-named-w5120.png`, `commitment-curve-arms-carryp0-w5120.png` | on vs off pairs |
| `lens-fidelity-w5120.png`, `lens-fidelity-w1024.png` | top-1 agreement and p(answer) per layer |
| `FIELD_READOUT_DESIGN.md` | §5 the commitment window; §6 attention capture; the design note proper |

`RECEIPT.json` carries the artifact and capture hashes (23 artifacts, 438 capture directories, 16.2 GB of capture files, a content digest over the receipt body with the clock stripped, and the measured/inferred split). `verify_report.py` re-derives every number in this report and in the design note from those receipts; it currently prints `ALL CHECKS PASSED`.
