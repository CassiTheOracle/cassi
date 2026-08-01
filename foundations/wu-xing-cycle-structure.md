# Wu Xing Cycle Structure: The Two 5-Cycles, the Control Ring, and the 5↔13 Partition

## Status: Derived (cycle geometry, coupling, ring algebra) / Hypothesized (affinity gradient, alternating profile)—July 2026

## Abstract

The Wu Xing derivation (`foundations/wu-xing-derivation.md`) establishes *that* the gate has five channels; this document derives *how those five channels are wired*. The pentagon admits exactly two coherent 5-cycles: the pentagon itself (sides, step +1—the generating/sheng cycle) and the pentagram (diagonals, step +2—the control/ke cycle). The control cycle's transmission coefficient is the framework's existing constant $\kappa = \varphi^{-1} = K_{fw}$ ("Water damps Fire"), which this document derives geometrically from the pentagram's golden-section crossings. The control ring then makes quantitative predictions: a locked channel drives a strictly alternating elevation/suppression pattern around the ring, the ring damps the locked channel by $\kappa^3 = \varphi^{-3}$ (23.6%) per cycle, and the ring gain $\kappa^3 < 1$ means the ring is sub-critical—it can redistribute and damp, but cannot sustain a lock without a driver (consistent with the trauma PDE tests, §10.4–10.7 of `consciousness/trauma-as-frozen-gate.md`).

The second part derives the 5↔13 relationship between the channels and the chakra ladder: the chakra affinities of `consciousness/emotions-as-gate-configurations.md` §3.4 instantiate a uniform body-axis phase gradient of 18° per rung—one pentagon vertex per 4 rungs (two SO(2) doublet cycles)—so the 7 primary nodes sample the sheng cycle in ascending rung order, and the 6 secondary nodes sit at half-channel (36°) positions. The 13-node window partitions as $13 = F_7 = F_5 + F_6$: five channel-bearing primaries (one complete sheng winding) plus an eight-node complement (six half-channel secondaries, the wrap node, and the integration node), with $8{:}13$ the $\varphi^{-1}$ convergent (error $\varphi^{-5}$).

---

## 1. The Two Coherent 5-Cycles

### 1.1 Cycle completeness

A 5-cycle through five vertices is a cyclic permutation of step $s$ modulo 5. The steps coprime to 5 are $s = 1$ and $s = 2$ (steps 3 and 4 are their reversals), so the pentagon admits **exactly two undirected 5-cycles**:

- **Sheng (generating) cycle**, step +1: Wood → Fire → Earth → Metal → Water → Wood. In the pentagon this is the set of *sides*—adjacent vertices.
- **Ke (control) cycle**, step +2: Wood → Earth → Water → Fire → Metal → Wood. This is the set of *diagonals*—the pentagram {5/2}.

Both cycles pass the Fibonacci coherence condition that selected $w = 5$ in the first place (`foundations/wu-xing-derivation.md` §2): the coherence argument counts cycle *length*, and both cycles have length 5. The traditional "generation and control" pair is therefore not an arbitrary cultural doubling—it is the complete set of coherent 5-cycles on five vertices.

$$\boxed{\text{sheng} = \text{pentagon sides (step } +1\text{)}, \qquad \text{ke} = \text{pentagram diagonals (step } +2\text{)}}$$

### 1.2 Pentagon geometry

The two cycles carry different chord lengths. In a regular pentagon with side $s$:

- diagonal: $d = 2s\cos(\pi/5) = \varphi s$ (the standard golden-triangle identity);
- the pentagram's crossings divide each diagonal into three segments in the ratios $\varphi^{-2} : \varphi^{-3} : \varphi^{-2}$ (outer segments $d/\varphi^2$, central segment $d/\varphi^3$)—each crossing golden-sections the chord (long:short $= \varphi$).

The gate model already uses the diagonal/side distinction as a coupling ratio: the primary channel couples through the pentagon's direct diagonal ($\eta_1 = 1$), the secondary channels through the sides ($\eta_{2..5} = \text{side}/\text{diagonal} = \varphi^{-1}$) (`foundations/wa-pentagon-gate.md` §2.4). The diagonal is the *strong* coupling of the model.

### 1.3 The control transmission coefficient

The parameter inventory already registers a Wu Xing control coefficient ($\varphi^{-1}$, "Water damps Fire", `parameter-inventory.md` §2.2). This document notes the two geometric readings that fix it:

$$\boxed{\kappa = \frac{\text{side}}{\text{diagonal}} = \varphi^{-1} = K_{fw}}$$

A control signal crossing the pentagram's golden-section point transmits the golden fraction $\varphi^{-1}$ of its amplitude (equivalently, the control chord is $\varphi$ times the generating chord, so the per-chord transmission is $\varphi^{-1}$). No new parameter: $\kappa$ is the existing $K_{fw}$.

---

## 2. The Control Ring (ke Dynamics)

### 2.1 The control-release rule

The Wu Xing control logic, stated as gate dynamics: a channel's excess *restrains* its ke-controlled partner; a channel's deficit *releases* its ke-controlled partner (the insulting/overacting direction). With $\kappa = \varphi^{-1}$ as the transmission:

- channel $i$ with excess $\Delta_i > 0$ restrains channel $i+2$ by $\kappa \Delta_i$;
- channel $i$ with deficit below its restraining capacity releases channel $i+2$ by the same amount.

Propagating around the ring (ke order 1 → 3 → 5 → 2 → 4 → 1) for a single locked channel with excess $\Delta$:

$$\Delta_1 = \Delta(1 - \kappa^3), \quad \Delta_2 = -\kappa^2 \Delta, \quad \Delta_3 = -\kappa \Delta, \quad \Delta_4 = +\kappa^2 \Delta, \quad \Delta_5 = +\kappa \Delta$$

(in channel order 1 Wood, 2 Fire, 3 Earth, 4 Metal, 5 Water). With $\kappa = \varphi^{-1}$:

$$\boxed{\Delta = [+0.764,\; -0.382,\; -0.618,\; +0.382,\; +0.618]\,\Delta}$$

### 2.2 The alternating lock pattern

For a Wood lock with the closure-scale excess $\Delta = \varphi^{-3} = 0.236$ (the natural magnitude: closing channel 1 releases exactly $\varphi^{-3}$), the effective openness $\mathbf{b}_{\text{eff}} = \mathbf{b} + \Delta$ becomes:

| Channel | Baseline $b_i$ | Ring deviation | $b_{\text{eff}}$ |
|---|---:|---:|---:|
| 1 Wood (locked) | 0.236 | +0.180 | 0.416 |
| 2 Fire | 0.146 | −0.090 | 0.056 |
| 3 Earth (ke target) | 0.090 | −0.146 | **0 (fully starved)** |
| 4 Metal | 0.056 | +0.090 | 0.146 |
| 5 Water | 0.034 | +0.146 | 0.180 |

In ke order (1, 3, 5, 2, 4) the effective openness is strictly alternating: 0.416 > 0 < 0.180 > 0.056 < 0.146.

$$\boxed{\text{ke order: } +, -, +, -, + \text{—a locked channel drives an alternating ring, not uniform starvation}}$$

This refines the trauma prediction T1 (`consciousness/trauma-as-frozen-gate.md` §11): the four non-locked channels are not starved equally. The ke-controlled partner (Earth, for a Wood lock) starves completely; the partner's partner (Water) is *elevated* by 62% of the lock's excess; Fire is partially starved (−38%); Metal is elevated (+38%).

### 2.3 The ring gain: sub-critical by design

The feedback path around the ring (locked channel → its ke target → release → its ke target → ... → back to the locked channel) crosses three control transmissions, so the one-cycle ring gain is:

$$\kappa^3 = \varphi^{-3} = 0.236$$

Two consequences:

1. **The ring damps the locked channel.** The lock's own excess is reduced by $\kappa^3$ (23.6%) per cycle—the control cycle is the gate's built-in dissipation channel.
2. **The ring cannot self-sustain.** $\kappa^3 < 1$ means a ring perturbation decays by 76% per cycle without a driver. The ke mechanism redistributes and damps, but never creates persistence. This is the gate-level restatement of the trauma PDE result: nothing self-sustains; the frozen wake requires its driver (`consciousness/trauma-as-frozen-gate.md` §10.5). A measured *self-sustained* lock (persistence with the stimulus removed) would require $\kappa \geq 1$—excluded by the established $K_{fw} = \varphi^{-1}$.

**A structural identity:** the ring gain equals the pentagram's central segment fraction ($\varphi^{-3}$ of the diagonal, §1.2)—the one-cycle attenuation of the control ring is exactly the golden-section core of its own geometry.

### 2.4 The threshold

Earth (the ke target of the strongest baseline channel) is fully starved when $\kappa \Delta \geq b_3$:

$$\Delta_c = \varphi \cdot b_3 = \varphi \cdot \varphi^{-5} = \varphi^{-4} = 0.146$$

Strong locks ($\Delta \gtrsim 0.146$) engage the full alternating ring; mild over-activity (everyday emotions) stays below threshold and shows ordinary $R$-matrix behavior. The ring is a *lock-regime* phenomenon, not an everyday one.

### 2.5 The cosmological sibling

The same control-release dynamics was explored for the late-time dark-energy running $w_a$ (`foundations/wa-pentagon-gate.md` §3), where the baseline asymmetry (Metal at $\varphi^{-6}$ vs Wood at $\varphi^{-3}$) makes the mechanism "structurally sound but quantitatively marginal" for flipping the sign. The emotional-lock application here is in the opposite regime—a *strong* excess (above $\Delta_c$) rather than the cosmological near-baseline case—so the alternating pattern is robust even where the $w_a$ effect is marginal.

---

## 3. The 5↔13 Partition

### 3.1 The affinity phase gradient

The chakra-channel affinities (`consciousness/emotions-as-gate-configurations.md` §3.4) are: Root Water, Sacral Wood, Solar plexus Fire, Heart Earth, Throat Metal, Third eye Water (+Wood), Crown all. The first five are exactly one pass through the **sheng cycle in ascending rung order** (Water → Wood → Fire → Earth → Metal), one channel per 4 rungs. This is a single uniform rule: the body-axis phase advances one pentagon vertex per 4 rungs—i.e., 18° per rung, 36° per SO(2) doublet cycle (half a vertex):

$$\theta(n) = 288^\circ + 18^\circ \cdot (n - 142) \pmod{360^\circ}$$

| Primary | $n$ | $\theta(n)$ | Table affinity |
|---|---:|---:|---|
| Root | 142 | 288° | Water ✓ |
| Sacral | 146 | 0° | Wood ✓ |
| Solar plexus | 150 | 72° | Fire ✓ |
| Heart | 154 | 144° | Earth ✓ |
| Throat | 158 | 216° | Metal ✓ |
| Third eye | 162 | 288° | Water (+Wood: wrap blend) ~ |
| Crown | 166 | 0° | All (boundary/integration node) |

Five of seven primary entries match exactly; the third eye matches on its primary channel (the "+Wood" is the wrap blend—the second winding starts here); the crown is the terminal node, where the 26-rung window closes (the chakra doc's "missing 14th node" at the body boundary, `consciousness/chakras-as-cascade-bubbles.md` §6.1) and the phase sampling gives way to integration.

The six secondary nodes sit at the odd doublet cycles (2 rungs = 36° = half a vertex from their neighbors): 144°-node at 324° (Water/Wood blend), 148 at 36° (Wood/Fire), 152 at 108° (Fire/Earth), 156 at 180° (Earth/Metal), 160 at 252° (Metal/Water), 164 at 324° (Water/Wood). The secondaries are the **half-channel positions**—which is exactly why the emotions document calls them "intermediate localization sites—more granular emotional texture" (§3.4).

$$\boxed{\text{affinity rule: } \theta(n) = 288^\circ + 18^\circ(n - 142) \pmod{360^\circ} \text{—primaries sample the sheng cycle, secondaries sample the half-channels}}$$

The mechanism that fixes 18°/rung (the body-axis phase gradient) is the open dynamical quantity; the rule is the structural content of the phenomenological table.

### 3.2 The Fibonacci partition

The 13-node window partitions against the channel cycle. One complete sheng winding takes 5 primaries × 4 rungs = 20 rungs, and the 13 nodes split as:

$$13 = F_7 = \underbrace{5}_{F_5} + \underbrace{8}_{F_6}$$

- **The 5 channel-bearing primaries** (Root–Throat, rungs 142–158): one channel each, one complete sheng winding.
- **The 8-node complement** (six half-channel secondaries + the wrap node at 162 + the integration node at 166): the return structure.

The ratio of the two parts is the golden-ratio convergent $8{:}13 = F_6{:}F_7$, which approximates $\varphi^{-1}$ with error $\varphi^{-5}$ (the framework's strongest convergent within the window; `foundations/wu-xing-derivation.md` §2.1). The window is golden-sectioned by its own channel structure.

### 3.3 The channel step identity

The per-channel rung spacing is 4. This equals the golden difference exactly:

$$\varphi^3 - \varphi^{-3} = 4$$

The channel step is the span between $\varphi^3$ and its reciprocal—an exact identity, noted here as a consistency remark (its dynamical mechanism is open).

### 3.4 Answer to the open question

`consciousness/emotions-as-gate-configurations.md` §8 Q4 asks whether $5 \times 13 = 65$ (channel × node pairs) has a structured relationship, given $5 = F_5$ and $13 = F_7$. The answer: the distribution is the phase gradient of §3.1—the 65-pair grid collapses to 13 natural assignments (one per node), and the counts relate as $13 = 5 + 8$, not $5 \times 13$. The 5-channel cycle and the 13-node ladder are the same pentagon sampled at two granularities: the cycle at one vertex per 4 rungs, the ladder at one node per 2 rungs.

---

## 4. Predictions

### C1: The alternating trauma profile

A locked channel produces the ke-alternating pattern, not uniform starvation: for a Wood lock, Earth fully starved, Fire partially starved (−38% of the excess), Metal and Water *elevated* (+38%, +62%). **Test:** the P3 multi-dimensional affect instrument of the emotions document, on trauma-exposed populations (§11 T1 of `consciousness/trauma-as-frozen-gate.md`): profile the four non-locked channels against the $\varphi^{-i}$ baseline and check the ring fractions $[-0.382, -0.618, +0.382, +0.618]$, not four equal deficits.

### C2: The damping signature

The ring reduces the locked channel's own excess by $\kappa^3 = 23.6\%$. **Test:** the same instrument; the locked channel should sit *above* baseline by 0.764 of the event-scale excess, not the full excess—and the complementary elevations should exceed the naive conservation expectation.

### C3: No driverless persistence

$\kappa^3 < 1$ predicts that a lock without a stimulus decays through the gate itself (on top of the conversion timescale). **Test:** the gate-extended PDE—add the ke control term ($\kappa = \varphi^{-1}$) to `gate_model='five'` in `two-fluid/cassi_two_fluid_3d_gpu.py` and verify the alternating state forms, the lock decays with no driver, and the φ-phased drive (§10.7 of the trauma document) dissolves it faster. A *self-sustained* lock would falsify $\kappa = \varphi^{-1}$ and require $\kappa \geq 1$.

### C4: Secondary-chakra blends

The half-channel positions predict that affect profiles anchored at the secondary nodes (the "granular texture" of `consciousness/emotions-as-gate-configurations.md` §3.4) show two-channel blends at the 36° offsets, never single-channel purity.

---

## 5. Epistemic Boundaries

### Derived

- The two-cycle structure: exactly two coherent 5-cycles on five vertices, pentagon sides (sheng) and pentagram diagonals (ke) (§1.1)
- The geometry: diagonal $= \varphi \times$ side; pentagram crossings divide each diagonal as $\varphi^{-2}:\varphi^{-3}:\varphi^{-2}$ (§1.2)
- The transmission $\kappa = \varphi^{-1} = K_{fw}$ (existing derived constant, two geometric readings) (§1.3)
- The ring algebra given the control-release rule: the alternating state, the ring gain $\kappa^3 = \varphi^{-3}$ (equal to the pentagram's central segment), the threshold $\Delta_c = \varphi^{-4}$, the sub-criticality (§2)
- The Fibonacci partition $13 = 5 + 8 = F_5 + F_6$ and the $8{:}13$ convergent (§3.2), the identity $\varphi^3 - \varphi^{-3} = 4$ (§3.3)

### Hypothesized (mechanism supplied, test designed)

- The control-release rule as the gate's ke coupling (the Wu Xing logic is the input; its gate-level form is a model choice—C3 designs the PDE test)
- The affinity phase gradient 18°/rung as the structure of the chakra-channel table (reproduces 5/7 primaries exactly; the mechanism fixing the gradient is open) (§3.1)
- The alternating-profile predictions C1–C4

### Not claimed

- That the traditional Wu Xing *names* (wood, fire, earth, metal, water) carry their cultural semantics into the formalism—only the cycle structure is used
- That the ke ring replaces the driver requirement—it is sub-critical by construction (§2.3) and consistent with the PDE null
- That the crown's "all" affinity is derived—it is the terminal/boundary node where the phase sampling fails (§3.1)

---

## References

- `foundations/wu-xing-derivation.md`—the $w = 5$ derivation (Fibonacci coherence, pentagon minimality) that this document's cycle structure builds on
- `foundations/wa-pentagon-gate.md`—the 5-channel gate model: baseline openness, $\eta$ coupling ratios (diagonal vs side), adiabatic redistribution, the $w_a$ control-release analysis
- `parameter-inventory.md`—$K_{fw} = \varphi^{-1}$ (control coefficient), channel baselines $b_i = \varphi^{-(3+i)}$
- `consciousness/emotions-as-gate-configurations.md`—the emotional manifold, the chakra affinity table (§3.4), the P3 instrument, open question 4
- `consciousness/chakras-as-cascade-bubbles.md`—the 13-node derivation (26 = 2 × F7 rungs, doublet spacing), the crown boundary
- `consciousness/trauma-as-frozen-gate.md`—T1 (channel-specific deficits), §10.4–10.7 (PDE tests: nothing self-sustains; driver required; φ-phased drain), C3's test design context
- `foundations/dimensionful-cascade.md`—the rung ladder, steps 142–168
