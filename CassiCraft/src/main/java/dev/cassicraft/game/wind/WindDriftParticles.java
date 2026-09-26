package dev.cassicraft.game.wind;

import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;

import java.util.Random;

/**
 * The wind's client-visible presentation (the-wind.md §7 gate (b) — a bounded
 * directional transport read, rendered as a moving current with a mouth-and-tail).
 *
 * <p>On each server tick it reads the wind at the first online player's position
 * (the {@link WindRead} pure classifier over the published snapshot, the seam —
 * never a raw buffer) and, when the local current is above the measured noise
 * floor, spawns a bounded number of <b>vanilla</b> cloud particles in a short
 * band along the current's direction — the "mouth-and-tail": the band reads as
 * a current moving <em>with</em> the flow, the tail trailing upwind and the
 * mouth leading downwind. Ordinary {@link ParticleTypes#CLOUD} particles, no
 * custom rendering, no mixins; the client renders them from the server's
 * {@link ServerLevel#sendParticles} broadcast.
 *
 * <p>Honesty rules, held:
 * <ul>
 *   <li><b>CALM = no particles</b> — when the wind reads CALM there is honestly
 *       no current, so nothing spawns (never a fake breeze).</li>
 *   <li><b>Never writes, never grants</b> — particles are presentation only; the
 *       wind provides nothing (the no-free-energy cap, the-wind.md §5d). No
 *       block mutation, no velocity, no mint.</li>
 *   <li><b>Bounded</b> — a named per-tick particle budget, near the player's own
 *       vicinity only, never the whole window, and only when the field is
 *       publishing.</li>
 * </ul>
 */
public final class WindDriftParticles {

	/** The vanilla particle — a soft drifting cloud (reads as a current, not a firework). */
	private static final net.minecraft.core.particles.ParticleOptions PARTICLE = ParticleTypes.CLOUD;

	/**
	 * [design] Max particles to spawn per online player per tick — a bounded,
	 * small budget (the doc's "bounded band", field-instruments.md §1.4's sample
	 * cost profile). Presentation only, never a cost the server feels.
	 */
	public static final int PARTICLES_PER_TICK = 4;

	/**
	 * [design] Length of the mouth-and-tail band, in blocks along the current
	 * direction — the tail trails upwind (offset −dir·len/2 … +dir·len/2), so a
	 * short line of clouds reads as a directional current.
	 */
	public static final float BAND_BLOCKS = 3.0f;

	/** [design] Spawn cadence — spawn every Nth tick (bounded server cost). */
	private static final int CADENCE_TICKS = 2;

	/** A small local RNG for particle placement along the band (presentation only, never feeds the read). */
	private static final Random RNG = new Random();

	private final SnapshotPublisher publisher;

	public WindDriftParticles(SnapshotPublisher publisher) {
		this.publisher = publisher;
	}

	/** Called every server tick; spawns the current's particles for online players. */
	public void onServerTick(MinecraftServer server) {
		FieldSnapshot snap = publisher.freshest();
		ServerLevel overworld = server.overworld();
		if (snap == null || overworld == null || (server.getTickCount() % CADENCE_TICKS) != 0) {
			return;
		}
		double[] center = snap.job() != null && !snap.job().isWindowless()
				? snap.job().windowCenter()
				: new double[] { 0, 0, 0 };
		for (ServerPlayer p : overworld.players()) {
			net.minecraft.core.BlockPos pos = p.blockPosition();
			WindRead.WindReading w = WindRead.read(snap, center, pos.getX(), pos.getY(), pos.getZ());
			if (w.isCalm()) {
				continue; // honest CALM — no current, no particles.
			}
			spawnBand(overworld, pos, w);
		}
	}

	/** Spawn a short line of cloud particles along the current's horizontal direction. */
	private static void spawnBand(ServerLevel level, net.minecraft.core.BlockPos pos, WindRead.WindReading w) {
		double gx = w.gradX();
		double gz = w.gradZ();
		double len = Math.sqrt(gx * gx + gz * gz);
		if (len < 1e-9) {
			return;
		}
		double dx = gx / len;
		double dz = gz / len;
		double half = BAND_BLOCKS * 0.5;
		double px = pos.getX() + 0.5;
		double py = pos.getY() + 0.5;
		double pz = pos.getZ() + 0.5;
		for (int i = 0; i < PARTICLES_PER_TICK; i++) {
			double t = -half + RNG.nextDouble() * BAND_BLOCKS;
			level.sendParticles(PARTICLE, px + dx * t, py, pz + dz * t,
					1, 0.15, 0.1, 0.15, 0.02);
		}
	}
}
