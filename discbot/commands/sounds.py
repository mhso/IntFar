import random

from api import audio_handler
from api.util import SUPPORTED_GAMES, get_website_link

async def handle_set_event_sound(client, message, game, sound, event):
    game_name = SUPPORTED_GAMES[game]
    response = ""
    event_fmt = "Int-Far" if event == "intfar" else "{emote_Doinks}"
    event_fmt = f"{event_fmt} in {game_name}"

    if sound is None: # Get current set sound for event.
        current_sound = client.database.get_event_sound(game, message.author.id, event)
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
        client.database.remove_event_sound(game, message.author.id, event)
        response = f"Removed sound from triggering when getting {event_fmt}."

    elif not audio_handler.is_valid_sound(sound):
        response = f"Invalid sound: `{sound}`. See `!sounds` for a list of valid sounds."

    else:
        client.database.set_event_sound(game, message.author.id, sound, event)
        response = (
            f"The sound `{sound}` will now play when you get {event_fmt} " +
            "{emote_poggers}"
        )

    await message.channel.send(client.insert_emotes(response))

async def handle_play_sound_msg(client, message, sound):
    voice_state = message.author.voice
    success, status = await client.audio_handler.play_sound(sound, voice_state, message)

    if not success:
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

    sounds_list = audio_handler.get_available_sounds()
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
    valid_orders = ["alphabetical", "oldest", "newest"]

    if ordering not in valid_orders:
        await message.channel.send(
            f"Invalid ordering: '{ordering}'. Must be one of: `{', '.join(valid_orders)}`."
        )
        return

    sounds_list = client.audio_handler.get_sounds(ordering)
    header = "Available sounds:"
    footer = f"Upload your own at `{get_website_link()}/soundboard`!"

    await client.paginate(message.channel, sounds_list, 0, 10, header, footer)
