package dev.cassicraft.game.energy;

/**
 * MODULE 2/3 — the energy-harnessing practice's named use (energy-harnessing.md
 * §5.1 "power precision tools at deeper rungs" — the mining burst; §6 the
 * no-free-energy cap {@code output ≤ φ⁻¹·input}). A <b>pure, Minecraft-free</b>
 * converter: given the <em>drawn coherence budget</em> — the withdrawal the
 * harness made through the Q4 lane at the draw point, in the field's own
 * {@code q}-units — it computes the bounded mining-burst (a vanilla
 * {@code HASTE} effect) that buy is worth. The burst's <b>magnitude</b>
 * (amplifier, one level per charge unit the draw buys) is strictly bounded by
 * the drawn budget:
 *
 * <pre>
 *   drawnBudget = 0.5 · φ⁻¹ · sqrt(q_local_pre)   // the withdrawal, ≤ the no-mint cap
 *   charge      = drawnBudget · USE_EFFICIENCY    // the (1−q)-like shed — strictly less
 *   units       = floor(charge / BUDGET_UNIT)     // whole charge units the burst buys
 *   amplifier   = min(units − 1, HARNESS_MAX_AMPLIFIER)   // Haste 0..MAX
 * </pre>
 *
 * <p>so the burst's value in budget units, {@code (amplifier + 1)} (haste-0 is
 * one real level), never exceeds the units the charge bought, and the charge is
 * {@code USE_EFFICIENCY < 1} of the drawn budget, which is itself
 * {@code HARNESS_DRAW_FRACTION < 1} of the <em>no-mint cap</em>
 * {@code φ⁻¹·sqrt(q_local_pre)} ({@code energy-harnessing.md} §6 — a draw can
 * only spend what the field's coherence already holds; no minting). The game
 * command applies this as a vanilla {@code MobEffectInstance(HASTE, …)} on the
 * player; the gate verifies the pure plan (this class) is deterministic,
 * monotone in the budget, and <b>output ≤ input</b> — a real spend, never a
 * grant.
 *
 * <p>Honest scope (the Q4 lane's micro-scale, measured): a single cap-honored
 * draw's realized field move is {@code dEY·dt² ≈ 2.5e-7} — the lane's additive
 * {@code ψ + v·dt + source·dt²} form is dt²-scaled, so a bounded withdrawal at
 * the cell is micro-scale (the genesis/combustion slices' honest negatives:
 * the lane does not mint, it micro-steers existing coherence). The budget the
 * harness is <em>entitled</em> to spend is the named, no-mint-capped withdrawal
 * magnitude — the field pays it (q moves down vs control), the burst is that
 * budget's honest output. A burst may only fire when the charge clears
 * {@link #HARNESS_MINIMUM_FIRE}: a genuinely thin field fires nothing.
 */
public final class HarnessUse {

	/**
	 * The (1−q)-like shed — the burst's charge is this fraction of the drawn
	 * budget, so output &lt; input (energy-harnessing §2 the waste law
	 * {@code E_waste = (1−q)·E_throughput}, §6 output ≤ φ⁻¹·input with margin:
	 * the burst never spends the whole draw, part is shed as the honest glow of
	 * the (1−q) floor). [design] probe-set to 0.9 — the burst keeps 90 % of the
	 * drawn coherence, sheds 10 %; the honest margin is the draw's own
	 * {@code HARNESS_DRAW_FRACTION} under the no-mint cap plus this sub-unit.
	 */
	public static final double USE_EFFICIENCY = 0.9;

	/**
	 * One charge unit of the drawn budget — the {@code q} a single haste-0
	 * level-second of the burst is worth. [design] denominated so a whole
	 * cap-honored draw (a named fraction of the no-mint cap ≈ 0.5·φ⁻¹·√q ≈ 0.25
	 * at the settled body's q ≈ 0.64) buys several whole units ({@code 0.9·0.25/
	 * 0.05 ≈ 4}), giving a real graded burst (Haste-1..2) while a genuinely
	 * thin field (near the spent floor) fires nothing. Re-read from
	 * {@link HarnessDeterminismMain}'s printed numbers if the field's scale
	 * changes — never a guessed value.
	 */
	public static final double BUDGET_UNIT = 0.05;

	/**
	 * The burst window — a named cooldown-short HASTE grant of this many server
	 * ticks (the practice cadence's sub-window; 20 ticks = 1 s at 20 Hz). The
	 * burst's magnitude is its amplifier (bounded by the charge); the window is
	 * the fixed cadence so the honesty law bounds one scalar (the amplifier),
	 * not a two-dimensional grant.
	 */
	public static final int HARNESS_DURATION_TICKS = 20;

	/**
	 * The burst's maximum amplifier — the bounded burst caps at Haste-2 (three
	 * real levels, the player-shaped boost); a deeper budget buys the same
	 * window, not an unbounded swing (energy-harnessing §2 the honest machines
	 * are bounded, never a free tap).
	 */
	public static final int HARNESS_MAX_AMPLIFIER = 2;

	/**
	 * The minimum charge a burst may fire from — below this the draw was too
	 * thin to buy even a haste-0 second's level (a genuinely depleted point
	 * fires nothing, never an over-granted boost; the state reads
	 * {@link HarnessRead.State#SPENT}/{@link HarnessRead.State#RESTING} instead).
	 */
	public static final int HARNESS_MINIMUM_FIRE = 1;

	private HarnessUse() {
	}

	/**
	 * The bounded mining-burst a drawn coherence budget buys — pure and
	 * deterministic (same budget → same burst).
	 */
	public record MiningBurst(int amplifier, int durationTicks, double charge) {

		/** The burst's value in whole charge units — (haste-0 counts one level). */
		public int unitsValue() {
			return Math.max(1, amplifier + 1);
		}
	}

	/**
	 * Compute the bounded mining-burst from a drawn coherence budget (the
	 * withdrawal the harness made, in {@code q}-units). Pure, deterministic,
	 * monotone in the budget, and honestly bounded:
	 * <pre>
	 *   (amplifier + 1) · BUDGET_UNIT ≤ charge ≤ USE_EFFICIENCY · drawnBudget
	 *                                     ≤ φ⁻¹ · sqrt(q_local_pre)   (via the lane cap)
	 * </pre>
	 * Returns {@code null} when the charge is too thin to buy a single level
	 * (no burst — the honest "the draw found no spendable coherence").
	 *
	 * @param drawnBudget the withdrawal magnitude in {@code q}-units (already
	 *        the cap-bounded Q4-lane draw)
	 */
	public static MiningBurst plan(double drawnBudget) {
		double charge = drawnBudget * USE_EFFICIENCY;
		int units = (int) Math.floor(charge / BUDGET_UNIT);
		if (units < HARNESS_MINIMUM_FIRE) {
			return null;
		}
		int amplifier = Math.min(units - 1, HARNESS_MAX_AMPLIFIER);
		return new MiningBurst(amplifier, HARNESS_DURATION_TICKS, charge);
	}

	/**
	 * The honesty bound this class enforces — the burst's value in charge units
	 * must never exceed the charge's own unit count (output ≤ input), and the
	 * charge must never exceed the drawn budget (the (1−q)-like shed). A pure
	 * check the gate asserts over a produced {@link MiningBurst}.
	 */
	public static boolean isHonest(MiningBurst burst, double drawnBudget) {
		if (burst == null) {
			return drawnBudget <= 0 || drawnBudget * USE_EFFICIENCY < BUDGET_UNIT;
		}
		double chargeUnits = chargeUnits(drawnBudget);
		return burst.unitsValue() <= chargeUnits
				&& burst.charge() <= drawnBudget
				&& burst.charge() <= drawnBudget * 1.0000001; // the shed is strict, within fp
	}

	/** The whole charge-unit count a drawn budget buys (the honesty denominator). */
	public static double chargeUnits(double drawnBudget) {
		double charge = drawnBudget * USE_EFFICIENCY;
		return Math.max(0.0, charge / BUDGET_UNIT);
	}

}
