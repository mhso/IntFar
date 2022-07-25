import random

from api import audio_handler

async def handle_set_event_sound(client, message, sound, event):
    response = ""
    event_fmt = "Int-Far" if event == "intfar" else "{emote_Doinks}"
    if sound is None: # Get current set sound for event.
        current_sound = client.database.get_event_sound(message.author.id, event)
        example_cmd = f"!{event}_sound"
        if current_sound is None:
            response = (
                f"You have not yet set a sound that triggers when getting {event_fmt}. " +
                f"Do so by writing `{example_cmd} [sound]`" + " {emote_uwucat}\n" +
                "See a list of available sounds with `!sounds`"
            )
        else:
            response = (
                f"You currently have `{current_sound}` as the sound that triggers " +
                f"when getting {event_fmt} " + "{emote_Bitcoinect}\n" +
                f"Use `{example_cmd} remove` to remove this sound."
            )
    elif sound == "remove":
        client.database.remove_event_sound(message.author.id, event)
        response = f"Removed sound from triggering when getting {event_fmt}."
    elif sound not in audio_handler.get_available_sounds():
        response = f"Invalid sound: `{sound}`. See `!sounds` for a list of valid sounds."
    else:
        client.database.set_event_sound(message.author.id, sound, event)
        response = (
            f"The sound `{sound}` will now play when you get {event_fmt} " +
            "{emote_poggers}"
        )

    await message.channel.send(client.insert_emotes(response))

async def handle_play_sound_msg(client, message, sound):
    voice_state = message.author.voice
    success, status = await client.audio_handler.play_sound(voice_state, sound)

    if not success:
        await message.channel.send(client.insert_emotes(status))

async def handle_random_sound_msg(client, message):
    voice_state = message.author.voice

    sounds_list = audio_handler.get_available_sounds()
    sound = sounds_list[random.randint(0, len(sounds_list)-1)]

    await message.channel.send(f"Playing random sound: `{sound}`")

    success, status = await client.audio_handler.play_sound(voice_state, sound)

    if not success:
        await message.channel.send(client.insert_emotes(status))

async def handle_sounds_msg(client, message, ordering="alphabetical"):
    valid_orders = ["alphabetical", "oldest", "newest"]

    if ordering not in valid_orders:
        await message.channel.send(
            f"Invalid ordering: '{ordering}'. Must be one of: `{', '.join(valid_orders)}`."
        )
        return

    sounds_list = client.audio_handler.get_sounds(ordering)
    header = "Available sounds:"
    footer = "Upload your own at `https://mhooge.com/intfar/soundboard`!"

    await client.paginate(message.channel, sounds_list, 0, 10, header, footer)
