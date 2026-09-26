package dev.cassicraft.game.wake;

/**
 * MODULE 2/3 — the wake probe's shared verdict (signature-predator.md §8 — the
 * readable-trail slice's honest question). A <b>pure, Minecraft-free</b> verdict
 * decoder over the wake measurement — shared by {@link WakeProbeMain} (the
 * measurement) and {@link WakeDeterminismMain} (the gate), so the verdict is
 * computed once, in one place, never forced.
 *
 * <p><b>Verdict rules</b> (as the brief's named floors):
 * <ul>
 *   <li><b>SUPPORTS</b> — a measurable wake exists: the peak attributable
 *       {@code ΔS = (q·(1+ε²))_shout − (q·(1+ε²))_control} at/above
 *       {@link WakeProbeMain#WAKE_DELTA_S_FRACTION} (5%) of the body's own S at
 *       the practice point, AND a lifetime &gt; {@link WakeProbeMain#WAKE_LIFETIME_FLOOR}
 *       (1 field-unit) — the wake persists, it does not collapse within a
 *       field-unit.</li>
 *   <li><b>CONTRADICTS</b> — no wake above the body's floor: the peak
 *       attributable {@code ΔS} is below the 5% floor (the coherent body absorbs
 *       the shout's bound write into its own cohesion below the measurement
 *       floor), OR the elevation is a propagating far-field front rather than a
 *       local wake.</li>
 *   <li><b>INCONCLUSIVE</b> — the measurement cannot discriminate (e.g. a wake
 *       peaked above the floor but its lifetime did not reach the bar).</li>
 * </ul>
 *
 * <p>Never mutates — a pure function of the measured numbers. Minecraft-free:
 * compiles against the domain only, so both the probe and gate replay it headlessly.
 */
public final class WakeVerdict {

	/**
	 * The wake-elevation floor fraction — SUPPORTS requires peak attributable
	 * {@code ΔS} at/above this fraction of the body's own S at the practice point
	 * (the brief's named floor, 5%).
	 */
	public static final double DELTA_S_FRACTION = 0.05;

	/**
	 * The wake-lifetime floor (field-units) — SUPPORTS requires the wake to
	 * persist this many field-units (the brief's named bar, 1 field-unit). A wake
	 * that collapses within one field-unit is absorbed, not persistent.
	 */
	public static final double LIFETIME_FLOOR = 1.0;

	/**
	 * The far-field front bar — a box-uniform far-field attributable ΔS at/above
	 * this fraction of the floor reads as a propagating front rather than a
	 * confined wake.
	 */
	public static final double FRONT_FLOOR_FRACTION = 0.5;

	private WakeVerdict() {
	}

	/**
	 * Compute the wake verdict from the measured numbers — a pure function of the
	 * measurement, never forced.
	 *
	 * @param peakDS   the peak attributable ΔS across samples (shout − control)
	 * @param deltaSFloor the 5%-of-body-S ΔS floor ({@code DELTA_S_FRACTION × bodyS})
	 * @param lifetime the wake's lifetime in field-units (last sample still above floor)
	 * @param bodyS    the body's own S at the practice point (the settled control read)
	 * @param farMean  the far-field mean attributable ΔS (box beyond the front radius)
	 * @param farAbs   the far-field mean|ΔS| (box beyond the front radius)
	 */
	public static String size(double peakDS, double deltaSFloor, double lifetime,
			double bodyS, double farMean, double farAbs) {
		boolean peakAbove = peakDS >= deltaSFloor;
		boolean persists = lifetime > LIFETIME_FLOOR;
		boolean frontLike = Math.abs(farMean) >= deltaSFloor * FRONT_FLOOR_FRACTION
				|| Math.abs(farAbs) >= deltaSFloor;
		if (peakAbove && persists && !frontLike) {
			return "SUPPORTS — a measurable, persistent local wake above the body's floor: peak attributable "
					+ "ΔS=" + num(peakDS) + " ≥ " + num(deltaSFloor) + " (5% of body S), lifetime "
					+ num(lifetime) + " ft > " + LIFETIME_FLOOR + " ft, and no box-uniform far-field front — "
					+ "the player's shout leaves a legible wake the signature-predator could hunt";
		}
		if (peakAbove && persists && frontLike) {
			return "CONTRADICTS — the attributable elevation is a propagating FRONT (box-uniform far-field "
					+ "ΔS=" + num(farMean) + "), not a local wake — the shout's perturbation delocalizes at c_s "
					+ "rather than leaving a confined, legible wake";
		}
		if (!peakAbove) {
			return "CONTRADICTS — the coherent condensed body absorbs the shout's bound write below the "
					+ "measurement floor: peak attributable ΔS=" + num(peakDS) + " < " + num(deltaSFloor)
					+ " (5% of the body's own S=" + num(bodyS) + " at the point) at every sample — the body "
					+ "re-locks the dt²-scaled, no-mint-capped injection into its own cohesion (the "
					+ "combustion-body precedent confirmed), so no wake is resolvable above the body's floor "
					+ "and the signature-predator has no elevated-ε² trail to prefer over the static body";
		}
		return "INCONCLUSIVE — a wake peaked above the floor (" + num(peakDS) + " ≥ " + num(deltaSFloor)
				+ ") but its lifetime (" + num(lifetime) + " ft) did not reach the " + LIFETIME_FLOOR
				+ " ft bar — the wake is real but too short-lived to be a persistent trail";
	}

	private static String num(double v) {
		return String.format(java.util.Locale.ROOT, "%.4f", v);
	}
}
