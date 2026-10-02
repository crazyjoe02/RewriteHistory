# 1886 Season

Data files (standings.csv, batting.csv, pitching.csv, etc.) will be added here
once the season is underway. Until then, build.py lists the active franchises
alphabetically by league with no won-loss record.

## Season stats & player pages (from the WhatIfSports CSV exports)
1. Upload the CSVs, then run: `python3 import_wis_csv.py && python3 compute_war.py && python3 build.py`
   - writes batting/pitching/fielding.csv plus batting_splits, batting_metrics, pitching_splits, pitching_metrics
   - compute_war.py also stores the Value Batting components (Rbat, Rbaser, Rfield, Rpos, RAA, WAA, Rrep, RAR, oWAR, dWAR)
2. Biographical data lives in data/bio.csv (built once by build_bio.py from the Chadwick/Lahman People register).
   Re-run build_bio.py only when new real players join the league; add any name mismatches to its OVERRIDES.
3. Player pages are assembled by player_extras.py (standard/value/advanced batting, splits, appearances,
   fielding league averages, leaderboards) and rendered with templates/player.html.
