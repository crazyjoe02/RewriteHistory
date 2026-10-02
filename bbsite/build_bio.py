#!/usr/bin/env python3
"""Build data/bio.csv (Baseball-Reference-style biographical data) for every real player.

Source: the Chadwick Bureau / Lahman "People.csv" (the same register Baseball-Reference uses).
    curl -sSfL -o /tmp/People.csv https://raw.githubusercontent.com/chadwickbureau/baseballdatabank/master/core/People.csv
    python3 build_bio.py /tmp/People.csv

Matching: first+last name, limited to players whose real careers overlap the 1880s.
OVERRIDES pins ambiguous names and nickname/spelling differences to a specific playerID.
Prospects (WhatIfSports-generated players) are skipped: they have no real-world record.
"""
import csv, glob, os, sys, collections

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = sys.argv[1] if len(sys.argv) > 1 else "/tmp/People.csv"

OVERRIDES = {
    # ambiguous same-name players
    "Bill Phillips": "phillbi01", "Jim Donnelly": "donneji01", "Ed Kennedy": "kenneed01",
    "John Coleman": "colemjo01", "Bill Gleason": "gleasbi01", "John Ward": "wardjo01",
    "Jim McCormick": "mccorji01", "Bill White": "whitebi02",
    # nickname / spelling differences between the sim and the register
    "Charley Radbourn": "radboch01", "Stump Wiedman": "wiedmst01", "Gurdon Whiteley": "whitegu01",
    "Charlie Getzien": "getzich01", "John Healy": "healyjo01", "Ned Williamson": "willine01",
    "Orator Shaffer": "shaffor01", "Pete Gillespie": "gillepe01", "Ed Begley": "begleed01",
    "Bill Stemmeyer": "stemmbi01", "Jack McGeachy": "mcgeaja01", "Elton Chamberlain": "chambel01",
    "Buck Gladman": "gladmbu01", "Cannonball Titcomb": "titcoca01", "Tony Madigan": "madigto01",
}
MONTHS = ["", "January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]


def era_ok(p):
    d, fg = p["debut"][:4], p["finalGame"][:4]
    return bool(d) and int(d) <= 1892 and (not fg or int(fg) >= 1876)


def date(y, m, d):
    if not y:
        return ""
    if m and d:
        return f"{MONTHS[int(m)]} {int(d)}, {y}"
    return str(y)


def place(city, state, country):
    parts = [x for x in (city, state) if x]
    if country and country != "USA":
        parts.append(country)
    return ", ".join(parts)


def main():
    people = list(csv.DictReader(open(SRC, encoding="utf-8")))
    by_id = {p["playerID"]: p for p in people}
    by_name = collections.defaultdict(list)
    for p in people:
        by_name[(p["nameFirst"].strip().lower(), p["nameLast"].strip().lower())].append(p)

    league = {}
    for f in sorted(glob.glob(os.path.join(HERE, "data", "*", "batting.csv")) +
                    glob.glob(os.path.join(HERE, "data", "*", "pitching.csv"))):
        for r in csv.DictReader(open(f)):
            last, first = [x.strip() for x in r["Player"].split(",", 1)]
            nm = f"{first} {last}"
            league.setdefault(nm, False)
            if r.get("Prospect") == "Y":
                league[nm] = True

    out, unmatched = [], []
    for nm, prospect in sorted(league.items()):
        if prospect:
            continue
        p = by_id.get(OVERRIDES[nm]) if nm in OVERRIDES else None
        if p is None:
            first, last = nm.rsplit(" ", 1)
            c = [x for x in by_name[(first.lower(), last.lower())] if era_ok(x)]
            p = c[0] if len(c) == 1 else None
        if p is None:
            unmatched.append(nm)
            continue
        h = int(p["height"]) if p["height"] else None
        out.append({
            "Player": nm, "bbrefID": p["bbrefID"] or p["playerID"],
            "FullName": f"{p['nameGiven']} {p['nameLast']}".strip(),
            "Born": date(p["birthYear"], p["birthMonth"], p["birthDay"]),
            "BirthYear": p["birthYear"], "BirthMonth": p["birthMonth"], "BirthDay": p["birthDay"],
            "BirthPlace": place(p["birthCity"], p["birthState"], p["birthCountry"]),
            "Died": date(p["deathYear"], p["deathMonth"], p["deathDay"]),
            "DeathPlace": place(p["deathCity"], p["deathState"], p["deathCountry"]),
            "Height": f"{h // 12}-{h % 12}" if h else "", "Weight": p["weight"],
            "Bats": {"R": "Right", "L": "Left", "B": "Both"}.get(p["bats"], ""),
            "Throws": {"R": "Right", "L": "Left"}.get(p["throws"], ""),
            "MLBDebut": p["debut"], "MLBFinal": p["finalGame"],
        })
    with open(os.path.join(HERE, "data", "bio.csv"), "w", newline="") as fo:
        w = csv.DictWriter(fo, fieldnames=list(out[0].keys()))
        w.writeheader(); w.writerows(out)
    print(f"bio rows: {len(out)}   unmatched real players: {unmatched or 'none'}")


if __name__ == "__main__":
    main()
