package dev.cassicraft.game.sampler;

import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.domain.thread.CassiFieldThread;
import dev.cassicraft.domain.thread.KernelLoader;
import dev.cassicraft.game.writer.BlockMutation;
import dev.cassicraft.game.writer.WorldWriter;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;

import java.util.ArrayDeque;
import java.util.Queue;

/**
 * Server-session coordinator for the living-terrain seam (BUILD-PLAN.md §5, §7).
 * Owns the per-server-session {@link CassiFieldThread} (the domain worker),
 * the {@link SnapshotPublisher} handoff, the {@link TickSampler}, the
 * {@link WorldWriter}, and the shared {@code intent} queue that flows from
 * sampler to writer.
 *
 * <p>The lifecycle is explicit — {@link #beginSession} stands up the field
 * thread (started at world load, seed derived from the world seed) and
 * {@link #endSession} joins it — never a finalizer/GC hook (BUILD-PLAN.md §3.3).
 * The domain worker is <b>started on the level-load thread</b> via
 * {@code ServerLevelEvents.LOAD} (the clean "world load" hook) and closed on
 * {@code UNLOAD} / {@code SERVER_STOPPING}.
 *
 * <p>This is the only owner of the four-module composition; {@code CassiCraft}
 * keeps startup-only wiring and routes the server tick into
 * {@link #sampler()} + {@link #writer()}.
 */
public final class SamplerShutdown {

	private SnapshotPublisher publisher;
	private CassiFieldThread fieldThread;
	private TickSampler sampler;
	private WorldWriter writer;
	private double[] windowCenter = new double[] { 0, 0, 0 };
	private final Queue<BlockMutation> intent = new ArrayDeque<>();

	/**
	 * Stand up a fresh session: a world-seed-derived field thread + sampler +
	 * writer wired to one immutable-snapshot handoff.
	 *
	 * @param windowCenter the box's center in world coords — anchored to where the
	 *        player enters (the corpus's anchor-to-window, async-field-domain §7 Q1);
	 *        grid (32,32,32) maps to this point, so the player stands in the field's
	 *        real interior, not a clamped edge
	 * @return the world-seed-derived field seed actually used (for logging).
	 */
	public long beginSession(ServerLevel level, long worldSeed, double[] windowCenter) {
		endSession(); // defensive — never leave a prior session's worker running
		this.publisher = new SnapshotPublisher();
		this.fieldThread = new CassiFieldThread(publisher);
		this.windowCenter = windowCenter.clone();
		long seed = worldSeed;
		CassiFieldThread.Cfg cfg = new CassiFieldThread.Cfg(
				seed,
				CassiFieldThread.JOB_STEP_CAP,
				CassiFieldThread.SNAPSHOT_CADENCE,
				new KernelLoader().load(),
				this.windowCenter);
		fieldThread.start(cfg);

		this.sampler = new TickSampler(publisher);
		this.writer = new WorldWriter(intent);
		this.writer.onServerStart(level.getServer());
		return seed;
	}

	/** The anchored box center (world coords) of the live session. */
	public double[] windowCenter() {
		return windowCenter.clone();
	}

	/** Tick hook: sampler reads the freshest publish → intent; writer applies it. */
	public void onServerTick(MinecraftServer server) {
		if (sampler == null || writer == null) {
			return;
		}
		sampler.onServerTick(server, intent);
		writer.flushIntents(server);
	}

	/** The per-session sampler (module 2). */
	public TickSampler sampler() {
		return sampler;
	}

	/** The per-session world-writer (module 4, the only mutator). */
	public WorldWriter writer() {
		return writer;
	}

	/** The per-session immutable-snapshot handoff (read by sampler + reader). */
	public SnapshotPublisher publisher() {
		return publisher;
	}

	public boolean isRunning() {
		return fieldThread != null && fieldThread.isRunning();
	}

	/**
	 * Explicit close on world unload / server stop — joins the field worker and
	 * releases the writer. Idempotent, never a finalizer.
	 */
	public synchronized void endSession() {
		if (fieldThread != null) {
			fieldThread.close();
			fieldThread = null;
		}
		if (writer != null) {
			writer.close();
			writer = null;
		}
		sampler = null;
		intent.clear();
	}
}
