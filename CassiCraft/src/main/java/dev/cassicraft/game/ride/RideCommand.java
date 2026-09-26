package dev.cassicraft.game.ride;

import com.mojang.brigadier.CommandDispatcher;
import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.game.sampler.Quantizer;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.core.BlockPos;
import net.minecraft.network.chat.Component;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.entity.vehicle.minecart.Minecart;
import net.minecraft.world.level.entity.EntityTypeTest;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;

/**
 * The {@code /cassicraft ride} command — the ride's readable-from-the-instruments
 * gate (coherence-highway.md §6e: the ride is readable, never hidden; the field
 * read surfaces show what is carrying the cart). Prints, at the caller's position
 * (or an explicit block — or the nearest minecart if one is near), the sampled
 * published channels (ρ, q, ε², |∇(g·Φ)|), the derived π/ρ, the engine-real haul
 * acceleration being applied (the same {@link RideHaul} the coordinator uses), and
 * the current speed of the vehicle at that position.
 *
 * <p>It is a <b>read</b> only — never a write, never a new movement pass, never a
 * mint (coherence-highway §6d: the haul is the field's own ∇(g·Φ); the command
 * reports it, it does not grant it). The command class compiles standalone against
 * the game runtime; the caller wires the registration into the
 * {@code CommandRegistrationCallback} block (via {@code CassiCraft.java}).
 */
public final class RideCommand {

	/** [design] How close a minecart must be to the read position to be the "vehicle". */
	private static final double VEHICLE_RADIUS_BLOCKS = 2.0;

	private RideCommand() {
	}

	/** Register {@code /cassicraft ride}. */
	public static void register(CommandDispatcher<CommandSourceStack> dispatcher) {
		dispatcher.register(Commands.literal("cassicraft")
				.then(Commands.literal("ride")
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
	 * Run the ride read at a position. The publisher supplier is the Weatherglass's
	 * session publisher (the same one {@code /cassicraft read} reads); with no
	 * world, no publish, or a stale gate the read fails honestly.
	 *
	 * @param xyz explicit block coords, or {@code null} for the caller's position
	 *        (console → the world spawn)
	 */
	public static int run(CommandSourceStack source, int[] xyz) {
		if (dev.cassicraft.CassiCraft.WEATHERGLASS == null) {
			source.sendFailure(Component.literal("The ride reader is not armed (no world loaded)."));
			return 0;
		}
		ServerPlayer player = source.getPlayer();
		BlockPos pos = xyz != null
				? new BlockPos(xyz[0], xyz[1], xyz[2])
				: (player != null ? player.blockPosition() : fallbackPos(source));
		FieldSnapshot snap = dev.cassicraft.CassiCraft.WEATHERGLASS.publisherSupplier().get().freshest();
		if (snap == null) {
			source.sendFailure(Component.literal("The field is not yet publishing."));
			return 0;
		}
		double[] center = snap.job() != null && !snap.job().isWindowless()
				? snap.job().windowCenter()
				: new double[] { 0, 0, 0 };
		Quantizer.FieldReading r = Quantizer.sampleReading(snap, center, pos.getX(), pos.getY(), pos.getZ());
		RideHaul.Haul haul = RideHaul.of(r);

		double vehicleSpeed = -1.0; // -1 = no vehicle read (no near cart, no player velocity)
		ServerLevel overworld = source.getServer().overworld();
		if (overworld != null) {
			Minecart near = nearestCart(overworld, pos);
			if (near != null) {
				vehicleSpeed = speed(near.getDeltaMovement());
			} else if (player != null) {
				vehicleSpeed = speed(player.getDeltaMovement());
			}
		}
		final double vehicleSpeedFinal = vehicleSpeed;

		source.sendSuccess(() -> Component.literal(text(pos, haul, vehicleSpeedFinal)), false);
		return 1;
	}

	/** The live ride readout text (deterministic pure function of the haul + speed). */
	public static String text(BlockPos pos, RideHaul.Haul haul, double vehicleSpeed) {
		StringBuilder sb = new StringBuilder()
				.append("Ride @ (").append(pos.getX()).append(",").append(pos.getY()).append(",").append(pos.getZ()).append(")\n");
		if (haul.rho() <= 0f) {
			sb.append("  Out-of-box air \u2014 no field here; the cart rides vanilla (the field ends at the box).\n");
			sb.append("  Haul applied: none.");
			if (vehicleSpeed >= 0) {
				sb.append("  speed=").append(fmt(vehicleSpeed));
			}
			return sb.toString();
		}
		sb.append("  \u03c1=").append(fmt(haul.rho()))
			.append("  q=").append(fmt(haul.q()))
			.append("  \u03b5\u00b2=").append(fmt(haul.eps2()))
			.append("  |\u2207(g\u00b7\u03a6)|=").append(fmt(haul.gradMag()))
			.append("  \u03c0/\u03c1=").append(fmt(haul.piOverRho())).append("\n");
		sb.append("  Haul applied \u0394v/tick = <")
			.append(fmt(haul.ax() * RideHaul.RIDE_DT)).append(",")
			.append(fmt(haul.ay() * RideHaul.RIDE_DT)).append(",")
			.append(fmt(haul.az() * RideHaul.RIDE_DT)).append(">  (|a|=").append(fmt(haulMag(haul))).append(")\n");
		if (vehicleSpeed >= 0) {
			sb.append("  Cart/vehicle speed = ").append(fmt(vehicleSpeed));
		} else {
			sb.append("  No vehicle speed read (no rider or near cart).");
		}
		return sb.toString();
	}

	private static double haulMag(RideHaul.Haul h) {
		return Math.sqrt(h.ax() * h.ax() + h.ay() * h.ay() + h.az() * h.az());
	}

	/** The nearest living minecart within the vehicle radius, else {@code null}. */
	private static Minecart nearestCart(ServerLevel level, BlockPos pos) {
		AABB box = new AABB(pos.getX() - VEHICLE_RADIUS_BLOCKS, pos.getY() - VEHICLE_RADIUS_BLOCKS,
				pos.getZ() - VEHICLE_RADIUS_BLOCKS, pos.getX() + VEHICLE_RADIUS_BLOCKS,
				pos.getY() + VEHICLE_RADIUS_BLOCKS, pos.getZ() + VEHICLE_RADIUS_BLOCKS);
		Minecart best = null;
		double bestD = Double.MAX_VALUE;
		for (Minecart c : level.getEntities(EntityTypeTest.forClass(Minecart.class), box, Minecart::isAlive)) {
			double d = c.distanceToSqr(pos.getX(), pos.getY(), pos.getZ());
			if (d < bestD) {
				bestD = d;
				best = c;
			}
		}
		return best;
	}

	private static double speed(Vec3 v) {
		return Math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z);
	}

	/** Caller (player) position or the world spawn for console/headless use. */
	private static BlockPos fallbackPos(CommandSourceStack source) {
		ServerLevel overworld = source.getServer().overworld();
		return overworld != null && overworld.getRespawnData() != null && overworld.getRespawnData().pos() != null
				? overworld.getRespawnData().pos()
				: BlockPos.ZERO;
	}

	private static String fmt(double v) {
		return String.format("%.4f", v);
	}
}
