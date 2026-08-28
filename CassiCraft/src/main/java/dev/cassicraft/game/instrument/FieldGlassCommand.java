package dev.cassicraft.game.instrument;

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
 * The {@code /cassicraft fieldglass} command — the FieldGlass read
 * (field-instruments.md §1, §2.2; material-regimes.md §1, §4, §5–6). Prints the
 * FieldGlass's full chart at the caller's position (or an explicit block): the
 * five published channels — local {@code q} (lume), {@code ρ} (depth), {@code ε²}
 * (strain), the river gradient {@code ∇(g·Φ)} (the lean, direction + magnitude),
 * the {@code (1−q)} waste fraction — plus the governing material regime (the
 * TIER-REAL rung and the [design] constants). This is the <b>headless-testable
 * field-glass</b>: the command that presents the instrument read the way a worn
 * or held field-glass would, in the same seekable form as {@code /cassicraft
 * read}, {@code /cassicraft material}, {@code /cassicraft sky}.
 *
 * <p>The command reads {@link FieldGlassRead#read} off the published channels via
 * the Weatherglass publisher supplier (the same seam as {@code /cassicraft read}
 * and {@code /cassicraft material}). It is a <b>read</b> only — never a write,
 * never a block mutation, never a free-energy grant (only-mutator rule;
 * no-free-energy cap). No tick hook — on-demand read.
 *
 * <p>The command class compiles standalone against the game runtime (no edit to
 * {@code CassiCraft.java} is needed to build it); the caller wires the
 * registration into the {@code CommandRegistrationCallback} block.
 */
public final class FieldGlassCommand {

	/** Register {@code /cassicraft fieldglass [x y z]}. */
	public static void register(CommandDispatcher<CommandSourceStack> dispatcher) {
		dispatcher.register(Commands.literal("cassicraft")
				.then(Commands.literal("fieldglass")
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
	 * Run the FieldGlass read at a position.
	 *
	 * @param xyz explicit block coords, or {@code null} for the caller's position
	 *        (console → the world spawn)
	 */
	public static int run(CommandSourceStack source, int[] xyz) {
		if (dev.cassicraft.CassiCraft.WEATHERGLASS == null) {
			source.sendFailure(Component.literal("The FieldGlass is not armed (no world loaded)."));
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
		FieldGlassRead.FieldGlassReadout out = FieldGlassRead.read(r);
		source.sendSuccess(() -> Component.literal("FieldGlass @ (" + pos.getX() + "," + pos.getY() + "," + pos.getZ() + ")\n" + out.text()),
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

	private FieldGlassCommand() {
	}
}
