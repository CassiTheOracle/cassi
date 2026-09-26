package dev.cassicraft.game.rain;

import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.game.sampler.Quantizer;
import net.minecraft.core.BlockPos;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;

/**
 * The gentle fall's client-visible presentation (the-rain §2, §7e — the
 * flood's beginning VISIBLE as the fall thickening). A <b>bounded, vanilla-only
 * consumer</b>: on every {@link #RAIN_SPAWN_EVERY_TICKS} server ticks it takes
 * the corpus's "one extra sample at the player's position" (field-instruments
 * §1.4) for each online player, classifies the local weather via
 * {@link RainRead}, and — when the player's position classifies a rain or its
 * flood's beginning — spawns ordinary Minecraft rain/droplet particles
 * ({@link ParticleTypes#RAIN} / {@link ParticleTypes#DRIPPING_WATER}) in a small
 * ring <em>above the player</em>, at the player's vicinity only. No custom
 * rendering, no mixins, no new channel — vanilla particles broadcast by the
 * server level.
 *
 * <p><b>The readable-before-it-arrives honesty made sensory:</b> when a
 * position classifies {@link RainRead.Weather#FLOODS_BEGINNING} the fall
 * <em>intensifies</em> (a higher named spawn rate) — the flood's beginning is
 * VISIBLE as the fall thickening, never hidden. When the position classifies
 * {@link RainRead.Weather#STORM_FRONT} or {@link RainRead.Weather#NO_RAIN} no
 * rain particles spawn (the front is the storm's wound, not the nourishing
 * fall; the dry state has no fall).
 *
 * <p><b>Discipline (only-mutator + no-free-energy):</b> this never writes a
 * block and never grants anything — the presentation is a pure consumer of the
 * published snapshot, deterministic in its fall (the-rain §7c), and provides
 * nothing beyond the field's own return (the-rain §7d). With no publish yet it
 * skips; with no online player it is a no-op.
 */
public final class RainPresenter {

	/**
	 * [design] Fall cadence — spawn rain particles every this many server ticks
	 * (a bounded, glanceable fall, not a per-tick stream); follows the publish's
	 * cadence, not 20 Hz.
	 */
	public static final int RAIN_SPAWN_EVERY_TICKS = 10;

	/** [design] The gentle fall's particle count per spawn tick (a soft, bounded fall). */
	public static final int RAIN_PARTICLE_COUNT = 12;

	/** [design] The flood's-beginning particle count per spawn tick — the fall thickens. */
	public static final int FLOOD_PARTICLE_COUNT = 24;

	/** [design] Ring radius around the player where the fall's droplets land (blocks). */
	public static final double RAIN_RING_RADIUS = 1.6;

	/** [design] Height above the player's feet where the fall spawns (blocks). */
	public static final double RAIN_FALL_HEIGHT = 3.0;

	private final SnapshotPublisher publisher;

	public RainPresenter(SnapshotPublisher publisher) {
		this.publisher = publisher;
	}

	/** Called every server tick. Reads the published snapshot at each online
	 * player's position; spawns bounded vanilla rain particles when the local
	 * weather is a fall. Read-only — never writes a block, never grants. */
	public void onServerTick(MinecraftServer server) {
		if (server.getTickCount() % RAIN_SPAWN_EVERY_TICKS != 0) {
			return;
		}
		FieldSnapshot snap = publisher.freshest();
		if (snap == null) {
			return;
		}
		double[] center = snap.job() != null && !snap.job().isWindowless()
				? snap.job().windowCenter()
				: new double[] { 0, 0, 0 };
		for (ServerPlayer player : server.getPlayerList().getPlayers()) {
			if (player.level() == null || !(player.level() instanceof ServerLevel world)) {
				continue;
			}
			BlockPos pos = player.blockPosition();
			Quantizer.FieldReading r = Quantizer.sampleReading(
					snap, center, pos.getX(), pos.getY(), pos.getZ());
			RainRead.WeatherRead w = RainRead.classify(r);
			switch (w.kind()) {
			case RAIN -> spawnFall(world, pos, RAIN_PARTICLE_COUNT);
			case FLOODS_BEGINNING -> spawnFall(world, pos, FLOOD_PARTICLE_COUNT);
			default -> { /* NO_RAIN / STORM_FRONT — no nourishing fall to render. */ }
			}
		}
	}

	/**
	 * Spawn vanilla rain/droplet particles in a small ring above the player's
	 * position — the player's vicinity only, never the whole window. The seven
	 * ring offsets are fixed (deterministic, no RNG), so the same field state
	 * yields the same fall (the-rain §7c).
	 */
	private static void spawnFall(ServerLevel world, BlockPos pos, int count) {
		double cx = pos.getX() + 0.5;
		double cy = pos.getY() + RAIN_FALL_HEIGHT;
		double cz = pos.getZ() + 0.5;
		double spread = RAIN_RING_RADIUS * 0.5;
		// A bounded ring of rain and the heavier droplets dripping off the fall.
		world.sendParticles(ParticleTypes.RAIN, cx, cy, cz, count, spread, 0.6, spread, 0.0);
		world.sendParticles(ParticleTypes.DRIPPING_WATER, cx - RAIN_RING_RADIUS, cy, cz,
				count / 3, 0.2, 0.4, 0.2, 0.0);
		world.sendParticles(ParticleTypes.DRIPPING_WATER, cx + RAIN_RING_RADIUS, cy, cz,
				count / 3, 0.2, 0.4, 0.2, 0.0);
	}
}
