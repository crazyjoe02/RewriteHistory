import json,csv,sys
sys.path.insert(0,'/home/claude/bbsite')
known=set()
for s in ('1885','1886'):
    for g in json.load(open(f'/home/claude/bbsite/data/{s}/games.json')):
        for t in g['batting'].values(): known|={r['player'] for r in t['rows']}
        for t in g['pitching'].values(): known|={r['player'] for r in t['rows']}
def check(*lists):
    bad=[r['player'] for L in lists for r in L if r['player'] not in known]
    print('UNKNOWN NAMES:',bad if bad else 'none')
