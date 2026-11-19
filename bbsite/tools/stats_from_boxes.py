#!/usr/bin/env python3
"""Interim season stats built from the box scores (data/<season>/games.json + the PBP .md files),
for use while a season is in progress. Writes data/<season>/{batting,pitching,fielding}.csv in the
WIS-export column layout. Replaced by import_wis_csv.py when the real season export arrives.

Usage: python3 tools/stats_from_boxes.py 1887   (then compute_war.py, build.py)
Fielding PO/A/DP/Inn are reconstructed from the play-by-play (checked: every defensive half must
produce the right number of putouts); E and PB come from the box-score footnotes.
"""
import csv, json, os, re, sys, glob
from collections import defaultdict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import derive as D

SEASON = sys.argv[1] if len(sys.argv) > 1 else "1887"
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.exists(os.path.join(_ROOT, "data", SEASON, "batting_metrics.csv")) and "--force" not in sys.argv:
    sys.exit(f"{SEASON} already has the official WIS export (batting_metrics.csv); not overwriting. Use --force to rebuild from box scores.")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
NL = {'BSN', 'CHC', 'CLV', 'NYG', 'PHI', 'PIT'}
POSN = {'1': 'P', '2': 'C', '3': '1B', '4': '2B', '5': '3B', '6': 'SS', '7': 'LF', '8': 'CF', '9': 'RF'}
FIELD_POS = ['P', 'C', '1B', '2B', '3B', 'SS', 'LF', 'CF', 'RF']

# ---------------------------------------------------------------- names / bio
prior = {}      # display name -> stored "Last, First"
bt = {}         # display -> (B, T)
prospect = {}
for f in sorted(glob.glob(os.path.join(DATA, '*', '*.csv'))):
    if f'/{SEASON}/' in f or not re.search(r'(batting|pitching|fielding)\.csv$', f):
        continue
    for r in csv.DictReader(open(f)):
        n = r.get('Player', '')
        if ',' not in n: continue
        l, fi = [p.strip() for p in n.split(',', 1)]
        d = f'{fi} {l}'
        prior[d] = n
        b = list(bt.get(d, ('', '')))
        if r.get('B'): b[0] = r['B']
        if r.get('T'): b[1] = r['T']
        bt[d] = tuple(b)
        if r.get('Prospect'): prospect[d] = r['Prospect']
bio = {r['Player']: r for r in csv.DictReader(open(os.path.join(DATA, 'bio.csv')))}
draft = set()
for f in glob.glob(os.path.join(DATA, '*', 'draft.csv')):
    for r in csv.DictReader(open(f)):
        n = r['Player']
        draft.add(f"{n.split(',',1)[1].strip()} {n.split(',',1)[0].strip()}" if ',' in n else n)


def stored(d):
    if d in prior: return prior[d]
    parts = d.split(' ')
    return f"{parts[-1]}, {' '.join(parts[:-1])}"


def bats_throws(d):
    b, t = bt.get(d, ('', ''))
    if d in bio:
        b = b or {'Right': 'R', 'Left': 'L', 'Both': 'S'}.get(bio[d].get('Bats', ''), bio[d].get('Bats', '')[:1])
        t = t or {'Right': 'R', 'Left': 'L'}.get(bio[d].get('Throws', ''), bio[d].get('Throws', '')[:1])
    return b, t


def is_prospect(d):
    if d in prospect: return prospect[d]
    return '' if (d in bio or d in prior or d in draft) else 'Y'

# ---------------------------------------------------------------- footnote parsing
def fn_counts(text, team_rows):
    """'J.Davis 2 (2), E.McKean (1)' -> {full name: n}; 'B.Nash' -> 1."""
    out = defaultdict(int)
    if not text: return out
    amap = {D.abbr(r['player']): r['player'] for r in team_rows}
    for part in re.split(r',\s*(?![^()]*\))', text):
        part = re.sub(r'\(.*?\)', '', part).strip()
        if not part: continue
        m = re.match(r'(.+?)\s+(\d+)$', part)
        nm, n = (m.group(1), int(m.group(2))) if m else (part, 1)
        out[amap.get(nm.strip(), nm.strip())] += n
    return out

# ---------------------------------------------------------------- play-by-play defence simulation
LOC = re.compile(r"\b(?:to|down the)\s+(?:the\s+)?(?:deep\s+|shallow\s+)?(LCF|RCF|LF|CF|RF|SS|1B|2B|3B|C|pitcher|catcher|first|second|third|right|left|center)\b")
LOCMAP = {'LCF': 'CF', 'RCF': 'CF', 'pitcher': 'P', 'catcher': 'C', 'first': '1B', 'second': '2B', 'third': '3B',
          'right': 'RF', 'left': 'LF', 'center': 'CF'}
KVERB = ('strikes out', 'strike 3', 'frozen on strike')
SKIP = ('enters the game', 'moves to')
HITW = ('single', 'double', 'triple', 'homer')


def loc(t):
    m = LOC.search(t)
    if not m: return None
    return LOCMAP.get(m.group(1), m.group(1))


def credits(t):
    """Return (list of (pos,'PO'|'A')), is_dp) for one play line, from the fielding side's view."""
    c = []
    dp = False
    m = re.search(r'(\d)-(\d)(?:-(\d))?\s+(?:double play|fielder)', t)
    if m:
        seq = [POSN[x] for x in m.groups() if x]
        for i, p in enumerate(seq):
            if i < len(seq) - 1: c.append((p, 'A'))
            if i >= 1: c.append((p, 'PO'))
        return c, 'double play' in t
    if any(k in t for k in KVERB): return [('C', 'PO')], False
    if re.search(r'caught (?:stealing|trying to steal)|nailed stealing|is caught|picked off', t):
        base = re.search(r'(2B|3B|second|third|home)', t)
        b = base.group(1) if base else '2B'
        return [('C', 'A'), ({'2B': 'SS', 'second': 'SS', '3B': '3B', 'third': '3B'}.get(b, 'C'), 'PO')], False
    if 'reaches on' in t or 'error' in t.split('.')[0] or 'can\'t hold onto the pitch' in t:
        return [], False
    if 'grounds out' in t or 'sacrifice bunt' in t:
        p = loc(t) or 'SS'
        return ([('1B', 'PO')] if p == '1B' else [(p, 'A'), ('1B', 'PO')]), False
    if 'steps on the bag for the force' in t:
        return [(loc(t) or '3B', 'PO')], False
    if 'throws to second for the force' in t:
        return [(loc(t) or 'P', 'A'), ('SS', 'PO')], False
    if 'They get the force at 2B' in t:
        p = loc(t) or 'SS'
        return [(p, 'A'), ('2B' if p in ('SS', '3B', 'P', 'C') else 'SS', 'PO')], False
    if re.search(r'\b(flies|pops|lines|fouls) out|flyout|lines out', t):
        p = loc(t.split('.')[0]) or 'CF'
        return [(p, 'PO')], False
    return [], False


def is_pa(t):
    if any(s in t for s in SKIP): return False
    if re.search(r'steals|swipes|steal |passed ball|caught stealing|nailed stealing|caught trying|picked off', t): return False
    return True


def simulate(g, md):
    A, H = g['linescore']['rows'][0]['label'], g['linescore']['rows'][1]['label']
    side_abbr = {'a': g['away'], 'h': g['home']}
    rows = {s: g['batting'][side_abbr[s]]['rows'] for s in 'ah'}
    amap = {s: {D.abbr(r['player']): r['player'] for r in rows[s]} for s in 'ah'}
    entered = set()
    for line in md.splitlines():
        m = re.match(r'-\s+(\S+)\s+enters the game', line.strip())
        if m: entered.add(m.group(1))
    pos = {}
    for s in 'ah':
        pos[s] = {}
        for r in rows[s]:
            k = D.abbr(r['player'])
            if k in entered: continue
            p = r['pos'].split('-')[0]
            if p in FIELD_POS: pos[s][p] = r['player']
    pit_rows = {s: g['pitching'][side_abbr[s]]['rows'] for s in 'ah'}
    for s in 'ah':
        pos[s]['P'] = pit_rows[s][0]['player']
    fld = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))   # side -> player -> pos -> stat
    pstat = defaultdict(lambda: defaultdict(float))                      # pitcher -> stat
    gp = defaultdict(set)
    for s in 'ah':
        for p, n in pos[s].items():
            gp[(s, n)].add(p); fld[s][n][p + '_GS'] = 1
    ph = {s: {} for s in 'ah'}
    half_outs = []
    cur_def = None
    first_play = False
    for line in md.splitlines():
        line = line.strip()
        m = re.match(r'#+\s*Inning\s+(\d+)\s*-\s*(.+)$', line)
        if m:
            bat = D.side_of(m.group(2).strip(), A, H)
            cur_def = 'h' if bat == 'a' else 'a'
            half_outs.append([cur_def, 0]); first_play = True
            continue
        if not line.startswith('- '): continue
        t = D.clean(line[2:])
        who = t.split(' ')[0]
        side = 'a' if who in amap['a'] else ('h' if who in amap['h'] else None)
        mm = re.match(r'(\S+) enters the game (?:at (\w+)|to pitch|as a pinch-(?:hitter|runner) for (\S+?)\.?$)', t)
        if mm and side:
            name = amap[side][who]
            if 'to pitch' in t: p = 'P'
            elif mm.group(2): p = mm.group(2)
            else:
                ph[side][amap[side].get(mm.group(3).rstrip('.'), mm.group(3))] = name
                continue
            if p in FIELD_POS:
                pos[side][p] = name; gp[(side, name)].add(p)
            continue
        mm = re.match(r'(\S+) moves to (\w+)', t)
        if mm and side:
            name = amap[side][who]; p = mm.group(2)
            for q, n in list(pos[side].items()):
                if n == name: del pos[side][q]
            pos[side][p] = name; gp[(side, name)].add(p)
            continue
        if cur_def is None: continue
        d = cur_def
        if first_play:
            # a pinch-hitter/runner still in the game takes over the position of the man he replaced
            for p, n in list(pos[d].items()):
                if n in ph[d] and ph[d][n] not in pos[d].values():
                    pos[d][p] = ph[d][n]; gp[(d, ph[d][n])].add(p)
            ph[d] = {}
            first_play = False
        pitcher = pos[d]['P']
        c, dp = credits(t)
        outs = 0
        for p, kind in c:
            n = pos[d].get(p)
            if n is None: continue
            fld[d][n][p + '_' + kind] += 1
            if kind == 'PO': outs += 1
        if dp:
            for n in set(pos[d].get(p) for p, _ in c):
                if n: fld[d][n][[p for p, _ in c if pos[d].get(p) == n][0] + '_DP'] += 1
        for p, n in pos[d].items():
            fld[d][n][p + '_outs'] += outs
        half_outs[-1][1] += outs
        if re.search(r'steals|swipes|steal ', t) and 'caught' not in t and 'nailed' not in t:
            fld[d][pos[d]['C']]['C_SB'] += 1
        if re.search(r'caught stealing|caught trying|nailed stealing', t):
            fld[d][pos[d]['C']]['C_CS'] += 1
        if is_pa(t) and (who in amap['a'] or who in amap['h']) and side != d:
            ps = pstat[pitcher]
            ps['BFP'] += 1
            if re.search(r'ball four|walk|free pass|draws the walk|intentionally walked', t): ps['BB'] += 1
            elif re.search(r'drilled|plunked|pitch off|hit by', t): ps['HBP'] += 1
            elif 'sacrifice bunt' in t: ps['SH'] += 1
            else:
                ps['AB'] += 1
                if 'homer' in t: ps['TB'] += 4
                elif 'triple' in t: ps['TB'] += 3
                elif 'double' in t and 'double play' not in t: ps['TB'] += 2
                elif 'single' in t: ps['TB'] += 1
            if 'intentionally walked' in t: ps['IBB'] += 1
    return fld, gp, pstat, half_outs

# ---------------------------------------------------------------- aggregate
games = json.load(open(os.path.join(DATA, SEASON, 'games.json')))
B = defaultdict(lambda: defaultdict(float))
P = defaultdict(lambda: defaultdict(float))
F = defaultdict(lambda: defaultdict(float))
problems = []
for g in games:
    md = None
    for p_ in (os.path.join(DATA, SEASON, 'pbp', f"{g.get('gid')}.md"), f"/tmp/g{SEASON}box{g['game_num']}/{g.get('gid')}.md"):
        if os.path.exists(p_): md = open(p_).read(); break
    if md is None:
        problems.append(f"no PBP md for {g['game_num']} {g['away']}@{g['home']}"); continue
    fld, gp, pstat, half_outs = simulate(g, md)
    side_abbr = {'a': g['away'], 'h': g['home']}
    # expected putouts per defensive half: outs recorded by that team's pitchers
    for s in 'ah':
        team = side_abbr[s]
        exp = sum(int(r['ip'].split('.')[0]) * 3 + int(r['ip'].split('.')[1]) for r in g['pitching'][team]['rows'])
        got = sum(o for d, o in half_outs if d == s)
        if exp != got:
            problems.append(f"g{g['game_num']} {team}: putouts {got} vs outs {exp}")
        for i, (d, o) in enumerate(half_outs):
            if d == s and o > 3: problems.append(f"g{g['game_num']} {team} half {i}: {o} putouts")
    for s in 'ah':
        team = side_abbr[s]; lg = 'NL' if team in NL else 'AA'
        bt_ = g['batting'][team]
        rows = bt_['rows']; fnt = bt_['footnotes']
        extra = {k: fn_counts(fnt.get(k), rows) for k in ('HBP', 'SF', 'SH', 'IBB', '2-Out RBI', 'E', 'PB')}
        for r in rows:
            n = r['player']; k = (n, team)
            b = B[k]; b['Lg'] = lg
            b['G'] += 1
            if r['pos'] not in ('PH', 'PR') and not any(n in x for x in [set()]):
                pass
            for c, src in (('AB', 'ab'), ('R', 'r'), ('H', 'h'), ('2B', '2b'), ('3B', '3b'), ('HR', 'hr'), ('RBI', 'rbi'),
                           ('BB', 'bb'), ('SO', 'so'), ('SB', 'sb'), ('CS', 'cs')):
                b[c] += r[src]
            b['HBP'] += extra['HBP'].get(n, 0); b['SF'] += extra['SF'].get(n, 0); b['SH'] += extra['SH'].get(n, 0)
            b['IBB'] += extra['IBB'].get(n, 0); b['RBI2O'] += extra['2-Out RBI'].get(n, 0)
            b['GS'] += 1 if any(fld[s][n].get(p + '_GS') for p in FIELD_POS) else 0
            if r['pos'] == 'PH': b['PHAB'] += r['ab']; b['PHH'] += r['h']
        md_lines = [D.clean(l.strip()[2:]) for l in md.splitlines() if l.strip().startswith('- ')]
        for r in rows:
            ab = D.abbr(r['player'])
            B[(r['player'], team)]['GIDP'] += sum(1 for t in md_lines if t.startswith(ab + ' ') and 'into a' in t and 'double play' in t)
        # fielding
        for n, st in fld[s].items():
            for p in FIELD_POS:
                if (s, n) not in gp or p not in gp[(s, n)]: continue
                fr = F[(n, team, p)]; fr['Lg'] = lg
                fr['GP'] += 1; fr['GS'] += st.get(p + '_GS', 0)
                fr['outs'] += st.get(p + '_outs', 0)
                fr['PO'] += st.get(p + '_PO', 0); fr['A'] += st.get(p + '_A', 0); fr['DP'] += st.get(p + '_DP', 0)
                if p == 'C':
                    fr['SB'] += st.get('C_SB', 0); fr['CS'] += st.get('C_CS', 0)
        for n, e in extra['E'].items():
            ps_ = [p for p in FIELD_POS if (s, n) in gp and p in gp[(s, n)]]
            if not ps_: problems.append(f"g{g['game_num']} E for {n}: no position"); continue
            F[(n, team, ps_[0])]['E'] += e
        for n, e in extra['PB'].items():
            if (n, team, 'C') in F: F[(n, team, 'C')]['PB'] += e
        # pitching
        prs = g['pitching'][team]['rows']
        opp_runs = g['linescore']['rows'][0 if s == 'h' else 1]['R']
        for i, r in enumerate(prs):
            n = r['player']; p = P[(n, team)]; p['Lg'] = lg
            p['G'] += 1
            outs = int(r['ip'].split('.')[0]) * 3 + int(r['ip'].split('.')[1])
            p['outs'] += outs
            for c, src in (('H', 'h'), ('R', 'r'), ('ER', 'er'), ('HR', 'hr'), ('BB', 'bb'), ('SO', 'so')):
                p[c] += r[src]
            if i == 0:
                p['GS'] += 1
                if len(prs) == 1:
                    p['CG'] += 1
                    if r['r'] == 0: p['SHO'] += 1
                if outs >= 18 and r['er'] <= 3: p['QS'] += 1
            dec = r['decision'] or ''
            if dec.startswith('W'): p['W'] += 1
            if dec.startswith('L'): p['L'] += 1
            if dec.startswith('SV'): p['SV'] += 1; p['SVO'] += 1
            if dec.startswith('BS'): p['SVO'] += 1
            for c in ('BFP', 'AB', 'TB', 'HBP', 'SH', 'IBB'):
                p['_' + c] += pstat[n].get(c, 0)


def fmt3(x):
    s = f"{x:.3f}"
    return s[1:] if s.startswith('0') else s


def ipstr(outs):
    return f"{int(outs) // 3}.{int(outs) % 3}"


out = os.path.join(DATA, SEASON)
bat_f = "Player,Team,Lg,SN,B,G,AB,R,H,2B,3B,HR,RBI,BB,SO,HBP,SB,CS,AVG,OBP,SLG,OPS,STRK,L STRK,Prospect,PA,IBB,SF,SH,GIDP,GS,PHAB,PHH,GB,FB,NP,IFH,BH,LOB,RBI2O,GIDPO,RC".split(',')
with open(os.path.join(out, 'batting.csv'), 'w', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=bat_f); w.writeheader()
    for (n, team), b in sorted(B.items(), key=lambda kv: stored(kv[0][0])):
        ab, h = b['AB'], b['H']; tb = h + b['2B'] + 2 * b['3B'] + 3 * b['HR']
        obd = ab + b['BB'] + b['HBP'] + b['SF']
        avg = h / ab if ab else 0; obp = (h + b['BB'] + b['HBP']) / obd if obd else 0; slg = tb / ab if ab else 0
        row = {'Player': stored(n), 'Team': team, 'Lg': b['Lg'], 'SN': SEASON, 'B': bats_throws(n)[0], 'Prospect': is_prospect(n),
               'AVG': fmt3(avg), 'OBP': fmt3(obp), 'SLG': fmt3(slg), 'OPS': fmt3(obp + slg),
               'PA': int(ab + b['BB'] + b['HBP'] + b['SF'] + b['SH']), 'STRK': '', 'L STRK': '',
               'RC': f"{(h + b['BB']) * tb / (ab + b['BB']):.1f}" if ab + b['BB'] else '0.0'}
        for c in ('G', 'AB', 'R', 'H', '2B', '3B', 'HR', 'RBI', 'BB', 'SO', 'HBP', 'SB', 'CS', 'IBB', 'SF', 'SH', 'GIDP', 'GS', 'PHAB', 'PHH', 'RBI2O'):
            row[c] = int(b[c])
        for c in ('GB', 'FB', 'NP', 'IFH', 'BH', 'LOB', 'GIDPO'):
            row[c] = 0
        w.writerow(row)

pit_f = "Player,Team,League,SN,T,G,GS,CG,SHO,W,L,SV,SVO,IP,H,R,ER,HR,BB,SO,OAV,OBP,SLG,WHIP,ERA,Prospect,QS,IBB,HBP,WP,BK,BFP".split(',')
with open(os.path.join(out, 'pitching.csv'), 'w', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=pit_f); w.writeheader()
    for (n, team), p in sorted(P.items(), key=lambda kv: stored(kv[0][0])):
        ip = p['outs'] / 3
        oab = p['_AB'] or 0; bfp = p['_BFP']
        row = {'Player': stored(n), 'Team': team, 'League': p['Lg'], 'SN': SEASON, 'T': bats_throws(n)[1], 'IP': ipstr(p['outs']),
               'OAV': fmt3(p['H'] / oab if oab else 0), 'OBP': fmt3((p['H'] + p['BB'] + p['_HBP']) / bfp if bfp else 0),
               'SLG': fmt3(p['_TB'] / oab if oab else 0),
               'WHIP': f"{(p['H'] + p['BB']) / ip:.2f}" if ip else '0.00', 'ERA': f"{9 * p['ER'] / ip:.2f}" if ip else '0.00',
               'Prospect': is_prospect(n), 'IBB': int(p['_IBB']), 'HBP': int(p['_HBP']), 'WP': 0, 'BK': 0, 'BFP': int(bfp)}
        for c in ('G', 'GS', 'CG', 'SHO', 'W', 'L', 'SV', 'SVO', 'H', 'R', 'ER', 'HR', 'BB', 'SO', 'QS'):
            row[c] = int(p[c])
        w.writerow(row)

fld_f = "Player,Team,Lg,SN,Pos,GP,GS,Inn,E,PO,A,DP,GoodPlays,PoorPlays,FPct,RF,SB,CS,CERA,PB,PK,Prospect,EThrow".split(',')
# catcher ERA: earned runs allowed by the team while he caught isn't tracked per out; use team ER rate for the games caught
with open(os.path.join(out, 'fielding.csv'), 'w', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=fld_f); w.writeheader()
    for (n, team, pos), fr in sorted(F.items(), key=lambda kv: (stored(kv[0][0]), FIELD_POS.index(kv[0][2]))):
        inn = fr['outs'] / 3
        ch = fr['PO'] + fr['A'] + fr['E']
        row = {'Player': stored(n), 'Team': team, 'Lg': fr['Lg'], 'SN': SEASON, 'Pos': pos, 'GP': int(fr['GP']), 'GS': int(fr['GS']),
               'Inn': ipstr(fr['outs']), 'E': int(fr['E']), 'PO': int(fr['PO']), 'A': int(fr['A']), 'DP': int(fr['DP']),
               'GoodPlays': 0, 'PoorPlays': 0, 'FPct': fmt3((fr['PO'] + fr['A']) / ch) if ch else '.000',
               'RF': f"{9 * (fr['PO'] + fr['A']) / inn:.2f}" if inn else '0.00',
               'SB': int(fr['SB']), 'CS': int(fr['CS']), 'CERA': '0.00', 'PB': int(fr['PB']), 'PK': 0,
               'Prospect': is_prospect(n), 'EThrow': 0}
        w.writerow(row)

print(f"{SEASON}: {len(B)} batting, {len(P)} pitching, {len(F)} fielding rows from {len(games)} games")
for p in problems: print('  !!', p)
