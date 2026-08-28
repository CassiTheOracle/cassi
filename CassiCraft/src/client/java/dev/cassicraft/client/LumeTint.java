package dev.cassicraft.client;

import dev.cassicraft.game.reader.FieldReader;
import dev.cassicraft.game.sampler.Quantizer;

/**
 * The Weatherglass lume colour mapping (field-instruments.md §1.2, §1.4) — a
 * deterministic, monotonic, [design] presentation of the <b>published</b>
 * channels, reusing {@link FieldReader}'s band constants so the lume and the
 * readout always agree (no drift between presentations). Returns an ARGB tint
 * over the {@code weatherglass_lume} overlay layer:
 *
 * <ul>
 *   <li><b>q lume</b> — brightness rises monotonically with q between
 *       {@code Q_COLLAPSE} and {@code Q_STEADY}; at/below the collapse floor it
 *       is <em>dead flat grey</em> (the desert's signature — a real, desaturated
 *       reading, distinct from the dark no-reading state).</li>
 *   <li><b>ε² climbing glow</b> — brightness and red-shift added monotonically
 *       as ε² rises toward {@code EPS2_FLOOR} (the storm-front / scar tell).</li>
 *   <li><b>(1−q) waste tint</b> — a warm hue shift proportional to the waste
 *       fraction (the energy-harnessing waste-glow idiom).</li>
 *   <li><b>Lean — deferred</b> (no custom rendering, house rule): ∇(g·Φ) is
 *       still read by the right-click readout ({@code /cassicraft read}); the
 *       lume does not fake a static lean texture.</li>
 * </ul>
 *
 * <p>The honesty rule: when {@link LumeState#hasReading()} is {@code false}
 * (the field not publishing) the caller returns full transparency/black — the
 * honest dark Weatherglass.
 */
public final class LumeTint {

	/** [design] Waste-fraction scale for the warm hue shift (mirrors {@link
	 * FieldReader#describeWaste}: ≥ 0.3 is "wasteful"). */
	public static final float WASTE_WARM_SCALE = 0.30f;

	/** [design] Min overlay alpha (fraction of 255) at zero lume brightness. */
	public static final float ALPHA_FLOOR = 0.30f;

	/** [design] Grey-read alpha for the desert's flat-grey state (overlay alpha byte). */
	public static final int GREY_ALPHA = 0xC0;
	/** [design] Grey rgb for the desert's flat-grey state. */
	public static final int GREY_RGB = 0x96;

	private LumeTint() {
	}

	/**
	 * Compute the overlay ARGB tint for the given published reading.
	 *
	 * @param q the published coherence
	 * @param eps2 the derived decoherence
	 * @return the ARGB tint (0x00000000 = fully transparent)
	 */
	public static int tint(float q, float eps2) {
		if (q <= FieldReader.Q_COLLAPSE) {
			// The desert: dead flat grey — a real (desaturated, dim) reading,
			// distinct from the dark no-reading state.
			return (GREY_ALPHA << 24) | (GREY_RGB << 16) | (GREY_RGB << 8) | GREY_RGB;
		}
		float lume = clamp01((q - FieldReader.Q_COLLAPSE) / (FieldReader.Q_STEADY - FieldReader.Q_COLLAPSE));
		float climb = clamp01(eps2 / Quantizer.EPS2_FLOOR);
		float waste = clamp01((1f - q) / WASTE_WARM_SCALE);

		// Brightness: a steady baseline under the q lume, raised by the ε² climb.
		float brightness = clamp01(ALPHA_FLOOR + 0.70f * lume + 0.45f * climb);
		// Warm pale-amber base; ε² red-shifts the climb, waste warms the hue.
		float r = clamp01(1.00f + 0.35f * climb + 0.25f * waste);
		float g = clamp01(0.93f + 0.05f * climb - 0.28f * waste);
		float b = clamp01(0.80f - 0.10f * climb - 0.35f * waste);

		int alpha = Math.round(brightness * 255.0f);
		return (alpha << 24)
				| (Math.round(r * 255.0f) << 16)
				| (Math.round(g * 255.0f) << 8)
				| Math.round(b * 255.0f);
	}

	private static float clamp01(float v) {
		return v < 0f ? 0f : (v > 1f ? 1f : v);
	}
}
