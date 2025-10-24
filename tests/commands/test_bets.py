from time import time
import pytest

from intfar.api import betting
from intfar.api.util import SUPPORTED_GAMES
from intfar.discbot.discord_mocks import *
from tests.commands import get_games, call_command

@pytest.mark.asyncio
async def test_betting(discord_client):
    guild = discord_client.guilds[0]
    member = guild.members[0]
    channel = guild.text_channels[0]

    for game in list(SUPPORTED_GAMES) + [None]:
        channel.messages_sent = []
        game = await call_command(
            "!betting [game]",
            discord_client,
            member,
            channel,
            guild,
            2,
            game
        )

        tokens_name = discord_client.config.betting_tokens
        max_mins = betting.MAX_BETTING_THRESHOLD

        game_response = ""
        for bet in discord_client.betting_handlers[game].all_bets:
            game_response += f"\n`{bet.event_id}` - Bet on {bet.description}"

        expected_output = [
            (
                "Betting usage: `!bet [game] [amount] [event] (person)`\n"
                "This places a bet on the next (or current) match for the given game.\n"
                f"`!bet [game] all [event] (person)` bets **all** your {tokens_name} on an event!\n"
                f"You can place a bet during a game, but it has to be done before {max_mins} "
                "minutes. Betting during a game returns a lower reward, based on "
                "how much time has passed in the game.\n"
                f"**--- List of available events to bet on for {SUPPORTED_GAMES[game]} ---**"
            ),
            game_response
        ]

        assert channel.messages_sent == expected_output, "Wrong content of sent messages"

@pytest.mark.asyncio
async def test_bet_simple(discord_client):
    guild = discord_client.guilds[0]
    member = guild.members[0]
    channel = guild.text_channels[0]
    tokens_now = discord_client.config.starting_tokens

    for game in list(SUPPORTED_GAMES) + [None]:
        channel.messages_sent = []
        should_succeed = game is not None

        # Make a bet on winning a game
        game = await call_command(
            "!bet [game] 10 game_win",
            discord_client,
            member,
            channel,
            guild,
            1,
            game
        )

        if should_succeed:
            tokens_now -= 10

        game_name = SUPPORTED_GAMES[game]
        tokens_name = discord_client.config.betting_tokens

        if should_succeed:
            expected_output = (
                f"Bet succesfully placed: `winning the game` in a {game_name} game for "
                f"**10** {tokens_name}.\n"
                "The return multiplier for that event is **2**.\n"
                "You placed your bet before the game started, you will get the full reward.\n"
                "Potential winnings:\n"
                f"10 x 2 = **20** {tokens_name}"
                f"\nYour {tokens_name} balance is now `{tokens_now}`."
            )
        else:
            expected_output = (
                f"Bet was not placed: 'winning the game' - Such a bet has already been made for {game_name}!"
            )

        assert channel.messages_sent[0] == expected_output, "Wrong content of sent message"

@pytest.mark.asyncio
async def test_bet_targetted(discord_client):
    guild = discord_client.guilds[0]
    member = guild.members[0]
    channel = guild.text_channels[0]
    tokens_now = discord_client.config.starting_tokens

    for game in list(SUPPORTED_GAMES) + [None]:
        channel.messages_sent = []

        should_succeed = game is not None

        # Make a bet on winning a game
        game = await call_command(
            "!bet [game] 10 intfar Slugger",
            discord_client,
            member,
            channel,
            guild,
            1,
            game
        )

        if should_succeed:
            tokens_now -= 10

        game_name = SUPPORTED_GAMES[game]
        tokens_name = discord_client.config.betting_tokens

        if should_succeed:
            expected_output = (
                f"Bet succesfully placed: `Slugger being Int-Far` in a {game_name} game for "
                f"**10** {tokens_name}.\n"
                "The return multiplier for that event is **2**.\n"
                "You placed your bet before the game started, you will get the full reward.\n"
                "Potential winnings:\n"
                f"10 x 2 x [players_in_game] = **20** {tokens_name} (minimum)\n"
                "[players_in_game] is a multiplier. Because you bet on a specific person, "
                f"you will get more {tokens_name} if more players are in the game."
                f"\nYour {tokens_name} balance is now `{tokens_now}`."
            )
        else:
            expected_output = (
                f"Bet was not placed: 'Slugger being Int-Far' - Such a bet has already been made for {game_name}!"
            )

        assert channel.messages_sent[0] == expected_output, "Wrong content of sent message"

@pytest.mark.asyncio
async def test_bet_multi(discord_client):
    guild = discord_client.guilds[0]
    member = guild.members[0]
    channel = guild.text_channels[0]
    tokens_now = discord_client.config.starting_tokens

    for game in list(SUPPORTED_GAMES) + [None]:
        channel.messages_sent = []

        should_succeed = game is not None

        # Make a bet on winning a game
        game = await call_command(
            "!bet [game] 10 game_win & 10 doinks & 5 intfar Slugger & 5 most_kills Murt",
            discord_client,
            member,
            channel,
            guild,
            1,
            game
        )

        if should_succeed:
            tokens_now -= 30

        game_name = SUPPORTED_GAMES[game]
        tokens_name = discord_client.config.betting_tokens

        if should_succeed:
            expected_output = (
                f"Multi-bet successfully placed! "
                f"You bet on **all** the following happening in a {game_name} game:"
                f"\n- `winning the game` for **10** {tokens_name} (**2x** return)"
                f"\n- `someone being awarded doinks` for **10** {tokens_name} (**2x** return)"
                f"\n- `Slugger being Int-Far` for **5** {tokens_name} (**2x** return)"
                f"\n- `Murt getting the most kills` for **5** {tokens_name} (**1x** return)"
                f"\nThis bet uses the following ticket ID: **0**. "
                "You will need this ticket to cancel the bet.\n"
                "You placed your bet before the game started, you will get the full reward.\n"
                "Potential winnings:\n"
                f"(10 x 2 + 10 x 2 + 5 x 2 x [players_in_game] + 5 x 1 x [players_in_game]) x 4 "
                f"= **220** {tokens_name} (minimum)\n"
                "[players_in_game] is a multiplier. Because you bet on a specific person, "
                f"you will get more {tokens_name} if more players are in the game."
                f"\nYour {tokens_name} balance is now `{tokens_now}`."
            )
        else:
            expected_output = (
                f"An identical multi-bet has already been made for {SUPPORTED_GAMES[game]}!"
            )

        assert channel.messages_sent[0] == expected_output, "Wrong content of sent message"

@pytest.mark.asyncio
async def test_cancel_bet(discord_client):
    guild = discord_client.guilds[0]
    members = guild.members
    channel = guild.text_channels[0]
    tokens_now = discord_client.config.starting_tokens

    for game in list(SUPPORTED_GAMES) + [None]:
        channel.messages_sent = []
        disc_id = members[0].id

        # Add a regular bet to the database
        discord_client.game_databases[game or DEFAULT_GAME].make_bet(disc_id, guild.id, "game_win", 5, 0)
        discord_client.meta_database.update_token_balance(disc_id, 5, False)

        # Cancel the bet
        game = await call_command(
            "!cancel_bet game_win [game]",
            discord_client,
            members[0],
            channel,
            guild,
            1,
            game,
        )

        game_name = SUPPORTED_GAMES[game]
        tokens_name = discord_client.config.betting_tokens

        expected_output = (
            f"Bet on `winning the game` in a {game_name} game for "
            f"**5** {tokens_name} successfully cancelled.\n"
            f"Your {tokens_name} balance is now `{tokens_now}`."
        )

        assert channel.messages_sent[0] == expected_output, "Wrong content of sent message"

        # Add a multi-bet to the database
        ticket = discord_client.game_databases[game or DEFAULT_GAME].generate_ticket_id(disc_id)
        events = [("game_win", 5, None), ("doinks", 5, members[1].id)]
        for event, amount, target in events:
            discord_client.game_databases[game or DEFAULT_GAME].make_bet(disc_id, guild.id, event, amount, 0, target, ticket)
            discord_client.meta_database.update_token_balance(disc_id, 5, False)

        # Cancel the bet
        game = await call_command(
            f"!cancel_bet {ticket} [game]",
            discord_client,
            members[0],
            channel,
            guild,
            2,
            game,
        )

        game_name = SUPPORTED_GAMES[game]
        tokens_name = discord_client.config.betting_tokens

        expected_output = (
            f"Multi-bet for {game_name} with "
            f"ticket ID **{ticket}** successfully cancelled.\n"
            f"Your {tokens_name} balance is now `{tokens_now}`."
        )

        assert channel.messages_sent[1] == expected_output, "Wrong content of sent message"

@pytest.mark.asyncio
async def test_active_bets(discord_client):
    guild = discord_client.guilds[0]
    members = guild.members
    channel = guild.text_channels[0]

    for game in SUPPORTED_GAMES:
        channel.messages_sent = []
        disc_id = members[0].id

        game = await call_command(
            "!active_bets [game]",
            discord_client,
            members[0],
            channel,
            guild,
            1,
            game,
        )

        game_database = discord_client.game_databases[game]
        game_name = SUPPORTED_GAMES[game]
        tokens_name = discord_client.config.betting_tokens

        expected_output = (
            f"Bets for **{game_name}**:\n"
            "Say wat has no active bets."
        )
        assert channel.messages_sent[0] == expected_output, "Wrong content of sent message"

        # Create some bets
        game_database.make_bet(disc_id, guild.id, "game_win", 5, 0)

        ticket = game_database.generate_ticket_id(disc_id)
        events = [("game_win", 5, None), ("doinks", 5, members[1].id)]
        for event, amount, target in events:
            game_database.make_bet(disc_id, guild.id, event, amount, 0, target, ticket)
            discord_client.meta_database.update_token_balance(disc_id, amount, False)

        game = await call_command(
            "!active_bets [game]",
            discord_client,
            members[0],
            channel,
            guild,
            2,
            game,
        )

        expected_output = (
            f"Bets for **{game_name}**:\n"
            "Say wat has the following active bets:\n"
            f"=== In **{guild.name}** ===\n"
            f"- `winning the game` for **5** {tokens_name}\n"
            f"- Multi-bet (ticket = {ticket}): `winning the game` & `Slugger being awarded doinks` for **10** {tokens_name}"
        )
        assert channel.messages_sent[1] == expected_output, "Wrong content of sent message"

        with game_database:
            game_database.execute_query("DELETE FROM bets")

@pytest.mark.asyncio
async def test_all_bets(discord_client):
    guild = discord_client.guilds[0]
    members = guild.members
    channel = guild.text_channels[0]

    for game in get_games():
        channel.messages_sent = []
        disc_id_1 = members[0].id
        disc_id_2 = members[1].id

        game = await call_command(
            "!bets [game]",
            discord_client,
            members[0],
            channel,
            guild,
            1,
            game,
        )

        game_database = discord_client.game_databases[game]
        game_name = SUPPORTED_GAMES[game]
        tokens_name = discord_client.config.betting_tokens

        expected_output = "Say wat has not won or lost any bets yet!"
        assert channel.messages_sent[0] == expected_output, "Wrong content of sent message"

        # Create some bets
        ticket = game_database.generate_ticket_id(disc_id_2)
        events = [("game_win", 5, None), ("doinks", 10, members[1].id)]
        for event, amount, target in events:
            bet_id = game_database.make_bet(disc_id_2, guild.id, event, amount, 0, target, ticket)
            discord_client.meta_database.update_token_balance(disc_id_2, amount, False)
            game_database.mark_bet_as_resolved(bet_id, 1, time(), True, 100)

        discord_client.meta_database.update_token_balance(disc_id_2, 100, True)

        game = await call_command(
            "!bets [game] Slugger",
            discord_client,
            members[0],
            channel,
            guild,
            2,
            game,
        )

        expected_output = (
            f"Slugger has made a total of **1** bets for **{game_name}**.\n"
            "- Bets won: **1 (100%)**\n"
            f"- Average amount of {tokens_name} wagered: **15**\n"
            f"- Total {tokens_name} wagered: **15**\n"
            f"- Total {tokens_name} won: **100**\n"
            "- Bet made the most often: `winning the game` (made **1** times)\n"
            "- Bets that targeted a person: **1 (100%)**\n"
            "- Bets made during a game: **0 (0%)**"
        )
        assert channel.messages_sent[1] == expected_output, "Wrong content of sent message"

        # Create some more bets
        bet_id = game_database.make_bet(disc_id_1, guild.id, "game_loss", 25, 0.5)
        discord_client.meta_database.update_token_balance(disc_id_1, 25, False)
        game_database.mark_bet_as_resolved(bet_id, 2, time(), False, 25)

        game = await call_command(
            "!bets [game]",
            discord_client,
            members[0],
            channel,
            guild,
            3,
            game,
        )

        expected_output = (
            f"Say wat has made a total of **1** bets for **{game_name}**.\n"
            "- Bets won: **0 (0%)**\n"
            f"- Average amount of {tokens_name} wagered: **25**\n"
            f"- Total {tokens_name} wagered: **25**\n"
            f"- Total {tokens_name} won: **0**\n"
            "- Bet made the most often: `losing the game` (made **1** times)\n"
            "- Bets that targeted a person: **0 (0%)**\n"
            "- Bets made during a game: **1 (100%)**"
        )
        assert channel.messages_sent[2] == expected_output, "Wrong content of sent message"

        with game_database:
            game_database.execute_query("DELETE FROM bets")

@pytest.mark.asyncio
async def test_token_balance(discord_client):
    guild = discord_client.guilds[0]
    member = guild.members[0]
    channel = guild.text_channels[0]

    tokens_name = discord_client.config.betting_tokens
    tokens_now = discord_client.config.starting_tokens

    await call_command(
        "!gbp",
        discord_client,
        member,
        channel,
        guild,
        1,
    )

    expected_output = f"Say wat has **{tokens_now}** {tokens_name}"

    assert channel.messages_sent[0] == expected_output, "Wrong content of sent messages"

    await call_command(
        "!gbp all",
        discord_client,
        member,
        channel,
        guild,
        2
    )

    expected_output = (
        f"Say wat has **{tokens_now}** {tokens_name}\n"
        f"Slugger has **{tokens_now}** {tokens_name}\n"
        f"Murt has **{tokens_now}** {tokens_name}\n"
        f"Eddie Smurphy has **{tokens_now}** {tokens_name}\n"
        f"Nønø has **{tokens_now}** {tokens_name}\n"
        f"Zikzak has **{tokens_now}** {tokens_name}"
    )

    assert channel.messages_sent[1] == expected_output, "Wrong content of sent messages"

@pytest.mark.asyncio
async def test_bet_return(discord_client):
    guild = discord_client.guilds[0]
    member = guild.members[0]
    channel = guild.text_channels[0]

    for game in get_games():
        channel.messages_sent = []

        await call_command(
            "!bet_return bleh [game]",
            discord_client,
            member,
            channel,
            guild,
            1,
            game
        )

        expected_output = "Invalid event to bet on: 'bleh'."

        assert channel.messages_sent[0] == expected_output, "Wrong content of sent messages"

        await call_command(
            "!bet_return game_win [game]",
            discord_client,
            member,
            channel,
            guild,
            2,
            game
        )

        expected_output = (
            "Betting on `winning the game` would return **2** times your investment.\n"
            "If you bet after the game has started, the return will be lower.\n"
        )

        assert channel.messages_sent[1] == expected_output, "Wrong content of sent messages"

        await call_command(
            "!bet_return doinks [game]",
            discord_client,
            member,
            channel,
            guild,
            3,
            game
        )

        expected_output = (
            "Betting on `someone being awarded doinks` would return **2** times your investment.\n"
            "If you bet after the game has started, the return will be lower.\n"
            "If you bet on this event happening to a *specific* person "
            "(not just *anyone*), then the return will be further multiplied "
            "by how many people are in the game."
        )

        assert channel.messages_sent[2] == expected_output, "Wrong content of sent messages"

        await call_command(
            "!bet_return intfar [game] Slugger",
            discord_client,
            member,
            channel,
            guild,
            4,
            game
        )

        expected_output = (
            f"Betting on `Slugger being Int-Far` would return **2** times your investment.\n"
            "If you bet after the game has started, the return will be lower.\n"
            "Since you bet on this event happening to a *specific* person "
            "(not just *anyone*), then the return will be further multiplied "
            "by how many people are in the game."
        )

        assert channel.messages_sent[3] == expected_output, "Wrong content of sent messages"
