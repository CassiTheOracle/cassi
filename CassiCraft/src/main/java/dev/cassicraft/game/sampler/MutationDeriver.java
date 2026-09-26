package dev.cassicraft.game.sampler;

import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.game.sampler.Quantizer.BlockKind;
import dev.cassicraft.game.writer.BlockMutation;
import net.minecraft.core.BlockPos;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/** Pure package seam for bounded production field-to-intent derivation. */
final class MutationDeriver {
    static final int VICINITY_RADIUS = 16;

    private MutationDeriver() {
    }

    /** Probe-only unbounded derivation; production must use the session seam. */
    static List<BlockMutation> deriveUnboundedProbe(FieldSnapshot snapshot, double[] windowCenter,
            int cx, int cy, int cz, Map<BlockPos, BlockKind> prior) {
        return derive(snapshot, windowCenter, cx, cy, cz, prior, null, null);
    }

    static List<BlockMutation> derive(FieldSnapshot snapshot, double[] windowCenter,
            int cx, int cy, int cz, Map<BlockPos, BlockKind> prior,
            TerrainHorizon horizon, UUID playerId) {
        List<BlockMutation> emitted = new ArrayList<>();
        BlockPos limit = horizon == null || playerId == null ? null : horizon.horizon(playerId);
        for (int dz = -VICINITY_RADIUS; dz < VICINITY_RADIUS; dz++) {
            for (int dy = -VICINITY_RADIUS; dy < VICINITY_RADIUS; dy++) {
                for (int dx = -VICINITY_RADIUS; dx < VICINITY_RADIUS; dx++) {
                    BlockPos pos = new BlockPos(cx + dx, cy + dy, cz + dz);
                    if (horizon != null && (limit == null || pos.getY() > limit.getY())) {
                        prior.remove(pos);
                        continue;
                    }
                    Quantizer.CellSample s = Quantizer.sampleAt(snapshot, windowCenter,
                            pos.getX(), pos.getY(), pos.getZ());
                    BlockKind priorKind = prior.getOrDefault(pos, BlockKind.AIR);
                    BlockKind kind = Quantizer.quantize(s.rho(), s.q(), s.eps2(), priorKind);
                    if (kind != priorKind) {
                        prior.put(pos, kind);
                        emitted.add(new BlockMutation(pos, kind));
                    }
                }
            }
        }
        return emitted;
    }
}
