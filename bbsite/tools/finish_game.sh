#!/bin/bash
# usage: finish_game.sh GAMENUM HOME AWAY
cd /home/claude/bbsite && python3 -c "
import csv,sys
g,h,a='$1','$2','$3'
with open('data/1886/schedule.csv') as f:
    rows=list(csv.DictReader(f)); fn=rows[0].keys()
for r in rows:
    if r['GameNum']==g and r['HomeAbbr']==h and r['AwayAbbr']==a:
        r['BoxScoreSlug']=f'{g}-{a.lower()}-{h.lower()}'
with open('data/1886/schedule.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fn); w.writeheader(); w.writerows(rows)
print('slug set')
"
python3 build.py 2>&1 | tail -2
rm -f /home/claude/baseball-sim-site.zip
cd /home/claude && zip -rq baseball-sim-site.zip bbsite
cp -f baseball-sim-site.zip /mnt/user-data/outputs/baseball-sim-site.zip
echo packaged
