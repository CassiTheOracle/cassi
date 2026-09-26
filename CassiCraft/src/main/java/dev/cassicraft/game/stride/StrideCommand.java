package dev.cassicraft.game.stride;

import com.mojang.brigadier.CommandDispatcher;
import dev.cassicraft.domain.snapshot.FieldSnapshot;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;

/**
 * The {@code /cassicraft stride} command — the stride's readable-from-the-
 * instruments read (the-walk.md §4e: every read the walk presents is also
 * readable from the instruments, never hidden-only). Prints the bounded stride
 * read at the caller's position (or an explicit block), the same headless-
 * testable {@code [x y z]} pattern as {@code /cassicraft wind} and
 * {@code /cassicraft ride}: a pure consumer of the session's published snapshot
 * via the Weatherglass publisher supplier.
 *
 * <p>The command is a <b>standing read</b> (zero-step, {@link StrideRead} with
 * {@code step = 0}) so it is a deterministic headless probe — it prints the
 * horizontal river magnitude + direction, the local {@code q} (easy / thin
 * ground), and the stride state (STILL water for a standing read). The live
 * {@link StrideCoordinator} applies the same read per-player on movement; the
 * command exposes the read itself (the-walk.md §4e — the stride's reads are the
 * instruments' own, never hidden-only). It is a <b>read</b> only — never a
 * write, never a movement pass, never a mint (the-walk.md §4d).
 *
 * <p>The command class compiles standalone against the game runtime (no edit to
 * {@link dev.cassicraft.CassiCraft} is needed to build it); the caller wires the
 * registration into the {@code CommandRegistrationCallback} block.
 */
public final class StrideCommand {

	/** Register {@code /cassicraft stride [x y z]}. */
	public static void register(CommandDispatcher<CommandSourceStack> dispatcher) {
		dispatcher.register(Commands.literal("cassicraft")
				.then(Commands.literal("stride")
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
	 * Run the stride read at a position. The publisher supplier is the
	 * Weatherglass's session publisher (the same one {@code /cassicraft read}
	 * reads); with no world, no publish, or a stale gate the read fails honestly.
	 *
	 * @param xyz explicit block coords, or {@code null} for the caller's position
	 *        (console → the world spawn)
	 */
	public static int run(CommandSourceStack source, int[] xyz) {
		if (dev.cassicraft.CassiCraft.WEATHERGLASS == null) {
			source.sendFailure(Component.literal("The stride reader is not armed (no world loaded)."));
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
		// Standing read (zero-step) — deterministic headless probe.
		dev.cassicraft.game.sampler.Quantizer.FieldReading r =
				dev.cassicraft.game.sampler.Quantizer.sampleReading(snap, center,
						pos.getX(), pos.getY(), pos.getZ());
		StrideRead.StrideReading stride = StrideRead.of(r, 0, 0);
		source.sendSuccess(() -> Component.literal("Stride @ (" + pos.getX() + "," + pos.getY() + "," + pos.getZ() + ")\n" + stride.text()),
				false);
		return 1;
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

	private StrideCommand() {
	}
}
