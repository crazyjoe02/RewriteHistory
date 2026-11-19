"""Season-generic box-score builder (1887+).
spec: dict with keys
  season, gnum, date (ISO), gid, away, home (abbr), alabel, hlabel (display names, also used as PBP headers in the .md),
  loc, pog {player,team,note}, line {'a':[...], 'h':[...]} (None for an unplayed bottom half), rhe {'a':[R,H,E],'h':[...]},
  abat/hbat: list of "Name|Pos|AB R H RBI BB SO" strings (table order),
  apit/hpit: list of "Name|Dec|IP H R ER BB SO HR ERA" strings,
  afn/hfn: footnote dicts (WIS text, season totals in parentheses)
md lives at /tmp/g{season}box{gnum}/{gid}.md
"""
import json, re, sys, datetime
sys.path.insert(0, '/home/claude/bbsite/tools')
import derive as D
from extract_pbp import parse_playbyplay

def _bat(rows, dv):
    out = []
    for s in rows:
        n, pos, nums = s.split('|')
        ab, r, h, rbi, bb, so = map(int, nums.split())
        d = dv.get(D.abbr(n), D.new())
        out.append({"player": n, "pos": pos, "ab": ab, "r": r, "h": h, "rbi": rbi, "bb": bb, "so": so,
                    "2b": d['d'], "3b": d['t'], "hr": d['hr'], "sb": d['sb'], "cs": d['cs']})
    return out

def _pit(rows):
    out = []
    for s in rows:
        n, dec, nums = s.split('|')
        ip, h, r, er, bb, so, hr, era = nums.split()
        out.append({"player": n, "decision": dec, "ip": ip, "h": int(h), "r": int(r), "er": int(er), "bb": int(bb),
                    "so": int(so), "hr": int(hr), "era": era})
    return out

def tot(rows):
    return {k: sum(r[k] for r in rows) for k in ["ab", "r", "h", "rbi", "bb", "so", "2b", "3b", "hr", "sb", "cs"]}

def ptot(rows):
    outs = sum(int(r["ip"].split('.')[0]) * 3 + int(r["ip"].split('.')[1]) for r in rows)
    d = {k: sum(r[k] for r in rows) for k in ["h", "r", "er", "bb", "so", "hr"]}
    d["ip"] = f"{outs // 3}.{outs % 3}"
    return d

def raw_from_md(md, A, H):
    """md (### Inning N - Team / - play) -> raw text for parse_playbyplay, with recomputed score lines."""
    _, _, _, lines = D.derive(md, A, H)
    out = []; hi = 0
    for line in md.splitlines():
        s = line.strip()
        m = re.match(r'#+\s*Inning\s+(\d+)\s*-\s*(.+)$', s)
        if m:
            if hi:
                a = re.findall(r'\d+', lines[hi - 1][1])
                out.append(f' - {A} {a[0]} {a[1]} {a[2]} - {H} {a[3]} {a[4]} {a[5]} ')
            hi += 1
            team = A if D.side_of(m.group(2).strip(), A, H) == 'a' else H
            out.append(f' - {m.group(1)}    {m.group(1)}    {team} - |'); continue
        if s.startswith('- '):
            out.append(f' | {D.clean(s[2:])} |')
    a = re.findall(r'\d+', lines[-1][1])
    out.append(f' - {A} {a[0]} {a[1]} {a[2]} - {H} {a[3]} {a[4]} {a[5]} ')
    return ''.join(out)

def build(sp, write=True):
    season = sp['season']; A, H = sp['alabel'], sp['hlabel']
    import os, shutil
    src = f"/tmp/g{season}box{sp['gnum']}/{sp['gid']}.md"
    keep = f"/home/claude/bbsite/data/{season}/pbp/{sp['gid']}.md"
    os.makedirs(os.path.dirname(keep), exist_ok=True)
    if os.path.exists(src): shutil.copy(src, keep)
    md = open(keep).read()
    bat, pit, score, _ = D.derive(md, A, H)
    abat, hbat = _bat(sp['abat'], bat['a']), _bat(sp['hbat'], bat['h'])
    apit, hpit = _pit(sp['apit']), _pit(sp['hpit'])
    # cross-check table vs play-by-play
    bad = 0; unk = bat['unk']
    for s, rows in (('a', abat), ('h', hbat)):
        seen = set()
        for r in rows:
            k = D.abbr(r['player']); seen.add(k); d = bat[s].get(k, D.new())
            for f1, f2 in (('ab', 'ab'), ('r', 'r'), ('h', 'h'), ('rbi', 'rbi'), ('bb', 'bb'), ('so', 'so')):
                if r[f1] != d[f2]:
                    print(f'  BAT {s} {r["player"]}: {f1} table {r[f1]} pbp {d[f2]}'); bad += 1
        for k in bat[s]:
            if k not in seen and any(v for v in bat[s][k].values()):
                print(f'  BAT {s} {k} in pbp but not in table: {bat[s][k]}'); bad += 1
    for s, rows in (('a', apit), ('h', hpit)):
        for r in rows:
            d = pit[s].get(D.abbr(r['player']))
            if d is None: print(f'  PIT {s} {r["player"]} not in pbp'); bad += 1; continue
            for f in ('h', 'bb', 'so', 'hr'):
                if r[f] != d[f]: print(f'  PIT {s} {r["player"]}: {f} table {r[f]} pbp {d[f]}'); bad += 1
    ta, th = tot(abat), tot(hbat)
    ra, rh = sp['rhe']['a'], sp['rhe']['h']
    chk = [(ta['r'], ta['h']) == tuple(ra[:2]), (th['r'], th['h']) == tuple(rh[:2]),
           sum(x or 0 for x in sp['line']['a']) == ra[0], sum(x or 0 for x in sp['line']['h']) == rh[0],
           score['a'] == ra, score['h'] == rh]
    print(sp['away'], '@', sp['home'], 'pbp score', score, 'diffs', bad, 'checks', 'OK' if all(chk) else f'!!! {chk}')
    if not write: return
    text = raw_from_md(md, A, H)
    pbp = parse_playbyplay(text, A, H)
    m = {A: sp['away'], H: sp['home']}
    for h in pbp:
        h['team'] = m[h['team']]; h['score_after']['away']['team'] = sp['away']; h['score_after']['home']['team'] = sp['home']
    dt = datetime.date.fromisoformat(sp['date'])
    sub = sp.get('subtitle') or f"Regular Season — {dt.strftime('%B')} {dt.day}, {dt.year}"
    inn = max(len(sp['line']['a']), len(sp['line']['h']))
    g = {"season": season, "game_num": sp['gnum'], "gid": sp['gid'], "date": sp['date'], "home": sp['home'], "away": sp['away'],
         "location": sp['loc'], "subtitle": sub, "player_of_game": sp['pog'],
         "linescore": {"innings": list(range(1, inn + 1)), "rows": [
             {"team": sp['away'], "label": A, "by_inning": sp['line']['a'], "R": ra[0], "H": ra[1], "E": ra[2]},
             {"team": sp['home'], "label": H, "by_inning": sp['line']['h'], "R": rh[0], "H": rh[1], "E": rh[2]}]},
         "batting": {sp['away']: {"rows": abat, "totals": ta, "footnotes": sp['afn']},
                     sp['home']: {"rows": hbat, "totals": th, "footnotes": sp['hfn']}},
         "pitching": {sp['away']: {"rows": apit, "totals": ptot(apit)}, sp['home']: {"rows": hpit, "totals": ptot(hpit)}},
         "playbyplay": pbp}
    path = f'/home/claude/bbsite/data/{season}/games.json'
    try: games = json.load(open(path))
    except FileNotFoundError: games = []
    games = [x for x in games if not (x['game_num'] == g['game_num'] and x['away'] == g['away'] and x['home'] == g['home'])]
    games.append(g)
    games.sort(key=lambda x: (x['game_num'], x['home']))
    json.dump(games, open(path, 'w'), indent=1)
    print('  written; games in file:', len(games))
