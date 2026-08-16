package dev.cassicraft.game.sky;

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
 * The {@code /cassicraft sky} command — the sky's readable-from-the-instruments
 * gate (atmosphere-orbits-auroras.md §3.3, weather-not-storm §5.4 gate (e): the
 * sky is readable from the instruments, never hidden-only). Prints the sky read
 * at the caller's position (or an explicit block) — the same headless-testable
 * pattern as {@code /cassicraft read}, {@code /cassicraft wind} and
 * {@code /cassicraft material}: a pure consumer of the session's published
 * snapshot via the Weatherglass publisher supplier.
 *
 * <p>The command reads {@link SkyRead#classify} off the published channels and
 * prints the glow intensity, the storm's leading-edge darkening (with the
 * readable-before-it-arrives framing — the front's {@code ε²} approach in the
 * same units the corpus reads it, weather-not-storm §2.1), the fog thickness,
 * and the raw measured {@code (ρ, q, ε²)}. It is a <b>read</b> only — never a
 * write, never a block mutation, never a mint (only-mutator rule; no-free-energy,
 * atmosphere §5c).
 *
 * <p>The command class compiles standalone against the game runtime (no edit to
 * {@code CassiCraft.java} is needed to build it); the caller wires the
 * registration into the {@code CommandRegistrationCallback} block.
 */
public final class SkyCommand {

	/** Register {@code /cassicraft sky [x y z]}. */
	public static void register(CommandDispatcher<CommandSourceStack> dispatcher) {
		dispatcher.register(Commands.literal("cassicraft")
				.then(Commands.literal("sky")
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
	 * Run the sky read at a position.
	 *
	 * @param xyz explicit block coords, or {@code null} for the caller's position
	 *        (console → the world spawn)
	 */
	public static int run(CommandSourceStack source, int[] xyz) {
		if (dev.cassicraft.CassiCraft.WEATHERGLASS == null) {
			source.sendFailure(Component.literal("The sky reader is not armed (no world loaded)."));
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
		SkyRead.Read s = SkyRead.classify(r);
		source.sendSuccess(() -> Component.literal("Sky @ (" + pos.getX() + "," + pos.getY() + "," + pos.getZ() + ")\n" + text(pos, s)),
				false);
		return 1;
	}

	/** The live sky readout text (deterministic pure function of the read). */
	public static String text(BlockPos pos, SkyRead.Read s) {
		StringBuilder sb = new StringBuilder()
				.append("  ").append(s.kind().label());
		if (s.isStormEdge()) {
			sb.append(" — the front's approach ").append(fmt(s.frontApproach()))
				.append(" ε²-units past the darkening threshold ").append(fmt(SkyRead.STORM_EDGE_EPS2))
				.append(" (readable-before-it-arrives, weather-not-storm §2: the sky darkens ahead of the storm)");
		} else {
			sb.append(" — leading-edge darkening ").append(fmt(s.darkening()))
				.append(" of ").append(fmt(SkyRead.STORM_EDGE_EPS2))
				.append(" (front approach ").append(fmt(s.frontApproach())).append(" ε²-units)");
		}
		sb.append("\n  Glow ").append(fmt(s.glow()))
			.append(" of a ").append(s.isGlow() ? "GLOW" : "non-glow sky (q-tail " + fmt(SkyRead.GLOW_Q_TAIL) + ")");
		sb.append("\n  Fog ").append(fmt(s.fog()))
			.append(" of the density ").append(fmt(SkyRead.FOG_RHO_TAIL));
		sb.append("\n  raw (ρ ").append(fmt(s.rho()))
			.append(", q ").append(fmt(s.q()))
			.append(", ε² ").append(fmt(s.eps2())).append(")");
		return sb.toString();
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

	private SkyCommand() {
	}
}
