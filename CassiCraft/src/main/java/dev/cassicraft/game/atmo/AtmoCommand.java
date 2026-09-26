package dev.cassicraft.game.atmo;

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
 * The {@code /cassicraft atmo} command — the atmosphere's readable-from-the-
 * instruments gate (atmosphere-orbits-auroras.md §3.3, the reader's atmospheric
 * form: the sky's field phenomena are readable, never hidden-only). Prints the
 * atmosphere field read (aurora / orbit well / envelope / clear) at the
 * caller's position (or an explicit block) — the same headless-testable pattern
 * as {@code /cassicraft read}, {@code /cassicraft sky} and {@code /cassicraft
 * wind}: a pure consumer of the session's published snapshot via the Weatherglass
 * publisher supplier.
 *
 * <p>The command reads {@link AtmoRead#classify} off the published channels and
 * prints the aurora's discharge (the (1−q) waste fraction), the envelope's
 * fog-density, the orbit well's |∇(g·Φ)| hold, and the raw measured channels.
 * It is a <b>read</b> only — never a write, never a block mutation, never a
 * mint (only-mutator rule; no-free-energy, atmosphere §5c).
 *
 * <p>The command class compiles standalone against the game runtime (no edit to
 * {@code CassiCraft.java} is needed to build it); the caller wires the
 * registration into the {@code CommandRegistrationCallback} block.
 */
public final class AtmoCommand {

	/** Register {@code /cassicraft atmo [x y z]}. */
	public static void register(CommandDispatcher<CommandSourceStack> dispatcher) {
		dispatcher.register(Commands.literal("cassicraft")
				.then(Commands.literal("atmo")
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
	 * Run the atmosphere read at a position.
	 *
	 * @param xyz explicit block coords, or {@code null} for the caller's position
	 *        (console → the world spawn)
	 */
	public static int run(CommandSourceStack source, int[] xyz) {
		if (dev.cassicraft.CassiCraft.WEATHERGLASS == null) {
			source.sendFailure(Component.literal("The atmosphere reader is not armed (no world loaded)."));
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
		AtmoRead.Read a = AtmoRead.classify(r);
		source.sendSuccess(() -> Component.literal("Atmo @ (" + pos.getX() + "," + pos.getY() + "," + pos.getZ() + ")\n" + text(pos, a)),
				false);
		return 1;
	}

	/** The live atmosphere readout text (deterministic pure function of the read). */
	public static String text(BlockPos pos, AtmoRead.Read a) {
		StringBuilder sb = new StringBuilder()
				.append("  ").append(a.kind().label());
		if (a.isAurora()) {
			sb.append(" — discharge ").append(fmt(a.discharge()))
				.append(" (the (1−q) waste the field sheds into the drain; q ").append(fmt(a.q()))
				.append(" ≥ the coherent floor, ε² ").append(fmt(a.eps2()))
				.append(" in the drain band [").append(fmt(AtmoRead.AURORA_EPS2_FLOOR))
				.append(", ").append(fmt(dev.cassicraft.game.sky.SkyRead.STORM_EDGE_EPS2))
				.append("))");
		} else if (a.isOrbitWell()) {
			sb.append(" — deep coherent q ").append(fmt(a.q()))
				.append(" over a |∇(g·Φ)| ").append(fmt(a.gradMag()))
				.append(" hold (the body-seed precursor; the tree arm that holds an orbit is later)");
		} else if (a.isInEnvelope()) {
			sb.append(" — fog-density ").append(fmt(a.fogDensity()))
				.append(" of the gas band (ρ ").append(fmt(a.rho()))
				.append(" between the vacuum floor ").append(fmt(AtmoRead.ENVELOPE_VACUUM_RHO))
				.append(" and condensation ").append(fmt(AtmoRead.ENVELOPE_CONDENSE_RHO)).append(")");
		}
		sb.append("\n  raw (ρ ").append(fmt(a.rho()))
			.append(", q ").append(fmt(a.q()))
			.append(", ε² ").append(fmt(a.eps2()))
			.append(", |∇(g·Φ)| ").append(fmt(a.gradMag())).append(")");
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

	private AtmoCommand() {
	}
}
