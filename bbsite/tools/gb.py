import json, sys
sys.path.insert(0, '/home/claude')
from extract_pbp import parse_playbyplay
def P(name,pos,ab,r,h,rbi,bb,so,d=0,t=0,hr=0,sb=0,cs=0):
    return {"player":name,"pos":pos,"ab":ab,"r":r,"h":h,"rbi":rbi,"bb":bb,"so":so,"2b":d,"3b":t,"hr":hr,"sb":sb,"cs":cs}
def Pi(n,dec,ip,h,r,er,bb,so,hr,era):
    return {"player":n,"decision":dec,"ip":ip,"h":h,"r":r,"er":er,"bb":bb,"so":so,"hr":hr,"era":era}
def tot(rows):
    return {k:sum(r[k] for r in rows) for k in ["ab","r","h","rbi","bb","so","2b","3b","hr","sb","cs"]}
def ptot(rows):
    outs=sum(round(float(r["ip"])*3) if False else int(r["ip"].split('.')[0])*3+int(r["ip"].split('.')[1]) for r in rows)
    d={k:sum(r[k] for r in rows) for k in ["h","r","er","bb","so","hr"]}; d["ip"]=f"{outs//3}.{outs%3}"; return d
def build(gid,gnum,date,away,home,away_pbp,home_pbp,away_lbl,home_lbl,loc,sub,pog,inn,aline,hline,aRHE,hRHE,abat,hbat,afn,hfn,apit,hpit):
    with open('/home/claude/bbsite/data/1886/games.json') as f: games=json.load(f)
    text=open(f'/tmp/g1886box{gnum}/{gid}.txt').read()
    pbp=parse_playbyplay(text,away_pbp,home_pbp)
    m={away_pbp:away,home_pbp:home}
    for h in pbp:
        h['team']=m[h['team']]; h['score_after']['away']['team']=away; h['score_after']['home']['team']=home
    g={"season":1886,"game_num":gnum,"date":date,"home":home,"away":away,"location":loc,"subtitle":sub,"player_of_game":pog,
       "linescore":{"innings":list(range(1,inn+1)),"rows":[
          {"team":away,"label":away_lbl,"by_inning":aline,"R":aRHE[0],"H":aRHE[1],"E":aRHE[2]},
          {"team":home,"label":home_lbl,"by_inning":hline,"R":hRHE[0],"H":hRHE[1],"E":hRHE[2]}]},
       "batting":{away:{"rows":abat,"totals":tot(abat),"footnotes":afn},home:{"rows":hbat,"totals":tot(hbat),"footnotes":hfn}},
       "pitching":{away:{"rows":apit,"totals":ptot(apit)},home:{"rows":hpit,"totals":ptot(hpit)}},
       "playbyplay":pbp}
    ta,th=tot(abat),tot(hbat)
    last=pbp[-1]['score_after']
    ok = (ta['r'],ta['h'])==(aRHE[0],aRHE[1]) and (th['r'],th['h'])==(hRHE[0],hRHE[1]) and last['away']['r']==aRHE[0] and last['home']['r']==hRHE[0] and sum(x or 0 for x in aline)==aRHE[0] and sum(x or 0 for x in hline)==hRHE[0]
    print(away,"tot",ta); print(home,"tot",th); print("half-inn",len(pbp),"last",last); print("CHECK OK" if ok else "!!! MISMATCH")
    # replace any existing entry for the same game instead of appending a duplicate
    games=[x for x in games if not (x['season']==g['season'] and x['game_num']==g['game_num'] and x['away']==g['away'] and x['home']==g['home'])]
    games.append(g)
    with open('/home/claude/bbsite/data/1886/games.json','w') as f: json.dump(games,f,indent=1)
    print("Total games:",len(games))
