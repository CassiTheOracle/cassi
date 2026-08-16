package dev.cassicraft.game.material;

import com.mojang.brigadier.CommandDispatcher;
import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.game.sampler.Quantizer;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;

/**
 * The {@code /cassicraft material} command — the real-element material read
 * (material-regimes.md §7, closing the "regime dressing is surface" deferral).
 * Prints the regime read at the caller's position (or an explicit block) — the
 * local {@code (ρ, q, ε²)}, the governing material tuple (name, rung {@code n},
 * the special-point distance), and the phase verdict. This is the <b>instrument
 * read</b>: the calibration is legible, never hidden (the owner sees the real
 * element, its rung, and the measuring [design] constants on demand).
 *
 * <p>The command reads {@link MaterialRegimeRead#classify} off the published
 * channels via the Weatherglass publisher supplier (the same seam as
 * {@code /cassicraft read} and {@code /cassicraft wind}). It is a <b>read</b>
 * only — never a write, never a block mutation, never a free-energy grant
 * (only-mutator rule; no-free-energy cap). No tick hook — on-demand read.
 *
 * <p>The command class compiles standalone against the game runtime (no edit to
 * {@code CassiCraft.java} is needed to build it); the caller wires the
 * registration into the {@code CommandRegistrationCallback} block.
 */
public final class MaterialCommand {

	/** Register {@code /cassicraft material [x y z]}. */
	public static void register(CommandDispatcher<CommandSourceStack> dispatcher) {
		dispatcher.register(Commands.literal("cassicraft")
				.then(Commands.literal("material")
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
	 * Run the material read at a position.
	 *
	 * @param xyz explicit block coords, or {@code null} for the caller's position
	 *        (console → the world spawn)
	 */
	public static int run(CommandSourceStack source, int[] xyz) {
		if (dev.cassicraft.CassiCraft.WEATHERGLASS == null) {
			source.sendFailure(Component.literal("The material reader is not armed (no world loaded)."));
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
		Quantizer.FieldReading r = Quantizer.sampleReading(snap, center, pos.getX(), pos.getY(), pos.getZ());
		MaterialRegimeRead.RegimeRead m = MaterialRegimeRead.classify(r);
		source.sendSuccess(() -> Component.literal("Material @ (" + pos.getX() + "," + pos.getY() + "," + pos.getZ() + ")\n" + MaterialRegimeRead.text(m)),
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

	private MaterialCommand() {
	}
}
