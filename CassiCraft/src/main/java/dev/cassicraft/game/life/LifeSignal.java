package dev.cassicraft.game.life;

import dev.cassicraft.game.sampler.Quantizer;

import java.util.List;

/**
 * The Life-Signal — a derived vitality classifier over the published channels
 * (life-signal.md §3/§6; corpus-map.md §4 step 3). A <b>pure, Minecraft-free</b>
 * consumer: given a maintenance window (a short time-series of {@link
 * Quantizer.FieldReading}s at one block position, taken at the publish cadence),
 * it derives the maintenance axes and answers <em>"does this anomaly breathe?"</em>
 * with one of the four classes.
 *
 * <p>The discriminating axis is <b>maintenance</b>: a live thing actively holds
 * its φ-lock against a drain; a fossil does not; a deliberate vent raises ε² on
 * purpose; a scar is a fallen floor (life-signal.md §1). No new channel — every
 * axis derives from the published q/ε²/(1−q)/∇(g·Φ) (life-signal.md §2), and the
 * classifier is <em>never a mutator</em> (the instrument rule, field-instruments
 * §2.1; the read-only-consumer discipline, coherence-magic §5.1).
 *
 * <p><b>The honest line.</b> The axes read real quantities; the decision rule —
 * the window length, the pulse threshold, the ε²-gradient sign flip, the class
 * boundaries — is <b>[design]</b>, Phase-1 probe-calibrated (life-signal.md §6a).
 * Determinism is a hard gate (life-signal.md §6d): the classifier is a pure
 * function of the channel series, so same field state → same class.
 */
public final class LifeSignal {

	/** The four vitality classes (life-signal.md §3.1), plus the idle sub-note. */
	public enum LifeClass {
		/** Maintained live coherence — moves/steers, the (1−q) glow pulses. */
		LIVE,
		/** Static residue — dark, q-locked, ε²≈0, no motion, no pulse (a fossil). */
		FOSSIL,
		/** Deliberate vent — clean phase + rising ε² (the Coda's tell). */
		VENT,
		/** Ordinary scar — broad low-q, high-ε² plateau, no core (a fallen floor). */
		SCAR
	}

	/** Number of {@link Quantizer.FieldReading}s over which maintenance is read [design]. */
	public static final int WINDOW_LEN = 6;
	/** (1−q) range over the window above which the region is read as breathing/pulsing [design]. */
	public static final float PULSE = 0.03f;
	/** ε² temporal rise (per window step) at/above which the region is read as a deliberate vent [design]. */
	public static final float EPS2_RISE = 0.02f;
	/** Mean (1−q) at/above which a flat region is read as a broad wasted floor — a scar [design]. */
	public static final float WASTE_SCAR = 0.25f;

	/** The derived maintenance axes + the classification over a window. */
	public record LifeReading(LifeClass cls,
			float wasteMean, float wastePulse, float epsMean, float epsGrad,
			float leanX, float leanY, float leanZ, String text) {
	}

	/**
	 * Classify a maintenance window (time-ordered oldest → newest) of samples at
	 * one block position. Pure, deterministic, a function only of the channel
	 * series — never of wall-clock or hidden state.
	 */
	public static LifeReading classify(List<Quantizer.FieldReading> window) {
		if (window == null || window.size() < 2) {
			throw new IllegalArgumentException("a maintenance window needs at least two published samples");
		}
		int n = Math.min(window.size(), WINDOW_LEN);

		float wasteSum = 0f, epsSum = 0f, wasteMin = Float.MAX_VALUE, wasteMax = -Float.MAX_VALUE;
		float lx = 0f, ly = 0f, lz = 0f;
		for (int i = window.size() - n; i < window.size(); i++) {
			Quantizer.FieldReading s = window.get(i);
			float waste = 1.0f - s.q();
			wasteSum += waste;
			epsSum += s.eps2();
			wasteMin = Math.min(wasteMin, waste);
			wasteMax = Math.max(wasteMax, waste);
			lx += s.gradX();
			ly += s.gradY();
			lz += s.gradZ();
		}
		Quantizer.FieldReading first = window.get(window.size() - n);
		Quantizer.FieldReading last = window.get(window.size() - 1);
		float wasteMean = wasteSum / n;
		float epsMean = epsSum / n;
		float wastePulse = wasteMax - wasteMin;
		float epsGrad = (last.eps2() - first.eps2()) / Math.max(1, n - 1);
		float leanX = lx / n, leanY = ly / n, leanZ = lz / n;

		LifeClass cls = decide(wasteMean, wastePulse, epsGrad);
		return new LifeReading(cls, wasteMean, wastePulse, epsMean, epsGrad,
				leanX, leanY, leanZ, describe(cls, window));
	}

	/**
	 * The [design] decision rule (life-signal.md §3.1/§6a, order matters): a
	 * deliberate vent <em>climbs</em> (rising ε² — the defining axis); a scar is
	 * a flat wasted plateau with no pulse; a maintained lock <em>breathes</em>
	 * ((1−q) pulse); a fossil is flat and dark. Everything not caught is residue.
	 */
	private static LifeClass decide(float wasteMean, float wastePulse, float epsGrad) {
		// VENT first: a rising ε² gradient is the deliberate-vent axis (§3.3).
		if (epsGrad >= EPS2_RISE) {
			return LifeClass.VENT;
		}
		// SCAR: a flat (non-pulsing), broad wasted floor — no core, no climb.
		if (wasteMean >= WASTE_SCAR && wastePulse < PULSE) {
			return LifeClass.SCAR;
		}
		// LIVE: the (1−q) glow breathes at the maintainer's cadence.
		if (wastePulse >= PULSE) {
			return LifeClass.LIVE;
		}
		// FOSSIL: flat, dark, ε²≈0, no pulse.
		return LifeClass.FOSSIL;
	}

	/**
	 * Blocking window collector (used by {@code /cassicraft life} and the
	 * determinism gate): polls {@code pub.freshest()} until {@code windowLen}
	 * <em>distinct</em> generations have published, sampling each at (x, y, z).
	 * The domain worker publishes on its own thread, so this advances even on a
	 * paused/empty server. Returns the time-ordered window (oldest → newest).
	 *
	 * @throws IllegalStateException if fewer than the requested window filled in
	 *                               {@code timeoutMs}
	 */
	public static java.util.List<Quantizer.FieldReading> collectWindow(
			dev.cassicraft.domain.snapshot.SnapshotPublisher pub,
			double[] windowCenter, int x, int y, int z, int windowLen, long timeoutMs)
			throws InterruptedException {
		java.util.List<Quantizer.FieldReading> window = new java.util.ArrayList<>(windowLen);
		long deadline = System.currentTimeMillis() + timeoutMs;
		int lastGen = -1;
		while (System.currentTimeMillis() < deadline) {
			dev.cassicraft.domain.snapshot.FieldSnapshot snap = pub.freshest();
			if (snap != null && snap.generation() > lastGen) {
				lastGen = snap.generation();
				if (snap.job() != null && !snap.job().isWindowless()) {
					windowCenter = snap.job().windowCenter();
				}
				window.add(Quantizer.sampleReading(snap, windowCenter, x, y, z));
				if (window.size() >= windowLen) {
					return window;
				}
			}
			Thread.sleep(30);
		}
		throw new IllegalStateException("field never published a full window (" + window.size() + "/" + windowLen + ")");
	}

	/** The "does it breathe?" presentation (life-signal.md §4.1) over real channels. */
	private static String describe(LifeClass cls, List<Quantizer.FieldReading> window) {
		Quantizer.FieldReading s = window.get(window.size() - 1);
		return "Life read @ maintenance window:\n"
				+ "  Class: " + cls + " — " + classPhrase(cls) + "\n"
				+ "  Waste (1\u2212q) mean = " + fmt(wasteMeanOf(window)) + ", pulse = " + fmt(1 - s.q()) + "\n"
				+ "  Motion: " + (isMoving(window) ? "moving" : "still") + "\n"
				+ "  \u03b5\u00b2 gradient: " + sign(epsGradOf(window)) + "\n"
				+ "  Lean \u2207(g\u00b7\u03a6): " + leanPhrase(window);
	}

	private static boolean isMoving(List<Quantizer.FieldReading> window) {
		// The field at a live-maintained point is not static across the window:
		// its read changes; a fossil's is flat. Proxy motion by channel change.
		Quantizer.FieldReading a = window.get(0), b = window.get(window.size() - 1);
		return Math.abs(b.q() - a.q()) > 1e-4f || Math.abs(b.eps2() - a.eps2()) > 1e-4f;
	}

	private static String classPhrase(LifeClass cls) {
		return switch (cls) {
		case LIVE -> "maintained live coherence — it breathes (the (1\u2212q) glow pulses)";
		case FOSSIL -> "static residue — dark, q-locked, \u03b5\u00b2\u22480, no pulse (a fossil)";
		case VENT -> "deliberate vent — clean phase + RISING \u03b5\u00b2 (the Coda's tell)";
		case SCAR -> "ordinary scar — broad low-q, high-\u03b5\u00b2 plateau, no core (a fallen floor)";
		};
	}

	private static String sign(float v) {
		return v > 1e-4f ? "rising" : (v < -1e-4f ? "falling" : "flat");
	}

	private static String leanPhrase(List<Quantizer.FieldReading> window) {
		float x = 0, y = 0, z = 0;
		for (Quantizer.FieldReading s : window) {
			x += s.gradX();
			y += s.gradY();
			z += s.gradZ();
		}
		float len = (float) Math.sqrt(x * (double) x + y * (double) y + z * (double) z);
		if (len < 1e-6f) {
			return "none (flat)";
		}
		String dir = (x > 0 ? "+X" : x < 0 ? "\u2212X" : "")
				+ (y > 0 ? ", +Y" : y < 0 ? ", \u2212Y" : "")
				+ (z > 0 ? ", +Z" : z < 0 ? ", \u2212Z" : "");
		return dir.replaceFirst("^, ", "") + " (|grad| " + fmt(len) + ")";
	}

	private static float epsGradOf(List<Quantizer.FieldReading> window) {
		return (window.get(window.size() - 1).eps2() - window.get(0).eps2())
				/ Math.max(1, window.size() - 1);
	}

	private static float wasteMeanOf(List<Quantizer.FieldReading> window) {
		float sum = 0;
		for (Quantizer.FieldReading s : window) {
			sum += 1.0f - s.q();
		}
		return sum / window.size();
	}

	private static String fmt(float v) {
		return String.format("%.3f", v);
	}

	private LifeSignal() {
	}
}
