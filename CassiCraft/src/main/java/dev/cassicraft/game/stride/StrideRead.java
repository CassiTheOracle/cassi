package dev.cassicraft.game.stride;

import dev.cassicraft.game.sampler.Quantizer;

/**
 * THE STRIDE — the player's walk reading the field's published river
 * (designs/the-walk.md §2a — "walking a ridge is cheap going downhill along
 * ∇(g·Φ)": the pedestrian's relation to the gradient, designed as a read).
 * The player-analog of the ride's {@code game/ride/RideHaul} (the minecart is
 * carried by the field; the walker <b>reads</b> the same current to make each
 * step cheap with the lean, dear against it — {@code the-walk.md} §3 "where to
 * step", the Weatherglass's fourth form the lean, {@code field-instruments.md}
 * §1.2). A <b>pure, Minecraft-free consumer</b> of the published channels,
 * never a write, never a new movement pass ({@code field-instruments.md} §2.1
 * — a read with a presentation idiom, never a channel).
 *
 * <p>The read's three quantities, each grounded in the measured settled body
 * (seed 42 @ 12 generations, DT=0.001; the percentiles cited in the constant
 * javadocs below are the same measured continuum {@code game/wind/WindRead}
 * cites and the ride's descent measures):
 * <ul>
 *   <li><b>The horizontal river</b> {@code |∇(g·Φ)_xz|} + its direction — the
 *       current at the player's feet, read from the published gradient exactly
 *       as {@code RideHaul} does (the same {@link Quantizer#sampleReading}
 *       seam, never a reimplementation). The current flows <b>downhill</b>,
 *       so the with-the-current direction is the normalized
 *       {@code (−gradX, −gradZ)} — the same direction {@code RideHaul}'s
 *       engine-real haul {@code a = −G_N·(π/ρ)·∇(g·Φ)} accelerates a cart
 *       (coherence-highway.md §2); the walker rides the lean ungated.</li>
 *   <li><b>The local q</b> (coherence) — high-q ground is "easy walking"
 *       (the coherent bulk the terrain reads solid, {@code Quantizer.TAU_C} /
 *       the {@code q} p90 on the settled body); low-q is the thin's dear
 *       crossing (the-walk.md §2b).</li>
 *   <li><b>The stride state</b> — WITH the current / AGAINST / STILL water,
 *       from how the player's walking direction aligns with the current
 *       direction. A standing read (no step) is STILL water regardless — the
 *       stride never nudges a still player (the honest no-free-energy cap,
 *       the-walk.md §4d: a walk that "generates" something is a lie the cap
 *       forbids; the stride reads a relation to the gradient, never mints).</li>
 * </ul>
 *
 * <p><b>The bounded stride law (Deliverable-1's honest core):</b> the stride's
 * aid magnitude is at most a fixed fraction of the current itself —
 * {@code aidMag = min(STRIDE_RIVER_FACTOR·gradH, MAX_DELTA_PER_TICK)} — so the
 * nudge a stride can grant is bounded by the river's own published magnitude
 * times a named factor and a named per-tick clamp. The field does the work; a
 * stride never minting momentum beyond the current's own aid
 * (the-walk.md §4d guard 1: free <em>movement</em> down-gradient, never free
 * <em>energy</em>). Directionality: the aid acts in the current's downhill
 * direction, so a walk <b>with</b> the current gains it (a positive signed
 * aid), a walk <b>against</b> is resisted (negative), and a perpendicular or
 * still walk gains nothing — the river direction determines the sign.
 *
 * <p>Minecraft-free — compiles against the domain + sampler only, so the
 * determinism gate that replays the stride is headless-testable without a
 * server, exactly as {@code game/ride/RideHaul}.
 */
public final class StrideRead {

	/**
	 * [design] The river's "still water" floor — a horizontal current
	 * {@code |∇(g·Φ)_xz|} below this reads STILL WATER (no coherent directional
	 * current to ride or fight). Cited against the measured settled body: the
	 * box's horizontal gradient runs p50=2.236, p80=3.526, p90=4.335, p99=6.880
	 * with a low tail — 3.6% below 0.5 and 13.3% below 1.0 (WindRead's measured
	 * noise-floor continuum, the same gate's own census). The floor at 1.0 reads
	 * that near-flat tail as STILL WATER while the organized ~87% keeps a real
	 * current — an honest non-vacuous boundary, never a free grant.
	 */
	public static final float STILL_WATER_GRAD = 1.0f;

	/**
	 * [design] The "easy walking" q floor — a local coherence at or above this
	 * reads the ground as easy (the walker's thin-dearness of the-walk.md §2b
	 * drops away). Cited against the measured settled body: the box's q runs
	 * p50=0.608, p90=0.893, p95=0.991, p99=1.190 (WindRead's measured
	 * continuum); 0.95 sits at the genuinely coherent walkable ground (≈p90–95),
	 * below which a thin/dear crossing genuinely labors. A labeled statistic of
	 * the published q, never a speed cap.
	 */
	public static final float EASY_Q = 0.95f;

	/**
	 * [design] The stride-river factor — the bounded stride aid is this fraction
	 * of the current's own magnitude ({@code min(STRIDE_RIVER_FACTOR·gradH, …)}),
	 * so a stride's nudge is <b>structurally no-mint</b>: it can never exceed a
	 * fixed fraction of the published river, never a boost beyond the current's
	 * own aid (the-walk.md §4d guard 1). Calibrated against the measured
	 * horizontal current: on the settled walking ground (p50=2.236, p95=5.109)
	 * the aid runs min(0.04·2.236, ·5.109) ≈ 0.09–0.20 m/s — a felt few-percent
	 * of Minecraft's ~4.32 m/s walk speed, legible as "cheap going downhill"
	 * without ever being travel-mint (the-walk.md §4d guard 3).
	 */
	public static final float STRIDE_RIVER_FACTOR = 0.04f;

	/**
	 * [design] The per-tick stride-delta clamp — a single stride application may
	 * change a player's velocity by at most this much, so a stride can never
	 * teleport, never spike on a degenerate gradient, never overpower the walk
	 * (the ride's bound, {@code MinecartRideCoordinator.MAX_DELTA_PER_TICK = 1.0},
	 * kept tighter for a player-analog — the stride is a nudge, not a cart).
	 * Combined with {@link #STRIDE_RIVER_FACTOR} it is the honesty cap the gate
	 * asserts: the max observed |Δv| stays ≤ this AND ≤ gradH·factor (the
	 * no-mint bound of the-walk.md §4d).
	 */
	public static final float MAX_DELTA_PER_TICK = 0.25f;

	/** The stride's relation to the river at the position. */
	public enum StrideState {
		/** Walking with the current — the stride's nudge aids the walk. */
		WITH,
		/** Walking against the current — the stride's nudge resists the walk. */
		AGAINST,
		/** No coherent directional current, or the player is standing (unaffected). */
		STILL_WATER
	}

	/**
	 * A bounded stride read at one position — the horizontal river (magnitude +
	 * direction), the local q, and the stride state with the bounded aid.
	 *
	 * @param rho       the sampled density at the position
	 * @param q         the sampled coherence at the position
	 * @param gradH     |∇(g·Φ)_xz| (the horizontal river magnitude)
	 * @param gradX     the published x-gradient component
	 * @param gradZ     the published z-gradient component
	 * @param currentX  the normalized downhill (with-the-current) x-direction
	 * @param currentZ  the normalized downhill (with-the-current) z-direction
	 * @param state     the stride state (WITH / AGAINST / STILL_WATER)
	 * @param aidMag    the bounded stride aid magnitude {@code min(factor·gradH, clamp)}
	 * @param signedAid the signed aid projected onto the walk direction (positive with, negative against)
	 * @param easyWalk  true when {@code q ≥ EASY_Q} (easy walking ground)
	 * @param text      the human-readable readout
	 */
	public record StrideReading(
			float rho, float q, float gradH,
			float gradX, float gradZ,
			float currentX, float currentZ,
			StrideState state, float aidMag, float signedAid, boolean easyWalk, String text) {
	}

	/**
	 * Read the stride at one position given the player's horizontal step intent.
	 *
	 * @param r       the fused {@link Quantizer.FieldReading} at the player's position
	 * @param stepX   the player's horizontal move intent (x, meters); 0 = standing
	 * @param stepZ   the player's horizontal move intent (z, meters)
	 * @return the stride read (a pure function of the reading + step)
	 */
	public static StrideReading of(Quantizer.FieldReading r, double stepX, double stepZ) {
		float rho = r.rho();
		float q = r.q();
		float gx = r.gradX();
		float gz = r.gradZ();
		double gradH = Math.sqrt(gx * (double) gx + gz * (double) gz);
		double stepH = Math.hypot(stepX, stepZ);

		// The current flows downhill: the with-the-current direction is the
		// normalized −∇(g·Φ)_xz — the same direction RideHaul accelerates along.
		float currentX = 0f, currentZ = 0f;
		float aidMag = 0f;
		float signedAid = 0f;
		StrideState state = StrideState.STILL_WATER;

		if (gradH >= STILL_WATER_GRAD) {
			double inv = 1.0 / gradH;
			currentX = (float) (-gx * inv);
			currentZ = (float) (-gz * inv);
			// The bounded honest aid: at most a fixed fraction of the current
			// itself, clamped — the field does the work, never minted.
			double aid = STRIDE_RIVER_FACTOR * gradH;
			if (aid > MAX_DELTA_PER_TICK) {
				aid = MAX_DELTA_PER_TICK;
			}
			aidMag = (float) aid;
			// The signed aid on the player's walk: positive with the current
			// (the nudge aids the walk), negative against (the nudge resists),
			// zero standing or perpendicular (unaffected).
			if (stepH > 1e-6) {
				signedAid = (float) ((currentX * stepX + currentZ * stepZ) / stepH * aid);
				state = signedAid > 0 ? StrideState.WITH
						: signedAid < 0 ? StrideState.AGAINST : StrideState.STILL_WATER;
			}
			// A standing / perpendicular step stays STILL WATER — never pushes a
			// still player (the no-free-energy cap).
		}

		boolean easyWalk = q >= EASY_Q;
		String text = "Stride @ (" + fmt(stepX) + "," + fmt(stepZ) + ")\n"
				+ "  River |\u2207(g\u00b7\u03a6)_xz| = " + fmt(gradH)
				+ (gradH >= STILL_WATER_GRAD ? " \u2014 a directional current" : " \u2014 STILL water")
				+ "  | Lean: " + leanWord(gx, gz, gradH)
				+ (gradH >= STILL_WATER_GRAD
						? (" \u2014 downstream toward (" + fmt(dirX(gx, gradH)) + "," + fmt(dirZ(gz, gradH)) + ")")
						: "")
				+ "\n"
				+ "  Coherence q = " + fmt(q) + (easyWalk ? " \u2014 easy walking (high-q ground)" : " \u2014 thin ground (a dear crossing)")
				+ "\n"
				+ "  Stride = " + state.name()
				+ (state == StrideState.WITH ? " \u2014 with the current: aid +" + fmt(signedAid) + " (free movement, never a boost)"
						: state == StrideState.AGAINST ? " \u2014 against the current: resist \u2212" + fmt(signedAid) + " (the current labors)"
						: " \u2014 unaffected")
				+ "\n"
				+ "  Bounded aid |\u0394v| \u2264 min(" + fmt(STRIDE_RIVER_FACTOR * gradH) + ", "
				+ fmt(MAX_DELTA_PER_TICK) + ") = " + fmt(aidMag)
				+ " \u2014 at most the river's own aid, clamped (no mint)";
		return new StrideReading(rho, q, (float) gradH, gx, gz,
				currentX, currentZ, state, aidMag, signedAid, easyWalk, text);
	}

	private static String leanWord(float gx, float gz, double gradH) {
		if (gradH < STILL_WATER_GRAD) {
			return "none (flat \u2014 the field is level here)";
		}
		return "the field leans " + (Math.abs(gx) > Math.abs(gz) ? (gx > 0 ? "+X" : "\u2212X") : (gz > 0 ? "+Z" : "\u2212Z"));
	}

	/** The x-component of the downstream (with-the-current) unit direction. */
	private static double dirX(float gx, double gradH) {
		return -gx / gradH;
	}

	/** The z-component of the downstream (with-the-current) unit direction. */
	private static double dirZ(float gz, double gradH) {
		return -gz / gradH;
	}

	private static String fmt(double v) {
		return String.format("%.3f", v);
	}

	private StrideRead() {
	}
}
