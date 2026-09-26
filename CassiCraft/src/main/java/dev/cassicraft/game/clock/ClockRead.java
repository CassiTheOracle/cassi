package dev.cassicraft.game.clock;

/**
 * Pure presentation mapping for the Clock instrument. The field channels are
 * engine-real; the tempo idiom is [design] and never changes simulation time.
 */
public final class ClockRead {
    public static final float MIN_Q = 0.0f;
    public static final float MAX_Q = 1.0f;
    public static final float FAST_RATE = 1.0f;
    public static final float SLOW_RATE = 0.0f;

    public record Tempo(float q, float waste, float rate, String band, String text) {}

    /** Map q to a bounded proposed tempo rate: 0 = patient/slow, 1 = rushed/fast. */
    public static Tempo read(float q) {
        float bounded = clampFinite(q);
        float waste = 1.0f - bounded;
        float rate = waste;
        String band = rate >= 0.66f ? "rushed / faster" : rate >= 0.33f ? "steady" : "patient / slower";
        String text = "Proposed field tempo [design] — " + band
                + " | q=" + fmt(bounded) + " 1−q=" + fmt(waste)
                + " tempo=" + fmt(rate)
                + " (presentation only; Minecraft and engine time unchanged)";
        return new Tempo(bounded, waste, rate, band, text);
    }

    /** Finite clamp used at the presentation boundary; NaN is the safe patient endpoint. */
    public static float clampFinite(float q) {
        if (Float.isNaN(q)) return MAX_Q;
        if (q == Float.POSITIVE_INFINITY) return MAX_Q;
        if (q == Float.NEGATIVE_INFINITY) return MIN_Q;
        return Math.max(MIN_Q, Math.min(MAX_Q, q));
    }

    private static String fmt(float value) {
        return String.format(java.util.Locale.ROOT, "%.3f", value);
    }

    private ClockRead() {}
}
