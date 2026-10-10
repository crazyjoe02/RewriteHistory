"""Starter/Reliever and vs-LHB/RHB pitching splits rebuilt from the stored play-by-play.

Each plate appearance is charged to the pitcher on the mound; outs (batter and runner outs)
are counted per play so innings pitched can be split by batter handedness.  Runs are charged
to the pitcher (and batter hand) responsible for the runner who scored; a pitcher-game's
earned runs are then shared across those runs pro rata (exact whenever all of a pitcher's
runs in a game were earned or all unearned)."""
import csv, json, os, re
from collections import defaultdict

NM = r"[A-Z]\.[A-Z][A-Za-z']+"
ALIAS = {"Blue Lew Hardtack": "B.Hardtack"}


def abbr(full):
    if full in ALIAS:
        return ALIAS[full]
    p = full.split(" ", 1)
    return p[0][0] + "." + p[1].replace(" ", "") if len(p) > 1 else full


def clean(p):
    p = re.sub(r'^\[[A-Z+, /]*\]\s*', '', p.strip().strip('"'))
    p = re.sub(r'^[A-Z+]{1,8}\s*\|\s*', '', p)
    p = re.sub(r'^[A-Z+]{2,8}\s+(?=[A-Z]\.)', '', p)
    return p.strip()


RUNNER_OUT = [r"is gunned down", r"is thrown out", r"is out at", r"is called out", r"is caught", r"is nailed", r"is picked off",
              r"doubled off", r"is tagged out", r"is out on the front end", r"is out trying", r"is retired"]


def classify(p, first):
    """Return a dict describing the batter's plate appearance (or None for non-PA lines) and outs on the play."""
    runner_outs = 0
    for pat in RUNNER_OUT:
        for m in re.finditer("(" + NM + ") " + pat, p):
            runner_outs += 1
    if re.match(NM + r" (?:steals|swipes)\b", p) or re.match(NM + r" (?:is (?:caught|nailed|out on the front end|called out on the front end|picked off)|is caught stealing)", p):
        return None, runner_outs
    if any(k in p for k in ("wild pitch", "passed ball", "balk", "lets one get away", "pickoff attempt",
                            "can't handle the pitch", "can't hold onto the pitch", "returns to the plate")):
        return None, runner_outs
    if "steal of home" in p:
        return None, runner_outs
    if ("double steal" in p or "each steal" in p) and not re.search(r"strike 3|strikes out|strike three", p):
        return None, runner_outs
    e = dict(ab=1, h=0, d=0, t=0, hr=0, bb=0, hbp=0, so=0, sh=0, sf=0, outs=0)
    rb = len(re.findall("(" + NM + r")(?: [a-z][a-z ,']*?)? scores", p))
    if (re.search(NM + r" reaches", p) and re.search(r"error", p)) or "charged with an error" in p:
        if "sacrifice" in p or "bunt" in p and "sacrifice" in p:
            e.update(ab=0, sh=1)
        return e, runner_outs
    if re.search(r"strike 3|strikes out|strike three", p):
        e.update(so=1, outs=1); return e, runner_outs
    if "triple play" in p:
        e["outs"] = 3; return e, 0
    if "double play" in p or "doubled off" in p or "double off" in p:
        e["outs"] = 2; return e, 0
    if re.search(r"homer|home ?run|grand slam", p):
        e.update(h=1, hr=1); return e, runner_outs
    if re.search(r"\btriple\b", p) or re.search(r"\bdoubles?\b|2-base hit", p) or "single" in p or "Texas Leaguer" in p:
        e["h"] = 1
        if re.search(r"\btriple\b", p): e["t"] = 1
        elif re.search(r"\bdoubles?\b|2-base hit", p) and "single" not in p: e["d"] = 1
        return e, runner_outs
    if re.search(r"walk|ball four|free pass", p):
        e.update(ab=0, bb=1); return e, runner_outs
    if re.search(r"by a pitch|pitch off|drilled|plunked|hit in the", p):
        e.update(ab=0, hbp=1); return e, runner_outs
    if re.search(r"strike 3|strikes out|strike three", p):
        e.update(so=1, outs=1); return e, runner_outs
    if "sacrifice bunt" in p:
        e.update(ab=0, sh=1, outs=1); return e, runner_outs
    if "is called safe" in p or "the runner is safe" in p:
        return e, runner_outs
    if "beats the throw" in p or "throws to second for the force" in p or "fielder's choice" in p:
        e["outs"] = 1; return e, runner_outs
    if rb and re.search(r"fl(?:ies|y)out|flies out|lines out|pops out|fouls out", p):
        e.update(ab=0, sf=1, outs=1); return e, runner_outs
    e["outs"] = 1
    return e, runner_outs


class PBPSplits:
    """Accumulates per pitcher: self.acc[name][key][stat] where key is 'Starter'/'Reliever',
    'L'/'R' (batter hand) or 'Home'/'Away'."""
    STATS = ("BF", "ab", "h", "d", "t", "hr", "bb", "hbp", "so", "sh", "sf", "outs", "R", "ER")

    def __init__(self, data_dir, season, disp):
        self.acc = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
        self.issues = []
        d = os.path.join(data_dir, str(season))
        self.bats = {disp(r["Player"]): r.get("B", "R") for r in csv.DictReader(open(os.path.join(d, "batting.csv")))}
        self.throws = {disp(r["Player"]): list(r.values())[4] for r in csv.DictReader(open(os.path.join(d, "pitching.csv")))}
        for g in json.load(open(os.path.join(d, "games.json"))):
            self._game(g)

    def _hand(self, batter, pit):
        b = self.bats.get(batter, "R")
        if b == "S":
            b = "L" if self.throws.get(pit, "R") == "R" else "R"
        return b if b in ("L", "R") else "R"

    def _game(self, g):
        names = {}
        for team in (g["away"], g["home"]):
            m = {}
            for r in g["batting"].get(team, {}).get("rows", []) + g["pitching"].get(team, {}).get("rows", []):
                m[abbr(r["player"])] = r["player"]
            names[team] = m
        starters = {t: v["rows"][0]["player"] for t, v in g["pitching"].items() if v["rows"]}
        cur = dict(starters)
        resp = {}                                                  # runner -> (pitcher, hand)
        charged = defaultdict(lambda: defaultdict(float))          # pitcher -> hand -> runs charged
        onbase = defaultdict(lambda: defaultdict(float))           # pitcher -> hand -> baserunners (fallback)
        for hf in g["playbyplay"]:
            bat = hf["team"]; fld = g["home"] if bat == g["away"] else g["away"]
            venue = "Home" if fld == g["home"] else "Away"
            outs_half, pending, last_keys, pending_pit = 0, 0, None, None
            for raw in hf["plays"]:
                p = clean(raw)
                nms = re.findall(NM, p)
                if not nms:
                    continue
                if "enters the game to pitch" in p:
                    full = names[fld].get(nms[0])
                    if full:
                        cur[fld] = full
                    continue
                if any(k in p for k in ("enters the game", "remains in the game", "moves to")):
                    continue
                pit = cur.get(fld)
                batter = names[bat].get(nms[0], nms[0])
                ev, rout = classify(p, nms[0])
                scorers = [names[bat].get(s, s) for s in re.findall("(" + NM + r")(?: [a-z][a-z ,']*?)? scores", p)]
                if rout:
                    for m in re.finditer("(" + NM + r") (?:is (?:caught|nailed|picked off|thrown out|out at|called out|tagged out|gunned down|out on the front end))", p):
                        resp.pop(names[bat].get(m.group(1), m.group(1)), None)
                if ev is None:
                    if rout and pending_pit not in (None, pit) and last_keys:
                        pass
                    if rout:
                        if pending and pending_pit != pit and last_keys:
                            lp, lh, lr, lv = last_keys
                            for k in (lr, lh, lv):
                                self.acc[pending_pit][k]["outs"] += pending
                            pending = 0
                        pending_pit = pit
                    pending += rout                    # runner outs: charged to the next batter's PA
                    outs_half += rout
                    for s in scorers:
                        pr, hb = resp.pop(s, (pit, last_keys[1] if last_keys else "R"))
                        charged[pr][hb] += 1
                    continue
                hand = self._hand(batter, pit)
                role = "Starter" if pit == starters.get(fld) else "Reliever"
                if pending and pending_pit != pit:     # pitcher changed after a runner out
                    prole = "Starter" if pending_pit == starters.get(fld) else "Reliever"
                    for k in (prole, last_keys[1] if last_keys else hand, venue):
                        self.acc[pending_pit][k]["outs"] += pending
                    pending = 0
                keys = (role, hand, venue)
                o = ev["outs"] + rout + pending
                pending = 0
                for k in keys:
                    a = self.acc[pit][k]
                    a["BF"] += 1
                    for st in ("ab", "h", "d", "t", "hr", "bb", "hbp", "so", "sh", "sf"):
                        a[st] += ev[st]
                    a["outs"] += o
                outs_half += ev["outs"] + rout
                last_keys = (pit, hand, role, venue)
                reached = ev["h"] or ev["bb"] or ev["hbp"] or (ev["outs"] == 0) or "beats the throw" in p \
                    or "fielder's choice" in p or "throws to second for the force" in p
                if ev["h"] or ev["bb"] or ev["hbp"]:
                    onbase[pit][hand] += 1
                for s in scorers:
                    if s == batter:
                        continue
                    pr, hb = resp.pop(s, (pit, hand))
                    charged[pr][hb] += 1
                if ev["hr"]:
                    mm = re.search(r"(\d)-run", p)
                    n = int(mm.group(1)) if mm else (4 if "grand slam" in p else 1)
                    for _ in range(max(0, n - 1 - len(scorers))):
                        charged[pit][hand] += 1
                    charged[pit][hand] += 1
                    resp.pop(batter, None)
                elif batter in scorers:
                    charged[pit][hand] += 1
                elif reached:
                    resp[batter] = (pit, hand)
            if pending and last_keys:                  # inning ended on a runner out
                _, hand, _, venue = last_keys
                prole = "Starter" if pending_pit == starters.get(fld) else "Reliever"
                for k in (prole, hand, venue):
                    self.acc[pending_pit][k]["outs"] += pending
            if outs_half != 3 and hf is not g["playbyplay"][-1]:
                self.issues.append(("outs", g["game_num"], g["away"], g["home"], hf["inning"], hf["half"], outs_half))
        # Tie runs/earned runs back to each pitcher's box-score line, shared by hand pro rata
        for t, v in g["pitching"].items():
            for r in v["rows"]:
                nm = r["player"]
                share = dict(charged[nm]) if sum(charged[nm].values()) else dict(onbase[nm])
                tot = sum(share.values())
                if not tot:
                    share, tot = {"R": 1.0}, 1.0
                for hb, x in share.items():
                    self.acc[nm][hb]["R"] += r["r"] * x / tot
                    self.acc[nm][hb]["ER"] += r["er"] * x / tot
                if sum(charged[nm].values()) != r["r"]:
                    self.issues.append(("runs", g["game_num"], nm, sum(charged[nm].values()), r["r"]))
