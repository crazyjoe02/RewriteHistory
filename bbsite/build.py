#!/usr/bin/env python3
"""
Static site generator for the historical baseball league reference site.

Usage:
    python3 build.py

Reads:
    data/teams.csv                      -- master franchise registry
    data/<season>/batting.csv
    data/<season>/pitching.csv
    data/<season>/standings.csv

Writes the full static site into site/
"""
import csv
import json
import os
import re
import shutil
import glob
from collections import defaultdict
from jinja2 import Environment, FileSystemLoader

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT, "data")
SITE_DIR = os.path.join(ROOT, "site")
TEMPLATES_DIR = os.path.join(ROOT, "templates")

LEAGUE_NAMES = {"NL": "National League", "AA": "American Association"}


def load_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def slugify_player_id(name):
    """Baseball-Reference style ID: last5 + first2 + 01, lowercase, alnum only."""
    if "," in name:
        last, first = [p.strip() for p in name.split(",", 1)]
    else:
        parts = name.strip().split(" ", 1)
        last, first = (parts[0], parts[1] if len(parts) > 1 else "")
    last_clean = re.sub(r"[^A-Za-z]", "", last).lower()
    first_clean = re.sub(r"[^A-Za-z]", "", first).lower()
    base = (last_clean[:5] or "xxxxx") + (first_clean[:2] or "xx")
    return base + "01"


def slugify_manager(name):
    """Simple URL-safe slug for a manager/owner name."""
    slug = re.sub(r"[^A-Za-z0-9]+", "-", name.strip()).strip("-").lower()
    return slug or "unknown"


def display_name(raw):
    """Convert 'Last, First' -> 'First Last' for display."""
    if "," in raw:
        last, first = [p.strip() for p in raw.split(",", 1)]
        return f"{first} {last}"
    return raw


def last_name_of(raw):
    """Extract just the last name from 'Last, First' (or 'First Last') for sorting."""
    if "," in raw:
        return raw.split(",", 1)[0].strip()
    parts = raw.strip().split(" ")
    return parts[-1] if parts else raw


def discover_seasons():
    seasons = []
    for entry in sorted(os.listdir(DATA_DIR)):
        full = os.path.join(DATA_DIR, entry)
        if os.path.isdir(full) and entry.isdigit():
            seasons.append(int(entry))
    return sorted(seasons)


def main():
    # --- Load franchise eras registry ---
    team_eras = load_csv(os.path.join(DATA_DIR, "franchises.csv"))
    teams = team_eras  # backward-compat alias used elsewhere for "all team rows"
    teams_by_abbr = {t["Abbr"]: t for t in team_eras}

    franchises_by_id = defaultdict(list)
    for era in team_eras:
        franchises_by_id[era["FranchiseID"]].append(era)
    for fid in franchises_by_id:
        franchises_by_id[fid].sort(key=lambda e: int(e["StartSeason"]))

    # hub_abbr: every historical abbr -> the CURRENT (most recent / ongoing) abbr for its franchise.
    # An era with a blank EndSeason is the active one; if somehow none are blank, use the latest StartSeason.
    hub_abbr = {}
    current_era_by_franchise = {}
    for fid, eras in franchises_by_id.items():
        current = next((e for e in eras if not e["EndSeason"]), eras[-1])
        current_era_by_franchise[fid] = current
        for e in eras:
            hub_abbr[e["Abbr"]] = current["Abbr"]

    seasons = discover_seasons()
    if not seasons:
        print("No season data found under data/<season>/. Nothing to build.")
        return
    latest_season = seasons[-1]
    first_season = seasons[0]

    # --- Load all season data ---
    all_standings = {}   # season -> list of rows
    all_batting = {}     # season -> list of rows
    all_pitching = {}    # season -> list of rows
    all_ps_batting = {}  # season -> list of postseason batting rows
    all_ps_pitching = {} # season -> list of postseason pitching rows
    all_fielding = {}    # season -> list of fielding rows (one row per player+position)

    for season in seasons:
        sdir = os.path.join(DATA_DIR, str(season))
        standings_path = os.path.join(sdir, "standings.csv")
        batting_path = os.path.join(sdir, "batting.csv")
        pitching_path = os.path.join(sdir, "pitching.csv")
        ps_batting_path = os.path.join(sdir, "postseason_batting.csv")
        ps_pitching_path = os.path.join(sdir, "postseason_pitching.csv")
        fielding_path = os.path.join(sdir, "fielding.csv")

        standings_rows = load_csv(standings_path) if os.path.exists(standings_path) else []
        batting_rows = load_csv(batting_path) if os.path.exists(batting_path) else []
        pitching_rows = load_csv(pitching_path) if os.path.exists(pitching_path) else []
        ps_batting_rows = load_csv(ps_batting_path) if os.path.exists(ps_batting_path) else []
        ps_pitching_rows = load_csv(ps_pitching_path) if os.path.exists(ps_pitching_path) else []
        fielding_rows = load_csv(fielding_path) if os.path.exists(fielding_path) else []

        # normalize display name to master registry (fixes source typos/casing)
        for row in standings_rows:
            master = teams_by_abbr.get(row["TeamAbbr"])
            if master:
                row["TeamName"] = master["FranchiseName"]
            row["Season"] = season
            row["OwnerSlug"] = slugify_manager(row.get("Owner", ""))

        # compute Finish (rank within league) for standings rows
        by_league = defaultdict(list)
        for row in standings_rows:
            by_league[row["League"]].append(row)
        for lg, rows in by_league.items():
            rows.sort(key=lambda r: -float(r["PCT"]))
            for i, row in enumerate(rows, start=1):
                row["Finish"] = f"{i} of {len(rows)}"

        # assign PlayerID to batting/pitching rows
        for row in batting_rows:
            row["PlayerID"] = slugify_player_id(row["Player"])
            row["LastName"] = last_name_of(row["Player"])
            row["Player"] = display_name(row["Player"])
        for row in pitching_rows:
            row["PlayerID"] = slugify_player_id(row["Player"])
            row["LastName"] = last_name_of(row["Player"])
            row["Player"] = display_name(row["Player"])
        for row in ps_batting_rows:
            row["PlayerID"] = slugify_player_id(row["Player"])
            row["LastName"] = last_name_of(row["Player"])
            row["Player"] = display_name(row["Player"])
        for row in ps_pitching_rows:
            row["PlayerID"] = slugify_player_id(row["Player"])
            row["LastName"] = last_name_of(row["Player"])
            row["Player"] = display_name(row["Player"])
        for row in fielding_rows:
            row["PlayerID"] = slugify_player_id(row["Player"])
            row["LastName"] = last_name_of(row["Player"])
            row["Player"] = display_name(row["Player"])
            row["Season"] = season
            row["Inn"] = float(str(row["Inn"]).replace(",", "") or 0)

        all_standings[season] = standings_rows
        all_batting[season] = batting_rows
        all_pitching[season] = pitching_rows
        all_ps_batting[season] = ps_batting_rows
        all_ps_pitching[season] = ps_pitching_rows
        all_fielding[season] = fielding_rows

    # --- Set up Jinja ---
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), trim_blocks=True, lstrip_blocks=True)
    env.globals["hub_abbr"] = hub_abbr
    env.globals["team_name_by_abbr"] = {abbr: t["FranchiseName"] for abbr, t in teams_by_abbr.items()}

    # --- Reset output dir (keep static/) ---
    if os.path.exists(SITE_DIR):
        for entry in os.listdir(SITE_DIR):
            if entry == "static":
                continue
            full = os.path.join(SITE_DIR, entry)
            if os.path.isdir(full):
                shutil.rmtree(full)
            else:
                os.remove(full)
    os.makedirs(SITE_DIR, exist_ok=True)

    def write(path, template_name, **ctx):
        ctx.setdefault("latest_season", latest_season)
        ctx.setdefault("first_season", first_season)
        full_path = os.path.join(SITE_DIR, path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        depth = path.count("/")
        ctx["root"] = "../" * depth if depth else "./"
        tmpl = env.get_template(template_name)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(tmpl.render(**ctx))

    # --- Home page (latest season standings; data written later once postseason data is ready) ---

    # --- Year standings pages (data prepared here; written later once awards/ASG data is ready) ---
    def active_franchises_for_season(season):
        """Whichever era of each franchise applies to this season (handles relocations)."""
        active = []
        for fid, eras in franchises_by_id.items():
            era = next((e for e in eras if int(e["StartSeason"]) <= season
                        and (not e["EndSeason"] or int(e["EndSeason"]) >= season)), None)
            if era:
                active.append(era)
        return active

    # --- Schedule (doesn't need player-ID resolution, safe to load early) ---
    schedule_by_team_season = defaultdict(list)
    for season in seasons:
        sched_path = os.path.join(DATA_DIR, str(season), "schedule.csv")
        if not os.path.exists(sched_path):
            continue
        for row in load_csv(sched_path):
            row["Season"] = int(row["Season"])
            row["GameNum"] = int(row["GameNum"])
            if row.get("Date") and len(row["Date"]) == 10 and row["Date"][4] == "-":
                y, m, d = row["Date"].split("-")
                row["DateDisplay"] = f"{m}-{d}-{y}"
            else:
                row["DateDisplay"] = row.get("Date", "")
            schedule_by_team_season[(row["HomeAbbr"], row["Season"])].append(row)
            schedule_by_team_season[(row["AwayAbbr"], row["Season"])].append(row)
    for key in schedule_by_team_season:
        schedule_by_team_season[key].sort(key=lambda r: r["GameNum"])

    # --- Owner lookup (persistent per franchise, survives relocations) ---
    owners_by_fid = {}
    owners_path = os.path.join(DATA_DIR, "owners.csv")
    if os.path.exists(owners_path):
        for row in load_csv(owners_path):
            owners_by_fid[row["FranchiseID"]] = row["Owner"]

    # --- Live standings, computed directly from schedule.csv results (for in-progress
    # seasons that don't have a final standings.csv yet) ---
    def compute_team_record(abbr, season):
        games = schedule_by_team_season.get((abbr, season), [])
        played = [g for g in games if str(g.get("HomeScore", "")).strip() != "" and str(g.get("AwayScore", "")).strip() != ""]
        w = l = home_w = home_l = away_w = away_l = 0
        one_run_w = one_run_l = 0
        rs = ra = 0
        results = []
        for g in played:
            is_home = g["HomeAbbr"] == abbr
            own = int(g["HomeScore"]) if is_home else int(g["AwayScore"])
            opp = int(g["AwayScore"]) if is_home else int(g["HomeScore"])
            win = own > opp
            rs += own
            ra += opp
            if win:
                w += 1
            else:
                l += 1
            if is_home:
                if win: home_w += 1
                else: home_l += 1
            else:
                if win: away_w += 1
                else: away_l += 1
            if abs(own - opp) == 1:
                if win: one_run_w += 1
                else: one_run_l += 1
            results.append("W" if win else "L")
        streak = ""
        if results:
            last = results[-1]
            cnt = 0
            for r in reversed(results):
                if r != last:
                    break
                cnt += 1
            streak = f"{last}{cnt}"
        if len(results) >= 10:
            last10 = results[-10:]
            l10 = f"{last10.count('W')}-{last10.count('L')}"
        else:
            l10 = "-"
        pct = (w / (w + l)) if (w + l) else 0.0
        return {
            "W": w, "L": l, "PCT": pct, "GamesPlayed": len(played), "Streak": streak, "L10": l10,
            "Home": f"{home_w}-{home_l}", "Away": f"{away_w}-{away_l}",
            "RS": rs, "RA": ra, "OneRun": f"{one_run_w}-{one_run_l}",
        }

    def compute_live_league_table(season, league_code, active_eras):
        rows = []
        for era in active_eras:
            if era["League"] != league_code:
                continue
            rec = compute_team_record(era["Abbr"], season)
            rec["TeamAbbr"] = era["Abbr"]
            rec["TeamName"] = era["FranchiseName"]
            rec["Owner"] = owners_by_fid.get(era["FranchiseID"], "")
            rows.append(rec)
        rows.sort(key=lambda r: -r["PCT"])
        if rows:
            leader = rows[0]
            for r in rows:
                gb = ((leader["W"] - r["W"]) + (r["L"] - leader["L"])) / 2
                r["GB"] = "-" if gb == 0 else (f"{gb:g}")
        return rows

    live_standings_by_season_team = {}  # (abbr, season) -> record dict with GB, for team-page lookups

    year_leagues_ctx = {}
    year_is_preseason = {}
    year_is_live = {}
    for season in seasons:
        rows = all_standings[season]
        active = active_franchises_for_season(season)
        has_played_games = any(
            str(g.get("HomeScore", "")).strip() != "" and str(g.get("AwayScore", "")).strip() != ""
            for era in active
            for g in schedule_by_team_season.get((era["Abbr"], season), [])
        )
        if rows:
            year_is_preseason[season] = False
            year_is_live[season] = False
            leagues_ctx = []
            for lg_code in ["AA", "NL"]:
                lg_rows = [r for r in rows if r["League"] == lg_code]
                lg_rows.sort(key=lambda r: -float(r["PCT"]))
                leagues_ctx.append((LEAGUE_NAMES[lg_code], lg_code, lg_rows))
            year_leagues_ctx[season] = leagues_ctx
        elif has_played_games:
            # In-progress season: no final standings.csv yet, but games have been played --
            # compute a live standings table directly from schedule.csv results.
            year_is_preseason[season] = False
            year_is_live[season] = True
            leagues_ctx = []
            for lg_code in ["AA", "NL"]:
                lg_rows = compute_live_league_table(season, lg_code, active)
                leagues_ctx.append((LEAGUE_NAMES[lg_code], lg_code, lg_rows))
                for r in lg_rows:
                    live_standings_by_season_team[(r["TeamAbbr"], season)] = r
            year_leagues_ctx[season] = leagues_ctx
        else:
            # No games played yet -- list active franchises alphabetically instead of a standings table.
            year_is_preseason[season] = True
            year_is_live[season] = False
            leagues_ctx = []
            for lg_code in ["AA", "NL"]:
                lg_teams = sorted([e for e in active if e["League"] == lg_code], key=lambda e: e["FranchiseName"])
                leagues_ctx.append((LEAGUE_NAMES[lg_code], lg_code, lg_teams))
            year_leagues_ctx[season] = leagues_ctx

    # --- Team pages (per-abbr, per-season rosters/stats) ---
    for abbr, team in teams_by_abbr.items():
        for season in seasons:
            standing = next((r for r in all_standings[season] if r["TeamAbbr"] == abbr), None)
            schedule = schedule_by_team_season.get((abbr, season), [])
            if not standing and not schedule:
                continue
            batters = [r for r in all_batting[season] if r["Team"] == abbr]
            batters.sort(key=lambda r: -float(r["AVG"]) if r["AB"] and int(r["AB"]) > 0 else 0)
            pitchers = [r for r in all_pitching[season] if r["Team"] == abbr]
            pitchers.sort(key=lambda r: -int(r["W"]))
            fielders = [r for r in all_fielding[season] if r["Team"] == abbr]
            fielders.sort(key=lambda r: -float(r["Inn"]))
            write(f"teams/{abbr}/{season}.html", "team_season.html",
                  team=team, season=season, standing=standing, batters=batters, pitchers=pitchers,
                  fielders=fielders, schedule=schedule)

    # --- Franchise hub pages (season-by-season across every era, e.g. Detroit -> Cleveland) ---
    for fid, eras in franchises_by_id.items():
        current = current_era_by_franchise[fid]
        franchise_seasons = []
        for season in seasons:
            for era in eras:
                match = next((r for r in all_standings[season] if r["TeamAbbr"] == era["Abbr"]), None)
                if match:
                    franchise_seasons.append(match)
                elif schedule_by_team_season.get((era["Abbr"], season)):
                    live = live_standings_by_season_team.get((era["Abbr"], season))
                    if live:
                        franchise_seasons.append({
                            "Season": season, "TeamAbbr": era["Abbr"], "TeamName": era["FranchiseName"],
                            "League": era["League"], "W": live["W"], "L": live["L"], "PCT": live["PCT"],
                            "GB": live["GB"], "Finish": None, "InProgress": True,
                        })
                    else:
                        franchise_seasons.append({
                            "Season": season, "TeamAbbr": era["Abbr"], "TeamName": era["FranchiseName"],
                            "League": era["League"], "W": None, "L": None, "PCT": None, "GB": None,
                            "Finish": None, "InProgress": False,
                        })
        write(f"teams/{current['Abbr']}/index.html", "team_index.html",
              team=current, seasons=list(reversed(franchise_seasons)), eras=eras)

    # --- Player pages ---
    players = defaultdict(lambda: {"batting": [], "pitching": [], "postseason_batting": [], "postseason_pitching": [], "fielding": [], "name": None, "last_name": None, "bats": None, "throws": None})
    for season in seasons:
        for row in all_batting[season]:
            pid = row["PlayerID"]
            players[pid]["batting"].append(row)
            players[pid]["name"] = row["Player"]
            players[pid]["last_name"] = row.get("LastName")
            players[pid]["bats"] = row.get("B")
        for row in all_pitching[season]:
            pid = row["PlayerID"]
            players[pid]["pitching"].append(row)
            players[pid]["name"] = row["Player"]
            players[pid]["last_name"] = row.get("LastName")
            players[pid]["throws"] = row.get("T")
        for row in all_ps_batting[season]:
            pid = row["PlayerID"]
            players[pid]["postseason_batting"].append(row)
            players[pid]["name"] = row["Player"]
            players[pid]["last_name"] = row.get("LastName")
        for row in all_ps_pitching[season]:
            pid = row["PlayerID"]
            players[pid]["postseason_pitching"].append(row)
            players[pid]["name"] = row["Player"]
            players[pid]["last_name"] = row.get("LastName")
        for row in all_fielding[season]:
            pid = row["PlayerID"]
            players[pid]["fielding"].append(row)
            players[pid]["name"] = row["Player"]
            players[pid]["last_name"] = row.get("LastName")

    # --- All-Star selections ---
    name_to_pid = {}
    dupe_names = set()
    for pid, pdata in players.items():
        nm = pdata["name"]
        if nm in name_to_pid and name_to_pid[nm] != pid:
            dupe_names.add(nm)
        name_to_pid[nm] = pid
    if dupe_names:
        print(f"WARNING: duplicate player display names, All-Star matching may be ambiguous: {sorted(dupe_names)}")

    # --- Placeholder pages for drafted players with no stats yet (e.g. incoming rookies) ---
    NAME_ALIASES = {
        "Charlie Bassett": "Charley Bassett",
        "Thomas Esterbrook": "Dude Esterbrook",
    }

    def resolve_player_name(name):
        name = NAME_ALIASES.get(name, name)
        return name_to_pid.get(name)

    placeholder_count = 0
    for draft_path in sorted(glob.glob(os.path.join(DATA_DIR, "*", "draft.csv"))):
        for row in load_csv(draft_path):
            raw_name = row["Player"].strip()
            name = NAME_ALIASES.get(raw_name, raw_name)
            if name in name_to_pid:
                continue
            base_pid = slugify_player_id(name)
            pid = base_pid
            n = 2
            while pid in players:
                pid = base_pid[:-2] + f"{n:02d}"
                n += 1
            players[pid]["name"] = name
            players[pid]["is_placeholder"] = True
            name_to_pid[name] = pid
            placeholder_count += 1
    if placeholder_count:
        print(f"NOTE: created {placeholder_count} placeholder player page(s) for drafted players with no stats yet.")

    # --- Player photos (optional; public-domain images only) ---
    photos_path = os.path.join(DATA_DIR, "photos.csv")
    photo_count = 0
    if os.path.exists(photos_path):
        for row in load_csv(photos_path):
            name = display_name(row["Player"])
            pid = name_to_pid.get(name)
            if not pid:
                print(f"NOTE: Photo for '{row['Player']}' has no matching player page -- skipped.")
                continue
            players[pid]["photo_url"] = row["PhotoURL"]
            players[pid]["photo_credit"] = row["PhotoCredit"]
            players[pid]["photo_credit_url"] = row["PhotoCreditURL"]
            photo_count += 1
    if photo_count:
        print(f"NOTE: attached {photo_count} player photo(s).")

    for pid in players:
        players[pid]["allstar_seasons"] = []

    for season in seasons:
        allstar_path = os.path.join(DATA_DIR, str(season), "allstars.csv")
        if not os.path.exists(allstar_path):
            continue
        for row in load_csv(allstar_path):
            nm = row["Player"].strip()
            pid = name_to_pid.get(nm)
            if not pid:
                print(f"WARNING: All-Star '{nm}' ({season}) not found among loaded players -- check spelling.")
                continue
            players[pid]["allstar_seasons"].append({
                "Season": row["Season"], "League": row["League"],
                "Pos": row["Pos"], "Team": row["Team"],
            })

    # --- Awards ---
    AWARD_ORDER = ["MVP", "Champion Hurler", "Rookie of the Year", "Fireman", "Silver Slugger", "Gold Glove"]
    AWARD_DISPLAY = {
        "MVP": "Most Valuable Player",
        "Champion Hurler": "Champion Hurler Award",
        "Rookie of the Year": "Rookie of the Year",
        "Fireman": "Fireman Award",
        "Silver Slugger": "Silver Slugger Award",
        "Gold Glove": "Gold Glove Award",
    }
    AWARD_TYPE = {
        "MVP": "voting", "Champion Hurler": "voting", "Rookie of the Year": "voting", "Fireman": "voting",
        "Silver Slugger": "position", "Gold Glove": "position",
    }
    POSITION_ORDER = ["P", "C", "1B", "2B", "3B", "SS", "LF", "CF", "RF", "OF"]

    for pid in players:
        players[pid]["awards_won"] = []

    awards_by_season = {}
    for season in seasons:
        awards_path = os.path.join(DATA_DIR, str(season), "awards.csv")
        season_awards = []
        if os.path.exists(awards_path):
            raw_rows = load_csv(awards_path)
            by_award = defaultdict(list)
            for row in raw_rows:
                row["PlayerID"] = name_to_pid.get(row["Player"].strip())
                if not row["PlayerID"]:
                    print(f"WARNING: Award entry '{row['Player']}' ({season}, {row['Award']}) not found among loaded players -- check spelling.")
                by_award[row["Award"]].append(row)

            for award_key in AWARD_ORDER:
                rows = by_award.get(award_key, [])
                if not rows:
                    continue  # e.g. Rookie of the Year has no valid 1885 nominees
                nl_rows = [r for r in rows if r["League"] == "NL"]
                aa_rows = [r for r in rows if r["League"] == "AA"]
                if AWARD_TYPE[award_key] == "voting":
                    nl_rows.sort(key=lambda r: int(r["Rank"]))
                    aa_rows.sort(key=lambda r: int(r["Rank"]))
                else:
                    nl_rows.sort(key=lambda r: POSITION_ORDER.index(r["Pos"]) if r["Pos"] in POSITION_ORDER else 99)
                    aa_rows.sort(key=lambda r: POSITION_ORDER.index(r["Pos"]) if r["Pos"] in POSITION_ORDER else 99)
                season_awards.append({
                    "key": award_key,
                    "display": AWARD_DISPLAY[award_key],
                    "type": AWARD_TYPE[award_key],
                    "nl_rows": nl_rows,
                    "aa_rows": aa_rows,
                })
                # winner badges: rank 1 for voting awards; every row for position awards (each is already a sole winner)
                for row in rows:
                    if int(row["Rank"]) == 1 and row["PlayerID"]:
                        label = f"{season} {row['League']} {AWARD_DISPLAY[award_key]}"
                        if AWARD_TYPE[award_key] == "position":
                            label += f" ({row['Pos']})"
                        players[row["PlayerID"]]["awards_won"].append({"Season": season, "Label": label})
        awards_by_season[season] = season_awards

    # --- Postseason data (loaded early so World Series MVP badge is ready before player pages render) ---
    postseason_by_season = {}
    for season in seasons:
        ps_path = os.path.join(DATA_DIR, str(season), "postseason.json")
        if not os.path.exists(ps_path):
            continue
        with open(ps_path, encoding="utf-8") as f:
            series = json.load(f)
        mvp = series.get("mvp")
        if mvp:
            mvp_pid = name_to_pid.get(mvp["player"])
            if mvp_pid:
                label = f"{season} World's Championship Series MVP"
                players[mvp_pid]["awards_won"].append({"Season": season, "Label": label})
                mvp["pid"] = mvp_pid
            else:
                print(f"WARNING: World Series MVP '{mvp['player']}' ({season}) not found among loaded players -- check spelling.")
        postseason_by_season[season] = series

    # --- Transactions (draft picks + trades; loaded early so player pages can show them) ---
    for pid in players:
        players[pid]["draft_picks"] = []
        players[pid]["trades"] = []

    draft_by_season = defaultdict(list)
    trades_by_season = defaultdict(list)

    for draft_path in sorted(glob.glob(os.path.join(DATA_DIR, "*", "draft.csv"))):
        for row in load_csv(draft_path):
            row["Season"] = int(row["Season"])
            row["Round"] = int(row["Round"])
            row["Pick"] = int(row["Pick"])
            pid = resolve_player_name(row["Player"])
            row["PlayerID"] = pid
            team = teams_by_abbr.get(row["TeamAbbr"])
            row["TeamName"] = team["FranchiseName"] if team else row["TeamAbbr"]
            draft_by_season[row["Season"]].append(row)
            if pid:
                players[pid]["draft_picks"].append(row)
            else:
                print(f"NOTE: Draft pick for '{row['Player']}' ({row['Season']}) has no matching player page -- shown as plain text.")

    for trades_path in sorted(glob.glob(os.path.join(DATA_DIR, "*", "trades.csv"))):
        for row in load_csv(trades_path):
            row["Season"] = int(row["Season"])
            pid = resolve_player_name(row["Player"])
            row["PlayerID"] = pid
            from_team = teams_by_abbr.get(row["FromTeamAbbr"])
            to_team = teams_by_abbr.get(row["ToTeamAbbr"])
            row["FromTeamName"] = from_team["FranchiseName"] if from_team else row["FromTeamAbbr"]
            row["ToTeamName"] = to_team["FranchiseName"] if to_team else row["ToTeamAbbr"]
            trades_by_season[row["Season"]].append(row)
            if pid:
                players[pid]["trades"].append(row)
            else:
                print(f"WARNING: Trade involving '{row['Player']}' ({row['Season']}) not found among loaded players -- check spelling.")

    for season_key in draft_by_season:
        draft_by_season[season_key].sort(key=lambda r: (r["Round"], r["Pick"]))

    # --- Narrative draft-day trades (multi-asset trades involving picks + players) ---
    TEAM_LINK_ALIASES = {
        "Baltimore Orioles": "BLN", "Orioles": "BLN",
        "Brooklyn Grays": "BRO", "Grays": "BRO",
        "Cincinnati Red Stockings": "CIN", "Red Stockings": "CIN",
        "Louisville Colonels": "LOU", "Colonels": "LOU",
        "Philadelphia Athletics": "PAT", "Athletics": "PAT",
        "St. Louis Browns": "STL", "Browns": "STL",
        "Boston Beaneaters": "BSN", "Beaneaters": "BSN",
        "Chicago White Stockings": "CHC", "White Stockings": "CHC",
        "Cleveland Blues": "CLV", "Blues": "CLV",
        "Detroit Wolverines": "DTN", "Wolverines": "DTN",
        "New York Giants": "NYG", "Giants": "NYG",
        "Philadelphia Quakers": "PHI", "Quakers": "PHI",
        "Pittsburgh Alleghenys": "PIT", "Alleghenys": "PIT",
    }
    TRADE_NAME_ALIASES = {"Charlie Radbourne": "Charley Radbourn"}

    _team_pattern = re.compile("|".join(re.escape(k) for k in sorted(TEAM_LINK_ALIASES, key=len, reverse=True)))

    def _team_sub(m):
        name = m.group(0)
        abbr = TEAM_LINK_ALIASES[name]
        return f'<a href="../teams/{hub_abbr.get(abbr, abbr)}/index.html">{name}</a>'

    all_player_names = sorted(set(name_to_pid) | set(TRADE_NAME_ALIASES), key=len, reverse=True)
    _player_pattern = re.compile("|".join(re.escape(n) for n in all_player_names)) if all_player_names else None

    def linkify_trade_text(text):
        matched_pids = []

        def player_sub(m):
            name = m.group(0)
            pid = name_to_pid.get(TRADE_NAME_ALIASES.get(name, name))
            if not pid:
                print(f"NOTE: Trade text mentions '{name}' -- no matching player page, left as plain text.")
                return name
            matched_pids.append(pid)
            return f'<a href="../players/{pid}.html">{name}</a>'

        text = _team_pattern.sub(_team_sub, text)
        if _player_pattern:
            text = _player_pattern.sub(player_sub, text)
        return text, matched_pids

    for pid in players:
        players[pid]["trade_mentions"] = []

    pick_trades_by_season = {}
    for pt_path in sorted(glob.glob(os.path.join(DATA_DIR, "*", "pick_trades.json"))):
        season = int(os.path.basename(os.path.dirname(pt_path)))
        with open(pt_path, encoding="utf-8") as f:
            raw_trades = json.load(f)
        linked_list = []
        for t in raw_trades:
            html, matched_pids = linkify_trade_text(t)
            linked_list.append(html)
            for pid in set(matched_pids):
                players[pid]["trade_mentions"].append({"season": season, "html": html})
        pick_trades_by_season[season] = linked_list


    def compute_batting_totals(rows):
        if not rows:
            return None
        sums = defaultdict(int)
        for r in rows:
            for k in ["G", "AB", "R", "H", "2B", "3B", "HR", "RBI", "BB", "SO", "HBP", "SB", "CS"]:
                sums[k] += int(r.get(k) or 0)
        ab = sums["AB"] or 1
        hits = sums["H"]
        walks = sums["BB"]
        hbp = sums["HBP"]
        singles = hits - sums["2B"] - sums["3B"] - sums["HR"]
        tb = singles + 2 * sums["2B"] + 3 * sums["3B"] + 4 * sums["HR"]
        totals = dict(sums)
        if len(rows) == 1:
            # Single season: mirror the source's own rate stats exactly rather than
            # re-deriving them (the sim's OBP formula factors in things like SF that
            # aren't in our export, so a recomputed value can be off by a rounding hair).
            totals["AVG"] = float(rows[0]["AVG"])
            totals["OBP"] = float(rows[0]["OBP"])
            totals["SLG"] = float(rows[0]["SLG"])
            totals["OPS"] = float(rows[0]["OPS"])
        else:
            avg = hits / ab
            obp = (hits + walks + hbp) / (ab + walks + hbp) if (ab + walks + hbp) else 0
            slg = tb / ab
            totals["AVG"] = avg
            totals["OBP"] = obp
            totals["SLG"] = slg
            totals["OPS"] = obp + slg
        return totals

    def compute_pitching_totals(rows):
        if not rows:
            return None
        psums = defaultdict(float)
        for r in rows:
            for k in ["G", "GS", "CG", "SHO", "W", "L", "SV", "IP", "H", "R", "ER", "HR", "BB", "SO"]:
                psums[k] += float(r.get(k) or 0)
        ip = psums["IP"] or 1
        era = 9 * psums["ER"] / ip
        whip = (psums["BB"] + psums["H"]) / ip
        totals = dict(psums)
        for k in ["G", "GS", "CG", "SHO", "W", "L", "SV", "H", "R", "ER", "HR", "BB", "SO"]:
            totals[k] = int(totals[k])
        totals["ERA"] = era
        totals["WHIP"] = whip
        return totals

    def build_display_rows(rows, totals_fn):
        """Group a player's rows by season; when a season has stints with more than
        one team (a mid-season trade), insert a bold combined '2TM'-style row after
        them, matching Baseball-Reference's convention for split seasons."""
        from itertools import groupby
        rows_sorted = sorted(rows, key=lambda r: int(r["SN"]))
        display = []
        for season, group in groupby(rows_sorted, key=lambda r: r["SN"]):
            group = list(group)
            display.extend(group)
            if len(group) > 1:
                combined = totals_fn(group)
                combined["SN"] = season
                combined["Team"] = f"{len(group)}TM"
                combined["_combined"] = True
                display.append(combined)
        return display

    for pid, pdata in players.items():
        batting_rows = sorted(pdata["batting"], key=lambda r: int(r["SN"]))
        pitching_rows = sorted(pdata["pitching"], key=lambda r: int(r["SN"]))
        ps_batting_rows = sorted(pdata["postseason_batting"], key=lambda r: int(r["SN"]))
        ps_pitching_rows = sorted(pdata["postseason_pitching"], key=lambda r: int(r["SN"]))

        batting_career = compute_batting_totals(batting_rows)
        pitching_career = compute_pitching_totals(pitching_rows)
        ps_batting_career = compute_batting_totals(ps_batting_rows)
        ps_pitching_career = compute_pitching_totals(ps_pitching_rows)

        pdata["batting_career"] = batting_career
        pdata["pitching_career"] = pitching_career
        pdata["teams"] = sorted(set(r["Team"] for r in batting_rows) | set(r["Team"] for r in pitching_rows))

        allstar_seasons = sorted(pdata.get("allstar_seasons", []), key=lambda a: int(a["Season"]))
        allstar_years = [a["Season"] for a in allstar_seasons]
        awards_won = sorted(pdata.get("awards_won", []), key=lambda a: int(a["Season"]))
        old_trades = sorted(pdata.get("trades", []), key=lambda t: t["Season"])
        draft_picks = sorted(pdata.get("draft_picks", []), key=lambda d: d["Season"])
        trade_mentions = sorted(pdata.get("trade_mentions", []), key=lambda t: t["season"])

        # Fallback for old simple trades.csv entries not covered by a narrative trade
        # mention in that same season (keeps players like Jim McCormick from losing
        # their only trade record).
        narrative_seasons = set(t["season"] for t in trade_mentions)
        trade_entries = list(trade_mentions)
        for t in old_trades:
            if t["Season"] in narrative_seasons:
                continue
            html = (f'Traded by <a href="../teams/{hub_abbr.get(t["FromTeamAbbr"], t["FromTeamAbbr"])}/index.html">{t["FromTeamName"]}</a> to the '
                    f'<a href="../teams/{hub_abbr.get(t["ToTeamAbbr"], t["ToTeamAbbr"])}/index.html">{t["ToTeamName"]}</a>.')
            trade_entries.append({"season": t["Season"], "html": html})

        # Interleave by season: draft pick(s) for a season, then trade(s) for that season.
        tx_seasons = sorted(set(d["Season"] for d in draft_picks) | set(e["season"] for e in trade_entries))
        transactions = []
        for s in tx_seasons:
            for d in draft_picks:
                if d["Season"] == s:
                    transactions.append({"kind": "draft", "data": d})
            for e in trade_entries:
                if e["season"] == s:
                    transactions.append({"kind": "trade", "html": e["html"]})

        batting_display_rows = build_display_rows(batting_rows, compute_batting_totals)
        pitching_display_rows = build_display_rows(pitching_rows, compute_pitching_totals)

        # --- Fielding: season-by-season rows plus one career-totals row per position ---
        fielding_rows_for_player = sorted(pdata.get("fielding", []), key=lambda r: (r["Season"], r["Pos"]))
        fielding_by_pos = defaultdict(list)
        for r in fielding_rows_for_player:
            fielding_by_pos[r["Pos"]].append(r)

        def compute_fielding_totals(rows):
            sums = defaultdict(float)
            for r in rows:
                for k in ["GP", "GS", "Inn", "E", "PO", "A", "DP", "GoodPlays", "PoorPlays", "SB", "CS", "PB", "PK"]:
                    sums[k] += float(r.get(k) or 0)
            totals = dict(sums)
            for k in ["GP", "GS", "E", "PO", "A", "DP", "GoodPlays", "PoorPlays", "SB", "CS", "PB", "PK"]:
                totals[k] = int(totals[k])
            if len(rows) == 1:
                totals["FPct"] = float(rows[0]["FPct"])
                totals["CERA"] = float(rows[0]["CERA"])
                totals["RF"] = float(rows[0]["RF"])
            else:
                chances = sums["PO"] + sums["A"] + sums["E"]
                totals["FPct"] = (sums["PO"] + sums["A"]) / chances if chances else 0.0
                totals["CERA"] = 9 * sums.get("ER", 0) / sums["Inn"] if sums["Inn"] else 0.0
                totals["RF"] = 9 * (sums["PO"] + sums["A"]) / sums["Inn"] if sums["Inn"] else 0.0
            return totals

        fielding_career_by_pos = {pos: compute_fielding_totals(rows) for pos, rows in fielding_by_pos.items()}

        # Position summary for the subtitle line, ordered by total innings at each
        # position (career, most-played first) -- e.g. "SS-CF".
        position_summary = "-".join(
            pos for pos, _ in sorted(
                fielding_career_by_pos.items(), key=lambda kv: kv[1]["Inn"], reverse=True
            )
        )

        write(f"players/{pid}.html", "player.html",
              player_name=pdata["name"], bats=pdata["bats"], throws=pdata["throws"],
              position_summary=position_summary,
              photo_url=pdata.get("photo_url"), photo_credit=pdata.get("photo_credit"),
              photo_credit_url=pdata.get("photo_credit_url"),
              batting_rows=batting_display_rows, pitching_rows=pitching_display_rows,
              batting_career=batting_career, pitching_career=pitching_career,
              allstar_count=len(allstar_years), allstar_years=allstar_years,
              awards_won=awards_won,
              ps_batting_rows=ps_batting_rows, ps_pitching_rows=ps_pitching_rows,
              ps_batting_career=ps_batting_career, ps_pitching_career=ps_pitching_career,
              fielding_rows=fielding_rows_for_player, fielding_career_by_pos=fielding_career_by_pos,
              transactions=transactions,
              is_placeholder=pdata.get("is_placeholder", False))

    # --- League leaders pages ---
    def top_n(rows, key_field, n=10, reverse=True, min_field=None, min_value=0):
        pool = rows
        if min_field:
            pool = [r for r in pool if float(r.get(min_field) or 0) >= min_value]
        pool = [r for r in pool if r.get(key_field) not in (None, "")]
        pool_sorted = sorted(pool, key=lambda r: float(r[key_field]), reverse=reverse)
        return pool_sorted[:n]

    def fmt_rows(rows, key_field, fmt):
        out = []
        for r in rows:
            r2 = dict(r)
            r2["display"] = fmt.format(float(r[key_field]))
            out.append(r2)
        return out

    write("leaders/index.html", "leaders_index.html", seasons=seasons)

    for season in seasons:
        batting_rows = all_batting[season]
        pitching_rows = all_pitching[season]

        # season length proxy from standings (W+L), used for qualifying thresholds
        srows = all_standings[season]
        team_games = max((int(r["W"]) + int(r["L"]) for r in srows), default=162)
        min_ab = int(round(3.1 * team_games))
        min_ip = team_games  # 1.0 * team games, B-Ref convention

        batting_categories = [
            {"label": "AVG", "rows": fmt_rows(top_n(batting_rows, "AVG", min_field="AB", min_value=min_ab), "AVG", "{:.3f}")},
            {"label": "HR", "rows": fmt_rows(top_n(batting_rows, "HR"), "HR", "{:.0f}")},
            {"label": "RBI", "rows": fmt_rows(top_n(batting_rows, "RBI"), "RBI", "{:.0f}")},
            {"label": "Runs", "rows": fmt_rows(top_n(batting_rows, "R"), "R", "{:.0f}")},
            {"label": "Hits", "rows": fmt_rows(top_n(batting_rows, "H"), "H", "{:.0f}")},
            {"label": "SB", "rows": fmt_rows(top_n(batting_rows, "SB"), "SB", "{:.0f}")},
            {"label": "OPS", "rows": fmt_rows(top_n(batting_rows, "OPS", min_field="AB", min_value=min_ab), "OPS", "{:.3f}")},
        ]
        pitching_categories = [
            {"label": "Wins", "rows": fmt_rows(top_n(pitching_rows, "W"), "W", "{:.0f}")},
            {"label": "ERA", "rows": fmt_rows(top_n(pitching_rows, "ERA", reverse=False, min_field="IP", min_value=min_ip), "ERA", "{:.2f}")},
            {"label": "Strikeouts", "rows": fmt_rows(top_n(pitching_rows, "SO"), "SO", "{:.0f}")},
            {"label": "Saves", "rows": fmt_rows(top_n(pitching_rows, "SV"), "SV", "{:.0f}")},
            {"label": "WHIP", "rows": fmt_rows(top_n(pitching_rows, "WHIP", reverse=False, min_field="IP", min_value=min_ip), "WHIP", "{:.2f}")},
        ]

        write(f"leaders/{season}.html", "leaders_season.html",
              season=season, batting_categories=batting_categories,
              pitching_categories=pitching_categories, min_ab=min_ab, min_ip=min_ip)

    # --- Career (all-time) leaders ---
    # Career qualifying thresholds scale with total team-games played across every loaded season,
    # consistent with how each individual season's thresholds were computed above.
    total_team_games = 0
    for season in seasons:
        srows = all_standings[season]
        total_team_games += max((int(r["W"]) + int(r["L"]) for r in srows), default=162)
    career_min_ab = int(round(3.1 * total_team_games))
    career_min_ip = total_team_games

    career_batting_pool = []
    career_pitching_pool = []
    for pid, pdata in players.items():
        teams_str = "/".join(pdata["teams"])
        if pdata["batting_career"]:
            row = dict(pdata["batting_career"])
            row["PlayerID"] = pid
            row["Player"] = pdata["name"]
            row["LastName"] = pdata["last_name"]
            row["Teams"] = teams_str
            career_batting_pool.append(row)
        if pdata["pitching_career"]:
            row = dict(pdata["pitching_career"])
            row["PlayerID"] = pid
            row["Player"] = pdata["name"]
            row["LastName"] = pdata["last_name"]
            row["Teams"] = teams_str
            career_pitching_pool.append(row)

    career_batting_categories = [
        {"label": "AVG", "rows": fmt_rows(top_n(career_batting_pool, "AVG", min_field="AB", min_value=career_min_ab), "AVG", "{:.3f}")},
        {"label": "HR", "rows": fmt_rows(top_n(career_batting_pool, "HR"), "HR", "{:.0f}")},
        {"label": "RBI", "rows": fmt_rows(top_n(career_batting_pool, "RBI"), "RBI", "{:.0f}")},
        {"label": "Runs", "rows": fmt_rows(top_n(career_batting_pool, "R"), "R", "{:.0f}")},
        {"label": "Hits", "rows": fmt_rows(top_n(career_batting_pool, "H"), "H", "{:.0f}")},
        {"label": "SB", "rows": fmt_rows(top_n(career_batting_pool, "SB"), "SB", "{:.0f}")},
        {"label": "OPS", "rows": fmt_rows(top_n(career_batting_pool, "OPS", min_field="AB", min_value=career_min_ab), "OPS", "{:.3f}")},
    ]
    career_pitching_categories = [
        {"label": "Wins", "rows": fmt_rows(top_n(career_pitching_pool, "W"), "W", "{:.0f}")},
        {"label": "ERA", "rows": fmt_rows(top_n(career_pitching_pool, "ERA", reverse=False, min_field="IP", min_value=career_min_ip), "ERA", "{:.2f}")},
        {"label": "Strikeouts", "rows": fmt_rows(top_n(career_pitching_pool, "SO"), "SO", "{:.0f}")},
        {"label": "Saves", "rows": fmt_rows(top_n(career_pitching_pool, "SV"), "SV", "{:.0f}")},
        {"label": "WHIP", "rows": fmt_rows(top_n(career_pitching_pool, "WHIP", reverse=False, min_field="IP", min_value=career_min_ip), "WHIP", "{:.2f}")},
    ]

    write("leaders/career.html", "career_leaders.html",
          batting_categories=career_batting_categories,
          pitching_categories=career_pitching_categories,
          min_ab=career_min_ab, min_ip=career_min_ip)

    # --- Manager pages ---
    managers = defaultdict(lambda: {"name": None, "seasons": []})
    for season in seasons:
        for row in all_standings[season]:
            slug = row["OwnerSlug"]
            managers[slug]["name"] = row.get("Owner", "Unknown")
            managers[slug]["seasons"].append(row)

    for slug, mdata in managers.items():
        seasons_sorted = sorted(mdata["seasons"], key=lambda r: int(r["Season"]))
        write(f"managers/{slug}.html", "manager.html",
              manager_name=mdata["name"], seasons=seasons_sorted)

    # --- Awards pages ---
    write("awards/index.html", "awards_index.html", seasons=seasons)
    for season in seasons:
        write(f"awards/{season}.html", "awards_season.html",
              season=season, categories=awards_by_season[season],
              ws_mvp=postseason_by_season.get(season, {}).get("mvp"))

    # --- All-Star Game pages ---
    def resolve_pids(game_data):
        """Fill in each batting/pitching row's player-page link by matching against the site roster."""
        for team_data in list(game_data.get("batting", {}).values()) + list(game_data.get("pitching", {}).values()):
            for row in team_data.get("rows", []):
                row["pid"] = name_to_pid.get(row["player"])

    allstar_game_seasons = set()
    for season in seasons:
        asg_path = os.path.join(DATA_DIR, str(season), "allstar_game.json")
        if os.path.exists(asg_path):
            with open(asg_path, encoding="utf-8") as f:
                game_data = json.load(f)
            resolve_pids(game_data)
            write(f"allstar-game/{season}.html", "allstar_game.html", season=season, game=game_data)
            allstar_game_seasons.add(season)

    # --- Regular season game box scores (linked from each team's Schedule section) ---
    for season in seasons:
        games_path = os.path.join(DATA_DIR, str(season), "games.json")
        if not os.path.exists(games_path):
            continue
        with open(games_path, encoding="utf-8") as f:
            game_list = json.load(f)
        for g in game_list:
            slug = f"{g['game_num']}-{g['away'].lower()}-{g['home'].lower()}"
            resolve_pids(g)
            write(f"boxscore/{season}/{slug}.html", "allstar_game.html",
                  season=season, game=g, is_regular_season_game=True)

    # --- Postseason pages (write box scores + index using data already loaded above) ---
    for season, series in postseason_by_season.items():
        for g in series["games"]:
            resolve_pids(g)
            score_rows = {r["team"]: r["R"] for r in g["linescore"]["rows"]}
            g["winner_team"] = series["winner"]["team"] if score_rows[series["winner"]["team"]] > score_rows[series["loser"]["team"]] else series["loser"]["team"]
            g["score_summary"] = f'{series["winner"]["team_name"] if g["winner_team"]==series["winner"]["team"] else series["loser"]["team_name"]} win {max(score_rows.values())}-{min(score_rows.values())}'
            write(f"postseason-game/{season}-{g['game_number']}.html", "allstar_game.html",
                  season=season, game=g, is_postseason_game=True, series=series)
        write(f"postseason/{season}.html", "postseason_index.html", season=season, series=series)

    # --- Season hub pages (standings + condensed awards + All-Star Game link + postseason) ---
    for season in seasons:
        write(f"years/{season}.html", "standings.html",
              leagues=year_leagues_ctx[season], season=season,
              categories=awards_by_season[season],
              has_allstar_game=season in allstar_game_seasons,
              postseason=postseason_by_season.get(season),
              has_draft=season in draft_by_season,
              trades=trades_by_season.get(season, []),
              pick_trades=pick_trades_by_season.get(season, []),
              is_preseason=year_is_preseason[season], is_live=year_is_live[season])

    for season, picks in draft_by_season.items():
        write(f"draft/{season}.html", "draft_results.html", season=season, draft_picks=picks)

    # --- Seasons index page (modeled on baseball-reference.com/leagues/) ---
    SUMMARY_AWARDS = ["MVP", "Champion Hurler", "Fireman", "Rookie of the Year"]
    seasons_summary = []
    for season in sorted(seasons, reverse=True):
        awards_dict = {cat["key"]: cat for cat in awards_by_season.get(season, [])}
        row = {"season": season}
        for lg_code in ["AA", "NL"]:
            lg_rows = [r for r in all_standings[season] if r["League"] == lg_code]
            champion = max(lg_rows, key=lambda r: float(r["PCT"]), default=None)
            entry = {"champion": champion}
            for award_key in SUMMARY_AWARDS:
                cat = awards_dict.get(award_key)
                winner = None
                if cat:
                    rows_for_lg = cat["aa_rows"] if lg_code == "AA" else cat["nl_rows"]
                    winner = next((r for r in rows_for_lg if r["Rank"] == "1"), None)
                entry[award_key] = winner
            row[lg_code] = entry
        seasons_summary.append(row)
    write("seasons/index.html", "seasons_index.html", seasons_summary=seasons_summary)

    most_recent_postseason = None
    if postseason_by_season:
        most_recent_postseason = postseason_by_season[max(postseason_by_season.keys())]

    write("index.html", "index.html",
          leagues=year_leagues_ctx[latest_season], season=latest_season,
          all_teams=sorted(current_era_by_franchise.values(), key=lambda t: t["FranchiseName"]),
          postseason=most_recent_postseason,
          is_preseason=year_is_preseason[latest_season], is_live=year_is_live[latest_season])

    # --- Search index (client-side JSON, used by the header search box) ---
    search_entries = []
    for abbr, team in teams_by_abbr.items():
        if not any(r["TeamAbbr"] == abbr for s in seasons for r in all_standings[s]):
            continue
        search_entries.append({
            "type": "Team",
            "name": team["FranchiseName"],
            "sub": f'{team["League"]} \u00b7 {abbr}',
            "url": f"teams/{abbr}/index.html",
        })
    for pid, pdata in players.items():
        seasons_played = sorted(set(r["SN"] for r in pdata["batting"] + pdata["pitching"]))
        if not seasons_played:
            yr_range = "no stats yet"
        elif len(seasons_played) == 1:
            yr_range = f"{seasons_played[0]}"
        else:
            yr_range = f"{seasons_played[0]}\u2013{seasons_played[-1]}"
        search_entries.append({
            "type": "Player",
            "name": pdata["name"],
            "sub": yr_range,
            "url": f"players/{pid}.html",
        })
    for season in seasons:
        search_entries.append({
            "type": "Season",
            "name": f"{season} Season",
            "sub": "Standings",
            "url": f"years/{season}.html",
        })
    search_entries.append({
        "type": "Leaders",
        "name": "Career Leaders",
        "sub": "All-time totals",
        "url": "leaders/career.html",
    })
    for season in seasons:
        search_entries.append({
            "type": "Awards",
            "name": f"{season} Awards",
            "sub": "MVP, Champion Hurler, and more",
            "url": f"awards/{season}.html",
        })
    for season in allstar_game_seasons:
        search_entries.append({
            "type": "All-Star Game",
            "name": f"{season} All-Star Game",
            "sub": "Box score & play-by-play",
            "url": f"allstar-game/{season}.html",
        })
    for season, series in postseason_by_season.items():
        search_entries.append({
            "type": "Postseason",
            "name": series["series_name"],
            "sub": series["result"],
            "url": f"postseason/{season}.html",
        })
    for season in draft_by_season:
        search_entries.append({
            "type": "Draft",
            "name": f"{season} Draft Results",
            "sub": f"{len(draft_by_season[season])} picks",
            "url": f"draft/{season}.html",
        })
    for slug, mdata in managers.items():
        seasons_managed = sorted(set(str(r["Season"]) for r in mdata["seasons"]))
        yr_range = seasons_managed[0] if len(seasons_managed) == 1 else f"{seasons_managed[0]}\u2013{seasons_managed[-1]}"
        search_entries.append({
            "type": "Manager",
            "name": mdata["name"],
            "sub": yr_range,
            "url": f"managers/{slug}.html",
        })

    search_index_path = os.path.join(SITE_DIR, "static", "search-index.json")
    os.makedirs(os.path.dirname(search_index_path), exist_ok=True)
    with open(search_index_path, "w", encoding="utf-8") as f:
        json.dump(search_entries, f)

    print(f"Built site for seasons: {seasons}")
    print(f"  {len(teams_by_abbr)} teams, {len(players)} players")
    print(f"Output: {SITE_DIR}")


if __name__ == "__main__":
    main()
