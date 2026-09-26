package dev.cassicraft.game.ride;

import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.game.sampler.Quantizer;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.vehicle.minecart.Minecart;
import net.minecraft.world.level.entity.EntityTypeTest;
import net.minecraft.world.phys.AABB;
import net.minecraft.world.phys.Vec3;

/**
 * The ride's network-side tick hook (coherence-highway.md §6b — the Phase-1
 * <b>ride-downhill slice made a real ride</b>): a vanilla minecart that rides
 * the field's own river-law haul.
 *
 * <p>On every {@link #RIDE_EVERY_TICKS} server ticks, for each vanilla minecart
 * in the world whose position samples an <b>interior</b> field read (its position
 * maps to a grid coordinate inside the 192³ box — not out-of-box air), this
 * applies {@link RideHaul}'s engine-real haul {@code a = −G_N·(π/ρ)·∇(g·Φ)}
 * (sampled at the cart's position via {@link Quantizer#sampleReading} off the
 * freshest published snapshot) as a <b>bounded velocity delta</b> on the cart.
 * On flat or decoherent ground the haul contributes nothing honest — the cart
 * coasts to a stop, exactly as the probe measured (the flat-control epsilon of
 * {@code RideDeterminismMain}). On out-of-box air, or with no publish yet, the
 * cart rides as an ordinary vanilla minecart (the field ends at the box — honest).
 *
 * <p><b>Discipline (only-mutator + no-free-energy, held):</b>
 * <ul>
 *   <li>The only entity modification is the bounded velocity delta on minecarts —
 *       clamped per the engine's π/ρ bound and to a named per-tick delta cap so a
 *       single tick can never teleport the cart. Vanilla minecart physics otherwise
 *       (friction, collisions, riding) untouched. Never writes a block.</li>
 *   <li>The haul is the field's own ∇(g·Φ) (the probe proved it); the cart gains
 *       ONLY the engine-real haul. No mint, no speed floor, no "the road grants
 *       momentum", no energy.</li>
 *   <li>Bounded: iterates only vanilla minecarts, samples each interior position
 *       once per ride tick, and is a safe no-op with zero minecarts, no publish,
 *       or on the cadence gaps.</li>
 * </ul>
 *
 * <p>No mixins, no custom rendering (vanilla minecart model), no custom entity type —
 * Fabric events only (wired via the {@code CassiCraft.java} updater). The haul is
 * a pure function of the published channels (the deterministic ride gate threads
 * it), so the same field state yields the same haul on the cart.
 */
public final class MinecartRideCoordinator {

	/**
	 * Ride cadence — apply the haul every this many server ticks. A bounded,
	 * felt cadence (the field's publish cadence, not a per-tick stream); a
	 * cart is coasted by the field, not jittered every tick.
	 */
	public static final int RIDE_EVERY_TICKS = 2;

	/**
	 * The per-tick velocity-delta cap — one ride step may change a cart's
	 * velocity by this much at most, so no single tick can teleport the cart.
	 * The engine-real haul rarely approaches this: with π/ρ ≤ 0.72 and the
	 * probe's RIDE_DT = 0.05, a per-tick step of {@code |a|·0.05} stays well
	 * below it, and the cap is the honesty bound against a degenerate grad.
	 */
	public static final double MAX_DELTA_PER_TICK = 1.0;

	/**
	 * Iteration box — a wide AABB over the loaded world's minecarts. The field
	 * box is 192³ (96-extent); a minecart far outside (out-of-box air) rides
	 * vanilla anyway, but the iteration must still find every loaded cart.
	 */
	private static final double ITERATE_HALF = 4000.0;

	private static final AABB ITERATE_BOX =
			new AABB(-ITERATE_HALF, -ITERATE_HALF, -ITERATE_HALF, ITERATE_HALF, ITERATE_HALF, ITERATE_HALF);

	private final SnapshotPublisher publisher;

	public MinecartRideCoordinator(SnapshotPublisher publisher) {
		this.publisher = publisher;
	}

	/** Called every server tick; coasts each interior-field minecart down the haul. */
	public void onServerTick(MinecraftServer server) {
		if (server.getTickCount() % RIDE_EVERY_TICKS != 0) {
			return;
		}
		FieldSnapshot snap = publisher.freshest();
		ServerLevel overworld = server.overworld();
		if (snap == null || overworld == null) {
			return; // no publish yet — the ride waits, vanilla otherwise.
		}
		double[] center = snap.job() != null && !snap.job().isWindowless()
				? snap.job().windowCenter()
				: new double[] { 0, 0, 0 };
		java.util.List<Minecart> carts = overworld.getEntities(
				EntityTypeTest.forClass(Minecart.class), ITERATE_BOX, Minecart::isAlive);
		for (Minecart cart : carts) {
			applyHaul(snap, center, cart);
		}
	}

	/** Sample the field at the cart's position; apply the engine-real haul as a
	 * bounded velocity delta when the sample is interior field (not out-of-box air). */
	private static void applyHaul(FieldSnapshot snap, double[] center, Minecart cart) {
		Vec3 pos = cart.position();
		int bx = (int) Math.round(pos.x);
		int by = (int) Math.round(pos.y);
		int bz = (int) Math.round(pos.z);
		Quantizer.FieldReading r = Quantizer.sampleReading(snap, center, bx, by, bz);
		if (r.rho() <= 0f) {
			return; // out-of-box air — no field here, the cart rides vanilla (honest).
		}
		RideHaul.Haul haul = RideHaul.of(r);
		Vec3 v = cart.getDeltaMovement();
		double dvx = haul.ax() * RideHaul.RIDE_DT;
		double dvy = haul.ay() * RideHaul.RIDE_DT;
		double dvz = haul.az() * RideHaul.RIDE_DT;
		double dvMag = Math.sqrt(dvx * dvx + dvy * dvy + dvz * dvz);
		if (dvMag > MAX_DELTA_PER_TICK) {
			double s = MAX_DELTA_PER_TICK / dvMag;
			dvx *= s;
			dvy *= s;
			dvz *= s;
		}
		cart.setDeltaMovement(new Vec3(v.x + dvx, v.y + dvy, v.z + dvz));
	}
}
