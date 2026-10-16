# intfar

Stat commands use all recorded games by default. Append `year` to use the current
calendar year, or a specific year such as `2025`:

```text
!average kda
!average kda year
!average kda Player Name 2025
!best kills all year
!intfar all 2025
!summary 2025
```

The year option goes last, after any game, champion/map, role, or player. It works
with `average`/`avg`, `best`/`most`/`highest`, `worst`/`least`/`lowest`/`fewest`,
`champion`/`champ`, `wr`/`winrate`, `summary`, `performance`/`penis`, `intfar`,
`doinks`, `intfar_relations`, `doinks_relations`, `match_history`, `rank`, and
`status`. `all` continues to select all players where supported. Calendar years
use Europe/Copenhagen time; historical ranks show the latest recorded rank in
the selected year. LAN commands keep their event-specific time range.

Year-stat regression tests run without private bot resources:

```sh
uv run pytest --confcutdir=tests/unit tests/unit
```
