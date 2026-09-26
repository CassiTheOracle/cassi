package dev.cassicraft.game.sampler;

import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.domain.thread.CassiFieldThread;
import dev.cassicraft.domain.thread.KernelLoader;
import dev.cassicraft.game.sampler.Quantizer.BlockKind;
import dev.cassicraft.game.writer.BlockMutation;
import net.minecraft.core.BlockPos;

import java.util.HashMap;
import java.util.List;
import java.util.UUID;

public final class SkyMaterializationDeterminismMain {
    private static final UUID A = UUID.fromString("00000000-0000-0000-0000-000000000001");
    private static final UUID B = UUID.fromString("00000000-0000-0000-0000-000000000002");

    public static void main(String[] args) throws Exception {
        SnapshotPublisher publisher = new SnapshotPublisher();
        CassiFieldThread worker = new CassiFieldThread(publisher);
        double[] center = { 0, 70, 0 };
        worker.start(new CassiFieldThread.Cfg(42L, CassiFieldThread.JOB_STEP_CAP,
                CassiFieldThread.SNAPSHOT_CADENCE, new KernelLoader().load(), center));
        try {
            FieldSnapshot snapshot = await(publisher);
            MaterializationSession session = new MaterializationSession();
            List<BlockMutation> raw = MutationDeriver.deriveUnboundedProbe(snapshot, center, 0, 70, 0, new HashMap<>());
            require(!raw.isEmpty(), "anti-vacuity raw candidate");
            require(session.derive(snapshot, center, A, new BlockPos(0, 70, 0), false).isEmpty(), "no horizon");
            List<BlockMutation> grounded = session.derive(snapshot, center, A, new BlockPos(0, 70, 0), true);
            require(grounded.stream().noneMatch(m -> m.pos().getY() >= 70), "feet ceiling");
            require(grounded.stream().anyMatch(m -> m.pos().getY() < 70), "below retention");
            require(session.derive(snapshot, center, A, new BlockPos(0, 80, 0), false)
                    .stream().noneMatch(m -> m.pos().getY() >= 70), "airborne retention");
            BlockMutation target = raw.stream().filter(m -> m.kind() != BlockKind.AIR && m.pos().getY() > 1)
                    .findFirst().orElseThrow(() -> new IllegalStateException("no raw target"));
            BlockPos targetPos = target.pos();
            session.clear();
            List<BlockMutation> high = session.derive(snapshot, center, A, targetPos.above(2), true);
            require(high.stream().anyMatch(m -> m.pos().equals(targetPos)), "high target eligible");
            List<BlockMutation> low = session.derive(snapshot, center, A, targetPos, true);
            require(low.stream().noneMatch(m -> m.pos().equals(targetPos)), "low target suppressed");
            require(!session.tracks(targetPos), "suppressed target absent from prior");
            List<BlockMutation> fresh = session.derive(snapshot, center, A, targetPos.above(1), true);
            require(fresh.stream().anyMatch(m -> m.pos().equals(targetPos)), "raised target fresh");
            require(session.derive(snapshot, center, B, new BlockPos(0, 90, 0), false).isEmpty(),
                    "turnover B airborne");
            require(B.equals(session.owner()) && session.priorCount() == 0, "B turnover state");
            List<BlockMutation> ownerB = session.derive(snapshot, center, B,
                    new BlockPos(0, 70, 0), true);
            require(!ownerB.isEmpty(), "B grounded fresh");
            session.clear();
            List<BlockMutation> rejoinAir = session.derive(snapshot, center, A,
                    new BlockPos(0, 70, 0), false);
            require(rejoinAir.isEmpty() && A.equals(session.owner()) && session.priorCount() == 0,
                    "same UUID rejoin airborne");
            List<BlockMutation> rejoin = session.derive(snapshot, center, A,
                    new BlockPos(0, 70, 0), true);
            require(!rejoin.isEmpty(), "same UUID rejoin grounded fresh");
            session.clear();
            require(session.owner() == null && session.priorCount() == 0, "close state");
            System.out.println("[sky-materialization] PASS rawIntents=" + raw.size()
                    + " groundedIntents=" + grounded.size() + " freshIntents=" + fresh.size()
                    + " ownerBIntents=" + ownerB.size() + " rejoinIntents=" + rejoin.size()
                    + " noHorizon=PASS feetCeiling=PASS belowRetention=PASS airborne=PASS"
                    + " unchangedPriorReset=PASS ownerTurnoverReset=PASS departureRejoin=PASS closeClear=PASS");
        } finally {
            worker.close();
            require(!worker.isRunning(), "worker close");
        }
    }

    private static FieldSnapshot await(SnapshotPublisher publisher) throws InterruptedException {
        long deadline = System.currentTimeMillis() + 120_000;
        while (System.currentTimeMillis() < deadline) {
            FieldSnapshot snapshot = publisher.freshest();
            if (snapshot != null && snapshot.generation() >= 12) return snapshot;
            Thread.sleep(20);
        }
        throw new IllegalStateException("no snapshot");
    }

    private static void require(boolean condition, String label) {
        if (!condition) throw new IllegalStateException("FAIL " + label);
    }

    private SkyMaterializationDeterminismMain() {}
}
