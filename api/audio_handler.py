from glob import glob
import asyncio
import json
import os
import math

from discord import PCMVolumeTransformer
from discord.player import FFmpegPCMAudio

from streamscape import Streamscape
from streamscape.sites import SITES
from streamscape.errors import StreamCreationError
from mhooge_flask.logging import logger

from api.config import Config
from api.youtube_api import YouTubeAPIClient, NUM_SEARCH_RESULTS
from discbot.commands.util import ADMIN_DISC_ID

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
                # at this point the source data is either exhausted or the process is fubar
                self._kill_process()
                return

class AudioHandler:
    """
    Class that handles playing sound files or audio streams from YouTube or Soundcloud
    through the Discord voice API.
    Enables the queueing of multiple sounds that will be played in order and manages
    control buttons for pausing, skipping, or stopping the playing of audio streams.
    """
    EMOJI_PREV = "⏮️"
    EMOJI_PLAY = "⏯️"
    EMOJI_STOP = "⏹️"
    EMOJI_NEXT = "⏭️"
    AUDIO_CONTROL_EMOJIS = [
        EMOJI_PREV, EMOJI_PLAY, EMOJI_STOP, EMOJI_NEXT
    ]

    def __init__(self, config: Config, stream_handler: Streamscape):
        self.youtube_api = YouTubeAPIClient(config)
        self.config = config
        self.stream_handler = stream_handler
        self.voice_stream = {} # Keep track of connections to voice channels.
        self.web_stream = {}
        self.playback_msg = {}
        self.sound_queue = {}
        self.active_youtube_suggestions = {}
        self.youtube_suggestions_msg = {}

    async def _play_loop(self, guild_id):
        while (sound_queue := self.sound_queue.get(guild_id, [])) != []:
            sound_name, message, sound_type = sound_queue.pop(0)
            if sound_type == "search":
                del self.active_youtube_suggestions[guild_id]
                await self.youtube_suggestions_msg[guild_id].delete()
                del self.youtube_suggestions_msg[guild_id]
                sound_type = "url"

            if sound_type == "file":
                # Stream audio from a file
                audio_source = FFmpegPCMAudio(f"{SOUNDS_PATH}/{sound_name}.mp3", executable="ffmpeg")
                volume = 1
            else:
                # Stream audio from a URL using Streamscape
                sample_rate = 48000
                try:
                    self.web_stream[guild_id] = self.stream_handler.get_stream(
                        sound_name,
                        sample_rate=sample_rate,
                        buffer_size=1024,
                        raw_format="s16le"
                    )
                except ValueError:
                    # URL was invalid in some way
                    await message.channel.send(
                        f"Could not get audio from '{sound_name}'. "
                        "Either the link is invalid or the site could not be reached."
                    )
                    continue
                except Exception:
                    logger.exception("Error during Streamscape 'get_stream'")

                    # Uncaught exception when creating stream.
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

                try:
                    self.web_stream[guild_id].open()
                except StreamCreationError:
                    response = (
                        "Failed to start this video/song for some reason :( "
                        "maybe it is age-restricted or maybe Int-Far just sucks."
                    )
                    await message.channel.send(response)
                    continue

                audio_source = ClosableFFmpegPCMAudio(
                    self.web_stream[guild_id],
                    executable="ffmpeg",
                    pipe=True,
                    before_options=f"-f s16le -ar {sample_rate} -ac 2"
                )
                volume = 0.2
                self.playback_msg[guild_id] = await message.channel.send(self._get_playback_str(guild_id))
                for control_button in self.AUDIO_CONTROL_EMOJIS:
                    await self.playback_msg[guild_id].add_reaction(control_button)

            # Create volume controlled FFMPEG player from sound file.
            player = PCMVolumeTransformer(audio_source, volume=volume)

            # Start the player and wait until it is done.
            self.voice_stream[guild_id].play(player)

            while self.voice_stream[guild_id].is_playing():
                await asyncio.sleep(0.5)
                if self.playback_msg.get(guild_id) is not None:
                    await self.playback_msg[guild_id].edit(content=self._get_playback_str(guild_id))

            await asyncio.sleep(0.5)

            if guild_id in self.playback_msg:
                # Delete playback progress message
                await self.playback_msg[guild_id].delete()
                del self.playback_msg[guild_id]

            self.voice_stream[guild_id].stop()

            if guild_id in self.web_stream:
                del self.web_stream[guild_id]

            if sound_type == "url" and audio_source.error:
                return False, audio_source.error

        # Disconnect from voice channel.
        await self.voice_stream[guild_id].disconnect()

        # Reset the sound queue and voice stream for the current guild
        if guild_id in self.sound_queue:
            del self.sound_queue[guild_id]
        del self.voice_stream[guild_id]
    
        return True, None

    async def play_sound(self, sounds, voice_state, message=None):
        """
        Add one or more sounds to the sound queue for the given server.
        The sounds will be played as soon as their spot in the queue is reached
        or immediately, if the queue is empty.
        """
        if not isinstance(sounds, list):
            sounds = [sounds]

        validated_sounds = []
        for sound in sounds:
            # Check if 'sound' refers to a valid mp3 sound snippet.
            if is_valid_sound(sound):
                validated_sounds.append((sound, message, "file"))
                continue

            # Check if 'sound' is an integer referring to the results of a YouTube search.
            if (
                message is not None
                and (video_suggestions := self.active_youtube_suggestions.get(message.guild.id)) is not None
            ):
                try:
                    sound_index = int(sound)
                    if 0 < sound_index <= NUM_SEARCH_RESULTS:
                        sound = video_suggestions[sound_index - 1][2]
                        validated_sounds.append((sound, message, "search"))
                        continue

                except ValueError:
                    pass

            # Check if 'sound' is a URL to a valid website
            is_valid_url, url = self.stream_handler.validate_url(sound)
            if is_valid_url:
                validated_sounds.append((url, message, "url"))

            else:
                valid_sites = ", ".join(f"{site}.com" for site in SITES)
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
            guild_id = voice_channel.guild.id

            for sound, msg, sound_type in validated_sounds:
                if sound_type in ("url", "search") and msg is not None:
                    if self.voice_stream.get(guild_id) is not None:
                        response = f"Adding sound to the queue..."
                    else:
                        hosts = ["youtube", "soundcloud"]
                        hostname = None
                        for host in hosts:
                            if host in sound:
                                hostname = host
                                break

                        if hostname is None:
                            hostname = "link"

                        response = f"Playing sound from `{hostname}`..."
                    await msg.channel.send(response)
                    if len(validated_sounds) > 1:
                        await asyncio.sleep(0.5)

            # Add sound to queue.
            if guild_id not in self.sound_queue:
                self.sound_queue[guild_id] = []

            self.sound_queue[guild_id].extend(validated_sounds)

            if guild_id not in self.voice_stream:
                # If no voice connection exists, make a new one.
                self.voice_stream[guild_id] = await voice_channel.connect(timeout=5)

                success, status = await self._play_loop(guild_id) # Play sounds in the queue.
                return success, status

            return True, None

    async def skip_sound(self, voice_state):
        # Check if user is in a voice channel.
        if voice_state is None:
            err_msg = (
                "You must be in a voice channel to skip sounds {emote_simp_but_closeup}"
            )
            return err_msg
        
        guild_id = voice_state.channel.guild.id

        # Check if a stream is active
        if (web_stream := self.web_stream.get(guild_id)) is not None:
            sound_title = "sound" if web_stream.title is None else f"`{web_stream.title}`"
            msg = f"Skipped {sound_title}."
            web_stream.stop()
            return msg

        # No active stream, do nothing
        return None

    async def stop_sound(self, voice_state):
        # Check if user is in a voice channel.
        if voice_state is None:
            err_msg = (
                "You must be in a voice channel to stop sounds {emote_simp_but_closeup}"
            )
            return err_msg

        guild_id = voice_state.channel.guild.id

        # Check if a stream is active
        if (web_stream := self.web_stream.get(guild_id)) is not None:
            sound_quantifier = "sound" if len(self.sound_queue) == 1 else "sounds"
            sound_queue = self.sound_queue.get(guild_id, [])
            queue_len_str = (
                "..." if sound_queue == []
                else f" and clearing queue of **{len(sound_queue)}** other {sound_quantifier}..."
            )
            msg = f"Stopping sound{queue_len_str}"
            del self.sound_queue[guild_id]
            web_stream.stop()
            return msg

        # No active stream, do nothing
        return None

    async def audio_control_pressed(self, emoji, member, channel):
        """
        Called when a user reacts to the currently active playback status message
        with a valid audio control emoji such as play, pause, stop, or skip.
        """
        guild_id = channel.guild.id
        if (web_stream := self.web_stream.get(guild_id)) is not None and member.voice is not None:
            if emoji.name == self.EMOJI_NEXT:
                # Stop the active stream and skip to the next sound in the queue
                if (msg := await self.skip_sound(member.voice)) is not None:
                    await channel.send(msg)
            elif emoji.name == self.EMOJI_PLAY:
                # Pause or resume the active stream
                web_stream.pause_or_play()
            elif emoji.name == self.EMOJI_STOP:
                # Stop the active stream and empty the sound queue
                if (msg := await self.stop_sound(member.voice)) is not None:
                    await channel.send(msg)

    def get_sounds(self, ordering):
        sounds = []
        for sound in get_available_sounds(ordering):
            sounds.append(f"- `{sound[0]}`")

        return sounds

    def get_sound_owners(self):
        return get_sound_owners()

    def get_youtube_suggestions(self, search_term, message):
        success, suggestions = self.youtube_api.query(search_term)
        if success:
            self.active_youtube_suggestions[message.guild.id] = suggestions

        return success, suggestions

    def _get_playback_str(self, guild_id):
        """
        Get a string describing the status and progress of the audio stream currently
        being played. This string is posted and periodically updated by the bot in
        the text channel where the sound was started from. The status includes the
        title of the audio/video being played as well as progress and duration.
        """
        duration = None
        if self.web_stream.get(guild_id) is not None and self.web_stream[guild_id].duration is not None:
            duration = self.web_stream[guild_id].duration

        chars_per_line = 68

        # 'Now playing' string
        now_playing = _get_padded_str("Now Playing", chars_per_line)

        title = self.web_stream[guild_id].title if self.web_stream[guild_id].title is not None else self.web_stream[guild_id].url
        title = _get_padded_str(f'"{title}"', chars_per_line)

        # Create string describing time played vs. total duration
        progress = self.web_stream[guild_id].progress
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

        # Bring it all together. Format as a PHP code block for pretty colors
        return (
            "```php\n"
            f"{now_playing}\n"
            f"{title}\n"
            f"{time_str}```{blue_blocks_str}{white_blocks_str}"
        )
