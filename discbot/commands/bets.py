from asyncio import sleep
import api.util as api_util
from api import betting
from discbot.commands import util as commands_util
from discbot.commands.meta import handle_usage_msg

async def handle_betting_msg(client, message):
    max_mins = betting.MAX_BETTING_THRESHOLD
    tokens_name = client.config.betting_tokens
    response = "Betting usage: `!bet [game] [amount] [event] (person)`\n"
    response += "This places a bet on the next (or current) match for the given game.\n"
    response += f"`!bet [game] all [event] (person)` bets **all** your {tokens_name} on an event!\n"
    response += f"You can place a bet during a game, but it has to be done before {max_mins} "
    response += "minutes. Betting during a game returns a lower reward, based on "
    response += "how much time has passed in the game.\n"
    response += "**--- List of available events to bet on ---**"
    await message.channel.send(response)

    for game in api_util.SUPPORTED_GAMES:
        game_response = f"\n\nFor **{api_util.SUPPORTED_GAMES[game]}**:"
        for bet in client.betting_handlers[game].all_bets:
            game_response += f"\n`{bet.event_id}` - Bet on {bet.description}"

        await sleep(0.5)
        await message.channel.send(game_response)

def get_bet_params(client, args):
    amounts = []
    events = []
    targets = []

    if len(args) == 0:
        return [None, [], [], []]

    game = args[0]
    if game not in api_util.SUPPORTED_GAMES:
        game = client.meta_database.DEFAULT_GAME
        index = 0
    else:
        index = 1

    while index < len(args):
        event = args[index+1]
        amount = args[index]
        if "&" in (event, amount):
            raise ValueError("Multi-bet input is formatted incorrectly!")

        target = None
        if index + 2 < len(args) and args[index+2] != "&":
            try:
                end_index = args.index("&", index)
            except ValueError:
                end_index = len(args)
            target = commands_util.extract_target_name(args, index+2, end_index)
            index = end_index + 1
        else:
            index += 3

        amounts.append(amount)
        events.append(event)
        targets.append(target)

    return [game, amounts, events, targets]

async def handle_make_bet_msg(client, message, game, amounts, events, targets):
    if events == [] or amounts == [] or None in amounts or None in events:
        await handle_usage_msg(client, message, "bet")
        return

    target_ids = []
    target_names = []

    for target_name in targets:
        target_id = None
        discord_name = None

        if target_name is not None: # Bet on a specific person doing a thing.
            if target_name == "me":
                target_id = message.author.id
            else:
                target_name = target_name.lower()
                target_id = client.try_get_user_data(target_name.strip(), message.guild.id)

                if target_id is None:
                    msg = "Error: Invalid summoner or Discord name "
                    msg += f"{client.get_emoji_by_name('PepeHands')}"
                    await message.channel.send(msg)
                    return
    
            discord_name = client.get_discord_nick(target_id, message.guild.id)

        target_ids.append(target_id)
        target_names.append(discord_name)

    with client.meta_database:
        response = client.betting_handlers[game].place_bet(
            message.author.id,
            message.guild.id,
            amounts,
            client.get_game_start(game, message.guild.id),
            events,
            target_ids,
            target_names
        )[1]

    await message.channel.send(response)

async def handle_cancel_bet_msg(client, message, betting_event, game, target_id=None):
    target_name = (
        None if target_id is None
        else client.get_discord_nick(target_id, message.guild.id)
    )

    response = client.betting_handlers[game].cancel_bet(
        message.author.id,
        message.guild.id,
        betting_event,
        client.get_game_start(game, message.guild.id),
        target_id,
        target_name
    )[1]

    await message.channel.send(response)

async def handle_give_tokens_msg(client, message, amount, target_id):
    target_name = client.get_discord_nick(target_id, message.guild.id)

    max_tokens_before, max_tokens_holder = client.meta_database.get_max_tokens_details()

    response = client.betting_handlers["lol"].give_tokens(
        message.author.id, amount, target_id, target_name
    )[1]

    balance_after = client.meta_database.get_token_balance(target_id)

    if balance_after > max_tokens_before and target_id != max_tokens_holder:
        # This person now has the most tokens of all users!
        tokens_name = client.config.betting_tokens
        response += f"\n{target_name} now has the most {tokens_name} of everyone! "
        await client.assign_top_tokens_role(max_tokens_holder, target_id)

    await message.channel.send(response)

async def handle_active_bets_msg(client, message, game, target_id):
    def get_bet_description(game, disc_id, single_person=True):
        active_bets = client.meta_database.get_bets(game, True, disc_id)
        recepient = client.get_discord_nick(disc_id, message.guild.id)

        response = ""
        if active_bets is None:
            if single_person:
                response = f"{recepient} has no active bets."
            else:
                response = None
        else:
            tokens_name = client.config.betting_tokens
            response = f"{recepient} has the following active bets:"
            bets_by_guild = {guild_id: [] for guild_id in api_util.GUILD_IDS}
            for bet_data in active_bets:
                bets_by_guild[bet_data[1]].append(bet_data)

            for guild_id in bets_by_guild:
                guild_bets = bets_by_guild[guild_id]
                if guild_bets != []:
                    guild_name = client.get_guild_name(guild_id)
                    response += f"\n=== In **{guild_name}** ==="

                for _, guild_id, _, amounts, events, targets, _, ticket, _ in guild_bets:
                    bets_str = "\n - "
                    total_cost = 0
                    if len(amounts) > 1:
                        bets_str += f"Multi-bet (ticket = {ticket}): "
                    for index, (amount, event, target) in enumerate(zip(amounts, events, targets)):
                        person = None
                        if target is not None:
                            person = client.get_discord_nick(target, message.guild.id)

                        bet_desc = client.betting_handlers[game].get_dynamic_bet_desc(event, person)
                        bets_str += f"`{bet_desc}`"
                        if index != len(amounts) - 1:
                            bets_str += " & "

                        total_cost += amount

                    bets_str += f" for {total_cost} {tokens_name}"

                    response += bets_str

        return response

    response = ""

    games_to_check = [game] if game is not None else api_util.SUPPORTED_GAMES
    for game in games_to_check:
        game_response = f"Bets for **{api_util.SUPPORTED_GAMES[game]}**:\n"
        if target_id is None:
            # Check active bets for everyone
            any_bet = False
            for disc_id in client.game_databases[game].game_users.keys():
                bets_for_person = get_bet_description(game, disc_id, False)
                if bets_for_person is not None:
                    if any_bet:
                        bets_for_person = "\n" + bets_for_person
                    game_response += bets_for_person
                    any_bet = True

            if any_bet:
                if response != "":
                    game_response = "\n" + game_response

                response += game_response

        else:
            # Check active bets for a single person
            game_response += get_bet_description(game, target_id)
            if response != "":
                game_response = "\n" + game_response

            response += game_response

    if target_id is None and response == "":
        response = "No one has any active bets."

    await message.channel.send(response)

async def handle_all_bets_msg(client, message, game, target_id):
    game_name = api_util.SUPPORTED_GAMES[game]
    all_bets = client.meta_database.get_bets(game, False, target_id)
    tokens_name = client.config.betting_tokens
    bets_won = 0
    had_target = 0
    during_game = 0
    spent = 0
    most_often_event = 0
    max_event_count = 0
    winnings = 0
    betting_descs = {bet.event_id: bet.description for bet in client.betting_handlers[game].all_bets}
    event_counts = {event_id: 0 for event_id in betting_descs}

    target_name = client.get_discord_nick(target_id, message.guild.id)

    if all_bets is None:
        response = f"{target_name} has not won or lost any bets yet!"
    else:
        for _, _, _, amounts, events, targets, game_time, result, payout in all_bets:
            for amount, event_id, target in zip(amounts, events, targets):
                spent += amount
                event_counts[event_id] += 1
                if event_counts[event_id] > max_event_count:
                    max_event_count = event_counts[event_id]
                    most_often_event = event_id
                if target is not None:
                    had_target += 1

            if result == 1:
                bets_won += 1
                winnings += payout if payout is not None else 0
            if game_time > 0:
                during_game += 1

        average_amount = int(spent / len(all_bets))
        pct_won = int((bets_won / len(all_bets)) * 100)
        pct_target = int((had_target / len(all_bets)) * 100)
        pct_during = int((during_game / len(all_bets)) * 100)
        event_desc = betting_descs[most_often_event]

        response = f"{target_name} has made a total of **{len(all_bets)}** bets for **{game_name}**.\n"
        response += f"- Bets won: **{bets_won} ({pct_won}%)**\n"
        response += f"- Average amount of {tokens_name} wagered: **{api_util.format_tokens_amount(average_amount)}**\n"
        response += f"- Total {tokens_name} wagered: **{api_util.format_tokens_amount(spent)}**\n"
        response += f"- Total {tokens_name} won: **{api_util.format_tokens_amount(winnings)}**\n"
        response += f"- Bet made the most often: `{event_desc}` (made **{max_event_count}** times)\n"
        response += f"- Bets that targeted a person: **{had_target} ({pct_target}%)**\n"
        response += f"- Bets made during a game: **{during_game} ({pct_during}%)**"

    await message.channel.send(response)

async def handle_token_balance_msg(client, message, target_id):
    def get_token_balance(disc_id):
        name = client.get_discord_nick(disc_id, message.guild.id)
        balance = client.meta_database.get_token_balance(disc_id)
        return balance, name

    tokens_name = client.config.betting_tokens

    response = ""
    if target_id is None: # Get betting balance for all.
        balances = []
        for disc_id in client.meta_database.all_users:
            balance, name = get_token_balance(disc_id)
            balances.append((balance, name))

        balances.sort(key=lambda x: x[0], reverse=True)

        for balance, name in balances:
            response += f"\n{name} has **{api_util.format_tokens_amount(balance)}** {tokens_name}"
    else:
        balance, name = get_token_balance(target_id)
        response = f"\n{name} has **{api_util.format_tokens_amount(balance)}** {tokens_name}"

    await message.channel.send(response)

async def handle_bet_return_msg(client, message, betting_event, game, target_id=None):
    target_name = (
        None if target_id is None
        else client.get_discord_nick(target_id, message.guild.id)
    )

    response = client.betting_handlers[game].get_bet_return_desc(betting_event, target_id, target_name)
    await message.channel.send(response)
