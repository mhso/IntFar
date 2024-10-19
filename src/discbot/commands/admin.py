from discbot.commands.base import *

class KickCommand(Command):
    NAME = "kick"
    DESCRIPTION = "Kick a player from Int-Far FOREVER AFTER!"
    MANDATORY_PARAMS = [TargetParam("person")]
    COMMANDS_DICT = commands_util.ADMIN_COMMANDS

    async def handle(self, target_id: int):
        target_name = self.client.get_discord_nick(target_id, self.message.guild.id)

        response = f"{target_name} has been kicked from Int-Far "
        response += "for being a bad boi!\nHis data will be WIPED "
        response += "and he will forever live in shame {emote_im_nat_kda_player_yo}"

        await self.message.channel.send(self.client.insert_emotes(response))

class RestartCommand(Command):
    NAME = "restart"
    DESCRIPTION = "Restart the Int-Far master process and reload code."
    COMMANDS_DICT = commands_util.ADMIN_COMMANDS

    async def handle(self):
        await self.message.channel.send("Restarting Int-Far...")

        # Exit code is caught by main process.
        exit(2)
