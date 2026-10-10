import re


def parse_playbyplay(text, away_name, home_name):
    """Parse the WhatIfSports flattened play-by-play text into a list of half-inning dicts.

    Each dict: {half, inning, team (full name), plays: [str], score_after: {away:{team,r,h,e}, home:{...}} or None}
    """
    header_re = re.compile(
        r'-\s*(\d+)\s+\d+\s+(' + re.escape(away_name) + '|' + re.escape(home_name) + r')\s*-'
    )
    headers = list(header_re.finditer(text))
    score_re = re.compile(
        re.escape(away_name) + r'\s+(\d+)\s+(\d+)\s+(\d+)\s*-\s*' + re.escape(home_name) + r'\s+(\d+)\s+(\d+)\s+(\d+)'
    )

    halves = []
    for i, m in enumerate(headers):
        inning = int(m.group(1))
        team_name = m.group(2)
        body_start = m.end()
        body_end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        body = text[body_start:body_end]

        score_m = None
        for sm in score_re.finditer(body):
            score_m = sm
        if score_m:
            plays_text = body[:score_m.start()]
            away_r, away_h, away_e, home_r, home_h, home_e = map(int, score_m.groups())
        else:
            plays_text = body
            away_r = away_h = away_e = home_r = home_h = home_e = None

        cells = [c.strip() for c in plays_text.split('|')]
        plays = []
        for c in cells:
            if not c:
                continue
            if re.fullmatch(r'-{2,}', c):
                continue
            if re.fullmatch(r'[A-Z+\-]{1,8}', c):
                continue
            plays.append(c)

        half_label = "Top" if team_name == away_name else "Bottom"
        halves.append({
            "half": half_label,
            "inning": inning,
            "team": team_name,
            "plays": plays,
            "score_after": {
                "away": {"team": away_name, "r": away_r, "h": away_h, "e": away_e},
                "home": {"team": home_name, "r": home_r, "h": home_h, "e": home_e},
            } if score_m else None
        })
    return halves
