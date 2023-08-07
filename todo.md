# Plan for multi-game Int-Far (tilføjelse af CSGO)

## Ændringer i databasen
- Tilføj navn på spil til `games`: ✅
- Lav en `users` tabel med basic user info: ✅
- Lav en `users_lol` og en `users_csgo` tabel: ❌
- Del `participants` op i LoL og CS: ❌

## Ændringer i commands
- Tilføj game som en parameter til mange commands

## Ændringer i database.py
- Find alle referencer til 

## CSGO register page
- Lav routing/db logic
- Lav HTML
- Lav CSS

## Fix referencer
### Til database.py
- `user_exists`: ❌
- `add_user`: ❌
- `remove_user`: ❌
- `discord_id_from_summoner_name` (hedder nu `discord_id_from_ingame_name`): ❌
- `summoner_from_discord_id` (hedder nu `game_user_data_from_discord_id`): ❌
- `game_exists`: ❌
- `delete_game`: ❌
- `get_most_extreme_stat`: ❌
- `get_best_or_worst_stat`: ❌
- `get_doinks_count`: ❌
- `get_max_doinks_details`: ❌
- `get_doinks_reason_counts`: ❌
- `get_game_ids`: ❌