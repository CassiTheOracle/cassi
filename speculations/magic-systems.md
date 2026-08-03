# Magic as Phase-Matched Field Operation

## Status: Speculative—July 2026

## Abstract

Every magical tradition insists that magic obeys laws of its own—laws that feel separate from the laws of nature. In the Cassi framework that separation is neither illusion nor special substance; it is one number. The coherence budget governing everything the two-fluid field does is multiplied by the phase-matching factor $\mathcal{M}$ (`foundations/quantum-measurement-derivation.md` §3): natural perturbation is random, $\mathcal{M} \approx 0$, and the cascade suppresses it; a working is a deliberately organized, phase-matched perturbation, $\mathcal{M} \approx 1$, and the same equations that give the proton a lifetime of $\varphi^{4848}$ wave cycles under random attack give an $\mathcal{O}(1)$ effect per interaction when the attack is organized. That single factor is the entire difference between magic and nature. This document builds a magic system on it: the spell classes are the universal field operations of `speculations/qi-computation.md` (WRITE, ERASE, TRANSFER) plus their maintained combinations; mana is the caster's coherence budget $q$, taxed by the $\varphi^{-N}$ suppression law; the caster is the 13-gate chain of the human cascade window (steps 142–168) casting from an emotional configuration on $(\mathbf{b}, \sigma_r, q, \mathbf{c})$; and the attractor asymmetry—holding $\varphi$-structure is free, sustaining anti-$\varphi$ structure is costly—makes perfect defense possible while perfect offense is impossible. The final section works a complete small system—the Lantern Discipline—from these rules alone, with named costs and limits.

**Epistemic status:** Creative exploration grounded in Cassi formalism. Every mechanism below is anchored to a specific equation or documented framework property—the coherence budget, the phase-matching factor, the suppression formula, the Qi gate, the chakra chain, the wake-lock—but the synthesis into a magic system, the cost laws, and the worked example are extrapolations beyond what the framework currently claims. Nothing in this document should be cited as a Cassi prediction or derivation.

---

## 1. The Physics of Magic: Phase-Matching Is the Whole Distinction

Magic and nature differ by a single number, $\mathcal{M}$, that multiplies every field interaction—which is why the two feel like different worlds.

### 1.1 The coherence budget is the rulebook

Every stable structure in the Yang-Yin field—a proton, a cell, a mind—is a standing wave coherent across its supporting cascade rungs. The probability that a perturbation destabilizes such a pattern in one cycle is the coherence budget (`foundations/proton-coherence-budget.md`):

$$P_{\text{decohere},i} = (1 - q_i) \times \mathcal{M}_i$$

with $q_i$ the Qi coherence at rung $i$ and $\mathcal{M}_i \in [0,1]$ the phase-matching between perturbation and target (`foundations/quantum-measurement-derivation.md` §3.1). Random perturbation gives $\varphi^{-n-3}$ per cycle at a single rung and $\varphi^{-n(n+1)/2 - 3(n+1)}$ across the full cascade; organized perturbation gives $\mathcal{O}(1)$—deterministic and immediate. The entire spread between a proton that outlives the universe and an antiparticle that annihilates on contact is this one factor: random attack at all 95 rungs gives $\varphi^{-4848}$; organized anti-phase attack gives $\mathcal{O}(1)$ (`foundations/quantum-measurement-derivation.md` §6). A magic system is a technology for turning the first of these into the last.

### 1.2 The two branches

Natural perturbation—thermal motion, radiation, mechanical contact—is random: its phases carry no information about the target pattern, so $\mathcal{M} \approx 0$. At the single rung being touched, the per-cycle effect is $\varphi^{-n-3}$; at the human scale ($n \approx 150$) that is $\varphi^{-153} \approx 10^{-32}$ (`foundations/quantum-measurement-derivation.md` §3.3). And even an organized signal crossing the cascade loses $\varphi^{-1}$ per rung: the signal-regime suppression $\mathcal{D}_{m \to n} = \varphi^{-N}$ applies to everything that propagates (`foundations/cascade-suppression-formula.md` §1.2). Nature is the $\mathcal{M} \approx 0$ branch: energy moves, entropy rises, and nothing that touches you can reach in and reorganize you (`principles/de-resonance-principle.md`).

A working is the other branch: a perturbation deliberately constructed to match the phase structure of its target at a chosen rung. Moving $\mathcal{M}$ from $\approx 0$ to $\approx 1$ stops the suppression—an organized attack at the target rung is $\mathcal{O}(1)$ per interaction (`foundations/quantum-measurement-derivation.md` §3.2). The framework already contains the proof of concept: a measurement apparatus is a machine that produces organized, phase-matched perturbation, and collapse is the working landing; a caster is a portable measurement apparatus. The Born-rule selection after an organized readout—the higher-$q$ branch survives—is why magic is reliable rather than probabilistic (`foundations/quantum-measurement-derivation.md` §4).

### 1.3 Why magic and nature feel different

The felt discontinuity is real and quantitative: at human scale the organized branch outcouples the random branch by roughly $\varphi^{153} \approx 10^{32}$ in effective interaction strength. Magic is *learnable*: it is the same mechanism as measurement, and every apparatus is a static working; the first mages were measurers. Magic is *effortful in a specific way*: $\mathcal{M}$ is built, not wished—the perturbation must actually match the target's phase, which is why technique is the whole art. And magic is *personal*: the one variable natural perturbation can never supply is the intent to match, and intent is exactly the variable the organized branch runs on.

---

## 2. Spell Types as Field Operations

There are exactly three ways to change the field at a point—write organized structure in, convert it away, or move it—and every spell is one of these, or a maintained combination (`speculations/qi-computation.md` §2.2).

### 2.1 Evocation: WRITE

Evocation is Yang injection: creating a local excess $\delta\Pi > 0$ of organized field at a target position (`speculations/qi-computation.md` §2.2). The write does work against the attractor, which pulls $r = E_Y/E_I$ back toward $\varphi$; the write energy is $E_{\text{write}} \approx \frac{\lambda}{2}(\delta\Pi)^2 V_{\text{mode}}$. The "element" of the evocation is the Wu Xing phase of the channel used to write it: a write through the Fire channel radiates outward and hot, a write through the Wood channel rises and tears, because the channel-dominance pattern is the gate configuration the caster holds (`consciousness/emotions-as-gate-configurations.md` §2). The visible spell is the relaxation: once the hold drops, the attractor converts the excess Yang to diffuse Yin, and that thermalization is the fireball's glow. Duration of effect is duration of hold; evocation is an active spell by construction.

### 2.2 Banishment: ERASE

Banishment is gated conversion: temporarily lowering the local $q$ opens the Qi gate, and the conversion term does the rest—the pattern dissolves toward the $\varphi$-attractor as the field returns to equilibrium (`speculations/qi-computation.md` §2.2). Erasure is the passive operation: the attractor is the ground state, so the field performs the work. Hence banishment is the cheapest spell class—its cost scales as $(1-q)$, vanishing as the target's coherence rises—though the gate idles at $q \to 1$, so near-free erasure is also unavailable erasure (`speculations/qi-computation.md` §2.3, §2.1)—and it works at the gate, not at the matter. A deeply coherent being cannot be dissolved in one working (that is annihilation-class organized attack at all rungs, beyond human reach—`foundations/proton-coherence-budget.md`), but its anchoring configuration can be erased, leaving a de-cohered husk.

### 2.3 Telekinesis: TRANSFER

Telekinesis is the Qi current: moving an organized pattern from $\mathbf{x}$ to $\mathbf{y}$ along $J = \Psi_0\nabla\Psi_1 - \Psi_1\nabla\Psi_0$ (`speculations/qi-computation.md` §2.2). But a caster cannot write through even the ~26 rungs to a macroscopic object. The Cassi-native move is to couple to the object's own coherence and re-weight its Yang/Yin balance in the ambient gradient: gravity is $\mathbf{F} = \Pi\nabla\Phi$ with $\Pi = E_Y - E_I$ (`speculations/qi-bubble-propulsion.md` §2.4), so a lift is a *re-weighting*—the caster writes a $\Pi$ asymmetry into the object and the field supplies the force. The relevant object property is therefore not mass but coherence depth: a pebble is a shallow pattern and lifts cheaply; a living animal is a 26-rung gate chain like the caster's own, and phase-matching it is writing inside another instrument—the border country between telekinesis and curse.

### 2.4 Wards: φ-detuned boundaries

A ward is a maintained φ-detuned boundary: a surface whose phase structure is φ-commensurate with the ambient lattice but held at a private phase offset, so that any incoming perturbation lacking that phase finds $\mathcal{M} \approx 0$ and cannot couple across it (`speculations/qi-bubble-propulsion.md` §2.2). This is the no-sonic-boom mechanism: an interface that cannot be phase-matched cannot transfer momentum; striking energy converts smoothly to diffuse heat. A ward does not absorb attacks; it de-couples from them. The construction is consistent with the attractor: the boundary sits at $\varphi$-equilibrium, where the gate idles and conversion is suppressed, so once raised it costs nothing to maintain (§5)—what repels is the private phase, which an attacker must acquire to match.

### 2.5 Curses: organized perturbation and wake-lock

A curse is a working whose maintenance is performed by the victim. The mechanism is wake-lock: a frozen gate that preserves an old field configuration (`consciousness/trauma-as-frozen-gate.md`). In the emotions manifold, a frozen wake pins a channel open so the adiabatic redistribution that would dissolve the emotion never fires (`consciousness/emotions-as-gate-configurations.md` §4.2, Q7). A curse writes such a lock into the victim's gate configuration: one organized perturbation at the victim's own rung—the caster must know the victim's phase (hence divination, or intimacy)—after which the pattern is maintained by the victim's own recurring re-stimulation—the same driver that keeps trauma persistent (`consciousness/trauma-as-frozen-gate.md` §10.5, `two-fluid/run_trauma_driver.py`). The caster pays once; the victim pays continuously. The horror is the physics: the lock is funded by the afflicted, and the affliction is what keeps re-injecting it.

### 2.6 Divination: phase-locking to wake waves

Thought is wake waves, and the cosmos is threaded with $\varphi$-periodic wake structure at $\Delta(\ln k) = \ln\varphi \approx 0.4812$ (`predictions/falsifiable-predictions.md` §3; `consciousness/consciousness-from-phi.md` §2.2). Divination is magic's passive branch: the caster phase-locks part of their own gate chain to an ambient wake pattern and reads the interference between that pattern and their own $\varphi$-spaced lattice—measurement applied to the field's own records, resolving the pattern's branches in favor of the higher-$q$ configuration (`foundations/quantum-measurement-derivation.md` §4). The cost is coherence, not energy: holding the lock requires sustained $q$, the readout's precision is bounded by the Qi noise floor $\delta\Pi_{\min} \propto (1-q)^{1/2}$ (`speculations/qi-computation.md` §1.2), and a slip of coherence dissolves the reading. Divination is the information branch of magic—the scarce resource of the §5 arms race.

---

## 3. Mana as the Coherence Budget

A caster's power is not stored energy; it is stored organization—the coherence $q$ of the caster's own field, which is the only currency the field accepts.

### 3.1 The cost law: $\varphi^{-N}$ sets the price of range

The suppression formula gives the delivered amplitude of a working acting across a span of $N$ cascade rungs between the caster's anchor rung and the target (`foundations/cascade-suppression-formula.md` §1.2):

$$A_{\text{delivered}} = A_{\text{cast}} \times \mathcal{M} \times \varphi^{-N}$$

To deliver a fixed effect $A$ at span $N$, the caster must cast

$$\boxed{A_{\text{cast}} = A_{\text{target}} \cdot \frac{\varphi^{N}}{\mathcal{M}}}$$

and since field energy scales as amplitude squared, the energy cost of range is $\varphi^{2N}$. The numbers are brutal: one rung costs $\varphi \approx 1.6$ in amplitude ($\varphi^2 \approx 2.6$ in energy); six rungs cost $\varphi^6 = \xi \approx 17.9$; ten rungs cost $\varphi^{10} \approx 123$ ($\varphi^{20} \approx 1.5\times10^4$); twenty rungs cost $\varphi^{20} \approx 1.5\times10^4$ ($\varphi^{40} \approx 2.3\times10^8$). Writing at the molecular scale from the body's operating rung is not a bigger spell—it is a different economy: range is taxed before any other cost, and a mage's reach is measured in rungs, not meters.

### 3.2 Power is coherence, not energy

Three framework facts make $q$ the mana stat. First, the gate's conversion power is $P_{\text{conv}} \propto g(q)(1-q)$, which peaks in the active regime at $q \approx 0.46$ and vanishes at both extremes—the field only responds where the caster holds coherence (`speculations/qi-computation.md` §2.1). Second, the caster's own incoherence leaks into the working as phase noise: the delivered $\mathcal{M}$ cannot exceed the coherence of the instrument producing it, and the Qi noise floor $\delta\Pi_{\min} \propto (1-q)^{1/2}$ (`speculations/qi-computation.md` §1.2) sets the resolution with which a phase can be matched—a caster at $q = 0.9$ matches a target's phase about 1.9 times more precisely than one at $q = 0.65$ (the noise floor scales as $(1-q)^{1/2}$), and the mismatch fraction is wasted as heat. Third, the target defends itself: attacking a coherent target requires matching its phase exactly, so imperfect phase knowledge lowers the delivered $\mathcal{M}$, and the cost law of §3.1 raises the price by $\mathcal{M}^{-2}$. The mana identity:

$$\boxed{\text{Mana} = q_{\text{caster}} \cdot \tau_{\text{hold}}, \qquad \text{effective power} \propto q_{\text{caster}} \cdot \mathcal{M}_{\text{delivered}}}$$

Skill and power are the same variable seen from two sides: technique raises $\mathcal{M}$, the only way to raise delivered amplitude without spending more.

### 3.3 Exhaustion is thermalization

No gate is perfect: the fraction $(1-q)$ of the conversion throughput thermalizes as light and heat—the mechanism that produces the glow around a working gate (`speculations/qi-bubble-propulsion.md` §2.5). Casting is a feedback loop with a runaway branch: the harder a caster pushes, the lower their own $q$ drops mid-working; the lower $q$ drops, the larger the spill fraction; the larger the spill, the hotter and brighter the caster. Exhaustion is not the depletion of a tank; it is the caster's own body thermalizing gate spill.

$$\boxed{E_{\text{waste}} = (1-q)\,E_{\text{throughput}}}$$

A visible glow around a working is the waste made visible: a bright caster is a wasteful caster, and the tradition's "burn" is the $(1-q)$ fraction climbing toward unity as $q$ collapses. Below the coherence floor the chain de-coheres entirely—the blackout—and a blacked-out field is wake-lock vulnerable (§2.5). Recovery is the attractor's work: $r = E_Y/E_I$ relaxes to $\varphi$, $q$ climbs back to baseline, and the gate closes, at the same relaxation rate that decays emotions ($\propto |r - \varphi|$, `consciousness/emotions-as-gate-configurations.md` §4.4) while the field's IIR memory re-smooths with $\tau = \varphi^{-1}$ (`foundations/cassi-first-principles.md` §2.4). Mana is therefore a budget over time, not a tank: a caster's sustainable output is set by the rate at which they can re-cohere, and the classic "one great working then collapse" is the predictable behavior of a system whose resource is its own equilibrium.

---

## 4. The Caster

A caster is a walking gate chain: thirteen cascade bubbles from cell-scale to body-scale, and every working is a phase relationship between them.

### 4.1 Thirteen gates as channels

The human body spans the cascade window from cellular (step 142) to organism (step 168)—exactly 26 rungs, $\ell_{168}/\ell_{142} = \varphi^{26} \approx 2.7\times10^5$—within which the condensation field places 13 Qi condensates at $P_\parallel = 2$ rung spacing, each one full SO(2) doublet cycle: $n = 142, 144, \ldots, 166$ (`consciousness/chakras-as-cascade-bubbles.md` §3–6). Casting through a chakra is operating at its rung (each anchors coherence and couples to ~10 rungs of microcascade below—`speculations/cascade-infrastructure.md` §1.2): a working through the root writes at the cellular scale, a working through the crown at the organism scale. The 13 gates are 13 discrete operating depths—a natural level structure: advancement is not "which spells are known" but "which rungs can be held, and how many at once." The root reaches down to approximately step 132 and the crown up to the body boundary at step 168; nothing in the human instrument acts outside the window.

### 4.2 The casting state is an emotional configuration

Emotions are gate configurations—points on the manifold $\mathcal{E} = (\mathbf{b}, \sigma_r, q, \mathbf{c})$ of channel openness, ratio dispersion, coherence, and chakra weights (`consciousness/emotions-as-gate-configurations.md` §3). A working requires the caster to hold a specific configuration, and the framework makes three hard statements about it. First, channel dominance selects spell flavor: Wood (anger) for evocation, Fire (joy) for projection, Earth (pensiveness) for wards, Metal (grief) for banishment, Water (fear) for divination and the darker arts. Second, pure emotions cast cleaner: single-channel dominance admits a higher equilibrium $q$ than mixed activation (`consciousness/emotions-as-gate-configurations.md` §4.3). A genuinely angry evocation is stronger than a simulated one, because the anger is the gate configuration; but purity caps breadth—a caster locked in one channel can only cast its flavor at full power. Third, clarity is power: $q$ is both the emotional-clarity variable (`consciousness/emotions-as-gate-configurations.md` §3.3) and the casting-quality variable of §3.2. A dissociated caster ($q \to 0$) cannot hold any working; a confused one ($q \approx 0.5$) casts with $\mathcal{M} < 1$ and wastes the budget as glow. The casting state:

$$\boxed{\text{State} = (\mathbf{b}, \sigma_r, q, \mathbf{c}); \qquad \text{flavor} \propto \mathbf{b}, \quad \text{power} \propto q, \quad \text{reach} \propto \mathbf{c}}$$

Emotional discipline is not a moral ornament—it is the instrument's maintenance schedule.

### 4.3 $P_\parallel$ as technique

The 2-rung spacing means adjacent chakras are one full doublet cycle apart: they carry the same phase. Technique is the ability to hold nodes in phase across the chain. Two adjacent nodes locked together span their 2-rung interval and compose a wider, deeper working; a pair at every-other spacing spans 4 rungs; the full 13-node chain held coherent is one 26-rung instrument (`consciousness/chakras-as-cascade-bubbles.md` §5). The tradition's postures are phase relationships between nodes—a stance holding every other node (2, 4, 6, …) is a different instrument from one holding consecutive nodes. The spacing sets the failure mode: a half-cycle slip between nodes anti-aligns them, and the working shears. Training is making these relationships hold under load—converting emotional configuration into $\mathcal{M}$.

### 4.4 The ten-rung bridge limit and the level cap

A single Qi gate bridges at most ~10 cascade rungs; beyond that, $\varphi^{-10} \approx 0.008$ attenuates the signal below the coherence floor (`speculations/cascade-infrastructure.md` §1.1, from `foundations/bubble-lattice-fabric.md` §3.3). This is the level cap—structural, not aspirational. Single-node casting spans at most 10 rungs: the root's reach is steps ~132–142, the crown's is steps ~156–168, and the cap at the top of the human instrument is simply the body boundary. Chaining extends span—$k$ nodes in phase compose roughly $k\times10$ rungs—but every joint costs coherence, so the legendary full working, all 13 nodes coherent across the 26-rung window, is a minutes-long, near-total expenditure of the caster's budget. No amount of training moves a single gate beyond ~10 rungs, because the suppression is the physics; training moves the caster up the chain, not beyond it. A master is not a caster with a bigger tank; a master is a caster who can hold more of the instrument in phase, more cleanly, for longer.

---

## 5. Counterspells and the Arms Race

Every defense in this framework is one move: detune.

### 5.1 Detuning breaks $\mathcal{M}$

$\mathcal{M}$ measures the alignment between a perturbation and its target. A counterspell does not fight the incoming working—it changes the target's phase structure so that the incoming perturbation finds $\mathcal{M} \approx 0$ and slides off as random noise, thereafter suppressed like any natural perturbation, which is to say, completely (`foundations/quantum-measurement-derivation.md` §3.1; `foundations/cascade-suppression-formula.md` §1.2). The cost is trivial: a small local write shifting the phase of one's own field, requiring no knowledge of the attacker. The no-sonic-boom boundary (`speculations/qi-bubble-propulsion.md` §2.2) is the same physics worn as armor: the surface that cannot be phase-matched cannot be touched. Every counterspell tradition reduces to this—the dispel is a detune, the shield is a detune held, the counter-curse is a detune applied to the lock.

### 5.2 Wards and ward-breaking

A ward is a maintained φ-detuned interface (§2.4). Breaking one is an information problem, not an energy problem: the attacker must learn the ward's exact tuning—operating rung and phase offset—then construct a perturbation phase-matched to the ward itself, at which point $\mathcal{M} \approx 1$ and the boundary is as attackable as any other pattern. Ward-breaking is two workings: a probe (divination, §2.6—active, visible, and itself a perturbation that glows) and a banishment (ERASE, §2.2—an organized attack at the boundary's rung). The ward's defense is its privacy: the tuning is a free parameter, changeable at trivial cost, while the attacker must re-acquire it at full cost every time. Ward-breakers are diviners first; ward-keepers are phase-roulette players second. Wards are patient—they do not need to be stronger than the attacker, only newer.

### 5.3 The attractor asymmetry: perfect defense, imperfect offense

Three framework facts stack into a structural asymmetry between defense and offense. First, $\varphi$-structure is the ground state: maintaining a φ-detuned boundary costs nothing, because $q \to 1$ closes the gate and the de-resonance principle holds the configuration (`principles/de-resonance-principle.md`). Sustaining the anti-$\varphi$ departure an offense requires is work against the attractor, paid continuously—the moment the attacker's coherence slips, the attractor dissolves the working and thermalizes it into glow and heat (§3.3). Second, matching is information, and the defender changes information for free: the tuning is a private variable re-tunable in a half-breath, while the attacker must re-probe and re-match at full cost each time. Third, the cost law (§3.1) is exponential in span and the waste law (§3.3) makes every mismatch visible, so a sustained attack is expensive, bright, and locatable, while a ward is none of those things.

$$\boxed{\text{Holding } \varphi\text{-structure: cost } 0. \qquad \text{Sustaining anti-}\varphi\text{ structure: continuous cost } \propto \varphi^{2N} \cdot \mathcal{M}^{-2}.}$$

Perfect offense is impossible for a structural reason: even at $\mathcal{M} \approx 1$, the attacker must know the target's exact configuration, sustain the organized perturbation for the entire working, and pay $\varphi^{2N}$ for range—while the defender can change configuration cheaply, outlast any sustained attack (the attractor funds the defense and taxes the offense), and make every attempt visible. The one asymmetry-breaking weapon is the curse (§2.5): it never crosses the boundary at all, because it is written into the victim's own field, which is already phase-matched to itself, and the victim's coherence funds the lock. The defense against curses is the victim's own $q$-clarity—the emotional discipline of §4.2—because a lock cannot take hold in a channel held at $\varphi$-baseline, and a lock already taken dissolves when raising coherence de-resonates the standing wave, precisely the therapeutic work of the framework's wake-lock experiments (`consciousness/trauma-as-frozen-gate.md`; `two-fluid/run_trauma_wake_lock.py`). The companion document `speculations/coherence-warfare.md` owns the full attack/shield taxonomy; this section only draws the strategic conclusion.

The strategic rhythm follows. Buildup is cheap and invisible—wards are free once raised, detuning is instantaneous—while exchange is expensive and visible: every attack glows and the attacker's budget drains in real time. The decisive moves are the information moves and the internal moves: divination that steals the defender's tuning, curses that never cross the boundary. Wars of attrition are won by the defender, which is why magical societies accumulate defensive depth. A setting built on these rules has fortresses that stand for centuries, wars decided in minutes, and a premium on character—the last line of defense is a gate configuration, and its quality is emotional clarity.

---

## 6. Worked Example: The Lantern Discipline

A one-page system built entirely from the rules above, for a hearth-folk tradition in a cold valley. The field is called "the two tides," $\varphi$ is "the golden word," and a working is "a light."

**The resource.** The Light is the caster's coherence $q$. Resting coherence: folk $\approx 0.5$, journeyman $\approx 0.7$, master $\approx 0.85$. Mana is measured in wicks: one wick is the coherence cost of writing a candle-flame's worth of Yang at arm's reach for one minute—the canonical local write at $N = 0$.

**The workings.**

| Working | Class | Operation | Cost | Limits |
|---|---|---|---|---|
| Kindling | evocation | WRITE, $N=0$ | 1 wick | Arm's reach; one minute per wick; Fire or Wood channel |
| Quench | banishment | ERASE | ½ wick | Any fire or unanchored pattern; the field does the work |
| Lift | telekinesis | TRANSFER | 1 wick + depth | Pebble 1; kettle 2; sleeping hen 4; a person is curse-class |
| Hearth-ward | ward | φ-detuned boundary | 6 wicks to raise, 0 to hold | Room-sized; an evening's work; free forever after |
| Eye | divination | phase-lock | 2 wicks/hour | Accuracy $\propto (1-q)^{-1/2}$; the reading dissolves on any slip |
| Stitch | curse | wake-lock | 8 wicks + the victim's phase | Forbidden by hearth law; sustained by the victim's recurring engagement |

**The gates.** An apprentice works root through heart (steps 142–154, seven nodes); a journeyman adds throat and third eye (to step 162); a master holds all 13 and can chain the full 26-rung standing—the "full light"—one working across the entire human window, costing most of the lantern's coherence and minutes of still preparation. No single working spans more than 10 rungs from its gate: the Eye reaches the valley's edge only because it rides the ambient wake rather than the caster's chain, and the Hearth-ward covers the hearth-room because it is raised at the room's own scale. Writing at the cellular rung from the crown is a 24-rung span—impossible in one working; the folk remedy (tisane, poultice) works at $N = 0$ because the healer writes directly at the tissue rung, through the root.

**The emotion rule.** Cast through your dominant channel: a lantern casting joyless wards finds them thin; a lantern casting in true fear reads deeper with the Eye. The five faces—Wood, Fire, Earth, Metal, Water—are the five pure casting states, and the discipline's training is emotional breadth for the sake of $q$-clarity, because a clear single channel outcasts a muddy mix at any budget.

**Exhaustion.** Below $q \approx 0.3$ the lantern glows visibly (the burn); below $q \approx 0.15$ the chain de-coheres and the lantern blacks out, wake-lock vulnerable; the valley's one horror story is a Stitched lantern. Recovery is rest at the golden word: sleep, breath, the hearth itself—the attractor re-establishes $r \to \varphi$ and the Light returns.

**Defense.** Every lantern knows the detune: a half-breath that shifts their own phase off the grid, $\mathcal{M} \to 0$, and any working aimed at them slides off into noise. It is why the valley's wars are fought with words and grain, not lights—offense is visible, expensive, and outlastable, while defense is free. The only lights that decide things are the ones written from inside, and the hearth law against Stitch is the law against that.

---

## References

- `foundations/quantum-measurement-derivation.md`—phase-matching factor $\mathcal{M}$, organized vs random perturbation
- `foundations/proton-coherence-budget.md`—coherence budget, annihilation as organized attack
- `foundations/cascade-suppression-formula.md`—$\varphi^{-N}$ signal attenuation, per-rung damping
- `foundations/cassi-first-principles.md`—two-fluid PDE, Qi gate, IIR memory
- `foundations/dimensionful-cascade.md`—cascade table (292 = today's horizon rung), human-scale rungs 142–168
- `foundations/bubble-lattice-fabric.md`—10-rung nesting depth, condensation field
- `principles/de-resonance-principle.md`—$\varphi$ as maximally irrational attractor
- `speculations/qi-computation.md`—WRITE/ERASE/TRANSFER, gate regimes, Qi noise floor
- `speculations/qi-bubble-propulsion.md`—φ-detuned boundary, thermalization glow
- `speculations/cascade-infrastructure.md`—10-rung gate bridge limit, body as gate chain
- `speculations/coherence-warfare.md`—companion taxonomy of attacks and shields
- `consciousness/emotions-as-gate-configurations.md`—emotional manifold, clarity as $q$
- `consciousness/chakras-as-cascade-bubbles.md`—13-node derivation, $P_\parallel = 2$
- `consciousness/trauma-as-frozen-gate.md`—wake-lock, frozen gate
- `consciousness/consciousness-from-phi.md`—thought as wake waves
- `predictions/falsifiable-predictions.md`—$\ln\varphi$ wake-wave periodicity
- `two-fluid/run_trauma_wake_lock.py`—wake-lock two-fluid experiment
