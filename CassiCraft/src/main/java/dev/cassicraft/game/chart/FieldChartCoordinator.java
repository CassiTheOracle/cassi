package dev.cassicraft.game.chart;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.UUID;
import java.util.function.Supplier;

import dev.cassicraft.domain.snapshot.FieldSnapshot;
import dev.cassicraft.domain.snapshot.SnapshotPublisher;
import dev.cassicraft.game.reader.FieldReader;
import net.minecraft.core.BlockPos;

/** Sole behavior path for session-local Field Chart draws, reads, slots, and summaries. */
public final class FieldChartCoordinator {
    public static final int SLOT_COUNT = 8;
    public enum Kind { INSPECT, DRAW, REDRAW, SLOT, SUMMARY }
    public record Result(Kind kind, boolean accepted, boolean dark, int slot,
            FieldChartRecord record, FieldChartRead.Comparison comparison, String message) {
        public boolean changed() { return accepted && (kind == Kind.DRAW || kind == Kind.REDRAW || kind == Kind.SLOT); }
    }
    private record Context(FieldSnapshot snapshot, double[] window, int generation) {
        Context {
            window = window.clone();
        }
        FieldReader.FieldReadout read(BlockPos position) { return FieldReader.read(snapshot, window, position.getX(), position.getY(), position.getZ()); }
    }
    private static final class Session {
        private final FieldChartRecord[] records = new FieldChartRecord[SLOT_COUNT];
        private int selected;
    }
    private final Supplier<SnapshotPublisher> publisher;
    private final HashMap<UUID, Session> sessions = new HashMap<>();

    public FieldChartCoordinator(Supplier<SnapshotPublisher> publisher) { this.publisher = publisher; }

    public synchronized Result inspect(UUID owner) {
        Context context = context();
        if (context == null) return dark(Kind.INSPECT, 0, "Field Chart is dark — the field is not yet publishing.");
        Session session = session(owner);
        FieldChartRecord record = session.records[session.selected];
        if (record == null) return new Result(Kind.INSPECT, false, false, session.selected, null, null, "Field Chart slot " + session.selected + " is blank.");
        FieldChartRead.Comparison comparison = FieldChartRead.compare(record, context.read(record.position()));
        return new Result(Kind.INSPECT, true, false, session.selected, record, comparison, present(record, comparison));
    }

    public synchronized Result draw(UUID owner, BlockPos position) { return capture(owner, position, false); }
    public synchronized Result redraw(UUID owner, BlockPos position) { return capture(owner, position, true); }

    /** Item interaction grammar: fresh-publish guard, then selected-slot draw or redraw. */
    public synchronized Result drawOrRedraw(UUID owner, BlockPos position) {
        Context context = context();
        if (context == null) return dark(Kind.DRAW, 0, "Field Chart is dark — the field is not yet publishing.");
        Session session = session(owner);
        return capture(owner, position, session.records[session.selected] != null, context);
    }

    public synchronized Result select(UUID owner, int slot) {
        requireSlot(slot);
        if (context() == null) return dark(Kind.SLOT, 0, "Field Chart is dark — the field is not yet publishing.");
        Session session = session(owner);
        session.selected = slot;
        FieldChartRecord record = session.records[slot];
        return new Result(Kind.SLOT, true, false, slot, record, null, "Field Chart selected slot " + slot + (record == null ? " (blank)." : "."));
    }

    public synchronized Result summary(UUID owner) {
        Context context = context();
        if (context == null) return dark(Kind.SUMMARY, 0, "Field Chart is dark — the field is not yet publishing.");
        Session session = session(owner);
        int filled = filled(session);
        StringBuilder text = new StringBuilder("Field Chart (").append(filled).append('/').append(SLOT_COUNT).append("):\n");
        for (int i = 0; i < SLOT_COUNT; i++) {
            FieldChartRecord record = session.records[i];
            text.append("  ").append(i).append(": ");
            if (record == null) text.append("blank");
            else text.append(present(record, FieldChartRead.compare(record, context.read(record.position()))));
            if (i == session.selected) text.append("  <selected>");
            if (i + 1 < SLOT_COUNT) text.append('\n');
        }
        return new Result(Kind.SUMMARY, true, false, session.selected, null, null, text.toString());
    }

    public synchronized void clearSession() { sessions.clear(); }
    public synchronized int selected(UUID owner) { Session s = sessions.get(owner); return s == null ? 0 : s.selected; }
    public synchronized int filled(UUID owner) { Session s = sessions.get(owner); return s == null ? 0 : filled(s); }
    public synchronized List<FieldChartRecord> records(UUID owner) {
        Session s = sessions.get(owner);
        if (s == null) return List.of();
        ArrayList<FieldChartRecord> copy = new ArrayList<>(SLOT_COUNT);
        for (FieldChartRecord record : s.records) if (record != null) copy.add(record);
        return List.copyOf(copy);
    }

    private Result capture(UUID owner, BlockPos position, boolean explicitRedraw) {
        Context context = context();
        if (context == null) return dark(explicitRedraw ? Kind.REDRAW : Kind.DRAW, 0, "Field Chart is dark — the field is not yet publishing.");
        return capture(owner, position, explicitRedraw, context);
    }

    private Result capture(UUID owner, BlockPos position, boolean explicitRedraw, Context context) {
        Session session = session(owner);
        int slot = session.selected;
        FieldChartRecord current = session.records[slot];
        if (!explicitRedraw && current != null) return new Result(Kind.DRAW, false, false, slot, current, null, "Field Chart slot " + slot + " is occupied; use redraw to replace it.");
        if (explicitRedraw && current == null) return new Result(Kind.REDRAW, false, false, slot, null, null, "Field Chart slot " + slot + " is blank; draw first.");
        FieldReader.FieldReadout reading = context.read(position);
        FieldChartRecord record = new FieldChartRecord(owner, slot, position, reading.q(), reading.eps2(), context.generation());
        session.records[slot] = record;
        return new Result(explicitRedraw ? Kind.REDRAW : Kind.DRAW, true, false, slot, record, null,
                (explicitRedraw ? "Redrew" : "Drew") + " Field Chart slot " + slot + ": " + position.getX() + "," + position.getY() + "," + position.getZ()
                + " q_draw=" + record.qDraw() + " eps2_draw=" + record.eps2Draw() + " generation=" + record.generation());
    }

    private Context context() {
        SnapshotPublisher current = publisher.get();
        if (current == null) return null;
        FieldSnapshot snapshot = current.freshest();
        if (snapshot == null) return null;
        double[] window = snapshot.job() != null && !snapshot.job().isWindowless()
                ? snapshot.job().windowCenter().clone() : new double[] { 0, 0, 0 };
        return new Context(snapshot, window, snapshot.generation());
    }

    private static Result dark(Kind kind, int slot, String message) { return new Result(kind, false, true, slot, null, null, message); }
    private static String present(FieldChartRecord record, FieldChartRead.Comparison comparison) {
        return "slot " + record.slot() + " @ (" + record.position().getX() + "," + record.position().getY() + "," + record.position().getZ() + ") " + comparison.text();
    }
    private Session session(UUID owner) {
        if (owner == null) throw new IllegalArgumentException("owner is required");
        return sessions.computeIfAbsent(owner, ignored -> new Session());
    }
    private static int filled(Session session) { int count = 0; for (FieldChartRecord r : session.records) if (r != null) count++; return count; }
    private static void requireSlot(int slot) { if (slot < 0 || slot >= SLOT_COUNT) throw new IllegalArgumentException("slot must be between 0 and 7: " + slot); }
}
