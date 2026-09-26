package dev.cassicraft.game.lume;

import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.game.reader.WeatherglassItem;
import dev.cassicraft.game.sampler.Quantizer;
import net.fabricmc.fabric.api.networking.v1.ServerPlayNetworking;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerPlayer;

/**
 * The Weatherglass always-on lume coordinator (field-instruments.md §1.4). On
 * every {@code LUME_PUSH_EVERY_TICKS} server ticks it takes the corpus's "one
 * extra sample at the player's position" (gate (d)) for every online player
 * holding a {@link WeatherglassItem} in their main hand — sampling the published
 * snapshot via {@link Quantizer#sampleReading} off the freshest
 * {@code window_center}, exactly as the read command does — and pushes the six
 * published values to that player via {@link LumePayload}.
 *
 * <p><b>Discipline (only-mutator + read-only rules):</b> this never writes a
 * block and never touches domain buffers (the server never reads physics state —
 * async-field-domain.md §5). It reads only published channel values off the
 * immutable snapshot and ships them over one bounded channel ({@link
 * LumePayload}); the refresh cadence follows the publish's cadence, not 20 Hz —
 * the lume is a glance. With no publish yet, it skips; with no glass-holding
 * player, it is a no-op.
 */
public final class LumePusher {

	/**
	 * [design] Push cadence — the lume samples on the publish cadence (every
	 * couple of physics jobs), not per tick; a glance does not need 20 Hz
	 * (field-instruments §1.4).
	 */
	public static final int LUME_PUSH_EVERY_TICKS = 5;

	private final WeatherglassItem instrument;
	private final SnapshotPublisher publisher;

	public LumePusher(WeatherglassItem instrument, SnapshotPublisher publisher) {
		this.instrument = instrument;
		this.publisher = publisher;
	}

	/** Called every server tick. Read-only; skips when it is not this tick, the
	 * player holds no glass, or the domain has not published yet. */
	public void onServerTick(MinecraftServer server) {
		if (server.getTickCount() % LUME_PUSH_EVERY_TICKS != 0) {
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
			if (player.getMainHandItem().getItem() != instrument) {
				continue;
			}
			net.minecraft.core.BlockPos pos = player.blockPosition();
			Quantizer.FieldReading r = Quantizer.sampleReading(
					snap, center, pos.getX(), pos.getY(), pos.getZ());
			ServerPlayNetworking.send(player, new LumePayload(
					r.rho(), r.q(), r.eps2(), r.gradX(), r.gradY(), r.gradZ()));
		}
	}
}
