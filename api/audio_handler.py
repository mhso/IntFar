from glob import glob
import asyncio
import os

from discord import PCMVolumeTransformer
from discord.player import FFmpegPCMAudio

SOUNDS_PATH = "app/static/sounds/"

def get_available_sounds():
    return sorted([
        x.replace("\\", "/").split("/")[-1].split(".")[0]
        for x in glob(f"{SOUNDS_PATH}/*.mp3")
    ])

async def play_sound(client, message, sound):
    voice_state = message.author.voice
    if sound not in get_available_sounds(): # Check if 'sound' refers to a valid mp3 sound snippet.
        await message.channel.send(
            f"Invalid name of sound: '{sound}'. Use !sounds for a list of available sounds."
        )
    elif voice_state is None: # Check if user is in a voice channel.
        response = client.insert_emotes(
            "You must be in a voice channel to play sounds {emote_simp_but_closeup}"
        )
        await message.channel.send(response)
    else:
        voice_channel = voice_state.channel

        if client.config.env == "dev":
            ffmpeg_exe = "ffmpeg"
        else:
            ffmpeg_exe = os.path.abspath("resources/ffmpeg-4.1.6/ffmpeg")

        # Create voice channel stream for the channel the user is in.
        player = PCMVolumeTransformer(
            FFmpegPCMAudio(f"{SOUNDS_PATH}/{sound}.mp3", executable=ffmpeg_exe)
        )
        vc_stream = await voice_channel.connect()
        # Create FFMPEG MP3 audio player.

        # Start the player and wait until it is done.
        vc_stream.play(player)
        while vc_stream.is_playing():
            await asyncio.sleep(0.5)
        vc_stream.stop()

        # Disconnect from voice channel.
        await vc_stream.disconnect()

async def handle_sounds_msg(message):
    response = "Available sounds:"
    for sound in get_available_sounds():
        response += f"\n- `{sound}`"
    await message.channel.send(response)
