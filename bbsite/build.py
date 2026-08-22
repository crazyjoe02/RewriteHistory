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
import os
import re
import shutil
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
    # --- Load master team registry ---
    teams = load_csv(os.path.join(DATA_DIR, "teams.csv"))
    teams_by_abbr = {t["Abbr"]: t for t in teams}

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

    for season in seasons:
        sdir = os.path.join(DATA_DIR, str(season))
        standings_path = os.path.join(sdir, "standings.csv")
        batting_path = os.path.join(sdir, "batting.csv")
        pitching_path = os.path.join(sdir, "pitching.csv")

        standings_rows = load_csv(standings_path) if os.path.exists(standings_path) else []
        batting_rows = load_csv(batting_path) if os.path.exists(batting_path) else []
        pitching_rows = load_csv(pitching_path) if os.path.exists(pitching_path) else []

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

        all_standings[season] = standings_rows
        all_batting[season] = batting_rows
        all_pitching[season] = pitching_rows

    # --- Set up Jinja ---
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), trim_blocks=True, lstrip_blocks=True)

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

    # --- Home page (latest season standings) ---
    latest_rows = all_standings[latest_season]
    leagues_ctx = []
    for lg_code in ["AA", "NL"]:
        rows = [r for r in latest_rows if r["League"] == lg_code]
        rows.sort(key=lambda r: -float(r["PCT"]))
        leagues_ctx.append((LEAGUE_NAMES[lg_code], lg_code, rows))

    write("index.html", "index.html",
          leagues=leagues_ctx, season=latest_season,
          all_teams=sorted(teams, key=lambda t: t["FranchiseName"]))

    # --- Year standings pages ---
    for season in seasons:
        rows = all_standings[season]
        leagues_ctx = []
        for lg_code in ["AA", "NL"]:
            lg_rows = [r for r in rows if r["League"] == lg_code]
            lg_rows.sort(key=lambda r: -float(r["PCT"]))
            leagues_ctx.append((LEAGUE_NAMES[lg_code], lg_code, lg_rows))
        write(f"years/{season}.html", "standings.html", leagues=leagues_ctx, season=season)

    # --- Team pages ---
    for abbr, team in teams_by_abbr.items():
        team_seasons = []
        for season in seasons:
            match = next((r for r in all_standings[season] if r["TeamAbbr"] == abbr), None)
            if match:
                team_seasons.append(match)
        if not team_seasons:
            continue  # franchise not active in any loaded season yet
        write(f"teams/{abbr}/index.html", "team_index.html", team=team, seasons=team_seasons)

        for season in seasons:
            standing = next((r for r in all_standings[season] if r["TeamAbbr"] == abbr), None)
            if not standing:
                continue
            batters = [r for r in all_batting[season] if r["Team"] == abbr]
            batters.sort(key=lambda r: -float(r["AVG"]) if r["AB"] and int(r["AB"]) > 0 else 0)
            pitchers = [r for r in all_pitching[season] if r["Team"] == abbr]
            pitchers.sort(key=lambda r: -int(r["W"]))
            write(f"teams/{abbr}/{season}.html", "team_season.html",
                  team=team, season=season, standing=standing, batters=batters, pitchers=pitchers)

    # --- Player pages ---
    players = defaultdict(lambda: {"batting": [], "pitching": [], "name": None, "last_name": None, "bats": None, "throws": None})
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

    for pid, pdata in players.items():
        batting_rows = sorted(pdata["batting"], key=lambda r: int(r["SN"]))
        pitching_rows = sorted(pdata["pitching"], key=lambda r: int(r["SN"]))

        batting_career = None
        if batting_rows:
            sums = defaultdict(int)
            for r in batting_rows:
                for k in ["G", "AB", "R", "H", "2B", "3B", "HR", "RBI", "BB", "SO", "HBP", "SB", "CS"]:
                    sums[k] += int(r.get(k) or 0)
            ab = sums["AB"] or 1
            hits = sums["H"]
            walks = sums["BB"]
            hbp = sums["HBP"]
            singles = hits - sums["2B"] - sums["3B"] - sums["HR"]
            tb = singles + 2 * sums["2B"] + 3 * sums["3B"] + 4 * sums["HR"]
            avg = hits / ab
            obp = (hits + walks + hbp) / (ab + walks + hbp) if (ab + walks + hbp) else 0
            slg = tb / ab
            batting_career = dict(sums)
            batting_career["AVG"] = avg
            batting_career["OBP"] = obp
            batting_career["SLG"] = slg
            batting_career["OPS"] = obp + slg

        pitching_career = None
        if pitching_rows:
            psums = defaultdict(float)
            for r in pitching_rows:
                for k in ["G", "GS", "CG", "SHO", "W", "L", "SV", "IP", "H", "R", "ER", "HR", "BB", "SO"]:
                    psums[k] += float(r.get(k) or 0)
            ip = psums["IP"] or 1
            era = 9 * psums["ER"] / ip
            whip = (psums["BB"] + psums["H"]) / ip
            pitching_career = dict(psums)
            # counting stats look better as ints; IP keeps its decimal
            for k in ["G", "GS", "CG", "SHO", "W", "L", "SV", "H", "R", "ER", "HR", "BB", "SO"]:
                pitching_career[k] = int(pitching_career[k])
            pitching_career["ERA"] = era
            pitching_career["WHIP"] = whip

        pdata["batting_career"] = batting_career
        pdata["pitching_career"] = pitching_career
        pdata["teams"] = sorted(set(r["Team"] for r in batting_rows) | set(r["Team"] for r in pitching_rows))

        write(f"players/{pid}.html", "player.html",
              player_name=pdata["name"], bats=pdata["bats"], throws=pdata["throws"],
              batting_rows=batting_rows, pitching_rows=pitching_rows,
              batting_career=batting_career, pitching_career=pitching_career)

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

    # --- Search index (client-side JSON, used by the header search box) ---
    import json
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
        yr_range = f"{seasons_played[0]}" if len(seasons_played) == 1 else f"{seasons_played[0]}\u2013{seasons_played[-1]}"
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
