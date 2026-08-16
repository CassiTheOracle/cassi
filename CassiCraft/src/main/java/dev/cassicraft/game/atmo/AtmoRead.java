package dev.cassicraft.game.atmo;

import dev.cassicraft.game.material.MaterialRegistry;
import dev.cassicraft.game.sampler.Quantizer;

/**
 * The atmosphere's field phenomenology read (atmosphere-orbits-auroras.md —
 * the sky's field-driven phenomena read honestly off the published channels).
 * A <b>pure, Minecraft-free</b> consumer: given one {@link Quantizer.FieldReading}
 * at a position it classifies the three phenomena the committed sky slice
 * (SkyRead) does <b>not</b> name — the <b>aurora</b> (the coherence discharge
 * into a drain, the (1−q) waste glow), the <b>envelope</b> (the sub-condensation
 * gas band vs the vacuum ceiling), and the <b>orbit well</b> (the body-seed
 * condensation candidate, the honest Phase-1 precursor read for orbits).
 *
 * <p><b>No free energy — every phenomenon is a read, never a write</b>
 * (atmosphere §5c the only-mutator rule; the doc's §3.1 steady honesty flag:
 * the (1−q) glow is engine-real; "a discharge along field lines into a drain"
 * is a [design] mapping over it). This class reads only the published channels
 * ({@code ρ},{@code q},{@code ε²},{@code ∇(g·Φ)}) and registry constants; it
 * never writes a block, perturbs the field, or changes the sky dimension.
 *
 * <p><b>The three phenomena, each a tail/co-location read of a real channel:</b>
 * <ul>
 *   <li><b>{@link Kind#AURORA}</b> — the coherence discharge into a drain.
 *       The doc §3.1: coherence streams along the field's coupling lines into a
 *       region where ε² rises (a drain), and the (1−q) fraction re-radiates as
 *       glow. So an aurora is the <b>co-location</b> of delivered coherence
 *       ({@code q} at/above its coherent high tail, {@link #AURORA_Q_FLOOR})
 *       with a drain ({@code ε²} in the rising-decoherence band,
 *       {@link #AURORA_EPS2_FLOOR} up to the storm floor {@link
 *       dev.cassicraft.game.sky.SkyRead#STORM_EDGE_EPS2} — above which the ε²
 *       is the destroying storm the sky owns, not a glowing drain). Intensity =
 *       the waste fraction {@code 1−q} (the (1−q) glow law, engine-real,
 *       qi-bubble-propulsion §2.5): the field sheds most where the lock is most
 *       imperfect.</li>
 *   <li><b>{@link Kind#ENVELOPE}</b> — the atmosphere's sub-condensation gas
 *       band vs the vacuum ceiling. The doc §1.4: below the gas-regime lower
 *       floor ({@code ρ < AIR_THETA_C}) is the KSP vacuum where the RealSim
 *       drag terms vanish; at/above condensation ({@code ρ ≥ TAU_C}) is the
 *       ground/body; the envelope is the wave-bearing {@code ρ} band between
 *       them. {@code fogDensity} normalizes within the band.</li>
 *   <li><b>{@link Kind#ORBIT_WELL}</b> — the body-seed condensation candidate.
 *       The doc §2.2: a body is the merge lineage condensing under the
 *       order-selective coherence gate, a local condensation whose own
 *       gravitational hold is felt in the open field. This Phase-1 read flags
 *       where the field is locally condensing (deep coherent {@code q},
 *       {@link #BODY_SEED_Q}) <b>and</b> carries a genuine gravitational
 *       character (|∇(g·Φ)| at/above {@link #BODY_HOLD_GRAD}) — the *precursor*
 *       of an orbitable body, never an orbit itself (the tree-gravity arm that
 *       actually holds orbits is not in Phase-1; the doc §6 gates it). [design]
 *       flagged honestly.</li>
 * </ul>
 *
 * <p><b>Priority</b> is {@code AURORA > ORBIT_WELL > ENVELOPE > CLEAR}: a
 * coherence discharge reads before the body-seed it drains toward, which reads
 * before the ambient thickness of the gas band. Same channels every time;
 * deterministic (never a seeded sky roll — the doc §5c gate (c) HARD).
 *
 * <p><b>The {@code [design]} thresholds are probe-calibrated / cited to the
 * measured settled box</b> (seed 42 @ the current settle, DT=0.001, 0.768
 * field-time units — the same census SkyRead and WindRead cite): the aurora's
 * q/ε² tails and the orbit well cite the measured percentiles in their
 * javadocs; the envelope band cites the registry's own condensation/void lines
 * (Quantizer.TAU_C = the measured ρ condensation boundary, MaterialRegistry's
 * AIR_THETA_C = the void floor). Never hardcode a threshold you did not
 * measure — re-read {@link #AURORA_Q_FLOOR}, {@link #AURORA_EPS2_FLOOR},
 * {@link #BODY_SEED_Q} and {@link #BODY_HOLD_GRAD} from
 * AtmosphereDeterminismMain's printed census if the field's distribution
 * changes.
 */
public final class AtmoRead {

	/**
	 * The aurora's delivered-coherence {@code q} floor — at/above this {@code q}
	 * the position carries enough coherence to feed a discharge (the field's
	 * coupling line delivering order to the drain, atmosphere §3.1). [design]
	 * probe-calibrated from the measured settled-box q distribution
	 * (AtmosphereDeterminismMain, seed 42 @ the current settle, DT=0.001,
	 * 0.768 field-time units): q p90=0.899, p99=1.165, max=1.427, mean=0.635.
	 * The floor sits at the coherent high tail's center (≈p90), so a position
	 * genuinely delivering coherence (the best-locked field) can discharge
	 * while the ordinary coherence body (p50≈0.635) does not.
	 */
	public static final float AURORA_Q_FLOOR = 0.90f;

	/**
	 * The aurora's drain-band {@code ε²} floor — at/above this {@code ε²} and
	 * below the storm floor {@link dev.cassicraft.game.sky.SkyRead#STORM_EDGE_EPS2}
	 * a position is a drain: the φ-lock is slipping enough that the delivered
	 * coherence discharges, but not so far that the field is destroyed (the
	 * storm's darkening, which the sky slice owns). [design] probe-calibrated
	 * from the measured settled-box ε² distribution
	 * (AtmosphereDeterminismMain / WindDeterminismMain, seed 42 @ the current
	 * settle): ε² p90=0.202, p95=0.251, p99=0.385, max=0.573, mean=0.102. The
	 * floor sits at ≈p90 — a genuinely elevated decoherence (the top ~10%), not
	 * the coherent bulk.
	 */
	public static final float AURORA_EPS2_FLOOR = 0.20f;

	/**
	 * The body-seed {@code q} condensation floor — at/above this deep coherent
	 * {@code q} the field is locally condensing toward organized matter (the
	 * merge lineage's coherent gate, atmosphere §2.2; the order-selective
	 * coherence gate {@code q_sel = q_coh·q_ord > φ⁻² ≈ 0.382}). [design]
	 * probe-calibrated: this sits in the deep coherent tail, matching the sky
	 * slice's own glow tail (SkyRead GLOW_Q_TAIL = 1.05, ≈ top 5–10% of the
	 * lattice) — the genuinely best-locked condensate reads as a body-seed
	 * precursor while the ordinary field does not.
	 */
	public static final float BODY_SEED_Q = 1.05f;

	/**
	 * The body-seed gravitational-hold floor — at/above this |∇(g·Φ)| a
	 * position carries a strong enough river gradient that a condensation there
	 * would feel its own gravitational hold (the honest Phase-1 precursor of an
	 * orbitable body, atmosphere §2.2). [design] probe-calibrated from the
	 * measured settled-box |∇(g·Φ)| distribution (AtmosphereDeterminismMain,
	 * seed 42 @ the current settle): |∇| p10=1.447, p50=2.918, p90=4.998,
	 * p99=6.984, max=8.193. The floor at 4.5 sits just under the measured
	 * p90 — a genuinely strong well (the top ~1% co-located with deep q, per
	 * the gate's ORBIT sweep: |∇|≥4 with q≥1.05 → 0.98% of the lattice), not
	 * the flat field. A [design] dial cited against the measured continuum,
	 * never a free grant.
	 */
	public static final float BODY_HOLD_GRAD = 4.5f;

	/**
	 * The envelope's vacuum floor — below this {@code ρ} the field is the KSP
	 * vacuum (the gas-regime lower floor, atmosphere §1.4). Cited to the
	 * registry's void threshold: {@code MaterialRegistry.AIR_THETA_C}
	 * (material-regimes §2 "Gas: ρ < θ_c but above a second lower floor").
	 */
	public static final float ENVELOPE_VACUUM_RHO =
			(float) MaterialRegistry.AIR_THETA_C;

	/**
	 * The envelope's condensation ceiling — at/above this {@code ρ} the field
	 * is the condensed body/ground (the terrain's own boundary, Quantizer.TAU_C,
	 * cited to the measured ρ condensation boundary). The envelope is the
	 * wave-bearing gas band below this.
	 */
	public static final float ENVELOPE_CONDENSE_RHO = Quantizer.TAU_C;

	private AtmoRead() {
	}

	/** The atmosphere phenomenon at one position. */
	public enum Kind {
		/** {@code q} coherent-high co-located with a rising-ε² drain — the (1−q) discharge glow. */
		AURORA("AURORA — the coherence discharge into a drain"),
		/** Deep coherent {@code q} co-located with a strong ∇(g·Φ) — the body-seed condensation candidate. */
		ORBIT_WELL("ORBIT WELL — a body-seed condensation candidate"),
		/** {@code ρ} in the sub-condensation gas band — the envelope, the atmosphere vs the vacuum ceiling. */
		ENVELOPE("ENVELOPE — inside the atmosphere's gas band"),
		/** none of the above — the dry sky / the void. */
		CLEAR("CLEAR — no field phenomenon here");

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
			float gradX, float gradY, float gradZ, float gradMag,
			float discharge, float fogDensity) {

		/** Whether this position reads a coherence discharge (the aurora). */
		public boolean isAurora() {
			return kind == Kind.AURORA;
		}

		/** Whether this position reads a body-seed condensation candidate. */
		public boolean isOrbitWell() {
			return kind == Kind.ORBIT_WELL;
		}

		/** Whether this position sits inside the atmosphere's gas band. */
		public boolean isInEnvelope() {
			return kind == Kind.ENVELOPE;
		}

		/**
		 * The aurora's glow — the waste fraction {@code 1−q} (the (1−q) glow
		 * law, atmosphere §3.1): how much of the delivered coherence the drain
		 * fails to re-lock. Nonzero exactly where the discharge runs at a
		 * coherence deficit (q&lt;1) over a drain; ≤ 0 once the field is
		 * over-coherent (no waste to shed).
		 */
		public float discharge() {
			return discharge;
		}

		/**
		 * The envelope's fog density — {@code ρ} normalized within the gas band
		 * (0 at the vacuum floor, 1 at condensation, atmosphere §1.5
		 * "fog-density ∝ ρ"): thick near the ground, thinning to the ceiling.
		 */
		public float fogDensity() {
			return fogDensity;
		}
	}

	/**
	 * The |∇(g·Φ)| magnitude at the position — the river gradient's strength,
	 * the local gravitational character (the same channel the wind's flow-face
	 * reads, atmosphere §2.2 "the body would move under the river law").
	 */
	public static float gradMag(Quantizer.FieldReading r) {
		double gx = r.gradX(), gy = r.gradY(), gz = r.gradZ();
		return (float) Math.sqrt(gx * gx + gy * gy + gz * gz);
	}

	/**
	 * Classify the local atmosphere from one {@link FieldReading}.
	 *
	 * @param r the published-channel reading at the block position
	 * @return the atmosphere verdict + intensities; a pure function of the
	 *         reading (same reading → same atmosphere, atmosphere §5c —
	 *         deterministic, never a seeded roll).
	 */
	public static Read classify(Quantizer.FieldReading r) {
		float q = r.q();
		float eps2 = r.eps2();
		float rho = r.rho();
		float gm = gradMag(r);

		// The aurora's discharge — delivered coherence into a rising-ε² drain
		// (atmosphere §3.1). The drain band is [AURORA_EPS2_FLOOR, storm floor):
		// above the storm floor the ε² is the destroying darkening (sky's own),
		// not a glowing drain. The glow = the (1−q) waste fraction, capped at 0.
		boolean inDrain = eps2 >= AURORA_EPS2_FLOOR
				&& eps2 < dev.cassicraft.game.sky.SkyRead.STORM_EDGE_EPS2;
		if (inDrain && q >= AURORA_Q_FLOOR) {
			float discharge = Math.max(0f, 1f - q);
			return new Read(Kind.AURORA, q, eps2, rho, r.gradX(), r.gradY(), r.gradZ(),
					gm, discharge, fogDensityFor(rho));
		}

		// The orbit well — a local condensation candidate (deep coherent q) with
		// a genuine gravitational hold (strong ∇(g·Φ)). [design] Phase-1
		// precursor read; the tree arm that actually holds orbits is later.
		if (q >= BODY_SEED_Q && gm >= BODY_HOLD_GRAD) {
			return new Read(Kind.ORBIT_WELL, q, eps2, rho, r.gradX(), r.gradY(), r.gradZ(),
					gm, 0f, fogDensityFor(rho));
		}

		// The envelope — the sub-condensation gas band (the atmosphere vs the
		// vacuum ceiling, atmosphere §1.4). At/above condensation = the ground,
		// below the vacuum floor = the void; between them the wave-bearing air.
		if (rho >= ENVELOPE_VACUUM_RHO && rho < ENVELOPE_CONDENSE_RHO) {
			return new Read(Kind.ENVELOPE, q, eps2, rho, r.gradX(), r.gradY(), r.gradZ(),
					gm, 0f, fogDensityFor(rho));
		}

		// CLEAR — none of the field's atmosphere phenomena (the dry sky, the
		// condensed ground, or the void).
		return new Read(Kind.CLEAR, q, eps2, rho, r.gradX(), r.gradY(), r.gradZ(),
				gm, 0f, fogDensityFor(rho));
	}

	/**
	 * The envelope's fog-density — {@code ρ} normalized within the gas band
	 * (0 at the vacuum floor, 1 at condensation). A pure presentation of the
	 * published {@code ρ}, the doc's fog-density-as-ρ (§1.5).
	 */
	private static float fogDensityFor(float rho) {
		float span = ENVELOPE_CONDENSE_RHO - ENVELOPE_VACUUM_RHO;
		if (span <= 0f) {
			return rho >= ENVELOPE_CONDENSE_RHO ? 1f : 0f;
		}
		return Math.max(0f, Math.min(1f, (rho - ENVELOPE_VACUUM_RHO) / span));
	}
}
