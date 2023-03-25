from glob import glob
import asyncio
import json
import os

from discord import PCMVolumeTransformer
from discord.player import FFmpegPCMAudio

SOUNDS_PATH = "app/static/sounds/"

def get_available_sounds(ordering="alphabetical"):
    sounds = [
        (os.path.basename(sound).split(".")[0], os.stat(sound).st_ctime)
        for sound in glob(f"{SOUNDS_PATH}/*.mp3")
    ]

    def order_func(sound_tuple):
        if ordering == "newest":
            return -sound_tuple[1]

        if ordering == "oldest":
            return sound_tuple[1]

        return sound_tuple[0]        

    return [sound_tuple[0] for sound_tuple in sorted(sounds, key=order_func)]

def get_sound_owners():
    owner_file_path = os.path.join(os.path.abspath(SOUNDS_PATH), "owners.json")
    with open(owner_file_path, encoding="utf-8") as fp:
        return json.load(fp)

class AudioHandler: # Keep track of connection to voice channel.
    def __init__(self, config):
        self.config = config
        self.voice_stream = None # Keep track of connection to voice.
        self.sound_queue = []

    async def play_loop(self):
        while self.sound_queue != []:
            sound = self.sound_queue.pop(0)

            # Create volume controlled FFMPEG player from sound file.
            player = PCMVolumeTransformer(
                FFmpegPCMAudio(f"{SOUNDS_PATH}/{sound}.mp3", executable="ffmpeg")
            )

            # Start the player and wait until it is done.
            self.voice_stream.play(player)
            while self.voice_stream.is_playing():
                await asyncio.sleep(0.5)

            await asyncio.sleep(0.5)
            self.voice_stream.stop()

        # Disconnect from voice channel.
        await self.voice_stream.disconnect()

        self.voice_stream = None

    async def play_sound(self, voice_state, sounds):
        if not isinstance(sounds, list):
            sounds = [sounds]

        for sound in sounds:
            # Check if 'sound' refers to a valid mp3 sound snippet.
            if sound not in get_available_sounds():
                err_msg = (
                    f"Invalid name of sound: '{sound}'. " +
                    "Use !sounds for a list of available sounds."
                )
                if len(sounds) == 1:
                    return False, err_msg

        if voice_state is None: # Check if user is in a voice channel.
            err_msg = (
                "You must be in a voice channel to play sounds {emote_simp_but_closeup}"
            )
            return False, err_msg
        elif sounds != []:
            voice_channel = voice_state.channel

            # Add sound to queue.
            self.sound_queue.extend(sounds)

            if self.voice_stream is None:
                # If no voice connection exists, make a new one.
                self.voice_stream = await voice_channel.connect(timeout=5)

                await self.play_loop() # Play sounds in the queue.

            return True, None

    def get_sounds(self, ordering):
        sounds = []
        for sound in get_available_sounds(ordering):
            sounds.append(f"- `{sound}`")

        return sounds
    
    def get_owners(self):
        return get_sound_owners()
