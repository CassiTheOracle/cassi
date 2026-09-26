# Particle Agglomeration — Cassi PDU merge design (matter formation at the particle level)

**Status:** DESIGN + numpy prototype + standalone GPU shader + verify probe (this wave). No
`cassi_sim.gd` edits (a parallel worker owns the sim-integration wave next).
**Repo:** `godot/space-sim`. New files only: this doc, `research/meshless/stage6_merge.py`,
`compute/cassi_particle_merge.glsl`, `scripts/verify_merge.gd`, `scenes/verify_merge.tscn`.
**Date:** 2026-08-13

---

## 0. The relationship to the meshless vision (honest framing)

MESHLESS_PLAN.md's matter-formation doctrine is **"matter is what a cell *becomes*
when it crosses the condensation threshold"** (§3.3, Stage 3, §8 R3): the *field* collapses a
condensed core into one matter particle (mass = Σρ·V, position = ρ-weighted centroid),
gated on the **peak-phase q_field = EY²+EI²** firing on a connected core.

This work is the **particle-level complement at the *other* end of the same cascade**: when
structure already exists as particles, *two* of them that come within a merge radius in an
already-coherent region coalesce. It does **not** create particles from the field (that is
Stage 3's job); it **grows** existing particles toward larger objects. The two stages form
one pipeline:

```
two-fluid field ──(condensation, field→matter)──▶ dust particles ──(this merge, matter→object)──▶
   accreting objects ──(BH condensation/σ-regularized accretion, object→BH)──▶ black holes
```

The relationship is made honest in the title: this is **matter *formation* FROM matter**
(agglomeration), the particle-level analogue of (and eventual hand-off to) the meshless
collapse. Key difference — the **gate quantity**:

| | Stage 3 (meshless collapse) | this merge |
|---|---|---|
| gate quantity | q_field = EY²+EI² (peak-phase magnitude) | q_coh = ρ²/(ρ²+φ⁻²+ε²) |
| gate sense | *above* threshold (condensation peak) | *above* threshold (coherent region) |
| object | connected cell core → one matter particle | pair (i,j) within R_m → one survivor |
| mass source | Σ ρ·V over the core | m_i + m_j (already-partcl) |

R3 resolved that condensation fires on q_field *because coherence is LOW at deviation peaks
by construction*. The merge gate is the opposite and complementary: coalescence happens
where coherence is **HIGH** (structure forms in coherent regions; non-coherent regions
free-stream). These are two sides of the same φ-anchored crossover — the field condenses
where it peaks, and the resulting objects only merge where they remain coherent. They do
not conflict; the distinction is exactly why the merge must use **q_coh, not q_field**.

---

## 1. Mass comes as per-particle `pos[i].w` today (Q3)

Verified in `cassi_sim.gd` + `cassi_nbody_gravity.glsl` + `cassi_mass_deposit.glsl`:

- `_init_particles` draws a **Salpeter IMF mass per particle**: `pos[i4 + 3] = m`
  (line 1766), Σ = `_total_init_mass`, `m_mean = _total_init_mass / N_particles`
  (line 2052). **Mass is per-particle and non-uniform.**
- The nbody KDK **preserves `pos[i].w` through integration** (`pos[i] = vec4(p_new, pos[i].w)`
  line 793) — mass rides the position buffer.
- `cassi_mass_deposit.glsl` reads `pos[i].w` as the deposited mass (`float mass = p.w`;
  `if (mass <= 0.0) return;` — zero-mass particles are skipped: a **built-in dead-particle
  convention already exists** at the deposit).
- `cassi_instancer.glsl` reads `pos[i].w` for **size-by-mass and the mass color gradient**
  (lines 164-178). So a merged object with summed mass, written to the survivor's `pos.w`,
  is *automatically* rendered larger by the instancer — **no instancer change needed**.

**Conclusion:** the merge works directly on `pos[i].w`. The merged survivor mass
= Σ of the merged particles' `pos.w`; dead particles get `pos[i].w = 0` (deposit skips,
instancer shows nothing, nbody force unaffected). The task's "per-particle mass buffer" is
therefore best realized as a **merge-owned mirror** so the merge never depends on the nbody
integrator's format, and the wiring wave binds it explicitly.

### Buffer-family contract (the merge writes this; wiring waves bind it)

ONE persistent per-particle merge-state family, `N_particles` entries — exactly the task's
"ONE new buffer family (per-particle mass + alive flag)", realized as:

| buffer | type | per particle | meaning |
|---|---|---|---|
| `alive` | float | 1.0 alive / 0.0 merged-away | the dead flag the deposit convention already understands |
| `mass` | float | current canonical mass (mirror of `pos.w` the merge owns) | survivor's summed mass after finalize |
| `mom` | vec4 | `xyz` = accumulated Σm·v into this particle, `w` = receive-count | momentum accumulation (folded into `vel` at finalize) |
| `cen` | vec4 | `xyz` = accumulated Σm·x into this particle | centroid numerator (folded into `pos`) |

Finalize (pass_mode 5) writes `pos[i].w = mass[i]` for alive i and `pos[i].w = 0` for dead i
(and folds `mom/cen` into `vel/pos`), so the existing deposit/nbody/instancer readers pick up
the merged state with **zero edits**. The vector buffers `mom`/`cen` are the *resolution
scratch* of the family (the atomics target); `w` doubles as the "received?" test and the
momentum-fold count. Wiring waves that want per-particle mass decoupled from `pos` bind
`mass`, `alive` (each `N_particles·4` B) and optionally the folded `pos`/`vel`.

---

## 2. The merge rule (Q1)

**Rule.** Two alive particles i, j merge iff
1. their min-image distance `d(i,j) ≤ R_m`, AND
2. the local coherence `q_coh` sampled at the pair **midpoint** exceeds the threshold:
   `q_coh(x) = ρ²/(ρ² + φ⁻² + ε²)`, ρ = EY+EI, ε = EY − φ·EI, `q_coh > Q_th`.
On merge: total mass and total momentum conserved → survivor position = mass-weighted
centroid, survivor velocity = momentum-weighted mean. The survivor is deterministic:
**the lowest-index member of each connected in-range, coherence-qualified cluster**
(§5). Merging is *not* a coalescing of a whole connected component in one step; it proceeds
as a directed acyclic collapse along strictly-decreasing indices, one hop per pass (§5).

**Threshold choice — `Q_th = φ⁻² ≈ 0.382`.** φ⁻² IS the framework's decoherence
cross-over (PHI_INV2), already the `q_min`/decoherence anchor in the instancer's approach
band and the q-denominator scale in the law itself (`q = ρ²/(ρ²+φ⁻²+ε²)` saturates to ~0.25
at ρ≈φ⁻²/... — the term φ⁻² in the denominator is precisely the level at which coherent
density and the decoherence scale balance). At `q_coh > φ⁻²` the local field is above the
coherence/diffusion balance → structure-forming; at `q_coh < φ⁻²` the region is dominated by
the decoherence floor → free-streaming. This is the single natural, parameter-free,
φ-anchored threshold available, and it matches the doctrine (the sim's small-deviation
background sits at q_coh ~ 1e-3…1e-1, well below; condensed attractor regions hit
0.947 ~ 1, above — so the gate cleanly separates background from structure).

**`R_m = ⅟₂·h₀`, `h₀ = 2·min(extent)/N_grid`** (half the reference grid cell). Justification:
the grid's spectral Poisson and TSC deposit cannot *resolve* two particles closer than ~1
cell — they sit in the same gravitational micro-well and deposit into the same cells. Merging
them at `R_m = ⅟₂h₀` is therefore a **resolution-conserving** operation (it removes a
numerically-duplicate degree of freedom), not a physics invention; it is small enough to
leave genuine resolved structure (≥1-2 cell separations) untouched. `R_m` is a push-constant
knob (`Rm_frac` on the host), so the G27 sensitivity sweep (§7) exercises it directly.

**Inelastic penalty — RECOMMEND conservative (momentum-only), let RealSim's drag dissipate.**
Rationale:
- RealSim (gravity_mode 4) already provides **three** per-particle dissipative terms
  (drag −γ·(ρ/ρ_ref)·v, viscosity −ν·(v − v_field), friction −μ·|a_g|·v̂) evaluated at each
  particle every step — they are *already* the kinetic-energy drain. An additional bespoke
  inelastic merge term would double-count the same physics and reintroduce a free parameter
  the doctrine deliberately avoided.
- Momentum-only merging keeps a **verifiable conservation invariant** (G29 ≲ 1e-3 on the
  GPU; exact in the float64 prototype G25 to 1e-12) — the cleanest possible gate.
- The merged object inherits the momentum-weighted mean velocity, so any residual relative
  kinetic energy of the pair is implicitly lost *without* a formula — the definition of
  perfectly inelastic coalescence (ΔKE = ½μ|v_i−v_j|² removed) is the natural inelastic
  content, and it is conserved-free (momentum only).
Documented forward option: an explicit inelastic term (e.g. damp the *relative* velocity
component by a factor) could be added behind a future push-constant toggle (default off),
but it is NOT needed to close this wave's gates and would complicate the conservation proof.

---

## 3. The q sample for the gate (Q4)

The gate needs **q_coh = ρ²/(ρ²+φ⁻²+ε²)**, which depends on ρ = EY+EI and ε = EY−φ·EI —
neither of which is the stored `_field_q` buffer. `_field_q` is `qv = EY²+EI²`
(cassi_two_fluid.glsl line 197: `q[id] = q_val` with `q_val = ey²+ei²`), a *different*
quantity, and is a derived buffer (could be stale if not refreshed). **The merge shader binds
FieldEY + FieldEI directly and computes q_coh in-shader** from a single trilinear sample of
EY and EI at the pair midpoint — exactly the nbody's fused-scatter trilinear map
(`gc = (wp·inv_ext)·hn + hn`, `hn = N/2`, periodic wraps). This is Q4's answer: do NOT use
`_field_q`; use EY/EI with the law's own combination. (If a future `_field_q` were made to
hold q_coh it would be an option, but today it holds q_field and must not be reused.)

The sample point is the **min-image midpoint** `(p_i + p_j)/2` of the pair (wrapped), so a
pair that straddles a high/q boundary gates on the region between them — the physical "is
the gap coherent" test. The planted-field gates place pairs deep inside uniform regions, so
the exact sample point is non-fragile.

---

## 4. Interaction with the BH sector + the meshless vision (Q5)

The merge is the **"dust → object" stage**; BH accretion is the **"object → BH" stage**:
```
dust ──merge──▶ object ──BH condensation/σ-regularized accretion──▶ BH
```
- **Feeds BH accretion:** the survivors are denser, more massive particles flowing in the
  two-fluid field. The existing BH point-source term (`bh_point_gravity`, σ-regularized,
  gated by `black_holes_enabled`) already attracts them; the condensation scanner
  (cassi_condensation.glsl) nucleates BH records from q_field peaks. The merge
  *concentrates* the particle mass so the σ-regularized BH term's softened wells become
  well-populated — merged objects are the natural accretion seeds (a future wiring wave can
  tie a survivor's mass/position into a BH record via the existing bh[4..] slots without new
  machinery).
- **Complementarity with the meshless collapse:** the meshless arm collapses *field* cores
  into matter; this merge grows *particle* clumps into objects. In the integrated sim a
  merged survivor is (a) a heavier deposition source (TSC mass ×, gating the field),
  (b) a bigger instancer sprite (size-by-mass, zero code), and (c) an eventual BH seed. The
  two stages therefore do not double-count: field→matter and matter→object→BH are sequential
  rungs, and the merge operationally *prepares* structure for the condensation pathway's
  extreme (BH) rung.

---

## 5. GPU implementation (Q2) — one shader, iterated; one persistent buffer family

**Structure.** `cassi_particle_merge.glsl` is ONE shader with a `pass_mode` selector
(mirroring cassi_nbody_gravity.glsl's pass_mode dispatch), plus a **spatial hash** built from
the nbody/deposit world→grid map. The hash shares the convention of mass_deposit/nbody (the
"occupancy hashing convention" the task references): cell index from `(wp·inv_ext)·hn + hn`.
**Honest note:** `cassi_occupancy.glsl` is a *box-classification* sampler (inner/face/corner
counters) — it has NO neighbor list. The neighbor-finding machinery is therefore built here:
a **cell-count → host prefix-sum → fill-list → 27-neighborhood scan**, using a coarse hash
grid sized to `R_m` (not the physics grid) so the neighborhood provably covers all
in-range pairs.

Scratch buffers (allocated by the probe; wiring wave re-allocates per contract): `cellCount`,
`cellStart`, `cellList` (uint). The **persistent** state is the §1 family (`alive`, `mass`,
`mom`, `cen`) — exactly the task's ONE new buffer family. The prefix-sum is host-side in this
standalone wave (a per-step GPU scan is a documented wiring-wave optimization to avoid a
stutter-class readback; at ≤50k particles the count readback is a few MB).

**Pass sequence (host loops until `mergeCount == 0` or a cycle cap; each
"cycle" is the (fold, best, sink, hop) reduction):**
- `0 reset` — `alive[i]=1`, `mass[i]=pos[i].w`, and `mom/cen` initialized to the
  canonical momentum/centroid numerators (`vel[i]·mass[i]`, `pos[i]·mass[i]`) so the
  first `fold` is an identity.
- `2 count` — alive i atomically `cellCount[cell(i)]++`; host prefix-sums →
  `cellStart`, copies to a running head `cellHead`.
- `3 fill` — alive i `slot = atomicAdd(cellHead[cell(i)],1); cellList[slot] = i`.
- Per cycle (repeat until `mergeCount == 0` or cap):
  - `1 fold` — for alive i with `mass[i] > 0`: `pos[i]=cen[i].xyz/mass[i]`,
    `vel[i]=mom[i].xyz/mass[i]`, `mom=cen=0`. (Folds the accumulated
    momentum/centroid numerators into canonical state; `mom/cen` are the running
    accumulation, re-initialized per cycle after folding.)
  - `4 best` — alive i scans own + 26 neighbor cells' lists and stores
    `best[i]` = min index over qualified alive neighbors (else i), and
    `sink[i] = (best[i] == i)` (i has no LOWER qualified neighbor).
  - `5 hop` — alive i with `best[i] < i AND sink[best[i]]`:
    `atomicAdd(mass[best], mass[i])`,
    `atomicAdd(mom[best].xyz, mass[i]*vel[i].xyz)`, `atomicAdd(mom[best].w, 1)`,
    `atomicAdd(cen[best].xyz, mass[i]*pos[i].xyz)`, `alive[i] = 0`, `mergeCount++`.
- `6 finalize` — write `pos[i].w = mass[i]` (alive) / 0 (dead); a final `fold`.

**Race-freedom (the crux).** A naive double-merge races: if i merges into j
while j merges into k in the *same* dispatch, j could read i's freshly-added
momentum before the atomic lands (or after), double-counting or stranding it.
The scheme above removes this with the **sink rule**: a particle i transfers
ONLY into a target `best[i]` that is a *sink* (`sink[best[i]]` — it has no
lower-index qualified neighbor, so it cannot itself forward this cycle). Hence
**a receiver is never also a forwarder in the same cycle**: 
- receivers (sinks) never forward → every transferred state is retained and
  then folded by the next cycle's `fold`, so it is forwarded (if at all) in a
  later cycle *after* being folded into canonical `pos/vel/mass` — no
  mid-cycle read of a being-written accumulator.
- each connected qualified cluster has exactly one sink (its minimum index),
  so every cluster still collapses, over `O(diameter)` cycles, to that member,
  and the transfer is acyclic (index strictly decreases along every edge).
Momentum/mass are exactly conserved: each cycle moves the source's full
canonical state to a sink that survives the cycle, and a sink's later
forward carries its entire accumulated state.

**Resolution scheme choice.** Atomic-CAS union-find over the full graph was
rejected (needs a `rep[]` re-bind + convergence over arbitrary graphs, heavier
than the observed per-step merge rate warrants). The **lowest-index-sink
iterative reduction** is instead: at ≤50k particles with an expected per-step
merge rate of a handful-to-thousands, each cycle is O(N_particles · 27 ·
⟨cell occupancy⟩) and the host loop (≤ K=16 cycles) is cheap; it is standard,
provably conservative, and deterministic modulo fp accumulation order (the
*merge set* is a fixed function of the input). Scratch: `best` (int) and
`sink` (float) per particle plus the cell-hash buffers.

**Float atomics:** `GL_EXT_shader_atomic_float` (already used and verified on this
RX 7900 XTX / Godot 4.7 by cassi_mass_deposit.glsl) provides `float atomicAdd`; the receive
counter `mom.w` uses `float atomicAdd(…, 1.0)`.

---

## 6. Gates

| gate | scope | assertion |
|---|---|---|
| G25 | numpy (stage6) | random cloud + planted close pair: total mass & total momentum conserved to ~1e-12 (float64) across the merge |
| G26 | numpy | identical pairs in LOW-q regions do NOT merge; the SAME pairs in HIGH-q regions DO (same seed) |
| G27 | numpy | small collapsing cluster (RealSim drag on): merge reduces count(t) monotonically while mass stays constant; R_m sensitivity reported |
| G28 | GPU vs numpy | GPU merge (spatial hash + float atomics) merges the SAME planted pairs with the SAME masses as the exact numpy reference (≤1e-3 relative) |
| G29 | GPU | GPU momentum conservation ≤ 1e-3 |

---

## 7. Prototype gates (run: `python stage6_merge.py`), then the GPU probe

`stage6_merge.py` is the exact float64 reference the GPU must match: direct O(N²) pair scan
(same rules, same deterministic lowest-index collapse), the planted random/high-low/collapse
tests (G25-G27), and — when `_diag/merge_gpu.json` exists — the GPU-vs-reference comparison
(G28/G29), mirroring how stage5_verify.py consumes the FMM GPU dump.

`verify_merge.gd` (self-contained local-RD probe, windowed console exe — NEVER --headless,
per the machine's no-RD rule): builds the synthetic planted input + a piecewise-constant
EY/EI field (HIGH-q region: EY=φ, EI=1 → q_coh≈0.947; LOW-q region: EY=EI=0.05 → q_coh≈0.03),
runs the merge pass sequence, dumps `_diag/merge_gpu.json` (input pos/vel/mass/alive + EY/EI +
final alive/pos/vel/mass + mergeCount), and does local structural checks (pipelines build, no
NaN). `stage6_merge.py` then computes G28/G29 from the identical planted input.

---

## 8. Honest caveats

- **No sim edits this wave** — the wiring (dispatch in `_physics_step`, buffer allocation,
  G_N re-calibration for merged mass, optional inelastic toggle) is a documented hand-off to
  the integration worker. The §1 buffer contracts are exact so that worker binds without
  re-deriving.
- The **host prefix-sum** per merge call is fine standalone; a wiring wave should add a GPU
  exclusive scan to avoid a per-step readback stall (the codebase already treats 0.5 s
  readbacks as a stutter source).
- Dead particles stay in `pos[]` with `pos[i].w = 0` (never compacted this wave). The deposit
  already skips them; compaction/reindexing is a wiring/GC concern.
- Determinism is exact for the *merge set*; individual accumulated masses differ by fp
  summation order (bounded by G28's 1e-3).
