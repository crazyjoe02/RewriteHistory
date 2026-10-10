Box-score helper scripts (copies). After a container reset, restore with:
    cp /home/claude/bbsite/tools/{gb.py,extract_pbp.py,finish_game.sh} /home/claude/ && chmod +x /home/claude/finish_game.sh
gb.build(...) needs the play-by-play text saved at /tmp/g1886box{GAME}/{GID}.txt.
Pass the team names exactly as the play-by-play spells them (e.g. "Louisvill Colonels", "Saint Louis Browns").
finish_game.sh GAMENUM HOME AWAY sets the schedule slug, rebuilds, and repackages the zip.

WebFetch now returns a structured extract instead of raw page text. Save the play-by-play as
/tmp/g1886box{GAME}/{GID}.md ("### Inning N - Team", "- play" lines, "**Score: Away R H E | Home R H E**"),
then run: python3 md2raw.py GAME GID "Away Label" "Home Label"  -> writes the .txt that gb.build reads.
The extract's batting tables are unreliable (wrong R/H/2B); always re-derive batter lines from the play-by-play.
namecheck.check(rows...) flags player names not seen in any earlier box score.

derive.py (added at Game 86): derives every batter/pitcher line from the play-by-play.
  python3 derive.py fix GAME GID "Away PBP name" "Home PBP name"   -> recomputes the half-inning score lines in the .md
  from derive import pbpcheck; pbpcheck(GAME,GID,A,H,abat,hbat,apit,hpit)  -> lists any entered field that disagrees
Known WIS quirks it will flag (accept WIS): an RBI credited on an error play; a groundout occasionally scored as SF.
Runs scored ahead of an N-run homer are not named in the text, so R for those runners is taken as entered.
