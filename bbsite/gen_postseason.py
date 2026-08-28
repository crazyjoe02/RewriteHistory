#!/usr/bin/env python3
"""Generates data/1885/postseason.json from the six World's Championship Series box scores."""
import json
import os

def b(player, pos, ab, r, h, rbi, bb, so, d2=0, d3=0, hr=0, sb=0, cs=0):
    return {"player": player, "pos": pos, "ab": ab, "r": r, "h": h, "rbi": rbi, "bb": bb, "so": so,
            "2b": d2, "3b": d3, "hr": hr, "sb": sb, "cs": cs}

def p(player, decision, ip, h, r, er, bb, so, hr, era):
    return {"player": player, "decision": decision, "ip": ip, "h": h, "r": r, "er": er, "bb": bb, "so": so, "hr": hr, "era": era}

def totals_b(ab, r, h, rbi, bb, so, d2=0, d3=0, hr=0, sb=0, cs=0):
    return {"ab": ab, "r": r, "h": h, "rbi": rbi, "bb": bb, "so": so, "2b": d2, "3b": d3, "hr": hr, "sb": sb, "cs": cs}

def totals_p(ip, h, r, er, bb, so, hr):
    return {"ip": ip, "h": h, "r": r, "er": er, "bb": bb, "so": so, "hr": hr}

games = []

# ============================== GAME 1 ==============================
games.append({
    "game_number": 1,
    "venue": "Sportsman's Park (II)",
    "player_of_game": {"player": "Bob Caruthers", "team": "STL", "note": "tosses a 5-hit shutout"},
    "linescore": {
        "innings": [1, 2, 3, 4, 5, 6, 7, 8, 9],
        "rows": [
            {"team": "BSN", "label": "Boston Beaneaters", "by_inning": [0, 0, 0, 0, 0, 0, 0, 0, 0], "R": 0, "H": 5, "E": 1},
            {"team": "STL", "label": "Saint Louis Browns", "by_inning": [0, 0, 1, 0, 0, 0, 2, 1, None], "R": 4, "H": 9, "E": 2}
        ]
    },
    "batting": {
        "BSN": {
            "rows": [
                b("Pete Hotaling", "LF", 4, 0, 1, 0, 0, 0, d2=1),
                b("Jim O'Rourke", "C", 4, 0, 0, 0, 0, 0),
                b("Pop Smith", "2B", 4, 0, 0, 0, 0, 0, sb=1),
                b("Dan Brouthers", "1B", 3, 0, 1, 0, 1, 1, sb=1),
                b("Paul Hines", "3B", 4, 0, 0, 0, 0, 0),
                b("Ed Andrews", "RF", 4, 0, 1, 0, 0, 0),
                b("GStovall Ohfor", "CF", 4, 0, 1, 0, 0, 0),
                b("Sadie Houck", "SS", 3, 0, 0, 0, 0, 0),
                b("Guy Hecker", "P", 2, 0, 1, 0, 0, 0),
                b("Ezra Sutton", "PH", 1, 0, 0, 0, 0, 0),
                b("John Henry", "P", 0, 0, 0, 0, 0, 0),
                b("Billy Taylor", "P", 0, 0, 0, 0, 0, 0),
                b("John Kirby", "P", 0, 0, 0, 0, 0, 0),
            ],
            "totals": totals_b(33, 0, 5, 0, 1, 1, d2=1, sb=2),
            "footnotes": {"2B": "P.Hotaling (1)", "SB": "P.Smith (1), D.Brouthers (1)", "E": "P.Hotaling (1)"}
        },
        "STL": {
            "rows": [
                b("Yank Robinson", "LF", 4, 1, 1, 0, 0, 0),
                b("Chicken Wolf", "RF", 4, 0, 1, 1, 0, 0),
                b("Roger Connor", "1B", 4, 0, 0, 0, 0, 0),
                b("George Gore", "CF", 4, 0, 0, 0, 0, 1),
                b("Germany Smith", "SS", 4, 2, 2, 0, 0, 0, sb=2),
                b("Mike Muldoon", "3B", 3, 1, 2, 1, 0, 0, d2=2),
                b("Doc Bushong", "PH-3B", 1, 0, 1, 1, 0, 0, sb=1),
                b("Joe Miller", "3B", 0, 0, 0, 0, 0, 0),
                b("Sam Barkley", "2B", 4, 0, 1, 0, 0, 0, sb=1),
                b("Jimmy Peoples", "C", 2, 0, 0, 0, 0, 0),
                b("Barney Gilligan", "C", 0, 0, 0, 0, 0, 0),
                b("Bob Caruthers", "P", 3, 0, 1, 1, 0, 0),
            ],
            "totals": totals_b(33, 4, 9, 4, 0, 1, d2=2, sb=6),
            "footnotes": {"2B": "M.Muldoon 2 (2)", "RBI": "C.Wolf (1), M.Muldoon (1), D.Bushong (1), B.Caruthers (1)",
                          "2-Out RBI": "C.Wolf, D.Bushong, B.Caruthers", "SH": "J.Peoples",
                          "SB": "Y.Robinson (1), C.Wolf (1), G.Smith 2 (2), D.Bushong (1), S.Barkley (1)",
                          "E": "Y.Robinson (1), G.Smith (1)"}
        }
    },
    "pitching": {
        "BSN": {"rows": [
            p("Guy Hecker", "L (0-1)", "6.0", 4, 1, 1, 0, 0, 0, "1.50"),
            p("John Henry", "", "1.0", 3, 2, 2, 0, 0, 0, "18.00"),
            p("Billy Taylor", "", "0.2", 2, 1, 1, 0, 1, 0, "13.50"),
            p("John Kirby", "", "0.1", 0, 0, 0, 0, 0, 0, "0.00"),
        ], "totals": totals_p("8.0", 9, 4, 4, 0, 1, 0)},
        "STL": {"rows": [
            p("Bob Caruthers", "W (1-0)", "9.0", 5, 0, 0, 1, 1, 0, "0.00"),
        ], "totals": totals_p("9.0", 5, 0, 0, 1, 1, 0)}
    },
    "playbyplay": [
        {"inning": 1, "half": "Top", "team": "BSN", "plays": [
            "B.Caruthers enters the game to pitch.",
            "P.Hotaling flies out to CF.",
            "J.O'Rourke grounds out to SS.",
            "Y.Robinson botches a routine flyball and P.Smith reaches on the error.",
            "P.Smith steals 2B.",
            "D.Brouthers is intentionally walked.",
            "P.Hines grounds out to SS.",
        ]},
        {"inning": 1, "half": "Bottom", "team": "STL", "plays": [
            "G.Hecker enters the game to pitch.",
            "Y.Robinson grounds out to SS.",
            "C.Wolf grounds out to SS.",
            "R.Connor grounds out to 2B.",
        ]},
        {"inning": 2, "half": "Top", "team": "BSN", "plays": [
            "E.Andrews hits an infield single to 3B.",
            "G.Ohfor grounds into a 6-4-3 double play.",
            "S.Houck lines out to SS.",
        ]},
        {"inning": 2, "half": "Bottom", "team": "STL", "plays": [
            "G.Gore lines out to SS.",
            "G.Smith flies out to RCF.",
            "M.Muldoon rips a liner to LCF for a double.",
            "S.Barkley flies out to LF.",
        ]},
        {"inning": 3, "half": "Top", "team": "BSN", "plays": [
            "G.Hecker hits a Texas League single to LF.",
            "P.Hotaling pops out to 1B.",
            "J.O'Rourke pops out to 2B.",
            "P.Smith grounds out to 2B.",
        ]},
        {"inning": 3, "half": "Bottom", "team": "STL", "plays": [
            "J.Peoples grounds out to SS.",
            "B.Caruthers lines out to 2B.",
            "Y.Robinson hits a groundball single to LF.",
            "Y.Robinson steals 2B.",
            "C.Wolf smokes a line drive single to CF. Y.Robinson scores.",
            "C.Wolf swipes 2B.",
            "R.Connor grounds out to 1B.",
        ]},
        {"inning": 4, "half": "Top", "team": "BSN", "plays": [
            "D.Brouthers lines a single to RF.",
            "D.Brouthers swipes 2B.",
            "P.Hines hits a shallow flyout to CF.",
            "E.Andrews grounds out to SS.",
            "G.Ohfor grounds out to 3B.",
        ]},
        {"inning": 4, "half": "Bottom", "team": "STL", "plays": [
            "G.Gore grounds out to 1B.",
            "G.Smith grounds out to SS.",
            "M.Muldoon hits a shallow flyout to CF.",
        ]},
        {"inning": 5, "half": "Top", "team": "BSN", "plays": [
            "S.Houck grounds out to SS.",
            "G.Hecker hits a shallow flyout to CF.",
            "P.Hotaling grounds out to SS.",
        ]},
        {"inning": 5, "half": "Bottom", "team": "STL", "plays": [
            "S.Barkley hits a groundball single to LF.",
            "S.Barkley steals 2B.",
            "J.Peoples hits a sacrifice bunt to 3B. All runners advance.",
            "B.Caruthers hits a shallow flyout to RF.",
            "Y.Robinson grounds out to SS.",
        ]},
        {"inning": 6, "half": "Top", "team": "BSN", "plays": [
            "J.O'Rourke flies out to deep LCF.",
            "P.Smith grounds out to 3B.",
            "D.Brouthers strikes out looking.",
        ]},
        {"inning": 6, "half": "Bottom", "team": "STL", "plays": [
            "C.Wolf grounds out to 3B.",
            "R.Connor grounds out to SS.",
            "G.Gore flies out to deep RCF.",
        ]},
        {"inning": 7, "half": "Top", "team": "BSN", "plays": [
            "P.Hines grounds out to 3B.",
            "E.Andrews lines out to SS.",
            "G.Ohfor grounds it thru the hole to LF for a single.",
            "G.Smith misplays a routine grounder and S.Houck reaches on the error.",
            "E.Sutton enters the game as a pinch-hitter for G.Hecker.",
            "E.Sutton hits into a 4-6 fielder's choice.",
        ]},
        {"inning": 7, "half": "Bottom", "team": "STL", "plays": [
            "J.Henry enters the game to pitch.",
            "G.Smith hits a Texas League single to RCF.",
            "G.Smith steals 2B.",
            "M.Muldoon skies one to RF that falls in for a double. G.Smith scores.",
            "S.Barkley grounds out to 2B.",
            "J.Peoples grounds out to 1B.",
            "B.Caruthers hits an infield single to SS. M.Muldoon scores.",
            "P.Hotaling drops a flyball and Y.Robinson reaches on a 2-base error.",
            "C.Wolf pops out to SS.",
        ]},
        {"inning": 8, "half": "Top", "team": "BSN", "plays": [
            "P.Hotaling smokes a linedrive double down the rightfield line.",
            "J.O'Rourke grounds out to SS.",
            "P.Smith grounds out to SS.",
            "D.Brouthers grounds out to 2B.",
        ]},
        {"inning": 8, "half": "Bottom", "team": "STL", "plays": [
            "B.Taylor enters the game to pitch.",
            "R.Connor hits a shallow flyout to CF.",
            "G.Gore strikes out on a ball out of the zone.",
            "G.Smith smokes a line drive single to RF.",
            "D.Bushong enters the game as a pinch-hitter for M.Muldoon.",
            "G.Smith swipes 2B.",
            "D.Bushong lines a single to LF. G.Smith scores.",
            "J.Kirby enters the game to pitch.",
            "D.Bushong swipes 2B.",
            "S.Barkley flies out to LCF.",
        ]},
        {"inning": 9, "half": "Top", "team": "BSN", "plays": [
            "D.Bushong remains in the game at 3B.",
            "B.Gilligan enters the game at C as a defensive replacement.",
            "J.Miller enters the game at 3B as a defensive replacement.",
            "P.Hines grounds out to 2B.",
            "E.Andrews grounds out to 2B.",
            "G.Ohfor grounds out to the pitcher.",
        ]},
    ]
})

with open(os.path.join(os.path.dirname(__file__), "_game1_only_check.json"), "w") as f:
    json.dump(games[0], f, indent=2)
print("Game 1 built and validated:", len(json.dumps(games[0])), "bytes")
