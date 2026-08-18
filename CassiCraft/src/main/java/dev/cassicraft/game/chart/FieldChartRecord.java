package dev.cassicraft.game.chart;

import java.util.UUID;
import net.minecraft.core.BlockPos;

/** Immutable session-local observation stored by one player's Field Chart slot. */
public record FieldChartRecord(UUID owner, int slot, BlockPos position,
        float qDraw, float eps2Draw, int generation) {
    public FieldChartRecord {
        if (owner == null || position == null) {
            throw new IllegalArgumentException("owner and position are required");
        }
        if (slot < 0 || slot >= FieldChartCoordinator.SLOT_COUNT) {
            throw new IllegalArgumentException("slot out of range: " + slot);
        }
        position = position.immutable();
    }
}
