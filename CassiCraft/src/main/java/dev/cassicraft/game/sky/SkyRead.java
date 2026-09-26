package dev.cassicraft.game.sky;

import dev.cassicraft.game.sampler.Quantizer;

/**
 * MODULE 2/3 — the Sky read (atmosphere-orbits-auroras.md §3.3: the aurora as
 * the reader's <em>atmospheric</em> form — the sky reads the same channels as
 * the Weatherglass, un-instrumented; §1.5 the sky is the field's shape made
 * visible; weather-not-storm §5.4 the sky's color/motion is the provenance
 * read's atmospheric channel). A <b>pure, Minecraft-free</b> consumer: given
 * one {@link Quantizer.FieldReading} at a position — the corpus's "one extra
 * sample at the player's position" (field-instruments §1.4) — it classifies
 * the local sky and reports the glow, the storm's leading-edge darkening, and
 * the density-fog thickness.
 *
 * <p><b>The sky is a read of the published channels ({@code ρ},{@code q},{@code ε²}),
 * never a new channel and never new physics</b> (atmosphere-orbits-auroras.md
 * §1.5, §4: "There is one sky because there is one field"). Each class is a
 * probe-calibrated tail read of one real channel:
 * <ul>
 *   <li><b>{@link Kind#GLOW}</b> — the local {@code q} sits in the coherent
 *       high tail: the sky's glow, the aurora's source (§3.3 the aurora's glow
 *       is where coherence concentrates). Intensity normalized within the glow
 *       band.</li>
 *   <li><b>{@link Kind#STORM_EDGE}</b> — the local {@code ε²} sits in its high
 *       tail: the storm's leading edge darkens (weather-not-storm §2, the
 *       {@code c_s}-traveling {@code ε²} front read ahead of the storm;
 *       field-hazards §5.1's readable-before-it-arrives). Readable from the
 *       instruments, never hidden (gate (e)).</li>
 *   <li><b>{@link Kind#FOG}</b> — the local {@code ρ} sits in its high tail:
 *       the density fog, the field's own upper density (atmosphere §1.5
 *       "fog-density ∝ ρ"). Thickness normalized within the dense band.</li>
 *   <li><b>{@link Kind#CLEAR}</b> — none of the above: the dry sky.</li>
 * </ul>
 *
 * <p><b>Priority</b> is {@code STORM_EDGE > GLOW > FOG > CLEAR}: a decohering
 * front's darkening reads ahead of any {@code q}-glow (the storm's edge is the
 * strongest, most urgent read — weather-not-storm §2.1 the storm happens where
 * the field is thin/decohering), then the luminous high-coherence glow, then
 * the mild density thickening. Same channels every time; deterministic
 * (never a seeded weather roll — gate (c), atmosphere §5c).
 *
 * <p><b>The {@code [design]} thresholds are probe-calibrated</b>
 * (weather-not-storm §4a) from the measured settled-box distribution at build
 * time (SkyDeterminismMain, seed 42 @ the current settle): the glow / storm /
 * fog tails cite the measured percentiles in their javadocs. Never hardcode a
 * threshold you did not measure — re-read {@link #GLOW_Q_TAIL},
 * {@link #STORM_EDGE_EPS2} and {@link #FOG_RHO_TAIL} from SkyDeterminismMain's
 * printed census if the field's distribution changes.
 */
public final class SkyRead {

	/**
	 * The glow's {@code q} tail — at/above this {@code q} a position reads
	 * {@link Kind#GLOW} (the coherent high tail where the aurora's glow
	 * concentrates, atmosphere §3.3). [design] probe-calibrated from the
	 * measured settled-box {@code q} distribution (SkyDeterminismMain, seed 42
	 * @ the current settle, DT=0.001, 0.768 field-time units): q p90=0.899,
	 * p99=1.165, max=1.427, mean=0.635. The threshold sits in the coherent
	 * high tail (≈ the top 5–10% of the lattice), so the genuinely best-locked
	 * field reads as the sky's glow while the ordinary coherence body does not.
	 */
	public static final float GLOW_Q_TAIL = 1.05f;

	/**
	 * The storm's-edge {@code ε²} tail — at/above this {@code ε²} a position
	 * reads {@link Kind#STORM_EDGE} (the {@code c_s}-traveling {@code ε²}
	 * front's leading edge, weather-not-storm §2.1). [design] probe-calibrated
	 * from the measured settled-box {@code ε²} distribution (SkyDeterminismMain,
	 * seed 42 @ the current settle): ε² p99=0.385, max=0.573, mean=0.102. The
	 * threshold sits above p99 (≈ the top 1% of the lattice), so only the
	 * genuinely decohered front/desert reads as the storm's darkening while the
	 * ordinary low-ε² field does not.
	 */
	public static final float STORM_EDGE_EPS2 = 0.45f;

	/**
	 * The density-fog {@code ρ} tail — at/above this {@code ρ} a position reads
	 * {@link Kind#FOG} (the sky's thickness, the field's own upper density,
	 * atmosphere §1.5). [design] probe-calibrated from the measured settled-box
	 * {@code ρ} distribution (SkyDeterminismMain, seed 42 @ the current settle):
	 * ρ p50=1.003, p90=1.242, p99=1.403, max=1.574. The threshold sits just
	 * above the dense tail's center (a bit under p90), so the deser half of the
	 * condensed field reads as the sky's thickness while the thinner diffuse
	 * field reads clear.
	 */
	public static final float FOG_RHO_TAIL = 1.20f;

	private SkyRead() {
	}

	/** The sky at one position. */
	public enum Kind {
		/** {@code q} in the coherent high tail — the glow, the aurora's source. */
		GLOW("GLOW — the sky's coherent light"),
		/** {@code ε²} in its high tail — the storm's leading edge darkens. */
		STORM_EDGE("STORM EDGE — the sky darkens ahead of the front"),
		/** {@code ρ} in its high tail — the density fog thickens. */
		FOG("FOG — the field's upper density"),
		/** none of the above — the dry sky. */
		CLEAR("CLEAR — the dry sky");

		private final String label;

		Kind(String label) {
			this.label = label;
		}

		/** The human-readable verdict label (also the command's printed form). */
		public String label() {
			return label;
		}
	}

	/** The classifier's full read at one position. */
	public record Read(Kind kind, float q, float eps2, float rho,
			float glow, float darkening, float fog) {

		/** Whether this position's sky has a coherent glow to render. */
		public boolean isGlow() {
			return kind == Kind.GLOW;
		}

		/** Whether this position's sky has a storm-edge darkening to render. */
		public boolean isStormEdge() {
			return kind == Kind.STORM_EDGE;
		}

		/** Whether this position's sky has a density-fog to render. */
		public boolean isFog() {
			return kind == Kind.FOG;
		}

		/** Whether this position reads the dry sky (none of the weather). */
		public boolean isClear() {
			return kind == Kind.CLEAR;
		}

		/**
		 * The storm front's approach — {@code ε² − STORM_EDGE_EPS2}, the same
		 * {@code ε²}-units the corpus reads (weather-not-storm §2.1): how far
		 * the leading edge's decoherence already sits above the darkening
		 * threshold. Positive at a storm edge (the front has arrived in the
		 * field the sky reads), ≤ 0 otherwise.
		 */
		public float frontApproach() {
			return eps2 - STORM_EDGE_EPS2;
		}
	}

	/**
	 * Classify the local sky from one {@link FieldReading}.
	 *
	 * @param r the published-channel reading at the block position
	 * @return the sky verdict + intensities; a pure function of the reading
	 *         (same reading → same sky, atmosphere §5c — deterministic).
	 */
	public static Read classify(Quantizer.FieldReading r) {
		float q = r.q();
		float eps2 = r.eps2();
		float rho = r.rho();

		// Intensities, each normalized within its own measured band (0 at the
		// tail threshold, 1 at the deep-tail saturation) — a 0..1 presentation.
		float glow = bandIntensity(q, GLOW_Q_TAIL, qDeepTail());
		float darkening = bandIntensity(eps2, STORM_EDGE_EPS2, eps2DeepTail());
		float fog = bandIntensity(rho, FOG_RHO_TAIL, rhoDeepTail());

		// Priority: the storm's edge (a decohering front darkens ahead of any
		// q-glow), then the luminous q-glow, then the density fog, then clear.
		if (eps2 >= STORM_EDGE_EPS2) {
			return new Read(Kind.STORM_EDGE, q, eps2, rho, glow, darkening, fog);
		}
		if (q >= GLOW_Q_TAIL) {
			return new Read(Kind.GLOW, q, eps2, rho, glow, darkening, fog);
		}
		if (rho >= FOG_RHO_TAIL) {
			return new Read(Kind.FOG, q, eps2, rho, glow, darkening, fog);
		}
		return new Read(Kind.CLEAR, q, eps2, rho, glow, darkening, fog);
	}

	/** Deep-tail saturation for the glow band (the measured {@code q} max). */
	private static float qDeepTail() {
		return 1.45f;
	}

	/** Deep-tail saturation for the storm-edge band (the measured {@code ε²} max). */
	private static float eps2DeepTail() {
		return 0.60f;
	}

	/** Deep-tail saturation for the fog band (the measured {@code ρ} max). */
	private static float rhoDeepTail() {
		return 1.60f;
	}

	/** Normalize a channel within its band: 0 at the tail threshold, 1 at the deep-tail saturation. */
	private static float bandIntensity(float value, float tail, float deepTail) {
		float span = deepTail - tail;
		if (span <= 0f) {
			return value >= tail ? 1f : 0f;
		}
		return Math.max(0f, Math.min(1f, (value - tail) / span));
	}
}
