package dev.cassicraft.game.energy;

import com.mojang.brigadier.CommandDispatcher;
import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.thread.CassiFieldThread;
import dev.cassicraft.game.sampler.Quantizer;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.effect.MobEffectInstance;
import net.minecraft.world.effect.MobEffects;

/**
 * The {@code /cassicraft harness [x y z]} command — the energy-harnessing
 * practice's <b>draw</b> through the real Q4 player-return lane
 * ({@code async-field-domain.md} §7 Q4; {@code wiring-requests/q4-write-lane-design.md};
 * energy-harnessing.md §0/§2/§6). The harness is the corpus's first
 * <em>consuming</em> mechanic: it draws a <b>bounded, cap-governed coherence
 * budget from the field</b> — a withdrawal through the lane — and spends it on
 * a real, honest use (a bounded mining burst, {@link HarnessUse}). The lane is
 * the ONLY write path: the command submits a source injection via
 * {@link CassiFieldThread#submitPerturbation} and NEVER touches the solver, the
 * domain, or Minecraft world state. WorldWriter stays the only block mutator.
 *
 * <p><b>The draw, framed in the lane's terms</b> (energy-harnessing §2.5 the
 * deep-rung reaper; §3 the charge/scar asymmetry — discharging is fast and
 * scars, q down):
 * <ul>
 *   <li><b>Matched-φ withdrawal.</b> The draw requests {@code dEY = −a} and
 *       {@code dEI = −a/φ} at the Yin—Yang ratio, so the overdraw component
 *       {@code dEY − φ·dEI = 0} — a pure coherence withdrawal that lowers the
 *       local q (the field gives up stored order) without breaking the lock
 *       and without ever hitting the lane's overdraw clamp. A matched-φ draw
 *       is the corpus's "a draw spends the field's coherence, never its
 *       strain" (the {@code dEY−φ·dEI = ε²-cost} branch is a documented
 *       strain-costed alternative; this matched-φ form is the safe honest
 *       path — q down, clamp 0).</li>
 *   <li><b>No-mint bounded.</b> The requested magnitude is
 *       {@link #HARNESS_DRAW_FRACTION} × the no-mint cap
 *       {@code φ⁻¹·sqrt(q_local_pre)} ({@code energy-harnessing.md} §6), so the
 *       draw never exceeds the local coherence it draws from (a draw cannot
 *       spend more than the field holds) and the lane's clampCount stays 0.</li>
 *   <li><b>Rate-limited.</b> The lane drains at most one perturbation per job
 *       (newest-wins) — the natural throttle; the command additionally enforces
 *       a named {@link #COOLDOWN_TICKS} so a player cannot fire a draw on every
 *       tick, and the pre-draw {@link HarnessRead.State} gate refuses a draw
 *       from an exhausted (SPENT) or cadence-waiting (RESTING) point.</li>
 *   <li><b>The use.</b> The drawn budget buys a bounded mining burst
 *       ({@link HarnessUse#plan} — a vanilla {@code HASTE} effect applied to the
 *       player), whose magnitude is strictly ≤ the draw (output ≤ input, the
 *       no-mint cap chained). The field pays: q at the draw point is measured
 *       down after the write. The burst fires in-game via
 *       {@code player.addEffect(new MobEffectInstance(MobEffects.HASTE, duration, amplifier))}
 *       — vanilla mechanics only, never a block write, never free energy.</li>
 * </ul>
 *
 * <p><b>Read-before/write/read-after.</b> The command reads the harness state
 * before the draw ({@link HarnessRead#classify}), computes the bounded
 * cap-governed draw from the measured pre-draw coherence, submits it through
 * {@link dev.cassicraft.CassiCraft#FIELD_THREAD}, awaits the drain (a publish
 * generation advance), reads the post-draw state, computes the honest burst,
 * applies it (and presents the draw particles), and reports pre → post plus the
 * worker's clamp telemetry. Blocking (≤ a few hundred ms) as it waits for the
 * fresh publish the drain lands, exactly as {@code /cassicraft still} does.
 *
 * <p>The command class compiles standalone against the game runtime (no edit to
 * {@code CassiCraft.java} is needed to build it); the caller wires the
 * registration + the {@code CassiCraft.FIELD_THREAD} static into the host.
 */
public final class HarnessCommand {

	/**
	 * The draw's requested magnitude as a fraction of the no-mint cap — the
	 * harness requests {@code HARNESS_DRAW_FRACTION × φ⁻¹ × sqrt(q_local_pre)}
	 * per channel, so the withdrawal is well inside the cap ({@code 0.5 < 1}):
	 * an honest draw <b>must not</b> clamp (the gate asserts clampCount 0). The
	 * corpus's "you cannot draw more than φ⁻¹×√q_local" — the draw spends a
	 * bounded, cap-governed budget, never all of it.
	 */
	public static final double HARNESS_DRAW_FRACTION = 0.5;

	/**
	 * The draw's matched-φ write ratio — {@code dEY = φ·dEI} so the overdraw
	 * component {@code dEY − φ·dEI = 0} (a coherence withdrawal at the Yin—Yang
	 * ratio, q4-write-lane-design §3; coherence-magic §4.3 — a perfect φ-lock
	 * has no overdraw to clamp).
	 */
	public static final double DRAW_RATIO = dev.cassicraft.domain.engine.TwoFluidSolver.PHI;

	/** The draw's Gaussian falloff radius (cells) — a tight locality, the body
	 * surrendering one spot's coherence (the stilling's own radius scale). */
	public static final int DRAW_RADIUS = 2;

	/**
	 * The practice's cooldown — at least this many server ticks between harness
	 * draws (a player cannot fire a draw every tick; the lane's newest-wins is
	 * the hard throttle, this is the playable cadence, energy-harnessing §3 the
	 * charge/scar asymmetry — discharging is fast, so the practice is the
	 * cadence, and the field must recover between draws). 40 ticks = 2 s.
	 */
	public static final int COOLDOWN_TICKS = 40;

	/** The drain-await timeout — the lane is CPU-bound, a job (64 steps + 5 ms) lands inside a few seconds. */
	public static final long DRAIN_TIMEOUT_MS = 10_000;

	/** The last draw tick per command invocation, or -1 before any draw (0 if no server tick yet). */
	private static int lastHarnessTick = -1;

	private HarnessCommand() {
	}

	/** Register {@code /cassicraft harness [x y z]}. */
	public static void register(CommandDispatcher<CommandSourceStack> dispatcher) {
		dispatcher.register(Commands.literal("cassicraft")
				.then(Commands.literal("harness")
						.executes(ctx -> draw(ctx.getSource(), null))
						.then(Commands.argument("x", com.mojang.brigadier.arguments.IntegerArgumentType.integer())
								.then(Commands.argument("y", com.mojang.brigadier.arguments.IntegerArgumentType.integer())
										.then(Commands.argument("z", com.mojang.brigadier.arguments.IntegerArgumentType.integer())
												.executes(ctx -> draw(ctx.getSource(), new int[] {
														com.mojang.brigadier.arguments.IntegerArgumentType.getInteger(ctx, "x"),
														com.mojang.brigadier.arguments.IntegerArgumentType.getInteger(ctx, "y"),
														com.mojang.brigadier.arguments.IntegerArgumentType.getInteger(ctx, "z"),
												})))))));
	}

	/**
	 * Run one bounded, cap-governed coherence draw through the real Q4 lane at a
	 * position, and spend the drawn budget on a bounded mining burst (the named
	 * use).
	 *
	 * @param xyz explicit block coords, or {@code null} for the caller's position
	 *        (console → the world spawn)
	 */
	public static int draw(CommandSourceStack source, int[] xyz) {
		if (dev.cassicraft.CassiCraft.WEATHERGLASS == null) {
			source.sendFailure(Component.literal("The harness is not armed (no world loaded)."));
			return 0;
		}
		CassiFieldThread worker = dev.cassicraft.CassiCraft.FIELD_THREAD;
		if (worker == null || !worker.isRunning()) {
			source.sendFailure(Component.literal("The field thread is not running — no write lane to draw through."));
			return 0;
		}
		BlockPos pos = xyz != null
				? new BlockPos(xyz[0], xyz[1], xyz[2])
				: fallbackPos(source);
		// The practice's cadence: at most one draw per cooldown window.
		int tick = source.getServer().getTickCount();
		if (lastHarnessTick >= 0 && tick - lastHarnessTick < COOLDOWN_TICKS) {
			int wait = COOLDOWN_TICKS - (tick - lastHarnessTick);
			source.sendFailure(Component.literal("The field needs a moment to recover before the next draw — wait "
					+ wait + " ticks (the harness cadence; at most one draw per cooldown)."));
			return 0;
		}

		dev.cassicraft.domain.snapshot.SnapshotPublisher pub =
				dev.cassicraft.CassiCraft.WEATHERGLASS.publisherSupplier().get();
		FieldSnapshot pre = pub.freshest();
		if (pre == null || pre.job() == null) {
			source.sendFailure(Component.literal("The field is not yet publishing \u2014 nothing to draw from."));
			return 0;
		}
		double[] center = !pre.job().isWindowless()
				? pre.job().windowCenter()
				: new double[] { 0, 0, 0 };
		Quantizer.FieldReading preR = Quantizer.sampleReading(pre, center,
				pos.getX(), pos.getY(), pos.getZ());
		HarnessRead.Read preState = HarnessRead.classify(preR);

		// The pre-draw gate: only a READY point holds spendable coherence. A
		// SPENT point has already paid (q ≤ spent ceiling); a RESTING point is
		// between the cadence or the strain band — the harness refuses rather
		// than over-drain the same spot.
		if (!preState.isReady()) {
			source.sendFailure(Component.literal(
					"The harness reads " + preState.state().label()
					+ " @ (" + pos.getX() + "," + pos.getY() + "," + pos.getZ() + ") "
					+ "(q " + fmt(preR.q()) + ", ε² " + fmt(preR.eps2()) + ") — no spendable coherence to draw here now."));
			return 0;
		}

		// The bounded, cap-governed draw: the withdrawal magnitude is a named
		// fraction of the no-mint cap φ⁻¹·sqrt(q_local), at the matched-φ ratio,
		// so the overdraw component dEY − φ·dEI = 0 and the request sits well
		// inside the no-mint cap (an honest draw never clamps).
		double noMintCap = dev.cassicraft.domain.thread.CassiFieldThread.PERTURB_NO_MINT_PHI_INV
				* Math.sqrt(Math.max(preR.q(), 0.0));
		double drawnBudget = noMintCap * HARNESS_DRAW_FRACTION;
		double dEY = -drawnBudget;
		double dEI = -drawnBudget / DRAW_RATIO;

		// The write: a bounded matched-φ withdrawal through the REAL lane. The
		// lane clamps (no-mint + overdraw) if the request ever exceeds them; the
		// matched-φ draw requests well within, so clampCount is expected 0 — an
		// unexpected clamp is a design bug, never a silenced counter.
		worker.submitPerturbation(pos.getX(), pos.getY(), pos.getZ(), dEY, dEI, DRAW_RADIUS);

		// Await the drain (a publish generation advance — the field's own response
		// IS the next publish; the lane is input, never output).
		int startGen = pub.generation();
		FieldSnapshot post = null;
		try {
			long deadline = System.currentTimeMillis() + DRAIN_TIMEOUT_MS;
			while (System.currentTimeMillis() < deadline) {
				FieldSnapshot s = pub.freshest();
				if (s != null && s.generation() > startGen) {
					post = s;
					break;
				}
				Thread.sleep(5);
			}
		} catch (InterruptedException e) {
			Thread.currentThread().interrupt();
			source.sendFailure(Component.literal("Harness interrupted while awaiting the field's draw drain."));
			return 0;
		}
		if (post == null || post.job() == null) {
			source.sendFailure(Component.literal("The field did not drain the draw within the bound — the withdrawal was submitted but its response is unseen."));
			return 0;
		}
		double[] postCenter = !post.job().isWindowless() ? post.job().windowCenter() : center;
		Quantizer.FieldReading postR = Quantizer.sampleReading(post, postCenter,
				pos.getX(), pos.getY(), pos.getZ());
		HarnessRead.Read postState = HarnessRead.classify(postR);
		long clamps = worker.perturbationClampCount();

		// The use: the drawn budget buys a bounded mining burst (pure, honest —
		// output ≤ input). Apply it to the player (vanilla HASTE), and present
		// the draw's bounded particles at the point.
		HarnessUse.MiningBurst burst = HarnessUse.plan(drawnBudget);
		ServerPlayer player = source.getPlayer();
		if (burst != null && player != null) {
			player.addEffect(new MobEffectInstance(MobEffects.HASTE,
					burst.durationTicks(), burst.amplifier()));
		}
		ServerLevel world = source.getLevel();
		if (world != null) {
			HarnessPresenter.presentDraw(world, pos, burst);
		}

		lastHarnessTick = tick;
		source.sendSuccess(() -> Component.literal(
				"HARNESS @ (" + pos.getX() + "," + pos.getY() + "," + pos.getZ() + ")\n"
				+ text(pos, preState, postState, preR, postR, drawnBudget, burst, clamps)),
				false);
		return 1;
	}

	/** The live harness readout text (deterministic pure function of the read + draw meta). */
	private static String text(BlockPos pos, HarnessRead.Read pre, HarnessRead.Read post,
			Quantizer.FieldReading preR, Quantizer.FieldReading postR,
			double drawnBudget, HarnessUse.MiningBurst burst, long clamps) {
		String use = burst == null
				? "no burst (the draw was too thin to buy a mining level — the field spent, honestly)"
				: "HASTE " + burst.amplifier() + " for " + burst.durationTicks() + " ticks"
						+ " (charge " + fmt((float) burst.charge()) + " ≤ drawn " + fmt((float) drawnBudget) + ")";
		return "  pre  " + pre.state().label() + " (q " + fmt(preR.q()) + ", ε² " + fmt(preR.eps2()) + ")\n"
				+ "  post " + post.state().label() + " (q " + fmt(postR.q()) + ", ε² " + fmt(postR.eps2()) + ")\n"
				+ "  regime " + pre.regime().material().name() + " (rung "
				+ String.format("%.3f", pre.regime().material().n()) + ")\n"
				+ "  bounded matched-φ draw dEY=" + fmt((float) drawnBudget)
				+ " dEI=" + fmt((float) (drawnBudget / DRAW_RATIO))
				+ " radius=" + DRAW_RADIUS + " cells (≤ φ⁻¹·√q = "
				+ fmt((float) (drawnBudget / HARNESS_DRAW_FRACTION)) + ") | lane clampCount=" + clamps
				+ " (expected 0 for the honest draw)\n"
				+ "  use: " + use;
	}

	/** Caller (player) position or the world spawn for console/headless use. */
	private static BlockPos fallbackPos(CommandSourceStack source) {
		ServerPlayer player = source.getPlayer();
		if (player != null) {
			return player.blockPosition();
		}
		ServerLevel overworld = source.getServer().overworld();
		return overworld != null && overworld.getRespawnData() != null && overworld.getRespawnData().pos() != null
				? overworld.getRespawnData().pos()
				: BlockPos.ZERO;
	}

	private static String fmt(float v) {
		return String.format("%.3f", v);
	}
}
