import openpyxl, csv, re

TEAM_MAP = {
    "boston beaneaters": "BSN",
    "chicago white stockings": "CHC",
    "detroit wolverines": "DTN",
    "new york giants": "NYG",
    "philadelphia quakers": "PHI",
    "pittsburgh alleghenys": "PIT",
    "baltimore orioles": "BLN",
    "brooklyn grays": "BRO",
    "cincinnati red stockings": "CIN",
    "louisville colonels": "LOU",
    "philadelphia athletics": "PAT",
    "st. louis browns": "STL",
    "saint louis browns": "STL",
    "phladelphia athletics": "PAT",  # typo in source
}

def normalize(name):
    return re.sub(r'\s+', ' ', name.strip().lower())

def parse_standings(xlsx_path, season, out_csv):
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    ws = wb['Sheet1']
    rows = list(ws.iter_rows(values_only=True))
    current_league = None
    out_rows = []
    for row in rows:
        if not any(row):
            continue
        first = str(row[0]).strip() if row[0] else ""
        if "National League Standings" in first:
            current_league = "NL"
            continue
        if "American Association Standings" in first:
            current_league = "AA"
            continue
        if first == "Team":
            continue  # header row
        # data row
        team_name = first
        key = normalize(team_name)
        abbr = TEAM_MAP.get(key)
        if not abbr:
            print(f"WARNING: no abbreviation match for '{team_name}'")
            continue
        wl = row[1]
        w, l = wl.replace('\xa0','').split('-')
        pct = row[2]
        gb = row[3]
        div_record = row[4]
        one_run = row[5]
        rf = row[6]
        ra = row[7]
        home = row[8]
        away = row[9]
        owner = row[10]
        out_rows.append([season, current_league, abbr, team_name, w, l, pct, gb, div_record, one_run, rf, ra, home, away, owner])
    with open(out_csv, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Season','League','TeamAbbr','TeamName','W','L','PCT','GB','DivRecord','OneRunRecord','RF','RA','Home','Away','Owner'])
        writer.writerows(out_rows)
    print(f"Wrote {len(out_rows)} rows to {out_csv}")

parse_standings('/mnt/user-data/uploads/1885_Final_Standings.xlsx', 1885, 'data/1885/standings.csv')
