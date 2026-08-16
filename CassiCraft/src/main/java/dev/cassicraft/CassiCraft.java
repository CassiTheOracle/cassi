package dev.cassicraft;

import dev.cassicraft.game.sampler.SamplerShutdown;
import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerLifecycleEvents;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerLevelEvents;
import net.fabricmc.fabric.api.event.lifecycle.v1.ServerTickEvents;
import net.minecraft.server.level.ServerLevel;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * MODULE 2/3/4 HOST — Minecraft entrypoint. Startup wiring only (BUILD-PLAN.md
 * §5, §7). Routes the server lifecycle into the four-module seam:
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
 * <p>This is the only host class that owns Minecraft wiring. Everything below the
 * seam (the {@code dev.cassicraft.domain} package) compiles against no Minecraft
 * symbol and is reached only through this entrypoint's handoff.
 */
public class CassiCraft implements ModInitializer {

	private static final Logger LOGGER = LoggerFactory.getLogger(CassiCraft.class);

	private final SamplerShutdown session = new SamplerShutdown();

	@Override
	public void onInitialize() {
		// World load → start the domain field thread + sampler + writer for this
		// world. The overworld is the Phase-1 substrate (its seed is the field seed).
		ServerLevelEvents.LOAD.register((server, level) -> {
			if (server.overworld() != level || session.isRunning()) {
				return; // only the overworld hosts the living-terrain seam, once
			}
			long seed = level.getSeed();
			long used = session.beginSession(level, seed);
			LOGGER.info("[cassicraft] field thread started for world (seed {}), sampler + writer armed", used);
		});

		// World unload → join the field worker (explicit close).
		ServerLevelEvents.UNLOAD.register((server, level) -> {
			if (server.overworld() == level || session.isRunning()) {
				session.endSession();
				LOGGER.info("[cassicraft] field thread closed (world unload)");
			}
		});

		// Server stop → release the session if a world never unloaded cleanly.
		ServerLifecycleEvents.SERVER_STOPPING.register(server -> {
			if (session.isRunning()) {
				session.endSession();
				LOGGER.info("[cassicraft] field thread closed (server stop)");
			}
		});

		// The server tick routes sampler → writer once per tick.
		ServerTickEvents.END_SERVER_TICK.register(server -> session.onServerTick(server));
	}
}
