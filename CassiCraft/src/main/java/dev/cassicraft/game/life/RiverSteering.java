package dev.cassicraft.game.life;

import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.game.sampler.Quantizer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.Mob;
import net.minecraft.world.entity.animal.Animal;

/**
 * The life response to the field — the river-law steering pass (field-emergent-
 * ecology.md §2.2). A <b>read-only consumer of the domain</b> that, each cadence,
 * nudges the passive animals (the chosen life class: {@link Animal}) toward the
 * horizontal river gradient {@code ∇(g·Φ)} sampled at their position — life
 * <em>drifts along the river the field already draws</em>.
 *
 * <p>This is <b>not</b> a power source: it steers along the existing gradient and
 * grants no speed, energy, or hidden stat — a reversible directional bias (if the
 * gradient reverses, the steer reverses; a body out of the field's reach is never
 * pulled). It never mutates the world's blocks (the only-mutator rule for block
 * state is absolute — the {@code dev.cassicraft.game.writer.WorldWriter} alone
 * writes blocks). The domain is read only through the public seam
 * ({@link SnapshotPublisher#freshest} → {@link Quantizer#sampleReading}).
 *
 * <p>Registered on the server tick at a cadence; one entry point shared with the
 * {@code /cassicraft life} readout.
 */
public final class RiverSteering {

	/** Cadence in server ticks — steer animals this often (spread the cost, §6 budget). */
	private static final int STEER_EVERY_TICKS = 20;
	/** Max degrees the facing is turned toward the river gradient per pass [design]. */
	private static final float MAX_TURN = 4.0f;
	/** Horizontal |∇(g·Φ)| below which the field is level and no steer applies. */
	private static final float STEER_FLOOR = 0.004f;

	private final SnapshotPublisher publisher;
	private long lastSteerTick = -1;

	public RiverSteering(SnapshotPublisher publisher) {
		this.publisher = publisher;
	}

	/** Called every server tick; steers on cadence. Pure read of the domain. */
	public void onServerTick(ServerLevel level, long tick) {
		if (tick - lastSteerTick < STEER_EVERY_TICKS) {
			return;
		}
		lastSteerTick = tick;
		FieldSnapshot snap = publisher.freshest();
		if (snap == null) {
			return;
		}
		double[] windowCenter = snap.job() != null && !snap.job().isWindowless()
				? snap.job().windowCenter()
				: new double[] { 0, 0, 0 };
		for (Entity e : level.getAllEntities()) {
			if (e instanceof Animal animal && animal.isAlive()) {
				steer(animal, snap, windowCenter);
			}
		}
	}

	private static void steer(Mob mob, FieldSnapshot snap, double[] windowCenter) {
		Quantizer.FieldReading r = Quantizer.sampleReading(snap, windowCenter,
				mob.getBlockX(), mob.getBlockY(), mob.getBlockZ());
		float gx = r.gradX();
		float gz = r.gradZ();
		double len = Math.sqrt(gx * (double) gx + gz * (double) gz);
		if (len < STEER_FLOOR) {
			return; // the field is level here — life has nothing to steer along
		}
		double riverBearing = Math.toDegrees(Math.atan2(-gx, -gz)); // downhill (the river's draw)
		double current = mob.getYRot();
		// Shortest circular angular turn toward the river bearing, clamped.
		double delta = (riverBearing - current + 540) % 360 - 180;
		if (delta > MAX_TURN) {
			delta = MAX_TURN;
		} else if (delta < -MAX_TURN) {
			delta = -MAX_TURN;
		}
		mob.setYRot((float) (current + delta));
	}
}
