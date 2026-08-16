package dev.cassicraft.game.walk;

import dev.cassicraft.game.sampler.Quantizer;

/**
 * The stride-cost read — the movement term of the corpus's Phase-1 movement
 * step (corpus-map.md §4 step 4): {@code the-walk + the-carry + the-climb}
 * slices, "movement is a costed read of q/ε²/∇(g·Φ}". A <b>pure, Minecraft-free,
 * read-only consumer</b> that, given a {@link Quantizer.FieldReading} at a
 * mover's position (the sample-at-position pattern, field-instruments §1.4),
 * computes the stride's drag from the published channels.
 *
 * <p>The three honest reads (the-walk.md §2), all derived over the published
 * channels — never a new channel, never a write:
 * <ul>
 *   <li><b>The gradient at foot-pace (§2a)</b> — moving downhill along {@code ∇(g·Φ)}
 *       is cheap (free <em>movement</em>, the field doing work it always does);
 *       moving against it labors. A descent-easement discounts the stride toward
 *       zero drag but never below it — foot-pace is foot-pace (no travel-mint,
 *       §4d).</li>
 *   <li><b>The thin's cost (§2b)</b> — crossing thin ground (low q, high
 *       {@code (1−q)}) spends more waste per stride; high {@code ε²} drags. A
 *       patience cost, never a speed-capped bar.</li>
 *   <li><b>The load / vertical twins (the-carry §2, the-climb §2)</b> — a carried
 *       load (<code>load ∈ [0,1]</code>, the pack's field-read weight) slows the
 *       footing ("a heavy carry slows the walk's footing", the-carry §3); the
 *       climb adds a vertical term dear against the upward ∇(g·Φ) (a climb taxes
 *       more with a pack, the-climb §3).</li>
 * </ul>
 * <b>Determinism is a hard gate</b> (the-walk §4c): the cost is a pure function of
 * the published channels — same ground, same field state → same stride's cost.
 * The <em>weights</em> are [design], probe-calibrated (the-walk §4a); the axes
 * read real quantities.
 */
public final class MovementCost {

	/** Weight on the (1−q) waste in the base drag [design]. */
	public static final float WASTE_W = 1.0f;
	/** Weight on the ε² decoherence in the base drag [design]. */
	public static final float EPS2_W = 0.35f;
	/** Discount on the base drag for a stride aligned with ∇(g·Φ) downhill [design]. */
	public static final float DESCENT_EASEMENT = 3.0f;
	/** Vertical (climb) weight on the upward y-gradient [design]. */
	public static final float CLIMB_W = 0.8f;
	/** Carry-load multiplier on the dearness terms ("a heavy carry slows the footing") [design]. */
	public static final float LOAD_W = 0.6f;

	/** The stride's drag in [0,1] (0 = no drag at foot-pace) + the readout. */
	public record StrideCost(
			float drag, float wasteTerm, float eps2Term, float descentEasement,
			float verticalPenalty, float loadMult, String text) {
	}

	/**
	 * Compute the stride cost at a block position's reading.
	 *
	 * @param r the fused sample at the mover's position
	 * @param stepX/Y/Z the intended movement direction (meters; vertical Y up).
	 *        A zero vector reads the "standing" cost (no direction to cheapen).
	 * @param load the carried load in [0,1] (0 = unloaded; the pack's field-read weight)
	 */
	public static StrideCost strideCost(Quantizer.FieldReading r,
			double stepX, double stepY, double stepZ, float load) {
		float wasteTerm = (1.0f - r.q()) * WASTE_W;          // thin's dearness
		float eps2Term = r.eps2() * EPS2_W;                  // decoherence drag
		float base = Math.max(0.0f, wasteTerm + eps2Term);   // the round stride cost
		float loadMult = 1.0f + LOAD_W * clamp01(load);      // a laden walk is dearer

		// Descent easement: a step aligned with the horizontal ∇(g·Φ) (downhill) is
		// cheap — the field does the work. Misdirection/against costs the full drag.
		float gradH = (float) Math.sqrt(r.gradX() * (double) r.gradX() + r.gradZ() * (double) r.gradZ());
		float horizontalSpeed = (float) Math.hypot(stepX, stepZ);
		float descentEasement = 0.0f;
		if (horizontalSpeed > 1e-6f && gradH > 1e-6f) {
			// Downhill is (−gradX, −gradZ) normalized; how aligned is the step?
			float cos = (float) ((stepX * -r.gradX() + stepZ * -r.gradZ())
					/ (horizontalSpeed * (gradH + 1e-9f)));
			descentEasement = DESCENT_EASEMENT * gradH * Math.max(0.0f, cos);
		}

		// Vertical (climb): ascending against the upward gradient adds drag;
		// ascending along it (up a natural re-lock) is discounted the same way.
		float verticalPenalty = 0.0f;
		if (stepY > 1e-6f && r.gradY() > 1e-6f) {
			// Climbing against the upward pull: the more the field pulls the body
			// back down, the dearer the handhold (the-climb: dear against the grain).
			verticalPenalty = CLIMB_W * r.gradY();
		}

		// Cost: base dearness (weighted by load) reduced by the descent easement,
		// plus the vertical climb tax; clamped to a true drag in [0,1] — never a boost.
		float drag = clamp01(base * loadMult - descentEasement + verticalPenalty);

		String text = "Stride @ (" + fmt(stepX) + "," + fmt(stepY) + "," + fmt(stepZ) + ")\n"
				+ "  Drag = " + fmt(drag) + " (0 = cheap at foot-pace)\n"
				+ "  Thin (1\u2212q) term = " + fmt(wasteTerm)
				+ " | \u03b5\u00b2 term = " + fmt(eps2Term) + "\n"
				+ "  Descent easement = " + fmt(descentEasement)
				+ " | Vertical (climb) = " + fmt(verticalPenalty) + "\n"
				+ "  Carry load mult = " + fmt(loadMult)
				+ (descentEasement > 0.02f ? " (cheap going downhill along \u2207(g\u00b7\u03a6))" : "")
				+ (verticalPenalty > 0.02f ? " (a climb taxes)" : "");
		return new StrideCost(drag, wasteTerm, eps2Term, descentEasement,
				verticalPenalty, loadMult, text);
	}

	private static float clamp01(float v) {
		return v < 0 ? 0 : (v > 1 ? 1 : v);
	}

	private static String fmt(double v) {
		return String.format("%.3f", v);
	}

	private MovementCost() {
	}
}
