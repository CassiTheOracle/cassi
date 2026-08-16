package dev.cassicraft.game.sampler;

import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.game.sampler.Quantizer.BlockKind;
import dev.cassicraft.game.writer.BlockMutation;
import net.minecraft.core.BlockPos;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.server.level.ServerPlayer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.HashMap;
import java.util.Map;

/**
 * MODULE 2 — TICK-SAMPLER (server thread, 20 Hz, read-only). The domain hosts
 * the {@link SnapshotPublisher}; the sampler reads the freshest snapshot and
 * derives <b>intent</b> (an ordered list of {@link BlockMutation}s) that the
 * world-writer — the only mutator — applies. The sampler never mutates world
 * state (BUILD-PLAN.md §5.1, async-field-domain.md §1).
 *
 * <p>Registered via {@code ServerTickEvents.END_SERVER_TICK} from the entrypoint.
 * Per tick: pulls {@link SnapshotPublisher#freshest()} (a lock-free volatile
 * load — never blocks), tracks the last-consumed generation to <b>drop stale</b>
 * publishes (BUILD-PLAN.md §4.2), and on a cadence re-quantizes the player's
 * vicinity (the active/dirty region — never the full 192³ volume, the §9.2
 * anti-goal) emitting only blocks whose quantized kind changed.
 *
 * <p>The quantization is hysteresis-aware: a solid block only dissolves below
 * {@code τ_c − δ}, so a jittering field does not flicker blocks each tick
 * (chunk-field-quantization.md §3). Re-quantizing an unchanged region emits no
 * mutations — the {@link Quantizer#quantize} diff against the prior pass is
 * idempotent.
 */
public class TickSampler {

	private static final Logger LOGGER = LoggerFactory.getLogger(TickSampler.class);

	/** Re-quantization cadence in server ticks (cut-first pressure valve, §5.2). */
	private static final int QUANTIZE_EVERY_TICKS = 5;
	/** Radius (blocks) of the player-vicinity square re-quantized each cadence — controls the per-tick budget. */
	private static final int VICINITY_RADIUS = 16;   // 32³ blocks ≈ 1–2 ms, inside the 1–6 ms budget

	private final SnapshotPublisher publisher;
	private final Map<BlockPos, BlockKind> prior = new HashMap<>();

	private long lastQuantTick = -1;
	private int lastConsumedGen = -1;
	private boolean announcedConsumption;

	public TickSampler(SnapshotPublisher publisher) {
		this.publisher = publisher;
	}

	/** The snapshot handoff this sampler consumes (the field thread's publisher). */
	public SnapshotPublisher publisher() {
		return publisher;
	}

	/**
	 * Called every server tick (20 Hz). Pulls the freshest publish, drops stale
	 * generations, and on the quantization cadence emits changed-block intent.
	 */
	public void onServerTick(MinecraftServer server, java.util.Queue<BlockMutation> writerIntent) {
		FieldSnapshot freshest = publisher.freshest();
		if (freshest == null) {
			// Domain not publishing yet; nothing to sample.
			return;
		}
		long tick = server.getTickCount();
		// Stale-generation drop: only consume publishes newer than the last one
		// we actually quantized (async-field-domain.md §5.1).
		if (freshest.generation() <= lastConsumedGen) {
			return;
		}
		if (tick - lastQuantTick < QUANTIZE_EVERY_TICKS) {
			return; // re-quant cadence not yet due (still "tick-only" liveness)
		}
		lastQuantTick = tick;
		lastConsumedGen = freshest.generation();

		double[] windowCenter = freshest.job() != null && !freshest.job().isWindowless()
				? freshest.job().windowCenter()
				: new double[] { 0, 0, 0 };

		BlockPos player = playerVicinity(server);
		int cx = player.getX();
		int cy = player.getY();
		int cz = player.getZ();

		// Emit only mutations that actually flipped kind across the hysteresis band.
		int emitted = 0;
		for (int dz = -VICINITY_RADIUS; dz < VICINITY_RADIUS; dz++) {
			for (int dy = -VICINITY_RADIUS; dy < VICINITY_RADIUS; dy++) {
				for (int dx = -VICINITY_RADIUS; dx < VICINITY_RADIUS; dx++) {
					BlockPos pos = new BlockPos(cx + dx, cy + dy, cz + dz);
					Quantizer.CellSample s = Quantizer.sampleAt(freshest, windowCenter, pos.getX(), pos.getY(), pos.getZ());
					BlockKind priorKind = prior.getOrDefault(pos, BlockKind.AIR);
					BlockKind kind = Quantizer.quantize(s.rho(), s.q(), s.eps2(), priorKind);
					if (kind != priorKind) {
						prior.put(pos, kind);
						writerIntent.add(new BlockMutation(pos, kind));
						emitted++;
					}
				}
			}
		}
		// One-time INFO lease: prove the sampler consumes the published field and
		// derives intent, without flooding the boot log (steady state is DEBUG).
		if (!announcedConsumption) {
			announcedConsumption = true;
			LOGGER.info("[cassicraft/sampler] consumed snapshot gen={} around ({},{},{}), emitted {} block mutations",
					freshest.generation(), cx, cy, cz, emitted);
		}
	}

	/**
	 * The player-vicinity anchor for the re-quantization region. Uses the first
	 * online player's position; when the server is empty (headless demo) it
	 * falls back to the world's respawn (spawn) position — inside the loaded
	 * spawn area, so the writer can actually apply the demo terrain with no
	 * client connected. The player-anchored box advection is a later refinement
	 * (BUILD-PLAN.md §5.3).
	 */
	private static BlockPos playerVicinity(MinecraftServer server) {
		ServerLevel level = server.overworld();
		if (level != null) {
			for (ServerPlayer p : level.players()) {
				if (p != null) {
					return p.blockPosition();
				}
			}
			if (level.getRespawnData() != null && level.getRespawnData().pos() != null) {
				return level.getRespawnData().pos();
			}
		}
		return BlockPos.ZERO;
	}
}
