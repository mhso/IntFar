from datetime import datetime
import random

from api.util import SUPPORTED_GAMES, get_website_link

async def handle_set_event_sound(client, message, game, sound, event):
    database = client.game_databases[game]
    game_name = SUPPORTED_GAMES[game]
    response = ""
    event_fmt = "Int-Far" if event == "intfar" else "{emote_Doinks}"
    event_fmt = f"{event_fmt} in {game_name}"

    if sound is None: # Get current set sound for event.
        current_sound = database.get_event_sound(message.author.id, event)
        example_cmd = f"!{event}_sound"
        if current_sound is None:
            response = (
                f"You have not yet set a sound that triggers when getting {event_fmt}. " +
                f"Do so by writing `{example_cmd} {game} [sound]`" + " {emote_uwucat}\n" +
                "See a list of available sounds with `!sounds`"
            )

        else:
            response = (
                f"You currently have `{current_sound}` as the sound that triggers " +
                f"when getting {event_fmt} " + "{emote_Bitcoinect}\n" +
                f"Use `{example_cmd} {game} remove` to remove this sound."
            )

    elif sound == "remove":
        database.remove_event_sound(message.author.id, event)
        response = f"Removed sound from triggering when getting {event_fmt}."

    elif not client.audio_handler.is_valid_sound(sound):
        response = f"Invalid sound: `{sound}`. See `!sounds` for a list of valid sounds."

    else:
        database.set_event_sound(message.author.id, sound, event)
        response = (
            f"The sound `{sound}` will now play when you get {event_fmt} " +
            "{emote_poggers}"
        )

    await message.channel.send(client.insert_emotes(response))

async def handle_set_join_sound(client, message, sound=None):
    response = ""

    if sound is None: # Get current set sound for joining.
        current_sound = client.meta_database.get_join_sound(message.author.id)
        if current_sound is None:
            response = (
                f"You have not yet set a sound that triggers when joining a voice channel. " +
                "Do so by writing `!join_sound [sound]` {emote_uwucat}\n" +
                "See a list of available sounds with `!sounds`"
            )

        else:
            response = (
                f"You currently have `{current_sound}` as the sound that triggers " +
                "when joining a voice channel {emote_Bitcoinect}\n" +
                "Use `!join_sound remove` to remove this sound."
            )

    elif sound == "remove":
        client.meta_database.remove_join_sound(message.author.id)
        response = "Removed sound from triggering when joining a voice channel."

    elif not client.audio_handler.is_valid_sound(sound):
        response = f"Invalid sound: `{sound}`. See `!sounds` for a list of valid sounds."

    else:
        client.meta_database.set_join_sound(message.author.id, sound)
        response = (
            f"The sound `{sound}` will now play when you join a voice channel " +
            "{emote_poggers}"
        )

    await message.channel.send(client.insert_emotes(response))

async def handle_play_sound_msg(client, message, sound):
    voice_state = message.author.voice
    success, status = await client.audio_handler.play_sound(sound, voice_state, message)

    if not success:
        await message.channel.send(client.insert_emotes(status))

async def handle_seek_sound_msg(client, message, time_str):
    voice_state = message.author.voice
    status = await client.audio_handler.seek_sound(voice_state, time_str)

    if status is not None:
        await message.channel.send(client.insert_emotes(status))

async def handle_skip_sound_msg(client, message):
    voice_state = message.author.voice
    status = await client.audio_handler.skip_sound(voice_state)

    if status is not None:
        await message.channel.send(client.insert_emotes(status))

async def handle_stop_sound_msg(client, message):
    voice_state = message.author.voice
    status = await client.audio_handler.stop_sound(voice_state)

    if status is not None:
        await message.channel.send(client.insert_emotes(status))

async def handle_random_sound_msg(client, message):
    voice_state = message.author.voice

    sounds_list = client.audio_handler.get_sounds()
    sound = sounds_list[random.randint(0, len(sounds_list)-1)][0]

    await message.channel.send(f"Playing random sound: `{sound}`")

    success, status = await client.audio_handler.play_sound(sound, voice_state)

    if not success:
        await message.channel.send(client.insert_emotes(status))

async def handle_search_msg(client, message, *search_args):
    if not search_args:
        return

    search_str = " ".join(search_args)
    success, data = client.audio_handler.get_youtube_suggestions(search_str, message)

    if not success:
        await message.channel.send(data)
        return

    response = f"Search results from YouTube for `{search_str}`:"
    if data == []:
        response += "\nNo results appear to be found :("
    else:
        for index, suggestion in enumerate(data, start=1):
            response += f"\n- **{index}**: `{suggestion[0]}` - by *{suggestion[1]}*"

    suggestions_msg = await message.channel.send(response)
    client.audio_handler.youtube_suggestions_msg[message.guild.id] = suggestions_msg

async def handle_sounds_msg(client, message, ordering="newest"):
    valid_orders = ["alphabetical", "oldest", "newest", "most_played", "least_played"]

    if ordering not in valid_orders:
        await message.channel.send(
            f"Invalid ordering: '{ordering}'. Must be one of: `{', '.join(valid_orders)}`."
        )
        return

    sounds_list = [
        f"- `{sound}` (uploaded **{timestamp}** by {client.get_discord_nick(owner_id, message.guild.id) or 'Unknown'}, **{plays}** plays)"
        for sound, owner_id, plays, timestamp in client.audio_handler.get_sounds(ordering)
    ]
    header = "Available sounds:"
    footer = f"Upload your own at `{get_website_link()}/soundboard`!"

    await client.paginate(message.channel, sounds_list, 0, 10, header, footer)

async def handle_billboard_msg(client, message):
    database = client.meta_database
    timestamp = datetime.now()

    date_start_1, date_end_1 = database.get_weekly_timestamp(timestamp, 2)
    week_old = {
        sound: (plays, rank)
        for sound, plays, rank
        in database.get_weekly_sound_hits(date_start_1, date_end_1)
    }

    date_start_2, date_end_2 = database.get_weekly_timestamp(timestamp, 1)
    week_new = [
        (sound, plays, rank)
        for sound, plays, rank
        in database.get_weekly_sound_hits(date_start_2, date_end_2)
    ]

    billboard_data = []
    for index, (sound, plays_now, rank_now) in enumerate(week_new, start=1):
        if sound in week_old:
            plays_then, rank_then = week_old[sound]
            rank_shift = rank_then - rank_now
            plays_diff = plays_now - plays_then
        else:
            rank_shift = 0
            plays_diff = 0

        sound_part = f"`{index}. {sound}:"
        plays_part = f"{plays_now} play{'' if plays_now == 1 else 's'}"
        if plays_diff != 0:
            plays_diff_part = f"({'+' if plays_diff > 0 else '-'}{abs(plays_diff)})"
        else:
            plays_diff_part = ""

        if rank_shift != 0:
            emoji = ":arrow_up_small:" if rank_shift > 0 else ":small_red_triangle_down:"
            rank_diff_part = f"{emoji} {abs(rank_shift)}"
        else:
            rank_diff_part = ""

        billboard_data.append((sound_part, plays_part, plays_diff_part, rank_diff_part))

    # Calculate padding for each row of billboard data
    paddings = []
    index = 0
    chunk_size = 10
    while index < len(billboard_data):
        chunk = billboard_data[index : index + chunk_size]
        row_padding = [0 for _ in billboard_data[0]]
        for row in chunk:
            for col_index, col_data in enumerate(row):
                row_padding[col_index] = max(len(col_data), row_padding[col_index])

        paddings.extend([row_padding for _ in range(chunk_size)])
        index += chunk_size

    # Apply padding to each row
    formatted_data = []
    for (padding, row_data) in zip (paddings, billboard_data):
        line = ""
        for index, (pad, data) in enumerate(zip(padding, row_data)):
            pad_str = " " * (pad - len(data))
            line += data + " " + pad_str

            if index == 2:
                line += "`  "

        formatted_data.append(line)

    dt_start = datetime.fromtimestamp(date_start_2).strftime("%d/%m/%Y")
    dt_end = datetime.fromtimestamp(date_end_2).strftime("%d/%m/%Y")

    header = f"The hottest hit sounds from **{dt_start}** - **{dt_end}**:"

    await client.paginate(message.channel, formatted_data, 0, chunk_size, header)
