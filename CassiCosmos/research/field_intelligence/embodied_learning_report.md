# Embodied World-Field Learning Report

## Status: ADOPT — 2026-08-31

The embodied field-intelligence experiment is **ADOPTED**. A single authoritative Yang/Yin world field now owns fast dynamics, slow plasticity, eligibility, reward measurement, action selection, and the rendered phase view. The causal learning gates, negative controls, exact snapshot continuation, render-purity check, and same-frame ordering check all pass.

Repository-wide acceptance is **PASS**: the fresh post-fix battery is 37/37, including both `verify_field_intelligence` and the windowed `verify_presentation_layers` arm.

## Implemented system

- `FieldPlasticity`: one full-resolution `vec2` storage buffer over the existing $N^3$ world cells, carrying policy plasticity $P$ and eligibility $e$.
- `FieldLearningState`: one fixed 128-byte state header carrying reward, action, episode, frame-order, fault, and snapshot metadata.
- Six target-conditioned actuator lobes represent the signed $\pm X$, $\pm Y$, and $\pm Z$ actions spatially inside the field. There is no second model, policy network, optimizer object, or CPU-owned adaptive state.
- The GPU owner list records reward measurement, bounded plasticity/eligibility update, action selection, learned Yang/Yin source coupling, the ordinary two-fluid/PDE evolution, and the field view in explicit barrier order.
- Learned control reaches the probe only through the existing field medium and `FieldVel`/`RealSim` viscosity path; no direct particle impulse was added.
- Disabled mode binds a 128-byte zero-state fallback and preserves the original two-fluid equations exactly.
- Clear, snapshot, restore, and reinitialize operations cover the exact GPU-owned $P/e$ state and header. Snapshots include the grid/profile contract and SHA-256 checksum and reject incompatible writes.
- The renderer exposes one stable `Texture2DRD` wrapper. Phase/energy occupies the main view, $P/e$ occupies the inset, and the render pass is read-only with respect to learning state.

## Frozen focused gates

| Gate | Result | Receipt |
|---|---|---|
| FI0 — allocation/header contract | PASS | $P/e=2{,}097{,}152$ bytes at $64^3$; header = 128 bytes; profile `64|0.180000000|0.8500000` |
| FI1 — default-off identity | PASS | Full/fallback SHA-256 prefixes both `78a69e226f3f` |
| FI2 — bounded finite learning | PASS | $|P|_{\max}=1.00000$; $|e|_{\max}=5.29051$; no non-finite state |
| FI3 — learned causal improvement | PASS | learned 5/6, clear 0/6; median distance $0.6940$ versus $6.0000$ |
| FI4 — negative controls | PASS | $\eta=0$: 0/6; shuffled reward: 1/6 |
| FI5 — snapshot integrity | PASS | SHA-256 `bd07b1f89b1607a7…`; incompatible snapshot writes rejected |
| FI6 — restored continuation | PASS | restored 5/6; median $0.6940$; all learned/restored distance deltas $\le 0.20$ |
| FI7 — render purity | PASS | learning checksum remained `7d27eee7057f` across the render-only check |
| FI8 — same-frame ordering | PASS | render tick = 1 and learning-header tick = 1 |
| FI9 — lifecycle rebuild | PASS | FI buffers and descriptor sets rebuilt across three grid/profile initializations |

Focused verifier receipt: `_diag/field_intelligence_interactive.log`, `_diag/field_intelligence_interactive.exit`, and `_diag/field_intelligence_verify.json`. The final focused run exited 0 and printed `FIELD_INTELLIGENCE_VERIFY PASS — FI0–FI9`.

## Causal demonstration

The actual windowed `field_intelligence_demo.tscn` story ran the six signed targets through:

1. train and freeze,
2. exact GPU snapshot,
3. learned replay,
4. clear only $P/e$,
5. same-body/same-field replay,
6. exact restore,
7. restored replay.

Final measured result:

| Condition | Successes | Median distance |
|---|---:|---:|
| Learned | 5/6 | 0.654662 |
| $P/e$ cleared | 0/6 | 6.000000 |
| Exact restore | 5/6 | 0.654662 |

The restored trajectory matched the learned trajectory within the frozen tolerance, and the snapshot checksum was `ee951c517447bc0dcf7ce26c5f1e201d2464170afadd2d29d4a129234d7a3f37`.

Windowed demo receipt: `_diag/field_intelligence_demo.log`, `_diag/field_intelligence_demo.exit`, `_diag/field_intelligence_demo.json`, and `_diag/field_intelligence_demo.png`. The run exited 0 and printed `FIELD_INTELLIGENCE_DEMO PASS — learned=5/6 clear=0/6 restored=5/6`. The log has no labeled warning, error, failure, orphan, or leak; the Vulkan backend prints three trailing `OpArrayLength is not supported yet.` capability messages.

## Presentation result

The final frame presents the causal result without CPU texture copying:

- phase is hue and field energy is light in the main panel;
- the lower-right inset shows the six learned $P/e$ lobes;
- the compact HUD reports learned, cleared, and restored medians and successes;
- the verdict names the causal intervention rather than merely displaying reward;
- Restart resets the neutral verdict color and Pause state, while manual clear/restore and fault paths reset their own verdict colors.

## GPU-layout and shared-consumer checks

The canonical layout preflight reports:

```text
[assert_layout] PASS: 0 mismatch(es)
```

Adding bindings 6 and 7 to `cassi_two_fluid.glsl` required every direct consumer to migrate. The simulator binds live FI buffers; FI-disabled owners bind an explicit zeroed 128-byte fallback. The standalone physics engine, mind engine, and direct two-fluid verifier scripts create, bind, and release that fallback through their existing lifecycle. The audit also found `verify_telescoping_weak.gd` still supplying the shader's obsolete 60-byte push constant; it now supplies the canonical 68 bytes, including `omega2=20` and `ham_completion=0`.

### Direct-consumer exercise matrix

| Consumer | Fresh exercise |
|---|---|
| `cassi_sim.gd` | **PASS** — FI0–FI9; the shared shader built and dispatched with live bindings 6–7. |
| `cassi_physics_engine.gd` | **PASS** — grid-path engine arms `verify_bh_accretion_engine`, `verify_merge_engine`, and `verify_multigrid_engine` all ran with `meshless_mode=false`; `verify_gridless_physics` also passed. |
| `cassi_mind_engine.gd` | **PASS** — 37/37 mind-engine checks. |
| `verify_rho_front.gd` | **PASS** — 4 checks, 0 failures. |
| `verify_eps_gap.gd` | **PASS** — 5 checks, 0 failures. |
| `verify_omega_invariant.gd` | **PASS** — 5 checks, 0 failures. |
| `verify_telescoping.gd` | **PASS** — 14 checks, 0 failures; OFF path differed by 0 bytes. |
| `verify_uniform_lapse.gd` | **PASS_IMPLEMENTATION_ONLY** — 10 checks, 0 failures; bindings 0–7 and baseline OFF bit identity passed. |
| `verify_qi_time.gd` | **FAIL** — its recorded negative G4 repeated (`z_phi=-0.959`, `z_uniform=-0.959`); pipeline creation, dispatch, and OFF bit identity passed. |
| `verify_telescoping_weak.gd` | **FAIL / HOLD** — the corrected 68-byte PC dispatched without layout errors and its OFF/charge/determinism checks passed, but the pre-registered G4c decision remained `overall_fp4=1`, not `phi2`. |

The two failing research probes are not battery arms and retain their measured negative verdicts; neither is relabeled as a migration pass. Their descriptor, push-constant, dispatch, and default-OFF checks establish the shared-shader compatibility result.

## Full battery receipt

A fresh 37-arm battery ran after the shared two-fluid migration and the render-topology frame-boundary repair:

```text
[Battery]   13/37 verify_presentation_layers   PASS (5 s)
[Battery]   29/37 verify_field_intelligence    PASS (12 s)
[Battery]   37/37 verify_tree_hier_refit_engine PASS (1 s)
[Battery] 37/37 PASS (total 273 s)
[Battery] runner exiting (exit code 0)
```

- Overall battery verdict: **PASS**, runner exit 0.
- Focused windowed presentation verifier: **13/13 PASS**, including temporal allocation, static-history reuse, shared-output ownership, Spectrum parity, and live opt-out cleanup.
- Gridless control: **PASS**, with `snapshot_generation=1`, topology status `[1,105614,0,8192]`, and process exit 0.
- A targeted shift-during-readback probe discarded the stale query before worker submission and resolved the current query as topology generation 1.

The presentation timeout originated in synchronous global-RenderingDevice topology readbacks during an active camera frame. The repaired path seeds immutable sites from the existing CPU mirror, asynchronously stages the four live field/gradient buffers, rejects query generations superseded during either transfer or worker execution, and begins topology work only after the renderer consumes its first setup-backed frame. A query publication now makes missing topology immediately rebuildable even while simulation stepping is paused.

## Verdict

**ADOPT** the embodied field-intelligence implementation and causal demo. It satisfies FI0–FI9, the exact clear/restore experiment, negative controls, GPU layout checks, an actual windowed presentation run, and the complete 37/37 CassiCosmos battery.
