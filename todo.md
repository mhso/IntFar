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

## Ændringer i stats for spil
game_stats.py fil/klasse til hver spil?

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
- `get_recent_intfars_and_doinks`: ❌
- `get_games_results`: ❌
- `get_games_count`: ❌
- `get_longest_game`: ❌
- `get_intfar_count`: ❌
- `get_intfar_reason_counts`: ❌
- `get_total_winrate`: ❌
- `get_winrate_relation`: ❌
- `get_meta_stats`: ❌
- `get_intfars_of_the_month`: ❌
- `get_longest_intfar_streak`: ❌
- `get_longest_no_intfar_streak`: ❌
- `get_current_intfar_streak`: ❌
- `get_longest_win_or_loss_streak`: ❌
- `get_current_win_or_loss_streak`: ❌
- `get_max_intfar_details`: ❌
- `get_intfar_stats`: ❌
- `get_intfar_relations`: ❌
- `get_doinks_stats`: ❌
- `get_doinks_relations`: ❌
- `get_performance_score`: ❌
- `save_missed_game`: ❌
- `get_missed_games`: ❌
- `remove_missed_game`: ❌
- `get_bets`: ❌
- `get_base_bet_return`: ❌
- `get_bet_id?`: ❌
- `make_bet`: ❌

### Til discord_bot.py
- `add_user`: ❌
- `play_event_sounds`: ❌

### Til game_stats.py
- `get_stat_value`: ❌
- `get_player_stats`: ❌
- `get_finished_game_summary`: ❌
- `get_active_game_summary`: ❌
