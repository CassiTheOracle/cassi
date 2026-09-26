package dev.cassicraft.game.rain;

import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.game.sampler.Quantizer;

/**
 * MODULE 2/3 — the weather readout (the-rain §4, §7e accessibility): the verbal
 * form of {@link RainRead}'s classification, mirroring {@code FieldReader}'s
 * read path (field-instruments §1.4's "one extra sample at the player's
 * position"). A <b>pure, Minecraft-free</b> consumer: given a published
 * {@link FieldSnapshot} and a block position it samples the reading via the
 * {@link Quantizer#sampleReading} seam, classifies the weather, and renders the
 * survival read into text — the same channels the Weatherglass and the reader
 * show, never hidden-only (the-rain §7e).
 *
 * <p>The {@code /cassicraft weather} command's executor is a thin wrapper over
 * {@link #readFreshest} (a Component with this text) — the exact pattern of the
 * {@code /cassicraft read} command over {@code FieldReader#readFreshest}. The
 * readout prints the verdict, the measured q and ε², the wetness factor (the
 * nourishing-but-wet cost, the-rain §3.1), and — during a fall — the
 * flood-beginning margin ({@code surfeit − q}, the q-units the corpus reads,
 * the-rain §4).
 */
public final class WeatherReadout {

	/** The one-line verdict + its measured channels + the wet cost + the flood margin. */
	public record Readout(String text) {
	}

	private WeatherReadout() {
	}

	/**
	 * Sample the freshest snapshot at a block position and render the weather
	 * readout text.
	 *
	 * @return the readout text, or {@code null} if the domain has not published yet.
	 */
	public static String readFreshest(SnapshotPublisher pub,
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

	/** Read the weather at a block position off an already-held snapshot. */
	public static String read(FieldSnapshot snap, double[] windowCenter,
			int blockX, int blockY, int blockZ) {
		Quantizer.FieldReading r = Quantizer.sampleReading(snap, windowCenter, blockX, blockY, blockZ);
		return read(r, blockX, blockY, blockZ);
	}

	/** Read the weather at a position from a bare published reading (the pure
	 * render — headless-testable; the command's live form). */
	public static String read(Quantizer.FieldReading r, int blockX, int blockY, int blockZ) {
		RainRead.WeatherRead w = RainRead.classify(r);
		StringBuilder sb = new StringBuilder();
		sb.append("Cassi weather @ (").append(blockX).append(',').append(blockY)
				.append(',').append(blockZ).append(")\n");
		sb.append("  Verdict   ").append(w.kind().label()).append('\n');
		sb.append("  q         ").append(fmt(w.q())).append('\n');
		sb.append("  1\u2212q       ").append(fmt(1.0f - w.q())).append('\n');
		sb.append("  \u03b5\u00b2         ").append(fmt(w.eps2())).append('\n');
		sb.append("  Wetness   ").append(fmt(w.wetness()))
				.append(" \u2014 the nourishing-but-wet cost (life-signal legibility dims by this)")
				.append('\n');
		if (w.isFalling()) {
			sb.append("  Flood edge  ").append(fmt(w.floodDistance()))
					.append(" below surfeit \u2014 the flood's beginning, readable before it arrives")
					.append('\n');
		}
		return sb.toString();
	}

	private static String fmt(float v) {
		return String.format("%.3f", v);
	}
}
