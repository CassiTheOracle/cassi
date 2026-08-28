package dev.cassicraft.game.stride;

import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.game.sampler.Quantizer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.phys.Vec3;

/**
 * THE STRIDE COORDINATOR — the player's movement application of the stride
 * (designs/the-walk.md §2a/§3 "where to step": a step with the lean is cheap,
 * a step against it labors). The <b>player analog</b> of the ride's
 * {@code game/ride/MinecartRideCoordinator}: the minecart coasts the field's
 * own river-law haul; the walker reads the same published current and the
 * stride nudges their existing walk — never a second movement pass, never a
 * teleport, never a boost beyond the current's own aid.
 *
 * <p><b>The bounded stride law (honest, the-walk.md §4c/§4d):</b> on each
 * {@link #STRIDE_EVERY_TICKS} server tick, for each player standing on solid
 * field ground (the {@code walkability} pattern of {@code game/walk/} — the
 * sampled block is solid, {@code ρ ≥ Quantizer.TAU_C}) with an actual horizontal
 * walk intent, this applies the bounded stride nudge in the current's downhill
 * direction ({@code (−gradX, −gradZ)}, the same direction {@code RideHaul}
 * accelerates along). The delta is:
 * <pre>
 *   |Δv| = min(STRIDE_RIVER_FACTOR · |∇(g·Φ)_xz|, MAX_DELTA_PER_TICK)
 * </pre>
 * — at most a fixed fraction of the river itself, clamped (§4d guard 1). The
 * nudge acts in the current's direction, so walking <b>with</b> the current is
 * aided (positive), <b>against</b> is resisted (the current labors), standing
 * still / in the air / perpendicular gains nothing. It is a <b>read-driven
 * nudge of the existing walk</b> — the stride adds a bounded velocity delta to
 * the player's normal movement, never replaces it, never spawns a teleport.
 * On out-of-box air, no publish, or cadence gaps the stride contributes
 * nothing honest (the current's own aid is the ceiling).
 *
 * <p><b>The no-free-energy argument (the-walk.md §4d), stated once:</b> a
 * stride that "generates" momentum is a lie the cap forbids. Here the stride
 * grants exactly the current's own aid — a bounded fraction of the published
 * ∇(g·Φ) at the player's feet, the field doing the work it always does on a
 * body moving down-gradient. The stride never stores the descent (no capacitor,
 * §4d guard 1), never sheds into a harvestable drain (guard 2), and is not a
 * travel-mint (guard 3 — a step with the lean is cheap <em>movement</em>, never
 * a free-transport exploit). Max |Δv| ≤ min(0.04·|∇h|, 0.25) — measured on the
 * settled body (|∇(g·Φ)_xz| p95≈5.1) that is ≈0.20 m/s, a few percent of walk
 * speed, felt-but-bounded the whole stride, and <b>capped by the river itself</b>.
 *
 * <p><b>Deterministic</b> (the-walk.md §4c HARD): the nudge is a pure function
 * of the published snapshot and the player's position — the same field state
 * yields the same delta, never a seeded roll. The gate threads it headlessly.
 *
 * <p>No mixins, no custom rendering — Fabric server events only (wired via the
 * {@code CassiCraft.java} updater, the {@code rideCoordinator} pattern).
 */
public final class StrideCoordinator {

	/**
	 * Stride cadence — apply the bounded nudge every this many server ticks.
	 * The field's publish cadence, not a per-tick stream; the walk is nudged by
	 * the current, not jittered every tick (the ride's {@code RIDE_EVERY_TICKS}).
	 */
	public static final int STRIDE_EVERY_TICKS = 2;

	private final SnapshotPublisher publisher;
	private long lastStrideTick = -1;

	public StrideCoordinator(SnapshotPublisher publisher) {
		this.publisher = publisher;
	}

	/** Called every server tick; nudges each on-solid-ground walking player on the
	 * {@link #STRIDE_EVERY_TICKS} cadence (the {@code StrideCostPass} tick pattern). */
	public void onServerTick(ServerLevel level, long tick) {
		if (tick - lastStrideTick < STRIDE_EVERY_TICKS) {
			return;
		}
		lastStrideTick = tick;
		FieldSnapshot snap = publisher.freshest();
		if (snap == null) {
			return; // no publish yet — the stride waits, vanilla walking otherwise.
		}
		double[] center = snap.job() != null && !snap.job().isWindowless()
				? snap.job().windowCenter()
				: new double[] { 0, 0, 0 };
		for (ServerPlayer player : level.players()) {
			applyStride(snap, center, player);
		}
	}

	/** Sample the field at the player's position; apply the bounded stride nudge
	 * only when the player is walking on solid field ground. */
	private static void applyStride(FieldSnapshot snap, double[] windowCenter, ServerPlayer player) {
		if (!player.onGround()) {
			return; // in the air — never nudges a falling/jumping player (honest).
		}
		int bx = player.getBlockX();
		int by = player.getBlockY();
		int bz = player.getBlockZ();
		// Walkability (the game/walk pattern): stand on solid field ground, ρ ≥ τ_c.
		Quantizer.CellSample floor = Quantizer.sampleAt(snap, windowCenter, bx, by - 1, bz);
		if (floor.rho() < Quantizer.TAU_C) {
			return; // not field-solid ground — vanilla footing (air/water) untouched.
		}
		Quantizer.FieldReading r = Quantizer.sampleReading(snap, windowCenter, bx, by, bz);
		if (r.rho() <= 0f) {
			return; // out-of-box air — no field here (honest).
		}
		Vec3 vel = player.getDeltaMovement();
		// The player's horizontal walk intent — if they are essentially standing
		// still (no walk), the stride does not push them (standing is unaffected).
		double stepX = vel.x;
		double stepZ = vel.z;
		StrideRead.StrideReading stride = StrideRead.of(r, stepX, stepZ);
		if (stride.state() == StrideRead.StrideState.STILL_WATER) {
			return; // no coherent current, or standing/perpendicular — unaffected.
		}
		// Apply the bounded nudge in the current's downhill direction. The aid is
		// already min(factor·gradH, clamp) — the river's own aid, never more.
		double dvx = stride.currentX() * (double) stride.aidMag();
		double dvz = stride.currentZ() * (double) stride.aidMag();
		player.setDeltaMovement(new Vec3(vel.x + dvx, vel.y, vel.z + dvz));
	}
}
