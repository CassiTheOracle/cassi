package dev.cassicraft.game.atmo;

import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.game.sampler.Quantizer;
import net.minecraft.core.BlockPos;
import net.minecraft.core.particles.ParticleTypes;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;

/**
 * The atmosphere field phenomena's client-visible presentation
 * (atmosphere-orbits-auroras.md §3.3 — the aurora as the reader's atmospheric
 * form; §1.5 the sky is the field's shape made visible). A <b>bounded,
 * vanilla-only consumer</b>: on a named cadence it takes the corpus's "one
 * extra sample at the player's position" (field-instruments §1.4) for each
 * online player, classifies the local atmosphere via {@link AtmoRead}, and —
 * when that position reads an {@link AtmoRead.Kind#AURORA} (the coherence
 * discharge into a drain, §3.1) — spawns an ordinary Minecraft particle (a
 * hanging luminous band) at the player's vicinity only. No custom rendering,
 * no sky-color/fog engine change, no mixins, no new channel — vanilla
 * particles broadcast by the server level.
 *
 * <p><b>Why a distinct particle from the sky's glow.</b> The committed sky
 * slice ({@code dev.cassicraft.game.sky.SkyPresenter}) renders the coherent
 * high-q glow's <em>source</em> as {@link ParticleTypes#END_ROD}. The aurora
 * here is the <b>discharge into a drain</b> — delivered coherence meeting a
 * rising-ε² well and shedding its (1−q) waste (§3.1) — so it presents as a
 * soft luminous {@link ParticleTypes#GLOW} (the glowing squid's luminescent
 * light), the doc's luminous band over the drain. Only the co-located
 * discharge (q coherent-high AND ε² in the drain band) fires; a position that
 * the sky's single-channel glow owns and that has no drain does not read an
 * aurora here, so the two presenters never double-light the same drain unless
 * the field itself is genuinely discharging.
 *
 * <p><b>Discipline (only-mutator + no-free-energy):</b> this never writes a
 * block and never grants anything — the presentation is a pure consumer of the
 * published snapshot, deterministic in its aurora (the doc §5c), and provides
 * nothing beyond the field's own read. With no publish yet it skips; with no
 * online player it is a no-op. The full rendered aurora curtain is a deferred
 * [design] (§6, later); Phase-1 presents the discharge's <em>site</em> as a
 * bounded vanilla luminous band.
 */
public final class AtmoPresenter {

	/**
	 * [design] Cadence — spawn the aurora's discharge particles every this many
	 * server ticks (a bounded, glanceable band, not a per-tick stream).
	 */
	public static final int AURORA_SPAWN_EVERY_TICKS = 10;

	/**
	 * [design] The aurora's particle count per spawn tick — a soft, lingering
	 * luminous band (bounded, scaled by the discharge strength).
	 */
	public static final int AURORA_PARTICLE_COUNT = 8;

	/**
	 * [design] The particle count ceiling when the discharge's waste fraction
	 * {@code 1−q} is strong (a brighter drain sheds a denser band).
	 */
	public static final int AURORA_PARTICLE_STRONG_COUNT = 14;

	/** [design] The waste-fraction floor above which the aurora reads "strong" (a denser band). */
	public static final float AURORA_STRONG_WASTE = 0.06f;

	/** [design] Radius of the presentation ring around the player (blocks). */
	public static final double AURORA_RING_RADIUS = 2.0;

	/** [design] Height above the player's feet where the aurora's discharge presents (blocks). */
	public static final double AURORA_PRESENT_HEIGHT = 3.0;

	private final SnapshotPublisher publisher;

	public AtmoPresenter(SnapshotPublisher publisher) {
		this.publisher = publisher;
	}

	/** Called every server tick. Reads the published snapshot at each online
	 * player's position; spawns bounded vanilla particles when the local
	 * atmosphere is a coherence discharge. Read-only — never writes a block,
	 * never perturbs the field, never grants. */
	public void onServerTick(MinecraftServer server) {
		if (server.getTickCount() % AURORA_SPAWN_EVERY_TICKS != 0) {
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
			AtmoRead.Read a = AtmoRead.classify(r);
			if (a.isAurora()) {
				spawnAurora(world, pos, a.discharge());
			}
		}
	}

	/**
	 * The aurora's discharge: a bounded soft luminous {@code GLOW} above the
	 * player — the luminescent track of delivered coherence shedding into the
	 * drain (atmosphere §3.1). The count scales by the waste fraction (a
	 * brighter drain sheds a denser glow), fixed offsets (deterministic, no
	 * RNG), so the same field state yields the same aurora (§5c).
	 */
	private static void spawnAurora(ServerLevel world, BlockPos pos, float discharge) {
		double cx = pos.getX() + 0.5;
		double cy = pos.getY() + AURORA_PRESENT_HEIGHT;
		double cz = pos.getZ() + 0.5;
		int count = discharge >= AURORA_STRONG_WASTE
				? AURORA_PARTICLE_STRONG_COUNT
				: AURORA_PARTICLE_COUNT;
		world.sendParticles(ParticleTypes.GLOW, cx, cy, cz,
				count, AURORA_RING_RADIUS * 0.5, 0.5, AURORA_RING_RADIUS * 0.5, 0.0);
	}
}
