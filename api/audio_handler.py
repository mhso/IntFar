from glob import glob
import asyncio
import json
import os
import math
import traceback
from discbot.commands.util import ADMIN_DISC_ID

from discord import PCMVolumeTransformer
from discord.player import FFmpegPCMAudio

from streamscape import Streamscape

from api.config import Config

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

    return sorted(sounds, key=order_func)

def is_valid_sound(sound):
    return sound in [tup[0] for tup in get_available_sounds()]

def get_sound_owners():
    owner_file_path = os.path.join(os.path.abspath(SOUNDS_PATH), "owners.json")
    with open(owner_file_path, encoding="utf-8") as fp:
        return json.load(fp)

def _get_time_str(seconds):
    secs = int(seconds)
    mins = 0
    hours = 0
    if secs >= 60:
        mins = secs // 60
    if mins >= 60:
        hours = mins // 60

    mins = mins % 60
    secs = secs % 60

    time_str = f"{mins:02d}:{secs:02d}"
    if hours > 0:
        time_str = f"{hours:02d}:{time_str}"

    return time_str

def _get_padded_str(string, total_chars):
    total_padding = total_chars - len(string)
    pad_left = math.floor(total_padding / 2)
    pad_right = math.ceil(total_padding / 2)
    return f"{' ' * pad_left}{string}{' ' * pad_right}"

class ClosableFFmpegPCMAudio(FFmpegPCMAudio):
    """
    Subclass of discord.py FFmpegPCMAudio class that overrides the `pipe_writer`
    class, to allow the audio stream to close properly when it is exhausted.
    """
    def __init__(self, source, *, executable = 'ffmpeg', pipe = False, stderr = None, before_options = None, options = None):
        self.error = None
        super().__init__(source, executable=executable, pipe=pipe, stderr=stderr, before_options=before_options, options=options)

    def _pipe_writer(self, source):
        def close_callback(err_msg=None):
            print("KILLING STREAM THROUGH CALLBACK!")
            self.error = err_msg
            self._kill_process()

        source.on("stop", close_callback)

        while self._process:
            # arbitrarily large read size
            data = source.read(-1)
            if not data and self._process.returncode is not None:
                print("PIPE PROCESS DED:", self._process.returncode)
                return
            try:
                if self._stdin is not None:
                    try:
                        self._stdin.write(data)
                    except AttributeError:
                        return
            except Exception:
                print("EXCEPTION IN FFMPEG PLAYER")
                traceback.print_exc()
                # at this point the source data is either exhausted or the process is fubar
                self._process.terminate()
                return

class AudioHandler:
    EMOJI_PREV = "⏮️"
    EMOJI_PLAY = "⏯️"
    EMOJI_STOP = "⏹️"
    EMOJI_NEXT = "⏭️"
    AUDIO_CONTROL_EMOJIS = [
        EMOJI_PREV, EMOJI_PLAY, EMOJI_STOP, EMOJI_NEXT
    ]

    def __init__(self, config: Config, stream_handler: Streamscape):
        self.config = config
        self.stream_handler = stream_handler
        self.voice_stream = None # Keep track of connection to voice channel.
        self.web_stream = None
        self.playback_msg = None
        self.sound_queue = []

    async def play_loop(self):
        while self.sound_queue != []:
            sound_name, message, sound_type = self.sound_queue.pop(0)

            if sound_type == "file":
                audio_source = FFmpegPCMAudio(f"{SOUNDS_PATH}/{sound_name}.mp3", executable="ffmpeg")
                volume = 1
            else:
                print(f"PLAYING STREAM FROM '{sound_name}'")
                sample_rate = 48000
                try:
                    self.web_stream = self.stream_handler.get_stream(
                        sound_name,
                        sample_rate=sample_rate,
                        buffer_size=1024,
                        dtype="int16"
                    )
                except ValueError:
                    # URL was invalid in some way
                    await message.channel.send(
                        f"Could not get audio from '{sound_name}'. "
                        "Either the link is invalid or the site could not be reached."
                    )
                    continue
                except Exception:
                    # Uncaught exception when creating stream. Probably a PortAudio or OS error.
                    admin_mention = None
                    for member in message.guild.members:
                        if member.id == ADMIN_DISC_ID:
                            admin_mention = member.mention
                            break

                    response = f"Weird error happened while recording sound... "
                    if admin_mention is not None:
                        response += f"This sounds like a job for {admin_mention}!"

                    await message.channel.send(response)
                    continue

                self.web_stream.open()
                audio_source = ClosableFFmpegPCMAudio(
                    self.web_stream,
                    executable="ffmpeg",
                    pipe=True,
                    before_options=f"-f s16le -ar {sample_rate} -ac 2"
                )
                volume = 0.3
                self.playback_msg = await message.channel.send(self._get_playback_str())
                for control_button in self.AUDIO_CONTROL_EMOJIS:
                    await self.playback_msg.add_reaction(control_button)

            # Create volume controlled FFMPEG player from sound file.
            player = PCMVolumeTransformer(audio_source, volume=volume)

            # Start the player and wait until it is done.
            self.voice_stream.play(player)
            while self.voice_stream.is_playing():
                await asyncio.sleep(0.5)
                if message is not None:
                    await self.playback_msg.edit(content=self._get_playback_str())

            await asyncio.sleep(0.5)

            if message is not None:
                await self.playback_msg.delete()

            self.voice_stream.stop()

            if self.web_stream is not None:
                self.web_stream = None
                self.playback_msg = None

            if sound_type == "url" and audio_source.error:
                return False, audio_source.error

        # Disconnect from voice channel.
        await self.voice_stream.disconnect()

        self.voice_stream = None
        return True, None

    async def play_sound(self, sounds, voice_state, message=None):
        if not isinstance(sounds, list):
            sounds = [sounds]

        validated_sounds = []
        for sound in sounds:
            # Check if 'sound' is a URL to a valid website
            is_valid_url, url = self.stream_handler.validate_url(sound)
            if is_valid_url:
                validated_sounds.append((url, message, "url"))

            # Check if 'sound' refers to a valid mp3 sound snippet.
            elif is_valid_sound(sound):
                validated_sounds.append((sound, message, "file"))

            else:
                valid_sites = ", ".join(self.stream_handler.VALID_STREAM_URLS.values())
                err_msg = (
                    f"Can't play sound `{sound}`. " +
                    f"Either provide a link to one of `{valid_sites}` or the name of a sound. "
                    "Use !sounds for a list of available sounds."
                )
                if len(sounds) == 1:
                    return False, err_msg

        if voice_state is None: # Check if user is in a voice channel.
            err_msg = (
                "You must be in a voice channel to play sounds {emote_simp_but_closeup}"
            )
            return False, err_msg
        elif validated_sounds != []:
            voice_channel = voice_state.channel

            for sound, msg, sound_type in validated_sounds:
                if sound_type == "url" and msg is not None:
                    if self.voice_stream is not None:
                        response = f"Adding sound to the queue..."
                    else:
                        hosts = ["youtube", "soundcloud"]
                        hostname = None
                        for host in hosts:
                            if host in url:
                                hostname = host
                                break

                        if hostname is None:
                            hostname = "link"

                        response = f"Playing sound from `{hostname}`..."
                    await msg.channel.send(response)
                    if len(validated_sounds) > 1:
                        await asyncio.sleep(0.5)

            # Add sound to queue.
            self.sound_queue.extend(validated_sounds)

            if self.voice_stream is None:
                # If no voice connection exists, make a new one.
                self.voice_stream = await voice_channel.connect(timeout=5)

                success, status = await self.play_loop() # Play sounds in the queue.
                return success, status

            return True, None

    async def skip_sound(self, voice_state):
        # Check if user is in a voice channel.
        if voice_state is None:
            err_msg = (
                "You must be in a voice channel to skip sounds {emote_simp_but_closeup}"
            )
            return err_msg

        # Check if a stream is active
        if self.web_stream is not None:
            sound_title = "sound" if self.web_stream.title is None else f"`{self.web_stream.title}`"
            msg = f"Skipped {sound_title}."
            self.web_stream.stop()
            return msg

        # No active stream, do nothing
        return None

    async def audio_control_pressed(self, emoji, member, channel):
        if self.web_stream is not None and member.voice is not None:
            if emoji.name == self.EMOJI_NEXT:
                await self.skip_sound(member.voice)
            elif emoji.name == self.EMOJI_PLAY:
                self.web_stream.pause_or_play()
            elif emoji.name == self.EMOJI_STOP:
                sound_quantifier = "sound" if len(self.sound_queue) == 1 else "sounds"
                queue_len_str = (
                    "..." if self.sound_queue == []
                    else f" and clearing queue of **{len(self.sound_queue)}** other {sound_quantifier}..."
                )
                await channel.send(f"Stopping sound{queue_len_str}")
                self.sound_queue.clear()
                self.web_stream.stop()

    def get_sounds(self, ordering):
        sounds = []
        for sound in get_available_sounds(ordering):
            sounds.append(f"- `{sound[0]}`")

        return sounds

    def get_owners(self):
        return get_sound_owners()

    def _get_playback_str(self):
        duration = None
        if self.web_stream is not None and self.web_stream.duration is not None:
            duration = self.web_stream.duration

        chars_per_line = 68

        # 'Now playing' string
        now_playing = _get_padded_str("Now Playing", chars_per_line)

        title = self.web_stream.title if self.web_stream.title is not None else self.web_stream.url
        title = _get_padded_str(f'"{title}"', chars_per_line)

        # Create string describing time played vs. total duration
        progress = self.web_stream.progress
        progress_str = _get_time_str(progress)
        if duration is not None:
            duration_str = _get_time_str(duration)
        else:
            duration_str = "??:??"

        # Get string describing time played vs. total duration
        time_str = f"{progress_str} / {duration_str}"
        time_str = _get_padded_str(time_str, chars_per_line)

        # Get fancy progress bar with emojis
        total_blocks = 24
        blue_blocks = 0
        if duration is not None:
            blue_blocks = round(((progress / duration) * 100) / (100 / total_blocks))

        white_blocks = total_blocks - blue_blocks

        blue_blocks_str = ":blue_square:" * blue_blocks
        white_blocks_str = ":white_large_square:" * white_blocks

        return (
            "```php\n"
            f"{now_playing}\n"
            f"{title}\n"
            f"{time_str}```{blue_blocks_str}{white_blocks_str}"
        )
