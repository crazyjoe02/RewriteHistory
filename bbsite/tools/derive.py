"""Derive box-score stats from a WIS play-by-play markdown file and cross-check the hand-entered lines.

md format: "### Inning N - Team" headers and "- play" bullets (score lines optional; they are recomputed).

  python3 derive.py fix GNUM GID "Away PBP name" "Home PBP name"
      -> recomputes every half-inning score line in /tmp/g1886box{GNUM}/{GID}.md (R H E running totals)
  from derive import pbpcheck; pbpcheck(GNUM,GID,A,H,abat,hbat,apit,hpit)
      -> prints every batter/pitcher field that disagrees with the play-by-play
"""
import re, sys
NM = r"[A-Z]\.[A-Z][A-Za-z']+"

def clean(play):
    play = re.sub(r'^\[[A-Z+, /]*\]\s*', '', play)
    play = re.sub(r'\s*\[[A-Z+, /]*\]\s*$', '', play)
    play = re.sub(r'\s*\((?:[A-Z+]{1,8})\)\s*$', '', play)
    play = re.sub(r'^[A-Z+]{1,8}:\s+', '', play)
    play = re.sub(r'^[A-Z+]{2,8}\s+(?=[A-Z]\.)', '', play)
    return play.strip().strip('"')

def side_of(team, A, H):
    return 'a' if team == A or (A.split()[-1] in team and H.split()[-1] not in team) else 'h'

def halves(md, A, H):
    out = []
    for line in md.splitlines():
        s = line.strip()
        m = re.match(r'#+\s*Inning\s+(\d+)\s*-\s*(.+)$', s)
        if m:
            out.append({'inn': int(m.group(1)), 'side': side_of(m.group(2).strip(), A, H), 'hdr': s, 'plays': []}); continue
        if s.startswith('- ') and out:
            out[-1]['plays'].append(clean(s[2:]))
    return out

ERR = ('error', 'throw sails', 'pickoff attempt away', 'drops a foul')
NONPA = ('wild pitch', 'passed ball', 'balk', 'lets one get away', 'pickoff', "can't handle the pitch", "can't hold onto the pitch")

def new():
    return dict(ab=0, r=0, h=0, rbi=0, bb=0, so=0, d=0, t=0, hr=0, sb=0, cs=0, sh=0, sf=0, hbp=0)

def derive(md, A, H):
    bat = {'a': {}, 'h': {}}; pit = {'a': {}, 'h': {}}; cur = {'a': None, 'h': None}
    score = {'a': [0, 0, 0], 'h': [0, 0, 0]}; lines = []; unk = {'a': 0, 'h': 0}
    g = lambda s, n: bat[s].setdefault(n, new())
    for hf in halves(md, A, H):
        b = hf['side']; f = 'h' if b == 'a' else 'a'
        for p in hf['plays']:
            names = re.findall(NM, p)
            if not names: continue
            first = names[0]
            if 'enters the game to pitch' in p:
                cur[f] = first; pit[f].setdefault(first, dict(h=0, bb=0, so=0, hr=0)); continue
            if any(k in p for k in ('enters the game', 'remains in the game', 'moves to')): continue
            scorers = re.findall('(' + NM + r")(?: [a-z][a-z ,']*?)? scores", p)
            if any(k in p for k in ERR): score[f][2] += 1
            for s_ in scorers: g(b, s_)['r'] += 1
            score[b][0] += len(scorers)
            if 'returns to the plate' in p: continue
            for n_ in re.findall('(' + NM + r') is (?:caught|nailed) (?:trying to )?steal', p):
                if n_ != first: g(b, n_)['cs'] += 1
            if 'double steal is pulled off by' in p:
                for n_ in names[:2]: g(b, n_)['sb'] += 1
                continue
            if re.match(NM + r" (?:is (?:caught|nailed|out on the front end|picked off)|is caught stealing)", p):
                g(b, first)['cs'] += 1; continue
            if re.search(r'\b(steals|swipes)\b', p) and p.startswith(first):
                g(b, first)['sb'] += 1; continue
            if any(k in p for k in NONPA): continue
            pc = pit[f].setdefault(cur[f], dict(h=0, bb=0, so=0, hr=0)) if cur[f] else dict(h=0, bb=0, so=0, hr=0)
            m = re.search('(' + NM + r') reaches', p)
            if m and 'error' in p:
                g(b, m.group(1))['ab'] += 1; continue
            st = g(b, first); rb = len(scorers)
            if 'double play' in p or 'double off' in p or 'doubled off' in p:
                st['ab'] += 1
            elif re.search(r'homer|home ?run|grand slam', p):
                mm = re.search(r'(\d)-run', p); n = int(mm.group(1)) if mm else (4 if 'grand slam' in p else 1)
                extra = max(0, n - 1 - rb); unk[b] += extra
                st['ab'] += 1; st['h'] += 1; st['hr'] += 1; st['r'] += 1; st['rbi'] += rb + 1 + extra
                score[b][0] += 1 + extra; score[b][1] += 1; pc['h'] += 1; pc['hr'] += 1
            elif re.search(r'\btriple\b', p) or re.search(r'\bdoubles?\b', p) or 'single' in p or 'Texas Leaguer' in p:
                st['ab'] += 1; st['h'] += 1; st['rbi'] += rb; score[b][1] += 1; pc['h'] += 1
                if re.search(r'\btriple\b', p): st['t'] += 1
                elif re.search(r'\bdoubles?\b', p) and 'single' not in p: st['d'] += 1
            elif re.search(r'walk|ball four|free pass', p):
                st['bb'] += 1; st['rbi'] += rb; pc['bb'] += 1
            elif re.search(r'by a pitch|pitch off|drilled|plunked|hit in the', p):
                st['hbp'] += 1; st['rbi'] += rb
            elif re.search(r'strike 3|strikes out|strike three', p):
                st['ab'] += 1; st['so'] += 1; pc['so'] += 1
            elif 'sacrifice bunt' in p:
                st['sh'] += 1; st['rbi'] += rb
            elif rb and re.search(r'fl(?:ies|y)out|flies out|lines out|pops out|fouls out', p):
                st['sf'] += 1; st['rbi'] += rb
            else:
                st['ab'] += 1; st['rbi'] += rb
        lines.append((hf['hdr'], f"**Score: AWAY {score['a'][0]} {score['a'][1]} {score['a'][2]} | HOME {score['h'][0]} {score['h'][1]} {score['h'][2]}**"))
    bat['unk'] = unk
    return bat, pit, score, lines

ALIAS = {'Blue Lew Hardtack': 'B.Hardtack'}
def abbr(full):
    if full in ALIAS: return ALIAS[full]
    parts = full.split(' ', 1)
    return parts[0][0] + '.' + parts[1].replace(' ', '') if len(parts) > 1 else full

def fix(gnum, gid, A, H):
    path = f'/tmp/g1886box{gnum}/{gid}.md'
    md = open(path).read()
    _, _, score, lines = derive(md, A, H)
    out = []; hi = 0
    body = [l for l in md.splitlines() if not re.match(r'\s*\*{0,2}Score', l.strip()) and l.strip()]
    for l in body:
        if re.match(r'#+\s*Inning', l.strip()) and hi:
            out.append(lines[hi - 1][1])
        if re.match(r'#+\s*Inning', l.strip()): hi += 1
        out.append(l)
    out.append(lines[-1][1])
    open(path, 'w').write('\n'.join(out) + '\n')
    print('final', score)

def pbpcheck(gnum, gid, A, H, abat, hbat, apit, hpit):
    bat, pit, score, _ = derive(open(f'/tmp/g1886box{gnum}/{gid}.md').read(), A, H)
    bad = 0; unk = bat.pop('unk')
    for s, rows in (('a', abat), ('h', hbat)):
        seen = set()
        exc = sum(max(0, r['r'] - bat[s].get(abbr(r['player']), new())['r']) for r in rows)
        if unk[s] and exc == unk[s]: print(f'  ({s}: {unk[s]} homer-driven run(s) credited to runners as entered)')
        for r in rows:
            k = abbr(r['player']); seen.add(k); d = bat[s].get(k, new())
            for f1, f2 in (('ab', 'ab'), ('r', 'r'), ('h', 'h'), ('rbi', 'rbi'), ('bb', 'bb'), ('so', 'so'), ('2b', 'd'), ('3b', 't'), ('hr', 'hr'), ('sb', 'sb'), ('cs', 'cs')):
                if r[f1] != d[f2] and not (f1 == 'r' and unk[s] and exc == unk[s] and r[f1] > d[f2]):
                    print(f'  BAT {s} {r["player"]}: {f1} entered {r[f1]} pbp {d[f2]}'); bad += 1
        for k in bat[s]:
            if k not in seen and any(v for v in bat[s][k].values()):
                print(f'  BAT {s} {k} in pbp but not entered: {bat[s][k]}'); bad += 1
    for s, rows in (('a', apit), ('h', hpit)):
        for r in rows:
            d = pit[s].get(abbr(r['player']))
            if d is None: print(f'  PIT {s} {r["player"]} not found in pbp'); bad += 1; continue
            for f in ('h', 'bb', 'so', 'hr'):
                if r[f] != d[f]: print(f'  PIT {s} {r["player"]}: {f} entered {r[f]} pbp {d[f]}'); bad += 1
    print('PBPCHECK', 'OK' if not bad else f'{bad} diffs', 'final', score)

if __name__ == '__main__':
    if sys.argv[1] == 'fix': fix(*sys.argv[2:6])
