package dev.cassicraft;

import com.mojang.brigadier.CommandDispatcher;
import dev.cassicraft.game.advect.FollowBehind;
import dev.cassicraft.game.life.LifeSignal;
import dev.cassicraft.game.life.RiverSteering;
import dev.cassicraft.game.lume.LumePayload;
import dev.cassicraft.game.lume.LumePusher;
import dev.cassicraft.game.reader.FieldReader;
import dev.cassicraft.game.reader.WeatherglassItem;
import dev.cassicraft.game.sampler.SamplerShutdown;
import dev.cassicraft.game.sampler.Quantizer;
import dev.cassicraft.game.spawn.SurfaceSpawn;
import dev.cassicraft.game.walk.MovementCost;
import dev.cassicraft.game.walk.StrideCostPass;
import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.command.v2.CommandRegistrationCallback;
import net.fabricmc.fabric.api.creativetab.v1.CreativeModeTabEvents;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerLifecycleEvents;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerLevelEvents;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;
import net.fabricmc.fabric.api.networking.v1.PayloadTypeRegistry;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.Commands;
import net.minecraft.core.BlockPos;
import net.minecraft.core.Registry;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.network.chat.Component;
import net.minecraft.resources.Identifier;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.item.CreativeModeTab;
import net.minecraft.world.item.ItemStack;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * MODULE 2/3/4 HOST — Minecraft entrypoint. Startup wiring only (BUILD-PLAN.md
 * §5, §7). Routes the server lifecycle into the four-module seam, and registers
 * the map-step-2 reader (Weatherglass item + the {@code /cassicraft read}
 * command) as pure consumers of the session's snapshot handoff:
 *
 * <ol>
 *   <li><b>World load</b> ({@link ServerLevelEvents.LOAD}) stands up the domain
 *       field thread (seeded from the world seed), the tick-sampler, and the
 *       world-writer via {@link SamplerShutdown#beginSession}.</li>
 *   <li><b>Server tick</b> routes the freshest-publish read + intent flush
 *       (the sampler reads, the writer mutates — the only-mutator rule).</li>
 *   <li><b>World unload / server stop</b> joins the field worker and closes the
 *       writer (explicit close, never a finalizer).</li>
 * </ol>
 *
 * <p>The item and the command share <em>one</em> read entry point,
 * {@link FieldReader#readFreshest}, so the readout path is identical whether a
 * player right-clicks the Weatherglass or runs {@code /cassicraft read} (the
 * headless-testable form).
 *
 * <p>This is the only host class that owns Minecraft wiring. Everything below the
 * seam (the {@code dev.cassicraft.domain} package) compiles against no Minecraft
 * symbol and is reached only through this entrypoint's handoff.
 */
public class CassiCraft implements ModInitializer {

	private static final Logger LOGGER = LoggerFactory.getLogger(CassiCraft.class);
	private static final String MOD_ID = "cassicraft";

	/** The single Weatherglass item (registered once at mod init). */
	public static WeatherglassItem WEATHERGLASS;

	private final SamplerShutdown session = new SamplerShutdown();

	/** The life response (river-law steering) for the live session (created per-session). */
	private RiverSteering steering;

	/** The movement-cost pass (stride drag) for the live session (created per-session). */
	private StrideCostPass strideCost;

	/** Sets the player's respawn on the field surface once the field publishes. */
	private SurfaceSpawn surfaceSpawn;

	/** The follow-behind advection coordinator (created per-session, nulled on teardown). */
	private FollowBehind followBehind;

	/** The always-on Weatherglass lume push coordinator (created per-session, nulled on teardown). */
	private LumePusher lumePusher;

	@Override
	public void onInitialize() {
		registerWeatherglass();

		// The always-on lume channel (field-instruments §1.4): a bounded S2C
		// presentation of the published snapshot, registered once. The client
		// receiver lives in the separate client entrypoint.
		PayloadTypeRegistry.clientboundPlay().register(LumePayload.TYPE, LumePayload.CODEC);

		// World load → start the domain field thread + sampler + writer for this
		// world. The overworld is the Phase-1 substrate (its seed is the field
		// seed). The box is anchored to where the player enters (the world spawn),
		// so grid (32,32,32) maps to the spawn block and the player stands in the
		// field's real interior, not a clamped edge (async-field-domain §7 Q1 —
		// the movable home-window, anchored-to-window). The follow-behind
		// coordinator re-homes that box behind the player as they walk (world-seams
		// §4.2's anchor-to-window policy); the box is 192³ ≈ 12×12 chunks.
		ServerLevelEvents.LOAD.register((server, level) -> {
			if (server.overworld() != level || session.isRunning()) {
				return; // only the overworld hosts the living-terrain seam, once
			}
			long seed = level.getSeed();
			BlockPos spawn = level.getRespawnData() != null && level.getRespawnData().pos() != null
					? level.getRespawnData().pos()
					: BlockPos.ZERO;
			double[] anchor = { spawn.getX(), spawn.getY(), spawn.getZ() };
			long used = session.beginSession(level, seed, anchor);
			followBehind = new FollowBehind(session.publisher(), session.fieldThread());
			lumePusher = new LumePusher(WEATHERGLASS, session.publisher());
			steering = new RiverSteering(session.publisher());
			strideCost = new StrideCostPass(session.publisher());
			surfaceSpawn = new SurfaceSpawn(session.publisher(), anchor);
			LOGGER.info("[cassicraft] field thread started for world (seed {}), window anchored at ({},{},{}), follow coordinator attached",
					used, (int) anchor[0], (int) anchor[1], (int) anchor[2]);
		});

		// World unload → join the field worker (explicit close).
		ServerLevelEvents.UNLOAD.register((server, level) -> {
			if (server.overworld() == level || session.isRunning()) {
				session.endSession();
				followBehind = null;
				lumePusher = null;
				steering = null;
				strideCost = null;
				surfaceSpawn = null;
				LOGGER.info("[cassicraft] field thread closed (world unload)");
			}
		});

		// Server stop → release the session if a world never unloaded cleanly.
		ServerLifecycleEvents.SERVER_STOPPING.register(server -> {
			if (session.isRunning()) {
				session.endSession();
				followBehind = null;
				lumePusher = null;
				steering = null;
				strideCost = null;
				surfaceSpawn = null;
				LOGGER.info("[cassicraft] field thread closed (server stop)");
			}
		});

		// The server tick routes sampler → writer once per tick (the only-mutator
		// rule: sampler reads, writer writes blocks), the life-steering pass veers
		// passive animals along the river gradient (a read, never a power source),
		// the stride-cost pass drags players in dear regions (a cost, never a
		// the surface-spawn sets the player's respawn on the field, and the
		// always-on lume pushes the published read to glass-holders (a glance).
		ServerTickEvents.END_SERVER_TICK.register(server -> {
			session.onServerTick(server);
			if (followBehind != null) {
				followBehind.onServerTick(server.overworld());
			}
			if (lumePusher != null) {
				lumePusher.onServerTick(server);
			}
			if (surfaceSpawn != null) {
				surfaceSpawn.onServerTick(server.overworld());
			}
			if (steering != null) {
				steering.onServerTick(server.overworld(), server.getTickCount());
			}
			if (strideCost != null) {
				strideCost.onServerTick(server.overworld(), server.getTickCount());
			}
		});
	}

	/**
	 * Register the Weatherglass item (creative tab), and the {@code /cassicraft
	 * read} command. Both consume {@link FieldReader#readFreshest} off the
	 * session's publisher — the same read path, one entry point.
	 */
	private void registerWeatherglass() {
		Identifier id = Identifier.fromNamespaceAndPath(MOD_ID, "weatherglass");
		// 26.2 requires the item id on the Properties before the Item constructor
		// runs (effectiveDescriptionId reads it at construction).
		net.minecraft.world.item.Item.Properties props = new net.minecraft.world.item.Item.Properties()
				.setId(net.minecraft.resources.ResourceKey.create(net.minecraft.core.registries.Registries.ITEM, id));
		WEATHERGLASS = new WeatherglassItem(() -> session.publisher(), props);
		Registry.register(BuiltInRegistries.ITEM, id, WEATHERGLASS);

		CreativeModeTabEvents.MODIFY_OUTPUT_ALL.register((tab, output) ->
				output.accept(new ItemStack(WEATHERGLASS), CreativeModeTab.TabVisibility.PARENT_AND_SEARCH_TABS));

		CommandRegistrationCallback.EVENT.register((dispatcher, buildContext, selection) -> {
			registerReadCommand(dispatcher);
			registerLifeCommand(dispatcher);
			registerStrideCommand(dispatcher);
		});
	}

	/** Register {@code /cassicraft read} — sample the field at the caller's position. */
	private static void registerReadCommand(CommandDispatcher<CommandSourceStack> dispatcher) {
		dispatcher.register(Commands.literal("cassicraft")
				.then(Commands.literal("read").executes(ctx -> runRead(ctx.getSource()))));
	}

	/**
	 * Register {@code /cassicraft life [x y z]} — collect a maintenance window at
	 * the given position (default: caller / spawn) and classify it. Blocking (≤ a
	 * few hundred ms) as it waits for fresh publishes; the domain worker keeps
	 * publishing even on an empty server, so the readout is verifiable headlessly.
	 */
	private static void registerLifeCommand(CommandDispatcher<CommandSourceStack> dispatcher) {
		dispatcher.register(Commands.literal("cassicraft")
				.then(Commands.literal("life")
						.executes(ctx -> runLife(ctx.getSource(), null))
						.then(Commands.argument("x", com.mojang.brigadier.arguments.IntegerArgumentType.integer())
								.then(Commands.argument("y", com.mojang.brigadier.arguments.IntegerArgumentType.integer())
										.then(Commands.argument("z", com.mojang.brigadier.arguments.IntegerArgumentType.integer())
												.executes(ctx -> runLife(ctx.getSource(), new int[] {
														com.mojang.brigadier.arguments.IntegerArgumentType.getInteger(ctx, "x"),
														com.mojang.brigadier.arguments.IntegerArgumentType.getInteger(ctx, "y"),
														com.mojang.brigadier.arguments.IntegerArgumentType.getInteger(ctx, "z"),
												})))))));
	}

	private static int runLife(CommandSourceStack source, int[] xyz) {
		if (CassiCraft.WEATHERGLASS == null) {
			source.sendFailure(Component.literal("The life reader is not armed (no world loaded)."));
			return 0;
		}
		BlockPos pos = xyz != null
				? new BlockPos(xyz[0], xyz[1], xyz[2])
				: fallbackPos(source);
		try {
			java.util.List<dev.cassicraft.game.sampler.Quantizer.FieldReading> window = LifeSignal.collectWindow(
					CassiCraft.WEATHERGLASS.publisherSupplier().get(),
					new double[] { 0, 0, 0 }, pos.getX(), pos.getY(), pos.getZ(),
					LifeSignal.WINDOW_LEN, 6000);
			LifeSignal.LifeReading life = LifeSignal.classify(window);
			source.sendSuccess(() -> Component.literal("Life @ (" + pos.getX() + "," + pos.getY() + "," + pos.getZ() + ")\n" + life.text()),
					false);
			return 1;
		} catch (IllegalStateException e) {
			source.sendFailure(Component.literal("The field never filled a maintenance window \u2014 not publishing yet."));
			return 0;
		} catch (InterruptedException e) {
			Thread.currentThread().interrupt();
			source.sendFailure(Component.literal("Life read interrupted."));
			return 0;
		}
	}

	/**
	 * Register {@code /cassicraft stride [x y z]} — read the stride-cost at a
	 * position (default caller / spawn). Headless-testable.
	 */
	private static void registerStrideCommand(CommandDispatcher<CommandSourceStack> dispatcher) {
		dispatcher.register(Commands.literal("cassicraft")
				.then(Commands.literal("stride")
						.executes(ctx -> runStride(ctx.getSource(), null))
						.then(Commands.argument("x", com.mojang.brigadier.arguments.IntegerArgumentType.integer())
								.then(Commands.argument("y", com.mojang.brigadier.arguments.IntegerArgumentType.integer())
										.then(Commands.argument("z", com.mojang.brigadier.arguments.IntegerArgumentType.integer())
												.executes(ctx -> runStride(ctx.getSource(), new int[] {
														com.mojang.brigadier.arguments.IntegerArgumentType.getInteger(ctx, "x"),
														com.mojang.brigadier.arguments.IntegerArgumentType.getInteger(ctx, "y"),
														com.mojang.brigadier.arguments.IntegerArgumentType.getInteger(ctx, "z"),
												})))))));
	}

	private static int runStride(CommandSourceStack source, int[] xyz) {
		if (CassiCraft.WEATHERGLASS == null) {
			source.sendFailure(Component.literal("The stride reader is not armed (no world loaded)."));
			return 0;
		}
		BlockPos pos = xyz != null
				? new BlockPos(xyz[0], xyz[1], xyz[2])
				: fallbackPos(source);
		dev.cassicraft.domain.snapshot.FieldSnapshot snap =
				CassiCraft.WEATHERGLASS.publisherSupplier().get().freshest();
		if (snap == null) {
			source.sendFailure(Component.literal("The field is not yet publishing."));
			return 0;
		}
		double[] center = snap.job() != null && !snap.job().isWindowless()
				? snap.job().windowCenter()
				: new double[] { 0, 0, 0 };
		// Standing (zero-step, zero-load) read so the command is a deterministic
		// headless probe; the live pass applies per-player motion + carried load.
		Quantizer.FieldReading r = Quantizer.sampleReading(snap, center, pos.getX(), pos.getY(), pos.getZ());
		MovementCost.StrideCost c = MovementCost.strideCost(r, 0, 0, 0, 0f);
		source.sendSuccess(() -> Component.literal("Stride @ (" + pos.getX() + "," + pos.getY() + "," + pos.getZ() + ")\n" + c.text()),
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

	private static int runRead(CommandSourceStack source) {
		BlockPos pos = fallbackPos(source);
		FieldReader.FieldReadout r = FieldReader.readFreshest(
				CassiCraft.WEATHERGLASS.publisherSupplier().get(),
				pos.getX(), pos.getY(), pos.getZ());
		if (r == null) {
			source.sendFailure(Component.literal("The Weatherglass is dark \u2014 the field is not yet publishing."));
			return 0;
		}
		source.sendSuccess(() -> Component.literal(r.text()), false);
		return 1;
	}
}
