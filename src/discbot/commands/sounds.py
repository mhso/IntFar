from datetime import datetime
import random
from typing import List

from api.util import SUPPORTED_GAMES, get_website_link
from discbot.commands.base import *

class SetEventSoundCommand(Command):
    ACCESS_LEVEL = "all"
    OPTIONAL_PARAMS = [GameParam("game"), CommandParam("sound")]

    def __init__(self, client: DiscordClient, message: Message, called_name: str, event: str):
        super().__init__(client, message, called_name)
        self.event = event

    async def handle(self, game: str, sound: str | None = None):
        database = self.client.game_databases[game]
        game_name = SUPPORTED_GAMES[game]
        response = ""
        event_fmt = "Int-Far" if self.event == "intfar" else "{emote_Doinks}"
        event_fmt = f"{event_fmt} in {game_name}"

        if sound is None: # Get current set sound for event.
            current_sound = database.get_event_sound(self.message.author.id, self.event)
            example_cmd = f"!{self.event}_sound"
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
            database.remove_event_sound(self.message.author.id, self.event)
            response = f"Removed sound from triggering when getting {event_fmt}."

        elif not self.client.audio_handler.is_valid_sound(sound):
            response = f"Invalid sound: `{sound}`. See `!sounds` for a list of valid sounds."

        else:
            database.set_event_sound(self.message.author.id, sound, self.event)
            response = (
                f"The sound `{sound}` will now play when you get {event_fmt} " +
                "{emote_poggers}"
            )

        await self.message.channel.send(self.client.insert_emotes(response))

class SetDoinkSoundCommand(SetEventSoundCommand):
    NAME = "doinks_sound"
    DESCRIPTION = "Set a sound to trigger when you are awarded Doinks in game."

    def __init__(self, client: DiscordClient, message: Message, called_name: str):
        super().__init__(client, message, called_name, "doinks")

class SetIntfarSoundCommand(SetEventSoundCommand):
    NAME = "intfar_sound"
    DESCRIPTION = "Set a sound to trigger when you are awarded Int-Far in a game."

    def __init__(self, client: DiscordClient, message: Message, called_name: str):
        super().__init__(client, message, called_name, "intfar")

class SetJoinSoundCommand(Command):
    NAME = "join_sound"
    DESCRIPTION = "Set a sound to trigger when joining a voice channel."
    ACCESS_LEVEL = "all"
    OPTIONAL_PARAMS = [CommandParam("sound")]

    async def handle(self, sound: str = None):
        response = ""

        if sound is None: # Get current set sound for joining.
            current_sound = self.client.meta_database.get_join_sound(self.message.author.id)
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
            self.client.meta_database.remove_join_sound(self.message.author.id)
            response = "Removed sound from triggering when joining a voice channel."

        elif not self.client.audio_handler.is_valid_sound(sound):
            response = f"Invalid sound: `{sound}`. See `!sounds` for a list of valid sounds."

        else:
            self.client.meta_database.set_join_sound(self.message.author.id, sound)
            response = (
                f"The sound `{sound}` will now play when you join a voice channel " +
                "{emote_poggers}"
            )

        await self.message.channel.send(self.client.insert_emotes(response))

class PlaySoundCommand(Command):
    NAME = "play"
    DESCRIPTION = "Play a sound (or a YouTube/Soundcloud link)! (See `!sounds` for a list of sounds)."
    MANDATORY_PARAMS = [CommandParam("sound")]

    async def handle(self, sound: str):
        voice_state = self.message.author.voice
        success, status = await self.client.audio_handler.play_sound(sound, voice_state, self.message)

        if success and self.client.audio_handler.is_valid_sound(sound):
            self.client.meta_database.add_sound_hit(sound, datetime.now())
        elif status is not None:
            await self.message.channel.send(self.client.insert_emotes(status))

class SeekSoundCommand(Command):
    NAME = "jump"
    DESCRIPTION = (
        "Jump to a specific point in an active YouTube/Soundcloud sound. "
        "Fx. '!jump 01:45', '!jump 1:5:34', or '!jump 30'"
    )
    MANDATORY_PARAMS = [CommandParam("time")]

    async def handle(self, time_str: str):
        voice_state = self.message.author.voice
        status = await self.client.audio_handler.seek_sound(voice_state, time_str)

        if status is not None:
            await self.message.channel.send(self.client.insert_emotes(status))

class SkipSoundCommand(Command):
    NAME = "skip"
    DESCRIPTION = "Skip an active YouTube/Soundcloud sound (if one is playing)."

    async def handle(self):
        voice_state = self.message.author.voice
        status = await self.client.audio_handler.skip_sound(voice_state)

        if status is not None:
            await self.message.channel.send(self.client.insert_emotes(status))

class StopSoundCommand(Command):
    NAME = "stop"
    DESCRIPTION = "Stop playing any active YouTube/Soundcloud sound and clear the queue of upcoming sounds"

    async def handle(self):
        voice_state = self.message.author.voice
        status = await self.client.audio_handler.stop_sound(voice_state)

        if status is not None:
            await self.message.channel.send(self.client.insert_emotes(status))

class RandomSoundCommand(Command):
    NAME = "play_random"
    DESCRIPTION = "Play a random sound. (See `!sounds` for a list of them)."

    async def handle_random_sound_msg(self):
        voice_state = self.message.author.voice

        sounds_list = self.client.audio_handler.get_sounds()
        sound = sounds_list[random.randint(0, len(sounds_list)-1)][0]

        await self.message.channel.send(f"Playing random sound: `{sound}`")

        success, status = await self.client.audio_handler.play_sound(sound, voice_state)

        if not success:
            await self.message.channel.send(self.client.insert_emotes(status))

class SearchCommand(Command):
    NAME = "search"
    DESCRIPTION = "Search for a YouTube video to play as a sound."

    async def handle_search_msg(self, search_args):
        if not search_args:
            return

        search_str = " ".join(search_args)
        success, data = self.client.audio_handler.get_youtube_suggestions(search_str, self.message)

        if not success:
            await self.message.channel.send(data)
            return

        response = f"Search results from YouTube for `{search_str}`:"
        if data == []:
            response += "\nNo results appear to be found :("
        else:
            for index, suggestion in enumerate(data, start=1):
                response += f"\n- **{index}**: `{suggestion[0]}` - by *{suggestion[1]}*"

        suggestions_msg = await self.message.channel.send(response)
        self.client.audio_handler.youtube_suggestions_msg[self.message.guild.id] = suggestions_msg

    async def parse_args(self, args: List[str]):
        return args

class SoundsCommand(Command):
    NAME = "sounds"
    DESCRIPTION = "See a list of all possible sounds to play."
    OPTIONAL_PARAMS = [CommandParam("ordering")]

    async def handle(self, ordering: str = "newest"):
        valid_orders = ["alphabetical", "oldest", "newest", "most_played", "least_played"]

        if ordering not in valid_orders:
            await self.message.channel.send(
                f"Invalid ordering: '{ordering}'. Must be one of: `{', '.join(valid_orders)}`."
            )
            return

        sounds_list = [
            f"- `{sound}` (uploaded **{timestamp}** by {self.client.get_discord_nick(owner_id, self.message.guild.id) or 'Unknown'}, **{plays}** plays)"
            for sound, owner_id, plays, timestamp in self.client.audio_handler.get_sounds(ordering)
        ]
        header = "Available sounds:"
        footer = f"Upload your own at `{get_website_link()}/soundboard`!"

        await self.client.paginate(self.message.channel, sounds_list, 0, 10, header, footer)

class BillboardCommand(Command):
    NAME = "billboard"
    DESCRIPTION = "View the hottest sounds of the last week!"

    async def handle(self):
        database = self.client.meta_database
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

        dt_start = datetime.fromtimestamp(date_start_2).strftime("%d/%m/%Y")
        dt_end = datetime.fromtimestamp(date_end_2).strftime("%d/%m/%Y")

        billboard_data = []
        for sound, plays_now, rank_now in week_new:
            if sound in week_old:
                plays_then, rank_then = week_old[sound]
                rank_shift = rank_then - rank_now
                plays_diff = plays_now - plays_then
            else:
                rank_shift = 0
                plays_diff = 0

            if len(sound) > 10:
                sound = sound[:7] + "..."

            sound_part = f"`{sound}:"
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

        if billboard_data == []:
            await self.message.channel.send(
                f"No sounds were played in between **{dt_start}** - **{dt_end}**"
            )
            return

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
        for row_index, (padding, row_data) in enumerate(zip(paddings, billboard_data), start=1):
            line = ""
            for col_index, (pad, data) in enumerate(zip(padding, row_data)):
                pad_str = " " * (pad - len(data))
                if col_index == 0:
                    line += f"{row_index}. "
                line += data + " " + pad_str

                if col_index == 2:
                    line += "` "

            formatted_data.append(line)

        header = f"The hottest hit sounds from **{dt_start}** - **{dt_end}**:"

        await self.client.paginate(self.message.channel, formatted_data, 0, chunk_size, header)
