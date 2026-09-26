package dev.cassicraft.game.instrument;

import dev.cassicraft.game.material.MaterialRegimeRead;
import dev.cassicraft.game.material.MaterialRegistry;
import dev.cassicraft.game.sampler.Quantizer;

/**
 * MODULE 2/3 — the FieldGlass read (field-instruments.md §1.2, §2.2 the base
 * idiom; material-regimes.md §1, §4). A <b>pure, Minecraft-free</b> consumer:
 * given ONE {@link Quantizer.FieldReading} at a position — the corpus's "one
 * extra sample at the player's position" (field-instruments §1.4) — it renders
 * the FieldGlass's full chart: the five published channels the instrument
 * reads, honestly tiered. The FieldGlass is a member of the instrument family
 * that aimes the Weatherglass's base idiom (<em>and</em> adds the density and
 * material-rung depth axes the Weatherglass's four forms leave out — the
 * {@code ρ} read and the {@code n}-rung read of the governing material
 * regime).
 *
 * <p>This is the "field-glass / divining-rod" presentation of the corpus's
 * family rule (field-instruments §2.1): <b>every instrument is a consumer of
 * the same publish with a presentation idiom, never a new channel.</b> Every
 * number below traces to a published channel ({@code ρ}, {@code q},
 * {@code ε²}, the river gradient {@code ∇(g·Φ)}) or a registry constant
 * ({@link MaterialRegistry}) — the read never writes, never perturbs the
 * field, never grants anything (only-mutator rule; no-free-energy cap).
 *
 * <p><b>The five channels, and how each is presented:</b>
 * <ul>
 *   <li><b>q</b> (coherence, attractor ≈ 0.947) — the <b>lume</b>: high →
 *       steady bright, mid → dim, collapsed → <em>dead flat grey</em> (the
 *       desert's signature, field-hazards §3).</li>
 *   <li><b>ρ</b> (density, {@code EY+EI}) — the <b>depth</b>: how much field is
 *       here, against the condensation ladder {@code θ_c}.</li>
 *   <li><b>ε²</b> (decoherence, {@code (EY − φ·EI)²}) — the <b>climbing glow</b>:
 *       a rising read marks a storm's front / scar / decoherence well
 *       (field-hazards §2.3).</li>
 *   <li><b>∇(g·Φ)</b> (the river gradient) — the <b>lean</b>: which way the
 *       field's downhill points (direction + magnitude, field-instruments §1.2).</li>
 *   <li><b>(1−q)</b> (the waste fraction, energy-harnessing §2) — the <b>waste
 *       tint</b>: how wasteful the field here is running.</li>
 * </ul>
 * The band thresholds below are the instrument's [design] idiom (presentation
 * over the real channels, field-instruments §1.4); the governing material's
 * rung {@code n = log_φ(M_Pl/m)} is TIER-REAL (MaterialRegistry), while its
 * {@code θ_c}/{@code ω₀²}/{@code ε²}-floor maps are flagged [design]
 * (material-regimes §7). Each is rendered with its tier so the calibration is
 * legible, never hidden.
 */
public final class FieldGlassRead {

	/** The field's healthy coherence attractor (canonical q ≈ 0.947). */
	public static final float Q_ATTRACTOR = 0.947f;
	/** Above this q the lume reads as steady/bright (calm, holding the φ-lock). */
	public static final float Q_STEADY = 0.80f;
	/** Below this q the lume dims; the desert signature (q-collapse) floor. */
	public static final float Q_COLLAPSE = 0.10f;

	private FieldGlassRead() {
	}

	/** The FieldGlass's full round at one point — the five published channels
	 * plus the governing material regime, tier-honest. */
	public record FieldGlassReadout(float rho, float q, float eps2,
			float gradX, float gradY, float gradZ, float waste,
			MaterialRegimeRead.RegimeRead regime, String text) {

		/** The river gradient's magnitude, |∇(g·Φ)|. */
		public float gradMag() {
			return (float) Math.sqrt(gradX * (double) gradX
					+ gradY * (double) gradY + gradZ * (double) gradZ);
		}
	}

	/**
	 * Render the FieldGlass read at a position from ONE published reading.
	 *
	 * @param r the published-channel reading at the block position
	 * @return the full tier-honest chart; a pure function of the reading
	 *         (same reading → same chart, the InstrumentDeterminismMain hard gate)
	 */
	public static FieldGlassReadout read(Quantizer.FieldReading r) {
		float q = r.q();
		float eps2 = r.eps2();
		float rho = r.rho();
		float waste = 1.0f - q;
		MaterialRegimeRead.RegimeRead regime = MaterialRegimeRead.classify(r);

		String text = "FieldGlass @ " + fmt(rho) + "ρ / " + fmt(q) + "q\n"
				+ "  Lume   " + fmt(q) + " q  \u2014 " + lumeForm(q) + " (attractor " + Q_ATTRACTOR + ")\n"
				+ "  Depth  " + fmt(rho) + " \u03c1  \u2014 " + depthForm(rho, regime) + "\n"
				+ "  Strain " + fmt(eps2) + " \u03b5\u00b2 \u2014 " + strainForm(eps2) + "\n"
				+ "  Waste  " + fmt(waste) + " 1\u2212q \u2014 " + wasteForm(waste) + "\n"
				+ "  Lean   " + leanText(r) + "\n"
				+ regimeForm(regime);
		return new FieldGlassReadout(rho, q, eps2,
				r.gradX(), r.gradY(), r.gradZ(), waste, regime, text);
	}

	/** The q lume form — steady, dim, or the desert's dead-flat grey. */
	private static String lumeForm(float q) {
		if (q >= Q_STEADY) {
			return "steady lume (the field holds the \u03c6-lock; attractor ~" + Q_ATTRACTOR + ")";
		}
		if (q >= Q_COLLAPSE) {
			return "dim lume (low coherence)";
		}
		return "dead flat grey (q collapse \u2014 the desert's signature)";
	}

	/**
	 * The ρ depth form — the local density against the material regime's
	 * condensation threshold {@code θ_c} (how far the field here condenses
	 * into matter, material-regimes §1).
	 */
	private static String depthForm(float rho, MaterialRegimeRead.RegimeRead regime) {
		MaterialRegistry.MaterialTuple m = regime.material();
		if (m.emptyRegime()) {
			return "void (below AIR's field \u2014 the empty regime, GAS)";
		}
		return "condensed toward " + m.name() + " (\u03c1 \u2265 \u03b8_c " + fmtThetaC(m) + " [design])";
	}

	/** The ε² climbing-glow form — a rising read marks a storm's front / a scar. */
	private static String strainForm(float eps2) {
		if (eps2 >= 0.5f) {
			return "climbing glow (decoherence rising \u2014 a storm's front / a scar)";
		}
		if (eps2 >= 0.05f) {
			return "faint climb (mild decoherence)";
		}
		return "quiet (no decoherence climb)";
	}

	/** The (1−q) waste-tint form. */
	private static String wasteForm(float waste) {
		if (waste >= 0.3f) {
			return "wasteful (hot tint \u2014 the field here bleeds energy)";
		}
		if (waste >= 0.1f) {
			return "some waste";
		}
		return "clean (cool tint)";
	}

	/**
	 * The lean — which way the river gradient's downhill points (direction +
	 * magnitude, the body would move under the river law
	 * {@code a = −G_N·(π/ρ)·∇(g·Φ)}, field-instruments §1.2).
	 */
	private static String leanText(Quantizer.FieldReading r) {
		double len = Math.sqrt(r.gradX() * (double) r.gradX()
				+ r.gradY() * (double) r.gradY() + r.gradZ() * (double) r.gradZ());
		if (len < 1e-6) {
			return "none (flat \u2014 the field is level here) |\u2207(g\u00b7\u03a6)| 0.000";
		}
		String x = r.gradX() > 0 ? "+X" : (r.gradX() < 0 ? "\u2212X" : "");
		String y = r.gradY() > 0 ? "+Y" : (r.gradY() < 0 ? "\u2212Y" : "");
		String z = r.gradZ() > 0 ? "+Z" : (r.gradZ() < 0 ? "\u2212Z" : "");
		String dir = (x + (y.isEmpty() ? "" : ", " + y) + (z.isEmpty() ? "" : ", " + z))
				.replaceFirst("^, ", "");
		return "downhill " + (dir.isEmpty() ? "(nil)" : "toward " + dir)
				+ " |\u2207(g\u00b7\u03a6)| " + fmt((float) len);
	}

	/**
	 * The governing material regime — the real-element rung (TIER-REAL) and the
	 * [design] constants, exactly the MaterialRegimeRead.vocabulary re-used
	 * (material-regimes.md §1, §7; §5–6 the rung/regime triples this readout reuses).
	 */
	private static String regimeForm(MaterialRegimeRead.RegimeRead regime) {
		MaterialRegistry.MaterialTuple m = regime.material();
		StringBuilder sb = new StringBuilder();
		sb.append("  Regime ").append(m.name())
				.append(regime.material() == MaterialRegistry.LAVA
						? " (molten " + MaterialRegistry.STONE.name() + ")" : "")
				.append(" \u2014 phase ").append(regime.phase().label()).append("\n");
		sb.append("  Rung ").append(String.format("%.4f", m.n()))
				.append(" = log\u03c6(M\u209a/m), ").append(m.realElement())
				.append(" [TIER-REAL]\n");
		sb.append("  \u03b8_c ").append(fmtThetaC(m))
				.append("  \u03c9\u2080\u00b2 ").append(String.format("%.2f", m.omega2()))
				.append("  \u03b5\u00b2-floor ").append(String.format("%.3f", m.eps2MeltFloor()))
				.append(" [design]\n");
		sb.append("  Nearest special point ").append(String.format("%.1f", m.nearestSpecialPoint()))
				.append(", dist ").append(String.format("%.4f", regime.specialPointDist()));
		return sb.toString();
	}

	private static String fmtThetaC(MaterialRegistry.MaterialTuple m) {
		return String.format("%.2f", m.thetaC());
	}

	private static String fmt(float v) {
		return String.format("%.3f", v);
	}
}
