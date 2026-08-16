package dev.cassicraft.game.reader;

import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.game.sampler.Quantizer;

/**
 * The Weatherglass readout (field-instruments.md §1.2, corpus-map §4 step 2).
 * A <b>pure, Minecraft-free</b> sampler: given a published {@link FieldSnapshot}
 * and a block position, it takes the corpus's "one extra sample at the player's
 * position" (the same {@link Quantizer#sampleReading} mapping the terrain uses)
 * and renders the four glanceable channels into text.
 *
 * <p>The four channels are the published ones — the instrument reads them, never
 * adds one (field-instruments §2.1: a consumer of the same publish with a
 * presentation idiom, never a new channel):
 * <ul>
 *   <li><b>q</b> (coherence, attractor ≈ 0.947) — the lume: high → steady bright,
 *       mid → dim, collapsed → <em>dead flat grey</em> (the desert's signature).</li>
 *   <li><b>ε²</b> (decoherence) — the climbing glow: a rising read marks a
 *       storm's front / scar / decoherence well.</li>
 *   <li><b>(1−q)</b> (the waste fraction) — the waste tint: how wasteful the
 *       field here is running.</li>
 *   <li><b>∇(g·Φ)</b> (the river gradient) — the lean: which way the field's
 *       downhill points (the body would move under the river law).</li>
 * </ul>
 * The band thresholds below are the instrument's [design] idiom (presentation
 * over the real channel), per field-instruments §1.4. This class never mutates —
 * it is a pure read of the published snapshot.
 */
public final class FieldReader {

	/** The field's healthy coherence attractor (canonical q ≈ 0.947). */
	public static final float Q_ATTRACTOR = 0.947f;
	/** Above this q the lume reads as steady/bright (calm, holding the φ-lock). */
	public static final float Q_STEADY = 0.80f;
	/** Below this q the lume dims; the desert signature (q-collapse) floor. */
	public static final float Q_COLLAPSE = 0.10f;

	/** The rounded, human-readable snapshot of the four channels at one point. */
	public record FieldReadout(float rho, float q, float eps2,
			float gradX, float gradY, float gradZ, String text) {
	}

	/**
	 * Sample the freshest snapshot at a block position and render the four forms.
	 *
	 * @param snap the published snapshot (freshest)
	 * @param windowCenter the domain box center (the snapshot's job window)
	 * @param blockX/Y/Z the block position to sample
	 */
	public static FieldReadout read(FieldSnapshot snap, double[] windowCenter,
			int blockX, int blockY, int blockZ) {
		Quantizer.FieldReading s = Quantizer.sampleReading(snap, windowCenter, blockX, blockY, blockZ);
		float q = s.q();
		float eps2 = s.eps2();
		float waste = 1.0f - q;
		float gx = s.gradX();
		float gy = s.gradY();
		float gz = s.gradZ();

		String qForm = describeQ(q);
		String epsForm = describeEps(eps2);
		String wasteForm = describeWaste(waste);
		String lean = describeLean(gx, gy, gz);

		String text = "Cassi field @ (" + blockX + "," + blockY + "," + blockZ + ")\n"
				+ "  Coherence q  = " + fmt(q) + "  \u2014 " + qForm + "\n"
				+ "  Waste 1\u2212q = " + fmt(waste) + "  \u2014 " + wasteForm + "\n"
				+ "  Decoherence \u03b5\u00b2 = " + fmt(eps2) + "  \u2014 " + epsForm + "\n"
				+ "  Lean: " + lean;
		return new FieldReadout(s.rho(), q, eps2, gx, gy, gz, text);
	}

	/**
	 * Shared single entry point used by both the Weatherglass item and the
	 * {@code /cassicraft read} command: pull the freshest publish and read the
	 * field at a block position.
	 *
	 * @return the readout, or {@code null} if the domain has not published yet.
	 */
	public static FieldReadout readFreshest(SnapshotPublisher pub,
			int blockX, int blockY, int blockZ) {
		FieldSnapshot snap = pub.freshest();
		if (snap == null) {
			return null;
		}
		double[] window = snap.job() != null && !snap.job().isWindowless()
				? snap.job().windowCenter()
				: new double[] { 0, 0, 0 };
		return read(snap, window, blockX, blockY, blockZ);
	}

	/** The q lume form — steady, dim, or the desert's dead-flat grey. */
	private static String describeQ(float q) {
		if (q >= Q_STEADY) {
			return "steady lume (the field holds the \u03c6-lock; attractor ~" + Q_ATTRACTOR + ")";
		}
		if (q >= Q_COLLAPSE) {
			return "dim lume (low coherence)";
		}
		return "dead flat grey (q collapse \u2014 the desert's signature)";
	}

	/** The ε² climbing-glow form. */
	private static String describeEps(float eps2) {
		if (eps2 >= 0.5f) {
			return "climbing glow (decoherence rising \u2014 a storm's front / a scar)";
		}
		if (eps2 >= 0.05f) {
			return "faint climb (mild decoherence)";
		}
		return "quiet (no decoherence climb)";
	}

	/** The (1−q) waste-tint form. */
	private static String describeWaste(float waste) {
		if (waste >= 0.3f) {
			return "wasteful (hot tint \u2014 the field here bleeds energy)";
		}
		if (waste >= 0.1f) {
			return "some waste";
		}
		return "clean (cool tint)";
	}

	/** The lean — the world direction the river gradient's downhill points. */
	private static String describeLean(float gx, float gy, float gz) {
		double len = Math.sqrt(gx * (double) gx + gy * (double) gy + gz * (double) gz);
		if (len < 1e-6) {
			return "none (flat \u2014 the field is level here)";
		}
		String x = gx > 0 ? "+X" : (gx < 0 ? "\u2212X" : "");
		String y = gy > 0 ? "+Y" : (gy < 0 ? "\u2212Y" : "");
		String z = gz > 0 ? "+Z" : (gz < 0 ? "\u2212Z" : "");
		String dir = (x + (y.isEmpty() ? "" : ", " + y) + (z.isEmpty() ? "" : ", " + z))
				.replaceFirst("^, ", "");
		return "downhill " + (dir.isEmpty() ? "(nil)" : "toward " + dir)
				+ " (|grad| " + fmt((float) len) + ")";
	}

	private static String fmt(float v) {
		return String.format("%.3f", v);
	}

	private FieldReader() {
	}
}
