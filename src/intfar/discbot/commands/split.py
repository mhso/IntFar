from intfar.api.game_data import get_stat_quantity_descriptions

async def handle_end_of_split_msg(client, disc_id):
    database = client.game_databases["lol"]

    stats_to_get = list(get_stat_quantity_descriptions("lol").keys())
    split_data = database.get_split_summary_data(disc_id, stats_to_get)

    split_data

    message = ""

    await client.send_dm(message, disc_id)

