package dev.cassicraft.client;

/**
 * The client-side holder of the freshest Weatherglass lume reading (the client-
 * thread mirror of the published snapshot at the player's position). Written by
 * the {@link CassiCraftClient} payload receiver, read by the lume tint source on
 * the client render thread. It carries exactly the six published channel values
 * of {@link dev.cassicraft.domain.snapshot.FieldSnapshot} — no hidden state,
 * never a new channel (field-instruments §2.1).
 *
 * <p>Thread discipline: the receiver runs on the client's networking thread and
 * the tint reads on the render thread; the volatile float fields are the
 * publication fence, and {@link #hasReading()} gates the dark no-reading state.
 */
public final class LumeState {

	private static final float[] EMPTY = { 0f, 0f, 0f, 0f, 0f, 0f };

	private static volatile boolean hasReading;
	private static final float[] values = new float[6];

	private LumeState() {
	}

	/** Store the freshest reading (rho, q, eps2, gradX, gradY, gradZ). */
	public static void update(float rho, float q, float eps2,
			float gradX, float gradY, float gradZ) {
		values[0] = rho;
		values[1] = q;
		values[2] = eps2;
		values[3] = gradX;
		values[4] = gradY;
		values[5] = gradZ;
		hasReading = true;
	}

	/** True once at least one lume payload has been received (field is publishing). */
	public static boolean hasReading() {
		return hasReading;
	}

	/** The six published values, as a defensive copy. */
	public static float[] values() {
		return hasReading ? values.clone() : EMPTY.clone();
	}
}
