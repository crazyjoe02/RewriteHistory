"""
compute_war.py

Computes an approximate Wins Above Replacement (WAR) for position players and
pitchers, adapted from the Baseball-Reference methodology described at:
  https://www.baseball-reference.com/about/war_explained_position.shtml

IMPORTANT — this is a principled ADAPTATION, not an exact replica, because
several inputs the official system requires do not exist in this project's
data:
  - No play-by-play data, so non-SB/CS baserunning (1st-to-3rd on singles,
    tagging up, etc.) cannot be measured. Baserunning runs here = SB/CS only.
  - No GIDP data, so Rdp (double-play avoidance runs) is set to 0 for everyone.
  - No Defensive Runs Saved / Total Zone / DRA data. A Range-Factor-based
    fielding runs estimate was attempted, but the underlying fielding.csv
    data (assembled from several pasted spreadsheets over the course of
    this project) contains individual-row data-entry errors severe enough
    to produce wrong results for specific players (e.g. one full-season
    1B shows only 144 putouts, an order of magnitude too low). Rather than
    publish defensive runs that are confidently wrong for an unknown subset
    of players, Rfield is set to 0 (league average) for everyone. Rpos
    (below) still applies, since it only depends on innings at a position,
    not on putouts/assists.
  - No park factors or opponent-strength data, so both are omitted.
  - No leverage index data, so no reliever leverage multiplier.
  - The final league-wide WAR re-centering step (matching a target total WAR
    for the league) is skipped; replacement level is applied directly via
    BR's stated formulas instead.

Everything else follows the documented formulas as closely as possible:
  - Rbat: linear-weights batting runs (Palmer-style coefficients), recentered
    so the league-average hitter (excluding pitchers) is exactly 0.
  - Rbr: SB/CS linear weights (0.30 / -0.60 per BR's cited approximate
    run values), recentered the same way.
  - Rdp: 0 (no data).
  - Rfield: 0 for everyone (see limitation above).
  - Rpos: BR's published 1885/1886 per-1350-inning positional constants,
    prorated by innings, with the pitcher-as-hitter adjustment computed via
    BR's stated formula, then recentered to sum to 0 across the season.
  - Rrep: 20.5 runs / 600 PA (BR's stated offensive replacement constant).
  - Pitching: Runs-Allowed-per-out vs. league average, converted to
    runs-above-replacement via BR's stated (20.5-1.8)/100 increment, using
    total runs allowed (not just earned) and innings pitched.
  - Runs are converted to wins using Runs Per Win = 10 * sqrt(RPG/9), where
    RPG is the season's actual combined runs-per-game environment (a
    standard, widely-used simplification of BR's PythagenPat approach).
"""
import csv
import math
import os

DATA_DIR = "data"
SEASONS = [1885, 1886]

POS_CONST = {
    "C": 10.0, "1B": 0.0, "2B": 3.0, "3B": 5.0, "SS": 10.0,
    "LF": -9.5, "CF": -8.0, "RF": -9.0,
}

REPL_PA_RUNS = 20.5 / 600.0
REPL_PITCH_INCREMENT = 0.187


def load_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fieldnames):
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp_path, path)


def f(row, key, default=0.0):
    v = row.get(key, "")
    if v in (None, ""):
        return default
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return default


def compute_season(season):
    bat_path = os.path.join(DATA_DIR, str(season), "batting.csv")
    pit_path = os.path.join(DATA_DIR, str(season), "pitching.csv")
    fld_path = os.path.join(DATA_DIR, str(season), "fielding.csv")

    batting = load_csv(bat_path)
    pitching = load_csv(pit_path)
    fielding = load_csv(fld_path)
    if not batting:
        print(f"{season}: no batting data found, skipping")
        return

    orig_bat_fields = [k for k in batting[0].keys() if k != "WAR"]
    orig_pit_fields = [k for k in pitching[0].keys() if k != "WAR"] if pitching else []

    pitcher_keys = set((r["Player"], r["Team"]) for r in pitching)

    for row in batting:
        row["_key"] = (row["Player"], row["Team"])
        row["_PA"] = f(row, "AB") + f(row, "BB") + f(row, "HBP")
        row["_1B"] = f(row, "H") - f(row, "2B") - f(row, "3B") - f(row, "HR")
        row["_raw_bat"] = (
            0.46 * row["_1B"] + 0.80 * f(row, "2B") + 1.02 * f(row, "3B") + 1.40 * f(row, "HR")
            + 0.33 * (f(row, "BB") + f(row, "HBP")) - 0.25 * (f(row, "AB") - f(row, "H"))
        )
        row["_raw_br"] = 0.30 * f(row, "SB") - 0.60 * f(row, "CS")
        row["_is_pitcher"] = row["_key"] in pitcher_keys
        row["Rbat"] = 0.0
        row["Rbr"] = 0.0

    for league in sorted(set(r["Lg"] for r in batting)):
        pool = [r for r in batting if r["Lg"] == league and not r["_is_pitcher"]]
        pa_sum = sum(r["_PA"] for r in pool) or 1.0
        bat_rate = sum(r["_raw_bat"] for r in pool) / pa_sum
        br_rate = sum(r["_raw_br"] for r in pool) / pa_sum
        for r in batting:
            if r["Lg"] != league:
                continue
            r["Rbat"] = r["_raw_bat"] - bat_rate * r["_PA"]
            r["Rbr"] = r["_raw_br"] - br_rate * r["_PA"]

    pos_lg = {}
    for row in fielding:
        pos = row.get("Pos", "")
        if pos not in POS_CONST:
            continue
        lg = row["Lg"]
        inn = f(row, "Inn")
        po_a = f(row, "PO") + f(row, "A")
        s = pos_lg.setdefault((lg, pos), [0.0, 0.0])
        s[0] += po_a
        s[1] += inn

    # Rfield is intentionally not computed here (see module docstring for why);
    # every player gets 0 fielding runs. Rpos still uses innings-at-position,
    # which is much less exposed to the PO/A data-entry errors found in
    # fielding.csv.
    rpos_raw_by_key = {}
    for row in fielding:
        pos = row.get("Pos", "")
        key = (row["Player"], row["Team"])
        inn = f(row, "Inn")
        if pos in POS_CONST and inn > 0:
            rpos_raw_by_key[key] = rpos_raw_by_key.get(key, 0.0) + POS_CONST[pos] * (inn / 1350.0)

    pitcher_pos_rate = {}
    for league in sorted(set(r["Lg"] for r in batting)):
        p_rows = [r for r in batting if r["Lg"] == league and r["_is_pitcher"]]
        pa_sum = sum(r["_PA"] for r in p_rows)
        run_sum = sum(r["Rbat"] + r["Rbr"] for r in p_rows)
        pitcher_pos_rate[league] = (-600.0 * run_sum / pa_sum) if pa_sum else 0.0

    for row in batting:
        key = row["_key"]
        raw_pos = rpos_raw_by_key.get(key, 0.0)
        if row["_is_pitcher"]:
            # pitcher_pos_rate is a "per 600 PA" constant (BR's stated formula),
            # analogous to the other positions' "per 1350 innings" constants.
            raw_pos += pitcher_pos_rate[row["Lg"]] * row["_PA"] / 600.0
        row["_Rpos_raw"] = raw_pos
        row["Rfield"] = 0.0

    total_pos = sum(r["_Rpos_raw"] for r in batting)
    total_pa = sum(r["_PA"] for r in batting) or 1.0
    pos_adj_rate = total_pos / total_pa
    for row in batting:
        row["Rpos"] = row["_Rpos_raw"] - pos_adj_rate * row["_PA"]
        row["Rrep"] = REPL_PA_RUNS * row["_PA"]

    standings = load_csv(os.path.join(DATA_DIR, str(season), "standings.csv"))
    if standings:
        rs = sum(f(r, "RF") for r in standings)
        gp = sum(f(r, "W") + f(r, "L") for r in standings)
    else:
        sched = load_csv(os.path.join(DATA_DIR, str(season), "schedule.csv"))
        played = [r for r in sched if str(r.get("HomeScore", "")).strip() != ""]
        rs = sum(f(r, "HomeScore") + f(r, "AwayScore") for r in played)
        gp = len(played) * 2
    rpg_total = (2.0 * rs / gp) if gp else 9.0
    rpw = 10.0 * math.sqrt(rpg_total / 9.0) if rpg_total > 0 else 10.0

    for row in batting:
        rar = row["Rbat"] + row["Rbr"] + row["Rfield"] + row["Rpos"] + row["Rrep"]
        row["WAR"] = round(rar / rpw, 2)
        for k in list(row.keys()):
            if k.startswith("_") or k in ("Rbat", "Rbr", "Rfield", "Rpos", "Rrep"):
                del row[k]

    for league in sorted(set(r["League"] for r in pitching)):
        p_rows = [r for r in pitching if r["League"] == league]
        outs_sum = sum(f(r, "IP") * 3.0 for r in p_rows)
        r_sum = sum(f(r, "R") for r in p_rows)
        rpo_lg = (r_sum / outs_sum) if outs_sum else 0.0
        repl_increment_per_out = rpo_lg * REPL_PITCH_INCREMENT
        for r in p_rows:
            outs = f(r, "IP") * 3.0
            if outs <= 0:
                r["WAR"] = 0.0
                continue
            rpo_p = f(r, "R") / outs
            runs_above_avg = (rpo_lg - rpo_p) * outs
            runs_above_rep = runs_above_avg + repl_increment_per_out * outs
            r["WAR"] = round(runs_above_rep / rpw, 2)

    write_csv(bat_path, batting, orig_bat_fields + ["WAR"])
    if pitching:
        write_csv(pit_path, pitching, orig_pit_fields + ["WAR"])
    print(f"{season}: RPG={rpg_total:.2f} RPW={rpw:.2f}  "
          f"batting rows={len(batting)}  pitching rows={len(pitching)}")


if __name__ == "__main__":
    for s in SEASONS:
        compute_season(s)
