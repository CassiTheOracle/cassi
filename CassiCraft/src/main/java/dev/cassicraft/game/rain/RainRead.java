package dev.cassicraft.game.rain;

import dev.cassicraft.game.sampler.Quantizer;

/**
 * MODULE 2/3 — the Rain classification (the-rain.md §2, §4 — the nourishing
 * weather, the flood's gentle twin). A <b>pure, Minecraft-free</b> consumer:
 * given one {@link Quantizer.FieldReading} at a position — the corpus's "one
 * extra sample at the player's position" (field-instruments §1.4, the same
 * sample the Weatherglass takes) — it classifies the local weather and reports
 * the wet cost and the flood-beginning margin.
 *
 * <p><b>The provenance inherited</b> (the-rain §2.3, weather-not-storm §2):
 * the Rain is the <em>same q-surfeit source as the flood</em>
 * (the-flood §2), read at a yield the field can take — a soft high-`q` fall
 * where regional `q` rises <em>within</em> the enriching band, feeds, and
 * recedes, never crossing the flood's overshoot. The distinguishing quantity is
 * <b>yield-rate, not source</b>: the flood and the rain are the same channels
 * read at a rate. This classifier reads one point of that rate — how high the
 * local `q` sits relative to the enriching band and the surfeit threshold.
 *
 * <p><b>The four classes</b>, a deterministic pure function of the published
 * channels (no RNG — the hard gate, the-rain §7c):
 * <ul>
 *   <li><b>{@link Weather#NO_RAIN}</b> — `q` below the enriching band's floor
 *       (the thin/dry state; the cold's floor, the-rain §1).</li>
 *   <li><b>{@link Weather#RAIN}</b> — `q` in the enriching band: the gentle
 *       fall, feeding within the band, receding, wet.</li>
 *   <li><b>{@link Weather#FLOODS_BEGINNING}</b> — `q` at/past the surfeit
 *       threshold: the rain has become the flood's beginning. The read is the
 *       SAME channels, never hidden — the rate read is the Rain's honest edge
 *       (field-hazards §5.1's readable-before-it-arrives discipline).</li>
 *   <li><b>{@link Weather#STORM_FRONT}</b> — `ε²` above its measured high
 *       tail: a `c_s`-traveling `ε²` front (field-hazards §2), the storm's
 *       wound — excluded from "weather we water under" (the-rain §2.3).</li>
 * </ul>
 *
 * <p><b>The wet cost</b> (the-rain §3.1): rain is nourishing but wet — it feeds
 * a plot but muddies a signature, the marsh's blur on a smaller scale. During a
 * fall the life-signal/readout legibility dims by {@link WeatherRead#wetness()},
 * a 0..1 factor deterministic from the same channels (the fall's intensity).
 * It is the same published `q`/`ε²` read wet, never a hidden debuff.
 *
 * <p><b>The band thresholds are [design], probe-calibrated</b> (the-rain §5a,
 * §7) from the measured q/ε² distribution at build time (RainDeterminismMain,
 * seed 42 @ the current settle): the floors/tails cite the measured percentiles
 * in their javadocs. Never hardcode a threshold you did not measure — re-read
 * {@link #ENRICHING_BAND_FLOOR}, {@link #SURFEIT_THRESHOLD} and
 * {@link #STORM_FRONT_EPS2} from RainDeterminismMain's printed census if the
 * field's distribution changes.
 */
public final class RainRead {

	/**
	 * The enriching band's floor — below this `q` the field reads thin/dry
	 * ({@link Weather#NO_RAIN}). [design] probe-calibrated from the measured
	 * settled-box q distribution (RainDeterminismMain, seed 42 @ the current
	 * settle, DT=0.001, 0.768 field-time units): q p10=0.387, p50=0.603,
	 * p90=0.899, mean=0.635. The floor sits just above p10, so the moderate
	 * coherence body (q ≈ 0.45..1.30 ≈ p11..p98+) reads as the crop-band the
	 * rain feeds (farm-that-feeds §2.1 "q mid"), while the thin q tail below
	 * p11 reads dry (NO_RAIN ≈ 19% of the lattice at the measured distribution).
	 */
	public static final float ENRICHING_BAND_FLOOR = 0.45f;

	/**
	 * The surfeit threshold — at/above this `q` a rain reads as
	 * {@link Weather#FLOODS_BEGINNING} (the enriching band's overshoot, the
	 * flood doc's band top, the-rain §4). [design] probe-calibrated from the
	 * measured settled-box q distribution (RainDeterminismMain, seed 42 @ the
	 * current settle): q p99=1.165, max=1.427. The threshold sits in the deep
	 * coherent tail (≈ p99+), so a genuinely over-organized locality reads as
	 * the rising water (FLOODS_BEGINNING ≈ 0.5% of the lattice), while the
	 * ordinary field-structure reads as rain.
	 */
	public static final float SURFEIT_THRESHOLD = 1.30f;

	/**
	 * The storm-front `ε²` tail — at/above this `ε²` a position reads
	 * {@link Weather#STORM_FRONT} (the `c_s`-traveling `ε²` front,
	 * field-hazards §2). [design] probe-calibrated from the measured settled-box
	 * ε² distribution (RainDeterminismMain, seed 42 @ the current settle): ε²
	 * p90=0.202, p99=0.385, max=0.573. The threshold sits in the high ε² tail
	 * (≈ p99.5+), so the genuinely decohered front/desert reads as the storm
	 * (excluded from the gentle fall — STORM_FRONT ≈ 0.2% of the lattice), while
	 * the ordinary low-ε² field does not.
	 */
	public static final float STORM_FRONT_EPS2 = 0.50f;

	private RainRead() {
	}

	/** The weather at one position. */
	public enum Weather {
		/** q below the enriching band's floor — the thin/dry state. */
		NO_RAIN("NO RAIN"),
		/** q in the enriching band — the gentle fall, feeding within the band. */
		RAIN("RAIN — gentle fall"),
		/** q at/past the surfeit threshold — the rain has become the flood's beginning. */
		FLOODS_BEGINNING("FLOOD'S BEGINNING"),
		/** ε² above its high tail — a storm's `c_s`-traveling front, not the nourishing fall. */
		STORM_FRONT("STORM FRONT");

		private final String label;

		Weather(String label) {
			this.label = label;
		}

		/** The human-readable verdict label (also the command's printed form). */
		public String label() {
			return label;
		}
	}

	/** The classifier's full read at one position. */
	public record WeatherRead(Weather kind, float q, float eps2,
			float wetness, float floodDistance) {

		/** Whether this position is within the nourishing fall (rain or its flood-beginning). */
		public boolean isFalling() {
			return kind == Weather.RAIN || kind == Weather.FLOODS_BEGINNING;
		}

		/** The flood-beginning margin — `surfeit − q`, the q-units the corpus
		 * reads (the-rain §4): how far below the surfeit the local q sits.
		 * Positive during a feeding rain (the honest readable-before-it-arrives
		 * margin); ≤ 0 once the rain becomes the flood's beginning. */
		public float floodDistance() {
			return floodDistance;
		}
	}

	/**
	 * Classify the local weather at a position from one {@link FieldReading}.
	 *
	 * @param r the published-channel reading at the block position
	 * @return the weather verdict + wet cost + flood-beginning margin; a pure
	 *         function of the reading (same reading → same verdict, the-rain §7c).
	 */
	public static WeatherRead classify(Quantizer.FieldReading r) {
		float q = r.q();
		float eps2 = r.eps2();

		// The storm's ε² front overrides the q read — the front is the storm's
		// wound, not the nourishing fall (the-rain §2.3, field-hazards §2).
		if (eps2 >= STORM_FRONT_EPS2) {
			return new WeatherRead(Weather.STORM_FRONT, q, eps2, 0f,
					SURFEIT_THRESHOLD - q);
		}

		// The q-driven fall: below the band floor = dry; in the band = the gentle
		// fall; at/past the surfeit = the flood's beginning.
		if (q >= SURFEIT_THRESHOLD) {
			return new WeatherRead(Weather.FLOODS_BEGINNING, q, eps2, 1f,
					SURFEIT_THRESHOLD - q);
		}
		if (q >= ENRICHING_BAND_FLOOR) {
			// Wetness = the fall's intensity, normalized within the band (0 at
			// the floor, 1 at the surfeit) — the honest read of how wet it is.
			float span = SURFEIT_THRESHOLD - ENRICHING_BAND_FLOOR;
			float wetness = Math.max(0f, Math.min(1f, (q - ENRICHING_BAND_FLOOR) / span));
			return new WeatherRead(Weather.RAIN, q, eps2, wetness,
					SURFEIT_THRESHOLD - q);
		}
		// NO_RAIN — thin/dry; no fall, no wet, no flood approach.
		return new WeatherRead(Weather.NO_RAIN, q, eps2, 0f, SURFEIT_THRESHOLD - q);
	}
}
