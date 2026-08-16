package dev.cassicraft.game.wind;

import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.game.sampler.Quantizer;

/**
 * THE WIND — the directional weather, the weather stack's flow-face
 * (designs/the-wind.md §1, §7). A moving current of coherence/ε² through the
 * air — the one form that is not a region or a front but a directional current
 * moving through.
 *
 * <p><b>Flow-face resolution (the honest seam).</b> The corpus names the
 * published medium velocity {@code FieldVel} ({@code vel[id] =
 * vec4(∂EY/∂t, ∂EI/∂t, 0, ε²)}, atmosphere-orbits-auroras.md §1.3) as the
 * wind's channel — but the CassiCraft port's publish does <b>not</b> carry
 * {@code FieldVel} (the immutable {@link FieldSnapshot} is exactly q, pot,
 * grad (∇(g·Φ)), rho, generation, job). Adding {@code FieldVel} is a
 * publish-shape change — a domain seam decision owned by the director, not a
 * consumer slice. So this Phase-1 wind is read from the published <b>gradient
 * channel</b> — the horizontal {@code ∇(g·Φ)} at the position — which the
 * corpus itself names as the wind's own weather: "a tailwind cheapens that
 * descent — the wind at your back is the gradient's own weather"
 * (coherence-highway.md §1/§1.1), and "the current ... is downhill toward
 * matter in ∇(g·Φ)" (the-wind.md §4). <b>The {@code FieldVel} publication is a
 * deferred domain touch</b>, never silently claimed: a future publish-shape
 * change can upgrade this read to the true medium velocity, but today the
 * wind's direction and strength are a [design] over the published ∇(g·Φ) the
 * doc's honest boundary allows. The reader is a bounded consumer of the
 * already-published channels (PHASE-1-ABLE, the-wind.md §7 gate (b)), never a
 * write.
 *
 * <p><b>The carry</b> (the-wind.md §3): the wind transports — a settlement
 * reads the wind to know what the field is carrying toward it
 * (field-hazards.md §5.1 readable-before-it-arrives). This read probes upwind
 * (along −direction, a named distance) and classifies what the current carries
 * toward the position: high ε² upwind → a storm's front; high q upwind →
 * coherence; else clear. Deterministic, the same published channels, never
 * hidden (gate (e)).
 *
 * <p><b>The cost-and-aid</b> (the-wind.md §4): a tailwind cheapens the descent,
 * a headwind taxes the walk — "the gradient's own weather". It is a <b>read</b>:
 * the walk's stride-cost already consumes ∇(g·Φ) live (the-walk.md §2a); the
 * wind never adds a second movement pass. This read reports the aid-or-cost the
 * current implies at the position, derived from the published grad — a real
 * exchange reported, never a mint (no-free-energy cap, the-wind.md §5d / §7
 * gate (d): a wind provides nothing, never a travel-mint).
 *
 * <p><b>Determinism</b> (the-wind.md §7 gate (c), HARD): the wind is a pure
 * deterministic function of the published channels — identical field state →
 * identical wind, never a seeded gust roll.
 *
 * <p>Minecraft-free — reads {@link Quantizer#sampleReading} off the pure
 * published-array sampling seam and derives ε² exactly as {@link Quantizer}
 * does. The band thresholds and the noise floor below are the instrument's
 * [design] presentation over the real channel (probe-calibrated on the
 * measured settled box; the measured percentiles are cited in the constant
 * javadocs).
 */
public final class WindRead {

	/**
	 * [design] Probe distance (whole cells) for the upwind carry read — one
	 * whole 3 m cell along the −direction (CELL_WORLD_WIDTH = 2·EXTENT/N = 3 m,
	 * CassiFieldThread). The doc's "bounded sample band, not a point"
	 * (the-wind.md §2.2) is bounded by one cell at Phase-1: the current's
	 * readable-before-it-arrives read at the position's own upwind neighbor.
	 */
	public static final int CARRY_PROBE_CELLS = 1;

	/**
	 * [design] Horizontal-gradient noise floor — a |∇(g·Φ)_xz| below this reads
	 * CALM (no direction). Probe-calibrated from the measured settled-box
	 * horizontal-gradient distribution (seed 42 @ 12 generations, DT=0.001): the
	 * box's |∇(g·Φ)_xz| runs p50=2.236, p80=3.526, p90=4.335, p99=6.880; the weak
	 * near-flat tail sits at min=0.0008 with 3.6% of the box below 0.5 and 13.3%
	 * below 1.0. The floor at 1.0 reads that low tail (≈13% of the field) as
	 * CALM — a non-vacuous honest near-flat read while the organized majority
	 * (~87%) keeps a directional current. A [design] dial cited against the
	 * measured continuum, never a free grant.
	 */
	public static final float GRAD_H_NOISE_FLOOR = 1.0f;

	/**
	 * [design] Fully-calm threshold — a horizontal current at or above this
	 * reads "strong" (strength → 1.0). Probe-calibrated from the measured |∇h|
	 * p95 ≈ 5.109: the strong currents are the field's deep coherent sweeps (the
	 * top 5%); everything between the noise floor and this is a scaled gradient
	 * of the measured continuum (p50=2.235 → strength ≈ 0.30, p90=4.335 →
	 * strength ≈ 0.81). A [design] dial cited against the measured percentiles,
	 * never a free grant.
	 */
	public static final float GRAD_H_STRONG = 5.1f;

	/**
	 * [design] Upwind ε² floor for "carrying a storm front" — the storm is a
	 * c<sub>s</sub>-traveling ε² front (field-hazards.md §2); when ε² upwind is
	 * at/above this, the current is carrying a storm's leading edge toward the
	 * position (the provenance classifier's sibling, weather-not-storm.md §2).
	 * Probe-calibrated: the settled box's ε² runs p50=0.080, p90=0.200,
	 * p95=0.251, p99=0.370 (mean=0.101); a carry of decoherence reads at ≈p95 of
	 * the field — a genuinely elevated upwind ε², not the coherent bulk.
	 */
	public static final float CARRY_EPS2_FLOOR = 0.25f;

	/**
	 * [design] Upwind q floor for "carrying coherence" — when q upwind is
	 * at/above this, the current is carrying the field's organized coherence
	 * toward the position. Probe-calibrated: the settled box's q runs p50=0.608,
	 * p90=0.893, p95=0.991, p99=1.190 (mean=0.628); q ≥ 1.0 reads a genuinely
	 * organized upwind locality (the deep coherent tail, ≈top 5%), not the
	 * p90 bulk.
	 */
	public static final float CARRY_Q_FLOOR = 1.0f;

	/** Compass word for a horizontal direction given the dominant axis. */
	public enum Direction {
		CALM, N, NE, E, SE, S, SW, W, NW
	}

	/** The wind's named strength band — a deterministic named 0..1 current. */
	public enum Strength {
		/** Below the noise floor — no coherent directional current (honest CALM). */
		CALM,
		/** A weak but real directional current (|∇h| at the noise floor to the light zone). */
		LIGHT,
		/** A moderate current (the field's mid-band of measured |∇h|). */
		MODERATE,
		/** The strong deep-gradient sweeps (the tail of the measured |∇h|). */
		STRONG
	}

	/** The carry classification — what the current is carrying toward the position. */
	public enum Carry {
		/** High ε² upwind — a storm's leading edge is being carried toward the position. */
		STORM_FRONT,
		/** High q upwind — organized coherence is being carried toward the position. */
		COHERENCE,
		/** Neither an elevated upwind ε² nor q — the current carries no weather toward the position. */
		CLEAR
	}

	/** A bounded wind read at one position — the flow-face over the published channels. */
	public record WindReading(
			Direction direction,
			Strength strength,
			float strengthValue,      // the named 0..1 current strength
			float gradH,              // |∇(g·Φ)_xz| at the position (the raw measured current)
			float gradX, float gradZ, // the horizontal gradient components
			Carry carry,
			float carryUpwindEps2,    // ε² at the upwind probe position
			float carryUpwindQ,       // q at the upwind probe position
			float costAid             // the signed aid(+)/tax(−) the current implies, derived from the grad
	) {
		public boolean isCalm() {
			return direction == Direction.CALM;
		}
	}

	private WindRead() {
	}

	/**
	 * Read the wind at a position from the published channels. The carry's
	 * upwind probe samples one whole cell upwind (along −direction) via the
	 * same pure {@link Quantizer#sampleReading} seam — a second bounded sample
	 * off the same immutable snapshot (the "bounded sample band",
	 * field-instruments.md §1.4). Deterministic: a pure function of the
	 * published channels and the block position, no RNG, never a gust roll.
	 *
	 * @param snap         the published snapshot
	 * @param windowCenter the domain box center (snap.job().windowCenter())
	 * @param blockX/Y/Z   the block position to read the wind at
	 */
	public static WindReading read(FieldSnapshot snap, double[] windowCenter,
			int blockX, int blockY, int blockZ) {
		Quantizer.FieldReading r = Quantizer.sampleReading(snap, windowCenter, blockX, blockY, blockZ);
		return classify(r, windowCenter, blockX, blockY, blockZ, snap);
	}

	/**
	 * Classify a full wind reading: direction + strength from the horizontal
	 * published ∇(g·Φ) at the position, the carry from the upwind probe, and the
	 * cost-and-aid from the current's strength. The pure-function heart of the
	 * read (gate (c)), kept separate so the determinism gate can fingerprint it
	 * over a sample grid without re-invoking the sampler work.
	 */
	static WindReading classify(Quantizer.FieldReading r, double[] windowCenter,
			int blockX, int blockY, int blockZ, FieldSnapshot snap) {
		float gx = r.gradX();
		float gz = r.gradZ();
		float gradH = (float) Math.sqrt(gx * (double) gx + gz * (double) gz);

		Direction dir = directionOf(gx, gz, gradH);
		Strength str = strengthOf(gradH);
		float strength = strengthValue(gradH);

		// The carry: probe upwind (opposite the flow — the current flows down
		// the gradient toward the position, so what it carries toward the player
		// comes from −direction). One whole cell upwind.
		float upwindEps2 = 0f;
		float upwindQ = 0f;
		Carry carry = Carry.CLEAR;
		if (dir != Direction.CALM) {
			int px = blockX - (int) Math.round(Math.signum(gx) * CARRY_PROBE_CELLS);
			int pz = blockZ - (int) Math.round(Math.signum(gz) * CARRY_PROBE_CELLS);
			float[] up = probeUpwind(snap, windowCenter, px, blockY, pz);
			upwindEps2 = up[0];
			upwindQ = up[1];
			carry = classifyCarry(upwindEps2, upwindQ);
		}

		// The cost-and-aid: a read of the current the walk's live pass already
		// consumes (the lean, the-walk.md §2a). The current implies a tailwind
		// aid — a step with the current is free movement down-gradient, +strength —
		// and a headwind tax — a step against the current (against the lean)
		// labors, −strength. Reported as the signed aid-or-cost the current
		// implies; never a new live movement pass, never a mint (no-free-energy
		// cap, the-wind.md §5d — a tailwind's cheapness is free movement, the
		// field doing the work it always does, never stored energy).
		float costAid = dir == Direction.CALM ? 0f : strength;

		return new WindReading(dir, str, strength, gradH, gx, gz, carry, upwindEps2, upwindQ, costAid);
	}

	/** A compass word from the dominant horizontal gradient axis. */
	private static Direction directionOf(float gx, float gz, float gradH) {
		if (gradH < GRAD_H_NOISE_FLOOR) {
			return Direction.CALM;
		}
		int bx = gx >= 0 ? 1 : (gx < 0 ? -1 : 0);
		int bz = gz >= 0 ? 1 : (gz < 0 ? -1 : 0);
		// North is −Z in Minecraft block space; East is +X.
		if (bx > 0 && bz == 0) return Direction.E;
		if (bx < 0 && bz == 0) return Direction.W;
		if (bx == 0 && bz > 0) return Direction.S;
		if (bx == 0 && bz < 0) return Direction.N;
		if (bx > 0 && bz < 0) return Direction.NE;
		if (bx > 0 && bz > 0) return Direction.SE;
		if (bx < 0 && bz < 0) return Direction.NW;
		return Direction.SW;
	}

	private static Strength strengthOf(float gradH) {
		if (gradH < GRAD_H_NOISE_FLOOR) return Strength.CALM;
		if (gradH >= GRAD_H_STRONG) return Strength.STRONG;
		if (gradH >= GRAD_H_NOISE_FLOOR + 0.5f * (GRAD_H_STRONG - GRAD_H_NOISE_FLOOR)) {
			return Strength.MODERATE;
		}
		return Strength.LIGHT;
	}

	/**
	 * The named 0..1 current strength — a linear ramp of the measured |∇h|
	 * from the calibrated noise floor (0) to the calibrated strong current (1).
	 */
	private static float strengthValue(float gradH) {
		if (gradH <= GRAD_H_NOISE_FLOOR) return 0f;
		float s = (gradH - GRAD_H_NOISE_FLOOR) / (GRAD_H_STRONG - GRAD_H_NOISE_FLOOR);
		return s > 1f ? 1f : s;
	}

	/** Sample ε² and q at an arbitrary block position via the pure seam (out-of-box → 0). */
	private static float[] probeUpwind(FieldSnapshot snap, double[] windowCenter,
			int x, int y, int z) {
		Quantizer.FieldReading up = Quantizer.sampleReading(snap, windowCenter, x, y, z);
		return new float[] { up.eps2(), up.q() };
	}

	/** The carry classifier — storm front (high ε²) beats coherence (high q), else clear. */
	private static Carry classifyCarry(float upwindEps2, float upwindQ) {
		if (upwindEps2 >= CARRY_EPS2_FLOOR) {
			return Carry.STORM_FRONT;
		}
		if (upwindQ >= CARRY_Q_FLOOR) {
			return Carry.COHERENCE;
		}
		return Carry.CLEAR;
	}
}
