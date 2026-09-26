package dev.cassicraft.game.practice;

import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.game.sampler.Quantizer;
import net.minecraft.core.BlockPos;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;

/**
 * The stilling/shout practice's client-visible presentation (the-stilling.md §4.2
 * the held quiet readable, the-shout.md §5e the loud readable — never hidden-only).
 * A <b>bounded, vanilla-only consumer</b>: on a named cadence it takes the corpus's
 * "one extra sample at the player's position" (field-instruments §1.4) for each
 * online player, classifies the local practice state via {@link StillingShoutRead},
 * and — when that position reads the practice's states — spawns ordinary Minecraft
 * particles at the player's vicinity only:
 *
 * <ul>
 *   <li><b>{@link StillingShoutRead.State#STILL}</b> — a calm coherent glow (the
 *       body's rest / a stilling's after-state) as the soft luminous
 *       {@link ParticleTypes#GLOW} — the coherent bulk's own luminescence, the
 *       still place the practitioner holds.</li>
 *   <li><b>{@link StillingShoutRead.State#WAKE}</b> — a vented wake (the shout's
 *       mark) as a small dense burst of {@link ParticleTypes#END_ROD} — the
 *       directed luminous wake the delivered coherence leaves before it re-locks
 *       (the-shout §2.3).</li>
 *   <li><b>{@link StillingShoutRead.State#CHURNED}</b> — a louder broken-lock read
 *       (perturbation present) as a wider {@link ParticleTypes#END_ROD} scatter —
 *       the danger the practicing body must steer back, never a seeded burst.</li>
 *   <li>{@code RETURNING} / {@code VOID} — no practice presentation (the field on
 *       its way back reads still-quiet; the void has nothing to show).</li>
 * </ul>
 *
 * <p><b>Discipline (only-mutator + no-free-energy):</b> this never writes a block
 * and never perturbs the field — the presentation is a pure consumer of the
 * published snapshot (deterministic in its still/wake/churned, fixed offsets, no
 * RNG), and provides nothing beyond the field's own read. With no publish yet it
 * skips; with no online player it is a no-op. This is the practice's <em>read</em>
 * face, the calm/wake the practitioner owns; the practice's <em>write</em> is
 * {@link StillingShoutCommand} through the real Q4 lane.
 */
public final class StillingShoutPresenter {

	/**
	 * [design] Cadence — present the practice states every this many server ticks
	 * (a bounded, glanceable read, not a per-tick stream; the family cadence the
	 * rain/atmo presenters use).
	 */
	public static final int PRESENT_EVERY_TICKS = 10;

	/** [design] The still's particle count per spawn tick — a soft, calm coherent glow. */
	public static final int STILL_PARTICLE_COUNT = 6;

	/** [design] The wake's particle count per spawn tick — a denser burst, the vent. */
	public static final int WAKE_PARTICLE_COUNT = 10;

	/** [design] The churned's particle count — a wider scatter, the broken lock. */
	public static final int CHURNED_PARTICLE_COUNT = 14;

	/** [design] Height above the player's feet where the practice presents (blocks). */
	public static final double PRESENT_HEIGHT = 2.0;

	/** [design] Radius of the practice presentation around the player (blocks). */
	public static final double PRESENT_RADIUS = 1.4;

	private final SnapshotPublisher publisher;

	public StillingShoutPresenter(SnapshotPublisher publisher) {
		this.publisher = publisher;
	}

	/** Called every server tick. Reads the published snapshot at each online
	 * player's position; spawns bounded vanilla particles when the local practice
	 * state is still / wake / churned. Read-only — never writes a block, never
	 * perturbs the field, never grants. */
	public void onServerTick(MinecraftServer server) {
		if (server.getTickCount() % PRESENT_EVERY_TICKS != 0) {
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
			StillingShoutRead.Read p = StillingShoutRead.classify(r);
			switch (p.state()) {
			case STILL -> presentStill(world, pos);
			case WAKE -> presentWake(world, pos);
			case CHURNED -> presentChurned(world, pos);
			default -> { /* RETURNING / VOID — no practice read to render. */ }
			}
		}
	}

	/**
	 * The still: a calm coherent {@code GLOW} above the player — the body's rest,
	 * fixed offsets (deterministic, no RNG), so the same field state yields the
	 * same still (the-stilling §5c).
	 */
	private static void presentStill(ServerLevel world, BlockPos pos) {
		double cx = pos.getX() + 0.5;
		double cy = pos.getY() + PRESENT_HEIGHT;
		double cz = pos.getZ() + 0.5;
		world.sendParticles(ParticleTypes.GLOW, cx, cy, cz,
				STILL_PARTICLE_COUNT, PRESENT_RADIUS * 0.3, 0.4, PRESENT_RADIUS * 0.3, 0.0);
	}

	/**
	 * The wake: a denser {@code END_ROD} burst — the vented delivered coherence
	 * the medium has not yet re-locked (the-shout §2.3). Fixed offsets.
	 */
	private static void presentWake(ServerLevel world, BlockPos pos) {
		double cx = pos.getX() + 0.5;
		double cy = pos.getY() + PRESENT_HEIGHT;
		double cz = pos.getZ() + 0.5;
		world.sendParticles(ParticleTypes.END_ROD, cx, cy, cz,
				WAKE_PARTICLE_COUNT, PRESENT_RADIUS * 0.5, 0.5, PRESENT_RADIUS * 0.5, 0.0);
	}

	/**
	 * The churned: a wider {@code END_ROD} scatter — the broken lock the
	 * practicing body must steer back. Fixed offsets, never a seeded burst.
	 */
	private static void presentChurned(ServerLevel world, BlockPos pos) {
		double cx = pos.getX() + 0.5;
		double cy = pos.getY() + PRESENT_HEIGHT;
		double cz = pos.getZ() + 0.5;
		world.sendParticles(ParticleTypes.END_ROD, cx, cy, cz,
				CHURNED_PARTICLE_COUNT, PRESENT_RADIUS, 0.7, PRESENT_RADIUS, 0.0);
	}
}
