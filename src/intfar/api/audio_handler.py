import asyncio
import math
from datetime import datetime
import os
from subprocess import Popen, PIPE
from time import time
from typing import Dict

from discord import Message, PCMVolumeTransformer, TextChannel, VoiceClient
from discord.player import FFmpegPCMAudio, AudioSource

from mhooge_flask.logging import logger

from intfar.api.config import Config
from intfar.api.meta_database import MetaDatabase
from intfar.api.youtube_api import YouTubeAPIClient, NUM_SEARCH_RESULTS
from intfar.api.util import get_closest_match
from intfar.discbot.commands.util import ADMIN_DISC_ID

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

class AudioStream:
    def __init__(self, client: VoiceClient, title: str | None, duration: float | None = None):
        self.client = client
        self.title = title
        self.duration = duration
        self.status = "Starting..."
        self.message: Message | None = None
        self.progress: float = 0.0

    def start(self, source: AudioSource):
        self.client.play(source)
        self.last_resume = time()
        self.status = "Now Playing"

class AudioHandler:
    """
    Class that handles playing sound files or audio streams from YouTube or Soundcloud
    through the Discord voice API.
    Enables the queueing of multiple sounds that will be played in order and manages
    control buttons for pausing, skipping, seeking, or stopping the playing of audio streams.
    """
    EMOJI_PREV = "⏮️"
    EMOJI_PLAY = "⏯️"
    EMOJI_STOP = "⏹️"
    EMOJI_NEXT = "⏭️"
    AUDIO_CONTROL_EMOJIS = [
        EMOJI_PREV, EMOJI_PLAY, EMOJI_STOP, EMOJI_NEXT
    ]

    def __init__(self, config: Config, meta_database: MetaDatabase):
        self.meta_database = meta_database
        self.config = config
        self.sounds_path = f"{config.static_folder}/sounds"
        self.youtube_api = YouTubeAPIClient(config)
        self.voice_streams: Dict[int, VoiceClient] = {} # Keep track of connections to voice channels
        self.audio_streams: Dict[int, AudioStream] = {} # Keep track of playing audio
        self.sound_queue = {}
        self.active_youtube_suggestions = {}
        self.youtube_suggestions_msg = {}

    async def _download_from_url(self, message: Message, url: str):
        filename = '%(title)s.mp3'
        args = ["yt-dlp", "-x", "--audio-format", "mp3", "-o", filename, "--restrict-filenames", "--print", "after_move:filepath", url]
        process = Popen(args, stdout=PIPE, stderr=PIPE, text=True)

        stdout, stderr = process.communicate()

        if not stdout or process.returncode != 0:
            # Error when downloading video with yt-dlp
            logger.bind(
                event="yt_dlp_error", stdout=stdout, stderr=stderr
            ).error(f"Error when downloading file with yt-dlp: {stderr}")

            response = (
                f"Could not play sound from the given URL. "
                "Either it's not a valid YouTube link "
                "or some network fuckery is going on"
            )
            await message.channel.send(response)

            return None, None

        filename = stdout.strip()
        title = os.path.basename(filename).split(".")[0].replace("_", " ")

        return filename, title

    def _get_sound_duration(self, sound_path: str) -> float | None:
        args = ["ffprobe", "-show_entries", "format=duration", "-v", "quiet", "-print_format", "compact=print_section=0:nokey=1:escape=csv", sound_path]
        process = Popen(args, stdout=PIPE, stderr=PIPE, text=True)

        stdout, stderr = process.communicate()
        if stdout == "" or process.returncode != 0:
            # Error when getting duration of sound with ffbrope
            logger.bind(
                event="ffprobe_error", stdout=stdout, stderr=stderr
            ).error(f"Error when getting duration of sound with ffbrope: {stderr}")

            return None

        return float(stdout.strip())

    async def _send_audio_progress_message(self, audio_stream: AudioStream, channel: TextChannel, guild_id: int):
        audio_stream.message = await channel.send(self._get_playback_str(guild_id))
        for control_button in self.AUDIO_CONTROL_EMOJIS:
            try:
                await audio_stream.message.add_reaction(control_button)
            except Exception:
                return

    async def _play_loop(self, guild_id: int, user_triggered: bool = False):
        while (sound_queue := self.sound_queue.get(guild_id, [])) != []:
            sound_name, message, sound_type = sound_queue.pop(0)
            if sound_type == "search":
                del self.active_youtube_suggestions[guild_id]
                await self.youtube_suggestions_msg[guild_id].delete()
                del self.youtube_suggestions_msg[guild_id]
                sound_type = "url"

            if sound_type == "file":
                # Stream audio from a file
                sound_path = f"{self.sounds_path}/{sound_name}.mp3"
                title = f'"{sound_name}"'
                owner_id = self.meta_database.get_sound_owner(sound_name)
                if owner_id is not None and (member := message.guild.get_member(owner_id)):
                    title += f" by {member.nick}"

                volume = 1
            else:
                sound_path, title = await self._download_from_url(message, sound_name)
                title = f'"{title}"'
                volume = 0.2

            if sound_path is None:
                continue

            try:
                # Get duration of sound
                duration = self._get_sound_duration(sound_path) if user_triggered else None
                show_status = user_triggered and (duration is None or duration > 5)

                # Create volume controlled FFMPEG player from sound file.
                audio_source = PCMVolumeTransformer(FFmpegPCMAudio(sound_path, executable="ffmpeg"), volume=volume)

                # Start the player and wait until it is done.
                voice_stream = self.voice_streams[guild_id]
                audio_stream = AudioStream(voice_stream, title, duration)
                self.audio_streams[guild_id] = audio_stream

                # Write sound status message in text channel and add sound control emojis
                if show_status:
                    asyncio.create_task(self._send_audio_progress_message(audio_stream, message.channel, guild_id))

                audio_stream.start(audio_source)

                # Play loop. Wait for sound to finish and update progress and status, if relevant
                while voice_stream.is_playing() or voice_stream.is_paused():
                    await asyncio.sleep(1)

                    if show_status and audio_stream.message is not None:
                        new_content = self._get_playback_str(guild_id)
                        if new_content != audio_stream.message.content:
                            await audio_stream.message.edit(content=new_content)

                await asyncio.sleep(0.5)

            finally:
                if sound_type == "url" and os.path.exists(sound_path):
                    os.remove(sound_path)

                if (
                    user_triggered
                    and guild_id in self.audio_streams
                    and self.audio_streams[guild_id].message is not None
                ):
                    await self.audio_streams[guild_id].message.delete()

                self.voice_streams[guild_id].stop()

        # Disconnect from voice channel.
        await self.voice_streams[guild_id].disconnect()

        # Reset the sound queue, audio stream, and voice stream for the current guild
        if guild_id in self.sound_queue:
            del self.sound_queue[guild_id]

        if guild_id in self.audio_streams:
            del self.audio_streams[guild_id]

        del self.voice_streams[guild_id]

        return True, None

    def _is_url(self, sound_name: str):
        return (
            (sound_name.startswith("http://") or sound_name.startswith("https://"))
            and "." in sound_name
        )

    async def play_sound(self, sounds, voice_state, message: Message | None = None):
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
            if self.is_valid_sound(sound):
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

            # Check if 'sound' is a sound file or a URL to a valid website
            if len(sounds) == 1:
                # Check if given sound closely matches an actual sound
                sound_match = get_closest_match(sound, [t[0] for t in self.get_sounds()])
                if sound_match is not None:
                    err_msg = f"Can't play sound `{sound}`, did you mean `{sound_match}`?"
                    return False, err_msg

                if not self._is_url(sound):
                    err_msg = (
                        f"Can't play sound `{sound}`. " +
                        f"Either provide a link to YouTube or the name of a sound.\n"
                        "Use `!sounds` for a list of available sounds.\n"
                        "Use `!search` to search for a video on YouTube."
                    )

                    return False, err_msg

            validated_sounds.append((sound, message, "url"))

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
                    if self.voice_streams.get(guild_id) is not None:
                        response = f"Adding sound to the queue..."
                    else:
                        response = f"Playing sound from the interwebz..."

                    await msg.channel.send(response)
                    if len(validated_sounds) > 1:
                        await asyncio.sleep(0.5)

            # Add sound to queue.
            if guild_id not in self.sound_queue:
                self.sound_queue[guild_id] = []

            self.sound_queue[guild_id].extend(validated_sounds)

            if guild_id not in self.voice_streams:
                self.voice_streams[guild_id] = await voice_channel.connect(timeout=5)

                success, status = await self._play_loop(guild_id, message is not None) # Play sounds in the queue.
                return success, status

            return True, None
        
        return False, "No sounds given"

    async def seek_sound(self, voice_state, ratio_or_time_str):
        # Check if user is in a voice channel.
        if voice_state is None:
            return (
                "You must be in a voice channel to jump in a sound {emote_simp_but_closeup}"
            )

        # Check if a stream is active
        guild_id = voice_state.channel.guild.id
        web_stream = self.web_streams.get(guild_id)
        if web_stream is None:
            # No active stream, do nothing
            return None

        try:
            ratio = float(ratio_or_time_str)
        except ValueError:
            split = ratio_or_time_str.split(":")
            seconds = 0
            multiplier = 1
            for time_part in reversed(split):
                try:
                    val = int(time_part)
                    seconds += (val * multiplier)
                    multiplier *= 60
                except ValueError:
                    return (
                        f"Invalid time to skip to: '{ratio_or_time_str}'"
                    )

            ratio = seconds / web_stream.duration

        if ratio < 0 or ratio > 1:
            return (
                "Error: The time to jump to is not within the bounds "
                "of the duration of the sound {emote_simp_but_closeup}"
            )

        self.web_stream_status[guild_id] = "Jumping..."
        web_stream.seek(ratio)

        await asyncio.sleep(2)

        self.web_stream_status[guild_id] = "Now Playing"

    async def skip_sound(self, voice_state):
        # Check if user is in a voice channel.
        if voice_state is None:
            err_msg = (
                "You must be in a voice channel to skip sounds {emote_simp_but_closeup}"
            )
            return err_msg

        guild_id = voice_state.channel.guild.id

        # Check if a stream is active
        if (audio_stream := self.audio_streams.get(guild_id)) is not None:
            audio_stream.status = "Skipping..."
            sound_title = "sound" if audio_stream.title is None else f"`{audio_stream.title}`"
            msg = f"Skipped {sound_title}."
            audio_stream.client.stop()
            return msg

        # No active stream, do nothing
        return None

    async def pause_sound(self, voice_state):
        # Check if user is in a voice channel.
        if voice_state is None:
            err_msg = (
                "You must be in a voice channel to pause sounds {emote_simp_but_closeup}"
            )
            return err_msg

        guild_id = voice_state.channel.guild.id

        if (audio_stream := self.audio_streams.get(guild_id)) is not None:
            pausing = audio_stream.client.is_playing()
            if pausing:
                audio_stream.status = "Pausing..."
                audio_stream.client.pause()
                audio_stream.progress += time() - audio_stream.last_resume
            else:
                audio_stream.status = "Resuming..."
                audio_stream.client.resume()
                audio_stream.last_resume = time()

            await asyncio.sleep(1)
            audio_stream.status = "Paused" if pausing else "Now Playing"

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
        if (audio_stream := self.audio_streams.get(guild_id)) is not None:
            audio_stream.status = "Stopping..."
            sound_quantifier = "sound" if len(self.sound_queue) == 1 else "sounds"
            sound_queue = self.sound_queue.get(guild_id, [])
            queue_len_str = (
                "..." if sound_queue == []
                else f" and clearing queue of **{len(sound_queue)}** other {sound_quantifier}..."
            )
            msg = f"Stopping sound{queue_len_str}"
            del self.sound_queue[guild_id]
            audio_stream.client.stop()
            return msg

        # No active stream, do nothing
        return None

    async def audio_control_pressed(self, emoji, member, channel):
        """
        Called when a user reacts to the currently active playback status message
        with a valid audio control emoji such as play, pause, stop, or skip.
        """
        if channel.guild.id in self.audio_streams and member.voice is not None:
            if emoji.name == self.EMOJI_NEXT:
                # Stop the active stream and skip to the next sound in the queue
                if (msg := await self.skip_sound(member.voice)) is not None:
                    await channel.send(msg)
            elif emoji.name == self.EMOJI_PLAY:
                # Pause or resume the active stream
                await self.pause_sound(member.voice)
            elif emoji.name == self.EMOJI_STOP:
                # Stop the active stream and empty the sound queue
                if (msg := await self.stop_sound(member.voice)) is not None:
                    await channel.send(msg)

    def get_sounds(self, ordering="newest"):
        sounds = []
        for sound, owner_id, plays, timestamp in self.meta_database.get_sounds(ordering):
            dt_fmt = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
            sounds.append((sound, owner_id, plays, dt_fmt))

        return sounds

    def is_valid_sound(self, sound):
        return self.meta_database.is_valid_sound(sound)

    def get_youtube_suggestions(self, search_term, message):
        success, suggestions = self.youtube_api.query(search_term)
        if success:
            self.active_youtube_suggestions[message.guild.id] = suggestions

        return success, suggestions

    def _get_playback_str(self, guild_id: int):
        """
        Get a string describing the status and progress of the audio stream currently
        being played. This string is posted and periodically updated by the bot in
        the text channel where the sound was started from. The status includes the
        title of the audio/video being played as well as progress and duration.
        """
        stream = self.audio_streams.get(guild_id)
        if not stream:
            return ""

        duration = None
        if stream.duration is not None:
            duration = stream.duration

        chars_per_line = 68

        # Status of playback
        now_playing = _get_padded_str(stream.status, chars_per_line)

        title = stream.title if stream.title is not None else "Unknown Sound"
        title = _get_padded_str(title, chars_per_line)

        # Get the progress in seconds of the current sound
        if stream.client.is_paused():
            progress = stream.progress
        else:
            progress = time() - stream.last_resume + stream.progress if stream.last_resume else 0

        if duration is not None and progress > duration:
            progress = duration

        # Create string describing time played vs. total duration
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
