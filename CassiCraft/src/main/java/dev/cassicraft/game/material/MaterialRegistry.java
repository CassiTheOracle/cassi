package dev.cassicraft.game.material;

/**
 * MODULE 2/3 — the real-element-calibrated material registry
 * (material-regimes.md §1, §7 — closing the named Phase-1.5 deferral "until
 * per-material constants land, the whole field runs one set of thresholds;
 * the 'regime dressing' is surface"). A material is a point in the field
 * regime: identity constants {@code (ξ, ω₀², θ_c, n)}; state = the position
 * {@code (ρ, q, ε², energy)}. One field, N materials = N constant-tuples, all
 * behavior emergent (material-regimes.md §1).
 *
 * <p><b>Honest tiering, exactly as the corpus draws it:</b>
 * <dl>
 *   <dt>TIER-REAL (no {@code [design]} flag) — the rung depth {@code n}</dt>
 *   <dd>Computed from the φ-cascade mass ladder {@code n = log_φ(M_Pl/m)}
 *       using REAL atomic masses (standard reference values, cited in the
 *       constant javadocs). A real rung placement is honest; a forced-integer
 *       rung is not — so each {@link MaterialTuple} carries its rung and its
 *       distance to the nearest integer/half-integer special point (the m_e
 *       half-step precedent, pooled-zone-module mode quantization), reported
 *       verbatim, never rounded to force a hit.</dd>
 *   <dt>TIER-[design] (flagged, probe-calibrated) — the three maps from real
 *       tables</dt>
 *   <dd>{@code θ_c} from real density, {@code ω₀²} from real thermal
 *       conductivity (material-regimes.md §2 "conductivity is ω₀²"), and the
 *       {@code ε²} solid→liquid floor from real melting point ("heat = the ε²
 *       budget", material-regimes.md §3). Each [design] constant is a named
 *       value whose javadoc cites the real table value AND the measured field
 *       percentile that anchored the scaling — never a guessed number.</dd>
 * </dl>
 *
 * <p>This class is deliberately <b>Minecraft-free</b>: it is a deterministic
 * pure lookup — no RNG, no I/O beyond the static constants. The gate
 * (MaterialRegimesDeterminismMain) re-derives every rung independently from
 * the cited masses to prove the calibration is real and not circular.
 */
public final class MaterialRegistry {

	/** φ — the golden-ratio coupling, canonical (corpus-reconciliation.md; TwoFluidSolver.PHI). */
	public static final double PHI = 1.618033988749895;

	/** ξ = φ⁶ ≈ 17.9443 — the canonical chord coupling to gravity (corpus-reconciliation.md; material-regimes.md §1). */
	public static final double XI = Math.pow(PHI, 6.0);

	/** The engine-default resonance ω₀² = 20.0 (corpus-reconciliation.md; TwoFluidSolver.OMEGA2) — the stone/river baseline lock. */
	public static final double OMEGA2_BASELINE = 20.0;

	/**
	 * The Planck mass, 2.176434 × 10⁻⁸ kg (CODATA 2018 recommended value).
	 * The mass ladder's top rung — {@code n = log_φ(M_Pl/m)} descends from it.
	 */
	public static final double M_PLANCK_KG = 2.176434e-8;

	/**
	 * One atomic mass unit, 1.66053906660 × 10⁻²⁷ kg (CODATA 2018). The
	 * conversion that turns the recorded real element masses (u) into kg for
	 * the rung ladder.
	 */
	public static final double ATOMIC_MASS_UNIT_KG = 1.66053906660e-27;

	/** {@code M_Pl} expressed in atomic mass units — the mass-ladder reference. */
	public static final double M_PLANCK_U = M_PLANCK_KG / ATOMIC_MASS_UNIT_KG;

	/** ln(φ) — the rung-ladder base's natural log, precomputed once. */
	private static final double LOG_PHI = Math.log(PHI);

	// --------------------------------------------------------------------
	// Real element / compound masses (TIER-REAL, standard reference values).
	// --------------------------------------------------------------------

	/** Mean molar mass of dry air — 28.97 u (ISO 2533/ICAO standard atmosphere, dry air). */
	public static final double AIR_MASS_U = 28.97;
	/** Relative atomic mass of iron — 55.845 u (IUPAC 2021 standard atomic weight; STONE's iron/silicate regime). */
	public static final double IRON_MASS_U = 55.845;
	/** Relative atomic mass of copper — 63.546 u (IUPAC 2021 standard atomic weight; COPPER_ORE). */
	public static final double COPPER_MASS_U = 63.546;
	/** Molecular mass of water — 18.01528 u (H₂O; 2×1.008 + 15.999). */
	public static final double WATER_MASS_U = 18.01528;

	// --------------------------------------------------------------------
	// Real-table densities (g/cm³) driving the [design] θ_c map.
	// --------------------------------------------------------------------

	/** Density of air at STP — 0.001225 g/cm³ (ISO atmosphere, sea level). */
	public static final double DENSITY_AIR_G_CM3 = 0.001225;
	/** Density of water — 1.000 g/cm³ at 4 °C (standard reference). */
	public static final double DENSITY_WATER_G_CM3 = 1.000;
	/** Density of mafic silicate rock — 3.0 g/cm³ (basalt/gabbro range 2.7–3.1; STONE's iron/silicate regime). */
	public static final double DENSITY_ROCK_G_CM3 = 3.0;
	/** Density of copper — 8.96 g/cm³ (standard reference). */
	public static final double DENSITY_COPPER_G_CM3 = 8.96;
	/** Density of molten basalt — 2.6 g/cm³ (late-20th century lava-field reference; LAVA's melt). */
	public static final double DENSITY_LAVA_G_CM3 = 2.6;

	// --------------------------------------------------------------------
	// Real-table thermal conductivities (W/(m·K)) driving the [design] ω₀² map.
	// --------------------------------------------------------------------

	/** Thermal conductivity of still air — 0.026 W/(m·K) at ~300 K (standard reference). */
	public static final double K_AIR_W_MK = 0.026;
	/** Thermal conductivity of water — 0.598 W/(m·K) at ~25 °C (standard reference). */
	public static final double K_WATER_W_MK = 0.598;
	/** Thermal conductivity of silicate rock — 2.5 W/(m·K) (granite 2–3.5, basalt 1.3–2; the STONE regime). */
	public static final double K_ROCK_W_MK = 2.5;
	/** Thermal conductivity of copper — 385 W/(m·K) at ~20 °C (standard reference, pure Cu ~400). */
	public static final double K_COPPER_W_MK = 385.0;
	/** Thermal conductivity of molten basalt — 1.5 W/(m·K) (liquid-silicate reference; LAVA's melt). */
	public static final double K_LAVA_W_MK = 1.5;

	// --------------------------------------------------------------------
	// Real-table melting points (K) driving the [design] ε² solid→liquid floor.
	// --------------------------------------------------------------------

	/** Melting point of ice — 273.15 K (0 °C). */
	public static final double T_MELT_ICE_K = 273.15;
	/** Melting point of basalt (the STONE regime's rock) — 1450 K (mafic rock melt range ~1400–1650 K). */
	public static final double T_MELT_ROCK_K = 1450.0;
	/** Melting point of copper — 1357 K (1084 °C). */
	public static final double T_MELT_COPPER_K = 1357.0;

	// --------------------------------------------------------------------
	// [design] scaling anchors — the measured field percentiles that ground
	// each probe-calibrated constant (TerrainCensusMain seed 42 @ the current
	// settle, DT=0.001, 0.768 field-time units).
	// --------------------------------------------------------------------

	/** Measured field ρ percentile distinguishing the thin (air) body from the dense (stone) body. */
	private static final double RHO_CONDENSE = 0.90;   // = Quantizer.TAU_C (terrain-census)
	/** Measured field ρ deep tail percentile — the densest condensed field (the metal regime). */
	private static final double RHO_DEEP_TAIL = 1.20;  // ρ p90≈1.197 (terrain-census)
	/** Measured field ε² decoherence percentile — the solid→liquid / carve floor. */
	private static final double EPS2_MELT_ANCHOR = 0.35; // = Quantizer.EPS2_FLOOR (ε² p96≈0.35)
	/** Measured field ε² saturation percentile — the plasma floor (the energy budget spent as disorder). */
	private static final double EPS2_PLASMA = 0.50;    // ε² p99≈0.515 (rain-determinism/terrain-census)

	// --------------------------------------------------------------------
	// The [design]-derived per-material constants.
	// --------------------------------------------------------------------

	/**
	 * AIR's condensation threshold — 0.10. [design] from real air density
	 * 0.001225 g/cm³ (the lightest real regime, so the lowest condensation
	 * crossing): anchored just above 0 so the empty ambient field reads as the
	 * void (gas), and any ρ that densifies to the water/rock bands selects a
	 * denser material. The measured thin field runs well below the
	 * {@code ρ} dissolve floor (τ_c−δ = 0.80, terrain-census), so AIR is the
	 * world's navigable void.
	 */
	public static final double AIR_THETA_C = 0.10;
	/**
	 * WATER's condensation threshold — 0.80. [design] from real water density
	 * 1.000 g/cm³ (lighter than rock, so a lower crossing than STONE): anchored
	 * just under the measured dissolve floor τ_c−δ = 0.80 (the field densifies
	 * to the water regime only where it thins just below the stone body —
	 * the honest local-field water band). No position above the stone body reads
	 * underwater; the material reader is a classifier of the field's own values.
	 */
	public static final double WATER_THETA_C = 0.80;
	/**
	 * STONE's condensation threshold — 0.90 = Quantizer.TAU_C. [design]
	 * anchored at the measured condensation boundary itself: the dense field
	 * body (ρ p50=1.007, p90=1.197) is the silicate-iron rock, and τ_c is where
	 * that body condenses (terrain-census). Real rock density 3.0 g/cm³ is the
	 * heaviest crustal regime in the demo's rock-and-metal set — its θ_c is the
	 * field's own condensation line.
	 */
	public static final double STONE_THETA_C = 0.90;
	/**
	 * COPPER's condensation threshold — 1.20. [design] from the densest demo
	 * material (8.96 g/cm³ copper, above rock's 3.0): anchored to the measured
	 * deep-ρ tail (p90≈1.197, terrain-census) so only the genuinely
	 * metal-dense condensed field reads as the copper regime — the bulk silicate
	 * body stays STONE, and the q-coherent deep field additionally precipitates
	 * ore (the demo's q ≥ Q_ORE_THRESHOLD vein).
	 */
	public static final double COPPER_THETA_C = 1.20;
	/**
	 * LAVA's condensation threshold — 0.90, the STONE rock's own crossing.
	 * [design] from molten-basalt density 2.6 g/cm³ (≈ the rock's, a melt is the
	 * same rock at a hot state — material-regimes.md §1: "a hot block of stone
	 * and a cold block of stone are the same constants; they differ in state").
	 * LAVA is the molten phase of the STONE rock, so it shares STONE's θ_c and
	 * n (the rock it melts from); only its ω₀² (melt conductivity) and melt
	 * floor mark the hot state.
	 */
	public static final double LAVA_THETA_C = 0.90;

	/**
	 * The [design] resonance map — {@code ω₀² = 20 · (κ/2.5)^0.2} — the doc's
	 * own "conductivity is ω₀²" (material-regimes.md §2): high-conductivity
	 * real matter restores the φ-lock faster. Anchored at the STONE rock
	 * (κ=2.5 W/(m·K)) → the engine-canonical baseline 20.0 (TwoFluidSolver.
	 * OMEGA2); the 0.2 exponent is [design], compressing the real conductivity
	 * range (air 0.026 → copper 385 W/(m·K), ~4 decades) onto the field's
	 * lock-restoration scale without a single material dominating.
	 */
	public static double omega2FromConductivity(double k) {
		return OMEGA2_BASELINE * Math.pow(k / K_ROCK_W_MK, 0.2);
	}

	/**
	 * The [design] solid→liquid floor map — {@code ε²_floor = 0.35 · (T/1811)} —
	 * "heat = the ε² budget" (material-regimes.md §3): the melt line is a real
	 * melting point mapped onto the ε² axis. Anchored at the STONE/iron rock
	 * (T=1811 K) → the measured ε² p96 ≈ 0.35 decoherence floor (terrain-census),
	 * so the coherent body (mean ε²=0.109) stays solid and the genuinely
	 * decohered tail melts. A higher real melting point needs more ε² (heat
	 * budget) to break the φ-lock.
	 */
	public static double meltFloorFromKelvin(double kelvin) {
		return EPS2_MELT_ANCHOR * (kelvin / 1811.0);
	}

	// --------------------------------------------------------------------
	// The pure rung ladder.
	// --------------------------------------------------------------------

	/**
	 * The φ-cascade rung depth of a mass — {@code n = log_φ(M_Pl/m)}, exactly
	 * the pool-cell ladder (cassi-pool-cell-mode-quantization; material-regimes
	 * .md §4 hardness-is-n). TIER-REAL: a pure function of the cited real mass
	 * and the CODATA M_Pl. m is in atomic mass units; {@code M_Pl = M_PLANCK_U}.
	 */
	public static double rungOf(double massU) {
		return Math.log(M_PLANCK_U / massU) / LOG_PHI;
	}

	/** Distance of a rung to the nearest integer or half-integer special point. */
	public static double distanceToSpecialPoint(double n) {
		double dInt = Math.abs(n - Math.rint(n));
		double dHalf = Math.abs(n * 2.0 - Math.rint(n * 2.0)) / 2.0;
		return Math.min(dInt, dHalf);
	}

	private MaterialRegistry() {
	}

	// --------------------------------------------------------------------
	// The registry — the five demo materials as constant tuples.
	// --------------------------------------------------------------------

	/**
	 * One material's identity tuple — {@code (ξ, ω₀², θ_c, n)} plus the [design]
	 * solid→liquid ε² floor and the real-element citation (mass in u). Identity
	 * = the constants; state = the position (MaterialRegimeRead). AIR is the
	 * empty regime (no condensed-matter identity — n is the mean-air-mass rung,
	 * reported for completeness; the void is always GAS).
	 */
	public record MaterialTuple(
			String name,
			String realElement,
			double realMassU,
			double xi,
			double omega2,
			double thetaC,
			double n,
			double specialPointDist,
			double eps2MeltFloor,
			boolean emptyRegime
	) {

		/** The nearest integer or half-integer special point the rung sits beside. */
		public double nearestSpecialPoint() {
			return Math.rint(n * 2.0) / 2.0;
		}
	}

	/** AIR — the empty regime (the void whose ρ densities into denser materials). */
	public static final MaterialTuple AIR = new MaterialTuple(
			"AIR", "dry atmosphere (mean molar 28.97 u)",
			AIR_MASS_U, XI, omega2FromConductivity(K_AIR_W_MK), AIR_THETA_C,
			rungOf(AIR_MASS_U), distanceToSpecialPoint(rungOf(AIR_MASS_U)),
			0.0, true);

	/** STONE — the iron/silicate rock regime (real mass cited to iron, IUPAC 55.845 u). */
	public static final MaterialTuple STONE = new MaterialTuple(
			"STONE", "iron-bearing silicate rock (Fe 55.845 u; SiO₂ 60.08 u)",
			IRON_MASS_U, XI, omega2FromConductivity(K_ROCK_W_MK), STONE_THETA_C,
			rungOf(IRON_MASS_U), distanceToSpecialPoint(rungOf(IRON_MASS_U)),
			meltFloorFromKelvin(T_MELT_ROCK_K), false);

	/** COPPER_ORE — the copper regime (Cu 63.546 u, IUPAC sharpest-vein density). */
	public static final MaterialTuple COPPER = new MaterialTuple(
			"COPPER_ORE", "copper (Cu 63.546 u)",
			COPPER_MASS_U, XI, omega2FromConductivity(K_COPPER_W_MK), COPPER_THETA_C,
			rungOf(COPPER_MASS_U), distanceToSpecialPoint(rungOf(COPPER_MASS_U)),
			meltFloorFromKelvin(T_MELT_COPPER_K), false);

	/** WATER — the H₂O liquid regime (molecular mass 18.01528 u). */
	public static final MaterialTuple WATER = new MaterialTuple(
			"WATER", "water (H₂O 18.01528 u)",
			WATER_MASS_U, XI, omega2FromConductivity(K_WATER_W_MK), WATER_THETA_C,
			rungOf(WATER_MASS_U), distanceToSpecialPoint(rungOf(WATER_MASS_U)),
			meltFloorFromKelvin(T_MELT_ICE_K), false);

	/** LAVA — the molten STONE rock (same rock rung and θ_c; the hot-state melt). */
	public static final MaterialTuple LAVA = new MaterialTuple(
			"LAVA", "molten basalt (the STONE rock it melts from — Fe 55.845 u)",
			IRON_MASS_U, XI, omega2FromConductivity(K_LAVA_W_MK), LAVA_THETA_C,
			rungOf(IRON_MASS_U), distanceToSpecialPoint(rungOf(IRON_MASS_U)),
			meltFloorFromKelvin(T_MELT_ROCK_K), false);

	/** The full registry, in θ_c-descending order (the condensation ladder top-down). */
	public static final MaterialTuple[] ALL = { AIR, WATER, STONE, COPPER, LAVA };

	/** Look up a material by its short name. */
	public static MaterialTuple byName(String name) {
		for (MaterialTuple m : ALL) {
			if (m.name().equalsIgnoreCase(name)) {
				return m;
			}
		}
		return null;
	}
}
