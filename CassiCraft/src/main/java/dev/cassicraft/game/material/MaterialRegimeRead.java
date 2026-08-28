package dev.cassicraft.game.material;

import dev.cassicraft.game.sampler.Quantizer;

/**
 * MODULE 2/3 — the material-regime read (material-regimes.md §1, §2). A
 * <b>pure, Minecraft-free</b> consumer: given ONE {@link Quantizer.FieldReading}
 * at a position (the corpus's "one extra sample at the player's position",
 * field-instruments §1.4 — the same fused 8-corner sample the Weatherglass
 * takes), it classifies the local regime state and which material tuple governs
 * it.
 *
 * <p><b>The honest classification</b> (material-regimes.md §2): the state's
 * position selects the tuple — the densest material whose condensation
 * threshold {@code θ_c} the local {@code ρ} reaches — then the phase machine
 * splits by the ε² budget ("heat = the ε² budget", §3):
 * <ul>
 *   <li><b>{@link Phase#SOLID}</b> — {@code ρ ≥ θ_c} and {@code ε²} below the
 *       material's (real-melting-point) solid floor: coherent, dense, φ-locked.</li>
 *   <li><b>{@link Phase#LIQUID}</b> — {@code ρ ≥ θ_c} but {@code ε²} at/above the
 *       solid floor: dense yet decohered (the field cannot hold the φ-lock
 *       rigidly, so it flows — the molten rock of the STONE band is LAVA).</li>
 *   <li><b>{@link Phase#GAS}</b> — {@code ρ < θ_c}: diffuse, poorly-held matter
 *       (and always the verdict of the empty AIR regime).</li>
 *   <li><b>{@link Phase#PLASMA}</b> — {@code ε²} at/above the measured
 *       saturation band: the coherence budget is spent as disorder even though
 *       {@code ρ} may be high.</li>
 * </ul>
 *
 * <p>This is a <b>read of the published channels via the sampling seam</b> —
 * never a write, never free energy (a material read grants nothing; it
 * classifies the field's own values, only-mutator rule). Purine and
 * deterministic: same reading → same tuple and phase (the hard gate,
 * MaterialRegimesDeterminismMain (d)).
 */
public final class MaterialRegimeRead {

	/**
	 * The measured field ε² saturation band — at/above this a dense region reads
	 * {@link Phase#PLASMA} (the energy budget spent as disorder; the coherence
	 * budget is exhausted even at high ρ). [design] probe-calibrated from the
	 * measured settled-box ε² distribution (TerrainCensusMain / RainDeterminismMain,
	 * seed 42 @ the current settle): ε² p99≈0.515, max≈0.573; 0.50 sits in the
	 * genuine saturation tail, so the ordinary low-ε² field (mean 0.109) never
	 * reads plasma.
	 */
	public static final double PLASMA_EPS2 = 0.50;

	private MaterialRegimeRead() {
	}

	/** The emergent phase — regions of the same (ρ, q, ε²) space, not materials. */
	public enum Phase {
		/** Coherent, dense, φ-locked — {@code ρ ≥ θ_c}, ε² below the solid floor. */
		SOLID("SOLID"),
		/** Dense yet decohered — {@code ρ ≥ θ_c}, ε² at/above the solid floor. */
		LIQUID("LIQUID"),
		/** Diffuse, poorly-held matter — {@code ρ < θ_c} (and always AIR). */
		GAS("GAS"),
		/** The coherence budget spent as disorder — ε² at/above the saturation band. */
		PLASMA("PLASMA");

		private final String label;

		Phase(String label) {
			this.label = label;
		}

		/** The human-readable verdict label. */
		public String label() {
			return label;
		}
	}

	/** The regime read at one position — the governing tuple plus the phase verdict. */
	public record RegimeRead(MaterialRegistry.MaterialTuple material, Phase phase,
			float rho, float q, float eps2, double specialPointDist) {

		/** Whether the position is condensed (solid or liquid). */
		public boolean isCondensed() {
			return phase == Phase.SOLID || phase == Phase.LIQUID;
		}

		/** Whether the position is solid (the anti-vacuity's positive class). */
		public boolean isSolid() {
			return phase == Phase.SOLID;
		}
	}

	/**
	 * Classify the local regime at a position from one {@link FieldReading}.
	 *
	 * <p><b>Tuple selection</b> — the densest material whose condensation
	 * threshold the local {@code ρ} reaches (the highest {@code θ_c ≤ ρ});
	 * below AIR's threshold the field is the empty void (AIR, GAS). This is the
	 * "nearest θ_c/ρ region" of material-regimes.md §2, made monotone by
	 * density: an AIR band between AIR's own θ_c and WATER's, a WATER band below
	 * STONE's, and so on. The STONE band's liquid phase is the molten rock,
	 * reported as the LAVA tuple (LAVA shares STONE's θ_c and rung — "the rock
	 * it melts from").
	 *
	 * @param r the published-channel reading at the block position
	 * @return the governing material + phase verdict; a pure function of the
	 *         reading (same reading → same verdict, the hard gate).
	 */
	public static RegimeRead classify(Quantizer.FieldReading r) {
		float rho = r.rho();
		float q = r.q();
		float eps2 = r.eps2();

		// Plasma overrides first — the spent coherence budget is the regime's
		// dominant fact, regardless of how high ρ sits (material-regimes §2).
		if (eps2 >= PLASMA_EPS2) {
			return new RegimeRead(MaterialRegistry.STONE, Phase.PLASMA, rho, q, eps2,
					MaterialRegistry.distanceToSpecialPoint(MaterialRegistry.STONE.n()));
		}

		// Tuple selection by density: the densest material whose θ_c ≤ ρ.
		MaterialRegistry.MaterialTuple tuple;
		if (rho >= MaterialRegistry.COPPER_THETA_C) {
			tuple = MaterialRegistry.COPPER;
		} else if (rho >= MaterialRegistry.STONE_THETA_C) {
			tuple = MaterialRegistry.STONE;
		} else if (rho >= MaterialRegistry.WATER_THETA_C) {
			tuple = MaterialRegistry.WATER;
		} else {
			tuple = MaterialRegistry.AIR; // the void; ρ < AIR's condensation
		}

		// Phase: the empty regime is always GAS; dense material is solid below
		// its real-melting-point floor, liquid at/above it (the rock's liquid
		// phase is the LAVA tuple — the melt line, material-regimes §2).
		if (tuple.emptyRegime()) {
			return new RegimeRead(tuple, Phase.GAS, rho, q, eps2,
					MaterialRegistry.distanceToSpecialPoint(tuple.n()));
		}
		if (eps2 >= tuple.eps2MeltFloor()) {
			MaterialRegistry.MaterialTuple phaseTuple =
					tuple == MaterialRegistry.STONE ? MaterialRegistry.LAVA : tuple;
			return new RegimeRead(phaseTuple, Phase.LIQUID, rho, q, eps2,
					MaterialRegistry.distanceToSpecialPoint(phaseTuple.n()));
		}
		return new RegimeRead(tuple, Phase.SOLID, rho, q, eps2,
				MaterialRegistry.distanceToSpecialPoint(tuple.n()));
	}

	/**
	 * Whether a sample's regime reaches the COPPER identity by density — the
	 * deep-dense metal tail ({@code ρ ≥ MaterialRegistry.COPPER_THETA_C}, the
	 * densest demo material's condensation band, material-regimes.md §1). This
	 * is the registry's block-kind dressing test the Quantizer consults (it is
	 * also the copper branch of {@link #classify}). The {@code q}-precipitated
	 * ore vein is a second copper axis the Quantizer's own {@code q ≥
	 * Q_ORE_THRESHOLD} dial supplies (material-regimes.md §3 "a vein is where q
	 * accumulates").
	 */
	public static boolean isCopperRegime(float rho) {
		return rho >= (float) MaterialRegistry.COPPER_THETA_C;
	}

	/** The material command's printed readout (deterministic pure function of the read). */
	public static String text(RegimeRead r) {
		StringBuilder sb = new StringBuilder();
		MaterialRegistry.MaterialTuple m = r.material();
		sb.append("  Regime state  ρ=").append(fmt(r.rho()))
				.append("  q=").append(fmt(r.q()))
				.append("  ε²=").append(fmt(r.eps2())).append("\n");
		sb.append("  Governing material ").append(m.name())
				.append(r.material() == MaterialRegistry.LAVA ? " (molten " + MaterialRegistry.STONE.name() + ")" : "")
				.append("\n");
		sb.append("  Phase ").append(r.phase().label()).append("\n");
		sb.append("  Tuple ξ=").append(String.format("%.4f", m.xi()))
				.append("  ω₀²=").append(String.format("%.2f", m.omega2()))
				.append("  θ_c=").append(String.format("%.2f", m.thetaC()))
				.append("  n=").append(String.format("%.4f", m.n()))
				.append("  (nearest special point ").append(String.format("%.1f", m.nearestSpecialPoint()))
				.append(", dist ").append(String.format("%.4f", r.specialPointDist())).append(")\n");
		sb.append("  Element ").append(m.realElement());
		return sb.toString();
	}

	private static String fmt(float v) {
		return String.format("%.4f", v);
	}
}
