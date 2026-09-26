package dev.cassicraft.game.practice;

import dev.cassicraft.game.sampler.Quantizer;

/**
 * MODULE 2/3 — the stilling/shout practice's read (the-stilling.md §2.1 the
 * maintenance-axis hold; the-shout.md §2.1 the loud register; async-field-domain.md
 * §7 Q4 the player-return channel the practice's write rides). A <b>pure,
 * Minecraft-free</b> consumer: given one {@link Quantizer.FieldReading} at a
 * position — the corpus's "one extra sample at the player's position"
 * (field-instruments §1.4) — it classifies the field at the practice point into
 * the practice's states:
 *
 * <ul>
 *   <li><b>{@link State#STILL}</b> — the body's rest state (q high, ε² low): the
 *       low-ε² coherent bulk, and the after-state of a stilling's matched-φ write
 *       (a still raises q while the overdraw component {@code dEY−φ·dEI=0} leaves
 *       the local lock untouched, so the point stays at the maintenance-axis
 *       hold, life-signal §1/§3).</li>
 *   <li><b>{@link State#WAKE}</b> — post-write: ε² in the drain band with coherent
 *       q still present — delivered/vented coherence the medium has not yet
 *       re-locked, the shout's wake (the-shout.md §2.3 a directed source the
 *       medium carries; atmosphere-orbits-auroras.md §3.1 the drain band).</li>
 *   <li><b>{@link State#CHURNED}</b> — perturbation present: ε² at/above the
 *       destroying decoherence floor — a write that broke the lock, the storm's
 *       darkening the sky slice owns (weather-not-storm §2, SkyRead
 *       {@code STORM_EDGE_EPS2}). A stilling or shout that ever reads churned has
 *       crossed its own bound — a design bug, never a silenced counter.</li>
 *   <li><b>{@link State#RETURNING}</b> — coherent but between the still and the
 *       wake: ε² mid-band while q holds — the field on its way back toward rest
 *       after a disturbance (the maintenance axis re-locking, life-signal §3).</li>
 *   <li><b>{@link State#VOID}</b> — no field: ρ below the vacuum floor (the empty
 *       air / space outside the condensed body, atmosphere-orbits-auroras.md
 *       §1.4 / material-regimes §2 the void floor).</li>
 * </ul>
 *
 * <p><b>The {@code [design]} thresholds are probe-calibrated / cited to the
 * measured settled body</b> (the {@code Quantizer} census of the settled box, seed
 * 42 @ 12 generations, and the sky/atmo reads' own settled-box census at the
 * current settle): the coherent bulk runs q p50 ≈ 0.64, ρ p50 ≈ 1.0 and a low
 * bulk ε² mean ≈ 0.10; the drain band's floor is the aurora's
 * {@code AURORA_EPS2_FLOOR = 0.20}, and the destroying decoherence is
 * {@code SkyRead.STORM_EDGE_EPS2 = 0.45}. Never hardcode a threshold you did not
 * measure — re-read {@link #STILL_Q_FLOOR}, {@link #STILL_EPS2_CEIL},
 * {@link #WAKE_EPS2_FLOOR} and {@link #CHURNED_EPS2_FLOOR} from
 * {@link StillingShoutDeterminismMain}'s printed settled-body census if the
 * field's distribution changes.
 *
 * <p><b>Priority</b> is {@code VOID > CHURNED > WAKE > STILL > RETURNING}: the
 * empty space first (nothing to practice on), then the broken lock (the loud
 * danger), then the vented wake, then the coherent still, then the mid-return.
 * Same channels every time; deterministic (never a seeded practice roll — the
 * stilling/shout gates' determinism, the-stilling §5c, the-shout §5c).
 */
public final class StillingShoutRead {

	/**
	 * The still's coherent {@code q} floor — at/above this {@code q} a position
	 * carries a real coherence body. [design] probe-calibrated to the measured
	 * settled body (Quantizer census, seed 42 @ 12 generations): the dense body
	 * (ρ ≥ τ_c = 0.90, the φ-locked branch {@code EY=φ·EI}) carries q ≥ 0.43 for
	 * ρ ≥ 0.90 and the whole-box q mean is ≈ 0.64; a position at q ≥ 0.45 is
	 * solidly inside the coherent body, not the thin field or the void.
	 */
	public static final float STILL_Q_FLOOR = 0.45f;

	/**
	 * The still's {@code ε²} ceiling — below this the local field holds the
	 * body's rest lock. [design] probe-calibrated to the measured settled-box ε²
	 * distribution (Quantizer census: coherent bulk mean ≈ 0.109; SkyDeterminism
	 * / AtmosphereDeterminism: mean ≈ 0.102): the ceiling sits above the low bulk
	 * mean and below the drain-band floor {@link #WAKE_EPS2_FLOOR}, so the
	 * ordinary coherent bulk reads still while a drain (ε² ≥ 0.20) reads as a
	 * wake/discharge.
	 */
	public static final float STILL_EPS2_CEIL = 0.15f;

	/**
	 * The wake's {@code ε²} floor — at/above this (and below the destroyed lock
	 * {@link #CHURNED_EPS2_FLOOR}) a position with coherent q is a wake: the
	 * delivered/vented coherence the medium has not yet re-locked. Cites the
	 * aurora's drain-band floor (AtmoRead {@code AURORA_EPS2_FLOOR = 0.20},
	 * atmosphere-orbits-auroras.md §3.1 — the drain where ε² rises): a shout's
	 * wake sits here, above the bulk's still and below the destroyed front.
	 */
	public static final float WAKE_EPS2_FLOOR =
			dev.cassicraft.game.atmo.AtmoRead.AURORA_EPS2_FLOOR;

	/**
	 * The wake's coherent {@code q} floor — a wake needs delivered coherence
	 * still present (the shout projects the body's own signature; the-shout.md
	 * §2.1). Same floor as the still's {@link #STILL_Q_FLOOR}, citing the same
	 * measured body.
	 */
	public static final float WAKE_Q_FLOOR = STILL_Q_FLOOR;

	/**
	 * The churned {@code ε²} floor — at/above this the local lock is broken:
	 * perturbation present, the destroying decoherence the sky slice owns as the
	 * storm's darkening (weather-not-storm §2, SkyRead {@code STORM_EDGE_EPS2 =
	 * 0.45}, ε² p99 ≈ 0.39–0.52, max ≈ 0.57 — the top ~1% of the lattice). A
	 * practiced write that reads churned has crossed into the discharge; the
	 * matched-φ still/shout never should.
	 */
	public static final float CHURNED_EPS2_FLOOR =
			dev.cassicraft.game.sky.SkyRead.STORM_EDGE_EPS2;

	/**
	 * The void's {@code ρ} ceiling — below this the field is the vacuum (no
	 * condensed body to practice against, atmosphere-orbits-auroras.md §1.4 the
	 * KSP vacuum floor). Cites the material registry's void threshold
	 * ({@code MaterialRegistry.AIR_THETA_C}, material-regimes §2 "Gas").
	 */
	public static final float VOID_RHO_CEIL =
			(float) dev.cassicraft.game.material.MaterialRegistry.AIR_THETA_C;

	private StillingShoutRead() {
	}

	/** The practice state at one field position. */
	public enum State {
		/** The body's rest — q high, ε² low (and the stilling's after-state). */
		STILL("STILL — the body's rest (q high, ε² low)"),
		/** Post-write — vented coherence the medium has not yet re-locked. */
		WAKE("WAKE — delivered coherence, not yet re-locked"),
		/** Perturbation present — the lock has broken (ε² in the destroying tail). */
		CHURNED("CHURNED — perturbation present (ε² high)"),
		/** Coherent but mid-band — the field returning toward the still. */
		RETURNING("RETURNING — coherent, returning toward the still"),
		/** No field — the vacuum / empty air outside the body. */
		VOID("VOID — no field to practice against");

		private final String label;

		State(String label) {
			this.label = label;
		}

		/** The human-readable verdict label (also the command's printed form). */
		public String label() {
			return label;
		}
	}

	/** The classifier's full read at one position. */
	public record Read(State state, float q, float eps2, float rho) {

		/** Whether the point reads the body's rest (still or a stilling's after-state). */
		public boolean isStill() {
			return state == State.STILL;
		}

		/** Whether the point reads a wake (post-write, vented coherence). */
		public boolean isWake() {
			return state == State.WAKE;
		}

		/** Whether the point reads perturbation present (churned). */
		public boolean isChurned() {
			return state == State.CHURNED;
		}
	}

	/**
	 * Classify the field at a practice point from one {@link FieldReading}.
	 *
	 * @param r the published-channel reading at the block position
	 * @return the practice state + the measured channels; a pure function of the
	 *         reading (same reading → same state, the-stilling §5c / the-shout
	 *         §5c — deterministic, never a seeded practice roll).
	 */
	public static Read classify(Quantizer.FieldReading r) {
		float q = r.q();
		float eps2 = r.eps2();
		float rho = r.rho();

		// The vacuum first — nothing to practice against.
		if (rho < VOID_RHO_CEIL) {
			return new Read(State.VOID, q, eps2, rho);
		}
		// Perturbation present — the lock has broken (the destroying decoherence).
		if (eps2 >= CHURNED_EPS2_FLOOR) {
			return new Read(State.CHURNED, q, eps2, rho);
		}
		// The wake — delivered/vented coherence the medium has not yet re-locked.
		if (eps2 >= WAKE_EPS2_FLOOR && q >= WAKE_Q_FLOOR) {
			return new Read(State.WAKE, q, eps2, rho);
		}
		// The body's rest — q high, ε² low.
		if (q >= STILL_Q_FLOOR && eps2 < STILL_EPS2_CEIL) {
			return new Read(State.STILL, q, eps2, rho);
		}
		// Coherent but mid-band — the field on its way back toward the still.
		return new Read(State.RETURNING, q, eps2, rho);
	}
}
