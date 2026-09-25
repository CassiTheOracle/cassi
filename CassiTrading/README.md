# Cassi Trading

## Canonical field runtime

`cassi_trading_field.py` turns a chronological market stream into experience
in Cassi's `cognition.field`. The current entity-hosted path attaches the
`cassi-trading` regional computer to the **same serialized owner** as Cassi's
research, memory, and resident brain. The hash-chained trading ledger retains
observations, outcomes, provenance, and operator choices.

Start the entity server with `--trading-activity-home <member-home>` and
`--trading-activity-db <canonical-ingestion.sqlite3>`, then authorize
`activity_scope: {\"activities\": {\"trading\": [\"ingest\"]}}` and
`activity_run` on a research programme. Each `ingest` action consumes 1–256
accepted closed bars, writes a source-bound receipt, and files an outcome in
the entity's work memory. Add `--trading-paper-program-id <program-id>` and
the `paper-step` scope for simulated trading. That programme's allowed roots
must cover both the member home and ingestion database. An existing standalone
ledger with no matching hosted trading computer is preserved and refused
until its adaptive state can be migrated explicitly. These operations expose
no live order path.

The standalone runner below remains available for offline reproduction or
separately held fields; it does not join the entity owner.

Run the deterministic end-to-end scenario:

```text
python run_cassi_trading_field.py run --demo-bars 200
```

Continue the same field from closed candles:

```text
python run_cassi_trading_field.py run --csv path/to/bars.csv --symbol BTC-USD
python run_cassi_trading_field.py status
```

The default field home is `_diag/trading-field`. A different persistent home
or Hive can be selected before the command:

```text
python run_cassi_trading_field.py \
  --data-home path/to/field \
  --hive-home path/to/hive \
  run --csv path/to/bars.csv --symbol BTC-USD
```

The field can consume the accepted closed-candle stream directly from the
durable market-ingestion database:

```text
python run_cassi_trading_field.py \
  --data-home _diag/trading-field \
  run --ingestion-db _diag/market-ingestion/market.sqlite3
```

Every accepted event is linked to its trading-ledger bar before the ingestion
watermark advances. A crash between those steps is safe: the repeated bar is
recognized exactly, the missing provenance link is written, and only then is
the source event marked delivered.

### Canonical field paper member

The canonical field operates a persistent **paper-only** member over accepted
closed candles. First create an authorised research program in the local Cassi
entity whose `allowed_roots` cover the member home and the ingestion database.
Give the runner its existing member/host-mission IDs, that program's actual ID,
the loopback entity URL, and the name of an environment variable holding the
entity API token:

```text
python run_cassi_trading_field.py \
  --data-home _diag/trading-field \
  run --ingestion-db _diag/market-ingestion/market.sqlite3 \
  --paper-only --member-id trader-btc --mission-id <original-host-mission-id> \
  --entity-url http://127.0.0.1:<entity-port> \
  --entity-program-id <active-program-id> \
  --entity-token-env CASSI_ENTITY_API_TOKEN \
  --follow

python run_cassi_trading_field.py \
  --data-home _diag/trading-field \
  status --paper-only --ingestion-db _diag/market-ingestion/market.sqlite3
```

The runner verifies the authenticated program's active status and both workspace
scopes before admitting a source candle or altering the paper account. It pins
the verified program and original host mission separately, retaining that
identity across restarts. Its single-owner lock prevents another paper worker
from opening the same member home.
The first action admits existing accepted candles as field history behind a
no-fill activation boundary. In follow mode it waits for new accepted candles,
checks program authority and feed health at each action, and advances one bar
at a time through the same open field and ingestion store.

A new field target becomes a bounded **pending paper order** after its signal
bar closes. A fill uses the next eligible accepted candle's close and recorded
slippage, or the pending order expires; the decision candle cannot fill itself.
Receipts link the signal, the later execution source and price, and the
one-bar lag. Risk, exposure, turnover, and data-health limits remain visible.
Pending state, receipts, and delivery watermarks survive a restart without
replaying a fill. Older same-bar paper receipts remain immutable and explicitly
labelled as legacy; the field's internal modeled outcomes retain their own
provenance. Inspect executable paper results through the causal account and
its post-cutover figures, rather than interpreting the field's modeled outcome
as an executable return.

`Ctrl+C`, SIGTERM, or a `STOP_PAPER_WORKER` file inside the member home ends
follow mode with a receipt and durable cancellation of any pending order. Remove
the stop file before an intentional restart. A verified paused or revoked
program also cancels pending paper intent, including while no candle arrives;
network/authentication uncertainty blocks new action while retaining pending
state for recovery. `status --paper-only` reads the bounded application view,
including latest disposition, pending intent, execution, cancellation, feed
health, and program attestation. Inspection grants no fresh action permission.

Keep the public feed separate with its `--mode live --no-paper` profile while
this canonical member is active. The market-ingestion paper option below retains
its older shadow-policy account; do not run both paper loops for the same
trading responsibility.

For a high-volume public stream, `--public-feed-channels quotes` keeps fresh
heartbeat/ticker observations while REST supplies the closed bars for research;
`--public-feed-channels bars` subscribes to heartbeats only. Both keep the
feed's wall-clock health checks authoritative.

To expose the member through Cassi Surface, start `cassi_field_brain_server.py`
with `--trading-paper-view <member-home>/trading-paper-application.json`. The
host backend validates the view digest, durable member binding, and entity
program attestation before publishing a bounded accessibility summary through
the existing authenticated `/v1/surface` API. The program must already include
`trading-paper/paper-account` in `surface_scope`, with only
`observation: [\"accessibility\"]` and `operations: []`. The source accepts no
input or orders and does not start a second trading worker, access a private
account, or create a mission.

### Mathematics in the paper research program

To have Cassi investigate the field's trading observations, enable the entity's
hosted trading activity with `--trading-activity-home <member-home>`,
`--trading-activity-db <ingestion-db>`, and
`--trading-paper-program-id <active-program-id>`. Admit a research program with
the same ID. Its `allowed_roots` must cover the member home and canonical
ingestion database; give it `activity_run` and exact
`"activity_scope":{"activities":{"trading":["paper-step"]}}`.

Set `"standing":true` on the research program so a finished investigation
waits for the next closed bar under the same field identity. For a completed
program with retained paper history, send `continue` to its existing program
control endpoint with a fresh quantitative question; the hosted member remains
bound to that program ID.

For example, the
program's mission can ask Cassi to derive and challenge quantitative
relationships among market changes, numeric field state, chosen exposure, and
later paper outcomes. An initial question might ask which signal conditions
predict movement by the next eligible bar, and which apparent relationships
survive changes in market regime. She can select the next observation, propose
a source-bound calculation through the existing research method tools, inspect
its actual result, revise the question, and retain useful methods in her field.
Keep the canonical ingestion feed running separately; a hosted paper step
advances the same persistent member and should not run concurrently with the
standalone paper worker for that member home.

Each `trading/paper-step` with new accepted bars now places a mathematical
observation in that program's workbench. It carries the exact source revision,
observation and availability times, market OHLCV, numeric field-decision state,
requested and applied targets, and the paper account and feed health. A new
signal is marked as pending. A later settlement names the signal event and
its canonical digest alongside the execution event, elapsed time, reference
prices, and actual fill. The workbench keeps the hosted receipt digest and the
canonical event digests as source references; methods can compare the exact
signal and execution without treating a pending order as a fill. Internal
modeled outcomes are separately named. A step that processes no bar adds no
new mathematical observation. The field-held workbench and retained research
methods allow the same inquiry to continue after a restart.

For a first calculation, compare the executed fill price with the signal
candle's close on the two linked source records. Continue with exposure
changes, observed paper-account movements, and competing explanations across
subsequent observations. This is paper evidence; relationships drawn from it
are questions for ongoing measurement, not live order instructions.

Long campaigns can advance in bounded chronological slices and emit an atomic,
content-digested receipt:

```text
python run_cassi_trading_field.py \
  --data-home _diag/trading-field \
  run --csv path/to/bars.csv --symbol BTC-USD \
  --max-new-bars 720 \
  --update-thresholds 256,768,1536 \
  --update-interval 1024 \
  --receipt _diag/trading-field/campaign-receipt.json
```

Repeating the command continues the same field. The complete source prefix is
rechecked against resident evidence, while only the requested number of new
bars can advance learning.

Each decision preserves normalized movement, variability, volume, path shape,
account exposure, and drawdown. Consequences mature independently over 1, 6,
24, and 168 bars. The observed policy/account path and every fixed-exposure
alternative are both retained, with the alternatives explicitly identified as
no-market-impact models rather than executed trades. Prediction error and
regret select a bounded mixture of recent and informative experiences for the
next field update.

The compact semantic panel that discovery learns from is eight decisions by
default: four training and four held-out decisions at every configured action
level. `--semantic-panel-decisions` widens the panel up to the model window and
`--semantic-panel-actions` restricts it to a subset of action levels, trading
context evidence against action coverage; three spanning levels identify the
same slope and intercept an affine mechanism needs. Panel width and field
geometry are creation-time values, like the learning cadence.

The shared semantic learner compares constant, exposure-only, contextual
multiscale, and regime-conditioned mechanisms on a later chronological slice.
Rather than receiving market-regime keys, it surveys the complete
pre-observation state and action, discovers useful numeric or categorical
dimensions, and learns bounded hierarchical boundaries that can choose a
different mechanism in each supported leaf. Dimensions, boundaries, and
candidate choices come only from training experience; the later slice validates
the frozen portable composite. Missing or unseen context abstains with a support
gap. Because a later evaluation slice routinely sits outside the range the panel
observed, numeric features carry that observed range widened by a quarter of it:
the mechanism keeps speaking just beyond its experience, the observed range
stays on the record so the two remain distinguishable, and anything beyond the
widened envelope still abstains. Every split must also leave at least four
supporting decisions on each side, so discovery grows fewer, better-evidenced
leaves rather than thin ones. A mechanism can guide action only after improving
objective RMSE by at least two percent on the reserved slice, six supporting
training decisions, and full holdout support. The discovered composite is held
to that same standard, measured on that same slice: whichever mechanism proves
itself best there guides, whether the field fitted it locally or discovery
selected it from the semantic panel. When the composite does not clear the
standard while a fixed candidate does, the candidate that proved itself is
retained as the guiding mechanism instead, and when neither clears it the
composite stays retained without guidance. The field's own discovery keeps its
evidence in the update record, and the update row carries both verdicts — what
the selected mechanism scored on the reserved slice and what the field's own
retained choice scored — so the comparison is readable from one record.
Otherwise the deterministic policy and drawdown gate remain in control.
Unsuccessful actions still become useful experience.

New fields update at 256, 768, and 1,536 matured outcomes per horizon, then
every 1,024 outcomes. These creation-time values can be overridden with
`--update-thresholds` and `--update-interval`; resident fields retain their
original cadence. Every update archives the complete decision panel as evidence,
while the field receives a compact, source-bound summary and retains the
selected mechanism itself. Each archive admission and learning request settles
inside an immutable successor before one owner publication, so a fault or
capacity refusal cannot expose a partial update. The live regional descriptor,
rather than a trading-specific size estimate, supplies exact used and available
capacity. Learning reserves the final 20 percent of both the semantic task
region and the overall workspace; once either reserve is reached, later updates
are durably deferred and the last valid field keeps trading without reset or
overflow.

Region capacity follows the declared field geometry: the semantic task region
holds six bytes per field mode, and the field declares a workspace ceiling that
covers the owner's nine-word-per-mode geometry plus resident evidence.
`--field-mode-count` is therefore the single knob that sizes both, and panel
width, cadence, and campaign length must fit inside what it buys: a wider panel
retains more context evidence per update, so a long campaign needs either a
larger geometry or fewer, better-evidenced generations. An override that
repeats a resident field's own value is a resume; any other value needs a new
home, because cadence and geometry decide what a field's evidence means.

The risk budget is measured separately from the reported account statistic. A
drawdown of 20 percent caps exposure at one quarter of the action range; a
drawdown of 35 percent halts trading for 720 bars. After the cooldown the halt
releases, the budget re-bases to the current equity, and trading resumes for
720 bars at a quarter-size cap before full size returns. The account's reported
peak and drawdown keep their all-time meaning, so a recovered field that re-bases
still records the full path it traded.

### Hive exchange

Verified semantic mechanisms are exported as `reasoning-strategy` capsules.
The capsule contains the portable program and its diagnostics, not raw prices
or account identity. Export stays enabled. Import is off initially and can be
toggled persistently:

```text
python run_cassi_trading_field.py skills enable
python run_cassi_trading_field.py skills sync
python run_cassi_trading_field.py skills disable
```

Imported skills are limited to promoted trading bundles with the exact local
representation contract. They are staged rather than applied directly and
must beat local candidates on the next local chronological holdout: the
contributing field's verification stays on the record as the method's
provenance, while its admissibility is measured here, on the same reserved
slice and support requirement as every locally fitted candidate. The shared
Hive defaults to `Cassi/.cassi/hive` and can also be selected with
`CASSI_HIVE_HOME` or `--hive-home`.

This runtime produces target exposure decisions and evidence. It does not
authenticate to an exchange or submit, change, or cancel orders.

## Historical research evidence

The remaining foundry, residency, benchmark, and paper commands preserve the
older `RefinementField` and raw-event experiments so their receipts and
checkpoints remain reproducible. They are historical evidence replayers, not
the canonical adaptive trading runtime, and their checkpoints are not imported
into `cassi_trading_field.py`.

### Historical local foundry

From this directory:

```text
python run_cassi_trading_foundry.py --demo-bars 240 --out-dir _diag/trading-foundry
```

The runner writes:

- `foundry_receipt.json`: hash-bound data, selected strategy, development
  rounds, holdout metrics, field identity, and ownership declarations;
- `refinement_field.chk`: the field checkpoint produced by that run.

For local CSV data, use columns `timestamp,symbol,open,high,low,close,volume`:

```text
python run_cassi_trading_foundry.py --csv path/to/bars.csv --symbol BTCUSDT
```

The replay splits the series into train, validation, and a final holdout.
The holdout is evaluated only after bounded refinement has selected a program.
Fees and slippage are explicit replay costs.
To reuse a learned trading field as a prior:

```text
python run_cassi_trading_foundry.py \
  --csv next-window.csv \
  --symbol BTCUSDT \
  --field-in _diag/trading-foundry/refinement_field.chk \
  --frozen-field \
  --out-dir _diag/trading-foundry-next
```

Frozen reuse makes the prior field available for candidate ranking without
trying to append lessons to a saturated checkpoint. General Cassi math/Python
knowledge belongs one layer above this trading-specific field: it should be
exported as verified CassiPy skills and used by a future program synthesizer,
not copied as opaque trading state.

For longer chronological evolution, carry the selected program and field
through non-overlapping historical windows:

```text
python run_cassi_long_foundry.py \
  --csv _diag/coinbase-btcusd-1h-2024.csv \
  --symbol BTC-USD \
  --window-bars 720 \
  --step-bars 720 \
  --max-windows 12 \
  --max-rounds 1 \
  --max-candidates 4 \
  --validation-slices 3 \
  --minimum-improvement 0.0005 \
  --component-limit 4.0 \
  --out _diag/coinbase-btcusd-1h-2024-long-foundry-cap4.json
```

Each window has its own holdout. The selected algorithm and field checkpoint
are carried only into later windows, and each window records its result
against the configured initial seed program. If the bounded field reaches its
component capacity, the receipt records that boundary and continues algorithm
selection with the last valid field frozen; it never silently resets or
discards the learning state.

Promotion uses three chronological validation slices in the recommended
configuration. A candidate must clear trade-count, drawdown, and improvement
gates in every slice, and selection maximizes the candidate's worst-slice
objective before aggregate validation. This is the profit-generalization gate;
increasing rounds or candidate breadth does not substitute for it.

The optional `--seed-mutation` flag supports controlled seed experiments and
binds the mutation into the receipt's initial program. `fast_down` improved the
2024 BTC screen from +2.5276% to +4.7625%, but the held-out January 2025
screen declined from -6.4380% to -6.9258%. It is therefore not the production
default yet; the untouched seed remains the honest cross-period baseline.

The same guarded protocol can be compared across bar durations. Aggregate only
complete UTC buckets and pass the bar duration through `--timeframe-hours` so
annualized replay metrics use the correct number of periods. The 2024
120-day-window comparison receipt is
`_diag/timescale-foundry-comparison-2024-s3.json`: it covers 1-hour, 6-hour,
and daily BTC bars with three validation slices. None of the scales produced a
profitable holdout in this first comparison, and no mutation improved the seed
at 6-hour or daily resolution. The daily arm has sparse holdout activity, so it
is a screening result rather than a final daily-timescale conclusion.

The first smaller-timescale comparison is recorded in
`_diag/subhour-foundry-comparison-2024-q1-s3.json`. On matched 40-day
windows, hourly bars returned `+1.12%` with no mutation, 15-minute bars
returned `-5.01%` versus a `-6.57%` seed and promoted `exit_down` followed by
`fast_down`, while 5-minute bars returned `-16.12%` and made no mutation.
The 15-minute and hourly comparison bars were derived from the continuous
5-minute source so every tested bucket was complete.

The bounded strategy catalog now contains seven families:
`trend_pullback`, `breakout`, `mean_reversion`, `trend_following`,
`momentum_continuation`, `volatility_expansion`, and `range_reversion`.
Use `--max-candidates 16` to evaluate the full catalog in a round; the
conservative production protocol can keep a smaller candidate budget. The
family-only holdout screen is recorded in
`_diag/strategy-family-holdout-screen-2024-q1-s3.json`. `breakout` had the
highest raw compounded result on the hourly and 5-minute screens, but the
5-minute result had zero trades and is not actionable. `trend_following` was
the strongest non-seed family with active trades on the 15-minute and
5-minute screens. High-volatility families can abstain completely, so
trade-count gates remain essential.

The raw-event profile defaults to a `0.5` stored-component bound. The
`--component-limit` setting raises that fixed bound together with the Qi
physics amplitude and checkpoint identity; it is not a silent clamp or a
second adaptive store. A write that would exceed the bound first invokes the
fixed multiscale Qi consolidation and retries. Successful retries are recorded
in the raw transition receipt. If the retry still cannot fit, the residency
writer records a recoverable `capacity-saturated` event for that write only;
the field is carried forward and later writes remain eligible. The residency
runner also exposes `--field-wave-width` (an even fixed mode count from 16
through 4096), and both capacity settings are checkpoint-visible.


Long-foundry lessons use the quality-aware transfer gate: novel outcomes
receive a bounded provisional write into a field-owned transfer family and can
be consolidated only after the field reproduces them on a held-out context.
The deterministic families are `risk` (`drawdown`, `cost`), `opportunity`
(`edge`, `flat`), and `baseline` (`stable`); unrelated families abstain.
Contradictory outcomes receive a bounded corrective write, repeated
confirmation is written once, and uncertain outcomes remain provisional. Each
development candidate records this admission decision, and each long-run
window records aggregate lesson counts and repeats. Other explicit
field-learning adapters retain their declared immediate-admission semantics.

## Aggressive single-field residency

`cassi_aggressive_residency.py` keeps the program fixed while one
`RefinementField` owns contextual action selection. Each causal decision
combines hourly, four-hour, daily, volume, volatility, five-minute
microstructure, position, and drawdown context. The field ranks seven target
sizes from full short through flat to full long. A persistent account then
applies next-open fills, prior-position gaps, fees, spread, volatility-scaled
slippage, short funding, stop exits, maximum holding periods, drawdown caps,
and cooldowns.

Delayed outcomes are written as situation-action-consequence memory in the
field's temporal scales. Each lesson is bound to a deterministic 90-day era,
the current direction-volatility regime, time since the regime transition,
and account position. The read path includes the immediately preceding era,
so useful behavior crosses a calendar boundary once and then expires.
Confirming outcomes reinforce the same action; contradictory outcomes write
`reject` over that action and remove it from the available choice set.
Uncertain outcomes remain separate and cannot masquerade as authority. The
lesson objective is compounded log growth minus path drawdown and downside
deviation, including execution and funding costs. A second curriculum
revisits the largest regrets, missed opportunities, and high-volatility
episodes under threefold execution friction. There is no learned sidecar or
fallback model.

Train from an existing field checkpoint:

```text
python cassi_aggressive_residency.py \
  --history E:/CassiTrading/market-data/coinbase-btcusd-1h-2016-to-0919-complete.csv \
  --fine-history E:/CassiTrading/market-data/coinbase-btcusd-5m-2024-q1.csv \
  --initial-checkpoint _diag/repeated-experience-2016-to-0919-v9/pass-002/final_refinement_field.chk \
  --program-receipt _diag/repeated-experience-2016-to-0919-v9/pass-002/backfill_receipt.json \
  --output-root _diag/aggressive-residency-v1
```

The verified 2016–2026 curriculum processed 93,937 hourly bars and 23,305
decision times without a capacity event. Online learning changed 10,279
targets, obtained direct field support on 1,124 decisions, and finished at
`+32.02%` with `35.81%` maximum drawdown. The matched frozen-before arm
finished at `+41.26%` with `32.42%` maximum drawdown, while replaying the final
field frozen over the same already-seen history finished at `-30.99%`.
Consequently, the run proves causal field authority and retained learning but
does not promote the trained checkpoint as a superior trading policy.

`--mode prospective` loads a checkpoint read-only, emits a digest-bound
receipt, and verifies that neither its field bytes nor fingerprint changed.
Training writes `aggressive_residency_receipt.json`,
`final_refinement_field.chk`, and `runtime_state.json`; the independent
verifier checks causal indices, matched decision counts, pairwise comparison
values, field identities, checkpoint linkage, and content digests.

### Chronological field promotion

`cassi_temporal_promotion.py` turns temporal learning into a causal promotion
campaign. A candidate learns only from the available development interval,
then competes against both the incumbent field and the unchanged starting
field on the immediately following untouched window. It enters the lineage
only when its risk-adjusted compounded-growth objective clears both controls.
If the starting field later regains a sufficient advantage, the runtime
resets to it rather than carrying stale authority forward.

```text
python cassi_temporal_promotion.py \
  --history E:/CassiTrading/market-data/coinbase-btcusd-1h-2016-to-0919-complete.csv \
  --fine-history E:/CassiTrading/market-data/coinbase-btcusd-5m-2024-q1.csv \
  --initial-checkpoint _diag/repeated-experience-2016-to-0919-v9/pass-002/final_refinement_field.chk \
  --program-receipt _diag/repeated-experience-2016-to-0919-v9/pass-002/backfill_receipt.json \
  --output-root _diag/temporal-promotion-v2
```

The verified 2016–2026 campaign contains 39 contiguous untouched evaluation
windows, four candidate promotions, three stale-field resets, and no capacity
events. The carried promoted path compounded `$1.00` to `$1.58996`; replaying
the unchanged starting field across the same windows compounded to `$1.49202`,
while retaining each incumbent without the new reset decision compounded to
`$1.33233`. Candidate reads exercised field authority 1,349 times: 426
positive selections and 923 rejected-action avoidances. The worst selected
window drawdown was `20.58%`.

The persisted runtime contains the selected checkpoint, field fingerprint,
program, account, completed-window count, last observed timestamp, and next
causal bar index. Its independent verifier reconstructs every promotion/reset
decision, field lineage edge, objective, account handoff, artifact digest, and
receipt link. This establishes a historically promoted candidate, not an
exchange or live-execution claim.

### Graded relational steering

`cassi_aggressive_residency.py` now writes field-owned market outcomes into two
relations: the full direction-and-volatility regime and its shared daily
direction. At read time, the current era carries full proximity and the
previous era carries `0.55` proximity. Promotion and rejection pressure are
the field emission score weighted by this relational proximity. The selected
position interpolates continuously between the program request and the
field-preferred safe target. A contradictory action therefore reduces a
position by the field's measured strength rather than requiring an all-or-none
override.

The first frozen relational holdout trained only on 2016, then evaluated the
next 2,160 hourly bars through 2017-03-30. It wrote 335 causal lessons into
one field and generated 474 field-authorized training decisions. On the later
untouched window, field inhibition fired 367 times and reduced the loss from
`-6.8249%` for the unchanged field to `-2.9632%`; maximum drawdown fell from
`14.8218%` to `12.8667%`. The candidate still lost money, so the promotion
rule correctly retained the starting field: no positive-growth exception was
made. This is evidence that graded relational inhibition reaches action and
reduces harmful exposure in this historical regime; it is not a profitable
strategy claim.

The independently verified receipt is
`_diag/relational-authority-holdout/temporal_promotion_receipt.json`
(`3f3ee9ccfce08b99ede7f4c1229893bc5c88356158fc859e28bf8f0eedc96b75`).
It contains the held-out candidate, incumbent, starting-field control,
authority counts, field/checkpoint lineage, and causal data windows.

### Transition-aware steering

The relational field also writes a causal 24-hour regime-flow relation:
`d1=<prior>><current>:vol=<prior>><current>`. This relation describes whether
daily direction and volatility are persisting, accelerating, reversing, or
changing together. It joins the full-regime and shared-direction relations at
`0.85` current-era proximity and `0.4675` prior-era proximity. Its pressure
uses the same bounded interpolation and rejection mechanism, so a known
transition can attenuate exposure without bypassing the field's uncertainty,
drawdown, or positive-growth promotion boundaries.

The matched 2016-development / 2017-Q1 untouched holdout wrote 335 lessons
and produced 1,032 field-authorized development decisions. In evaluation it
again issued 367 avoidances. Net return was `-2.9328%`, compared with
`-2.9632%` for the two-relation field and `-6.8249%` for the unchanged-field
control. The transition relation reduced the loss by a further `0.0304`
percentage points, while maximum drawdown increased from `12.8667%` to
`12.9369%`. The candidate remained negative and was not promoted. This is a
measured, bounded incremental effect rather than a claim that transition
memory is ready for durable strategy authority.

The independently verified receipt is
`_diag/transition-authority-holdout/temporal_promotion_receipt.json`
(`afbd342c0cb90dc60b9fb057fd2eacbafc0d18666429352e3613270540ab5482`).

### Coherence-acceleration steering

The field now reads a bounded two-window coherence relation:
`coherence=<strengthening|exhausting|recovering|breaking|emerging|settling|sustaining|reorganizing>:vol=<expanding|contracting|steady>`.
It compares the completed current 24-hour return and volatility window with
the preceding completed 24-hour window. This separates a transition that is
gaining coherence from one that is exhausting, reversing, or settling. The
relation has `0.75` current-era proximity and `0.4125` prior-era proximity;
its promote and reject emissions use the same continuous authority and safety
boundaries as every other field relation.

On the matched 2016-development / 2017-Q1 untouched holdout, the
acceleration-aware field wrote 335 lessons, made 784 field-authorized
development decisions, and issued 174 later avoidances. Its `-1.8869%`
evaluation return improved on the transition-only field's `-2.9328%` by
`1.0458` percentage points and on the unchanged-field control's `-6.8249%`
by `4.9380` percentage points. Maximum drawdown fell to `12.4657%`, below
the transition-only `12.9369%` and control `14.8218%`. The candidate remained
negative and therefore was not promoted: the field demonstrates a stronger
bounded reduction of harmful flow in this holdout, not a profitable strategy.

The independently verified receipt is
`_diag/acceleration-authority-holdout/temporal_promotion_receipt.json`
(`489ac48a93536a2f4eb9c1fd07d2c6d58f8e4f8d0cee3df6e012b311974ff4c5`).

### Cross-regime authority board

Evidence scope for the screens below, including the reserved-tail audit:
their starting checkpoint and selected strategy come from the second backfill
pass over all 93,937 bars from 2016-01-01 through 2026-09-19. Evaluation is
later than each screen's additional training and disables learning, but its
data is not unseen by the starting lineage. These are reused-history
comparisons. Receipt integrity and the recorded verdict strings do not
establish out-of-sample transfer. A genuinely unseen evaluation requires
date-clean provenance for both the field and the selected strategy.

`cassi_cross_regime_board.py` applies the acceleration-aware field to four
independent chronological transfers. Every scenario restores the identical
initial field, learns on one complete 8,760-bar year, freezes learning, and
then compares the selected field with that unchanged starting field through
the following learning-disabled 2,160 bars. The board derives each causal slice from
the source timestamps, binds every scenario receipt and checkpoint, and
rejects altered aggregate rows during independent verification.

The frozen board covers early-bull (2016 → 2017-Q1), bear-break
(2017 → 2018-Q1), volatility-shock (2019 → 2020-Q1), and recovery-rally
(2020 → 2021-Q1). It found no harmful transfers. The field actively inhibited
exposure in two regimes: early-bull return improved from `-6.8249%` to
`-1.8869%`, with drawdown falling from `14.8218%` to `12.4657%`; the
volatility-shock return improved from `-1.2800%` to `-0.1429%`, with drawdown
falling from `11.0658%` to `10.2555%`. In bear-break and recovery-rally, the
field made no nonzero authority decision and exactly matched the unchanged
control. The board therefore reports `SUPPORTS_INHIBITORY_TRANSFER_ONLY`:
the relation improved these two reused-history comparisons, while it does not
establish out-of-sample safety or portable positive-growth authority.

The independently verified board receipt is
`_diag/cross-regime-acceleration-board/cross_regime_board.json`
(`be752d29669c5b7deddfe614e3ff6f89dd320d56b7681105361df42e88146391`).
It binds the shared initial checkpoint, program, both source data sets, four
field lineages, and each learning-disabled evaluation.

### Constructive-authority screen

The same board now has a `constructive-authority` scenario family for the
harder question: whether field learning can add positive, drawdown-bounded
growth rather than only suppress harmful exposure. It restores the same field
for post-crash expansion (2020 → 2021-Q2), pre-ETF expansion
(2023 → 2024-Q2), post-ETF transition (2024 → 2025-Q1), and late-cycle
transition (2025 → 2026-Q1). Run it with:

```text
python cassi_cross_regime_board.py \
  --history E:/CassiTrading/market-data/coinbase-btcusd-1h-2016-to-0919-complete.csv \
  --fine-history E:/CassiTrading/market-data/coinbase-btcusd-5m-2024-q1.csv \
  --initial-checkpoint _diag/repeated-experience-2016-to-0919-v9/pass-002/final_refinement_field.chk \
  --program-receipt _diag/repeated-experience-2016-to-0919-v9/pass-002/backfill_receipt.json \
  --scenario-set constructive-authority \
  --out _diag/constructive-authority-board
```

The frozen screen did not establish constructive authority. The field emitted
no promote decisions in all four later windows. It abstained exactly in the
post-ETF and late-cycle transfers, but its avoidance-only response was harmful
in both expansion screens: post-crash return changed from `-9.4933%` to
`-12.4538%` and drawdown rose from `15.9514%` to `16.6988%`; pre-ETF return
changed from `+1.2461%` to `-3.8126%` and drawdown rose from `4.0699%` to
`7.0144%`. The result is `DOES_NOT_SUPPORT_PORTABLE_AUTHORITY`. The next
field change must create a separately measured positive-authority channel; it
must not reinterpret inhibition as opportunity.

The independently verified receipt is
`_diag/constructive-authority-board/cross_regime_board.json`
(`4b534a60b62bc47f0c7451a64258aa053d295dea341917f06c1539553eba82dc`).

### Positive-authority channel

The `market:v4` opportunity descriptor names agreement between the completed
hourly, four-hour, daily, and trend directions when the completed coherence
flow is strengthening, recovering, emerging, or sustaining. Other situations
share an `unresolved` descriptor; that descriptor is still written and queried.
Its key omits current position. Learning uses the existing action-outcome
writer; repeated writes of one outcome are not independent market occurrences.

The channel was screened once on the same four constructive transfers.
All 540 decision points within each 2,160-bar evaluation had zero supported
field authority, the selected arm remained the incumbent, and every candidate
metric exactly matched its starting-field control. This records absent
evaluation influence; it does not by itself identify why support was absent.
The independently verified receipt is
`_diag/positive-authority-board/cross_regime_board.json`
(`b03e994bd5d0d24bf256d5aa04cfe8377776187bc154bdc1ae6e68264d6cac28`).

### Mature-opportunity channel

The `market:v5` relation is the field's more selective constructive object. It
requires aligned completed hourly, four-hour, daily, and trend direction; a
favorable completed coherence flow; persistent 24-, 48-, and 72-hour movement;
and a contained or recoverable current distance from the 72-hour closing-price
extreme. The relation omits both era and position. Nonmatching situations share
an `unresolved` key that remains eligible for writes and reads. The observed
price path and execution-cost model determine each action's outcome label.

Its four-transfer screen had zero supported, promote, and avoidance decisions
in every evaluation arm, with exact starting-control metrics. Development did
learn: the four candidate-training summaries contain 1,340 lessons, 418
promote admissions, and 925 field-promote decisions, without capacity events.
The absence of later influence does not prove insufficient positive evidence
or insufficient recurrence; retention, context reach, and transfer remain
unresolved explanations. These counts cover all relations, not this relation
alone.
The independently verified receipt is
`_diag/mature-opportunity-board/cross_regime_board.json`
(`e72e71da7bdb47ffe702f2fc36d5afbdce87a8d7d76764936936930ea64d132a`).

### Field recurrence program

`cassi_field_recurrence.py` carries one field checkpoint through ordered,
disjoint development windows and compares the final state with its initial
state on a later learning-disabled window. Its synthetic lineage and overlap
checks pass. The first historical invocation was stopped after discovering
that its inherited field and strategy already incorporated the proposed
evaluation period. No historical recurrence receipt or authority result was
produced. The experienced checkpoint remains available for continued learning;
an unseen-transfer measurement needs a separate date-clean lineage.

### Reserved-tail audit

`cassi_temporal_tail_audit.py` spends the bars left outside every development
and promotion decision exactly once. It restores the promoted and unchanged
starting checkpoints into matched, learning-disabled arms with the same
program, account, costs, and causal data stream. The command refuses to
overwrite an existing receipt.

```text
python cassi_temporal_tail_audit.py \
  --history E:/CassiTrading/market-data/coinbase-btcusd-1h-2016-to-0919-complete.csv \
  --fine-history E:/CassiTrading/market-data/coinbase-btcusd-5m-2024-q1.csv \
  --promotion-receipt _diag/temporal-promotion-v2/temporal_promotion_receipt.json \
  --runtime-state _diag/temporal-promotion-v2/temporal_runtime_state.json \
  --promoted-checkpoint _diag/temporal-promotion-v2/promoted_refinement_field.chk \
  --starting-checkpoint _diag/repeated-experience-2016-to-0919-v9/pass-002/final_refinement_field.chk \
  --out _diag/temporal-promotion-v2/reserved_tail_audit.json
```

The reserved 937 hourly bars span 2026-08-11 through 2026-09-19. Both frozen
arms made 234 decisions and produced the same `2.1430%` net return, `2.2172%`
maximum drawdown, five trades, and `$1.62403` final equity from the carried
`$1.58996` account. The promoted field issued no supported promote or
avoidance decision; all 234 targets, positions, and authority labels matched
the starting-field control. The receipt therefore records
`DOES_NOT_SUPPORT`: this tail neither demonstrates a promoted-field advantage
nor a disadvantage. It shows that unmatched temporal knowledge abstains
rather than forcing stale actions. The independent verifier reconstructs the
two-arm decision comparison, objectives, causal indices, immutable checkpoint
hashes, and receipt digest.


## Reuse the learned math/Python layer

Export the already verified CassiPy capability substrate:

```text
python run_cassi_skill_bundle.py --out _diag/cassi-skill-bundle.json
```

The bundle contains twenty-one executable, differentially verified math/Python
skills: eight general CassiPy lessons plus thirteen financial-math algorithms
covering returns, drawdown, volatility, downside and tail risk, transaction
costs, sizing, multi-dimensional risk-adjusted objectives, hit rate, profit
factor, and risk of ruin. Each skill retains its source, immutable AST, test
cases, and digests. The bundle is the capability prior that the algorithm
synthesizer composes with market-specific field memory.

The field now uses a typed composition grammar rather than only four named
profiles. Return, risk, cost, objective, sizing, and performance slots accept
only role-compatible verified skills; the expanded registry yields thirty-two
bounded compositions (four named programs plus single-slot typed variants).
The new downside, tail-risk, profit-factor, Kelly-cap, and risk-of-ruin skills
are therefore executable choices rather than descriptive labels. A
composition's observed validation outcome is written back into the field under
its own composition identity, so later rounds can refine the financial program
itself as well as the trading strategy. The selected return, risk,
execution-cost, sizing, and objective algorithms score validation candidates;
the same composition is then reported against the frozen holdout so selection
benefit and out-of-sample decay remain visible.

## Verify the canonical runtime

```text
python -m pytest -q test_cassi_trading_field.py
```

This exercises multi-horizon experience, field-selected mechanisms, exact
restart and replay, semantic-only Hive export, persistent import controls, and
the single-owner/no-legacy-state invariant.

The historical evidence replayers retain their original suites:

```text
python -m unittest -v test_cassi_trading_foundry.py test_cassi_aggressive_residency.py test_cassi_temporal_promotion.py test_cassi_cross_regime_board.py test_cassi_trading_benchmark.py test_cassi_trading_realtime.py test_cassi_skill_bundle.py
```

Those suites cover their fixed strategy contracts, causal replay, historical
receipt integrity, field checkpoint restoration, and skill-bundle evidence.

## Milestone benchmark

Run the deterministic five-level benchmark:

```text
python run_cassi_trading_benchmark.py \
  --out-dir _diag/trading-foundry-benchmark \
  --fixed-financial-composition balanced
```

The fixed composition is the canonical objective control. Change it explicitly
when running a different control experiment.

For a real historical CSV, use the same benchmark protocol:

```text
python run_cassi_trading_benchmark.py \
  --csv path/to/bars.csv \
  --symbol BTCUSDT \
  --out-dir _diag/trading-foundry-benchmark \
  --fixed-financial-composition balanced
```

To create a reproducible public-data CSV without an API key:

```text
python download_coinbase_history.py --product BTC-USD --start 2025-01-01T00:00:00Z --end 2025-02-01T00:00:00Z --granularity 3600 --out _diag/coinbase-btcusd-1h-2025-01.csv
```

The downloader accepts Coinbase granularities `60`, `300`, `900`, `3600`,
`21600`, and `86400` seconds. For sub-hour comparisons, preserve provenance:
download complete 5-minute candles first, then aggregate complete UTC buckets
to 15-minute or hourly bars. The public 15-minute endpoint can contain an
isolated missing candle even when the 5-minute series is continuous.
CSV mode requires at least 576 ordered bars. The first sixth is reserved for
field calibration; the following five equal windows are the matched evaluation
levels. Any remaining tail bars are reported as unused rather than silently
folded into another split.

It compares three matched arms on the same evaluation data identities:

- **guided:** a field is calibrated on a separate development series (synthetic
  in the default mode, or the first historical window in CSV mode), then
  selects both strategy refinements and financial compositions;
- **blind:** a control field cannot predict or learn refinement outcomes;
- **fixed:** the guided field still refines the strategy, but a fixed financial
  composition override isolates the effect of financial-program selection.

The receipt reports per-level holdout returns, objectives, drawdowns, selected
program identities, field reach status, all three composition identities, and
guided-minus-fixed as well as guided-minus-blind deltas. It also records each
composition's validation objective, frozen-holdout objective, and delta versus
the default objective. The result is a measurement board, not a claim of live
profitability.

The retained historical smoke receipt
`_diag/trading-foundry-composition-historical/milestone_benchmark.json` uses
8,785 hourly BTC-USD bars, a 1,464-bar calibration window, five matched
1,464-bar evaluation windows, one refinement round, four candidates per round,
and `balanced` as the fixed objective. The guided field selected
`cost_aware`, `growth`, `balanced`, `cost_aware`, and `balanced` across the
five windows. Its guided-minus-fixed financial-objective deltas were
`+0.0439435887`, `+0.0318470024`, `-0.0219817571`, `+0.0312080468`, and
`+0.0404220418`. Four of five windows therefore favored the field-selected
financial program, while the third window remains a useful negative control.

## Standard realtime benchmark

The standard realtime scenario is the causal bridge between historical replay
and the paper account. It runs `RT-1-mixed-hourly`: 384 hourly synthetic bars
with a four-regime mixed stream, 48 warmup bars, and 336 live bars. One bar is
released at a time. The strategy may use only the released prefix when making
the next-bar decision; the following bar is used only to settle that decision.

Every 24 live bars, the field evaluates bounded strategy mutations and typed
financial compositions using only bars available at that cutoff. It writes one
bounded observed outcome back into the field, records composition learning, and
continues trading with the selected program. If a candidate would exceed the
component bound, the raw learner first invokes the fixed multiscale
consolidation and retries. A successful retry is included in the transition
receipt. If the retry still cannot fit, that review records a recoverable
`capacity-saturated` admission for the single write; the realtime wrapper
retains its declared saturation policy rather than resetting the field. This
keeps the bounded behavior explicit in the receipt.



Run the canonical scenario:

```text
python run_cassi_trading_realtime.py \
  --out-dir _diag/trading-realtime-benchmark
```

The `realtime_benchmark.json` receipt contains the source and event-root
digests, every causal decision, every adaptation cutoff, candidate replay
scope, field before/after identities, financial teaching receipt, final
equity, and a content digest. `verify_realtime_benchmark` rejects a decision
whose input prefix, next-bar index, or adaptation replay end does not match
the causal protocol. This is a deterministic paper-trading benchmark, not a
claim of live profitability.

To use the same causal protocol as an external validation arm, first calibrate
on the pinned synthetic RT-1 stream, then replay independent closed historical
windows from a CSV. Each window inherits the synthetic field checkpoint and
final strategy identity before its own realtime bar stream begins:

```text
python run_cassi_trading_realtime.py \
  --csv _diag/coinbase-btcusd-1h-2024.csv \
  --symbol BTC-USD \
  --external-windows 5 \
  --out-dir _diag/trading-realtime-external-2024
```

The resulting `external_realtime_validation.json` contains the complete
synthetic calibration receipt and five independently verified historical
window receipts. Historical windows begin from the same calibration field and
strategy but retain their causal online adaptation path; no historical window
is used to pre-train another window.

## Long-horizon market residency

The residency benchmark extends the realtime protocol into a persistent
closed-bar account loop. `MR-1-field-residency` first calibrates on a pinned
synthetic mixed-regime stream, then runs three matched external arms on the
same bars:

- `static-baseline`: the seed strategy with no adaptive field;
- `field-residency`: the calibrated strategy and checkpoint continue learning
  from realized account outcomes at each review;
- `frozen-transfer`: the calibrated strategy and checkpoint continue without
  any online writes.

The default protocol uses 768 calibration bars, 1,536 external bars, a
48-bar warmup, a 24-bar review interval, and the repository's maximum fixed
field component bound of `4.0`. Every decision is made from the
released prefix and settled on the following closed bar. Reviews record the
field identity, strategy/composition transition, realized-prefix failure
signature, and the exact future-bar exclusion. There are no counterfactual
candidate backtests in this arm; the field receives only the account outcome
that actually occurred.

Run the synthetic residency milestone:

```text
python run_cassi_market_residency.py \
  --out _diag/market-residency.json
```

Run the same calibrated transfer on the first closed historical BTC-USD
window:

```text
python run_cassi_market_residency.py \
  --csv _diag/coinbase-btcusd-1h-2024.csv \
  --symbol BTC-USD \
  --external-bars 1536 \
  --out _diag/market-residency-historical-2024.json
```

Each receipt is independently digest-checked. The verifier rejects missing
field checkpoint identity, mismatched arm data, policy changes in the frozen
arm, non-causal prefix counts, review lookahead, inconsistent pair deltas, or
tampered receipt content. If a bounded write reaches its fixed component
capacity, the learner attempts multiscale consolidation before retrying. A
still-rejected write is recorded with a recoverable `capacity-saturated` event,
while the field checkpoint remains intact and later reviews continue learning;
the arm never silently resets the learned state. This is a field-residency and
causal-learning milestone, not a claim of live profitability or an exchange
execution path.


## Chronological residency campaign

`MR-2-chronological-residency` calibrates the field once and then advances
through disjoint chronological windows. It compares four controls:

- `carried_field`: field state, strategy, and selected composition continue
  from one window into the next;
- `frozen_transfer`: every window starts from the same calibrated checkpoint
  and strategy, with learning disabled;
- `fresh_field`: every window starts with a newly taught field and the seed
  strategy;
- `static_baseline`: every window starts with the seed strategy and no field.

The carried arm is the continuity experiment. The frozen arm isolates transfer
without further writing, while the fresh arm measures how much of the result
comes from merely having a within-window learner rather than retained
chronological memory. Window equity is normalized locally and compounded only
after each arm has completed its causal window.

Run the five-window synthetic campaign:

```text
python run_cassi_market_residency_campaign.py \
  --external-windows 5 \
  --out _diag/market-residency-campaign.json
```

Run the same campaign on five chronological BTC-USD windows:

```text
python run_cassi_market_residency_campaign.py \
  --csv _diag/coinbase-btcusd-1h-2024.csv \
  --symbol BTC-USD \
  --external-windows 5 \
  --out _diag/market-residency-campaign-historical-2024.json
```

The campaign receipt verifies window ordering, disjoint data identities,
causal decisions inside every window, carried checkpoint and strategy
inheritance, frozen-transfer invariance, fresh-field resets, compounded
metrics, source provenance, and the final content digest.
The earlier five-window 2024 receipt is retained as a negative pre-recovery
baseline: compounded final equity was `0.3208` for `carried_field`, `0.5431`
for `frozen_transfer`, `0.4400` for `fresh_field`, and `0.6301` for
`static_baseline`. Its carried windows reached the then-configured capacity
without a recoverable write path, which motivated the capacity-aware rerun.
The current protocol instead distinguishes successful consolidation retries
from individual rejected writes, preserves the field checkpoint, and lets
later chronological windows continue. No strategy promotion is justified
until retained learning is evaluated against the frozen transfer control on an
unseen period.

The capacity comparison is now measurable rather than inferred from a frozen
flag. In a three-window synthetic smoke (`144` calibration bars, `192`
external bars, `24`-bar warmup and review interval), the verified carried arm
recorded calibration/carried capacity events of `5/[17, 33, 50]` at
`field_component_limit=0.5`, `0/[5, 15, 33]` at `1.0`, and `0/[0, 0, 0]`
at `4.0`, all with `field_wave_width=512`. Widening the last mode to `1024`
also produced `0/[0, 0, 0]`. Every run verified `PASS`; the short synthetic
stream happened to produce the same carried compound return
(`0.1185378667`) across these capacity settings, so these numbers establish
capacity and continuity behavior, not a trading-performance claim. The next
capacity gate is the same comparison on an unseen chronological period with
the frozen-transfer control retained.

## Paper trading

The paper runner consumes closed bars, emits the existing `shadow` policy
decision, and settles fills locally. It never sends an order to an exchange.
The account, fills, policy receipts, event IDs, and field-independent strategy
state are persisted atomically so a restart cannot duplicate a bar or fill.

Deterministic synthetic paper session:

```text
python run_cassi_paper.py \
  --csv _diag/paper-smoke.csv \
  --state _diag/paper-state.json \
  --out _diag/paper-latest.json
```

Read-only public Coinbase candles, excluding the currently open candle:

```text
python run_cassi_paper.py \
  --coinbase-product BTC-USD \
  --granularity 3600 \
  --once \
  --state _diag/coinbase-paper-state.json \
  --out _diag/coinbase-paper-latest.json
```

The current implementation is deliberately limited to one product, closed-bar
market fills, local fees/slippage, long-only exposure, drawdown freeze, and
the existing portfolio constraints. Its paper policy allows a full bounded
position transition so the strategy intent can be compared one-for-one with
the historical replay; the account still rejects leverage and short targets.
It is a paper account, not a live execution adapter.

Compare a completed paper state against historical replay:

```text
python run_cassi_paper_replay.py \
  --state _diag/coinbase-paper-state.json \
  --out _diag/coinbase-paper-parity.json
```

The parity receipt checks every decision up to the final bar, counts paper
fills against replay trades, records fee/equity differences caused by local
fill modeling, and includes mutation-visible controls. A public 299-bar
closed-candle soak produced exact signal parity and matching 11-fill counts;
paper equity was $0.41 above replay because the paper account applies
price-based fees and slippage to local fills.

## Durable market ingestion and monitoring

`run_cassi_market_ingestion.py` is the production data path for the paper account. It keeps the provider's exact messages and Cassi's canonical events in a SQLite WAL database, admits only closed candles, persists consumer watermarks, and resumes without processing the same event twice. The initial history warms the strategy but is marked delivered before paper trading starts, so startup cannot manufacture historical fills.

Bootstrap the database and paper account from the latest closed candles:

```text
python run_cassi_market_ingestion.py --mode once
```

Run the continuous public feed:

```text
python run_cassi_market_ingestion.py --mode live
```

The live service's default channel profile is `all`: heartbeat, ticker, and
matches. Heartbeats expose trade-ID gaps; a gap triggers an overlapping REST
reconciliation before exposure can open again. Repeated polling also detects
revised historical candles. A changed candle is first retained as an explicit
conflict and turns health RED; only an identical second observation promotes the
revision and supersedes the former canonical version.

For the hosted paper research member, run a separate read-only public feed
against its canonical ingestion database:

```text
python run_cassi_market_ingestion.py --mode live --no-paper --public-feed-channels bars --db path/to/market.sqlite3
```

`--public-feed-channels` chooses one explicit profile: `all` (default, all three
channels), `quotes` (heartbeat+ticker), or `bars` (heartbeat only). The `bars`
profile skips the high-volume quote and match streams and reconciles closed bars
through REST every 60 seconds. Heartbeat trade-cursor gap enforcement runs only
when `matches` is subscribed; in the `bars` profile REST reconciliation is the
authority for bar continuity, while raw heartbeats and their source timestamps
are still persisted for health. All profiles preserve the database across
restarts, keep accepted closed bars and the ledger intact on restart, and still
block paper exposure when timestamps, gaps, or source health fail.

The default files are under `_diag/market-ingestion/`: `market.sqlite3`, `health.json`, `run-receipt.json`, `paper-state.json`, and `paper-latest.json`. Health is operational authority:
Each snapshot exposes heartbeat, market, and reconciliation ages; the signed exchange-to-receipt and candle-close-to-receipt wall-clock deltas; a lower bound when the exchange clock leads the workstation; gap, conflict, duplicate, schema-rejection, and reconnect counters; consumer backlog; and free disk space. Excessive time divergence degrades or blocks new exposure instead of reporting an impossible negative network latency.

- `GREEN`: the feed is current, reconciliation is complete, and the paper consumer may open exposure.
- `YELLOW`: degraded but bounded; existing state remains visible, while opening exposure is blocked.
- `RED`: stale, disconnected, conflicted, or awaiting recovery; opening exposure is blocked.

Export a lossless recording while running and replay it into an empty database:

```text
python run_cassi_market_ingestion.py --mode live --recording _diag/market-ingestion/raw.jsonl.gz
python run_cassi_market_ingestion.py --mode replay --replay _diag/market-ingestion/raw.jsonl.gz --db _diag/market-replay/market.sqlite3 --receipt _diag/market-replay/replay-receipt.json
```

Replay preserves the original receive times and reconstructs the same canonical event roots. Bounded `--max-messages` and `--max-seconds` runs are available for operational probes.
`Ctrl+C` closes the feed, persists the final health snapshot and a `STOPPED_BY_OPERATOR` receipt, and exits successfully.

Private account state remains deliberately separate from market data and order execution. An authenticated recorder outside this workspace can supply the declared account-event JSONL format; Cassi only reconstructs and audits it:

```text
python run_cassi_account_reconciliation.py --events path/to/account-events.jsonl
```

Orders, fills, balances, positions, and authoritative snapshots are persisted independently. Duplicate events are idempotent. A sequence gap or an impossible terminal-order transition quarantines the event and requires an authoritative snapshot before the account is considered reconciled. The market runner can couple this authority to paper exposure with `--require-account-reconciliation`. Neither runner contains an authenticated exchange client or an order-submission path.

## Continuous operation

`run_cassi_trading_service.py` keeps the trading stack alive across crashes,
stalls, and logons. Its home (default `E:/CassiData/outputs/CassiTrading/_service`)
holds `services.json`, `status.json`, per-service logs, and stop files. The
supervisor re-reads `services.json` whenever it changes, restarts a service
that exits or whose `health_path` goes stale (backoff 5 s doubling to 5 min),
stops Python services gracefully through `run/<name>.stop`, and terminates
executables named by `argv`. `external_port` marks a port that another owner
may already serve; the supervisor then leaves it alone. `start_when` holds a
service until its listed ports accept connections and the requested memory is
free, then starts it on its own, so a heavy service yields the machine to
other work instead of thrashing it.

```text
python run_cassi_trading_service.py install   # logon task, rechecked every 5 minutes
python run_cassi_trading_service.py start
python run_cassi_trading_service.py status
python run_cassi_trading_service.py stop      # stays off until start
```

The manifest declares four services:

- `feed-1h`: the `bars` feed for the paper member's canonical ingestion database.
- `feed-5m`: a `bars` feed at 300-second granularity in its own database, the
  intraday history for daytrading research.
- `brain`: `llama-server` with `Qwen3.5-9B-Q8_0.gguf` on `127.0.0.1:8097`,
  fully offloaded to the GPU. The service runs a private copy of the server
  build from `_service/brain-bin`, so rebuilds of the shared llama.cpp tree
  never collide with the running brain. `--load-mode none` keeps host memory
  near 1.3 GB (a memory-mapped model stays resident in RAM on Windows), and
  `--no-cassi-modal` keeps the dense Qwen3.5 forward pass unmodified. The
  CassiFI self-improvement engine shares this brain on the same port.
- `entity`: the field–brain server on `127.0.0.1:8090` with
  `--brain-backend external` on the `brain` service (`--model-url
  http://127.0.0.1:8097`, `--model-path` `Qwen3.5-9B-Q8_0.gguf`), gated by
  `start_when` on that port and 3 GB of free RAM. The
  entity carries the hosted `btc-paper-math` trading activity and
  research roots covering every program's allowed roots. Its `stage` block
  copies the CassiFI native field runtime into `_service/field-runtime` before
  each start, once the build has been unchanged for two minutes, under the
  image name `cassi-trading-field-runtime.exe`; `--program-native-runtime`
  points the entity at that copy, so native rebuilds in the shared tree leave
  the running field runtime untouched. `required_child` names the same image:
  if the entity's native runtime disappears, the supervisor restarts the
  entity, which resumes its programs and relaunches native residency from the
  latest settled build.

The `bars` profile reconciles each candle as soon as it closes: two seconds
after the close, then every five seconds until the provider publishes it.
Health allows a 30-second publication grace before it expects the new bar.

Heartbeat rows and their raw messages expire after `--transient-retention-hours`
(24 by default); closed bars and the ledger are kept forever. Health history
keeps a row at every state change and one row per five minutes otherwise. Stop
a feed before rebuilding its file:

```text
python run_cassi_market_ingestion.py --mode compact --db path/to/market.sqlite3
```
