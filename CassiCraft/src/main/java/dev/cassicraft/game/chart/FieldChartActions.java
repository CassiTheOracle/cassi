package dev.cassicraft.game.chart;

import java.util.UUID;
import net.minecraft.core.BlockPos;

/** Pure runtime policy seam shared by item/command adapters and headless gates. */
public final class FieldChartActions {
    static FieldChartCoordinator.Result itemUse(FieldChartCoordinator chart, UUID owner, BlockPos position, boolean crouching) {
        return crouching ? chart.drawOrRedraw(owner, position) : chart.inspect(owner);
    }
    static FieldChartCoordinator.Result inspect(FieldChartCoordinator chart, UUID owner) { return chart.inspect(owner); }
    static FieldChartCoordinator.Result draw(FieldChartCoordinator chart, UUID owner, BlockPos position) { return chart.draw(owner, position); }
    static FieldChartCoordinator.Result redraw(FieldChartCoordinator chart, UUID owner, BlockPos position) { return chart.redraw(owner, position); }
    static FieldChartCoordinator.Result slot(FieldChartCoordinator chart, UUID owner, int slot) { return chart.select(owner, slot); }
    static FieldChartBearing.Result bearing(FieldChartCoordinator chart, UUID owner, int x, int y, int z) { return chart.bearing(owner, x, y, z); }
    static FieldChartCoordinator.Result summary(FieldChartCoordinator chart, UUID owner) { return chart.summary(owner); }
    private FieldChartActions() {}
}
