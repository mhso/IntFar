from datetime import datetime

import api.util as api_util
from api.awards import get_intfar_reasons
from api.register import register_for_game
import discbot.commands.util as commands_util

async def handle_register_msg(client, message, game, username, *extra_args):
    disc_id = message.author.id
    status_code, status_msg = register_for_game(client.database, client.api_clients[game], disc_id, username, *extra_args)

    if status_code > 0:
        users_in_voice = client.get_users_in_voice()
        for guild_id in users_in_voice:
            for disc_id in users_in_voice[guild_id][game]:
                if message.author.id == disc_id: # User is already in voice channel.
                    await client.user_joined_voice(disc_id, guild_id)
                    break

    await message.channel.send(client.insert_emotes(status_msg))

async def handle_unregister_msg(client, message, game):
    user_in_game = False
    for guild_id in api_util.GUILD_IDS:
        users_in_game = client.get_users_in_game(game, guild_id) or []
        for disc_id in users_in_game:
            # If user is in game, unregistration is not allowed.
            if disc_id == message.author.id:
                user_in_game = True
                break

    if user_in_game:
        response = (
            "You can't unregister in the middle of a game " +
            "(that would be cheating {emote_im_nat_kda_player_yo})"
        )
    else:
        client.database.remove_user(game, message.author.id)
        game_name = api_util.SUPPORTED_GAMES[game]
        response = (
            f"You are no longer registered to the Int-Far™ Tracker™ for {game_name} " + "{emote_sadge} " +
            "Your games are no longer being tracked and your stats will not be shown. " +
            "However, your data has not been deleted and you can register again at any time."
        )

    await message.channel.send(client.insert_emotes(response))

async def handle_users_msg(client, message, game=None):
    response = ""
    games = api_util.SUPPORTED_GAMES if game is None else [game]
    for game in games:
        game_response = ""
        game_name = api_util.SUPPORTED_GAMES[game]
        for disc_id in client.database.users_by_game[game].keys():
            formatted_names = ", ".join(client.database.users_by_game[game][disc_id].ingame_name)
            nickname = client.get_discord_nick(disc_id, message.guild.id)
            game_response += f"\n- {nickname} ({formatted_names})"

        if game_response == "":
            if response != "":
                response += "\n\n"

            response += (
                f"**No lads are currently signed up for {game_name} "
                "{emote_nat_really_fine} but you can change this!!**"
            )
        else:
            response += f"\n\n**--- Registered bois for {game_name} ---**" + game_response

    await message.channel.send(client.insert_emotes(response))

async def handle_helper_msg(client, message):
    """
    Write the helper message to Discord.
    """
    game_names = list(api_util.SUPPORTED_GAMES.values())
    before_and = ", ".join(game_names[:-1])
    after_and = game_names[-1]
    games_desc = f"{before_and} and {after_and}"

    response = "I gotchu fam {emote_nazi}\n"
    response += "The Int-Far™ Tracker™ is a highly sophisticated bot "
    response += f"that watches when people in this server plays {games_desc}, "
    response += "and judges them harshly if they suck too hard {emote_simp_but_closeup}\n"
    response += "- Write `!commands` to see a list of available commands, and their usages\n"
    response += "- Write `!stats` to see a list of available stats to check\n"
    response += "- Write `!betting` to see a list of events to bet on and how to do so"

    await message.channel.send(client.insert_emotes(response))

async def handle_commands_msg(client, message):
    header = "**--- Valid commands, and their usages, are listed below ---**"
    lines = []
    for cmd in commands_util.COMMANDS:
        cmd_obj = commands_util.COMMANDS[cmd]
        if message.guild.id in cmd_obj.guilds:
            cmd_str = f"`{cmd_obj}` - {cmd_obj.desc}"
            lines.append(cmd_str)

    await client.paginate(message.channel, lines, 0, 7, header)

async def handle_usage_msg(client, message, command):
    valid_cmd, show_usage = commands_util.valid_command(message, command, None)
    if not valid_cmd and not show_usage:
        await message.channel.send(f"Not a valid command: '{command}'.")
        return

    # Get main command (if it is an alias)
    cmd_obj = commands_util.get_main_command(command)
    response = f"Usage: `{cmd_obj}`\n"
    response += cmd_obj.desc

    if cmd_obj.access_level is not None:
        response += "\n\n*Note: This command requires you to be registered to Int-Far"

        if cmd_obj.access_level == "self":
            response += ", if targetted at yourself."
        elif cmd_obj.access_level == "all":
            response += "."
        response += "*"

    await message.channel.send(response)

def get_uptime(dt_init):
    dt_now = datetime.now()
    return api_util.format_duration(dt_init, dt_now)

async def handle_uptime_msg(client, message):
    uptime_formatted = get_uptime(client.time_initialized)
    await message.channel.send(f"Int-Far™ Tracker™ has been online for {uptime_formatted}")

async def handle_status_msg(client, message, game):
    """
    Gather meta stats about Int-Far and write them to Discord.
    """
    response = f"**Uptime:** {get_uptime(client.time_initialized)}\n"

    (
        games, earliest_game, games_won, unique_game_guilds,
        longest_game_duration,
        longest_game_time, users, doinks_games,
        total_doinks, intfars, games_ratios,
        intfar_ratios, intfar_multi_ratios
    ) = client.database.get_meta_stats(game)

    pct_games_won = (games_won / games) * 100

    longest_game_start = datetime.fromtimestamp(longest_game_time)
    longest_game_end = datetime.fromtimestamp(longest_game_time + longest_game_duration)
    longest_game_fmt = api_util.format_duration(longest_game_start, longest_game_end)
    longest_game_date = datetime.fromtimestamp(longest_game_time).strftime("%Y-%m-%d")

    sounds = client.audio_handler.get_sounds("alphabetical")
    unique_owners = set(client.audio_handler.get_sound_owners().values())

    pct_intfar = int((intfars / games) * 100)
    pct_doinks = int((doinks_games / games) * 100)
    earliest_time = datetime.fromtimestamp(earliest_game).strftime("%Y-%m-%d")
    doinks_emote = client.insert_emotes("{emote_Doinks}")
    all_bets = client.database.get_bets(game, False)

    tokens_name = client.config.betting_tokens
    bets_won = 0
    total_bets = 0
    total_amount = 0
    total_payout = 0
    highest_payout = 0
    highest_payout_user = None
    unique_guilds = set()

    for disc_id in all_bets:
        bet_data = all_bets[disc_id]
        total_bets += len(bet_data)
        for _, guild_id, _, amounts, _, _, _, result, payout in bet_data:
            for amount in amounts:
                total_amount += amount

            unique_guilds.add(guild_id)

            if payout is not None:
                if payout > highest_payout:
                    highest_payout = payout
                    highest_payout_user = disc_id

                total_payout += payout

            if result == 1:
                bets_won += 1

    pct_bets_won = int((bets_won / total_bets) * 100)
    highest_payout_name = client.get_discord_nick(highest_payout_user, message.guild.id)

    intfar_reasons = get_intfar_reasons(game).values()

    reason_ratio_msg = "\n".join(f"- **{count:.1f}%** were for {reason}" for count, reason in zip(intfar_ratios, intfar_reasons))
    count_literals = ["one", "two", "three", "four", "five", "six", "seven", "eight"]
    def multi_criterias_msg(index, max_count):
        if index == 1:
            quantifier = f"met just {count_literals[index-1]} criteria"
        elif index == max_count:
            quantifier = f"swept and met all {count_literals[index-1]} criterias"
        else:
            quantifier = f"met {count_literals[index-1]} criterias"

        return f"- **{intfar_multi_ratios[index-1]:.1f}%** of Int-Fars {quantifier}"

    reason_multi_ratio_msg = "\n".join(multi_criterias_msg(index, len(intfar_multi_ratios)) for index in range(1, len(intfar_multi_ratios)+1))

    response += (
        f"--- Since **{earliest_time}** ---\n"
        f"- **{games}** games of **{api_util.SUPPORTED_GAMES[game]}** have been played in {unique_game_guilds} servers (**{pct_games_won:.1f}%** was won)\n"
        f"- Longest game lasted **{longest_game_fmt}**, played on {longest_game_date}\n"
        f"- **{users}** users have signed up for this game\n"
        f"- **{intfars}** Int-Far awards have been given\n"
        f"- **{total_doinks}** {doinks_emote} have been earned\n"
        f"- **{len(sounds)}** sounds have been uploaded by **{len(unique_owners)}** people\n"
        f"- **{total_bets}** bets have been made (**{pct_bets_won}%** was won)\n"
        f"- Bets were made in **{len(unique_guilds)}** different servers\n"
        f"- **{api_util.format_tokens_amount(total_amount)}** {tokens_name} have been spent on bets\n"
        f"- **{api_util.format_tokens_amount(total_payout)}** {tokens_name} have been won from bets\n"
        f"- **{api_util.format_tokens_amount(highest_payout)}** {tokens_name} was the biggest single win, by **{highest_payout_name}**\n"
        "--- Of all games played ---\n"
        f"- **{pct_intfar}%** resulted in someone being Int-Far\n"
        f"- **{pct_doinks}%** resulted in {doinks_emote} being handed out\n"
        f"- **{games_ratios[0]}%** were as a duo\n"
        f"- **{games_ratios[1]}%** were as a three-man\n"
        f"- **{games_ratios[2]}%** were as a four-man\n"
        f"- **{games_ratios[3]}%** were as a five-man stack\n"
        "--- When Int-Fars were earned ---\n"
        f"{reason_ratio_msg}\n"
        f"{reason_multi_ratio_msg}"
    )

    await message.channel.send(response)

async def handle_website_msg(client, message):
    response = (
        "Check out the amazing Int-Far website {emote_smol_gual}\n" +
        f"{api_util.get_website_link()}\n" +
        "Write `!website_verify` to sign in to the website, " +
        "allowing you to create bets, see stats, upload sounds, and more! "
        "You can also more easily sign up for CS2 here!"
    )

    await message.channel.send(client.insert_emotes(response))

async def handle_profile_msg(client, message, game, target_id=None):
    target_name = client.get_discord_nick(target_id, message.guild.id)

    response = f"URL to {target_name}'s Int-Far profile for {api_util.SUPPORTED_GAMES[game]}:\n"
    response += f"{api_util.get_website_link(game)}/user/{target_id}"

    await message.channel.send(response)

async def handle_verify_msg(client, message):
    """
    Handler for 'website_verify' command. Generates a unique URL that when accessed
    verifies a user and allows them to interact with the Int-Far website. This URL is
    then sent via. a Discord DM to the invoker of the command.
    """
    client_secret = client.database.get_client_secret(message.author.id)
    url = f"{api_util.get_website_link()}/verify/{client_secret}"
    response_dm = "Go to this link to verify yourself (totally not a virus):\n"
    response_dm += url + "\n"
    response_dm += "This will enable you to interact with the Int-Far bot from "
    response_dm += "the website, fx. to see stats or place bets.\n"
    response_dm += "To log in to a new device (phone fx.), simply use the above link again.\n"
    response_dm += "Don't show this link to anyone, or they will be able to log in as you!"

    mention = client.get_mention_str(message.author.id, message.guild.id)
    response_server = (
        f"Psst, {mention}, I sent you a DM with a secret link, "
        "where you can sign up for the website {emote_peberno}"
    )

    await message.channel.send(client.insert_emotes(response_server))

    # Send DM to the user
    dm_sent = await client.send_dm(response_dm, message.author.id)
    if not dm_sent:
        await message.channel.send(
            "Error: DM Message could not be sent for some reason ;( Try again!"
        )

async def handle_default_game_msg(client, message, game=None):
    if game is None:
        game = client.database.all_users[message.author.id].default_game
        game_name = api_util.SUPPORTED_GAMES[game]
        response = f"Your default game is *{game_name}*"

    else:
        client.database.set_default_game(message.author.id, game)
        game_name = api_util.SUPPORTED_GAMES[game]
        response = f"Your default game is now set to *{game_name}*"

    await message.channel.send(response)
