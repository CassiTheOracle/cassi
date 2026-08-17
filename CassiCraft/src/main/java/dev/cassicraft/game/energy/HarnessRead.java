package dev.cassicraft.game.energy;

import dev.cassicraft.game.material.MaterialRegimeRead;
import dev.cassicraft.game.material.MaterialRegistry;
import dev.cassicraft.game.sampler.Quantizer;

/**
 * MODULE 2/3 — the energy-harnessing practice's read (energy-harnessing.md §0
 * the core stance — energy is a field withdrawal, never a substance; §2.5 the
 * deep-rung reaper: "removing deep rungs de-orders the local field (lowers q)";
 * §6 the no-free-energy cap {@code output ≤ φ⁻¹·input}). A <b>pure,
 * Minecraft-free</b> consumer: given one {@link Quantizer.FieldReading} at a
 * position — the corpus's "one extra sample at the player's position"
 * (field-instruments §1.4) — it reads the harness's four facts about the local
 * field:
 *
 * <ul>
 *   <li><b>{@code q}</b> — the local coherence (the reservoir the draw spends;
 *       the field's stored order at the point).</li>
 *   <li><b>{@code ε²}</b> — the local strain, {@code (EY−φ·EI)²} (the draw's
 *       cost surface — a matched-φ draw leaves it untouched, a strain-costed
 *       draw would raise it; the decoherence channel, chunk-field-quantization
 *       §2.2 / material-regimes §2).</li>
 *   <li><b>The local regime / rung</b> — reused verbatim from
 *       {@link MaterialRegimeRead} (a material is a point in the field regime;
 *       a material's rung {@code n = log_φ(M_Pl/m)} = its stored-coherence
 *       depth — the "fuel" the harness spends, energy-harnessing §1.5/§3).</li>
 *   <li><b>The harness state</b> — whether the point holds spendable coherence:
 *       <b>{@link State#READY}</b> when the local {@code q} is at/above the
 *       measured coherent-body floor (the field has a real coherence budget to
 *       draw from), <b>{@link State#SPENT}</b> when a draw has exhausted the
 *       budget at the point ({@code q} below the floor — the field has already
 *       paid its coherence and has nothing more to give until it recovers),
 *       and <b>{@link State#RESTING}</b> when the point is coherent but the
 *       practice's cadence window has not yet elapsed (one draw per cooldown —
 *       the practice cadence).</li>
 * </ul>
 *
 * <p><b>The {@code [design]} thresholds are probe-calibrated / cited to the
 * measured settled body</b> (the {@code Quantizer} census of the settled box,
 * seed 42 @ 12 generations, and the stilling/shout gate's own settled-body
 * read): the coherent body (ρ ≥ τ_c = 0.90, the φ-locked branch {@code EY=φ·EI})
 * carries q ≥ 0.43 for ρ ≥ 0.90 and the whole-box q mean is ≈ 0.64; a position
 * at q ≥ 0.45 is solidly inside the coherent body (the stilling/shout
 * {@link dev.cassicraft.game.practice.StillingShoutRead#STILL_Q_FLOOR}, cited
 * to that measured body). Never hardcode a threshold you did not measure —
 * re-read {@link #READY_Q_FLOOR} and {@link #SPENT_Q_FLOOR} from
 * {@link HarnessDeterminismMain}'s printed settled-body q distribution if the
 * field's distribution changes.
 *
 * <p><b>Priority</b> is {@code VOID > SPENT > RESTING > READY}: the empty
 * space first (nothing to draw from), then the exhausted point (the field has
 * already paid), then the coherent-but-waiting point (the cadence), then the
 * ready coherent body. The void floor cites the material registry's vacuum
 * {@code AIR_THETA_C} (material-regimes §2 "Gas") exactly as the stilling read
 * does. Same channels every time; deterministic (never a seeded draw roll — the
 * harness gate's determinism, energy-harnessing §6 as coded in the Q4 lane).
 */
public final class HarnessRead {

	/**
	 * The ready {@code q} floor — at/above this a position carries a real,
	 * spendable coherence body (the draw's reservoir exists here). [design]
	 * probe-calibrated to the measured settled body: the dense coherent body
	 * carries q ≥ 0.43 for ρ ≥ 0.90 and the whole-box q mean is ≈ 0.64; a
	 * position at q ≥ 0.45 is solidly inside the coherent body, not the thin
	 * field or the void (the stilling/shout practice's own
	 * {@link dev.cassicraft.game.practice.StillingShoutRead#STILL_Q_FLOOR}).
	 * A harness draws <b>only</b> where the local coherence is at/above this
	 * floor — the field must hold spendable coherence before it is asked to
	 * spend any.
	 */
	public static final float READY_Q_FLOOR = 0.45f;

	/**
	 * The spent {@code q} ceiling — a draw may not fire when the local {@code q}
	 * is at/below this (the budget at the point is exhausted by an earlier
	 * draw; the field has already paid). [design] This sits a named margin
	 * below the ready floor — a single harness draw lowers the local q by its
	 * (cap-honored, sub-threshold-of-the-floor) withdrawal, but the SPENT gate is
	 * what makes repeated same-spot over-drain impossible in play: once the
	 * field's local coherence is driven under this ceiling, the harness refuses
	 * until the field itself recovers (energy-harnessing §3, the charge/scar
	 * asymmetry — discharging is fast and scars; the maintainer must let the
	 * field re-organize).
	 */
	public static final float SPENT_Q_CEIL = 0.20f;

	/**
	 * The strain ceiling — below this the local {@code ε²} is the body's rest
	 * lock (a matched-φ draw leaves it so). [design] cited to the measured
	 * settled-box ε² (Quantizer census, seed 42: coherent bulk mean ≈ 0.109;
	 * SkyDeterminism / AtmosphereDeterminism mean ≈ 0.102) and the stilling
	 * read's still ceiling {@code STILL_EPS2_CEIL = 0.15} — the ordinary
	 * coherent bulk sits here, so a READY draw point reads clean strain (the
	 * cost surface the draw spends against).
	 */
	public static final float STRAIN_EPS2_CEIL = 0.15f;

	/**
	 * The void's {@code ρ} ceiling — below this the field is the vacuum (no
	 * condensed body to draw from, atmosphere-orbits-auroras.md §1.4 the KSP
	 * vacuum floor). Cites the material registry's void threshold
	 * ({@code MaterialRegistry.AIR_THETA_C}, material-regimes §2 "Gas") exactly
	 * as the stilling read's void floor does.
	 */
	public static final float VOID_RHO_CEIL =
			(float) MaterialRegistry.AIR_THETA_C;

	private HarnessRead() {
	}

	/** The harness state at one field position. */
	public enum State {
		/** The field holds spendable coherence (qlocal ≥ the measured body floor). */
		READY("READY — the field holds spendable coherence to draw from"),
		/** A draw has exhausted the budget at the point (qlocal ≤ the spent ceiling). */
		SPENT("SPENT — the local budget is exhausted; let the field recover"),
		/** Coherent but the cadence window has not yet elapsed. */
		RESTING("RESTING — coherent, but the harness needs a moment to still"),
		/** No field — the vacuum / empty air outside the body. */
		VOID("VOID — no field to draw from");

		private final String label;

		State(String label) {
			this.label = label;
		}

		/** The human-readable verdict label (also the command's printed form). */
		public String label() {
			return label;
		}
	}

	/**
	 * The full harness read at one position — {@code q} (the reservoir), the
	 * derived {@code ε²} (the strain / cost surface), the local regime + rung
	 * (via {@link MaterialRegimeRead}, the stored-coherence-depth vocabulary),
	 * and the harness {@link State}. A pure function of the reading.
	 */
	public record Read(
			State state,
			float q,
			float eps2,
			float rho,
			MaterialRegimeRead.RegimeRead regime
	) {

		/** Whether the point holds spendable coherence (ready, not void/spent). */
		public boolean isReady() {
			return state == State.READY;
		}

		/** Whether the local coherence body is a deep-rung ordered regime (the copper metal tail). */
		public boolean isDeepRung() {
			return regime != null && regime.isCondensed()
					&& regime.material() == MaterialRegistry.COPPER;
		}
	}

	/**
	 * Classify the harness state at a position from one {@link FieldReading}
	 * (plus its material-regime read — the rung vocabulary, computed once and
	 * reused).
	 *
	 * @param r the published-channel reading at the block position
	 * @return the harness state + the measured channels + the regime/rung; a
	 *         pure function of the reading (same reading → same state — the
	 *         harness gate's determinism, never a seeded draw roll).
	 */
	public static Read classify(Quantizer.FieldReading r) {
		float q = r.q();
		float eps2 = r.eps2();
		float rho = r.rho();
		MaterialRegimeRead.RegimeRead regime = MaterialRegimeRead.classify(r);

		// The vacuum first — nothing to draw from.
		if (rho < VOID_RHO_CEIL) {
			return new Read(State.VOID, q, eps2, rho, regime);
		}
		// Exhausted — a prior draw drove the local coherence under the spent ceiling.
		if (q <= SPENT_Q_CEIL) {
			return new Read(State.SPENT, q, eps2, rho, regime);
		}
		// The ready coherent body — the field holds spendable coherence at/above
		// the measured body floor (and clean strain — the matched-φ draw's cost
		// surface sits at the rest lock).
		if (q >= READY_Q_FLOOR && eps2 < STRAIN_EPS2_CEIL) {
			return new Read(State.READY, q, eps2, rho, regime);
		}
		// Coherent but between — a cadence-gated point (or a strain band the
		// matched-φ draw does not want to enter): the harness needs a moment.
		return new Read(State.RESTING, q, eps2, rho, regime);
	}
}
