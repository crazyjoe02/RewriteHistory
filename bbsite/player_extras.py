"""Baseball-Reference-style player page data.

Everything here is computed from the league's own CSVs (data/<season>/*.csv), the box
scores (games.json) and the real-world register in data/bio.csv.  build.py calls
LeagueContext(...) once, then .player(...) for each player page.
"""
import csv, json, os
from collections import defaultdict

POS_ORDER = ["P", "C", "1B", "2B", "3B", "SS", "LF", "CF", "RF"]
POS_NAME = {"P": "Pitcher", "C": "Catcher", "1B": "First Baseman", "2B": "Second Baseman",
            "3B": "Third Baseman", "SS": "Shortstop", "LF": "Leftfielder", "CF": "Centerfielder",
            "RF": "Rightfielder", "OF": "Outfielder"}
COUNT = ["G", "GS", "PA", "AB", "R", "H", "2B", "3B", "HR", "RBI", "SB", "CS", "BB", "SO", "HBP",
         "SH", "SF", "IBB", "GIDP", "GB", "FB", "NP", "PHAB", "PHH", "IFH", "BH", "RC"]
VALUE = ["Rbat", "Rbaser", "Rfield", "Rpos", "RAA", "WAA", "Rrep", "RAR", "WAR", "oWAR", "dWAR"]
SPLITS = ["Home", "Away", "VS. LHP", "VS. RHP"]
SPLIT_LABEL = {"Home": "Home", "Away": "Away", "VS. LHP": "vs LH Starter", "VS. RHP": "vs RH Starter"}


def _load(path):
    return list(csv.DictReader(open(path, encoding="utf-8"))) if os.path.exists(path) else []


def num(v):
    try:
        return float(str(v).replace(",", "")) if v not in (None, "") else 0.0
    except (TypeError, ValueError):
        return 0.0


def disp(player):
    last, first = [x.strip() for x in player.split(",", 1)]
    return f"{first} {last}"


def outs(ip):
    whole, _, frac = str(ip or "0").partition(".")
    return int(whole or 0) * 3 + {"": 0, "0": 0, "1": 1, "3": 1, "2": 2, "7": 2}.get(frac[:1], 0)


def ip_str(o):
    return f"{o // 3}.{ {0: 0, 1: 1, 2: 2}[o % 3] }"


def rate(x, d=3):
    s = f"{x:.{d}f}"
    return s[1:] if s.startswith("0.") else s


def derive(r):
    """Add rate stats to a dict of summed counting stats (in place)."""
    ab, h, bb, hbp, sf = r["AB"], r["H"], r["BB"], r["HBP"], r["SF"]
    tb = h + r["2B"] + 2 * r["3B"] + 3 * r["HR"]
    pa = r["PA"] or (ab + bb + hbp + sf + r["SH"])
    r["PA"] = pa
    r["TB"] = tb
    r["AVG"] = h / ab if ab else 0.0
    r["OBP"] = (h + bb + hbp) / (ab + bb + hbp + sf) if (ab + bb + hbp + sf) else 0.0
    r["SLG"] = tb / ab if ab else 0.0
    r["OPS"] = r["OBP"] + r["SLG"]
    bip = ab - r["SO"] - r["HR"] + sf
    r["BAbip"] = (h - r["HR"]) / bip if bip > 0 else 0.0
    r["ISO"] = r["SLG"] - r["AVG"]
    r["HRp"] = 100 * r["HR"] / pa if pa else 0.0
    r["SOp"] = 100 * r["SO"] / pa if pa else 0.0
    r["BBp"] = 100 * r["BB"] / pa if pa else 0.0
    xbh = r["2B"] + r["3B"] + r["HR"]
    r["XBHp"] = 100 * xbh / pa if pa else 0.0
    r["XHp"] = 100 * xbh / h if h else 0.0
    r["SBp"] = 100 * r["SB"] / (r["SB"] + r["CS"]) if (r["SB"] + r["CS"]) else None
    r["GBFB"] = r["GB"] / r["FB"] if r["FB"] else None
    r["GBp"] = 100 * r["GB"] / (r["GB"] + r["FB"]) if (r["GB"] + r["FB"]) else None
    r["PPA"] = r["NP"] / pa if (pa and r["NP"]) else None
    return r


class LeagueContext:
    def __init__(self, data_dir, seasons, name_fn=None):
        self.name_fn = name_fn or disp
        self.seasons = sorted(int(s) for s in seasons)
        self.bat, self.fld, self.pit = {}, {}, {}
        for s in self.seasons:
            d = os.path.join(data_dir, str(s))
            self.bat[s] = _load(os.path.join(d, "batting.csv"))
            self.fld[s] = _load(os.path.join(d, "fielding.csv"))
            self.pit[s] = _load(os.path.join(d, "pitching.csv"))
        self.bio = {r["Player"]: r for r in _load(os.path.join(data_dir, "bio.csv"))}

        # WIS metrics + splits (only exist for seasons imported from the CSV exports)
        self.metrics, self.splits = {}, defaultdict(list)
        for s in self.seasons:
            d = os.path.join(data_dir, str(s))
            for r in _load(os.path.join(d, "batting_metrics.csv")):
                self.metrics[(s, self.name_fn(r["Player"]), r["Team"])] = r
            for r in _load(os.path.join(d, "batting_splits.csv")):
                self.splits[(s, self.name_fn(r["Player"]))].append(r)

        # Awards / All-Star selections by display name
        self.allstars, self.awards = defaultdict(list), defaultdict(list)
        for s in self.seasons:
            d = os.path.join(data_dir, str(s))
            for r in _load(os.path.join(d, "allstars.csv")):
                self.allstars[r["Player"]].append(r)
            for r in _load(os.path.join(d, "awards.csv")):
                self.awards[r["Player"]].append(r)

        # Box scores: league debut, last game, pinch-hit / pinch-run games
        self.debut, self.last, self.ph, self.pr = {}, {}, defaultdict(int), defaultdict(int)
        self.team_games = defaultdict(int)
        for s in self.seasons:
            gp = os.path.join(data_dir, str(s), "games.json")
            games = json.load(open(gp)) if os.path.exists(gp) else []
            for g in sorted(games, key=lambda g: (g.get("date", ""), g.get("game_num", 0))):
                slug = g.get("slug") or f"{g['game_num']}-{g['away'].lower()}-{g['home'].lower()}"
                _dt = g.get("date", "")
                try:
                    _y, _m, _d = _dt.split("-")
                    _txt = f"{['','January','February','March','April','May','June','July','August','September','October','November','December'][int(_m)]} {int(_d)}, {_y}"
                except ValueError:
                    _txt = _dt
                ref = {"season": s, "date": _dt, "date_text": _txt, "url": f"boxscore/{s}/{slug}.html",
                       "label": f"{g['away']} @ {g['home']}"}
                for team, side in list(g.get("batting", {}).items()) + list(g.get("pitching", {}).items()):
                    for row in side.get("rows", []):
                        nm = row.get("player")
                        if not nm:
                            continue
                        self.debut.setdefault(nm, ref)
                        self.last[nm] = ref
                        pos = str(row.get("pos", ""))
                        if pos.startswith("PH"):
                            self.ph[(s, team, nm)] += 1
                        elif pos.startswith("PR"):
                            self.pr[(s, team, nm)] += 1
            sched = _load(os.path.join(data_dir, str(s), "schedule.csv"))
            played = [r for r in sched if str(r.get("HomeScore", "")).strip() != ""]
            if played:
                for r in played:
                    self.team_games[(s, r["HomeAbbr"])] += 1
                    self.team_games[(s, r["AwayAbbr"])] += 1
            else:
                for r in _load(os.path.join(data_dir, str(s), "standings.csv")):
                    ab = r.get("Abbr") or r.get("Team")
                    self.team_games[(s, ab)] = int(num(r.get("W")) + num(r.get("L")))

        # League averages (per season + league) for OPS+, lgFld%, lgRF9
        self.lg_bat, self.lg_fld = {}, {}
        for s in self.seasons:
            acc = defaultdict(lambda: defaultdict(float))
            for r in self.bat[s]:
                a = acc[r["Lg"]]
                for k in ("AB", "H", "BB", "HBP", "SF", "2B", "3B", "HR"):
                    a[k] += num(r.get(k))
            for lg, a in acc.items():
                tb = a["H"] + a["2B"] + 2 * a["3B"] + 3 * a["HR"]
                den = a["AB"] + a["BB"] + a["HBP"] + a["SF"]
                self.lg_bat[(s, lg)] = {"OBP": (a["H"] + a["BB"] + a["HBP"]) / den if den else 0,
                                        "SLG": tb / a["AB"] if a["AB"] else 0}
            facc = defaultdict(lambda: defaultdict(float))
            for r in self.fld[s]:
                a = facc[(r["Lg"], r["Pos"])]
                for k in ("PO", "A", "E", "Inn"):
                    a[k] += num(r.get(k))
            for (lg, pos), a in facc.items():
                ch = a["PO"] + a["A"] + a["E"]
                self.lg_fld[(s, lg, pos)] = {"Fld": (a["PO"] + a["A"]) / ch if ch else 0,
                                             "RF9": 9 * (a["PO"] + a["A"]) / a["Inn"] if a["Inn"] else 0}

        self._build_leaderboards()

    # ------------------------------------------------------------------ leaderboards
    def _build_leaderboards(self):
        """Top-10 finishes per season & league (B-R 'Leaderboards, Awards, & Honors')."""
        self.lb = defaultdict(list)  # player -> list of entries
        for s in self.seasons:
            lgs = sorted({r["Lg"] for r in self.bat[s]})
            for lg in lgs:
                games = max([g for (ss, t), g in self.team_games.items() if ss == s] or [1])
                tot = defaultdict(lambda: defaultdict(float))
                for r in self.bat[s]:
                    if r["Lg"] != lg:
                        continue
                    t = tot[self.name_fn(r["Player"])]
                    for k in COUNT + ["WAR"]:
                        t[k] += num(r.get(k))
                rows = {p: derive(dict(t)) for p, t in tot.items()}
                q = lambda p: rows[p]["PA"] >= 3.1 * games
                bcats = [("WAR for Position Players", "WAR", True, "%.1f", None),
                         ("Batting Average", "AVG", True, "rate", q), ("On-Base %", "OBP", True, "rate", q),
                         ("Slugging %", "SLG", True, "rate", q), ("On-Base Plus Slugging", "OPS", True, "rate", q),
                         ("Runs Scored", "R", True, "%d", None), ("Hits", "H", True, "%d", None),
                         ("Total Bases", "TB", True, "%d", None), ("Doubles", "2B", True, "%d", None),
                         ("Triples", "3B", True, "%d", None), ("Home Runs", "HR", True, "%d", None),
                         ("Runs Batted In", "RBI", True, "%d", None), ("Bases on Balls", "BB", True, "%d", None),
                         ("Stolen Bases", "SB", True, "%d", None)]
                self._rank(rows, bcats, s, lg)
                ptot = defaultdict(lambda: defaultdict(float))
                for r in self.pit[s]:
                    if r.get("League") != lg:
                        continue
                    t = ptot[self.name_fn(r["Player"])]
                    for k in ("W", "L", "G", "GS", "CG", "SHO", "SV", "H", "ER", "BB", "SO", "WAR"):
                        t[k] += num(r.get(k))
                    t["outs"] += outs(r.get("IP"))
                prow = {}
                for p, t in ptot.items():
                    t = dict(t)
                    ip = t["outs"] / 3
                    t["IP"] = ip
                    t["ERA"] = 9 * t["ER"] / ip if ip else 99
                    t["WHIP"] = (t["BB"] + t["H"]) / ip if ip else 99
                    prow[p] = t
                pq = lambda p: prow[p]["IP"] >= 1.0 * games
                pcats = [("WAR for Pitchers", "WAR", True, "%.1f", None), ("Earned Run Average", "ERA", False, "%.2f", pq),
                         ("Wins", "W", True, "%d", None), ("WHIP", "WHIP", False, "%.3f", pq),
                         ("Innings Pitched", "IP", True, "ip", None), ("Strikeouts", "SO", True, "%d", None),
                         ("Complete Games", "CG", True, "%d", None), ("Shutouts", "SHO", True, "%d", None),
                         ("Saves", "SV", True, "%d", None)]
                self._rank(prow, pcats, s, lg)

    def _rank(self, rows, cats, s, lg):
        for label, key, high, fmt, qual in cats:
            pool = [p for p in rows if (qual is None or qual(p))]
            pool = [p for p in pool if rows[p].get(key) is not None and (rows[p][key] > 0 or not high)]
            pool.sort(key=lambda p: rows[p][key], reverse=high)
            for i, p in enumerate(pool[:10]):
                v = rows[p][key]
                rank = 1 + sum(1 for o in pool if (rows[o][key] > v if high else rows[o][key] < v))
                vs = rate(v) if fmt == "rate" else (ip_str(round(v * 3)) if fmt == "ip" else fmt % v)
                self.lb[p].append({"label": label, "season": s, "lg": lg, "value": vs, "rank": rank})

    # ------------------------------------------------------------------ per player
    def age(self, bio, season):
        if not bio or not bio.get("BirthYear"):
            return ""
        y, m, d = int(bio["BirthYear"]), int(bio["BirthMonth"] or 1), int(bio["BirthDay"] or 1)
        return season - y - (1 if (m, d) > (6, 30) else 0)

    def _season_groups(self, rows, from_teams):
        """[(season, [rows in stint order])]"""
        by = defaultdict(list)
        for r in rows:
            by[int(r["SN"])].append(r)
        out = []
        for s in sorted(by):
            out.append((s, sorted(by[s], key=lambda r: 0 if (s, r["Team"]) in from_teams else 1)))
        return out

    def player(self, player_key, name, batting_rows, pitching_rows, fielding_rows, trades, is_pitcher):
        bio = self.bio.get(name)
        from_teams = {(int(t["Season"]), t["FromTeamAbbr"]) for t in trades}
        fpos = defaultdict(lambda: defaultdict(float))  # (season, team) -> pos -> GP
        finn = defaultdict(lambda: defaultdict(float))
        fgs = defaultdict(float)
        for r in fielding_rows:
            k = (int(r["Season"]), r["Team"])
            fpos[k][r["Pos"]] += num(r.get("GP"))
            finn[k][r["Pos"]] += num(r.get("Inn"))
            fgs[k] += num(r.get("GS"))

        def pos_str(keys):
            inn = defaultdict(float)
            for k in keys:
                for p, v in finn[k].items():
                    inn[p] += v
            ps = [p for p, _ in sorted(inn.items(), key=lambda kv: -kv[1])]
            return "-".join(ps[:3])

        def awards_str(s):
            a = [f"AS" for x in self.allstars.get(name, []) if int(x["Season"]) == s]
            code = {"MVP": "MVP-{r}", "Champion Hurler": "CH-{r}", "Fireman": "FM-{r}",
                    "Gold Glove": "GG", "Silver Slugger": "SS"}
            a += [code.get(x["Award"], x["Award"] + "-{r}").format(r=x["Rank"])
                  for x in self.awards.get(name, []) if int(x["Season"]) == s]
            return ",".join(a)

        # ---------- batting-type tables (standard / value / advanced / appearances)
        std, career = [], defaultdict(float)
        nseasons = set()
        for s, grp in self._season_groups(batting_rows, from_teams):
            stints = []
            for r in grp:
                d = {k: num(r.get(k)) for k in COUNT + VALUE}
                d["_nodetail"] = r.get("PA") in (None, "")   # 1885 exports lack PA/GIDP/SH/SF/IBB
                if not r.get("PA"):
                    d["PA"] = 0
                if not r.get("GS"):
                    d["GS"] = fgs.get((s, r["Team"]), 0)
                d.update({"SN": s, "Team": r["Team"], "Lg": r["Lg"], "Age": self.age(bio, s),
                          "Pos": pos_str([(s, r["Team"])]) or ("P" if is_pitcher else "PH"),
                          "Awards": awards_str(s), "PH": self.ph.get((s, r["Team"], name), 0),
                          "PR": self.pr.get((s, r["Team"], name), 0),
                          "Def": min(d["G"], sum(fpos[(s, r["Team"])].values())),
                          "posG": {p: fpos[(s, r["Team"])].get(p, 0) for p in POS_ORDER},
                          "OF": min(d["G"], sum(fpos[(s, r["Team"])].get(p, 0) for p in ("LF", "CF", "RF")))})
                m = self.metrics.get((s, player_key, r["Team"]))
                d["Clutch"] = m.get("Clutch", "") if m else ""
                d["eBA"] = m.get("eBA", "") if m else ""
                d["WISWAR"] = num(m.get("WIS-WAR")) if m and m.get("WIS-WAR") not in (None, "") else None
                stints.append(derive(d))
                nseasons.add(s)
                for k in COUNT + VALUE + ["PH", "PR", "Def", "OF"]:
                    career[k] += d[k]
                for p in POS_ORDER:
                    career["pos_" + p] += d["posG"][p]
                if d["WISWAR"] is not None:
                    career["WISWAR"] += d["WISWAR"]
            if len(stints) > 1:
                c = {k: sum(x[k] for x in stints) for k in COUNT + VALUE + ["PH", "PR", "Def", "OF"]}
                c["PA"] = sum(x["PA"] for x in stints)
                lgs = {x["Lg"] for x in stints}
                c.update({"SN": s, "Team": f"{len(stints)}TM", "Lg": lgs.pop() if len(lgs) == 1 else "MLB",
                          "Age": stints[0]["Age"], "Pos": pos_str([(s, x["Team"]) for x in stints]),
                          "Awards": stints[0]["Awards"], "_combined": True,
                          "posG": {p: sum(x["posG"][p] for x in stints) for p in POS_ORDER},
                          "Clutch": "", "eBA": "",
                          "WISWAR": sum(x["WISWAR"] for x in stints if x["WISWAR"] is not None)
                          if any(x["WISWAR"] is not None for x in stints) else None})
                derive(c)
                std.append(c)
            std.extend(stints)

        for r in std:
            lgb = self.lg_bat.get((r["SN"], r["Lg"])) or self.lg_bat.get((r["SN"], (batting_rows or [{}])[0].get("Lg")))
            r["OPSp"] = round(100 * (r["OBP"] / lgb["OBP"] + r["SLG"] / lgb["SLG"] - 1)) if (lgb and lgb["OBP"] and lgb["SLG"] and r["AB"]) else None
        car = None
        if std:
            car = derive({k: career[k] for k in COUNT + VALUE + ["PH", "PR", "Def", "OF"]})
            car["posG"] = {p: career["pos_" + p] for p in POS_ORDER}
            car["Years"] = len(nseasons)
            car["WISWAR"] = career["WISWAR"] if any(r.get("WISWAR") is not None for r in std) else None
            # career OPS+: PA-weighted average of season OPS+
            w = [(r["OPSp"], r["PA"]) for r in std if not r.get("_combined") and r["OPSp"] is not None]
            car["OPSp"] = round(sum(a * b for a, b in w) / sum(b for _, b in w)) if w and sum(b for _, b in w) else None
            # rounding of value columns
        for r in std + ([car] if car else []):
            for k in VALUE:
                r[k] = round(r[k], 1) if k not in ("WAA", "oWAR", "dWAR") else round(r[k], 1)

        # ---------- splits (each season with split data; summed across teams)
        splits = []
        for s in self.seasons:
            rows = self.splits.get((s, player_key), [])
            if not rows:
                continue
            for lab in SPLITS:
                acc = defaultdict(float)
                for r in rows:
                    if r["Split"] != lab:
                        continue
                    for k in ("G", "AB", "H", "Doubles", "Triples", "HR", "RBI", "R", "SO", "BB", "SF", "SH", "HBP", "SB", "CS"):
                        acc[k] += num(r.get(k))
                if not acc:
                    continue
                d = {k: acc.get(k, 0) for k in ("G", "AB", "H", "HR", "RBI", "R", "SO", "BB", "SF", "SH", "HBP", "SB", "CS")}
                d["2B"], d["3B"] = acc["Doubles"], acc["Triples"]
                for k in ("PA", "IBB", "GIDP", "GB", "FB", "NP", "PHAB", "PHH", "IFH", "BH", "GS", "RC"):
                    d[k] = 0
                derive(d)
                d.update({"SN": s, "Split": SPLIT_LABEL[lab]})
                splits.append(d)

        # ---------- fielding enrichment (rows come from build.py's display list)
        for r in fielding_rows:
            pass  # raw rows untouched; enrichment happens in enrich_fielding()

        # ---------- leaderboards & honors
        lb = defaultdict(list)
        for e in sorted(self.lb.get(player_key, []), key=lambda e: (e["season"], e["rank"])):
            lb[e["label"]].append(e)
        order = ["WAR for Position Players", "WAR for Pitchers", "Batting Average", "On-Base %", "Slugging %",
                 "On-Base Plus Slugging", "Runs Scored", "Hits", "Total Bases", "Doubles", "Triples", "Home Runs",
                 "Runs Batted In", "Bases on Balls", "Stolen Bases", "Earned Run Average", "Wins", "WHIP",
                 "Innings Pitched", "Strikeouts", "Complete Games", "Shutouts", "Saves"]
        leaderboards = [{"label": k, "entries": lb[k]} for k in order if k in lb]
        honors = {"allstar": sorted(self.allstars.get(name, []), key=lambda x: int(x["Season"])),
                  "awards": sorted(self.awards.get(name, []), key=lambda x: (int(x["Season"]), int(num(x.get("Rank")))))}

        return {"bio": bio, "std_batting": std, "std_career": car, "splits": splits,
                "leaderboards": leaderboards, "honors": honors,
                "debut": self.debut.get(name), "last_game": self.last.get(name)}

    def enrich_fielding(self, rows, bio):
        """Add Ch, RF/G, lgFld%, lgRF9, CS%, Age to build.py's fielding display rows (in place)."""
        lg_of = {}
        for r in rows:
            if r.get("Lg"):
                lg_of[(r["Season"], r["Team"])] = r["Lg"]
        for r in rows:
            s = int(r["Season"])
            po, a, e = num(r.get("PO")), num(r.get("A")), num(r.get("E"))
            gp = num(r.get("GP"))
            r["Ch"] = int(po + a + e)
            r["RFG"] = (po + a) / gp if gp else 0.0
            r["RF9"] = 9 * (po + a) / num(r.get("Inn")) if num(r.get("Inn")) else 0.0
            sb, cs = num(r.get("SB")), num(r.get("CS"))
            r["CSp"] = 100 * cs / (sb + cs) if (sb + cs) else None
            lg = r.get("Lg") or next((v for (ss, t), v in lg_of.items() if ss == r["Season"]), "")
            lf = self.lg_fld.get((s, lg, r["Pos"]))
            r["lgFld"] = lf["Fld"] if lf else None
            r["lgRF9"] = lf["RF9"] if lf else None
            r["Age"] = self.age(bio, s)
            r["LgShow"] = lg if not r.get("_combined") else lg
        return rows
