package dev.cassicraft.game.sky;

import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.game.sampler.Quantizer;
import net.minecraft.core.BlockPos;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;

/**
 * The sky's client-visible presentation (atmosphere-orbits-auroras.md §3.3,
 * §1.5 — the atmosphere is a <b>visual/feel</b> layer; the sky is the field's
 * shape made visible). A <b>bounded, vanilla-only consumer</b>: on a named
 * cadence it takes the corpus's "one extra sample at the player's position"
 * (field-instruments §1.4) for each online player, classifies the local sky via
 * {@link SkyRead}, and — when that position reads a sky weather — spawns
 * ordinary Minecraft particles at the player's vicinity only. No custom
 * rendering, no sky-color/fog engine change, no mixins, no new channel —
 * vanilla particles broadcast by the server level.
 *
 * <p><b>The three bounded presentations</b>, each a deterministic spawn (fixed
 * offsets, no RNG density — only a named cadence, so the same field state
 * yields the same sky, atmosphere §5c):
 * <ul>
 *   <li><b>{@link SkyRead.Kind#GLOW}</b> — the glow as soft ambient light:
 *       {@link ParticleTypes#END_ROD} particles (a small bright rod, the aurora's
 *       source) drifting at a bounded rate in the player's vicinity.</li>
 *   <li><b>{@link SkyRead.Kind#STORM_EDGE}</b> — the darkening cue: <em>fewer but
 *       faster</em> {@link ParticleTypes#LARGE_SMOKE} particles (a dark,
 *       tightening shimmer) on a faster cadence — the leading edge reads as a
 *       darkening, never hidden (weather-not-storm §2, gate (e)).</li>
 *   <li><b>{@link SkyRead.Kind#FOG}</b> — the density fog as soft mist:
 *       {@link ParticleTypes#CLOUD} particles where {@code ρ} is dense.</li>
 * </ul>
 * {@link SkyRead.Kind#CLEAR} spawns nothing (the dry sky has no presentation).
 *
 * <p><b>Discipline (only-mutator + no-free-energy):</b> this never writes a
 * block and never grants anything — the presentation is a pure consumer of the
 * published snapshot, deterministic in its sky, and provides nothing beyond the
 * field's own read (atmosphere §5c). With no publish yet it skips; with no
 * online player it is a no-op. The full aurora — a rendered curtain — would need
 * a renderer and is a deferred [design] (atmosphere §6, later); Phase-1 presents
 * only the glow's <em>source</em> (where coherence concentrates) as bounded
 * vanilla light.
 */
public final class SkyPresenter {

	/**
	 * [design] Cadence — spawn sky particles every this many server ticks for
	 * the GLOW and FOG reads (a bounded, glanceable presentation, not a per-tick
	 * stream). The storm edge spawns on a faster cadence (see
	 * {@link #STORM_EDGE_CADENCE_TICKS}) to read as a dark tightening.
	 */
	public static final int SKY_SPAWN_EVERY_TICKS = 10;

	/** [design] The storm's-edge cadence — faster than the glow/fog (the darkening tightens). */
	public static final int STORM_EDGE_CADENCE_TICKS = 4;

	/** [design] The glow's particle count per spawn tick (a soft, bounded ambient light). */
	public static final int GLOW_PARTICLE_COUNT = 10;

	/** [design] The storm's-edge particle count per spawn tick — fewer, the darkening's sparseness. */
	public static final int STORM_EDGE_PARTICLE_COUNT = 6;

	/** [design] The fog's particle count per spawn tick (a soft, bounded mist). */
	public static final int FOG_PARTICLE_COUNT = 8;

	/** [design] Radius of the presentation ring around the player (blocks). */
	public static final double SKY_RING_RADIUS = 2.0;

	/** [design] Height above the player's feet where the sky's weather presents (blocks). */
	public static final double SKY_PRESENT_HEIGHT = 2.5;

	private final SnapshotPublisher publisher;

	public SkyPresenter(SnapshotPublisher publisher) {
		this.publisher = publisher;
	}

	/** Called every server tick. Reads the published snapshot at each online
	 * player's position; spawns bounded vanilla particles when the local sky is
	 * a weather. Read-only — never writes a block, never grants. */
	public void onServerTick(MinecraftServer server) {
		FieldSnapshot snap = publisher.freshest();
		if (snap == null || server.getTickCount() == 0) {
			return;
		}
		double[] center = snap.job() != null && !snap.job().isWindowless()
				? snap.job().windowCenter()
				: new double[] { 0, 0, 0 };
		boolean stormCadence = server.getTickCount() % STORM_EDGE_CADENCE_TICKS == 0;
		boolean glowCadence = server.getTickCount() % SKY_SPAWN_EVERY_TICKS == 0;
		for (ServerPlayer player : server.getPlayerList().getPlayers()) {
			if (player.level() == null || !(player.level() instanceof ServerLevel world)) {
				continue;
			}
			BlockPos pos = player.blockPosition();
			Quantizer.FieldReading r = Quantizer.sampleReading(
					snap, center, pos.getX(), pos.getY(), pos.getZ());
			SkyRead.Read s = SkyRead.classify(r);
			switch (s.kind()) {
			case GLOW -> { if (glowCadence) spawnGlow(world, pos); }
			case STORM_EDGE -> { if (stormCadence) spawnStormEdge(world, pos); }
			case FOG -> { if (glowCadence) spawnFog(world, pos); }
			default -> { /* CLEAR — the dry sky has no presentation. */ }
			}
		}
	}

	/**
	 * The glow: a bounded spread of {@code END_ROD} ambient-light particles above
	 * the player — the aurora's source. Fixed ring offsets (deterministic, no
	 * RNG), so the same field state yields the same glow.
	 */
	private static void spawnGlow(ServerLevel world, BlockPos pos) {
		double cx = pos.getX() + 0.5;
		double cy = pos.getY() + SKY_PRESENT_HEIGHT;
		double cz = pos.getZ() + 0.5;
		world.sendParticles(ParticleTypes.END_ROD, cx, cy, cz,
				GLOW_PARTICLE_COUNT, SKY_RING_RADIUS * 0.35, 0.4, SKY_RING_RADIUS * 0.35, 0.0);
	}

	/**
	 * The storm's edge: a <em>sparse</em> dark smoke read — fewer particles on
	 * the faster storm cadence, reading as the dark tightening of the front's
	 * leading edge. Fixed offsets (deterministic), no RNG density.
	 */
	private static void spawnStormEdge(ServerLevel world, BlockPos pos) {
		double cx = pos.getX() + 0.5;
		double cy = pos.getY() + SKY_PRESENT_HEIGHT;
		double cz = pos.getZ() + 0.5;
		world.sendParticles(ParticleTypes.LARGE_SMOKE, cx, cy, cz,
				STORM_EDGE_PARTICLE_COUNT, SKY_RING_RADIUS * 0.5, 0.3, SKY_RING_RADIUS * 0.5, 0.0);
	}

	/**
	 * The fog: a bounded spread of {@code CLOUD} mist particles where the field's
	 * density is high — the sky's thickness. Fixed offsets (deterministic).
	 */
	private static void spawnFog(ServerLevel world, BlockPos pos) {
		double cx = pos.getX() + 0.5;
		double cy = pos.getY() + SKY_PRESENT_HEIGHT * 0.5;
		double cz = pos.getZ() + 0.5;
		world.sendParticles(ParticleTypes.CLOUD, cx, cy, cz,
				FOG_PARTICLE_COUNT, SKY_RING_RADIUS, 0.5, SKY_RING_RADIUS, 0.0);
	}
}
