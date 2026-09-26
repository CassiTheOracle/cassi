package dev.cassicraft.game.energy;

import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.game.sampler.Quantizer;
import net.minecraft.core.BlockPos;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;

/**
 * The energy-harnessing practice's client-visible presentation
 * (energy-harnessing §0 the field operations are the machines; the draw is a
 * visible spend, never hidden-only). A <b>bounded, vanilla-only consumer</b>
 * with two faces:
 *
 * <ul>
 *   <li><b>The draw's presentation</b> ({@link #presentDraw} — called by
 *       {@link HarnessCommand#draw} at the draw point): a small, fixed,
 *       deterministic vanilla-particle burst marking where the coherence was
 *       withdrawn — the {@code END_ROD} droplet of the spent order drifting
 *       down, bounded and never a seeded scatter. When the draw bought a
 *       mining burst, a {@code GLOW} lifts from the point (the released
 *       coherence the player channels); with no burst (the draw too thin) only
 *       the spent droplet shows.</li>
 *   <li><b>The held presentation</b> ({@link #onServerTick} — a per-session,
 *       cadence-hooked glance at each online player's position): when the local
 *       point reads {@link HarnessRead.State#READY} a soft {@code GLOW} marks
 *       the spendable coherence (the harness's fuel is visible); a
 *       {@code SPENT} point shows the exhausted {@code ASH} cast — where the
 *       field has already paid. A cadence gate, same fixed offsets, no RNG —
 *       deterministic (the harness gate's determinism, energy-harnessing §6 as
 *       coded in the lane).</li>
 * </ul>
 *
 * <p><b>Discipline (only-mutator + no-free-energy):</b> this never writes a
 * block and never perturbs the field — the presentation is a pure consumer of
 * the published snapshot (deterministic, fixed offsets, no RNG), and provides
 * nothing beyond the field's own read. With no publish yet it skips; with no
 * online player it is a no-op. The harness's <em>write</em> is
 * {@link HarnessCommand} through the real Q4 lane; the presenter only frames
 * the draw.
 */
public final class HarnessPresenter {

	/**
	 * [design] The held-presentation cadence — present the harness states every
	 * this many server ticks (a bounded, glanceable read, not a per-tick stream;
	 * the rain/atmo practice-presenter cadence).
	 */
	public static final int PRESENT_EVERY_TICKS = 10;

	/** [design] The draw burst's spent-droplet particle count — a small, bounded mark. */
	public static final int DRAW_ROD_COUNT = 6;

	/** [design] The draw burst's lifted-glow particle count — the released coherence, bounded. */
	public static final int DRAW_GLOW_COUNT = 8;

	/** [design] The READY hold's glow count — a soft, calm spendable-coherence mark. */
	public static final int READY_GLOW_COUNT = 5;

	/** [design] The SPENT hold's ash count — the exhausted budget's cast. */
	public static final int SPENT_ASH_COUNT = 4;

	/** [design] Height above the draw point where the presentation sits (blocks). */
	public static final double PRESENT_HEIGHT = 1.5;

	/** [design] Radius of the presentation around the draw point (blocks). */
	public static final double PRESENT_RADIUS = 1.2;

	private final SnapshotPublisher publisher;

	public HarnessPresenter(SnapshotPublisher publisher) {
		this.publisher = publisher;
	}

	/**
	 * The draw's immediate presentation — a bounded, deterministic vanilla
	 * particle burst at the draw point marking the withdrawn coherence and
	 * (when a burst was bought) the released glow. Pure, fixed offsets, no RNG.
	 *
	 * @param world the server level (the draw point's world)
	 * @param pos   the draw point
	 * @param burst the mining burst the draw bought, or {@code null} if too thin
	 */
	public static void presentDraw(ServerLevel world, BlockPos pos, HarnessUse.MiningBurst burst) {
		double cx = pos.getX() + 0.5;
		double cy = pos.getY() + PRESENT_HEIGHT;
		double cz = pos.getZ() + 0.5;
		// The spent-droplet: the withdrawn coherence marked where it left the field.
		world.sendParticles(ParticleTypes.END_ROD, cx, cy, cz,
				DRAW_ROD_COUNT, PRESENT_RADIUS * 0.3, 0.25, PRESENT_RADIUS * 0.3, 0.0);
		if (burst != null) {
			// The released coherence the player channels — a glow lifts from the point.
			world.sendParticles(ParticleTypes.GLOW, cx, cy, cz,
					DRAW_GLOW_COUNT, PRESENT_RADIUS * 0.4, 0.3, PRESENT_RADIUS * 0.4, 0.0);
		}
	}

	/**
	 * Called every server tick. Reads the published snapshot at each online
	 * player's position; spawns bounded vanilla particles when the local harness
	 * state is READY (spendable coherence) or SPENT (already paid). Read-only —
	 * never writes a block, never perturbs the field, never grants.
	 */
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
			HarnessRead.Read p = HarnessRead.classify(r);
			switch (p.state()) {
			case READY -> presentReady(world, pos);
			case SPENT -> presentSpent(world, pos);
			default -> { /* RESTING / VOID — no harness face to render. */ }
			}
		}
	}

	/** The READY hold: a soft coherent {@code GLOW} — the spendable coherence, visible. */
	private static void presentReady(ServerLevel world, BlockPos pos) {
		double cx = pos.getX() + 0.5;
		double cy = pos.getY() + PRESENT_HEIGHT;
		double cz = pos.getZ() + 0.5;
		world.sendParticles(ParticleTypes.GLOW, cx, cy, cz,
				READY_GLOW_COUNT, PRESENT_RADIUS * 0.3, 0.35, PRESENT_RADIUS * 0.3, 0.0);
	}

	/** The SPENT hold: the exhausted budget's {@code ASH} cast — where the field already paid. */
	private static void presentSpent(ServerLevel world, BlockPos pos) {
		double cx = pos.getX() + 0.5;
		double cy = pos.getY() + PRESENT_HEIGHT;
		double cz = pos.getZ() + 0.5;
		world.sendParticles(ParticleTypes.ASH, cx, cy, cz,
				SPENT_ASH_COUNT, PRESENT_RADIUS * 0.3, 0.3, PRESENT_RADIUS * 0.3, 0.0);
	}
}
