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

class AudioHandler: # Keep track of connection to voice channel.
    def __init__(self, config):
        self.config = config
        self.voice_stream = None # Keep track of connection to voice.
        self.sound_queue = []

    async def play_loop(self):
        if self.config.env == "dev":
            ffmpeg_exe = "ffmpeg"
        else:
            ffmpeg_exe = os.path.abspath("resources/ffmpeg-4.1.6/ffmpeg")

        while self.sound_queue != []:
            sound = self.sound_queue.pop(0)

            # Create volume controlled FFMPEG player from sound file.
            player = PCMVolumeTransformer(
                FFmpegPCMAudio(f"{SOUNDS_PATH}/{sound}.mp3", executable=ffmpeg_exe)
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
                self.voice_stream = await voice_channel.connect()

                await self.play_loop() # Play sounds in the queue.

            return True, None

    def get_sounds(self):
        sounds = []
        for sound in get_available_sounds():
            sounds.append(f"- `{sound}`")
        return sounds
