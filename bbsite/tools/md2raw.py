"""Convert WebFetch structured play-by-play markdown into the raw text format gb.build/extract_pbp expect.
usage: python3 md2raw.py GNUM GID "Away Label" "Home Label"
reads /tmp/g1886box{GNUM}/{GID}.md, writes /tmp/g1886box{GNUM}/{GID}.txt"""
import re,sys
g,gid,A,H=sys.argv[1:5]
md=open(f'/tmp/g1886box{g}/{gid}.md').read()
out=[];cur=None
for line in md.splitlines():
    line=line.strip()
    m=re.match(r'#+\s*Inning\s+(\d+)\s*-\s*(.+)$',line)
    if m:
        n=m.group(1); t=m.group(2).strip()
        team = A if t==A or A.split()[-1] in t and H.split()[-1] not in t else H
        out.append(f' - {n}    {n}    {team} - |'); continue
    m=re.match(r'\*\*(?:Final )?Score:(.*)\|(.*)\*\*$',line)
    if m:
        a=re.findall(r'\d+',m.group(1))[-3:]+re.findall(r'\d+',m.group(2))[-3:]; out.append(f' - {A} {a[0]} {a[1]} {a[2]} - {H} {a[3]} {a[4]} {a[5]} '); continue
    if line.startswith('- '):
        play=re.sub(r'\s*\((?:[A-Z+]{1,8})\)\s*$','',line[2:].strip())
        play=re.sub(r'^\[[A-Z+, /]*\]\s*','',play)
        play=re.sub(r'\s*\[[A-Z+, /]*\]\s*$','',play)
        play=re.sub(r'^[A-Z+]{1,8}:\s+','',play)
        play=re.sub(r'^[A-Z+]{2,8}\s+(?=[A-Z]\.)','',play)
        out.append(f' | {play} |')
open(f'/tmp/g1886box{g}/{gid}.txt','w').write(''.join(out))
import sys; sys.path.insert(0,'/home/claude')
from extract_pbp import parse_playbyplay
p=parse_playbyplay(''.join(out),A,H)
print('halves',len(p),'plays',sum(len(x['plays']) for x in p),'last',p[-1]['score_after'])
