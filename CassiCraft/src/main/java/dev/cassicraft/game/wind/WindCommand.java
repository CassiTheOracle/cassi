package dev.cassicraft.game.wind;

import com.mojang.brigadier.CommandDispatcher;
import dev.cassicraft.domain.snapshot.FieldSnapshot;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;

/**
 * The {@code /cassicraft wind} command — the wind's readable-from-the-instruments
 * gate (the-wind.md §7 gate (e): the wind's direction and carry are readable from
 * the instruments, never hidden-only). Prints the bounded wind read at the
 * caller's position (or an explicit block), the same headless-testable pattern
 * as {@code /cassicraft read} and {@code /cassicraft stride}: a pure consumer of
 * the session's published snapshot via the Weatherglass publisher supplier.
 *
 * <p>The command reads {@link WindRead#read} off the published channels (the
 * horizontal ∇(g·Φ) flow-face + the upwind carry probe) and prints the
 * direction, strength, carry, cost-and-aid, and the raw measured gradient. It
 * is a <b>read</b> only — never a write, never a new movement pass, never a
 * mint (the no-free-energy cap, the-wind.md §5d).
 *
 * <p>The command class compiles standalone against the game runtime (no edit to
 * {@code CassiCraft.java} is needed to build it); the caller wires the
 * registration into the {@code CommandRegistrationCallback} block.
 */
public final class WindCommand {

	/** Register {@code /cassicraft wind}. */
	public static void register(CommandDispatcher<CommandSourceStack> dispatcher) {
		dispatcher.register(Commands.literal("cassicraft")
				.then(Commands.literal("wind")
						.executes(ctx -> run(ctx.getSource(), null))
						.then(Commands.argument("x", com.mojang.brigadier.arguments.IntegerArgumentType.integer())
								.then(Commands.argument("y", com.mojang.brigadier.arguments.IntegerArgumentType.integer())
										.then(Commands.argument("z", com.mojang.brigadier.arguments.IntegerArgumentType.integer())
												.executes(ctx -> run(ctx.getSource(), new int[] {
														com.mojang.brigadier.arguments.IntegerArgumentType.getInteger(ctx, "x"),
														com.mojang.brigadier.arguments.IntegerArgumentType.getInteger(ctx, "y"),
														com.mojang.brigadier.arguments.IntegerArgumentType.getInteger(ctx, "z"),
												})))))));
	}

	/**
	 * Run the wind read at a position. The publisher supplier is the
	 * Weatherglass's session publisher (the same one {@code /cassicraft read}
	 * reads); with no world, no publish, or a stale gate the read fails honestly.
	 *
	 * @param xyz explicit block coords, or {@code null} for the caller's position
	 *        (console → the world spawn)
	 */
	public static int run(CommandSourceStack source, int[] xyz) {
		if (dev.cassicraft.CassiCraft.WEATHERGLASS == null) {
			source.sendFailure(Component.literal("The wind reader is not armed (no world loaded)."));
			return 0;
		}
		BlockPos pos = xyz != null
				? new BlockPos(xyz[0], xyz[1], xyz[2])
				: fallbackPos(source);
		FieldSnapshot snap = dev.cassicraft.CassiCraft.WEATHERGLASS.publisherSupplier().get().freshest();
		if (snap == null) {
			source.sendFailure(Component.literal("The field is not yet publishing."));
			return 0;
		}
		double[] center = snap.job() != null && !snap.job().isWindowless()
				? snap.job().windowCenter()
				: new double[] { 0, 0, 0 };
		WindRead.WindReading w = WindRead.read(snap, center, pos.getX(), pos.getY(), pos.getZ());
		source.sendSuccess(() -> Component.literal(text(pos, w)), false);
		return 1;
	}

	/** The live wind readout text (deterministic pure function of the read). */
	public static String text(BlockPos pos, WindRead.WindReading w) {
		StringBuilder sb = new StringBuilder()
				.append("Wind @ (").append(pos.getX()).append(",").append(pos.getY()).append(",").append(pos.getZ()).append(")\n");
		if (w.isCalm()) {
			sb.append("  CALM \u2014 no coherent directional current (|grad xz ").append(fmt(w.gradH()))
				.append("|, below the measured noise floor)");
			return sb.toString();
		}
		sb.append("  Direction ").append(dirWord(w.direction()))
			.append("  (grad xz <").append(fmt(w.gradX())).append(",").append(fmt(w.gradZ())).append(">  |gradH| ").append(fmt(w.gradH())).append(")\n");
		sb.append("  Strength ").append(String.format("%.2f", w.strengthValue()))
			.append(" (").append(strengthWord(w.strength())).append(") \u2014 |grad(xz)| ")
			.append(fmt(w.gradH())).append(" vs the calibrated floor ")
			.append(fmt(WindRead.GRAD_H_NOISE_FLOOR)).append(" / strong ").append(fmt(WindRead.GRAD_H_STRONG)).append("\n");
		sb.append("  Carry ").append(carryWord(w.carry()))
			.append(w.carry() == WindRead.Carry.CLEAR ? ""
				: "  (upwind \u03b5\u00b2 " + fmt(w.carryUpwindEps2()) + ", q " + fmt(w.carryUpwindQ()) + " @ " + WindRead.CARRY_PROBE_CELLS + " cell)")
			.append("\n");
		sb.append("  Cost-and-aid ").append(w.costAid() > 0f
				? "tailwind aid +" + String.format("%.2f", w.costAid())
				: "headwind tax \u2212" + String.format("%.2f", -w.costAid()))
			.append(" \u2014 a read of the current, never a new movement pass (the walk's stride already reads the lean)");
		return sb.toString();
	}

	private static String dirWord(WindRead.Direction d) {
		switch (d) {
		case N: return "North";
		case NE: return "North-East";
		case E: return "East";
		case SE: return "South-East";
		case S: return "South";
		case SW: return "South-West";
		case W: return "West";
		case NW: return "North-West";
		default: return "CALM";
		}
	}

	private static String strengthWord(WindRead.Strength s) {
		switch (s) {
		case CALM: return "calm";
		case LIGHT: return "light current";
		case MODERATE: return "moderate current";
		case STRONG: return "strong current";
		default: return "?";
		}
	}

	private static String carryWord(WindRead.Carry c) {
		switch (c) {
		case STORM_FRONT: return "carrying a storm front (\u03b5\u00b2 upwind elevated)";
		case COHERENCE: return "carrying coherence (q upwind elevated)";
		default: return "clear";
		}
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

	private WindCommand() {
	}
}
