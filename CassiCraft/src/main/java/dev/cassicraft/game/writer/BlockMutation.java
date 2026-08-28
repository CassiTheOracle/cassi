package dev.cassicraft.game.writer;

import dev.cassicraft.game.sampler.Quantizer;
import net.minecraft.core.BlockPos;

/**
 * MODULE 4 — a single block mutation intent (BUILD-PLAN.md §5.1 item 3). The
 * sampler derives an ordered list of these; the world-writer is the only module
 * permitted to apply them to a {@code ServerLevel} (the only-mutator rule).
 *
 * <p>A mutation targets a block position with a quantized {@link Quantizer.BlockKind};
 * the writer maps that to a concrete {@code BlockState} (see {@link WorldWriter}).
 * Immutable by construction.
 */
public record BlockMutation(BlockPos pos, Quantizer.BlockKind kind) {
}
