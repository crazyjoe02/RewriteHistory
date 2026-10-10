"""Simulate an All-Star Game plate appearance by plate appearance from the league's season stats.

usage: python3 tools/sim_allstar.py SEASON SEED [--write]
Reads data/{SEASON}/allstars.csv (first player listed at each position starts; pitchers in listed order)
and data/{SEASON}/{batting,pitching}.csv. Writes data/{SEASON}/allstar_game.json with --write.

Format: modern-style All-Star Game -- every rostered player appears. Reserves replace the starters
in the 5th/6th innings; pitchers work short stints (1-3 outs to an inning each) so all 14 pitch.
"""
import csv, json, random, sys, os
from collections import defaultdict

SEASON = int(sys.argv[1]); SEED = int(sys.argv[2]); WRITE = "--write" in sys.argv
BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
D = os.path.join(BASE, "data", str(SEASON))
rng = random.Random(SEED)

AWAY, HOME = "AA", "NL"             # game at the Polo Grounds (NL park) -> NL is the home side
LABEL = {AWAY: f"{SEASON} AA", HOME: f"{SEASON} NL"}
POS_ORDER = ["C", "1B", "2B", "3B", "SS", "LF", "CF", "RF"]

def dn(raw):
    l, f = [p.strip() for p in raw.split(",", 1)]
    return f"{f} {l}"
def num(x):
    try: return float(str(x).replace(",", ""))
    except: return 0.0
def ab(name):
    first, last = name.split(" ", 1)
    return f"{first[0]}.{last}"

BAT = {dn(r["Player"]): r for r in csv.DictReader(open(os.path.join(D, "batting.csv")))}
PIT = {dn(r["Player"]): r for r in csv.DictReader(open(os.path.join(D, "pitching.csv")))}

# ---- league baselines -------------------------------------------------------------------
lg = defaultdict(float)
for r in BAT.values():
    for k in ["PA", "H", "2B", "3B", "HR", "BB", "HBP", "SO", "SB", "CS", "AB"]:
        lg[k] += num(r.get(k))
L = {"bb": lg["BB"]/lg["PA"], "hbp": lg["HBP"]/lg["PA"], "so": lg["SO"]/lg["PA"], "hr": lg["HR"]/lg["PA"]}
lg_bip = lg["PA"] - lg["BB"] - lg["HBP"] - lg["SO"] - lg["HR"]
L["hit_bip"] = (lg["H"] - lg["HR"]) / lg_bip
L["x2"] = lg["2B"]/(lg["H"]-lg["HR"]); L["x3"] = lg["3B"]/(lg["H"]-lg["HR"])

def shrink(k, n, prior, w):
    return (k + prior*w) / (n + w)

def batter_rates(name):
    r = BAT.get(name, {})
    pa = num(r.get("PA")); w = 60  # regress toward league (pitchers with few PA lean on league-wide pitcher-ish rates)
    h, d, t, hr = num(r.get("H")), num(r.get("2B")), num(r.get("3B")), num(r.get("HR"))
    bb, hbp, so = num(r.get("BB")), num(r.get("HBP")), num(r.get("SO"))
    pen = 0.75 if pa < 150 else 1.0   # weak-hitting pitchers
    bip = max(pa - bb - hbp - so - hr, 1)
    singles_etc = h - hr
    return {
        "bb": shrink(bb, pa, L["bb"], w), "hbp": shrink(hbp, pa, L["hbp"], w),
        "so": shrink(so, pa, L["so"]*(1.4 if pa < 150 else 1), w), "hr": shrink(hr, pa, L["hr"], w)*pen,
        "hit_bip": shrink(singles_etc, bip, L["hit_bip"]*pen, w),
        "x2": shrink(d, max(singles_etc, 1), L["x2"], 20), "x3": shrink(t, max(singles_etc, 1), L["x3"], 20),
        "sb_att": (num(r.get("SB")) + num(r.get("CS")) + 2) / (h - d - t - hr + bb + hbp + 20),
        "sb_pct": (num(r.get("SB")) + 6) / (num(r.get("SB")) + num(r.get("CS")) + 10),
        "gbfb": (num(r.get("GB")) + 30) / (num(r.get("GB")) + num(r.get("FB")) + 60),
    }

def pitcher_rates(name):
    r = PIT[name]; bf = num(r["BFP"]); w = 150
    h, hr, bb, so, hbp = num(r["H"]), num(r["HR"]), num(r["BB"]), num(r["SO"]), num(r["HBP"])
    bip = max(bf - bb - hbp - so - hr, 1)
    return {"bb": shrink(bb, bf, L["bb"], w), "hbp": shrink(hbp, bf, L["hbp"], w),
            "so": shrink(so, bf, L["so"], w), "hr": shrink(hr, bf, L["hr"], w),
            "hit_bip": shrink(h - hr, bip, L["hit_bip"], w), "wp": (num(r.get("WP")) + 2) / (bf + 200)}

def odds(b, p, l):
    if l <= 0: return b
    x = (b*p/l) / (b*p/l + (1-b)*(1-p)/(1-l))
    return min(max(x, 0.0), 0.95)

# ---- rosters ------------------------------------------------------------------------------
roster = {AWAY: defaultdict(list), HOME: defaultdict(list)}
team_of = {}
for r in csv.DictReader(open(os.path.join(D, "allstars.csv"))):
    roster[r["League"]][r["Pos"]].append(r["Player"]); team_of[r["Player"]] = r["Team"]

def ops(n):
    r = BAT[n]; return num(r["OBP"]) + num(r["SLG"])

def lineup(lgk):
    starters = {p: roster[lgk][p][0] for p in POS_ORDER}
    names = list(starters.values())
    by_obp = sorted(names, key=lambda n: -(num(BAT[n]["OBP"]) + 0.002*num(BAT[n]["SB"])))
    order = [by_obp[0]]
    rest = [n for n in names if n not in order]
    rest.sort(key=lambda n: -num(BAT[n]["OBP"])); order.append(rest.pop(0))
    rest.sort(key=lambda n: -ops(n)); order.append(rest.pop(0))
    rest.sort(key=lambda n: -num(BAT[n]["SLG"])); order.append(rest.pop(0))
    rest.sort(key=lambda n: -ops(n)); order += rest
    pos_of = {v: k for k, v in starters.items()}
    return [{"name": n, "pos": pos_of[n]} for n in order]

pitch_plan = {
    # outs each pitcher is scheduled to get (in roster order: SPs then RPs)
    HOME: [3, 3, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1, 1, 1],   # NL pitches the top halves: 27 outs
    AWAY: [3, 2, 2, 2, 2, 2, 2, 2, 2, 1, 1, 1, 1, 1],   # AA pitches the bottom halves: 24 outs (+ 9th if needed)
}
staff = {t: roster[t]["SP"] + roster[t]["RP"] for t in (AWAY, HOME)}

# reserves enter: catchers/IF in the 5th, OF + rest in the 6th (when that team takes the field)
SUB_INNING = {"C": 5, "1B": 5, "2B": 5, "3B": 6, "SS": 5, "LF": 6, "CF": 6, "RF": 6}

# ---- game state ---------------------------------------------------------------------------
order = {t: lineup(t) for t in (AWAY, HOME)}
slot_hist = {t: [[o["name"]] for o in order[t]] + [[]] for t in (AWAY, HOME)}   # 9th slot = pitchers
for t in (AWAY, HOME):
    order[t].append({"name": staff[t][0], "pos": "P"})
    slot_hist[t][8] = [staff[t][0]]
pos_label = {}   # player -> position string for box
for t in (AWAY, HOME):
    for o in order[t]: pos_label[o["name"]] = o["pos"]
defense = {t: {o["pos"]: o["name"] for o in order[t]} for t in (AWAY, HOME)}
cur_p = {t: 0 for t in (AWAY, HOME)}
p_outs = {t: 0 for t in (AWAY, HOME)}
nxt = {t: 0 for t in (AWAY, HOME)}
subs_done = {t: set() for t in (AWAY, HOME)}

BS = defaultdict(lambda: defaultdict(int))   # batting stats
PS = defaultdict(lambda: defaultdict(int))   # pitching stats (outs, h, r, er, bb, so, hr, bf)
p_appear = {t: [staff[t][0]] for t in (AWAY, HOME)}
foot = {t: defaultdict(list) for t in (AWAY, HOME)}
two_out_rbi = defaultdict(int)
errors = defaultdict(int)
score = {AWAY: 0, HOME: 0}; hits = {AWAY: 0, HOME: 0}; errs = {AWAY: 0, HOME: 0}
line = {AWAY: [], HOME: []}
pbp = []
lead_events = []   # (team that took lead, winning pitcher candidate, losing pitcher charged)

def pitcher(t): return staff[t][cur_p[t]]
def other(t): return HOME if t == AWAY else AWAY

FIELD_DIR = {"1B": "1B", "2B": "2B", "SS": "SS", "3B": "3B", "P": "the pitcher", "LF": "LF", "CF": "CF", "RF": "RF",
             "LCF": "LCF", "RCF": "RCF", "C": "C"}

def bring_pitcher(fteam, plays):
    """Move to the next pitcher if the current one met his outs target and someone is left."""
    left_after = len(staff[fteam]) - cur_p[fteam] - 1
    if left_after <= 0: return
    total = sum(PS[n]["outs"] for n in p_appear[fteam])
    remaining = sum(pitch_plan[fteam]) - total
    due = p_outs[fteam] >= pitch_plan[fteam][cur_p[fteam]]
    squeeze = (remaining <= left_after and p_outs[fteam] >= 1) or (remaining <= left_after and PS[pitcher(fteam)]["bf"] >= 1)
    if due or squeeze:
        cur_p[fteam] += 1; p_outs[fteam] = 0
        new = pitcher(fteam)
        p_appear[fteam].append(new)
        plays.append(f"{ab(new)} enters the game to pitch.")
        # new pitcher takes over the pitcher's batting slot
        for o in order[fteam]:
            if o["pos"] == "P": o["name"] = new
        slot_hist[fteam][8].append(new); pos_label[new] = "P"; defense[fteam]["P"] = new

def do_subs(fteam, inning, plays):
    for i, o in enumerate(order[fteam]):
        pos = o["pos"]
        if pos == "P" or pos in subs_done[fteam] or SUB_INNING[pos] != inning: continue
        res = roster[fteam][pos][1]
        o["name"] = res; defense[fteam][pos] = res; subs_done[fteam].add(pos)
        slot_hist[fteam][i].append(res); pos_label[res] = pos
        plays.append(f"{ab(res)} enters the game at {pos} as a defensive replacement.")

def run_scores(bteam, runner, plays_txt_parts, unearned=False, rbi_to=None, outs=0):
    score[bteam] += 1
    BS[runner["name"]]["r"] += 1
    resp = runner["resp"]
    PS[resp]["r"] += 1
    if not (runner.get("ue") or unearned): PS[resp]["er"] += 1
    if rbi_to:
        BS[rbi_to]["rbi"] += 1
        if outs == 2: two_out_rbi[rbi_to] += 1
    plays_txt_parts.append(f"{ab(runner['name'])} scores.")
    # lead change bookkeeping
    if score[bteam] == score[other(bteam)] + 1:
        lead_events.append((bteam, pitcher(bteam), resp))

def half(inning, top):
    bteam = AWAY if top else HOME; fteam = other(bteam)
    plays = []
    if inning > 1 or not top:
        pass
    if inning == 1:
        plays.append(f"{ab(pitcher(fteam))} enters the game to pitch.")
    do_subs(fteam, inning, plays)
    bring_pitcher(fteam, plays)
    outs = 0; bases = [None, None, None]; runs_before = score[bteam]
    while outs < 3:
        # walk-off check happens after each PA below
        slot = nxt[bteam]; batter = order[bteam][slot]["name"]; nxt[bteam] = (slot + 1) % 9
        pit = pitcher(fteam); br = batter_rates(batter); pr = pitcher_rates(pit)
        BS[batter]["pa"] += 1; PS[pit]["bf"] += 1
        # stolen base attempt before the pitch result (runner on 1st, 2nd open)
        if bases[0] and not bases[1] and outs < 2 and rng.random() < batter_rates(bases[0]["name"])["sb_att"]*0.9:
            rn = bases[0]
            if rng.random() < batter_rates(rn["name"])["sb_pct"]:
                plays.append(f"{ab(rn['name'])} {rng.choice(['steals 2B.','swipes 2B.','steals second base.'])}")
                BS[rn["name"]]["sb"] += 1; bases[1] = rn; bases[0] = None
            else:
                plays.append(f"{ab(rn['name'])} {rng.choice(['is caught stealing 2B.','is nailed stealing 2B.','is caught trying to steal 2B.'])}")
                BS[rn["name"]]["cs"] += 1; bases[0] = None; outs += 1; PS[pit]["outs"] += 1; p_outs[fteam] += 1
                if outs == 3:
                    BS[batter]["pa"] -= 1; PS[pit]["bf"] -= 1; nxt[bteam] = slot; break
        # wild pitch / passed ball
        if any(bases) and rng.random() < pr["wp"]*1.2:
            parts = [f"{ab(pit)} uncorks a wild pitch and all runners advance."]
            if bases[2]: run_scores(bteam, bases[2], parts)
            bases = [None, bases[0], bases[1]]
            plays.append(" ".join(parts))
            if inning >= 9 and not top and score[HOME] > score[AWAY]:
                BS[batter]["pa"] -= 1; PS[pit]["bf"] -= 1; break
        pbb = odds(br["bb"], pr["bb"], L["bb"]); phbp = odds(br["hbp"], pr["hbp"], L["hbp"])
        pso = odds(br["so"], pr["so"], L["so"]); phr = odds(br["hr"], pr["hr"], L["hr"])
        x = rng.random()
        me = {"name": batter, "resp": pit}
        parts = []
        if x < pbb or (pbb <= x < pbb + phbp):
            hbp = x >= pbb
            txt = rng.choice(["takes a pitch off the arm.", "is hit by the pitch."]) if hbp else rng.choice(
                ["draws the walk.", "takes ball four.", "walks.", "is issued the free pass."])
            parts.append(f"{ab(batter)} {txt}")
            if hbp: BS[batter]["hbp"] += 1; foot[bteam]["HBP"].append(ab(batter))
            else: BS[batter]["bb"] += 1; PS[pit]["bb"] += 1
            # force advances
            if bases[0]:
                if bases[1]:
                    if bases[2]: run_scores(bteam, bases[2], parts, rbi_to=batter, outs=outs)
                    bases[2] = bases[1]
                bases[1] = bases[0]
            bases[0] = me
        elif x < pbb + phbp + pso:
            BS[batter]["ab"] += 1; BS[batter]["so"] += 1; PS[pit]["so"] += 1
            parts.append(f"{ab(batter)} " + rng.choice(["strikes out swinging.", "swings and misses for strike 3.",
                         "is frozen on strike 3.", "takes strike 3 looking.", "strikes out on a ball out of the zone."]))
            outs += 1; PS[pit]["outs"] += 1; p_outs[fteam] += 1
        elif x < pbb + phbp + pso + phr:
            BS[batter]["ab"] += 1; BS[batter]["h"] += 1; BS[batter]["hr"] += 1; PS[pit]["h"] += 1; PS[pit]["hr"] += 1
            hits[bteam] += 1
            n = 1 + sum(1 for b in bases if b)
            where = rng.choice(["LF", "LCF", "CF", "RCF", "RF"])
            kind = {1: "a solo homer", 2: "a 2-run homer", 3: "a 3-run homer", 4: "a grand slam"}[n]
            parts.append(f"{ab(batter)} {rng.choice(['crushes','hits','launches'])} {kind} to {where}.")
            for b in (bases[2], bases[1], bases[0]):
                if b:
                    score[bteam] += 1; BS[b["name"]]["r"] += 1; PS[b["resp"]]["r"] += 1
                    if not b.get("ue"): PS[b["resp"]]["er"] += 1
                    if score[bteam] == score[other(bteam)] + 1: lead_events.append((bteam, pitcher(bteam), b["resp"]))
            score[bteam] += 1; BS[batter]["r"] += 1; PS[pit]["r"] += 1; PS[pit]["er"] += 1
            if score[bteam] == score[other(bteam)] + 1: lead_events.append((bteam, pitcher(bteam), pit))
            BS[batter]["rbi"] += n
            if outs == 2: two_out_rbi[batter] += n
            bases = [None, None, None]
        else:
            BS[batter]["ab"] += 1
            phit = odds(br["hit_bip"], pr["hit_bip"], L["hit_bip"])
            if rng.random() < phit:
                y = rng.random()
                kind = 3 if y < br["x3"] else 2 if y < br["x3"] + br["x2"] else 1
                BS[batter]["h"] += 1; PS[pit]["h"] += 1; hits[bteam] += 1
                if kind == 1:
                    parts.append(f"{ab(batter)} " + rng.choice(["lines a single to LF.", "grounds a single to RF.",
                        "hits a groundball single to CF.", "bloops a single to LCF.", "grounds it thru the hole to LF for a single.",
                        "hits an infield single to SS.", "smokes a line drive single to RCF.", "grounds it past the mound into CF for a single."]))
                    new = [me, None, None]
                    if bases[2]: run_scores(bteam, bases[2], parts, rbi_to=batter, outs=outs)
                    if bases[1]:
                        if rng.random() < (0.75 if outs == 2 else 0.55): run_scores(bteam, bases[1], parts, rbi_to=batter, outs=outs)
                        else: new[2] = bases[1]
                    if bases[0]:
                        if new[2] is None and rng.random() < 0.3: new[2] = bases[0]; parts.append(f"{ab(bases[0]['name'])} advances to 3B.")
                        else: new[1] = bases[0]
                    bases = new
                elif kind == 2:
                    BS[batter]["2b"] += 1
                    parts.append(f"{ab(batter)} " + rng.choice(["rips a liner to LCF for a double.", "hits a flyball double to RF.",
                        "smokes a linedrive double down the leftfield line.", "hits a line drive double to RCF.", "skies one to CF that falls in for a double."]))
                    new = [None, me, None]
                    for b in (bases[2], bases[1]):
                        if b: run_scores(bteam, b, parts, rbi_to=batter, outs=outs)
                    if bases[0]:
                        if rng.random() < (0.6 if outs == 2 else 0.4): run_scores(bteam, bases[0], parts, rbi_to=batter, outs=outs)
                        else: new[2] = bases[0]
                    bases = new
                else:
                    BS[batter]["3b"] += 1
                    parts.append(f"{ab(batter)} hits a triple.")
                    for b in (bases[2], bases[1], bases[0]):
                        if b: run_scores(bteam, b, parts, rbi_to=batter, outs=outs)
                    bases = [None, None, me]
            else:
                # ball in play, fielded: error chance, else out
                gb = rng.random() < br["gbfb"]
                if rng.random() < 0.055:
                    fpos = rng.choice(["SS", "3B", "2B", "1B"]) if gb else rng.choice(["LF", "CF", "RF"])
                    fielder = defense[fteam][fpos]; errors[fielder] += 1; errs[fteam] += 1
                    foot[fteam]["E"].append(fielder)
                    txt = rng.choice([f"{ab(fielder)} boots a routine grounder and {ab(batter)} reaches on the error.",
                                      f"{ab(fielder)} fields the groundball but makes a bad throw to 1B. {ab(batter)} reaches on the throwing error."]) if gb else \
                          f"{ab(fielder)} misplays a lazy flyball and {ab(batter)} reaches on the error."
                    parts.append(txt)
                    me["ue"] = True
                    new = [me, None, None]
                    if bases[2]: run_scores(bteam, bases[2], parts, unearned=True)
                    if bases[1]: new[2] = bases[1]
                    if bases[0]: new[1] = bases[0]
                    bases = new
                elif gb:
                    fpos = rng.choice(["SS", "SS", "2B", "2B", "3B", "3B", "1B", "P"])
                    if bases[0] and outs < 2 and rng.random() < 0.45:
                        dp = {"SS": "6-4-3", "2B": "4-6-3", "3B": "5-4-3", "1B": "3-6-3", "P": "1-6-3"}[fpos]
                        parts.append(f"{ab(batter)} grounds into a {dp} double play.")
                        BS[batter]["gidp"] += 1
                        outs += 2; PS[pit]["outs"] += 2; p_outs[fteam] += 2
                        new = [None, None, None]
                        if outs < 3:
                            if bases[2]: run_scores(bteam, bases[2], parts)
                            if bases[1]: new[2] = bases[1]
                        bases = new
                    elif bases[0] and outs < 2 and rng.random() < 0.5:
                        fc = {"SS": "6-4", "2B": "4-6", "3B": "5-4", "1B": "3-6", "P": "1-6"}[fpos]
                        parts.append(f"{ab(batter)} hits into a {fc} fielder's choice.")
                        outs += 1; PS[pit]["outs"] += 1; p_outs[fteam] += 1
                        new = [me, None, None]
                        if bases[2]: run_scores(bteam, bases[2], parts)
                        if bases[1]: new[2] = bases[1]
                        bases = new
                    else:
                        tgt = FIELD_DIR[fpos]
                        parts.append(f"{ab(batter)} grounds out to {tgt}.")
                        outs += 1; PS[pit]["outs"] += 1; p_outs[fteam] += 1
                        if outs < 3:
                            new = [None, bases[0], bases[1]]
                            if bases[2]:
                                if rng.random() < 0.5:
                                    run_scores(bteam, bases[2], parts, rbi_to=batter, outs=outs-1)
                                else: new[2] = bases[2]
                            bases = new
                else:
                    where = rng.choice(["LF", "CF", "RF", "LCF", "RCF", "SS", "2B", "3B"])
                    if where in ("SS", "2B", "3B"):
                        parts.append(f"{ab(batter)} pops out to {where}.")
                        outs += 1; PS[pit]["outs"] += 1; p_outs[fteam] += 1
                    else:
                        deep = rng.random() < 0.4
                        parts.append(f"{ab(batter)} " + (f"flies out to deep {where}." if deep else rng.choice(
                            [f"hits a shallow flyout to {where}.", f"flies out to {where}.", f"lines out to {where}."])))
                        outs += 1; PS[pit]["outs"] += 1; p_outs[fteam] += 1
                        if bases[2] and outs < 3 and rng.random() < (0.7 if deep else 0.25):
                            BS[batter]["ab"] -= 1; BS[batter]["sf"] += 1; foot[bteam]["SF"].append(ab(batter))
                            run_scores(bteam, bases[2], parts, rbi_to=batter, outs=outs-1); bases[2] = None
        plays.append(" ".join(parts))
        if inning >= 9 and not top and score[HOME] > score[AWAY]:
            break   # walk-off
        if outs < 3:
            bring_pitcher(fteam, plays)
    line[bteam].append(score[bteam] - runs_before)
    pbp.append({"inning": inning, "half": "Top" if top else "Bottom", "team": bteam, "plays": plays,
                "score_after": {"away": {"team": LABEL[AWAY], "r": score[AWAY], "h": hits[AWAY], "e": errs[AWAY]},
                                "home": {"team": LABEL[HOME], "r": score[HOME], "h": hits[HOME], "e": errs[HOME]}}})

inning = 0
while True:
    inning += 1
    half(inning, True)
    if inning >= 9 and score[HOME] > score[AWAY]:
        line[HOME].append(None); break
    half(inning, False)
    if inning >= 9 and score[HOME] != score[AWAY]:
        break

# ---- decisions ------------------------------------------------------------------------------
winner = HOME if score[HOME] > score[AWAY] else AWAY; loser = other(winner)
last_lead = [e for e in lead_events if e[0] == winner][-1]
# the winning team's pitcher of record when it took the lead for good
W = last_lead[1]; Lp = last_lead[2]
SV = None
fin = p_appear[winner][-1]
if fin != W:
    SV = fin   # finished the game protecting the lead in an exhibition: credit the save

def ipstr(o): return f"{o//3}.{o%3}"
def mkfoot(t):
    names = [x for slot in slot_hist[t] for x in slot]
    f = {}
    def lst(key, field):
        out = []
        for n in names:
            v = BS[n][field]
            if v: out.append(f"{ab(n)}" + (f" {v}" if v > 1 else "") + f" ({v})")
        if out: f[key] = ", ".join(out)
    lst("2B", "2b"); lst("3B", "3b"); lst("HR", "hr")
    rb = [f"{ab(n)}" + (f" {BS[n]['rbi']}" if BS[n]["rbi"] > 1 else "") for n in names if BS[n]["rbi"]]
    if rb: f["RBI"] = ", ".join(rb)
    tw = [f"{ab(n)}" + (f" {two_out_rbi[n]}" if two_out_rbi[n] > 1 else "") for n in names if two_out_rbi.get(n)]
    if tw: f["2-Out RBI"] = ", ".join(tw)
    if foot[t]["SF"]: f["SF"] = ", ".join(foot[t]["SF"])
    if foot[t]["HBP"]: f["HBP"] = ", ".join(foot[t]["HBP"])
    lst("SB", "sb"); lst("CS", "cs")
    e = [f"{ab(n)}" + (f" {errors[n]}" if errors[n] > 1 else "") + f" ({errors[n]})" for n in names if errors.get(n)]
    if e: f["E"] = ", ".join(e)
    return f

game = {"season": SEASON, "date": f"{SEASON}-07-06", "location": "Polo Grounds (IV)",
        "subtitle": f"Exhibition Game — Tuesday, July 6, {SEASON} · Polo Grounds, New York City"
                    + (f" ({inning} innings)" if inning > 9 else ""),
        "linescore": {"innings": list(range(1, inning + 1)), "rows": [
            {"team": AWAY, "label": LABEL[AWAY], "by_inning": line[AWAY], "R": score[AWAY], "H": hits[AWAY], "E": errs[AWAY]},
            {"team": HOME, "label": LABEL[HOME], "by_inning": line[HOME], "R": score[HOME], "H": hits[HOME], "E": errs[HOME]}]},
        "batting": {}, "pitching": {}, "playbyplay": pbp}
for t in (AWAY, HOME):
    rows = []
    for i, slot in enumerate(slot_hist[t]):
        for n in slot:
            s = BS[n]
            rows.append({"player": n, "pos": pos_label[n], "ab": s["ab"], "r": s["r"], "h": s["h"], "rbi": s["rbi"],
                         "bb": s["bb"], "so": s["so"], "2b": s["2b"], "3b": s["3b"], "hr": s["hr"], "sb": s["sb"], "cs": s["cs"]})
    tot = {k: sum(r[k] for r in rows) for k in ["ab", "r", "h", "rbi", "bb", "so", "2b", "3b", "hr", "sb", "cs"]}
    game["batting"][t] = {"rows": rows, "totals": tot, "footnotes": mkfoot(t)}
    prow = []; touts = 0
    for n in p_appear[t]:
        s = PS[n]; touts += s["outs"]
        dec = "W (1-0)" if n == W else "L (0-1)" if n == Lp else "SV (1)" if n == SV else ""
        era = f"{s['er']*27/s['outs']:.2f}" if s["outs"] else ("∞" if s["er"] else "0.00")
        prow.append({"player": n, "decision": dec, "ip": ipstr(s["outs"]), "h": s["h"], "r": s["r"], "er": s["er"],
                     "bb": s["bb"], "so": s["so"], "hr": s["hr"], "era": era})
    game["pitching"][t] = {"rows": prow, "totals": {"ip": ipstr(touts), **{k: sum(r[k] for r in prow) for k in ["h", "r", "er", "bb", "so", "hr"]}}}

# player of the game: best line on the winning side
def gs(n): s = BS[n]; return s["h"] + s["2b"] + 2*s["3b"] + 3*s["hr"] + 1.5*s["rbi"] + s["r"] + 0.5*s["bb"] + 0.5*s["sb"]
best = max([x for slot in slot_hist[winner] for x in slot], key=gs)
s = BS[best]
note = f"{s['rbi']} RBI" if s["rbi"] >= 2 else (f"collects {s['h']} hits" if s["h"] >= 2 else f"scores {s['r']} run" + ("s" if s["r"] != 1 else ""))
if s["hr"]: note = f"homers{' twice' if s['hr']>1 else ''}, {s['rbi']} RBI"
game["player_of_game"] = {"player": best, "team": winner, "note": note}

# ---- sanity checks ---------------------------------------------------------------------------
everyone = {n for t in (AWAY, HOME) for slot in slot_hist[t] for n in slot}
rostered = {n for t in (AWAY, HOME) for p in roster[t] for n in roster[t][p]}
missing = rostered - everyone
for t in (AWAY, HOME):
    bt = game["batting"][t]["totals"]; ls = game["linescore"]["rows"][0 if t == AWAY else 1]
    assert bt["r"] == ls["R"] == sum(x or 0 for x in ls["by_inning"]), (t, bt, ls)
    assert bt["h"] == ls["H"], t
    assert game["pitching"][other(t)]["totals"]["h"] == ls["H"] and game["pitching"][other(t)]["totals"]["r"] == ls["R"], t
print(f"seed {SEED}: AA {score[AWAY]}-{hits[AWAY]}-{errs[AWAY]}  NL {score[HOME]}-{hits[HOME]}-{errs[HOME]}  inn {inning}"
      f"  W {W}  L {Lp}  SV {SV}  PoG {best} ({note})  missing {sorted(missing)}")
if WRITE:
    json.dump(game, open(os.path.join(D, "allstar_game.json"), "w"), indent=1)
    print("written")
