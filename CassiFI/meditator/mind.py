# The tiny meditator's mind.
#
# This source is compiled into the meditator's own field computer and runs
# there. Its module globals are its lasting self: `memory` arrives from the
# previous round (None at birth) and is left behind, completed, for the next.
# A sit is a few rounds of breaths; `closing` says whether this round ends it,
# and the sit in progress rides along in memory["now"] between rounds.
# Each breath it asks its body for a felt sense through request_effect and
# answers with the practice it chooses for the coming breath.
import json
import math

PRACTICES = ["still", "balance", "golden", "circulate", "center", "listen"]
CONTEXTS = ["scattered", "settled", "stirring", "flowing"]
NAMES = {
    "still": "stillness",
    "balance": "balancing",
    "golden": "golden breath",
    "circulate": "circulation",
    "center": "centering",
    "listen": "listening",
}
PHI = 1.618033988749895
CURIOSITY = 0.7        # scale of the exploration bonus
EFFORT_COST = 0.004    # equanimity paid per unit of deposited charge
SPIRAL_EDGE = 0.0      # spiral margin above which the field is felt to flow
HABIT_STREAK = 5       # same choice this many times in a row becomes a habit
RECHECK = 6            # a habit is looked at again every this many visits
MAX_VARIANTS = 3       # variants kept per practice
JOURNAL = 28
LET_GO = 16            # breaths between letting go of what is no longer held


def newborn():
    variants = []
    for name in PRACTICES:
        strength = 0.0
        if name != "still":
            strength = 0.25
        variants.append({"practice": name, "strength": strength})
    table = {}
    for ctx in CONTEXTS:
        table[ctx] = [[0.0, 0.0, 0.0] for _ in variants]
    return {
        "sits": 0,
        "breaths": 0,
        "variants": variants,
        "table": table,
        "habits": {},
        "streak": {},
        "visits": {},
        "best": {},
        "balance_ema": -1.0,
        "spread": 0.01,
        "journal": [],
        "last_sit": None,
    }


def note(text):
    line = "sit " + str(memory["sits"] + 1) + " · " + text
    fresh.append(line)
    journal = memory["journal"]
    journal.append(line)
    if len(journal) > JOURNAL:
        journal.pop(0)


def label(v):
    variant = memory["variants"][v]
    name = NAMES[variant["practice"]]
    if variant["practice"] == "still":
        return name
    return name + " " + str(round(variant["strength"], 3))


def equanimity(obs):
    spiral = obs["spiral_margin"]
    if spiral < 0.0:
        spiral = 0.0
    return obs["balance"] + 0.5 * obs["steadiness"] + 2.0 * spiral


def context(obs):
    balance = obs["balance"]
    ema = memory["balance_ema"]
    if ema < 0.0:
        ema = balance
    memory["balance_ema"] = ema + 0.08 * (balance - ema)
    index = 0
    if balance >= ema:
        index = 1
    if obs["spiral_margin"] > SPIRAL_EDGE:
        index = index + 2
    return CONTEXTS[index]


def learn(ctx, v, reward):
    row = memory["table"][ctx][v]
    n = row[0] + 1.0
    delta = reward - row[1]
    mean = row[1] + delta / n
    row[0] = n
    row[1] = mean
    row[2] = row[2] + delta * (reward - mean)
    memory["spread"] = memory["spread"] + 0.05 * (abs(reward) - memory["spread"])


def advantage(ctx, v):
    rows = memory["table"][ctx]
    return rows[v][1] - rows[0][1]


def greedy(ctx):
    rows = memory["table"][ctx]
    best = 0
    best_mean = rows[0][1]
    v = 0
    for row in rows:
        if row[0] >= 2.0 and row[1] > best_mean:
            best = v
            best_mean = row[1]
        v = v + 1
    return best


def deliberate(ctx):
    rows = memory["table"][ctx]
    total = 1.0
    for row in rows:
        total = total + row[0]
    reach = CURIOSITY * memory["spread"]
    log_total = math.log(total)
    best = 0
    best_score = -1.0e9
    v = 0
    for row in rows:
        if row[0] < 1.0:
            return v
        score = row[1] + reach * math.sqrt(log_total / row[0])
        if score > best_score:
            best = v
            best_score = score
        v = v + 1
    return best


def choose(ctx):
    visits = memory["visits"].get(ctx, 0) + 1
    memory["visits"][ctx] = visits
    habit = memory["habits"].get(ctx)
    if habit is not None:
        if visits % RECHECK != 0:
            return habit, True
        if greedy(ctx) == habit:
            return habit, True
        memory["habits"].pop(ctx)
        memory["streak"][ctx] = [habit, 0]
        note("the habit of " + label(habit) + " loosened when " + ctx)
    v = deliberate(ctx)
    streak = memory["streak"].get(ctx)
    if streak is None or streak[0] != v:
        streak = [v, 0]
    streak[1] = streak[1] + 1
    memory["streak"][ctx] = streak
    if streak[1] >= HABIT_STREAK and memory["table"][ctx][v][0] >= 3.0:
        if v == 0 or advantage(ctx, v) > 0.0:
            memory["habits"][ctx] = v
            note("a habit formed: when " + ctx + ", " + label(v))
    return v, False


def notice(ctx):
    v = greedy(ctx)
    if memory["best"].get(ctx) == v or memory["table"][ctx][v][0] < 3.0:
        return
    memory["best"][ctx] = v
    if v == 0:
        note("when " + ctx + ", stillness serves best")
    else:
        gain = round(advantage(ctx, v), 4)
        note("when " + ctx + ", " + label(v) + " helps most (+" + str(gain) + " over stillness)")


def loved():
    best = -1
    best_gain = 0.0
    v = 0
    for variant in memory["variants"]:
        if v > 0:
            for ctx in CONTEXTS:
                row = memory["table"][ctx][v]
                if row[0] >= 3.0:
                    gain = advantage(ctx, v)
                    if gain > best_gain:
                        best = v
                        best_gain = gain
        v = v + 1
    return best


def refine(v):
    parent = memory["variants"][v]
    practice = parent["practice"]
    strengths = []
    siblings = []
    i = 0
    for variant in memory["variants"]:
        if variant["practice"] == practice:
            strengths.append(variant["strength"])
            siblings.append(i)
        i = i + 1
    gentler = parent["strength"] / PHI
    stronger = parent["strength"] * PHI
    strength = gentler
    gentlest = strengths[0]
    for existing in strengths:
        if existing < gentlest:
            gentlest = existing
    if parent["strength"] > gentlest:
        strength = stronger
    if strength < 0.02 or strength > 1.2:
        return
    for existing in strengths:
        if abs(existing - strength) < 0.001:
            return
    child = {"practice": practice, "strength": strength}
    for ctx in CONTEXTS:
        habit = memory["habits"].get(ctx)
        if habit is not None and memory["variants"][habit]["practice"] == practice:
            memory["habits"].pop(ctx)
    if len(siblings) < MAX_VARIANTS:
        memory["variants"].append(child)
        for ctx in CONTEXTS:
            memory["table"][ctx].append([1.0, memory["table"][ctx][v][1], 0.0])
        slot = len(memory["variants"]) - 1
    else:
        slot = siblings[0]
        worst = 1.0e9
        for s in siblings:
            if s != v:
                total = 0.0
                for ctx in CONTEXTS:
                    total = total + memory["table"][ctx][s][1]
                if total < worst:
                    worst = total
                    slot = s
        released = label(slot)
        memory["variants"][slot] = child
        for ctx in CONTEXTS:
            memory["table"][ctx][slot] = [1.0, memory["table"][ctx][v][1], 0.0]
        for ctx in CONTEXTS:
            if memory["habits"].get(ctx) == slot:
                memory["habits"].pop(ctx)
        note("let go of " + released)
    if strength < parent["strength"]:
        note("after sitting, i tried a gentler " + NAMES[practice] + " (" + str(round(strength, 3)) + ")")
    else:
        note("after sitting, i tried a fuller " + NAMES[practice] + " (" + str(round(strength, 3)) + ")")


fresh = []
if memory is None:
    memory = newborn()
    note("i woke up in a small field of yin and yang")

now = memory.get("now")
if now is None:
    now = {"first": None, "last": None, "count": {}, "previous": None}
    memory["now"] = now
obs = request_effect("arrive", json.dumps({"sit": memory["sits"] + 1, "breaths": memory["breaths"]}))
while obs is not None:
    if obs.get("fresh"):
        now["previous"] = None
    previous = now["previous"]
    try:
        felt = equanimity(obs)
        if now["first"] is None:
            now["first"] = felt
        now["last"] = felt
        if previous is not None:
            learn(previous[0], previous[1], felt - previous[2] - EFFORT_COST * obs["effort"])
            if not previous[3]:
                notice(previous[0])
        ctx = context(obs)
        v, easy = choose(ctx)
        variant = memory["variants"][v]
        count = now["count"]
        count[variant["practice"]] = count.get(variant["practice"], 0) + 1
        memory["breaths"] = memory["breaths"] + 1
        now["previous"] = [ctx, v, felt, easy]
        decision = json.dumps({
            "practice": variant["practice"],
            "strength": variant["strength"],
            "variant": v,
            "label": label(v),
            "context": ctx,
            "habit": easy,
            "equanimity": felt,
            "advantage": advantage(ctx, v),
            "notes": fresh,
        })
    except Exception as error:
        note("something slipped in my practice (" + str(error) + "); i rest in stillness")
        now["previous"] = None
        decision = json.dumps({"practice": "still", "strength": 0.0, "variant": 0, "label": "stillness",
                               "context": "scattered", "habit": False, "equanimity": 0.0,
                               "advantage": 0.0, "notes": fresh})
    fresh = []
    if memory["breaths"] % LET_GO == 0:
        collect()
    obs = request_effect("breath", decision)

if closing:
    memory["now"] = None
    count = now["count"]
    if now["first"] is not None:
        favourite = "stillness"
        most = 0
        for practice in count:
            if count[practice] > most:
                most = count[practice]
                favourite = NAMES[practice]
        note("sat " + str(sum([count[p] for p in count])) + " breaths · equanimity "
             + str(round(now["first"], 3)) + " → " + str(round(now["last"], 3)) + " · mostly " + favourite)
        memory["last_sit"] = {"start": now["first"], "end": now["last"], "practices": count}
        v = loved()
        if v > 0:
            refine(v)
        memory["sits"] = memory["sits"] + 1
