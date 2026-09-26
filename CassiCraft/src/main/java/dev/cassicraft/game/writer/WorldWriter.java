package dev.cassicraft.game.writer;

import dev.cassicraft.game.sampler.Quantizer;
import net.minecraft.core.BlockPos;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.block.Blocks;
import net.minecraft.world.level.block.state.BlockState;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.Queue;

/**
 * MODULE 4 — WORLD-WRITER: THE ONLY MUTATOR. The single class allowed to mutate
 * a {@link ServerLevel}. Per the four-module seam (BUILD-PLAN.md §2.1,
 * async-field-domain.md §1) the sampler derives intent ({@link BlockMutation}s)
 * and the writer applies it through vanilla {@code Level.setBlock} machinery —
 * it never reads the domain directly, and nothing else mutates world state.
 *
 * <p>The writer runs on the server thread. Each server tick
 * {@link #flushIntents} drains the sampler's intent queue and applies the
 * mutations to the overworld, <b>skipping unloaded chunks</b> (no force-load):
 * a mutation in a chunk that is not {@code load()}ed is dropped for this pass —
 * it is never forced into existence. The block mapping {@link Quantizer.BlockKind}
 * → {@link BlockState} is:
 * <ul>
 *   <li>{@code SOLID} → {@link Blocks#STONE} (the iron/silicate rung)</li>
 *   <li>{@code ORE} → {@link Blocks#COPPER_ORE} (the registry-dressed copper kind —
 *       the deep-dense metal regime or the coherence-precipitated q vein,
 *       material-regimes §1/§3; the Quantizer selects it, the writer places it)</li>
 *   <li>{@code AIR} → {@link Blocks#AIR}</li>
 * </ul>
 * The writer is the only block mutator and the only place a {@code BlockKind}
 * becomes a concrete {@code BlockState}; it never reads the domain and never
 * decides the kind itself — the Quantizer (which has the field sample) chooses
 * the dressed kind, the writer applies it. This is the material-regimes §7
 * deferral closed end-to-end: the real-element registry now dresses the world's
 * placed blocks, not just a printed table.
 * <p>The writer also clears a block's neighbours' light/geometry implicitly through
 * vanilla {@code setBlock} (flag {@code 3} = block update + send), so the seam
 * stays on-plan machinery.
 */
public class WorldWriter {

	private static final Logger LOGGER = LoggerFactory.getLogger(WorldWriter.class);

	private final Queue<BlockMutation> intent;
	private boolean announced;

	/**
	 * @param intent the shared sampler→writer intent queue (owned by the
	 *               session coordinator, both modules run on the server thread)
	 */
	public WorldWriter(Queue<BlockMutation> intent) {
		this.intent = intent;
	}

	/** The sampler (module 2) drops derived mutations here. Server-thread only. */
	public Queue<BlockMutation> intentQueue() {
		return intent;
	}

	/**
	 * Called from the entrypoint when the server starts. Phase-1 writes go to the
	 * overworld; the writer holds no other world state.
	 */
	public void onServerStart(MinecraftServer server) {
		// The overworld is the Phase-1 substrate (the 192³ box anchor).
	}

	/**
	 * Apply pending sampler intents to the given server. Called every tick after
	 * the sampler runs (BUILD-PLAN.md §5.1 item 4). Mutations in unloaded chunks
	 * are <b>requeued</b> for a later tick (never force-loaded) so intent is not
	 * lost if the block's chunk loads after the sampler emitted it.
	 */
	public void flushIntents(MinecraftServer server) {
		ServerLevel level = server.overworld();
		if (level == null || intent.isEmpty()) {
			return;
		}
		int applied = 0;
		int requeued = 0;
		int budget = intent.size();
		for (int i = 0; i < budget && !intent.isEmpty(); i++) {
			BlockMutation m = intent.poll();
			if (!level.isLoaded(m.pos())) {
				// Chunk not load()ed — do NOT force it; retry once it loads.
				intent.add(m);
				requeued++;
				continue;
			}
			BlockState state = blockStateFor(m.kind());
			if (level.getBlockState(m.pos()) != state) {
				if (level.setBlock(m.pos(), state, 3)) {
					applied++;
				}
			}
		}
		if (applied > 0) {
			if (!announced) {
				announced = true;
				LOGGER.info("[cassicraft/writer] applied {} block mutations to overworld (first pass, {} requeued)", applied, requeued);
			} else {
				LOGGER.debug("[cassicraft/writer] applied {} block mutations ({} requeued)", applied, requeued);
			}
		}
	}

	/** Map a quantized kind to the concrete demo block (BUILD-PLAN.md §5.3). */
	public static BlockState blockStateFor(Quantizer.BlockKind kind) {
		return switch (kind) {
		case ORE -> Blocks.COPPER_ORE.defaultBlockState();
		case SOLID -> Blocks.STONE.defaultBlockState();
		case AIR -> Blocks.AIR.defaultBlockState();
		};
	}

	/** Explicit teardown on server stop — drains any un-applied intents. */
	public void close() {
		intent.clear();
	}
}
