#!/usr/bin/env python3
"""Import WhatIfSports season CSV exports into data/<season>/{batting,pitching,fielding}.csv.

Usage:  python3 import_wis_csv.py [UPLOAD_DIR] [SEASON]
        (defaults: /mnt/user-data/uploads, 1886)

Rules applied (standing site conventions):
  * Real-life MLB rows (Season 2025/2026 without "(Prospect)") are skipped.
  * "(Prospect)" rows are kept, flagged Prospect=Y, label stripped from the name.
  * "(AAA)" tags stripped; "Unknown Palmer" -> "Billy Palmer".
  * Raw WIS team names mapped to site codes.
  * Names stored "Last, First"; an existing spelling is reused so player IDs never change.
  * Fielding pickoffs (PK) are not in the export, so they carry forward from the old file.
After running: python3 compute_war.py && python3 build.py
"""
import csv, math, os, re, sys
import pandas as pd

UP = sys.argv[1] if len(sys.argv) > 1 else "/mnt/user-data/uploads"
SEASON = sys.argv[2] if len(sys.argv) > 2 else "1886"
DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", SEASON)

TEAM = {'1886 Cleveland Blues': 'CLV', 'Baltimore Orioles': 'BLN', 'Boston Beaneaters': 'BSN', 'Brooklyn Grays': 'BRO',
        'Chicago White Stockings': 'CHC', 'Cincinnati Red Stockings': 'CIN', 'Cincinnati Red Stocking': 'CIN',
        'Louisvill Colonels': 'LOU', 'Louisville Colonels': 'LOU', 'New York Giants': 'NYG',
        'Philadelphia Athletics': 'PAT', 'Philadelphia Quakers': 'PHI', 'Pittsburgh Alleghenys': 'PIT',
        'Saint Louis Browns': 'STL', 'St. Louis Browns': 'STL'}
NL = {'BSN', 'CHC', 'CLV', 'NYG', 'PHI', 'PIT'}


def disp(n):
    l, f = [p.strip() for p in n.split(',', 1)]
    return f"{f} {l}"


def read(name):
    return list(csv.DictReader(open(os.path.join(DATA, name)))) if os.path.exists(os.path.join(DATA, name)) else []


def write(name, rows, fn):
    with open(os.path.join(DATA, name), 'w', newline='') as fo:
        w = csv.DictWriter(fo, fieldnames=fn, extrasaction='ignore')
        w.writeheader(); w.writerows(rows)


def f3(x):
    try: x = float(str(x).rstrip('%'))
    except ValueError: return '.000'
    if math.isnan(x): return '.000'
    return f"{x:.3f}"[1:] if x < 1 else f"{x:.3f}"


def f2(x, lead=True):
    try: x = float(x)
    except ValueError: x = float('nan')
    if math.isnan(x): return '0.00' if lead else '.00'
    s = f"{x:.2f}"
    return s if lead or not s.startswith('0.') else s[1:]


old_bat, old_pit, old_fld = read('batting.csv'), read('pitching.csv'), read('fielding.csv')
KNOWN = {disp(r['Player']): r['Player'] for r in old_bat + old_pit + old_fld}


def clean(raw, season):
    raw = re.sub(r'\s+', ' ', str(raw)).strip()
    prospect = '(Prospect)' in raw
    name = re.sub(r'\s*\(AAA\)', '', raw.replace('(Prospect)', '')).strip().replace('Unknown Palmer', 'Billy Palmer')
    keep = prospect or str(season).split('.')[0] == SEASON
    if name in KNOWN: stored = KNOWN[name]
    else:
        first, last = name.rsplit(' ', 1); stored = f"{last}, {first}"
    return keep, prospect, stored


report = {}

# ---------------- batting ----------------
src = pd.read_csv(os.path.join(UP, 'MLB145742_BattingRegSeason.csv'))
out = []
for _, r in src.iterrows():
    keep, pro, name = clean(r['Player'], r['Season'])
    if not keep: continue
    t = TEAM[r['Team']]; I = lambda k: int(r[k])
    out.append({'Player': name, 'Team': t, 'Lg': 'NL' if t in NL else 'AA', 'SN': SEASON, 'B': r['Bats'],
                'G': I('G'), 'AB': I('AB'), 'R': I('R'), 'H': I('H'), '2B': I('Doubles'), '3B': I('Triples'), 'HR': I('HR'),
                'RBI': I('RBI'), 'BB': I('BB'), 'SO': I('SO'), 'HBP': I('HBP'), 'SB': I('SB'), 'CS': I('CS'),
                'AVG': f3(r['BA']), 'OBP': f3(r['OBP']), 'SLG': f3(r['SLG']), 'OPS': f3(r['OPS']),
                'STRK': '', 'L STRK': '', 'WAR': '', 'Prospect': 'Y' if pro else '',
                'PA': I('PA'), 'IBB': I('IBB'), 'SF': I('SF'), 'SH': I('SH'), 'GIDP': I('GIDP')})
fn = ['Player', 'Team', 'Lg', 'SN', 'B', 'G', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'BB', 'SO', 'HBP', 'SB', 'CS',
      'AVG', 'OBP', 'SLG', 'OPS', 'STRK', 'L STRK', 'WAR', 'Prospect', 'PA', 'IBB', 'SF', 'SH', 'GIDP']
report['batting'] = (len(old_bat), len(out), sorted({(r['Player'], r['Team']) for r in old_bat} - {(r['Player'], r['Team']) for r in out}))
write('batting.csv', out, fn)

# ---------------- pitching ----------------
src = pd.read_csv(os.path.join(UP, 'MLB145742_PitchingRegSeason.csv'))
out = []
for _, r in src.iterrows():
    keep, pro, name = clean(r['Player'], r['Season'])
    if not keep: continue
    t = TEAM[r['Team']]; I = lambda k: int(r[k])
    out.append({'Player': name, 'Team': t, 'League': 'NL' if t in NL else 'AA', 'SN': SEASON, 'T': r['Throws'],
                'G': I('G'), 'GS': I('GS'), 'CG': I('CG'), 'SHO': I('SHO'), 'W': I('W'), 'L': I('L'), 'SV': I('SV'),
                'SVO': I('SVO'), 'IP': f"{float(r['IP']):.1f}", 'H': I('H'), 'R': I('R'), 'ER': I('ER'), 'HR': I('HR'),
                'BB': I('BB'), 'SO': I('SO'), 'OAV': f3(r['OAV']), 'OBP': f3(r['OBP']), 'SLG': f3(r['SLG']),
                'WHIP': f2(r['WHIP']), 'ERA': f2(r['ERA']), 'WAR': '', 'Prospect': 'Y' if pro else '',
                'QS': I('QS'), 'IBB': I('IBB'), 'HBP': I('HBP'), 'WP': I('WP'), 'BK': I('BK'), 'BFP': I('BFP')})
fn = ['Player', 'Team', 'League', 'SN', 'T', 'G', 'GS', 'CG', 'SHO', 'W', 'L', 'SV', 'SVO', 'IP', 'H', 'R', 'ER', 'HR',
      'BB', 'SO', 'OAV', 'OBP', 'SLG', 'WHIP', 'ERA', 'WAR', 'Prospect', 'QS', 'IBB', 'HBP', 'WP', 'BK', 'BFP']
report['pitching'] = (len(old_pit), len(out), sorted({(r['Player'], r['Team']) for r in old_pit} - {(r['Player'], r['Team']) for r in out}))
write('pitching.csv', out, fn)

# ---------------- fielding ----------------
src = pd.read_csv(os.path.join(UP, 'MLB145742_FieldingRegSeason.csv'))
pk = {(r['Player'], r['Team'], r['Pos']): r.get('PK', '0') for r in old_fld}
out = []
for _, r in src.iterrows():
    keep, pro, name = clean(r['Player'], r['Season'])
    if not keep: continue
    t = TEAM[r['Team']]; pos = r['Position']; I = lambda k: int(r[k])
    out.append({'Player': name, 'Team': t, 'Lg': 'NL' if t in NL else 'AA', 'SN': SEASON, 'Pos': pos,
                'GP': I('GP'), 'GS': I('GS'), 'Inn': f"{float(r['Innings']):.1f}", 'E': I('E'), 'PO': I('PO'), 'A': I('A'),
                'DP': I('DP'), 'GoodPlays': I('Plus Play'), 'PoorPlays': I('Minus Play'), 'FPct': f3(float(str(r['FPct']).rstrip('%') or 'nan') / 100 if str(r['FPct']) not in ('nan', '') else 'nan'),
                'RF': f2(r['RF'], lead=False), 'SB': I('SB'), 'CS': I('CS'), 'CERA': f2(r['C_ERA']), 'PB': I('PB'),
                'PK': pk.get((name, t, pos), '0'), 'Prospect': 'Y' if pro else '', 'EThrow': I('E Throwing')})
fn = ['Player', 'Team', 'Lg', 'SN', 'Pos', 'GP', 'GS', 'Inn', 'E', 'PO', 'A', 'DP', 'GoodPlays', 'PoorPlays', 'FPct', 'RF',
      'SB', 'CS', 'CERA', 'PB', 'PK', 'Prospect', 'EThrow']
report['fielding'] = (len(old_fld), len(out), sorted({(r['Player'], r['Team'], r['Pos']) for r in old_fld} - {(r['Player'], r['Team'], r['Pos']) for r in out}))
write('fielding.csv', out, fn)

for k, (was, now, dropped) in report.items():
    print(f"{k:9} rows {was} -> {now}   dropped: {dropped if dropped else 'none'}")
