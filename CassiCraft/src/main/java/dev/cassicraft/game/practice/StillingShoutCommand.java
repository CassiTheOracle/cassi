package dev.cassicraft.game.practice;

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

/**
 * The {@code /cassicraft still [x y z]} and {@code /cassicraft shout [x y z]}
 * commands — the stilling/shout practice's <b>write</b> through the real Q4
 * player-return lane ({@code async-field-domain.md} §7 Q4;
 * {@code wiring-requests/q4-write-lane-design.md}; the-stilling.md §2/§5b,
 * the-shout.md §2/§5b). The lane is the ONLY write path: the command submits a
 * bounded source injection via
 * {@link CassiFieldThread#submitPerturbation} and NEVER touches the solver, the
 * domain, or Minecraft world state. WorldWriter stays the only block mutator.
 *
 * <p><b>The two practice verbs, framed in the lane's terms</b>
 * (q4-write-lane-design.md §3):
 * <ul>
 *   <li><b>{@code still}</b> — a coherence-<em>restoring</em> write: it raises
 *       the local q (the field's own return toward rest) at the Yin—Yang ratio
 *       {@code dEY = φ·dEI}, so the overdraw component {@code dEY − φ·dEI = 0}
 *       and the write only steers the locale back to the φ-attractor — a
 *       maintenance-axis hold applied through the lane (the-stilling §2.1). The
 *       requested magnitudes sit well within the lane's no-mint cap (≈ 10 % of
 *       the measured φ⁻¹·sqrt(q) cap the genesis slice cites), so an honest
 *       still's {@link CassiFieldThread#perturbationClampCount()} stays 0.</li>
 *   <li><b>{@code shout}</b> — a coherence-<em>delivering</em> write: the same
 *       matched-φ injection at a <b>named larger radius</b> — the vent that
 *       perturbs neighbors, the wake the medium carries (the-shout §2.3). Still
 *       matched (overdraw 0), still bounded, still cap-governed — never a mint
 *       (the-shout §4: a shout converts nothing).</li>
 * </ul>
 *
 * <p><b>Rate-limited.</b> The lane drains at most one perturbation per job
 * (newest-wins coalescing) — the natural throttle. The command additionally
 * enforces a named {@link #COOLDOWN_TICKS} cooldown so a player cannot fire a
 * practice on every tick: one practice write per cooldown window, documented as
 * the practice's cadence (the-stilling §2.2 the held window).
 *
 * <p><b>Read-before/write/read-after.</b> The command reads the practice state
 * before the write ({@link StillingShoutRead#classify}), submits the bounded
 * matched-φ write through {@link CassiCraft#FIELD_THREAD}, awaits the drain (a
 * publish generation advance), then reads the post-practice state and reports
 * pre → post plus the worker's clamp telemetry. Blocking (≤ a few hundred ms)
 * as it waits for the fresh publish the drain lands, exactly as
 * {@code /cassicraft life} does.
 *
 * <p>The command class compiles standalone against the game runtime (no edit to
 * {@code CassiCraft.java} is needed to build it); the caller wires the
 * registration + the {@code CassiCraft.FIELD_THREAD} static into the host.
 */
public final class StillingShoutCommand {

	/**
	 * The stilling's matched-φ write ratio — {@code dEY = φ·dEI} so the overdraw
	 * component {@code dEY − φ·dEI = 0} (a coherence-restoring write, the Yin—Yang
	 * ratio, q4-write-lane-design.md §3; coherence-magic §4.3 — a perfect φ-lock
	 * has no overdraw to clamp).
	 */
	public static final double RESTORE_RATIO = dev.cassicraft.domain.engine.TwoFluidSolver.PHI;

	/**
	 * The stilling's requested EY magnitude — {@code 0.05}, ≈ 10 % of the measured
	 * no-mint cap (≈ 0.52 for the settled field's sqrt(q) ≈ 0.84, the genesis
	 * slice's cited number) and ≈ 8 % of the measured settled EY amplitude, so an
	 * honest still MUST not clamp (the gate asserts the still's clampCount stays 0).
	 */
	public static final double STILL_D_EY = 0.05;

	/** The stilling's matched EI magnitude — {@code STILL_D_EY / φ}, the coherence-restoring leg. */
	public static final double STILL_D_EI = STILL_D_EY / RESTORE_RATIO;

	/** The stilling's Gaussian falloff radius (cells) — a tight locality, the body
	 * holding one spot still. A single-cell-ish write, the Q4 gate's own radius
	 * scale. */
	public static final int STILL_RADIUS = 2;

	/**
	 * The shout's requested EY magnitude — the same matched-φ magnitude as the
	 * still (a shout projects the body's own signature; the-shout §2.1 the
	 * maintenance axis at its loud register), so the shout is the same bounded
	 * coherence, delivered outward.
	 */
	public static final double SHOUT_D_EY = STILL_D_EY;

	/** The shout's matched EI magnitude — {@code SHOUT_D_EY / φ}. */
	public static final double SHOUT_D_EI = SHOUT_D_EY / RESTORE_RATIO;

	/**
	 * The shout's Gaussian falloff radius (cells) — a <b>named larger radius</b>
	 * than the still's: the vent that perturbs neighbors, the directed wake the
	 * medium carries (the-shout §2.3). Still bounded, still cap-governed — the
	 * same coherence found at the still, delivered across the wake.
	 */
	public static final int SHOUT_RADIUS = 6;

	/**
	 * The practice's cooldown — at least this many server ticks between practice
	 * writes (a player cannot fire a still or shout every tick; the lane's
	 * newest-wins is the hard throttle, this is the playable cadence, the-stilling
	 * §2.2 the held window). 40 ticks = 2 s at 20 Hz.
	 */
	public static final int COOLDOWN_TICKS = 40;

	/** The drain-await timeout — the lane is CPU-bound, a job (64 steps + 5 ms) lands inside a few seconds. */
	public static final long DRAIN_TIMEOUT_MS = 10_000;

	/** The last practice tick per command invocation, or -1 before any practice (0 if no server tick yet). */
	private static int lastPracticeTick = -1;

	private StillingShoutCommand() {
	}

	/** Register {@code /cassicraft still [x y z]} and {@code /cassicraft shout [x y z]}. */
	public static void register(CommandDispatcher<CommandSourceStack> dispatcher) {
		dispatcher.register(Commands.literal("cassicraft")
				.then(Commands.literal("still")
						.executes(ctx -> practice(ctx.getSource(), null, false))
						.then(Commands.argument("x", com.mojang.brigadier.arguments.IntegerArgumentType.integer())
								.then(Commands.argument("y", com.mojang.brigadier.arguments.IntegerArgumentType.integer())
										.then(Commands.argument("z", com.mojang.brigadier.arguments.IntegerArgumentType.integer())
												.executes(ctx -> practice(ctx.getSource(), new int[] {
														com.mojang.brigadier.arguments.IntegerArgumentType.getInteger(ctx, "x"),
														com.mojang.brigadier.arguments.IntegerArgumentType.getInteger(ctx, "y"),
														com.mojang.brigadier.arguments.IntegerArgumentType.getInteger(ctx, "z"),
												}, false)))))));
		dispatcher.register(Commands.literal("cassicraft")
				.then(Commands.literal("shout")
						.executes(ctx -> practice(ctx.getSource(), null, true))
						.then(Commands.argument("x", com.mojang.brigadier.arguments.IntegerArgumentType.integer())
								.then(Commands.argument("y", com.mojang.brigadier.arguments.IntegerArgumentType.integer())
										.then(Commands.argument("z", com.mojang.brigadier.arguments.IntegerArgumentType.integer())
												.executes(ctx -> practice(ctx.getSource(), new int[] {
														com.mojang.brigadier.arguments.IntegerArgumentType.getInteger(ctx, "x"),
														com.mojang.brigadier.arguments.IntegerArgumentType.getInteger(ctx, "y"),
														com.mojang.brigadier.arguments.IntegerArgumentType.getInteger(ctx, "z"),
												}, true)))))));
	}

	/**
	 * Run one bounded practice write through the real Q4 lane at a position.
	 *
	 * @param xyz   explicit block coords, or {@code null} for the caller's position
	 *        (console → the world spawn)
	 * @param shout {@code false} = still, {@code true} = shout
	 */
	public static int practice(CommandSourceStack source, int[] xyz, boolean shout) {
		if (dev.cassicraft.CassiCraft.WEATHERGLASS == null) {
			source.sendFailure(Component.literal("The practice is not armed (no world loaded)."));
			return 0;
		}
		CassiFieldThread worker = dev.cassicraft.CassiCraft.FIELD_THREAD;
		if (worker == null || !worker.isRunning()) {
			source.sendFailure(Component.literal("The field thread is not running — no write lane to practice through."));
			return 0;
		}
		BlockPos pos = xyz != null
				? new BlockPos(xyz[0], xyz[1], xyz[2])
				: fallbackPos(source);
		// The practice's cadence: at most one write per cooldown window (the lane's
		// newest-wins is the hard throttle; this is the playable cadence).
		int tick = source.getServer().getTickCount();
		if (lastPracticeTick >= 0 && tick - lastPracticeTick < COOLDOWN_TICKS) {
			int wait = COOLDOWN_TICKS - (tick - lastPracticeTick);
			source.sendFailure(Component.literal("The field needs a moment to still before the next practice — wait "
					+ wait + " ticks (the lane drains at most one write per job)."));
			return 0;
		}
		double dEY = shout ? SHOUT_D_EY : STILL_D_EY;
		double dEI = shout ? SHOUT_D_EI : STILL_D_EI;
		int radius = shout ? SHOUT_RADIUS : STILL_RADIUS;

		dev.cassicraft.domain.snapshot.SnapshotPublisher pub =
				dev.cassicraft.CassiCraft.WEATHERGLASS.publisherSupplier().get();
		FieldSnapshot pre = pub.freshest();
		if (pre == null || pre.job() == null) {
			source.sendFailure(Component.literal("The field is not yet publishing \u2014 nothing to practice against."));
			return 0;
		}
		double[] center = !pre.job().isWindowless()
				? pre.job().windowCenter()
				: new double[] { 0, 0, 0 };
		Quantizer.FieldReading preR = Quantizer.sampleReading(pre, center,
				pos.getX(), pos.getY(), pos.getZ());
		StillingShoutRead.Read preState = StillingShoutRead.classify(preR);

		// The write: a bounded, matched-φ source injection through the REAL lane.
		// The lane clamps (no-mint + overdraw) if the request ever exceeds them;
		// the matched-φ still/shout requests are well within, so their clampCount is
		// expected 0 — an unexpected clamp is a design bug, never a silenced counter.
		worker.submitPerturbation(pos.getX(), pos.getY(), pos.getZ(), dEY, dEI, radius);

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
			source.sendFailure(Component.literal("Practice interrupted while awaiting the field's drain."));
			return 0;
		}
		if (post == null || post.job() == null) {
			source.sendFailure(Component.literal("The field did not drain the practice within the bound — the write was submitted but its response is unseen."));
			return 0;
		}
		double[] postCenter = !post.job().isWindowless() ? post.job().windowCenter() : center;
		Quantizer.FieldReading postR = Quantizer.sampleReading(post, postCenter,
				pos.getX(), pos.getY(), pos.getZ());
		StillingShoutRead.Read postState = StillingShoutRead.classify(postR);
		long clamps = worker.perturbationClampCount();

		String verb = shout ? "SHOUT" : "STILL";
		source.sendSuccess(() -> Component.literal(
				verb + " @ (" + pos.getX() + "," + pos.getY() + "," + pos.getZ() + ")\n"
				+ "  " + text(pos, preState, postState, preR, postR, dEY, radius, clamps)),
				false);
		return 1;
	}

	/** The live practice readout text (deterministic pure function of the read + write meta). */
	private static String text(BlockPos pos, StillingShoutRead.Read pre, StillingShoutRead.Read post,
			Quantizer.FieldReading preR, Quantizer.FieldReading postR,
			double dEY, int radius, long clamps) {
		return "  pre  " + pre.state().label() + " (q " + fmt(preR.q()) + ", ε² " + fmt(preR.eps2()) + ")\n"
				+ "  post " + post.state().label() + " (q " + fmt(postR.q()) + ", ε² " + fmt(postR.eps2()) + ")\n"
				+ "  bounded matched-φ write dEY=" + fmt((float) dEY) + " dEI=" + fmt((float) (dEY / RESTORE_RATIO))
				+ " radius=" + radius + " cells | lane clampCount=" + clamps
				+ " (expected 0 for the matched-φ still; the lane clamps any overdraw/no-mint)";
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
