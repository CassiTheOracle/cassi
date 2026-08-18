package dev.cassicraft;

import com.mojang.brigadier.CommandDispatcher;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.game.advect.FollowBehind;
import dev.cassicraft.game.life.LifeSignal;
import dev.cassicraft.game.life.RiverSteering;
import dev.cassicraft.game.lume.LumePayload;
import dev.cassicraft.game.lume.LumePusher;
import dev.cassicraft.game.reader.FieldReader;
import dev.cassicraft.game.reader.WeatherglassItem;
import dev.cassicraft.game.expedition.ExpeditionCoordinator;
import dev.cassicraft.game.onboarding.OnboardingCoordinator;
import dev.cassicraft.game.onboarding.OnboardingPresenter;
import dev.cassicraft.game.rain.RainPresenter;
import dev.cassicraft.game.rain.WeatherReadout;
import dev.cassicraft.game.sampler.SamplerShutdown;
import dev.cassicraft.game.sampler.Quantizer;
import dev.cassicraft.game.spawn.SurfaceSpawn;
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

	/** The single Q4 write-path handle — the session's field worker, set at world
	 * load and nulled on teardown (the practice commands submit bounded matched-φ
	 * writes through {@code CassiFieldThread.submitPerturbation}; the lane is the
	 * only write path — this is never the solver, never a block write). */
	public static dev.cassicraft.domain.thread.CassiFieldThread FIELD_THREAD;

	private final SamplerShutdown session = new SamplerShutdown();
	private OnboardingCoordinator onboardingCoordinator;
	private ExpeditionCoordinator expeditionCoordinator;
	/** Temporary read-only local wayfinding for active expeditions. */
	private dev.cassicraft.game.beacon.ExpeditionBeaconCoordinator expeditionBeacon;

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

	/** The wind's particle-drift coordinator (the-wind.md §7 gate (b); created per-session, nulled on teardown). */
	private dev.cassicraft.game.wind.WindDriftParticles windDrift;

	/** The gentle fall's particle presenter (created per-session, nulled on teardown). */
	private RainPresenter rainPresenter;

	/** The sky's particle presenter (created per-session, nulled on teardown). */
	private dev.cassicraft.game.sky.SkyPresenter skyPresenter;

	/** The atmosphere field phenomena's aurora presenter — the (1−q) discharge
	 * over a rising-ε² drain (atmosphere §3.1; created per-session, nulled on teardown). */
	private dev.cassicraft.game.atmo.AtmoPresenter atmoPresenter;

	/** The stilling/shout practice's particle presenter — the body's rest / the
	 * vented wake read at each player position (the-stilling §4.2, the-shout §5e;
	 * created per-session, nulled on teardown). */
	private dev.cassicraft.game.practice.StillingShoutPresenter stillingShoutPresenter;

	/** The energy-harnessing practice's particle presenter — the spendable
	 * coherence (READY) / the exhausted budget (SPENT) read at each player
	 * position, and the draw's bounded burst at the draw point (energy-harnessing
	 * §0/§6; created per-session, nulled on teardown). */
	private dev.cassicraft.game.energy.HarnessPresenter harnessPresenter;

	/** The signature-predator tick coordinator — attaches the live publish handoff
	 * to every loaded predicate so its tick reads the field's signature gradient
	 * (signature-predator.md §8; created per-session, nulled on teardown). */
	private dev.cassicraft.game.predator.PredatorTickCoordinator predatorCoordinator;

	/** The ride coordinator — applies the field's own river-law haul to vanilla
	 * minecarts on the field (coherence-highway §6b; created per-session, nulled on teardown). */
	private dev.cassicraft.game.ride.MinecartRideCoordinator rideCoordinator;

	/** The stride coordinator — a bounded nudge of each player's walk along the
	 * field's own horizontal ∇(g·Φ) current, only on solid ground (the-walk.md §2a;
	 * the ride's player-analog; created per-session, nulled on teardown). */
	private dev.cassicraft.game.stride.StrideCoordinator strideCoordinator;

	@Override
	public void onInitialize() {
		dev.cassicraft.game.predator.PredatorRegistration.register();
		net.fabricmc.fabric.api.object.builder.v1.entity.FabricDefaultAttributeRegistry.register(
				dev.cassicraft.game.predator.PredatorRegistration.TYPE,
				dev.cassicraft.game.predator.SignaturePredatorEntity.createAttributes());
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
			expeditionCoordinator = new ExpeditionCoordinator(session.publisher());
			expeditionBeacon = new dev.cassicraft.game.beacon.ExpeditionBeaconCoordinator(expeditionCoordinator);
			onboardingCoordinator = new OnboardingCoordinator();
			expeditionCoordinator.setCompletionObserver(player -> {
				OnboardingCoordinator onboarding = onboardingCoordinator;
				if (onboarding != null) {
					OnboardingPresenter.presentCompletion(player, onboarding);
				}
			});
			dev.cassicraft.CassiCraft.FIELD_THREAD = session.fieldThread();
			followBehind = new FollowBehind(session.publisher(), session.fieldThread());
			lumePusher = new LumePusher(WEATHERGLASS, session.publisher());
			rainPresenter = new RainPresenter(session.publisher());
			steering = new RiverSteering(session.publisher());
			strideCost = new StrideCostPass(session.publisher());
			surfaceSpawn = new SurfaceSpawn(session.publisher(), anchor);
			windDrift = new dev.cassicraft.game.wind.WindDriftParticles(session.publisher());
			rideCoordinator = new dev.cassicraft.game.ride.MinecartRideCoordinator(session.publisher());
			strideCoordinator = new dev.cassicraft.game.stride.StrideCoordinator(session.publisher());
			skyPresenter = new dev.cassicraft.game.sky.SkyPresenter(session.publisher());
			atmoPresenter = new dev.cassicraft.game.atmo.AtmoPresenter(session.publisher());
			stillingShoutPresenter = new dev.cassicraft.game.practice.StillingShoutPresenter(session.publisher());
			harnessPresenter = new dev.cassicraft.game.energy.HarnessPresenter(session.publisher());
			predatorCoordinator = new dev.cassicraft.game.predator.PredatorTickCoordinator(session.publisher());
			LOGGER.info("[cassicraft] field thread started for world (seed {}), window anchored at ({},{},{}), follow coordinator attached",
					used, (int) anchor[0], (int) anchor[1], (int) anchor[2]);
		});

		ServerLevelEvents.UNLOAD.register((server, level) -> {
			if (server.overworld() == level || session.isRunning()) {
				if (onboardingCoordinator != null) {
					onboardingCoordinator.clearSession();
					onboardingCoordinator = null;
				}
				if (expeditionBeacon != null) {
					expeditionBeacon.teardown();
					expeditionBeacon = null;
				}
				if (expeditionCoordinator != null) {
					expeditionCoordinator.teardown();
					expeditionCoordinator = null;
				}
				session.endSession();
				followBehind = null;
				dev.cassicraft.CassiCraft.FIELD_THREAD = null;
				lumePusher = null;
				steering = null;
				strideCost = null;
				surfaceSpawn = null;
				rainPresenter = null;
				windDrift = null;
				skyPresenter = null;
				rideCoordinator = null;
				strideCoordinator = null;
				atmoPresenter = null;
				stillingShoutPresenter = null;
				harnessPresenter = null;
				predatorCoordinator = null;
				LOGGER.info("[cassicraft] field thread closed (world unload)");
			}
		});
		ServerLifecycleEvents.SERVER_STOPPING.register(server -> {
			if (session.isRunning()) {
				if (onboardingCoordinator != null) {
					onboardingCoordinator.clearSession();
					onboardingCoordinator = null;
				}
				if (expeditionBeacon != null) {
					expeditionBeacon.teardown();
					expeditionBeacon = null;
				}
				if (expeditionCoordinator != null) {
					expeditionCoordinator.teardown();
					expeditionCoordinator = null;
				}
				session.endSession();
				followBehind = null;
				dev.cassicraft.CassiCraft.FIELD_THREAD = null;
				lumePusher = null;
				steering = null;
				strideCost = null;
				surfaceSpawn = null;
				rainPresenter = null;
				windDrift = null;
				skyPresenter = null;
				rideCoordinator = null;
				strideCoordinator = null;
				atmoPresenter = null;
				stillingShoutPresenter = null;
				harnessPresenter = null;
				predatorCoordinator = null;
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
			if (expeditionCoordinator != null) {
				expeditionCoordinator.tick(server);
			}
			if (expeditionBeacon != null) {
				expeditionBeacon.onServerTick(server);
			}
			if (followBehind != null) {
				followBehind.onServerTick(server.overworld());
			}
			if (lumePusher != null) {
				lumePusher.onServerTick(server);
			}
			if (rainPresenter != null) {
				rainPresenter.onServerTick(server);
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
			if (windDrift != null) {
				windDrift.onServerTick(server);
			}
			if (rideCoordinator != null) {
				rideCoordinator.onServerTick(server);
			}
			if (strideCoordinator != null) {
				strideCoordinator.onServerTick(server.overworld(), server.getTickCount());
			}
			if (skyPresenter != null) {
				skyPresenter.onServerTick(server);
			}
			if (atmoPresenter != null) {
				atmoPresenter.onServerTick(server);
			}
			if (predatorCoordinator != null) {
				predatorCoordinator.onServerTick(server);
			}
			if (stillingShoutPresenter != null) {
				stillingShoutPresenter.onServerTick(server);
			}
			if (harnessPresenter != null) {
				harnessPresenter.onServerTick(server);
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
		WEATHERGLASS = new WeatherglassItem(() -> session.publisher(), () -> expeditionCoordinator, props);
		Registry.register(BuiltInRegistries.ITEM, id, WEATHERGLASS);

		CreativeModeTabEvents.MODIFY_OUTPUT_ALL.register((tab, output) ->
				output.accept(new ItemStack(WEATHERGLASS), CreativeModeTab.TabVisibility.PARENT_AND_SEARCH_TABS));

		CommandRegistrationCallback.EVENT.register((dispatcher, buildContext, selection) -> {
			registerReadCommand(dispatcher);
			registerLifeCommand(dispatcher);
			registerStrideCommand(dispatcher);
			registerWindCommand(dispatcher);
			registerWeatherCommand(dispatcher);
			registerMaterialCommand(dispatcher);
			registerRideCommand(dispatcher);
			registerSkyCommand(dispatcher);
			registerAtmoCommand(dispatcher);
			registerFieldGlassCommand(dispatcher);
			registerStillingShoutCommand(dispatcher);
			registerPredatorCommand(dispatcher);
			registerHarnessCommand(dispatcher);
			registerSeamCommand(dispatcher);
		});
	}

	/** Register {@code /cassicraft read} — sample the field at the caller's position. */
	private static void registerReadCommand(CommandDispatcher<CommandSourceStack> dispatcher) {
		dispatcher.register(Commands.literal("cassicraft")
				.then(Commands.literal("read").executes(ctx -> runRead(ctx.getSource()))));
	}

	/**
	 * Register {@code /cassicraft wind} — the wind (the directional weather, a
	 * pure consumer of the published ∇(g·Φ) via the Weatherglass publisher) at
	 * the caller's position or an explicit block.
	 */
	private static void registerWindCommand(CommandDispatcher<CommandSourceStack> dispatcher) {
		dev.cassicraft.game.wind.WindCommand.register(dispatcher);
	}

	/** Register {@code /cassicraft material [x y z]} — the real-element material
	 * read (the governing constant tuple + phase verdict) at the caller's
	 * position or an explicit block (a pure consumer of the publish, never a write). */
	private static void registerMaterialCommand(CommandDispatcher<CommandSourceStack> dispatcher) {
		dev.cassicraft.game.material.MaterialCommand.register(dispatcher);
	}

	/** Register {@code /cassicraft sky [x y z]} — the sky's read (the glow /
	 * storm-edge darkening / density-fog, atmosphere §3.3) at the caller's
	 * position or an explicit block (a pure consumer of the publish, never a write). */
	private static void registerSkyCommand(CommandDispatcher<CommandSourceStack> dispatcher) {
		dev.cassicraft.game.sky.SkyCommand.register(dispatcher);
	}

	/** Register {@code /cassicraft atmo [x y z]} — the atmosphere's field read
	 * (the aurora's (1−q) discharge, the body-seed orbit well, the envelope's
	 * gas band, atmosphere §3.1/§3.3) at the caller's position or an explicit
	 * block (a pure consumer of the publish, never a write). */
	private static void registerAtmoCommand(CommandDispatcher<CommandSourceStack> dispatcher) {
		dev.cassicraft.game.atmo.AtmoCommand.register(dispatcher);
	}

	/** Register {@code /cassicraft fieldglass [x y z]} — the FieldGlass read (the
	 * five published channels: lume q, depth ρ, strain ε², the river ∇(g·Φ)'s
	 * lean, the (1−q) waste — plus the governing material regime, the TIER-REAL
	 * rung and [design] constants, material-regimes §1/§4) at the caller's
	 * position or an explicit block (a pure consumer of the publish, never a write). */
	private static void registerFieldGlassCommand(CommandDispatcher<CommandSourceStack> dispatcher) {
		dev.cassicraft.game.instrument.FieldGlassCommand.register(dispatcher);
	}

	/**
	 * Register {@code /cassicraft predator} — spawn a signature predator at the
	 * caller's position, or toggle the live predator population (the field-as-AI,
	 * embodied; signature-predator.md §8 — it hunts the field's signature
	 * gradient, a pure read of the published q/ε², never the player's coordinates).
	 */
	private static void registerPredatorCommand(CommandDispatcher<CommandSourceStack> dispatcher) {
		dev.cassicraft.game.predator.PredatorCommand.register(dispatcher);
	}

	/** Register {@code /cassicraft harness [x y z]}
	 * — the energy-harnessing practice's bounded, cap-governed coherence draw
	 * through the REAL Q4 player-return lane (energy-harnessing §0/§2.5/§6;
	 * q4-write-lane-design §3): the matched-φ withdrawal spends a bounded budget
	 * of the local field's coherence on a real use (a mining burst), never a mint. */
	private static void registerHarnessCommand(CommandDispatcher<CommandSourceStack> dispatcher) {
		dev.cassicraft.game.energy.HarnessCommand.register(dispatcher);
	}

	/**
	 * Register {@code /cassicraft seam [x y z]} — the world-seam read (world-seams.md
	 * §1.3/§4.2; the {@code SeamProbeMain} verdict SUPPORTS, so the read is honest): the
	 * player's local window position (offset + grid cell from the live window center) and
	 * the seam state (INTERIOR / EDGE_BAND within {@code SeamRead.EDGE_BAND_BLOCKS} m of
	 * the window boundary) at the caller's position or an explicit block — a pure consumer
	 * of the publish, never a write, never a phantom "edge of the world".
	 */
	private static void registerSeamCommand(CommandDispatcher<CommandSourceStack> dispatcher) {
		dispatcher.register(Commands.literal("cassicraft")
				.then(Commands.literal("seam")
						.executes(ctx -> runSeam(ctx.getSource(), null))
						.then(Commands.argument("x", com.mojang.brigadier.arguments.IntegerArgumentType.integer())
								.then(Commands.argument("y", com.mojang.brigadier.arguments.IntegerArgumentType.integer())
										.then(Commands.argument("z", com.mojang.brigadier.arguments.IntegerArgumentType.integer())
												.executes(ctx -> runSeam(ctx.getSource(), new int[] {
														com.mojang.brigadier.arguments.IntegerArgumentType.getInteger(ctx, "x"),
														com.mojang.brigadier.arguments.IntegerArgumentType.getInteger(ctx, "y"),
														com.mojang.brigadier.arguments.IntegerArgumentType.getInteger(ctx, "z"),
												})))))));
	}

	private static int runSeam(CommandSourceStack source, int[] xyz) {
		if (CassiCraft.WEATHERGLASS == null) {
			source.sendFailure(Component.literal("The seam reader is not armed (no world loaded)."));
			return 0;
		}
		BlockPos pos = xyz != null
				? new BlockPos(xyz[0], xyz[1], xyz[2])
				: fallbackPos(source);
		dev.cassicraft.game.seams.SeamRead.SeamReadout r = dev.cassicraft.game.seams.SeamRead.readFreshest(
				CassiCraft.WEATHERGLASS.publisherSupplier().get(),
				pos.getX(), pos.getY(), pos.getZ());
		if (r == null) {
			source.sendFailure(Component.literal("The world is not yet publishing \u2014 the field has not shipped its first window."));
			return 0;
		}
		source.sendSuccess(() -> Component.literal(r.text()), false);
		return 1;
	}

	/** Register {@code /cassicraft still [x y z]} and {@code /cassicraft shout [x y z]}
	 * — the practice's bounded matched-φ writes through the REAL Q4 player-return
	 * lane (async-field-domain §7 Q4; q4-write-lane-design §3): still = the
	 * coherence-restoring hold, shout = the coherence-delivering wake. The lane is
	 * the only write path — a pure Q4 consumer, never a block write, never a mint. */
	private static void registerStillingShoutCommand(CommandDispatcher<CommandSourceStack> dispatcher) {
		dev.cassicraft.game.practice.StillingShoutCommand.register(dispatcher);
	}

	/**
	 * Register {@code /cassicraft ride} — the ride's readable-from-the-instruments
	 * read (coherence-highway §6e): the engine-real haul at the caller's position
	 * or an explicit block (or the nearest minecart), a pure consumer of the
	 * published ∇(g·Φ), never a write.
	 */
	private static void registerRideCommand(CommandDispatcher<CommandSourceStack> dispatcher) {
		dev.cassicraft.game.ride.RideCommand.register(dispatcher);
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

	/** Register {@code /cassicraft stride [x y z]} — the stride's read of the
	 * field's river + stride state at the caller's position or an explicit block,
	 * a pure consumer of the published ∇(g·Φ) (never a write, never a movement pass). */
	private static void registerStrideCommand(CommandDispatcher<CommandSourceStack> dispatcher) {
		dev.cassicraft.game.stride.StrideCommand.register(dispatcher);
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

	/** Register {@code /cassicraft weather} — read the local weather at the caller's position. */
	private static void registerWeatherCommand(CommandDispatcher<CommandSourceStack> dispatcher) {
		dispatcher.register(Commands.literal("cassicraft")
				.then(Commands.literal("weather").executes(ctx -> runWeather(ctx.getSource()))));
	}

	private static int runWeather(CommandSourceStack source) {
		BlockPos pos = fallbackPos(source);
		String text = WeatherReadout.readFreshest(
				CassiCraft.WEATHERGLASS.publisherSupplier().get(),
				pos.getX(), pos.getY(), pos.getZ());
		if (text == null) {
			source.sendFailure(Component.literal("The Weatherglass is dark \u2014 the field is not yet publishing."));
			return 0;
		}
		source.sendSuccess(() -> Component.literal(text), false);
		return 1;
	}
}
